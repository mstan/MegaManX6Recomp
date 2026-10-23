"""Offline evidence-parser checks; no runtime or guest-memory writes."""
import struct
import unittest

from coop_debug import DebugError
from qualify_mmx6_coop_enemy_admission import (RECORD, SLOTS, STRIDE, native_43,
                                             parse_pool, preflight, resident_targeting_sample)


class NativeEnemyEvidenceTests(unittest.TestCase):
    def body(self, *, active=0x41, kind=1, record=RECORD):
        body = bytearray(STRIDE)
        body[0:7] = bytes([active, kind, 1, 0, 1, 1, 0])
        struct.pack_into("<iiI", body, 8, 416 << 16, 1080 << 16, record)
        body[0x5C] = 12
        body[0x60] = 4
        return body

    def pool(self, entries):
        pool = bytearray(SLOTS * STRIDE)
        for slot, body in entries:
            pool[slot * STRIDE:(slot + 1) * STRIDE] = body
        return pool

    def test_nonzero_slot_origin_and_native_init_without_render_flag(self):
        live, selected = parse_pool(self.pool([(17, self.body())]))
        self.assertEqual(len(live), 1)
        self.assertEqual((selected["slot"], selected["phase"], selected["hp"], selected["render"]),
                         (17, 1, 12, 0))
        self.assertEqual((selected["x"], selected["y"]), (416, 1080))

    def test_dead_stale_origin_and_other_type_do_not_prove_admission(self):
        live, selected = parse_pool(self.pool([(0, self.body(active=0)), (2, self.body(kind=2)),
                                               (3, self.body(record=RECORD + 12))]))
        self.assertIsNone(selected)
        self.assertEqual(len(live), 2)

    def test_duplicate_live_origin_is_ambiguous(self):
        with self.assertRaisesRegex(DebugError, "Multiple live"):
            parse_pool(self.pool([(1, self.body()), (9, self.body())]))

    def test_truncated_pool_cannot_qualify(self):
        with self.assertRaisesRegex(DebugError, "Truncated"):
            parse_pool(bytes(SLOTS * STRIDE - 1))

    def test_stored_wide_preference_does_not_override_active_native_43(self):
        gpu = {"width": 320, "height": 240,
               "ws": {"configured": 0, "mode": 0, "x_margin": 0, "nw_extra": 0}}
        self.assertTrue(native_43(gpu, {"native_wide": 1, "mode": 0, "nw_extra": 0}))
        gpu["ws"]["mode"] = 2
        self.assertFalse(native_43(gpu, {"native_wide": 1, "mode": 2, "nw_extra": 0}))
        self.assertFalse(native_43({}, {}))

    def test_preflight_uses_scanner_discriminator_before_admission(self):
        row = {"camera": [2, 944], "record_allocated": False, "instance": None,
               "observation": {"players": [{"x_raw": 144 << 16}]}}
        for camera_x in (0, 2, 47):
            row["camera"][0] = camera_x
            self.assertTrue(preflight(row), camera_x)
        for camera_x in (-1, 48, 80):
            row["camera"][0] = camera_x
            self.assertFalse(preflight(row), camera_x)
        row["camera"] = [2, 944]
        row["record_allocated"] = True
        self.assertFalse(preflight(row))
        row["record_allocated"] = False
        row["instance"] = {"origin": hex(RECORD)}
        self.assertFalse(preflight(row))
        row["instance"] = None
        row["camera"][1] = 943
        self.assertFalse(preflight(row))
        row["camera"][1] = 944
        row["observation"]["players"][0]["x_raw"] += 1
        self.assertFalse(preflight(row))

    def test_targeting_comparison_retains_waiting_and_active_native_action(self):
        _, target = parse_pool(self.pool([(0, self.body())]))
        row = {"instance": target,
               "observation": {"tick": 7, "players": [{"x_raw": 144 << 16}, {"x_raw": 305 << 16}]}}
        self.assertEqual(resident_targeting_sample(row)["action_plus5"], 1)
        target["action"] = 2
        self.assertEqual(resident_targeting_sample(row)["action_plus5"], 2)
        row["observation"]["players"][1]["x_raw"] = 304 << 16
        self.assertIsNone(resident_targeting_sample(row))  # Native strict <112 boundary.
        row["observation"]["players"][1]["x_raw"] = 305 << 16
        row["observation"]["players"][0]["x_raw"] = 305 << 16
        self.assertIsNone(resident_targeting_sample(row))  # P1 already near is no P2 discriminator.


if __name__ == "__main__":
    unittest.main()
