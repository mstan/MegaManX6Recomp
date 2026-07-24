#!/usr/bin/env python3
"""Tests for the resolver-backed MMX6 in-game Settings menu package."""

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

import tweaks_ingame_options_psxmod as ingame


class IngameOptionsPackageTests(unittest.TestCase):
    def test_manifest_contract(self) -> None:
        manifest = tomllib.loads(ingame.manifest_text())
        self.assertEqual(manifest["id"], ingame.PACKAGE_ID)
        self.assertEqual(manifest["version"], ingame.PACKAGE_VERSION)
        self.assertEqual(manifest["resolver"], f"builtin:{ingame.RESOLVER_ID}")
        self.assertEqual(
            manifest["dependency"],
            [{"id": "mmx6.tweaks.native", "version": ">=1.10.4"}],
        )
        self.assertEqual([feature["id"] for feature in manifest["feature"]],
                         ["settings_menu_options"])
        self.assertNotIn("option", manifest)
        self.assertNotIn("patch", manifest)
        self.assertNotIn("overlay", manifest)

    def test_source_control_boundary(self) -> None:
        self.assertEqual(ingame.SOURCE_CONTROLS, ("IngameOptions01",))

    @unittest.skipUnless(
        Path("mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin").is_file(),
        "local stock image and user-supplied Tweaks source are required",
    )
    def test_report_and_archive_are_deterministic(self) -> None:
        report = ingame.report(
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
        self.assertEqual(report["source_controls"], ["IngameOptions01"])
        self.assertEqual(
            report["validation"]["source_closure"],
            ["IngameOptions01", "ScriptPatch02"],
        )
        self.assertEqual(report["validation"]["source_write_count"], 23)
        with tempfile.TemporaryDirectory(prefix="mmx6-ingame-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            ingame.write_package(first, report)
            ingame.write_package(second, report)
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
