import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from audit_mmx6_audio_driver import audit, routine_metadata
from inventory_mmx6_coop_content import Executable

REPORT = Path(__file__).resolve().parents[1] / "docs/COOP_AUDIO_DRIVER_OWNERSHIP.json"


class DriverEvidence(unittest.TestCase):
    def synthetic(self):
        data = bytearray(2048 + 32)
        data[:8] = b"PS-X EXE"
        struct.pack_into("<II", data, 0x18, 0x80010000, 32)
        # One direct JAL, one indirect JALR, terminal JR RA and delay slot.
        struct.pack_into("<8I", data, 2048,
            0x0C000000 | (0x8005BE94 >> 2 & 0x03FFFFFF), 0,
            0x0040F809, 0, 0, 0, 0x03E00008, 0x27BD0018)
        return Executable(bytes(data))

    def test_exact_extent_and_direct_indirect_calls(self):
        exe = self.synthetic()
        result = routine_metadata(exe, "probe", 0x80010000, 0x80010020)
        self.assertEqual(result["direct_calls"], [{"site": "80010000", "target": "8005BE94"}])
        self.assertEqual(result["indirect_call_sites"], ["80010008"])
        self.assertEqual(result["bytes"], 32)
        changed = bytearray(exe.data)
        changed[-1] ^= 1
        self.assertNotEqual(result["sha256"], routine_metadata(Executable(bytes(changed)),
            "probe", 0x80010000, 0x80010020)["sha256"])

    def test_escaping_unaligned_and_missing_delay_slot_reject(self):
        exe = self.synthetic()
        for start, end in ((0x80010001, 0x80010020), (0x80010000, 0x80010024),
                           (0x80010000, 0x8001001C), (0x80010000, 0x80010000)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                routine_metadata(exe, "bad", start, end)

    def test_unknown_source_rejects_before_disc_access(self):
        with patch.object(Path, "read_bytes", return_value=self.synthetic().data), self.assertRaisesRegex(
                ValueError, "original SLUS"):
            audit(Path("unused"), Path("unused-disc"))

    def test_frozen_report_keeps_runtime_and_indirect_paths_open(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual((report["implementation_status"], report["local_coop"], report["netplay"]),
                         ("audit_only_no_runtime_fix", "unverified", "unverified"))
        functions = {row["name"]: row for row in report["routines"]}
        self.assertEqual(functions["driver_flush"]["indirect_call_sites"], ["8005C0A8", "8005C0D4"])
        self.assertEqual(functions["header_open"]["indirect_call_sites"], ["800604C4"])
        self.assertEqual(len(report["character_tones"]), 10)
        self.assertTrue(all(not row["noise_sample_255_slots"] for row in report["character_tones"]))
        self.assertTrue(report["remaining"])

    @unittest.skipUnless(os.environ.get("MMX6_AUDIO_EXE") and os.environ.get("MMX6_AUDIO_DISC"),
                         "Set original EXE/disc paths for source reproduction")
    def test_original_source_reproduces_frozen_report(self):
        self.assertEqual(audit(Path(os.environ["MMX6_AUDIO_EXE"]), Path(os.environ["MMX6_AUDIO_DISC"])),
                         json.loads(REPORT.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
