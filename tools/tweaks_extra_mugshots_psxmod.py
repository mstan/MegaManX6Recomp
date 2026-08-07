#!/usr/bin/env python3
"""Build the MMX6 Tweaks Hunter and Dr. Light mugshot package."""

from __future__ import annotations

import argparse
import hashlib
import json
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

import tweaks_assets_psxmod as assets
import tweaks_engine as engine
import tweaks_native_psxmod as native


PACKAGE_ID = "mmx6.tweaks.extra-mugshots"
PACKAGE_VERSION = "1.0.0"
PACKAGE_NAME = "Mega Man X6 Tweaks — Hunter and Dr. Light Mugshots"
RESERVED_BASE_SECTOR = 0x03DED000 // native.USER_SECTOR
RESERVED_LOGICAL_SIZE = 0x0422F800
LOGICAL_SIZE_OFFSET = 0xB0A6


@dataclass(frozen=True)
class Variant:
    value: str
    label: str
    source_value: str


@dataclass(frozen=True)
class Feature:
    feature_id: str
    name: str
    source_option: str
    records: tuple[int, int]
    variants: tuple[Variant, ...] = (
        Variant("custom_a", "Custom A", "Custom A"),
        Variant("custom_b", "Custom B", "Custom B"),
    )


@dataclass(frozen=True)
class Overlay:
    feature: str
    variant: str
    label: str
    user_offset: int
    expected: bytes
    replace: bytes
    operation_kind: str

    @property
    def when(self) -> tuple[str, str]:
        return ("variant", self.variant)


FEATURES = (
    Feature("mugshot_hunter", "Hunter Mugshot", "MugshotCustom01", (243, 244)),
    Feature("mugshot_dr_light", "Dr. Light Mugshot", "MugshotCustom02", (245, 246)),
)


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def logical_size_bytes(size: int) -> bytes:
    return struct.pack("<I", size) + struct.pack(">I", size)


def allocated_records() -> dict[int, tuple[int, int]]:
    return {
        243: (RESERVED_BASE_SECTOR, 8192),
        244: (RESERVED_BASE_SECTOR + 4, 512),
        245: (RESERVED_BASE_SECTOR + 5, 8192),
        246: (RESERVED_BASE_SECTOR + 9, 512),
    }


def assemble_variant(db, base: dict, feature: Feature, variant: Variant):
    merged = dict(base)
    merged[feature.source_option] = variant.source_value
    normalized, patchfile, patch_list, values, synth = engine._assemble(
        db, merged, base
    )
    inherited = set(db.patchlist_base) | set(db.patchlist_script)
    owned = [item for item in patch_list if item not in inherited]
    expected_owned = [feature.source_option, "MugshotAssembly"]
    if patchfile != "b01" or owned != expected_owned:
        raise AssertionError(
            f"{feature.source_option}/{variant.value} source closure changed: "
            f"{patchfile=} {owned=}"
        )
    _file_patch, files = engine.build_filelist(db, merged, base)
    if len(files) != 2:
        raise AssertionError(
            f"{feature.source_option}/{variant.value} file insert count changed"
        )
    return normalized, synth, files


def reference_overlays(
    stock: assets.DatView,
    b01: assets.DatView,
    feature: Feature,
    variant: Variant,
    synth: dict,
) -> tuple[list[Overlay], list[dict]]:
    overlays: list[Overlay] = []
    evidence: list[dict] = []
    for replacement_hex, raw_offset in synth["MugshotAssembly"]:
        replacement = bytes.fromhex(replacement_hex)
        whole, source_expected, replacement, ignored = assets._semantic_mugshot_write(
            b01, raw_offset, replacement
        )
        if ignored:
            raise AssertionError("Hunter/Dr. Light references unexpectedly spill")
        changed_fields = sorted(
            {
                index & ~1
                for index, pair in enumerate(zip(source_expected, replacement))
                if pair[0] != pair[1]
            }
        )
        for field_offset in changed_fields:
            identity = assets.DatIdentity(
                whole.record_id,
                whole.subasset_index,
                whole.asset_type,
                whole.relative_offset + field_offset,
                2,
            )
            expected, user_offset, _file_offset = stock.expected_and_offset(identity)
            replace = replacement[field_offset : field_offset + 2]
            overlays.append(
                Overlay(
                    feature.feature_id,
                    variant.value,
                    (
                        f"record-{identity.record_id:03d}-subasset-"
                        f"{identity.subasset_index:02d}-tile-reference-"
                        f"{identity.relative_offset:06x}"
                    ),
                    user_offset,
                    expected,
                    replace,
                    "mugshot_reference",
                )
            )
            evidence.append(assets._identity_json(identity))
    return overlays, evidence


