#!/usr/bin/env python3
"""Tests for the MMX6 New Game composer and package."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__.replace("\\", "/")).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_new_game_psxmod as new_game


class CatalogTests(unittest.TestCase):
    def test_feature_rows_are_independent(self) -> None:
        self.assertEqual(len(new_game.FEATURES), 64)
        self.assertEqual(
            len({item.feature_id for item in new_game.FEATURES}), 64
        )
        self.assertEqual(
            len({item.source_control for item in new_game.FEATURES}), 64
        )
        self.assertEqual(
            len([item for item in new_game.FEATURES if item.kind == "integer"]),
            4,
        )
        self.assertEqual(
            len([item for item in new_game.FEATURES if item.kind == "bit"]), 57
        )
        self.assertEqual(
            len([item for item in new_game.FEATURES if item.kind == "rank"]), 2
        )
        self.assertEqual(
            len([item for item in new_game.FEATURES if item.kind == "table"]), 1
        )

    def test_bit_domains_match_upstream_masks(self) -> None:
        hearts = [
            item.bit
            for item in new_game.FEATURES
            if item.field_offset == 0x88
        ]
        subtanks = [
            item.bit
            for item in new_game.FEATURES
            if item.field_offset == 0x50
        ]
        self.assertEqual(hearts, [1, 2, 4, 8, 16, 32, 64, 128])
        self.assertEqual(subtanks, [16, 32, 64, 128])

    def test_burndown_scope_is_explicit(self) -> None:
        added = {item.source_control for item in new_game.FEATURES[18:]}
        expected = {
            *(f"CharAdd{index:02d}" for index in range(2, 7)),
            *(f"PartsLifeUp{index:02d}" for index in range(1, 9)),
            *(f"PartsEnergyUp{index:02d}" for index in range(1, 9)),
            "RescRepFoundNoItem01",
            "PartsSet0101", "PartsSet0102", "PartsSet0103",
            "PartsSet0104", "PartsSet0203", "PartsSet0204",
            *(f"PartsSet0{group}0{index}"
              for group in range(3, 7) for index in range(1, 5)),
            "PartsSet0701", "PartsSet0702",
        }
        self.assertEqual(added, expected)
        self.assertEqual(len(added), 46)


@unittest.skipUnless(
    os.environ.get("MMX6_NEW_GAME_TEST_STOCK"),
    "set MMX6_NEW_GAME_TEST_STOCK for local integration",
)
class PackageIntegrationTests(unittest.TestCase):
    def test_source_parity_and_deterministic_package(self) -> None:
        report = new_game.build_report(
            Path(os.environ["MMX6_NEW_GAME_TEST_STOCK"])
        )
        self.assertEqual(report["package"]["catalog_control_count"], 74)
        self.assertEqual(report["package"]["source_control_count"], 64)
        self.assertEqual(report["package"]["deferred_control_count"], 10)
        self.assertEqual(len(report["source_controls"]), 64)
        self.assertEqual(len(report["source_control_ledger"]), 74)
        deferred = {
            item["source_control"]
            for item in report["source_control_ledger"]
            if item["status"] == "deferred"
        }
        self.assertEqual(deferred, {
            "CharAdd01", "CharStart01", "DebugCheckpointStart",
            "DebugStageStart", "PartsRandom01", "PartsRandom02",
            "PartsRandomTitle01", "RescRepFoundMark01",
            "RescRepFoundMarkOnly01", "ZeroDebug",
        })
        table = report["composed_resources"]["found_reploid_table"]
        middle = report["foundation"][1]
        self.assertEqual(
            table["source_raw_offset"] + table["size"],
            middle["source_raw_offset"],
        )
        self.assertTrue(report["validation"]["stock_guards_verified"])
        self.assertTrue(report["validation"]["isolated_source_parity"])
        for proof in report["validation"]["representative_combinations"]:
            self.assertTrue(proof["upstream_parity"])
            self.assertTrue(proof["order_independent"])

        resolver_text = (
            TOOLS.parent / "src" / "mods" / "mmx6_new_game_resolver.cpp"
        ).read_text(encoding="utf-8")

        def cpp_hex(name: str) -> bytes:
            block = re.search(
                rf"{name}\s*=\s*((?:\s*\"[0-9A-F]+\")+);",
                resolver_text,
            )
            self.assertIsNotNone(block, name)
            return bytes.fromhex("".join(re.findall(r'"([0-9A-F]+)"', block.group(1))))

        foundation = new_game.foundation_source()
        self.assertEqual(cpp_hex("kHookReplace"), foundation[0])
        self.assertEqual(cpp_hex("kTemplateReplace"), foundation[1])
        self.assertEqual(cpp_hex("kTailReplace"), foundation[2])
        self.assertEqual(
            cpp_hex("kHookExpected"),
            bytes.fromhex(report["foundation"][0]["expected"]),
        )
        self.assertEqual(
            cpp_hex("kTemplateExpected"),
            bytes.fromhex(report["foundation"][1]["expected"]),
        )
        self.assertEqual(
            cpp_hex("kTailExpected"),
            bytes.fromhex(report["foundation"][2]["expected"]),
        )
        self.assertEqual(
            cpp_hex("kFoundTableExpected"),
            bytes.fromhex(
                report["composed_resources"]["found_reploid_table"]["expected"]
            ),
        )

        with tempfile.TemporaryDirectory(prefix="mmx6-new-game-test-") as temp:
            first = Path(temp) / "first.psxmod"
            second = Path(temp) / "second.psxmod"
            new_game.write_package(
                first, report, new_game.PACKAGE_VERSION
            )
            new_game.write_package(
                second, report, new_game.PACKAGE_VERSION
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                manifest = tomllib.loads(
                    archive.read("manifest.toml").decode()
                )
            self.assertEqual(manifest["id"], new_game.PACKAGE_ID)
            self.assertEqual(
                manifest["resolver"],
                f"builtin:{new_game.RESOLVER_ID}",
            )
            self.assertEqual(len(manifest["feature"]), 64)
            self.assertEqual(len(manifest["option"]), 6)
            self.assertNotIn("patch", manifest)
            self.assertNotIn("overlay", manifest)
            self.assertTrue(
                all(not item["default_enabled"] for item in manifest["feature"])
            )


@unittest.skipUnless(
    os.environ.get("PSXRECOMP_RUNTIME_INCLUDE"),
    "set PSXRECOMP_RUNTIME_INCLUDE for trusted-resolver compile test",
)
class ResolverCompileTests(unittest.TestCase):
    def test_resolver_compiles_against_runtime_contract(self) -> None:
        root = TOOLS.parent
        source = root / "src" / "mods" / "mmx6_new_game_resolver.cpp"
        include = Path(os.environ["PSXRECOMP_RUNTIME_INCLUDE"])
        subprocess.run(
            [
                "g++",
                "-std=c++17",
                "-fsyntax-only",
                f"-I{include}",
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_resolver_runtime_composition(self) -> None:
        root = TOOLS.parent
        source = (
            root / "src" / "mods" / "mmx6_new_game_resolver.cpp"
        ).read_text(encoding="utf-8")
        include = Path(os.environ["PSXRECOMP_RUNTIME_INCLUDE"])
        feature_setup = "\n".join(
            (
                '    package.features.push_back(ModFeature{}); '
                f'package.features.back().id = "{feature.feature_id}";'
            )
            for feature in new_game.FEATURES
        )
        option_setup = "\n".join(
            (
                '    package.options.push_back(ModOption{}); '
                f'package.options.back().feature_id = "{feature.feature_id}"; '
                f'package.options.back().id = "'
                f'{"count" if feature.kind == "integer" else "rank"}"; '
                f'package.options.back().default_value = "'
                f'{"1" if feature.kind == "integer" else "C"}";'
            )
            for feature in new_game.FEATURES
            if feature.kind in {"integer", "rank"}
        )
        template_block = re.search(
            r"kTemplateReplace\s*=\s*((?:\s*\"[0-9A-F]+\")+);",
            source,
        )
        self.assertIsNotNone(template_block)
        template_base = bytes.fromhex(
            "".join(re.findall(r'"([0-9A-F]+)"', template_block.group(1)))
        )
        isolated_cases = []
        for index, feature in enumerate(new_game.FEATURES[18:], 1):
            expected_middle, expected_table = new_game.compose_state(
                {feature.feature_id: 1}, template_base
            )
            expected_writes = 4 if (
                feature.table_offset >= 0 or feature.kind == "table"
            ) else 3
            table_check = (
                f' || writes[3].replacement != '
                f'hex_bytes("{expected_table.hex().upper()}")'
                if expected_writes == 4
                else ""
            )
            isolated_cases.append(f'''
    {{
        ModSelection isolated;
        auto& feature = isolated.features["{feature.feature_id}"];
        feature.has_enabled = true;
        feature.enabled = true;
        writes.clear();
        errors.clear();
        if (!captured(package, isolated, writes, errors)) return {40 + index};
        if (
            !errors.empty() || writes.size() != {expected_writes} ||
            writes[1].replacement !=
                hex_bytes("{expected_middle.hex().upper()}"){table_check}
        ) return {110 + index};
    }}''')
        isolated_setup = "\n".join(isolated_cases)
        harness = r'''
#include "mod_packages.h"
#include <string>
#include <vector>

static PSXRecompV4::ModBuiltinResolver captured;
bool PSXRecompV4::mod_register_builtin_resolver(
    const std::string& id, ModBuiltinResolver resolver
) {
    if (id != "mmx6-new-game") return false;
    captured = std::move(resolver);
    return true;
}

__RESOLVER__

int main() {
    using namespace PSXRecompV4;
    ModPackage package;
    package.id = "mmx6.tweaks.new-game";
    package.version = "1.1.0";
    package.resolver = "builtin:mmx6-new-game";
__FEATURES__
__OPTIONS__
    if (!captured) return 1;

    ModSelection disabled;
    std::vector<ModResolution::Write> writes;
    std::vector<std::string> errors;
    if (!captured(package, disabled, writes, errors)) return 2;
    if (!writes.empty() || !errors.empty()) return 3;

    ModSelection selected;
    auto& life = selected.features["x_life_upgrades"];
    life.has_enabled = true;
    life.enabled = true;
    life.values["count"] = "16";
    auto& heart = selected.features["heart_tank_1"];
    heart.has_enabled = true;
    heart.enabled = true;
    auto& rank = selected.features["zero_starting_rank"];
    rank.has_enabled = true;
    rank.enabled = true;
    rank.values["rank"] = "UH";
    if (!captured(package, selected, writes, errors)) return 4;
    if (!errors.empty() || writes.size() != 3) return 5;
    if (
        writes[0].location != 0x8001E1B4 ||
        writes[1].location != 0x800769E0 ||
        writes[2].location != 0x8007A1C8
    ) return 6;
    const auto& composed = writes[1].replacement;
    if (composed.size() != 180) return 7;
    if (composed[0x24] != 0x40 || composed[0x88] != 0x01) return 8;
    if (
        composed[0x60] != 0x00 ||
        composed[0x70] != 0x0F ||
        composed[0x71] != 0x27
    ) return 9;
    for (const auto& write : writes) {
        if (
            write.package_id != "mmx6.tweaks.new-game" ||
            write.feature_id != "new_game_foundation"
        ) return 10;
    }

__ISOLATED_CASES__

    writes.clear();
    errors.clear();
    auto& life_part = selected.features["parts_life_up_3"];
    life_part.has_enabled = true;
    life_part.enabled = true;
    auto& hyper_dash = selected.features["part_hyper_dash"];
    hyper_dash.has_enabled = true;
    hyper_dash.enabled = true;
    auto& no_item = selected.features["mark_no_item_reploids"];
    no_item.has_enabled = true;
    no_item.enabled = true;
    if (!captured(package, selected, writes, errors)) return 11;
    if (!errors.empty() || writes.size() != 4) return 12;
    if (writes[3].location != 0x800769A0) return 13;
    if (
        writes[1].replacement[0x90] != 0x04 ||
        writes[1].replacement[0x80] != 0x10
    ) return 14;
    if (
        writes[3].replacement.size() != 64 ||
        writes[3].replacement[0x00] != 0x20 ||
        writes[3].replacement[0x14] != 0x22 ||
        writes[3].replacement[0x2E] != 0x22
    ) return 15;

    writes.clear();
    errors.clear();
    life.values["count"] = "17";
    if (captured(package, selected, writes, errors)) return 16;
    if (!writes.empty() || errors.size() != 1) return 17;

    package.version = "1.0.0";
    life.values["count"] = "16";
    writes.clear();
    errors.clear();
    if (captured(package, selected, writes, errors)) return 18;
    if (!writes.empty() || errors.size() != 1) return 19;
    return 0;
}
'''.replace("__RESOLVER__", source).replace(
            "__FEATURES__", feature_setup
        ).replace("__OPTIONS__", option_setup).replace(
            "__ISOLATED_CASES__", isolated_setup
        )
        with tempfile.TemporaryDirectory(
            prefix="mmx6-new-game-resolver-"
        ) as temp:
            executable = Path(temp) / "resolver-test.exe"
            compiled = subprocess.run(
                [
                    "g++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    f"-I{include}",
                    "-x",
                    "c++",
                    "-",
                    "-o",
                    str(executable),
                ],
                input=harness,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            subprocess.run(
                [str(executable)],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
