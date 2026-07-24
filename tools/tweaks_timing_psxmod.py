#!/usr/bin/env python3
"""Build the reviewed MMX6 Tweaks timing/status format-4 package.

This converter is intentionally separate from tweaks_native_psxmod.py. It
admits only bounded controls whose source closure, encoded values, stock
guards, and semantic destinations can be reproduced exactly. Patched images
and whole-disc fallbacks are not runtime inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import tweaks_native_psxmod as native


PACKAGE_ID = "mmx6.tweaks.timing"
PACKAGE_NAME = "Mega Man X6 Timing and Status Tweaks"
PACKAGE_VERSION = "1.1.0"

ROOT = Path(__file__).absolute().parent.parent
DEFAULT_TWEAKS = native.DEFAULT_TWEAKS
DEFAULT_STOCK = native.DEFAULT_STOCK
DEFAULT_B01_BASE = ROOT / "build-mod-platform" / "test-mod-variants" / "base.bin"
DEFAULT_PATCHER_DATA = native.DEFAULT_PATCHER_DATA
DEFAULT_PATCHER_SOURCE = native.DEFAULT_PATCHER_SOURCE
DEFAULT_OUT = (
    ROOT
    / "build-mod-platform"
    / "test-psxmods"
    / "MMX6-Tweaks-Timing.psxmod"
)


@dataclass(frozen=True)
class SourceControl:
    source_id: str
    option_id: str
    label: str
    default: int
    minimum: int
    maximum: int
    raw_offsets: tuple[int, ...]


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    name: str
    description: str
    group: str
    controls: tuple[SourceControl, ...]


@dataclass(frozen=True)
class SparseField:
    offset: int
    option_id: str = ""
    encoding: str = "u8"
    addend: int = 0
    replacement: bytes | None = None

    @property
    def size(self) -> int:
        if self.replacement is not None:
            return len(self.replacement)
        return {"u8": 1, "u16le": 2, "u32le": 4}[self.encoding]


@dataclass(frozen=True)
class IntegerCondition:
    option_id: str
    operation: str
    value: int


@dataclass(frozen=True)
class SparsePatch:
    feature_id: str
    label: str
    target: str
    location: int
    expected: bytes
    fields: tuple[SparseField, ...]
    source_raw_offsets: tuple[int, ...]
    semantic_owner: str
    semantic_offset: int
    condition: IntegerCondition | None = None


def _anim_controls(
    set_number: int,
    defaults: tuple[int, ...],
    offsets: tuple[tuple[int, ...], ...],
    *,
    first_editable: int = 1,
) -> tuple[SourceControl, ...]:
    controls = []
    for index, (default, raw_offsets) in enumerate(
        zip(defaults, offsets), 1
    ):
        if index < first_editable:
            continue
        controls.append(
            SourceControl(
                f"Anim{set_number:02d}{index:02d}",
                f"timing_{index}",
                f"Timing {index}",
                default,
                1,
                99,
                raw_offsets,
            )
        )
    return tuple(controls)


ANIMATION_FEATURES = (
    FeatureSpec(
        "x_saber_timing",
        "X Saber Timing",
        "Set the seven positive timing values for X's normal Saber animation.",
        "Animation Timing",
        _anim_controls(
            1,
            (3, 2, 2, 3, 22, 4, 4),
            (
                (0x1D9BFAB4,),
                (0x1D9BFAB8, 0x1D997380),
                (0x1D9BFABC, 0x1D997384),
                (0x1D9BFAC0, 0x1D997388),
                (0x1D9BFAC4,),
                (0x1D9BFAC8,),
                (0x1D9BFACC,),
            ),
        ),
    ),
    FeatureSpec(
        "shadow_saber_timing",
        "Shadow Saber Timing",
        "Set the seven positive timing values for X's Shadow Armor Saber.",
        "Animation Timing",
        _anim_controls(
            2,
            (2, 1, 1, 2, 19, 4, 4),
            (
                (0x1D9BFAD4,),
                (0x1D9BFAD8, 0x1D9973B0),
                (0x1D9BFADC, 0x1D9973B4),
                (0x1D9BFAE0, 0x1D9973B8),
                (0x1D9BFAE4,),
                (0x1D9BFAE8,),
                (0x1D9BFAEC,),
            ),
        ),
    ),
    FeatureSpec(
        "zero_saber_cooldown_timing",
        "Zero Saber Cooldown Timing",
        (
            "Set the seven positive cooldown values after Zero's "
            "ground Saber combo."
        ),
        "Animation Timing",
        _anim_controls(
            3,
            (12, 4, 4, 4, 10, 6, 4),
            (
                (0x1D9C5EC0,),
                (0x1D9C5EC4, 0x1D9C5D5C, 0x1D9C5D20),
                (0x1D9C5EC8, 0x1D9C5D60, 0x1D9C5D24),
                (0x1D9C5ECC, 0x1D9C5D64, 0x1D9C5D28),
                (0x1D9C5ED0, 0x1D9C5D68, 0x1D9C5D2C),
                (0x1D9C5ED4, 0x1D9C5D6C, 0x1D9C5D30),
                (0x1D9C5ED8, 0x1D9C5D70, 0x1D9C5D34),
            ),
        ),
    ),
    FeatureSpec(
        "zero_z_buster_timing",
        "Zero Z-Buster Timing",
        "Set the seven positive timing values for Zero's Z-Buster animation.",
        "Animation Timing",
        _anim_controls(
            4,
            (1, 2, 2, 4, 6, 6, 4),
            (
                (0x1D9C64A8,),
                (0x1D9C64AC,),
                (0x1D9C64B0,),
                (0x1D9C64B4,),
                (0x1D9C64B8,),
                (0x1D9C64BC,),
                (0x1D9C64C0,),
            ),
        ),
    ),
)

MAX_LIVES_FEATURE = FeatureSpec(
    "maximum_lives",
    "Maximum Lives",
    (
        "Set the exact lives cap. Values above 9 also hide the pause-menu "
        "counter, matching Tweaks."
    ),
    "Lives",
    (
        SourceControl(
            "LivesValue04",
            "maximum",
            "Maximum",
            9,
            0,
            99,
            (0x1D968098, 0x1D968C90, 0x1D96808C, 0x1D968C84),
        ),
    ),
)

NIGHTMARE_OPACITY_FEATURE = FeatureSpec(
    "nightmare_dark_opacity",
    "Nightmare Dark Opacity",
    "Set the exact 1-64 opacity/intensity value used by Nightmare Dark.",
    "Nightmare Effects",
    (
        SourceControl(
            "NightmareMod01",
            "opacity",
            "Opacity",
            64,
            1,
            64,
            (0x1D9E1B74, 0x1DA3F634, 0x1DAFA320, 0x1DB1AC70),
        ),
    ),
)

FEATURES = (
    *ANIMATION_FEATURES,
    MAX_LIVES_FEATURE,
    NIGHTMARE_OPACITY_FEATURE,
)
FEATURE_BY_ID = {feature.feature_id: feature for feature in FEATURES}
ZERO_Z_BUSTER_TIMING_TABLE = range(0x11600, 0x1161C)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_source_database(patcher_source: Path, patcher_data: Path):
    try:
        import tweaks_engine as engine
    except ImportError as error:
        raise RuntimeError("cannot import tools/tweaks_engine.py") from error

    native.require_file(patcher_source, "Tweaks _dat.ahk")
    profile = patcher_data.parent / "profiles" / "default.x6tweaksprofile"
    native.require_file(profile, "Tweaks default profile")
    source_root = patcher_source.parent.parent
    database = engine.twr.TweaksDB(source_root)
    defaults = engine.twr.load_profile(profile)
    return engine, database, defaults


def _resolve_source_selection(
    engine,
    database,
    defaults: dict[str, str],
    selections: dict[str, int],
) -> tuple[str, list[str], dict, list[tuple[int, bytes]]]:
    merged = dict(defaults)
    merged.update({key: str(value) for key, value in selections.items()})
    _normalized, patchfile, patch_list, values, synth = engine._assemble(
        database, merged, defaults
    )
    inherited = set(database.patchlist_base) | set(
        database.patchlist_script
    )
    owned = [name for name in patch_list if name not in inherited]
    _file_patch, file_entries = engine.build_filelist(
        database, merged, defaults
    )
    if file_entries:
        raise AssertionError(
            f"timing/status source selection inserts files: {file_entries!r}"
        )
    writes = []
    for name in owned:
        for data_hex, raw_offset in engine.expand_entry(
            database, name, patchfile, values, synth
        ):
            for split_hex, split_offset in engine.ecc_split(
                data_hex, raw_offset
            ):
                writes.append((split_offset, bytes.fromhex(split_hex)))
    return patchfile, owned, synth, writes


def _audit_animation_sources(
    engine, database, defaults: dict[str, str]
) -> dict[str, dict]:
    evidence = {}
    for feature in ANIMATION_FEATURES:
        feature_samples = {}
        expected_source_ids = [control.source_id for control in feature.controls]
        for control in feature.controls:
            if defaults.get(control.source_id) != str(control.default):
                raise AssertionError(
                    f"{control.source_id} source default changed"
                )
            patchfile, owned, synth, writes = _resolve_source_selection(
                engine,
                database,
                defaults,
                {control.source_id: control.default},
            )
            if patchfile or owned or synth or writes:
                raise AssertionError(
                    f"{control.source_id} default is not a no-op"
                )
            tested = []
            for value in (1, 50, 99):
                if value == control.default:
                    continue
                patchfile, owned, synth, writes = _resolve_source_selection(
                    engine,
                    database,
                    defaults,
                    {control.source_id: value},
                )
                expected = [
                    (offset, bytes((value,)))
                    for offset in control.raw_offsets
                ]
                if (
                    patchfile != "b01"
                    or owned != [control.source_id]
                    or synth
                    or writes != expected
                ):
                    raise AssertionError(
                        f"{control.source_id}={value} source semantics changed: "
                        f"patchfile={patchfile!r}, owned={owned!r}, "
                        f"synth={sorted(synth)!r}, writes={writes!r}"
                    )
                tested.append(value)
            feature_samples[control.source_id] = tested

        combined = {
            control.source_id: 99
            for control in feature.controls
            if control.default != 99
        }
        patchfile, owned, synth, writes = _resolve_source_selection(
            engine, database, defaults, combined
        )
        expected_writes = [
            (offset, b"\x63")
            for control in feature.controls
            for offset in control.raw_offsets
        ]
        if (
            patchfile != "b01"
            or owned != expected_source_ids
            or synth
            or writes != expected_writes
        ):
            raise AssertionError(
                f"{feature.feature_id} combined source semantics changed"
            )
        evidence[feature.feature_id] = {
            "source_samples": feature_samples,
            "combined_sample": 99,
            "source_closure": expected_source_ids,
        }
    return evidence


def _expected_lives_writes(value: int) -> list[tuple[int, bytes]]:
    writes = []
    if value > 9:
        writes.append((0x1D92B588, bytes(4)))
    writes.extend(
        (
            (0x1D968098, value.to_bytes(2, "little")),
            (0x1D968C90, value.to_bytes(2, "little")),
            (0x1D96808C, (value + 1).to_bytes(2, "little")),
            (0x1D968C84, (value + 1).to_bytes(2, "little")),
        )
    )
    return writes


def _audit_lives_source(
    engine, database, defaults: dict[str, str]
) -> dict:
    control = MAX_LIVES_FEATURE.controls[0]
    if defaults.get(control.source_id) != str(control.default):
        raise AssertionError("LivesValue04 source default changed")
    samples = {}
    for value in (0, 1, 8, 9, 10, 99):
        patchfile, owned, synth, writes = _resolve_source_selection(
            engine, database, defaults, {control.source_id: value}
        )
        if value == control.default:
            if patchfile or owned or synth or writes:
                raise AssertionError("LivesValue04 default is not a no-op")
        else:
            expected_owned = (
                ["LivesDisplay01", "LivesValue04", "LivesValue04b"]
                if value > 9
                else ["LivesValue04", "LivesValue04b"]
            )
            if (
                patchfile != "b01"
                or owned != expected_owned
                or set(synth) != {"LivesValue04b"}
                or writes != _expected_lives_writes(value)
            ):
                raise AssertionError(
                    f"LivesValue04={value} source semantics changed"
                )
        samples[str(value)] = [
            {"raw_offset": offset, "replace": payload.hex().upper()}
            for offset, payload in writes
        ]
    return {
        "source_samples": samples,
        "conditional_helper": {
            "source_id": "LivesDisplay01",
            "condition": "maximum > 9",
        },
        "companion_value": "maximum + 1",
    }


def _nightmare_template(value: int) -> bytes:
    return (
        bytes((value,))
        + bytes.fromhex("00422802004014")
        + bytes((value - 1,))
        + bytes.fromhex("000224")
    )


def _expected_nightmare_writes(value: int) -> list[tuple[int, bytes]]:
    template = _nightmare_template(value)
    return [
        (0x1D9E1B74, template),
        (0x1DA3F634, template),
        (0x1DAFA320, template[:8]),
        (0x1DAFA458, template[8:]),
        (0x1DB1AC70, template),
    ]


def _audit_nightmare_source(
    engine, database, defaults: dict[str, str]
) -> dict:
    control = NIGHTMARE_OPACITY_FEATURE.controls[0]
    if defaults.get(control.source_id) != str(control.default):
        raise AssertionError("NightmareMod01 source default changed")
    samples = {}
    for value in (1, 28, 63, 64):
        patchfile, owned, synth, writes = _resolve_source_selection(
            engine, database, defaults, {control.source_id: value}
        )
        if value == control.default:
            if patchfile or owned or synth or writes:
                raise AssertionError("NightmareMod01 default is not a no-op")
        elif (
            patchfile != "b01"
            or owned != ["NightmareMod0100"]
            or set(synth) != {"NightmareMod0100"}
            or writes != _expected_nightmare_writes(value)
        ):
            raise AssertionError(
                f"NightmareMod01={value} source semantics changed"
            )
        samples[str(value)] = [
            {"raw_offset": offset, "replace": payload.hex().upper()}
            for offset, payload in writes
        ]
    return {
        "source_samples": samples,
        "template": (
            "u8(opacity), fixed 7-byte instruction body, "
            "u8(opacity - 1), fixed 3-byte instruction tail"
        ),
    }


def audit_sources(patcher_source: Path, patcher_data: Path) -> dict[str, dict]:
    engine, database, defaults = _load_source_database(
        patcher_source, patcher_data
    )
    evidence = _audit_animation_sources(engine, database, defaults)
    evidence[MAX_LIVES_FEATURE.feature_id] = _audit_lives_source(
        engine, database, defaults
    )
    evidence[NIGHTMARE_OPACITY_FEATURE.feature_id] = (
        _audit_nightmare_source(engine, database, defaults)
    )
    return evidence


class StockMapper:
    def __init__(
        self, stock: native.RawMode2Image, b01_base: native.RawMode2Image
    ):
        self.stock = stock
        self.b01_base = b01_base
        self.stock_load = struct.unpack(
            "<I", stock.read_file(native.SLUS_NAME)[0x18:0x1C]
        )[0]
        self.stock_bin_entry = stock.entries["ROCK_X6.BIN"]
        self.stock_members = native.indexed_archive_members(
            stock.read_file("ROCK_X6.BIN")
        )
        self.b01_members = native.indexed_archive_members(
            b01_base.read_file("ROCK_X6.BIN")
        )

    def map_guard(
        self, raw_offset: int, guard_size: int
    ) -> tuple[str, int, bytes, str, int]:
        user_offset = native.raw_to_user_offset(raw_offset)
        entry, file_offset = self.b01_base.containing_file(
            user_offset, guard_size
        )
        if entry.name == native.SLUS_NAME:
            expected = native.read_iso_file_range(
                self.b01_base, entry.name, file_offset, guard_size
            )
            stock_expected = native.read_iso_file_range(
                self.stock, entry.name, file_offset, guard_size
            )
            if expected != stock_expected:
                raise AssertionError(
                    f"guard at 0x{raw_offset:X} depends on a B01 SLUS rewrite"
                )
            location = self.stock_load + file_offset - native.USER_SECTOR
            return "main_exe", location, expected, native.SLUS_NAME, file_offset

        if entry.name != "ROCK_X6.BIN":
            raise AssertionError(
                f"guard at 0x{raw_offset:X} targets unsupported {entry.name}"
            )
        try:
            source_member, relative_offset = native.containing_member(
                self.b01_members, file_offset, guard_size
            )
        except ValueError:
            if (
                file_offset in ZERO_Z_BUSTER_TIMING_TABLE
                and file_offset + guard_size <= ZERO_Z_BUSTER_TIMING_TABLE.stop
            ):
                expected = native.read_iso_file_range(
                    self.b01_base, entry.name, file_offset, guard_size
                )
                stock_expected = native.read_iso_file_range(
                    self.stock, entry.name, file_offset, guard_size
                )
                if expected != stock_expected:
                    raise AssertionError(
                        f"guard at 0x{raw_offset:X} depends on a B01 "
                        "unindexed ROCK_X6.BIN rewrite"
                    )
                location = self.stock_bin_entry.lba * native.USER_SECTOR + file_offset
                if location % native.USER_SECTOR + guard_size > native.USER_SECTOR:
                    raise AssertionError(
                        f"guard at 0x{raw_offset:X} crosses a runtime sector"
                    )
                return (
                    "disc_user",
                    location,
                    expected,
                    "ROCK_X6.BIN unindexed Zero Z-Buster timing table",
                    file_offset,
                )
            raise
        stock_member = self.stock_members.get(source_member.member_id)
        if stock_member is None:
            raise AssertionError(
                f"stock lacks ROCK_X6.BIN member {source_member.member_id}"
            )
        expected = source_member.payload[
            relative_offset : relative_offset + guard_size
        ]
        stock_expected = stock_member.payload[
            relative_offset : relative_offset + guard_size
        ]
        if expected != stock_expected:
            raise AssertionError(
                f"guard at 0x{raw_offset:X} depends on a B01 member rewrite"
            )
        semantic_offset = stock_member.file_offset + relative_offset
        location = (
            self.stock_bin_entry.lba * native.USER_SECTOR + semantic_offset
        )
        if location % native.USER_SECTOR + guard_size > native.USER_SECTOR:
            raise AssertionError(
                f"guard at 0x{raw_offset:X} crosses a runtime sector"
            )
        owner = f"ROCK_X6.BIN member {source_member.member_id}"
        return "disc_user", location, expected, owner, semantic_offset


def _mapped_patch(
    mapper: StockMapper,
    feature_id: str,
    label: str,
    raw_offset: int,
    guard_size: int,
    fields: tuple[SparseField, ...],
    *,
    source_raw_offsets: tuple[int, ...] | None = None,
    condition: IntegerCondition | None = None,
) -> SparsePatch:
    target, location, expected, owner, semantic_offset = mapper.map_guard(
        raw_offset, guard_size
    )
    for field in fields:
        if field.offset < 0 or field.offset + field.size > len(expected):
            raise AssertionError(f"{label} field exceeds its complete guard")
    return SparsePatch(
        feature_id,
        label,
        target,
        location,
        expected,
        fields,
        source_raw_offsets or (raw_offset,),
        owner,
        semantic_offset,
        condition,
    )


def build_operations(
    stock: native.RawMode2Image, b01_base: native.RawMode2Image
) -> tuple[SparsePatch, ...]:
    mapper = StockMapper(stock, b01_base)
    operations = []

    for feature in ANIMATION_FEATURES:
        for control in feature.controls:
            for occurrence, raw_offset in enumerate(control.raw_offsets, 1):
                operation = _mapped_patch(
                    mapper,
                    feature.feature_id,
                    f"{control.source_id}-{occurrence}",
                    raw_offset,
                    4,
                    (SparseField(0, control.option_id),),
                )
                if operation.expected[0] != control.default:
                    raise AssertionError(
                        f"{control.source_id} stock guard default changed"
                    )
                operations.append(operation)

    maximum = MAX_LIVES_FEATURE.controls[0]
    for occurrence, raw_offset in enumerate(
        (0x1D968098, 0x1D968C90), 1
    ):
        operation = _mapped_patch(
            mapper,
            MAX_LIVES_FEATURE.feature_id,
            f"LivesValue04-cap-{occurrence}",
            raw_offset,
            4,
            (SparseField(0, maximum.option_id, "u16le"),),
        )
        if operation.expected[:2] != maximum.default.to_bytes(2, "little"):
            raise AssertionError("LivesValue04 stock cap guard changed")
        operations.append(operation)
    for occurrence, raw_offset in enumerate(
        (0x1D96808C, 0x1D968C84), 1
    ):
        operation = _mapped_patch(
            mapper,
            MAX_LIVES_FEATURE.feature_id,
            f"LivesValue04-cap-plus-one-{occurrence}",
            raw_offset,
            4,
            (SparseField(0, maximum.option_id, "u16le", addend=1),),
        )
        if operation.expected[:2] != (
            maximum.default + 1
        ).to_bytes(2, "little"):
            raise AssertionError("LivesValue04 stock companion guard changed")
        operations.append(operation)
    operations.append(
        _mapped_patch(
            mapper,
            MAX_LIVES_FEATURE.feature_id,
            "LivesDisplay01-above-nine",
            0x1D92B588,
            4,
            (SparseField(0, replacement=bytes(4)),),
            condition=IntegerCondition(maximum.option_id, "gt", 9),
        )
    )

    opacity = NIGHTMARE_OPACITY_FEATURE.controls[0]
    for occurrence, raw_offset in enumerate(
        (0x1D9E1B74, 0x1DA3F634), 1
    ):
        operation = _mapped_patch(
            mapper,
            NIGHTMARE_OPACITY_FEATURE.feature_id,
            f"NightmareMod01-record-{occurrence}",
            raw_offset,
            12,
            (
                SparseField(0, opacity.option_id),
                SparseField(8, opacity.option_id, addend=-1),
            ),
        )
        if operation.expected != _nightmare_template(opacity.default):
            raise AssertionError("NightmareMod01 stock record changed")
        operations.append(operation)
    first = _mapped_patch(
        mapper,
        NIGHTMARE_OPACITY_FEATURE.feature_id,
        "NightmareMod01-sector-split-head",
        0x1DAFA320,
        8,
        (SparseField(0, opacity.option_id),),
    )
    tail = _mapped_patch(
        mapper,
        NIGHTMARE_OPACITY_FEATURE.feature_id,
        "NightmareMod01-sector-split-tail",
        0x1DAFA458,
        4,
        (SparseField(0, opacity.option_id, addend=-1),),
    )
    if first.expected != _nightmare_template(opacity.default)[:8]:
        raise AssertionError("NightmareMod01 split head guard changed")
    if tail.expected != _nightmare_template(opacity.default)[8:]:
        raise AssertionError("NightmareMod01 split tail guard changed")
    operations.extend((first, tail))
    operation = _mapped_patch(
        mapper,
        NIGHTMARE_OPACITY_FEATURE.feature_id,
        "NightmareMod01-record-4",
        0x1DB1AC70,
        12,
        (
            SparseField(0, opacity.option_id),
            SparseField(8, opacity.option_id, addend=-1),
        ),
    )
    if operation.expected != _nightmare_template(opacity.default):
        raise AssertionError("NightmareMod01 final stock record changed")
    operations.append(operation)

    validate_operations(tuple(operations))
    return tuple(operations)


def _field_default(feature: FeatureSpec, field: SparseField) -> bytes:
    if field.replacement is not None:
        return field.replacement
    control = next(
        control
        for control in feature.controls
        if control.option_id == field.option_id
    )
    value = control.default + field.addend
    return value.to_bytes(field.size, "little")


def validate_operations(operations: tuple[SparsePatch, ...]) -> None:
    owned = []
    for operation in operations:
        feature = FEATURE_BY_ID[operation.feature_id]
        claimed = []
        for field in operation.fields:
            if field.offset + field.size > len(operation.expected):
                raise AssertionError(f"{operation.label} field exceeds guard")
            begin = operation.location + field.offset
            end = begin + field.size
            for previous_begin, previous_end in claimed:
                if begin < previous_end and previous_begin < end:
                    raise AssertionError(
                        f"{operation.label} has overlapping fields"
                    )
            claimed.append((begin, end))
            owned.append(
                (
                    operation.target,
                    begin,
                    end,
                    _field_default(feature, field),
                    operation.label,
                )
            )
        for other in operations:
            if operation is other or operation.target != other.target:
                continue
            begin = max(operation.location, other.location)
            end = min(
                operation.location + len(operation.expected),
                other.location + len(other.expected),
            )
            if begin >= end:
                continue
            left = operation.expected[
                begin - operation.location : end - operation.location
            ]
            right = other.expected[
                begin - other.location : end - other.location
            ]
            if left != right:
                raise AssertionError(
                    f"incompatible guards: {operation.label}/{other.label}"
                )
    owned.sort(key=lambda item: (item[0], item[1], item[2], item[4]))
    for index, left in enumerate(owned):
        for right in owned[index + 1 :]:
            if right[0] != left[0] or right[1] >= left[2]:
                break
            if left[1] < right[2] and right[1] < left[2]:
                raise AssertionError(
                    f"owned-field collision: {left[4]}/{right[4]}"
                )


def source_controls_report() -> list[dict]:
    return [
        {
            "feature_id": feature.feature_id,
            "option_id": control.option_id,
            "source_id": control.source_id,
            "label": control.label,
            "source_default": control.default,
            "accepted_minimum": control.minimum,
            "accepted_maximum": control.maximum,
            "source_raw_offsets": list(control.raw_offsets),
            "conversion_status": "exact-bounded-source-control",
        }
        for feature in FEATURES
        for control in feature.controls
    ]


def operation_report(operation: SparsePatch) -> dict:
    return {
        "kind": "sparse-guarded-patch",
        "label": operation.label,
        "target": operation.target,
        "location": operation.location,
        "complete_guard": operation.expected.hex().upper(),
        "guard_size": len(operation.expected),
        "semantic_owner": operation.semantic_owner,
        "semantic_offset": operation.semantic_offset,
        "source_raw_offsets": list(operation.source_raw_offsets),
        "owned_fields": [
            {
                "offset": field.offset,
                "size": field.size,
                "option_id": field.option_id or None,
                "encoding": field.encoding if field.option_id else None,
                "addend": field.addend if field.option_id else None,
                "replace": (
                    field.replacement.hex().upper()
                    if field.replacement is not None
                    else None
                ),
            }
            for field in operation.fields
        ],
        "when_integer": (
            {
                "option": operation.condition.option_id,
                "op": operation.condition.operation,
                "value": operation.condition.value,
            }
            if operation.condition
            else None
        ),
    }


def build_report(
    stock_sha256: str,
    b01_sha256: str,
    source_sha256: str,
    source_evidence: dict[str, dict],
    operations: tuple[SparsePatch, ...],
    package_version: str,
    converter_sha256: str,
) -> dict:
    by_feature = {
        feature.feature_id: {
            "status": "exact-source-conversion-pending-live-smoke",
            "source_controls": [
                control.source_id for control in feature.controls
            ],
            "source_audit": source_evidence[feature.feature_id],
            "semantic_operations": [
                operation_report(operation)
                for operation in operations
                if operation.feature_id == feature.feature_id
            ],
        }
        for feature in FEATURES
    }
    canonical_plan = [
        (
            operation.feature_id,
            operation.target,
            operation.location,
            operation.expected.hex(),
            tuple(
                (
                    field.offset,
                    field.option_id,
                    field.encoding,
                    field.addend,
                    (
                        field.replacement.hex()
                        if field.replacement is not None
                        else None
                    ),
                )
                for field in operation.fields
            ),
            (
                (
                    operation.condition.option_id,
                    operation.condition.operation,
                    operation.condition.value,
                )
                if operation.condition
                else None
            ),
        )
        for operation in operations
    ]
    return {
        "status": "reviewed-format-4-timing-status-tranche",
        "package_id": PACKAGE_ID,
        "package_version": package_version,
        "stock_sha256": stock_sha256,
        "converter_sha256": converter_sha256,
        "provenance": {
            "b01_base_sha256": b01_sha256,
            "patcher_source_sha256": source_sha256,
        },
        "source_controls": sorted(
            control.source_id
            for feature in FEATURES
            for control in feature.controls
        ),
        "source_control_details": source_controls_report(),
        "features": by_feature,
        "composition": {
            "sparse_patch_operations": len(operations),
            "complete_guard_bytes": sum(
                len(operation.expected) for operation in operations
            ),
            "owned_field_bytes": sum(
                field.size
                for operation in operations
                for field in operation.fields
            ),
            "stock_guards_verified": True,
            "b01_to_stock_semantic_mapping_verified": True,
            "incompatible_owned_overlaps": 0,
            "plan_fingerprint": _sha256(
                json.dumps(
                    canonical_plan, separators=(",", ":")
                ).encode("utf-8")
            ),
        },
        "deferred": {
            "animation_zero_values": {
                "status": "deferred",
                "reason": (
                    "Tweaks rewrites zero to a 01 sentinel plus an offset+2 "
                    "companion byte, and a zero first frame can terminate the "
                    "set loop. Positive values only are admitted."
                ),
            },
        },
        "forbidden_runtime_payloads": {
            "derived_disc": False,
            "vcdiff": False,
            "patched_oracle": False,
            "package_code": False,
        },
    }


def build_manifest(
    operations: tuple[SparsePatch, ...], package_version: str
) -> str:
    lines = [
        "format_version = 4",
        f"id = {_q(PACKAGE_ID)}",
        f"version = {_q(package_version)}",
        f"name = {_q(PACKAGE_NAME)}",
        (
            'author = "acediez, DuoDynamo, NectarHime; '
            'PSXRecomp integration"'
        ),
        (
            'description = "Independent bounded timing and status controls '
            'converted from MMX6 Tweaks."'
        ),
        'license = "Generated locally; original credits retained"',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {_q(native.GAME_ID)}",
        f"disc_sha256 = {_q(native.STOCK_SHA256)}",
    ]
    for feature in FEATURES:
        lines += [
            "",
            "[[feature]]",
            f"id = {_q(feature.feature_id)}",
            f"name = {_q(feature.name)}",
            f"description = {_q(feature.description)}",
            f"group = {_q(feature.group)}",
            "default_enabled = false",
        ]
        for control in feature.controls:
            lines += [
                "",
                "[[option]]",
                f"feature = {_q(feature.feature_id)}",
                f"id = {_q(control.option_id)}",
                f"label = {_q(control.label)}",
                f"description = {_q(feature.description)}",
                f"group = {_q(feature.group)}",
                'type = "integer"',
                f"min = {control.minimum}",
                f"max = {control.maximum}",
                "step = 1",
                f"default = {control.default}",
            ]
    for operation in operations:
        lines += [
            "",
            "[[patch]]",
            f"feature = {_q(operation.feature_id)}",
            f"target = {_q(operation.target)}",
            (
                f"address = {operation.location}"
                if operation.target == "main_exe"
                else f"offset = {operation.location}"
            ),
            f"expected = {_q(operation.expected.hex().upper())}",
            "fields = [",
        ]
        for field in operation.fields:
            if field.replacement is not None:
                body = (
                    f"offset = {field.offset}, "
                    f"replace = {_q(field.replacement.hex().upper())}"
                )
            else:
                values = [
                    f"offset = {field.offset}",
                    f"option = {_q(field.option_id)}",
                    f"encoding = {_q(field.encoding)}",
                ]
                if field.addend:
                    values.append(f"addend = {field.addend}")
                body = ", ".join(values)
            lines.append(f"  {{ {body} }},")
        lines += ["]", "order = 0"]
        if operation.condition:
            condition = operation.condition
            lines.append(
                "when_integer = { "
                f"option = {_q(condition.option_id)}, "
                f"op = {_q(condition.operation)}, "
                f"value = {condition.value} "
                "}"
            )
    return "\n".join(lines) + "\n"


def write_package(
    out: Path,
    operations: tuple[SparsePatch, ...],
    report: dict,
    package_version: str,
) -> None:
    manifest = build_manifest(operations, package_version)
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, payload in (
            ("manifest.toml", manifest),
            (
                "conversion-report.json",
                json.dumps(report, indent=2, sort_keys=True) + "\n",
            ),
            (
                "README.txt",
                (
                    "Generated locally from verified MMX6 Tweaks source data "
                    "and a stock Mega Man X6 USA v1.1 image.\n"
                    "This format-4 package applies guarded sparse fields to "
                    "the stock image at runtime. It contains no patched disc, "
                    "derived-disc recipe, VCDIFF, or executable package code.\n"
                ),
            ),
        ):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload.encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=DEFAULT_STOCK)
    parser.add_argument("--b01-base", type=Path, default=DEFAULT_B01_BASE)
    parser.add_argument(
        "--patcher-data", type=Path, default=DEFAULT_PATCHER_DATA
    )
    parser.add_argument(
        "--patcher-source", type=Path, default=DEFAULT_PATCHER_SOURCE
    )
    parser.add_argument("--package-version", default=PACKAGE_VERSION)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path, description in (
        (args.stock, "stock MMX6 BIN"),
        (args.b01_base, "isolated B01 base oracle"),
        (args.patcher_source, "Tweaks _dat.ahk"),
    ):
        native.require_file(path, description)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.package_version):
        raise ValueError("--package-version must be numeric X.Y.Z")

    stock_sha256 = native.file_sha256(args.stock)
    if stock_sha256 != native.STOCK_SHA256:
        raise ValueError(
            f"unsupported stock image: {stock_sha256}; "
            f"expected {native.STOCK_SHA256}"
        )
    source_evidence = audit_sources(args.patcher_source, args.patcher_data)
    with native.RawMode2Image(args.stock) as stock, native.RawMode2Image(
        args.b01_base
    ) as b01_base:
        operations = build_operations(stock, b01_base)
    report = build_report(
        stock_sha256,
        native.file_sha256(args.b01_base),
        native.file_sha256(args.patcher_source),
        source_evidence,
        operations,
        args.package_version,
        native.file_sha256(Path(__file__)),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.verify_only:
        write_package(
            args.out, operations, report, args.package_version
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
