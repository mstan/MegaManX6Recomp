"""Pure native reentry protocol/source/ownership tests, no native launches."""
from copy import deepcopy
import itertools
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import mmx6_coop_native_reentry as reentry
from test_mmx6_coop_private_effects import publication
import coop_debug as debug


def response():
    raw=bytearray(reentry.READ_BYTES)
    def put(address,payload):raw[address-reentry.READ_BASE:address-reentry.READ_BASE+len(payload)]=payload
    play=bytearray(0x468);play[:3]=bytes((4,4,0));play[0xC]=13;play[0x5B:0x5D]=bytes((32,32));play[0x5E:0x60]=bytes((1,1))
    put(reentry.PLAY,play);put(reentry.FRONT,bytes((7,1))+bytes(22))
    put(reentry.CURRENT,bytes((1,))+bytes(reentry.CURRENT_BYTES-1))
    put(reentry.PLAYER+0xE7,bytes((1,)))
    put(reentry.MENU+4,bytes((1,6,2,1)))
    return dict(addr=hex(reentry.READ_BASE),len=reentry.READ_BYTES,hex=raw.hex())


def native_row(*,decoded=(0,0,0)):
    return dict(decoded=list(decoded),mode=[4,4,0],fade=0)


class NativeReentryProtocolTests(unittest.TestCase):
    def test_one_atomic_fixed_read_covers_buffer_body_pad_play_frontend_and_native_menu(self):
        client=Mock();client.request.return_value=response();evidence=[]
        row=reentry.read_native(client,evidence=evidence)
        client.request.assert_called_once_with("read_ram",addr=hex(reentry.READ_BASE),len=reentry.READ_BYTES)
        client.read.assert_not_called()
        self.assertEqual(reentry.READ_BYTES,0x5EB88)
        self.assertLess(reentry.READ_BYTES*2+256,1024*1024)
        self.assertEqual(row["current_header"],1)
        self.assertEqual(row["mode"],[4,4,0])
        self.assertEqual(row["menu"],[1,6,2,1])
        self.assertEqual(len(bytes.fromhex(row["play_hex"])),0x468)
        self.assertEqual(evidence[0]["status"],"accepted")
        self.assertEqual(evidence[0]["snapshot_sha256"],row["snapshot_sha256"])

    def test_wrong_mapping_short_long_or_invalid_payload_is_rejected_and_retained(self):
        original=response()
        for change in (dict(addr="0x80070CC5"),dict(len=reentry.READ_BYTES-1),dict(len=True),
                       dict(hex=original["hex"][:-2]),dict(hex=original["hex"]+"00"),
                       dict(hex="ZZ"+original["hex"][2:])):
            with self.subTest(change=next(iter(change))):
                client=Mock();client.request.return_value=dict(original,**change);evidence=[]
                with self.assertRaises(debug.DebugError):reentry.read_native(client,evidence=evidence)
                self.assertEqual(evidence[0]["status"],"rejected")
                self.assertIn("error",evidence[0])

    def test_title_input_readiness_requires_the_source_fade_and_blocking_gates(self):
        row=dict(frontend=[1,3,0,0],frontend_blocked=0,fade=0,stage=14,section=0)
        self.assertTrue(reentry.title_ready(row))
        for mutation in (dict(frontend_blocked=1),dict(fade=1),dict(frontend=[1,2,0,0]),dict(stage=13)):
            self.assertFalse(reentry.title_ready(dict(row,**mutation)))
        prompt=dict(frontend=[7,1,0,0],fade=0,current_header=1)
        self.assertTrue(reentry.current_prompt(prompt))
        self.assertFalse(reentry.current_prompt(dict(prompt,current_header=255)))


