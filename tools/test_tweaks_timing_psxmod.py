#!/usr/bin/env python3
"""Deterministic tests for the standalone MMX6 timing/status converter."""

from __future__ import annotations

import hashlib
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

import tweaks_timing_psxmod as timing


class TimingPackageTests(unittest.TestCase):
    def test_reviewed_source_control_surface_is_narrow(self) -> None:
        by_feature = {
            feature.feature_id: feature for feature in timing.FEATURES
        }
        self.assertEqual(
            list(by_feature),
            [
                "x_saber_timing",
                "shadow_saber_timing",
                "zero_saber_cooldown_timing",
                "maximum_lives",
                "nightmare_dark_opacity",
            ],
        )
        self.assertEqual(
            [len(feature.controls) for feature in timing.ANIMATION_FEATURES],
            [7, 7, 6],
        )
        source_ids = [
            control.source_id
            for feature in timing.FEATURES
            for control in feature.controls
        ]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertNotIn("Anim0301", source_ids)
        self.assertFalse(any(source.startswith("Anim04") for source in source_ids))
        for feature in timing.ANIMATION_FEATURES:
            for control in feature.controls:
                self.assertEqual((control.minimum, control.maximum), (1, 99))
                self.assertGreaterEqual(control.default, 1)
        report_controls = timing.source_controls_report()
        self.assertEqual(len(report_controls), 22)
        self.assertTrue(
            all(
                item["conversion_status"]
                == "exact-bounded-source-control"
                for item in report_controls
            )
        )

    def test_source_templates_cover_conditional_and_sector_split_writes(
        self,
    ) -> None:
        self.assertEqual(
            timing._expected_lives_writes(9),
            [
                (0x1D968098, b"\x09\x00"),
                (0x1D968C90, b"\x09\x00"),
                (0x1D96808C, b"\x0A\x00"),
                (0x1D968C84, b"\x0A\x00"),
            ],
        )
        self.assertEqual(
            timing._expected_lives_writes(10)[0],
            (0x1D92B588, bytes(4)),
        )
        nightmare = timing._expected_nightmare_writes(28)
        self.assertEqual(len(nightmare), 5)
        self.assertEqual(nightmare[2][0], 0x1DAFA320)
        self.assertEqual(nightmare[3][0], 0x1DAFA458)
        self.assertEqual(nightmare[2][1] + nightmare[3][1],
                         timing._nightmare_template(28))
        self.assertEqual(nightmare[0][1][0], 28)
        self.assertEqual(nightmare[0][1][8], 27)

    def _fixture_operations(self) -> tuple[timing.SparsePatch, ...]:
        return (
            timing.SparsePatch(
                "x_saber_timing",
                "Anim0101-1",
                "disc_user",
                0x1000,
                bytes.fromhex("0300012F"),
                (timing.SparseField(0, "timing_1"),),
                (0x1D9BFAB4,),
                "ROCK_X6.BIN member 24",
                0xB91C,
            ),
            timing.SparsePatch(
                "maximum_lives",
                "LivesDisplay01-above-nine",
                "main_exe",
                0x80019780,
                bytes.fromhex("CC68000C"),
                (timing.SparseField(0, replacement=bytes(4)),),
                (0x1D92B588,),
                timing.native.SLUS_NAME,
                0x9F80,
                timing.IntegerCondition("maximum", "gt", 9),
            ),
            timing.SparsePatch(
                "nightmare_dark_opacity",
                "NightmareMod01-record-1",
                "disc_user",
                0x2000,
                timing._nightmare_template(64),
                (
                    timing.SparseField(0, "opacity"),
                    timing.SparseField(8, "opacity", addend=-1),
                ),
                (0x1D9E1B74,),
                "ROCK_X6.BIN member 73",
                0x293CC,
            ),
        )

    def test_manifest_is_format_4_default_disabled_and_sparse(self) -> None:
        manifest = timing.build_manifest(
            self._fixture_operations(), timing.PACKAGE_VERSION
        )
        parsed = tomllib.loads(manifest)
        self.assertEqual(parsed["format_version"], 4)
        self.assertEqual(parsed["id"], timing.PACKAGE_ID)
        self.assertEqual(len(parsed["feature"]), 5)
        self.assertTrue(
            all(not feature["default_enabled"] for feature in parsed["feature"])
        )
        self.assertFalse(
            any(option["id"] == "enabled" for option in parsed["option"])
        )
        by_label = {
            patch["feature"] + ":" + str(patch.get("address", patch.get("offset"))):
            patch
            for patch in parsed["patch"]
        }
        animation = by_label["x_saber_timing:4096"]
        self.assertNotIn("replace", animation)
        self.assertNotIn("replace_from", animation)
        self.assertEqual(
            animation["fields"],
            [{"offset": 0, "option": "timing_1", "encoding": "u8"}],
        )
        display = by_label[f"maximum_lives:{0x80019780}"]
        self.assertEqual(
            display["fields"], [{"offset": 0, "replace": "00000000"}]
        )
        self.assertEqual(
            display["when_integer"],
            {"option": "maximum", "op": "gt", "value": 9},
        )
        opacity = by_label["nightmare_dark_opacity:8192"]
        self.assertEqual(opacity["fields"][1]["addend"], -1)

    def test_archive_bytes_are_deterministic(self) -> None:
        operations = self._fixture_operations()
        evidence = {
            feature.feature_id: {"test": True}
            for feature in timing.FEATURES
        }
        report = timing.build_report(
            timing.native.STOCK_SHA256,
            "b" * 64,
            "c" * 64,
            evidence,
            operations,
            timing.PACKAGE_VERSION,
            "d" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.psxmod"
            second = Path(directory) / "second.psxmod"
            timing.write_package(
                first, operations, report, timing.PACKAGE_VERSION
            )
            timing.write_package(
                second, operations, report, timing.PACKAGE_VERSION
            )
            first_bytes = first.read_bytes()
            second_bytes = second.read_bytes()
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(
                hashlib.sha256(first_bytes).hexdigest(),
                hashlib.sha256(second_bytes).hexdigest(),
            )
            with timing.zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "manifest.toml",
                        "conversion-report.json",
                        "README.txt",
                    ],
                )
                archived_report = json.loads(
                    archive.read("conversion-report.json")
                )
                self.assertEqual(
                    archived_report["package_id"], timing.PACKAGE_ID
                )
                self.assertIn("source_controls", archived_report)
                self.assertEqual(
                    archived_report["deferred"]["Anim04"]["status"],
                    "deferred",
                )


if __name__ == "__main__":
    unittest.main()
