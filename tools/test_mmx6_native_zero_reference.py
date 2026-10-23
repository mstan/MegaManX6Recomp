"""Native-reference protocol/ownership fixtures; no game/art qualification."""
import copy
import itertools
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock,patch

import mmx6_native_zero_reference as reference
from coop_debug import DebugError,UnstableObservation


def body_and_trails(*,marker=0,visible=False,phase=0):
    raw=bytearray(reference.BODY_AND_TRAILS_BYTES)
    raw[0]=raw[2]=raw[3]=raw[4]=1
    raw[5]=6 if marker else 2
    raw[0x5C]=32;raw[0xE7]=5;raw[0x47]=7
    struct.pack_into("<b",raw,0x8C,marker)
    struct.pack_into("<I",raw,0x30,0x801EF6D0)
    struct.pack_into("<IIHH",raw,0x38,0x801D0000,0x801C0000,0x0500,0x7800)
    for i in range(3):
        start=reference.TRAILS-reference.PLAYER+i*0x60
        raw[start]=0x11;raw[start+2]=i
        raw[start+3]=raw[start+4]=int(visible);raw[start+5]=phase;raw[start+0x16]=4;raw[start+0x47]=7
        struct.pack_into("<IIHH",raw,start+0x38,0x801D0000,0x801C0000,0x0500,reference.TRAIL_CLUTS[i])
        struct.pack_into("<IHHH",raw,start+0x50,reference.PLAYER if not i else reference.TRAILS+(i-1)*0x60,3,8,(5-i)*2)
    return bytes(raw)


def play(timer=10):
    raw=bytearray(0x94);raw[0]=10;raw[0x38]=1;raw[0x5E]=5;raw[0x5F]=0x11
    struct.pack_into("<I",raw,0x90,timer)
    return bytes(raw)


def sample(timer=10,**kwargs):
    session=Mock()
    session.read.side_effect=[play(timer),body_and_trails(**kwargs),play(timer)]
    return reference.read_native(session)


def menu_sample(*,mode=(4,4,0),held=0,previous=0,edge=0,dialogue_active=0,
                dialogue_phase=0,coherent=True):
    return dict(mode=list(mode),mode_before=list(mode),coherent_mode=coherent,
                held=held,previous=previous,edge=edge,
                decoded_hex=struct.pack("<3H",held,previous,edge).hex(),
                dialogue_active=dialogue_active,dialogue_phase=dialogue_phase)


