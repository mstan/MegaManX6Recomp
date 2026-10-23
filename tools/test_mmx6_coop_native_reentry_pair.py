"""Pure owned-pair/source/input/failure seams; no game, socket or launch."""
import io
import json
import re
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import mmx6_coop_native_reentry_pair as adapter
import qualify_mmx6_coop_pair as runner
import qualify_mmx6_coop_jump_audio as source_validation
import coop_host_profile as profiles


def status(bits=0,armed=True):
    return dict(host_input_slots=2,host_port=1,host_layer=armed,host_buttons=hex(0xFFFF^bits),
        host_axes=[128]*4,slot0=dict(connected=True,analog=False,type=0),slot1=dict(connected=True,analog=False,type=0),
        override=-1,override_p2=-1,override_pad_type=-1,override_axes_valid=False)


class InputClient:
    def __init__(self):
        self.requests=[];self.bits=0;self.armed=False;self.fail_neutral=False
        self.reentry_route=adapter.Route(self.request,{})
    def request(self,command,**fields):
        self.requests.append((command,fields))
        if command=="set_input":
            bits=0xFFFF^int(fields["buttons"],0)
            if self.fail_neutral and not bits:raise OSError("neutral endpoint refused")
            self.bits=bits;self.armed=True;return dict(ok=True)
        if command=="clear_input":self.bits=0;self.armed=False;return dict(ok=True)
        if command=="pad_status":return status(self.bits,self.armed)
        raise AssertionError("Unexpected non-host control: "+command)
    def host_input(self,bits=0):return self.reentry_route.set(0,bits)


class SourceBindingTests(unittest.TestCase):
    def test_only_exact_original_single_track_zero_index_is_admitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);raw=root/"original.bin";raw.write_bytes(b"source fixture")
            other=root/"other.bin";other.write_bytes(raw.read_bytes());cue=root/"runtime.cue"
            valid='FILE "original.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n'
            cue.write_text(valid)
            receipt=adapter.bind_original_disc(cue,raw)
            self.assertEqual(receipt["original_raw_bin"],str(raw.resolve()))
            self.assertEqual(receipt["index"],"00:00:00")
            for bad in (valid.replace("original.bin","other.bin"),valid.replace("00:00:00","00:00:01"),
                        valid.replace("MODE2/2352","MODE1/2048"),valid+' TRACK 02 AUDIO\n',
                        valid+'FILE "other.bin" BINARY\n',valid.replace('"original.bin"','original.bin')):
                cue.write_text(bad)
                with self.assertRaises(ValueError):adapter.bind_original_disc(cue,raw)

    def test_fresh_topology_and_exact_config_sources_are_prepared_before_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/"saves").mkdir();raw=root/"original.bin";raw.write_bytes(b"fixture")
            cue=root/"runtime.cue";cue.write_text('FILE "original.bin" BINARY\nTRACK 01 MODE2/2352\nINDEX 01 00:00:00\n')
            exe=root/"SLUS_013.95";exe.write_bytes(b"original fixture")
            settings='[video]\nrenderer="opengl"\naspect_ratio="4:3"\nrewind=false\n[controller]\np1_device = "keyboard"\np2_device = "none"\n'
            # Use the real title layout: memcard_dir belongs to [runtime].
            # A handcrafted [game] fixture masked the actual staging failure.
            config=(Path(__file__).resolve().parents[1]/"game.toml").read_text(encoding="utf-8")
            for key,value in (("exe",exe),("disc",cue),("memcard_dir",root/"saves")):
                config,count=re.subn(r'(?m)^'+key+r'\s*=.*$',lambda _:key+' = '+json.dumps(value.as_posix()),config)
                self.assertEqual(count,1)
            (root/"game.toml").write_text(config,encoding="utf-8");(root/"settings.toml").write_text(settings)
            with patch.object(adapter.helper.content,"EXE_SHA256",adapter.preparation.sha256(exe)):
                receipt=adapter.prepare_profile(root,cue,raw)
                self.assertEqual(receipt["local_input_port"],1)
                self.assertIn('p2_mode = "digital"',(root/"settings.toml").read_text())
                faster,count=re.subn(r'(?m)^disc_speed\s*=.*$','disc_speed = "2x"',config)
                self.assertEqual(count,1)
                (root/"settings.toml").write_text(settings);(root/"game.toml").write_text(faster,encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"default loader"):adapter.prepare_profile(root,cue,raw)
                (root/"game.toml").write_text(re.sub(r'(?m)^memcard_dir\s*=.*\n','',config),encoding="utf-8")
                (root/"settings.toml").write_text(settings)
                with self.assertRaisesRegex(ValueError,"private-card binding"):adapter.prepare_profile(root,cue,raw)


