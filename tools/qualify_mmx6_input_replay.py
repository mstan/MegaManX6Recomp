"""Own one sealed offline capture and private same-image N/C replay (Windows).

No source cards, guest writes, direct SIO overrides, fixtures or outcome hashes.
Exit0 means a complete native-consumption stream was consumed; R26 and native
outcome equality remain unverified. Every destination must be fresh F:/G:.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import traceback

import coop_debug as debug
import coop_host_profile as manifests
import mmx6_input_recording as codec
import prepare_mmx6_coop_playtest as preparation
import prepare_mmx6_input_replay as replay_preparation
import qualify_mmx6_coop_baseline as baseline

SUCCESS = "native_stream_consumed_outcomes_unverified"
PREFIXES = ("PSX_", "MMX6_INPUT_", "RNET_", "LNG_")


def json_object(path: Path, maximum=1024 * 1024) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field: " + key)
            result[key] = value
        return result
    raw = replay_preparation.bounded(path, maximum)
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid JSON constant")))
    if not isinstance(value, dict):
        raise ValueError("Expected an artifact JSON object")
    return value


def sanitized_environment(owned: dict, profile: Path) -> dict:
    # Keep credentials out of receipts; only this explicit owned overlay is
    # recorded. Never mutate the parent process environment.
    environment = {name: value for name, value in os.environ.items()
                   if not name.upper().startswith(PREFIXES)}
    environment.update(owned)
    environment.update(SDL_AUDIODRIVER="dummy", XDG_DATA_HOME=str(profile / "data"),
                       XDG_CONFIG_HOME=str(profile / "appdata"),
                       PYTHONPYCACHEPREFIX=str(profile / "cache/pycache"))
    return environment


def replay_environment(profile: Path, receipt: dict) -> dict:
    profile = preparation.local_output(profile).resolve(strict=True)
    values = json_object(profile / "environment.json")
    if values != receipt["environment"]:
        raise ValueError("Prepared replay environment changed")
    path_keys = {"TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "XDG_CACHE_HOME", "PYTHONPYCACHEPREFIX",
                 "PSX_RESIDENT_CACHE", "PSX_OVERLAY_CACHE_DIR", "PSX_OVERLAY_CAPTURE_ROOT",
                 "PSX_OVERLAY_CAPTURES", "MMX6_INPUT_REPLAY", "MMX6_INPUT_REPLAY_PROFILE", "MMX6_INPUT_RECORDING_DIR"}
    if set(values) != path_keys | {"SDL_AUDIODRIVER"} or values["SDL_AUDIODRIVER"] != "dummy":
        raise ValueError("Unsupported replay environment contract")
    for name in path_keys:
        if not isinstance(values[name], str):
            raise ValueError("Replay environment path must be text")
        path = Path(values[name]).resolve()
        if (path == profile and name != "MMX6_INPUT_REPLAY_PROFILE") or not path.is_relative_to(profile):
            raise ValueError("Replay environment escaped its owned profile")
    if (Path(values["MMX6_INPUT_REPLAY"]).resolve() != profile / "replay/inputs.jsonl" or
            Path(values["MMX6_INPUT_REPLAY_PROFILE"]).resolve() != profile):
        raise ValueError("Replay input/profile binding changed")
    return sanitized_environment(values, profile)


def configure_two_digital_slots(candidate: Path) -> None:
    # prepare() owns this fresh configuration. Never edit a user's profile.
    path = candidate / "settings.toml"
    text = path.read_text(encoding="utf-8")
    old = 'p1_device = "keyboard"\np2_device = "none"'
    if text.count(old) != 1:
        raise ValueError("Unexpected fresh automated controller configuration")
    path.write_text(text.replace(old, 'p1_device = "keyboard"\np2_device = "keyboard"\n'
                                 'p1_mode = "digital"\np2_mode = "digital"'), encoding="utf-8")


class OwnedClient:
    def __init__(self, control): self.control = control
    def request(self, command, **fields): return self.control(command, **fields)
    def read(self, address, size): return debug.DebugClient.read(self, address, size)


def verify_host_status(status: dict, seat: int, pressed: int | None = None) -> None:
    if (type(status.get("host_input_slots")) is not int or status["host_input_slots"] < 2 or
            type(status.get("host_port")) is not int or status["host_port"] != seat + 1):
        raise ValueError("SDK lacks acknowledged per-port published host devices")
    for slot in (0, 1):
        pad = status.get(f"slot{slot}", {})
        if (pad.get("connected") is not True or pad.get("analog") is not False or
                type(pad.get("type")) is not int or pad["type"] != 0):
            raise ValueError("Both offline native slots must stay connected and digital")
    if any(status.get(name) != -1 for name in ("override", "override_p2", "override_pad_type")) or \
            status.get("override_axes_valid") is not False:
        raise ValueError("Direct SIO override is active; ordinary capture is unsupported")
    if pressed is not None:
        try: actual = int(status.get("host_buttons", ""), 0)
        except (TypeError, ValueError): actual = -1
        if status.get("host_layer") is not True or actual != (0xFFFF ^ pressed):
            raise ValueError("Selected virtual host port did not acknowledge its buttons")


class HostRoute:
    def __init__(self, control, report, progress_timeout):
        self.control, self.client, self.report, self.timeout = control, OwnedClient(control), report, progress_timeout
        report.update(inputs=[], observations=[], windows=[], checks={})
    def set(self, seat, bits):
        if type(seat) is not int or seat not in (0, 1) or type(bits) is not int or not 0 <= bits <= 0xFFFF:
            raise ValueError("Expected a co-op seat and 16-bit host buttons")
        self.control("set_input", layer="host", port=seat+1, buttons=hex(0xFFFF ^ bits))
        status = self.control("pad_status", port=seat+1)
        verify_host_status(status, seat, bits)
        self.report["inputs"].append(dict(seat=seat, pressed=bits, status=status))
    def sample(self, label):
        row = debug.observe(self.client)
        if (row.ready != 1 or row.enrolled != 1 or row.failed != 0 or row.mailbox or
                row.scene_owner or row.pause_owner or row.native_mode != 10 or row.native_phase != 0 or
                row.lifecycle != (0, 0) or any(player.hp <= 0 for player in row.players)):
            raise debug.DebugError("Capture route left healthy independent native intro")
        self.report["observations"].append(dict(label=label, **row.json()))
        return row
    def advance(self, start, frames, label):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            row = self.sample(label)
            delta = (row.native_timer-start.native_timer) & 0xFFFFFFFF
            if delta >= 0x80000000:
                raise debug.DebugError("Native world clock moved backwards")
            if delta >= frames:
                self.report["windows"].append(dict(label=label, requested_native_ticks=frames,
                                                   start=start.json(), end=row.json()))
                return row
            time.sleep(.015)
        raise debug.DebugError("Native world clock did not finish the held host-input window")
    def hold(self, seat, bits, frames, label):
        start = self.sample(label + " start")
        original = None
        try:
            self.set(seat, bits)
            return self.advance(start, frames, label)
        except BaseException as error:
            original = error
            raise
        finally:
            try:
                self.set(seat, 0)  # Neutral, never disconnect/clear the device.
            except Exception as error:
                self.report.setdefault("release_errors", []).append(dict(seat=seat, error=str(error),
                    original_error=str(original) if original else None))
                if original is None: raise
    def exercise(self):
        deadline = time.monotonic() + self.timeout
        while True:
            start = self.sample("both heroes idle")
            if all(player.action == 2 for player in start.players): break
            if time.monotonic() >= deadline: raise debug.DebugError("Heroes did not settle after the frontend input release")
            time.sleep(.015)
        moved = self.hold(1, 0x20, 12, "P2 ordinary host Right")
        settled = self.advance(moved, 5, "P2 neutral release")
        jumped = self.hold(0, 0x4000, 5, "P1 ordinary host Jump")
        self.report["checks"].update(
            p2_native_movement=moved.players[1].x_raw > start.players[1].x_raw,
            p1_independent=moved.players[0].x_raw == start.players[0].x_raw,
            p1_native_jump=jumped.players[0].y_raw < settled.players[0].y_raw,
            p2_jump_independent=jumped.players[1].y_raw == settled.players[1].y_raw,
            mailbox_unused=not any(row["mailbox"] for row in self.report["observations"]))
        if not all(self.report["checks"].values()):
            raise debug.DebugError("Accepted two-seat native baseline checks failed")


def require_windows():
    if os.name != "nt":
        raise ValueError("This runner requires Windows listener/PID ownership checks")


def control_for(process, port, client, transcript):
    def control(command, **fields):
        if process.poll() is not None or not baseline.owns_listener(port, process.pid):
            raise debug.DebugError("Owned runtime does not own this debug listener")
        row = dict(command=command, fields=fields)
        try:
            row["response"] = client.request(command, **fields)
            return row["response"]
        except Exception as error:
            row["error"] = str(error)
            raise
        finally:
            transcript.write(json.dumps(row, separators=(",", ":")) + "\n"); transcript.flush()
    return control


def reserve(port):
    with socket.socket() as reservation: reservation.bind(("127.0.0.1", port))


def native_capture_started(candidate):
    """Only gate agent input on a visible complete first N; never admit a prefix.

    The buffered worker may publish later than the native call. Waiting is
    safe; injecting during BIOS before any N could change unrecorded serial
    branches. Final admission still requires the complete canonical trace.
    """
    paths = list(candidate.glob("saves/**/input-recordings/session-*/inputs.jsonl"))
    if not paths: return False
    if len(paths) != 1: raise ValueError("Multiple capture streams appeared during cold boot")
    with paths[0].open("rb") as source:
        rows = []
        for _ in range(2):
            raw = source.readline(codec.MAX_LINE+1)
            if not raw.endswith(b"\n"): return False
            if len(raw) > codec.MAX_LINE: raise ValueError("Malformed live native capture line bound")
            row = json.loads(raw)
            if codec.canonical(row) != raw: raise ValueError("Noncanonical live native capture prefix")
            rows.append(row)
    header, first = rows
    if (header.get("type") != "header" or header.get("schema") != 1 or header.get("contract") != codec.CONTRACT or
            first.get("type") != "N" or first.get("native") != 0 or first.get("order") != 0 or
            first.get("caller") not in codec.NATIVE_CALLERS):
        raise ValueError("Recorder did not begin with its mapped original native N")
    return True


def verify_expected_image(executable, expected_sha256):
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Capture requires an explicit exact executable SHA256")
    actual = preparation.sha256(executable)
    if actual != expected_sha256:
        raise ValueError(f"Staged capture executable differs from explicitly expected SHA256: {actual}")
    return actual


def run_capture(candidate, port, timeout, progress_timeout, report, *, expected_exe_sha256):
    require_windows(); reserve(port)
    prepared = json_object(candidate / "preparation.json")
    validated = baseline.candidate_environment(candidate, prepared)
    owned = json_object(candidate / "environment.json")
    if any(validated.get(name) != value for name, value in owned.items()):
        raise ValueError("Candidate environment validation changed")
    environment = sanitized_environment(owned, candidate)
    output = candidate / "native-recording"; output.mkdir()
    args = [str(candidate / "mmx6-runtime.exe"), "--game", str(candidate / "game.toml"),
            "--memcard-dir", str(candidate / "saves"), "--seal-interpreted-overlays", "--hidden-window", "--debug-port", str(port)]
    report.update(args=args, status="failed_setup", expected_exe_sha256=expected_exe_sha256,
                  input_path="per-port virtual host devices through ordinary offline sampler")
    process = None; route = None
    with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr, \
            (output / "control.jsonl").open("w") as transcript:
        try:
            # Candidate receipt validation and embedded manifest presence do not
            # replace the caller's exact image identity. Recheck at launch too.
            report["prelaunch_exe_sha256"] = verify_expected_image(candidate / "mmx6-runtime.exe", expected_exe_sha256)
            process = subprocess.Popen(args, cwd=candidate, env=environment, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report["owned_pid"] = process.pid
            control = control_for(process, port, debug.DebugClient(port), transcript)
            route = HostRoute(control, report, progress_timeout)
            deadline, next_pulse, release_at, step = time.monotonic()+timeout, 0.0, None, 0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise debug.DebugError(f"Capture runtime exited during setup: {process.returncode}")
                if not baseline.owns_listener(port, process.pid):
                    time.sleep(.1); continue
                if not report.get("host_device_preflight"):
                    for seat in (0, 1):
                        verify_host_status(control("pad_status", port=seat+1), seat)
                        route.set(seat, 0)
                    report["host_device_preflight"] = True
                if not report.get("first_native_record_observed"):
                    if not native_capture_started(candidate):
                        time.sleep(.03); continue
                    report["first_native_record_observed"] = True
                mode = route.client.read(0x800CCED0, 2)
                if mode[0] == 10:
                    try:
                        idle = route.sample("native intro setup")
                        if all(player.action == 2 for player in idle.players): break
                    except debug.DebugError:
                        pass  # Native co-op context can be incomplete during boot/cutscenes.
                now = time.monotonic()
                if release_at is not None and now >= release_at:
                    route.set(0, 0); release_at = None
                if now >= next_pulse and release_at is None:
                    route.set(0, 8 if mode[0] != 10 and step % 3 == 0 else 0x4000)
                    step += 1; release_at = now+.15; next_pulse = now+.8
                time.sleep(.03)
            else:
                raise debug.DebugError("Ordinary host-input boot did not reach two idle heroes")
            route.set(0, 0); route.set(1, 0)
            report["status"] = "failed_route"
            route.exercise()
            report["status"] = "route_completed"
        finally:
            if process is not None:
                cleanup = baseline.stop_owned_runtime(process,
                    clear_inputs=() if route is None else (lambda: route.set(0, 0), lambda: route.set(1, 0)),
                    request_quit=lambda: control("quit"))
                report["cleanup"] = cleanup
    if report["status"] != "route_completed" or report["cleanup"] != dict(shutdown="graceful_owned_debug", exit_code=0):
        raise debug.DebugError("Capture did not complete with clean owned quit/drain")


def inspect_recording(candidate, image_sha, manifest_sha):
    recordings = list(candidate.glob("saves/**/input-recordings/session-*/inputs.jsonl"))
    if len(recordings) != 1:
        raise ValueError("Require exactly one finalized native capture under the private save root")
    path = recordings[0]
    if path.stat().st_size > replay_preparation.MAX_BYTES:
        raise ValueError("Native capture exceeds the supported replay prefetch bound")
    with path.open("rb") as stream: summary = codec.validate(stream, max_events=replay_preparation.MAX_EVENTS)
    identity = summary.identity
    if identity["image_sha256"] != image_sha or identity["manifest_sha256"] != manifest_sha or identity["mode"] != "offline":
        raise ValueError("Captured actual image/manifest/mode differs from the required candidate")
    settings = json_object(path.parent / "settings.json")
    implementation = json_object(path.parent / "simulation-contract.json")
    ports = settings.get("input", {}).get("ports", [])
    if settings.get("declared_scope_available") != 1 or len(ports) < 2:
        raise ValueError("Capture lacks complete resolved startup controller scope")
    for seat in (0, 1):
        if any(type(ports[seat].get(key)) is not int or ports[seat][key] != value
               for key, value in dict(seat=seat, device_kind=1, configured_mode=2, connected=1, type=0).items()):
            raise ValueError("Captured startup topology was not two connected digital keyboards")
    if implementation.get("interpreted_overlays_sealed") != 1 or implementation.get("oracle") != 0:
        raise ValueError("Capture lacks actual sealed ordinary implementation")
    saw_p1 = saw_p2 = False; repeated_frames = 0; previous_frame = None
    with path.open("rb") as stream:
        for raw in stream:
            row = json.loads(raw)
            if row.get("type") == "N":
                saw_p1 = saw_p1 or bool(row["pads"][0][0] & 0x40)  # Native byte-swapped Cross.
                repeated_frames += row["frame"] == previous_frame; previous_frame = row["frame"]
            if row.get("type") == "C": saw_p2 = saw_p2 or bool(row["buttons"] & 0x20)
    if not saw_p1 or not saw_p2:
        raise ValueError("Trace did not retain both actual native P1 and extra P2 route inputs")
    return path.parent, dict(identity=identity, events=summary.events, natives=summary.natives,
                             p2_reads=summary.p2_reads, repeated_native_frames=repeated_frames,
                             actual_p1_cross_word_anywhere=saw_p1, actual_p2_right_read=saw_p2,
                             trace_sha256=preparation.sha256(path))


def verify_replay_result(profile, status, expected):
    required = {"schema", "epoch", "contract", "trace_sha256", "events", "consumed", "status", "failure", "scope"}
    if (set(status) != required or type(status["schema"]) is not int or status["schema"] != 1 or
            type(status["epoch"]) is not int or not 0 < status["epoch"] <= 0xFFFFFFFFFFFFFFFF or
            status["contract"] != codec.CONTRACT or status["trace_sha256"] != expected["trace_sha256"] or
            type(status["events"]) is not int or status["events"] != expected["events"] or
            type(status["consumed"]) is not int or status["consumed"] != expected["events"] or
            status["status"] != "consumed" or status["failure"] != "" or
            status["scope"] != "ordered native/P2 consumption only; no full SIO or outcome qualification"):
        raise ValueError("Replay did not commit an exact complete consumed result")
    if preparation.sha256(profile / "replay/inputs.jsonl") != expected["trace_sha256"]:
        raise ValueError("Prepared replay trace changed during execution")


def run_replay(profile, receipt, port, timeout, expected, report):
    require_windows(); reserve(port)
    if (profile / "replay-result.json").exists():
        raise ValueError("Replay result already exists; prepare a fresh private profile")
    if (receipt["executable"] != str(profile / "mmx6-runtime.exe") or
            receipt["arguments"] != ["--game", str(profile / "game.toml"), "--memcard-dir", str(profile / "saves"),
                                     "--seal-interpreted-overlays", "--no-launcher"]):
        raise ValueError("Prepared replay command changed")
    if preparation.sha256(profile / "mmx6-runtime.exe") != receipt["image_sha256"]:
        raise ValueError("Prepared replay executable changed")
    environment = replay_environment(profile, receipt)
    output = profile / "native-replay"; output.mkdir()
    args = [receipt["executable"], *receipt["arguments"], "--hidden-window", "--debug-port", str(port)]
    report.update(args=args, status="running")
    process = None
    with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr, \
            (output / "control.jsonl").open("w") as transcript:
        try:
            process = subprocess.Popen(args, cwd=profile, env=environment, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report["owned_pid"] = process.pid
            control = control_for(process, port, debug.DebugClient(port), transcript)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                result = profile / "replay-result.json"
                if result.is_file():
                    try: status = json_object(result)
                    except (ValueError, OSError): status = None  # Worker may still be committing the result.
                    if status and status.get("status") == "failed":
                        report["runtime_result"] = status
                        raise debug.DebugError("Native replay reported failure")
                if time.monotonic() >= deadline:
                    raise debug.DebugError("Owned native replay exceeded its process deadline")
                time.sleep(.05)
            report["exit_code"] = process.poll()
            if report["exit_code"] != 0:
                raise debug.DebugError("Owned native replay exited without successful EOF consumption")
            status = json_object(profile / "replay-result.json")
            verify_replay_result(profile, status, expected)
            report.update(status="consumed", runtime_result=status)
        finally:
            if process is not None:
                report["cleanup"] = baseline.stop_owned_runtime(process, clear_inputs=(), request_quit=lambda: control("quit"))


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "source", "disc", "output"): result.add_argument("--"+name, required=True, type=Path)
    result.add_argument("--expected-exe-sha256", required=True)
    result.add_argument("--expected-manifest-sha256", required=True)
    result.add_argument("--record-port", type=int, default=24920)
    result.add_argument("--replay-port", type=int, default=24921)
    result.add_argument("--boot-timeout", type=float, default=240)
    result.add_argument("--replay-timeout", type=float, default=240)
    result.add_argument("--progress-timeout", type=float, default=12)
    return result


def options(p, args):
    for name in ("expected_exe_sha256", "expected_manifest_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", getattr(args, name)): p.error("Expected exact lowercase SHA256 identities")
    if (not 1 <= args.record_port <= 65535 or not 1 <= args.replay_port <= 65535 or args.record_port == args.replay_port):
        p.error("Require two distinct debug ports in 1..65535")
    for name, bound in (("boot_timeout", 600), ("replay_timeout", 600), ("progress_timeout", 60)):
        value = getattr(args, name)
        if not math.isfinite(value) or not 0 < value <= bound: p.error("Require finite bounded timeouts")


def run(args):
    require_windows()
    output = preparation.local_output(args.output)
    if output.exists(): raise ValueError("Output exists; retain prior evidence and select a fresh profile")
    output.mkdir(parents=True)
    modules = (debug, manifests, codec, preparation, replay_preparation, baseline)
    report = dict(schema=1, kind="owned_offline_native_capture_replay", status="failed_setup", r26="unverified",
                  native_outcome_comparison="not_performed", whole_machine_replay="unverified", checks={},
                  tools={Path(module.__file__).name: preparation.sha256(Path(module.__file__)) for module in modules},
                  runner_sha256=preparation.sha256(Path(__file__)), record={}, replay={},
                  limits=["Same physical host and exact image only; no physical-controller qualification",
                          "No live RAM/output comparison or EOF end-state claim", "No raw SIO/publication replay",
                          "EOF next-consumption fence has no proven hard native/wall bound; runner supplies an external timeout"])
    (output / "runner-source.py").write_bytes(Path(__file__).read_bytes())
    try:
        if preparation.sha256(args.build / "mmx6-runtime.exe") != args.expected_exe_sha256:
            raise ValueError("Build executable differs from explicitly expected SHA256")
        candidate = output / "record"
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
        configure_two_digital_slots(candidate)
        report["staged_exe_sha256"] = verify_expected_image(candidate / "mmx6-runtime.exe", args.expected_exe_sha256)
        manifest = manifests.validate_build_manifest(args.build, [args.build / "mmx6-runtime.exe", candidate / "mmx6-runtime.exe"],
                                                     evidence_directory=output / "manifest")
        if manifest["declared_sha256"] != args.expected_manifest_sha256:
            raise ValueError("Build manifest differs from explicitly expected compiled identity")
        report["build_manifest"] = manifest
        report["checks"]["staged_exact_image_and_declared_manifest"] = True
        run_capture(candidate, args.record_port, args.boot_timeout, args.progress_timeout, report["record"],
                    expected_exe_sha256=args.expected_exe_sha256)
        recording, inspected = inspect_recording(candidate, args.expected_exe_sha256, args.expected_manifest_sha256)
        report["capture"] = dict(directory=str(recording), **inspected)
        profile = output / "replay"
        receipt = replay_preparation.prepare(recording, candidate, profile)
        report["replay_preparation"] = receipt
        report["checks"]["complete_canonical_offline_capture_and_startup_artifacts"] = True
        manifests.validate_build_manifest(args.build, [candidate / "mmx6-runtime.exe", profile / "mmx6-runtime.exe"])
        report["status"] = "failed_replay"
        run_replay(profile, receipt, args.replay_port, args.replay_timeout, inspected, report["replay"])
        report["checks"]["complete_consumed_status_and_owned_exit_zero"] = True
        report["status"] = SUCCESS
    except Exception as error:
        report["error"] = dict(type=type(error).__name__, message=str(error))
        report["traceback"] = traceback.format_exc()
    finally:
        (output / "qualification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    p = parser(); args = p.parse_args(argv); options(p, args)
    try: result = run(args)
    except (ValueError, OSError) as error: p.exit(1, str(error) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == SUCCESS else 1


if __name__ == "__main__": raise SystemExit(main())
