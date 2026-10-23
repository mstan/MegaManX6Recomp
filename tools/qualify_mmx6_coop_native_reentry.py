"""Own one fresh offline source-bound native final-Quit/reentry case.

Baseline owns boot/listener/process cleanup; the existing menu adapter owns
post-reentry gameplay windows. Frontend input uses persistent original native
pad controls without waiting on the retired game's diagnostic clock.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

import coop_debug as debug
import mmx6_coop_native_reentry as reentry
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_native_quit as quit_runner
import qualify_mmx6_coop_personal_menu as menu_runner

card_hashes=quit_runner.card_hashes


def make_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    staging=parser.add_mutually_exclusive_group(required=True)
    staging.add_argument("--build",type=Path)
    staging.add_argument("--candidate",type=Path,help="Fresh prepared automated profile, never previously launched")
    parser.add_argument("--source",type=Path)
    parser.add_argument("--disc",type=Path,help="Runtime original disc/CUE for new staging")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--original-disc",type=Path,required=True,help="Exact original raw2352-byte BIN for EXE/archive source guards")
    parser.add_argument("--expected-exe-sha256",required=True)
    parser.add_argument("--route",choices=("current_data","new_game"),required=True)
    parser.add_argument("--port",type=int,default=24899)
    parser.add_argument("--timeout",type=float,default=240,help="Native boot deadline")
    parser.add_argument("--progress-timeout",type=float,default=12,help="Each native/frontend input deadline")
    parser.add_argument("--reentry-timeout",type=float,default=180,help="Original native story/map/arrival deadline")
    return parser


def validate_options(parser,args):
    # Reuse staging/hash/port/deadline guards. The shared helper's later guest
    # menu retains its fixed default12 windows, not an ignored CLI setting.
    menu_runner.validate_options(parser,SimpleNamespace(**vars(args),window_frames=12))
    if args.original_disc.suffix.lower()!=".bin":parser.error("--original-disc must be the raw original BIN, separate from runtime CUE")
    if not math.isfinite(args.reentry_timeout) or not args.progress_timeout<=args.reentry_timeout<=240:
        parser.error("Reentry deadline must be in [progress-timeout,240]")


class PersistentNativeInput:
    """Only the baseline's owned control; ACKs remain protocol receipts."""
    def __init__(self,control,report):
        self.control,self.report=control,report
        report["persistent_native_input"]=[]

    def set_input(self,seat,bits):
        if type(seat) is not int or seat not in (0,1) or type(bits) is not int or not 0<=bits<=0xFFFF:
            raise ValueError("Expected original native seat0/1 and16-bit pressed mask")
        command="press" if bits else "clear_input"
        fields=dict(port=seat+1)
        if bits:fields.update(buttons=0xFFFF^bits,frames=0)
        receipt=dict(seat=seat,pressed=bits,command=command,fields=fields,status="requested",
                     input_path="offline_native",acceptance="Helper must observe native decoded response and consumed neutral")
        self.report["persistent_native_input"].append(receipt)
        try:
            response=self.control(command,**fields)
            receipt.update(status="rpc_completed",response=response)
            return response
        except Exception as error:
            receipt.update(status="rpc_failed",error=str(error),error_type=type(error).__name__)
            raise


def make_exercise(args,candidate,prepared,metadata):
    def exercise(control,_client,destination,report):
        report.update(checks=dict(native_reentry_automated_case_completed=False,native_private_cards_unchanged=False,
                                 owned_input_clear_requests_completed=False),artwork_review="pending",ledger_status="unverified")
        adapter=menu_runner.OfflineMenuAdapter(control,report,timeout=args.progress_timeout)
        persistent=PersistentNativeInput(control,report)
        owned_debug=SimpleNamespace(observe=debug.observe,
            capture_present=lambda client,path:debug.capture_present(client,path,request=control))
        failure=None;before_cards=None
        try:
            before_cards=card_hashes(candidate);report["private_cards_before"]=before_cards
            adapter.settle_idle()
            case=reentry.native_reentry_smoke(dict(mode="local",input_path="offline_native",clients=[adapter.client],
                both=lambda fn:[fn(0)],debug=owned_debug,report=report,output=destination,set_input=persistent.set_input,
                hold=adapter.hold,native_advance=adapter.native_advance,transport_window=adapter.transport_window,
                candidate_exe_sha256=prepared["exe_sha256"],candidate_binding=metadata),
                original_disc=args.original_disc,expected_exe_sha256=args.expected_exe_sha256,route=args.route,
                timeout=args.progress_timeout,reentry_timeout=args.reentry_timeout)
            report["checks"].update(case["checks"])
            completed=case["status"]==reentry.SUCCESS and bool(case["checks"]) and all(case["checks"].values())
            report["checks"]["native_reentry_automated_case_completed"]=completed
            if not completed:raise debug.DebugError("Native final-Quit/reentry helper did not complete its automated checks")
        except Exception as error:
            failure=error
            report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
            # ReentryError derives RuntimeError; translate it for the baseline's
            # existing catch/finally without rewriting its retained partial case.
            raise debug.DebugError(f"Native reentry {args.route} case failed: {error}") from error
        finally:
            cleanup_errors=[]
            for seat in (0,1):
                try:persistent.set_input(seat,0)
                except Exception as error:cleanup_errors.append(dict(seat=seat,error=str(error)))
            report["persistent_input_cleanup_errors"]=cleanup_errors
            report["checks"]["owned_input_clear_requests_completed"]=not cleanup_errors
            card_error=None
            try:
                report["private_cards_after"]=card_hashes(candidate)
                report["checks"]["native_private_cards_unchanged"]=(before_cards is not None and report["private_cards_after"]==before_cards)
            except OSError as error:
                card_error=error;report["private_card_read_error"]=str(error)
                report["checks"]["native_private_cards_unchanged"]=False
            if failure is None and (cleanup_errors or card_error is not None or not report["checks"]["native_private_cards_unchanged"]):
                report.update(error="Native reentry input release or private-card verification failed",error_type="DebugError")
                raise debug.DebugError("Native reentry input release or private-card verification failed") from card_error
    return exercise