class PublishedRouteTests(unittest.TestCase):
    def test_route_installation_does_not_reset_pair_checks_or_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);clients=[InputClient(),InputClient()];handles=[]
            for seat in (0,1):(root/f"peer-{seat}/logs").mkdir(parents=True)
            report=dict(checks=dict(already_verified=True),resolved_state_crc=["retained"],observations=["prior"])
            try:adapter.install_routes(clients,[Mock(pid=1001),Mock(pid=1002)],[24901,24902],report,root,handles)
            finally:
                for handle in handles:handle.close()
            self.assertEqual(report["checks"],dict(already_verified=True))
            self.assertEqual(report["observations"],["prior"])
            self.assertEqual([r["logical_seat"] for r in report["native_reentry_published_routes"]],[0,1])
            self.assertEqual([r["owned_pid"] for r in report["native_reentry_published_routes"]],[1001,1002])
            self.assertEqual([r["debug_port"] for r in report["native_reentry_published_routes"]],[24901,24902])
    def test_two_logical_seats_use_separate_peers_local_port1_with_neutral_axes(self):
        clients=[InputClient(),InputClient()]
        clients[0].host_input(8);clients[1].host_input(0x4000)
        for peer,bits in zip(clients,(8,0x4000)):
            command,fields=peer.requests[0]
            self.assertEqual(command,"set_input")
            self.assertEqual(fields,dict(layer="host",port=1,buttons=hex(0xFFFF^bits),lx=128,ly=128,rx=128,ry=128,lt=0,rt=0))
            peer.host_input(0);peer.reentry_route.clear()
            self.assertEqual(peer.requests[-2],("clear_input",dict(layer="host",port=1)))
        for client in clients:
            with self.assertRaises(ValueError):client.reentry_route.set(1,8)
            self.assertTrue(all(command in ("set_input","pad_status","clear_input") for command,_ in client.requests))

    def test_malformed_ack_or_lost_ownership_never_falls_back_to_sio(self):
        for mutate in (lambda r:r.update(host_axes=[128,127,128,128]),
                       lambda r:r.update(host_buttons="0xffff"),lambda r:r["slot1"].update(connected=False),
                       lambda r:r.update(override_p2=0)):
            bad=status(8);mutate(bad);control=Mock(side_effect=[dict(ok=True),bad])
            route=adapter.Route(control,{})
            with self.assertRaises(ValueError):route.set(0,8)
            self.assertEqual([c.args[0] for c in control.call_args_list],["set_input","pad_status"])
        process=Mock(pid=1234);process.poll.return_value=None;client=InputClient();stream=io.StringIO()
        with patch.object(adapter.host.baseline,"owns_listener",return_value=False):
            route=adapter.Route(adapter.host.control_for(process,24901,client,stream),{})
            with self.assertRaisesRegex(Exception,"debug listener"):route.set(0,8)
        self.assertFalse(client.requests)


