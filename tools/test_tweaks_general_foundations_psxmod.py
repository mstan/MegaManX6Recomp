#!/usr/bin/env python3
"""Tests for the MMX6 General shared-foundation package."""

from __future__ import annotations

import os
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

import tweaks_general_foundations_psxmod as foundations


class GeneralFoundationTests(unittest.TestCase):
    def test_manifest_is_resolver_backed(self) -> None:
        manifest = tomllib.loads(foundations.manifest_text())
        self.assertEqual(manifest["id"], foundations.PACKAGE_ID)
        self.assertEqual(manifest["version"], foundations.PACKAGE_VERSION)
        self.assertEqual(
            manifest["resolver"],
            f"builtin:{foundations.RESOLVER_ID}",
        )
        self.assertEqual(
            [feature["id"] for feature in manifest["feature"]],
            [
                "ultimate_armor_rank_unlock",
                "black_zero_rank_unlock",
                "normalize_unarmored_x_defense",
                "normalize_zero_defense",
            ],
        )
        self.assertNotIn("patch", manifest)
        self.assertNotIn("overlay", manifest)

    @unittest.skipUnless(
        Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin").is_file(),
        "local stock image and user-supplied Tweaks source are required",
    )
    def test_source_closures_and_deterministic_archive(self) -> None:
        stock = Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin")
        report = foundations.report(stock)
        self.assertEqual(
            report["source_controls"],
            [
                "MissRepUnlocksRank01",
                "MissRepUnlocksRank02",
                "LowerDef01",
                "LowerDef02",
            ],
        )
        self.assertEqual(
            report["validation"]["cases"]["both_rank_unlocks"][
                "source_closure"
            ],
            [
                "MissRepUnlocksBase01",
                "MissRepUnlocksRank01",
                "MissRepUnlocksRank02",
            ],
        )
        self.assertEqual(
            report["validation"]["cases"]["normalize_x_and_zero_defense"][
                "source_closure"
            ],
            ["LowerDef_All_A"],
        )
        with tempfile.TemporaryDirectory(prefix="mmx6-foundations-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            foundations.write_package(first, report)
            foundations.write_package(second, report)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "README.txt",
                        "conversion-report.json",
                        "manifest.toml",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
