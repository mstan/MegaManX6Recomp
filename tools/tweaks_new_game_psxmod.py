#!/usr/bin/env python3
"""Build the reviewed resolver-backed MMX6 Tweaks New Game package."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
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
PACKAGE_VERSION = "1.4.0"
RESOLVER_ID = "mmx6-new-game"
FOUNDATION_RAWS = (0x1D930B9C, 0x1D9965F8, 0x1D99A630)
INTRO_ARMOR_RAW = 0x1D930B4C
INTRO_ARMOR_SIZE = 40
INTRO_ARMOR_HOOK = bytes.fromhex(
    "010002245F00A2A05E00A2A03031478D040003340400E314303144250800"
    "42245F00A2A05E00A3A0"
)
FOUND_TABLE_RAW = 0x1D9965B8
FOUND_TABLE_SIZE = 64
PARTS_TABLE_RAW = 0x1D98BBFC
PARTS_TABLE_SIZE = 512
PARTS_TABLE_WRITE_SIZE = PARTS_TABLE_SIZE
NO_ITEM_FOUND_TABLE = bytes.fromhex(
    "2020202202222220222000222220022202222222022200202222022222000220"
    "2222202020222002222222200202022020222220222002202202222002202022"
)
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
    table_offset: int = -1
    table_bit: int = 0


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
    Feature("available_shadow_armor", "Shadow Armor Available", "CharAdd02",
            "bit", 0x34, bit=0x02),
    Feature("available_blade_armor", "Blade Armor Available", "CharAdd03",
            "bit", 0x34, bit=0x04),
    Feature("available_ultimate_armor", "Ultimate Armor Available", "CharAdd04",
            "bit", 0x34, bit=0x08),
    Feature("available_zero", "Zero Available", "CharAdd05",
            "bit", 0x34, bit=0x10),
    Feature("available_black_zero", "Black Zero Available", "CharAdd06",
            "bit", 0x34, bit=0x20),
    Feature("intro_stage_armor", "Intro Stage Starting Armor", "CharStart01",
            "choice", 0x34, aux_offset=0x4C),
    *tuple(
        Feature(
            f"parts_life_up_{index}",
            f"Start with Life Up Part {index}",
            f"PartsLifeUp{index:02d}",
            "bit",
            0x90,
            bit=1 << (index - 1),
            table_offset=offset,
            table_bit=bit,
        )
        for index, (offset, bit) in enumerate((
            (0x00, 0x02), (0x0D, 0x02), (0x14, 0x20), (0x1E, 0x20),
            (0x22, 0x02), (0x2C, 0x20), (0x30, 0x02), (0x3C, 0x20),
        ), 1)
    ),
    *tuple(
        Feature(
            f"parts_energy_up_{index}",
            f"Start with Energy Up Part {index}",
            f"PartsEnergyUp{index:02d}",
            "bit",
            0xA0,
            bit=1 << (index - 1),
            table_offset=offset,
            table_bit=bit,
        )
        for index, (offset, bit) in enumerate((
            (0x01, 0x02), (0x0A, 0x02), (0x16, 0x02), (0x1A, 0x20),
            (0x26, 0x02), (0x2B, 0x02), (0x33, 0x02), (0x3E, 0x02),
        ), 1)
    ),
    *tuple(
        Feature(feature_id, name, source, "bit", offset, bit=bit,
                table_offset=table_offset, table_bit=table_bit)
        for (
            feature_id, name, source, offset, bit, table_offset, table_bit
        ) in (
            ("part_hyper_dash", "Start with Hyper Dash", "PartsSet0101",
             0x80, 0x10, 0x2E, 0x20),
            ("part_energy_saver", "Start with Energy Saver", "PartsSet0102",
             0x80, 0x20, 0x35, 0x02),
            ("part_super_recover", "Start with Super Recover", "PartsSet0103",
             0x80, 0x40, 0x04, 0x20),
            ("part_buster_plus", "Start with Buster Plus", "PartsSet0104",
             0x80, 0x80, 0x10, 0x20),
            ("part_speedster", "Start with Speedster", "PartsSet0203",
             0x80, 0x04, 0x23, 0x02),
            ("part_jumper", "Start with Jumper", "PartsSet0204",
             0x80, 0x08, 0x0E, 0x20),
            ("part_hyperdrive", "Start with Hyperdrive", "PartsSet0301",
             0x81, 0x10, 0x1D, 0x20),
            ("part_power_drive", "Start with Power Drive", "PartsSet0302",
             0x81, 0x20, 0x16, 0x20),
            ("part_weapon_driver", "Start with Weapon Driver", "PartsSet0303",
             0x81, 0x40, 0x0A, 0x20),
            ("part_life_recover", "Start with Life Recover", "PartsSet0304",
             0x81, 0x80, 0x02, 0x02),
            ("part_speed_shot", "Start with Speed Shot", "PartsSet0401",
             0x81, 0x01, 0x3B, 0x02),
            ("part_shock_buffer", "Start with Shock Buffer", "PartsSet0402",
             0x81, 0x02, 0x1D, 0x02),
            ("part_d_barrier", "Start with D-Barrier", "PartsSet0403",
             0x81, 0x04, 0x36, 0x20),
            ("part_d_converter", "Start with D-Converter", "PartsSet0404",
             0x81, 0x08, 0x39, 0x20),
            ("part_quick_charge", "Start with Quick Charge", "PartsSet0501",
             0x7C, 0x10, 0x24, 0x02),
            ("part_weapon_plus", "Start with Weapon Plus", "PartsSet0502",
             0x7C, 0x20, 0x37, 0x02),
            ("part_saber_plus", "Start with Saber Plus", "PartsSet0503",
             0x7C, 0x40, 0x2F, 0x02),
            ("part_saber_extend", "Start with Saber Extend", "PartsSet0504",
             0x7C, 0x80, 0x1F, 0x02),
            ("part_weapon_recover", "Start with Weapon Recover", "PartsSet0601",
             0x7C, 0x01, 0x2D, 0x20),
            ("part_over_drive", "Start with Over Drive", "PartsSet0602",
             0x7C, 0x02, 0x27, 0x20),
            ("part_rapid_5", "Start with Rapid 5", "PartsSet0603",
             0x7C, 0x04, 0x07, 0x02),
            ("part_ultimate_buster", "Start with Ultimate Buster",
             "PartsSet0604", 0x7C, 0x08, 0x17, 0x02),
            ("part_shot_eraser", "Start with Shot Eraser", "PartsSet0701",
             0x7D, 0x01, 0x09, 0x02),
            ("part_master_saber", "Start with Master Saber", "PartsSet0702",
             0x7D, 0x02, 0x3D, 0x02),
        )
    ),
    Feature(
        "mark_no_item_reploids",
        "Mark No-Item Reploids as Rescued",
        "RescRepFoundNoItem01",
        "table",
        -1,
    ),
    Feature(
        "found_reploid_mark_status",
        "Found Reploid Mark Status",
        "RescRepFoundMark01",
        "mark_status",
        -1,
    ),
    Feature(
        "mark_reploids_only",
        "Mark Reploids Only",
        "RescRepFoundMarkOnly01",
        "mark_only",
        -1,
    ),
    Feature(
        "randomize_reploid_parts",
        "Randomize Reploid Parts",
        "PartsRandomTitle01",
        "parts_randomizer",
        -1,
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
CHAR_START_VALUES = {
    "none": ("None", "No Armor", 0x00, 0x01, 0x00),
    "blade": ("Blade Armor", "Blade Armor", 0x03, 0x05, 0x0F),
    "shadow": ("Shadow Armor", "Shadow Armor", 0x02, 0x03, 0xF0),
    "ultimate": ("Ultimate Armor", "Ultimate Armor", 0x04, 0x09, 0x00),
}
FOUND_MARK_VALUES = {
    "dead": ("DEAD", "Dead", 0x03),
    "missing": ("MISSING", "Missing", 0x04),
}
PARTS_RANDOM_VALUES = {
    "only_parts": (
        "PartsRandom01",
        "Between Reploids already carrying Parts",
    ),
    "all_reploids": (
        "PartsRandom02",
        "Between all Reploids",
    ),
}
PARTS_RANDOM_SOURCE_CONTROLS = (
    "PartsRandomTitle01", "PartsRandom01", "PartsRandom02",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _source_db():
    return engine.twr.TweaksDB(engine.twr.DEFAULT_PATCHER_SRC)


def _table_entries(name: str) -> tuple[str, ...]:
    entries = tuple(
        item.strip()
        for item in _source_db().dat[name].splitlines()
        if item.strip()
    )
    if any(len(item) != 8 for item in entries):
        raise AssertionError(f"{name} contains a non-u32 table entry")
    return entries


def parts_table_original() -> tuple[str, ...]:
    entries = _table_entries("RescRepPartsTable_Original")
    if len(entries) != 128:
        raise AssertionError("RescRepPartsTable_Original changed size")
    return entries


def parts_table_only_parts() -> tuple[str, ...]:
    entries = _table_entries("RescRepPartsTable_OnlyParts")
    if len(entries) != 40:
        raise AssertionError("RescRepPartsTable_OnlyParts changed size")
    return entries


def parts_table_no_part_indices() -> set[int]:
    result = {
        int(item)
        for item in _source_db().dat["RescRepParts_NoPartsIndex"].split(",")
        if item.strip()
    }
    if len(result) != 88:
        raise AssertionError("RescRepParts_NoPartsIndex changed size")
    return result


def random_parts_table(mode: str) -> tuple[str, ...]:
    if mode not in PARTS_RANDOM_VALUES:
        raise AssertionError(f"unsupported randomizer mode: {mode}")
    rng = random.Random(engine.DEFAULT_PARTS_SEED)
    if mode == "all_reploids":
        table = list(parts_table_original())
        rng.shuffle(table)
        return tuple(table)
    shuffled = list(parts_table_only_parts())
    rng.shuffle(shuffled)
    no_part_indices = parts_table_no_part_indices()
    iterator = iter(shuffled)
    return tuple(
        "00000000" if index in no_part_indices else next(iterator)
        for index in range(1, 129)
    )


def parts_table_bytes(table: tuple[str, ...]) -> bytes:
    if len(table) != 128 or any(len(item) != 8 for item in table):
        raise AssertionError("invalid Reploid parts table shape")
    return bytes.fromhex("".join(table))


def parts_table_final_image(virtual_table: tuple[str, ...], active: bool) -> bytes:
    original = bytearray(parts_table_bytes(parts_table_original()))
    if active:
        original[:PARTS_TABLE_WRITE_SIZE] = parts_table_bytes(
            virtual_table
        )[:PARTS_TABLE_WRITE_SIZE]
    return bytes(original)


def selected_random_mode(selection: dict[str, object]) -> str | None:
    value = selection.get("randomize_reploid_parts")
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("mode", "only_parts")
    mode = str(value)
    if mode not in PARTS_RANDOM_VALUES:
        raise AssertionError(f"unsupported randomizer mode: {mode}")
    return mode


def carrier_table_for_selection(selection: dict[str, object]) -> tuple[str, ...]:
    mode = selected_random_mode(selection)
    return parts_table_original() if mode is None else random_parts_table(mode)


def part_code_by_feature() -> dict[str, str]:
    db = _source_db()
    return {
        feature.feature_id: db.dat[feature.source_control + "_Code"].strip()
        for feature in FEATURES
        if (
            feature.source_control.startswith("PartsSet")
            and feature.source_control + "_Code" in db.dat
        )
    }


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
    if feature.kind == "choice":
        source_value = CHAR_START_VALUES[str(value)][0]
    elif feature.kind == "mark_status":
        source_value = FOUND_MARK_VALUES[str(value)][0]
    elif feature.kind == "parts_randomizer":
        mode = str(value)
        source_control = PARTS_RANDOM_VALUES[mode][0]
        return {
            "PartsRandomTitle01": "1",
            "PartsRandom01": "1" if source_control == "PartsRandom01" else "0",
            "PartsRandom02": "1" if source_control == "PartsRandom02" else "0",
        }
    else:
        source_value = (
            value
            if feature.kind in {"integer", "rank"}
            else 1
        )
    return {
        engine_control: str(source_value)
    }


def compose_full_state(
    selection: dict[str, object], base: bytes
) -> tuple[bytes, bytes, bytes, bool]:
    template = bytearray(base)
    found_table = bytearray(FOUND_TABLE_SIZE)
    masks: dict[int, int] = {}
    mark = 0x02
    if "found_reploid_mark_status" in selection:
        mark = FOUND_MARK_VALUES[str(selection["found_reploid_mark_status"])][2]
    mark_only = bool(selection.get("mark_reploids_only"))

    def marked_table_bit(table_bit: int) -> int:
        if table_bit == 0x02:
            return mark
        if table_bit == 0x20:
            return mark << 4
        raise AssertionError(f"unexpected found-table mark bit 0x{table_bit:02X}")

    def remark_table(table: bytes) -> bytes:
        result = bytearray(table)
        for index, value in enumerate(result):
            low = mark if (value & 0x02) else 0
            high = (mark << 4) if (value & 0x20) else 0
            result[index] = low | high
        return bytes(result)

    def found_table_from_carrier(table: tuple[str, ...]) -> tuple[bytes, bool]:
        selected_codes = {
            code
            for feature_id, code in part_code_by_feature().items()
            if feature_id in selection
        }
        selected_life = {
            int(feature_id.rsplit("_", 1)[1])
            for feature_id in selection
            if feature_id.startswith("parts_life_up_")
        }
        selected_energy = {
            int(feature_id.rsplit("_", 1)[1])
            for feature_id in selection
            if feature_id.startswith("parts_energy_up_")
        }
        no_item = "mark_no_item_reploids" in selection
        active = bool(selected_codes or selected_life or selected_energy or no_item)
        if not active:
            return bytes(FOUND_TABLE_SIZE), False
        nibbles: list[int] = []
        life_index = 0
        energy_index = 0
        for entry in table:
            if entry in selected_codes:
                nibbles.append(mark)
            elif entry == "00000000" and no_item:
                nibbles.append(mark)
            elif entry == "01000000":
                life_index += 1
                nibbles.append(mark if life_index in selected_life else 0)
            elif entry == "02000000":
                energy_index += 1
                nibbles.append(mark if energy_index in selected_energy else 0)
            else:
                nibbles.append(0)
        if len(nibbles) != 128:
            raise AssertionError("invalid found-table nibble count")
        return bytes(
            (nibbles[index + 1] << 4) | nibbles[index]
            for index in range(0, len(nibbles), 2)
        ), True

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
        elif feature.kind == "choice":
            _source_value, _label, _char, availability, armor_parts = (
                CHAR_START_VALUES[str(value)]
            )
            template[feature.field_offset] |= availability
            if armor_parts:
                template[feature.aux_offset] |= armor_parts
        elif feature.kind == "table":
            for offset, value in enumerate(remark_table(NO_ITEM_FOUND_TABLE)):
                found_table[offset] |= value
        elif feature.kind in {"mark_status", "mark_only", "parts_randomizer"}:
            pass
        else:
            if not (
                mark_only and
                feature.source_control.startswith("PartsSet")
            ):
                masks[feature.field_offset] = (
                    masks.get(feature.field_offset, 0) | feature.bit
                )
            if feature.source_control.startswith("CharAdd"):
                masks[feature.field_offset] |= 0x01
            if feature.table_offset >= 0:
                found_table[feature.table_offset] |= marked_table_bit(
                    feature.table_bit
                )
    for offset, value in masks.items():
        template[offset] |= value
    if "intro_stage_armor" in selection:
        if "available_shadow_armor" in selection:
            template[0x4C] |= 0xF0
        if "available_blade_armor" in selection:
            template[0x4C] |= 0x0F
    parts_table = carrier_table_for_selection(selection)
    parts_table_active = selected_random_mode(selection) is not None
    if parts_table_active:
        found_table_bytes, _active = found_table_from_carrier(parts_table)
        found_table = bytearray(found_table_bytes)
    return (
        bytes(template),
        bytes(found_table),
        parts_table_final_image(parts_table, parts_table_active),
        parts_table_active,
    )


def compose_state(
    selection: dict[str, object], base: bytes
) -> tuple[bytes, bytes]:
    template, found_table, _parts_table, _parts_active = compose_full_state(
        selection, base
    )
    return template, found_table


def compose_template(selection: dict[str, object], base: bytes) -> bytes:
    return compose_state(selection, base)[0]


def upstream_final_writes(db, profile: dict, selection: dict[str, str]):
    merged = engine.merged_profile(db, json.dumps(selection))
    patchfile, writes = engine.build_writelist(db, merged, profile)
    owned = {}
    for data, raw in writes:
        if raw in {FOUND_TABLE_RAW, PARTS_TABLE_RAW} or raw in FOUNDATION_RAWS or (
            FOUNDATION_RAWS[1] <= raw < FOUNDATION_RAWS[1] + 180
        ):
            owned[raw] = bytes.fromhex(data)
    if patchfile != "b01":
        raise AssertionError("New Game selection unexpectedly left B01")
    return writes, owned


def apply_owned_writes(
    foundation: tuple[bytes, bytes, bytes],
    writes: list[tuple[str, int]],
) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    first, middle, third = map(bytearray, foundation)
    found_table = bytearray(FOUND_TABLE_SIZE)
    parts_table = bytearray(parts_table_bytes(parts_table_original()))
    buffers = [
        (FOUNDATION_RAWS[0], first),
        (FOUNDATION_RAWS[1], middle),
        (FOUNDATION_RAWS[2], third),
        (FOUND_TABLE_RAW, found_table),
        (PARTS_TABLE_RAW, parts_table),
    ]
    for data_hex, raw in writes:
        data = bytes.fromhex(data_hex)
        for begin, buffer in buffers:
            if begin <= raw and raw + len(data) <= begin + len(buffer):
                buffer[raw - begin : raw - begin + len(data)] = data
                break
    return (
        bytes(first), bytes(middle), bytes(third),
        bytes(found_table), bytes(parts_table),
    )


def validate_source_parity(db, profile: dict, foundation):
    feature_evidence = []
    for feature in FEATURES:
        if feature.kind == "integer":
            values = (
                feature.minimum,
                (feature.minimum + feature.maximum) // 2,
                feature.maximum,
            )
        elif feature.kind == "rank":
            values = tuple(RANK_VALUES)
        elif feature.kind == "choice":
            values = tuple(CHAR_START_VALUES)
        elif feature.kind == "mark_status":
            values = tuple(FOUND_MARK_VALUES)
        elif feature.kind == "parts_randomizer":
            values = tuple(PARTS_RANDOM_VALUES)
        else:
            values = (1,)
        cases = []
        for value in dict.fromkeys(values):
            selection = source_selection(feature, value)
            composer_selection = {feature.feature_id: value}
            if feature.kind in {"mark_status", "mark_only"}:
                selection = {"PartsSet0101": "1", **selection}
                composer_selection = {
                    "part_hyper_dash": 1,
                    feature.feature_id: value,
                }
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
                    feature.source_control,
                    "RescRepFoundTable",
                ]
                if feature.kind == "table"
                else [
                    "NewGame",
                    "CharStart01",
                    "CharAdd",
                    "ArmorParts",
                ]
                if feature.kind == "choice"
                else [
                    "NewGame",
                    "RescRepFoundMark01",
                    "PartsSet01",
                    "PartsSetA",
                    "PartsSetB",
                    "RescRepFoundTable",
                ]
                if feature.kind == "mark_status"
                else [
                    "NewGame",
                    "RescRepFoundMarkOnly01",
                    "PartsSet01",
                    "RescRepFoundTable",
                ]
                if feature.kind == "mark_only"
                else [
                    "NewGame",
                    "PartsRandomTitle01",
                    PARTS_RANDOM_VALUES[str(value)][0],
                    "RescRepPartsTable",
                ]
                if feature.kind == "parts_randomizer"
                else [
                    "NewGame",
                    "HeartTankAdd"
                    if feature.field_offset == 0x88
                    else "SubtankAdd"
                    if feature.field_offset == 0x50
                    else "CharAdd"
                    if feature.source_control.startswith("CharAdd")
                    else "PartsLifeUp"
                    if feature.source_control.startswith("PartsLifeUp")
                    else "PartsEnergyUp"
                    if feature.source_control.startswith("PartsEnergyUp")
                    else feature.source_control[:10],
                ]
            )
            if feature.kind == "table":
                expected_synth = {"RescRepFoundTable"}
            elif feature.kind == "choice":
                expected_synth = {"ArmorParts"}
            elif feature.kind == "mark_status":
                expected_synth = {
                    "PartsSetA", "PartsSetB", "RescRepFoundTable"
                }
            elif feature.kind == "mark_only":
                expected_synth = {"RescRepFoundTable"}
            elif feature.kind == "parts_randomizer":
                expected_synth = {"RescRepPartsTable"}
            elif feature.table_offset >= 0:
                if feature.source_control.startswith("PartsSet"):
                    expected_owned += [
                        "PartsSetA", "PartsSetB", "RescRepFoundTable"
                    ]
                    expected_synth = {
                        "PartsSetA", "PartsSetB", "RescRepFoundTable"
                    }
                else:
                    expected_owned += ["RescRepFoundTable"]
                    expected_synth = {"RescRepFoundTable"}
            else:
                expected_synth = set()
            if owned != expected_owned or set(synth) != expected_synth:
                raise AssertionError(
                    f"{feature.source_control} closure changed: {owned}, {synth}"
                )
            writes, _ = upstream_final_writes(db, profile, selection)
            final = apply_owned_writes(foundation, writes)
            composed, found_table, parts_table, _parts_table_active = compose_full_state(
                composer_selection, foundation[1]
            )
            if final != (
                foundation[0], composed, foundation[2], found_table, parts_table
            ):
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
                else "none"
                if item.kind == "choice"
                else "dead"
                if item.kind == "mark_status"
                else "only_parts"
                if item.kind == "parts_randomizer"
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
                else "ultimate"
                if item.kind == "choice"
                else "missing"
                if item.kind == "mark_status"
                else "all_reploids"
                if item.kind == "parts_randomizer"
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
        composed = compose_state(values, foundation[1])
        full = compose_full_state(values, foundation[1])
        reverse = compose_state(
            dict(reversed(list(values.items()))), foundation[1]
        )
        if final != (
            foundation[0], full[0], foundation[2], full[1], full[2]
        ):
            raise AssertionError(f"{label} combination parity failed")
        if reverse != composed:
            raise AssertionError(f"{label} composition is order-dependent")
        result.append(
            {
                "label": label,
                "enabled_features": len(values),
                "middle_sha256": sha256(composed[0]),
                "found_table_sha256": sha256(composed[1]),
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
        table_user_offset = native.raw_to_user_offset(FOUND_TABLE_RAW)
        table_entry, table_file_offset = stock_image.containing_file(
            table_user_offset, FOUND_TABLE_SIZE
        )
        if table_entry.name != native.SLUS_NAME:
            raise AssertionError("found-Reploid table left main executable")
        table_expected = stock_image.read_user(
            table_user_offset, FOUND_TABLE_SIZE
        )
        if table_expected != bytes(FOUND_TABLE_SIZE):
            raise AssertionError("found-Reploid stock table changed")
        table_guard = {
            "source_raw_offset": FOUND_TABLE_RAW,
            "guest_address": load_address + table_file_offset - 2048,
            "size": FOUND_TABLE_SIZE,
            "expected": table_expected.hex().upper(),
            "expected_sha256": sha256(table_expected),
        }
        parts_user_offset = native.raw_to_user_offset(PARTS_TABLE_RAW)
        parts_entry, parts_file_offset = stock_image.containing_file(
            parts_user_offset, PARTS_TABLE_WRITE_SIZE
        )
        if parts_entry.name != native.SLUS_NAME:
            raise AssertionError("Reploid parts table left main executable")
        parts_expected = stock_image.read_user(
            parts_user_offset, PARTS_TABLE_WRITE_SIZE
        )
        expected_original = parts_table_bytes(parts_table_original())
        if parts_expected != expected_original[:PARTS_TABLE_WRITE_SIZE]:
            raise AssertionError("stock Reploid parts table changed")
        parts_guard = {
            "source_raw_offset": PARTS_TABLE_RAW,
            "guest_address": load_address + parts_file_offset - 2048,
            "size": PARTS_TABLE_WRITE_SIZE,
            "expected": parts_expected.hex().upper(),
            "expected_sha256": sha256(parts_expected),
            "default_seed": engine.DEFAULT_PARTS_SEED,
            "only_parts_sha256": sha256(
                parts_table_bytes(random_parts_table("only_parts"))[
                    :PARTS_TABLE_WRITE_SIZE
                ]
            ),
            "all_reploids_sha256": sha256(
                parts_table_bytes(random_parts_table("all_reploids"))[
                    :PARTS_TABLE_WRITE_SIZE
                ]
            ),
        }
    evidence = validate_source_parity(db, profile, foundation)
    combinations = validate_combinations(db, profile, foundation)
    converted = {item.source_control for item in FEATURES}
    converted.update(PARTS_RANDOM_SOURCE_CONTROLS)
    excluded = {
        "CharAdd01": (
            "Falcon Armor availability is already the stock New Game state; "
            "selecting the Tweaks control alone emits no patchfile, owned "
            "writes, or synthesized payload."
        ),
        "DebugCheckpointStart": (
            "Hidden debug-start control emits no patchfile, owned writes, or "
            "synthesized payload through the normal submitted profile path."
        ),
        "DebugStageStart": (
            "Hidden debug-start control emits no patchfile, owned writes, or "
            "synthesized payload through the normal submitted profile path."
        ),
        "ZeroDebug": (
            "Hidden Zero debug-start control emits no patchfile, owned writes, "
            "or synthesized payload through the normal submitted profile path."
        ),
    }
    def deferred_reason(control: str) -> str:
        return "source closure is not fully proven by this tranche"

    ledger = [
        {
            "source_control": control,
            "status": (
                "converted" if control in converted
                else "excluded" if control in excluded
                else "deferred"
            ),
            "reason": (
                "exact shared composer field/table composition implemented"
                if control in converted
                else excluded[control]
                if control in excluded
                else deferred_reason(control)
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
            "excluded_control_count": len(excluded),
            "deferred_control_count": (
                len(controls) - len(converted) - len(excluded)
            ),
        },
        "excluded_source_controls": [
            {"source_control": control, "reason": reason}
            for control, reason in sorted(excluded.items())
        ],
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
        "composed_resources": {
            "found_reploid_table": table_guard,
            "reploid_parts_table": parts_guard,
        },
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
        elif feature.kind == "choice":
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "armor"',
                'label = "Armor"',
                'description = "Intro Stage starting armor while enabled."',
                'group = "New Game Status"',
                'type = "choice"',
                'default = "none"',
            ]
            for value, (_source, label, _char, _availability, _armor_parts) in (
                CHAR_START_VALUES.items()
            ):
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(value)}",
                    f"label = {q(label)}",
                ]
        elif feature.kind == "mark_status":
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "status"',
                'label = "Status"',
                'description = "Status to apply to matching Reploids."',
                'group = "New Game Status"',
                'type = "choice"',
                'default = "dead"',
            ]
            for value, (_source, label, _mark) in FOUND_MARK_VALUES.items():
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(value)}",
                    f"label = {q(label)}",
                ]
        elif feature.kind == "parts_randomizer":
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "mode"',
                'label = "Mode"',
                (
                    'description = "Which Reploid slots participate in the '
                    'deterministic shuffle."'
                ),
                'group = "New Game Status"',
                'type = "choice"',
                'default = "only_parts"',
            ]
            for value, (_source, label) in PARTS_RANDOM_VALUES.items():
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(value)}",
                    f"label = {q(label)}",
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
        "converted_source_controls": report["package"]["source_control_count"],
        "excluded_source_controls": report["package"]["excluded_control_count"],
        "deferred_source_controls": report["package"]["deferred_control_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