def record_overlays(
    stock_image: native.RawMode2Image,
    feature: Feature,
    variant: Variant,
    files: list[tuple[str, str, int]],
) -> tuple[list[Overlay], list[dict]]:
    stock_dat_start = stock_image.entries["ROCK_X6.DAT"].lba * native.USER_SECTOR
    records = allocated_records()
    overlays: list[Overlay] = []
    evidence: list[dict] = []
    for index, (file_var, file_path, _raw_offset) in enumerate(files):
        record_id = feature.records[index]
        sector, size = records[record_id]
        payload = Path(file_path).read_bytes()
        if len(payload) != size:
            raise AssertionError(f"{file_var} payload size changed")
        table_offset = stock_dat_start + record_id * 8
        table_replace = struct.pack("<II", sector, size)
        overlays.append(
            Overlay(
                feature.feature_id,
                variant.value,
                f"record-{record_id:03d}-table",
                table_offset,
                b"\x00" * 8,
                table_replace,
                "new_record_table",
            )
        )
        payload_offset = stock_dat_start + sector * native.USER_SECTOR
        expected = stock_image.read_user(payload_offset, len(payload))
        overlays.append(
            Overlay(
                feature.feature_id,
                variant.value,
                f"record-{record_id:03d}-payload",
                payload_offset,
                expected,
                payload,
                "new_record_payload",
            )
        )
        evidence.append(
            {
                "record_id": record_id,
                "sector": sector,
                "size": size,
                "source": assets._logical_asset_source(Path(file_path)),
                "sha256": sha256(payload),
            }
        )
    stock_size = stock_image.read_user(LOGICAL_SIZE_OFFSET, 8)
    overlays.append(
        Overlay(
            feature.feature_id,
            variant.value,
            "rock-x6-dat-logical-size",
            LOGICAL_SIZE_OFFSET,
            stock_size,
            logical_size_bytes(RESERVED_LOGICAL_SIZE),
            "logical_dat_size",
        )
    )
    return overlays, evidence