class ExerciseTests(unittest.TestCase):
    def context(self,root):
        clients=[InputClient(),InputClient()]
        report=dict(candidate_exe_sha256="a"*64,peers=[dict(preparation=dict(exe_sha256="a"*64)) for _ in range(2)],
            checks={k:True for k in ("host_profile_settled_before_guest","declared_build_manifest_bound_to_staged_images",
                "default_resident_loader_committed","native_reentry_original_source_bound","native_reentry_declared_sources_match")},
            resolved_state_crc=["actual resolved sample"],host_profile_startup=dict(profile="fixed actual profile"),
            host_profile_build_manifest=dict(sha256="b"*64),native_reentry_prepared=[{},{}],native_reentry_original={})
        return dict(clients=clients,report=report,output=root,debug=Mock(),both=lambda fn:[fn(0),fn(1)],
            network=Mock(),transport_window=Mock(),matched=Mock(),native_advance=Mock())
    def exercise(self,ctx):
        return adapter.exercise(ctx,expected_sha="a"*64,original_disc=Path("original.bin"),plan=dict(scope="same_machine"))

    def test_original_persistent_controls_and_paused_transport_reach_existing_helper(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(Path(temporary))
            def completed(case,**fields):
                self.assertEqual(fields,dict(original_disc=Path("original.bin"),expected_exe_sha256="a"*64,
                    route="new_game",timeout=12,reentry_timeout=180))
                self.assertEqual(case["input_path"],"published_host");self.assertTrue(case["same_machine"])
                case["set_input"](0,8);case["set_input"](0,0)
                case["hold"](1,0x40,4,"P2 menu Down")
                case["debug"].capture_present(ctx["clients"][0],Path(temporary)/"nested/personal-menu/paused.png")
                self.assertTrue((Path(temporary)/"nested/personal-menu").is_dir())
                return dict(status=adapter.helper.SUCCESS,checks=dict(complete_actual_helper_fixture=True))
            with patch.object(adapter.helper,"native_reentry_smoke",side_effect=completed):self.exercise(ctx)
            self.assertTrue(all(ctx["report"]["checks"].values()))
            self.assertEqual([c.args for c in ctx["transport_window"].call_args_list],[(4,),(5,)])
            ctx["native_advance"].assert_not_called() # Paused holds never use the world clock.

    def test_missing_evidence_or_route_rejects_before_any_native_input(self):
        for mutate in (lambda c:c["report"]["checks"].update(native_reentry_declared_sources_match=False),
                       lambda c:c["report"].update(resolved_state_crc=[]),
                       lambda c:c["report"]["peers"][1]["preparation"].update(exe_sha256="b"*64),
                       lambda c:setattr(c["clients"][1],"reentry_route",None)):
            ctx=self.context(Path("owned"));mutate(ctx)
            with patch.object(adapter.helper,"native_reentry_smoke") as invoke,self.assertRaises(ValueError):self.exercise(ctx)
            invoke.assert_not_called();self.assertTrue(all(not c.requests for c in ctx["clients"]))

    def test_partial_native_failure_survives_both_neutral_and_card_cleanup_errors(self):
        ctx=self.context(Path("owned"))
        def failure(case,**fields):
            case["set_input"](0,8);ctx["clients"][0].fail_neutral=True
            ctx["report"]["native_reentry"]=[dict(status="failed_behavior",error="native arrival never fresh")]
            raise adapter.helper.ReentryError("native arrival never fresh")
        with patch.object(adapter,"cards",side_effect=[[{"private.mcd":"before"},{}],OSError("card unavailable")]), \
                patch.object(adapter.helper,"native_reentry_smoke",side_effect=failure):
            with self.assertRaisesRegex(adapter.helper.ReentryError,"arrival never fresh"):self.exercise(ctx)
        self.assertEqual(ctx["report"]["native_reentry"][0]["status"],"failed_behavior")
        self.assertFalse(ctx["report"]["checks"]["native_reentry_private_cards_unchanged"])
        self.assertEqual(len(ctx["report"]["native_reentry_input_cleanup_errors"]),1)
        self.assertEqual(ctx["clients"][1].bits,0)

    def test_card_change_or_incomplete_case_revokes_success(self):
        for completed in (True,False):
            ctx=self.context(Path("owned"))
            with patch.object(adapter,"cards",side_effect=[[{},{}],[{"changed.mcd":"new"},{}]]), \
                    patch.object(adapter.helper,"native_reentry_smoke",return_value=dict(status=adapter.helper.SUCCESS,
                        checks=dict(check=completed))):
                with self.assertRaises(adapter.helper.ReentryError):self.exercise(ctx)


class BeforeLaunchTests(unittest.TestCase):
    def test_original_binding_failure_prevents_staging_and_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);build=root/"build";build.mkdir();(build/"mmx6-runtime.exe").write_bytes(b"fixture")
            args=runner.make_parser().parse_args(["--tools-root",str(Path(__file__).parent),"--source",str(root),
                "--build",str(build),"--disc",str(root/"runtime.cue"),"--out",str(root/"unused"),
                "--native-reentry","new_game"])
            with patch.object(adapter,"bind_original_disc",side_effect=ValueError("raw source mismatch")), \
                    patch.object(adapter.preparation,"prepare") as prepare,patch.object(runner.subprocess,"Popen") as launch:
                with self.assertRaisesRegex(ValueError,"raw source mismatch"):runner.run(args)
            prepare.assert_not_called();launch.assert_not_called()

    def test_manifest_or_actual_source_failure_is_retained_before_any_popen(self):
        for failure in ("manifest","source"):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);build=root/"build";build.mkdir();image=b"fixture";(build/"mmx6-runtime.exe").write_bytes(image)
                args=runner.make_parser().parse_args(["--tools-root",str(Path(__file__).parent),"--source",str(root),
                    "--build",str(build),"--disc",str(root/"runtime.cue"),"--out",str(root/"output"),
                    "--original-disc",str(root/"original.bin"),"--native-reentry","new_game","--require-host-profile",
                    "--expected-host-profile","mmx6.win64-clang22.loopback","--expected-host-profile-revision","2",
                    "--require-state-crc","--expected-exe-sha256",adapter.preparation.sha256(build/"mmx6-runtime.exe")])
                def prepare(_build,_source,directory,_disc,*,automated):
                    self.assertTrue(automated)
                    for name in ("logs","saves","mods"):(directory/name).mkdir(parents=True,exist_ok=True)
                    (directory/"mmx6-runtime.exe").write_bytes(image);(directory/"environment.json").write_text(json.dumps(environment))
                    return dict(exe_sha256=args.expected_exe_sha256,source_card=None)
                environment={k:str(root/"private") for k in ("TEMP","TMP","LOCALAPPDATA","APPDATA", "PSX_RESIDENT_CACHE","PSX_OVERLAY_CACHE_DIR")}
                environment["PSX_OVERLAY_AUTOCOMPILE_OFF"]="1"
                with patch.object(adapter,"bind_original_disc",return_value=dict(cue="fixed")), \
                        patch.object(adapter.helper,"load_sources",return_value=dict(original={})), \
                        patch.object(adapter.preparation,"prepare",side_effect=prepare), \
                        patch.object(adapter,"prepare_profile",return_value={}), \
                        patch.object(adapter.host.baseline,"candidate_environment",return_value=environment), \
                        patch.object(profiles,"validate_build_manifest",side_effect=ValueError("manifest refused") if failure=="manifest" else None,return_value=dict(sha256="b"*64)), \
                        patch.object(source_validation,"validate_sources",side_effect=ValueError("source refused")) as verify_source, \
                        patch.object(runner.socket,"socket",return_value=Mock()), \
                        patch.object(runner.subprocess,"Popen") as launch:
                    report=runner.run(args)
                launch.assert_not_called()
                if failure=="manifest":verify_source.assert_not_called()
                else:verify_source.assert_called_once()
                self.assertEqual(report["status"],"failed_setup");self.assertIn(failure+" refused",report["error"])
                self.assertTrue((root/"output/qualification.json").is_file())


