"""Boundary/revision tests for read-only native MMX6 content extraction.

Optional original-data checks use MMX6_CONTENT_EXE and MMX6_CONTENT_DISC.
No game process, source disc write, save or network connection is used.
"""
import json
import os
from pathlib import Path
import struct
import unittest

import inventory_mmx6_coop_content as content


class MalformedInputTests(unittest.TestCase):
    def test_executable_header_and_declared_payload_are_bounded(self):
        for data in (b"", b"PS-X EXE", b"x" * 2048):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                content.Executable(data)
        image = bytearray(2052)
        image[:8] = b"PS-X EXE"
        struct.pack_into("<II", image, 0x18, 0x80010000, 8)
        with self.assertRaisesRegex(ValueError, "Truncated"):
            content.Executable(image)
        struct.pack_into("<I", image, 0x1C, 4)
        exe = content.Executable(image)
        self.assertEqual(exe.offset(0x80010000, 4), 2048)
        for address, count in ((0x8000FFFF, 1), (0x80010001, 4), (0x80010000, -1)):
            with self.subTest(address=address, count=count), self.assertRaises(ValueError):
                exe.offset(address, count)

    def test_placement_list_uses_its_own_exact_terminator(self):
        base = 0x800E9860
        record = struct.pack("<4B2h", 0x10, 4, 127, 4, -1, 32767)
        terminator = struct.pack("<4B2h", 0, 0, 0, 15, 0, 0)
        unrelated = struct.pack("<4B2h", 0, 1, 2, 3, 20, 30)
        result = content.placement_list(record + terminator + unrelated, base, base)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["subtype"], result[0]["x"], result[0]["y"]), (127, -1, 32767))
        # Native termination compares byte3 to 15, not its low nibble.
        flagged = bytearray(record)
        flagged[3] = 0x1F
        self.assertEqual(len(content.placement_list(flagged + terminator, base, base)), 1)

    def test_placement_list_rejects_truncation_bad_address_and_missing_end(self):
        base = 0x800E9860
        record = struct.pack("<4B2h", 0, 4, 1, 4, 1, 2)
        for data, address in ((record, base), (record[:7], base),
                              (record, base - 4), (record, base + 1)):
            with self.subTest(size=len(data), address=address), self.assertRaises(ValueError):
                content.placement_list(data, address, base)
        with self.assertRaisesRegex(ValueError, "QA bound"):
            content.placement_list(record * 4096, base, base)

    def test_checkpoint_pointers_cannot_escape_the_authored_record_region(self):
        image = bytearray(2048 + 0x80000)
        image[:8] = b"PS-X EXE"
        struct.pack_into("<II", image, 0x18, 0x80010000, 0x80000)
        exe = content.Executable(image)
        struct.pack_into("<I", image, exe.offset(content.CHECKPOINT_ROOT, 4),
                         content.CHECKPOINT_ROOT - 4)
        for record in (content.RECORD_START - 4, content.RECORD_START + 1, content.POINTER_START):
            struct.pack_into("<I", image, exe.offset(content.CHECKPOINT_ROOT - 4, 4), record)
            with self.subTest(record=record), self.assertRaisesRegex(ValueError, "record"):
                content.checkpoint_inventory(exe)
        struct.pack_into("<I", image, exe.offset(content.CHECKPOINT_ROOT, 4),
                         content.CHECKPOINT_ROOT + 4)
        with self.assertRaisesRegex(ValueError, "table"):
            content.checkpoint_inventory(exe)

    def test_archive_rejects_gaps_truncation_and_extra_descriptors(self):
        archive = bytearray((2 + 59) * 2048)
        for index in range(59):
            struct.pack_into("<II", archive, index * 8, 2 + index, 4)
        self.assertEqual(len(content.archive_members(archive)), 59)
        bad = bytearray(archive)
        struct.pack_into("<I", bad, 8, 4)
        with self.assertRaisesRegex(ValueError, "extent"):
            content.archive_members(bad)
        with self.assertRaises(ValueError):
            content.archive_members(archive[:-2048])
        struct.pack_into("<II", archive, 59 * 8, 61, 4)
        with self.assertRaisesRegex(ValueError, "count"):
            content.archive_members(archive)


class FrozenReportTests(unittest.TestCase):
    def test_committed_inventory_is_auditable_and_has_no_gameplay_passes(self):
        path = Path(__file__).resolve().parents[1] / "docs" / "COOP_X6_CONTENT.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["source_sha256"], content.EXE_SHA256)
        self.assertEqual(report["bin_sha256"], content.BIN_SHA256)
        self.assertEqual(len(report["locations"]), 115)
        for key, count in (("placement_sections", 1964), ("secondary_placement_sections", 365)):
            self.assertEqual(len(report[key]), 23)
            self.assertEqual(sum(len(row["placements"]) for row in report[key]), count)
        self.assertEqual([r["native_id"] for r in report["reploids"]], list(range(128)))
        obligations = report["campaign_obligations"] + report["mechanics_obligations"]
        self.assertEqual(len({row["id"] for row in obligations}), len(obligations))
        self.assertEqual(len(report["campaign_obligations"]), 23)
        def check_unverified(value):
            if isinstance(value, dict):
                if "status" in value:
                    self.assertEqual(value["status"], "unverified")
                if "checks" in value:
                    self.assertEqual(set(value["checks"].values()), {"unverified"})
                for item in value.values():
                    check_unverified(item)
            elif isinstance(value, list):
                for item in value:
                    check_unverified(item)
        check_unverified(report)


@unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                     "Set MMX6_CONTENT_EXE and MMX6_CONTENT_DISC for original-data checks")
class OriginalDataTests(unittest.TestCase):
    def test_original_sources_reproduce_the_frozen_inventory(self):
        report = content.inventory(Path(os.environ["MMX6_CONTENT_EXE"]),
                                   disc_path=Path(os.environ["MMX6_CONTENT_DISC"]))
        frozen = Path(__file__).resolve().parents[1] / "docs" / "COOP_X6_CONTENT.json"
        self.assertEqual(report, json.loads(frozen.read_text(encoding="utf-8")))

    def test_modified_or_other_revision_executable_is_rejected(self):
        # Use the caller-owned scratch directory instead of an OS Temp default.
        import tempfile
        data = bytearray(Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes())
        data[-1] ^= 1
        with tempfile.TemporaryDirectory(prefix="mmx6-content-", dir=os.environ["TEMP"]) as scratch:
            path = Path(scratch) / "modified.exe"
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "Unsupported EXE"):
                content.inventory(path)


if __name__ == "__main__":
    unittest.main()
