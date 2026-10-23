"""Pure offline reentry runner/input/lifecycle seams; no process or game."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import coop_debug as debug
import mmx6_coop_native_reentry as helper
import qualify_mmx6_coop_native_reentry as runner


def args(**changed):
    values=dict(candidate=None,output=None,build=None,source=None,disc=None,original_disc=Path("original.bin"),
                expected_exe_sha256="a"*64,route="new_game",port=24899,timeout=240,progress_timeout=12,reentry_timeout=180)
    values.update(changed);return SimpleNamespace(**values)


class ReentryOptionTests(unittest.TestCase):
    identity=["--original-disc","original.bin","--expected-exe-sha256","a"*64,"--route","current_data"]
    def parse(self,*options):
        parser=runner.make_parser();selected=parser.parse_args(list(options));runner.validate_options(parser,selected);return selected
    def rejected(self,*options):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.parse(*options)

    def test_explicit_fresh_candidate_raw_source_route_and_hash_required(self):
        selected=self.parse("--candidate","fresh",*self.identity)
        self.assertEqual(selected.port,24899);self.assertEqual(selected.reentry_timeout,180)
        self.assertEqual(selected.route,"current_data")
        self.assertEqual(self.parse("--candidate","fresh",*self.identity,"--route","new_game").route,"new_game")
        for flag in ("--original-disc","--expected-exe-sha256","--route"):
            options=self.identity.copy();at=options.index(flag);del options[at:at+2]
            self.rejected("--candidate","fresh",*options)
        self.rejected("--candidate","fresh",*self.identity,"--route","card_load")
        self.rejected("--candidate","fresh",*self.identity,"--original-disc","runtime.cue")
        self.rejected("--candidate","fresh",*self.identity,"--netplay")

    def test_build_staging_and_all_deadlines_are_bounded_without_unused_options(self):
        self.rejected("--build","build",*self.identity)
        self.parse("--build","build","--source","frozen-source","--disc","runtime.cue","--output","fresh",*self.identity)
        for flag in ("--source","--disc","--output"):
            self.rejected("--candidate","fresh",*self.identity,flag,"unused")
        for flag,value in (("--expected-exe-sha256","A"*64),("--port","0"),("--timeout","nan"),
                           ("--progress-timeout","inf"),("--reentry-timeout","nan"),("--reentry-timeout","241"),
                           ("--reentry-timeout","6"),("--window-frames","30")):
            self.rejected("--candidate","fresh",*self.identity,flag,value)


class PersistentInputTests(unittest.TestCase):
    def test_original_ports_active_low_persistent_frames_and_neutral_without_clock_reads(self):
        control=Mock(return_value={"status":"ok"});report={};source=runner.PersistentNativeInput(control,report)
        source.set_input(0,8);source.set_input(1,0x4000);source.set_input(0,0);source.set_input(1,0)
        self.assertEqual([(c.args,c.kwargs) for c in control.call_args_list],[
            (("press",),dict(port=1,buttons=0xFFF7,frames=0)),
            (("press",),dict(port=2,buttons=0xBFFF,frames=0)),
            (("clear_input",),dict(port=1)),(("clear_input",),dict(port=2))])
        self.assertTrue(all(r["status"]=="rpc_completed" for r in report["persistent_native_input"]))
        self.assertTrue(all("accepted" not in r for r in report["persistent_native_input"]))
        self.assertTrue(all(r["input_path"]=="offline_native" for r in report["persistent_native_input"]))

    def test_invalid_masks_and_listener_refusal_cannot_be_reported_as_input_acceptance(self):
        control=Mock(side_effect=debug.DebugError("owned listener no longer matches"));report={}
        source=runner.PersistentNativeInput(control,report)
        for seat,bits in ((True,8),(2,8),(0,-1),(1,65536),(0,True)):
            with self.assertRaises(ValueError):source.set_input(seat,bits)
        control.assert_not_called()
        with self.assertRaisesRegex(debug.DebugError,"owned listener"):source.set_input(0,8)
        self.assertEqual(report["persistent_native_input"][0]["status"],"rpc_failed")


class ReentryExerciseTests(unittest.TestCase):
    def invoke(self,helper_call,*,cards=None,control=None):
        report={};adapter=Mock();control=control or Mock(return_value={"status":"ok"})
        with patch.object(runner.menu_runner,"OfflineMenuAdapter",return_value=adapter), \
                patch.object(runner,"card_hashes",side_effect=cards or [{"private.mcd":"before"},{"private.mcd":"before"}]), \
                patch.object(helper,"native_reentry_smoke",side_effect=helper_call):
            try:runner.make_exercise(args(),Path("private"),dict(exe_sha256="a"*64),{})(control,None,Path("output"),report)
            except Exception as error:return report,adapter,control,error
        return report,adapter,control,None

    def test_native_helper_gets_original_persistent_source_and_gameplay_adapter_separately(self):
        def completed(ctx,**fields):
            self.assertEqual(ctx["input_path"],"offline_native")
            self.assertEqual(fields,dict(original_disc=Path("original.bin"),expected_exe_sha256="a"*64,
                route="new_game",timeout=12,reentry_timeout=180))
            self.assertIsInstance(ctx["set_input"].__self__,runner.PersistentNativeInput)
            ctx["set_input"](0,8);ctx["set_input"](0,0)
            return dict(status=helper.SUCCESS,checks=dict(source_native_reentry=True))
        report,adapter,control,error=self.invoke(completed)
        self.assertIsNone(error);adapter.settle_idle.assert_called_once()
        adapter.wait_counter.assert_not_called();adapter.transport_window.assert_not_called()
        self.assertEqual(control.call_args_list[0].kwargs,dict(port=1,buttons=0xFFF7,frames=0))
        self.assertEqual([c.kwargs for c in control.call_args_list[-2:]],[dict(port=1),dict(port=2)])
        self.assertTrue(all(report["checks"].values()))

    def test_empty_current_data_failed_case_remains_setup_failure_before_any_quit_press(self):
        def refused(ctx,**fields):
            ctx["report"].setdefault("native_reentry",[]).append(dict(status="failed_setup",error="empty current data",inputs=[]))
            raise helper.ReentryError("Current-data header is empty; refused before any Quit input")
        report,adapter,control,error=self.invoke(refused)
        self.assertIsInstance(error,debug.DebugError)
        self.assertIn("empty; refused",str(error))
        self.assertEqual(report["native_reentry"][0]["status"],"failed_setup")
        self.assertEqual(report["error_type"],"ReentryError")
        self.assertFalse(report["checks"]["native_reentry_automated_case_completed"])
        self.assertEqual([c.args for c in control.call_args_list],[("clear_input",),("clear_input",)])

    def test_failure_while_held_always_clears_both_owned_ports_without_confirmation(self):
        def failed(ctx,**fields):
            ctx["set_input"](0,0x4000)
            ctx["report"].setdefault("native_reentry",[]).append(dict(status="failed_behavior",inputs=["retained original Cross"]))
            raise helper.ReentryError("Original native arrival never became fresh")
        report,adapter,control,error=self.invoke(failed)
        self.assertIsInstance(error,debug.DebugError)
        self.assertEqual([c.args[0] for c in control.call_args_list],["press","clear_input","clear_input"])
        self.assertEqual(report["native_reentry"][0]["status"],"failed_behavior")
        self.assertTrue(report["checks"]["owned_input_clear_requests_completed"])

    def test_secondary_clear_and_card_errors_do_not_replace_original_native_failure(self):
        def failed(ctx,**fields):raise helper.ReentryError("original source-bound failure")
        control=Mock(side_effect=debug.DebugError("owned endpoint unavailable"))
        report,adapter,control,error=self.invoke(failed,cards=[{},OSError("private-card hash unavailable")],control=control)
        self.assertIn("original source-bound failure",str(error))
        self.assertEqual(report["error"],"original source-bound failure")
        self.assertEqual(len(report["persistent_input_cleanup_errors"]),2)
        self.assertEqual(report["private_card_read_error"],"private-card hash unavailable")
        self.assertFalse(report["checks"]["native_private_cards_unchanged"])

    def test_card_mutation_revokes_an_otherwise_completed_native_case(self):
        report,adapter,control,error=self.invoke(lambda *args,**kwargs:dict(status=helper.SUCCESS,checks=dict(native=True)),
            cards=[{"private.mcd":"before"},{"private.mcd":"after"}])
        self.assertIsInstance(error,debug.DebugError)
        self.assertTrue(report["checks"]["native_reentry_automated_case_completed"])
        self.assertFalse(report["checks"]["native_private_cards_unchanged"])
        self.assertIn("private-card verification",report["error"])


class ReentryRunnerLifecycleTests(unittest.TestCase):
    def test_bad_build_hash_is_refused_before_prepare_or_baseline_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(helper,"load_sources",return_value=dict(original={})), \
                    patch.object(runner.preparation,"sha256",return_value="b"*64), \
                    patch.object(runner.preparation,"prepare") as prepare,patch.object(runner.baseline,"run") as launch:
                with self.assertRaisesRegex(ValueError,"expected SHA256"):
                    runner.run(args(build=root/"build",source=root/"source",disc=root/"runtime.cue",output=root/"new"))
            prepare.assert_not_called();launch.assert_not_called()

    def test_source_pristine_and_loader_rejection_prevent_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for stage in ("source","pristine","loader"):
                with self.subTest(stage=stage),patch.object(helper,"load_sources",return_value=dict(original={})) as source, \
                        patch.object(runner.menu_runner,"pristine_candidate",return_value=dict(exe_sha256="a"*64)) as pristine, \
                        patch.object(runner.quit_runner,"require_default_loader",return_value={}) as loader, \
                        patch.object(runner.baseline,"run") as launch:
                    {"source":source,"pristine":pristine,"loader":loader}[stage].side_effect=ValueError("retained setup guard")
                    with self.assertRaisesRegex(ValueError,"setup guard"):runner.run(args(candidate=root))
                    launch.assert_not_called()

    def test_baseline_owned_cleanup_report_original_failure_and_environment_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/"temp").mkdir();prefix=sys.pycache_prefix
            def stopped(candidate,*pos,**keywords):
                self.assertNotIn("PSX_NETPLAY",os.environ);self.assertNotIn("RNET_SESSION",os.environ)
                self.assertEqual(pos,(24899,240,False));self.assertTrue(callable(keywords["exercise"]))
                (candidate/"baseline").mkdir()
                (candidate/"baseline/qualification.json").write_text('{"status":"failed","shutdown":"quit_ack_exit"}\n')
                return dict(status="failed",shutdown="quit_ack_exit",returncode=0,
                    exercise=dict(checks=dict(native_reentry_automated_case_completed=False),
                                  native_reentry=[dict(status="failed_setup",error="empty native buffer")]))
            try:
                with patch.dict(os.environ,{"PSX_NETPLAY":"1","RNET_SESSION":"foreign"}), \
                        patch.object(helper,"load_sources",return_value=dict(original={"archive_sha256":"pinned"})), \
                        patch.object(runner.menu_runner,"pristine_candidate",return_value=dict(exe_sha256="a"*64)), \
                        patch.object(runner.quit_runner,"require_default_loader",return_value=dict(policy="default_seamless_loading")), \
                        patch.object(runner.baseline,"run",side_effect=stopped):
                    result=runner.run(args(candidate=root))
                    self.assertEqual(os.environ["PSX_NETPLAY"],"1");self.assertEqual(os.environ["RNET_SESSION"],"foreign")
            finally:sys.pycache_prefix=prefix
            self.assertEqual(result["status"],"failed");self.assertFalse(result["automated_checks_passed"])
            self.assertEqual(result["shutdown"],"quit_ack_exit");self.assertEqual(result["returncode"],0)
            self.assertEqual(result["original_baseline"]["status"],"failed")
            self.assertEqual((root/"baseline/qualification.json").read_text(),'{"status":"failed","shutdown":"quit_ack_exit"}\n')
            self.assertEqual(json.loads((root/"qualification.json").read_text())["exercise"]["native_reentry"][0]["status"],"failed_setup")
            for name in ("runner-source.py","native-reentry-helper-source.py","native-reentry-menu-source.py"):
                self.assertTrue((root/name).is_file())


if __name__=="__main__":unittest.main()
