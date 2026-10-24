"""Owned, muted, same-build native warm/cold X6 snapshot qualification.

Uses original pad input and asynchronous save/load completion receipts. Never
writes guest RAM, fixture mailboxes, source cards, or a comparison ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import time
import zlib

import qualify_mmx6_coop_baseline as baseline
from prepare_mmx6_coop_playtest import local_output, prepare, sha256
from coop_debug import (BODY_BYTES, DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES,
                        DebugError, capture_present, parse_diagnostic)


# Read-only, current-build wire inspection, not an alternate state loader.
# runtime/include/boot_state.h + runtime/src/mod_snapshot.c; internal game schema4 is
# src/mods/mmx6_coop_snapshot.inc. Reject future layouts instead of guessing.
MAX_STATE_BYTES = 64 * 1024 * 1024
HOST_WIRE_SCHEMA = 4
HOST_RESOURCE_BYTES = 88
HOST_PLAYER_BYTES = 0x158 + 0x1400 + 0x120 + 0xF0
HOST_AUDIO_PRIORITIES_OFFSET = HOST_PLAYER_BYTES + 25 + 2*0x158 + 0x205
HOST_GIGA_BACKUP_BYTES = 64
HOST_SEMANTIC_BYTES = HOST_AUDIO_PRIORITIES_OFFSET + 24 + 128*5 + 80*2 + 96*14 + HOST_GIGA_BACKUP_BYTES
HOST_CORE_END = HOST_RESOURCE_BYTES + HOST_SEMANTIC_BYTES
HOST_CACHE_OFFSET = HOST_CORE_END + 10  # publication count + presentation tail
PRIVATE_SUCCESS = "automated_private_effect_state_checks_passed_artwork_pending"
SPU_VOICE_WIRE_BYTES = 114
SPU_BASE_BYTES = 256*2 + 24*SPU_VOICE_WIRE_BYTES + 64
SPU_PRIVATE_STRIDE = 16+1+8+SPU_VOICE_WIRE_BYTES
SPU_CURRENT_BYTES = SPU_BASE_BYTES + 24*SPU_PRIVATE_STRIDE + 4
MMX6_AUDIO_OWNER = 0x4D4D583650320001
MMX6_AUDIO_MASK = 0x00F00B09


def forward(old, new):
    return type(old) is int and type(new) is int and 0 < ((new-old) & 0xFFFFFFFF) < 0x80000000


def parse_state_image(data):
    """Bounded current-build PST/MSNP/X6 wire reader; never applies state."""
    def require(ok, message):
        if not ok:
            raise DebugError("Snapshot inspection: " + message)

    require(36 <= len(data) <= MAX_STATE_BYTES, "invalid file size")
    header = struct.unpack_from("<9I", data)
    require(header[0] == 0x50535842 and header[1] == 10 and 1 <= header[7] <= 256,
            "unsupported PST header/version/count")
    sections, at = {}, 36
    for _ in range(header[7]):
        require(at+16 <= len(data), "truncated section header")
        tag, flags, size = struct.unpack_from("<IIQ", data, at);at += 16
        require(tag not in sections and flags in (0, 1) and size <= MAX_STATE_BYTES and at+size <= len(data),
                "duplicate/invalid/truncated section")
        payload = data[at:at+size];at += size
        # Only host/RAM/private-SPU are inspected; the runtime already validated all
        # subsystem payloads before reporting completed save/load operations.
        if tag in (2, 9, 0x16) and flags:
            require(len(payload) >= 4, "truncated compressed length")
            raw_size = struct.unpack_from("<I", payload)[0]
            require(0 < raw_size <= MAX_STATE_BYTES, "unbounded compressed section")
            inflater = zlib.decompressobj()
            try:
                inflated = inflater.decompress(payload[4:], raw_size+1)
            except zlib.error as error:
                raise DebugError("Snapshot inspection: invalid compressed section") from error
            require(len(inflated) == raw_size and inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail,
                    "compressed section length/trailer mismatch")
            payload = inflated
        sections[tag] = payload
    require(at == len(data) and {2,9,0x16}<=sections.keys(), "missing required inspection section/trailing data")
    ram, host = sections[2], sections[0x16]
    require(len(ram) in (2*1024*1024, 8*1024*1024), "invalid native RAM geometry")
    require(16 <= len(host) <= 16*1024*1024, "invalid host section size")
    magic, version, count, reserved = struct.unpack_from("<4I", host)
    require((magic, version, reserved) == (0x504E534D, 1, 0) and 1 <= count <= 64, "unsupported MSNP header")
    records, at, previous = {}, 16, ""
    for _ in range(count):
        require(at+12 <= len(host), "truncated provider header")
        schema, id_size, size = struct.unpack_from("<3I", host, at);at += 12
        require(1 <= id_size <= 96 and at+id_size+size <= len(host), "truncated provider record")
        try:
            identity = host[at:at+id_size].decode("ascii")
        except UnicodeDecodeError as error:
            raise DebugError("Snapshot inspection: non-ASCII provider") from error
        at += id_size
        require(re.fullmatch(r"[a-z0-9][a-z0-9._-]*[a-z0-9]|[a-z0-9]", identity) and identity > previous,
                "invalid/noncanonical provider IDs")
        records[identity] = (schema, host[at:at+size]);at += size;previous = identity
    require(at == len(host), "trailing provider data")
    require("mmx6.local-coop" in records and "mmx6.local-coop.prototype" not in records,
            "expected one offline co-op provider")
    schema, payload = records["mmx6.local-coop"]
    require(schema == 1 and len(payload) >= HOST_CACHE_OFFSET+8 and
            struct.unpack_from("<II", payload) == (0x53503658, HOST_WIRE_SCHEMA), "unsupported X6 provider schema")
    cache_at = HOST_CACHE_OFFSET
    count = struct.unpack_from("<I", payload, cache_at)[0];cache_at += 4
    require(count <= 4096, "unbounded retained sprite count")
    for index in range(count):
        require(cache_at+44 <= len(payload), "truncated sprite record")
        _, identity, tile = struct.unpack_from("<IHH", payload, cache_at)
        size = struct.unpack_from("<I", payload, cache_at+40)[0];cache_at += 44
        pixels = 65536 if tile == 0xFFFF else 256
        require(identity == 0x6000+index and 1 <= size <= 1+pixels*2 and cache_at+size <= len(payload),
                "invalid sprite ID/pixel size")
        encoded = payload[cache_at:cache_at+size];cache_at += size
        require(encoded[0] in (0, 1), "unknown pixel encoding")
        if not encoded[0]:
            require(size == 1+pixels*2, "truncated raw bank pixels")
        else:
            require((size-1) % 4 == 0, "truncated bank run")
            lengths = [struct.unpack_from("<H", encoded, i)[0] for i in range(1, size, 4)]
            require(all(lengths) and sum(lengths) == pixels, "invalid bank runs")
    require(cache_at+4 <= len(payload), "missing UI cache count")
    ui_count = struct.unpack_from("<I", payload, cache_at)[0];cache_at += 4
    require(ui_count <= 4096 and cache_at+ui_count*40 == len(payload), "truncated/trailing UI banks")
    for index in range(ui_count):
        page, clut, _, identity = struct.unpack_from("<4H", payload, cache_at+40*index)
        require(identity == 0x7000+index and clut <= 32767 and not page & 0x180, "invalid UI bank identity")
    core = payload[HOST_RESOURCE_BYTES:HOST_CORE_END]
    spu=sections[9]
    require(len(spu)==SPU_CURRENT_BYTES,'unsupported current private-SPU owner wire length')
    owners=[];modes=[];registers=[];bindings=[];voices=[]
    for slot in range(24):
        at=SPU_BASE_BYTES+slot*SPU_PRIVATE_STRIDE
        mode=spu[at+16];owner=struct.unpack_from('<Q',spu,at+17)[0]
        voice=spu[at+25:at+25+SPU_VOICE_WIRE_BYTES]
        active,addr,repeat,bank,pending=struct.unpack_from('<i4I',voice)
        require(mode<=3 and active in (0,1) and bank<32 and pending<32,'invalid current private-SPU voice scalar')
        owners.append(owner);modes.append(mode);registers.append(spu[at:at+16].hex());bindings.append([bank,pending])
        voices.append(dict(slot=slot,owner_tag=f'0x{owner:016x}',active=active,addr=addr,repeat=repeat,
            sample_bank=bank,pending_bank=pending,env_level=struct.unpack_from('<H',voice,95)[0],
            adsr_phase=voice[101],voice_wire_hex=voice.hex()))
    input_at = HOST_PLAYER_BYTES+10+1+4
    start_at = HOST_PLAYER_BYTES+25+2*0x158+1
    return dict(build_key=[*header[:7], header[8]], provider_ids=list(records),
        provider_schema=schema, provider_payload_sha256=hashlib.sha256(payload).hexdigest(),
        resource_binding_hex=payload[:HOST_RESOURCE_BYTES].hex(), semantic_core_hex=core.hex(),
        internal_wire_schema=HOST_WIRE_SCHEMA,
        zero_giga_backup_hex=core[-HOST_GIGA_BACKUP_BYTES:].hex(),
        audio_priorities_hex=core[HOST_AUDIO_PRIORITIES_OFFSET:HOST_AUDIO_PRIORITIES_OFFSET+24].hex(),
        private_spu=dict(owner_tags=owners,modes=modes,registers_hex=registers,bank_bindings=bindings,
            voices=voices,guest_clock_phase=struct.unpack_from('<I',spu,len(spu)-4)[0],
            section_sha256=hashlib.sha256(spu).hexdigest()),
        private_body_hex=core[:0x158].hex(), shots_hex=core[0x158:0x1558].hex(),
        trails_hex=core[0x1558:0x1678].hex(), attached_hex=core[0x1678:0x1768].hex(),
        p1_body_hex=ram[0x970A0:0x970A0+BODY_BYTES].hex(),
        native_timer=struct.unpack_from("<I", ram, 0xCCED0+0x90)[0],
        native_mode_phase=list(ram[0xCCED0:0xCCED2]), native_menu_state=list(ram[0xCF814:0xCF816]),
        input_history=dict(previous_input=struct.unpack_from("<H", core, input_at)[0],
            edges=struct.unpack_from("<H", core, input_at+2)[0], start=core[start_at],
            native_words=list(struct.unpack_from("<3H", core, 0x7C))),
        publication_tick=struct.unpack_from("<I", payload, HOST_CORE_END)[0],
        bank_count=count, ui_bank_count=ui_count,
        banks_sha256=hashlib.sha256(payload[HOST_CACHE_OFFSET:]).hexdigest())


def reduce_provider_restore(saved, restored):
    checks={name: saved[key] == restored[key] for name,key in (
        ("exact_current_build_key", "build_key"), ("same_provider_set", "provider_ids"),
        ("same_resource_and_original_asset_binding", "resource_binding_hex"),
        ("full_private_context_and_host_input_history", "semantic_core_hex"),
        ("explicit_native_and_host_input_history", "input_history"),
        ("saved_native_world_clock", "native_timer"), ("saved_native_mode_phase", "native_mode_phase"),
        ("saved_native_menu_state", "native_menu_state"),
        ("full_retained_bank_payloads", "banks_sha256"),
        ("saved_sprite_bank_count", "bank_count"), ("saved_ui_bank_count", "ui_bank_count"),
        ('persistent_private_audio_priorities','audio_priorities_hex'))}
    for key in ('owner_tags','modes','registers_hex','bank_bindings'):
        checks['private_spu_'+key]=saved['private_spu'][key]==restored['private_spu'][key]
    return checks


def require_audio_owner_contract(inspection):
    owners=inspection['private_spu']['owner_tags']
    expected=[MMX6_AUDIO_OWNER if MMX6_AUDIO_MASK&(1<<i) else 0 for i in range(24)]
    if owners!=expected:
        raise DebugError('Current-build snapshot does not retain the exact nine private voice owners')


def validate_state_build(build, source, profiles, expected_manifest, output):
    import coop_host_profile as manifests
    import qualify_mmx6_coop_jump_audio as binding
    manifest=manifests.validate_build_manifest(build,[p/'mmx6-runtime.exe' for p in profiles],
        evidence_directory=output/'manifest')
    if manifest['declared_sha256']!=expected_manifest:
        raise DebugError('Native state candidate manifest differs from explicit expected identity')
    return dict(manifest=manifest,declared_sources=binding.validate_sources(build,source,manifest))


def private_sample(client):
    import mmx6_coop_private_effects as effects
    raw = client.read(DIAGNOSTIC_ADDRESS, effects.END)
    parsed = effects.parse_effect_diagnostic(raw)
    row = parsed.json()
    base = row["observation"]
    if not row["available"] or base["ready"] != 1 or base["enrolled"] != 1 or base["failed"] or base["mailbox"]:
        raise DebugError("Current coherent private-effects extension and ready offline context required")
    row.update(p1_body_hex=raw[0x1800:0x1958].hex(), shots_hex=raw[0x300:0x1700].hex(),
               bank_count=struct.unpack_from("<I", raw, 28)[0], native_menu_state=list(client.read(0x800CF814, 2)))
    return row


def private_visible(row):
    return (row["available"] and row["marker"] > 0 and row["observation"]["players"][1]["action"] in (0x0C, 6) and
            len(row["trails"]) == 3 and
            all(e["allocation"] == 0x11 and e["visible"] == e["active"] == 1 and e["phase"] == 0 for e in row["trails"]))


def private_paused(row):
    base = row["observation"]
    return (base["native_mode"] == 10 and base["native_phase"] == 2 and base["pause_owner"] == 1 and
            row["native_menu_state"][0] == 1 and tuple(base["lifecycle"]) == (0, 0) and
            not base["scene_owner"] and [p["character"] for p in base["players"]] == [0, 1] and
            all(p["active"] and p["state"] == 1 and 0 < p["hp"] < 128 for p in base["players"]) and private_visible(row))


def reduce_private_restore(saved, row, *, completed_tick):
    """The first completion observation is an anchor, never restored evidence."""
    return dict(new_publication_after_completed_load=forward(completed_tick, row["observation"]["tick"]),
        publication_after_saved_provider=forward(saved["publication_tick"], row["observation"]["tick"]),
        native_p1_pause_retains_live_dash=private_paused(row),
        saved_native_clock_restored=saved["native_timer"] == row["observation"]["native_timer"],
        saved_native_menu_state_restored=saved["native_menu_state"] == row["native_menu_state"],
        full_private_body=saved["private_body_hex"] == row["p2_body_hex"],
        full_private_shots=saved["shots_hex"] == row["shots_hex"],
        full_private_trails=saved["trails_hex"] == "".join(e["raw_hex"] for e in row["trails"]),
        full_private_attached=saved["attached_hex"] == "".join(e["raw_hex"] for e in row["attached"]),
        full_p1_body=saved["p1_body_hex"] == row["p1_body_hex"],
        native_input_history=saved["input_history"]["native_words"] ==
            [row["native_held"], row["native_previous"], row["native_edges"]])


def snapshot_operation(control, operation, slot, records, *, timeout=20):
    before = control("savestate_status")
    if type(before.get("generation")) is not int or before.get("pending") != 0:
        raise DebugError("Snapshot operation requires an idle completion counter")
    acknowledgement = control("savestate", op=operation, slot=slot)
    record = dict(before=before, acknowledgement=acknowledgement, observations=[])
    records.append(record)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = control("savestate_status")
        record["observations"].append(status)
        generation = status.get("generation")
        advanced = type(generation) is int and 0 < ((generation - before["generation"]) & 0xFFFFFFFF) < 0x80000000
        if advanced and status.get("pending") == 0:
            record["completion"] = status
            if status.get("last_ok") != 1 or status.get("last_op") != operation or status.get("last_slot") != slot:
                raise DebugError(f"{operation}: completed with a failed or mismatched receipt")
            return status
        time.sleep(.05)
    raise DebugError(f"{operation}: acknowledgement did not reach a completed safe-boundary generation")


def sample(client):
    raw = client.read(DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES)
    row = parse_diagnostic(raw)
    if row.mailbox or row.failed or row.ready != 1 or row.enrolled != 1:
        raise DebugError("Snapshot observation has an unsafe/unready co-op context")
    bodies = [raw[0x1800:0x1800 + BODY_BYTES], raw[0x100:0x100 + BODY_BYTES]]
    return dict(observation=row.json(), bank_count=struct.unpack_from("<I", raw, 28)[0],
                native_menu_state=list(client.read(0x800CF814, 2)),
                body_hex=[body.hex() for body in bodies],
                body_sha256=[hashlib.sha256(body).hexdigest() for body in bodies])


def wait_sample(client, predicate, *, timeout=12):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = sample(client)
        if predicate(latest):
            return latest
        time.sleep(.025)
    raise DebugError(f"Native state predicate timed out; last={latest}")


def advance(client, count):
    start = sample(client)["observation"]["tick"]
    return wait_sample(client, lambda row: ((row["observation"]["tick"] - start) & 0xFFFFFFFF) >= count)


def pause(control, client, enabled):
    if not enabled:
        wait_sample(client, lambda row: row["observation"]["native_phase"] == 2 and
                    row["native_menu_state"][0] == 1)
    control("press", port=1, buttons=0xFFF7, frames=4)
    try:
        row = wait_sample(client, lambda row: row["observation"]["native_phase"] == (2 if enabled else 0)
                          and row["observation"]["pause_owner"] == (1 if enabled else 0))
    finally:
        control("clear_input", port=1)
    if enabled:
        # Native phase2 includes the opening/fade. The original game's menu
        # accepts input only after its state at CF814 reaches1 (pause fixture).
        row = wait_sample(client, lambda row: row["observation"]["native_phase"] == 2 and
                          row["native_menu_state"][0] == 1)
    return row


def restoration(saved, restored):
    fields = ("hp", "ammo", "weapon", "x_raw", "y_raw", "action", "character", "active")
    return dict(paused_p1_restored=restored["observation"]["native_phase"] == 2 and
                restored["observation"]["pause_owner"] == 1,
                resources_and_actor_fields_restored=all(
                    all(old[field] == new[field] for field in fields)
                    for old, new in zip(saved["observation"]["players"], restored["observation"]["players"])),
                complete_native_bodies_restored=saved["body_hex"] == restored["body_hex"])


def private_cards(candidate):
    return {str(p.relative_to(candidate / "saves")): sha256(p)
            for p in sorted((candidate / "saves").glob("*.mcd"))}


def staged_image_binding(candidate, expected_sha):
    prepared = json.loads((candidate / "preparation.json").read_text(encoding="utf-8"))
    if (prepared.get("exe_sha256") != expected_sha or sha256(candidate / "mmx6-runtime.exe") != expected_sha or
            prepared.get("automated_profile") is not True or prepared.get("source_card") is not None or
            prepared.get("source_card_sha256") is not None):
        raise DebugError("Private effect snapshots require the exact image and a private card-free automated preparation")
    baseline.candidate_environment(candidate, prepared)
    files = [candidate / "mmx6-runtime.exe", *candidate.glob("*.dll")]
    for directory in ("assets", "bios", "mods/bundled"):
        files.extend(p for p in (candidate / directory).rglob("*") if p.is_file())
    return {str(p.relative_to(candidate)).replace("\\", "/"): sha256(p) for p in sorted(files)}


def copy_slot_image(candidate, slot, artifact):
    paths = list((candidate / "saves").glob(f"*/state_*_slot{slot:02d}.pst"))
    if len(paths) != 1 or artifact.exists():
        raise DebugError("Completed save must produce one private slot image and a new retained artifact")
    if not paths[0].resolve().is_relative_to((candidate/"saves").resolve()) or not 36 <= paths[0].stat().st_size <= MAX_STATE_BYTES:
        raise DebugError("Completed slot image escaped the private profile or exceeded its bounded size")
    shutil.copy2(paths[0], artifact)
    parsed = parse_state_image(artifact.read_bytes())
    receipt = dict(path=str(artifact), sha256=sha256(artifact), size=artifact.stat().st_size,
                   slot_relative_path=str(paths[0].relative_to(candidate / "saves")), inspection=parsed)
    return receipt


def private_resources(row):
    return [(p["hp"], p["weapon"], tuple(p["ammo"])) for p in row["observation"]["players"]]


def private_resume_phase(reference, row, *, gameplay_seen, closing_tick):
    """Classify the source's one final menu publication before owner reset.

    stage_tick chooses ownership at entry, calls the original menu, then
    publishes. That call can change PLAY.phase2 to0; pause_owner clears only
    on the next stage entry. Accept no second distinct residual publication.
    All roster/resource/P1-position checks apply even to the closing interval.
    """
    base=row["observation"]
    if (base["native_mode"] != 10 or base["scene_owner"] or tuple(base["lifecycle"]) != (0,0) or
            [p["character"] for p in base["players"]] != [0,1] or
            any(not p["active"] or p["state"] != 1 for p in base["players"]) or
            private_resources(row) != private_resources(reference) or
            base["players"][0]["x_raw"] != reference["observation"]["players"][0]["x_raw"]):
        raise DebugError("Restored native dash resume changed roster, personal resources or P1 position")
    if base["native_phase"]==2 and base["pause_owner"]==1 and not gameplay_seen and closing_tick is None:
        return False,closing_tick
    if base["native_phase"]==0 and base["pause_owner"]==1 and not gameplay_seen:
        if closing_tick is not None and closing_tick != base["tick"]:
            raise DebugError("Native menu owner persisted across distinct gameplay publications")
        return False,base["tick"]
    if base["native_phase"]!=0 or base["pause_owner"]:
        raise DebugError("Restored native dash resume changed menu ownership")
    return True,closing_tick


def reduce_restored_retirement(reference, rows):
    """Observed native recovery only; timer progress is not a once-world proof."""
    checks = dict(original_menu_resume_advances_native_world=False,
        native_phase1_and_phase2_observed=False, finite_all_three_retired=False,
        ordered_native_recovery_publications=False, recovery_personal_resources_preserved=False,
        recovery_original_p1_position_preserved=False)
    if len(rows) < 3:
        return checks
    first_negative = next((i for i,row in enumerate(rows) if row["marker"] < 0), None)
    checks["original_menu_resume_advances_native_world"] = forward(
        reference["observation"]["native_timer"], rows[-1]["observation"]["native_timer"])
    checks["ordered_native_recovery_publications"] = all(
        forward(a["observation"]["tick"], b["observation"]["tick"]) and
        forward(a["observation"]["native_timer"], b["observation"]["native_timer"])
        for a,b in zip(rows, rows[1:]))
    checks["recovery_personal_resources_preserved"] = all(private_resources(row) == private_resources(reference) for row in rows)
    checks["recovery_original_p1_position_preserved"] = all(
        row["observation"]["players"][0]["x_raw"] == reference["observation"]["players"][0]["x_raw"] for row in rows)
    if first_negative is not None:
        drain = rows[first_negative:]
        checks["native_phase1_and_phase2_observed"] = all(row["marker"] <= 0 for row in drain) and all(
            any(row["marker"] < 0 and any(e["active"] and e["phase"] == phase for e in row["trails"]) for row in drain)
            for phase in (1, 2))
        delta = (drain[-1]["observation"]["native_timer"]-drain[0]["observation"]["native_timer"]) & 0xFFFFFFFF
        checks["finite_all_three_retired"] = (0 < delta <= 32 and drain[-1]["marker"] == 0 and
            len(drain[-1]["trails"]) == 3 and all(e["visible"] == e["active"] == 0 for e in drain[-1]["trails"]))
    return checks


class PrivateStateCase:
    """Original-input adapter around the existing owned baseline lifecycle."""
    def __init__(self, control, destination, evidence, *, timeout, adapter=None, input_path="offline_native"):
        from qualify_mmx6_coop_personal_menu import OfflineMenuAdapter
        self.adapter = adapter if adapter is not None else OfflineMenuAdapter(control, evidence, timeout=timeout)
        self.input_path = input_path
        self.control, self.client = control, self.adapter.client
        self.destination, self.evidence, self.timeout = destination, evidence, timeout
        evidence.update(status="failed_setup", checks={}, operations=[], observations=[], captures=[], inputs=[],
                        input_path=input_path, artwork_review="pending", ledger_status="unverified")

    def sample(self, label):
        row = private_sample(self.client)
        self.evidence["observations"].append(dict(label=label, **row))
        return row

    def wait(self, predicate, label):
        deadline = time.monotonic()+self.timeout
        while time.monotonic() < deadline:
            row = self.sample(label)
            if predicate(row):
                return row
            time.sleep(.012)
        raise DebugError(label+": native/coherent state predicate timed out")

    def hold(self, seat, bits, frames, label):
        before = self.sample(label+" before")
        receipt = dict(path=self.input_path, seat=seat, pressed=bits, accepted=False, bypasses=[], label=label,
                       before_tick=before["observation"]["tick"])
        self.evidence["inputs"].append(receipt)
        self.adapter.hold(seat, bits, frames, label)
        after = self.sample(label+" after neutral")
        receipt.update(accepted=True, after_tick=after["observation"]["tick"])
        return after

    def capture(self, label):
        self.evidence["captures"].append(capture_present(self.client, self.destination/(label+".png"), request=self.control))

    def open_live_window(self):
        self.adapter.settle_idle()
        initial = self.sample("Healthy idle before original native Circle")
        self.evidence["initial"] = initial
        if (any(p["hp"] != 32 for p in initial["observation"]["players"]) or initial["marker"] != 0 or
                any(e["visible"] or e["active"] for e in initial["trails"])):
            raise DebugError("Private snapshot setup requires healthy native heroes and retired trails")
        attempted = False
        def during_dash():
            nonlocal attempted
            row = self.sample("Circle+Left held before native P1 pause")
            if not attempted and row["observation"]["native_phase"] == 0 and private_visible(row):
                attempted = True
                self.evidence["accepted_native_dash"] = row
                self.hold(0, 8, 4, "Original P1 Start during accepted P2 Circle")
                row = self.wait(private_paused, "Input-ready P1 pause retaining positive native private pools")
                self.evidence["opened_live_window"] = row
            return row
        before = self.sample("P2 dash input bracket start")
        receipt = dict(path=self.input_path, seat=1, pressed=0x2080, accepted=False, bypasses=[],
                       before_tick=before["observation"]["tick"], label="Original P2 Circle+Left")
        self.evidence["inputs"].append(receipt)
        held = self.adapter.hold_observed(1, 0x2080, 8, receipt["label"], during_dash)
        receipt.update(accepted=True, held_ticks=[r["observation"]["tick"] for r in held])
        final = self.sample("Native positive effect state after accepted input neutral")
        receipt["after_tick"] = final["observation"]["tick"]
        if not attempted or not private_paused(final):
            raise DebugError("Ordinary native pause failed to retain the chosen live effect snapshot window")
        self.capture("live-private-effects-before-save")
        return initial

    def stable_window(self, label):
        """At least three new publications with a frozen full private context."""
        rows = []
        deadline = time.monotonic()+self.timeout
        while time.monotonic() < deadline:
            row = self.sample(label)
            if not private_paused(row):
                raise DebugError(label+": positive private pools/native input-ready pause lost")
            if rows and row["observation"]["tick"] == rows[-1]["observation"]["tick"]:
                continue
            if rows and not forward(rows[-1]["observation"]["tick"], row["observation"]["tick"]):
                raise DebugError(label+": diagnostic publication moved backwards")
            rows.append(row)
            if len(rows) >= 3:
                keys = ("p2_body_hex", "shots_hex", "trails", "attached", "native_held", "native_previous", "native_edges")
                if not all(all(r[k] == rows[0][k] for k in keys) and
                           r["observation"]["native_timer"] == rows[0]["observation"]["native_timer"] and
                           private_resources(r) == private_resources(rows[0]) for r in rows):
                    raise DebugError(label+": private state changed across paused publications")
                return rows
            time.sleep(.012)
        raise DebugError(label+": no three new completed private-state publications")

    def completed_load(self, saved, slot):
        snapshot_operation(self.control, "load", slot, self.evidence["operations"])
        anchor = self.sample("First observation after matching completed load receipt")
        self.evidence["load_publication_anchor"] = anchor
        tick = anchor["observation"]["tick"]
        restored = self.wait(lambda row: all(reduce_private_restore(saved, row, completed_tick=tick).values()),
                             "New published restored private state after completed load")
        self.evidence["restored"] = restored
        self.evidence["checks"].update(reduce_private_restore(saved, restored, completed_tick=tick))
        self.stable_window("Restored full private state remains frozen")
        return restored

    def resume_and_retire(self, reference, label):
        # Observe while Start is held: a control helper's final neutral spacing
        # must not conceal the short native phase1 transition.
        history = []
        self.evidence.setdefault("resume_recovery_windows", []).append(dict(label=label, observations=history))
        before = self.sample(label+" native Start bracket")
        receipt = dict(path=self.input_path, seat=0, pressed=8, accepted=False, bypasses=[], label=label,
                       before_tick=before["observation"]["tick"])
        self.evidence["inputs"].append(receipt)
        def observe_resume():
            row = self.sample(label+" native Start held")
            if row["observation"]["native_phase"] == 0:
                history.append(row)
            return row
        self.adapter.hold_observed(0, 8, 6, label+" original native Start", observe_resume)
        after_start = self.sample(label+" native Start after neutral")
        receipt.update(accepted=True, after_tick=after_start["observation"]["tick"])
        deadline, first_negative, start_timer = time.monotonic()+self.timeout, None, None
        gameplay_seen, closing_tick = False, None
        pending = list(history);history.clear()
        while time.monotonic() < deadline:
            row = pending.pop(0) if pending else self.sample(label+" native private effect continuation/drain")
            if history and row["observation"]["tick"] == history[-1]["observation"]["tick"]:
                time.sleep(.005);continue
            history.append(row)
            base = row["observation"]
            accepted,closing_tick=private_resume_phase(reference,row,
                gameplay_seen=gameplay_seen,closing_tick=closing_tick)
            if not accepted:
                time.sleep(.008)
                continue
            gameplay_seen=True
            timer = base["native_timer"]
            if start_timer is None:
                start_timer = timer
            if first_negative is None and row["marker"] < 0:
                first_negative = timer
            if first_negative is None:
                if ((timer-start_timer)&0xFFFFFFFF) > 120:
                    raise DebugError("Restored native positive-marker continuation exceeded its observation window")
            else:
                if row["marker"] > 0 or ((timer-first_negative)&0xFFFFFFFF) > 32:
                    raise DebugError("Restored native negative-marker drain retriggered or exceeded its finite bound")
                if row["marker"] == 0 and all(e["visible"] == e["active"] == 0 for e in row["trails"]):
                    break
            time.sleep(.008)
        else:
            raise DebugError("Restored native effect recovery timed out")
        checks = reduce_restored_retirement(reference, [row for row in history if
            row["observation"]["native_phase"] == 0 and row["observation"]["pause_owner"] == 0])
        self.evidence["checks"].update(checks)
        if not all(checks.values()):
            raise DebugError("Restored native dash did not expose its full source-bound drain and retirement")
        # Actual input after load must move P2 independently; no ack-only pass.
        self.adapter.settle_idle()
        before = self.sample("Restored native controls before genuine P2 Right")
        after = self.hold(1, 0x20, 6, "Original independent P2 Right after native retirement")
        old, new = before["observation"]["players"], after["observation"]["players"]
        independent = new[1]["x_raw"] > old[1]["x_raw"] and new[0]["x_raw"] == old[0]["x_raw"]
        preserved = private_resources(after) == private_resources(reference)
        self.evidence["checks"].update(genuine_p2_input_resumed_independently=independent,
                                      personal_hp_ammo_weapon_preserved=preserved)
        if not independent or not preserved:
            raise DebugError("Actual restored native input independence or personal resources failed")
        self.capture(label+"-native-after-dash-retirement-and-input")


def run_private_effects(args):
    import mmx6_coop_private_effects as effects
    import qualify_mmx6_coop_personal_menu as menu_adapter
    output = local_output(args.output)
    output.mkdir(parents=True)  # No overwritten prior receipts.
    report = dict(kind="native_same_build_private_effect_warm_cold_snapshot", status="failed_setup", phases={}, checks={},
        expected_exe_sha256=args.expected_sha, runner_source_sha256=sha256(Path(__file__)),
        artwork_review="pending", ledger_status="unverified", input_path="offline_native", limits=[
            "Current exact image, same local machine, healthy intro and fixed X/P1 + Zero/P2 only",
            "P1 original native pause retains a previously live Zero dash; no synthetic freeze or guest writes",
            "Read-only probe saves inspect restored provider input history and cache payloads, not a second loader",
            "Publication/presentation tail may advance; full semantic host state and immutable bank bytes must match",
            "Finite native phase1/2 retirement applies to the three dash trails; attached records are restored byte-for-byte",
            "Completed composed captures still require artwork review; no ledger, rewind, rollback or campaign pass",
            "Staging source observations are not compilation provenance; no AOT performance claim"])
    report["helper_sources"] = {Path(module.__file__).name: sha256(Path(module.__file__))
        for module in (effects, menu_adapter, baseline)}
    report["wire_contract"] = dict(pst=10, msnp=1, offline_provider="mmx6.local-coop", provider_schema=1,
        internal_wire_schema=HOST_WIRE_SCHEMA,private_spu_bytes=SPU_CURRENT_BYTES,
        source="src/mods/mmx6_coop_snapshot.inc", resources_bytes=HOST_RESOURCE_BYTES,
        semantic_core_bytes=HOST_SEMANTIC_BYTES, excluded_tail_bytes=10,
        excluded_tail_fields=["frame_count", "hud_fade", "world_packets", "hud_seat"])
    saved = {}
    try:
        if not args.expected_sha or not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha):
            raise ValueError("--private-effects requires --expected-sha with an exact lowercase executable SHA256")
        for port in (24893, 24894):
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", port))
        staged = {}
        for phase in ("warm", "cold"):
            candidate = output/phase
            os.environ.update(TEMP=str(output/"temp"), TMP=str(output/"temp"))
            (output/"temp").mkdir(exist_ok=True)
            prepare(args.build, args.source, candidate, args.disc, automated=True)
            staged[phase] = staged_image_binding(candidate, args.expected_sha)
        if staged["warm"] != staged["cold"]:
            raise DebugError("Warm/cold executable, DLL, original asset, BIOS or catalog identities differ")
        report["staged_image_bindings"] = staged
        report["exe_sha256"] = args.expected_sha
        report.update(validate_state_build(args.build,args.source,[output/'warm',output/'cold'],
            args.expected_manifest_sha256,output))

        def warm_exercise(control, _client, destination, evidence):
            case = PrivateStateCase(control, destination, evidence, timeout=args.progress_timeout)
            evidence["private_cards_before"] = private_cards(output/"warm")
            case.open_live_window()
            before = case.stable_window("Input-ready original live pool window before safe-boundary save")
            evidence["before_save_window"] = before
            snapshot_operation(control, "save", 8, evidence["operations"])
            image = copy_slot_image(output/"warm", 8, output/"snapshot.pst")
            report["snapshot"] = image;saved.update(image["inspection"])
            require_audio_owner_contract(saved)
            published = case.wait(lambda row: all(reduce_private_restore(saved, row,
                completed_tick=before[0]["observation"]["tick"]).values()),
                "Fresh original private pools after completed save")
            saved_match = reduce_private_restore(saved, published, completed_tick=before[0]["observation"]["tick"])
            evidence["saved_publication_checks"] = saved_match
            if not all(saved_match.values()):
                raise DebugError("Safe-boundary image did not retain the observed full native private effect state")
            evidence["status"] = "failed_behavior"
            case.resume_and_retire(published, "warm-before-load")
            evidence["before_load"] = case.sample("Naturally changed state before warm load")
            if private_visible(evidence["before_load"]):
                raise DebugError("Warm state did not naturally diverge from the positive saved effect pools")
            restored = case.completed_load(saved, 8)
            case.capture("warm-restored-live-private-pools-present")
            snapshot_operation(control, "save", 7, evidence["operations"])
            probe = copy_slot_image(output/"warm", 7, output/"warm-restored-probe.pst")
            evidence["restored_provider_probe"] = probe
            evidence["checks"].update(reduce_provider_restore(saved, probe["inspection"]))
            if not all(evidence["checks"].values()):
                raise DebugError("Warm actual loaded provider differs from saved semantic state/history/banks")
            case.resume_and_retire(restored, "warm-after-load")
            evidence["checks"]["native_private_cards_preserved"] = private_cards(output/"warm") == evidence["private_cards_before"]
            if not evidence["checks"]["native_private_cards_preserved"]:
                raise DebugError("Private native cards changed during warm snapshot operations")
            evidence["status"] = PRIVATE_SUCCESS

        report["phases"]["warm"] = baseline.run(output/"warm", 24893, args.boot_timeout, False, exercise=warm_exercise)
        if report["phases"]["warm"]["status"] != "passed":
            raise DebugError("Warm private-effect qualification failed; cold process was not launched")
        cold_snapshot = output/"cold/saves"/report["snapshot"]["slot_relative_path"]
        cold_snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output/"snapshot.pst", cold_snapshot)
        if sha256(cold_snapshot) != report["snapshot"]["sha256"]:
            raise DebugError("Exact private cold snapshot copy changed")

        def cold_exercise(control, _client, destination, evidence):
            case = PrivateStateCase(control, destination, evidence, timeout=args.progress_timeout)
            evidence["private_cards_before"] = private_cards(output/"cold")
            case.adapter.settle_idle()
            before = case.sample("Fresh-process cold private pools/cache before load")
            evidence["before_load"] = before
            if before["bank_count"] >= saved["bank_count"] or before["marker"] != 0 or any(
                    e["visible"] or e["active"] for e in before["trails"]):
                raise DebugError("Cold process did not begin with fewer retained banks and retired native private pools")
            evidence["checks"]["fresh_process_cache_smaller_without_warm_cache_copy"] = True
            restored = case.completed_load(saved, 8)
            evidence["status"] = "failed_behavior"
            case.capture("cold-restored-live-private-pools-present")
            snapshot_operation(control, "save", 7, evidence["operations"])
            probe = copy_slot_image(output/"cold", 7, output/"cold-restored-probe.pst")
            evidence["restored_provider_probe"] = probe
            evidence["checks"].update(reduce_provider_restore(saved, probe["inspection"]))
            if not all(evidence["checks"].values()):
                raise DebugError("Cold actual loaded provider failed full state/history/cache reconstruction")
            case.resume_and_retire(restored, "cold-after-load")
            evidence["checks"]["native_private_cards_preserved"] = private_cards(output/"cold") == evidence["private_cards_before"]
            if not evidence["checks"]["native_private_cards_preserved"]:
                raise DebugError("Private native cards changed during cold snapshot operations")
            evidence["status"] = PRIVATE_SUCCESS

        report["phases"]["cold"] = baseline.run(output/"cold", 24894, args.boot_timeout, False, exercise=cold_exercise)
        for phase, result in report["phases"].items():
            report["checks"][phase+"_completed_private_effect_state_case"] = (result["status"] == "passed" and
                result.get("exercise", {}).get("status") == PRIVATE_SUCCESS)
            report["checks"][phase+"_private_cards_unchanged"] = result["existing_private_cards_unchanged"]
            report.setdefault("final_private_cards", {})[phase] = private_cards(output/phase)
            if staged_image_binding(output/phase, args.expected_sha) != staged[phase]:
                raise DebugError("Candidate executable/assets/catalog changed during native qualification")
        if all(report["checks"].values()):
            report["status"] = PRIVATE_SUCCESS
        else:
            report["status"] = "failed_behavior" if any(
                phase.get("exercise", {}).get("status") == "failed_behavior" for phase in report["phases"].values()) else "failed_setup"
            report["error"] = "A retained native phase failed; see its original baseline and partial case receipts"
    except (DebugError, OSError, ValueError) as error:
        report["error"] = str(error)
        if any(phase.get("exercise", {}).get("status") == "failed_behavior" for phase in report["phases"].values()):
            report["status"] = "failed_behavior"
    finally:
        (output/"qualification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def run(args):
    if getattr(args, "private_effects", False):
        return run_private_effects(args)
    output = local_output(args.output)
    output.mkdir(parents=True)  # Fresh root; retain every failed attempt.
    report = dict(kind="native_same_build_warm_cold_snapshot", status="failed_setup", phases={}, checks={},
                  runner_source_sha256=sha256(Path(__file__)),
                  limits=["Same build and intro only; rewind, network state transfer and campaign restoration unverified",
                          "No AOT performance claim; source observations are not binary provenance",
                          "Composed captures require visual inspection; canonical screenshots may omit GL banks"])
    slot = 8
    try:
        for port in (24893, 24894):
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", port))
        for phase in ("warm", "cold"):
            prepare(args.build, args.source, output / phase, args.disc, automated=True)
        warm, cold = output / "warm", output / "cold"
        digest = sha256(warm / "mmx6-runtime.exe")
        if digest != sha256(cold / "mmx6-runtime.exe") or (args.expected_sha and digest != args.expected_sha):
            raise DebugError("Staged warm/cold executable identities differ from the requested same-build candidate")
        report["exe_sha256"] = digest
        saved = {}

        def warm_exercise(control, client, destination, evidence):
            evidence.update(checks={}, operations=[], captures=[])
            advance(client, 55)
            initial = sample(client)
            evidence["initial"] = initial
            control("press", port=2, buttons=0xBFFF, frames=6)
            jumped = advance(client, 5)
            control("press", port=2, buttons=0x7FFF, frames=8)
            attacked = advance(client, 6)
            control("clear_input", port=2)
            settled = advance(client, 70)
            evidence.update(jumped=jumped, attacked=attacked, settled=settled)
            evidence["checks"]["p2_native_jump_before_save"] = (
                jumped["observation"]["players"][1]["y_raw"] < initial["observation"]["players"][1]["y_raw"])
            evidence["checks"]["warm_retained_bank_growth"] = settled["bank_count"] > initial["bank_count"]
            evidence["captures"].append(capture_present(client, destination / "warm-native-resources.png", request=control))
            pause(control, client, True)
            advance(client, 5)
            before = sample(client)
            evidence["before_save"] = before
            evidence["captures"].append(capture_present(client, destination / "warm-paused-before-save.png", request=control))
            snapshot_operation(control, "save", slot, evidence["operations"])
            saved.update(sample(client))
            paths = list((warm / "saves").glob(f"*/state_*_slot{slot:02d}.pst"))
            if len(paths) != 1:
                raise DebugError(f"Completed save did not create one private slot image: {paths}")
            artifact = output / "snapshot.pst"
            shutil.copy2(paths[0], artifact)
            saved["slot_relative_path"] = str(paths[0].relative_to(warm / "saves"))
            report["snapshot"] = dict(path=str(artifact), size=artifact.stat().st_size,
                                      sha256=sha256(artifact), slot_relative_path=saved["slot_relative_path"])
            evidence["saved"] = dict(saved)
            pause(control, client, False)
            advance(client, 8)
            control("press", port=2, buttons=0xFFDF, frames=16)
            moved = advance(client, 24)
            control("clear_input", port=2)
            evidence["moved_after_save"] = moved
            evidence["checks"]["p2_changed_before_load"] = (
                moved["observation"]["players"][1]["x_raw"] != saved["observation"]["players"][1]["x_raw"])
            snapshot_operation(control, "load", slot, evidence["operations"])
            restored = wait_sample(client, lambda row: row["observation"]["native_phase"] == 2)
            evidence["restored"] = restored
            evidence["checks"].update(restoration(saved, restored))
            evidence["captures"].append(capture_present(client, destination / "warm-paused-restored.png", request=control))

        report["phases"]["warm"] = baseline.run(warm, 24893, args.boot_timeout, False, exercise=warm_exercise)
        if "snapshot" not in report:
            raise DebugError("Warm phase produced no completed same-build snapshot for cold qualification")
        destination = cold / "saves" / saved["slot_relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output / "snapshot.pst", destination)
        if sha256(destination) != report["snapshot"]["sha256"]:
            raise DebugError("Private cold snapshot copy changed")

        def cold_exercise(control, client, destination, evidence):
            evidence.update(checks={}, operations=[], captures=[])
            advance(client, 55)
            before = sample(client)
            evidence["before_load"] = before
            evidence["checks"]["cold_cache_smaller_than_saved"] = before["bank_count"] < saved["bank_count"]
            snapshot_operation(control, "load", slot, evidence["operations"])
            restored = wait_sample(client, lambda row: row["observation"]["native_phase"] == 2)
            evidence["restored"] = restored
            evidence["checks"].update(restoration(saved, restored))
            evidence["checks"]["saved_retained_cache_reconstructed"] = restored["bank_count"] == saved["bank_count"]
            evidence["captures"].append(capture_present(client, destination / "cold-paused-restored.png", request=control))
            pause(control, client, False)
            old = advance(client, 8)
            control("press", port=2, buttons=0xFFDF, frames=12)
            moved = advance(client, 20)
            control("clear_input", port=2)
            evidence["checks"]["cold_p2_control_independent"] = (
                moved["observation"]["players"][1]["x_raw"] > old["observation"]["players"][1]["x_raw"] and
                moved["observation"]["players"][0]["x_raw"] == old["observation"]["players"][0]["x_raw"])
            control("press", port=1, buttons=0xBFFF, frames=6)
            jumped = advance(client, 5)
            control("clear_input", port=1)
            evidence["checks"]["cold_p1_control_independent"] = (
                jumped["observation"]["players"][0]["y_raw"] < moved["observation"]["players"][0]["y_raw"] and
                jumped["observation"]["players"][1]["y_raw"] == moved["observation"]["players"][1]["y_raw"])
            evidence.update(after_p2_input=moved, after_p1_input=jumped)
            evidence["captures"].append(capture_present(client, destination / "cold-native-after-input.png", request=control))

        report["phases"]["cold"] = baseline.run(cold, 24894, args.boot_timeout, False, exercise=cold_exercise)
        report["checks"] = {name: phase["status"] == "passed" for name, phase in report["phases"].items()}
        report["status"] = "passed" if all(report["checks"].values()) else "failed"
    except (DebugError, OSError, ValueError) as error:
        report["error"] = str(error)
        if report["phases"]:
            report["status"] = "failed"
    finally:
        (output / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha")
    parser.add_argument('--expected-manifest-sha256')
    parser.add_argument("--boot-timeout", type=float, default=200)
    parser.add_argument("--private-effects", action="store_true",
                        help="Qualify live Zero private pools in warm/cold processes; requires exact image and manifest SHA256")
    parser.add_argument("--progress-timeout", type=float, default=12)
    return parser


def validate_options(parser, args):
    if args.expected_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha):
        parser.error("--expected-sha must contain 64 lowercase hexadecimal digits")
    if args.private_effects and not args.expected_sha:
        parser.error("--private-effects requires --expected-sha")
    if args.private_effects and (args.expected_manifest_sha256 is None or
        re.fullmatch(r'[0-9a-f]{64}',args.expected_manifest_sha256) is None):
        parser.error('--private-effects requires exact --expected-manifest-sha256')
    if not math.isfinite(args.boot_timeout) or not 0 < args.boot_timeout <= 600:
        parser.error("--boot-timeout must be in (0,600]")
    if not math.isfinite(args.progress_timeout) or not 0 < args.progress_timeout <= 60:
        parser.error("--progress-timeout must be in (0,60]")


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    validate_options(parser, args)
    result = run(args)
    print(json.dumps(dict(status=result["status"], error=result.get("error"), report=str(args.output / "qualification.json"))))
    return 0 if result["status"] in ("passed", PRIVATE_SUCCESS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
