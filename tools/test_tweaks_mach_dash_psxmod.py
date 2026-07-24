#!/usr/bin/env python3
"""Unit tests for the trusted Blade Mach Dash package generator."""

from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_mach_dash_psxmod as mach


class MachDashPackageTests(unittest.TestCase):
    def test_exact_control_inventory_and_quarantine(self) -> None:
        self.assertEqual(len(mach.SOURCE_CONTROLS), 14)
        self.assertEqual(len(set(mach.SOURCE_CONTROLS)), 14)
        self.assertNotIn("MachDashDuration02", mach.SOURCE_CONTROLS)
        self.assertEqual(
            mach.QUARANTINED,
            ("MachDashDuration02", "MachDashSpeed02", "MachDashSpeed03"),
        )

    def test_manifest_is_one_coherent_behavior_row(self) -> None:
        parsed = tomllib.loads(mach.manifest_text())
        self.assertEqual(parsed["resolver"], "builtin:mmx6-mach-dash")
        self.assertEqual(len(parsed["feature"]), 1)
        self.assertFalse(parsed["feature"][0]["default_enabled"])
        self.assertEqual(
            [option["id"] for option in parsed["option"]],
            ["input", "wait", "cancel", "duration", "speed", "immunity"],
        )
        self.assertEqual(len(parsed["option"][0]["choice"]), 3)
        self.assertEqual(len(parsed["option"][1]["choice"]), 4)
        self.assertEqual(len(parsed["option"][2]["choice"]), 4)
        self.assertNotIn("patch", parsed)

    def test_archive_is_deterministic_and_ledger_is_string_only(self) -> None:
        report = {
            "package_id": mach.PACKAGE_ID,
            "source_controls": sorted(mach.SOURCE_CONTROLS),
        }
        first = mach.archive_bytes(report)
        self.assertEqual(first, mach.archive_bytes(report))
        with mach.zipfile.ZipFile(mach.io.BytesIO(first)) as archive:
            stored = json.loads(archive.read("conversion-report.json"))
            self.assertTrue(
                all(isinstance(item, str) for item in stored["source_controls"])
            )


if __name__ == "__main__":
    unittest.main()
