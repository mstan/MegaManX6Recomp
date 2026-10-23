"""Read-only R14 portal observations; automatic approach/setup remains unproven.

No launcher, pad commands, checkpoint/position writes, success/counter writes,
native cards, SDK changes or ledger results. Each block is individually atomic;
native and private-publication RPCs are deliberately not a joint actor sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import coop_debug as debug
import mmx6_coop_checkpoint as checkpoint
import inventory_mmx6_coop_content as content

BASE, END = 0x8008EF48, 0x800F3A00
SIZE = END - BASE  # 412344 bytes; hex envelope fits the existing 1 MiB client.
POOL, STRIDE, SLOTS = BASE, 0x9C, 48
PLAYER, CAMERA, PLAY, RECORD = 0x800970A0, 0x800971F8, 0x800CCED0, 0x800F2B0C
BIN_TABLE, ARCHIVE_LBA = 0x800E0B58, 211185
SOURCE_MEMBER_SHA = "c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5"
DESTINATION_MEMBER_SHA = "7f49ac29077a76c6dc0aaafc474ad4d4eece65402282549de2f1ff2b5d748aef"
SOURCE_WINDOWS = (
    (0x800EBD80, 0xC1C, "649b1982448e991220f590c33c2e63ea0851750ec7a6dd78038f06604738365f"),
    (0x800F38B8, 0x7C, "3ddf40bbf8a26b1afbb70e52e7f8630bfbe88bdee0c7ea3a00df5ea5acf5601c"),
    (0x800E9864, 0x14, "53b05d275b9e87395fd528643ec36cb8907090872218b132cd804162b4ee7f43"),
)
SETUP_GAP = "CP3's authored spawn is 128px above the portal; safe terrain and a traversable approach remain unproven"
COHERENCE_GAP = "Native portal/namespace and published private-player blocks are separate RPCs"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _pointer(value):
    return not value & 1 and (0x80010000 <= value < 0x80200000 or
                             0x9F000000 <= value < 0xA0000000)


def _body(raw):
    if len(raw) != debug.BODY_BYTES:
        raise debug.DebugError("Truncated portal-case player body")
    word = lambda at: struct.unpack_from("<I", raw, at)[0]
    phase, action, hp = raw[4], raw[5], raw[0x5C]
    return dict(active=raw[0], character=raw[2], visible=raw[3], phase=phase, action=action, hp=hp,
        x_raw=struct.unpack_from("<i", raw, 8)[0], y_raw=struct.unpack_from("<i", raw, 12)[0],
        terrain=raw[0x67], contacts=raw[0x70], iframe=raw[0x61],
        locks=[raw[0x7A], raw[0xD0], raw[0xD4]], facing=raw[0x15],
        attack_box=word(0x50), damage_box=word(0x54), body_box=word(0x68),
        compression=word(0x38), assembly=word(0x3C),
        page=struct.unpack_from("<H", raw, 0x40)[0], clut=struct.unpack_from("<H", raw, 0x42)[0],
        native_ground_contact=bool(raw[0] and raw[3] and phase == 1 and action >= 2 and
            0 < hp < 0x80 and not raw[0x67] and raw[0x70] & 8 and
            not (raw[0x7A] | raw[0xD0] | raw[0xD4]) and _pointer(word(0x68))),
        resource_pointers_valid=_pointer(word(0x38)) and _pointer(word(0x3C)), raw_hex=raw.hex())


def source_plan(original: Path, disc: Path, inventory: Path | None = None) -> dict:
    """Derive source checkpoints and selected immutable asset metadata only."""
    exe = checkpoint.original_executable(original)
    inventory = inventory or Path(__file__).resolve().parents[1] / "docs/COOP_X6_CONTENT.json"
    data, locations, sections = checkpoint.verified_inventory(inventory, exe)
    source = next(s for s in data["placement_sections"] if (s["stage"], s["section"]) == (4, 0))
    destination = next(s for s in data["placement_sections"] if (s["stage"], s["section"]) == (20, 1))
    record = source["placements"][18]
    if tuple(record[k] for k in ("address", "object_id", "subtype", "category", "x", "y")) != \
            ("800F2B0C", 0x1C, 1, 0, 1552, 1584):
        raise ValueError("Frozen portal origin differs")
    raw = content.RawDisc(disc)
    try:
        archive = raw.extent(ARCHIVE_LBA, 1665024)
    finally:
        raw.stream.close()
    if sha(archive) != content.BIN_SHA256:
        raise ValueError("Portal plan requires the pinned original archive")
    members = content.archive_members(archive)
    windows = []
    for native, expected in ((source, SOURCE_MEMBER_SHA), (destination, DESTINATION_MEMBER_SHA)):
        member = members[native["loader_member"]]
        if member != native["source_member"] or member["sha256"] != expected:
            raise ValueError("Selected original portal/destination member differs")
        payload = archive[member["sector"] * 2048:member["sector"] * 2048 + member["size"]]
        if native is source:
            for address, size, digest in SOURCE_WINDOWS:
                if sha(payload[address-content.OVERLAY_BASE:address-content.OVERLAY_BASE+size]) != digest:
                    raise ValueError("Original portal source closure differs")
            if payload[RECORD-content.OVERLAY_BASE:RECORD-content.OVERLAY_BASE+8] != struct.pack("<4B2h", 0, 28, 1, 0, 1552, 1584):
                raise ValueError("Original authored portal bytes differ")
        else:
            windows.append(dict(address=content.OVERLAY_BASE, size=0x1000, sha256=sha(payload[:0x1000])))
    ranked = sorted((r for r in locations if (r["stage"], r["section"]) == (4, 0)),
                    key=lambda r: ((r["player"]["x"]-1552)**2 + (r["player"]["y"]-1584)**2, r["checkpoint"]))
    return dict(schema=1, scope="R14 Recycle record18 read-only setup/observation preparation",
        original_exe_sha256=content.EXE_SHA256, original_archive_sha256=content.BIN_SHA256,
        inventory_sha256=checkpoint.INVENTORY_SHA256, portal=record,
        nearest_authored_checkpoint=ranked[0], alternate_approach_checkpoint=checkpoint.select(locations, sections, 4, 0, 2),
        distance_squared=(ranked[0]["player"]["x"]-1552)**2+(ranked[0]["player"]["y"]-1584)**2,
        source_section=source | {"placements": [record]},
        destination_section=destination | {"placements": []},
        destination=checkpoint.select(locations, sections, 20, 1, 0),
        native_destination_path=["800EC978 writes41h", "8001E3D4 ->80042F7C maps4 to20/1",
                                 "8001E930 clears checkpoint before major9 initializer8001E1BC"],
        destination_code_windows=windows, automatic_actions=[], proven_safe_contact_positions=[],
        setup_status="unverified_setup_gap", setup_gap=SETUP_GAP, coherence_gap=COHERENCE_GAP,
        bypass_policy="Any later private checkpoint/position/prerequisite setup must be explicit and tainted; no portal/transition/success writes",
        limits=["Nearest by authored squared distance in the same section is not reachability or ground proof",
                "CP3 camera locksX1568/Y1440; source spawn1728/1456 is176right/128above portal",
                "Destination20/1/CP0 follows original41h mapping and major8 CP reset; actual load remains unverified",
                "BIN descriptor and code prefix presence alone are not completed streaming/GPU or artwork evidence"])


def _read(request, address, size):
    if not callable(request) or type(address) is not int or type(size) is not int or \
            not 0 <= address <= 0xFFFFFFFF or not 1 <= size <= SIZE or address + size > 0x100000000:
        raise ValueError("Expected owned read-only request and bounded address/size")
    response = request("read_ram", addr=hex(address), len=size)
    if not isinstance(response, dict) or response.get("ok") is not True or \
            response.get("len") != size or not isinstance(response.get("hex"), str) or \
            len(response["hex"]) != size * 2:
        raise debug.DebugError("Portal read_ram returned an invalid/truncated bounded envelope")
    try:
        if int(response.get("addr", ""), 0) != address:
            raise ValueError("address mismatch")
        raw = bytes.fromhex(response["hex"])
    except (ValueError, TypeError) as error:
        raise debug.DebugError("Portal read_ram address/hex differs") from error
    if len(raw) != size:
        raise debug.DebugError("Portal read_ram decoded length differs")
    return raw


def parse_native(raw: bytes) -> dict:
    if len(raw) != SIZE:
        raise debug.DebugError("Portal native block has the wrong extent")
    def read(address, count):
        if count < 0 or address < BASE or address + count > END:
            raise debug.DebugError("Native portal field outside coherent block")
        return raw[address-BASE:address-BASE+count]
    byte = lambda a: read(a, 1)[0]
    word = lambda a: struct.unpack("<I", read(a, 4))[0]
    mode, phase, stage, section, cp = [byte(PLAY+o) for o in (0, 1, 12, 13, 0x1D)]
    source_namespace = (stage, section) == (4, 0)
    portal = None
    if source_namespace:
        for slot in range(SLOTS):
            actor = read(POOL+slot*STRIDE, STRIDE)
            if not (actor[0] & 1) or struct.unpack_from("<I", actor, 0x10)[0] != RECORD:
                continue  # A freed native slot can retain an old origin pointer.
            if portal is not None:
                raise debug.DebugError("Duplicate live portal origin")
            if actor[1:3] != bytes((28, 1)) or actor[4] > 3 or actor[5] > 5 or actor[6] > 2:
                raise debug.DebugError("Native origin-bound portal type/phase contract differs")
            portal = dict(slot=slot, address=POOL+slot*STRIDE, origin=RECORD,
                flags=actor[0], type=actor[1], subtype=actor[2], visible=actor[3],
                phase=actor[4], action=actor[5], subaction=actor[6],
                x_raw=struct.unpack_from("<i", actor, 8)[0], y_raw=struct.unpack_from("<i", actor, 12)[0],
                timer=struct.unpack_from("<h", actor, 0x7C)[0], saved_body_box=struct.unpack_from("<I", actor, 0x88)[0],
                raw_hex=actor.hex())
    record = read(RECORD, 8)
    original_record = struct.pack("<4B2h", 0, 28, 1, 0, 1552, 1584)
    record_match = record in (original_record, bytes((1,))+original_record[1:])
    source_windows = [dict(address=a, size=n, sha256=sha(read(a, n)), matches=sha(read(a, n)) == h)
                      for a, n, h in SOURCE_WINDOWS]
    camera = read(CAMERA, 0x54)
    camera_fields = dict(zip(("x", "y", "min_x", "max_x", "min_y", "max_y"),
        (struct.unpack_from("<h", camera, o)[0] for o in (0xA, 0xE, 0x1E, 0x1C, 0x22, 0x20))))
    descriptors = {str(index): list(struct.unpack("<II", read(BIN_TABLE+index*8, 8))) for index in (6, 28)}
    return dict(kind="single_rpc_native_block", raw_sha256=sha(raw), raw_bytes=SIZE,
        mode=mode, phase=phase, stage=stage, section=section, checkpoint=cp,
        native_timer=word(PLAY+0x90), transition=byte(PLAY+0x0F), fade=struct.unpack("<b", read(0x80097424, 1))[0],
        freeze=byte(PLAY+0x10), shared_entry_lock=byte(PLAY+0x1C), loader_status=word(0x8009509C),
        portal=portal, source_record_hex=record.hex(), source_record_match=record_match,
        source_windows=source_windows, native_bin_descriptors=descriptors,
        source_closure_present=bool(source_namespace and record_match and all(r["matches"] for r in source_windows) and
            word(0x800F308C) == 0x800EC678 and descriptors["6"] == [211338, 42944]),
        resident_player=_body(read(PLAYER, debug.BODY_BYTES)), resident_attribution="native resident character only; not a private seat attribution",
        camera=camera_fields, camera_hex=camera.hex(), play_hex=read(PLAY, 0xE0).hex(),
        destination_code_prefix_sha256=sha(read(content.OVERLAY_BASE, 0x1000)))


def observe_native(owned_request) -> dict:
    """One larger read_ram, not DebugClient.read's64KiB convenience wrapper."""
    return parse_native(_read(owned_request, BASE, SIZE))


