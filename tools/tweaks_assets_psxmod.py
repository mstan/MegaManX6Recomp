#!/usr/bin/env python3
"""Build the reviewed MMX6 Tweaks portrait and palette asset package.

This converter intentionally handles only the stock-disc-safe asset slice:

* twelve independent mugshot features (Alia through Sigma);
* Ultimate X's five replacement palette choices; and
* Nightmare Zero's replacement palette.

Hunter and Dr. Light mugshots, loading logos, stage objects, and executable
ceiling behavior are different composition domains and are rejected here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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


PACKAGE_ID = "mmx6.tweaks.assets"
PACKAGE_VERSION = "1.0.0"
PACKAGE_NAME = "Mega Man X6 Tweaks — Portraits and Palettes"


@dataclass(frozen=True)
class Variant:
    value: str
    label: str
    source_value: str


@dataclass(frozen=True)
class Feature:
    feature_id: str
    name: str
    description: str
    group: str
    source_option: str
    variants: tuple[Variant, ...]
    kind: str
    allowed_asset_records: tuple[int, ...] = ()


@dataclass(frozen=True)
class DatIdentity:
    record_id: int
    subasset_index: int | None
    asset_type: int | None
    relative_offset: int
    size: int

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        return (
            self.record_id,
            -1 if self.subasset_index is None else self.subasset_index,
            -1 if self.asset_type is None else self.asset_type,
            self.relative_offset,
            self.size,
        )

    def label(self) -> str:
        if self.subasset_index is None:
            return (
                f"record-{self.record_id:03d}-"
                f"range-{self.relative_offset:06x}-{self.size:04x}"
            )
        return (
            f"record-{self.record_id:03d}-subasset-"
            f"{self.subasset_index:02d}-range-"
            f"{self.relative_offset:06x}-{self.size:04x}"
        )


@dataclass(frozen=True)
class AssetOverlay:
    feature: str
    variant: str
    label: str
    identity: DatIdentity
    user_offset: int
    expected: bytes
    replace: bytes
    operation_kind: str
    source_option: str
    source_value: str
    source_raw_offset: int
    source_file: str = ""

    @property
    def when(self) -> tuple[str, str] | None:
        feature = FEATURE_BY_ID[self.feature]
        return (
            ("variant", self.variant)
            if len(feature.variants) > 1
            else None
        )


def _variants(*values: tuple[str, str, str]) -> tuple[Variant, ...]:
    return tuple(Variant(*item) for item in values)


FEATURES = (
    Feature(
        "mugshot_alia",
        "Alia Mugshot",
        "Replace Alia's dialogue portrait.",
        "Portraits",
        "MugshotCustom03",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
    ),
    Feature(
        "mugshot_x",
        "X Mugshot",
        "Replace X's dialogue portrait.",
        "Portraits",
        "MugshotCustom04",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (163, 164),
    ),
    Feature(
        "mugshot_ultimate_x",
        "Ultimate X Mugshot",
        "Replace Ultimate X's dialogue portrait.",
        "Portraits",
        "MugshotCustom05",
        _variants(
            ("custom_a", "Custom A", "Custom A"),
            ("custom_b", "Custom B", "Custom B"),
            ("custom_c", "Custom C", "Custom C"),
            ("custom_d", "Custom D", "Custom D"),
        ),
        "mugshot",
        (167, 168),
    ),
    Feature(
        "mugshot_falcon_x",
        "Falcon Armor X Mugshot",
        "Replace Falcon Armor X's dialogue portrait.",
        "Portraits",
        "MugshotCustom06",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (169, 170),
    ),
    Feature(
        "mugshot_shadow_x",
        "Shadow Armor X Mugshot",
        "Replace Shadow Armor X's dialogue portrait.",
        "Portraits",
        "MugshotCustom07",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (171, 172),
    ),
    Feature(
        "mugshot_blade_x",
        "Blade Armor X Mugshot",
        "Replace Blade Armor X's dialogue portrait.",
        "Portraits",
        "MugshotCustom08",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (173, 174),
    ),
    Feature(
        "mugshot_zero",
        "Zero Mugshot",
        "Replace Zero's dialogue portrait.",
        "Portraits",
        "MugshotCustom09",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (165, 166),
    ),
    Feature(
        "mugshot_black_zero",
        "Black Zero Mugshot",
        "Replace Black Zero's dialogue portrait.",
        "Portraits",
        "MugshotCustom10",
        _variants(
            ("custom_a", "Custom A", "Custom A"),
            ("custom_b", "Custom B", "Custom B"),
        ),
        "mugshot",
        (175, 176),
    ),
    Feature(
        "mugshot_nightmare_zero",
        "Nightmare Zero Mugshot",
        "Replace Nightmare Zero's dialogue portrait.",
        "Portraits",
        "MugshotCustom11",
        _variants(
            ("custom_a", "Custom A", "Custom A"),
            ("custom_b", "Custom B", "Custom B"),
        ),
        "mugshot",
        (193, 194),
    ),
    Feature(
        "mugshot_dynamo",
        "Dynamo Mugshot",
        "Replace Dynamo's dialogue portrait.",
        "Portraits",
        "MugshotCustom12",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (195, 196),
    ),
    Feature(
        "mugshot_gate",
        "Gate Mugshot",
        "Replace Gate's dialogue portrait.",
        "Portraits",
        "MugshotCustom13",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (199, 200),
    ),
    Feature(
        "mugshot_sigma",
        "Sigma Mugshot",
        "Replace Sigma's dialogue portrait.",
        "Portraits",
        "MugshotCustom14",
        _variants(("custom_a", "Custom A", "Custom A")),
        "mugshot",
        (201, 202),
    ),
    Feature(
        "palette_ultimate_x",
        "Ultimate X Palette",
        "Replace Ultimate X's player and menu palettes.",
        "Palettes",
        "SpritePalette01",
        _variants(
            ("x6_proto_x4", "X6 Proto / X4", "X6 Proto/X4"),
            ("x5", "X5", "X5"),
            ("custom_a", "Custom A", "Custom A"),
            ("custom_b", "Custom B", "Custom B"),
            ("custom_c", "Custom C", "Custom C"),
        ),
        "palette",
    ),
    Feature(
        "palette_nightmare_zero",
        "Nightmare Zero Palette",
        "Replace Nightmare Zero's sprite palette.",
        "Palettes",
        "SpritePalette02",
        _variants(("custom_a", "Custom A", "Custom A")),
        "palette",
    ),
)

FEATURE_BY_ID = {item.feature_id: item for item in FEATURES}

DEFERRED = {
    "MugshotCustom01": (
        "Hunter needs new DAT records 243/244 and script-aware portrait "
        "references that compose with Retranslation."
    ),
    "MugshotCustom02": (
        "Dr. Light needs new DAT records 245/246 and script-aware portrait "
        "references that compose with Retranslation."
    ),
    "TitleLoading01/02/03": (
        "The upstream patcher admits non-stock logos are incomplete on the "
        "title-demo return path and silently forces Disable Demos."
    ),
    "StageMod0404": (
        "The Recycle Lab teleport needs a reviewed typed stage-object schema."
    ),
    "AutoCrouching01/02/03 + RecycleCeiling01": (
        "Ceiling behavior needs one registered-hook feature with three "
        "non-stock modes, not asset overlays."
    ),
}

TITLE_OWNERS = {
    (107, 8),
    (26, 0),
    (107, 1),
    (107, 3),
}

RETRANSLATION_SUBASSET_OWNERS = {
    *((record_id, 7) for record_id in range(85, 90)),
    *((record_id, 9) for record_id in range(85, 90)),
}
RETRANSLATION_WHOLE_RECORDS = {
    106,
    110,
    111,
    *range(149, 162),
    *range(203, 243),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class DatView:
    def __init__(self, image: native.RawMode2Image):
        self.image = image
        self.entry = image.entries["ROCK_X6.DAT"]
        self.records = native.dat_records(image.read_file("ROCK_X6.DAT"))

    def source_identity(self, raw_offset: int, size: int) -> DatIdentity:
        user_offset = native.raw_to_user_offset(raw_offset)
        entry, file_offset = self.image.containing_file(user_offset, size)
        if entry.name != "ROCK_X6.DAT":
            raise AssertionError(
                f"source range 0x{raw_offset:X}+0x{size:X} targets {entry.name}"
            )
        record = self._record_containing(file_offset, size)
        relative = file_offset - record.sector * native.USER_SECTOR
        try:
            subassets = native.parse_subassets(record)
        except ValueError:
            subassets = ()
        cursor = native.USER_SECTOR
        for index, subasset in enumerate(subassets):
            end = cursor + len(subasset.payload)
            if cursor <= relative and relative + size <= end:
                return DatIdentity(
                    record.record_id,
                    index,
                    subasset.asset_type,
                    relative - cursor,
                    size,
                )
            cursor = (
                (end + native.USER_SECTOR - 1)
                // native.USER_SECTOR
                * native.USER_SECTOR
            )
        if relative + size > record.size:
            raise AssertionError(
                f"source range leaves DAT record {record.record_id}"
            )
        return DatIdentity(record.record_id, None, None, relative, size)

    def expected_and_offset(
        self, identity: DatIdentity
    ) -> tuple[bytes, int, int]:
        try:
            record = self.records[identity.record_id]
        except KeyError as error:
            raise AssertionError(
                f"stock lacks DAT record {identity.record_id}"
            ) from error
        if identity.subasset_index is None:
            begin = identity.relative_offset
            end = begin + identity.size
            if end > len(record.payload):
                raise AssertionError(
                    f"stock DAT record {identity.record_id} is too small"
                )
            expected = record.payload[begin:end]
            record_relative = begin
        else:
            subassets = native.parse_subassets(record)
            try:
                subasset = subassets[identity.subasset_index]
            except IndexError as error:
                raise AssertionError(
                    f"stock record {identity.record_id} lacks subasset "
                    f"{identity.subasset_index}"
                ) from error
            if subasset.asset_type != identity.asset_type:
                raise AssertionError(
                    f"stock record {identity.record_id} subasset "
                    f"{identity.subasset_index} type is "
                    f"0x{subasset.asset_type:X}, expected "
                    f"0x{identity.asset_type:X}"
                )
            begin = identity.relative_offset
            end = begin + identity.size
            if end > len(subasset.payload):
                raise AssertionError(
                    f"stock record {identity.record_id} subasset "
                    f"{identity.subasset_index} is too small"
                )
            expected = subasset.payload[begin:end]
            record_relative = (
                native.subasset_payload_offset(
                    record, identity.subasset_index
                )
                + begin
            )
        file_offset = (
            record.sector * native.USER_SECTOR + record_relative
        )
        user_offset = self.entry.lba * native.USER_SECTOR + file_offset
        return expected, user_offset, file_offset

    def read_source(self, raw_offset: int, size: int) -> bytes:
        return self.image.read_user(
            native.raw_to_user_offset(raw_offset), size
        )

    def _record_containing(
        self, file_offset: int, size: int
    ) -> native.DatRecord:
        for record in self.records.values():
            begin = record.sector * native.USER_SECTOR
            if begin <= file_offset and file_offset + size <= begin + record.size:
                return record
        raise AssertionError(
            f"ROCK_X6.DAT range 0x{file_offset:X}+0x{size:X} "
            "has no record owner"
        )


def _maximal_changed_runs(
    expected: bytes, replacement: bytes
) -> list[tuple[int, int]]:
    if len(expected) != len(replacement):
        raise AssertionError("changed-run inputs have different sizes")
    result: list[tuple[int, int]] = []
    begin: int | None = None
    for index, (left, right) in enumerate(zip(expected, replacement)):
        if left != right and begin is None:
            begin = index
        elif left == right and begin is not None:
            result.append((begin, index - begin))
            begin = None
    if begin is not None:
        result.append((begin, len(expected) - begin))
    return result


def _semantic_mugshot_write(
    b01: DatView, raw_offset: int, replacement: bytes
) -> tuple[DatIdentity, bytes, bytes, int]:
    """Bound MugshotAssembly to its owned type-0x18 payload.

    Nightmare Zero exposes an upstream StringRewrite quirk: assembly_07.bin is
    too short for Nightmare Zero's relative slot, so the patcher appends ten
    bytes into alignment padding after the type-0x18 subasset. Padding is not
    an asset field and has no loader-visible owner. Prove that the spill stays
    in padding, report it, and omit it from the native plan.
    """
    start = b01.source_identity(raw_offset, 1)
    if start.subasset_index is None or start.asset_type != 0x18:
        raise AssertionError(
            f"MugshotAssembly left type 0x18: {start}"
        )
    record = b01.records[start.record_id]
    subasset = native.parse_subassets(record)[start.subasset_index]
    capacity = len(subasset.payload) - start.relative_offset
    if capacity <= 0:
        raise AssertionError("MugshotAssembly begins past its subasset")
    semantic_size = min(len(replacement), capacity)
    ignored = len(replacement) - semantic_size
    if ignored:
        padded_size = (
            (len(subasset.payload) + native.USER_SECTOR - 1)
            // native.USER_SECTOR
            * native.USER_SECTOR
        )
        available_padding = padded_size - len(subasset.payload)
        if ignored > available_padding:
            raise AssertionError(
                "MugshotAssembly spill reaches the next logical subasset"
            )
    identity = DatIdentity(
        start.record_id,
        start.subasset_index,
        start.asset_type,
        start.relative_offset,
        semantic_size,
    )
    expected = b01.read_source(raw_offset, semantic_size)
    return identity, expected, replacement[:semantic_size], ignored


def _profile_context() -> tuple[object, dict]:
    source_dir = engine.twr.DEFAULT_PATCHER_SRC
    db = engine.twr.TweaksDB(source_dir)
    profile = engine.twr.load_profile(engine.twr.DEFAULT_PROFILE)
    return db, profile


def _assemble_variant(
    db, base: dict, feature: Feature, variant: Variant
) -> tuple[dict, str, list[str], dict, list[tuple[str, str, int]]]:
    merged = dict(base)
    merged[feature.source_option] = variant.source_value
    normalized, patchfile, patch_list, _values, synth = engine._assemble(
        db, merged, base
    )
    inherited = set(db.patchlist_base) | set(db.patchlist_script)
    owned = [item for item in patch_list if item not in inherited]
    expected_owned = (
        [feature.source_option, "MugshotAssembly"]
        if feature.kind == "mugshot"
        else [feature.source_option]
    )
    if patchfile != "b01" or owned != expected_owned:
        raise AssertionError(
            f"{feature.source_option}={variant.source_value!r} closure "
            f"changed: patchfile={patchfile!r}, owned={owned!r}"
        )
    expected_synth = (
        {"MugshotAssembly"}
        if feature.kind == "mugshot"
        else {feature.source_option}
    )
    if set(synth) != expected_synth:
        raise AssertionError(
            f"{feature.source_option}={variant.source_value!r} synthesized "
            f"{sorted(synth)!r}, expected {sorted(expected_synth)!r}"
        )
    file_patch, files = engine.build_filelist(db, merged, base)
    if file_patch != "b01":
        raise AssertionError("asset file list unexpectedly left B01")
    expected_files = 46 if feature.source_option == "MugshotCustom03" else (
        2 if feature.kind == "mugshot" else 0
    )
    if len(files) != expected_files:
        raise AssertionError(
            f"{feature.source_option}={variant.source_value!r} emitted "
            f"{len(files)} files, expected {expected_files}"
        )
    return normalized, patchfile, owned, synth, files


def _make_overlay(
    stock: DatView,
    b01: DatView,
    feature: Feature,
    variant: Variant,
    identity: DatIdentity,
    replacement: bytes,
    operation_kind: str,
    source_raw_offset: int,
    source_file: str = "",
    label_suffix: str = "",
) -> AssetOverlay:
    expected, user_offset, _file_offset = stock.expected_and_offset(identity)
    source_expected, _source_offset, _source_file_offset = (
        b01.expected_and_offset(identity)
    )
    if expected != source_expected:
        raise AssertionError(
            f"{feature.feature_id}/{identity.label()} differs between stock "
            "and the B01 source base"
        )
    if len(expected) != len(replacement):
        raise AssertionError("overlay guard and replacement sizes differ")
    if expected == replacement:
        raise AssertionError(
            f"{feature.feature_id}/{identity.label()} is a stock no-op"
        )
    suffix = f"-{label_suffix}" if label_suffix else ""
    return AssetOverlay(
        feature.feature_id,
        variant.value,
        f"{variant.value}-{identity.label()}{suffix}",
        identity,
        user_offset,
        expected,
        replacement,
        operation_kind,
        feature.source_option,
        variant.source_value,
        source_raw_offset,
        source_file,
    )


def _build_mugshot_variant(
    stock: DatView,
    b01: DatView,
    db,
    base: dict,
    feature: Feature,
    variant: Variant,
) -> tuple[list[AssetOverlay], dict]:
    _normalized, _patchfile, owned, synth, files = _assemble_variant(
        db, base, feature, variant
    )
    overlays: list[AssetOverlay] = []
    file_evidence = []
    for file_var, source, raw_offset in files:
        source_path = Path(source)
        native.require_file(source_path, f"{feature.name} source asset")
        replacement = source_path.read_bytes()
        identity = b01.source_identity(raw_offset, len(replacement))
        if feature.allowed_asset_records:
            if identity.record_id not in feature.allowed_asset_records:
                raise AssertionError(
                    f"{feature.feature_id} asset escaped records "
                    f"{feature.allowed_asset_records}: {identity}"
                )
            if identity.subasset_index is not None or identity.relative_offset:
                raise AssertionError(
                    f"{feature.feature_id} expected a complete DAT record"
                )
        else:
            if feature.source_option != "MugshotCustom03":
                raise AssertionError("only Alia may use subasset fan-out")
            if identity.asset_type not in (0x1060D, 0x1A):
                raise AssertionError(
                    f"Alia asset has unexpected type {identity.asset_type}"
                )
            if identity.relative_offset != 0:
                raise AssertionError("Alia asset does not begin at subasset 0")
        overlay = _make_overlay(
            stock,
            b01,
            feature,
            variant,
            identity,
            replacement,
            "mugshot_asset",
            raw_offset,
            str(source_path),
            file_var.lower(),
        )
        overlays.append(overlay)
        file_evidence.append(
            {
                "file_var": file_var,
                "source": _logical_asset_source(source_path),
                "source_sha256": sha256(replacement),
                "source_raw_offset": raw_offset,
                "identity": _identity_json(identity),
            }
        )

    reference_fields = []
    ignored_padding_bytes = 0
    for replacement_hex, raw_offset in synth["MugshotAssembly"]:
        replacement = bytes.fromhex(replacement_hex)
        (
            whole_identity,
            source_expected,
            replacement,
            ignored,
        ) = _semantic_mugshot_write(b01, raw_offset, replacement)
        ignored_padding_bytes += ignored
        changed_fields = sorted(
            {
                index & ~1
                for index, pair in enumerate(
                    zip(source_expected, replacement)
                )
                if pair[0] != pair[1]
            }
        )
        for field_offset in changed_fields:
            if field_offset + 2 > len(replacement):
                raise AssertionError("mugshot reference field is truncated")
            identity = DatIdentity(
                whole_identity.record_id,
                whole_identity.subasset_index,
                whole_identity.asset_type,
                whole_identity.relative_offset + field_offset,
                2,
            )
            overlay = _make_overlay(
                stock,
                b01,
                feature,
                variant,
                identity,
                replacement[field_offset : field_offset + 2],
                "mugshot_reference",
                raw_offset,
                label_suffix="tile-reference",
            )
            overlays.append(overlay)
            reference_fields.append(_identity_json(identity))

    if feature.source_option in (
        "MugshotCustom03",
        "MugshotCustom12",
        "MugshotCustom13",
        "MugshotCustom14",
    ) and reference_fields:
        raise AssertionError(
            f"{feature.source_option} unexpectedly changes animation references"
        )
    return overlays, {
        "source_option": feature.source_option,
        "source_value": variant.source_value,
        "source_closure": owned,
        "file_inserts": file_evidence,
        "narrow_type18_reference_fields": reference_fields,
        "source_mugshot_assembly_bytes_replayed": 0,
        "unowned_alignment_padding_bytes_omitted": ignored_padding_bytes,
    }


def _build_palette_variant(
    stock: DatView,
    b01: DatView,
    db,
    base: dict,
    feature: Feature,
    variant: Variant,
) -> tuple[list[AssetOverlay], dict]:
    _normalized, _patchfile, owned, synth, _files = _assemble_variant(
        db, base, feature, variant
    )
    overlays: list[AssetOverlay] = []
    source_payload_bytes = 0
    changed_bytes = 0
    changed_runs = 0
    identities = []
    for replacement_hex, raw_offset in synth[feature.source_option]:
        replacement = bytes.fromhex(replacement_hex)
        source_expected = b01.read_source(raw_offset, len(replacement))
        whole_identity = b01.source_identity(raw_offset, len(replacement))
        if whole_identity.asset_type not in (0x5, 0x9, 0xD):
            raise AssertionError(
                f"{feature.source_option} left reviewed palette types: "
                f"{whole_identity}"
            )
        source_payload_bytes += len(replacement)
        for relative, size in _maximal_changed_runs(
            source_expected, replacement
        ):
            identity = DatIdentity(
                whole_identity.record_id,
                whole_identity.subasset_index,
                whole_identity.asset_type,
                whole_identity.relative_offset + relative,
                size,
            )
            overlay = _make_overlay(
                stock,
                b01,
                feature,
                variant,
                identity,
                replacement[relative : relative + size],
                "palette_changed_run",
                raw_offset,
                label_suffix="palette",
            )
            overlays.append(overlay)
            changed_bytes += size
            changed_runs += 1
            identities.append(_identity_json(identity))
    if not overlays:
        raise AssertionError(
            f"{feature.source_option}={variant.source_value!r} is a no-op"
        )
    return overlays, {
        "source_option": feature.source_option,
        "source_value": variant.source_value,
        "source_closure": owned,
        "source_payload_bytes": source_payload_bytes,
        "emitted_changed_bytes": changed_bytes,
        "emitted_changed_runs": changed_runs,
        "stock_identical_bytes_omitted": source_payload_bytes - changed_bytes,
        "identities": identities,
    }


def _identity_json(identity: DatIdentity) -> dict:
    return {
        "record_id": identity.record_id,
        "subasset_index": identity.subasset_index,
        "asset_type": identity.asset_type,
        "relative_offset": identity.relative_offset,
        "size": identity.size,
    }


def _logical_asset_source(path: Path) -> str:
    data_root = engine.twr.DEFAULT_RUN_EXTRACTED / "data"
    try:
        return path.absolute().relative_to(data_root.absolute()).as_posix()
    except ValueError:
        return path.name


def _validate_no_product_overlap(overlays: list[AssetOverlay]) -> None:
    ordered = sorted(
        overlays,
        key=lambda item: (
            item.user_offset,
            len(item.expected),
            item.feature,
            item.variant,
            item.label,
        ),
    )
    for index, left in enumerate(ordered):
        left_end = left.user_offset + len(left.expected)
        for right in ordered[index + 1 :]:
            if right.user_offset >= left_end:
                break
            right_end = right.user_offset + len(right.expected)
            if left.user_offset >= right_end:
                continue
            same_choice_domain = (
                left.feature == right.feature
                and left.variant != right.variant
            )
            if not same_choice_domain:
                raise AssertionError(
                    f"incompatible asset overlap: {left.feature}/"
                    f"{left.variant}/{left.label} and {right.feature}/"
                    f"{right.variant}/{right.label}"
                )


def _validate_current_feature_boundaries(
    overlays: list[AssetOverlay],
) -> dict:
    title_conflicts = []
    retranslation_conflicts = []
    for overlay in overlays:
        identity = overlay.identity
        owner = (identity.record_id, identity.subasset_index)
        if owner in TITLE_OWNERS:
            title_conflicts.append(overlay.label)
        if (
            identity.record_id in RETRANSLATION_WHOLE_RECORDS
            or owner in RETRANSLATION_SUBASSET_OWNERS
        ):
            retranslation_conflicts.append(overlay.label)
    if title_conflicts or retranslation_conflicts:
        raise AssertionError(
            "asset slice crosses existing feature ownership: "
            f"title={title_conflicts}, retranslation={retranslation_conflicts}"
        )
    return {
        "title_screen_overlap_operations": 0,
        "retranslation_overlap_operations": 0,
        "title_owners_checked": [
            {"record_id": record, "subasset_index": subasset}
            for record, subasset in sorted(TITLE_OWNERS)
        ],
        "retranslation_whole_records_checked": sorted(
            RETRANSLATION_WHOLE_RECORDS
        ),
        "retranslation_subassets_checked": [
            {"record_id": record, "subasset_index": subasset}
            for record, subasset in sorted(
                RETRANSLATION_SUBASSET_OWNERS
            )
        ],
    }


def _selected_overlays(
    overlays: list[AssetOverlay], selection: dict[str, str]
) -> list[AssetOverlay]:
    return [
        item
        for item in overlays
        if item.variant == selection[item.feature]
    ]


def _combination_proof(
    label: str,
    selection: dict[str, str],
    overlays: list[AssetOverlay],
    db,
    base: dict,
    b01: DatView,
) -> dict:
    selected = _selected_overlays(overlays, selection)
    _validate_no_product_overlap(selected)

    merged = dict(base)
    expected_owned = []
    for feature in FEATURES:
        variant = next(
            item
            for item in feature.variants
            if item.value == selection[feature.feature_id]
        )
        merged[feature.source_option] = variant.source_value
        expected_owned.append(feature.source_option)
    _normalized, patchfile, patch_list, _values, synth = engine._assemble(
        db, merged, base
    )
    inherited = set(db.patchlist_base) | set(db.patchlist_script)
    owned = [item for item in patch_list if item not in inherited]
    if patchfile != "b01":
        raise AssertionError(f"{label} combination left B01")
    allowed_owned = set(expected_owned) | {"MugshotAssembly"}
    if set(owned) != allowed_owned or len(owned) != len(allowed_owned):
        raise AssertionError(
            f"{label} combination has hidden closure: {owned!r}"
        )
    expected_synth = {
        "MugshotAssembly",
        "SpritePalette01",
        "SpritePalette02",
    }
    if set(synth) != expected_synth:
        raise AssertionError(
            f"{label} combination synthesized {sorted(synth)!r}"
        )

    selected_reference_keys = {
        (
            item.identity.record_id,
            item.identity.subasset_index,
            item.identity.asset_type,
            item.identity.relative_offset,
            item.replace,
        )
        for item in selected
        if item.operation_kind == "mugshot_reference"
    }
    combined_reference_keys = set()
    for replacement_hex, raw_offset in synth["MugshotAssembly"]:
        replacement = bytes.fromhex(replacement_hex)
        whole, expected, replacement, _ignored = _semantic_mugshot_write(
            b01, raw_offset, replacement
        )
        for field_offset in sorted(
            {
                index & ~1
                for index, pair in enumerate(zip(expected, replacement))
                if pair[0] != pair[1]
            }
        ):
            combined_reference_keys.add(
                (
                    whole.record_id,
                    whole.subasset_index,
                    whole.asset_type,
                    whole.relative_offset + field_offset,
                    replacement[field_offset : field_offset + 2],
                )
            )
    if selected_reference_keys != combined_reference_keys:
        missing = combined_reference_keys - selected_reference_keys
        extra = selected_reference_keys - combined_reference_keys
        raise AssertionError(
            f"{label} MugshotAssembly decomposition changed: "
            f"missing={len(missing)}, extra={len(extra)}"
        )
    return {
        "label": label,
        "selection": selection,
        "source_owned_controls": sorted(expected_owned),
        "source_synthesis": sorted(synth),
        "selected_overlay_operations": len(selected),
        "selected_overlay_bytes": sum(
            len(item.replace) for item in selected
        ),
        "mugshot_reference_union_exact": True,
        "hidden_source_closure_count": 0,
        "incompatible_overlap_count": 0,
    }


def _validate_disabled_is_stock(db, base: dict) -> None:
    merged = dict(base)
    patchfile, patch_list, synth = engine.build_patchlist(db, merged, base)
    if patchfile or patch_list or synth:
        raise AssertionError(
            "the unmodified Tweaks profile unexpectedly emits a patch plan"
        )


def build_assets(
    stock_image: native.RawMode2Image,
    b01_image: native.RawMode2Image,
    stock_path: Path,
    b01_path: Path,
) -> tuple[list[AssetOverlay], dict]:
    actual_stock_hash = file_sha256(stock_path)
    if actual_stock_hash != native.STOCK_SHA256:
        raise AssertionError(
            f"stock SHA-256 is {actual_stock_hash}, expected "
            f"{native.STOCK_SHA256}"
        )
    stock = DatView(stock_image)
    b01 = DatView(b01_image)
    db, base = _profile_context()
    _validate_disabled_is_stock(db, base)

    overlays: list[AssetOverlay] = []
    feature_reports = []
    for feature in FEATURES:
        variants = []
        for variant in feature.variants:
            if feature.kind == "mugshot":
                variant_overlays, evidence = _build_mugshot_variant(
                    stock, b01, db, base, feature, variant
                )
            elif feature.kind == "palette":
                variant_overlays, evidence = _build_palette_variant(
                    stock, b01, db, base, feature, variant
                )
            else:
                raise AssertionError(f"unknown feature kind {feature.kind}")
            overlays.extend(variant_overlays)
            evidence["overlay_operations"] = len(variant_overlays)
            evidence["overlay_bytes"] = sum(
                len(item.replace) for item in variant_overlays
            )
            variants.append(evidence)
        feature_reports.append(
            {
                "feature_id": feature.feature_id,
                "name": feature.name,
                "source_option": feature.source_option,
                "disabled_behavior": "stock",
                "variant_count": len(feature.variants),
                "variants": variants,
            }
        )

    _validate_no_product_overlap(overlays)
    boundary_report = _validate_current_feature_boundaries(overlays)
    first_selection = {
        feature.feature_id: feature.variants[0].value
        for feature in FEATURES
    }
    last_selection = {
        feature.feature_id: feature.variants[-1].value
        for feature in FEATURES
    }
    combinations = [
        _combination_proof(
            "first-choice",
            first_selection,
            overlays,
            db,
            base,
            b01,
        ),
        _combination_proof(
            "last-choice",
            last_selection,
            overlays,
            db,
            base,
            b01,
        ),
    ]

    fingerprint_input = [
        (
            item.feature,
            item.variant,
            item.identity.key,
            sha256(item.expected),
            sha256(item.replace),
        )
        for item in overlays
    ]
    report = {
        "source_controls": sorted(
            feature.source_option for feature in FEATURES
        ),
        "package": {
            "id": PACKAGE_ID,
            "version": PACKAGE_VERSION,
            "feature_count": len(FEATURES),
            "mugshot_feature_count": 12,
            "palette_feature_count": 2,
            "source_control_count": 14,
            "non_stock_variant_count": sum(
                len(item.variants) for item in FEATURES
            ),
        },
        "provenance": {
            "game_id": native.GAME_ID,
            "stock_input": "Mega Man X6 USA v1.1 MODE2/2352 BIN",
            "stock_sha256": actual_stock_hash,
            "b01_input": "MMX6 Tweaks v2.6.1 B01 base oracle",
            "b01_sha256": file_sha256(b01_path),
            "patcher_version": "MMX6 Tweaks v2.6.1",
            "patcher_dat_sha256": file_sha256(
                engine.twr.DEFAULT_PATCHER_SRC / "data" / "_dat.ahk"
            ),
            "patcher_exception_a_sha256": file_sha256(
                engine.twr.DEFAULT_PATCHER_SRC
                / "_patch"
                / "exception_a.ahk"
            ),
            "default_profile_sha256": file_sha256(
                engine.twr.DEFAULT_PROFILE
            ),
            "converter_source_sha256": file_sha256(
                Path(__file__.replace("\\", "/")).absolute()
            ),
            "converter_command": (
                "tools/tweaks_assets_psxmod.py --stock <stock-v1.1.bin> "
                "--b01-base <b01-base.bin> --out <package.psxmod>"
            ),
        },
        "features": feature_reports,
        "operations": {
            "overlay_operations": len(overlays),
            "overlay_bytes": sum(len(item.replace) for item in overlays),
            "mugshot_assembly_source_bytes_replayed": 0,
            "main_exe_patch_operations": 0,
            "new_dat_record_operations": 0,
            "plan_fingerprint": sha256(
                json.dumps(
                    fingerprint_input, separators=(",", ":")
                ).encode()
            ),
        },
        "validation": {
            "disabled_is_stock": True,
            "all_variant_source_closures_exact": True,
            "stock_guards_verified": True,
            "logical_record_subasset_mapping": True,
            "stock_identical_palette_bytes_omitted": True,
            "incompatible_internal_overlap_operations": 0,
            **boundary_report,
            "representative_combinations": combinations,
        },
        "deferred": DEFERRED,
    }
    return overlays, report


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_manifest(
    overlays: list[AssetOverlay],
    asset_paths: dict[int, str],
    package_version: str,
) -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(package_version)}",
        f"name = {q(PACKAGE_NAME)}",
        'author = "acediez, Metalwario64"',
        (
            'description = "Independent stock-disc portrait and palette '
            'replacements from MMX6 Tweaks."'
        ),
        'license = "Generated locally; original credits retained"',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        'source_name = "Mega Man X6 Tweaks"',
        'source_url = "https://www.romhacking.net/hacks/4035/"',
        "",
        "[[author_link]]",
        'name = "acediez"',
        'url = "https://twitter.com/acediez"',
        "[[author_link]]",
        'name = "Metalwario64"',
        'url = "https://x.com/metalwario64"',
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
            f"description = {q(feature.description)}",
            f"group = {q(feature.group)}",
            "default_enabled = false",
        ]
        if len(feature.variants) > 1:
            lines += [
                "",
                "[[option]]",
                f"feature = {q(feature.feature_id)}",
                'id = "variant"',
                'label = "Variant"',
                f"description = {q(feature.description)}",
                f"group = {q(feature.group)}",
                'type = "choice"',
                f"default = {q(feature.variants[0].value)}",
            ]
            for variant in feature.variants:
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(variant.value)}",
                    f"label = {q(variant.label)}",
                ]
    for index, overlay in enumerate(overlays):
        lines += [
            "",
            "[[overlay]]",
            f"feature = {q(overlay.feature)}",
            'target = "disc_user"',
            f"offset = {overlay.user_offset}",
            f"file = {q(asset_paths[index])}",
            f"sha256 = {q(sha256(overlay.replace))}",
            f"expected_sha256 = {q(sha256(overlay.expected))}",
            "order = 0",
        ]
        if overlay.when is not None:
            lines.append(
                f"when = {{ {overlay.when[0]} = "
                f"{q(overlay.when[1])} }}"
            )
    return "\n".join(lines) + "\n"


def _archive_member(
    archive: zipfile.ZipFile, name: str, payload: bytes | str
) -> None:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(
        info, payload.encode("utf-8") if isinstance(payload, str) else payload
    )


def write_package(
    output: Path,
    overlays: list[AssetOverlay],
    report: dict,
    package_version: str,
) -> None:
    asset_paths = {
        index: f"assets/payloads/{sha256(overlay.replace)}.bin"
        for index, overlay in enumerate(overlays)
    }
    manifest = build_manifest(overlays, asset_paths, package_version)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        _archive_member(archive, "manifest.toml", manifest)
        written_payloads: dict[str, bytes] = {}
        for index, overlay in enumerate(overlays):
            path = asset_paths[index]
            previous = written_payloads.get(path)
            if previous is not None:
                if previous != overlay.replace:
                    raise AssertionError(
                        f"payload hash collision at {path}"
                    )
                continue
            _archive_member(archive, path, overlay.replace)
            written_payloads[path] = overlay.replace
        _archive_member(
            archive,
            "conversion-report.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        _archive_member(
            archive,
            "README.txt",
            (
                "Generated locally from a verified stock Mega Man X6 v1.1 "
                "disc and a user-supplied MMX6 Tweaks v2.6.1 extraction.\n"
                "Disabled features leave the immutable stock disc unchanged. "
                "The package contains no derived disc image.\n"
            ),
        )


def inspect_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names[0] != "manifest.toml":
            raise AssertionError("manifest.toml is not the first archive member")
        manifest = tomllib.loads(
            archive.read("manifest.toml").decode("utf-8")
        )
        if manifest["id"] != PACKAGE_ID:
            raise AssertionError("generated package ID changed")
        if len(manifest.get("feature", [])) != len(FEATURES):
            raise AssertionError("generated feature count changed")
        if manifest.get("patch"):
            raise AssertionError("asset package unexpectedly contains patches")
        for overlay in manifest.get("overlay", []):
            payload = archive.read(overlay["file"])
            if sha256(payload) != overlay["sha256"]:
                raise AssertionError(
                    f"payload hash mismatch for {overlay['file']}"
                )
        return {
            "archive_members": len(names),
            "feature_count": len(manifest.get("feature", [])),
            "option_count": len(manifest.get("option", [])),
            "overlay_count": len(manifest.get("overlay", [])),
        }


def deterministic_write_check(
    output: Path,
    overlays: list[AssetOverlay],
    report: dict,
    package_version: str,
) -> str:
    write_package(output, overlays, report, package_version)
    first = output.read_bytes()
    with tempfile.TemporaryDirectory(prefix="mmx6-assets-") as directory:
        repeat = Path(directory) / output.name
        write_package(repeat, overlays, report, package_version)
        second = repeat.read_bytes()
    if first != second:
        raise AssertionError("package archive rebuild is not deterministic")
    return sha256(first)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=native.DEFAULT_STOCK)
    parser.add_argument(
        "--b01-base",
        type=Path,
        default=native.DEFAULT_ORACLE_DIR / "base.bin",
        help="local B01 source-layout oracle; never packaged",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build-mod-platform/test-psxmods")
        / "MMX6-Tweaks-Assets.psxmod",
    )
    parser.add_argument("--package-version", default=PACKAGE_VERSION)
    parser.add_argument(
        "--report-out",
        type=Path,
        help="optional standalone copy of conversion-report.json",
    )
    args = parser.parse_args()

    native.require_file(args.stock, "stock Mega Man X6 v1.1 BIN")
    native.require_file(args.b01_base, "MMX6 Tweaks B01 base oracle")
    with native.RawMode2Image(args.stock) as stock_image, (
        native.RawMode2Image(args.b01_base)
    ) as b01_image:
        overlays, report = build_assets(
            stock_image,
            b01_image,
            args.stock,
            args.b01_base,
        )
    report["package"]["version"] = args.package_version
    archive_hash = deterministic_write_check(
        args.out,
        overlays,
        report,
        args.package_version,
    )
    inspection = inspect_package(args.out)
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
                "sha256": archive_hash,
                "overlay_bytes": report["operations"]["overlay_bytes"],
                **inspection,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
