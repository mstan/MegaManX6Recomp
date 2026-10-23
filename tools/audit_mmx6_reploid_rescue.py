#!/usr/bin/env python3
"""Read-only original-source Reploid audit; emits metadata, never game bytes.

No launcher, RAM/success writes, cards, gameplay qualification or live ledger.
Only the existing bounded EXE/BIN inventory extents are read from a raw disc.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import ntpath
from pathlib import Path
import re
import struct

from inventory_mmx6_coop_content import (BIN_SHA256, EXE_SHA256, Executable,
    OVERLAY_BASE, OVERLAY_SELECTOR, RawDisc, archive_members, placement_list)

INVENTORY_SHA = "67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad"
PLAY, POOL, POOL_END, STRIDE = 0x800CCED0, 0x800C1220, 0x800C4560, 0xA4
REWARDS, REPORT_MEMBER = 0x8006D674, 20
REPORT_SHA = "353abfee70d0d12cbdc32d620c5482e15ff26a603e4af58b5d341071ca78a956"
STATE_NAMES = {0: "unrescued", 2: "rescued", 3: "dead", 4: "missing_or_infected_loss"}
EXE_WINDOWS = (
    ("overlap", 0x8002DCF4, 0x8002DE54),
    ("shared_actor_allocator", 0x8002C4C4, 0x8002C530),
    ("actor_clear", 0x8002C9B0, 0x8002C9D4),
    ("origin_rearm_and_clear", 0x8002CA54, 0x8002CAB4),
    ("reploid_init", 0x8004E800, 0x8004EA78),
    ("waiting_and_rescue_before_infection", 0x8004EA78, 0x8004EC30),
    ("delayed_heal", 0x8004EC30, 0x8004ED4C),
    ("heal_setup_and_tanks", 0x8004ED4C, 0x8004EECC),
    ("rescue_contact", 0x8004EECC, 0x8004EFD0),
    ("reploid_dispatch", 0x8004F834, 0x8004F880),
    ("heal_dispatch", 0x8004F880, 0x8004F8A0),
    ("rescued_animation", 0x8004F8C0, 0x8004F9A0),
    ("escape_delay", 0x8004F9A0, 0x8004FAD0),
    ("escape_and_despawn", 0x8004FAD0, 0x8004FB40),
    ("waiting_offscreen_cleanup", 0x8004FB40, 0x8004FB60),
    ("infected_damage_contact_and_loss", 0x8004FB60, 0x8004FC40),
    ("infected_setup", 0x8004FC40, 0x8004FD58),
    ("infected_attack_delay", 0x8004FD58, 0x8004FE50),
    ("heal_freeze", 0x8004FE58, 0x8004FE8C),
    ("facing_resident_player", 0x8004FE8C, 0x8004FF00),
    ("found_setter", 0x8004FF00, 0x8004FF4C),
    ("found_getter", 0x8004FF4C, 0x8004FF7C),
    ("message_effect_allocator", 0x8004FF7C, 0x8004FFF8),
    ("nightmare_infection_approach", 0x80040CB0, 0x80040E3C),
    ("nightmare_infection_contact", 0x80040E3C, 0x80040FB4),
    ("nightmare_consumed_bookkeeping", 0x80042D3C, 0x80042D98),
    ("nightmare_select_reploid", 0x80042D98, 0x80042E68),
    ("nightmare_validate_reploid", 0x80042E68, 0x80042EB4),
    ("new_game_found_copy", 0x8001E088, 0x8001E1BC),
    ("mission_entry_backup", 0x8001E914, 0x8001E9EC),
    ("native_save_payload_unpack", 0x8001BA1C, 0x8001BD40),
    ("native_save_payload_pack", 0x8001BD40, 0x8001C024),
    ("rescued_count_display", 0x80018F98, 0x800190FC),
)
REPORT_WINDOWS = (
    ("new_rescue_report_scan", 0x800E9E34, 0x800EA0D0),
    ("reward_grant_path_slice", 0x800EA1F0, 0x800EA5D0),
    ("reward_bit_index", 0x800F05AC, 0x800F05E8),
    ("new_rescue_predicate", 0x800F05E8, 0x800F0630),
    ("prior_native_save_rescued_predicate", 0x800F0630, 0x800F0668),
    ("mission_entry_found_getter", 0x800F06F4, 0x800F0724),
    ("upgrade_ordinal", 0x800F0724, 0x800F0784),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def found_slot(native_id: int, *, base: int = PLAY+0xD8) -> dict:
    if type(native_id) is not int or not 0 <= native_id < 128:
        raise ValueError("Native Reploid ID must be an integer0..127")
    return dict(word_address=f"{base+(native_id//8)*4:08X}", shift=(native_id & 7)*4,
                mask=f"{0xF << ((native_id & 7)*4):08X}",
                byte_address=f"{base+native_id//2:08X}", nibble="high" if native_id & 1 else "low")


def decode_found(data: bytes) -> list[dict]:
    if len(data) != 64:
        raise ValueError("Found-state table must contain exactly64 bytes")
    # Physical getter permits all16 nibble values. Only native writer values
    # 0/2/3/4 have established meanings; never relabel unknown1/5..15 as rescue.
    return [dict(native_id=i, value=(data[i//2] >> ((i & 1)*4)) & 15,
                 meaning=STATE_NAMES.get((data[i//2] >> ((i & 1)*4)) & 15, "unknown_native_value"))
            for i in range(128)]


def read_window(payload: bytes, base: int, start: int, end: int) -> bytes:
    if start & 3 or end & 3 or start < base or end <= start or end-base > len(payload):
        raise ValueError("Native source window escaped its pinned image")
    return payload[start-base:end-base]


def code_window(payload: bytes, base: int, name: str, start: int, end: int) -> dict:
    data = read_window(payload, base, start, end)
    calls, stores = [], []
    for offset in range(0, len(data), 4):
        word = struct.unpack_from("<I", data, offset)[0]
        pc, op = start+offset, word >> 26
        if op == 3:
            calls.append(dict(address=f"{pc:08X}", target=f"{((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2):08X}"))
        if op in (40, 41, 43):
            immediate = struct.unpack("<h", struct.pack("<H", word & 0xFFFF))[0]
            stores.append(dict(address=f"{pc:08X}", bytes={40:1, 41:2, 43:4}[op],
                               base_register=(word >> 21) & 31, offset=immediate))
    return dict(id=name, start=f"{start:08X}", end_exclusive=f"{end:08X}",
                bytes=len(data), sha256=sha(data), direct_calls=calls, stores=stores)


def table(payload: bytes, base: int, address: int, count: int, width: int) -> dict:
    if width not in (1, 2, 4) or count <= 0 or address < base or address+count*width-base > len(payload):
        raise ValueError("Native table escaped its pinned image")
    raw = payload[address-base:address+count*width-base]
    values = list(struct.unpack("<"+{1:"B", 2:"H", 4:"I"}[width]*count, raw))
    return dict(address=f"{address:08X}", count=count, width=width, bytes=len(raw), sha256=sha(raw), values=values)


def source_function(source: str, name: str) -> str:
    match = re.search(r"^static [^\n;]+\b"+re.escape(name)+r"\([^\n]*\) \{", source, re.M)
    if not match:
        raise ValueError(f"Missing inspected adapter function {name}")
    # These inspected functions contain no braces in literals/comments. Do not
    # use this small extractor as a general C parser on unrelated source.
    level = 0
    for at in range(source.index("{", match.start()), len(source)):
        level += (source[at] == "{") - (source[at] == "}")
        if level == 0:
            return source[match.start():at+1]
    raise ValueError(f"Unterminated adapter function {name}")


def adapter_contract(source: str, game_config: str) -> dict:
    names = ("pickup_as_seat", "pickup_collect", "pickup_tick", "leave_zero_context")
    spans = {name: source_function(source, name) for name in names}
    for address, callback in (("8004EECC", "pickup_collect"), ("8004EC30", "pickup_tick")):
        if f"psx_mod_set_function_replacement(0x{address},{callback})" not in source or f'"0x{address}"' not in game_config:
            raise ValueError("Native Reploid replacement/configured entry contract changed")
    return dict(source="src/mods/mmx6_coop_plugin.c", configured_entries=["8004EECC", "8004EC30"],
        functions=[dict(name=name, bytes=len(text.encode()), sha256=sha(text.encode())) for name,text in spans.items()],
        policy=["P1 then P2, only lifecycle ALIVE and not a scene passenger, using the original contact predicate",
                "Continue to P2 only while native actor phase+4 remains1; stop after successful phase2/3",
                "Record collector for phase2 only; original actor/world state machine remains once per world pass",
                "Delayed phase2 executes under the saved collector; owner entry cleared when native phase differs from2",
                "Projection swaps PLAYER body and PLAY+38/+5E identity; shared life/freeze/found/reward flags survive",
                "Delayed pickup_tick has no separate collector-life check; vehicle alternative bodies are not projected"],
        limitations=["Source registration/config seed does not prove a particular generated/AOT/interpreter hook executed",
                     "No claim that absent/dead collector, vehicle, slot reuse, simultaneous infection, menu or native-card behavior passed"])


def frozen_inventory(data: bytes) -> dict:
    if sha(data) != INVENTORY_SHA:
        raise ValueError("Frozen original inventory SHA changed")
    report = json.loads(data)
    if [r["native_id"] for r in report["reploids"]] != list(range(128)):
        raise ValueError("Frozen inventory must map all128 IDs exactly once")
    return report


def map_records(exe: Executable, archive: bytes, frozen: dict) -> tuple[list[dict], list[dict]]:
    members = archive_members(archive)
    rewards = table(exe.data[2048:2048+exe.size], exe.base, REWARDS, 128, 4)["values"]
    if Counter(rewards)[1] != 8 or Counter(rewards)[2] != 8 or any(v and (v & (v-1)) for v in rewards):
        raise ValueError("Original reward assignment domain changed")
    sources, placements = [], {}
    for section in frozen["placement_sections"]:
        slot = section["stage"]*2+section["section"]
        member_index = struct.unpack_from("<H", exe.data, exe.offset(OVERLAY_SELECTOR+slot*2,2))[0]
        root = exe.word(0x8007349C+slot*4)
        member = members[member_index]
        if member_index != section["loader_member"] or member != section["source_member"] or f"{root:08X}" != section["table"]:
            raise ValueError("Authored section/member binding differs from frozen inventory")
        payload = archive[member["sector"]*2048:member["sector"]*2048+member["size"]]
        rows = placement_list(payload, root, OVERLAY_BASE)
        if rows != section["placements"]:
            raise ValueError("Authored placement records differ from frozen inventory")
        sites = [f"{OVERLAY_BASE+i:08X}" for i in range(0,len(payload)-3,4)
                 if struct.unpack_from("<I",payload,i)[0] == 0x8004F834]
        sources.append(dict(stage=section["stage"], section=section["section"], **member,
                            reploid_dispatch_pointer_sites=sites,
                            pointer_limit="Pointer presence is source metadata; active dispatch requires native runtime evidence"))
        for native in rows:
            if native["category"] == 4 and native["object_id"] == 4:
                identifier = native["subtype"]
                if identifier in placements or not 0 <= identifier < 128:
                    raise ValueError("Duplicate/out-of-domain authored Reploid ID")
                placements[identifier] = (section, native)
    if set(placements) != set(range(128)):
        raise ValueError("Missing authored Reploid IDs")
    rows = []
    for original in frozen["reploids"]:
        identifier = original["native_id"]
        section,native = placements[identifier]
        compare = dict(native_id=identifier, stage=section["stage"], section=section["section"],
                       placement_index=native["index"], address=native["address"], x=native["x"], y=native["y"])
        if any(original[k] != value for k,value in compare.items()) or original["id"] != f"reploid-{identifier:03d}":
            raise ValueError("Reploid definition differs from frozen inventory")
        code = rewards[identifier]
        kind = "none" if not code else "life_upgrade" if code == 1 else "energy_upgrade" if code == 2 else "part"
        ordinal = sum(bool(v & code) for v in rewards[:identifier+1]) if code in (1,2) else None
        once = (0x100 if code == 1 else 0x1000000) << (ordinal-1) if ordinal else code
        rows.append(dict(id=original["id"], inventory_definition=original,
            inventory_definition_sha256=sha(canonical(original)), native_placement=native,
            member=section["loader_member"], found=found_slot(identifier),
            mission_entry_found=found_slot(identifier,base=PLAY+0x118),
            native_save_payload=dict(word_offset=f"{0x44+(identifier//8)*4:X}", shift=(identifier & 7)*4),
            reward=dict(table_address=f"{REWARDS+identifier*4:08X}", code=f"{code:08X}", kind=kind,
                        ordinal=ordinal, once_mask=f"{once:08X}",
                        once_word=f"{PLAY+(0x6C if code in (1,2) else 0x70):08X}" if code else None,
                        beneficiary="mission_report_active_PLAY+38_character" if code in (1,2) else "shared_parts" if code else None),
            runtime_status="unverified"))
    return rows,sources


def audit(image: bytes, archive: bytes, inventory_data: bytes, adapter: str, config: str) -> dict:
    if sha(image) != EXE_SHA256 or sha(archive) != BIN_SHA256:
        raise ValueError("Require pinned original SLUS-01395v1.1 EXE and ROCK_X6.BIN")
    exe = Executable(image)
    frozen = frozen_inventory(inventory_data)
    records,sources = map_records(exe,archive,frozen)
    member = archive_members(archive)[REPORT_MEMBER]
    if member["sha256"] != REPORT_SHA:
        raise ValueError("Original mission-report member changed")
    report_payload = archive[member["sector"]*2048:member["sector"]*2048+member["size"]]
    payload = image[2048:2048+exe.size]
    result = dict(schema=1, kind="original_native_reploid_rescue_attribution_audit",
        status="source_mapped_runtime_unverified", source=dict(exe_sha256=sha(image), exe_bytes=len(image),
            archive_sha256=sha(archive), inventory_sha256=sha(inventory_data), report_member=member),
        native_pool=dict(start=f"{POOL:08X}", end_exclusive=f"{POOL_END:08X}", stride=STRIDE, slots=(POOL_END-POOL)//STRIDE,
            identity="allocated+0, object+1==4, subtype+2==native_id, origin_pointer+10 binds authored placement"),
        state=dict(current=f"{PLAY+0xD8:08X}", mission_entry=f"{PLAY+0x118:08X}", bytes=64,
                   field_bits=4, physical_domain=list(range(16)), source_writer_values=[0,2,3,4],
                   setter_argument_masks=dict(native_id="FF",state="FF"),
                   setter_limit="Native setter has no128-ID bound or4-bit clamp; inspected callers/authored IDs provide those guards. No write API is exposed here.",
                   meanings={str(k):v for k,v in STATE_NAMES.items()},
                   unknown="1 and5..15 remain unknown, never silently treated as rescued/infected"),
        transitions=[
            dict(id="init_suppressed", source="8004E824..8004E840", before="actor phase0", after="phase8 then actor_clear",
                 guard="subtype!=80h and current found nibble in2/3/4", found_write=None),
            dict(id="init_waiting", source="8004EA44..8004EA60", before="actor phase0", after="phase1/action0/availability1",
                 guard="not suppressed; special subtype80h instead has availability0", found_write=None),
            dict(id="rescue_contact", source="8004EECC..8004EFB8", before="phase1", after="phase2 if collector HP below native max; else phase3",
                 guard="selected body masked HP nonzero and original overlap true; ride flagD5 can select shared alternate vehicle body",
                 found_write=2, effects="shared lives+39 increment capped9; random2/4/8/16 heal units; native heal/tank setup"),
            dict(id="heal_complete", source="8004EC30..8004ED34", before="phase2", after="phase3/action0, allocation bit08 clear",
                 guard="one HP every4 own calls; stop at max or requested units; completion next subaction call",
                 found_write=None, effects="clear native freeze bytes PLAY+10..17/+19"),
            dict(id="rescued_escape", source="8004F8C0..8004FB28", before="phase3", after="phase4 delay80, phase5 native escape, actor_clear",
                 guard="native animation and offscreen predicate; no success-flag write bypass", found_write=None),
            dict(id="nightmare_request", source="80040DF4/80040F7C", before="visible allocated object4 availability1", after="availability2",
                 guard="native nearest target, validated live object, strict absX<2 and abs(NightmareY+28-ReploidY)<2",
                 found_write=None, effects="Nightmare infection bookkeeping at42D3C"),
            dict(id="infection_commit", source="8004EB48..8004EB84", before="phase1 availability2", after="phase6/action2/subaction0, availability0",
                 guard="rescue contact first returnsfalse (both eligible co-op seats fail)", found_write=4),
            dict(id="infected_killed", source="8004FB98..8004FBD0", before="phase6 hostile", after="phase8 invisible, effect31",
                 guard="native damage helper31474 returnsnegative", found_write=3),
            dict(id="infected_offscreen_loss", source="8004FBDC..8004FC2C", before="phase6 hostile", after="phase8",
                 guard="native offscreen predicate2CAB4 returnsnonzero", found_write=4),
            dict(id="waiting_offscreen", source="8004EBBC..8004EC14/8004FB40", before="phase1", after="phase7 invisible then origin rearm and actor_clear",
                 guard="native camera predicate and subtype!=80h", found_write=None),
        ],
        actor_fields={"0":"allocation byte", "1":"object type byte4", "2":"native ID byte0..127;80h is a separate non-inventory special actor",
            "3":"visibility byte", "4":"phase byte0..8", "5":"phase action byte", "6":"subaction byte",
            "7":"availability/infection request byte:1 targetable,2 infection pending,0 unavailable",
            "8/C":"current16.16 position words", "10":"native placement pointer word", "68":"contact-box pointer word",
            "50/54":"infected collision-descriptor pointer words; original types retained without inventing a new owner",
            "5C":"infected native HP byte initialized13", "60":"infected native strength byte initialized6",
            "7C":"floating reference Y halfword", "7E":"ground/float selector byte", "7F":"heal units/countdown byte",
            "80":"heal4-tick byte counter (on Reploid; Nightmare+80 is a different target-pointer word)",
            "81":"escape/infection delay byte", "82":"facing selector byte0/40h", "83":"infected flash flag byte", "84":"ID high-nibble10h visual-class byte"},
        tables=[table(payload,exe.base,0x80078C7C,9,4), table(payload,exe.base,0x80078CA0,6,4),
                table(payload,exe.base,REWARDS,128,4), table(payload,exe.base,0x8006D634,16,4),
                table(payload,exe.base,0x80078BE8,4,1), table(payload,exe.base,0x80075FE8,46,1)],
        code_windows=[dict(region="exe",**code_window(payload,exe.base,*w)) for w in EXE_WINDOWS]+[
                     dict(region="BIN20",**code_window(report_payload,OVERLAY_BASE,*w)) for w in REPORT_WINDOWS],
        authored_members=sources, adapter=adapter_contract(adapter,config), reploids=records,
        persistence=dict(pack_function="8001BD40", unpack_function="8001BA1C",
            pack_payload_base="80070CC4", unpack_payload_base="native a0 argument", payload_found_offset="44", found_bytes=64,
            shared_parts=dict(play_offset="70", payload_offset="04", bytes=4),
            upgrade_once=dict(play_offset="6C", payload_offset="10", bytes=4),
            character_hp_max=dict(play_offset="5B", payload_offset="36", bytes=2),
            character_energy_max=dict(play_offset="61", payload_offset="38", bytes=2),
            nightmare_consumed_flags=dict(play_offset="178",payload_offset="CE", rows=22,row_bytes=32,
                native_index="byte80075FE8[stage*2+section]*32+(NightmareID_halfword88>>3), bit=(ID&7)",
                guard="Native Nightmare actor IDs/table eligibility must be validated; this is not a second Reploid-state table"),
            lives="PLAY+39 run-state increment is not persisted here; unpack initializes2 or4 from native parts flags",
            limit="Payload serialization source only; card/container checksums, I/O completion and cold continue remain unverified"),
        counts=dict(reploids=len(records), reward_kinds=dict(Counter(r["reward"]["kind"] for r in records)),
                    gameplay_passes=0),
        remaining_proofs=["Each of128 authored placements and all seven frozen cases independently in local/netplay",
            "Actual hook interception and once-world update/order, including same-frame P1/P2/Nightmare competition",
            "Collector HP/heal/tank/life/SFX/message attribution at low/full HP and absent/dead/scene/vehicle boundaries",
            "Native mission-report reward beneficiary and once masks, equipment availability, stage exit/next destination",
            "Copied-card native save completion, cold boot/continue and retry/reentry after rescued/infected/dead/missing states"],
        candidate_boundaries=["Vehicle rescue path reads shared alternate body800CD340/800CD3F0 outside current body-only collector projection; qualify or reject that path before adding private vehicle support",
            "Delayed owner tick lacks lifecycle eligibility check; obtain a native counterexample before changing death/absence behavior during native heal freeze",
            "Mission-report Life/Energy Up follows active PLAY+38, not remembered rescue collector; define co-op policy and native evidence before changing shared native grants",
            "Pickup owner entries identify actor pointer only; qualify deallocation/slot reuse and phase transitions before adding generation/origin guards"],
        limits=["All runtime outcomes unverified; source data and registered handlers are not gameplay passes",
            "Original tables only; new-game/Tweaks patches can change initial found/reward assignments and must be recorded separately",
            "Native card offsets are relative to the serialized game payload; no card/container bytes are read or modified",
            "Mission-report grant path is a bounded slice, not a complete audit of report UI, stage selection or native card I/O"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--disc",type=Path)
    inputs.add_argument("--bin",type=Path)
    root=Path(__file__).resolve().parents[1]
    parser.add_argument("--inventory",type=Path,default=root/"docs/COOP_X6_CONTENT.json")
    parser.add_argument("--adapter",type=Path,default=root/"src/mods/mmx6_coop_plugin.c")
    parser.add_argument("--config",type=Path,default=root/"game.toml")
    outputs=parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument("--output",type=Path)
    outputs.add_argument("--check",type=Path)
    args=parser.parse_args()
    image=args.exe.read_bytes()
    if args.disc:
        disc=RawDisc(args.disc)
        try: files=disc.inventory_files()
        finally: disc.stream.close()
        if files["SLUS_013.95"]!=image:
            raise ValueError("Disc EXE differs from supplied original")
        archive=files["ROCK_X6.BIN"]
    else:
        archive=args.bin.read_bytes()
    result=audit(image,archive,args.inventory.read_bytes(),args.adapter.read_text(encoding="utf-8"),args.config.read_text(encoding="utf-8"))
    if args.check:
        if result!=json.loads(args.check.read_text(encoding="utf-8")):
            raise ValueError("Committed Reploid source audit differs; do not overwrite runtime evidence")
        print("Original Reploid source audit matches;128 IDs;0 gameplay passes")
    else:
        if ntpath.splitdrive(str(args.output.resolve()))[0].lower()=="c:":
            raise ValueError("Generated audit metadata must stay off C:")
        with args.output.open("x",encoding="utf-8") as stream:
            json.dump(result,stream,indent=2,ensure_ascii=False)
            stream.write("\n")
        print(f"Wrote {len(result['reploids'])} source-bound Reploid records;0 gameplay passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
