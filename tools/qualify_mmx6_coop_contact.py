"""Own one offline native R2 contact/menu/contact trial; artwork stays pending.

Reuse the existing baseline lifecycle and OfflineMenuAdapter. Require a fresh
private profile, the exact frozen executable and an original raw BIN for the
immutable Zero hurtbox resolver. No source cards, fixtures or ledger updates.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

import coop_debug as debug
import inventory_mmx6_coop_content as inventory
import mmx6_coop_contact as contact
import mmx6_coop_personal_menu as menu
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_personal_menu as menu_runner


SUCCESS = "automated_contact_checks_passed_artwork_review_pending"


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    staging = parser.add_mutually_exclusive_group(required=True)
    staging.add_argument("--build", type=Path)
    staging.add_argument("--candidate", type=Path, help="One prepared, unused automated private profile")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--disc", type=Path, help="Disc/CUE for a newly staged runtime profile")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--original-disc", type=Path, required=True,
                        help="Original raw2352-byte-sector BIN for the source-qualified Zero overlay")
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--port", type=int, default=24897)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--progress-timeout", type=float, default=12)
    # Shared validation bounds this compatibility value; contact's owned menu
    # retains its source-derived default12-frame windows and Down/Up cursor.
    parser.set_defaults(window_frames=12)
    return parser


def validate_options(parser, args):
    menu_runner.validate_options(parser, args)
    if args.expected_exe_sha256 != contact.EXE_SHA:
        parser.error("R2 requires the selected frozen37cdc487 executable SHA256")
    if args.original_disc.suffix.lower() != ".bin":
        parser.error("--original-disc requires the original raw BIN, distinct from the runtime CUE argument")


def run(args):
    # Resolve/verify the bounded original members before staging or launching.
    original_disc = args.original_disc.resolve(strict=True)
    zero_overlay = contact.load_zero_overlay(original_disc)
    candidate = preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        os.environ.update(TEMP=str(candidate / "temp"), TMP=str(candidate / "temp"))
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
    prepared = menu_runner.pristine_candidate(candidate, args.expected_exe_sha256)
    if prepared["exe_sha256"] != contact.EXE_SHA:
        raise ValueError("R2 prepared executable is not the selected frozen candidate")
    os.environ.update(TEMP=str(candidate / "temp"), TMP=str(candidate / "temp"),
                      PYTHONPYCACHEPREFIX=str(candidate / "temp/pycache"))
    sys.pycache_prefix = str(candidate / "temp/pycache")
    modules = (debug, inventory, contact, menu, preparation, baseline, menu_runner, contact.enemy)
    metadata = dict(kind="owned_offline_contact_pause_contact", mode="local",
        expected_exe_sha256=args.expected_exe_sha256, candidate_exe_sha256=prepared["exe_sha256"],
        runner_sha256=preparation.sha256(Path(__file__)),
        tool_sha256={Path(module.__file__).name: preparation.sha256(Path(module.__file__)) for module in modules},
        original_disc=str(original_disc), original_source=dict(exe_sha256=inventory.EXE_SHA256,
            archive_sha256=inventory.BIN_SHA256, zero_overlay_sha256=contact.ZERO_SHA,
            scope="Verified bounded EXE/archive/Zero members, not a whole-raw-disc hash"),
        artwork_review="pending", ledger_status="unverified", input_path="offline_native",
        limits=["Source-derived R2 route; accepted native contact and retreat require the actual retained trial",
                "Original baseline receipt/status remains separate and unchanged",
                "Staging source observations are not compilation provenance",
                "No guest RAM/fixture/mailbox/success-flag/source-card writes",
                "Automated completion does not approve artwork or pass R2"])
    for name, source in (("runner-source.py", Path(__file__)),
                         ("contact-helper-source.py", Path(contact.__file__)),
                         ("menu-helper-source.py", Path(menu.__file__))):
        (candidate / name).write_bytes(source.read_bytes())
    (candidate / "runner-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    def exercise(control, client, destination, report):
        report.update(checks={"contact_pause_contact_automated_case_completed": False}, artwork_review="pending")
        adapter = menu_runner.OfflineMenuAdapter(control, report, timeout=args.progress_timeout)
        owned_debug = SimpleNamespace(observe=debug.observe,
            capture_present=lambda owned, path: debug.capture_present(owned, path, request=control))

        def rpc(peer, command, **fields):
            if peer != 0:
                raise ValueError("Offline R2 adapter owns only peer0")
            return control(command, **fields)

        try:
            adapter.settle_idle()
            case = contact.contact_pause_contact(dict(mode="local", input_path="offline_native",
                clients=[adapter.client], both=lambda fn: [fn(0)], debug=owned_debug,
                report=report, output=destination, hold=adapter.hold,
                native_advance=adapter.native_advance, transport_window=adapter.transport_window,
                candidate_exe_sha256=prepared["exe_sha256"], zero_overlay=zero_overlay, rpc=rpc),
                expected_exe_sha256=args.expected_exe_sha256)
            report["checks"].update(case["checks"])
            report["checks"]["contact_pause_contact_automated_case_completed"] = case["status"] == SUCCESS
        except Exception as error:
            report.update(error=str(error), error_type=type(error).__name__, traceback=traceback.format_exc())
            # Shared menu errors derive RuntimeError; baseline handles DebugError.
            # Keep the already attached partial contact/menu cases and original
            # error while letting its existing owned cleanup/report path finish.
            raise debug.DebugError(f"Native R2 contact/menu/contact case failed: {error}") from error

    result = baseline.run(candidate, args.port, args.timeout, False, exercise=exercise)
    original_path = candidate / "baseline/qualification.json"
    original_status = result["status"]
    result.update(kind=metadata["kind"], runner=metadata,
        original_baseline=dict(path=str(original_path), sha256=preparation.sha256(original_path), status=original_status),
        artwork_review="pending", ledger_status="unverified")
    result["automated_checks_passed"] = (original_status == "passed" and
        result.get("exercise", {}).get("checks", {}).get("contact_pause_contact_automated_case_completed") is True)
    if result["automated_checks_passed"]:
        result["status"] = SUCCESS
    (candidate / "qualification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    validate_options(parser, args)
    try:
        result = run(args)
    except (OSError, ValueError, debug.DebugError) as error:
        parser.exit(1, f"R2 runner setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"], error=result.get("error"),
        artwork_review=result["artwork_review"], ledger_status=result["ledger_status"],
        report=str((args.candidate or args.output) / "qualification.json"))))
    return 0 if result["automated_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
