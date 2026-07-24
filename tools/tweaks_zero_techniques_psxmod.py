#!/usr/bin/env python3
"""Build the resolver-backed MMX6 Zero Techniques package."""

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

import tweaks_native_psxmod as native
import tweaks_zero_techniques_audit as audit


PACKAGE_ID = "mmx6.tweaks.zero-techniques"
PACKAGE_VERSION = "1.0.0"
RESOLVER_ID = "mmx6-zero-techniques"
SOURCE_CONTROLS = audit.REJECTED_CONTROLS


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def choice_option(
    lines: list[str], option_id: str, label: str, default: str,
    choices: list[tuple[str, str]], description: str = "",
) -> None:
    lines += [
        "",
        "[[option]]",
        'feature = "zero_techniques"',
        f"id = {q(option_id)}",
        f"label = {q(label)}",
        f"description = {q(description or 'Zero Techniques option.')}",
        'group = "Zero Techniques"',
        'type = "choice"',
        f"default = {q(default)}",
    ]
    for value, choice_label in choices:
        lines += [
            "",
            "[[option.choice]]",
            f"value = {q(value)}",
            f"label = {q(choice_label)}",
        ]


def manifest_text() -> str:
    lines = [
        "format_version = 3",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 Zero Techniques"',
        (
            'author = "acediez and MMX6 Tweaks contributors; '
            'PSXRecomp integration"'
        ),
        (
            'description = "Resolver-backed coupled Zero technique input '
            'and behavior controls."'
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
        'id = "zero_techniques"',
        'name = "Zero Techniques"',
        (
            'description = "Configure Sentsuizan, Ensuizan, Guard Shell, '
            'and Yammar Option inputs as one coupled Tweaks domain."'
        ),
        'group = "Player Mechanics"',
        "default_enabled = false",
    ]
    choice_option(
        lines,
        "sentsuizan_input",
        "Sentsuizan Input",
        "up_attack",
        [
            ("up_attack", "Up + Attack"),
            ("down_special", "Down + Special"),
            ("up_special", "Up + Special"),
        ],
        "Input command for Sentsuizan.",
    )
    choice_option(
        lines,
        "sentsuizan_mode",
        "Sentsuizan Mode",
        "press_no_cancel",
        [
            ("press_no_cancel", "Press / No Cancel"),
            ("press_back", "Press / Back"),
            ("hold_release", "Hold / Release"),
        ],
        "Execution/cancel behavior for Sentsuizan.",
    )
    choice_option(
        lines,
        "ensuizan_input",
        "Ensuizan Input",
        "down_special",
        [
            ("down_special", "Down + Special"),
            ("up_special", "Up + Special"),
            ("up_attack", "Up + Attack"),
            ("air_special", "Special"),
        ],
        "Input command for Ensuizan.",
    )
    lines += [
        "",
        "[[option]]",
        'feature = "zero_techniques"',
        'id = "ensuizan_air_mode"',
        'label = "Ensuizan Air Move Mode"',
        'description = "Enable Tweaks air-move Ensuizan behavior."',
        'group = "Zero Techniques"',
        'type = "boolean"',
        "default = false",
        "",
        "[[option]]",
        'feature = "zero_techniques"',
        'id = "ensuizan_reps"',
        'label = "Ensuizan Repetitions"',
        'description = "Execution/cancelling count while Air Move Mode is enabled."',
        'group = "Zero Techniques"',
        'type = "integer"',
        "min = 1",
        "max = 255",
        "step = 1",
        "default = 3",
    ]
    choice_option(
        lines,
        "guard_shell_activation",
        "Guard Shell Activation",
        "menu",
        [
            ("menu", "Menu Activation"),
            ("like_x", "Activate like X"),
            ("down_special", "Down + Special"),
            ("up_giga", "Up + Giga Attack"),
        ],
        "Guard Shell activation command.",
    )
    lines += [
        "",
        "[[option]]",
        'feature = "zero_techniques"',
        'id = "yammar_like_x"',
        'label = "Yammar Option Like X"',
        'description = "Activate Yammar Option like X."',
        'group = "Zero Techniques"',
        'type = "boolean"',
        "default = false",
    ]
    return "\n".join(lines) + "\n"


def report(stock_path: Path, source_dir: Path, profile_path: Path) -> dict:
    if file_sha256(stock_path) != native.STOCK_SHA256:
        raise AssertionError("stock disc SHA-256 does not match USA v1.1")
    zero_audit = audit.build_audit(source_dir, profile_path)
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "source_controls": sorted(SOURCE_CONTROLS),
        "excluded_source_controls": [],
        "deferred_source_controls": [],
        "features": {
            "zero_techniques": {
                "source_controls": sorted(SOURCE_CONTROLS),
                "product_boundary": (
                    "one resolver-backed option domain; invalid combinations "
                    "that Tweaks would silently rewrite fail closed"
                ),
            },
        },
        "validation": {
            "zero_audit_cases": zero_audit["cases"],
            "cross_forcing_is_fail_closed": True,
            "retranslation_hints_use_resolver_context": True,
        },
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
            "Resolver-backed Zero Techniques package generated from verified "
            "MMX6 Tweaks v2.6.1 source. It contains no native code or derived "
            "disc.\n",
        )


def inspect_package(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        manifest = tomllib.loads(archive.read("manifest.toml").decode())
        if (
            manifest["id"] != PACKAGE_ID
            or manifest["version"] != PACKAGE_VERSION
            or manifest["resolver"] != f"builtin:{RESOLVER_ID}"
            or len(manifest["feature"]) != 1
            or len(manifest.get("option", [])) != 7
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
    parser.add_argument("--patcher-source", type=Path, default=(
        Path("mmx6-tweaks") / "_patcher" / "src_extracted"
        / "Mega Man X6 Tweaks Patcher (v2.6.1)" / "_src"
    ))
    parser.add_argument("--default-profile", type=Path, default=(
        Path("mmx6-tweaks") / "_patcher" / "run_extracted"
        / "profiles" / "default.x6tweaksprofile"
    ))
    parser.add_argument("--out", type=Path, default=(
        Path("build-mod-platform") / "mods" / "packages"
        / "MMX6-Tweaks-Zero-Techniques.psxmod"
    ))
    args = parser.parse_args()
    conversion_report = report(
        args.stock, args.patcher_source, args.default_profile)
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