def validate_overlaps(overlays: list[Overlay]) -> dict:
    selected_domains = {
        (item.feature, item.variant) for item in overlays
    }
    for feature, variant in selected_domains:
        selected = [
            item
            for item in overlays
            if item.variant == variant or item.feature != feature
        ]
        ordered = sorted(
            selected,
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
                same_choice_domain = (
                    left.feature == right.feature
                    and left.variant != right.variant
                )
                if same_choice_domain:
                    continue
                begin = max(left.user_offset, right.user_offset)
                end = min(left_end, right.user_offset + len(right.expected))
                left_replace = left.replace[
                    begin - left.user_offset : end - left.user_offset
                ]
                right_replace = right.replace[
                    begin - right.user_offset : end - right.user_offset
                ]
                if left_replace != right_replace:
                    raise AssertionError(
                        f"mugshot overlap: {left.feature}/{left.label} vs "
                        f"{right.feature}/{right.label}"
                    )
    return {"incompatible_internal_overlap_operations": 0}


def build_package_data(
    stock_path: Path,
    b01_path: Path,
) -> tuple[list[Overlay], dict]:
    if file_sha256(stock_path) != native.STOCK_SHA256:
        raise AssertionError("stock disc SHA-256 does not match USA v1.1")
    db = engine.twr.TweaksDB(engine.twr.DEFAULT_PATCHER_SRC)
    base = engine.twr.load_profile(engine.twr.DEFAULT_PROFILE)
    overlays: list[Overlay] = []
    feature_reports: dict[str, dict] = {}
    with native.RawMode2Image(stock_path) as stock_image, native.RawMode2Image(
        b01_path
    ) as b01_image:
        stock = assets.DatView(stock_image)
        b01 = assets.DatView(b01_image)
        for feature in FEATURES:
            variants = {}
            for variant in feature.variants:
                _normalized, synth, files = assemble_variant(
                    db, base, feature, variant
                )
                ref_overlays, refs = reference_overlays(
                    stock, b01, feature, variant, synth
                )
                rec_overlays, records = record_overlays(
                    stock_image, feature, variant, files
                )
                overlays.extend(ref_overlays)
                overlays.extend(rec_overlays)
                variants[variant.value] = {
                    "source_value": variant.source_value,
                    "new_records": records,
                    "reference_fields": refs,
                    "overlay_operations": len(ref_overlays) + len(rec_overlays),
                }
            feature_reports[feature.feature_id] = {
                "source_control": feature.source_option,
                "variants": variants,
            }
    validation = validate_overlaps(overlays)
    report = {
        "source_controls": [feature.source_option for feature in FEATURES],
        "package": {
            "id": PACKAGE_ID,
            "version": PACKAGE_VERSION,
            "feature_count": len(FEATURES),
            "reserved_base_sector": RESERVED_BASE_SECTOR,
            "reserved_logical_size": RESERVED_LOGICAL_SIZE,
        },
        "features": feature_reports,
        "operations": {
            "overlay_operations": len(overlays),
            "overlay_bytes": sum(len(item.replace) for item in overlays),
            "new_dat_record_operations": sum(
                1 for item in overlays if item.operation_kind.startswith("new_record")
            ),
            "logical_size_operations": sum(
                1 for item in overlays if item.operation_kind == "logical_dat_size"
            ),
            "plan_fingerprint": sha256(
                json.dumps(
                    [
                        (
                            item.feature,
                            item.variant,
                            item.user_offset,
                            sha256(item.expected),
                            sha256(item.replace),
                        )
                        for item in overlays
                    ],
                    separators=(",", ":"),
                ).encode()
            ),
        },
        "validation": {
            "stock_guards_verified": True,
            "disabled_is_stock": True,
            "uses_native_retranslation_reserved_extent": True,
            **validation,
        },
        "provenance": {
            "stock_sha256": file_sha256(stock_path),
            "b01_sha256": file_sha256(b01_path),
            "patcher_dat_sha256": file_sha256(
                engine.twr.DEFAULT_PATCHER_SRC / "data" / "_dat.ahk"
            ),
            "default_profile_sha256": file_sha256(engine.twr.DEFAULT_PROFILE),
        },
    }
    return overlays, report


def build_manifest(overlays: list[Overlay], asset_paths: dict[int, str]) -> str:
    lines = [
        "format_version = 1",
        f"id = {q(PACKAGE_ID)}",
        f"version = {q(PACKAGE_VERSION)}",
        f"name = {q(PACKAGE_NAME)}",
        'author = "acediez, Metalwario64"',
        (
            'description = "Adds Hunter and Dr. Light custom mugshots using '
            'the native Retranslation reserved DAT extent."'
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
            'description = "Replace this dialogue portrait."',
            'group = "Portraits"',
            "default_enabled = false",
            "",
            "[[option]]",
            f"feature = {q(feature.feature_id)}",
            'id = "variant"',
            'label = "Variant"',
            'description = "Choose the replacement portrait variant."',
            'group = "Portraits"',
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
            f"when = {{ {overlay.when[0]} = {q(overlay.when[1])} }}",
        ]
    return "\n".join(lines) + "\n"


def archive_member(archive: zipfile.ZipFile, name: str, payload: bytes | str) -> None:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(
        info, payload.encode("utf-8") if isinstance(payload, str) else payload
    )


def write_package(output: Path, overlays: list[Overlay], report: dict) -> None:
    asset_paths = {
        index: f"assets/payloads/{sha256(overlay.replace)}.bin"
        for index, overlay in enumerate(overlays)
    }
    manifest = build_manifest(overlays, asset_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive_member(archive, "manifest.toml", manifest)
        written: dict[str, bytes] = {}
        for index, overlay in enumerate(overlays):
            path = asset_paths[index]
            if path in written:
                if written[path] != overlay.replace:
                    raise AssertionError(f"payload hash collision at {path}")
                continue
            archive_member(archive, path, overlay.replace)
            written[path] = overlay.replace
        archive_member(
            archive,
            "conversion-report.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        archive_member(
            archive,
            "README.txt",
            "Generated locally from verified MMX6 Tweaks mugshot assets. "
            "Disabled features leave the immutable stock disc unchanged.\n",
        )


def inspect_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        manifest = tomllib.loads(archive.read("manifest.toml").decode("utf-8"))
        if manifest["id"] != PACKAGE_ID:
            raise AssertionError("generated package ID changed")
        return {
            "feature_count": len(manifest.get("feature", [])),
            "option_count": len(manifest.get("option", [])),
            "overlay_count": len(manifest.get("overlay", [])),
            "archive_members": len(archive.namelist()),
        }


def deterministic_write_check(output: Path, overlays: list[Overlay], report: dict) -> str:
    write_package(output, overlays, report)
    first = output.read_bytes()
    with tempfile.TemporaryDirectory(prefix="mmx6-extra-mugshots-") as directory:
        repeat = Path(directory) / Path(str(output).replace("\\", "/")).name
        write_package(repeat, overlays, report)
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
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build-mod-platform/test-psxmods")
        / "MMX6-Tweaks-Extra-Mugshots.psxmod",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    overlays, report = build_package_data(args.stock, args.b01_base)
    if not args.verify_only:
        archive_sha = deterministic_write_check(args.out, overlays, report)
        report["archive"] = {
            "sha256": archive_sha,
            **inspect_package(args.out),
        }
        write_package(args.out, overlays, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.verify_only:
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