class MenuPulseTests(unittest.TestCase):
    def test_clear_ack_waits_for_both_decoded_held_and_previous_to_be_neutral(self):
        session=Mock();record={}
        sequence=[menu_sample(),menu_sample(held=0x40,edge=0x40),
                  menu_sample(held=0x40,previous=0x40),menu_sample(previous=0x40),menu_sample()]
        with patch.object(reference,"_read_menu_input",side_effect=sequence),patch.object(reference.time,"sleep"):
            reference._menu_press(session,0x4000,lambda row:True,receipt=record)
        self.assertEqual(record["status"],"native_transition_and_neutral_observed")
        self.assertEqual(len(record["neutral_after"]),3)
        self.assertTrue(record["pressed_observed"] and record["edge_observed"] and record["neutral_consumed"])
        self.assertEqual(session.request.call_args_list[0].kwargs,dict(port=1,buttons=0xBFFF,frames=0))
        self.assertEqual(session.request.call_args_list[-1].args,("clear_input",))

    def test_ack_and_mode_transition_without_a_consumed_button_cannot_pass(self):
        session=Mock();record={}
        # A native animation transition can happen while the input has not
        # reached the decoder. A true predicate or press ACK cannot qualify it.
        with patch.object(reference,"_read_menu_input",return_value=menu_sample(mode=(4,11,1))),\
             patch.object(reference.time,"sleep"),\
             patch.object(reference.time,"monotonic",side_effect=itertools.count(0,.01)):
            with self.assertRaisesRegex(DebugError,"held_response"):
                reference._menu_press(session,0x4000,lambda row:True,timeout=.08,receipt=record)
        self.assertEqual(record["status"],"failed_setup")
        self.assertFalse(record["pressed_observed"] or record["transition_observed"])
        self.assertTrue(record["neutral_consumed"])
        self.assertEqual(record["timeout_stages"],["held_response"])
        self.assertTrue(all(row["expected_transition"] for row in record["held_response"]))

    def test_release_ack_with_stale_previous_is_a_retained_setup_failure(self):
        session=Mock();record={};rows=iter([menu_sample(),menu_sample(held=0x2000,edge=0x2000)])
        def observe(_):return next(rows,menu_sample(previous=0x2000))
        with patch.object(reference,"_read_menu_input",side_effect=observe),patch.object(reference.time,"sleep"),\
             patch.object(reference.time,"monotonic",side_effect=itertools.count(0,.01)):
            with self.assertRaisesRegex(DebugError,"neutral_after"):
                reference._menu_press(session,0x20,lambda row:True,timeout=.08,receipt=record)
        self.assertEqual(record["status"],"failed_setup")
        self.assertTrue(record["transition_observed"])
        self.assertFalse(record["neutral_consumed"])
        self.assertEqual(record["timeout_stage"],"neutral_after")
        self.assertEqual(record["neutral_after"][-1]["previous"],0x2000)
        self.assertIn("neutral_after",record["release_error"])

    def test_mode_brackets_and_truncated_triples_do_not_count_as_neutral(self):
        session=Mock();dialogue=bytes(0x10)
        session.read.side_effect=[bytes((4,11,0)),bytes(6),dialogue,bytes((4,11,1))]
        row=reference._read_menu_input(session)
        self.assertFalse(reference._neutral_menu_input(row))
        self.assertEqual(session.read.call_args_list[1].args,(reference.PAD_DECODE,6))
        for bad in (bytes(5),bytes(7)):
            session.read.side_effect=[bytes((4,11,1)),bad,dialogue,bytes((4,11,1))]
            with self.assertRaisesRegex(DebugError,"Truncated"):reference._read_menu_input(session)

    def test_briefing_initialization_and_text_animation_are_not_input_ready(self):
        for row in (menu_sample(mode=(4,11,0),dialogue_active=1,dialogue_phase=3),
                    menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=1),
                    menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=2),
                    menu_sample(mode=(4,11,1),dialogue_active=0,dialogue_phase=3),
                    menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=3,coherent=False)):
            self.assertFalse(reference._briefing_ready(row),row)
        ready=menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=3)
        self.assertTrue(reference._briefing_ready(ready))
        session=Mock();record={}
        sequence=[menu_sample(mode=(4,11,0)),menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=2),
                  ready,menu_sample(mode=(4,11,1),held=0x40,edge=0x40,dialogue_active=1,dialogue_phase=1),menu_sample()]
        def observe(_):
            if len(sequence)>2 and not reference._briefing_ready(sequence[0]):
                self.assertFalse(any(c.args==("press",) for c in session.request.call_args_list))
            return sequence.pop(0)
        with patch.object(reference,"_read_menu_input",side_effect=observe),patch.object(reference.time,"sleep"):
            reference._menu_press(session,0x4000,lambda row:row["dialogue_phase"]!=3,
                                  ready=reference._briefing_ready,receipt=record)
        self.assertEqual(len(record["neutral_before"]),3)
        self.assertTrue(record["neutral_consumed"])

    def test_invalid_pulses_are_rejected_before_controls(self):
        for bits,timeout in ((0,2),(True,2),(-1,2),(0x10000,2),(0x20,float("nan")),(0x20,0),(0x20,13)):
            session=Mock()
            with self.assertRaises(ValueError):reference._menu_press(session,bits,lambda row:True,timeout=timeout)
            session.request.assert_not_called()

    def test_neutral_cursor_animation_must_finish_before_confirmation_press(self):
        session=Mock();record={}
        sequence=[menu_sample(mode=(4,4,6)),menu_sample(mode=(4,4,6)),menu_sample(mode=(4,4,5)),
                  menu_sample(mode=(4,4,7),held=0x40,edge=0x40),menu_sample(mode=(4,4,7))]
        def observe(_):
            if sequence[0]["mode"]==[4,4,6]:
                self.assertFalse(any(c.args==("press",) for c in session.request.call_args_list))
            return sequence.pop(0)
        with patch.object(reference,"_read_menu_input",side_effect=observe),patch.object(reference.time,"sleep"):
            reference._menu_press(session,0x4000,lambda row:row["mode"]!=[4,4,5],receipt=record,
                                  ready=lambda row:row["mode"]==[4,4,5])
        self.assertEqual(len(record["neutral_before"]),3)
        self.assertEqual(record["held_response"][-1]["mode"],[4,4,7])
        self.assertTrue(record["neutral_consumed"])

    def test_original_response_error_is_not_replaced_by_cleanup_protocol_failure(self):
        session=Mock();record={}
        session.request.side_effect=[dict(ok=True),DebugError("release protocol failure")]
        with patch.object(reference,"_read_menu_input",side_effect=[menu_sample(),menu_sample(held=0x2000)]),\
             self.assertRaisesRegex(RuntimeError,"response failure"):
            reference._menu_press(session,0x20,lambda row:(_ for _ in ()).throw(RuntimeError("response failure")),receipt=record)
        self.assertEqual(record["error"],"response failure")
        self.assertEqual(record["release_error"],"release protocol failure")
        self.assertFalse(record["neutral_consumed"])


