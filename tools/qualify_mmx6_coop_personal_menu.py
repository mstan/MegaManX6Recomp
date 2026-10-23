"""Owned offline native Zero-menu case on a fresh, exact-SHA private candidate.

Stages or reuses one pristine F:/G: profile, then delegates process lifecycle to
the baseline runner. No source cards, guest writes, fixtures or ledger updates.
Exit0 means automated checks completed; composed artwork review stays pending.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import traceback
from types import SimpleNamespace

import coop_debug as debug
import mmx6_coop_personal_menu as menu
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline


DIRECTIONS = dict(up=0x10, right=0x20, down=0x40, left=0x80)
FRESH_PATHS = ("baseline", "qualification.json", "runner-source.py", "menu-helper-source.py",
               "runner-metadata.json", "qualifier-source.py")
PRIVATE_EMPTY_DIRS = ("saves", "temp", "cache", "data", "appdata", "resident")
SUCCESS = "automated_checks_passed_artwork_review_pending"


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    staging = parser.add_mutually_exclusive_group(required=True)
    staging.add_argument("--build", type=Path)
    staging.add_argument("--candidate", type=Path, help="Use one fresh prepared private profile without restaging")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--disc", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--port", type=int, default=24896)
    parser.add_argument("--timeout", type=float, default=240, help="Native boot deadline in seconds")
    parser.add_argument("--progress-timeout", type=float, default=12, help="Deadline for each bounded native/publication window")
    parser.add_argument("--window-frames", type=int, default=12)
    parser.add_argument("--cursor-change", choices=DIRECTIONS, default="right")
    parser.add_argument("--cursor-restore", choices=DIRECTIONS, default="left")
    return parser


def validate_options(parser: argparse.ArgumentParser, args) -> None:
    if args.build and not all((args.source, args.disc, args.output)):
        parser.error("--build requires --source, --disc and --output")
    if args.candidate and any((args.source, args.disc, args.output)):
        parser.error("--candidate uses its existing preparation; omit staging arguments")
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_exe_sha256):
        parser.error("Expected executable SHA256 must contain 64 lowercase hex digits")
    if not 1 <= args.port <= 65535:
        parser.error("Debug port must be in 1..65535")
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 600:
        parser.error("Native boot timeout must be in (0,600]")
    if not math.isfinite(args.progress_timeout) or not 0 < args.progress_timeout <= 60:
        parser.error("Progress timeout must be in (0,60]")
    if not 6 <= args.window_frames <= 120:
        parser.error("Menu windows must be in 6..120 frames")


def pristine_candidate(candidate: Path, expected_sha: str) -> dict:
    candidate = preparation.local_output(candidate).resolve(strict=True)
    if not candidate.is_dir() or any((candidate / name).exists() for name in FRESH_PATHS):
        raise ValueError("Prepared candidate must be fresh; retain previous qualification evidence")
    prepared = json.loads((candidate / "preparation.json").read_text(encoding="utf-8"))
    if prepared.get("automated_profile") is not True or prepared.get("source_card") is not None or \
            prepared.get("source_card_sha256") is not None:
        raise ValueError("Menu candidate needs an automated private profile without source cards")
    for name in PRIVATE_EMPTY_DIRS:
        path = (candidate / name).resolve(strict=True)
        if not path.is_relative_to(candidate) or not path.is_dir() or next(path.iterdir(), None) is not None:
            raise ValueError(f"Prepared private {name} must be empty and remain inside the candidate")
    actual = preparation.sha256(candidate / "mmx6-runtime.exe")
    if actual != expected_sha or prepared.get("exe_sha256") != actual:
        raise ValueError("Menu candidate does not match the explicitly expected executable SHA256")
    # Validate hashes, source observations and every child process path before
    # baseline.run opens logs or starts the owned process.
    baseline.candidate_environment(candidate, prepared)
    return prepared


class OwnedReadClient:
    """Read/capture-only view; every RPC retains baseline's listener PID check."""
    allowed = frozenset(("read_ram", "present_shot", "present_shot_seq"))

    def __init__(self, control):
        self.control = control

    def request(self, command, **fields):
        if command not in self.allowed:
            raise debug.DebugError("Menu observer cannot send input, memory writes or fixture commands")
        return self.control(command, **fields)

    def read(self, address, size):
        # Reuse the shared length/hex decoder instead of trusting RPC payloads.
        return debug.DebugClient.read(self, address, size)


