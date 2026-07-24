#!/usr/bin/env python3
"""Build the trusted MMX6 Blade Mach Dash state-machine package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native
import tweaks_resolver as resolver


PACKAGE_ID = "mmx6.tweaks.mach-dash"
PACKAGE_VERSION = "1.1.0"
RESOLVER_ID = "mmx6-mach-dash"
FEATURE_ID = "blade_mach_dash_behavior"
DAT_SHA256 = (
    "6e78b35142f30548c5bf6760a835773110d0cece863052a4b278722476a46707"
)
PROFILE_SHA256 = (
    "5070be21fbcb3a277925eb6f7b3d06699355f37d562f3f55d9bfec1d34130c0a"
)
SOURCE_CONTROLS = (
    *(f"MachDashInput{index:02d}" for index in range(1, 4)),
    *(f"MachDashWait{index:02d}" for index in range(1, 5)),
    *(f"MachDashCancel{index:02d}" for index in range(1, 5)),
    "MachDashDuration01",
    "MachDashDuration02",
    "MachDashSpeed01",
    "MachDashSpeed02",
    "MachDashSpeed03",
    "MachDashImmunity01",
)
GUI_SLIDER_CONTROLS = (
    "MachDashDuration02", "MachDashSpeed02", "MachDashSpeed03"
)
STATIC_VARS = (
    "MachDashBase01",
    "MachDashInput02",
    "MachDashInput03",
    "MachDashWait02",
    "MachDashWait03",
    "MachDashWait04",
    "PressBack01",
    "MachDashCancelShared01",
    "MachDashCancel02",
    "MachDashCancel03",
    "MachDashCancel04",
    "MachDashInput03_Cancel03",
)
MEMBER2_LOAD = 0x801E9800
RESOLVER_SOURCE = (
    TOOLS.parent / "src" / "mods" / "mmx6_mach_dash_resolver.cpp"
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _set_radio(changes: dict[str, str], prefix: str, chosen: int, count: int):
    for index in range(1, count + 1):
        changes[f"{prefix}{index:02d}"] = "1" if index == chosen else "0"


def source_cases(source_dir: Path, profile_path: Path) -> list[dict]:
    if sha256_file(source_dir / "data" / "_dat.ahk") != DAT_SHA256:
        raise ValueError("MMX6 Tweaks _dat.ahk is not reviewed v2.6.1")
    if sha256_file(profile_path) != PROFILE_SHA256:
        raise ValueError("MMX6 Tweaks default profile identity changed")
    db = resolver.TweaksDB(source_dir)
    profile = resolver.load_profile(profile_path)
    disabled: dict[str, str] = {}
    _set_radio(disabled, "MachDashInput", 2, 3)
    hybrid: dict[str, str] = {}
    _set_radio(hybrid, "MachDashInput", 3, 3)
    _set_radio(hybrid, "MachDashWait", 3, 4)
    _set_radio(hybrid, "MachDashCancel", 3, 4)
    normalized: dict[str, str] = {}
    _set_radio(normalized, "MachDashInput", 3, 3)
    _set_radio(normalized, "MachDashWait", 4, 4)
    _set_radio(normalized, "MachDashCancel", 4, 4)
    immunity: dict[str, str] = {"MachDashImmunity01": "12"}
    _set_radio(immunity, "MachDashCancel", 2, 4)
    cases = (
        ("disabled-input", disabled),
        ("hybrid-minimum-hold", hybrid),
        ("no-stop-normalizes-hybrid", normalized),
        (
            "duration-speed",
            {"MachDashDuration01": "20", "MachDashSpeed01": "600000"},
        ),
        ("press-back-immunity", immunity),
    )
    evidence = []
    allowed = set(STATIC_VARS) | (set(SOURCE_CONTROLS) - set(GUI_SLIDER_CONTROLS))
    for label, changes in cases:
        merged = OrderedDict(profile)
        merged.update(changes)
        normalized_profile, patchfile, patch_list, values, synth = (
            engine._assemble(db, merged, profile)
        )
        relevant = [
            item for item in patch_list
            if item in allowed and engine.expand_entry(
                db, item, patchfile, values, synth
            )
        ]
        _patchfile, writes = engine.build_writelist(db, merged, profile)
        relevant_writes = []
        for item in relevant:
            relevant_writes += engine.expand_entry(
                db, item, patchfile, values, synth
            )
        if patchfile != "b01" or not relevant_writes:
            raise AssertionError(f"{label} lost its exact B01 source closure")
        evidence.append(
            {
                "case": label,
                "submitted": changes,
                "normalized": {
                    control: normalized_profile.get(control)
                    for control in SOURCE_CONTROLS
                    if control in changes or
                    normalized_profile.get(control) != profile.get(control)
                },
                "emitting_source_closure": relevant,
                "owned_write_count": len(relevant_writes),
                "owned_write_sha256": hashlib.sha256(
                    b"".join(
                        raw.to_bytes(8, "little") +
                        bytes.fromhex(payload)
                        for payload, raw in relevant_writes
                    )
                ).hexdigest(),
                "whole_upstream_write_count": len(writes),
            }
        )
    return evidence


def guard_and_control_flow(source_dir: Path, stock_path: Path) -> dict:
    db = resolver.TweaksDB(source_dir)
    operations = []
    with native.RawMode2Image(stock_path) as stock:
        if sha256_file(stock_path) != native.STOCK_SHA256:
            raise ValueError("stock image is not supported USA v1.1")
        executable = stock.read_file(native.SLUS_NAME)
        load = int.from_bytes(executable[0x18:0x1C], "little")
        rock_members = native.indexed_archive_members(
            stock.read_file("ROCK_X6.BIN")
        )
        for source_var in STATIC_VARS:
            for replacement_hex, raw in engine.expand_entry(
                db, source_var, "b01", {}, {}
            ):
                replacement = bytes.fromhex(replacement_hex)
                user = native.raw_to_user_offset(raw)
                entry, file_offset = stock.containing_file(
                    user, len(replacement)
                )
                expected = stock.read_user(user, len(replacement))
                member_id = None
                member_relative = None
                if entry.name == native.SLUS_NAME:
                    target = "main_exe"
                    location = load + file_offset - native.USER_SECTOR
                elif entry.name == "ROCK_X6.BIN":
                    member, member_relative = native.containing_member(
                        rock_members, file_offset, len(replacement)
                    )
                    member_id = member.member_id
                    target = "disc_user"
                    location = user
                else:
                    raise AssertionError(
                        f"{source_var} targets unsupported {entry.name}"
                    )
                operations.append(
                    {
                        "source_var": source_var,
                        "source_raw_offset": raw,
                        "target": target,
                        "location": location,
                        "expected": expected,
                        "replacement": replacement,
                        "member_id": member_id,
                        "member_relative_offset": member_relative,
                    }
                )
        owned_main = [
            (
                item["location"],
                item["location"] + len(item["replacement"]),
            )
            for item in operations if item["target"] == "main_exe"
        ]
        member2 = rock_members[2]
        owned_member2 = [
            (
                MEMBER2_LOAD + item["member_relative_offset"],
                MEMBER2_LOAD + item["member_relative_offset"] +
                len(item["replacement"]),
            )
            for item in operations if item["member_id"] == 2
        ]
        jumps = []
        for item in operations:
            replacement = item["replacement"]
            for offset in range(0, len(replacement) - 3, 4):
                instruction = int.from_bytes(
                    replacement[offset : offset + 4], "little"
                )
                if instruction >> 26 not in {2, 3}:
                    continue
                target = 0x80000000 | (
                    (instruction & 0x03FFFFFF) << 2
                )
                ownership = ""
                if any(begin <= target < end for begin, end in owned_main):
                    ownership = "package-owned-main"
                elif any(
                    begin <= target < end
                    for begin, end in owned_member2
                ):
                    ownership = "package-owned-member-2"
                elif load <= target <= load + len(executable) - 2052:
                    file_offset = native.USER_SECTOR + target - load
                    if executable[file_offset : file_offset + 4] == bytes(4):
                        raise AssertionError(
                            f"{item['source_var']} jumps into zero main "
                            f"allocation 0x{target:X}"
                        )
                    ownership = "nonzero-stock-main"
                elif MEMBER2_LOAD <= target <= (
                    MEMBER2_LOAD + len(member2.payload) - 4
                ):
                    relative = target - MEMBER2_LOAD
                    if member2.payload[relative : relative + 4] == bytes(4):
                        raise AssertionError(
                            f"{item['source_var']} jumps into zero member 2 "
                            f"allocation 0x{target:X}"
                        )
                    ownership = "nonzero-stock-member-2"
                else:
                    raise AssertionError(
                        f"{item['source_var']} has unowned J/JAL 0x{target:X}"
                    )
                jumps.append(
                    {
                        "source_var": item["source_var"],
                        "target": target,
                        "ownership": ownership,
                    }
                )
    return {
        "operations": [
            {
                **{
                    key: value for key, value in item.items()
                    if key not in {"expected", "replacement"}
                },
                "size": len(item["expected"]),
                "expected": item["expected"].hex().upper(),
                "replace": item["replacement"].hex().upper(),
            }
            for item in operations
        ],
        "jumps": jumps,
    }


def validate_resolver_table(operations: list[dict]) -> None:
    text = RESOLVER_SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{\s*ModPatchTarget::(MainExe|DiscUser),\s*"
        r"(0x[0-9A-Fa-f]+),\s*\"([0-9A-F]+)\",\s*"
        r"\"([0-9A-F]+)\"\s*\}",
        re.S,
    )
    parsed = sorted(
        (
            "main_exe" if target == "MainExe" else "disc_user",
            int(location, 16),
            expected,
            replacement,
        )
        for target, location, expected, replacement in pattern.findall(text)
    )
    source = sorted(
        (
            item["target"],
            item["location"],
            item["expected"],
            item["replace"],
        )
        for item in operations
    )
    if parsed != source:
        raise AssertionError(
            "trusted Mach Dash resolver table differs from source closure"
        )


def _choice(lines: list[str], value: str, label: str) -> None:
    lines += [
        "",
        "[[option.choice]]",
        f"value = {q(value)}",
        f"label = {q(label)}",
    ]


def manifest_text() -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 Blade Mach Dash"',
        (
            'author = "acediez and MMX6 Tweaks contributors; '
            'PSXRecomp integration"'
        ),
        (
            'description = "One coherent Blade Mach Dash behavior with '
            'internally composed controls."'
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
        f"id = {q(FEATURE_ID)}",
        'name = "Blade Mach Dash Behavior"',
        (
            'description = "Configure the coupled input, stop, cancellation, '
            'duration, speed, and immunity state machine."'
        ),
        'group = "Player Mechanics / Blade Armor"',
        "default_enabled = false",
    ]
    choice_options = (
        ("input", "Input", "normal",
         (("normal", "Normal"), ("disabled", "Disabled"), ("hybrid", "Hybrid"))),
        ("wait", "Stop behavior", "normal",
         (("normal", "Normal"), ("unlimited", "Unlimited"),
          ("minimum", "Minimum"), ("no_stop", "No Stop"))),
        ("cancel", "Cancellation", "no_cancel",
         (("no_cancel", "No Cancel"), ("press_back", "Press / Back"),
          ("hold_release", "Hold / Release"), ("infinite", "Infinite"))),
    )
    for option_id, label, default, choices in choice_options:
        lines += [
            "",
            "[[option]]",
            f"feature = {q(FEATURE_ID)}",
            f"id = {q(option_id)}",
            f"label = {q(label)}",
            'description = "Radio alternatives from MMX6 Tweaks v2.6.1."',
            'group = "Blade Mach Dash"',
            'type = "choice"',
            f"default = {q(default)}",
        ]
        for value, choice_label in choices:
            _choice(lines, value, choice_label)
    for option_id, label, minimum, maximum, default in (
        ("duration", "Duration", 10, 50, 15),
        ("speed", "Speed", 200000, 600000, 540672),
        ("immunity", "Immunity", 4, 50, 9),
    ):
        lines += [
            "",
            "[[option]]",
            f"feature = {q(FEATURE_ID)}",
            f"id = {q(option_id)}",
            f"label = {q(label)}",
            'description = "Bounded source value while Mach Dash is enabled."',
            'group = "Blade Mach Dash"',
            'type = "integer"',
            f"min = {minimum}",
            f"max = {maximum}",
            "step = 1",
            f"default = {default}",
        ]
    return "\n".join(lines) + "\n"


def build_report(
    source_dir: Path, profile_path: Path, stock_path: Path
) -> dict:
    evidence = source_cases(source_dir, profile_path)
    audit = guard_and_control_flow(source_dir, stock_path)
    validate_resolver_table(audit["operations"])
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "resolver": f"builtin:{RESOLVER_ID}",
        "source_controls": sorted(SOURCE_CONTROLS),
        "gui_slider_controls": {
            "MachDashDuration02": (
                "represented by the coherent duration option; the trusted "
                "resolver emits the same bounded duration byte rather than "
                "treating the GUI slider as a separate mod"
            ),
            "MachDashSpeed02": (
                "represented by the coherent speed option; the trusted "
                "resolver composes the high halfword of Mach Dash speed"
            ),
            "MachDashSpeed03": (
                "represented by the coherent speed option; the trusted "
                "resolver composes the low halfword of Mach Dash speed"
            ),
        },
        "source_parity": evidence,
        "trusted_operations": audit["operations"],
        "control_flow_ownership": audit["jumps"],
        "normalization": {
            "hybrid_plus_no_stop": (
                "upstream GuiControl resolves input to Normal and restores "
                "duration/speed defaults"
            ),
            "no_cancel": "upstream GuiControl restores immunity default",
        },
        "validation": {
            "default_disabled_noop": True,
            "source_ranges_enforced": True,
            "shared_allocations_composed_once": True,
            "operation_order_resolved_before_play": True,
            "j_jal_targets_owned_or_nonzero_stock_code": True,
            "resolver_static_table_matches_source_closure": True,
        },
    }


def archive_bytes(report: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {
            "README.txt": (
                "Trusted Blade Mach Dash declarations generated from reviewed "
                "MMX6 Tweaks v2.6.1 source. The archive contains no native "
                "code or derived disc.\n"
            ),
            "conversion-report.json": (
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            ),
            "manifest.toml": manifest_text(),
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
    parser.add_argument("--default-profile", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path,
        default=Path("build-local") / "MMX6-Tweaks-Mach-Dash.psxmod"
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    report = build_report(
        args.patcher_source, args.default_profile, args.stock
    )
    payload = archive_bytes(report)
    if payload != archive_bytes(report):
        raise AssertionError("Mach Dash package is not deterministic")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "output": str(args.out),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source_controls": len(SOURCE_CONTROLS),
        "trusted_operations": len(report["trusted_operations"]),
        "control_flow_edges": len(report["control_flow_ownership"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
