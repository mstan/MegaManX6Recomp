#!/usr/bin/env python3
"""Focused tests for the reviewed MMX6 Tweaks asset package converter."""

from __future__ import annotations

import os
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_assets_psxmod as assets
import tweaks_native_psxmod as native


class CatalogTests(unittest.TestCase):
    def test_catalog_is_fourteen_independent_rows(self) -> None:
        self.assertEqual(len(assets.FEATURES), 14)
        self.assertEqual(
            len([item for item in assets.FEATURES if item.kind == "mugshot"]),
            12,
        )
        self.assertEqual(
            len([item for item in assets.FEATURES if item.kind == "palette"]),
            2,
        )
        self.assertEqual(
            len({item.feature_id for item in assets.FEATURES}),
            len(assets.FEATURES),
        )
        self.assertNotIn(
            "MugshotCustom01",
            {item.source_option for item in assets.FEATURES},
        )
        self.assertNotIn(
            "MugshotCustom02",
            {item.source_option for item in assets.FEATURES},
        )
        self.assertEqual(
            sorted(item.source_option for item in assets.FEATURES),
            sorted(
                {
                    "MugshotCustom03",
                    "MugshotCustom04",
                    "MugshotCustom05",
                    "MugshotCustom06",
                    "MugshotCustom07",
                    "MugshotCustom08",
                    "MugshotCustom09",
                    "MugshotCustom10",
                    "MugshotCustom11",
                    "MugshotCustom12",
                    "MugshotCustom13",
                    "MugshotCustom14",
                    "SpritePalette01",
                    "SpritePalette02",
                }
            ),
        )

    def test_only_real_variant_domains_get_options(self) -> None:
        configurable = {
            item.feature_id
            for item in assets.FEATURES
            if len(item.variants) > 1
        }
        self.assertEqual(
            configurable,
            {
                "mugshot_ultimate_x",
                "mugshot_black_zero",
                "mugshot_nightmare_zero",
                "palette_ultimate_x",
            },
        )
        self.assertEqual(
            sum(len(item.variants) for item in assets.FEATURES), 23
        )

    def test_architecture_deferred_domains_remain_explicit(self) -> None:
        self.assertEqual(
            set(assets.DEFERRED),
            {
                "MugshotCustom01",
                "MugshotCustom02",
                "TitleLoading01/02/03",
                "StageMod0404",
                "AutoCrouching01/02/03 + RecycleCeiling01",
            },
        )


@unittest.skipUnless(
    os.environ.get("MMX6_ASSET_TEST_STOCK")
    and os.environ.get("MMX6_ASSET_TEST_B01"),
    "set MMX6_ASSET_TEST_STOCK and MMX6_ASSET_TEST_B01 for local integration",
)
class LocalIntegrationTests(unittest.TestCase):
    def test_deterministic_reviewed_package(self) -> None:
        stock_path = Path(os.environ["MMX6_ASSET_TEST_STOCK"])
        b01_path = Path(os.environ["MMX6_ASSET_TEST_B01"])
        with native.RawMode2Image(stock_path) as stock_image, (
            native.RawMode2Image(b01_path)
        ) as b01_image:
            overlays, report = assets.build_assets(
                stock_image,
                b01_image,
                stock_path,
                b01_path,
            )

        self.assertEqual(len(overlays), 1440)
        self.assertEqual(report["operations"]["overlay_bytes"], 379813)
        self.assertEqual(
            report["source_controls"],
            sorted(item.source_option for item in assets.FEATURES),
        )
        self.assertEqual(
            report["operations"]["mugshot_assembly_source_bytes_replayed"], 0
        )
        self.assertEqual(
            report["validation"]["title_screen_overlap_operations"], 0
        )
        self.assertEqual(
            report["validation"]["retranslation_overlap_operations"], 0
        )
        for proof in report["validation"]["representative_combinations"]:
            self.assertTrue(proof["mugshot_reference_union_exact"])
            self.assertEqual(proof["hidden_source_closure_count"], 0)
            self.assertEqual(proof["incompatible_overlap_count"], 0)

        with tempfile.TemporaryDirectory(prefix="mmx6-assets-test-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            assets.write_package(
                first, overlays, report, assets.PACKAGE_VERSION
            )
            assets.write_package(
                second, overlays, report, assets.PACKAGE_VERSION
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            inspection = assets.inspect_package(first)
            self.assertEqual(inspection["feature_count"], 14)
            self.assertEqual(inspection["option_count"], 4)
            self.assertEqual(inspection["overlay_count"], 1440)

            with zipfile.ZipFile(first) as archive:
                manifest = tomllib.loads(
                    archive.read("manifest.toml").decode("utf-8")
                )
            self.assertEqual(manifest["id"], assets.PACKAGE_ID)
            self.assertEqual(
                manifest["target"][0]["disc_sha256"], native.STOCK_SHA256
            )
            self.assertTrue(
                all(
                    not feature["default_enabled"]
                    for feature in manifest["feature"]
                )
            )
            self.assertNotIn("patch", manifest)


if __name__ == "__main__":
    unittest.main()
