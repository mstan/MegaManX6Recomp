#!/usr/bin/env python3
"""Build the adversarially reviewed MMX6 standalone-player package.

Only controls whose complete v2.6.1 source closure is a set of fixed,
stock-owned writes are admitted here. Coupled input state machines, shared
parameterized hooks, and controls whose GUI silently enables another control
belong to separate resolver domains.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native
import tweaks_resolver as resolver


PACKAGE_ID = "mmx6.tweaks.player-standalone"
PACKAGE_VERSION = "1.0.0"
PATCHER_DAT_SHA256 = (
    "6e78b35142f30548c5bf6760a835773110d0cece863052a4b278722476a46707"
)
PATCHER_INIT_SHA256 = (
    "8fd2faff0d532975c66fb99742d4036dd99bdf14a7f060833b3c8d6436de488b"
)

PLAYER_CONTROLS = (
    "Anim0301",
    *(f"Anim04{index:02d}" for index in range(1, 8)),
    "DashGlobal01",
    "DashSpeedCont01",
    "DashSpeedCont02",
    "GuardShellFix01",
    "HoverUnlock02",
    *(f"MachDashCancel{index:02d}" for index in range(1, 5)),
    "MachDashDuration01",
    "MachDashDuration02",
    "MachDashImmunity01",
    *(f"MachDashInput{index:02d}" for index in range(1, 4)),
    "MachDashSpeed01",
    "MachDashSpeed02",
    "MachDashSpeed03",
    *(f"MachDashWait{index:02d}" for index in range(1, 5)),
    "ShadowSlide01",
    "ZeroAutoselect01",
    *(f"ZeroEnsuizanInput{index:02d}" for index in range(1, 5)),
    "ZeroEnsuizanMode01",
    "ZeroEnsuizanReps01",
    "ZeroGuardShellInput01",
    "ZeroGuardShellInput02",
    "ZeroGuardShellInput04",
    "ZeroGuardShellInput05",
    *(f"ZeroSentsuizanInput{index:02d}" for index in range(1, 4)),
    *(f"ZeroSentsuizanMode{index:02d}" for index in range(1, 4)),
    "ZeroYammarInput01",
)


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    name: str
    description: str
    source_control: str
    source_closure: tuple[str, ...]


@dataclass(frozen=True)
class FixedPatch:
    feature_id: str
    source_var: str
    target: str
    location: int
    expected: bytes
    replacement: bytes
    source_raw_offset: int
    semantic_owner: str
    semantic_offset: int


FEATURES = (
    FeatureSpec(
        "unlock_x_air_dash",
        "Unlock X's Air Dash",
        "Allow X to use the air dash without its normal armor restriction.",
        "DashGlobal01",
        ("DashGlobal01",),
    ),
    FeatureSpec(
        "guard_shell_bug_fix",
        "Guard Shell Bug Fix",
        "Apply the reviewed Guard Shell hit-detection correction.",
        "GuardShellFix01",
        ("GuardShellFix01",),
    ),
    FeatureSpec(
        "zero_weapon_autoselect",
        "Zero Weapon Auto-select",
        "Automatically select Zero's matching weapon after acquiring a technique.",
        "ZeroAutoselect01",
        ("ZeroAutoselect_Common", "ZeroAutoselect01"),
    ),
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _source_db(source_dir: Path):
    dat = source_dir / "data" / "_dat.ahk"
    init = source_dir / "data" / "_dat_init.ahk"
    if sha256_file(dat) != PATCHER_DAT_SHA256:
        raise ValueError("MMX6 Tweaks _dat.ahk is not reviewed v2.6.1 source")
    if sha256_file(init) != PATCHER_INIT_SHA256:
        raise ValueError(
            "MMX6 Tweaks _dat_init.ahk is not reviewed v2.6.1 source"
        )
    return resolver.TweaksDB(source_dir)


def _closure(db, source_control: str) -> tuple[str, ...]:
    result: list[str] = []
    visiting: set[str] = set()

    def add(name: str) -> None:
        if name in visiting:
            return
        visiting.add(name)
        for dependency in db.prereq.get(name, ()):
            add(dependency)
        result.append(name)

    add(source_control)
    return tuple(result)


def _raw_writes(db, spec: FeatureSpec) -> list[tuple[str, bytes, int]]:
    if _closure(db, spec.source_control) != spec.source_closure:
        raise ValueError(
            f"{spec.source_control} source closure changed: "
            f"{_closure(db, spec.source_control)}"
        )
    writes: list[tuple[str, bytes, int]] = []
    for source_var in spec.source_closure:
        expanded = engine.expand_entry(db, source_var, "b01", {}, {})
        if not expanded:
            raise ValueError(f"{source_var} source closure emits no writes")
        for replacement_hex, raw_offset in expanded:
            replacement = bytes.fromhex(replacement_hex)
            if not replacement:
                raise ValueError(f"{source_var} emits an empty source write")
            writes.append((source_var, replacement, raw_offset))
    return writes


def resolve_patches(
    stock_path: Path, source_dir: Path
) -> tuple[FixedPatch, ...]:
    if sha256_file(stock_path) != native.STOCK_SHA256:
        raise ValueError("stock image is not supported USA v1.1")
    db = _source_db(source_dir)
    patches: list[FixedPatch] = []
    with native.RawMode2Image(stock_path) as stock:
        executable = stock.read_file(native.SLUS_NAME)
        load_address = int.from_bytes(executable[0x18:0x1C], "little")
        rock_members = native.indexed_archive_members(
            stock.read_file("ROCK_X6.BIN")
        )
        for spec in FEATURES:
            for source_var, replacement, raw_offset in _raw_writes(db, spec):
                user_offset = native.raw_to_user_offset(raw_offset)
                entry, file_offset = stock.containing_file(
                    user_offset, len(replacement)
                )
                expected = stock.read_user(user_offset, len(replacement))
                if entry.name == native.SLUS_NAME:
                    target = "main_exe"
                    location = (
                        load_address + file_offset - native.USER_SECTOR
                    )
                    owner = native.SLUS_NAME
                    semantic_offset = file_offset - native.USER_SECTOR
                elif entry.name == "ROCK_X6.BIN":
                    member, relative = native.containing_member(
                        rock_members, file_offset, len(replacement)
                    )
                    if (
                        member.payload[relative : relative + len(replacement)]
                        != expected
                    ):
                        raise ValueError(
                            f"{source_var} is not contained by one indexed member"
                        )
                    target = "disc_user"
                    location = user_offset
                    owner = f"ROCK_X6.BIN member {member.member_id}"
                    semantic_offset = relative
                else:
                    raise ValueError(
                        f"{source_var} targets unsupported file {entry.name}"
                    )
                patches.append(
                    FixedPatch(
                        spec.feature_id,
                        source_var,
                        target,
                        location,
                        expected,
                        replacement,
                        raw_offset,
                        owner,
                        semantic_offset,
                    )
                )
    _validate_disjoint(patches)
    _validate_code_targets(patches, stock_path)
    return tuple(patches)


def _validate_disjoint(patches: list[FixedPatch]) -> None:
    ownership: dict[tuple[str, int], str] = {}
    for patch in patches:
        for location in range(
            patch.location, patch.location + len(patch.expected)
        ):
            key = (patch.target, location)
            previous = ownership.get(key)
            if previous is not None:
                raise ValueError(
                    f"standalone ownership overlap: {previous} and "
                    f"{patch.feature_id} at {patch.target}:0x{location:X}"
                )
            ownership[key] = patch.feature_id


def _validate_code_targets(
    patches: list[FixedPatch], stock_path: Path
) -> None:
    """Reject J/JAL replacements that target an unowned zero allocation."""
    owned_main = [
        (patch.location, patch.location + len(patch.replacement))
        for patch in patches
        if patch.target == "main_exe"
    ]
    with native.RawMode2Image(stock_path) as stock:
        executable = stock.read_file(native.SLUS_NAME)
        load = int.from_bytes(executable[0x18:0x1C], "little")
        guest_end = load + len(executable) - native.USER_SECTOR
        for patch in patches:
            for offset in range(0, len(patch.replacement) - 3, 4):
                instruction = int.from_bytes(
                    patch.replacement[offset : offset + 4], "little"
                )
                if instruction >> 26 not in {2, 3}:
                    continue
                target = 0x80000000 | (
                    (instruction & 0x03FFFFFF) << 2
                )
                if any(begin <= target < end for begin, end in owned_main):
                    continue
                if not load <= target <= guest_end - 4:
                    raise ValueError(
                        f"{patch.source_var} jumps outside owned/main code: "
                        f"0x{target:X}"
                    )
                file_offset = native.USER_SECTOR + target - load
                stock_target = executable[file_offset : file_offset + 4]
                if stock_target == bytes(4):
                    raise ValueError(
                        f"{patch.source_var} jumps into unowned zero stock "
                        f"allocation 0x{target:X}"
                    )


def manifest_text(patches: tuple[FixedPatch, ...]) -> str:
    lines = [
        "format_version = 3",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 Standalone Player Tweaks"',
        (
            'author = "acediez and MMX6 Tweaks contributors; '
            'PSXRecomp integration"'
        ),
        (
            'description = "Independent fixed player behaviors for a stock '
            'USA v1.1 disc."'
        ),
        'license = "Generated locally; original credits retained"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {q(native.GAME_ID)}",
        f"disc_sha256 = {q(native.STOCK_SHA256)}",
    ]
    for spec in FEATURES:
        lines += [
            "",
            "[[feature]]",
            f"id = {q(spec.feature_id)}",
            f"name = {q(spec.name)}",
            f"description = {q(spec.description)}",
            'group = "Player Mechanics"',
            "default_enabled = false",
        ]
    for patch in patches:
        lines += [
            "",
            "[[patch]]",
            f"feature = {q(patch.feature_id)}",
            f"target = {q(patch.target)}",
            (
                f"address = {patch.location}"
                if patch.target == "main_exe"
                else f"offset = {patch.location}"
            ),
            f"expected = {q(patch.expected.hex().upper())}",
            f"replace = {q(patch.replacement.hex().upper())}",
            "order = 0",
        ]
    return "\n".join(lines) + "\n"


def _deferred_reason(control: str) -> str:
    if control in {"Anim0301", *(f"Anim04{i:02d}" for i in range(1, 8))}:
        return "animation ownership/zero-sentinel semantics are not proven"
    if control in {
        "MachDashDuration02", "MachDashSpeed02", "MachDashSpeed03"
    }:
        return "quarantined misdirected source write; no contrary proof"
    if control == "HoverUnlock02":
        return (
            "not standalone: GUI forces HoverUnlock01 and ASM10 terminates "
            "the live source payload after slot 9"
        )
    if control == "ShadowSlide01":
        return (
            "hidden PatchList_Base dependency: callsite JAL targets the absent "
            "stock ArmorByPart_Common foundation at guest 0x8007A5DC"
        )
    if control.startswith("DashSpeedCont"):
        return "shared parameterized continuous-dash resolver domain"
    if control.startswith("MachDash"):
        return "coupled Mach Dash resolver domain"
    if control.startswith("Zero"):
        return "coupled Zero technique resolver domain"
    return "outside this fixed-write standalone domain"


def conversion_report(
    stock_path: Path, source_dir: Path, patches: tuple[FixedPatch, ...]
) -> dict:
    converted = {feature.source_control for feature in FEATURES}
    if len(PLAYER_CONTROLS) != 49 or len(set(PLAYER_CONTROLS)) != 49:
        raise AssertionError("Player Mechanics ledger is not exactly 49 controls")
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "stock_sha256": sha256_file(stock_path),
        "patcher_dat_sha256": sha256_file(
            source_dir / "data" / "_dat.ahk"
        ),
        "source_controls": sorted(converted),
        "source_control_ledger": [
            {
                "source_control": control,
                "status": "converted" if control in converted else "deferred",
                "reason": (
                    "exact fixed-write source closure with disjoint stock ownership"
                    if control in converted
                    else _deferred_reason(control)
                ),
            }
            for control in PLAYER_CONTROLS
        ],
        "features": {
            spec.feature_id: {
                "source_control": spec.source_control,
                "source_closure": list(spec.source_closure),
                "writes": [
                    {
                        "source_var": patch.source_var,
                        "source_raw_offset": patch.source_raw_offset,
                        "target": patch.target,
                        "location": patch.location,
                        "size": len(patch.expected),
                        "expected": patch.expected.hex().upper(),
                        "replace": patch.replacement.hex().upper(),
                        "semantic_owner": patch.semantic_owner,
                        "semantic_offset": patch.semantic_offset,
                    }
                    for patch in patches
                    if patch.feature_id == spec.feature_id
                ],
            }
            for spec in FEATURES
        },
        "validation": {
            "default_disabled_noop": True,
            "fixed_stock_guards": True,
            "exact_source_closure": True,
            "all_feature_byte_ownership_disjoint": True,
            "composition_order_independent": True,
            "jump_targets_owned_or_nonzero_stock_code": True,
        },
    }


def archive_bytes(manifest: str, report: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {
            "README.txt": (
                "Generated locally from reviewed MMX6 Tweaks v2.6.1 source. "
                "This package contains guarded declarations only; it contains "
                "no derived disc or runtime patcher code.\n"
            ),
            "conversion-report.json": (
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            ),
            "manifest.toml": manifest,
        }
        for name in sorted(members):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name].encode("utf-8"))
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--patcher-source", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build-local")
        / "MMX6-Tweaks-Player-Standalone.psxmod",
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()

    patches = resolve_patches(args.stock, args.patcher_source)
    report = conversion_report(args.stock, args.patcher_source, patches)
    payload = archive_bytes(manifest_text(patches), report)
    if payload != archive_bytes(manifest_text(patches), report):
        raise AssertionError("package archive is not deterministic")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "output": str(args.out),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "features": len(FEATURES),
                "source_controls": len(report["source_controls"]),
                "writes": len(patches),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
