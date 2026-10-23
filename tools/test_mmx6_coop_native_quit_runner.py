"""Pure CLI/owned adapter guards; no process, native runtime or title build."""
from copy import deepcopy
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import coop_debug as debug
import mmx6_coop_native_quit as helper
import mmx6_coop_published_input as published
import qualify_mmx6_coop_native_quit as offline
from qualify_mmx6_coop_pair import exercise_native_quit_pair, same_machine_plan


def peers():
    return [dict(preparation=dict(exe_sha256="a"*64),argv=["candidate.exe","--net-slot",str(seat),
        "--net-input-player","0","--net-bind",f"127.0.0.1:{29901+seat}","--net-peer",f"127.0.0.1:{29902-seat}",
        "--net-delay","3"]) for seat in range(2)]


class QuitRunnerOptions(unittest.TestCase):
    identity=["--original-exe","SLUS_013.95","--expected-exe-sha256","a"*64,
              "--native-quit-scenario","guest_authority"]
    def parse(self,*flags):
        parser=offline.make_parser();args=parser.parse_args(list(flags));offline.validate_options(parser,args)
        return args
    def rejected(self,*flags):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.parse(*flags)

    def test_exact_fresh_candidate_scenario_and_original_source_are_explicit(self):
        args=self.parse("--candidate","fresh",*self.identity)
        self.assertEqual(args.port,24898)
        self.assertIsNone(args.build)
        for flag in ("--original-exe","--expected-exe-sha256","--native-quit-scenario"):
            flags=self.identity.copy();at=flags.index(flag);del flags[at:at+2]
            self.rejected("--candidate","fresh",*flags)
        self.rejected("--candidate","fresh",*self.identity,"--native-quit-scenario","final_quit")

    def test_build_mode_cannot_reuse_or_smuggle_settings_into_candidate(self):
        self.rejected("--build","build",*self.identity)
        self.parse("--build","build","--source","source","--disc","original.cue","--output","fresh",*self.identity)
        for flag in ("--source","--disc","--output"):
            self.rejected("--candidate","fresh",*self.identity,flag,"unused")
        for flag,value in (("--expected-exe-sha256","A"*64),("--port","0"),("--timeout","nan"),
                           ("--progress-timeout","inf"),("--window-frames","5")):
            self.rejected("--candidate","fresh",*self.identity,flag,value)

    def test_live_effect_pages_are_a_separate_explicit_scenario(self):
        args=self.parse("--candidate","fresh",*self.identity,"--native-quit-scenario","p1_pages_cancel_live_effects")
        self.assertEqual(args.native_quit_scenario,"p1_pages_cancel_live_effects")
        self.assertEqual(self.parse("--candidate","fresh",*self.identity).native_quit_scenario,"guest_authority")


