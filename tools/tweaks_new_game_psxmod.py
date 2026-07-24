#!/usr/bin/env python3
"""Build the reviewed resolver-backed MMX6 Tweaks New Game package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__.replace("\\", "/")).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_native_psxmod as native


PACKAGE_ID = "mmx6.tweaks.new-game"
PACKAGE_VERSION = "1.0.0"
RESOLVER_ID = "mmx6-new-game"
FOUNDATION_RAWS = (0x1D930B9C, 0x1D9965F8, 0x1D99A630)
FOUNDATION_HASHES = (
    "650ea19428557bf4849f703b30a7daf8c75486655f8c3f7d5ead17b6adc7f159",
    "951fae5d7f169f3381d16d607f6a0cbb7de2b117573f4dd003c43a11c6b73154",
    "a9e8b1c571af2d9cae794992fc97e48e92024a19f3556fea80ebce2e19ed5e4e",
)


@dataclass(frozen=True)
class Feature:
    feature_id: str
    name: str
    source_control: str
    kind: str
    field_offset: int
    minimum: int = 0
    maximum: int = 0
    addend: int = 0
    multiplier: int = 1
    bit: int = 0
    aux_offset: int = 0


FEATURES = (
    Feature("x_life_upgrades", "X Starting Life Upgrades", "LifeUp01",
            "integer", 0x24, 1, 16, 0x20, 2),
    Feature("zero_life_upgrades", "Zero Starting Life Upgrades", "LifeUp02",
            "integer", 0x28, 1, 16, 0x20, 2),
    Feature("x_energy_upgrades", "X Starting Energy Upgrades", "EnergyUp01",
            "integer", 0x3C, 1, 8, 0x30, 2),
    Feature("zero_energy_upgrades", "Zero Starting Energy Upgrades", "EnergyUp02",
            "integer", 0x40, 1, 8, 0x30, 2),
    Feature("x_starting_rank", "X Starting Rank", "CharRank01",
            "rank", 0x5C, aux_offset=0x6C),
    Feature("zero_starting_rank", "Zero Starting Rank", "CharRank02",
            "rank", 0x60, aux_offset=0x70),
    *tuple(
        Feature(
            f"heart_tank_{index}",
            f"Start with Heart Tank {index}",
            f"HeartTankAdd{index:02d}",
            "bit",
            0x88,
            bit=1 << (index - 1),
        )
        for index in range(1, 9)
    ),
    *tuple(
        Feature(
            f"sub_tank_{index}",
            f"Start with Sub Tank {index}",
            f"SubTankAdd{index:02d}",
            "bit",
            0x50,
            bit=1 << (index + 3),
        )
        for index in range(1, 5)
    ),
)
FEATURE_BY_ID = {item.feature_id: item for item in FEATURES}
RANK_VALUES = {
    "C": (6, 200),
    "B": (5, 300),
    "A": (4, 500),
    "SA": (3, 800),
    "GA": (2, 1200),
    "PA": (1, 5000),
    "UH": (0, 9999),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def source_catalog(db) -> list[str]:
    catalog = engine.twr.parse_gui_catalog(engine.twr.DEFAULT_PATCHER_SRC, db)
    controls = [
        item["var"]
        for item in catalog
        if item["tab_title"] == "New Game Status"
    ]
    if len(controls) != 74 or len(set(controls)) != 74:
        raise AssertionError(f"New Game catalog changed: {len(controls)} controls")
    return controls


def foundation_source() -> tuple[bytes, bytes, bytes]:
    text = (
        engine.twr.DEFAULT_PATCHER_SRC / "data" / "_dat.ahk"
    ).read_text(encoding="utf-8-sig")
    result = []
    for index, (raw, wanted_hash) in enumerate(
        zip(FOUNDATION_RAWS, FOUNDATION_HASHES), 1
    ):
        payload = bytes.fromhex(
            re.search(
                rf"(?m)^NewGame_ASM0{index}\s*=\s*([0-9A-F]+)\s*$", text
            ).group(1)
        )
        parsed_raw = int(
            re.search(
                rf"(?m)^NewGame_ASM0{index}_Offset\s*=\s*([0-9A-F]+)\s*$",
                text,
            ).group(1),
            16,
        )
        if parsed_raw != raw or sha256(payload) != wanted_hash:
            raise AssertionError(f"NewGame ASM0{index} source identity changed")
        result.append(payload)
    if tuple(map(len, result)) != (8, 180, 16):
        raise AssertionError("New Game foundation sizes changed")
    return tuple(result)


def source_selection(feature: Feature, value=1) -> dict[str, str]:
    engine_control = feature.source_control.replace(
        "SubTankAdd", "SubtankAdd"
    )
    return {
        engine_control: str(
            value if feature.kind in {"integer", "rank"} else 1
        )
    }


def compose_template(selection: dict[str, object], base: bytes) -> bytes:
    template = bytearray(base)
    masks: dict[int, int] = {}
    for feature_id in sorted(selection):
        feature = FEATURE_BY_ID[feature_id]
        value = selection[feature_id]
        if feature.kind == "integer":
            if not feature.minimum <= value <= feature.maximum:
                raise AssertionError(f"{feature_id} value is out of range")
            template[feature.field_offset] = (
                feature.addend + feature.multiplier * value
            )
        elif feature.kind == "rank":
            rank, souls = RANK_VALUES[str(value)]
            template[feature.field_offset] = rank
            template[feature.aux_offset : feature.aux_offset + 2] = (
                souls.to_bytes(2, "little")
            )
        else:
            masks[feature.field_offset] = (
                masks.get(feature.field_offset, 0) | feature.bit
            )
    for offset, value in masks.items():
        template[offset] = value
    return bytes(template)


def upstream_final_writes(db, profile: dict, selection: dict[str, str]):
    merged = engine.merged_profile(db, json.dumps(selection))
    patchfile, writes = engine.build_writelist(db, merged, profile)
    owned = {}
    for data, raw in writes:
        if raw in FOUNDATION_RAWS or (
            FOUNDATION_RAWS[1] <= raw < FOUNDATION_RAWS[1] + 180
        ):
            owned[raw] = bytes.fromhex(data)
    if patchfile != "b01":
        raise AssertionError("New Game selection unexpectedly left B01")
    return writes, owned


def apply_owned_writes(
    foundation: tuple[bytes, bytes, bytes],
    writes: list[tuple[str, int]],
) -> tuple[bytes, bytes, bytes]:
    first, middle, third = map(bytearray, foundation)
    buffers = [
        (FOUNDATION_RAWS[0], first),
        (FOUNDATION_RAWS[1], middle),
        (FOUNDATION_RAWS[2], third),
    ]
    for data_hex, raw in writes:
        data = bytes.fromhex(data_hex)
        for begin, buffer in buffers:
            if begin <= raw and raw + len(data) <= begin + len(buffer):
                buffer[raw - begin : raw - begin + len(data)] = data
                break
    return bytes(first), bytes(middle), bytes(third)


def validate_source_parity(db, profile: dict, foundation):
    feature_evidence = []
    for feature in FEATURES:
        values = (
            (feature.minimum, (feature.minimum + feature.maximum) // 2,
             feature.maximum)
            if feature.kind == "integer"
            else tuple(RANK_VALUES) if feature.kind == "rank" else (1,)
        )
        cases = []
        for value in dict.fromkeys(values):
            selection = source_selection(feature, value)
            merged = engine.merged_profile(db, json.dumps(selection))
            _norm, _pf, patch_list, _values, synth = engine._assemble(
                db, merged, profile
            )
            inherited = set(db.patchlist_base) | set(db.patchlist_script)
            owned = [item for item in patch_list if item not in inherited]
            expected_owned = (
                ["NewGame", feature.source_control]
                if feature.kind == "integer"
                else [
                    "NewGame",
                    feature.source_control,
                    "Souls01"
                    if feature.source_control == "CharRank01"
                    else "Souls02",
                ]
                if feature.kind == "rank"
                else [
                    "NewGame",
                    "HeartTankAdd"
                    if feature.field_offset == 0x88
                    else "SubtankAdd",
                ]
            )
            if owned != expected_owned or synth:
                raise AssertionError(
                    f"{feature.source_control} closure changed: {owned}, {synth}"
                )
            writes, _ = upstream_final_writes(db, profile, selection)
            final = apply_owned_writes(foundation, writes)
            composed = compose_template({feature.feature_id: value}, foundation[1])
            if final != (foundation[0], composed, foundation[2]):
                raise AssertionError(
                    f"{feature.source_control}={value} composer parity failed"
                )
            cases.append(
                {
                    "value": value,
                    "source_closure": owned,
                    "composed_middle_sha256": sha256(composed),
                }
            )
        feature_evidence.append(
            {
                "feature_id": feature.feature_id,
                "source_control": feature.source_control,
                "cases": cases,
            }
        )
    return feature_evidence


def validate_combinations(db, profile: dict, foundation):
    cases = {
        "minimum": {
            item.feature_id: (
                item.minimum
                if item.kind == "integer"
                else "C"
                if item.kind == "rank"
                else 1
            )
            for item in FEATURES
        },
        "maximum": {
            item.feature_id: (
                item.maximum
                if item.kind == "integer"
                else "UH"
                if item.kind == "rank"
                else 1
            )
            for item in FEATURES
        },
    }
    result = []
    for label, values in cases.items():
        source = {}
        for feature_id, value in values.items():
            source.update(source_selection(FEATURE_BY_ID[feature_id], value))
        writes, _ = upstream_final_writes(db, profile, source)
        final = apply_owned_writes(foundation, writes)
        composed = compose_template(values, foundation[1])
        reverse = compose_template(
            dict(reversed(list(values.items()))), foundation[1]
        )
        if final != (foundation[0], composed, foundation[2]):
            raise AssertionError(f"{label} combination parity failed")
        if reverse != composed:
            raise AssertionError(f"{label} composition is order-dependent")
        result.append(
            {
                "label": label,
                "enabled_features": len(values),
                "middle_sha256": sha256(composed),
                "upstream_parity": True,
                "order_independent": True,
            }
        )
    return result


def build_report(stock_path: Path) -> dict:
    if file_sha256(stock_path) != native.STOCK_SHA256:
        raise AssertionError("stock disc SHA-256 does not match USA v1.1")
    db = engine.twr.TweaksDB(engine.twr.DEFAULT_PATCHER_SRC)
    profile = engine.twr.load_profile(engine.twr.DEFAULT_PROFILE)
    patchfile, patch_list, synth = engine.build_patchlist(db, profile, profile)
    if patchfile or patch_list or synth:
        raise AssertionError("disabled/default profile emits writes")
    controls = source_catalog(db)
    foundation = foundation_source()
    stock_guards = []
    with native.RawMode2Image(stock_path) as stock_image:
        load_address = struct.unpack(
            "<I", stock_image.read_file(native.SLUS_NAME)[0x18:0x1C]
        )[0]
        for raw, payload in zip(FOUNDATION_RAWS, foundation):
            user_offset = native.raw_to_user_offset(raw)
            entry, file_offset = stock_image.containing_file(
                user_offset, len(payload)
            )
            if entry.name != native.SLUS_NAME:
                raise AssertionError("New Game foundation left main executable")
            expected = stock_image.read_user(user_offset, len(payload))
            stock_guards.append(
                {
                    "guest_address": load_address + file_offset - 2048,
                    "expected": expected.hex().upper(),
                    "expected_sha256": sha256(expected),
                }
            )
    evidence = validate_source_parity(db, profile, foundation)
    combinations = validate_combinations(db, profile, foundation)
    converted = {item.source_control for item in FEATURES}
    ledger = [
        {
            "source_control": control,
            "status": "converted" if control in converted else "deferred",
            "reason": (
                "exact shared-foundation field composition implemented"
                if control in converted
                else "field semantics or coupled New Game/RescRep composition "
                "not yet proven by this tranche"
            ),
        }
        for control in controls
    ]
    return {
        "package": {
            "id": PACKAGE_ID,
            "version": PACKAGE_VERSION,
            "resolver": f"builtin:{RESOLVER_ID}",
            "feature_count": len(FEATURES),
            "source_control_count": len(converted),
            "catalog_control_count": len(controls),
            "deferred_control_count": len(controls) - len(converted),
        },
        "provenance": {
            "stock_sha256": native.STOCK_SHA256,
            "patcher_version": "MMX6 Tweaks v2.6.1",
            "patcher_dat_sha256": file_sha256(
                engine.twr.DEFAULT_PATCHER_SRC / "data" / "_dat.ahk"
            ),
            "default_profile_sha256": file_sha256(engine.twr.DEFAULT_PROFILE),
            "converter_source_sha256": file_sha256(
                Path(__file__.replace("\\", "/")).absolute()
            ),
            "trusted_resolver_source_sha256": file_sha256(
                TOOLS.parent
                / "src"
                / "mods"
                / "mmx6_new_game_resolver.cpp"
            ),
        },
        "foundation": [
            {
                "source_raw_offset": raw,
                "size": len(payload),
                "replacement_sha256": sha256(payload),
                **guard,
            }
            for raw, payload, guard in zip(
                FOUNDATION_RAWS, foundation, stock_guards
            )
        ],
        "features": evidence,
        "source_controls": sorted(converted),
        "source_control_ledger": ledger,
        "validation": {
            "disabled_selection_emits_no_writes": True,
            "isolated_source_parity": True,
            "stock_guards_verified": True,
            "foundation_emitted_once_per_resolution": True,
            "representative_combinations": combinations,
        },
    }


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_manifest(version: str) -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(version)}",
        'name = "Mega Man X6 Tweaks — New Game Status"',
        'author = "acediez and MMX6 Tweaks contributors; PSXRecomp integration"',
        'description = "Independent starting-status features composed by a trusted game resolver."',
        'license = "Generated locally; original credits retained"',
        f'resolver = "builtin:{RESOLVER_ID}"',
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
            f"id = {q(feature.feature_id)}",
            f"name = {q(feature.name)}",
            (
                f"description = {q('Apply this starting status without changing '
                'other New Game features.')}"
            ),
            'group = "New Game Status"',
            "default_enabled = false",
        ]
        if feature.kind == "integer":
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "count"',
                'label = "Count"',
                'description = "Starting upgrade count while enabled."',
                'group = "New Game Status"',
                'type = "integer"',
                f"min = {feature.minimum}",
                f"max = {feature.maximum}",
                "step = 1",
                f"default = {feature.minimum}",
            ]
        elif feature.kind == "rank":
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "rank"',
                'label = "Rank"',
                'description = "Starting Hunter Rank and matching Soul count."',
                'group = "New Game Status"',
                'type = "choice"',
                'default = "C"',
            ]
            for value in RANK_VALUES:
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(value)}",
                    f"label = {q(value)}",
                ]
    return "\n".join(lines) + "\n"


def archive_member(archive, name: str, payload: str):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload.encode("utf-8"))


def write_package(path: Path, report: dict, version: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        archive_member(archive, "manifest.toml", build_manifest(version))
        archive_member(
            archive,
            "conversion-report.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n",
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
        if manifest["id"] != PACKAGE_ID or len(manifest["feature"]) != len(FEATURES):
            raise AssertionError("generated manifest shape changed")
        if "patch" in manifest or "overlay" in manifest:
            raise AssertionError("resolver package contains declarative writes")
        return len(archive.namelist())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=native.DEFAULT_STOCK)
    parser.add_argument("--out", type=Path, default=Path("build-local")
                        / "MMX6-Tweaks-New-Game.psxmod")
    parser.add_argument("--report-out", type=Path)
    parser.add_argument("--package-version", default=PACKAGE_VERSION)
    args = parser.parse_args()
    report = build_report(args.stock)
    report["package"]["version"] = args.package_version
    write_package(args.out, report, args.package_version)
    first = args.out.read_bytes()
    with tempfile.TemporaryDirectory(prefix="mmx6-new-game-") as temp:
        repeat = Path(temp) / "repeat.psxmod"
        write_package(repeat, report, args.package_version)
        if repeat.read_bytes() != first:
            raise AssertionError("package rebuild is not deterministic")
    members = inspect_package(args.out)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "output": str(args.out),
        "sha256": sha256(first),
        "archive_members": members,
        "features": len(FEATURES),
        "converted_source_controls": len(FEATURES),
        "deferred_source_controls": 74 - len(FEATURES),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