class NativeReentryInputTests(unittest.TestCase):
    def test_malformed_or_bypass_input_is_rejected_before_sampler_control(self):
        for mask,path in ((0,"offline_native"),(0x10000,"offline_native"),(8,"sio")):
            ctx=dict(set_input=Mock(),input_path=path)
            with self.assertRaises(ValueError):
                reentry.pulse(ctx,[],mask,lambda row:True,Mock(),label="invalid")
            ctx["set_input"].assert_not_called()

    def test_real_decoder_hold_response_and_consumed_neutral_are_distinct(self):
        ctx=dict(set_input=Mock(),input_path="offline_native");attempts=[]
        observe=Mock(side_effect=[native_row(),native_row(decoded=(0x40,0,0x40)),
            native_row(decoded=(0,0x40,0)),native_row()])
        with patch.object(reentry.time,"sleep"):
            reentry.pulse(ctx,attempts,0x4000,lambda row:True,observe,label="actual native Cross")
        self.assertEqual([c.args for c in ctx["set_input"].call_args_list],[(0,0x4000),(0,0)])
        self.assertTrue(attempts[0]["pressed_observed"] and attempts[0]["neutral_consumed"])
        self.assertEqual(len([r for r in attempts[0]["samples"] if r["stage"]=="neutral after"]),2)

    def test_ack_or_automatic_mode_transition_without_native_held_input_is_a_failure(self):
        ctx=dict(set_input=Mock(),input_path="published_host");attempts=[]
        with patch.object(reentry.time,"sleep"),patch.object(reentry.time,"monotonic",side_effect=itertools.count(0,.01)):
            with self.assertRaisesRegex(reentry.ReentryError,"response timed out"):
                reentry.pulse(ctx,attempts,8,lambda row:True,lambda label:native_row(),label="Start",timeout=.05)
        self.assertFalse(attempts[0]["transition_observed"])
        self.assertTrue(attempts[0]["neutral_consumed"])
        self.assertEqual(ctx["set_input"].call_args_list[-1].args,(0,0))

    def test_both_published_peers_must_consume_the_same_original_button(self):
        ctx=dict(set_input=Mock(),input_path="published_host");attempts=[]
        neutral=dict(peers=[native_row(),native_row()])
        first_only=dict(peers=[native_row(decoded=(0x800,0,0x800)),native_row()])
        both=dict(peers=[native_row(decoded=(0x800,0,0x800)) for _ in range(2)])
        observe=Mock(side_effect=[neutral,first_only,both,neutral])
        with patch.object(reentry.time,"sleep"):
            reentry.pulse(ctx,attempts,8,lambda row:True,observe,label="both native Start")
        self.assertEqual(len([r for r in attempts[0]["samples"] if r["stage"]=="response"]),2)
        self.assertEqual(attempts[0]["path"],"published_host")

    def test_original_failure_survives_a_failed_neutral_release(self):
        ctx=dict(set_input=Mock(side_effect=[OSError("owned sampler refused"),OSError("neutral refused")]),input_path="offline_native")
        attempts=[]
        with self.assertRaisesRegex(OSError,"owned sampler refused"):
            reentry.pulse(ctx,attempts,8,lambda row:True,lambda label:native_row(),label="Start")
        self.assertEqual(attempts[0]["release_error"],"neutral refused")


