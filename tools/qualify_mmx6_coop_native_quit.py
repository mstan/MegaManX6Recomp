"""Own one fresh offline native Quit probe; no final Quit or current-data flow.

Reuse baseline lifecycle and OfflineMenuAdapter. All paths/cards are private,
input is original native pad input, and artwork/ledger status remains pending.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tomllib
import traceback
from types import SimpleNamespace

import coop_debug as debug
import mmx6_coop_native_quit as native_quit
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_personal_menu as menu_runner


def make_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    staging=parser.add_mutually_exclusive_group(required=True)
    staging.add_argument("--build",type=Path)
    staging.add_argument("--candidate",type=Path,help="Fresh prepared automated profile, never previously launched")
    parser.add_argument("--source",type=Path)
    parser.add_argument("--disc",type=Path,help="Runtime original disc/CUE for new staging")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--original-exe",type=Path,required=True,help="Exact original SLUS_013.95, separate from runtime CUE")
    parser.add_argument("--expected-exe-sha256",required=True)
    parser.add_argument("--native-quit-scenario",choices=("guest_authority","p1_pages_cancel"),required=True)
    parser.add_argument("--port",type=int,default=24898)
    parser.add_argument("--timeout",type=float,default=240)
    parser.add_argument("--progress-timeout",type=float,default=12)
    parser.add_argument("--window-frames",type=int,default=12)
    return parser


def validate_options(parser,args):
    menu_runner.validate_options(parser,args)


def require_default_loader(candidate):
    """Keep normal Seamless behavior and forbid a hidden state override."""
    catalog=candidate/"mods/bundled"
    manifests=[]
    for path in catalog.glob("*/*/manifest.toml"):
        item=tomllib.loads(path.read_text(encoding="utf-8-sig"))
        if item.get("id")=="mmx6.enhancement.seamless-loading":manifests.append((path,item))
    if len(manifests)!=1:
        raise ValueError("Native Quit requires one staged default Seamless Loading package")
    path,item=manifests[0]
    features=[f for f in item.get("feature",[]) if f.get("id")=="seamless-loading"]
    if len(features)!=1 or features[0].get("default_enabled") is not True:
        raise ValueError("Native Quit requires Seamless Loading enabled by its normal catalog default")
    selection=tomllib.loads((candidate/"mods/state.toml").read_text(encoding="utf-8-sig"))
    expected=dict(format_version=2,package=[dict(id="mmx6.local-coop",version="0.0.1")],
                  feature=[dict(package_id="mmx6.local-coop",id="prototype",enabled=True)])
    if selection!=expected or selection["feature"][0].get("enabled") is not True:
        raise ValueError("Native Quit requires the fresh default loader/settings without feature overrides")
    return dict(policy="default_seamless_loading",manifest=str(path),manifest_sha256=preparation.sha256(path),
                state_sha256=preparation.sha256(candidate/"mods/state.toml"))


def card_hashes(candidate):
    return {path.name:preparation.sha256(path) for path in sorted((candidate/"saves").glob("*.mcd"))}


def make_exercise(args,candidate,prepared,metadata):
    def exercise(control,_client,destination,report):
        report.update(checks={"native_quit_automated_case_completed":False},artwork_review="pending",ledger_status="unverified")
        adapter=menu_runner.OfflineMenuAdapter(control,report,timeout=args.progress_timeout)
        owned_debug=SimpleNamespace(observe=debug.observe,
            capture_present=lambda client,path:debug.capture_present(client,path,request=control))
        before_cards=card_hashes(candidate)
        report["private_cards_before"]=before_cards
        try:
            adapter.settle_idle()
            case=native_quit.native_quit_smoke(dict(mode="local",input_path="offline_native",
                clients=[adapter.client],both=lambda fn:[fn(0)],debug=owned_debug,report=report,output=destination,
                hold=adapter.hold,native_advance=adapter.native_advance,transport_window=adapter.transport_window,
                candidate_exe_sha256=prepared["exe_sha256"],candidate_binding=metadata),
                original_exe=args.original_exe,expected_exe_sha256=args.expected_exe_sha256,
                scenario=args.native_quit_scenario,timeout=args.progress_timeout,window_frames=args.window_frames)
            report["checks"].update(case["checks"])
            report["checks"]["native_quit_automated_case_completed"]=(case["status"]==native_quit.SUCCESS and
                bool(case["checks"]) and all(case["checks"].values()))
            report["checks"]["native_private_cards_unchanged"]=card_hashes(candidate)==before_cards
            if not all(report["checks"].values()):raise debug.DebugError("Native Quit case or private card retention failed")
        except Exception as error:
            report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
            # Preserve attached failed_behavior/failed_setup and let the existing
            # baseline finally block perform listener-checked owned shutdown.
            raise debug.DebugError(f"Native Quit {args.native_quit_scenario} case failed: {error}") from error
        finally:
            try:
                report["private_cards_after"]=card_hashes(candidate)
                report["checks"]["native_private_cards_unchanged"]=report["private_cards_after"]==before_cards
            except OSError as card_error:
                report["private_card_read_error"]=str(card_error)
                report["checks"]["native_private_cards_unchanged"]=False
                if "error" not in report:raise debug.DebugError("Private card verification failed") from card_error
    return exercise


def run(args):
    original=native_quit.verify_original(args.original_exe)  # Before staging/launch.
    candidate=preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"))
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
    prepared=menu_runner.pristine_candidate(candidate,args.expected_exe_sha256)
    loader=require_default_loader(candidate)
    os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"),
                      PYTHONPYCACHEPREFIX=str(candidate/"temp/pycache"))
    sys.pycache_prefix=str(candidate/"temp/pycache")
    modules=(debug,native_quit,preparation,baseline,menu_runner,native_quit.menu)
    metadata=dict(kind="owned_offline_native_quit",scenario=args.native_quit_scenario,
        mode="local",machine_scope="same_machine",input_path="offline_native",
        candidate_exe_sha256=prepared["exe_sha256"],expected_exe_sha256=args.expected_exe_sha256,
        original=original,loading=loader,runner_sha256=preparation.sha256(Path(__file__)),
        tool_sha256={Path(m.__file__).name:preparation.sha256(Path(m.__file__)) for m in modules},
        artwork_review="pending",ledger_status="unverified",source_build_binding="Staging observations are not compilation provenance",
        limits=["Fresh native intro only; full final Quit/current-data/character reentry unqualified",
                "Guest admission remains a failed behavior with exit1; it is never converted into expected-success",
                "No guest RAM/mailbox/fixture/success-flag/source-card writes; no R7/R15 ledger pass"])
    (candidate/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    (candidate/"native-quit-helper-source.py").write_bytes(Path(native_quit.__file__).read_bytes())
    # Baseline owns launch/cleanup. Remove inherited session/input/backend
    # controls only from this CLI process while constructing its offline child.
    inherited={key:value for key,value in os.environ.items() if key.upper().startswith(("PSX_","RNET_"))}
    metadata["discarded_inherited_runtime_variables"]=sorted(inherited)
    (candidate/"runner-metadata.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    for key in inherited:os.environ.pop(key)
    try:
        result=baseline.run(candidate,args.port,args.timeout,False,exercise=make_exercise(args,candidate,prepared,metadata))
    finally:
        os.environ.update(inherited)
    original_path=candidate/"baseline/qualification.json"
    original_status=result["status"]
    result.update(kind=metadata["kind"],runner=metadata,artwork_review="pending",ledger_status="unverified",
        original_baseline=dict(path=str(original_path),sha256=preparation.sha256(original_path),status=original_status))
    result["automated_checks_passed"]=(original_status=="passed" and
        result.get("exercise",{}).get("checks",{}).get("native_quit_automated_case_completed") is True)
    if result["automated_checks_passed"]:result["status"]=native_quit.SUCCESS
    (candidate/"qualification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None):
    parser=make_parser();args=parser.parse_args(argv);validate_options(parser,args)
    try:result=run(args)
    except (OSError,ValueError,debug.DebugError) as error:parser.exit(1,f"Native Quit setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"],error=result.get("error"),artwork_review="pending",ledger_status="unverified",
        report=str((args.candidate or args.output)/"qualification.json"))))
    return 0 if result["automated_checks_passed"] else 1


if __name__=="__main__":raise SystemExit(main())
