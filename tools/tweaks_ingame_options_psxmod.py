#!/usr/bin/env python3
"""Build the resolver-backed MMX6 in-game Settings menu package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__.replace("\\", "/")).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native


PACKAGE_ID = "mmx6.tweaks.ingame-options"
PACKAGE_VERSION = "1.0.0"
RESOLVER_ID = "mmx6-ingame-options"
SOURCE_CONTROLS = ("IngameOptions01",)


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def manifest_text() -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 In-Game Settings Menu"',
        'author = "acediez; PSXRecomp integration"',
        (
            'description = "Adds the MMX6 Tweaks custom options to the '
            'in-game Settings menu. Requires Retranslation."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {q('builtin:' + RESOLVER_ID)}",
        'save_compatibility = "shared"',
        "",
        "[[dependency]]",
        'id = "mmx6.tweaks.native"',
        'version = ">=1.10.4"',
        "",
        "[[target]]",
        f"game_id = {q(native.GAME_ID)}",
        f"disc_sha256 = {q(native.STOCK_SHA256)}",
        "",
        "[[feature]]",
        'id = "settings_menu_options"',
        'name = "Settings Menu Options"',
        (
            'description = "Expose Tweaks-controlled settings in the '
            'in-game menu; Nightmare Fire hard-disable composes safely."'
        ),
        'group = "Settings Menu"',
        "default_enabled = false",
    ]
    return "\n".join(lines) + "\n"


def validate_source(stock_path: Path, source_dir: Path, profile_path: Path) -> dict:
    if file_sha256(stock_path) != native.STOCK_SHA256:
        raise AssertionError("stock disc SHA-256 does not match USA v1.1")
    db = engine.twr.TweaksDB(source_dir)
    base = engine.twr.load_profile(profile_path)
    inherited = set(db.patchlist_base) | set(db.patchlist_script)

    standalone = dict(base)
    standalone["IngameOptions01"] = "1"
    _norm, patchfile, patch_list, _values, synth = engine._assemble(
        db, standalone, base
    )
    if patchfile or patch_list or synth:
        raise AssertionError(
            "IngameOptions01 should remain payloadless without Retranslation"
        )

    with_retranslation = dict(base)
    with_retranslation["ScriptPatch02"] = "1"
    with_retranslation["IngameOptions01"] = "1"
    _norm, patchfile, patch_list, values, synth = engine._assemble(
        db, with_retranslation, base
    )
    owned = [name for name in patch_list if name not in inherited]
    if patchfile != "s02" or owned != ["IngameOptions01", "ScriptPatch02"] or synth:
        raise AssertionError(
            f"IngameOptions01 source closure changed: {patchfile=} {owned=} {synth=}"
        )
    writes = []
    for data_hex, raw_offset in engine.expand_entry(
        db, "IngameOptions01", patchfile, values, synth
    ):
        for split_hex, split_offset in engine.ecc_split(data_hex, raw_offset):
            writes.append((split_offset, bytes.fromhex(split_hex)))
    if len(writes) != 23:
        raise AssertionError(f"IngameOptions01 write count changed: {len(writes)}")
    return {
        "standalone_is_normalized_off": True,
        "requires_retranslation": True,
        "source_patchfile": patchfile,
        "source_closure": owned,
        "source_write_count": len(writes),
        "fire_overlap_policy": (
            "Resolver omits the first Nightmare Fire hook when hard-disable "
            "is active and composes the second as hard-disable word plus "
            "settings-menu tail word."
        ),
    }


def report(stock_path: Path, source_dir: Path, profile_path: Path) -> dict:
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "source_controls": list(SOURCE_CONTROLS),
        "excluded_source_controls": [],
        "deferred_source_controls": [],
        "features": {
            "settings_menu_options": {
                "source_controls": list(SOURCE_CONTROLS),
                "product_boundary": (
                    "one resolver-backed row because it owns menu hook "
                    "composition and depends on native Retranslation"
                ),
            },
        },
        "validation": validate_source(stock_path, source_dir, profile_path),
        "provenance": {
            "stock_sha256": file_sha256(stock_path),
            "source_dat_sha256": file_sha256(source_dir / "data" / "_dat.ahk"),
            "default_profile_sha256": file_sha256(profile_path),
        },
    }


def archive_member(archive, name: str, payload: str):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload.encode("utf-8"))


def write_package(path: Path, conversion_report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive_member(archive, "manifest.toml", manifest_text())
        archive_member(
            archive,
            "conversion-report.json",
            json.dumps(conversion_report, indent=2, sort_keys=True) + "\n",
        )
        archive_member(
            archive,
            "README.txt",
            "Resolver-backed In-Game Settings Menu package generated from "
            "verified MMX6 Tweaks v2.6.1 source. It contains no native code "
            "or derived disc.\n",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=native.DEFAULT_STOCK)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=engine.twr.DEFAULT_PATCHER_SRC,
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=engine.twr.DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=(
            native.ROOT
            / "build-mod-platform"
            / "test-psxmods"
            / "MMX6-Tweaks-Ingame-Options.psxmod"
        ),
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    conversion_report = report(args.stock, args.source_dir, args.profile)
    print(json.dumps(conversion_report, indent=2, sort_keys=True))
    if not args.verify_only:
        write_package(args.out, conversion_report)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