class SourceAndObservationTests(unittest.TestCase):
    def test_native_body_and_all_three_full_trails_share_one_exact_rpc(self):
        session=Mock()
        raw=body_and_trails(marker=1,visible=True)
        session.read.side_effect=[play(),raw,play()]
        row=reference.read_native(session)
        self.assertTrue(reference.visible_dash(row))
        self.assertEqual(session.read.call_args_list[1].args,(reference.PLAYER,0x378))
        self.assertEqual(row["trails"][2]["parent"],reference.TRAILS+0x60)
        self.assertEqual(row["trails"][0]["raw_hex"],raw[0x258:0x2B8].hex())
        self.assertEqual(len(session.read.call_args_list),3)  # Two labeled clock brackets, one pool read.

    def test_changed_cross_rpc_clock_or_mode_truncation_and_wrong_link_reject(self):
        for after in (play(11),bytes((4,))+play()[1:]):
            session=Mock();session.read.side_effect=[play(),body_and_trails(),after]
            with self.assertRaises(UnstableObservation):reference.read_native(session)
        session=Mock();session.read.side_effect=[play(),body_and_trails()[:-1],play()]
        with self.assertRaises(DebugError):reference.read_native(session)
        raw=bytearray(body_and_trails(marker=1,visible=True));raw[0x258+0x50]^=1
        session=Mock();session.read.side_effect=[play(),bytes(raw),play()]
        with self.assertRaisesRegex(DebugError,"parent"):reference.read_native(session)

    def test_source_guard_checks_full_live_window_and_retains_mismatch(self):
        session=Mock();session.read.return_value=b"different"
        records=[]
        with self.assertRaisesRegex(DebugError,"guard"):
            reference._guard_code(session,{"exe":b"12345678"},"exe",0x80010000,((0x80010000,0x80010008),),records)
        self.assertEqual(len(records),1)
        self.assertNotEqual(records[0]["sha256"],records[0]["expected_sha256"])

    def test_actual_palette_protocol_requires_both_nonempty48word_views(self):
        session=Mock()
        encoded="".join(f"{v:04x}" for v in range(48))
        session.request.return_value=dict(x=208,y=480,w=48,h=1,hex=encoded)
        rows=reference.read_trail_palettes(session)
        self.assertEqual(rows["vram_peek"]["colors"],list(range(48)))
        self.assertEqual([call.args[0] for call in session.request.call_args_list],["vram_peek","gl_fbo_peek"])
        for bad in (dict(x=208,y=480,w=16,h=1,hex=encoded),dict(x=208,y=480,w=48,h=1,hex="0"*192),
                    dict(x=208,y=480,w=48,h=1,hex="zzzz"*48)):
            session.request.return_value=bad
            with self.assertRaises(DebugError):reference.read_trail_palettes(session)


