"""Negative evidence cases; these fixtures do not qualify native gameplay."""
import copy
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from mmx6_coop_private_pause import PrivatePauseError, private_pause_smoke, reduce_private_freeze


def peer(tick=100, timer=50):
    pools={name:[dict(raw_hex=bytes(size).hex(), allocation=0x11, phase=0,
                     visible=1,active=1) for _ in range(3)]
           for name,size in (("trails",0x60),("attached",0x50))}
    return dict(available=True,marker=1,p2_body_hex=bytes(0x158).hex(),**pools,
        menu=[1,0],cursor=0,observation=dict(tick=tick,native_timer=timer,
        native_mode=10,native_phase=2,pause_owner=1,lifecycle=[0,0],
        ready=1,enrolled=1,failed=0,mailbox=0,scene_owner=0,players=[
            dict(active=1,character=0,state=1,action=2,hp=32,x_raw=144<<16,weapon=0,ammo=[288]*9),
            dict(active=1,character=1,state=1,action=12,hp=32,x_raw=160<<16,weapon=0,ammo=[288]*9)]))


def samples(online=False):
    rows=[]
    for offset in (0,6,12):
        row=dict(peers=[peer(100+offset) for _ in range(2 if online else 1)])
        if online:
            row["network"]=[dict(active=1,players=2,max_players=2,rollback=0,
                desync=0,tick=1000+offset,resolved_through=998+offset) for _ in range(2)]
        rows.append(row)
    return rows


class PrivateBodyFreezeEvidence(unittest.TestCase):
    def test_complete_visible_p1_owned_pause_with_advancing_observers(self):
        for online in (False,True):
            self.assertTrue(all(reduce_private_freeze(samples(online),networked=online).values()))

    def test_transient_body_input_or_timer_mutation_cannot_hide_between_equal_endpoints(self):
        rows=samples();raw=bytearray.fromhex(rows[1]["peers"][0]["p2_body_hex"])
        raw[0x7C]=1;rows[1]["peers"][0]["p2_body_hex"]=raw.hex()
        self.assertEqual(rows[0]["peers"][0]["p2_body_hex"],rows[-1]["peers"][0]["p2_body_hex"])
        self.assertFalse(reduce_private_freeze(rows)["exact_private_body_frozen"])

    def test_all_six_full_native_pool_records_are_compared(self):
        for name in ("trails","attached"):
            for slot in range(3):
                rows=samples();actor=rows[1]["peers"][0][name][slot]
                data=bytearray.fromhex(actor["raw_hex"]);data[-1]=99;actor["raw_hex"]=data.hex()
                with self.subTest(pool=name,slot=slot):
                    self.assertFalse(reduce_private_freeze(rows)["exact_private_pools_frozen"])

    def test_truncated_pool_or_body_cannot_be_matching_frozen_state(self):
        rows=samples()
        for row in rows:row["peers"][0]["p2_body_hex"]="00"
        self.assertFalse(reduce_private_freeze(rows)["exact_private_body_frozen"])
        rows=samples()
        for row in rows:row["peers"][0]["trails"][0]["raw_hex"]="00"
        self.assertFalse(reduce_private_freeze(rows)["exact_private_pools_frozen"])

    def test_empty_or_negative_marker_window_is_not_effect_retention(self):
        for marker in (0,-1):
            rows=samples()
            for row in rows:row["peers"][0]["marker"]=marker
            self.assertFalse(reduce_private_freeze(rows)["visible_preexisting_private_trails"])
        rows=samples()
        for row in rows:
            for trail in row["peers"][0]["trails"]:trail.update(visible=0,active=0)
        self.assertFalse(reduce_private_freeze(rows)["visible_preexisting_private_trails"])

    def test_drain_phase_or_wrong_action_is_not_preexisting_accepted_ground_dash(self):
        rows=samples();rows[0]["peers"][0]["trails"][0]["phase"]=1
        self.assertFalse(reduce_private_freeze(rows)["visible_preexisting_private_trails"])
        rows=samples();rows[0]["peers"][0]["observation"]["players"][1]["action"]=48
        self.assertFalse(reduce_private_freeze(rows)["visible_preexisting_private_trails"])

    def test_transient_wrong_owner_resume_departure_or_native_clock_advance_fails(self):
        for key,value,check in (("pause_owner",2,"native_pause_owned"),
                                ("native_phase",0,"native_pause_owned"),
                                ("lifecycle",[0,4],"native_pause_owned"),
                                ("native_timer",51,"world_timer_frozen")):
            rows=samples();rows[1]["peers"][0]["observation"][key]=value
            with self.subTest(key=key):self.assertFalse(reduce_private_freeze(rows)[check])

    def test_other_input_window_cannot_reset_the_original_clock_reference(self):
        reference=samples()[0];rows=samples()
        for row in rows:row["peers"][0]["observation"]["native_timer"]=51
        reduced=reduce_private_freeze(rows,reference=reference)
        self.assertTrue(reduced["world_timer_frozen"])
        self.assertFalse(reduced["original_menu_clock_retained"])

    def test_cursor_and_each_seats_resources_cannot_change(self):
        rows=samples();rows[1]["peers"][0]["cursor"]=1
        self.assertFalse(reduce_private_freeze(rows)["original_cursor_retained"])
        for seat in (0,1):
            for key in ("hp","weapon","ammo"):
                rows=samples();player=rows[1]["peers"][0]["observation"]["players"][seat]
                if key=="ammo":player[key][0]-=1
                else:player[key]-=1
                with self.subTest(seat=seat,key=key):
                    self.assertFalse(reduce_private_freeze(rows)["personal_resources_preserved"])

    def test_missing_extension_wrong_roster_pending_hit_or_scene_is_rejected(self):
        for mutation in ("extension","roster","pending_hit","scene"):
            rows=samples();row=rows[1]["peers"][0]
            if mutation=="extension":row["available"]=False
            elif mutation=="roster":row["observation"]["players"][1]["character"]=0
            elif mutation=="pending_hit":row["observation"]["players"][1]["hp"]=0x9C
            else:row["observation"]["scene_owner"]=1
            reduced=reduce_private_freeze(rows)
            self.assertFalse(reduced["exact_private_body_frozen"] if mutation=="extension" else reduced["fixed_native_roster_ready"])

    def test_stopped_engine_stalled_resolution_and_transient_desync_cannot_pass(self):
        rows=samples()
        for row in rows:row["peers"][0]["observation"]["tick"]=100
        self.assertFalse(reduce_private_freeze(rows)["diagnostic_publications_advanced"])
        rows=samples(True)
        for row in rows:row["network"][1]["resolved_through"]=998
        self.assertFalse(reduce_private_freeze(rows,networked=True)["resolved_ticks_advanced"])
        rows=samples(True);rows[1]["network"][1]["desync"]=1
        self.assertFalse(reduce_private_freeze(rows,networked=True)["network_active_without_desync"])

    def test_duplicate_polls_allowed_only_with_three_forward_publications(self):
        rows=samples(True);rows.insert(1,copy.deepcopy(rows[0]))
        self.assertTrue(all(reduce_private_freeze(rows,networked=True).values()))
        rows=samples();rows[1]["peers"][0]["observation"]["tick"]=100
        self.assertFalse(reduce_private_freeze(rows)["ordered_publications"])
        rows=samples();rows[1]["peers"][0]["observation"]["tick"]=99
        self.assertFalse(reduce_private_freeze(rows)["ordered_publications"])

    def test_publication_wrap_is_forward(self):
        rows=samples()
        for row,tick in zip(rows,(0xFFFFFFFC,2,8)):row["peers"][0]["observation"]["tick"]=tick
        self.assertTrue(all(reduce_private_freeze(rows).values()))

    def test_short_window_cannot_satisfy_source_departure_threshold_duration(self):
        self.assertFalse(reduce_private_freeze(samples(),minimum_progress=90)["diagnostic_publications_advanced"])


