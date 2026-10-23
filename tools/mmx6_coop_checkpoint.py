"""Source-bound PRIVATE OFFLINE checkpoint setup; never progression evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import time

import coop_debug as debug

import inventory_mmx6_coop_content as content

SPANS = ((0x8001E6E4, 0x8001E730), (0x8001E914, 0x8001E9EC),
         (0x8001E1BC, 0x8001E32C), (0x80029B8C, 0x80029D18))
CAPABILITY = 0x31504B43  # CKP1, little endian.
INVENTORY_SHA256 = "67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad"

# Original bytes are read, never distributed. This narrowly scoped policy is
# reproduced by camera_source_audit() and checked against resident RAM on entry.
CAMERA_SOURCE_SPANS = (
    (0x80028EBC, 0x3C0, "4089a81cde8dc3d2f2c93cb57f1ba278ae6551a9b5a4a72861600c776610ceca"),
    (0x8002927C, 0xE0, "d9ed7c9aa57753adbcead391e60d469bf4c2f491556743b82c1ef014804e0ace"),
    (0x800294B4, 0x84, "dbbe58ad96183f5246ae4ae8d9618e800cc07b889c992d6423e384fe0b828da8"),
    (0x80029B8C, 0x18C, "d7935b9037f6b1df0020983af5feb7accfa5ff87357d7e1089563d7a70d6b058"),
    (0x8005211C, 0x1E4, "7abab3ed7e47891f68c687a136683ce42d45e8a2d590b85016f2d193f4c7a240"),
    (0x8006DE94, 4, "bc20286b0ffa86dfd8f5f773c6881b0d84c0933b723e9195643b46ed34bca8ab"),
    (0x8007212C, 36, "7875f0a7e39a4fc9d563c87181b2d58a7e9b1281ac2db1f3d0bbddf7ce441a7c"),
    (0x80073134, 8, "4ed372c528b16f3f21f32642046987fbc5ada461e6548e849613da0ee6c31aef"),
    (0x80073300, 4, "c1b77b08a648d56869d3a8946ad9974de1f18338b543d19d285270c53fca58ea"),
    (0x8007349C, 4, "6606ea3db93fc0dec5be3e8a8de19f58d67fb5e5f262141297edf13a81f1692e"),
    (0x800791E8, 0x88, "a4e91ddfa0ac5997b1054ded8dba4dff98e83d1c4d805254f2c08c89bc52afbc"),
    (0x80079D70, 4, "cf54956d97bf0d559e0e973225da06f72f041880658a52f88113dc26e7d2feaa"),
    (0x800FA25C, 8, "f6cb35fe49b2007b256fccfef7d8787fb282a3784bff49d42eca907e904f61e3"),
    (0x800FA6E0, 4, "b866e554ad4ec8f23cf7012ba8cbbf1d0b47e8089c8b0a94c6023e93c88908de"),
)
INTRO_MEMBER_SHA256 = "d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607"
CP1_REGION = (2112, 2143, 1040, 1135, 0xFFFF, 0xFFFF, 896, 0xFFFF)


def camera_source_audit(exe: content.Executable, intro: bytes) -> dict:
    """Reproduce only the original EXE and selected BIN2 camera closure."""
    if hashlib.sha256(exe.data).hexdigest() != content.EXE_SHA256 or \
            hashlib.sha256(intro).hexdigest() != INTRO_MEMBER_SHA256:
        raise ValueError("Camera audit needs the pinned original EXE and intro BIN2")
    spans = []
    for address, size, expected in CAMERA_SOURCE_SPANS:
        payload = (exe.data[exe.offset(address, size):exe.offset(address, size)+size]
                   if address < 0x800E9860 else intro[address-0x800E9860:address-0x800E9860+size])
        actual = hashlib.sha256(payload).hexdigest()
        if len(payload) != size or actual != expected:
            raise ValueError(f"Camera source span differs at {address:08X}")
        spans.append(dict(address=f"{address:08X}", size=size, sha256=actual))
    if struct.unpack_from("<8H", exe.data, exe.offset(0x80079260, 16)) != CP1_REGION:
        raise ValueError("Original CP1 dynamic region differs")
    return dict(source_exe_sha256=content.EXE_SHA256, intro_member_sha256=INTRO_MEMBER_SHA256,
        scope=dict(stage=0, section=0, checkpoint=1, record="8007212C"),
        spans=spans, placement=dict(address="800FA25C", index=9, category=3, type=0, subtype=7),
        region=dict(address="80079260", values=list(CP1_REGION)),
        native_dispatch=dict(stage_root="8006DE94", intro_type_table="800FA6E0", handler="80052258",
            phase_table="800791E8", initializer="80052294", update="8005211C",
            region_root="80079D70", intro_regions="800791F0", binding_offset="18"),
        current_min_y_store="8002917C", target_min_y_store="800521F4",
        fixed_point=dict(expression="signed16(P1.integerY-CAM.integerY-CAM.signedHalfword2C)",
            branch="8002912C BGEZ a1 directly to 8002917C", prerequisite="nonnegative result and targetMinY<cameraY"),
        status="source_audit_only_native_qualification_pending")


def camera_source_evidence(client, target: dict) -> dict:
    """Read-only resident closure guards; a mismatch keeps authored-only policy."""
    evidence = dict(verified=False, source_exe_sha256=content.EXE_SHA256, spans=[])
    if (target.get("stage"), target.get("section"), target.get("checkpoint"), target.get("record")) != \
            (0, 0, 1, "8007212C"):
        return evidence
    for address, size, expected in CAMERA_SOURCE_SPANS:
        payload = client.read(address, size)
        actual = hashlib.sha256(payload).hexdigest()
        evidence["spans"].append(dict(address=f"{address:08X}", size=len(payload), sha256=actual))
        if len(payload) != size or actual != expected:
            return evidence
    evidence["verified"] = True
    return evidence


def dynamic_cp1_camera(target: dict, body: bytes, camera: bytes, evidence: dict | None) -> bool:
    """Exact original region plus nonnegative smoother branch fixed point.

    8002912C branches directly to SH A1,22(A0) with signed16
    A1=PLAYER.integerY-CAM.integerY-CAM[2C]. Do not repair that native formula.
    """
    if not evidence or evidence.get("verified") is not True or \
            evidence.get("source_exe_sha256") != content.EXE_SHA256 or \
            evidence.get("spans") != [dict(address=f"{a:08X}", size=n, sha256=h)
                                      for a,n,h in CAMERA_SOURCE_SPANS] or \
            (target.get("stage"), target.get("section"), target.get("checkpoint"), target.get("record")) != \
            (0, 0, 1, "8007212C") or len(camera) != 0x54 or \
            target.get("camera") != dict(x=1968,y=944,min_x=1968,max_x=5120,min_y=944,max_y=944):
        return False
    px, py = struct.unpack_from("<h", body, 0xA)[0], struct.unpack_from("<h", body, 0xE)[0]
    x, y = struct.unpack_from("<h", camera, 0xA)[0], struct.unpack_from("<h", camera, 0xE)[0]
    max_x,min_x,max_y,min_y = struct.unpack_from("<4h", camera, 0x1C)
    target_max_x,target_min_x,target_max_y,target_min_y = struct.unpack_from("<4h", camera, 0x24)
    offset = struct.unpack_from("<h", camera, 0x2C)[0]
    expected = ((py-y-offset+0x8000)&0xFFFF)-0x8000
    authored=target["camera"]
    return (CP1_REGION[0] <= px <= CP1_REGION[1] and CP1_REGION[2] <= py <= CP1_REGION[3] and
        (min_x,max_x,max_y)==(authored["min_x"],authored["max_x"],authored["max_y"]) and
        (target_min_x,target_max_x,target_max_y)==(authored["min_x"],authored["max_x"],authored["max_y"]) and
        target_min_y==CP1_REGION[6] and target_min_y<y and expected>=0 and min_y==expected and
        abs(target_min_y-min_y)>2 and offset==0x60 and camera[0]==camera[3]==camera[4]==camera[0x44]==1 and
        camera[0x47]==2 and not body[0xCC] and not body[0xE0] and (x,y)==(authored["x"],authored["y"]))


def fnv32(data: bytes) -> int:
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def original_executable(path: Path) -> content.Executable:
    path = Path(path)
    if path.suffix.lower() == ".bin":
        disc = content.RawDisc(path)
        try:
            payload = disc.inventory_files()["SLUS_013.95"]
        finally:
            disc.stream.close()
    else:
        if path.stat().st_size != 522240:
            raise ValueError("Checkpoint source must be the bounded original EXE or raw BIN")
        payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != content.EXE_SHA256:
        raise ValueError("Checkpoint entry needs original SLUS-01395 USA v1.1 EXE identity")
    return content.Executable(payload)


def inventory(path: Path) -> tuple[dict, list[dict], set[tuple[int, int]]]:
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != INVENTORY_SHA256:
        raise ValueError("Checkpoint inventory must match the frozen source metadata identity")
    data = json.loads(payload.decode("utf-8"))
    rows = data.get("locations", [])
    keys = [(r["stage"], r["section"], r["checkpoint"]) for r in rows]
    if data.get("source_sha256") != content.EXE_SHA256 or len(rows) != 115 or len(set(keys)) != 115:
        raise ValueError("Checkpoint inventory must retain the 115 original unique tuples")
    sections = {(r["stage"], r["section"]) for r in data["placement_sections"]}
    if len(sections) != 23 or sum((r["stage"], r["section"]) in sections for r in rows) != 94:
        raise ValueError("Checkpoint inventory lost authored campaign section bounds")
    return data, rows, sections


def verified_inventory(path: Path, exe: content.Executable):
    data, rows, sections = inventory(path)
    if content.checkpoint_inventory(exe) != rows:
        raise ValueError("Frozen checkpoint metadata differs from original executable tables")
    return data, rows, sections


def select(rows, sections, stage: int, section: int, checkpoint: int) -> dict:
    if any(type(v) is not int or not 0 <= v <= 255 for v in (stage, section, checkpoint)):
        raise ValueError("Checkpoint stage, section and index must be unsigned bytes")
    matches = [r for r in rows if (r["stage"], r["section"], r["checkpoint"]) ==
               (stage, section, checkpoint)]
    if len(matches) != 1:
        raise ValueError("Checkpoint tuple is absent from the immutable 115-record inventory")
    if (stage, section) not in sections:
        raise ValueError("Inventoried menu/cutscene/unresolved namespace is not campaign entry setup")
    return matches[0]


def render_header(path: Path, exe: content.Executable) -> str:
    _, rows, sections = verified_inventory(path, exe)
    lines = ["/* Generated by tools/mmx6_coop_checkpoint.py from the immutable inventory.",
             f" * Original EXE SHA256 {content.EXE_SHA256}",
             f" * Inventory SHA256 {hashlib.sha256(Path(path).read_bytes()).hexdigest()}",
             " * FNV guards detect mismatched resident code/data; they are not cryptographic identity.",
             " * The offline runner separately verifies the complete original EXE SHA256. */",
             "#ifndef MMX6_COOP_CHECKPOINT_DATA_H", "#define MMX6_COOP_CHECKPOINT_DATA_H",
             "typedef struct { uint8_t stage,section,checkpoint,campaign; uint32_t table,record,hash; } Mmx6Checkpoint;",
             "static const Mmx6Checkpoint checkpoint_inventory[115]={"]
    for row in rows:
        record = int(row["record"], 16)
        at = exe.offset(record, 36)
        values = (row["stage"], row["section"], row["checkpoint"],
                  int((row["stage"], row["section"]) in sections), int(row["table"], 16),
                  record, fnv32(exe.data[at:at + 36]))
        lines.append("    {%u,%u,%u,%u,0x%08Xu,0x%08Xu,0x%08Xu}," % values)
    lines += ["};", "typedef struct { uint32_t first,end,hash; } Mmx6CheckpointCode;",
              "static const Mmx6CheckpointCode checkpoint_code[]={"]
    for first, end in SPANS:
        at = exe.offset(first, end - first)
        lines.append("    {0x%08Xu,0x%08Xu,0x%08Xu}," %
                     (first, end, fnv32(exe.data[at:at + end - first])))
    return "\n".join(lines + ["};", "#endif", ""])


def fixture_status(client) -> dict:
    data = client.read(debug.DIAGNOSTIC_ADDRESS + 0xA0, 32)
    if len(data) != 32 or struct.unpack_from("<I", data)[0] != CAPABILITY:
        raise debug.DebugError("Candidate has no private checkpoint-entry capability")
    state, reason, stage, section, checkpoint = data[8:13]
    if state > 5 or reason > 8 or data[28] > 1:
        raise debug.DebugError("Malformed checkpoint fixture publication")
    return dict(generation=struct.unpack_from("<I", data, 4)[0], state=state, reason=reason,
                stage=stage, section=section, checkpoint=checkpoint,
                nonce=struct.unpack_from("<I", data, 16)[0],
                initializer_entries=struct.unpack_from("<I", data, 20)[0],
                record=f"{struct.unpack_from('<I', data, 24)[0]:08X}", tainted=data[28])


def reduce_entry_readiness(target: dict, completed_tick: int, current: dict,
                           native_play: bytes, native_player_camera: bytes, gpu: dict,
                           camera_source: dict | None = None) -> dict:
    """Source-bound settled entry, not merely mode0A plus a cached publication.

    29B8C installs exact spawn X/Y and camera bounds. Guarded intro CP1 also has
    an authored native region changing minY through the original signed branch.
    Native arrival/gravity may
    change Y before control returns, so Y uses actual stable grounded position
    inside the actual camera/GPU viewport, never a guessed spawn-Y tolerance.
    The exact authored-X contract is conservative for scripted moving entries.
    """
    checks = dict(publication_after_completed_receipt=False, enrolled_living_idle_roster=False,
        native_gameplay_tuple=False,native_entry_gates_clear=False,native_p1_visible_idle_grounded=False,
        native_previous_position_settled=False,native_p1_agrees_with_publication=False,
        p1_at_authored_x=False,selected_camera_bounds=False,camera_inside_authored_bounds=False,
        actors_in_current_native_viewport=False,display_enabled=False)
    if len(native_play)!=0x1E or len(native_player_camera) not in (0x198,0x1AC):
        return checks
    try:
        delta=(current["tick"]-completed_tick)&0xFFFFFFFF
        checks["publication_after_completed_receipt"]=0<delta<0x80000000
        players=current["players"]
        checks["enrolled_living_idle_roster"]=(current["ready"]==current["enrolled"]==1 and
            current["failed"]==current["mailbox"]==current["scene_owner"]==current["scene_phase"]==0 and
            current["native_mode"]==10 and current["native_phase"]==current["pause_owner"]==0 and
            tuple(current["lifecycle"])==(0,0) and len(players)==2 and
            [p["character"] for p in players]==[0,1] and
            all(p["active"] and p["state"]==1 and p["action"]==2 and 0<p["hp"]<128 for p in players))
        checks["native_gameplay_tuple"]=(native_play[0],native_play[1],native_play[12],native_play[13],native_play[0x1D])==\
            (10,0,target["stage"],target["section"],target["checkpoint"])
        checks["native_entry_gates_clear"]=all(native_play[at]==0 for at in (0x0F,0x10,0x1C))
        body=native_player_camera[:0x158];camera=native_player_camera[0x158:]
        actor=debug.Player.parse(body)
        checks["native_p1_visible_idle_grounded"]=(actor.active and body[3]==1 and actor.character==0 and
            actor.state==1 and actor.action==2 and 0<actor.hp<128 and not body[0x67] and bool(body[0x70]&8))
        checks["native_previous_position_settled"]=struct.unpack_from("<ii",body,8)==struct.unpack_from("<ii",body,0x18)
        checks["native_p1_agrees_with_publication"]=(actor.x_raw,actor.y_raw,actor.hp)==\
            (players[0]["x_raw"],players[0]["y_raw"],players[0]["hp"])
        checks["p1_at_authored_x"]=actor.x_raw==(target["player"]["x"]<<16)
        x,y=struct.unpack_from("<h",camera,0x0A)[0],struct.unpack_from("<h",camera,0x0E)[0]
        max_x,min_x,max_y,min_y=struct.unpack_from("<hhhh",camera,0x1C)
        authored=target["camera"]
        checks["selected_camera_bounds"]=((min_x,max_x,min_y,max_y)==
            (authored["min_x"],authored["max_x"],authored["min_y"],authored["max_y"]) or
            dynamic_cp1_camera(target,body,camera,camera_source))
        # Legacy receipt key retained: these are now the verified native bounds,
        # either authored directly or the exact guarded original CP1 branch.
        checks["camera_inside_authored_bounds"]=min_x<=x<=max_x and min_y<=y<=max_y
        width,height=gpu.get("width"),gpu.get("height")
        margin=gpu.get("ws",{}).get("x_margin")
        checks["display_enabled"]=type(gpu.get("disabled")) is int and gpu["disabled"]==0
        if all(type(value) is int for value in (width,height,margin)) and width>0 and height>0 and margin>=0:
            checks["actors_in_current_native_viewport"]=all(
                ((x-margin)<<16)<=p["x_raw"]<((x+width+margin)<<16) and
                (y<<16)<=p["y_raw"]<((y+height)<<16)
                for p in players)
    except (KeyError,ValueError,TypeError,struct.error):
        pass
    return checks


def enter_checkpoint(control, client, target: dict, receipt: dict, *, timeout=60, nonce=1) -> dict:
    """One owned offline mailbox transaction; retains partial setup evidence.

    `control` must be the baseline's PID/listener-checked callback. Only the
    existing diagnostic command payload is written; gameplay input afterward
    remains original native input. This operation taints ordinary-input proof.
    """
    import math
    if not math.isfinite(timeout) or not 0 < timeout <= 180 or type(nonce) is not int or not 1 <= nonce <= 0xFFFFFFFF:
        raise ValueError("Checkpoint setup needs a bounded timeout and nonzero uint32 nonce")
    stage, section, checkpoint = (target[key] for key in ("stage", "section", "checkpoint"))
    if any(type(v) is not int or not 0 <= v <= 255 for v in (stage, section, checkpoint)):
        raise ValueError("Checkpoint transaction requires inventoried unsigned-byte selectors")
    receipt.update(kind="private_offline_native_checkpoint_entry", status="failed_setup",
                   prerequisite_bypass=True, ordinary_input_evidence_tainted=True, target=target,
                   source_exe_sha256=content.EXE_SHA256, nonce=nonce, observations=[], checks={},
                   completion_waiting=[],composed_capture_required_after_readiness=True,
                   ledger_status="unverified", artwork_review="pending")
    network = control("netplay_status")
    receipt["network_status"] = network
    if type(network.get("active")) is not int or network["active"] != 0:
        raise debug.DebugError("Checkpoint fixture requires an explicitly inactive owned offline session")
    before = fixture_status(client)
    receipt["before"] = before
    before_players = debug.observe(client)
    receipt["before_players"] = before_players.json()
    if before["state"] in (1, 2) or client.read(debug.DIAGNOSTIC_ADDRESS + 0x50, 1) != b"\0":
        raise debug.DebugError("Another diagnostic fixture operation is pending")
    # Payload first, command byte last; the actual plugin validates the tuple,
    # native code/tables, offline status and stage boundary before mutation.
    payload = bytes((stage, section, checkpoint)) + struct.pack("<I", nonce)
    for offset, value in enumerate(payload, 0x51):
        control("write_ram", addr=hex(debug.DIAGNOSTIC_ADDRESS + offset), val=hex(value))
    control("write_ram", addr=hex(debug.DIAGNOSTIC_ADDRESS + 0x50), val="0x8")
    deadline = time.monotonic() + timeout
    expected_generation = (before["generation"] + 1) & 0xFFFFFFFF
    completed_tick=None
    while time.monotonic() < deadline:
        observed = fixture_status(client)
        receipt["observations"].append(observed)
        if observed["generation"] != before["generation"]:
            if observed["generation"] != expected_generation or observed["nonce"] != nonce:
                raise debug.DebugError("Checkpoint fixture completion belongs to another request")
            if observed["state"] in (4, 5):
                raise debug.DebugError(f"Checkpoint fixture failed/rejected: {observed}")
            if observed["state"] == 3:
                native = client.read(0x800CCED0, 0x1E)
                receipt["native_entry_result"] = native.hex()
                current = debug.observe(client)
                receipt["final_players"] = current.json()
                receipt["checks"] = dict(
                    requested_tuple=(observed["stage"], observed["section"], observed["checkpoint"]) ==
                                    (stage, section, checkpoint),
                    original_initializer_observed_once=observed["initializer_entries"] == 1,
                    inventoried_record=observed["record"] == target["record"],
                    fixture_bypass_retained=observed["tainted"] == 1,
                    native_gameplay=(native[0], native[12], native[13], native[0x1D]) ==
                                    (10, stage, section, checkpoint))
                if not all(receipt["checks"].values()):
                    raise debug.DebugError("Checkpoint entry completion did not match the requested native setup")
                if completed_tick is None:
                    # Payload RPCs can advance the OLD world beyond the
                    # pre-request tick. Anchor AFTER first state3 instead.
                    completed_tick=current.tick
                    receipt["completion_anchor"]=dict(fixture=observed,publication=current.json())
                probe=dict(publication=current.json(),native_play=native.hex(),readiness_computed=False)
                receipt["completion_waiting"].append(probe)
                if "camera_source_evidence" not in receipt:
                    receipt["camera_source_evidence"]=camera_source_evidence(client,target)
                actual=client.read(0x800970A0,0x1AC)  # P1 + entire primary camera in ONE native read.
                probe["native_player_camera"]=actual.hex()
                gpu=control("gpu_state")
                checks=reduce_entry_readiness(target,completed_tick,current.json(),native,actual,gpu,
                    receipt["camera_source_evidence"])
                probe.update(gpu_state=gpu,checks=checks,readiness_computed=True)
                receipt["checks"].update(checks)
                if all(checks.values()):
                    receipt["native_camera_after_entry"] = actual[0x158:].hex()
                    receipt["status"] = "prerequisite_bypass_setup_completed_artwork_pending"
                    return receipt
        time.sleep(.03)
    raise debug.DebugError("Checkpoint fixture did not complete native entry and co-op enrollment before its deadline")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--header", type=Path)
    parser.add_argument("--camera-audit", action="store_true",
                        help="Print source-only JSON from original raw BIN, without writing files")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.camera_audit:
        if args.original.suffix.lower()!=".bin":
            parser.error("Camera audit requires the original raw BIN containing EXE and selected intro member")
        disc=content.RawDisc(args.original)
        try:
            files=disc.inventory_files()
        finally:
            disc.stream.close()
        archive=files["ROCK_X6.BIN"]
        if hashlib.sha256(archive).hexdigest()!=content.BIN_SHA256:
            parser.error("Camera audit original archive identity differs")
        member=content.archive_members(archive)[2]
        start=member["sector"]*2048
        print(json.dumps(camera_source_audit(content.Executable(files["SLUS_013.95"]),
            archive[start:start+member["size"]]),indent=2))
        raise SystemExit(0)
    if args.inventory is None or args.header is None:
        parser.error("Header reproduction requires --inventory and --header")
    rendered = render_header(args.inventory, original_executable(args.original))
    if args.check:
        if args.header.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Checkpoint guard header differs from original source/inventory")
    else:
        with args.header.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