class OfflineMenuAdapter:
    def __init__(self, control, report: dict, *, timeout: float = 12):
        self.control = control
        self.client = OwnedReadClient(control)
        self.report = report
        self.timeout = timeout
        report.update(adapter_observations=[], adapter_windows=[], input_cleanup_errors=[])

    def sample(self, label):
        row = debug.observe(self.client)
        self.report["adapter_observations"].append(dict(label=label, **row.json()))
        if (row.ready != 1 or row.enrolled != 1 or row.failed != 0 or
                row.mailbox or row.scene_owner or row.native_mode != 10 or
                row.lifecycle != (0, 0)):
            raise debug.DebugError("Personal-menu adapter left healthy native co-op gameplay/menu")
        return row

    def wait_counter(self, field, frames, label):
        if field not in ("tick", "native_timer") or not 1 <= frames <= 600:
            raise ValueError("Expected a bounded native/publication progress window")
        start = self.sample(label + " start")
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            row = self.sample(label)
            delta = (getattr(row, field) - getattr(start, field)) & 0xFFFFFFFF
            if delta >= 0x80000000:
                raise debug.DebugError(f"{label}: native/publication counter moved backwards")
            if delta >= frames:
                self.report["adapter_windows"].append(dict(label=label, counter=field,
                    requested_frames=frames, start=start.json(), end=row.json()))
                return row
            time.sleep(.015)
        raise debug.DebugError(f"{label}: {field} did not advance through the bounded window")

    def transport_window(self, frames):
        # The native world clock is intentionally frozen in the menu. Only
        # coherent diagnostic publications pace offline input/release here.
        return self.wait_counter("tick", frames, "Offline menu scheduler publications")

    def native_advance(self, frames, label):
        return self.wait_counter("native_timer", frames, label)

    def hold_observed(self, seat, bits, frames, label, observe):
        """Sample during accepted input; always release before returning/error.

        The observer reads/captures and may use the owning adapter to hold the
        other seat. Endpoint-only samples can miss transient actor advancement.
        """
        if (seat not in (0, 1) or not 0 <= bits <= 0xFFFF or
                not 6 <= frames <= 120 or not callable(observe)):
            raise ValueError("Expected a native seat/mask, 6..120 publications and observer")
        error, samples = None, []
        start = self.sample(label + " start")
        try:
            self.control("press", port=seat + 1, buttons=0xFFFF ^ bits, frames=0)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                row = self.sample(label)
                delta = (row.tick - start.tick) & 0xFFFFFFFF
                if delta >= 0x80000000:
                    raise debug.DebugError(f"{label}: publication counter moved backwards")
                samples.append(observe())
                if delta >= frames + 2 and len(samples) >= 3:
                    self.report["adapter_windows"].append(dict(label=label, counter="tick",
                        requested_frames=frames, start=start.json(), end=row.json(),
                        held_observations=len(samples)))
                    break
                time.sleep(.015)
            else:
                raise debug.DebugError(f"{label}: held input publication window timed out")
        except BaseException as caught:
            error = caught
            raise
        finally:
            try:
                self.control("clear_input", port=seat + 1)
            except Exception as cleanup_error:
                self.report["input_cleanup_errors"].append(dict(label=label, seat=seat,
                    error=str(cleanup_error), original_error=str(error) if error else None))
                if error is None:
                    raise
        self.transport_window(3)
        return samples

    def hold(self, seat, bits, frames, label):
        if seat not in (0, 1) or not 0 <= bits <= 0xFFFF or not 1 <= frames <= 120:
            raise ValueError("Expected native seat0/1, pressed mask and bounded frame count")
        error = None
        try:
            # SDK792 expires this counter on each override GET, including
            # low-latency resamples, rather than once per guest frame. Hold
            # until the bounded publication window completes, then clear in
            # finally; a short read-count pulse is not a native-frame hold.
            self.control("press", port=seat + 1, buttons=0xFFFF ^ bits, frames=0)
            self.wait_counter("tick", frames + 2, label)
        except BaseException as caught:
            error = caught
            raise
        finally:
            try:
                self.control("clear_input", port=seat + 1)
            except Exception as cleanup_error:
                self.report["input_cleanup_errors"].append(dict(label=label, seat=seat,
                    error=str(cleanup_error), original_error=str(error) if error else None))
                if error is None:
                    raise
        self.transport_window(3)

    def settle_idle(self):
        self.control("clear_input", port=1)
        self.control("clear_input", port=2)
        deadline, previous = time.monotonic() + self.timeout, None
        while time.monotonic() < deadline:
            row = self.sample("Settle reused baseline jump to native idle")
            idle = row.native_phase == 0 and row.pause_owner == 0 and all(
                player.active and player.state == 1 and player.action == 2 and player.hp == 32
                for player in row.players)
            if idle and previous is not None:
                old = previous
                delta = (row.tick - old.tick) & 0xFFFFFFFF
                if 2 <= delta < 0x80000000 and all(
                        (a.x_raw, a.y_raw) == (b.x_raw, b.y_raw) for a, b in zip(old.players, row.players)):
                    self.report["settled_idle"] = row.json()
                    return row
            previous = row if idle else None
            self.transport_window(2)
        raise debug.DebugError("Reused baseline jump did not settle to two stable native idle heroes")