class OfflineAdapterProtocolTests(unittest.TestCase):
    def loader(self,root):
        folder=root/"mods/bundled/mmx6.enhancement.seamless-loading/0.1.0";folder.mkdir(parents=True)
        (folder/"manifest.toml").write_text('id="mmx6.enhancement.seamless-loading"\n[[feature]]\nid="seamless-loading"\ndefault_enabled=true\n')
        (root/"mods/state.toml").write_text('format_version=2\n[[package]]\nid="mmx6.local-coop"\nversion="0.0.1"\n[[feature]]\npackage_id="mmx6.local-coop"\nid="prototype"\nenabled=true\n')
        return folder/"manifest.toml"

    def test_default_loader_is_actual_catalog_and_selection_not_a_label(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=self.loader(root)
            self.assertEqual(offline.require_default_loader(root)["policy"],"default_seamless_loading")
            original=manifest.read_text();manifest.write_text(original.replace("true","false"))
            with self.assertRaises(ValueError):offline.require_default_loader(root)
            manifest.write_text(original)
            with (root/"mods/state.toml").open("a") as stream:
                stream.write('\n[[feature]]\npackage_id="mmx6.enhancement.seamless-loading"\nid="seamless-loading"\nenabled=false\n')
            with self.assertRaises(ValueError):offline.require_default_loader(root)

    def test_native_helper_failure_is_wrapped_for_baseline_cleanup_without_losing_case(self):
        args=SimpleNamespace(progress_timeout=12,window_frames=12,native_quit_scenario="guest_authority",
                             original_exe=Path("verified"),expected_exe_sha256="a"*64)
        report={};adapter=Mock();control=Mock()
        def rejected(ctx,**fields):
            self.assertEqual(ctx["input_path"],"offline_native")
            self.assertIs(ctx["hold"],adapter.hold)
            ctx["report"].setdefault("native_quit",[]).append(dict(status="failed_behavior",error="guest admitted"))
            raise helper.NativeQuitError("guest admitted before confirmation")
        with patch.object(offline.menu_runner,"OfflineMenuAdapter",return_value=adapter), \
                patch.object(offline,"card_hashes",return_value={}), \
                patch.object(helper,"native_quit_smoke",side_effect=rejected):
            with self.assertRaisesRegex(debug.DebugError,"guest admitted before confirmation"):
                offline.make_exercise(args,Path("private"),dict(exe_sha256="a"*64),{})(control,None,Path("output"),report)
        adapter.settle_idle.assert_called_once()
        self.assertEqual(report["native_quit"][0]["status"],"failed_behavior")
        self.assertFalse(report["checks"]["native_quit_automated_case_completed"])
        self.assertTrue(report["checks"]["native_private_cards_unchanged"])
        self.assertEqual(report["error_type"],"NativeQuitError")
        control.assert_not_called()  # This adapter does not invent a cleanup/confirm path.

    def test_live_effect_offline_case_receives_the_existing_owned_observed_input(self):
        args=SimpleNamespace(progress_timeout=12,window_frames=12,native_quit_scenario="p1_pages_cancel_live_effects",
                             original_exe=Path("verified"),expected_exe_sha256="a"*64)
        adapter=Mock();report={}
        def inspect(ctx,**fields):
            self.assertIs(ctx["hold_observed"],adapter.hold_observed)
            self.assertEqual(ctx["input_path"],"offline_native")
            self.assertEqual(fields["scenario"],"p1_pages_cancel_live_effects")
            return dict(status=helper.SUCCESS,checks=dict(fixture_callback_contract=True))
        with patch.object(offline.menu_runner,"OfflineMenuAdapter",return_value=adapter), \
                patch.object(offline,"card_hashes",return_value={}), \
                patch.object(helper,"native_quit_smoke",side_effect=inspect):
            offline.make_exercise(args,Path("private"),dict(exe_sha256="a"*64),{})(Mock(),None,Path("output"),report)
        adapter.settle_idle.assert_called_once()

    def test_secondary_card_read_failure_preserves_native_failure(self):
        args=SimpleNamespace(progress_timeout=12,window_frames=12,native_quit_scenario="guest_authority",
                             original_exe=Path("verified"),expected_exe_sha256="a"*64)
        report={}
        with patch.object(offline.menu_runner,"OfflineMenuAdapter"), \
                patch.object(offline,"card_hashes",side_effect=[{},OSError("card verification unavailable")]), \
                patch.object(helper,"native_quit_smoke",side_effect=helper.NativeQuitError("original guest failure")):
            with self.assertRaisesRegex(debug.DebugError,"original guest failure"):
                offline.make_exercise(args,Path("private"),dict(exe_sha256="a"*64),{})(Mock(),None,Path("output"),report)
        self.assertEqual(report["private_card_read_error"],"card verification unavailable")
        self.assertFalse(report["checks"]["native_private_cards_unchanged"])

    def test_offline_runtime_environment_isolated_and_original_failed_receipt_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/"temp").mkdir()
            args=SimpleNamespace(candidate=root,output=None,build=None,original_exe=Path("verified"),
                expected_exe_sha256="a"*64,native_quit_scenario="guest_authority",port=24898,
                timeout=240,progress_timeout=12,window_frames=12)
            def stopped(candidate,*args,**kwargs):
                self.assertNotIn("PSX_NETPLAY",os.environ)
                self.assertNotIn("RNET_SESSION",os.environ)
                (candidate/"baseline").mkdir();(candidate/"baseline/qualification.json").write_text('{"status":"failed"}\n')
                return dict(status="failed",exercise=dict(checks=dict(native_quit_automated_case_completed=False)))
            old_prefix=__import__("sys").pycache_prefix
            try:
                with patch.dict(os.environ,{"PSX_NETPLAY":"1","RNET_SESSION":"foreign"}), \
                        patch.object(helper,"verify_original",return_value={}), \
                        patch.object(offline.menu_runner,"pristine_candidate",return_value=dict(exe_sha256="a"*64)), \
                        patch.object(offline,"require_default_loader",return_value={}), \
                        patch.object(offline.baseline,"run",side_effect=stopped):
                    result=offline.run(args)
                    self.assertEqual(os.environ["PSX_NETPLAY"],"1")
                    self.assertEqual(os.environ["RNET_SESSION"],"foreign")
            finally:__import__("sys").pycache_prefix=old_prefix
            self.assertEqual(result["status"],"failed")
            self.assertFalse(result["automated_checks_passed"])
            self.assertEqual(result["original_baseline"]["status"],"failed")
            self.assertEqual((root/"baseline/qualification.json").read_text(),'{"status":"failed"}\n')


