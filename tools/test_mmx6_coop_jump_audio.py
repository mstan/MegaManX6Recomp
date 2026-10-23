"""Pure protocol/reducer tests; optional originals reproduce metadata, never run it."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import struct
from unittest.mock import patch

import mmx6_coop_jump_audio as audio


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT/"docs/COOP_JUMP_AUDIO_CONTRACT.json").read_text(encoding="utf-8"))


def wire(seq=0, frame=0, kind="KEYON", voice=20):
    return dict(seq=seq, frame=frame, kind=kind, v=voice, addr="0x01000",
                pitch="0x0478", adsr_lo="0x80FF", adsr_hi="0x1FC0",
                vol_l="0x1000", vol_r="0x1000")


def reply(*rows, total=None):
    return dict(ok=True, total=len(rows) if total is None else total,
                count=len(rows), events=list(rows))


def voices():
    result = dict(ok=True, **{k: "0x0000" for k in ("ctrl", "main_l", "main_r")},
                  **{k: "0x000000" for k in ("kon", "koff", "pmon", "non", "eon", "endx", "active_mask")})
    result["voices"] = [dict(v=i, active=1, vol_l="0x0000", vol_r="0x0000", pitch="0x0478",
        adsr_lo="0x80FF", adsr_hi="0x1FC0", phase="0x0000", env="0x0000",
        start="0x01000", loop="0x01000", cur_addr="0x01000", repeat_addr="0x01000",
        flags="0x01", sample_idx=28, env_phase=3, vol_cur_l=0, vol_cur_r=0) for i in range(24)]
    return result


class EventTests(unittest.TestCase):
    def reject(self, value, after=None):
        with self.assertRaises(audio.AudioQualificationError):
            audio.parse_events(value, after)

    def test_zero_based_first_event_is_retained(self):
        total, events = audio.parse_events(reply(wire()), after=0)
        self.assertEqual(total, 1)
        self.assertEqual([e["seq"] for e in events], [0])

    def test_suffix_is_not_a_frame_count(self):
        total, events = audio.parse_events(reply(wire(8, 100), wire(9, 100), total=10), 9)
        self.assertEqual(total, 10)
        self.assertEqual([e["seq"] for e in events], [9])
        self.assertEqual(events[0]["frame"], 100)

    def test_missing_suffix_reset_duplicate_reorder(self):
        for value, after in ((reply(wire(4), total=5), 3), (reply(wire(), total=1), 2),
                             (reply(wire(), wire()), None), (reply(wire(1), wire()), None)):
            with self.subTest(value=value, after=after):
                self.reject(value, after)

    def test_malformed_or_truncated_events_refused(self):
        good = reply(wire())
        for key, value in (("ok", 1), ("total", True), ("count", True),
                           ("count", 4097), ("events", []), ("total", 0)):
            bad = copy.deepcopy(good); bad[key] = value
            with self.subTest(key=key, value=value): self.reject(bad)
        self.reject(reply(total=1))

    def test_event_field_bounds_and_exact_hex(self):
        for key, value in (("seq", True), ("frame", -1), ("kind", "OTHER"), ("v", 48),
                           ("addr", "0x80000"), ("pitch", "0478"), ("adsr_hi", "0x1FC00")):
            row = wire(); row[key] = value
            with self.subTest(key=key, value=value): self.reject(reply(row))

    def test_irq_and_private_event_schema_is_explicit(self):
        audio.parse_events(reply(wire(voice=47)))
        audio.parse_events(reply(wire(kind="IRQ", voice=255)))
        self.reject(reply(wire(kind="IRQ", voice=20)))
        self.reject(reply(wire(voice=255)))

    def test_unsigned_engine_frame_wrap_and_regression(self):
        audio.parse_events(reply(wire(0, 0xFFFFFFFF), wire(1, 0)))
        self.reject(reply(wire(0, 10), wire(1, 9)))


class VoiceTests(unittest.TestCase):
    def test_end_stop_can_leave_active_silent_voice(self):
        snapshot = audio.parse_voices(voices())
        self.assertEqual(snapshot["voices"][20]["active"], 1)
        self.assertEqual(snapshot["voices"][20]["env"], 0)
        self.assertEqual(snapshot["voices"][20]["env_phase"], 3)
        self.assertEqual(snapshot["voices"][20]["sample_idx"], 28)

    def test_exact_voice_set_required(self):
        for change in (lambda v: v["voices"].pop(),
                       lambda v: v["voices"][1].update(v=0),
                       lambda v: v["voices"][0].update(active=True),
                       lambda v: v["voices"][0].update(sample_idx=29),
                       lambda v: v["voices"][0].update(env="0x8000"),
                       lambda v: v["voices"][0].update(cur_addr="0x80000"),
                       lambda v: v["voices"][0].update(vol_cur_l=-32769)):
            value = voices(); change(value)
            with self.subTest(value=value["voices"][0]):
                with self.assertRaises(audio.AudioQualificationError): audio.parse_voices(value)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CONTRACT

    def test_frozen_source_contract(self):
        self.assertEqual(audio.validate_contract(self.contract), audio.CONTRACT_SHA256)
        self.assertEqual(len(self.contract["tones"]), 18)
        self.assertEqual(len(self.contract["native_windows"]), 9)
        self.assertEqual(self.contract["local"], "unverified")
        self.assertEqual(self.contract["netplay"], "unverified")
        for tone in self.contract["tones"]:
            self.assertEqual(tone["pitch"], 0x478 if tone["group"] == 3 else
                             (0x5A8 if tone["character"] == "X" else 0x5F5))

    def test_source_sample_or_pass_fabrication_refused(self):
        for mutate in (lambda c: c.update(local="passed"),
                       lambda c: c["tones"][0].update(sample_sha256="0"*64),
                       lambda c: c["tones"][1].update(pitch=0),
                       lambda c: c["native_windows"].pop()):
            value = copy.deepcopy(self.contract); mutate(value)
            with self.assertRaises(ValueError): audio.validate_contract(value)

    def test_native_pitch_rejects_unbounded_inputs(self):
        for values in ((-1, 0, 60, 0), (60, 128, 60, 0), (True, 0, 60, 0)):
            with self.assertRaises(ValueError): audio.native_pitch(*values, lambda _: 0)

    @unittest.skipUnless(os.getenv("MMX6_AUDIO_EXE") and os.getenv("MMX6_AUDIO_DISC"),
                         "Set both original-source paths for bounded metadata reproduction")
    def test_original_metadata_reproduction(self):
        actual = audio.build_contract(Path(os.environ["MMX6_AUDIO_EXE"]), Path(os.environ["MMX6_AUDIO_DISC"]))
        self.assertEqual(actual, self.contract)
        audio.validate_contract(actual)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.contract = CONTRACT
        self.first, self.second, self.end = audio.parse_events(
            reply(wire(0, 10), wire(1, 11), wire(2, 20, "END_STOP")))[1]
        self.events = [self.first, self.second, self.end]
        self.identities = {}
        for event, character, record in ((self.first, "X", 2), (self.second, "Zero", 4)):
            tone = next(t for t in self.contract["tones"] if (t["character"], t["group"], t["record"]) ==
                        (character, 3, record))
            self.identities[event["seq"]] = dict(tone=copy.deepcopy(tone), sample_matches=True)

    def compare(self):
        return audio.compare_overlap(self.events, self.first, self.second, self.identities, 0)

    def test_replacement_cannot_be_a_natural_end_pass(self):
        result = self.compare()
        self.assertTrue(result["collision_observed"])
        self.assertTrue(result["checks"]["vocal_lifetime_overlap"])
        self.assertFalse(result["checks"]["p1_natural_end"])
        self.assertTrue(result["checks"]["p2_natural_end"])
        self.assertFalse(all(result["checks"].values()))

    def test_source_sample_pitch_adsr_mismatch(self):
        for key, value in (("sample_matches", False), ("tone", None)):
            before = copy.deepcopy(self.identities)
            self.identities[1][key] = value
            self.assertFalse(self.compare()["checks"]["p2_source_sample"])
            self.identities = before
        self.identities[1]["tone"]["character"] = "X"
        self.assertFalse(self.compare()["checks"]["p2_source_sample"])
        self.identities[1]["tone"]["character"] = "Zero"
        for key in ("pitch", "adsr_lo", "adsr_hi"):
            before = self.second[key]; self.second[key] ^= 1
            self.assertFalse(self.compare()["checks"]["p2_pitch_adsr"])
            self.second[key] = before

    def test_early_natural_end_is_not_overlap(self):
        end = dict(self.end, seq=1, frame=10)
        second = dict(self.second, seq=2)
        result = audio.compare_overlap([self.first, end, second], self.first, second, self.identities, 0)
        self.assertFalse(result["checks"]["vocal_lifetime_overlap"])

    def test_keyoff_loop_unobserved_are_distinct(self):
        for kind, disposition in (("KEYOFF", "keyed_off"), ("END_LOOP", "looped")):
            row = dict(self.end, kind=kind)
            self.assertEqual(audio.lifetime([self.first, row], self.first)["disposition"], disposition)
        self.assertEqual(audio.lifetime([self.first], self.first)["disposition"], "unobserved")

    def test_invalid_selected_event_or_frame_regression_refused(self):
        with self.assertRaises(ValueError):
            audio.compare_overlap(self.events, self.second, self.first, self.identities, 0)
        with self.assertRaises(ValueError):
            audio.compare_overlap([], self.first, self.second, self.identities, 0)
        with self.assertRaises(audio.AudioQualificationError):
            audio.lifetime([self.first, dict(self.end, frame=9)], self.first)


class ProbeTests(unittest.TestCase):
    def observer(self, request):
        return audio.AudioObserver(None, request, CONTRACT)

    def test_unmapped_address_does_not_claim_source_sample(self):
        def unexpected(*args, **kwargs): self.fail("Unmapped tone must not probe SPU")
        found = self.observer(unexpected).identify(dict(addr=0x7FFFF), dict(bases=[0]*16))
        self.assertFalse(found["sample_matches"])

    def test_driver_uses_exact_original_table_extents(self):
        raw, records = bytearray(0x1A8), bytearray(0x80)
        for i in range(16):
            struct.pack_into("<I", raw, 0x40+i*4, 0x80010000+i*4)
            struct.pack_into("<I", raw, 0x168+i*4, 0x1000+i*16)
            struct.pack_into("<I", records, i*4, i+100)
            struct.pack_into("<I", records, 0x40+i*4, 0x80020000+i*8)
        struct.pack_into("<H", raw, 0x80, 0x1234)
        raw[0x108:0x118] = bytes(range(16))
        calls = []
        class Client:
            def read(self, address, count):
                calls.append((address, count))
                return bytes(raw if address == 0x800E5588 else records)
        observer = self.observer(lambda *a, **k: self.fail("No RPC for native table read"))
        observer.client = Client()
        tables = observer.driver()
        self.assertEqual(calls, [(0x800E5588, 0x1A8), (0x80097738, 0x80)])
        self.assertEqual(tables["headers"][15], 0x8001003C)
        self.assertEqual(tables["bases"][15], 0x10F0)
        self.assertEqual(tables["record_pointers"][15], 0x80020078)
        self.assertEqual(tables["record_ends"], list(range(100,116)))
        self.assertEqual(tables["release_adjust"], 0x1234)
        self.assertEqual(tables["vab_status"], list(range(16)))

    def test_truncated_driver_table_refused(self):
        observer = self.observer(lambda *a, **k: None)
        class Client:
            def read(self, address, count): return bytes(count-1)
        observer.client = Client()
        with self.assertRaises(audio.AudioQualificationError): observer.driver()

    def test_sample_read_is_exact_bounded_and_never_retains_bytes(self):
        tone = next(t for t in CONTRACT["tones"] if
                    (t["character"], t["group"], t["record"]) == ("Zero", 3, 2))
        calls = []
        def request(command, **fields):
            calls.append((command, fields))
            return dict(ok=True, addr=f'0x{fields["addr"]:05X}', len=fields["len"], hex="00"*fields["len"])
        found = self.observer(request).identify(dict(addr=tone["offset"]), dict(bases=[0]*16))
        self.assertEqual(calls, [("spu_ram", dict(addr=tone["offset"], len=tone["bytes"]))])
        self.assertFalse(found["sample_matches"])
        self.assertEqual(found["observed_sha256"], hashlib.sha256(bytes(tone["bytes"])).hexdigest())
        self.assertNotIn("hex", found)

    def test_truncated_spu_reply_refused(self):
        tone = next(t for t in CONTRACT["tones"] if
                    (t["character"], t["group"], t["record"]) == ("Zero", 3, 2))
        with self.assertRaises(audio.AudioQualificationError):
            self.observer(lambda *a, **k: dict(ok=True, addr="0x01060", len=1, hex="00")).identify(
                dict(addr=tone["offset"]), dict(bases=[0]*16))

    def test_adapter_refuses_online_or_unilateral_inputs_before_controls(self):
        for mode, path in (("netplay", "published_host"), ("local", "debug_sio")):
            calls = []
            ctx = dict(mode=mode, input_path=path, clients=[None], report={}, candidate=ROOT,
                       expected_sha256="0"*64, request=lambda *a, **k: calls.append(a),
                       hold=lambda *a: calls.append(a), native_advance=lambda *a: calls.append(a))
            with self.assertRaises(ValueError): audio.jump_overlap_smoke(ctx, CONTRACT)
            self.assertEqual(calls, [])


class ContextTests(unittest.TestCase):
    def test_native_rng_silence_is_inconclusive_and_releases_both_seats(self):
        with tempfile.TemporaryDirectory(prefix="jump-audio-context-") as directory:
            candidate = Path(directory)
            if candidate.drive.lower() not in ("f:", "g:"):
                self.fail("Tests require TEMP/TMP on F:/G:")
            payload = b"synthetic-context-identity-only"
            digest = hashlib.sha256(payload).hexdigest()
            (candidate/"mmx6-runtime.exe").write_bytes(payload)
            (candidate/"preparation.json").write_bytes(json.dumps(dict(exe_sha256=digest)).encode("ascii"))
            controls, report, state = [], {}, dict(jumping=False)
            class Observer:
                events = []
                def __init__(self, *args): pass
                def poll(self):
                    players = [dict(character=c, form=f, state=1, action=2, hp=32, speech_gate=0,
                                    airborne=0, ground=True, y=100, vy=0) for c,f in ((0,1),(1,5))]
                    if state["jumping"]:
                        players[0].update(action=6, y=90, vy=-1, airborne=1, ground=False)
                    return dict(observation=dict(ready=1,enrolled=1,failed=0,mailbox=0,native_mode=10,
                                native_phase=0,scene_owner=0,pause_owner=0,lifecycle=(0,0)),
                                players=players,event_total=0,new_events=[])
                def driver(self): return dict(release_adjust=0,vab_status=[1]*16)
            def hold(seat, bits, frames, label):
                controls.append((seat,bits,frames,label))
                if bits: state["jumping"] = True
            def advance(*args): state["jumping"] = False
            ctx = dict(mode="local",input_path="published_host",clients=[None],report=report,
                       candidate=candidate,expected_sha256=digest,hold=hold,native_advance=advance,
                       request=lambda cmd,**fields: voices())
            with patch.object(audio,"AudioObserver",Observer):
                result = audio.jump_overlap_smoke(ctx,CONTRACT,max_attempts=1)
            self.assertEqual(result["status"],"inconclusive_native_rng_no_two_voice_window")
            self.assertEqual(len(result["attempts"]),1)
            self.assertEqual(result["attempts"][0]["first_keys"],[])
            self.assertEqual([(c[0],c[1]) for c in controls],[(0,audio.CROSS),(0,0),(1,0)])
            self.assertEqual(report["jump_audio"],[result])

    def test_setup_failure_retains_prefix_and_cleanup_error_is_not_success(self):
        with tempfile.TemporaryDirectory(prefix="jump-audio-failure-") as directory:
            candidate = Path(directory)
            if candidate.drive.lower() not in ("f:", "g:"):
                self.fail("Tests require TEMP/TMP on F:/G:")
            payload=b"synthetic-context-failure-only";digest=hashlib.sha256(payload).hexdigest()
            (candidate/"mmx6-runtime.exe").write_bytes(payload)
            (candidate/"preparation.json").write_bytes(json.dumps(dict(exe_sha256=digest)).encode("ascii"))
            calls,report=[],{}
            class Observer:
                events=[]
                def __init__(self,*args):pass
                def poll(self):raise audio.AudioQualificationError("synthetic truncated diagnostic")
            def hold(seat,bits,frames,label):
                calls.append((seat,bits))
                if seat==0:raise RuntimeError("synthetic neutral failure")
            ctx=dict(mode="local",input_path="published_host",clients=[None],report=report,
                     candidate=candidate,expected_sha256=digest,hold=hold,
                     native_advance=lambda *a: self.fail("No advancement after setup failure"),
                     request=lambda *a,**k: self.fail("No RPC after setup failure"))
            with patch.object(audio,"AudioObserver",Observer):
                with self.assertRaisesRegex(audio.AudioQualificationError,"truncated diagnostic"):
                    audio.jump_overlap_smoke(ctx,CONTRACT)
            self.assertEqual(calls,[(0,0),(1,0)])
            result=report["jump_audio"][0]
            self.assertEqual(result["status"],"failed_cleanup")
            self.assertIn("truncated diagnostic",result["error"]["message"])
            self.assertEqual(result["neutral_errors"][0]["seat"],0)

    def test_candidate_mismatch_refuses_before_control_or_rpc(self):
        with tempfile.TemporaryDirectory(prefix="jump-audio-") as directory:
            candidate = Path(directory)
            if candidate.drive.lower() not in ("f:", "g:"):
                self.fail("Tests require TEMP/TMP on F:/G:")
            (candidate/"mmx6-runtime.exe").write_bytes(b"synthetic-not-an-executable")
            (candidate/"preparation.json").write_bytes(b'{"exe_sha256":"bad"}')
            calls = []
            ctx = dict(mode="local", input_path="published_host", clients=[None], report={},
                       candidate=candidate, expected_sha256="0"*64,
                       request=lambda *a, **k: calls.append(a), hold=lambda *a: calls.append(a),
                       native_advance=lambda *a: calls.append(a))
            with self.assertRaises(ValueError): audio.jump_overlap_smoke(ctx, CONTRACT)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
