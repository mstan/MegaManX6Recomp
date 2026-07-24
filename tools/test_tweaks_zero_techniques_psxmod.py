#!/usr/bin/env python3
"""Tests for the resolver-backed MMX6 Zero Techniques package."""

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

import tweaks_zero_techniques_psxmod as zero


class ZeroTechniquesPackageTests(unittest.TestCase):
    def test_manifest_is_one_resolver_feature(self) -> None:
        manifest = tomllib.loads(zero.manifest_text())
        self.assertEqual(manifest["id"], zero.PACKAGE_ID)
        self.assertEqual(manifest["version"], zero.PACKAGE_VERSION)
        self.assertEqual(manifest["resolver"], f"builtin:{zero.RESOLVER_ID}")
        self.assertEqual([feature["id"] for feature in manifest["feature"]],
                         ["zero_techniques"])
        self.assertEqual(len(manifest["option"]), 7)
        self.assertNotIn("patch", manifest)
        self.assertNotIn("overlay", manifest)

    def test_source_controls_match_zero_audit_boundary(self) -> None:
        self.assertEqual(len(zero.SOURCE_CONTROLS), 17)
        self.assertIn("ZeroEnsuizanInput04", zero.SOURCE_CONTROLS)
        self.assertIn("ZeroYammarInput01", zero.SOURCE_CONTROLS)

    @unittest.skipUnless(
        Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin").is_file(),
        "local stock image and user-supplied Tweaks source are required",
    )
    def test_report_and_archive_are_deterministic(self) -> None:
        report = zero.report(
            Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin"),
            Path(
                "mmx6-tweaks/_patcher/src_extracted/"
                "Mega Man X6 Tweaks Patcher (v2.6.1)/_src"
            ),
            Path(
                "mmx6-tweaks/_patcher/run_extracted/profiles/"
                "default.x6tweaksprofile"
            ),
        )
        self.assertEqual(report["source_controls"], sorted(zero.SOURCE_CONTROLS))
        self.assertTrue(
            report["validation"]["cross_forcing_is_fail_closed"])
        with tempfile.TemporaryDirectory(prefix="mmx6-zero-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            zero.write_package(first, report)
            zero.write_package(second, report)
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