class PairPlanAndPublishedInputTests(unittest.TestCase):
    def test_actual_plan_is_two_cross_linked_numeric_loopback_endpoints(self):
        self.assertEqual(same_machine_plan(peers())["numeric_host"],"127.0.0.1")
        for endpoint in ("localhost:29901","192.168.1.2:29901","[::1]:29901","127.0.0.1:65536"):
            plans=peers();at=plans[0]["argv"].index("--net-bind");plans[0]["argv"][at+1]=endpoint
            with self.assertRaises(ValueError):same_machine_plan(plans)
        plans=peers();at=plans[1]["argv"].index("--net-peer");plans[1]["argv"][at+1]="127.0.0.1:29903"
        with self.assertRaises(ValueError):same_machine_plan(plans)
        for flag,value in (("--net-slot","1"),("--net-input-player","1"),("--net-delay","2")):
            plans=peers();at=plans[0]["argv"].index(flag);plans[0]["argv"][at+1]=value
            with self.assertRaises(ValueError):same_machine_plan(plans)
        plans=peers();plans[0]["argv"].extend(["--net-peer","127.0.0.1:29902"])
        with self.assertRaises(ValueError):same_machine_plan(plans)

    def ctx(self):
        report=dict(candidate_exe_sha256="a"*64,peers=peers(),checks=dict(host_profile_settled_before_guest=True,
            declared_build_manifest_bound_to_staged_images=True,default_resident_loader_committed=True),
            resolved_state_crc=[dict(samples=["retained-resolved-sample"])],
            host_profile_startup=dict(profile="actual verified agreement"),host_profile_build_manifest=dict(sha256="b"*64))
        clients=[Mock(),Mock()]
        return dict(clients=clients,report=report,network=Mock(),transport_window=Mock(),both=Mock(),debug=Mock(),
                    output=Path("private"),matched=Mock(),native_advance=Mock())

    def exercise(self,ctx):
        return exercise_native_quit_pair(ctx,native_quit=helper,published_input=published,original_exe=Path("verified"),
                                         expected_sha="a"*64,scenario="guest_authority")

    def test_missing_actual_evidence_or_image_mismatch_prevents_input(self):
        for mutate in (lambda r:r["checks"].update(default_resident_loader_committed=False),
                       lambda r:r["checks"].update(host_profile_settled_before_guest=False),
                       lambda r:r.update(resolved_state_crc=[]),lambda r:r.update(candidate_exe_sha256="b"*64),
                       lambda r:r["peers"][1]["preparation"].update(exe_sha256="b"*64)):
            ctx=self.ctx();mutate(ctx["report"])
            with patch.object(helper,"native_quit_smoke") as invoke,self.assertRaises(ValueError):self.exercise(ctx)
            invoke.assert_not_called()
            for client in ctx["clients"]:client.host_input.assert_not_called()

    def test_failure_uses_only_original_published_host_and_neutral_not_confirmation(self):
        ctx=self.ctx()
        def rejected(case_ctx,**fields):
            self.assertEqual(case_ctx["input_path"],"published_host")
            self.assertTrue(case_ctx["same_machine"])
            case_ctx["hold"](1,1,4,"actual guest Select")
            ctx["report"].setdefault("native_quit",[]).append(dict(status="failed_behavior"))
            raise helper.NativeQuitError("guest admitted")
        with patch.object(helper,"native_quit_smoke",side_effect=rejected):
            with self.assertRaisesRegex(helper.NativeQuitError,"guest admitted"):self.exercise(ctx)
        self.assertEqual([call.args for call in ctx["clients"][1].host_input.call_args_list],[(1,),(0,)])
        ctx["clients"][0].host_input.assert_not_called()
        for client in ctx["clients"]:client.request.assert_not_called()
        self.assertEqual([call.args for call in ctx["transport_window"].call_args_list],[(4,),(5,)])
        self.assertFalse(ctx["report"]["checks"]["native_quit_automated_case_completed"])
        self.assertEqual(ctx["report"]["native_quit"][0]["status"],"failed_behavior")

    def test_live_effect_pair_receives_observed_host_input_on_the_same_adapter(self):
        ctx=self.ctx()
        def inspect(case_ctx,**fields):
            self.assertEqual(fields["scenario"],"p1_pages_cancel_live_effects")
            self.assertIs(case_ctx["hold_observed"].__self__,case_ctx["hold"].__self__)
            self.assertIsInstance(case_ctx["hold"].__self__,published.PublishedHeldInput)
            self.assertEqual(case_ctx["input_path"],"published_host")
            return dict(status=helper.SUCCESS,checks=dict(fixture_callback_contract=True))
        with patch.object(helper,"native_quit_smoke",side_effect=inspect):
            exercise_native_quit_pair(ctx,native_quit=helper,published_input=published,original_exe=Path("verified"),
                expected_sha="a"*64,scenario="p1_pages_cancel_live_effects")
        for client in ctx["clients"]:client.request.assert_not_called();client.host_input.assert_not_called()


if __name__=="__main__":unittest.main()