def observe_publication(owned_request, diagnostic_address=debug.DIAGNOSTIC_ADDRESS) -> dict:
    if type(diagnostic_address) is not int or diagnostic_address & 3 or \
            not 0x9F000000 <= diagnostic_address <= 0xA0000000-debug.DIAGNOSTIC_BYTES:
        raise ValueError("Expected actual owned diagnostic allocation address")
    raw = _read(owned_request, diagnostic_address, debug.DIAGNOSTIC_BYTES)
    publication = debug.parse_diagnostic(raw)
    return dict(kind="single_rpc_private_publication", observation=publication.json(),
        raw_sha256=sha(raw), players=[_body(raw[0x1800:0x1958]), _body(raw[0x100:0x258])],
        namespace="unavailable in this base publication", portal_contact="unavailable in this base publication")


def observe_context(ctx: dict, *, expected_exe_sha256: str) -> dict:
    """Owned launcher adapters supply verified per-process read-only callbacks.

    This helper neither owns processes nor moves actors. It cannot qualify R14.
    """
    if not isinstance(ctx, dict) or not isinstance(expected_exe_sha256, str) or \
            not re.fullmatch("[0-9a-f]{64}", expected_exe_sha256) or ctx.get("candidate_exe_sha256") != expected_exe_sha256:
        raise ValueError("Portal observer needs the explicitly verified actual candidate image")
    requests = ctx.get("read_only_requests")
    expected_count = {"local": 1, "netplay": 2}.get(ctx.get("mode"))
    if expected_count is None or not isinstance(requests, (list, tuple)) or len(requests) != expected_count or not all(callable(r) for r in requests):
        raise ValueError("Expected one owned local or two owned peer read-only callbacks")
    addresses = ctx.get("diagnostic_addresses", [debug.DIAGNOSTIC_ADDRESS]*expected_count)
    if not isinstance(addresses, (list, tuple)) or len(addresses) != expected_count:
        raise ValueError("Diagnostic addresses must belong to each owned process")
    if not isinstance(ctx.get("report"), dict):
        raise ValueError("Owned report is required to retain partial observation failures")
    case = dict(candidate_exe_sha256=expected_exe_sha256, mode=ctx["mode"], status="unverified_setup_gap",
        setup_gap=SETUP_GAP, coherence_gap=COHERENCE_GAP, ledger_status="unverified",
        peers=[],
        checks=dict(p1_outside_p2_actual_contact=False, accepted_input_route=False,
                    safe_source_feet=False, native_destination_and_both_arrivals=False,
                    independent_controls=False, completed_composed_capture=False),
        limits=["Two individually coherent RPCs per peer, not one combined private/native snapshot",
                "Source floor/route and original accepted-input runner remain to be established",
                "No loader/artwork/passenger/input success is inferred from this read-only sample"])
    ctx["report"].setdefault("recycle_portal_observer", []).append(case)
    try:
        for request, address in zip(requests, addresses):
            peer = {};case["peers"].append(peer)
            peer["native"] = observe_native(request)
            peer["publication"] = observe_publication(request, address)
    except Exception as error:
        case.update(status="failed_observation_setup_gap", error=str(error), error_type=type(error).__name__)
        raise
    return case


