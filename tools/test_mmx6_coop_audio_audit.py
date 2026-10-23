"""Native audio metadata tests; no game or speaker output."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest

from audit_mmx6_coop_audio import audit, bank_metadata, subassets

REPORT = Path(__file__).resolve().parents[1] / "docs/COOP_AUDIO_NATIVE_AUDIT.json"


def synthetic_bank():
    # Two records deliberately reference different VAB handles in one group.
    offset, programs = 16, 1
    header = bytearray(offset + 32 + 2048 + programs * 512 + 512)
    struct.pack_into("<II", header, 0, (3 << 24) | offset, 16)
    header[8:16] = bytes((0x83, 0, 0xC0, 20, 0x81, 1, 0x70, 3))
    struct.pack_into("<4sIII", header, offset, b"pBAV", 7, 0, len(header) - offset + 16)
    struct.pack_into("<HHH", header, offset + 18, programs, 2, 1)
    return header, bytes(16)


class MetadataTests(unittest.TestCase):
    def test_cross_bank_records_and_explicit_voice_slots_are_preserved(self):
        header, body = synthetic_bank()
        result = bank_metadata(header, body, 3)
        self.assertEqual(result["referenced_vab_handles"], [1, 3])
        self.assertEqual(result["cross_bank_records"], [1])
        self.assertEqual(result["sound_records"][0]["first_voice"], 20)
        self.assertEqual(result["sound_records"][0]["tone_start"], 12)
        self.assertEqual(result["sound_records"][1]["first_voice"], 3)

    def test_malformed_bank_extents_and_body_sizes_reject(self):
        header, body = synthetic_bank()
        cases = [(header[:7], body), (header, body[:-1]), (header, body + bytes(16))]
        bad = copy.copy(header)
        struct.pack_into("<I", bad, 0, (3 << 24) | (len(header) + 4))
        cases.append((bad, body))
        bad = copy.copy(header)
        bad[16:20] = b"xxxx"
        cases.append((bad, body))
        bad = copy.copy(header)
        struct.pack_into("<H", bad, 16 + 18, 128)
        cases.append((bad, body))
        for h, b in cases:
            with self.subTest(header_size=len(h), body_size=len(b)), self.assertRaises(ValueError):
                bank_metadata(h, b, 3)

    def test_dat_members_cannot_escape_descriptor_extents(self):
        data = bytearray(4096)
        struct.pack_into("<IIII", data, 0, 1, len(data), 6, 2049)
        with self.assertRaisesRegex(ValueError, "escapes"):
            subassets(data)
        with self.assertRaises(ValueError):
            subassets(bytes(32))

    def test_frozen_native_sources_expose_collision_without_claiming_a_fix(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["implementation_status"], "audit_only_no_runtime_fix")
        self.assertEqual((report["local_coop"], report["netplay"]), ("unverified", "unverified"))
        self.assertEqual(report["state_observations"]["per_voice_record_stride"], 0x38)
        self.assertEqual([row["member"] for row in report["player_banks"]], list(range(85, 90)))
        for row in report["player_banks"]:
            voices = row["banks"][1]
            self.assertEqual(voices["sample_type"], "00020303")
            self.assertEqual(voices["cross_bank_records"], [17])
            self.assertEqual(voices["sound_records"][0]["first_voice"], 20)
            if row["member"] == 85:
                self.assertEqual(voices["sound_records"][12]["first_voice"], 20)
            else:
                self.assertTrue(voices["sound_records"][12]["empty"])
            self.assertEqual(voices["status"], "unverified")

    @unittest.skipUnless(os.environ.get("MMX6_AUDIO_EXE") and os.environ.get("MMX6_AUDIO_DISC"),
                         "Set MMX6_AUDIO_EXE and MMX6_AUDIO_DISC for original-source reproduction")
    def test_original_sources_reproduce_frozen_metadata(self):
        actual = audit(Path(os.environ["MMX6_AUDIO_EXE"]), Path(os.environ["MMX6_AUDIO_DISC"]))
        self.assertEqual(actual, json.loads(REPORT.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