class FinalCleanupTests(unittest.TestCase):
    def report(self):
        return dict(status="passed",default_intro_qualified=True,default_launch_qualified=True,checks={},
            native_reentry_private_cards_before=[{},{}],peers=[dict(shutdown="graceful_owned_debug",exit_code=0) for _ in range(2)])
    def test_only_both_owned_ack_exit_zero_and_unchanged_cards_keep_success(self):
        report=self.report()
        with patch.object(adapter,"cards",return_value=[{},{}]):adapter.finalize(report,Path("owned"),runtime_ready=True,owned_processes=2)
        self.assertEqual(report["status"],"passed");self.assertTrue(all(report["checks"].values()))
        for mutate in (lambda r:r["peers"][1].update(shutdown="owned_popen_terminated"),
                       lambda r:r["peers"][0].update(exit_code=1),lambda r:r["peers"][0].update(input_release_errors=["refused"]),
                       lambda r:r["peers"][0].update(private_card_error="unreadable")):
            report=self.report();mutate(report);report["error"]="retained native failure"
            with patch.object(adapter,"cards",return_value=[{},{}]):adapter.finalize(report,Path("owned"),runtime_ready=True,owned_processes=2)
            self.assertEqual(report["status"],"failed");self.assertFalse(report["default_intro_qualified"])
            self.assertEqual(report["error"],"retained native failure")
    def test_final_card_mutation_read_failure_and_partial_launch_revoke_success(self):
        for result in ([{"new.mcd":"changed"},{}],OSError("final card unreadable")):
            report=self.report()
            with patch.object(adapter,"cards",side_effect=result if isinstance(result,Exception) else None,
                              return_value=result if not isinstance(result,Exception) else None):
                adapter.finalize(report,Path("owned"),runtime_ready=True,owned_processes=2)
            self.assertFalse(report["checks"]["native_reentry_final_private_cards_unchanged"])
            self.assertEqual(report["status"],"failed");self.assertFalse(report["default_intro_qualified"])
        report=self.report()
        with patch.object(adapter,"cards",return_value=[{},{}]):adapter.finalize(report,Path("owned"),runtime_ready=False,owned_processes=1)
        self.assertEqual(report["status"],"failed_setup")


if __name__=="__main__":unittest.main()
