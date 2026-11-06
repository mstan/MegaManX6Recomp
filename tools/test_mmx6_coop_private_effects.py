"""Parser/reducer fixtures only: no running-game or ledger qualification."""
from dataclasses import replace
import hashlib
import os
import re
from pathlib import Path
import struct
import tempfile
import tomllib
import unittest
from unittest.mock import Mock

from coop_debug import DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES, DebugError, UnstableObservation
from mmx6_coop_private_effects import (
    ATTACHED, END, EXTENSION_BYTES, HEADER, MAGIC, NATIVE_TRAILS, PLAYER, SCHEMA,
    TRAILS, TRAIL_CLUTS, NativeEffect, observe_effects, parse_effect_diagnostic,
    reduce_effect_menu_freeze, reduce_effect_render_review, reduce_zero_dash,
)


def publication(tick=10, *, timer=None, marker=0, visible=False, trail_phase=0,
                menu=False, unavailable=False):
    data = bytearray(END)
    struct.pack_into("<II", data, 0, 0x434F4F50, tick)
    struct.pack_into("<I", data, 36, tick if timer is None else timer)
    struct.pack_into("<III", data, 0x80, 1, DIAGNOSTIC_BYTES, (tick*2) & 0xFFFFFFFF)
    data[0x8C:0x8F] = bytes((1, 1, 0))
    data[0x90:0x92] = bytes((10, 2 if menu else 0))
    data[0x3C] = 2 if menu else 0
    struct.pack_into("<II", data, 0x94, 0x12345678, 1)
    for base, character in ((0x100, 1), (0x1800, 0)):
        data[base] = data[base+3] = data[base+4] = 1
        data[base+2] = character
        data[base+5] = 0x0C if marker else 2
        data[base+0x5C] = 32
        struct.pack_into("<ii", data, base+8, (144+character*80) << 16, 1080 << 16)
        struct.pack_into("<IIHH", data, base+0x38, 0x9F010000, 0x9F020000, 0x0500, 0x7800)
        data[base+0x47] = 7
    struct.pack_into("<b", data, 0x18C, marker)
    data[8:16] = data[0x108:0x110]
    data[24] = data[0x15C]
    if unavailable:
        return bytes(data)
    struct.pack_into("<IIII", data, HEADER, MAGIC, SCHEMA, EXTENSION_BYTES, tick)
    for i in range(3):
        start = TRAILS + i*0x60
        data[start] = 0x11
        data[start+2] = i
        data[start+3] = data[start+4] = int(visible)
        data[start+5] = trail_phase
        data[start+0x16] = 4
        struct.pack_into("<ii", data, start+8, (220-i*5) << 16, 1080 << 16)
        struct.pack_into("<ii", data, start+0x18, (219-i*5) << 16, 1080 << 16)
        struct.pack_into("<IIHH", data, start+0x38, 0x9F010000, 0x9F020000, 0x0500, TRAIL_CLUTS[i])
        data[start+0x47] = 7
        struct.pack_into("<IHHH", data, start+0x50, PLAYER if not i else NATIVE_TRAILS+(i-1)*0x60,
                         3, 8, (5-i)*2)
        if i < 2:
            start = ATTACHED+i*0x50
            data[start] = 0x21
            data[start+2] = i
            data[start+0x16] = 2
            struct.pack_into("<I", data, start+0x30, 0x8007789C)
            struct.pack_into("<IHH", data, start+0x3C, 0x9F030000, 0, 0x7802)
    return bytes(data)


def row(*args, **kwargs):
    return parse_effect_diagnostic(publication(*args, **kwargs))


def dash():
    return (row(10), [row(11, marker=1, visible=True), row(12, marker=1, visible=True)],
            [row(13, marker=-1, visible=True, trail_phase=1),
             row(20, marker=-1, visible=True, trail_phase=2), row(30)])


def reduce_dash(before=None, active=None, released=None, **kwargs):
    defaults = dash()
    return reduce_zero_dash(before or defaults[0], defaults[1] if active is None else active,
        defaults[2] if released is None else released, mode="local", input_path="offline_native",
        input_receipts=[dict(path="offline_native", seat=1, pressed=0x2000, accepted=True, bypasses=[], before_tick=10, after_tick=12),
                        dict(path="offline_native", seat=1, pressed=0, accepted=True, bypasses=[], before_tick=12, after_tick=13)], **kwargs)