class PrivatePauseContracts(unittest.TestCase):
    def context(self,mode="local"):
        empty=lambda *args,**kwargs:None
        return dict(mode=mode,input_path="published_host" if mode=="netplay" else "offline_native",
            clients=[None]*(2 if mode=="netplay" else 1),both=empty,
            debug=SimpleNamespace(capture_present=empty),effects=SimpleNamespace(__file__=__file__,
                observe_effects=empty,reduce_effect_menu_freeze=empty,reduce_zero_dash=empty),
            report={},output=Path(__file__).parent,candidate_exe_sha256="a"*64,
            hold=empty,hold_observed=empty,native_advance=empty,transport_window=empty)

    def test_explicit_actual_candidate_binding_cannot_be_omitted_or_mismatched(self):
        for expected in ("a"*40,"A"*64,"b"*64,None):
            with self.assertRaises(ValueError):private_pause_smoke(self.context(),expected_exe_sha256=expected)

    def test_online_direct_sio_mailbox_or_missing_crc_callbacks_rejected_before_input(self):
        for path in ("offline_native","mailbox","direct_sio"):
            ctx=self.context("netplay");ctx["input_path"]=path
            with self.assertRaises(ValueError):private_pause_smoke(ctx,expected_exe_sha256="a"*64)
        with self.assertRaisesRegex(ValueError,"transport status"):
            private_pause_smoke(self.context("netplay"),expected_exe_sha256="a"*64)

    def test_observed_hold_is_required_and_deadlines_cannot_be_unbounded(self):
        ctx=self.context();del ctx["hold_observed"]
        with self.assertRaises(ValueError):private_pause_smoke(ctx,expected_exe_sha256="a"*64)
        for options in (dict(timeout=float("nan")),dict(timeout=61),dict(window_frames=0),dict(max_retirement_ticks=121)):
            with self.assertRaises(ValueError):private_pause_smoke(self.context(),expected_exe_sha256="a"*64,**options)

    def test_acknowledged_dash_without_native_marker_never_requests_p1_menu(self):
        temporary=Path(os.environ["TEMP"]).resolve(strict=True)
        self.assertNotEqual(temporary.drive.upper(),"C:")
        with tempfile.TemporaryDirectory(dir=temporary) as directory:
            ctx=self.context();ctx["output"]=directory;inputs=[];tick=100

            def observed(client):
                nonlocal tick
                tick+=1;row=peer(tick)
                row["marker"]=0;row["observation"].update(native_phase=0,pause_owner=0)
                row["observation"]["players"][1]["action"]=2
                for trail in row["trails"]:trail.update(visible=0,active=0)
                return SimpleNamespace(json=lambda:copy.deepcopy(row))

            ctx["effects"].observe_effects=observed
            ctx["clients"]=[SimpleNamespace(read=lambda address,count:bytes(count))]
            ctx["both"]=lambda callback:[callback(0)]
            ctx["hold"]=lambda *args:inputs.append(args)
            ctx["hold_observed"]=lambda seat,bits,frames,label,observe:[observe() for _ in range(3)]
            with self.assertRaisesRegex(PrivatePauseError,"trail window"):
                private_pause_smoke(ctx,expected_exe_sha256="a"*64)
            self.assertEqual(inputs,[])  # No invented native acceptance -> no nested P1 Start.
            case=ctx["report"]["private_pause"][0]
            self.assertEqual(case["status"],"failed_setup")
            self.assertEqual(case["ledger_status"],"unverified")
            self.assertGreaterEqual(len(case["observations"]),3)


if __name__=="__main__":
    unittest.main()
