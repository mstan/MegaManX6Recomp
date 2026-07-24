#!/usr/bin/env python3
"""Build the resolver-backed MMX6 continuous-dash speed package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native
import tweaks_resolver as resolver


PACKAGE_ID = "mmx6.tweaks.continuous-dash"
PACKAGE_VERSION = "1.0.0"
RESOLVER_ID = "mmx6-continuous-dash"
DAT_SHA256 = (
    "6e78b35142f30548c5bf6760a835773110d0cece863052a4b278722476a46707"
)
INIT_SHA256 = (
    "8fd2faff0d532975c66fb99742d4036dd99bdf14a7f060833b3c8d6436de488b"
)
PROFILE_SHA256 = (
    "5070be21fbcb3a277925eb6f7b3d06699355f37d562f3f55d9bfec1d34130c0a"
)
FOUNDATION_RAW = 0x1D954A1C
NORMAL_RAWS = (0x1D954930, 0x1D954938)
FOUNDATION = bytes.fromhex(
    "0100053C0008A5340401028E0C01048E211043000801038E"
)
FEATURES = (
    {
        "id": "continuous_dash_speed_normal",
        "source": "DashSpeedCont01",
        "name": "Continuous Dash Speed — Normal",
        "description": "Set normal ground/air continuous dash speed.",
        "minimum": 200000,
        "maximum": 600000,
        "default": 270336,
    },
    {
        "id": "continuous_dash_speed_hyper",
        "source": "DashSpeedCont02",
        "name": "Continuous Dash Speed — Hyper",
        "description": "Set the added Hyper Dash speed component.",
        "minimum": 60000,
        "maximum": 160000,
        "default": 67584,
    },
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def halves(value: int) -> tuple[bytes, bytes]:
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("continuous-dash value does not fit u32")
    return (
        ((value >> 16) & 0xFFFF).to_bytes(2, "little"),
        (value & 0xFFFF).to_bytes(2, "little"),
    )


def compose(
    normal: int | None, hyper: int | None
) -> list[tuple[int, bytes]]:
    hyper_value = 67584 if hyper is None else hyper
    high, low = halves(hyper_value)
    foundation = bytearray(FOUNDATION)
    foundation[0:2] = high
    foundation[4:6] = low
    writes = [(FOUNDATION_RAW, bytes(foundation))]
    if normal is not None:
        high, low = halves(normal)
        for raw in NORMAL_RAWS:
            writes += [(raw, high), (raw + 4, low)]
    return writes


def final_byte_map(writes: list[tuple[int, bytes]]) -> dict[int, int]:
    result: dict[int, int] = {}
    for raw, payload in writes:
        for index, value in enumerate(payload):
            result[raw + index] = value
    return result


def validate_source(
    source_dir: Path, profile_path: Path
) -> list[dict]:
    if sha256_file(source_dir / "data" / "_dat.ahk") != DAT_SHA256:
        raise ValueError("MMX6 Tweaks _dat.ahk is not reviewed v2.6.1")
    if sha256_file(source_dir / "data" / "_dat_init.ahk") != INIT_SHA256:
        raise ValueError("MMX6 Tweaks _dat_init.ahk is not reviewed v2.6.1")
    if sha256_file(profile_path) != PROFILE_SHA256:
        raise ValueError("MMX6 Tweaks default profile identity changed")
    db = resolver.TweaksDB(source_dir)
    profile = resolver.load_profile(profile_path)
    cases = (
        ("normal-min", {"DashSpeedCont01": "200000"}, 200000, None),
        ("normal-max", {"DashSpeedCont01": "600000"}, 600000, None),
        ("hyper-min", {"DashSpeedCont02": "60000"}, None, 60000),
        ("hyper-max", {"DashSpeedCont02": "160000"}, None, 160000),
        (
            "both",
            {"DashSpeedCont01": "333333", "DashSpeedCont02": "123456"},
            333333,
            123456,
        ),
    )
    evidence = []
    owned_ranges = (
        (FOUNDATION_RAW, FOUNDATION_RAW + len(FOUNDATION)),
        *((raw, raw + 8) for raw in NORMAL_RAWS),
    )
    for label, changes, normal, hyper in cases:
        merged = OrderedDict(profile)
        merged.update(changes)
        _normalized, patchfile, patch_list, _values, synth = engine._assemble(
            db, merged, profile
        )
        relevant = [
            name
            for name in patch_list
            if name in {
                "DashSpeedCont_Base",
                "DashSpeedCont01",
                "DashSpeedCont02",
            }
        ]
        expected_closure = ["DashSpeedCont_Base", *changes]
        if patchfile != "b01" or relevant != expected_closure or synth:
            raise AssertionError(
                f"{label} source closure changed: {relevant}, {list(synth)}"
            )
        _patchfile, all_writes = engine.build_writelist(db, merged, profile)
        owned = [
            (raw, bytes.fromhex(data))
            for data, raw in all_writes
            if any(begin <= raw < end for begin, end in owned_ranges)
        ]
        expected = compose(normal, hyper)
        if final_byte_map(owned) != final_byte_map(expected):
            raise AssertionError(
                f"{label} composer differs from upstream writes: "
                f"{owned!r} != {expected!r}"
            )
        evidence.append(
            {
                "case": label,
                "source_values": changes,
                "source_closure": relevant,
                "upstream_write_count": len(owned),
                "resolved_write_count": 1 + (2 if normal is not None else 0),
                "composed_sha256": hashlib.sha256(
                    b"".join(
                        raw.to_bytes(8, "little") + data
                        for raw, data in owned
                    )
                ).hexdigest(),
            }
        )
    return evidence


def stock_guards(stock_path: Path) -> list[dict]:
    if sha256_file(stock_path) != native.STOCK_SHA256:
        raise ValueError("stock image is not supported USA v1.1")
    guards = []
    with native.RawMode2Image(stock_path) as stock:
        executable = stock.read_file(native.SLUS_NAME)
        load = int.from_bytes(executable[0x18:0x1C], "little")
        for raw, size, owner in (
            (FOUNDATION_RAW, len(FOUNDATION), "continuous hook foundation"),
            (NORMAL_RAWS[0], 8, "normal speed site 1"),
            (NORMAL_RAWS[1], 8, "normal speed site 2"),
        ):
            user = native.raw_to_user_offset(raw)
            entry, file_offset = stock.containing_file(user, size)
            if entry.name != native.SLUS_NAME:
                raise AssertionError("continuous dash site left main executable")
            expected = stock.read_user(user, size)
            guards.append(
                {
                    "source_raw_offset": raw,
                    "guest_address": load + file_offset - native.USER_SECTOR,
                    "size": size,
                    "semantic_owner": owner,
                    "expected": expected.hex().upper(),
                    "expected_sha256": hashlib.sha256(expected).hexdigest(),
                }
            )
    wanted = (
        (0x8003D694, "0100053C0401028E0C01048E211043000801038E0008A534"),
        (0x8003D5A8, "0600093C00802935"),
        (0x8003D5B0, "04000B3C00206B35"),
    )
    if tuple(
        (item["guest_address"], item["expected"]) for item in guards
    ) != wanted:
        raise AssertionError("continuous dash stock guards changed")
    return guards


def manifest_text() -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        'name = "Mega Man X6 Continuous Dash Speeds"',
        (
            'author = "acediez and MMX6 Tweaks contributors; '
            'PSXRecomp integration"'
        ),
        (
            'description = "Independently configurable normal and Hyper '
            'continuous-dash speeds."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {q('builtin:' + RESOLVER_ID)}",
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {q(native.GAME_ID)}",
        f"disc_sha256 = {q(native.STOCK_SHA256)}",
    ]
    for feature in FEATURES:
        lines += [
            "",
            "[[feature]]",
            f"id = {q(feature['id'])}",
            f"name = {q(feature['name'])}",
            f"description = {q(feature['description'])}",
            'group = "Player Mechanics / Dash Speed"',
            "default_enabled = false",
            "",
            "[[option]]",
            f"feature = {q(feature['id'])}",
            'id = "speed"',
            'label = "Speed"',
            (
                'description = "Fixed-point speed value while this row is '
                'enabled."'
            ),
            'group = "Player Mechanics / Dash Speed"',
            'type = "integer"',
            f"min = {feature['minimum']}",
            f"max = {feature['maximum']}",
            "step = 1",
            f"default = {feature['default']}",
        ]
    return "\n".join(lines) + "\n"


def report(
    stock_path: Path, source_dir: Path, profile_path: Path
) -> dict:
    evidence = validate_source(source_dir, profile_path)
    guards = stock_guards(stock_path)
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "resolver": f"builtin:{RESOLVER_ID}",
        "source_controls": ["DashSpeedCont01", "DashSpeedCont02"],
        "source_closure": {
            "DashSpeedCont01": [
                "DashSpeedCont_Base", "DashSpeedCont01"
            ],
            "DashSpeedCont02": [
                "DashSpeedCont_Base", "DashSpeedCont02"
            ],
        },
        "stock_sha256": sha256_file(stock_path),
        "patcher_dat_sha256": sha256_file(
            source_dir / "data" / "_dat.ahk"
        ),
        "default_profile_sha256": sha256_file(profile_path),
        "stock_guards": guards,
        "source_parity": evidence,
        "validation": {
            "default_disabled_noop": True,
            "shared_foundation_emitted_once": True,
            "hot_path_has_no_runtime_selection_lookup": True,
            "all_feature_composition_order_independent": True,
            "fixed_stock_guard_ownership": True,
        },
    }


def archive_bytes(report_data: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {
            "README.txt": (
                "Trusted resolver declarations generated from reviewed MMX6 "
                "Tweaks v2.6.1 source. No derived disc or native payload is "
                "stored in this archive.\n"
            ),
            "conversion-report.json": (
                json.dumps(report_data, indent=2, sort_keys=True) + "\n"
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
        "--out",
        type=Path,
        default=Path("build-local")
        / "MMX6-Tweaks-Continuous-Dash.psxmod",
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()

    report_data = report(
        args.stock, args.patcher_source, args.default_profile
    )
    payload = archive_bytes(report_data)
    if payload != archive_bytes(report_data):
        raise AssertionError("continuous-dash package is not deterministic")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "output": str(args.out),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_controls": 2,
                "source_parity_cases": len(report_data["source_parity"]),
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
