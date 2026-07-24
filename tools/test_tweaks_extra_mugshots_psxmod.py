#!/usr/bin/env python3
"""Tests for the Hunter/Dr. Light extra mugshot package."""

from __future__ import annotations

import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_extra_mugshots_psxmod as extra


class ExtraMugshotPackageTests(unittest.TestCase):
    def test_manifest_shape_from_empty_overlay_plan(self) -> None:
        manifest = tomllib.loads(extra.build_manifest([], {}))
        self.assertEqual(manifest["id"], extra.PACKAGE_ID)
        self.assertEqual(manifest["version"], extra.PACKAGE_VERSION)
        self.assertEqual(
            [feature["id"] for feature in manifest["feature"]],
            ["mugshot_hunter", "mugshot_dr_light"],
        )
        self.assertEqual(len(manifest["option"]), 2)
        self.assertNotIn("patch", manifest)

    def test_reserved_extent_constants(self) -> None:
        records = extra.allocated_records()
        self.assertEqual(records[243], (extra.RESERVED_BASE_SECTOR, 8192))
        self.assertEqual(records[244], (extra.RESERVED_BASE_SECTOR + 4, 512))
        self.assertEqual(records[245], (extra.RESERVED_BASE_SECTOR + 5, 8192))
        self.assertEqual(records[246], (extra.RESERVED_BASE_SECTOR + 9, 512))
        self.assertEqual(extra.RESERVED_LOGICAL_SIZE, 0x03DF2000)

    @unittest.skipUnless(
        Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin").is_file(),
        "local stock image and user-supplied Tweaks source are required",
    )
    def test_report_and_archive_are_deterministic(self) -> None:
        overlays, report = extra.build_package_data(
            Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin"),
            Path("build-mod-platform/test-mod-variants/base.bin"),
        )
        self.assertEqual(
            report["source_controls"],
            ["MugshotCustom01", "MugshotCustom02"],
        )
        self.assertGreater(len(overlays), 0)
        with tempfile.TemporaryDirectory(prefix="mmx6-extra-mugshots-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            extra.write_package(first, overlays, report)
            extra.write_package(second, overlays, report)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIn("manifest.toml", archive.namelist())
                self.assertIn("conversion-report.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