class NativeReentryOwnershipTests(unittest.TestCase):
    def saved_and_restored(self):
        # Independent literal source examples:8001BB04..40 resource stores,
        # 8001BAF8 tanks,8001BC54..90 22x32 campaign rows and8001BCF0 arrays.
        saved=bytearray(reentry.CURRENT_BYTES);saved[0]=1;play=bytearray(0x468)
        saved[0x36:0x3C]=bytes((32,40,48,56,0xA,0x11))
        play[0x5B:0x5D]=bytes((32,40));play[0x61:0x63]=bytes((48,56));play[0x60]=0xA;play[0x5F]=0x11
        saved[0x14:0x16]=bytes((2,0x10));play[0x6A:0x6C]=bytes((2,0x10))
        saved[0xCE+7]=0xA5;play[0x178+7]=0xA5
        saved[0x390+8]=7;play[0x43C+8]=7
        saved=bytes(saved)
        before=dict(current_header=saved[0],current_data_hex=saved.hex(),current_data_sha256=reentry.sha(saved))
        restored=dict(before,play_hex=play.hex(),mode=[4,4,0],fade=0,campaign_character=0)
        return before,restored

    def test_current_data_compares_source_imported_progress_not_abandoned_body_hp(self):
        before,restored=self.saved_and_restored()
        self.assertTrue(all(reentry.reduce_current_data(before,restored)["checks"].values()))
        self.assertNotIn("abandoned_body_hp",reentry.reduce_current_data(before,restored)["checks"])

    def test_one_rescue_flag_or_max_resource_change_or_guest_promotion_remains_failed(self):
        before,restored=self.saved_and_restored()
        for offset in (0x178,0x5B,0x6A,0x43C):
            changed=bytearray.fromhex(restored["play_hex"]);changed[offset]^=1
            result=reentry.reduce_current_data(before,dict(restored,play_hex=changed.hex()))
            self.assertFalse(result["checks"]["source_imported_campaign_fields_match"])
            self.assertTrue(result["differences"])
        self.assertFalse(reentry.reduce_current_data(before,dict(restored,campaign_character=1))["checks"]["primary_campaign_is_x_at_native_map"])
        self.assertFalse(reentry.reduce_current_data(before,dict(restored,current_data_sha256="changed"))["checks"]["original_current_buffer_retained"])

    def test_old_publication_newer_than_pre_quit_still_cannot_pass_reentry(self):
        old=debug.parse_diagnostic(publication(100)[:debug.DIAGNOSTIC_BYTES]).json()
        # Tick100 is newer than a hypothetical pre-Quit10 but it is the first
        # observed diagnostic at actual native arrival and may still be stale.
        self.assertFalse(reentry.fresh_reentry([old],[deepcopy(old)]))
        current=debug.parse_diagnostic(publication(101)[:debug.DIAGNOSTIC_BYTES]).json()
        self.assertTrue(reentry.fresh_reentry([old],[current]))
        current["players"][0]["character"]=1
        self.assertFalse(reentry.fresh_reentry([old],[current]))
        self.assertFalse(reentry.fresh_reentry([],[]))

    def test_new_game_defaults_are_not_current_data_resource_retention(self):
        client=Mock();client.request.return_value=response();row=reentry.read_native(client)
        self.assertEqual(reentry.new_game_defaults(row),dict(campaign_character=0,armor=1,unlocks=1,max_hp=[32,32],native_body_form=1))
        changed=dict(row,campaign_character=1,armor=5)
        self.assertNotEqual(reentry.new_game_defaults(changed),reentry.new_game_defaults(row))

    def test_projected_guest_identity_cannot_supply_primary_default_form_evidence(self):
        base=dict(mode=[10,0,0],campaign_character=0,native_player=dict(character=0))
        self.assertTrue(reentry.primary_scope(base))
        self.assertFalse(reentry.primary_scope(dict(base,campaign_character=1,native_player=dict(character=1))))
        self.assertFalse(reentry.primary_scope(dict(base,campaign_character=0,native_player=dict(character=1))))

    def test_empty_current_data_is_refused_before_any_quit_control_or_source_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            diag=debug.parse_diagnostic(publication(10)[:debug.DIAGNOSTIC_BYTES]).json();debugger=Mock()
            debugger.observe.return_value=SimpleNamespace(json=lambda:diag)
            ctx=dict(mode="local",input_path="offline_native",candidate_exe_sha256="a"*64,
                clients=[Mock()],both=lambda fn:[fn(0)],set_input=Mock(),debug=debugger,report={},output=Path(temporary),
                hold=Mock(),native_advance=Mock(),transport_window=Mock())
            row=dict(mode=[10,0,0],current_header=255)
            with patch.object(reentry,"load_sources",return_value=dict(original={})),patch.object(reentry,"read_native",return_value=row):
                with self.assertRaisesRegex(reentry.ReentryError,"empty; refused before any Quit"):
                    reentry.native_reentry_smoke(ctx,original_disc="original.bin",expected_exe_sha256="a"*64)
            ctx["set_input"].assert_not_called();ctx["clients"][0].read.assert_not_called()
            case=ctx["report"]["native_reentry"][0]
            self.assertEqual(case["status"],"failed_setup")
            self.assertEqual(case["code_guards"],[])
            self.assertEqual(case["ledger_status"],"unverified")

    def test_separate_new_game_flow_uses_real_final_choice_and_new_arrival_anchor_before_guest_helper(self):
        # Deterministic protocol-state fixture only; never a gameplay pass.
        with tempfile.TemporaryDirectory() as temporary:
            client=Mock();client.read.side_effect=lambda address,size:bytes(size)
            debugger=Mock();state=dict(mode=[10,0,0],stage=0,section=0,campaign_character=0,armor=1,unlocks=1,
                frontend=[6,2,0,0],frontend_blocked=0,fade=0,choice=0,menu=[0,0,0,0],quit_page=0,
                current_header=255,current_data_hex=(bytes((255,))+bytes(reentry.CURRENT_BYTES-1)).hex(),
                current_data_sha256="fixture-buffer",dialogue_hex=bytes(16).hex(),decoded=[0,0,0])
            play=bytearray(0x468);play[0x5B:0x5D]=bytes((32,32));state["play_hex"]=play.hex()
            body=bytearray(0x158);body[0xE7]=1
            state.update(native_player=dict(character=0),native_body_hex=body.hex())
            controls=[];ticks=iter(range(10,100));arrivals=[]
            def set_input(seat,bits):
                controls.append((seat,bits));native_bits=((bits&255)<<8)|(bits>>8)
                state["decoded"]=[native_bits,0,native_bits]
                if not bits:return
                if bits==8 and state["frontend"][:2]==[1,3]:state["frontend"]=[6,1,0,0]
                elif bits==8:state.update(mode=[10,2,0],menu=[1,0,0,0])
                elif bits==1:state.update(menu=[1,6,2,1],quit_page=0,choice=0)
                elif bits==0x40:state["choice"]=1
                elif bits==0x10:state["choice"]=0
                elif bits==0x4000:
                    if state["frontend"][:2]==[6,1]:state.update(frontend=[6,2,0,0],mode=[10,0,0],stage=0,menu=[0,0,0,0])
                    elif state["quit_page"]==0:state["quit_page"]=1
                    else:
                        self.assertEqual(state["choice"],0)
                        state.update(frontend=[1,3,0,0],stage=14,menu=[0,0,0,0])
            def diagnostic(client):
                tick=next(ticks);raw=bytearray(publication(tick,menu=state["mode"][1]==2))
                raw[0x3C]=int(state["mode"][1]==2)
                result=debug.parse_diagnostic(bytes(raw[:debug.DIAGNOSTIC_BYTES]))
                if len(controls)>10:arrivals.append(tick)
                return result
            debugger.observe.side_effect=diagnostic;debugger.capture_present.return_value=dict(path="fixture-only.png")
            ctx=dict(mode="local",input_path="offline_native",candidate_exe_sha256="a"*64,
                clients=[client],both=lambda fn:[fn(0)],set_input=set_input,debug=debugger,report={},output=Path(temporary),
                hold=Mock(),native_advance=Mock(),transport_window=Mock())
            sources=dict(original={},exe_base=0x80010000,exe=bytes(0x20000),title=bytes(0x8000))
            with patch.object(reentry,"load_sources",return_value=sources), \
                    patch.object(reentry,"read_native",side_effect=lambda *args,**kwargs:deepcopy(state)), \
                    patch.object(reentry.menu,"personal_menu_smoke",return_value=dict(checks=dict(fixture_guest_contract=True))) as guest:
                case=reentry.native_reentry_smoke(ctx,original_disc="original.bin",expected_exe_sha256="a"*64,route="new_game")
            self.assertEqual(case["status"],reentry.SUCCESS)
            self.assertEqual(case["artwork_review"],"pending")
            self.assertEqual([bits for seat,bits in controls if bits],[8,1,0x40,0x4000,0x10,0x4000,8,0x4000])
            self.assertGreater(case["reentered_diagnostic"][0]["tick"],case["arrival_diagnostic_anchor"][0]["tick"])
            self.assertNotIn("current_data_reductions",case)
            self.assertNotIn("resolved_core_mod_crc_completed",case["checks"])
            self.assertEqual(guest.call_args.kwargs["cursor_buttons"],(0x40,0x10))
            self.assertTrue(all(seat==0 for seat,bits in controls))
            self.assertTrue(all(c["neutral_consumed"] for c in case["inputs"]))


