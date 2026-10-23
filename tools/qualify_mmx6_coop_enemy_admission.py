"""Bounded original-input offline R13 enemy admission/interaction case.

Record25 is admitted by the shared camera while P1 stays fixed. Read-only
instance evidence goes beyond the record bit; no guest setup writes are used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import time

import qualify_mmx6_coop_baseline as baseline
from prepare_mmx6_coop_playtest import local_output, prepare, sha256
from coop_debug import (DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES, DebugError,
                        capture_present, parse_diagnostic)

RECORD = 0x800FA2DC
POOL = 0x8008EF48
STRIDE = 0x9C
SLOTS = 48
BUILD_SHA = "bd7b9449d9fbc5c9c2137902ba2d8d525d1886211b03fd6756d0f76fbc9c263e"


def native_43(gpu, native_wide):
    # ws_nw.native_wide is a stored preference even while widescreen is off.
    # GpuWsDebug.mode is the active mode: 0=off, 1=squash, 2=native-wide.
    ws = gpu.get("ws", {})
    return (gpu.get("width"), gpu.get("height"), ws.get("configured"),
            ws.get("mode"), ws.get("x_margin"), ws.get("nw_extra"),
            native_wide.get("mode"), native_wide.get("nw_extra")) == \
            (320, 240, 0, 0, 0, 0, 0, 0)


def parse_pool(raw):
    if len(raw) != STRIDE * SLOTS:
        raise DebugError("Truncated native enemy pool")
    live, matching = [], []
    for slot in range(SLOTS):
        body = raw[slot * STRIDE:(slot + 1) * STRIDE]
        if not body[0]:  # Freed native slots may retain stale origin fields.
            continue
        record = struct.unpack_from("<I", body, 0x10)[0]
        x, y = struct.unpack_from("<ii", body, 8)
        item = dict(address=hex(POOL + slot * STRIDE), slot=slot, origin=hex(record),
                    flags=body[0], type=body[1], subtype=body[2], render=body[3],
                    phase=body[4], action=body[5], subaction=body[6], hp=body[0x5C],
                    strength=body[0x60], iframe=body[0x61], x_raw=x, y_raw=y,
                    x=x / 65536, y=y / 65536, body_hex=body.hex())
        live.append(item)
        if record == RECORD and body[1] == 1:
            matching.append(item)
    if len(matching) > 1:
        raise DebugError("Multiple live type1 instances claim the same native placement record")
    return live, matching[0] if matching else None


def observe_case(client):
    raw = client.read(DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES)
    row = parse_diagnostic(raw)
    if (row.ready, row.enrolled, row.failed, row.lifecycle, row.native_mode,
            row.native_phase, row.pause_owner, row.scene_owner, row.mailbox) != \
            (1, 1, 0, (0, 0), 10, 0, 0, 0, 0):
        raise DebugError("Native enemy case left independent living intro gameplay")
    camera = client.read(0x800971F8, 0x20)
    current_x, current_y = struct.unpack_from("<h", camera, 0xA)[0], struct.unpack_from("<h", camera, 0xE)[0]
    previous_x, previous_y = struct.unpack_from("<h", camera, 0x16)[0], struct.unpack_from("<h", camera, 0x1A)[0]
    record = client.read(RECORD, 12)
    live, instance = parse_pool(client.read(POOL, SLOTS * STRIDE))
    return dict(observation=row.json(), camera=[current_x, current_y], previous_camera=[previous_x, previous_y],
                record_hex=record.hex(), record_allocated=bool(record[0] & 1), instance=instance,
                live_pool=live, native_shared_gate=client.read(0x800CCEE2, 1)[0],
                p2_hit_counter=struct.unpack_from("<I", raw, 0x28)[0],
                p2_contact_counter=struct.unpack_from("<I", raw, 0x44)[0])


def run(args):
    output = local_output(args.output)
    prepare(args.build, args.source, output, args.disc, automated=True)
    if sha256(output / "mmx6-runtime.exe") != BUILD_SHA:
        raise ValueError("R13 case requires the frozen bd7 candidate")

    def exercise(control, client, destination, report):
        report.update(checks={}, observations=[], captures=[],
            scope="offline intro record25 only; R13 comparison row remains incomplete",
            unverified=["paired transport equivalent", "independent runtime proof of exactly one native world update"],
            source_contract={"scanner": "80029F38", "allocator": "8002BBF4", "enemy_update_loop": "8002000C",
                             "record": hex(RECORD), "type1_init": "800EAFFC", "type1_phase1": "800EAC8C",
                             "intro_overlay_sha256": "d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607"},
            input_path="original port2 SIO pad; host virtual layer in this SDK is P1-only",
            limits=["Timer progress does not prove exactly one world update",
                    "Camera, pool and diagnostic reads are separate bounded observations, not one atomic world sample",
                    "Type1 native AI proximity tests resident P1; P2 proximity alone is not qualified targeting",
                    "No paired result, ledger pass, full campaign or audible assertion"])
        time.sleep(1)
        control("clear_input", port=1)
        control("clear_input", port=2)
        gpu = control("gpu_state")
        native_wide = control("ws_nw")  # No mutation fields: read-only query.
        report.update(gpu=gpu, native_wide=native_wide)
        if not native_43(gpu, native_wide):
            raise DebugError("Authored R13 bounds require native 4:3 with margin0")
        initial = observe_case(client)
        report["observations"].append(dict(label="initial", **initial))
        p1x = initial["observation"]["players"][0]["x_raw"]
        if p1x != 144 << 16 or initial["camera"] != [0, 944] or initial["record_allocated"] or initial["instance"]:
            raise DebugError("Initial record/camera/P1 conditions are confounded; no route traversal attempted")
        report["captures"].append(capture_present(client, destination / "before-admission.png", request=control))
        selected_address = None

        def take(label):
            row = observe_case(client)
            report["observations"].append(dict(label=label, **row))
            if row["observation"]["players"][0]["x_raw"] != p1x:
                raise DebugError("P1 moved during the fixed-primary admission case")
            if row["instance"] and selected_address is not None and row["instance"]["address"] != selected_address:
                raise DebugError("Native instance identity changed during the selected interaction")
            return row

        def window(frames, label):
            start = take(label + " start")["observation"]["tick"]
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                row = take(label)
                if ((row["observation"]["tick"] - start) & 0xFFFFFFFF) >= frames:
                    return row
                time.sleep(.01)
            raise DebugError("Native case publication window stopped advancing")

        admitted = None
        for step in range(32):
            control("press", port=2, buttons=0xFFDF, frames=4)
            row = window(5, f"P2 admission lead {step}")
            control("clear_input", port=2)
            if row["instance"]:
                admitted = row
                break
            if row["camera"][0] > 80:
                raise DebugError("Camera passed the selected admission window without a bound native instance")
        if admitted is None:
            raise DebugError("Bounded P2 lead did not admit the selected placement")
        report["admitted"] = admitted
        report["checks"]["camera_admits_record_with_p1_fixed"] = 48 <= admitted["camera"][0] <= 80
        initialized = window(8, "native enemy initialization")
        instance = initialized["instance"]
        if not instance or instance["phase"] != 1 or instance["hp"] != 12 or instance["subtype"] != 1:
            raise DebugError("Bound record did not execute its native type1 initialization")
        selected_address = instance["address"]
        report["initialized"] = initialized
        report["checks"]["record_bound_native_initialization"] = True
        report["captures"].append(capture_present(client, destination / "native-instance-admitted.png", request=control))

        for step in range(24):
            row = take("approach bound instance")
            target = row["instance"]
            if not target:
                raise DebugError("Selected instance disappeared before the planned interaction")
            if target["x"] - row["observation"]["players"][1]["x_raw"] / 65536 <= 40:
                break
            control("press", port=2, buttons=0xFFDF, frames=4)
            window(5, f"P2 approach {step}")
            control("clear_input", port=2)
        else:
            raise DebugError("P2 did not reach the bounded original-input attack position")
        before_attack = take("before native P2 attack")
        report["before_attack"] = before_attack
        control("press", port=2, buttons=0xBFFF, frames=6)
        window(4, "P2 jump toward selected enemy")
        control("press", port=2, buttons=0x7FFF, frames=8)
        hit = None
        for index in range(25):
            row = window(2, f"native P2 attack interaction {index}")
            target = row["instance"]
            if target and (target["hp"] < 12 or target["phase"] >= 2):
                hit = row
                break
        control("clear_input", port=2)
        report["interaction"] = hit or take("interaction not observed")
        report["checks"]["native_p2_attack_changes_bound_enemy"] = hit is not None
        report["checks"]["p1_stayed_fixed"] = all(
            row["observation"]["players"][0]["x_raw"] == p1x for row in report["observations"])
        report["checks"]["native_world_timer_advanced"] = (
            report["interaction"]["observation"]["native_timer"] > initial["observation"]["native_timer"])
        report["captures"].append(capture_present(client, destination / "native-enemy-interaction.png", request=control))

    result = baseline.run(output, 24895, 200, False, exercise=exercise)
    (output / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(dict(status=result["status"], error=result.get("error"),
                         report=str(args.output / "qualification.json"))))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
