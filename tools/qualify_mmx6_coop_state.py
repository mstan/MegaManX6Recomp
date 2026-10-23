"""Owned, muted, same-build native warm/cold X6 snapshot qualification.

Uses original pad input and asynchronous save/load completion receipts. Never
writes guest RAM, fixture mailboxes, source cards, or a comparison ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import struct
import time

import qualify_mmx6_coop_baseline as baseline
from prepare_mmx6_coop_playtest import local_output, prepare, sha256
from coop_debug import (BODY_BYTES, DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES,
                        DebugError, capture_present, parse_diagnostic)


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


def run(args):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha")
    parser.add_argument("--boot-timeout", type=float, default=200)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(dict(status=result["status"], error=result.get("error"), report=str(args.output / "qualification.json"))))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