class ReducerTests(unittest.TestCase):
    def traces(self):
        return (sample(10),[sample(11,marker=1,visible=True),sample(12,marker=1,visible=True)],
                [sample(13,marker=-1,visible=True,phase=1),sample(21,marker=-1,visible=True,phase=2),sample(29)])

    def test_native_positive_capture_brackets_and_finite_drain_are_required(self):
        before,active,released=self.traces()
        checks=reference.reduce_native_reference(before,active,released,active)
        self.assertTrue(all(checks.values()),checks)
        for bad in ([],[active[0]], [active[0],released[-1]]):
            self.assertFalse(reference.reduce_native_reference(before,active,released,bad)["capture_bracketed_by_visible_dash"])
        self.assertFalse(reference.reduce_native_reference(before,[sample(11)],released,active)["accepted_positive_marker"])

    def test_ack_endpoint_hard_clear_retrigger_and_resource_borrow_do_not_qualify(self):
        before,active,released=self.traces()
        for bad in ([sample(13),sample(29)],
                    [released[0],released[-1]],
                    [released[0],sample(20,marker=1,visible=True),released[1],released[-1]],
                    released[:-1]):
            self.assertFalse(reference.reduce_native_reference(before,active,bad,active)["finite_retirement"])
        changed=copy.deepcopy(active)
        changed[0]["trails"][1]["assembly"]^=0x100
        self.assertFalse(reference.reduce_native_reference(before,changed,released,active)["native_resources_and_cluts_retained"])
        changed=copy.deepcopy(active);changed[0]["player"]["character"]=0
        self.assertFalse(reference.reduce_native_reference(before,changed,released,active)["native_zero_roster"])
        self.assertFalse(reference.reduce_native_reference(before,active,released,active,max_drain_ticks=8)["finite_retirement"])


