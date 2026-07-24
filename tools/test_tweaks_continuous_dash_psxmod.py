#!/usr/bin/env python3
"""Deterministic unit tests for continuous-dash package construction."""

from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_continuous_dash_psxmod as dash


class ContinuousDashTests(unittest.TestCase):
    def test_numword_encoding_and_composition(self) -> None:
        self.assertEqual(
            dash.halves(0x00042000),
            (bytes.fromhex("0400"), bytes.fromhex("0020")),
        )
        normal = dash.compose(0x00042000, None)
        self.assertEqual(len(normal), 5)
        self.assertEqual(normal[0][0], dash.FOUNDATION_RAW)
        self.assertEqual(normal[1:], [
            (dash.NORMAL_RAWS[0], bytes.fromhex("0400")),
            (dash.NORMAL_RAWS[0] + 4, bytes.fromhex("0020")),
            (dash.NORMAL_RAWS[1], bytes.fromhex("0400")),
            (dash.NORMAL_RAWS[1] + 4, bytes.fromhex("0020")),
        ])
        both = dash.compose(333333, 123456)
        self.assertEqual(both, dash.compose(333333, 123456))
        self.assertNotEqual(both[0][1], dash.FOUNDATION)

    def test_manifest_has_two_rows_and_bounded_integer_options(self) -> None:
        parsed = tomllib.loads(dash.manifest_text())
        self.assertEqual(parsed["resolver"], "builtin:mmx6-continuous-dash")
        self.assertEqual(len(parsed["feature"]), 2)
        self.assertTrue(
            all(not feature["default_enabled"] for feature in parsed["feature"])
        )
        self.assertEqual(
            [(item["min"], item["max"]) for item in parsed["option"]],
            [(200000, 600000), (60000, 160000)],
        )
        self.assertNotIn("patch", parsed)
        self.assertNotIn("overlay", parsed)

    def test_archive_source_controls_are_strings(self) -> None:
        report = {
            "package_id": dash.PACKAGE_ID,
            "source_controls": ["DashSpeedCont01", "DashSpeedCont02"],
        }
        first = dash.archive_bytes(report)
        self.assertEqual(first, dash.archive_bytes(report))
        with dash.zipfile.ZipFile(dash.io.BytesIO(first)) as archive:
            stored = json.loads(archive.read("conversion-report.json"))
            self.assertEqual(
                stored["source_controls"],
                ["DashSpeedCont01", "DashSpeedCont02"],
            )


if __name__ == "__main__":
    unittest.main()
