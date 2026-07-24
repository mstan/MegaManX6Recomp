#!/usr/bin/env python3
"""Tests for the fixed-write MMX6 standalone-player package."""

from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_player_standalone_psxmod as player


class PlayerStandaloneTests(unittest.TestCase):
    def test_scope_is_narrow_and_ledger_is_exact(self) -> None:
        self.assertEqual(len(player.PLAYER_CONTROLS), 49)
        self.assertEqual(len(set(player.PLAYER_CONTROLS)), 49)
        self.assertEqual(
            [feature.source_control for feature in player.FEATURES],
            [
                "DashGlobal01",
                "GuardShellFix01",
                "ZeroAutoselect01",
            ],
        )
        self.assertNotIn(
            "HoverUnlock02",
            {feature.source_control for feature in player.FEATURES},
        )
        self.assertIn(
            "GUI forces HoverUnlock01",
            player._deferred_reason("HoverUnlock02"),
        )
        self.assertIn(
            "ArmorByPart_Common",
            player._deferred_reason("ShadowSlide01"),
        )
        for control in (
            "MachDashDuration02",
            "MachDashSpeed02",
            "MachDashSpeed03",
        ):
            self.assertIn("quarantined", player._deferred_reason(control))

    def test_manifest_is_default_disabled_and_resolver_backed(self) -> None:
        patches = (
            player.FixedPatch(
                "unlock_x_air_dash",
                "DashGlobal01",
                "main_exe",
                0x80001000,
                b"\x01\x02",
                b"\x03\x04",
                0x1234,
                "SLUS_013.95",
                0x1000,
            ),
        )
        parsed = tomllib.loads(player.manifest_text(patches))
        self.assertEqual(parsed["format_version"], 3)
        self.assertEqual(parsed["resolver"], f"builtin:{player.RESOLVER_ID}")
        self.assertEqual(len(parsed["feature"]), 3)
        self.assertTrue(
            all(not feature["default_enabled"] for feature in parsed["feature"])
        )
        self.assertNotIn("patch", parsed)

    def test_disjointness_fails_closed(self) -> None:
        first = player.FixedPatch(
            "a", "A", "main_exe", 10, b"\0\0", b"\1\1", 1, "exe", 1
        )
        second = player.FixedPatch(
            "b", "B", "main_exe", 11, b"\0", b"\2", 2, "exe", 2
        )
        with self.assertRaisesRegex(ValueError, "ownership overlap"):
            player._validate_disjoint([first, second])

    def test_archive_and_string_source_ledger_are_deterministic(self) -> None:
        patches = (
            player.FixedPatch(
                "unlock_x_air_dash",
                "DashGlobal01",
                "main_exe",
                0x80001000,
                b"\x01",
                b"\x02",
                0x1234,
                "SLUS_013.95",
                0x1000,
            ),
        )
        converted = {feature.source_control for feature in player.FEATURES}
        report = {
            "package_id": player.PACKAGE_ID,
            "source_controls": sorted(converted),
        }
        first = player.archive_bytes(player.manifest_text(patches), report)
        second = player.archive_bytes(player.manifest_text(patches), report)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.psxmod"
            path.write_bytes(first)
            with player.zipfile.ZipFile(path) as archive:
                archived = json.loads(
                    archive.read("conversion-report.json")
                )
                self.assertTrue(
                    all(
                        isinstance(control, str)
                        for control in archived["source_controls"]
                    )
                )


if __name__ == "__main__":
    unittest.main()