class OriginalSourceTests(unittest.TestCase):
    def test_original_import_and_title_branch_words_match_the_audited_contract(self):
        path=Path("G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin")
        if not path.is_file():self.skipTest("Local original disc is required for this optional source check")
        sources=reentry.load_sources(path)
        self.assertEqual(reentry.sha(sources["title"]),reentry.TITLE_SHA)
        def word(name,address):
            base=sources["exe_base"] if name=="exe" else reentry.TITLE_BASE
            return struct.unpack_from("<I",sources[name],address-base)[0]
        # Actual final Quit starts the frontend then ends the old game thread.
        self.assertEqual(word("exe",0x8001FE20),0x0C007497)
        self.assertEqual(word("exe",0x8001FE28),0x0C004CE8)
        # Current-data header FF branches away from the current-data prompt.
        self.assertEqual(word("title",0x800EA644),0x90440CC4)
        self.assertEqual(word("title",0x800EA648),0x240300FF)
        # The actual current-data branch imports80070CC4; no fake menu state.
        self.assertEqual(word("title",0x800EA900),0x0C006E87)
        self.assertEqual(word("title",0x800EA904),0x24840CC4)
        self.assertEqual(word("exe",0x8001BB40),0xA123005F)  # saved unlocks -> PLAY+5F
        self.assertEqual(word("exe",0x8001E16C),0xA0A2005F)  # New Game replaces unlocks with1


if __name__=="__main__":unittest.main()
