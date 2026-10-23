"""Owned native P1 pause and P2 private-effect case on a fresh exact image.

Exit0 reports automated observations only. Composed artwork review stays
pending and this runner never writes parity or native-content ledger results.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

import coop_debug as debug
import mmx6_coop_private_effects as effects
import mmx6_coop_private_pause as private_pause
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_personal_menu as offline


def make_parser():
    parser = offline.make_parser()
    parser.description = __doc__
    parser.set_defaults(port=24899)
    parser.add_argument("--max-retirement-ticks", type=int, default=32)
    return parser


def validate_options(parser, args):
    offline.validate_options(parser, args)
    if not 2 <= args.max_retirement_ticks <= 120:
        parser.error("Native retirement bound must be in2..120 ticks")


def run(args):
    candidate = preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        os.environ.update(TEMP=str(candidate/"temp"), TMP=str(candidate/"temp"))
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
    prepared = offline.pristine_candidate(candidate, args.expected_exe_sha256)
    os.environ.update(TEMP=str(candidate/"temp"), TMP=str(candidate/"temp"),
                      PYTHONPYCACHEPREFIX=str(candidate/"temp/pycache"))
    sys.pycache_prefix = str(candidate/"temp/pycache")
    modules = (debug, effects, private_pause, preparation, baseline, offline)
    metadata = dict(kind="owned_offline_private_effect_pause_runner", mode="local",
        expected_exe_sha256=args.expected_exe_sha256,
        candidate_exe_sha256=prepared["exe_sha256"], input_path="offline_native",
        runner_sha256=preparation.sha256(Path(__file__)),
        tool_sha256={Path(m.__file__).name:preparation.sha256(Path(m.__file__)) for m in modules},
        artwork_review="pending", ledger_status="unverified",
        limits=["Original-input case in a fresh private offline intro; no campaign/R9 pass",
                "No guest RAM, fixture, mailbox, success-flag or source-card writes",
                "Independent native effect data and composed artwork review required",
                "Direct offline debug pad input contaminates strict ordinary-input capture",
                "Preparation source observations are not compilation provenance"])
    (candidate/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    for name, module in (("effects-helper-source.py",effects),("private-pause-helper-source.py",private_pause)):
        (candidate/name).write_bytes(Path(module.__file__).read_bytes())
    (candidate/"runner-metadata.json").write_bytes((json.dumps(metadata,indent=2)+"\n").encode("utf-8"))

    def exercise(control, client, destination, report):
        report.update(checks={"private_effect_pause_automated_case_completed":False}, artwork_review="pending")
        adapter = offline.OfflineMenuAdapter(control, report, timeout=args.progress_timeout)
        owned_debug = SimpleNamespace(observe=debug.observe,
            capture_present=lambda owned,path:debug.capture_present(owned,path,request=control))
        try:
            adapter.settle_idle()
            case = private_pause.private_pause_smoke(dict(mode="local", input_path="offline_native",
                clients=[adapter.client], both=lambda fn:[fn(0)], debug=owned_debug,
                report=report, output=destination, hold=adapter.hold,
                hold_observed=adapter.hold_observed, effects=effects,
                native_advance=adapter.native_advance, transport_window=adapter.transport_window,
                candidate_exe_sha256=prepared["exe_sha256"]),
                expected_exe_sha256=args.expected_exe_sha256,
                window_frames=args.window_frames, timeout=args.progress_timeout,
                max_retirement_ticks=args.max_retirement_ticks)
            report["checks"]["private_effect_pause_automated_case_completed"] = (
                bool(case.get("checks")) and all(case["checks"].values()) and
                case.get("artwork_review") == "pending" and
                case.get("status") == "automated_private_pause_checks_passed_artwork_pending")
        except Exception as error:
            report.update(error=str(error), error_type=type(error).__name__, traceback=traceback.format_exc())
            raise debug.DebugError(f"Native private-effect pause case failed: {error}") from error

    result = baseline.run(candidate, args.port, args.timeout, False, exercise=exercise)
    original = candidate/"baseline/qualification.json"
    result.update(kind=metadata["kind"], runner=metadata, artwork_review="pending", ledger_status="unverified",
        original_baseline=dict(path=str(original),sha256=preparation.sha256(original),status=result["status"]))
    result["automated_case_completed"] = (result["status"] == "passed" and
        result.get("exercise",{}).get("checks",{}).get("private_effect_pause_automated_case_completed") is True)
    if result["automated_case_completed"]:
        result["status"] = "automated_private_effect_pause_checks_passed_artwork_pending"
    (candidate/"qualification.json").write_bytes((json.dumps(result,indent=2)+"\n").encode("utf-8"))
    return result


def main(argv=None):
    parser=make_parser();args=parser.parse_args(argv);validate_options(parser,args)
    try:
        result=run(args)
    except (OSError,ValueError,debug.DebugError) as error:
        parser.exit(1,f"Private-effect pause qualification failed: {error}\n")
    print(json.dumps(dict(status=result["status"],ledger_status="unverified",
        report=str((args.candidate or args.output)/"qualification.json"))))
    return 0 if result["automated_case_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