def reduce_native_transition(rows: list[dict], plan: dict) -> dict:
    """Conservative partial native observations, never aggregate admission/pass.

    Missing intermediate states stay missing. No private-seat correlation,
    accepted input, GPU completion or actual two-player control is inferred.
    """
    checks = dict(source_portal_seen=False, native_action2_seen=False, native_freeze_seen=False,
        native_41h_and_fade_seen=False, major8_seen=False, major9_seen=False,
        destination_native_ready_seen=False, published_both_arrivals=False,
        p1_outside_p2_contact=False, independent_controls=False, composed_capture=False)
    identity = None
    phase = 0
    for row in rows:
        portal = row.get("portal")
        current = tuple(portal.get(k) for k in ("address", "slot", "origin", "type", "subtype")) if portal else None
        if phase == 0 and (row["mode"], row["phase"]) == (10, 0) and row.get("source_closure_present") and \
                portal and current[2:] == (RECORD, 28, 1) and (portal["phase"], portal["action"]) == (1, 1):
            identity = current;checks["source_portal_seen"] = True;phase = 1
        elif phase in (1, 2) and portal and current == identity and row.get("source_closure_present") and (portal["phase"], portal["action"]) == (1, 2):
            checks["native_action2_seen"] = True;phase = 2
            if row["freeze"] == 2 and _pointer(portal["saved_body_box"]):checks["native_freeze_seen"] = True
            if row["transition"] == 0x41 and row["fade"] != 0 and checks["native_freeze_seen"]:
                checks["native_41h_and_fade_seen"] = True;phase = 3
        elif phase == 3 and (row["mode"], row["stage"], row["section"]) == (8, 20, 1):
            checks["major8_seen"] = True;phase = 4
        elif phase == 4 and (row["mode"], row["stage"], row["section"], row["checkpoint"]) == (9, 20, 1, 0):
            checks["major9_seen"] = True;phase = 5
        elif phase == 5 and (row["mode"], row["phase"], row["stage"], row["section"], row["checkpoint"]) == (10, 0, 20, 1, 0):
            target = plan["destination"]
            descriptor = plan["destination_section"]["source_member"]
            checks["destination_native_ready_seen"] |= bool(row["loader_status"] == 2 and not row["transition"] and
                not row["fade"] and not row["freeze"] and not row["shared_entry_lock"] and
                row["camera"] == target["camera"] and row["resident_player"]["native_ground_contact"] and
                row["resident_player"]["resource_pointers_valid"] and
                row["native_bin_descriptors"]["28"] == [ARCHIVE_LBA+descriptor["sector"], descriptor["size"]] and
                row["destination_code_prefix_sha256"] == plan["destination_code_windows"][0]["sha256"])
    return dict(status="unverified_setup_gap", ledger_status="unverified", checks=checks,
        setup_gap=SETUP_GAP, coherence_gap=COHERENCE_GAP,
        limitations=["Partial native transition only; missed states are not inferred",
                    "Native code/descriptor and one resident's ground flag are not completed loader/GPU or both-player proof"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps(source_plan(args.original, args.disc, args.inventory), indent=2))
