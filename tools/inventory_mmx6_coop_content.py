#!/usr/bin/env python3
"""Inventory original SLUS-01395 v1.1 content for reproducible co-op QA.

Reads an original EXE and optional extracted ROCK_X6.BIN or raw 2352-byte disc.
Emits metadata, never original executable/archive bytes or modified game state.
Every runtime obligation starts unverified. See docs/COOP_X6_CONTENT.md.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

EXE_SHA256 = "dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046"
BIN_SHA256 = "55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f"
CHECKPOINT_ROOT, CHECKPOINT_END = 0x80073300, 0x800733B8
POINTER_START, RECORD_START = 0x80073134, 0x80072108
OVERLAY_SELECTOR, OVERLAY_BASE = 0x8006DB78, 0x800E9860
SLOT_COUNT = (CHECKPOINT_END - CHECKPOINT_ROOT) // 4
PLACEMENT_ROOTS = (("placement_sections", 0x8007349C),
                   ("secondary_placement_sections", 0x80073554))
CHECKS = ("terrain_collision_scroll", "enemies_interactions", "music_sfx",
          "checkpoint_retry", "boss", "exit_actual_transition")
MODE_CHECKS = ("local_coop", "netplay")

# Semantic names come from the local Tweaks v2.0 workbook PlaythroughTable.
# Native pointers/counts and source addresses are always extracted below.
STAGES = {
    0: ("Intro / Eurasia ruins", "campaign"),
    1: ("Amazon Area / Commander Yammark", "investigator"),
    2: ("North Pole Area / Blizzard Wolfang", "investigator"),
    3: ("Magma Area / Blaze Heatnix", "investigator"),
    4: ("Recycle Lab / Metal Shark Player", "investigator"),
    5: ("Central Museum / Ground Scaravich", "investigator"),
    6: ("Inami Temple / Rainy Turtloid", "investigator"),
    7: ("Laser Institute / Shield Sheldon", "investigator"),
    8: ("Weapon Center / Infinity Mijinion", "investigator"),
    9: ("Native slot 09: semantic role unresolved", "unmapped"),
    10: ("Native slot 0A: semantic role unresolved", "unmapped"),
    11: ("Cutscene namespace", "presentation"),
    12: ("Secret Lab 3: refights (section 0), Sigma (section 1)", "final"),
    13: ("Stage select namespace", "menu"),
    14: ("Title/menu namespace", "menu"),
    15: ("Mission report namespace", "menu"),
    16: ("Secret Lab 1", "fortress"),
    17: ("Secret Lab 2 A / common", "fortress"),
    18: ("Secret Lab 2 B / character-specific", "fortress"),
    19: ("Alternate Amazon (section 0), North Pole (section 1)", "alternate"),
    20: ("Alternate Magma (section 0), Recycle (section 1)", "alternate"),
    21: ("Alternate Museum (section 0), Inami (section 1)", "alternate"),
    22: ("Alternate Laser (section 0), Weapon Center (section 1)", "alternate"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Executable:
    def __init__(self, data: bytes):
        if len(data) < 2048 or data[:8] != b"PS-X EXE":
            raise ValueError("Expected a complete PS-X EXE header")
        self.data = data
        self.base, self.size = struct.unpack_from("<II", data, 0x18)
        if not self.size or self.size > len(data) - 2048:
            raise ValueError("Truncated PS-X EXE payload")

    def offset(self, address: int, count: int) -> int:
        offset = address - self.base
        if count < 0 or offset < 0 or offset + count > self.size:
            raise ValueError(f"Address outside executable payload: {address:08X}+{count}")
        return offset + 2048

    def word(self, address: int) -> int:
        return struct.unpack_from("<I", self.data, self.offset(address, 4))[0]


def checkpoint_inventory(exe: Executable) -> list[dict]:
    roots = [exe.word(a) for a in range(CHECKPOINT_ROOT, CHECKPOINT_END, 4)]
    starts = sorted((set(roots) - {0}) | {CHECKPOINT_ROOT})
    result = []
    for slot, table in enumerate(roots):
        if not table:
            continue
        if table & 3 or not POINTER_START <= table < CHECKPOINT_ROOT:
            raise ValueError(f"Invalid checkpoint table: {table:08X}")
        end = starts[starts.index(table) + 1]
        for checkpoint, at in enumerate(range(table, end, 4)):
            record = exe.word(at)
            if (record < RECORD_START or record + 0x24 > POINTER_START
                    or (record - RECORD_START) % 0x24):
                raise ValueError(f"Invalid checkpoint record: {record:08X}")
            offset = exe.offset(record, 0x24)
            values = struct.unpack_from("<12h", exe.data, offset)
            stage, section = divmod(slot, 2)
            result.append(dict(
                id=f"s{stage:02d}-a{section}-c{checkpoint:02d}",
                stage=stage, section=section, checkpoint=checkpoint,
                stage_name=STAGES[stage][0], stage_role=STAGES[stage][1],
                table=f"{table:08X}", record=f"{record:08X}",
                player=dict(x=values[0], y=values[1]),
                camera=dict(x=values[2], y=values[3],
                            min_x=values[8], max_x=values[9],
                            min_y=values[10], max_y=values[11]),
                arrival=exe.data[offset + 0x18],
                status="unverified", checks={name: "unverified" for name in CHECKS},
            ))
    return result


def archive_members(data: bytes) -> list[dict]:
    """Validate the native two-sector header and 59 aligned extents."""
    if len(data) < 4096 or len(data) % 2048:
        raise ValueError("ROCK_X6.BIN must contain aligned sectors")
    entries = []
    cursor = 4096
    for index in range(59):
        sector, size = struct.unpack_from("<II", data, index * 8)
        if not size or size < 4 or sector * 2048 != cursor or cursor + size > len(data):
            raise ValueError(f"Invalid BIN extent at index {index}")
        entries.append(dict(index=index, sector=sector, size=size,
                            sha256=sha256(data[cursor:cursor + size])))
        cursor += (size + 2047) // 2048 * 2048
    if struct.unpack_from("<II", data, 59 * 8) != (0, 0) or cursor != len(data):
        raise ValueError("BIN descriptor count or final extent differs from native layout")
    return entries


def placement_list(payload: bytes, address: int, base: int) -> list[dict]:
    offset = address - base
    if address & 3 or offset < 0:
        raise ValueError(f"Invalid placement address: {address:08X}")
    records = []
    for index in range(4096):
        at = offset + index * 8
        if at + 8 > len(payload):
            raise ValueError(f"Unterminated placement list: {address:08X}")
        flags, object_id, subtype, category, x, y = struct.unpack_from("<4B2h", payload, at)
        if category == 15:
            return records
        records.append(dict(index=index, address=f"{address + index * 8:08X}",
                            flags=flags, object_id=object_id, subtype=subtype,
                            category=category, x=x, y=y, status="unverified"))
    raise ValueError(f"Placement list exceeds native QA bound: {address:08X}")


class RawDisc:
    """Read the two inventory input files only, without extracting disc data."""
    def __init__(self, path: Path):
        self.stream = path.open("rb")
        self.size = path.stat().st_size

    def sector(self, lba: int) -> bytes:
        if lba < 0 or (lba + 1) * 2352 > self.size:
            raise ValueError("ISO extent outside raw disc")
        self.stream.seek(lba * 2352)
        data = self.stream.read(2352)
        if len(data) != 2352 or data[15] not in (1, 2):
            raise ValueError("Expected raw MODE1/MODE2 sector")
        if data[15] == 2 and (data[18] & 0x20):
            raise ValueError("Form2 sector cannot contain inventory file data")
        start = 24 if data[15] == 2 else 16
        return data[start:start + 2048]

    def extent(self, lba: int, size: int) -> bytes:
        if size < 0 or size > 2_000_000:
            raise ValueError("Inventory extent exceeds bounded input size")
        return b"".join(self.sector(lba + i) for i in range((size + 2047) // 2048))[:size]

    def inventory_files(self) -> dict[str, bytes]:
        pvd = self.sector(16)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("Expected primary ISO9660 descriptor")
        root = pvd[156:190]
        lba, size = struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0]
        directory = self.extent(lba, size)
        files = {}
        at = 0
        while at < len(directory):
            count = directory[at]
            if not count:
                at = (at // 2048 + 1) * 2048
                continue
            rec = directory[at:at + count]
            if len(rec) != count or count < 34 or 33 + rec[32] > count:
                raise ValueError("Invalid ISO directory record")
            name = rec[33:33 + rec[32]].decode("ascii").split(";")[0]
            if name in ("SLUS_013.95", "ROCK_X6.BIN"):
                if name in files:
                    raise ValueError("Duplicate ISO inventory member")
                files[name] = self.extent(struct.unpack_from("<I", rec, 2)[0],
                                          struct.unpack_from("<I", rec, 10)[0])
            at += count
        if set(files) != {"SLUS_013.95", "ROCK_X6.BIN"}:
            raise ValueError("Original EXE/BIN missing from ISO root")
        return files


def obligation(identifier: int, title: str, procedure: str, **fields) -> dict:
    return dict(id=f"X6-{identifier:03d}", title=title, procedure=procedure,
                status="unverified", checks={key: "unverified" for key in MODE_CHECKS},
                evidence=[], **fields)


def obligations(sections: list[dict]) -> tuple[list[dict], list[dict]]:
    campaign = []
    for section in sections:
        stage, area = section["stage"], section["section"]
        campaign.append(obligation(len(campaign) + 1,
            f"{STAGES[stage][0]}: section {area}",
            "Use every listed checkpoint and authored placement as a coverage index; "
            "traverse intervening routes, retry each checkpoint and exercise native "
            "exit/admission triggers. Record terrain, actors, music/SFX, death, boss "
            "and actual destination independently. Do not grant success flags.",
            stage=stage, section=area,
            checkpoints=[row["id"] for row in section["locations"]],
            primary_placements=section["primary_count"],
            secondary_placements=section["secondary_count"]))
    scenarios = [
        ("Nightmare Zero admission", "Enter alternate routes under native pre-Zero story conditions; each seat triggers the real boss scene, including an absent/dead partner; retain the admitted encounter identity."),
        ("Nightmare Zero fight and Zero unlock", "Defeat Nightmare Zero using accepted attacks and verify reward, Zero unlock, return cutscene and actual next screen once; repeat each scene owner and valid native character."),
        ("Alternate High Max admission", "After native Zero unlock, enter each alternate destination through its real teleport and verify High Max replaces the prior boss without forced encounter flags."),
        ("High Max damage prerequisites", "Exercise native stun/weapon prerequisites from each seat, with one survivor and both alive; verify accepted and rejected hits, health and exactly-once death."),
        ("High Max victory campaign unlock", "Defeat alternate High Max natively; observe Gate-stage access, story report and card persistence without writing stage-unlock flags."),
        ("Dynamo story replacement", "After the native prerequisite, enter alternate arenas and verify Dynamo admission/AI replaces the prior boss for both scene owners."),
        ("Dynamo soul rewards", "Use the native reward interaction and repeated encounter; count spawned/collected souls and exit transitions with either collector and simultaneous attacks."),
        ("Nightmare Mother encounter", "Reach Secret Lab 1 boss admission natively; exercise both entities, hazard phases, either-player damage/death and boss clear transition."),
        ("Fortress High Max encounter", "Use the fortress route and native character branch; verify boss prerequisites and clear advance rather than bypassing its gate."),
        ("Gate encounter", "Exercise Gate arena moving platforms and attack-generated projectiles with both seats and survivor play; verify native damage rules and actual clear advance."),
        ("Investigator refight sequence", "Visit all 18 authored slot0C/0 checkpoints and every refight teleporter; retain each boss identity, exit, completed marker and final-gate admission. Check dynamic spawn coverage separately."),
        ("Sigma phases and endings", "Defeat both final phases through native attacks with each available character/seat owner; verify transitions, ending/credits and cold-load progression."),
        ("Reploid rescue ownership", "For all 128 indexed Reploids, rescue by either seat and simultaneous contact; verify one rescue and one set of rewards with no unintended partner heal."),
        ("Reploid infection/loss", "At each indexed Reploid permit native Nightmare contact, observe infection/loss, then retry/re-enter; record resulting found-state nibble and reward availability."),
        ("Reploid healing and extra life", "Rescue at low/full health with either collector and an absent/dead partner; verify delayed heal ownership and exactly-once life reward."),
        ("Reploid parts grants", "For each item-carrying Reploid verify the native part/Life Up/Energy Up grant, report and equipment availability for both seats; read back copied-card continuation."),
        ("Reploid irreversible state persistence", "Using private native-card copies, save rescued/infected/lost states, cold boot and continue; verify all 128 found-state entries and previously granted items."),
        ("Nightmare Soul pickup ownership", "Collect enemy and boss souls by either seat and simultaneously; verify shared/personal policy, exact count, disappearance and no duplicate pickup."),
        ("Nightmare Soul rank boundaries", "Earn through every original threshold (200,300,500,800,1200,5000,9999) by native pickups from one below; verify rank and parts capacity independently for X and Zero."),
        ("Nightmare Soul retry persistence", "Collect souls, die/checkpoint-retry, leave stage, save and cold continue; observe native count/rank retention and both-peer agreement."),
        ("Nightmare effect propagation", "Visit each Investigator stage, leave by native transition and read affected-stage effects; verify overwrite/order behavior and cold-load state against the native effect table."),
        ("Nightmare Bug", "Create Bug through its native source visit, enter every affected stage and exercise player interaction, attacks and lifetime in unified/split/private views."),
        ("Nightmare Ice", "Create Ice through its native source visit and test slippery terrain, collision and enemy/platform interaction in every affected route."),
        ("Nightmare Fire", "Create Fire through its native source visit and test actual fire hazards and altered ice/wall behavior with each player and both alive."),
        ("Nightmare Iron", "Create Iron through its native source visit and exercise falling/moving solids, damage and camera admission for either seat."),
        ("Nightmare Cube", "Create Cube through its native source visit and exercise cube solidity, weapon interactions and progression on each affected route."),
        ("Nightmare Rain", "Create Rain through its native source visit; check rain rendering, visibility, water/terrain interactions and private-render restoration across aspects."),
        ("Nightmare Mirror", "Create Mirror through its native source visit; exercise mirror appearances, collision/damage and ownership with both characters/seats."),
        ("Nightmare Dark", "Create Dark through its native source visit; verify darkness/light presentation and native gameplay visibility with independently positioned players."),
        ("Falcon X movement", "Exercise native Falcon air movement, dash, wall behavior and charge/weapon usage in either seat; verify personal effects and checkpoint/menu restoration."),
        ("Blade X Mach Dash", "Exercise native charge/hold/direction/release and collision in all directions from either seat; verify no partner input, sound or damage ownership leakage."),
        ("Blade X attacks", "Exercise Blade saber, charged buster and weapon interactions in either seat; count actor/effect updates and valid damage once per simulation frame."),
        ("Shadow X movement", "Exercise native ceiling/wall attachment, jumps, spikes and armor-dependent route access in either seat; verify camera and moving-solid interaction."),
        ("Shadow X attacks", "Exercise Shadow charge/saber/projectiles and weapon restrictions in either seat; verify damage, voice and effect ownership."),
        ("Ultimate X", "Enable only through the supported native code/unlock path; test Nova Strike, charge, resource use, menus and seat ownership; disclose any bypassed progression."),
        ("Zero techniques", "Earn every Investigator technique then exercise native directional/air/ground command conditions in either seat; validate accepted hits, personal energy and actor ownership."),
        ("Black Zero", "Unlock/select through the supported native path; verify palette, defense/offense and native bonus parts/technique behavior in either seat and after cold load."),
        ("Armor capsule collection", "Reach every capsule and collect by either seat; verify native character restrictions, dialogue owner, per-piece grant and armor-completion unlock."),
        ("Heart and weapon upgrades", "Collect every authored Heart Tank and Energy/Life Up; verify supported sharing policy, cap/HUD change, single consumption and native save retention."),
        ("Subtank collection and filling", "Collect each tank then fill at full health/weapon energy with either seat; verify recipient, capacity and no duplicated fill on split/private rendering."),
        ("Rank-limited parts equipment", "At each rank capacity, independently open personal menus, equip/unequip normal and limited-use parts; verify X/Zero restrictions and consumption on actual use."),
        ("Amazon Area terrain", "Audit narrow ceilings, blind drops, moving terrain and boss door from either camera/scene owner; verify alternate teleport and native destination."),
        ("North Pole ice and avalanches", "Exercise ice blocks, avalanche/spike/cave sections and armor-dependent access with both players; retain contact, death/retry and alternate-route evidence."),
        ("Magma Nightmare Snake rooms", "Exercise every scripted Snake wave/room, vertical scrolling, moving lava and exit; verify native wave prerequisites and either-player admission."),
        ("Recycle Lab press", "Exercise compressing/crushing solids and scrap/terrain changes at primary checkpoint sections; verify safe riding and lethal contact for each seat."),
        ("Recycle Lab Ride Armor", "Enter/exit native Ride Armor with either seat, collide/attack/take damage and transition/lose it; verify ownership, passenger policy and retry."),
        ("Central Museum room selection", "Enumerate native room-choice state and every realized room chain/warp, mapping the 516 authored primary records; verify randomized variants rather than one lucky route."),
        ("Inami Temple acid rain", "Exercise rain exposure/shelter, recovery, switches and actual hazard damage by each seat across camera separation; verify native route progression."),
        ("Laser Institute mirrors", "Exercise native laser/mirror aiming, blocking, solidity, teleport rooms and boss/alternate-door requirements with each seat and the partner offscreen."),
        ("Weapon Center Illumina", "Exercise the native large enemy/projectile sequence, scrolling and destruction/transition triggers with either attacker/camera owner; retain alternate-area admission."),
        ("Fortress armor-sensitive geometry", "Run each native X/Zero route and all supported armor movement sets through Gate-lab terrain, spikes, large gaps and moving solids; record actual access restrictions."),
        ("Native stage prerequisites", "Unlock fortress through each supported native route, including soul/rank and boss conditions; verify stage select/report plus reload without pre-setting success flags."),
        ("Character progression divergence", "Earn upgrades/techniques with differing X/Zero history and swap seats/menus; verify intended shared and personal progress, scene identity and native restrictions."),
        ("Private-card save/load", "Save from stage select/report, cold boot and continue with private copies; compare items, armor, parts, techniques, souls/ranks, found Reploids, Nightmare state and campaign flags."),
        ("Current-build snapshot mid-mechanic", "Save/load and rewind/rollback where supported during rescue, infection, Snake waves, room warps, armor movement and Gate fight; verify current-build state and native-card isolation."),
        ("Netplay campaign traversal", "Run actual two-peer stage clear, alternate teleport, refight and ending transitions under latency/jitter; compare accepted inputs, core/mod checksums and native progression at every boundary."),
    ]
    mechanics = [obligation(len(campaign) + index + 1, title, procedure)
                 for index, (title, procedure) in enumerate(scenarios)]
    return campaign, mechanics


def inventory(exe_path: Path, bin_path: Path | None = None,
              disc_path: Path | None = None) -> dict:
    image = exe_path.read_bytes()
    exe = Executable(image)
    if sha256(image) != EXE_SHA256:
        raise ValueError("Unsupported EXE: require original SLUS-01395 USA v1.1 SHA-256")
    if bin_path is not None and disc_path is not None:
        raise ValueError("Choose either extracted BIN or raw disc")
    report = dict(format_version=1, source="Original SLUS-01395 USA v1.1",
        source_sha256=sha256(image),
        checkpoint_evidence=dict(loader="80029B8C..80029D14", root="80073300",
            root_end_exclusive="800733B8", pointer_region="80073134..80073300",
            record_region="80072108..80073134", record_stride=36,
            native_index="(stage*2+section)*4, then checkpoint*4"),
        semantic_reference=dict(name="Mega Man X6 Tweaks Workbook v2.0",
            sha256="6855194c79f0830ee77b86901bc1997a481ce62de17dfaaced79d976d840e552",
            sheets=["PlaythroughTable", "ObjectOriginTable", "RescReploids", "Rank", "NightEftTable"],
            limits="Names/roles are research labels; runtime reachability is unverified."),
        locations=checkpoint_inventory(exe),
        coverage_rules=dict(initial_status="unverified",
            evidence="Record candidate identities, prerequisites/bypasses, inputs, RAM/actor observations, visuals and muted audio as applicable",
            scope="Actual authored table records, not proof of mechanics, reachability or complete dynamic actor/route coverage"))
    archive = bin_path.read_bytes() if bin_path is not None else None
    if disc_path is not None:
        disc = RawDisc(disc_path)
        try:
            files = disc.inventory_files()
        finally:
            disc.stream.close()
        if files["SLUS_013.95"] != image:
            raise ValueError("Disc and supplied EXE differ")
        archive = files["ROCK_X6.BIN"]
        report["disc_input"] = dict(format="raw2352", size=disc.size,
            verification="Selected EXE and BIN bytes pinned; no whole-disc hash claimed")
    if archive is not None:
        if sha256(archive) != BIN_SHA256:
            raise ValueError("Unsupported ROCK_X6.BIN: require original USA v1.1 SHA-256")
        members = archive_members(archive)
        report["bin_sha256"] = sha256(archive)
        report["placement_evidence"] = dict(
            primary="80029F38..8002A338 indexes8007349C; eight-byte records; byte3==15 terminates",
            secondary="8002A438..8002A468 indexes80073554; 8002A4E4 native entry producer",
            loader="80013E54..80013E80 selects8006DB78; destination word80010000=800E9860",
            archive="80016780..80016858 copies59 {sector,size} descriptors; two-sector header",
            limits="Static tables include scenery/controllers/variant records. Dynamic producers, native prerequisites and runtime actor identities require separate audit.")
        for key, root in PLACEMENT_ROOTS:
            sections = []
            for slot in range(SLOT_COUNT):
                table = exe.word(root + slot * 4)
                if not table:
                    continue
                member_index = struct.unpack_from("<H", image, exe.offset(OVERLAY_SELECTOR + slot * 2, 2))[0]
                if not 2 <= member_index <= 32:
                    raise ValueError("Placement table selects unexpected stage overlay")
                member = members[member_index]
                start = member["sector"] * 2048
                placements = placement_list(archive[start:start + member["size"]], table, OVERLAY_BASE)
                sections.append(dict(stage=slot // 2, section=slot % 2,
                    stage_name=STAGES[slot // 2][0], table=f"{table:08X}",
                    loader_member=member_index, source_member=member,
                    placements=placements))
            report[key] = sections
        # ObjectOriginTable identifies category4/object4 as rescuable Reploids.
        # All 128 subtypes occur exactly once across the 23 original tables.
        reploids = []
        for section in report["placement_sections"]:
            for row in section["placements"]:
                if row["object_id"] == 4 and row["category"] == 4:
                    reploids.append(dict(id=f"reploid-{row['subtype']:03d}",
                        native_id=row["subtype"], stage=section["stage"], section=section["section"],
                        placement_index=row["index"], address=row["address"], x=row["x"], y=row["y"],
                        status="unverified", checks={key: "unverified" for key in
                            ("rescue_p1", "rescue_p2", "simultaneous_contact", "infection_loss",
                             "reward_once", "retry_reentry", "native_card_cold_continue")}))
        if Counter(row["native_id"] for row in reploids) != Counter(range(128)):
            raise ValueError("Original Reploid placement coverage differs from 128 unique IDs")
        report["reploids"] = sorted(reploids, key=lambda row: row["native_id"])
    sections = []
    for row in report.get("placement_sections", []):
        sections.append(dict(stage=row["stage"], section=row["section"],
            locations=[loc for loc in report["locations"]
                       if (loc["stage"], loc["section"]) == (row["stage"], row["section"])],
            primary_count=len(row["placements"]),
            secondary_count=sum(len(alt["placements"]) for alt in report["secondary_placement_sections"]
                if (alt["stage"], alt["section"]) == (row["stage"], row["section"]))))
    # Reserve 001..023 for original placement sections even in EXE-only mode.
    if sections:
        campaign, mechanics = obligations(sections)
    else:
        _, mechanics = obligations([])
        for index, row in enumerate(mechanics, 24):
            row["id"] = f"X6-{index:03d}"
        campaign = []
    report["campaign_obligations"], report["mechanics_obligations"] = campaign, mechanics
    report["known_gaps"] = [
        "Native slots09/0A have checkpoint records but unresolved semantic roles.",
        "Menu/cutscene namespaces have records; these are not asserted playable routes.",
        "Recycle Lab section0 contains four checkpoint records not enumerated by the workbook checkpoint note.",
        "Refight slot0C/0 contains18 checkpoint records; admission/ordering and dynamic bosses still need native runtime evidence.",
        "Central Museum authored records include room variants; randomized room-choice graph and reachable combinations are unverified.",
        "Boss-stage identity depends on story/character/encounter state; alternate tables alone do not enumerate Nightmare Zero/High Max/Dynamo substitutions.",
        "Dynamic actors, every route/exit, actor identity mapping and transitions are not fully derived from these static tables.",
        "No local co-op or netplay gameplay validation is implied by inventory extraction."]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--bin", type=Path, help="Extracted original ROCK_X6.BIN")
    source.add_argument("--disc", type=Path, help="Original raw2352 .bin disc")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Compare existing report without writing")
    args = parser.parse_args()
    report = inventory(args.exe, args.bin, args.disc)
    if args.check:
        if json.loads(args.out.read_text(encoding="utf-8")) != report:
            raise SystemExit("Content inventory differs from source-derived report")
    else:
        with args.out.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    print(f"{len(report['locations'])} checkpoint records; all gameplay unverified")
    for key, _ in PLACEMENT_ROOTS:
        if key in report:
            print(f"{key}: {sum(len(r['placements']) for r in report[key])} records / {len(report[key])} sections")
    print(f"{len(report['campaign_obligations']) + len(report['mechanics_obligations'])} X6-specific obligations")


if __name__ == "__main__":
    main()
