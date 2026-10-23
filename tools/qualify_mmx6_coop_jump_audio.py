"""Own one pristine offline published-host jump-audio observation (Windows).

No SIO/mailbox writes, audio adapter, guest calls or audio output. The observer
decides comparison/inconclusive status; this runner owns identity, host-device
publication, private lifecycle, final recording/card checks and raw artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import os
import subprocess
import time
import tomllib
import traceback

import coop_debug as debug
import coop_host_profile as manifests
import mmx6_coop_jump_audio as audio
import mmx6_input_recording as codec
import prepare_mmx6_coop_playtest as preparation
import prepare_mmx6_input_replay as artifacts
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_input_replay as host


SUCCESS = "jump_audio_observations_complete_outcomes_unverified"
INCONCLUSIVE = "inconclusive_native_rng_no_two_voice_window"


def validate_sources(build: Path, source: Path, manifest: dict) -> dict:
    """Verify actual declared game/generated inputs without scanning trees.

    The embedded manifest covers more roots; this deliberately checks only the
    explicitly supplied game tree and its CMake-selected generated tree. It
    does not infer complete dependency provenance from current Git HEAD.
    """
    cache = {}
    for line in (build/"CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "//")) and "=" in line and ":" in line.split("=",1)[0]:
            key,value=line.split("=",1);cache[key.split(":",1)[0]]=value
    if Path(cache.get("CMAKE_HOME_DIRECTORY", "")).resolve()!=source.resolve():
        raise ValueError("Build cache is not bound to the explicitly supplied game source")
    generated_name=cache.get("GAME_GENERATED_DIR")
    if not generated_name:
        raise ValueError("Build lacks its actual GAME_GENERATED_DIR mapping")
    generated=(source/generated_name).resolve(strict=True)
    item=host.json_object(Path(manifest["manifest_path"]), maximum=8*1024*1024)
    roots={"game":source.resolve(strict=True),"game-generated":generated}
    checked={name:0 for name in roots};total=0
    for logical,expected in item["files"].items():
        parts=PurePosixPath(logical).parts
        if not parts or parts[0] not in roots:continue
        if len(parts)<2 or ".." in parts or "\\" in logical or ":" in logical:
            raise ValueError("Declared game source path escaped its logical root")
        root=roots[parts[0]];path=(root/Path(*parts[1:])).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Declared game source escaped its actual root")
        before=path.stat()
        if before.st_size!=expected["bytes"] or preparation.sha256(path)!=expected["sha256"]:
            raise ValueError("Actual declared game source changed: "+logical)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError("Declared source changed during verification: "+logical)
        checked[parts[0]]+=1;total+=before.st_size
    for required in ("game/CMakeLists.txt","game/src/mods/mmx6_coop_plugin.c"):
        if required not in item["files"]:
            raise ValueError("Required co-op source is absent from the compiled manifest")
    if not all(checked.values()):raise ValueError("Empty declared game/generated source coverage")
    return dict(checked_files=checked,checked_bytes=total,generated_root=str(generated),
                scope="Declared game and game-generated files only; other dependency roots not rehashed")


def verify_prepared_originals(candidate: Path, original: Path, disc: Path) -> dict:
    config=tomllib.loads((candidate/"game.toml").read_text(encoding="utf-8-sig"))
    if (Path(config["game"]["exe"]).resolve()!=original.resolve() or
            Path(config["game"]["disc"]).resolve()!=disc.resolve()):
        raise ValueError("Prepared original EXE/disc differs from explicit source paths")
    runtime=config["runtime"]
    if (runtime.get("openbios") is not True or runtime.get("bios_hle") is not True or
            runtime.get("bios_hle_keep_intro") is not False or runtime.get("disc_speed")!="1x"):
        raise ValueError("Jump observer requires the original default loader and authentic disc timing")
    settings=tomllib.loads((candidate/"settings.toml").read_text(encoding="utf-8-sig"))
    if (settings["video"].get("rewind") is not False or settings["video"].get("aspect_ratio")!="4:3" or
            settings["video"].get("renderer")!="opengl" or settings["video"].get("fullscreen")!=0):
        raise ValueError("Jump observer requires the fresh native-aspect non-rewind profile")
    return dict(exe_sha256=preparation.sha256(original),disc=str(disc.resolve()),
                loader="default OpenBIOS/HLE with authentic1x disc",settings_sha256=preparation.sha256(candidate/"settings.toml"))


def verify_pad(status: dict, seat: int, bits: int | None=None, *, cleared=False) -> None:
    host.verify_host_status(status,seat,None if cleared else bits)
    if (not isinstance(status.get("host_axes"),list) or len(status["host_axes"])!=4 or
            any(type(value) is not int or value!=128 for value in status["host_axes"])):
        raise ValueError("Selected host slot did not acknowledge neutral axes")
    if cleared and status.get("host_layer") is not False:
        raise ValueError("Selected host slot remained armed after host-only clear")


def verify_offline(status: dict) -> None:
    if status.get("ok") is not True or any(type(status.get(key)) is not int or status[key]!=0
                                          for key in ("active","rollback","desync")):
        raise ValueError("Native jump-audio qualifier requires observed inactive ordinary offline transport")


class AudioHostRoute(host.HostRoute):
    def set(self,seat,bits):
        if type(seat) is not int or seat not in (0,1) or type(bits) is not int or not 0<=bits<=0xFFFF:
            raise ValueError("Expected one native co-op seat and a 16-bit pressed mask")
        self.control("set_input",layer="host",port=seat+1,buttons=hex(0xFFFF^bits),
                     lx=128,ly=128,rx=128,ry=128,lt=0,rt=0)
        status=self.control("pad_status",port=seat+1);verify_pad(status,seat,bits)
        receipt=dict(seat=seat,pressed=bits,status=status)
        self.report["inputs"].append(receipt)
        return receipt

    def clear(self,seat):
        self.control("clear_input",layer="host",port=seat+1)
        status=self.control("pad_status",port=seat+1);verify_pad(status,seat,cleared=True)
        self.report.setdefault("host_slot_clears",[]).append(dict(seat=seat,status=status))

    def native_advance(self,frames,label):
        if type(frames) is not int or not 1<=frames<=120:
            raise ValueError("Require bounded native clock progress")
        return self.advance(self.sample(label+" start"),frames,label)

    def hold(self,seat,bits,frames,label):
        if type(frames) is not int or not 1<=frames<=120:
            raise ValueError("Require bounded native/publication input progress")
        start=self.sample(label+" start");original=None
        deadline=time.monotonic()+self.timeout
        try:
            acknowledgment=self.set(seat,bits)
            end=self.advance(start,frames,label)
            while True:
                native=(end.native_timer-start.native_timer)&0xFFFFFFFF
                publications=(end.tick-start.tick)&0xFFFFFFFF
                if not 0<publications<0x80000000 or not frames<=native<0x80000000:
                    raise debug.DebugError("Accepted hold lacks forward native/publication evidence")
                if bits!=audio.CROSS:break
                if native>120:
                    raise debug.DebugError("Original held jump exceeded its native observation bound")
                before,held=start.players[seat],end.players[seat]
                if (held.state==1 and held.character==before.character and held.hp==before.hp and
                        held.action==6 and held.y_raw<before.y_raw):break
                # One world update may consume the previous host sample. Keep
                # Cross held until actual native ascent, rather than releasing
                # on that first publication and seeing action7 afterward.
                if native>=120 or time.monotonic()>=deadline:
                    raise debug.DebugError("Original held jump never reached observed native action6 ascent")
                time.sleep(.005)
                end=self.sample(label+" held acceptance")
            receipt=dict(label=label,seat=seat,pressed=bits,requested_native_ticks=frames,
                         acknowledgment=acknowledgment,start=start.json(),end=end.json(),
                         actual_native_ticks=native,actual_publications=publications,
                         held_jump_observed=bits==audio.CROSS)
            self.report.setdefault("accepted_windows",[]).append(receipt)
            return receipt
        except BaseException as error:
            original=error;raise
        finally:
            try:self.set(seat,0) # Keep configured devices present until final teardown.
            except Exception as error:
                self.report.setdefault("release_errors",[]).append(dict(seat=seat,error=str(error),
                    original_error=str(original) if original else None))
                if original is None:raise


def card_hashes(candidate):
    return {str(path.relative_to(candidate)):preparation.sha256(path)
            for path in sorted((candidate/"saves").rglob("*.mcd"))}


def inspect_capture(candidate: Path, image: str, manifest: str, required_seats: set[int]) -> dict:
    paths=list(candidate.glob("saves/**/input-recordings/session-*/inputs.jsonl"))
    if len(paths)!=1:raise ValueError("Require one finalized native-consumption recording")
    path=paths[0]
    if path.stat().st_size>artifacts.MAX_BYTES:raise ValueError("Recording exceeds bounded validation scope")
    with path.open("rb") as stream:summary=codec.validate(stream,max_events=artifacts.MAX_EVENTS)
    identity=summary.identity
    if identity["image_sha256"]!=image or identity["manifest_sha256"]!=manifest or identity["mode"]!="offline" or identity["baseline"] is not None:
        raise ValueError("Native recording is not the exact offline cold-boot candidate")
    status=host.json_object(path.parent/"status.json",4096)
    if (set(status)!={"contract","epoch","failure","schema","scope","status"} or
            type(status.get("schema")) is not int or status["schema"]!=1 or
            type(status.get("epoch")) is not int or not 0<status["epoch"]<=0xFFFFFFFFFFFFFFFF or
            status.get("contract")!=codec.CONTRACT or status.get("scope")!=artifacts.STATUS_SCOPE or
            status.get("status")!="finalized" or status.get("failure")!="" or
            (path.parent/"status.json").read_bytes()!=codec.canonical(status)):
        raise ValueError("Native recording did not finalize cleanly")
    bundles={name:artifacts.bounded(path.parent/name,1024*1024)
             for name in ("settings.json","content.json","simulation-contract.json")}
    cards=[]
    for slot,expected in enumerate(identity["cards"],1):
        card=path.parent/f"card{slot}.initial.mcd"
        if expected is None:
            if card.exists():raise ValueError("Unexpected initial card artifact")
            cards.append(None)
        else:cards.append(artifacts.bounded(card,131072))
    codec.validate_startup_artifacts(identity,settings=bundles["settings.json"],cards=cards,baseline=None)
    for name,key in (("content.json","content_sha256"),("simulation-contract.json","simulation_contract_sha256")):
        if hashlib.sha256(bundles[name]).hexdigest()!=identity[key]:raise ValueError("Native startup bundle changed: "+name)
    settings=json.loads(bundles["settings.json"])
    implementation=json.loads(bundles["simulation-contract.json"])
    if settings.get("declared_scope_available")!=1 or implementation.get("interpreted_overlays_sealed")!=1 or implementation.get("oracle")!=0:
        raise ValueError("Recording lacks complete ordinary sealed startup scope")
    ports=settings["input"]["ports"]
    for seat in (0,1):
        expected=dict(seat=seat,device_kind=1,configured_mode=2,connected=1,type=0)
        if len(ports)<=seat or any(type(ports[seat].get(k)) is not int or ports[seat][k]!=v for k,v in expected.items()):
            raise ValueError("Recorded startup lacks stable connected digital host devices")
    seen=set()
    with path.open("rb") as stream:
        for raw in stream:
            event=json.loads(raw)
            if event.get("type")=="N" and event["pads"][0][0]&0x40:seen.add(0)
            if event.get("type")=="C" and event["buttons"]&audio.CROSS:seen.add(1)
    if not required_seats<=seen:raise ValueError("Native trace lacks a requested seat's accepted jump input")
    return dict(path=str(path),sha256=preparation.sha256(path),events=summary.events,natives=summary.natives,
                p2_reads=summary.p2_reads,identity=identity,requested_jump_seats=sorted(required_seats),
                consumed_cross_seen_anywhere=sorted(seen),scope="Ordered native N/P2 C consumption; no temporal jump association or audio/output equivalence")


def run_owned(candidate,port,boot_timeout,progress_timeout,report,contract,*,expected_image,first_seat,max_attempts,audio_timeout,private_banks=None):
    host.require_windows();host.reserve(port)
    prepared=host.json_object(candidate/"preparation.json")
    baseline.candidate_environment(candidate,prepared)
    environment=host.sanitized_environment(host.json_object(candidate/"environment.json"),candidate)
    output=candidate/"jump-audio";output.mkdir()
    args=[str(candidate/"mmx6-runtime.exe"),"--game",str(candidate/"game.toml"),"--memcard-dir",str(candidate/"saves"),
          "--seal-interpreted-overlays","--hidden-window","--debug-port",str(port)]
    report.update(status="failed_setup",args=args,environment=host.json_object(candidate/"environment.json"),
                  input_path="published_host",muted="SDL_AUDIODRIVER=dummy",cards_before=card_hashes(candidate),
                  diagnostics_scope="private_banks_v1" if private_banks is not None else "hardware_legacy")
    report["process_environment_overlay"]={name:environment[name] for name in
        ("SDL_AUDIODRIVER","XDG_DATA_HOME","XDG_CONFIG_HOME","PYTHONPYCACHEPREFIX")}
    process=route=control=None
    with (output/"stdout.log").open("w") as stdout,(output/"stderr.log").open("w") as stderr, \
            (output/"control.jsonl").open("w",encoding="utf-8") as transcript:
        try:
            host.verify_expected_image(candidate/"mmx6-runtime.exe",expected_image)
            process=subprocess.Popen(args,cwd=candidate,env=environment,stdout=stdout,stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            report["owned_pid"]=process.pid
            control=host.control_for(process,port,debug.DebugClient(port),transcript)
            route=AudioHostRoute(control,report,progress_timeout)
            deadline=time.monotonic()+boot_timeout;next_pulse=0.;release_at=None;step=0
            while time.monotonic()<deadline:
                if process.poll() is not None:raise debug.DebugError("Owned audio candidate exited during native setup")
                if not baseline.owns_listener(port,process.pid):time.sleep(.1);continue
                if not report.get("host_preflight"):
                    status=control("netplay_status");verify_offline(status);report["offline_before"]=status
                    for seat in (0,1):
                        verify_pad(control("pad_status",port=seat+1),seat)
                        route.set(seat,0)
                    report["host_preflight"]=True
                if not report.get("first_native_record_observed"):
                    if not host.native_capture_started(candidate):time.sleep(.03);continue
                    report["first_native_record_observed"]=True
                mode=route.client.read(0x800CCED0,2)
                if mode[0]==10:
                    try:
                        idle=route.sample("original frontend intro")
                        if all(p.action==2 for p in idle.players):break
                    except debug.DebugError:pass # Co-op context is incomplete during cutscenes.
                now=time.monotonic()
                if release_at is not None and now>=release_at:route.set(0,0);release_at=None
                if now>=next_pulse and release_at is None:
                    route.set(0,8 if mode[0]!=10 and step%3==0 else audio.CROSS)
                    step+=1;release_at=now+.15;next_pulse=now+.8
                time.sleep(.03)
            else:raise debug.DebugError("Original host-input frontend did not reach healthy intro")
            route.set(0,0);route.set(1,0)
            context=dict(mode="local",input_path="published_host",clients=[route.client],
                request=control,hold=route.hold,native_advance=route.native_advance,report=report,
                candidate=candidate,expected_sha256=expected_image)
            if private_banks is not None:context["private_banks"]=private_banks
            report["audio"]=audio.jump_overlap_smoke(context,contract,first_seat=first_seat,
                max_attempts=max_attempts,timeout=audio_timeout)
            status=control("netplay_status");verify_offline(status);report["offline_after"]=status
            report["status"]=report["audio"]["status"]
        finally:
            if process is not None:
                # Clear only the two virtual host slots; retain keyboard device topology.
                def clear(seat):
                    if route is not None:return route.clear(seat)
                    control("clear_input",layer="host",port=seat+1)
                report["cleanup"]=baseline.stop_owned_runtime(process,
                    clear_inputs=(lambda:clear(0),lambda:clear(1)),request_quit=lambda:control("quit"))
            report["cards_after"]=card_hashes(candidate)
            report["existing_private_cards_unchanged"]=all(report["cards_after"].get(name)==digest
                for name,digest in report["cards_before"].items())
            if not report["existing_private_cards_unchanged"]:report["status"]="failed_private_cards"
            if process is not None and report.get("cleanup")!=dict(shutdown="graceful_owned_debug",exit_code=0):
                report["status"]="failed_owned_cleanup"


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("build","source","disc","original-exe","output"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--contract",type=Path,default=Path(audio.__file__).resolve().parents[1]/"docs/COOP_JUMP_AUDIO_CONTRACT.json")
    p.add_argument("--expected-exe-sha256",required=True);p.add_argument("--expected-manifest-sha256",required=True)
    p.add_argument("--port",type=int,default=24940);p.add_argument("--first-seat",type=int,choices=(0,1),default=0)
    p.add_argument("--max-attempts",type=int,default=8)
    p.add_argument("--private-banks",action="store_true",
                   help="Require new read-only event-bank/private-voice diagnostics and exact Zero30/31 banks")
    p.add_argument("--boot-timeout",type=float,default=240);p.add_argument("--progress-timeout",type=float,default=12)
    p.add_argument("--audio-timeout",type=float,default=90)
    return p


def options(p,args):
    import re
    if any(re.fullmatch(r"[0-9a-f]{64}",getattr(args,key)) is None for key in ("expected_exe_sha256","expected_manifest_sha256")):
        p.error("Require explicit lowercase executable and declared-manifest SHA256")
    if not 1<=args.port<=65535 or not 1<=args.max_attempts<=8:p.error("Require port1..65535 and attempts1..8")
    for name,bound in (("boot_timeout",600),("progress_timeout",60),("audio_timeout",120)):
        if not math.isfinite(getattr(args,name)) or not 0<getattr(args,name)<=bound:p.error("Require finite bounded timeouts")


def run(args):
    host.require_windows()
    output=preparation.local_output(args.output)
    if output.exists():raise ValueError("Output exists; preserve it and select a fresh F:/G: profile")
    output.mkdir(parents=True)
    report=dict(schema=1,kind="owned_offline_jump_audio",status="failed_setup",r4="unverified",r12="unverified",
        diagnostics_scope="private_banks_v1" if args.private_banks else "hardware_legacy",
        audible_output="not_tested",checks={},tools={Path(m.__file__).name:preparation.sha256(Path(m.__file__))
        for m in (audio,debug,manifests,preparation,baseline,host,codec,artifacts)},runner_sha256=preparation.sha256(Path(__file__)),
        runtime={},limits=["Local native digital virtual host slots only; no physical-controller or paired proof",
            "No PCM comparison, independent SPU-sample clock or music continuity proof; explicit diagnostic scope is retained"])
    (output/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    try:
        contract=host.json_object(args.contract);report["contract_sha256"]=audio.validate_contract(contract)
        reproduced=audio.build_contract(args.original_exe,args.disc)
        if reproduced!=contract:raise ValueError("Actual original EXE/raw BIN does not reproduce the pinned audio contract")
        report["checks"]["original_source_contract_reproduced"]=True
        (output/"source-contract.json").write_bytes(args.contract.read_bytes())
        private_banks=audio.build_private_bank_contract(args.disc,contract) if args.private_banks else None
        if private_banks is not None:
            report["private_bank_source"]=private_banks
            report["checks"]["original_private_source_banks_reproduced"]=True
            (output/"source-private-banks.json").write_text(json.dumps(private_banks,indent=2)+"\n",encoding="utf-8")
        host.verify_expected_image(args.build/"mmx6-runtime.exe",args.expected_exe_sha256)
        candidate=output/"candidate"
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
        host.configure_two_digital_slots(candidate)
        host.verify_expected_image(candidate/"mmx6-runtime.exe",args.expected_exe_sha256)
        manifest=manifests.validate_build_manifest(args.build,[args.build/"mmx6-runtime.exe",candidate/"mmx6-runtime.exe"],
            evidence_directory=output/"manifest")
        if manifest["declared_sha256"]!=args.expected_manifest_sha256:raise ValueError("Compiled manifest differs from explicit expected SHA256")
        report["manifest"]=manifest;report["sources"]=validate_sources(args.build,args.source,manifest)
        report["originals"]=verify_prepared_originals(candidate,args.original_exe,args.disc)
        report["checks"]["exact_image_manifest_and_declared_game_sources"]=True
        run_error=None
        try:
            run_owned(candidate,args.port,args.boot_timeout,args.progress_timeout,report["runtime"],contract,
                expected_image=args.expected_exe_sha256,first_seat=args.first_seat,max_attempts=args.max_attempts,
                audio_timeout=args.audio_timeout,private_banks=private_banks)
        except Exception as error:
            run_error=error
        native=report["runtime"]
        try:
            if native.get("cleanup")!=dict(shutdown="graceful_owned_debug",exit_code=0) or not native.get("existing_private_cards_unchanged"):
                raise debug.DebugError("Owned shutdown/private-card retention failed")
            requested={row["seat"] for row in native.get("accepted_windows",[]) if row["pressed"]==audio.CROSS and row["label"].startswith("audio-")}
            report["capture"]=inspect_capture(candidate,args.expected_exe_sha256,args.expected_manifest_sha256,requested)
            report["checks"]["finalized_native_input_capture_and_owned_cleanup"]=True
        except Exception as error:
            report["postrun_error"]=dict(type=type(error).__name__,message=str(error))
            if run_error is None:raise
        if run_error is not None:raise run_error
        status=native.get("status")
        report["status"]=SUCCESS if status=="observations_complete" else status
        if status not in ("observations_complete","comparison_failed",INCONCLUSIVE):
            raise debug.DebugError("Observer did not complete a bounded audio comparison")
    except Exception as error:
        report["error"]=dict(type=type(error).__name__,message=str(error));report["traceback"]=traceback.format_exc()
        if report["status"]==SUCCESS:report["status"]="failed"
    finally:
        (output/"qualification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main(argv=None):
    p=parser();args=p.parse_args(argv);options(p,args)
    try:result=run(args)
    except (ValueError,OSError) as error:p.exit(1,str(error)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"]==SUCCESS else (2 if result["status"]==INCONCLUSIVE else 1)


if __name__=="__main__":raise SystemExit(main())
