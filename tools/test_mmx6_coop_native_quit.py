"""Pure native Quit evidence/ownership fixtures; no games or ledger results."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import mmx6_coop_native_quit as quit_ui


def row(tick=10, *, page=0, choice=0, owner=0):
    players=[dict(active=1,character=i,state=1,action=2,hp=32,x_raw=(144+i*40)<<16,y_raw=1115<<16,
                  weapon=0,ammo=[100]*9) for i in range(2)]
    return dict(observation=dict(ready=1,enrolled=1,failed=0,mailbox=0,scene_owner=0,native_mode=10,
        native_phase=2,pause_owner=owner+1,lifecycle=(0,0),players=players,native_timer=100,tick=tick),
        menu=[1,6],cursor=0,menu_phase=2,quit_phase=1,quit_page=page,choice=choice,fade=0,
        native_play_mode=10,native_play_phase=2,projected_campaign_character=0,
        shared_stage_clear_byte=0,shared_tank_flags=0)


def window(*, owner=0, page=0, choice=0, online=False):
    result=[]
    for tick in (10,20,30):
        current=dict(peers=[row(tick,page=page,choice=choice,owner=owner) for _ in range(2 if online else 1)])
        if online:
            current["network"]=[dict(active=1,players=2,max_players=2,rollback=0,desync=0,tick=tick,resolved_through=tick-3)
                                for _ in range(2)]
        result.append(current)
    return result


class NativeQuitEvidenceTests(unittest.TestCase):
    def reduce(self,samples,*,online=False):
        return quit_ui.reduce_quit_window(samples,owner=0,page=0,choice=0,reference=window()[0],networked=online)

    def test_first_page_and_clock_are_distinct_from_logical_sprite_visibility(self):
        checks=self.reduce(window())
        self.assertTrue(all(checks.values()))
        self.assertNotIn("p2_hidden",checks)
        self.assertNotIn("artwork_passed",checks)

    def test_wrong_page_choice_owner_fade_or_opening_substate_rejected(self):
        for change in (dict(quit_page=1),dict(choice=1),dict(fade=1),dict(quit_phase=0),
                       dict(menu_phase=1),dict(menu=[1,0]),dict(native_play_phase=0)):
            samples=window();samples[1]["peers"][0].update(change)
            self.assertFalse(self.reduce(samples)["exact_native_quit_page_ready"])
        samples=window();samples[1]["peers"][0]["observation"]["pause_owner"]=2
        self.assertFalse(self.reduce(samples)["exact_native_quit_page_ready"])

    def test_stale_publication_frozen_process_or_world_progress_cannot_pass(self):
        for change in (dict(tick=10),dict(native_timer=101)):
            samples=window();samples[1]["peers"][0]["observation"].update(change)
            self.assertFalse(all(self.reduce(samples).values()))
        samples=window()
        for sample in samples:sample["peers"][0]["observation"]["tick"]=10
        self.assertFalse(self.reduce(samples)["diagnostic_publications_advanced"])

    def test_transient_resource_roster_or_shared_progress_change_is_retained_as_failure(self):
        mutations=(lambda r:r["observation"]["players"][1].update(hp=28),
                   lambda r:r["observation"]["players"][0].update(character=1),
                   lambda r:r.update(shared_stage_clear_byte=1),lambda r:r.update(shared_tank_flags=0x1000),
                   lambda r:r.update(cursor=13))
        for mutate in mutations:
            samples=window();mutate(samples[1]["peers"][0])
            self.assertFalse(all(self.reduce(samples).values()))

    def test_one_projected_campaign_byte_is_not_promotion_evidence(self):
        samples=window();samples[1]["peers"][0]["projected_campaign_character"]=1
        self.assertTrue(all(self.reduce(samples).values()))

    def test_two_actual_transport_windows_required_on_same_machine(self):
        samples=window(online=True)
        reference=deepcopy(samples[0])
        def reduce():
            return quit_ui.reduce_quit_window(samples,owner=0,page=0,choice=0,reference=reference,networked=True)
        self.assertTrue(all(reduce().values()))
        for sample in samples:sample["network"][1]["tick"]=10
        self.assertFalse(reduce()["transport_ticks_advanced"])
        samples=window(online=True);samples[1]["network"][0]["desync"]=1
        self.assertFalse(reduce()["network_active_without_desync"])


class NativeQuitObserverTests(unittest.TestCase):
    def test_original_read_fields_and_separate_projection_are_recorded(self):
        raw=bytearray(0x3C);raw[4:8]=bytes((1,6,2,1));raw[0x14]=13
        struct.pack_into("<I",raw,0x34,1)
        globals_=bytearray(8);globals_[7]=1
        play=bytearray(0x6C);play[:2]=bytes((10,2));play[0x38]=1
        client=Mock();client.read.side_effect=[bytes(raw),bytes(globals_),bytes(play)]
        debug=SimpleNamespace(observe=lambda client:SimpleNamespace(json=lambda:row()["observation"]))
        parsed=quit_ui.observe_native_quit(client,debug)
        self.assertEqual(parsed["quit_page"],1)
        self.assertEqual(parsed["choice"],1)
        self.assertEqual(parsed["projected_campaign_character"],1)
        self.assertEqual(client.read.call_args_list[0].args,(quit_ui.MENU_BASE,0x3C))

    def test_short_native_read_is_not_an_eligible_ui_page(self):
        client=Mock();client.read.side_effect=[bytes(0x3B),bytes(8),bytes(0x6C)]
        debug=SimpleNamespace(observe=lambda client:SimpleNamespace(json=lambda:row()["observation"]))
        with self.assertRaises(quit_ui.NativeQuitError):quit_ui.observe_native_quit(client,debug)


class NativeQuitGuardTests(unittest.TestCase):
    def ctx(self,root,*,online=False):
        return dict(mode="netplay" if online else "local",input_path="published_host" if online else "offline_native",
            clients=[Mock() for _ in range(2 if online else 1)],both=Mock(),debug=SimpleNamespace(observe=Mock(),capture_present=Mock(return_value={"path":"retained-pending.png"})),
            report={},output=root,hold=Mock(),native_advance=Mock(),transport_window=Mock(),candidate_exe_sha256="a"*64,
            same_machine=True,network=Mock(),matched=Mock())

    def test_wrong_candidate_path_or_network_contract_rejected_before_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            for mutate in (lambda c:c.update(candidate_exe_sha256="b"*64),
                           lambda c:c.update(input_path="sio"),lambda c:c.update(same_machine=False),
                           lambda c:c.update(matched=None)):
                ctx=self.ctx(Path(temporary),online=True);mutate(ctx)
                with self.assertRaises(ValueError):
                    quit_ui.native_quit_smoke(ctx,original_exe="unused",expected_exe_sha256="a"*64)
                ctx["hold"].assert_not_called()

    def test_wrong_original_file_rejected_without_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.ctx(Path(temporary));path=Path(temporary)/"original.exe";path.write_bytes(bytes(522240))
            with self.assertRaises(ValueError):
                quit_ui.native_quit_smoke(ctx,original_exe=path,expected_exe_sha256="a"*64)
            ctx["hold"].assert_not_called()

    def test_guest_admission_retains_failure_and_never_sends_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.ctx(Path(temporary));ctx["both"].side_effect=lambda fn:[fn(0)]
            initial=row(owner=1);initial["menu"]=[0,0]
            initial["observation"].update(native_phase=0,pause_owner=0)
            paused=row(owner=1);paused["menu"]=[1,0]
            admitted=row(owner=1)
            # Reads consumed by initial, Start before/after, wait, Select
            # before/after, and the admission probe respectively.
            reads=[initial,initial,paused,paused,paused,admitted,admitted]
            with patch.object(quit_ui,"verify_original",return_value={}), \
                    patch.object(quit_ui,"observe_native_quit",side_effect=deepcopy(reads)):
                with self.assertRaisesRegex(quit_ui.NativeQuitError,"no confirmation"):
                    quit_ui.native_quit_smoke(ctx,original_exe="verified",expected_exe_sha256="a"*64,scenario="guest_authority")
            masks=[call.args[1] for call in ctx["hold"].call_args_list]
            self.assertEqual(masks,[quit_ui.START,quit_ui.SELECT])
            case=ctx["report"]["native_quit"][0]
            self.assertEqual(case["status"],"failed_behavior")
            self.assertIn("guest_quit_admitted",case)
            self.assertEqual(case["ledger_status"],"unverified")
            self.assertTrue(case["captures"])

    def test_failed_secondary_capture_does_not_replace_guest_authority_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.ctx(Path(temporary));ctx["both"].side_effect=lambda fn:[fn(0)]
            initial=row(owner=1);initial["menu"]=[0,0];initial["observation"].update(native_phase=0,pause_owner=0)
            paused=row(owner=1);paused["menu"]=[1,0]
            admitted=row(owner=1)
            ctx["debug"].capture_present.side_effect=OSError("retained capture failure")
            with patch.object(quit_ui,"verify_original",return_value={}), patch.object(quit_ui,"observe_native_quit",
                    side_effect=deepcopy([initial,initial,paused,paused,paused,admitted,admitted])):
                with self.assertRaisesRegex(quit_ui.NativeQuitError,"Guest Select entered"):
                    quit_ui.native_quit_smoke(ctx,original_exe="verified",expected_exe_sha256="a"*64,scenario="guest_authority")
            case=ctx["report"]["native_quit"][0]
            self.assertEqual(case["capture_errors"],["retained capture failure"])
            self.assertIn("no confirmation",case["error"])
            self.assertFalse(case["checks"]["guest_select_cannot_enter_native_quit"])
            self.assertEqual([call.args[1] for call in ctx["hold"].call_args_list],[quit_ui.START,quit_ui.SELECT])


if __name__=="__main__":unittest.main()
