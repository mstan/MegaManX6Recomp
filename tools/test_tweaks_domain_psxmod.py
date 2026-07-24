#!/usr/bin/env python3
"""Tests for the exact General, Stage-mode, and Boss package converter."""

from __future__ import annotations

import hashlib
import sys
import tomllib
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_domain_psxmod as domain


class DomainPackageTests(unittest.TestCase):
    def test_real_control_inventory_is_explicit(self) -> None:
        self.assertEqual(
            [item.package_id for item in domain.DOMAINS],
            [
                "mmx6.tweaks.general",
                "mmx6.tweaks.stage-modes",
                "mmx6.tweaks.boss-attacks",
                "mmx6.tweaks.damage-rules",
            ],
        )
        self.assertEqual(
            [len(item.features) for item in domain.DOMAINS],
            [13, 2, 1, 2],
        )
        represented = {
            control
            for item in domain.DOMAINS
            for feature in item.features
            for control in feature.source_controls
        }
        self.assertEqual(len(represented), 21)
        self.assertTrue(
            {
                "SharedStats01",
                "SharedStats02",
                "BossMod0105",
                "AutoCrouching01",
                "AutoCrouching02",
                "AutoCrouching03",
                "RecycleCeiling01",
                "StageMod0404",
                "DmgTableGate01",
                "DmgTableGateDmg01",
            }.issubset(represented)
        )
        fake_controls = {
            "DmgTableCurrent1",
            "DmgTableCurrent2",
            "DmgTableCurrent3",
            "DmgTableCurrent4",
            "DmgTableCurrent5",
            "DmgTableInput_S",
            "DmgTableInput_V",
            "ErrorRecalc",
            "PatchList_BaseHacks",
            "HelpButton",
            "BossHealth",
        }
        self.assertTrue(represented.isdisjoint(fake_controls))

    def test_intrinsic_stage_alternatives_are_one_row(self) -> None:
        feature = domain.STAGES.features[0]
        self.assertEqual(feature.feature_id, "falling_ceiling_behavior")
        self.assertEqual(feature.option_id, "mode")
        self.assertEqual(
            [variant.value for variant in feature.variants],
            ["automatic", "manual", "disable_ceiling"],
        )
        self.assertEqual(
            feature.variants[1].closure,
            ("AutoCrouching02", "AutoCrouching03"),
        )
        teleport = domain.STAGES.features[1]
        self.assertEqual(
            teleport.feature_id,
            "move_recycle_lab_hidden_teleport",
        )
        self.assertEqual(teleport.source_controls, ("StageMod0404",))
        self.assertEqual(teleport.variants[0].closure, ("StageMod0404",))

    def test_deferred_and_excluded_ledgers_are_distinct(self) -> None:
        excluded = {
            source: reason
            for item in domain.DOMAINS
            for source, reason in item.excluded
        }
        deferred = {
            source: reason
            for item in domain.DOMAINS
            for source, reason in item.deferred
        }
        self.assertEqual(
            set(deferred),
            {
                "ArmorByPart01",
                "ArmorByPart02",
                "ArmorByPart03",
                "ArmorByPart04",
                "LivesSwitch01",
                "IngameOptions01",
            },
        )
        self.assertTrue(
            {
                "DmgTableInput_S",
                "DmgTableInput_V",
                "ErrorRecalc",
                "PatchList_BaseHacks",
                "HelpButton",
            }.issubset(excluded)
        )
        self.assertTrue(set(deferred).isdisjoint(excluded))
        self.assertTrue(all(reason.strip() for reason in excluded.values()))
        self.assertTrue(all(reason.strip() for reason in deferred.values()))

    @unittest.skipUnless(
        domain.DEFAULT_STOCK.is_file()
        and domain.DEFAULT_SOURCE.is_dir()
        and domain.DEFAULT_PROFILE.is_file(),
        "local stock image and user-supplied Tweaks source are required",
    )
    def test_exact_source_closures_stock_guards_and_archives(self) -> None:
        package_hashes = []
        for item in domain.DOMAINS:
            patches, report = domain.build_domain(
                item,
                domain.DEFAULT_STOCK,
                domain.DEFAULT_SOURCE,
                domain.DEFAULT_PROFILE,
            )
            self.assertTrue(patches)
            self.assertFalse(
                report["provenance"]["patched_disc_oracle_used"]
            )
            self.assertTrue(
                report["validation"]["source_closures_exact"]
            )
            self.assertTrue(
                report["validation"]["internal_overlaps_composed"]
            )
            self.assertEqual(
                report["excluded_source_controls"],
                [
                    {"source_control": source, "reason": reason}
                    for source, reason in item.excluded
                ],
            )
            self.assertEqual(
                report["deferred_source_controls"],
                [
                    {"source_control": source, "reason": reason}
                    for source, reason in item.deferred
                ],
            )
            for patch in patches:
                self.assertIn(patch.target, {"main_exe", "disc_user"})
                self.assertTrue(patch.expected)
                self.assertEqual(
                    len(patch.expected), len(patch.replacement)
                )
            manifest = domain.manifest_text(item, patches)
            parsed = tomllib.loads(manifest)
            self.assertEqual(parsed["id"], item.package_id)
            if item is domain.DAMAGE_RULES:
                self.assertEqual(parsed["version"], "1.1.0")
                self.assertEqual(
                    parsed["resolver"], "builtin:mmx6-damage-rules"
                )
                self.assertNotIn("patch", parsed)
                self.assertEqual(parsed["option"][0]["type"], "integer")
                self.assertEqual(parsed["option"][0]["min"], 1)
                self.assertEqual(parsed["option"][0]["max"], 127)
                self.assertEqual(parsed["option"][0]["default"], 4)
            else:
                self.assertEqual(parsed["resolver"], "declarative")
            self.assertEqual(
                [feature["id"] for feature in parsed["feature"]],
                [feature.feature_id for feature in item.features],
            )
            self.assertTrue(
                all(
                    "source_controls" not in feature
                    for feature in parsed["feature"]
                )
            )
            first = domain.archive_bytes(manifest, report)
            second = domain.archive_bytes(manifest, report)
            self.assertEqual(first, second)
            package_hashes.append(hashlib.sha256(first).hexdigest())
            with zipfile.ZipFile(
                __import__("io").BytesIO(first)
            ) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "README.txt",
                        "conversion-report.json",
                        "manifest.toml",
                    ],
                )
        self.assertEqual(len(package_hashes), len(set(package_hashes)))


if __name__ == "__main__":
    unittest.main()
