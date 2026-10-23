"""Launch one private prepared candidate, retain bounded evidence, stop only it.

This establishes intro/input access, not campaign or full netplay parity.
Automated launches are hidden, muted and use the candidate's non-C paths.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from coop_debug import DebugClient, DebugError, observe
from prepare_mmx6_coop_playtest import sha256, local_output


def owns_listener(port: int, pid: int) -> bool:
    """Check the actual Windows TCP listener PID before sending controls."""
    if os.name != "nt":
        raise DebugError("Owned Windows candidate qualification requires Windows TCP ownership checks")
    import ctypes
    from ctypes import wintypes
    class Row(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in
                    ("state", "local_address", "local_port", "remote_address", "remote_port", "pid")]
    size = wintypes.DWORD()
    function = ctypes.windll.iphlpapi.GetExtendedTcpTable
    function(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)
    buffer = ctypes.create_string_buffer(size.value)
    if function(buffer, ctypes.byref(size), False, socket.AF_INET, 3, 0):
        return False
    count = wintypes.DWORD.from_buffer(buffer).value
    for index in range(count):
        row = Row.from_buffer(buffer, 4+index*ctypes.sizeof(Row))
        if socket.ntohs(row.local_port & 0xFFFF) == port and row.pid == pid:
            return True
    return False


def candidate_environment(candidate: Path, preparation: dict) -> dict:
    local_output(candidate)
    if Path(preparation["output"]).resolve() != candidate:
        raise ValueError("Candidate moved; prepare a fresh profile with resolved paths")
    for name, key in (("mmx6-runtime.exe", "exe_sha256"), ("game.toml", "game_config_sha256")):
        if sha256(candidate / name) != preparation[key]:
            raise ValueError(f"Prepared {name} changed; prepare a fresh candidate")
    for record in preparation.get("source_observation", {}).get("repositories", {}).values():
        if not record.get("available"):
            continue
        patch = Path(record["patch"]).resolve()
        if not patch.is_relative_to(candidate / "logs") or not patch.is_file() or \
                sha256(patch) != record["patch_sha256"]:
            raise ValueError("Source observation artifact changed or escaped the private profile")
    values = json.loads((candidate / "environment.json").read_text())
    path_keys = {"TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "XDG_CACHE_HOME",
                 "PSX_RESIDENT_CACHE", "PSX_OVERLAY_CACHE_DIR",
                 "PSX_OVERLAY_CAPTURE_ROOT", "PSX_OVERLAY_CAPTURES"}
    flags = {"PSX_OVERLAY_AUTOCOMPILE_OFF": "1", "PSX_DEV_INPUT": "0"}
    if set(values) != path_keys | set(flags):
        raise ValueError("Unexpected candidate environment keys")
    for name in path_keys:
        resolved = Path(values[name]).resolve()
        if not resolved.is_relative_to(candidate) or resolved == candidate:
            raise ValueError(f"Candidate {name} must stay inside the private profile")
        local_output(resolved)
    if any(values[name] != value for name, value in flags.items()):
        raise ValueError("Unexpected candidate runtime flags")
    environment = os.environ.copy()
    environment.pop("PSX_HEADLESS", None)
    environment.update(values)
    environment["SDL_AUDIODRIVER"] = "dummy"
    return environment


def run(candidate: Path, port: int, timeout: float, legacy: bool, *, exercise=None) -> dict:
    candidate = candidate.resolve(strict=True)
    preparation = json.loads((candidate / "preparation.json").read_text())
    environment = candidate_environment(candidate, preparation)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", port))
    output = candidate / "baseline"
    output.mkdir()  # Preserve previous failures instead of overwriting evidence.
    args = [str(candidate / "mmx6-runtime.exe"), "--game", str(candidate / "game.toml"),
            "--memcard-dir", str(candidate / "saves"), "--hidden-window", "--debug-port", str(port)]
    result = {"kind": "bounded_intro_baseline", "status": "failed_setup",
              "preparation": preparation, "args": args, "observations": [],
              "checks": {}, "limits": ["Intro only; no campaign, audible or physical-controller pass",
                                          "Bounded host digest is not a complete core/mod checksum"]}
    before = {p.name: p.read_bytes() for p in (candidate / "saves").glob("*.mcd")}
    client = DebugClient(port)
    process = None
    def control(command, **fields):
        if process is None or process.poll() is not None or not owns_listener(port, process.pid):
            raise DebugError("Owned runtime does not own the debug listener")
        return client.request(command, **fields)
    def sample():
        row = observe(client, allow_legacy=legacy)
        if row.lifecycle != (0, 0) or row.scene_owner or row.pause_owner or row.mailbox:
            raise DebugError("Intro actors left the safe independent-input setup")
        if not legacy and (row.ready != 1 or row.enrolled != 1 or row.failed != 0 or
                           row.native_mode != 10 or row.native_phase != 0):
            raise DebugError("Co-op context is not ready in native gameplay")
        return row
    def wait_ticks(start, count):
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            row = sample()
            if (row.native_timer-start.native_timer) & 0xFFFFFFFF >= count:
                return row
            time.sleep(0.015)
        raise DebugError("Native gameplay did not consume the bounded input window")
    try:
        with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(args, cwd=candidate, env=environment, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            result["owned_pid"] = process.pid
            deadline, next_input, step = time.monotonic()+timeout, 0.0, 0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise DebugError(f"Owned runtime exited during setup: {process.returncode}")
                try:
                    if not owns_listener(port, process.pid):
                        time.sleep(0.1)
                        continue
                    pad = client.request("pad_status")
                    if not pad.get("slot0", {}).get("connected"):
                        result["pad_status"] = pad
                        raise ValueError("Automated P1 pad is disconnected; prepare --automated")
                    mode = client.read(0x800CCED0, 2)
                    p1_action = client.read(0x800970A5, 1)[0]
                    result["setup_latest"] = {"native_mode": list(mode), "p1_action": p1_action,
                                              "p1_connected": pad["slot0"]["connected"]}
                    if mode[0] == 10 and p1_action == 2:
                        state = observe(client, allow_legacy=legacy)
                        if state.lifecycle == (0, 0) and state.players[1].action == 2:
                            break
                    if time.monotonic() >= next_input:
                        # Original frontend/dialogue input only. No state, actor,
                        # checkpoint, scene or progression writes are involved.
                        control("press", buttons=0xFFF7 if mode[0] != 10 and step % 3 == 0 else 0xBFFF, frames=6)
                        step += 1
                        next_input = time.monotonic()+0.8
                except (DebugError, ConnectionError, OSError):
                    pass  # Setup remains bounded by the single overall deadline.
                time.sleep(0.15)
            else:
                raise DebugError("Native intro did not reach two idle, living heroes before the setup deadline")
            control("clear_input")
            # Direct debug SIO injection; this does not qualify physical input
            # devices or host controller transforms. The mailbox stays unused.
            start = sample()
            result["observations"].append(start.json())
            result["status"] = "failed"
            control("press", port=2, buttons=0xFFDF, frames=12)
            moved = wait_ticks(start, 20)
            control("clear_input", port=2)
            result["observations"].append(moved.json())
            result["checks"]["p2_native_movement"] = moved.players[1].x_raw > start.players[1].x_raw
            result["checks"]["p1_independent"] = moved.players[0].x_raw == start.players[0].x_raw
            result["checks"]["mailbox_unused"] = start.mailbox == moved.mailbox == 0
            control("press", port=1, buttons=0xBFFF, frames=6)
            jumped = wait_ticks(moved, 5)
            result["observations"].append(jumped.json())
            result["checks"]["p1_native_jump"] = jumped.players[0].y_raw < moved.players[0].y_raw
            result["checks"]["p2_jump_independent"] = jumped.players[1].y_raw == moved.players[1].y_raw
            result["checks"]["healthy_heroes"] = all(p.hp > 0 for p in jumped.players)
            control("screenshot", path=str(output / "intro.png"))
            if not (output / "intro.png").is_file() or (output / "intro.png").stat().st_size == 0:
                raise DebugError("Screenshot command did not produce an artifact")
            result["intro_image_sha256"] = sha256(output / "intro.png")
            if exercise is not None:
                result["exercise"] = {}
                exercise(control, client, output, result["exercise"])
                result["checks"].update(result["exercise"].get("checks", {}))
            result["status"] = "passed" if all(result["checks"].values()) else "failed"
    except (DebugError, OSError, ValueError) as error:
        result["error"] = str(error)
        if process is not None and process.poll() is None:
            result["failure_observations"] = {}
            for command in ("pad_status", "netplay_status", "gpu_state"):
                try:
                    result["failure_observations"][command] = control(command)
                except (DebugError, OSError) as observation_error:
                    result["failure_observations"][command] = {"error": str(observation_error)}
            try:
                control("screenshot", path=str(output / "failure.png"))
            except (DebugError, OSError):
                pass
    finally:
        if process is not None:
            if process.poll() is not None:
                result["status"] = "failed" if result["status"] == "passed" else result["status"]
                result["unexpected_exit"] = True
            if process.poll() is None:
                try:
                    control("clear_input", port=1)
                    control("clear_input", port=2)
                    control("quit")
                    process.wait(timeout=5)
                    result["shutdown"] = "graceful"
                except (DebugError, OSError, subprocess.TimeoutExpired):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait(timeout=5)
                    result["shutdown"] = "owned_process_terminated"
            result["exit_code"] = process.poll()
        result["existing_private_cards_unchanged"] = all((candidate / "saves" / name).read_bytes() == data
                                                        for name, data in before.items())
        if not result["existing_private_cards_unchanged"]:
            result["status"] = "failed"
        (output / "qualification.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--port", type=int, default=24890)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--legacy", action="store_true", help="Allow frozen pre-schema baseline only")
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("Timeout must be in (0,600] seconds")
    result = run(args.candidate, args.port, args.timeout, args.legacy)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
