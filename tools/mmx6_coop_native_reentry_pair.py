"""Owned same-machine New Game reentry adapter; no process launches or RAM writes.

Every logical seat publishes into its own peer's LOCAL port1. The ordinary
frontend/netplay path resolves that peer's input into the logical session seat.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
import tomllib

import mmx6_coop_native_reentry as helper
import mmx6_coop_published_input as published
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_input_replay as host


def bind_original_disc(cue, raw):
    """Narrow exact single-data-track CUE contract; no guessed multi-file map."""
    cue,raw=Path(cue).resolve(strict=True),Path(raw).resolve(strict=True)
    if cue.suffix.lower()!=".cue" or raw.suffix.lower()!=".bin" or not raw.is_file() or cue.stat().st_size>65536:
        raise ValueError("Reentry requires a bounded runtime CUE and original raw BIN")
    lines=[line.strip() for line in cue.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    lines=[line for line in lines if not re.match(r"(?i)^REM(?:\s|$)",line)]
    if len(lines)!=3:
        raise ValueError("Reentry accepts only FILE/track01 MODE2/2352/index01 zero CUE")
    file=re.fullmatch(r'(?i)FILE\s+"([^"\r\n]+)"\s+BINARY',lines[0])
    if (file is None or re.fullmatch(r"(?i)TRACK\s+01\s+MODE2/2352",lines[1]) is None or
            re.fullmatch(r"(?i)INDEX\s+01\s+00:00:00",lines[2]) is None):
        raise ValueError("Runtime CUE has an unsupported source/track/index mapping")
    selected=(cue.parent/Path(file[1])).resolve(strict=True)
    if selected!=raw:raise ValueError("Runtime CUE does not select the explicit original raw BIN")
    stat=raw.stat()
    return dict(runtime_cue=str(cue),cue_sha256=preparation.sha256(cue),original_raw_bin=str(raw),
        raw_bytes=stat.st_size,raw_mtime_ns=stat.st_mtime_ns,track=1,mode="MODE2/2352",index="00:00:00",
        scope="Exact file/track binding and pinned EXE/archive members; no whole raw-disc hash claim")


def prepare_profile(directory,cue,raw):
    """Only the newly created profile; configure both devices before Popen."""
    directory=Path(directory)
    host.configure_two_digital_slots(directory)
    settings=tomllib.loads((directory/"settings.toml").read_text(encoding="utf-8-sig"))
    pads=settings["controller"]
    if any(pads.get("p"+str(i)+"_device")!="keyboard" or pads.get("p"+str(i)+"_mode")!="digital" for i in (1,2)):
        raise ValueError("Fresh paired reentry devices are not two stable digital host pads")
    config=tomllib.loads((directory/"game.toml").read_text(encoding="utf-8-sig"))
    game=config["game"];runtime=config["runtime"]
    cards=runtime.get("memcard_dir")
    if (Path(game["disc"]).resolve(strict=True)!=Path(cue).resolve(strict=True) or
            not isinstance(cards,str) or not cards or Path(cards).resolve()!=directory.resolve()/"saves" or
            preparation.sha256(Path(game["exe"]))!=helper.content.EXE_SHA256):
        raise ValueError("Prepared reentry original EXE/CUE/private-card binding changed")
    if (runtime.get("openbios") is not True or runtime.get("bios_hle") is not True or
            runtime.get("bios_hle_keep_intro") is not False or runtime.get("disc_speed")!="1x" or
            settings["video"].get("renderer")!="opengl" or settings["video"].get("aspect_ratio")!="4:3" or
            settings["video"].get("rewind") is not False):
        raise ValueError("Reentry requires native4:3, no rewind and the original default loader")
    return dict(settings_sha256=preparation.sha256(directory/"settings.toml"),
        game_config_sha256=preparation.sha256(directory/"game.toml"),original_exe_sha256=helper.content.EXE_SHA256,
        disc=bind_original_disc(cue,raw),local_input_port=1,session_input_player=0,
        topology="Both configured digital keyboard slots persist; each peer publishes only local port1")


class Route(host.HostRoute):
    """Reuse the real host sampler/ack path with explicit neutral axes."""
    def __init__(self,control,report):
        def checked(command,**fields):
            if command=="set_input":
                if fields.get("layer")!="host" or fields.get("port")!=1:
                    raise ValueError("A paired seat must publish only its owned peer's local hostport1")
                fields.update(lx=128,ly=128,rx=128,ry=128,lt=0,rt=0)
            result=control(command,**fields)
            if command=="pad_status":
                axes=result.get("host_axes")
                if not isinstance(axes,list) or len(axes)!=4 or any(type(v) is not int or v!=128 for v in axes):
                    raise ValueError("Published host axes were not acknowledged neutral")
            return result
        super().__init__(checked,report,12)

    def clear(self):
        self.control("clear_input",layer="host",port=1)
        status=self.control("pad_status",port=1);host.verify_host_status(status,0)
        if status.get("host_layer") is not False:
            raise ValueError("Owned hostport1 remained armed after host-only clear")


def install_routes(clients,processes,ports,report,output,handles):
    if not len(clients)==len(processes)==len(ports)==2:
        raise ValueError("Reentry needs both owned peer/listener pairs")
    inputs=[]
    report["native_reentry_published_routes"]=inputs
    for seat,client in enumerate(clients):
        path=Path(output)/f"peer-{seat}/logs/native-reentry-host-input.jsonl"
        transcript=path.open("w",encoding="utf-8");handles.append(transcript)
        item=dict(logical_seat=seat,local_port=1,debug_port=ports[seat],owned_pid=processes[seat].pid,transcript=str(path));inputs.append(item)
        # HostRoute initializes its own checks/observations, never the pair's
        # authoritative top-level checks or accumulated matched evidence.
        client.reentry_route=Route(host.control_for(processes[seat],ports[seat],client,transcript),item)


def cards(output):
    return [{p.name:preparation.sha256(p) for p in sorted((Path(output)/f"peer-{seat}/saves").glob("*.mcd"))}
            for seat in (0,1)]


def finalize(report,output,*,runtime_ready,owned_processes):
    """After owned process teardown: a helper result cannot waive cleanup."""
    try:
        final=cards(output);report["native_reentry_private_cards_final"]=final
        before=report.get("native_reentry_private_cards_before")
        unchanged=before is not None and final==before
    except OSError as error:
        report["native_reentry_final_card_error"]=str(error);unchanged=False
    peers=report.get("peers",[])
    cleaned=(owned_processes==len(peers)==2 and all(p.get("shutdown")=="graceful_owned_debug" and
        p.get("exit_code")==0 and not p.get("input_release_errors") and not p.get("private_card_error") for p in peers))
    report["checks"].update(native_reentry_final_private_cards_unchanged=unchanged,native_reentry_owned_pair_cleanup=cleaned)
    if not unchanged or not cleaned:
        report["status"]="failed" if runtime_ready else "failed_setup"
        report["default_intro_qualified"]=report["default_launch_qualified"]=False


def exercise(ctx,*,expected_sha,original_disc,plan):
    report=ctx["report"];clients=ctx["clients"]
    report["checks"]["native_reentry_automated_case_completed"]=False
    if (report.get("candidate_exe_sha256")!=expected_sha or len(report.get("peers",[]))!=2 or
            any(p.get("preparation",{}).get("exe_sha256")!=expected_sha for p in report["peers"]) or
            len(clients)!=2 or any(not isinstance(getattr(c,"reentry_route",None),Route) for c in clients)):
        raise ValueError("Reentry requires two exact staged images with owned published routes")
    required=("host_profile_settled_before_guest","declared_build_manifest_bound_to_staged_images",
              "default_resident_loader_committed","native_reentry_original_source_bound","native_reentry_declared_sources_match")
    if (not all(report["checks"].get(k) is True for k in required) or not report.get("resolved_state_crc") or
            not report.get("host_profile_startup") or not report.get("host_profile_build_manifest") or
            len(report.get("native_reentry_prepared",[]))!=2):
        raise ValueError("Reentry lacks actual source/settings/profile/manifest/CRC startup proof")
    def set_input(seat,bits):
        if type(seat) is not int or seat not in (0,1):raise ValueError("Invalid logical paired seat")
        clients[seat].host_input(bits)
    def capture(client,path):
        path=Path(path).resolve()
        if not path.is_relative_to(Path(ctx["output"]).resolve()):raise ValueError("Capture escaped owned pair output")
        path.parent.mkdir(parents=True,exist_ok=True)
        return ctx["debug"].capture_present(client,path)
    report["native_reentry_private_cards_before"]=cards(ctx["output"])
    adapter=published.PublishedHeldInput(clients,ctx["network"],ctx["transport_window"],report)
    failure=None
    try:
        case=helper.native_reentry_smoke(dict(mode="netplay",input_path="published_host",clients=clients,
            both=ctx["both"],debug=SimpleNamespace(observe=ctx["debug"].observe,capture_present=capture),
            report=report,output=ctx["output"],set_input=set_input,hold=adapter.hold,
            native_advance=ctx["native_advance"],transport_window=ctx["transport_window"],network=ctx["network"],
            matched=ctx["matched"],candidate_exe_sha256=expected_sha,same_machine=True,
            candidate_binding=dict(exe_sha256=expected_sha,declared_build=report["host_profile_build_manifest"],
                source=report["native_reentry_original"],profiles=report["host_profile_startup"],
                prepared=report["native_reentry_prepared"],network_plan=plan)),
            original_disc=original_disc,expected_exe_sha256=expected_sha,route="new_game",timeout=12,reentry_timeout=180)
        report["native_reentry_automated_status"]=case["status"]
        completed=case["status"]==helper.SUCCESS and bool(case["checks"]) and all(case["checks"].values())
        report["checks"]["native_reentry_automated_case_completed"]=completed
        if not completed:raise helper.ReentryError("Native paired New Game reentry did not complete its checks")
        return case
    except BaseException as error:
        failure=error;raise
    finally:
        errors=[]
        for seat,client in enumerate(clients):
            try:client.host_input(0) # Keep device topology; clear only at process teardown.
            except Exception as error:errors.append(dict(seat=seat,error=str(error)))
        report["native_reentry_input_cleanup_errors"]=errors
        report["checks"]["native_reentry_published_neutral_requests_completed"]=not errors
        card_error=None
        try:
            after=cards(ctx["output"]);report["native_reentry_private_cards_after"]=after
            report["checks"]["native_reentry_private_cards_unchanged"]=after==report["native_reentry_private_cards_before"]
        except OSError as error:
            card_error=error;report["native_reentry_private_card_error"]=str(error)
            report["checks"]["native_reentry_private_cards_unchanged"]=False
        if failure is None and (errors or card_error or not report["checks"]["native_reentry_private_cards_unchanged"]):
            raise helper.ReentryError("Paired New Game neutral release or private-card verification failed") from card_error
