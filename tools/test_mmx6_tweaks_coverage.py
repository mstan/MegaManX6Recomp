#!/usr/bin/env python3
"""Tests for installed-package MMX6 Tweaks coverage discovery."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mmx6_tweaks_coverage as coverage


class InstalledReportDiscoveryTests(unittest.TestCase):
    def test_selects_latest_numeric_version_per_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for package, versions in {
                "example.one": ("1.2.9", "1.10.0"),
                "example.two": ("2.0.0",),
            }.items():
                for version in versions:
                    report = (
                        root
                        / "packages"
                        / package
                        / version
                        / "conversion-report.json"
                    )
                    report.parent.mkdir(parents=True)
                    report.write_text("{}\n", encoding="utf-8")

            reports = coverage.discover_latest_reports(root)
            self.assertEqual(
                [
                    path.relative_to(root).as_posix()
                    for path in reports
                ],
                [
                    "packages/example.one/1.10.0/conversion-report.json",
                    "packages/example.two/2.0.0/conversion-report.json",
                ],
            )

    def test_rejects_non_numeric_version_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = (
                root
                / "packages"
                / "example"
                / "latest"
                / "conversion-report.json"
            )
            report.parent.mkdir(parents=True)
            report.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "numeric X.Y.Z"):
                coverage.discover_latest_reports(root)


if __name__ == "__main__":
    unittest.main()
