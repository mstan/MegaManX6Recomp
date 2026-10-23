"""Pure snapshot framing/evidence checks; no native execution or ledger pass."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import qualify_mmx6_coop_state as state
from coop_debug import DebugError
from mmx6_coop_private_effects import ATTACHED, END, TRAILS, parse_effect_diagnostic
from test_mmx6_coop_private_effects import publication


def private_publication(tick=10):
    raw = bytearray(publication(tick, timer=99, marker=1, visible=True, menu=True))
    raw[0x3C] = 1  # P1 owns the native menu.
    struct.pack_into("<I", raw, 28, 4)
    return bytes(raw)


def sampled(tick=10):
    client = Mock()
    client.read.side_effect = [private_publication(tick), b"\x01\x00"]
    return state.private_sample(client)


def provider(*, tick=10, bank_count=4):
    raw = private_publication(tick)
    metadata = struct.pack("<II", 0x53503658, 1)+bytes(state.HOST_RESOURCE_BYTES-8)
    core = bytearray(state.HOST_SEMANTIC_BYTES)
    core[:0x158] = raw[0x100:0x258]
    core[0x1558:0x1678] = raw[TRAILS:TRAILS+0x120]
    core[0x1678:0x1768] = raw[ATTACHED:ATTACHED+0xF0]
    # Exact source-owned scalar offsets, after full PlayerContext + lifecycle.
    at = state.HOST_PLAYER_BYTES+25+2*0x158
    core[at] = 1  # pause_owner+1
    core[at+3+0x200] = 1  # enrolled
    tail = struct.pack("<IBIB", tick, 128, 0, 0)
    cache = struct.pack("<I", bank_count)
    for index in range(bank_count):
        pixels = b"\x01"+struct.pack("<HH", 256, 0x1234+index)
        cache += struct.pack("<IHH", 0x9F010000, 0x6000+index, 0)+bytes(32)+struct.pack("<I", len(pixels))+pixels
    cache += struct.pack("<I", 1)+struct.pack("<4H", 0, 0x7800, 0, 0x7000)+bytes(32)
    return metadata+core+tail+cache


def image(payload=None, *, compress=False, build=123):
    payload = provider() if payload is None else payload
    identity = b"mmx6.local-coop"
    host = struct.pack("<4I", 0x504E534D, 1, 1, 0)+struct.pack("<3I", 1, len(identity), len(payload))+identity+payload
    ram = bytearray(2*1024*1024)
    ram[0x970A0:0x970A0+0x158] = private_publication()[0x1800:0x1958]
    ram[0xCCED0:0xCCED2] = b"\x0A\x02"
    ram[0xCF814:0xCF816] = b"\x01\x00"
    struct.pack_into("<I",ram,0xCCED0+0x90,99)
    result = struct.pack("<9I", 0x50535842, 10, 999, 0x80010000, build, 32, 42, 2, 12345)
    for tag,data in ((2,bytes(ram)), (0x16,host)):
        flags = int(compress)
        if compress:
            data = struct.pack("<I", len(data))+zlib.compress(data)
        result += struct.pack("<IIQ", tag, flags, len(data))+data
    return result


class StateWireTests(unittest.TestCase):
    def test_full_provider_offsets_bank_payload_and_native_history(self):
        parsed = state.parse_state_image(image(compress=True))
        self.assertEqual(parsed["publication_tick"], 10)
        self.assertEqual(parsed["bank_count"], 4)
        self.assertEqual(parsed["ui_bank_count"], 1)
        self.assertEqual(len(bytes.fromhex(parsed["semantic_core_hex"])), 9366)
        self.assertEqual(len(bytes.fromhex(parsed["shots_hex"])), 0x1400)
        self.assertEqual(parsed["private_body_hex"], sampled()["p2_body_hex"])
        self.assertTrue(all(state.reduce_private_restore(parsed, sampled(11), completed_tick=10).values()))

    def test_raw_and_compressed_frames_describe_same_state(self):
        self.assertEqual(state.parse_state_image(image()), state.parse_state_image(image(compress=True)))

    def test_truncation_unknown_schema_and_trailing_data_are_not_recovered(self):
        raw = image(compress=True)
        for value in (raw[:35], raw[:-1], raw+b"x"):
            with self.subTest(size=len(value)), self.assertRaises(DebugError):
                state.parse_state_image(value)
        for offset in (0, 4):
            changed = bytearray(provider());struct.pack_into("<I", changed, offset, 2)
            with self.assertRaises(DebugError):
                state.parse_state_image(image(changed))

    def test_duplicate_section_and_unbounded_inflate_are_rejected(self):
        raw = bytearray(image())
        host_at = 36+16+2*1024*1024
        struct.pack_into("<I", raw, host_at, 2)
        with self.assertRaises(DebugError):
            state.parse_state_image(raw)
        raw = bytearray(image(compress=True))
        struct.pack_into("<I", raw, 52, state.MAX_STATE_BYTES+1)
        with self.assertRaises(DebugError):
            state.parse_state_image(raw)

    def test_wrong_pixels_id_runs_and_ui_bank_fail_closed(self):
        for offset, encoded in ((state.HOST_CACHE_OFFSET+4+4,b"\xFF\xFF"),
                                (state.HOST_CACHE_OFFSET+4+44+1,b"\x00\x00"),
                                (len(provider())-40+6,b"\xFF\x7F")):
            changed = bytearray(provider());changed[offset:offset+len(encoded)] = encoded
            with self.subTest(offset=offset), self.assertRaises(DebugError):
                state.parse_state_image(image(changed))

    def test_provider_probe_rejects_hidden_input_and_pool_changes(self):
        saved = state.parse_state_image(image())
        for offset in (state.HOST_RESOURCE_BYTES+state.HOST_PLAYER_BYTES+15,
                       state.HOST_RESOURCE_BYTES+0x1558+0x5F,
                       state.HOST_RESOURCE_BYTES+0x1678+0x4F):
            changed = bytearray(provider());changed[offset] ^= 1
            restored = state.parse_state_image(image(changed))
            checks = state.reduce_provider_restore(saved, restored)
            self.assertFalse(checks["full_private_context_and_host_input_history"])
        changed = bytearray(provider());changed[state.HOST_RESOURCE_BYTES+state.HOST_PLAYER_BYTES+15] ^= 1
        self.assertFalse(state.reduce_provider_restore(saved,state.parse_state_image(image(changed)))["explicit_native_and_host_input_history"])

    def test_build_mismatch_bank_content_loss_and_wrong_asset_binding_reject(self):
        saved = state.parse_state_image(image())
        self.assertFalse(state.reduce_provider_restore(saved,state.parse_state_image(image(build=124)))["exact_current_build_key"])
        changed = bytearray(provider());changed[-1] = 1
        self.assertFalse(state.reduce_provider_restore(saved,state.parse_state_image(image(changed)))["full_retained_bank_payloads"])
        changed = bytearray(provider());changed[50] = 1
        self.assertFalse(state.reduce_provider_restore(saved,state.parse_state_image(image(changed)))["same_resource_and_original_asset_binding"])

    def test_only_publication_and_documented_presentation_tail_may_differ(self):
        saved = state.parse_state_image(image())
        changed = bytearray(provider(tick=20))
        changed[state.HOST_CORE_END+4] = 120  # presentation HUD fade
        self.assertTrue(all(state.reduce_provider_restore(saved,state.parse_state_image(image(changed))).values()))


class RestoredPublicationTests(unittest.TestCase):
    def setUp(self):
        self.saved = state.parse_state_image(image())

    def test_old_publication_after_request_is_not_after_completed_load(self):
        # A request started at5, completed at10. Cached10 is newer than5,
        # but only a publication strictly after completion10 may qualify.
        row = sampled(10)
        self.assertFalse(state.reduce_private_restore(self.saved,row,completed_tick=10)["new_publication_after_completed_load"])
        self.assertTrue(all(state.reduce_private_restore(self.saved,sampled(11),completed_tick=10).values()))

    def test_wrong_body_unknown_effect_bytes_shots_and_native_history_reject(self):
        original = sampled(11)
        for key in ("p2_body_hex", "shots_hex", "p1_body_hex"):
            changed = deepcopy(original);changed[key] = "FF"+changed[key][2:]
            self.assertFalse(all(state.reduce_private_restore(self.saved,changed,completed_tick=10).values()))
        changed = deepcopy(original);changed["trails"][0]["raw_hex"] = changed["trails"][0]["raw_hex"][:-2]+"FF"
        self.assertFalse(state.reduce_private_restore(self.saved,changed,completed_tick=10)["full_private_trails"])
        changed = deepcopy(original);changed["attached"][2]["raw_hex"] = "FF"+changed["attached"][2]["raw_hex"][2:]
        self.assertFalse(state.reduce_private_restore(self.saved,changed,completed_tick=10)["full_private_attached"])
        changed = deepcopy(original);changed["native_previous"] ^= 1
        self.assertFalse(state.reduce_private_restore(self.saved,changed,completed_tick=10)["native_input_history"])
        changed = deepcopy(original);changed["observation"]["native_timer"] += 1
        self.assertFalse(state.reduce_private_restore(self.saved,changed,completed_tick=10)["saved_native_clock_restored"])

    def test_lost_positive_window_or_other_menu_owner_cannot_qualify(self):
        for mutate in (lambda r:r.update(marker=0), lambda r:r["observation"].update(pause_owner=2),
                       lambda r:r.update(native_menu_state=[0,0])):
            row = sampled(11);mutate(row)
            self.assertFalse(state.reduce_private_restore(self.saved,row,completed_tick=10)["native_p1_pause_retains_live_dash"])

    def test_one_rpc_pools_cannot_be_stitched_with_a_stale_base(self):
        raw = bytearray(private_publication(11));struct.pack_into("<I",raw,0x1A0C,10)
        client = Mock();client.read.return_value = bytes(raw)
        with self.assertRaises(DebugError):
            state.private_sample(client)
        client.read.assert_called_once_with(state.DIAGNOSTIC_ADDRESS, END)


class PrivateStateCliTests(unittest.TestCase):
    def parse(self, extra):
        parser = state.make_parser()
        args = parser.parse_args(["--build","build","--source","source","--disc","original.cue","--output","output",*extra])
        state.validate_options(parser,args)
        return args

    def test_existing_body_only_command_and_explicit_private_case(self):
        self.assertFalse(self.parse([]).private_effects)
        self.assertTrue(self.parse(["--private-effects","--expected-sha","a"*64]).private_effects)

    def test_private_case_requires_exact_sha_and_bounded_timeouts(self):
        for extra in (["--private-effects"], ["--expected-sha","A"*64], ["--boot-timeout","nan"],
                      ["--progress-timeout","inf"], ["--progress-timeout","61"]):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.parse(extra)

    def test_prepared_wrong_executable_or_source_card_rejected_before_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/"mmx6-runtime.exe").write_bytes(b"candidate")
            prepared = dict(exe_sha256=state.sha256(root/"mmx6-runtime.exe"), automated_profile=True,
                            source_card=None,source_card_sha256=None)
            for change in ({"source_card":"owner.mcd"}, {"source_card_sha256":"a"*64}, {"exe_sha256":"b"*64}):
                (root/"preparation.json").write_text(json.dumps(dict(prepared,**change)))
                with patch.object(state.baseline,"candidate_environment") as lifecycle, self.assertRaises(DebugError):
                    state.staged_image_binding(root,prepared["exe_sha256"])
                lifecycle.assert_not_called()

    def test_failed_warm_setup_or_behavior_is_retained_without_a_cold_launch(self):
        for original_status in ("failed_setup", "failed_behavior"):
            with tempfile.TemporaryDirectory() as temporary:
                args = self.parse(["--private-effects","--expected-sha","a"*64])
                args.output = Path(temporary)/"new-private-output"
                phase = dict(status="failed", exercise=dict(status=original_status,error="retained native failure"))
                with patch.object(state,"prepare"), patch.object(state,"staged_image_binding",return_value={"exe":"a"*64}), \
                        patch.object(state.baseline,"run",return_value=phase) as lifecycle:
                    result = state.run(args)
                self.assertEqual(lifecycle.call_count,1)
                self.assertEqual(result["status"],original_status)
                self.assertEqual(result["phases"]["warm"]["exercise"]["error"],"retained native failure")
                self.assertEqual(json.loads((args.output/"qualification.json").read_text())["status"],original_status)


class NativeRecoveryEvidenceTests(unittest.TestCase):
    def recovery(self):
        def row(tick, timer, marker, phase=0, visible=True):
            return parse_effect_diagnostic(publication(tick,timer=timer,marker=marker,
                visible=visible,trail_phase=phase)).json()
        return [row(20,110,1), row(22,140,1), row(24,150,-1,1), row(26,158,-1,2), row(28,162,0,visible=False)]

    def test_positive_continuation_does_not_consume_negative_drain_bound(self):
        self.assertTrue(all(state.reduce_restored_retirement(sampled(),self.recovery()).values()))

    def test_marker_zero_without_all_slots_retired_or_phase2_is_insufficient(self):
        rows = self.recovery();rows[-1]["trails"][0]["active"] = 1
        self.assertFalse(state.reduce_restored_retirement(sampled(),rows)["finite_all_three_retired"])
        rows = self.recovery();rows[3]["trails"][0]["phase"] = 1
        rows[3]["trails"][1]["phase"] = rows[3]["trails"][2]["phase"] = 1
        self.assertFalse(state.reduce_restored_retirement(sampled(),rows)["native_phase1_and_phase2_observed"])

    def test_retrigger_stalled_clock_hp_or_p1_motion_cannot_qualify(self):
        mutations = (
            lambda r:r[3].update(marker=1),
            lambda r:r[3]["observation"].update(native_timer=r[2]["observation"]["native_timer"]),
            lambda r:r[2]["observation"]["players"][1].update(hp=28),
            lambda r:r[2]["observation"]["players"][0].update(x_raw=0),
            lambda r:r[-1]["observation"].update(native_timer=184))
        for mutate in mutations:
            rows=self.recovery();mutate(rows)
            self.assertFalse(all(state.reduce_restored_retirement(sampled(),rows).values()))


class MenuClosePublicationTests(unittest.TestCase):
    def test_native_owner_resets_on_next_stage_entry(self):
        saved=sampled();closing=sampled(11)
        self.assertEqual(state.private_resume_phase(saved,closing,gameplay_seen=False,closing_tick=None),(False,None))
        closing["observation"]["native_phase"]=0
        self.assertEqual(state.private_resume_phase(saved,closing,gameplay_seen=False,closing_tick=None),(False,11))
        self.assertEqual(state.private_resume_phase(saved,closing,gameplay_seen=False,closing_tick=11),(False,11))
        opened=deepcopy(closing);opened["observation"].update(tick=12,pause_owner=0)
        self.assertEqual(state.private_resume_phase(saved,opened,gameplay_seen=False,closing_tick=11),(True,11))

    def test_persistent_or_returning_owner_and_closing_corruption_refuse(self):
        saved=sampled();closing=sampled(12);closing["observation"]["native_phase"]=0
        for kwargs in (dict(gameplay_seen=False,closing_tick=11),dict(gameplay_seen=True,closing_tick=None)):
            with self.assertRaises(DebugError):state.private_resume_phase(saved,closing,**kwargs)
        for mutate in (lambda r:r["observation"].update(pause_owner=2),
                       lambda r:r["observation"]["players"][1].update(hp=28),
                       lambda r:r["observation"]["players"][0].update(x_raw=0),
                       lambda r:r["observation"].update(scene_owner=1)):
            changed=deepcopy(closing);mutate(changed)
            with self.assertRaises(DebugError):state.private_resume_phase(saved,changed,gameplay_seen=False,closing_tick=None)


if __name__ == "__main__":
    unittest.main()
