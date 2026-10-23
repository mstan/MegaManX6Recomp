"""Own one offline Recycle portal trial; setup is tainted and artwork pending.

Only existing diagnostic commands8 (CP2) and4 (both positions/previous) are
written. Original landing, controls, portal, fade and loader execute themselves.
Native and private publications remain separately attributed RPC observations.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import time
import tomllib
import traceback

import coop_debug as debug
import mmx6_coop_checkpoint as checkpoint
import mmx6_coop_collision_boxes as boxes
import mmx6_coop_recycle_portal as portal
import mmx6_coop_recycle_setup as setup
import mmx6_coop_reploid059 as reploid
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_personal_menu as offline

SUCCESS = "offline_portal_observations_complete_artwork_and_contact_attribution_pending"
X_BODY = (0x80073D50, bytes((0, 2, 11, 19)))
Z_BODY = (0x80073D54, bytes((0, 3, 11, 19)))
SCRATCH = (0x80097438, 0x8019A4B0, 0x801AF8B0)
RIGHT = 0x20


def require(condition, message):
    if not condition:
        raise debug.DebugError(message)


def verify_offline(status):
    require(isinstance(status, dict) and status.get("ok") is True and
            all(type(status.get(k)) is int and status[k] == 0 for k in ("active", "rollback", "desync")),
            "Portal qualifier requires observed inactive ordinary offline transport")


def runtime_sources(candidate, original, raw_disc):
    config = tomllib.loads((candidate/"game.toml").read_text(encoding="utf-8-sig"))
    require(Path(config["game"]["exe"]).resolve(strict=True) == original.resolve(strict=True),
            "Runtime original EXE differs from the explicitly pinned source")
    disc = Path(config["game"]["disc"]).resolve(strict=True)
    if disc.suffix.lower() == ".cue":
        text = disc.read_text(encoding="utf-8-sig")
        files = re.findall(r'^\s*FILE\s+"([^"\r\n]+)"\s+BINARY\s*$',text,re.M|re.I)
        tracks = re.findall(r'^\s*TRACK\s+\d+\s+(\S+)\s*$',text,re.M|re.I)
        require(len(files) == len(tracks) == 1 and tracks[0].upper() == "MODE2/2352",
                "Only the original single-track MODE2/2352 source CUE is qualified")
        target = (disc.parent/files[0]).resolve(strict=True)
    else:
        require(disc.suffix.lower() == ".bin", "Unsupported runtime source disc container")
        target = disc
    require(target == raw_disc.resolve(strict=True), "Runtime disc differs from explicitly pinned original raw BIN")
    return dict(exe=str(original.resolve()),disc=str(disc),raw_bin=str(target),
                binding="Exact resolved source paths; bounded original archive/member SHA verification")


def alive(body):
    return len(body) == 0x158 and body[0] != 0 and body[4] == 1 and 0 < body[0x5C] < 0x80


def idle(body):
    return alive(body) and body[3] == 1 and body[5] == 2 and not body[0x67] and \
        bool(body[0x70] & 8) and not (body[0x7A] | body[0xD0] | body[0xD4]) and \
        body[8:16] == body[0x18:0x20]


def bodies(publication):
    return tuple(bytes.fromhex(publication[k]) for k in ("p1_body_hex", "p2_body_hex"))


def valid_publication(publication, *, settled=False, allow_joining=False):
    p = publication["observation"]
    allowed_lifecycle = ((0,0),(0,3)) if allow_joining else ((0,0),)
    require(p["ready"] == 1 and p["failed"] == p["mailbox"] == 0 and
            tuple(p["lifecycle"]) in allowed_lifecycle,
            "Private bank unavailable, tainted by input mailbox, or hero dying/joining")
    b1, b2 = bodies(publication)
    require(alive(b1) and alive(b2) and b1[2] == 0 and b2[2] == 1,
            "Expected two living current fixed-roster bodies")
    if settled:
        require(p["enrolled"] == 1 and p["native_mode"] == 10 and
                p["native_phase"] == p["pause_owner"] == p["scene_owner"] == p["scene_phase"] == 0 and
                idle(b1) and idle(b2), "Both heroes must settle through original idle/ground/entry gates")
    return b1, b2


def original_box(sources, owner, pointer):
    if setup.CHARACTER_BASE <= pointer < setup.CHARACTER_BASE + boxes.OVERLAY_SIZE:
        return setup.source_box(sources, owner, pointer)
    require(0x80010000 <= pointer <= 0x8008F000 and not pointer & 3,
            "Box outside explicitly supported original EXE/character source")
    exe = sources["exe"]
    at = exe.offset(pointer, 4)
    return exe.data[at:at+4]


def current_boxes(control, sources, publication, *, settled=False):
    """P2 bytes come only from X6BX; current null damage is a native miss gate."""
    b1, b2 = valid_publication(publication, settled=settled)
    result = dict(body_pointers=[], body=[], damage=[], source="explicit original owner plus current X6BX bytes")
    for owner, (body, expected) in enumerate(zip((b1, b2), (X_BODY, Z_BODY))):
        body_pointer = struct.unpack_from("<I", body, 0x68)[0]
        require(body_pointer == expected[0], "Current terrain box pointer differs from bounded source envelope")
        if owner == 0:
            actual_body = portal._read(control, body_pointer, 4)
        else:
            record = publication["boxes"]["body"]
            require(record["available"] and record["origin"] == "native_ram" and record["pointer"] == body_pointer,
                    "Private terrain box lacks coherent native-RAM provenance")
            actual_body = bytes.fromhex(record["hex"])
        require(actual_body == expected[1], "Actual terrain box bytes differ")
        result["body_pointers"].append(body_pointer)
        result["body"].append(dict(pointer=body_pointer,hex=actual_body.hex(),
            origin="resident_native_ram" if owner == 0 else "native_ram"))
        pointer = struct.unpack_from("<I", body, 0x54)[0]
        if not pointer:
            require(not settled, "An idle hero has no current damage box")
            result["damage"].append(None)
            continue
        reference = original_box(sources, owner, pointer)
        if owner == 0:
            actual = portal._read(control, pointer, 4)
            origin = "resident_native_ram"
        else:
            record = publication["boxes"]["damage"]
            expected_origin = "private_overlay" if pointer >= boxes.OVERLAY else "native_ram"
            require(record["available"] and record["pointer"] == pointer and record["origin"] == expected_origin,
                    "Private damage box lacks its actual owning-bank provenance")
            actual, origin = bytes.fromhex(record["hex"]), record["origin"]
        require(actual == reference, "Current box differs from its explicit original character owner")
        result["damage"].append(dict(pointer=pointer, hex=actual.hex(), origin=origin))
    return result


def observe_native(control):
    raw = portal._read(control, portal.BASE, portal.SIZE)
    native, capsule = portal.parse_native(raw), setup.parse_capsule(raw)
    nearby = []
    for pool, stride, count, category in ((portal.POOL, portal.STRIDE, portal.SLOTS, 0),
            (setup.CAPSULE_POOL, setup.CAPSULE_STRIDE, setup.CAPSULE_COUNT, 4)):
        for slot in range(count):
            address = pool + slot * stride
            actor = raw[address-portal.BASE:address-portal.BASE+stride]
            if not actor[0] & 1:
                continue
            x, y = struct.unpack_from("<h", actor, 0xA)[0], struct.unpack_from("<h", actor, 0xE)[0]
            if not (1328 <= x <= 1695 and 1449 <= y <= 1744):
                continue
            origin, parent = struct.unpack_from("<I", actor, 0x10)[0], struct.unpack_from("<I", actor, 0x7C)[0]
            known = (category == 0 and origin == portal.RECORD and actor[1:3] == bytes((28, 1))) or \
                (category == 4 and capsule is not None and
                 ((origin == setup.CAPSULE_RECORD and actor[1:3] == bytes((26, 4))) or
                  (actor[1:3] == bytes((26, 16)) and parent == capsule["address"])))
            item = dict(category=category, address=address, type=actor[1], subtype=actor[2],
                origin=origin, parent=parent, x=x, y=y, known_source_actor=known)
            if category == 4:
                # Read the one permitted source record from THIS native block,
                # never dereference an arbitrary actor-supplied origin pointer.
                at = reploid.RECORD-portal.BASE
                record_hex = raw[at:at+8].hex() if origin == reploid.RECORD else None
                item.update(reploid.enrich(actor,address=address,category=category,record_hex=record_hex))
            else:
                item["raw_hex"] = actor.hex()
            nearby.append(item)
    layout = raw[0x80097438-portal.BASE:0x80097438-portal.BASE+528]
    return dict(native=native, capsule=capsule, nearby_actors=nearby,
                live_layout_hex=layout.hex(), native_block_sha256=setup.sha(raw),
                reploid059_source=dict(dispatch_table_address=reploid.DISPATCH_TABLE,
                    dispatch_table_hex=raw[reploid.DISPATCH_TABLE-portal.BASE:
                                           reploid.DISPATCH_TABLE-portal.BASE+20].hex()))


def probe_reploid_exclusion(control,sources,row,publication,body_evidence,receipt):
    """One explicit fixed-pointer box probe, bracketed by native actor samples.

    Nothing is written. The after-publication is separately attributed and
    cannot turn the actor/native and private blocks into one coherent sample.
    """
    receipt.update(status="unverified_probe",before_native=row,before_publication=publication,
                   body_evidence=body_evidence,source_guards=sources["reploid059_guards"])
    actor = reploid.find_actor(row) # Refuse unknown identity/pointer BEFORE reads.
    _,state = reploid.actor_state(actor)
    receipt["actor_baseline"] = state
    actual = portal._read(control,reploid.BOX_POINTER,4)
    receipt["body_box_probe"] = dict(address=reploid.BOX_POINTER,bytes=4,hex=actual.hex(),
        provenance="separate_owned_read_ram_fixed_source_pointer")
    table = struct.unpack("<I",portal._read(control,reploid.DISPATCH_POINTER,4))[0]
    receipt["dispatch_probe"] = dict(address=reploid.DISPATCH_POINTER,bytes=4,value=table,
        provenance="separate_owned_read_ram_fixed_scratch_slot")
    receipt["before_check"] = reploid.validate_frame(row,publication,body_evidence,receipt)
    after = observe_native(control)
    receipt["after_native"] = after
    after_pub = boxes.observe_owned(control)
    receipt["after_publication"] = after_pub
    receipt["after_check"] = reploid.validate_frame(after,after_pub,body_evidence,receipt)
    receipt.update(status="conditional_source_bound_contact_exclusion",
        native_runtime_qualification="read_only_scope_checks_observed_not_mechanic_qualification",
        attribution="Box and scratch RPCs bracketed by native blocks; private publications are separate RPCs",
        continuous_frame_coverage=False,native_reploid_mechanics="unverified")
    return receipt


def source_preflight(control, sources, row, receipt, *, publication=None, body_evidence=None):
    n = row["native"]
    require((n["mode"], n["phase"], n["stage"], n["section"], n["checkpoint"]) == (10, 0, 4, 0, 2) and
            n["source_closure_present"] and not n["transition"] and not n["fade"] and not n["freeze"],
            "CP2 original source/record/loader namespace not ready")
    terrain = sources["terrain"]
    require(bytes.fromhex(row["live_layout_hex"]) == terrain.layout, "Live528-byte map differs from original")
    if any(not a["known_source_actor"] for a in row["nearby_actors"]):
        require(publication is not None and body_evidence is not None,
                "Unqualified nearby native actor: retain partial evidence, do not place/move")
        probe_reploid_exclusion(control,sources,row,publication,body_evidence,
                               receipt.setdefault("reploid059_exclusion",{}))
    pointers = struct.unpack("<III", portal._read(control, 0x1F800004, 12))
    receipt["scratch_pointers"] = list(pointers)
    require(pointers == SCRATCH, "Live collision scratch pointers differ from this bounded source setup")
    receipt["collision_assets"] = []
    for pointer, expected in zip(pointers[1:], (terrain.metatiles, terrain.descriptors)):
        actual = b"".join(portal._read(control, pointer+at, min(32768, len(expected)-at))
                          for at in range(0, len(expected), 32768))
        artifact = dict(address=pointer, bytes=len(actual), sha256=setup.sha(actual),
                        matches_source=actual == expected)
        receipt["collision_assets"].append(artifact)
        require(artifact["matches_source"], "Full native metatile/descriptor bytes differ from original DAT98")
    receipt["layout_sha256"] = setup.sha(terrain.layout)


def command(control, client, opcode, payload, receipt, *, before_commit=None):
    require(type(opcode) is int and opcode in (4,8) and isinstance(payload,dict), "Only checkpoint and two-seat position setup are permitted")
    expected = {0x52,*range(0x54,0x5C)} if opcode == 4 else set(range(0x51,0x58))
    require(set(payload) == expected and all(type(k) is int and type(v) is int and 0 <= v <= 255 for k,v in payload.items()),
            "Diagnostic payload escapes the exact approved command fields")
    require((opcode == 4 and payload[0x52] == 2) or
            (opcode == 8 and tuple(payload[k] for k in (0x51,0x52,0x53)) == (4,0,2)),
            "Only atomic both-seat positions or Recycle CP2 are permitted")
    verify_offline(control("netplay_status"))
    require(client.read(debug.DIAGNOSTIC_ADDRESS+0x50, 1) == b"\0", "Another fixture operation is pending")
    receipt.update(opcode=opcode, payload={hex(k):v for k,v in payload.items()},
                   prerequisite_bypass=True, ordinary_input_evidence_tainted=True)
    for offset, value in payload.items():
        control("write_ram", addr=hex(debug.DIAGNOSTIC_ADDRESS+offset), val=hex(value))
    if before_commit is not None:
        before_commit()
    control("write_ram", addr=hex(debug.DIAGNOSTIC_ADDRESS+0x50), val=hex(opcode))


def request_checkpoint(control, client, target, receipt, timeout):
    require(tuple(target[k] for k in ("stage","section","checkpoint")) == (4,0,2), "Only source CP2 setup is supported")
    before = checkpoint.fixture_status(client)
    require(before["state"] not in (1, 2), "Checkpoint operation already pending")
    nonce = (time.monotonic_ns() & 0xFFFFFFFF) or 1
    receipt.update(before=before, target=target, nonce=nonce, observations=[])
    payload = bytes((4, 0, 2)) + struct.pack("<I", nonce)
    command(control, client, 8, dict(enumerate(payload, 0x51)), receipt)
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        row = checkpoint.fixture_status(client)
        receipt["observations"].append(row)
        if row["generation"] != before["generation"]:
            require(row["generation"] == (before["generation"]+1)&0xFFFFFFFF and row["nonce"] == nonce,
                    "Checkpoint receipt belongs to another operation")
            require(row["state"] not in (4, 5), "Native checkpoint fixture rejected/failed")
            if row["state"] == 3:
                require((row["stage"],row["section"],row["checkpoint"]) == (4,0,2) and
                        row["record"] == target["record"] and row["initializer_entries"] == row["tainted"] == 1,
                        "Initializer receipt differs from exactly one source CP2 initialization")
                receipt.update(status="initializer_completed_readiness_pending", completion=row,
                               ordinary_authored_checkpoint_readiness=False)
                return
        time.sleep(.015)
    raise debug.DebugError("CP2 initializer receipt timed out")


def place_both(control, client, plan, receipt, *, before_commit=None):
    point = plan.get("conditional_both_seat_probe")
    require(point is not None and point["seat"] == 2 and point["command"] == 4,
            "No common source-derived two-seat setup")
    require(type(point["x"]) is int and 1467 <= point["x"] <= 1557 and point["y"] == 1593 and
            any(lo <= point["x"] <= hi for lo,hi in plan["source_miss_intervals"]),
            "Position escapes the finite source floor/miss envelope")
    payload = {0x52:2}
    payload.update(dict(enumerate(struct.pack("<ii", point["x"]<<16, point["y"]<<16), 0x54)))
    command(control, client, 4, payload, receipt,before_commit=before_commit)
    receipt["source_solver"] = plan


def outside(row, p1_damage, expected_pointer):
    """P1 and actors share this ONE native block. Box source remains explicit."""
    n, c = row["native"], row["capsule"]
    p = n["portal"]
    require(c is not None and c["trigger_action_ready"] and c["x"] == 1424 and
            p is not None and (p["phase"],p["action"]) == (1,1), "Original capsule/portal not initialized idle")
    raw = bytes.fromhex(p["raw_hex"])
    require(struct.unpack_from("<I",raw,0x50)[0] == 0x800F38BC and
            struct.unpack_from("<I",raw,0x68)[0] == 0x800F38B8 and
            (p["x_raw"],p["y_raw"]) == (1552<<16,1584<<16),
            "Portal geometry pointers differ")
    player = n["resident_player"]
    require(player["damage_box"] == expected_pointer and expected_pointer != 0,
            "Native P1 current damage pointer changed since its owned source-box observation")
    px, py = player["x_raw"]>>16, player["y_raw"]>>16
    actor = dict(x=p["x_raw"]>>16,y=p["y_raw"]>>16,facing=raw[0x15],
                 layer=struct.unpack_from("<b",raw,0x14)[0],attack_pointer=0x800F38BC)
    who = dict(x=px,y=py,facing=player["facing"],iframe=player["iframe"],damage_pointer=player["damage_box"])
    portal_hit = setup.contact(actor, who, struct.pack("<bbBB",-18,-28,28,40), p1_damage,
                               (n["camera"]["x"],n["camera"]["y"]))
    capsule_hit = setup.capsule_region(c["x"], c["y"], px, py)
    require(not capsule_hit and not portal_hit["hit"], "Native resident P1 overlaps capsule or portal trigger")
    return dict(p1_capsule_miss=True,p1_portal_miss=True,portal_geometry=portal_hit,
                attribution="P1/actors one native RPC, immutable verified box source; no P2 contact inference")


def viewport(native,publication,gpu):
    require(type(gpu.get("disabled")) is int and gpu["disabled"] == 0 and
            gpu.get("width") == 320 and gpu.get("height") == 240,
            "Expected active original320x240 composed view")
    camera = native["native"]["camera"]
    require(all((camera["x"]<<16) <= struct.unpack_from("<i",b,8)[0] < ((camera["x"]+320)<<16) and
                (camera["y"]<<16) <= struct.unpack_from("<i",b,12)[0] < ((camera["y"]+240)<<16)
                for b in bodies(publication)), "Both settled player centers must lie inside the actual native viewport")
    require(all(portal._body(body)["resource_pointers_valid"] for body in bodies(publication)),
            "Both settled render resource pointers must be available")
    return dict(player_centers_in_view=True,render_pointers_available=True,artwork_review="pending",
                attribution="Separate settled native-camera and private-player RPCs; no composed-art approval")


class Trial:
    def __init__(self, control, adapter, output, report, sources, plan, timeout, entry_timeout):
        self.control,self.adapter,self.output,self.report = control,adapter,output,report
        self.sources,self.plan,self.timeout,self.entry_timeout = sources,plan,timeout,entry_timeout
        self.reploid_scope = None
        report.update(native_samples=[],box_samples=[],input_windows=[],captures=[],
                      prerequisite_bypass=True,ordinary_input_evidence_tainted=True,
                      artwork_review="pending",ledger_status="unverified",
                      p1_outside_p2_actual_contact="unverified_separate_rpc_attribution")

    def sample(self, label):
        native = observe_native(self.control)
        self.report["native_samples"].append(dict(label=label, **native))
        publication = boxes.observe_owned(self.control)
        self.report["box_samples"].append(dict(label=label, **publication))
        return native, publication

    def capture(self, name):
        item = debug.capture_present(self.adapter.client,self.output/name,request=self.control)
        self.report["captures"].append(item)

    def release(self, seat):
        self.control("clear_input",port=seat+1)

    def wait_entry_enrollment(self):
        """Original X landing enrolls P2 at X+24; never relocate before that."""
        deadline = time.monotonic()+self.entry_timeout
        rows = self.report.setdefault("entry_enrollment_wait",[])
        native_rows = self.report.setdefault("entry_native_wait",[])
        while time.monotonic() < deadline:
            native = observe_native(self.control);native_rows.append(native)
            pub = boxes.observe_owned(self.control);rows.append(pub)
            b1,b2 = valid_publication(pub,allow_joining=True)
            p = pub["observation"]
            require(p["native_mode"] == 10 and not (p["scene_owner"] or p["pause_owner"] or p["native_phase"]) and
                    all(struct.unpack_from("<h",b,0xE)[0] < 2048 for b in (b1,b2)),
                    "Original CP2 enrollment left its living scene-free entry")
            n = native["native"]
            resident = bytes.fromhex(n["resident_player"]["raw_hex"])
            native_ready = (n["mode"],n["phase"],n["stage"],n["section"],n["checkpoint"]) == (10,0,4,0,2) and \
                n["source_closure_present"] and not (n["fade"] or n["freeze"] or n["transition"] or n["shared_entry_lock"]) and \
                idle(resident) and struct.unpack_from("<i",resident,8)[0] == 480<<16
            # An initializer receipt does not refresh the co-op publication.
            # Compare separately attributed native/private P1 observations only
            # after original CP2 landing; do not infer cross-RPC atomicity.
            if native_ready and p["enrolled"] == 1 and tuple(p["lifecycle"]) == (0,0) and idle(b1) and \
                    b2[3] == 1 and struct.unpack_from("<I",b2,0x68)[0] == Z_BODY[0] and \
                    resident[8:16] == b1[8:16] and resident[0x5C] == b1[0x5C]:
                return pub
            time.sleep(.015)
        raise debug.DebugError("Original CP2 resident landing/enrollment did not complete")

    def wait_idle(self, *, source=False, point=None):
        deadline = time.monotonic()+self.entry_timeout
        previous = None
        while time.monotonic() < deadline:
            native,pub = self.sample("source landing" if source else "destination landing")
            # Original major9 arrival enrolls Zero through JOINING3. It must
            # complete natively before settled=True can qualify the landing.
            b1,b2 = valid_publication(pub,allow_joining=not source)
            n = native["native"]
            require(not n["transition"] and not n["fade"] and not n["freeze"] and
                    not pub["observation"]["scene_owner"], "Unexpected scene during neutral landing")
            require(all((struct.unpack_from("<h",b,0xE)[0] < 2048) for b in (b1,b2)),
                    "Neutral body left bounded source map height")
            try:
                valid_publication(pub,settled=True)
            except debug.DebugError:
                time.sleep(.015)
                continue
            if n["shared_entry_lock"] or (n["mode"],n["phase"]) != (10,0):
                time.sleep(.015)
                continue
            if (n["resident_player"]["x_raw"],n["resident_player"]["y_raw"],n["resident_player"]["hp"]) != \
                    (*struct.unpack_from("<ii",b1,8),b1[0x5C]):
                time.sleep(.015)
                continue
            if source:
                require((n["stage"],n["section"],n["checkpoint"]) == (4,0,2) and n["source_closure_present"],
                        "Source namespace/code changed during landing")
                require(point is not None and all(struct.unpack_from("<i",b,8)[0] == point["x"]<<16 for b in (b1,b2)),
                        "Original landing moved a hero away from disclosed solver X")
                if n["shared_entry_lock"] or (n["camera"]["x"],n["camera"]["y"]) != (1264,1424) or \
                        native["capsule"] is None or n["portal"] is None or \
                        not native["capsule"]["trigger_action_ready"] or (n["portal"]["phase"],n["portal"]["action"]) != (1,1):
                    time.sleep(.015)
                    continue
            else:
                require((n["stage"],n["section"],n["checkpoint"]) == (20,1,0), "Destination namespace differs")
            signature = (b1[8:16],b2[8:16])
            if previous == signature:
                return native,pub
            previous = signature
            time.sleep(.015)
        raise debug.DebugError("Native landing/entry lock/enrollment/camera/actors did not settle")

    def hold(self, seat, max_ticks, label, *, activation=False):
        require(seat in (0,1) and 1 <= max_ticks <= 30, "Bounded original Right only")
        receipt = dict(label=label,seat=seat,bits=RIGHT,frames=0,requested_native_ticks=max_ticks,
                       accepted="unverified",samples=[])
        self.report["input_windows"].append(receipt)
        start = boxes.observe_owned(self.control)
        valid_publication(start,settled=True)
        if activation:
            actual = current_boxes(self.control,self.sources,start,settled=True)
            native = observe_native(self.control)
            self.report["native_samples"].append(dict(label="immediate pre-input P1 miss",**native))
            if any(not a["known_source_actor"] for a in native["nearby_actors"]):
                self.reploid_scope = probe_reploid_exclusion(self.control,self.sources,native,start,
                    actual["body"],receipt.setdefault("reploid059_pre_input",{}))
            elif self.reploid_scope is not None:
                raise debug.DebugError("Previously bound Reploid059 vanished before original input")
            receipt["p1_pre_input_misses"] = outside(native,bytes.fromhex(actual["damage"][0]["hex"]),actual["damage"][0]["pointer"])
        receipt["before"] = start
        error = None
        try:
            self.control("press",port=seat+1,buttons=0xFFFF^RIGHT,frames=0)
            receipt["pad_status"] = self.control("pad_status")
            deadline = time.monotonic()+self.timeout
            while time.monotonic() < deadline:
                row,pub = self.sample(label)
                receipt["samples"].append(dict(native_index=len(self.report["native_samples"])-1,
                                                box_index=len(self.report["box_samples"])-1))
                p = pub["observation"];n = row["native"];actor = n["portal"]
                require(not p["failed"] and not p["mailbox"] and tuple(p["lifecycle"]) == (0,0) and
                        all(alive(b) for b in bodies(pub)), "Hero died/failed during original input")
                require(p["scene_owner"] != 1, "P1 unexpectedly owns a native scene")
                delta = (p["native_timer"]-start["observation"]["native_timer"])&0xFFFFFFFF
                tick_delta = (p["tick"]-start["observation"]["tick"])&0xFFFFFFFF
                require(delta < 0x80000000 and tick_delta < 180, "Input progress regressed or exceeded publication bound")
                receipt.update(observed_native_ticks=delta,observed_publications=tick_delta)
                if activation and ((actor and actor["action"] == 2) or p["scene_owner"] == 2):
                    receipt.update(stop="native_portal_or_owner2_observed",after=pub,accepted="native_effect_observed")
                    return
                if activation:
                    if self.reploid_scope is not None:
                        receipt.setdefault("reploid059_source_window_checks",[]).append(
                            reploid.validate_frame(row,pub,self.reploid_scope["body_evidence"],self.reploid_scope))
                    else:
                        require(not any(not a["known_source_actor"] for a in row["nearby_actors"]),
                                "New unqualified nearby actor during original portal approach")
                require(p["scene_owner"] == 0 and p["native_phase"] == p["pause_owner"] == 0,
                        "Unexpected native menu/scene during independent movement")
                if delta >= max_ticks:
                    receipt.update(stop="bounded_native_world_window",after=pub,accepted="native_progress_observed")
                    require(not activation, "P2 Right reached its bound without portal admission")
                    return
                time.sleep(.015)
            raise debug.DebugError("Original held-input native progress timed out")
        except BaseException as caught:
            error = caught
            raise
        finally:
            try:
                self.release(seat)
            except Exception as cleanup:
                self.report.setdefault("input_cleanup_errors",[]).append(dict(error=str(cleanup),original_error=str(error)))
                if error is None:
                    raise

    def run(self):
        self.adapter.settle_idle()
        verify_offline(self.control("netplay_status"))
        intro = boxes.observe_owned(self.control)
        self.report["intro_idle_publication"] = intro
        initial = current_boxes(self.control,self.sources,intro,settled=True)
        conditional = setup.derive_setup(self.sources["terrain"],*(bytes.fromhex(b["hex"]) for b in initial["damage"]))
        require(conditional["conditional_both_seat_probe"] is not None, "Actual intro idle boxes provide no common source setup")
        self.report["intro_conditional_plan"] = conditional
        target = self.plan["alternate_approach_checkpoint"]
        request_checkpoint(self.control,self.adapter.client,target,self.report.setdefault("checkpoint",{}),self.entry_timeout)
        self.wait_entry_enrollment()
        before,pub = self.sample("CP2 initializer complete before placement")
        source_preflight(self.control,self.sources,before,self.report.setdefault("before_placement_preflight",{}))
        pub = boxes.observe_owned(self.control)
        self.report["after_assets_entry_publication"] = pub
        current_boxes(self.control,self.sources,pub)  # Entry damage may legitimately be null.
        require(not pub["observation"]["scene_owner"], "Cannot relocate an existing native scene")
        def pre_commit():
            latest = boxes.observe_owned(self.control)
            self.report["position_precommit_publication"] = latest
            b1,b2 = valid_publication(latest)
            p = latest["observation"]
            require(p["enrolled"] == 1 and idle(b1) and p["native_mode"] == 10 and
                    p["native_phase"] == p["scene_owner"] == p["pause_owner"] == 0 and
                    all(1424 <= struct.unpack_from("<h",b,0xE)[0] < 1664 for b in (b1,b2)),
                    "Entry hero left the current visible living setup window; no position commit")
        place_both(self.control,self.adapter.client,conditional,self.report.setdefault("position_bypass",{}),before_commit=pre_commit)
        ready,pub = self.wait_idle(source=True,point=conditional["conditional_both_seat_probe"])
        actual = current_boxes(self.control,self.sources,pub,settled=True)
        feet = [setup.terrain_source.foot_probes(b,shape,self.sources["terrain"])
                for b,(_,shape) in zip(bodies(pub),(X_BODY,Z_BODY))]
        self.report["source_grounded_feet"] = feet
        require(all(struct.unpack_from("<h",b,0xE)[0] == y for b,y in zip(bodies(pub),(1595,1594))) and
                all(probe["code"] == 0x38 for foot in feet for probe in foot["probes"]),
                "Original grounded positions/three-foot source support differ from solver floor")
        c = ready["capsule"]
        recomputed = setup.derive_setup(self.sources["terrain"],*(bytes.fromhex(b["hex"]) for b in actual["damage"]),
                                      capsule=(c["x"],c["y"]))
        self.report["landed_actual_box_plan"] = recomputed
        x = conditional["conditional_both_seat_probe"]["x"]
        require(any(lo <= x <= hi for lo,hi in recomputed["source_miss_intervals"]),
                "Current landed damage boxes invalidate the disclosed source position")
        landed_preflight = self.report.setdefault("after_landing_preflight",{})
        source_preflight(self.control,self.sources,ready,landed_preflight,
                         publication=pub,body_evidence=actual["body"])
        self.reploid_scope = landed_preflight.get("reploid059_exclusion")
        self.report["p1_source_trigger_misses"] = outside(ready,bytes.fromhex(actual["damage"][0]["hex"]),actual["damage"][0]["pointer"])
        gpu = self.control("gpu_state");self.report["source_gpu_state"] = gpu
        self.report["source_visibility"] = viewport(ready,pub,gpu)
        n = ready["native"]
        original_checks = checkpoint.reduce_entry_readiness(target,
            self.report["entry_enrollment_wait"][0]["observation"]["tick"],pub["observation"],
            bytes.fromhex(n["play_hex"])[:0x1E],
            bytes.fromhex(n["resident_player"]["raw_hex"])+bytes.fromhex(n["camera_hex"]),gpu)
        self.report["original_checkpoint_readiness_checks"] = original_checks
        require(original_checks["p1_at_authored_x"] is False and
                all(value for key,value in original_checks.items() if key != "p1_at_authored_x"),
                "Original checkpoint readiness has an additional unresolved gap besides disclosed X placement")
        self.capture("portal-source-ready.png")
        self.hold(1,24,"P2 original Right portal approach",activation=True)
        deadline = time.monotonic()+self.entry_timeout
        while time.monotonic() < deadline:
            n,p = self.sample("original portal fade/load")
            require(not p["observation"]["failed"] and not p["observation"]["mailbox"], "Portal context failed")
            if p["observation"]["scene_owner"] == 1:
                raise debug.DebugError("Portal handoff attributed to P1")
            native_rows = [r["native"] for r in self.report["native_samples"]]
            transition = portal.reduce_native_transition(native_rows,self.plan)
            self.report["native_transition"] = transition
            if transition["checks"]["destination_native_ready_seen"]:
                break
            time.sleep(.015)
        else:
            raise debug.DebugError("Original action2/41h/fade/load/destination sequence incomplete before deadline")
        require(any(r["observation"]["scene_owner"] == 2 for r in self.report["box_samples"]),
                "No private owner2 publication retained during native portal handoff")
        destination,pub = self.wait_idle()
        current_boxes(self.control,self.sources,pub,settled=True)
        gpu = self.control("gpu_state");self.report["destination_gpu_state"] = gpu
        self.report["destination_visibility"] = viewport(destination,pub,gpu)
        self.report["destination_both_living_idle"] = pub
        self.capture("portal-destination-ready.png")
        for seat in (1,0):
            self.hold(seat,3,f"Destination independent seat{seat} Right")
            receipt = self.report["input_windows"][-1]
            before,after = bodies(receipt["before"]),bodies(receipt["after"])
            require(struct.unpack_from("<i",after[seat],8)[0] > struct.unpack_from("<i",before[seat],8)[0] and
                    before[1-seat][8:16] == after[1-seat][8:16], "Destination movement was absent or coupled")
            self.wait_idle()
        self.capture("portal-destination-independent-controls.png")
        self.report.update(status=SUCCESS,automated_observations_complete=True,
                           authored_checkpoint_x_matches=original_checks["p1_at_authored_x"])
        return self.report


def make_parser():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--build",type=Path);group.add_argument("--candidate",type=Path)
    for name in ("source","disc","output"):
        p.add_argument("--"+name,type=Path)
    p.add_argument("--original-exe",type=Path,required=True)
    p.add_argument("--original-disc",type=Path,required=True)
    p.add_argument("--expected-exe-sha256",required=True)
    p.add_argument("--port",type=int,default=24908)
    p.add_argument("--timeout",type=float,default=240)
    p.add_argument("--entry-timeout",type=float,default=90)
    p.add_argument("--progress-timeout",type=float,default=12)
    p.set_defaults(window_frames=12)
    return p


def validate_options(parser,args):
    offline.validate_options(parser,args)
    if not math.isfinite(args.entry_timeout) or not 0 < args.entry_timeout <= 180:
        parser.error("Entry/transition timeout must be in (0,180]")
    if args.original_disc.suffix.lower() != ".bin":
        parser.error("Original source requires the read-only raw BIN")


def run(args):
    sources = setup.load_sources(args.original_exe.resolve(strict=True),args.original_disc.resolve(strict=True))
    sources["reploid059_guards"] = reploid.source_guards(sources)
    plan = portal.source_plan(args.original_exe,args.original_disc)
    candidate = preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"))
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
    prepared = offline.pristine_candidate(candidate,args.expected_exe_sha256)
    binding = runtime_sources(candidate,args.original_exe,args.original_disc)
    os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"),
                      PYTHONPYCACHEPREFIX=str(candidate/"temp/pycache"))
    sys.pycache_prefix = str(candidate/"temp/pycache")
    modules = (setup,portal,boxes,checkpoint,reploid,setup.terrain_source,debug,offline,baseline,preparation)
    metadata = dict(kind="owned_offline_recycle_portal_qualifier",candidate_exe_sha256=prepared["exe_sha256"],
        expected_exe_sha256=args.expected_exe_sha256,original_exe_sha256=setup.content.EXE_SHA256,
        original_archive_sha256=setup.content.BIN_SHA256,inventory_sha256=checkpoint.INVENTORY_SHA256,
        runner_sha256=preparation.sha256(Path(__file__)),source_plan=plan,
        runtime_original_source_binding=binding,
        reploid059_source_guards=sources["reploid059_guards"],
        tool_sha256={Path(m.__file__).name:preparation.sha256(Path(m.__file__)) for m in modules},
        prerequisite_bypass=True,ordinary_input_evidence_tainted=True,artwork_review="pending",ledger_status="unverified",
        limits=["Only local offline CP2 checkpoint+two-seat position prerequisites; no original route/campaign/netplay pass",
            "Native actor and X6BX publications are separate RPCs: no exact-tick private contact attribution",
            "Actual composed capture completion requires subsequent visual review; ACK/source/memory are not artwork approval",
            "No HP/action/ground/lock/clock/success/destination writes or debugger guest calls; source cards untouched",
            "Staged source observations are not compilation provenance; retained partial failures are never overwritten"])
    (candidate/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    (candidate/"runner-metadata.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    def exercise(control,client,output,report):
        report["checks"] = dict(offline_portal_automated_observations_complete=False)
        case = report.setdefault("recycle_portal",{})
        adapter = offline.OfflineMenuAdapter(control,report,timeout=args.progress_timeout)
        try:
            Trial(control,adapter,output,case,sources,plan,args.progress_timeout,args.entry_timeout).run()
            report["checks"]["offline_portal_automated_observations_complete"] = True
        except Exception as error:
            case.update(status="unverified_partial_trial",error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
            raise debug.DebugError(f"Offline portal trial stopped: {error}") from error
        finally:
            for seat in (1,2):
                try:
                    control("clear_input",port=seat)
                except Exception as error:
                    case.setdefault("input_cleanup_errors",[]).append(dict(seat=seat,error=str(error)))
                    report["checks"]["offline_portal_automated_observations_complete"] = False
    result = baseline.run(candidate,args.port,args.timeout,False,exercise=exercise)
    baseline_path = candidate/"baseline/qualification.json"
    result.update(kind=metadata["kind"],runner=metadata,ledger_status="unverified",artwork_review="pending",
        prerequisite_bypass=True,ordinary_input_evidence_tainted=True,
        original_baseline=dict(path=str(baseline_path),sha256=preparation.sha256(baseline_path),status=result["status"]))
    result["automated_observations_complete"] = result["status"] == "passed" and \
        result.get("exercise",{}).get("checks",{}).get("offline_portal_automated_observations_complete") is True
    if result["automated_observations_complete"]:
        result["status"] = SUCCESS
    (candidate/"qualification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None):
    parser = make_parser();args = parser.parse_args(argv);validate_options(parser,args)
    try:
        result = run(args)
    except (OSError,ValueError,debug.DebugError) as error:
        parser.exit(1,f"Offline portal setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"],ledger_status="unverified",artwork_review="pending",
                          report=str((args.candidate or args.output)/"qualification.json"))))
    return 0 if result["automated_observations_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
