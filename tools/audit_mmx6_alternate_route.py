"""Reproduce a bounded original Recycle hidden-route/R14 source audit.

Reads the pinned EXE and archive extent only; emits hashes/metadata, never disc
bytes, native writes, a launcher, or local/netplay gameplay qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from audit_mmx6_coop_hud import committed, function
from audit_mmx6_death_particles import direct_calls
import inventory_mmx6_coop_content as content

BASE = "952bb4b7b684b9bf05dc9777ce37738b053247dd"
INVENTORY_SHA = "67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad"
MEMBER_SHA = "c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5"
R14_SHA = "f84b489de9124b06fc4ddff745018059da8666b678ae2330431c7953877326ff"
EXE_SPANS = (
    ("contact", 0x8002D654, 0x214),
    ("fade_request", 0x800139F4, 0x54),
    ("stage_transition", 0x8001E32C, 0x3B8),
    ("alternate_destination", 0x80042F7C, 0x2C),
    ("stage_initialize", 0x8001E1BC, 0x170),
    ("checkpoint_initialize", 0x80029B8C, 0x188),
    ("body_transition_probe", 0x8003A628, 0x50),
)
MEMBER_SPANS = (
    ("initialize", 0x800EBD80, 0x140),
    ("lock_player_and_world", 0x800EBEC0, 0xF4),
    ("restore_after_fade", 0x800EBFB4, 0xC4),
    ("controller", 0x800EC678, 0x4C),
    ("phase1", 0x800EC6C4, 0x7C),
    ("retire", 0x800EC740, 0x40),
    ("contact_admission", 0x800EC780, 0x78),
    ("request_alternate", 0x800EC8F8, 0xA4),
    ("collision_animation_dispatch", 0x800F38B8, 0x7C),
    ("subtype_initialize_dispatch", 0x800E9864, 0x14),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Member:
    def __init__(self, data: bytes):
        self.data = data

    def read(self, address: int, size: int) -> bytes:
        at = address - content.OVERLAY_BASE
        if size < 0 or at < 0 or at > len(self.data) - size:
            raise ValueError("Selected-member address outside original extent")
        return self.data[at:at + size]

    def word(self, address: int) -> int:
        return struct.unpack("<I", self.read(address, 4))[0]


def alternate_destination(exe: content.Executable, stage: int) -> tuple[int, int]:
    """The original 42F7C mapping, restricted to its proven caller's stages1..8.

    This predicts a native namespace, never loads it or certifies checkpoint0.
    """
    if type(stage) is not int or not 1 <= stage <= 8:
        raise ValueError("Alternate destination requires native Investigator stage1..8")
    expected = (0x2484FFFF, 0x000417C2, 0x00821021, 0x00021043,
                0x24420013, 0x30840001, 0xA0A20000, 0x03E00008, 0xA0C40000)
    if tuple(exe.word(0x80042F84 + i * 4) for i in range(9)) != expected:
        raise ValueError("Original alternate-destination signed arithmetic differs")
    return 0x13 + (stage - 1) // 2, (stage - 1) & 1


def audit(repository: Path, executable: bytes, archive: bytes) -> dict:
    if sha(executable) != content.EXE_SHA256 or sha(archive) != content.BIN_SHA256:
        raise ValueError("Require the pinned complete original EXE and archive")
    exe = content.Executable(executable)
    descriptor = content.archive_members(archive)[6]
    if descriptor["sha256"] != MEMBER_SHA:
        raise ValueError("Original Recycle overlay identity differs")
    start = descriptor["sector"] * 2048
    member = Member(archive[start:start + descriptor["size"]])
    paths = ("src/mods/mmx6_coop_plugin.c", "game.toml",
             "docs/COOP_PARITY_LEDGER.json", "docs/COOP_X6_CONTENT.json")
    files = {p: committed(repository, BASE, p) for p in paths}
    if sha(files[paths[3]]) != INVENTORY_SHA:
        raise ValueError("Frozen native inventory drift")
    inventory = json.loads(files[paths[3]])
    ledger = json.loads(files[paths[2]])
    matches = [r for r in ledger["comparisons"] if r["id"] == "R14"]
    if len(matches) != 1 or matches[0]["frozen_row_sha256"] != R14_SHA:
        raise ValueError("Missing, duplicate or changed frozen R14 definition")
    row = matches[0]
    section = next(s for s in inventory["placement_sections"]
                   if s["stage"] == 4 and s["section"] == 0)
    record = section["placements"][18]
    values = struct.unpack("<4B2h", member.read(int(record["address"], 16), 8))
    expected = tuple(record[k] for k in ("flags", "object_id", "subtype", "category", "x", "y"))
    table = exe.word(0x8006DC6C + 4 * 8)
    if values != expected or values != (0, 0x1C, 1, 0, 1552, 1584) or \
       table != 0x800F301C or member.word(table + 0x1C * 4) != 0x800EC678:
        raise ValueError("Original hidden-route record/handler mapping differs")
    phases = [member.word(0x800F3900 + i * 4) for i in range(4)]
    actions = [member.word(0x800F3910 + i * 4) for i in range(6)]
    substates = [member.word(0x800F3928 + i * 4) for i in range(3)]
    if phases != [0x800EBD80, 0x800EC6C4, 0x800EC740, 0x800EC740] or \
       actions[1:4] != [0x800EC780, 0x800EC880, 0x800EC8BC] or \
       substates != [0x800EBEC0, 0x800EC8F8, 0x800EBFB4]:
        raise ValueError("Original portal phase/action closure differs")
    plugin = files[paths[0]].decode()
    functions = {name: function(plugin, name) for name in (
        "activate", "interaction_inside", "interaction_begin", "stage_tick", "controller",
        "scene_locked", "scene_tick", "player_tick", "camera_target")}
    for data in functions.values():
        data.pop("source")
    spans = []
    for name, pc, size in EXE_SPANS + MEMBER_SPANS:
        data = executable[exe.offset(pc, size):exe.offset(pc, size) + size] if pc < content.OVERLAY_BASE else member.read(pc, size)
        spans.append(dict(name=name, address=f"{pc:08X}", size=size,
                          sha256=sha(data), direct_calls=direct_calls(data, pc)
                          if name not in ("collision_animation_dispatch", "subtype_initialize_dispatch") else []))
    destination = alternate_destination(exe, 4)
    locations = [r for r in inventory["locations"]
                 if (r["stage"], r["section"]) == destination]
    return dict(schema_version=1, source_only=True, scope=["R14"], game_commit=BASE,
        comparison=dict(id="R14", frozen_row_sha256=row["frozen_row_sha256"], x4=row["x4"],
                        bounded_check=row["x6"]["bounded_check"], local="unverified", netplay="unverified"),
        original=dict(exe_sha256=content.EXE_SHA256, archive_sha256=content.BIN_SHA256,
                      archive_lba=211185, archive_bytes=1665024, selected_member=descriptor),
        sources=[dict(path=p, bytes=len(data), sha256=sha(data)) for p, data in files.items()],
        functions=functions, native_spans=spans,
        research_label=dict(workbook_sha256="6855194c79f0830ee77b86901bc1997a481ce62de17dfaaced79d976d840e552",
            sheet="ObjectOriginTable", cell="C7", label="Hidden Area teleport",
            limits="Semantic research index only; original record/table/transition establish the native mapping. Workbook replacement bytes are not stock guards."),
        origin=dict(inventory_sha256=INVENTORY_SHA, stage=4, section=0,
            placement_index=18, record=record, record_sha256=sha(member.read(0x800F2B0C, 8)),
            category_root="8006DC6C", handler_table=f"{table:08X}",
            handler_slot="800F308C", handler="800EC678"),
        dispatch=dict(phase_table="800F3900", phases=[f"{p:08X}" for p in phases],
            action_table="800F3910", actions=[f"{p:08X}" for p in actions],
            action2_substate_table="800F3928", action2_substates=[f"{p:08X}" for p in substates],
            subtype1_initialize="800E9864[1] ->800EBE64 ->phase1/action1/subaction0"),
        contact=dict(call_pc="800EC79C", function="8002D654", arguments=["a0=portal", "a1=800970A0 resident PLAYER"],
            portal_attack_box="+50 ->800F38BC", portal_box=list(struct.unpack("<2b2B", member.read(0x800F38BC, 4))),
            player_box="PLAYER+54 (required nonzero)", immunity="PLAYER+61 nonzero rejects",
            geometry="native signed centers/facing, unsigned extents and directional half-open comparisons; not camera-center or fixed-radius admission",
            success="subtype1: actor+5=2,+6=0,+84=resident PLAYER integerX; subtype2 uses different action3 path",
            native_absence="no pad/Select prerequisite in this contact helper"),
        lock=dict(setup="800EBEC0", hp_gate="resident PLAYER+5C must be nonzero",
            camera_bytes=["CAM+44", "CAM+98", "CAM+EC"],
            play_flags=["10", "11", "12", "13", "14", "15", "16", "17", "19"], flag_value=2,
            body="PLAYER+5=2; old PLAYER+68 saved in actor+88, PLAYER+68 cleared",
            portal_fields={"+0":"OR8", "+6":"increment", "+7C":"timer half reset0",
                           "+80/+82":"resident PLAYER integerX"}),
        transition=dict(request="800EC8F8", timer="actor+7C signed half reaches29 on accepted update calls, not wall-clock frames",
            player_x="native frame parity picks actor+80 increasing or +82 decreasing and stores PLAYER+0A",
            request_pc="800EC964 ->800139F4(8)", flag_pc="800EC978", flag="PLAY+0F=subtype|40h; subtype1 gives41h",
            destination_caller="8001E3C8..8001E3E4 within8001E32C: stage1..8 and flag41h",
            destination_helper="80042F7C", destination_stage=destination[0], destination_section=destination[1],
            all_investigator_destinations=[dict(stage=s, destination_stage=alternate_destination(exe, s)[0],
                destination_section=alternate_destination(exe, s)[1]) for s in range(1, 9)],
            load="next major8 initialization8001E1BC calls80029B8C then camera routines8002927C/8002935C/800293CC, resets PLAY+0F and enters major0A",
            authored_destination_locations=locations,
            checkpoint_limit="Locations are authored candidates. This bounded audit does not prove which checkpoint is selected on actual entry or full streaming/overlay completion.",
            restore="800EBFB4 waits fade idle, restores PLAYER integerX, +68, camera+44/+98/+EC=1 and clears its shared flags"),
        adapter=dict(explicit_hooks="80050250 door;80051924 interaction;80052F64 optional event/dialogue zones;8003D308 script start",
            missing_portal_hook="No explicit800EC780/8002D654/type1C wrapper or corresponding scene admission in activate()",
            ordinary_world="stage_tick default calls original once with resident P1; controller projects P2 only for private body/shot/contact/attached/trail passes",
            other_context="survivor, P2 menu or established P2 scene can project Zero for the original world; this is not an either-player portal policy",
            passenger_gate="scene_tick phase3 waits owner grounded/controllable/HP with D0/D4/7A and shared locks clear; no explicit actual-destination generation token",
            camera="existing midpoint/tether camera hooks do not change this explicit PLAYER collision argument"),
        findings=[dict(id="authored-route", classification="source_proven_native_contract",
            text="Pinned original type1C/subtype1 Recycle actor leads through41h to alternate20/1; this is not the52F64 dialogue handler"),
            dict(id="resident-contact", classification="source_proven_adapter_coverage_gap",
            text="Native portal contact explicitly uses resident PLAYER and current adapter lacks a portal either-seat/owner wrapper; an actual leading-P2 counterexample remains unverified"),
            dict(id="projection-closure", classification="source_proven_constraint_for_future_fix",
            text="A whole-controller body projection would also redirect native saved body box/X, shared freeze flags, camera locks and transition writes; do not copy the intro near-X-only projection"),
            dict(id="destination-release", classification="unverified_native_obligation",
            text="Actual destination load, native selected checkpoint, safe full-foot landing and both controls must be observed before any R14 pass")],
        proposed_fix_boundary="First obtain original P1/co-op P1 references and a P1-far/P2-only native contact trace. Then design a source-guarded pure contact probe plus explicit portal owner/transition closure; never execute the shared portal AI twice or fake the success flag.",
        required_native_checks=[
            "Bind exact candidate/settings/original source; keep original native cards isolated. Reach record18 by genuine stage traversal or explicitly tainted private positioning, never write portal action/PLAY0F/route flags.",
            "Co-op-off native X/P1 then co-op P1: bind live category0 pool slot origin+10 to800F2B0C and retain phase/action, native box pointers, HP/immunity, position/facing and actual contact result.",
            "Living Zero/P2 only in the actual contact boxes while living X/P1 is outside: record ordinary world context and source-proven contact call/result; compare P1-only control. Also reject absent/fallen/passenger/menu cases.",
            "Observe exactly one original action2 setup/freeze and native fade/41h transition. Follow actual stage20/section1 initialization, selected checkpoint, archive/overlay identity, camera bounds/collision and completed composed frame.",
            "Keep passenger out until native destination exists, owner is grounded/controllable and full-foot safe terrain is established; independently accept both inputs after release, with retained character resources and finite beams.",
            "Exercise actual native return/exit separately. Repeat independently local and netplay on one exact candidate with resolved input/core/mod evidence; source, loading and capture ACK are not passes."],
        limits=["No plugin, SDK, CMake, ledger, runtime or save edits; no build/game launched",
            "Only EXE, archive metadata and selected Recycle member6 interpreted; no full-disc crawl",
            "Other portal subtypes, refight portals/R21, story replacement bosses and all eight route runtime cases remain outside scope",
            "Workbook label is a pinned research index, not executable proof or a patched-disc identity",
            "No X4 addresses, mechanics, inherited passes or rendered/native qualification"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    if args.exe.stat().st_size != 522240:
        parser.error("Expected bounded complete original EXE")
    raw = content.RawDisc(args.disc)
    try:
        archive = raw.extent(211185, 1665024)
    finally:
        raw.stream.close()
    rendered = json.dumps(audit(args.repository, args.exe.read_bytes(), archive), indent=2) + "\n"
    if args.check:
        if args.check.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Alternate-route source audit differs")
    else:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
