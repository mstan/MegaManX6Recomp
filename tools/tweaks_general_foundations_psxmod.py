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
PACKAGE_VERSION = "1.0.0"
RESOLVER_ID = "mmx6-general-foundations"
SOURCE_CONTROLS = (
    "MissRepUnlocksRank01",
    "MissRepUnlocksRank02",
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
        'author = "acediez; PSXRecomp integration by DuoDynamo and NectarHime"',
        (
            'description = "Resolver-backed MMX6 Tweaks controls that share '
            'General/Balance executable foundations."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {q('builtin:' + RESOLVER_ID)}",
        'save_compatibility = "shared"',
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
    ]
    return "\n".join(lines) + "\n"


def report(stock_path: Path) -> dict:
    cases = validate_source(stock_path)
    return {
        "package": {
            "id": PACKAGE_ID,
            "version": PACKAGE_VERSION,
            "feature_rows": 2,
            "resolver": f"builtin:{RESOLVER_ID}",
        },
        "source_controls": list(SOURCE_CONTROLS),
        "excluded_source_controls": [],
        "deferred_source_controls": [],
        "features": {
            "ultimate_armor_rank_unlock": {
                "source_controls": ["MissRepUnlocksRank01"],
            },
            "black_zero_rank_unlock": {
                "source_controls": ["MissRepUnlocksRank02"],
            },
        },
        "validation": {
            "source_closures_exact": True,
            "shared_foundation_composed_once": True,
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
            or len(manifest["feature"]) != 2
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
