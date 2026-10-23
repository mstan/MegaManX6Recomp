"""Owned PRIVATE OFFLINE native checkpoint setup; no retry/progression pass.

Uses the baseline lifecycle and original-input adapter on a fresh private
profile. Command8 is an explicit stage/checkpoint prerequisite bypass. It
taints ordinary-input proof and never grants HP, success flags or source cards.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

import coop_debug as debug
import mmx6_coop_checkpoint as checkpoint
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_personal_menu as offline


def number(value):
    return int(value, 0)


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    staging = parser.add_mutually_exclusive_group(required=True)
    staging.add_argument("--build", type=Path)
    staging.add_argument("--candidate", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--disc", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--original", type=Path, required=True,
                        help="Pinned original SLUS_013.95 EXE or original raw BIN, read only")
    parser.add_argument("--inventory", type=Path, default=Path(__file__).resolve().parents[1]/"docs/COOP_X6_CONTENT.json")
    parser.add_argument("--stage", type=number, required=True)
    parser.add_argument("--section", type=number, required=True)
    parser.add_argument("--checkpoint", type=number, required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--port", type=int, default=24898)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--entry-timeout", type=float, default=90)
    parser.add_argument("--progress-timeout", type=float, default=12)
    parser.set_defaults(window_frames=12)
    return parser


def validate_options(parser, args):
    offline.validate_options(parser, args)
    if not math.isfinite(args.entry_timeout) or not 0 < args.entry_timeout <= 180:
        parser.error("Native entry timeout must be in (0,180]")
    if any(not 0 <= value <= 255 for value in (args.stage, args.section, args.checkpoint)):
        parser.error("Stage, section and checkpoint selectors must fit unsigned bytes")


def run(args):
    # Full original EXE plus immutable115 inventory identity before staging.
    original = checkpoint.original_executable(args.original.resolve(strict=True))
    _, rows, sections = checkpoint.verified_inventory(args.inventory, original)
    target = checkpoint.select(rows, sections, args.stage, args.section, args.checkpoint)
    candidate = preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        os.environ.update(TEMP=str(candidate/"temp"), TMP=str(candidate/"temp"))
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
    prepared = offline.pristine_candidate(candidate, args.expected_exe_sha256)
    os.environ.update(TEMP=str(candidate/"temp"), TMP=str(candidate/"temp"),
                      PYTHONPYCACHEPREFIX=str(candidate/"temp/pycache"))
    sys.pycache_prefix = str(candidate/"temp/pycache")
    modules = (checkpoint, checkpoint.content, debug, offline, baseline, preparation)
    metadata = dict(kind="owned_private_offline_checkpoint_entry", target=target,
        original_source=str(args.original.resolve()), source_exe_sha256=checkpoint.content.EXE_SHA256,
        inventory_sha256=checkpoint.INVENTORY_SHA256,
        expected_exe_sha256=args.expected_exe_sha256, candidate_exe_sha256=prepared["exe_sha256"],
        prerequisite_bypass=True, ordinary_input_evidence_tainted=True,
        ledger_status="unverified", artwork_review="pending",
        tool_sha256={Path(m.__file__).name:preparation.sha256(Path(m.__file__)) for m in modules},
        limits=["Stage/checkpoint prerequisite bypass; no native retry, reachability, progression or mechanic pass",
                "Only94 authored campaign tuples permitted;21 remaining namespaces remain unsupported setup",
                "One hidden muted private process; all lifecycle and control RPCs retain PID/listener guards",
                "Original EXE SHA verified; resident code/data FNV guards are mismatch checks, not cryptographic identity",
                "No HP, success/unlock/rescue/clear flags, manual overlay/table writes or source cards",
                "Staging source observation is not compilation provenance; artwork remains pending"])
    (candidate/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    (candidate/"checkpoint-helper-source.py").write_bytes(Path(checkpoint.__file__).read_bytes())
    (candidate/"runner-metadata.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")

    def exercise(control, client, destination, report):
        report.update(checks={"private_checkpoint_entry_setup_completed":False})
        adapter = offline.OfflineMenuAdapter(control, report, timeout=args.progress_timeout)
        case = report.setdefault("checkpoint_entry", {})
        try:
            adapter.settle_idle()
            nonce = (time.monotonic_ns() & 0xFFFFFFFF) or 1
            checkpoint.enter_checkpoint(control, adapter.client, target, case,
                                        timeout=args.entry_timeout, nonce=nonce)
            case["capture"] = debug.capture_present(adapter.client, destination/"checkpoint-present.png", request=control)
            report["checks"]["private_checkpoint_entry_setup_completed"] = True
        except Exception as error:
            case.update(error=str(error), error_type=type(error).__name__, traceback=traceback.format_exc())
            raise debug.DebugError(f"Private checkpoint entry setup failed: {error}") from error

    result = baseline.run(candidate, args.port, args.timeout, False, exercise=exercise)
    baseline_path = candidate/"baseline/qualification.json"
    result.update(kind=metadata["kind"], runner=metadata, prerequisite_bypass=True,
        ordinary_input_evidence_tainted=True, ledger_status="unverified", artwork_review="pending",
        original_baseline=dict(path=str(baseline_path), sha256=preparation.sha256(baseline_path), status=result["status"]))
    result["automated_setup_completed"] = result["status"] == "passed" and \
        result.get("exercise", {}).get("checks", {}).get("private_checkpoint_entry_setup_completed") is True
    if result["automated_setup_completed"]:
        result["status"] = "prerequisite_bypass_setup_completed_artwork_pending"
    (candidate/"qualification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    validate_options(parser, args)
    try:
        result = run(args)
    except (OSError, ValueError, debug.DebugError) as error:
        parser.exit(1, f"Private checkpoint setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"], prerequisite_bypass=True,
        ledger_status="unverified", report=str((args.candidate or args.output)/"qualification.json"))))
    return 0 if result["automated_setup_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