def run(args):
    original=reentry.load_sources(args.original_disc)["original"]  # Before staging/launch; helper rechecks before controls.
    candidate=preparation.local_output(args.candidate or args.output)
    if not args.candidate:
        if preparation.sha256(args.build/"mmx6-runtime.exe")!=args.expected_exe_sha256:
            raise ValueError("Native reentry build image differs from the explicitly expected SHA256")
        os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"))
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
    prepared=menu_runner.pristine_candidate(candidate,args.expected_exe_sha256)
    loader=quit_runner.require_default_loader(candidate)
    os.environ.update(TEMP=str(candidate/"temp"),TMP=str(candidate/"temp"),PYTHONPYCACHEPREFIX=str(candidate/"temp/pycache"))
    sys.pycache_prefix=str(candidate/"temp/pycache")
    modules=(debug,reentry,preparation,baseline,menu_runner,quit_runner,reentry.content,reentry.native,reentry.menu,reentry.quit_ui)
    metadata=dict(kind="owned_offline_native_final_quit_reentry",route=args.route,mode="local",machine_scope="same_machine",
        input_path="offline_native",candidate_exe_sha256=prepared["exe_sha256"],expected_exe_sha256=args.expected_exe_sha256,
        original=original,loading=loader,runner_sha256=preparation.sha256(Path(__file__)),
        tool_sha256={Path(m.__file__).name:preparation.sha256(Path(m.__file__)) for m in modules},
        native_ram_mapping=dict(address=hex(reentry.READ_BASE),end_exclusive=hex(reentry.READ_END),bytes=reentry.READ_BYTES),
        progress_timeout=args.progress_timeout,reentry_timeout=args.reentry_timeout,guest_menu_window_frames=12,
        artwork_review="pending",ledger_status="unverified",source_build_binding="Staging observations are not compilation provenance",
        limits=["One fresh offline process; paired and earned-card preservation remain separate",
                "An empty current-data header refuses before any native Quit control; it is never fabricated",
                "New Game defaults do not qualify acquired-current-data preservation",
                "No guest RAM/mailbox/fixture/success-flag/source-card writes or R15 ledger pass"])
    snapshots=[]
    for name,path in (("runner-source.py",Path(__file__)),("native-reentry-helper-source.py",Path(reentry.__file__)),
                      ("native-reentry-menu-source.py",Path(reentry.menu.__file__))):
        destination=candidate/name;destination.write_bytes(path.read_bytes())
        snapshots.append(dict(path=str(destination),sha256=preparation.sha256(destination)))
    metadata["source_snapshots"]=snapshots
    inherited={key:value for key,value in os.environ.items() if key.upper().startswith(("PSX_","RNET_"))}
    metadata["discarded_inherited_runtime_variables"]=sorted(inherited)
    (candidate/"runner-metadata.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    for key in inherited:os.environ.pop(key)
    try:
        result=baseline.run(candidate,args.port,args.timeout,False,exercise=make_exercise(args,candidate,prepared,metadata))
    finally:os.environ.update(inherited)
    original_path=candidate/"baseline/qualification.json";original_status=result["status"]
    result.update(kind=metadata["kind"],runner=metadata,artwork_review="pending",ledger_status="unverified",
        original_baseline=dict(path=str(original_path),sha256=preparation.sha256(original_path),status=original_status))
    checks=result.get("exercise",{}).get("checks",{})
    result["automated_checks_passed"]=(original_status=="passed" and bool(checks) and
        checks.get("native_reentry_automated_case_completed") is True and all(checks.values()))
    if result["automated_checks_passed"]:result["status"]=reentry.SUCCESS
    (candidate/"qualification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None):
    parser=make_parser();args=parser.parse_args(argv);validate_options(parser,args)
    try:result=run(args)
    except (OSError,ValueError,debug.DebugError) as error:parser.exit(1,f"Native reentry setup failed: {error}\n")
    print(json.dumps(dict(status=result["status"],error=result.get("error"),artwork_review="pending",ledger_status="unverified",
        report=str((args.candidate or args.output)/"qualification.json"))))
    return 0 if result["automated_checks_passed"] else 1


if __name__=="__main__":raise SystemExit(main())