class ProfileTests(unittest.TestCase):
    def profile(self,directory):
        root=Path(directory)
        for name in ("saves","temp","data","appdata","resident","cache","mods/bundled/coop/1","mods/bundled/other/1"):
            (root/name).mkdir(parents=True)
        (root/"mmx6-runtime.exe").write_bytes(b"fixture image")
        digest=reference.preparation.sha256(root/"mmx6-runtime.exe")
        (root/"preparation.json").write_text(json.dumps(dict(automated_profile=True,source_card=None,
            source_card_sha256=None,exe_sha256=digest)))
        (root/"mods/bundled/coop/1/manifest.toml").write_text('id="mmx6.local-coop"\nversion="1"\n[[feature]]\nid="prototype"\ndefault_enabled=true\n')
        (root/"mods/bundled/other/1/manifest.toml").write_text('id="other"\nversion="1"\n[[feature]]\nid="default-on"\ndefault_enabled=true\n')
        return root,digest

    def test_real_state_disables_all_features_and_tampered_enabled_state_refuses(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
            root,digest=self.profile(directory)
            reference.disable_reference_mods(root)
            with patch.object(reference.baseline,"candidate_environment",return_value={}):
                reference.validate_reference_profile(root,digest)
                with self.assertRaisesRegex(ValueError,"changed"):
                    path=root/"mods/state.toml";path.write_text(path.read_text().replace("false","true",1))
                    reference.validate_reference_profile(root,digest)
                receipt=root/reference.DISABLED_STATE;data=json.loads(receipt.read_text())
                data["state_sha256"]=reference.preparation.sha256(path);receipt.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,"explicitly disable"):
                    reference.validate_reference_profile(root,digest)
            with self.assertRaisesRegex(ValueError,"fresh"):
                reference.disable_reference_mods(root)

    def test_source_cards_nonempty_profile_duplicate_versions_and_wrong_image_refuse(self):
        for reason in ("source_card","existing_save","duplicate"):
            with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
                root,digest=self.profile(directory)
                if reason=="source_card":
                    path=root/"preparation.json";data=json.loads(path.read_text());data["source_card"]="user.mcd";path.write_text(json.dumps(data))
                elif reason=="existing_save":(root/"saves/user.mcd").write_bytes(b"preserve")
                else:
                    (root/"mods/bundled/coop/2").mkdir();(root/"mods/bundled/coop/2/manifest.toml").write_text('id="mmx6.local-coop"\nversion="2"\n')
                with self.assertRaises(ValueError):reference.disable_reference_mods(root)

    def test_engine_formatting_normalization_preserves_exact_disabled_semantics(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
            root,digest=self.profile(directory)
            receipt=reference.disable_reference_mods(root)
            path=root/"mods/state.toml"
            path.write_text(path.read_text().replace("\n","\n\n"))
            with patch.object(reference.baseline,"candidate_environment",return_value={}):
                result=reference.validate_reference_profile(root,digest)
                self.assertNotEqual(result["actual_state_sha256"],receipt["state_sha256"])
                self.assertEqual(result["actual_state_semantic_sha256"],receipt["state_semantic_sha256"])
                path.write_text(path.read_text().replace('version = "1"','version = "2"',1))
                with self.assertRaisesRegex(ValueError,"changed"):
                    reference.validate_reference_profile(root,digest)


class OwnershipAndSelectionTests(unittest.TestCase):
    def test_failed_briefing_attempt_retains_mode_decoded_input_and_timeout(self):
        session=Mock();receipt={}
        session.read.side_effect=[bytes((10,0,0)),bytes((1,)),body_and_trails()[:0x158]]
        ready=menu_sample(mode=(4,11,1),dialogue_active=1,dialogue_phase=3)
        with patch.object(reference,"_guard_code"),patch.object(reference,"_read_menu_input",return_value=ready),\
             patch.object(reference.time,"sleep"),\
             patch.object(reference.time,"monotonic",side_effect=itertools.count(0,.01)):
            with self.assertRaisesRegex(DebugError,"held_response"):
                reference.select_native_zero(session,{"exe_base":0x80010000},receipt,
                                              allow_private_prerequisite=True,timeout=.4)
        self.assertEqual(receipt["status"],"failed_setup")
        self.assertTrue(receipt["ordinary_input_evidence_tainted"])
        self.assertEqual(len(receipt["inputs"]),2)
        attempt=receipt["inputs"][-1]
        self.assertEqual(attempt["purpose"],"native briefing page input")
        self.assertEqual(attempt["ready_sample"]["mode"],[4,11,1])
        self.assertEqual(attempt["held_response"][-1]["decoded_hex"],"000000000000")
        self.assertEqual(attempt["timeout_stage"],"held_response")
        self.assertTrue(attempt["neutral_consumed"])
        self.assertEqual(attempt["status"],"failed_setup")

    def test_original_unit_navigation_preserves_unlocks_and_never_assigns_form_or_cursor(self):
        class MenuModel:
            # Source-contract I/O model only, not original native game logic.
            def __init__(self,filtered=False):
                self.mode=(10,0,0);self.flags=1;self.cursor=0;self.selected=False;self.filtered=filtered;self.commands=[]
                self.requested=0;self.decoded=0;self.animation=0
            def offline(self):return dict(active=0)
            def read(self,address,size):
                if address==reference.PLAY and size==3:return bytes(self.mode)
                if address==reference.PLAY and size==0x94:return play()
                if address==reference.PLAY+0x5F:return bytes((self.flags,))
                if address==reference.MENU_COUNT:return bytes((2 if self.filtered else 3,))
                if address==reference.MENU_TABLE:return bytes((0,1) if self.filtered else (0,1,5))
                if address==reference.PLAY+0x30:return bytes((self.cursor,))
                if address==reference.PAD_DECODE:
                    if self.animation:
                        self.animation-=1
                        if not self.animation:self.mode=(4,4,5)
                    previous,self.decoded=self.decoded,self.requested
                    return struct.pack("<3H",self.decoded,previous,self.decoded&~previous)
                if address==reference.DIALOGUE:return bytes(0x10)
                if address==reference.PLAYER:
                    body=bytearray(body_and_trails())
                    if not self.selected:body[2]=0
                    return bytes(body[:size])
                raise AssertionError((address,size))
            def request(self,command,**fields):
                self.commands.append((command,fields))
                if command=="write_ram":
                    address,value=int(fields["addr"],0),int(fields["val"],0)
                    if address==reference.PLAY+0x5F:self.flags=value
                    if address==reference.PLAY:self.mode=(4,4,0)
                if command=="press":
                    bits=fields["buttons"]^0xFFFF
                    if self.decoded:raise AssertionError("Next pulse arrived before consumed native neutral")
                    if self.mode not in ((4,4,0),(4,4,5)):raise AssertionError("Input sent during native selector animation")
                    self.requested=((bits&255)<<8)|(bits>>8)
                    if bits==0x20:
                        self.cursor=(self.cursor+1)%3;self.mode=(4,4,6);self.animation=4
                    if bits==0x4000:
                        if self.mode==(4,4,0):self.mode=(4,4,5)
                        elif self.mode==(4,4,5):self.mode=(10,0,0);self.selected=True
                if command=="clear_input":self.requested=0
                return dict(ok=True)
        session=MenuModel();receipt={}
        with patch.object(reference,"_guard_code"):
            selected=reference.select_native_zero(session,{"exe_base":0x80010000},receipt,allow_private_prerequisite=True)
        self.assertTrue(reference.native_zero(selected))
        self.assertTrue(receipt["prerequisite_bypass"] and receipt["ordinary_input_evidence_tainted"])
        self.assertEqual(session.flags,0x11)
        self.assertEqual([int(f["addr"],0) for cmd,f in session.commands if cmd=="write_ram"],
                         [reference.PLAY+0x5F,reference.PLAY+1,reference.PLAY+2,reference.PLAY])
        self.assertTrue(all(f["frames"]==0 and f["port"]==1 for cmd,f in session.commands if cmd=="press"))
        self.assertEqual(sum(cmd=="press" for cmd,_ in session.commands)+1,sum(cmd=="clear_input" for cmd,_ in session.commands))
        self.assertTrue(all(row.get("neutral_consumed") for row in receipt["inputs"] if row["pressed"]))
        filtered=MenuModel(filtered=True)
        with patch.object(reference,"_guard_code"),self.assertRaisesRegex(DebugError,"filtered"):
            reference.select_native_zero(filtered,{"exe_base":0x80010000},{},allow_private_prerequisite=True)

    def test_lost_listener_or_wrong_actual_image_prevents_all_controls(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
            candidate=Path(directory);(candidate/"mmx6-runtime.exe").write_bytes(b"fixture")
            digest=reference.preparation.sha256(candidate/"mmx6-runtime.exe")
            process=Mock(pid=123);process.poll.return_value=None
            transport=Mock();transport.request.return_value=dict(active=0)
            with patch.object(reference,"validate_reference_profile",return_value={}),\
                 patch.object(reference,"process_image_path",return_value=(candidate/"mmx6-runtime.exe").resolve()),\
                 patch.object(reference.debug,"DebugClient",return_value=transport),\
                 patch.object(reference.baseline,"owns_listener",return_value=True) as owns:
                session=reference.OwnedNativeSession(process,1234,candidate,digest)
                with self.assertRaisesRegex(DebugError,"SHA256"):
                    reference.OwnedNativeSession(process,1234,candidate,"0"*64)
                owns.return_value=False
                count=transport.request.call_count
                with self.assertRaisesRegex(DebugError,"listener"):session.request("press",port=1,frames=0,buttons=0x9FDF)
                self.assertEqual(transport.request.call_count,count)
                owns.return_value=True
                with self.assertRaisesRegex(DebugError,"success writes"):session.request("write_ram",addr=hex(reference.PLAYER+0x8C),val="1")
                with self.assertRaisesRegex(DebugError,"held NativePad"):session.request("press",port=1,frames=6,buttons=0xBFFF)
            with patch.object(reference,"validate_reference_profile",return_value={}),\
                 patch.object(reference,"process_image_path",return_value=candidate/"another.exe"):
                with self.assertRaisesRegex(DebugError,"candidate image"):
                    reference.OwnedNativeSession(process,1234,candidate,"0"*64)

    def test_online_refused_and_native_input_neutralized_when_predicate_raises(self):
        session=Mock();session.offline.side_effect=DebugError("online")
        with self.assertRaises(DebugError):reference._menu_press(session,0x20,lambda row:True)
        session.request.assert_not_called()
        session=Mock();record={}
        with patch.object(reference,"_read_menu_input",side_effect=[menu_sample(),menu_sample(held=0x2000),menu_sample()]),\
             self.assertRaisesRegex(RuntimeError,"predicate"):
            reference._menu_press(session,0x20,lambda row:(_ for _ in ()).throw(RuntimeError("predicate")),receipt=record)
        self.assertEqual(session.request.call_args_list[-1].args,("clear_input",))
        self.assertEqual(session.request.call_args_list[0].kwargs["frames"],0)
        self.assertEqual(record["error"],"predicate")
        self.assertTrue(record["neutral_consumed"])
        self.assertEqual(record["status"],"failed_setup")

    def test_private_bypass_requires_explicit_boolean_and_idle_native_body(self):
        session=Mock();session.read.side_effect=[bytes((10,0,0)),bytes((1,))]
        with patch.object(reference,"_guard_code"):
            with self.assertRaisesRegex(DebugError,"explicit private bypass"):
                reference.select_native_zero(session,{"exe_base":0x80010000}, {},allow_private_prerequisite=False)
        self.assertFalse(any(call.args[0]=="write_ram" for call in session.request.call_args_list))
        with self.assertRaises(ValueError):reference.select_native_zero(session,{}, {},allow_private_prerequisite="yes")

    def test_partial_setup_failure_is_written_without_launching_or_stopping_process(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
            report={};process=Mock()
            with patch.object(reference,"load_sources",side_effect=ValueError("bad original source")):
                reference.run_native_zero_reference(process,1234,Path(directory),Path("original.bin"),"0"*64,report)
            saved=json.loads((Path(directory)/"native-zero-reference/reference.json").read_text())
            self.assertEqual(saved["status"],"failed_setup")
            self.assertEqual(saved["error"],"bad original source")
            self.assertEqual(saved["ledger_status"],"unverified")
            process.terminate.assert_not_called();process.kill.assert_not_called()
            with self.assertRaises(FileExistsError):
                reference.run_native_zero_reference(process,1234,Path(directory),Path("original.bin"),"0"*64,{})

    def test_full_case_keeps_completed_artwork_pending_and_uses_held_input_then_neutral(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"],prefix="x6-native-reference-") as directory:
            session=Mock(profile={},image_path=Path(directory)/"mmx6-runtime.exe",image_sha256="a"*64)
            session.request.return_value=dict(slot0=dict(connected=True))
            session.offline.return_value=dict(active=0)
            process=Mock(pid=123)
            native_rows=[sample(10),sample(11,marker=1,visible=True),sample(12,marker=1,visible=True),
                sample(17,marker=1,visible=True),sample(18,marker=-1,visible=True,phase=1),
                sample(19,marker=-1,visible=True,phase=1),sample(25,marker=-1,visible=True,phase=2),sample(33)]
            selected_row=sample(8)
            def capture(_session,path,**_):
                Path(path).write_bytes(b"fixture capture, not artwork proof")
                return dict(surface="composed_renderer_output",path=str(path),sha256=reference.preparation.sha256(Path(path)))
            def selected(_session,_sources,receipt,**_):
                receipt.update(code_guards=[],prerequisite_bypass=True,ordinary_input_evidence_tainted=True)
                return selected_row
            with patch.object(reference,"load_sources",return_value={}),\
                 patch.object(reference,"OwnedNativeSession",return_value=session),\
                 patch.object(reference,"select_native_zero",side_effect=selected),\
                 patch.object(reference,"_guard_code"),\
                 patch.object(reference,"read_native",side_effect=native_rows),\
                 patch.object(reference,"read_trail_palettes",return_value={"fixture":True}),\
                 patch.object(reference.debug,"capture_present",side_effect=capture):
                result=reference.run_native_zero_reference(process,1234,Path(directory),Path("source.bin"),"a"*64,{},hold_ticks=6)
            self.assertEqual(result["status"],"reference_observations_completed_artwork_pending",result)
            self.assertEqual(result["artwork_review"],"pending")
            self.assertEqual(result["ledger_status"],"unverified")
            press=next(c for c in session.request.call_args_list if c.args==("press",))
            self.assertEqual(press.kwargs,dict(port=1,buttons=0x9FDF,frames=0))
            self.assertEqual(session.request.call_args_list[-1].args,("clear_input",))
            process.terminate.assert_not_called()


@unittest.skipUnless(os.environ.get("MMX6_CONTENT_DISC"),"Set explicit original raw disc path for source guards")
class OriginalSourcesTests(unittest.TestCase):
    def test_original_source_bundle_and_all_runtime_guard_extents_are_bounded(self):
        sources=reference.load_sources(Path(os.environ["MMX6_CONTENT_DISC"]))
        for key,base,windows in (("exe",sources["exe_base"],reference.EXE_GUARDS),
                                  ("menu",reference.MENU_BASE,reference.MENU_GUARDS)):
            for first,end in windows:
                self.assertEqual(len(reference._window(sources[key],base,first,end)),end-first)
        self.assertEqual(reference._sha(sources["menu"]),reference.MENU_SHA)
        self.assertEqual(reference._sha(sources["zero"]),reference.ZERO_SHA)


if __name__=="__main__":unittest.main()
