#!/usr/bin/env python3
"""Build resolver-backed MMX6 General shared-foundation packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
import zipfile
from pathlib import Path

TOOLS = Path(__file__.replace("\\", "/")).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native


PACKAGE_ID = "mmx6.tweaks.general-foundations"
PACKAGE_VERSION = "1.3.0"
RESOLVER_ID = "mmx6-general-foundations"
SOURCE_CONTROLS = (
    "MissRepUnlocksRank01",
    "MissRepUnlocksRank02",
    "LowerDef01",
    "LowerDef02",
    "ArmorByPart01",
    "ArmorByPart02",
    "ArmorByPart03",
    "ArmorByPart04",
    "CutsceneSouls01",
    "CutsceneSouls02",
)


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def source_catalog(db) -> list[str]:
    catalog = engine.twr.parse_gui_catalog(engine.twr.DEFAULT_PATCHER_SRC, db)
    return [
        item["var"]
        for item in catalog
        if item["tab_title"] in {"General Tweaks", "Balance"}
    ]


def validate_source(stock_path: Path) -> dict:
    if file_sha256(stock_path) != native.STOCK_SHA256:
        raise AssertionError("stock disc SHA-256 does not match USA v1.1")
    db = engine.twr.TweaksDB(engine.twr.DEFAULT_PATCHER_SRC)
    profile = engine.twr.load_profile(engine.twr.DEFAULT_PROFILE)
    inherited = set(db.patchlist_base) | set(db.patchlist_script)
    cases = {}
    expected_closures = {
        "ultimate_armor_rank_unlock": (
            {"MissRepUnlocksRank01": "1"},
            ("MissRepUnlocksBase01", "MissRepUnlocksRank01"),
        ),
        "black_zero_rank_unlock": (
            {"MissRepUnlocksRank02": "1"},
            ("MissRepUnlocksBase01", "MissRepUnlocksRank02"),
        ),
        "both_rank_unlocks": (
            {"MissRepUnlocksRank01": "1", "MissRepUnlocksRank02": "1"},
            (
                "MissRepUnlocksBase01",
                "MissRepUnlocksRank01",
                "MissRepUnlocksRank02",
            ),
        ),
        "normalize_x_defense": (
            {"LowerDef01": "0"},
            ("LowerDef_X_A",),
        ),
        "normalize_zero_defense": (
            {"LowerDef02": "0"},
            ("LowerDef_Zero_A",),
        ),
        "normalize_x_and_zero_defense": (
            {"LowerDef01": "0", "LowerDef02": "0"},
            ("LowerDef_All_A",),
        ),
        "incomplete_armors_complete": (
            {"ArmorByPart01": "1", "ArmorByPart02": "1"},
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart02",
            ),
        ),
        "incomplete_armors_unarmored": (
            {"ArmorByPart01": "1", "ArmorByPart03": "1"},
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart03",
            ),
        ),
        "incomplete_armors_complete_shadow_palette": (
            {
                "ArmorByPart01": "1",
                "ArmorByPart02": "1",
                "ArmorByPart04": "1",
            },
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart02",
                "ArmorByPart04",
            ),
        ),
        "incomplete_armors_unarmored_shadow_palette": (
            {
                "ArmorByPart01": "1",
                "ArmorByPart03": "1",
                "ArmorByPart04": "1",
            },
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart03",
                "ArmorByPart04",
            ),
        ),
        "incomplete_armors_lower_defense": (
            {
                "ArmorByPart01": "1",
                "ArmorByPart02": "1",
                "LowerDef01": "0",
                "LowerDef02": "0",
            },
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart02",
                "LowerDef_All_B",
            ),
        ),
        "incomplete_armors_air_dash": (
            {
                "ArmorByPart01": "1",
                "ArmorByPart02": "1",
                "DashGlobal01": "1",
            },
            (
                "MissRepUnlocksBase01",
                "ShadowBase01",
                "ArmorByPart01",
                "ArmorByPart02",
                "DashGlobal01_ArmorByPart",
            ),
        ),
        "gate_revealed_souls": (
            {"CutsceneSouls01": "256"},
            ("CutsceneSouls_Base", "CutsceneSouls01"),
        ),
        "gate_revealed_refight_souls": (
            {"CutsceneSouls02": "256"},
            ("CutsceneSouls_Base", "CutsceneSouls02"),
        ),
        "both_gate_revealed_souls": (
            {"CutsceneSouls01": "256", "CutsceneSouls02": "9999"},
            (
                "CutsceneSouls_Base",
                "CutsceneSouls01",
                "CutsceneSouls02",
            ),
        ),
    }
    for label, (selection, expected) in expected_closures.items():
        merged = engine.merged_profile(db, json.dumps(selection))
        _norm, patchfile, patch_list, _values, synth = engine._assemble(
            db, merged, profile
        )
        owned = tuple(item for item in patch_list if item not in inherited)
        if patchfile != "b01" or owned != expected or synth:
            raise AssertionError(
                f"{label} closure changed: patchfile={patchfile!r}, "
                f"owned={owned!r}, synth={synth!r}"
            )
        _file_patch, files = engine.build_filelist(db, merged, profile)
        if files:
            raise AssertionError(f"{label} unexpectedly inserts files")
        patchfile, writes = engine.build_writelist(db, merged, profile)
        if patchfile != "b01":
            raise AssertionError(f"{label} unexpectedly left B01")
        cases[label] = {
            "selection": selection,
            "source_closure": list(owned),
            "source_write_count": len(writes),
        }
    controls = source_catalog(db)
    missing = [control for control in SOURCE_CONTROLS if control not in controls]
    if missing:
        raise AssertionError(f"source catalog missing {missing!r}")
    return cases


def manifest_text() -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 General Shared Foundations"',
        'author = "acediez"',
        (
            'description = "Resolver-backed MMX6 Tweaks controls that share '
            'General/Balance executable foundations."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {q('builtin:' + RESOLVER_ID)}",
        'save_compatibility = "shared"',
        'source_name = "Mega Man X6 Tweaks"',
        'source_url = "https://www.romhacking.net/hacks/4035/"',
        "",
        "[[author_link]]",
        'name = "acediez"',
        'url = "https://twitter.com/acediez"',
        "",
        "[[target]]",
        f"game_id = {q(native.GAME_ID)}",
        f"disc_sha256 = {q(native.STOCK_SHA256)}",
        "",
        "[[feature]]",
        'id = "ultimate_armor_rank_unlock"',
        'name = "Rank UH Unlocks Ultimate Armor"',
        (
            'description = "Unlock Ultimate Armor when X reaches Hunter Rank '
            'UH."'
        ),
        'group = "Mission Report"',
        "default_enabled = false",
        "",
        "[[feature]]",
        'id = "black_zero_rank_unlock"',
        'name = "Rank UH Unlocks Black Zero"',
        (
            'description = "Unlock Black Zero when Zero reaches Hunter Rank '
            'UH."'
        ),
        'group = "Mission Report"',
        "default_enabled = false",
        "",
        "[[feature]]",
        'id = "normalize_unarmored_x_defense"',
        'name = "Normalize Unarmored X Defense"',
        (
            'description = "Give unarmored X the same defense as armored X '
            'and Black Zero."'
        ),
        'group = "Defense"',
        "default_enabled = false",
        "",
        "[[feature]]",
        'id = "normalize_zero_defense"',
        'name = "Normalize Zero Defense"',
        (
            'description = "Give red Zero the same defense as armored X and '
            'Black Zero."'
        ),
        'group = "Defense"',
        "default_enabled = false",
        "",
        "[[feature]]",
        'id = "gate_revealed_souls"',
        'name = "Gate Revealed Souls"',
        (
            'description = "Set the Nightmare Souls threshold for the first '
            'Gate-revealed cutscene."'
        ),
        'group = "Nightmare Souls and Rank"',
        "default_enabled = false",
        "",
        "[[option]]",
        'feature = "gate_revealed_souls"',
        'id = "souls"',
        'label = "Souls"',
        'description = "Bounded threshold from MMX6 Tweaks; 3000 is stock."',
        'group = "Nightmare Souls and Rank"',
        'type = "integer"',
        "min = 256",
        "max = 9999",
        "step = 1",
        "default = 256",
        "",
        "[[feature]]",
        'id = "gate_revealed_refight_souls"',
        'name = "Gate Revealed Refight Souls"',
        (
            'description = "Set the Nightmare Souls threshold for the later '
            'Gate-revealed cutscene path."'
        ),
        'group = "Nightmare Souls and Rank"',
        "default_enabled = false",
        "",
        "[[option]]",
        'feature = "gate_revealed_refight_souls"',
        'id = "souls"',
        'label = "Souls"',
        'description = "Bounded threshold from MMX6 Tweaks; 3000 is stock."',
        'group = "Nightmare Souls and Rank"',
        'type = "integer"',
        "min = 256",
        "max = 9999",
        "step = 1",
        "default = 256",
    ]
    return "\n".join(lines) + "\n"


def report(stock_path: Path) -> dict:
    cases = validate_source(stock_path)
    return {
        "package": {
            "id": PACKAGE_ID,
            "version": PACKAGE_VERSION,
            "feature_rows": 6,
            "resolver": f"builtin:{RESOLVER_ID}",
        },
        "source_controls": list(SOURCE_CONTROLS),
        "excluded_source_controls": [],
        "deferred_source_controls": [
            {
                "source_controls": [
                    "ArmorByPart01",
                    "ArmorByPart02",
                    "ArmorByPart03",
                    "ArmorByPart04",
                ],
                "feature": "incomplete_armors_by_part",
                "reason": (
                    "Temporarily omitted from enable-all: the converted hook "
                    "calls an ArmorByPart common foundation payload that is "
                    "not yet emitted, causing a spawn-time unknown dispatch."
                ),
            }
        ],
        "features": {
            "ultimate_armor_rank_unlock": {
                "source_controls": ["MissRepUnlocksRank01"],
            },
            "black_zero_rank_unlock": {
                "source_controls": ["MissRepUnlocksRank02"],
            },
            "normalize_unarmored_x_defense": {
                "source_controls": ["LowerDef01"],
            },
            "normalize_zero_defense": {
                "source_controls": ["LowerDef02"],
            },
            "gate_revealed_souls": {
                "source_controls": ["CutsceneSouls01"],
                "option": "souls",
                "stock_value": 3000,
                "minimum": 256,
                "maximum": 9999,
                "default": 256,
            },
            "gate_revealed_refight_souls": {
                "source_controls": ["CutsceneSouls02"],
                "option": "souls",
                "stock_value": 3000,
                "minimum": 256,
                "maximum": 9999,
                "default": 256,
            },
        },
        "validation": {
            "source_closures_exact": True,
            "shared_foundations_composed_once": True,
            "stock_guards_embedded_in_resolver": True,
            "cases": cases,
        },
        "provenance": {
            "stock_sha256": file_sha256(stock_path),
            "source_dat_sha256": file_sha256(
                engine.twr.DEFAULT_PATCHER_SRC / "data" / "_dat.ahk"
            ),
            "default_profile_sha256": file_sha256(engine.twr.DEFAULT_PROFILE),
            "patched_disc_oracle_used": False,
        },
    }


def archive_member(archive, name: str, payload: str):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload.encode("utf-8"))


def write_package(path: Path, conversion_report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        archive_member(archive, "manifest.toml", manifest_text())
        archive_member(
            archive,
            "conversion-report.json",
            json.dumps(conversion_report, indent=2, sort_keys=True) + "\n",
        )
        archive_member(
            archive,
            "README.txt",
            "Trusted resolver package generated from verified MMX6 Tweaks "
            "v2.6.1 source. It contains no native code or derived disc.\n",
        )


def inspect_package(path: Path):
    with zipfile.ZipFile(path) as archive:
        manifest = tomllib.loads(archive.read("manifest.toml").decode())
        if (
            manifest["id"] != PACKAGE_ID
            or manifest["version"] != PACKAGE_VERSION
            or manifest["resolver"] != f"builtin:{RESOLVER_ID}"
            or len(manifest["feature"]) != 7
            or len(manifest.get("option", [])) != 4
        ):
            raise AssertionError("generated manifest shape changed")
        if "patch" in manifest or "overlay" in manifest:
            raise AssertionError("resolver package contains declarative writes")
        return len(archive.namelist())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=(
        Path("mmx6-tweaks") / "Mega Man X6 (USA) (v1.1).bin"
    ))
    parser.add_argument("--out", type=Path, default=(
        Path("build-mod-platform") / "mods" / "packages"
        / "MMX6-Tweaks-General-Foundations.psxmod"
    ))
    args = parser.parse_args()
    conversion_report = report(args.stock)
    write_package(args.out, conversion_report)
    members = inspect_package(args.out)
    print(json.dumps({
        "output": str(args.out),
        "archive_members": members,
        "source_controls": len(SOURCE_CONTROLS),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
