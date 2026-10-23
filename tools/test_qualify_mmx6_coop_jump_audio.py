"""Runner/protocol/error fixtures only: no native process or sockets are used."""
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import qualify_mmx6_coop_jump_audio as runner
from test_coop_debug_protocol import diagnostic


def pad(seat=0,bits=0,active=True):
    digital=dict(connected=True,analog=False,type=0)
    return dict(host_input_slots=2,host_port=seat+1,host_layer=active,
                host_buttons=hex(0xFFFF^bits),host_axes=[128]*4,slot0=digital,slot1=digital,
                override=-1,override_p2=-1,override_pad_type=-1,override_axes_valid=False)


class ProtocolTests(unittest.TestCase):
    def test_incomplete_active_or_rollback_transport_refused_before_input(self):
        runner.verify_offline(dict(ok=True,active=0,rollback=0,desync=0))
        for key,value in (("ok",1),("active",1),("active",False),("rollback",1),("desync",1)):
            status=dict(ok=True,active=0,rollback=0,desync=0);status[key]=value
            with self.assertRaises(ValueError):runner.verify_offline(status)
        with self.assertRaises(ValueError):runner.verify_offline(dict(ok=True,active=0))

    def test_strict_selected_host_ack_neutral_axes_and_devices(self):
        runner.verify_pad(pad(1,0x4000),1,0x4000)
        runner.verify_pad(pad(1,active=False),1,cleared=True)
        for key,value in (("host_port",1),("host_input_slots",1),("host_axes",[128,128,0,128]),
                          ("host_axes",[True]*4),("host_layer",False),("host_buttons","0xffff"),
                          ("override_p2",0),("override_axes_valid",True)):
            value_dict=pad(1,0x4000);value_dict[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):runner.verify_pad(value_dict,1,0x4000)
        for key,value in (("connected",False),("analog",True),("type",1)):
            value_dict=pad();value_dict["slot1"]=dict(value_dict["slot1"],**{key:value})
            with self.assertRaises(ValueError):runner.verify_pad(value_dict,0)
        with self.assertRaises(ValueError):runner.verify_pad(pad(),0,cleared=True)

    def test_set_clear_select_one_host_slot_without_sio_or_topology_write(self):
        commands=[];bits=[0,0];active=[False,False]
        def control(command,**fields):
            commands.append((command,fields));seat=fields["port"]-1
            if command=="set_input":
                self.assertEqual(fields["layer"],"host")
                self.assertEqual([fields[k]for k in ("lx","ly","rx","ry")],[128]*4)
                self.assertEqual((fields["lt"],fields["rt"]),(0,0))
                bits[seat]=int(fields["buttons"],0)^0xFFFF;active[seat]=True
            elif command=="clear_input":
                self.assertEqual(fields,dict(layer="host",port=2));bits[seat]=0;active[seat]=False
            elif command=="pad_status":return pad(seat,bits[seat],active[seat])
            else:self.fail("Unexpected mutation: "+command)
            return dict(ok=True)
        report={};route=runner.AudioHostRoute(control,report,1)
        route.set(0,8);route.set(1,runner.audio.CROSS);route.clear(1)
        self.assertEqual(bits,[8,0]);self.assertEqual(active,[True,False])
        self.assertEqual(set(c[0]for c in commands),{"set_input","pad_status","clear_input"})
        self.assertEqual(report["host_slot_clears"][0]["seat"],1)

    def test_hold_keeps_native_publication_receipt_and_neutralizes(self):
        start=runner.debug.parse_diagnostic(diagnostic(tick=10));start=replace(start,native_timer=20)
        end=replace(start,tick=12,native_timer=21)
        report={};route=runner.AudioHostRoute(Mock(),report,1)
        route.sample=Mock(return_value=start);route.advance=Mock(return_value=end)
        route.set=Mock(return_value=dict(ack="synthetic"))
        receipt=route.hold(1,runner.audio.CROSS,1,"audio-second-jump")
        self.assertEqual(receipt["actual_native_ticks"],1)
        self.assertEqual(receipt["actual_publications"],2)
        self.assertEqual(route.set.call_args_list[-1].args,(1,0))
        json.dumps(receipt) # The observer stores this directly in its report.
        self.assertEqual(report["accepted_windows"],[receipt])

    def test_hold_refuses_stalled_or_regressed_publications_and_preserves_original_error(self):
        start=runner.debug.parse_diagnostic(diagnostic(tick=10));start=replace(start,native_timer=20)
        for end in (replace(start,native_timer=21),replace(start,tick=9,native_timer=21),
                    replace(start,tick=11,native_timer=19)):
            report={};route=runner.AudioHostRoute(Mock(),report,1)
            route.sample=Mock(return_value=start);route.advance=Mock(return_value=end);route.set=Mock()
            with self.assertRaises(runner.debug.DebugError):route.hold(0,runner.audio.CROSS,1,"audio-first-jump")
            self.assertEqual(route.set.call_args_list[-1].args,(0,0))
            self.assertNotIn("accepted_windows",report)
        report={};route=runner.AudioHostRoute(Mock(),report,1)
        route.sample=Mock(return_value=start);route.advance=Mock(side_effect=RuntimeError("native timeout"))
        route.set=Mock(side_effect=[None,ValueError("release failed")])
        with self.assertRaisesRegex(RuntimeError,"native timeout"):route.hold(0,runner.audio.CROSS,1,"jump")
        self.assertEqual(report["release_errors"][0]["original_error"],"native timeout")

    def test_bounded_options_refuse_before_launch(self):
        base=["--build","build","--source","source","--disc","disc","--original-exe","original","--output","output",
              "--expected-exe-sha256","1"*64,"--expected-manifest-sha256","2"*64]
        for extra in (["--first-seat","2"],["--max-attempts","9"],["--max-attempts","0"],["--port","0"],
                      ["--boot-timeout","nan"],["--audio-timeout","121"],["--progress-timeout","0"],
                      ["--expected-exe-sha256","bad"]):
            p=runner.parser()
            with self.subTest(extra=extra),patch("sys.stderr",new=io.StringIO()),self.assertRaises(SystemExit):
                runner.options(p,p.parse_args(base+extra))


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="mmx6-jump-qualifier-",dir=os.environ["TEMP"])
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def sources(self):
        build=self.root/"build";source=self.root/"source";generated=source/"generated"
        build.mkdir();generated.mkdir(parents=True)
        files={}
        for logical,data in (("game/CMakeLists.txt",b"fixture recipe"),("game/src/mods/mmx6_coop_plugin.c",b"fixture plugin"),
                             ("game-generated/dispatch.c",b"fixture generated")):
            root=generated if logical.startswith("game-generated/")else source
            path=root/logical.split("/",1)[1];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            files[logical]=dict(bytes=len(data),sha256=runner.codec.sha256(data))
        manifest=build/"manifest.json";manifest.write_text(json.dumps(dict(files=files)))
        (build/"CMakeCache.txt").write_text(f"CMAKE_HOME_DIRECTORY:INTERNAL={source.as_posix()}\nGAME_GENERATED_DIR:STRING=generated\n")
        return build,source,dict(manifest_path=str(manifest))

    def test_declared_actual_game_generated_sources_and_changes(self):
        build,source,manifest=self.sources()
        found=runner.validate_sources(build,source,manifest)
        self.assertEqual(found["checked_files"],dict(game=2,**{"game-generated":1}))
        (source/"src/mods/mmx6_coop_plugin.c").write_bytes(b"changed plugin")
        with self.assertRaisesRegex(ValueError,"source changed"):runner.validate_sources(build,source,manifest)

    def test_unknown_missing_or_escaped_source_mapping_refused(self):
        build,source,manifest=self.sources();path=Path(manifest["manifest_path"]);original=path.read_text()
        item=json.loads(original);item["files"]["game/../outside"]=dict(bytes=0,sha256="0"*64)
        path.write_text(json.dumps(item))
        with self.assertRaises(ValueError):runner.validate_sources(build,source,manifest)
        path.write_text(original);(build/"CMakeCache.txt").write_text("GAME_GENERATED_DIR:STRING=generated\n")
        with self.assertRaises(ValueError):runner.validate_sources(build,source,manifest)

    def recording(self):
        candidate=self.root/"candidate";record=candidate/"saves/input-recordings/session-1";record.mkdir(parents=True)
        settings=dict(declared_scope_available=1,input=dict(ports=[dict(seat=i,device_kind=1,configured_mode=2,connected=1,type=0)for i in (0,1)]))
        bundles={"settings.json":runner.codec.canonical(settings),"content.json":b'{}\n',
                 "simulation-contract.json":runner.codec.canonical(dict(interpreted_overlays_sealed=1,oracle=0))}
        for name,data in bundles.items():(record/name).write_bytes(data)
        identity=dict(image_sha256="1"*64,manifest_sha256="2"*64,execution_id="synthetic",
            settings_sha256=runner.codec.sha256(bundles["settings.json"]),content_sha256=runner.codec.sha256(bundles["content.json"]),
            simulation_contract_sha256=runner.codec.sha256(bundles["simulation-contract.json"]),mode="offline",profile=None,cards=[None,None],baseline=None)
        stream=io.BytesIO();writer=runner.codec.Encoder(stream,identity)
        writer.append(dict(type="N",order=0,native=0,cycles=10,sim_tick=None,frame=20,caller=0x80012220,pads=[[0x40,0,0x40],[0,0,0]]))
        writer.append(dict(type="C",order=1,native=0,cycles=11,sim_tick=None,seat=1,consumer="stage",buttons=0x4000));writer.finish()
        (record/"inputs.jsonl").write_bytes(stream.getvalue())
        (record/"status.json").write_bytes(runner.codec.canonical(dict(contract=runner.codec.CONTRACT,epoch=1,failure="",schema=1,
            scope=runner.artifacts.STATUS_SCOPE,status="finalized")))
        return candidate,record

    def test_finalized_canonical_capture_and_actual_consumption_only(self):
        candidate,record=self.recording()
        found=runner.inspect_capture(candidate,"1"*64,"2"*64,{0,1})
        self.assertEqual((found["events"],found["natives"],found["p2_reads"]),(2,1,1))
        self.assertEqual(found["consumed_cross_seen_anywhere"],[0,1])
        self.assertIn("no temporal jump association",found["scope"])
        (record/"inputs.jsonl").write_bytes((record/"inputs.jsonl").read_bytes()[:-1])
        with self.assertRaises(ValueError):runner.inspect_capture(candidate,"1"*64,"2"*64,{0,1})

    def test_capture_bad_status_image_manifest_or_startup_bundle_refused(self):
        candidate,record=self.recording()
        for image,manifest in (("3"*64,"2"*64),("1"*64,"3"*64)):
            with self.assertRaises(ValueError):runner.inspect_capture(candidate,image,manifest,{0,1})
        path=record/"status.json";original=path.read_bytes();status=json.loads(original)
        for changed in (dict(status,status="failed"),dict(status,epoch=True),dict(status,schema=True),dict(status,extra=1)):
            path.write_bytes(runner.codec.canonical(changed))
            with self.assertRaises(ValueError):runner.inspect_capture(candidate,"1"*64,"2"*64,{0,1})
        path.write_bytes(original);(record/"settings.json").write_bytes(b"{}\n")
        with self.assertRaises(ValueError):runner.inspect_capture(candidate,"1"*64,"2"*64,{0,1})

    def candidate(self):
        candidate=self.root/"owned";candidate.mkdir();(candidate/"saves").mkdir()
        (candidate/"mmx6-runtime.exe").write_bytes(b"synthetic image never executed")
        (candidate/"preparation.json").write_bytes(b"{}")
        (candidate/"environment.json").write_text(json.dumps(dict(TEMP=str(candidate/"temp"))))
        return candidate

    def owned_run(self,candidate,observer,*,quit_error=False,ownership=True):
        process=Mock(pid=123);process.poll.return_value=None
        row=runner.debug.parse_diagnostic(diagnostic());commands=[];held=[0,0];active=[False,False]
        def request(command,**fields):
            commands.append((command,fields))
            if command=="set_input":
                seat=fields["port"]-1;held[seat]=int(fields["buttons"],0)^0xFFFF;active[seat]=True
            elif command=="clear_input":active[fields["port"]-1]=False
            elif command=="pad_status":
                seat=fields["port"]-1;return pad(seat,held[seat],active[seat])
            elif command=="read_ram":return dict(hex="0a00")
            elif command=="netplay_status":return dict(ok=True,active=0,rollback=0,desync=0)
            elif command=="quit":
                process.poll.return_value=0
                if quit_error:raise runner.debug.DebugError("bad quit ACK")
            else:self.fail("Unexpected command: "+command)
            return dict(ok=True)
        report={}
        with patch.object(runner.host,"require_windows"),patch.object(runner.host,"reserve"), \
                patch.object(runner.baseline,"candidate_environment",return_value={}), \
                patch.object(runner.baseline,"owns_listener",return_value=ownership), \
                patch.object(runner.subprocess,"Popen",return_value=process)as launch, \
                patch.object(runner.debug.DebugClient,"request",side_effect=request), \
                patch.object(runner.AudioHostRoute,"sample",return_value=row), \
                patch.object(runner.host,"native_capture_started",return_value=True), \
                patch.object(runner.audio,"jump_overlap_smoke",side_effect=observer):
            try:
                runner.run_owned(candidate,12345,.01,1,report,{},expected_image=runner.preparation.sha256(candidate/"mmx6-runtime.exe"),
                    first_seat=1,max_attempts=2,audio_timeout=10)
            except Exception as error:report["caught_error"]=str(error)
        return report,process,commands,launch

    def test_owned_runner_uses_host_only_hidden_muted_and_clears_both_slots(self):
        candidate=self.candidate()
        def observer(ctx,contract,**options):
            self.assertEqual(ctx["mode"],"local");self.assertEqual(ctx["input_path"],"published_host")
            self.assertEqual(options,dict(first_seat=1,max_attempts=2,timeout=10))
            return dict(status=runner.INCONCLUSIVE)
        report,process,commands,launch=self.owned_run(candidate,observer)
        self.assertEqual(report["status"],runner.INCONCLUSIVE)
        self.assertEqual(report["cleanup"],dict(shutdown="graceful_owned_debug",exit_code=0))
        self.assertTrue(report["existing_private_cards_unchanged"])
        self.assertEqual([f for c,f in commands if c=="clear_input"],[dict(layer="host",port=1),dict(layer="host",port=2)])
        self.assertEqual(set(c for c,f in commands),{"set_input","pad_status","clear_input","read_ram","netplay_status","quit"})
        self.assertIn("--hidden-window",launch.call_args.args[0]);self.assertIn("--seal-interpreted-overlays",launch.call_args.args[0])
        self.assertEqual(launch.call_args.kwargs["env"]["SDL_AUDIODRIVER"],"dummy")
        process.terminate.assert_not_called()

    def test_observer_failure_preserves_prefix_and_still_clears_selected_host_slots(self):
        candidate=self.candidate()
        def observer(ctx,*args,**options):
            ctx["report"]["jump_audio"]=[dict(error="synthetic sample truncation")]
            raise runner.debug.DebugError("synthetic sample truncation")
        report,process,commands,_=self.owned_run(candidate,observer)
        self.assertIn("sample truncation",report["caught_error"])
        self.assertEqual(report["jump_audio"][0]["error"],"synthetic sample truncation")
        self.assertEqual([f["port"]for c,f in commands if c=="clear_input"],[1,2])
        self.assertEqual(report["cleanup"]["shutdown"],"graceful_owned_debug")

    def test_bad_quit_ack_is_failure_even_when_owned_process_exits_zero(self):
        report,process,_,_=self.owned_run(self.candidate(),lambda *a,**k:dict(status="comparison_failed"),quit_error=True)
        self.assertEqual(report["status"],"failed_owned_cleanup")
        self.assertIn("bad quit ACK",report["cleanup"]["quit_protocol_error"]["message"])
        self.assertEqual(report["cleanup"]["exit_code"],0);process.terminate.assert_not_called()

    def test_private_card_mutation_is_retained_and_fails(self):
        candidate=self.candidate();card=candidate/"saves/card1.mcd";card.write_bytes(b"synthetic private original")
        def observer(*args,**kwargs):card.write_bytes(b"synthetic changed private card");return dict(status="comparison_failed")
        report,_,_,_=self.owned_run(candidate,observer)
        self.assertEqual(report["status"],"failed_private_cards")
        self.assertFalse(report["existing_private_cards_unchanged"])
        self.assertNotEqual(report["cards_before"],report["cards_after"])

    def test_foreign_listener_receives_no_commands_and_owned_process_alone_is_stopped(self):
        candidate=self.candidate();process=Mock(pid=123);process.poll.return_value=None
        def waited(timeout):process.poll.return_value=0
        process.wait.side_effect=waited;report={}
        with patch.object(runner.host,"require_windows"),patch.object(runner.host,"reserve"), \
                patch.object(runner.baseline,"candidate_environment",return_value={}), \
                patch.object(runner.baseline,"owns_listener",return_value=False), \
                patch.object(runner.subprocess,"Popen",return_value=process), \
                patch.object(runner.debug.DebugClient,"request")as request:
            with self.assertRaises(runner.debug.DebugError):
                runner.run_owned(candidate,12345,.001,1,report,{},expected_image=runner.preparation.sha256(candidate/"mmx6-runtime.exe"),
                    first_seat=0,max_attempts=1,audio_timeout=1)
        request.assert_not_called();process.terminate.assert_not_called()
        self.assertIn("quit_protocol_error",report["cleanup"])
        self.assertEqual(report["status"],"failed_owned_cleanup")

    def test_source_preflight_failure_keeps_report_and_refuses_output_reuse_without_launch(self):
        output=self.root/"receipt"
        argv=["--build",str(self.root/"build"),"--source",str(self.root/"source"),"--disc",str(self.root/"disc.bin"),
              "--original-exe",str(self.root/"original.exe"),"--output",str(output),
              "--expected-exe-sha256","1"*64,"--expected-manifest-sha256","2"*64]
        args=runner.parser().parse_args(argv)
        with patch.object(runner.host,"require_windows"),patch.object(runner.audio,"build_contract",return_value={}), \
                patch.object(runner.subprocess,"Popen")as launch:
            report=runner.run(args)
            self.assertEqual(report["status"],"failed_setup")
            self.assertIn("reproduce",report["error"]["message"])
            self.assertEqual(json.loads((output/"qualification.json").read_text()),report)
            self.assertEqual((output/"runner-source.py").read_bytes(),Path(runner.__file__).read_bytes())
            before=(output/"qualification.json").read_bytes()
            with self.assertRaisesRegex(ValueError,"Output exists"):runner.run(args)
            self.assertEqual((output/"qualification.json").read_bytes(),before)
        launch.assert_not_called()

    def test_observer_exception_still_validates_finalized_capture_without_hiding_original_error(self):
        contract=json.loads((Path(runner.audio.__file__).resolve().parents[1]/"docs/COOP_JUMP_AUDIO_CONTRACT.json").read_text())
        def prepare(build,source,candidate,*args,**kwargs):candidate.mkdir()
        def failed_observer(candidate,port,boot,progress,native,*args,**kwargs):
            native.update(cleanup=dict(shutdown="graceful_owned_debug",exit_code=0),existing_private_cards_unchanged=True,
                          accepted_windows=[dict(seat=0,pressed=runner.audio.CROSS,label="audio-first-jump")],
                          jump_audio=[dict(status="failed_setup",error="native predicate refused")])
            raise runner.debug.DebugError("original native predicate refused")
        for index,post_error in enumerate((False,True)):
            argv=["--build",str(self.root/"build"),"--source",str(self.root/"source"),"--disc",str(self.root/"disc.bin"),
                  "--original-exe",str(self.root/"original.exe"),"--output",str(self.root/f"postrun-{index}"),
                  "--expected-exe-sha256","1"*64,"--expected-manifest-sha256","2"*64]
            args=runner.parser().parse_args(argv)
            with patch.object(runner.host,"require_windows"),patch.object(runner.audio,"build_contract",return_value=contract), \
                    patch.object(runner.host,"verify_expected_image"),patch.object(runner.preparation,"prepare",side_effect=prepare), \
                    patch.object(runner.host,"configure_two_digital_slots"), \
                    patch.object(runner.manifests,"validate_build_manifest",return_value=dict(declared_sha256="2"*64)), \
                    patch.object(runner,"validate_sources",return_value={}),patch.object(runner,"verify_prepared_originals",return_value={}), \
                    patch.object(runner,"run_owned",side_effect=failed_observer), \
                    patch.object(runner,"inspect_capture",side_effect=ValueError("postrun truncation")if post_error else None,
                                 return_value=dict(events=5844,natives=4096,p2_reads=1748))as inspect, \
                    patch.object(runner.subprocess,"Popen")as launch:
                report=runner.run(args)
            inspect.assert_called_once_with(args.output/"candidate","1"*64,"2"*64,{0})
            launch.assert_not_called()
            self.assertEqual(report["status"],"failed_setup")
            self.assertEqual(report["error"]["message"],"original native predicate refused")
            if post_error:
                self.assertEqual(report["postrun_error"]["message"],"postrun truncation")
                self.assertNotIn("capture",report)
            else:
                self.assertEqual(report["capture"]["events"],5844)
                self.assertTrue(report["checks"]["finalized_native_input_capture_and_owned_cleanup"])


if __name__=="__main__":unittest.main()