class EffectParserTests(unittest.TestCase):
    def test_one_atomic_rpc_preserves_base_and_every_native_record_byte(self):
        raw = bytearray(publication(marker=1, visible=True))
        raw[TRAILS+0x5F] = 0xA7  # Unknown byte is retained, not reconstructed.
        client = Mock()
        client.read.return_value = bytes(raw)
        parsed = observe_effects(client)
        client.read.assert_called_once_with(DIAGNOSTIC_ADDRESS, END)
        self.assertEqual(parsed.observation.schema, 1)
        self.assertEqual(parsed.marker, 1)
        self.assertEqual(parsed.trails[0].raw_hex, raw[TRAILS:TRAILS+0x60].hex())
        self.assertEqual(parsed.trails[1].parent, NATIVE_TRAILS)
        self.assertEqual(parsed.attached[1].parent, PLAYER)
        self.assertEqual(parsed.json()["trails"][0]["clut"], 0x780D)

    def test_frozen_base_only_is_explicitly_unavailable_without_guessed_image(self):
        parsed = row(unavailable=True)
        self.assertFalse(parsed.available)
        self.assertEqual(parsed.unavailable_reason, "extension_unavailable")
        self.assertEqual(parsed.trails, ())
        self.assertNotIn("37cdc", str(parsed.json()))
        self.assertFalse(any(reduce_dash(before=parsed)["checks"].values()))

    def test_bad_length_partial_unknown_header_and_torn_tick_reject(self):
        for raw in (publication()[:-1], publication()+b"x", publication()[:DIAGNOSTIC_BYTES]):
            with self.assertRaises(DebugError):
                parse_effect_diagnostic(raw)
        for offset, value in ((HEADER, 0), (HEADER+4, 2), (HEADER+8, END)):
            raw = bytearray(publication())
            struct.pack_into("<I", raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(DebugError):
                parse_effect_diagnostic(bytes(raw))
        raw = bytearray(publication(unavailable=True))
        raw[TRAILS] = 0x11
        with self.assertRaises(DebugError):
            parse_effect_diagnostic(bytes(raw))
        raw = bytearray(publication())
        struct.pack_into("<I", raw, HEADER+12, 9)
        with self.assertRaises(UnstableObservation):
            parse_effect_diagnostic(bytes(raw))

    def test_base_odd_marker_and_bad_mirror_are_not_masked_by_valid_extension(self):
        for offset, value in ((0x88, 21), (8, 1)):
            raw = bytearray(publication())
            struct.pack_into("<I", raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(UnstableObservation):
                parse_effect_diagnostic(bytes(raw))
        client = Mock()
        client.read.return_value = bytes(raw)
        with self.assertRaises(UnstableObservation):
            observe_effects(client)
        self.assertEqual(client.read.call_count, 1)  # No hidden multi-RPC transaction.

    def test_native_link_type_slot_phase_counter_clut_and_resource_negatives(self):
        mutations = [(TRAILS, 0), (TRAILS, 0x12), (TRAILS+2, 1), (TRAILS+3, 2),
                     (TRAILS+4, 0), (TRAILS+5, 3), (TRAILS+0x50, 0),
                     (TRAILS+0x54, 4), (TRAILS+0x56, 9), (TRAILS+0x58, 11),
                     (TRAILS+0x42, 0), (TRAILS+0x16, 2),
                     (ATTACHED+2, 3)]
        for offset, value in mutations:
            raw = bytearray(publication(marker=1, visible=True))
            raw[offset] = value
            with self.subTest(offset=offset, value=value), self.assertRaises(DebugError):
                parse_effect_diagnostic(bytes(raw))
        for offset in (TRAILS+0x38, TRAILS+0x3C):
            raw = bytearray(publication(marker=1, visible=True))
            struct.pack_into("<I", raw, offset, 0xDEADBEEF)
            with self.assertRaises(DebugError):
                parse_effect_diagnostic(bytes(raw))
        with self.assertRaises(DebugError):
            NativeEffect.parse(bytes(0x5F), "trails", 0)

    def test_zeroed_falcon_and_allocated_hidden_records_do_not_require_visible_resources(self):
        parsed = row()
        self.assertEqual(parsed.attached[2].allocation, 0)
        self.assertEqual(parsed.attached[2].raw_hex, bytes(0x50).hex())
        raw = bytearray(publication())
        struct.pack_into("<I", raw, TRAILS+0x38, 0)
        self.assertEqual(parse_effect_diagnostic(bytes(raw)).trails[0].compression, 0)
        raw[TRAILS+3] = raw[TRAILS+4] = 1
        with self.assertRaises(DebugError):
            parse_effect_diagnostic(bytes(raw))


class DashReducerTests(unittest.TestCase):
    def test_native_marker_all_three_visibility_phase_chain_and_finite_retirement(self):
        result = reduce_dash()
        self.assertTrue(all(result["checks"].values()), result)
        self.assertEqual(result["status"], "partial_evidence")
        self.assertNotIn("passed", result)

    def test_input_ack_or_preexisting_marker_alone_is_not_accepted_dash(self):
        self.assertFalse(reduce_dash(active=[row(11)])["checks"]["accepted_native_dash_marker"])
        self.assertFalse(reduce_dash(before=row(10, marker=1, visible=True))["checks"]["accepted_native_dash_marker"])
        before, active, released = dash()
        wrong = replace(active[0], observation=replace(active[0].observation,
            players=(active[0].observation.players[0], replace(active[0].observation.players[1], action=48))))
        self.assertFalse(reduce_dash(active=[wrong])["checks"]["accepted_native_dash_marker"])
        with self.assertRaisesRegex(ValueError, "original input"):
            reduce_zero_dash(before, active, released, mode="netplay", input_path="direct_sio", input_receipts=[])
        bad = reduce_zero_dash(before, active, released, mode="netplay", input_path="published_host",
            input_receipts=[dict(path="published_host", seat=1, pressed=1, accepted=True, bypasses=["marker write"]),
                            dict(path="published_host", seat=1, pressed=0, accepted=True, bypasses=[])])
        self.assertFalse(bad["checks"]["original_input_receipts"])

    def test_missing_intermediate_drain_hard_clear_retrigger_or_unretired_tail_cannot_pass(self):
        for released in ([row(13), row(30)],
                         [row(13, marker=-1, visible=True, trail_phase=1), row(30)],
                         [row(13, marker=-1, visible=True, trail_phase=1),
                          row(20, marker=1, visible=True), row(30)],
                         [row(13, marker=-1, visible=True, trail_phase=1),
                          row(20, marker=-1, visible=True, trail_phase=2)]):
            self.assertFalse(reduce_dash(released=released)["checks"]["finite_native_retirement"])
        self.assertFalse(reduce_dash(max_retirement_ticks=8)["checks"]["finite_native_retirement"])

    def test_one_trail_or_resource_leak_cannot_be_hidden_by_final_idle(self):
        before, active, released = dash()
        raw = bytearray(publication(11, marker=1, visible=True))
        raw[TRAILS+2*0x60+3] = raw[TRAILS+2*0x60+4] = 0
        self.assertFalse(reduce_dash(active=[parse_effect_diagnostic(bytes(raw))])["checks"]["three_visible_native_trails"])
        raw = bytearray(publication(11, marker=1, visible=True))
        struct.pack_into("<I", raw, TRAILS+0x38, 0x80010000)
        bad = parse_effect_diagnostic(bytes(raw))
        checks = reduce_dash(active=[bad])["checks"]
        self.assertFalse(checks["owner_frame_resources"])
        self.assertFalse(checks["native_links_and_cluts_retained"])
        wrong_phase = replace(active[0], observation=replace(active[0].observation, native_phase=2))
        self.assertFalse(reduce_dash(active=[wrong_phase])["checks"]["eligible_fixed_roster"])

    def test_stale_backwards_and_wrap_publications(self):
        self.assertFalse(reduce_dash(active=[row(10, marker=1, visible=True)])["checks"]["ordered_publications"])
        before, active, released = dash()
        rows = [before, *active, *released]
        wrapped = [replace(r, observation=replace(r.observation,
            tick=(r.observation.tick-12) & 0xFFFFFFFF,
            native_timer=(r.observation.native_timer-12) & 0xFFFFFFFF)) for r in rows]
        self.assertTrue(reduce_dash(wrapped[0], wrapped[1:3], wrapped[3:])["checks"]["ordered_publications"])

    def test_stale_missing_or_overlapping_input_receipts_cannot_bind_a_new_native_dash(self):
        before, active, released = dash()
        receipts = [dict(path="offline_native", seat=1, pressed=0x2000, accepted=True, bypasses=[], before_tick=10, after_tick=12),
                    dict(path="offline_native", seat=1, pressed=0, accepted=True, bypasses=[], before_tick=12, after_tick=13)]
        for old in (dict(receipts[0], before_tick=1, after_tick=2),
                    dict(receipts[0], after_tick=31),
                    {k: v for k, v in receipts[0].items() if k != "before_tick"},
                    dict(receipts[0], after_tick=13)):
            reduced = reduce_zero_dash(before, active, released, mode="local", input_path="offline_native",
                                      input_receipts=[old, receipts[1]])
            self.assertFalse(reduced["checks"]["original_input_receipts"])


class MenuAndRenderReducerTests(unittest.TestCase):
    def window(self):
        return [row(tick, timer=50, marker=1, visible=True, menu=True) for tick in (20, 24, 28)]

    def resumed(self):
        raw = bytearray(publication(29, timer=51, marker=1, visible=True))
        struct.pack_into("<H", raw, TRAILS+0x54, 2)
        return parse_effect_diagnostic(bytes(raw))

    def test_nonempty_native_pools_freeze_then_resume_with_original_context(self):
        checks = reduce_effect_menu_freeze(self.window(), resumed=self.resumed())
        self.assertTrue(all(checks.values()), checks)
        p1_owned = [replace(r, observation=replace(r.observation, pause_owner=1)) for r in self.window()]
        self.assertTrue(all(reduce_effect_menu_freeze(p1_owned, owner=0, resumed=self.resumed()).values()))
        self.assertFalse(reduce_effect_menu_freeze(p1_owned, owner=1)["native_personal_menu_owned"])

    def test_empty_pools_frozen_engine_wrong_owner_or_transient_mutation_reject(self):
        empty = [row(tick, timer=50, menu=True) for tick in (20, 24, 28)]
        self.assertFalse(reduce_effect_menu_freeze(empty)["visible_trail_window"])
        same = [self.window()[0]]*3
        self.assertFalse(reduce_effect_menu_freeze(same)["publications_advanced"])
        window = self.window()
        for field, value, key in (("pause_owner", 1, "native_personal_menu_owned"),
                                  ("native_timer", 51, "native_timer_frozen")):
            changed = list(window)
            changed[1] = replace(changed[1], observation=replace(changed[1].observation, **{field: value}))
            self.assertFalse(reduce_effect_menu_freeze(changed)[key])
        raw = bytearray(publication(24, timer=50, marker=1, visible=True, menu=True))
        raw[ATTACHED+0x4F] = 1  # Complete pool comparison includes unknown bytes.
        window[1] = parse_effect_diagnostic(bytes(raw))
        self.assertFalse(reduce_effect_menu_freeze(window)["complete_private_pools_frozen"])
        self.assertFalse(reduce_effect_menu_freeze(self.window(), resumed=self.window()[-1])[
            "gameplay_resume_advances_private_effects"])

    def test_visibility_is_separate_from_verified_capture_and_explicit_artwork_review(self):
        visible = row(11, marker=1, visible=True)
        self.assertEqual(reduce_effect_render_review(visible, {}, {}), dict(
            native_visible_window=True, composed_capture_artifact=False, explicit_native_artwork_review=False))
        with tempfile.TemporaryDirectory(prefix="x6-effect-render-") as directory:
            path = Path(directory)/"present.png"
            path.write_bytes(b"fixture capture artifact, not native artwork")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            capture = dict(path=str(path), sha256=digest, surface="composed_renderer_output",
                before=dict(seq=1), completion=dict(seq=2, wrote=1))
            review = dict(capture_sha256=digest, status="matched_native_reference", owner="Zero/P2",
                visible_trail_slots=[0, 1, 2], cluts=list(TRAIL_CLUTS), reference="fixture source", retained_colors="matched", limits=[])
            self.assertTrue(all(reduce_effect_render_review(visible, capture, review).values()))
            for bad in (dict(capture, sha256="0"*64), dict(capture, surface="software_vram"),
                        dict(capture, completion=dict(seq=1, wrote=1)), dict(capture, completion=dict(seq=2, wrote=0)),
                        dict(capture, path="C:/Temp/effects.png")):
                self.assertFalse(reduce_effect_render_review(visible, bad, review)["composed_capture_artifact"])
            for bad in ({}, dict(review, retained_colors="pending"), dict(review, capture_sha256="0"*64),
                        dict(review, owner="X/P2"), dict(review, cluts=[0x7800]*3), dict(review, limits=["no native reference"])):
                self.assertFalse(reduce_effect_render_review(visible, capture, bad)["explicit_native_artwork_review"])


class OriginalGateTargetSourceTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                         "Pinned original EXE/disc not supplied")
    def test_gate_live_target_and_producer_words_match_original_member24(self):
        import inventory_mmx6_coop_content as content
        root=Path(__file__).resolve().parents[1]
        image=Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes()
        self.assertEqual(content.sha256(image),content.EXE_SHA256)
        exe=content.Executable(image)
        disc=content.RawDisc(Path(os.environ["MMX6_CONTENT_DISC"]))
        try:archive=disc.extent(211185,1665024)
        finally:disc.stream.close()
        self.assertEqual(content.sha256(archive),content.BIN_SHA256)
        member=content.archive_members(archive)[24]
        self.assertEqual(member['sha256'],'cde2ea7634a20b92c710384c00483586fd1e2c0b641da4b9e12515fb78d86fe2')
        payload=archive[member['sector']*2048:][:member['size']]
        self.assertEqual(struct.unpack_from('<H',image,exe.offset(0x8006DB78+36*2,2))[0],24)
        self.assertEqual(exe.word(0x8006DC6C+36*4),0x800F5F88)
        self.assertEqual(exe.word(0x8006DD24+36*4),0x800F60BC)
        word=lambda address:struct.unpack_from('<I',payload,address-content.OVERLAY_BASE)[0]
        for address,value in [(0x800F6074,0x800F49F0),(0x800F6124,0x800F0A24),
                              (0x800F772C,0x800F3BFC),(0x800F7730,0x800F3D74)]:
            self.assertEqual(word(address),value)
        source=(root/'src/mods/mmx6_coop_intro_target.inc').read_text()
        for name,start,end in [('gate_homing_target_words',0x800F3EFC,0x800F4024),
                               ('gate_homing_producer_words',0x800F1944,0x800F1970)]:
            body=re.search(r'static const uint32_t '+name+r'\[\]=\{(.*?)\};',source,re.S)
            self.assertIsNotNone(body)
            expected=[int(x,16)for x in re.findall(r'0x([0-9A-F]+)u',body.group(1))]
            self.assertEqual(expected,[word(address)for address in range(start,end,4)])
        plugin=(root/'src/mods/mmx6_coop_plugin.c').read_text()
        hooks=re.findall(r'psx_mod_register_instruction_plugin\("mmx6.local-coop.prototype",(0x[0-9A-F]+)u,(0x[0-9A-F]+)u,gate_homing_target\)',plugin)
        self.assertEqual([int(a,16)for a,_ in hooks],[0x800F3F08,0x800F3F54,0x800F3FB4,0x800F3FC4])
        for address,instruction in hooks:self.assertEqual(int(instruction,16),word(int(address,16)))
        # Compiled overlays read these declarations; runtime registration alone
        # covers the sealed interpreter but cannot emit native interceptions.
        for config in ('game.toml', 'packaging/release/game.toml'):
            declared = tomllib.loads((root/config).read_text())['recompiler']['mod_instruction_sites']
            self.assertFalse({int(a,16) for a,_ in hooks} - {int(a,16) for a in declared}, config)
        # The target LH must retire before its operand hook: PSX loads have
        # one instruction of delay. Negative-X SLT is the original jump delay.
        self.assertEqual([word(a)for a in (0x800F3F4C,0x800F3F50,0x800F3F54)],
                         [0x8465000E,0x9623000E,0x00C5202A])
        self.assertEqual([word(a)for a in (0x800F3FAC,0x800F3FB0,0x800F3FB4)],
                         [0x8444000A,0x0803CFF2,0x0064182A])


if __name__ == "__main__":
    unittest.main()