def run(args) -> dict:
    candidate = preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        # All helper subprocesses inherit private non-C temp/cache paths too.
        # prepare creates these before its source-observation Git commands.
        os.environ.update(TEMP=str(candidate / "temp"), TMP=str(candidate / "temp"))
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
    prepared = pristine_candidate(candidate, args.expected_exe_sha256)
    os.environ.update(TEMP=str(candidate / "temp"), TMP=str(candidate / "temp"),
                      PYTHONPYCACHEPREFIX=str(candidate / "temp/pycache"))
    sys.pycache_prefix = str(candidate / "temp/pycache")
    modules = (debug, menu, preparation, baseline)
    metadata = dict(kind="owned_offline_personal_menu_runner", mode="local", owner=1,
        expected_exe_sha256=args.expected_exe_sha256, candidate_exe_sha256=prepared["exe_sha256"],
        runner_sha256=preparation.sha256(Path(__file__)),
        tool_sha256={Path(module.__file__).name: preparation.sha256(Path(module.__file__)) for module in modules},
        input_path="offline_native", artwork_review="pending", ledger_status="unverified",
        source_build_binding="Staging observations are not compilation provenance",
        limits=["One original native Zero menu in a private offline intro; no netplay or full R8 pass",
                "No guest RAM, fixtures, mailbox, success-flag or source-card writes",
                "Completed automated checks still require composed artwork review",
                "Original baseline receipt is retained without rewriting its status"])
    (candidate / "runner-source.py").write_bytes(Path(__file__).read_bytes())
    (candidate / "menu-helper-source.py").write_bytes(Path(menu.__file__).read_bytes())
    (candidate / "runner-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    def exercise(control, client, destination, report):
        report.update(checks={"personal_menu_automated_case_completed": False}, artwork_review="pending")
        adapter = OfflineMenuAdapter(control, report, timeout=args.progress_timeout)
        # The module checks for existing capture files. The shared completed-
        # present protocol also requires its parent to exist before the RPC.
        (destination / "personal-menu").mkdir()
        owned_debug = SimpleNamespace(observe=debug.observe,
            capture_present=lambda owned, path: debug.capture_present(owned, path, request=control))
        try:
            adapter.settle_idle()
            case = menu.personal_menu_smoke(dict(mode="local", input_path="offline_native",
                clients=[adapter.client], both=lambda fn: [fn(0)], debug=owned_debug,
                report=report, output=destination, hold=adapter.hold,
                native_advance=adapter.native_advance, transport_window=adapter.transport_window),
                cursor_buttons=(DIRECTIONS[args.cursor_change], DIRECTIONS[args.cursor_restore]),
                window_frames=args.window_frames, timeout=args.progress_timeout)
            report["checks"].update(case["checks"])
            report["checks"]["personal_menu_automated_case_completed"] = case["status"] == SUCCESS
        except Exception as error:
            report.update(error=str(error), error_type=type(error).__name__, traceback=traceback.format_exc())
            # baseline catches DebugError and preserves its failed result plus
            # this partial case. MenuQualificationError is otherwise RuntimeError.
            raise debug.DebugError(f"Native personal-menu case failed: {error}") from error

    result = baseline.run(candidate, args.port, args.timeout, False, exercise=exercise)
    original_path = candidate / "baseline/qualification.json"
    original_status = result["status"]
    result.update(kind=metadata["kind"], runner=metadata,
                  original_baseline=dict(path=str(original_path), sha256=preparation.sha256(original_path),
                                         status=original_status),
                  artwork_review="pending", ledger_status="unverified")
    result["automated_checks_passed"] = (original_status == "passed" and
        result.get("exercise", {}).get("checks", {}).get("personal_menu_automated_case_completed") is True)
    if result["automated_checks_passed"]:
        result["status"] = SUCCESS
    (candidate / "qualification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    validate_options(parser, args)
    try:
        result = run(args)
    except (OSError, ValueError, debug.DebugError) as error:
        parser.exit(1, f"Personal-menu runner setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"], error=result.get("error"),
        artwork_review=result["artwork_review"], ledger_status=result["ledger_status"],
        report=str((args.candidate or args.output) / "qualification.json"))))
    return 0 if result["automated_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
