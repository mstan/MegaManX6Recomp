#!/usr/bin/env python3
"""Convert reviewed MMX6 Tweaks features to native stock-disc .psxmods.

This is deliberately fail-closed.  A feature is emitted only after its Tweaks
changes have been assigned to stable stock-disc ranges or guarded executable
operations.  Reference patched images are conversion oracles, never runtime
payloads.

The current reviewed slice contains Title Screen -> Rockman X6 (Japan) and the
English Retranslation. The latter is converted as logical ROCK_X6.DAT records,
not as the s02 rebuilt container, and includes only its owned
ScriptTextDisplay/ScriptMenuAlign executable edits.
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

RAW_SECTOR = 2352
USER_SECTOR = 2048
USER_HEADER = 24
GAME_ID = "SLUS-01395"
SLUS_NAME = "SLUS_013.95"
STOCK_SHA256 = (
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318"
)

ROOT = Path(__file__).absolute().parent.parent
MAIN_CHECKOUT = ROOT.parent / "MegaManX6Recomp"


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


DEFAULT_TWEAKS = first_existing(
    MAIN_CHECKOUT / "mmx6-tweaks",
    ROOT / "mmx6-tweaks",
)
DEFAULT_STOCK = DEFAULT_TWEAKS / "Mega Man X6 (USA) (v1.1).bin"
DEFAULT_ORACLE_DIR = ROOT / "build-mod-platform" / "test-mod-variants"
DEFAULT_PATCHER_DATA = DEFAULT_TWEAKS / "_patcher" / "run_extracted" / "data"
DEFAULT_PATCHER_SOURCE = (
    DEFAULT_TWEAKS
    / "_patcher"
    / "src_extracted"
    / "Mega Man X6 Tweaks Patcher (v2.6.1)"
    / "_src"
    / "data"
    / "_dat.ahk"
)


@dataclass(frozen=True)
class IsoEntry:
    name: str
    lba: int
    size: int
    is_directory: bool


class RawMode2Image:
    """Minimal ISO9660 reader over a MODE2/2352 track."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._file = self.path.open("rb")
        self.raw_size = self.path.stat().st_size
        self.user_size = (self.raw_size // RAW_SECTOR) * USER_SECTOR
        self.entries = self._read_root_entries()

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def read_user(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > self.user_size:
            raise ValueError(
                f"disc-user read outside {self.path.name}: {offset}+{size}"
            )
        result = bytearray()
        while size:
            lba, within = divmod(offset, USER_SECTOR)
            count = min(size, USER_SECTOR - within)
            self._file.seek(lba * RAW_SECTOR + USER_HEADER + within)
            chunk = self._file.read(count)
            if len(chunk) != count:
                raise RuntimeError(f"short read from {self.path}")
            result += chunk
            offset += count
            size -= count
        return bytes(result)

    def read_file(self, name: str) -> bytes:
        entry = self.entries[name.upper()]
        if entry.is_directory:
            raise ValueError(f"{name} is a directory")
        return self.read_user(entry.lba * USER_SECTOR, entry.size)

    def containing_file(self, offset: int, size: int) -> tuple[IsoEntry, int]:
        for entry in self.entries.values():
            begin = entry.lba * USER_SECTOR
            if not entry.is_directory and begin <= offset:
                if offset + size <= begin + entry.size:
                    return entry, offset - begin
        raise ValueError(
            f"disc-user range 0x{offset:X}+0x{size:X} is not inside an ISO file"
        )

    def _read_root_entries(self) -> dict[str, IsoEntry]:
        pvd = self.read_user(16 * USER_SECTOR, USER_SECTOR)
        if pvd[1:6] != b"CD001":
            raise ValueError(f"{self.path} has no ISO9660 PVD")
        root = pvd[156:190]
        root_lba = struct.unpack("<I", root[2:6])[0]
        root_size = struct.unpack("<I", root[10:14])[0]
        directory = self.read_user(root_lba * USER_SECTOR, root_size)
        entries: dict[str, IsoEntry] = {}
        cursor = 0
        while cursor < len(directory):
            length = directory[cursor]
            if length == 0:
                cursor = ((cursor // USER_SECTOR) + 1) * USER_SECTOR
                continue
            record = directory[cursor : cursor + length]
            cursor += length
            if len(record) < 34:
                continue
            raw_name = record[33 : 33 + record[32]].decode(
                "latin1", errors="replace"
            )
            if raw_name in ("\x00", "\x01"):
                continue
            name = raw_name.split(";", 1)[0].upper()
            entries[name] = IsoEntry(
                name=name,
                lba=struct.unpack("<I", record[2:6])[0],
                size=struct.unpack("<I", record[10:14])[0],
                is_directory=bool(record[25] & 2),
            )
        return entries


@dataclass(frozen=True)
class Overlay:
    feature: str
    label: str
    user_offset: int
    expected: bytes
    replace: bytes
    source: str = ""
    raw_offset: int | None = None
    iso_file: str = ""
    file_offset: int | None = None


@dataclass(frozen=True)
class Patch:
    feature: str
    label: str
    address: int
    expected: bytes
    replace: bytes


TITLE_ASSETS = (
    (
        "background_tileset",
        "title/bg_tileset_jpn/09 - 10014.bin",
        0x1F165968,
    ),
    (
        "background_palette",
        "title/bg_palette_jpn/00 - 5.bin",
        0x1DC0DE58,
    ),
    (
        "press_start_tileset",
        "title/start_tileset_jpn/01 - 10016.bin",
        0x1F112538,
    ),
    (
        "press_start_assembly",
        "title/start_assembly_jpn/03 - A.bin",
        0x1F12E768,
    ),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def raw_to_user_offset(raw_offset: int) -> int:
    lba, within = divmod(raw_offset, RAW_SECTOR)
    if not USER_HEADER <= within < USER_HEADER + USER_SECTOR:
        raise ValueError(
            f"raw offset 0x{raw_offset:X} is outside sector user data"
        )
    return lba * USER_SECTOR + within - USER_HEADER


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path}")


def build_title_overlays(
    stock: RawMode2Image,
    title_oracle: RawMode2Image,
    combined_oracle: RawMode2Image | None,
    patcher_data: Path,
) -> list[Overlay]:
    """Build and prove the four TitleScreen02-owned stock replacements."""
    overlays: list[Overlay] = []
    occupied: list[tuple[int, int, str]] = []
    for label, source, raw_offset in TITLE_ASSETS:
        source_path = patcher_data / source
        require_file(source_path, f"title asset {label}")
        payload = source_path.read_bytes()
        user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = stock.containing_file(user_offset, len(payload))
        if entry.name != "ROCK_X6.DAT":
            raise AssertionError(
                f"{label} targets {entry.name}, expected ROCK_X6.DAT"
            )
        expected = stock.read_user(user_offset, len(payload))
        if not any(expected):
            raise AssertionError(f"{label} stock range is empty")
        if expected == payload:
            raise AssertionError(f"{label} does not change the stock range")
        if title_oracle.read_user(user_offset, len(payload)) != payload:
            raise AssertionError(
                f"title-only oracle does not read {label} at its destination"
            )
        if combined_oracle is not None:
            if combined_oracle.read_user(user_offset, len(payload)) != payload:
                raise AssertionError(
                    f"combined oracle does not read {label} at its destination"
                )
        begin, end = user_offset, user_offset + len(payload)
        for other_begin, other_end, other_label in occupied:
            if begin < other_end and other_begin < end:
                raise AssertionError(f"{label} overlaps {other_label}")
        occupied.append((begin, end, label))
        overlays.append(
            Overlay(
                feature="title_screen",
                label=label,
                source=source,
                raw_offset=raw_offset,
                user_offset=user_offset,
                expected=expected,
                replace=payload,
                iso_file=entry.name,
                file_offset=file_offset,
            )
        )
    return overlays


def parse_owned_script_writes(source_path: Path) -> list[tuple[str, int, bytes]]:
    """Parse only active ScriptTextDisplay/ScriptMenuAlign AHK assignments."""
    require_file(source_path, "Tweaks _dat.ahk")
    text = source_path.read_text(encoding="utf-8-sig", errors="strict")
    # Remove block comments before matching.  The inactive IngameOptions block
    # intentionally reuses ScriptMenuAlign names.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    values: dict[str, str] = {}
    offsets: dict[str, int] = {}
    value_re = re.compile(
        r"^(Script(?:TextDisplay|MenuAlign)_ASM\d+)\s*=\s*([0-9A-F]+)\s*$",
        re.MULTILINE,
    )
    offset_re = re.compile(
        r"^(Script(?:TextDisplay|MenuAlign)_ASM\d+)_Offset\s*=\s*([0-9A-F]+)\s*$",
        re.MULTILINE,
    )
    for match in value_re.finditer(text):
        values[match.group(1)] = match.group(2)
    for match in offset_re.finditer(text):
        offsets[match.group(1)] = int(match.group(2), 16)
    names = sorted(values, key=lambda name: (name.split("_")[0], name))
    if len(names) != 15 or set(names) != set(offsets):
        raise AssertionError(
            "expected exactly 15 active ScriptTextDisplay/ScriptMenuAlign writes"
        )
    return [(name, offsets[name], bytes.fromhex(values[name])) for name in names]


@dataclass(frozen=True)
class DatRecord:
    record_id: int
    sector: int
    size: int
    payload: bytes


SCRIPT_SUBASSETS: dict[int, dict[int, tuple[int, int | None]]] = {
    **{
        record_id: {7: (0x10001, 0x8000), 9: (0x12, 0x2600)}
        for record_id in range(85, 90)
    },
    106: {0: (0x10001, 0x8000), 14: (0x15, 0x1600)},
    110: {0: (0x10001, 0x8000), 12: (0x15, 0x3000)},
    111: {0: (0x10001, 0x8000), 12: (0x15, 0x3000)},
    **{
        record_id: {
            0: (0x10001, 0x8000),
            (
                15
                if record_id in (149, 153, 157)
                else 12
                if record_id == 158
                else 11
                if record_id in (152, 161)
                else 14
            ): (0x15, 0x12000),
        }
        for record_id in range(149, 162)
    },
    **{
        record_id: {0: (0x15, None)}
        for record_id in range(203, 243)
    },
}

SCRIPT_IN_PLACE_IDS = frozenset(
    (
        *range(85, 90),
        *range(203, 207),
        *range(208, 213),
        *range(214, 221),
        *range(223, 227),
        *range(229, 235),
        *range(236, 239),
        240,
        242,
    )
)
SCRIPT_RELOCATED_IDS = frozenset(
    (
        106,
        110,
        111,
        *range(149, 162),
        207,
        213,
        221,
        222,
        227,
        228,
        235,
        239,
        241,
    )
)


@dataclass(frozen=True)
class Subasset:
    asset_type: int
    payload: bytes


def dat_records(data: bytes) -> dict[int, DatRecord]:
    records = {}
    for record_id in range(256):
        sector, size = struct.unpack_from("<II", data, record_id * 8)
        if sector == 0 and size == 0:
            continue
        begin = sector * USER_SECTOR
        end = begin + size
        if end > len(data):
            raise ValueError(
                f"DAT record {record_id} extends past its container: "
                f"0x{begin:X}+0x{size:X}"
            )
        records[record_id] = DatRecord(
            record_id, sector, size, data[begin:end]
        )
    return records


def parse_subassets(record: DatRecord) -> list[Subasset]:
    if len(record.payload) < USER_SECTOR:
        raise ValueError(f"DAT record {record.record_id} has no subasset header")
    count, outer_size = struct.unpack_from("<II", record.payload, 0)
    if outer_size != len(record.payload):
        raise ValueError(
            f"DAT record {record.record_id} outer size is "
            f"0x{outer_size:X}, expected 0x{len(record.payload):X}"
        )
    if 8 + count * 8 > USER_SECTOR:
        raise ValueError(f"DAT record {record.record_id} table is too large")
    cursor = USER_SECTOR
    result = []
    for index in range(count):
        asset_type, size = struct.unpack_from(
            "<II", record.payload, 8 + index * 8
        )
        end = cursor + size
        if end > len(record.payload):
            raise ValueError(
                f"DAT record {record.record_id} subasset {index} is truncated"
            )
        result.append(Subasset(asset_type, record.payload[cursor:end]))
        cursor = (end + USER_SECTOR - 1) // USER_SECTOR * USER_SECTOR
    if cursor != len(record.payload):
        raise ValueError(
            f"DAT record {record.record_id} subassets end at 0x{cursor:X}, "
            f"outer ends at 0x{len(record.payload):X}"
        )
    return result


def build_outer_record(subassets: list[Subasset]) -> bytes:
    if 8 + len(subassets) * 8 > USER_SECTOR:
        raise ValueError("subasset table does not fit one sector")
    result = bytearray(USER_SECTOR)
    for index, subasset in enumerate(subassets):
        struct.pack_into(
            "<II",
            result,
            8 + index * 8,
            subasset.asset_type,
            len(subasset.payload),
        )
        result += subasset.payload
        result += bytes((-len(result)) % USER_SECTOR)
    struct.pack_into("<II", result, 0, len(subassets), len(result))
    return bytes(result)


def coalesce_patches(patches: list[Patch]) -> list[Patch]:
    """Merge adjacent/compatible source writes into canonical guarded ranges."""
    result: list[Patch] = []
    for item in sorted(patches, key=lambda patch: patch.address):
        if not result:
            result.append(item)
            continue
        previous = result[-1]
        previous_end = previous.address + len(previous.replace)
        if item.address > previous_end:
            result.append(item)
            continue
        begin = previous.address
        end = max(previous_end, item.address + len(item.replace))
        expected: list[int | None] = [None] * (end - begin)
        replace: list[int | None] = [None] * (end - begin)
        for patch in (previous, item):
            offset = patch.address - begin
            for index, value in enumerate(patch.expected):
                at = offset + index
                if expected[at] is not None and expected[at] != value:
                    raise AssertionError(
                        f"incompatible expected bytes at 0x{begin + at:08X}"
                    )
                expected[at] = value
            for index, value in enumerate(patch.replace):
                at = offset + index
                if replace[at] is not None and replace[at] != value:
                    raise AssertionError(
                        f"incompatible replacements at 0x{begin + at:08X}"
                    )
                replace[at] = value
        if any(value is None for value in expected + replace):
            raise AssertionError("patch coalescing created an unguarded gap")
        result[-1] = Patch(
            feature=previous.feature,
            label=f"{previous.label}+{item.label}",
            address=begin,
            expected=bytes(expected),
            replace=bytes(replace),
        )
    return result


def build_retranslation_ops(
    stock: RawMode2Image,
    s02_base: RawMode2Image,
    script_oracle: RawMode2Image,
    patcher_source: Path,
    title_overlays: list[Overlay],
) -> tuple[list[Patch], list[Overlay], dict]:
    """Build custom stock outers containing only owned s02 subassets."""
    stock_dat_entry = stock.entries["ROCK_X6.DAT"]
    stock_dat_start = stock_dat_entry.lba * USER_SECTOR
    stock_dat = stock.read_file("ROCK_X6.DAT")
    s02_dat = s02_base.read_file("ROCK_X6.DAT")
    if stock.read_file("ROCK_X6.BIN") != s02_base.read_file("ROCK_X6.BIN"):
        raise AssertionError("s02 base unexpectedly changes ROCK_X6.BIN")
    stock_records = dat_records(stock_dat)
    s02_records = dat_records(s02_dat)
    if len(SCRIPT_SUBASSETS) != 61:
        raise AssertionError("reviewed script outer-record count changed")
    if sum(len(items) for items in SCRIPT_SUBASSETS.values()) != 82:
        raise AssertionError("reviewed script subasset count changed")
    if (
        set(SCRIPT_SUBASSETS)
        != SCRIPT_IN_PLACE_IDS | SCRIPT_RELOCATED_IDS
        or SCRIPT_IN_PLACE_IDS & SCRIPT_RELOCATED_IDS
    ):
        raise AssertionError("reviewed script record modes are inconsistent")

    custom_records: dict[int, bytes] = {}
    subasset_evidence = []
    for record_id, owned in sorted(SCRIPT_SUBASSETS.items()):
        original = stock_records[record_id]
        source = s02_records[record_id]
        stock_subassets = parse_subassets(original)
        s02_subassets = parse_subassets(source)
        # Prove the canonical builder preserves a stock outer exactly before
        # changing any feature-owned nested asset.
        if build_outer_record(stock_subassets) != original.payload:
            raise AssertionError(
                f"stock outer record {record_id} is not canonical"
            )
        custom_subassets = list(stock_subassets)
        for index, (expected_type, expected_size) in sorted(owned.items()):
            replacement = s02_subassets[index]
            if replacement.asset_type != expected_type:
                raise AssertionError(
                    f"record {record_id} subasset {index} type is "
                    f"0x{replacement.asset_type:X}, expected 0x{expected_type:X}"
                )
            if (
                expected_size is not None
                and len(replacement.payload) != expected_size
            ):
                raise AssertionError(
                    f"record {record_id} subasset {index} size is "
                    f"0x{len(replacement.payload):X}, "
                    f"expected 0x{expected_size:X}"
                )
            custom_subassets[index] = replacement
            subasset_evidence.append(
                {
                    "record_id": record_id,
                    "subasset_index": index,
                    "type": replacement.asset_type,
                    "size": len(replacement.payload),
                    "sha256": sha256(replacement.payload),
                }
            )
        custom_records[record_id] = build_outer_record(custom_subassets)

    protected = [
        (item.user_offset, item.user_offset + len(item.replace), item.label)
        for item in title_overlays
    ]
    overlays: list[Overlay] = []
    equal_size_ids = []
    relocated_ids = []
    record_evidence = []

    if stock_dat_entry.size % USER_SECTOR:
        raise AssertionError("stock ROCK_X6.DAT is not sector aligned")
    pack_sector = stock_dat_entry.size // USER_SECTOR
    pack_first_sector = pack_sector
    for record_id, target_payload in sorted(custom_records.items()):
        original = stock_records[record_id]
        if len(target_payload) == original.size:
            equal_size_ids.append(record_id)
            record_start = stock_dat_start + original.sector * USER_SECTOR
            overlays.append(
                Overlay(
                    feature="retranslation",
                    label=f"record-{record_id:03d}",
                    user_offset=record_start,
                    expected=original.payload,
                    replace=target_payload,
                    iso_file="ROCK_X6.DAT",
                    file_offset=original.sector * USER_SECTOR,
                )
            )
            record_evidence.append(
                {
                    "id": record_id,
                    "mode": "in-place",
                    "stock_sector": original.sector,
                    "size": len(target_payload),
                    "sha256": sha256(target_payload),
                }
            )
            continue

        relocated_ids.append(record_id)
        packed_offset = stock_dat_start + pack_sector * USER_SECTOR
        expected_backing = stock.read_user(packed_offset, len(target_payload))
        overlays.append(
            Overlay(
                feature="retranslation",
                label=f"record-{record_id:03d}-relocated",
                user_offset=packed_offset,
                expected=expected_backing,
                replace=target_payload,
                iso_file="ZNULL.DAT",
                file_offset=packed_offset
                - stock.entries["ZNULL.DAT"].lba * USER_SECTOR,
            )
        )
        old_table = stock_dat[record_id * 8 : record_id * 8 + 8]
        new_table = struct.pack("<II", pack_sector, len(target_payload))
        overlays.append(
            Overlay(
                feature="retranslation",
                label=f"record-{record_id:03d}-table",
                user_offset=stock_dat_start + record_id * 8,
                expected=old_table,
                replace=new_table,
                iso_file="ROCK_X6.DAT",
                file_offset=record_id * 8,
            )
        )
        record_evidence.append(
            {
                "id": record_id,
                "mode": "relocated",
                "stock_sector": original.sector,
                "packed_sector": pack_sector,
                "size": len(target_payload),
                "sha256": sha256(target_payload),
            }
        )
        pack_sector += len(target_payload) // USER_SECTOR

    znull_sectors = (
        stock.entries["ZNULL.DAT"].size + USER_SECTOR - 1
    ) // USER_SECTOR
    packed_sectors = pack_sector - pack_first_sector
    if packed_sectors != 0x1ABE:
        raise AssertionError(
            f"reviewed relocated payload was 0x{packed_sectors:X} sectors, "
            "expected 0x1ABE"
        )
    if packed_sectors > znull_sectors:
        raise AssertionError("relocated script records do not fit stock ZNULL")
    if (
        set(equal_size_ids) != SCRIPT_IN_PLACE_IDS
        or set(relocated_ids) != SCRIPT_RELOCATED_IDS
    ):
        raise AssertionError(
            "reviewed nested record modes changed: got in-place "
            f"{equal_size_ids}, relocated {relocated_ids}"
        )
    # The guest ISO lookup must expose the virtual DAT extent through the final
    # relocated record. Keep the stock LBA and update both ISO9660 byte orders.
    logical_dat_size = pack_sector * USER_SECTOR
    if logical_dat_size != 0x03DED000:
        raise AssertionError(
            f"reviewed virtual DAT extent changed: 0x{logical_dat_size:08X}"
        )
    iso_size_offset = 0xB0A6
    iso_size_expected = stock.read_user(iso_size_offset, 8)
    if iso_size_expected != bytes.fromhex("00E008030308E000"):
        raise AssertionError(
            "stock ROCK_X6.DAT ISO size record does not match USA v1.1"
        )
    overlays.append(
        Overlay(
            feature="retranslation",
            label="rock-x6-dat-logical-size",
            user_offset=iso_size_offset,
            expected=iso_size_expected,
            replace=bytes.fromhex("00D0DE0303DED000"),
            iso_file="ISO9660 root directory",
            file_offset=iso_size_offset,
        )
    )

    load_address = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    source_patches = []
    for name, raw_offset, replacement in parse_owned_script_writes(
        patcher_source
    ):
        user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = stock.containing_file(user_offset, len(replacement))
        if entry.name != SLUS_NAME:
            raise AssertionError(f"{name} targets {entry.name}, expected {SLUS_NAME}")
        expected = stock.read_user(user_offset, len(replacement))
        if script_oracle.read_user(user_offset, len(replacement)) != replacement:
            raise AssertionError(f"script oracle does not contain {name}")
        source_patches.append(
            Patch(
                feature="retranslation",
                label=name,
                address=load_address + file_offset - 2048,
                expected=expected,
                replace=replacement,
            )
        )
    patches = coalesce_patches(source_patches)
    if len(source_patches) != 15 or len(patches) != 12:
        raise AssertionError(
            "reviewed script patch canonicalization changed: expected "
            f"15 source writes -> 12 ranges, got "
            f"{len(source_patches)} -> {len(patches)}"
        )

    # Prove every operation is disjoint from the title feature, except identical
    # bytes (none are expected in this slice).
    for overlay in overlays:
        begin, end = overlay.user_offset, overlay.user_offset + len(overlay.replace)
        for p_begin, p_end, label in protected:
            if begin < p_end and p_begin < end:
                raise AssertionError(
                    f"retranslation {overlay.label} claims title asset {label}"
                )
    evidence = {
        "status": "ready",
        "selection": {"ScriptPatch02": 1},
        "logical_record_ids": sorted(custom_records),
        "owned_subasset_count": len(subasset_evidence),
        "owned_subassets": subasset_evidence,
        "in_place_record_ids": equal_size_ids,
        "relocated_record_ids": relocated_ids,
        "relocated_start_sector": pack_first_sector,
        "relocated_sectors": packed_sectors,
        "stock_znull_sectors": znull_sectors,
        "owned_source_main_exe_writes": len(source_patches),
        "canonical_main_exe_ranges": len(patches),
        "owned_main_exe_bytes": sum(len(item.replace) for item in patches),
        "records": record_evidence,
        "no_rock_x6_bin_changes": True,
        "title_ranges_unclaimed": True,
        "omitted_base_outer_record_ids": [107, 243, 244, 245, 246, 247],
    }
    return patches, overlays, evidence


def audit_retranslation(
    stock: RawMode2Image,
    script_oracle: RawMode2Image,
    patcher_source: Path,
) -> dict:
    """Prove the source-level executable edits without building assets."""
    load_address = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    writes = []
    for name, raw_offset, replacement in parse_owned_script_writes(
        patcher_source
    ):
        user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = stock.containing_file(user_offset, len(replacement))
        if entry.name != SLUS_NAME:
            raise AssertionError(f"{name} targets {entry.name}, expected {SLUS_NAME}")
        expected = stock.read_user(user_offset, len(replacement))
        actual = script_oracle.read_user(user_offset, len(replacement))
        if actual != replacement:
            raise AssertionError(
                f"retranslation oracle does not contain owned write {name}"
            )
        address = load_address + file_offset - 2048
        writes.append(
            {
                "name": name,
                "raw_offset": raw_offset,
                "disc_user_offset": user_offset,
                "main_exe_address": address,
                "size": len(replacement),
                "expected": expected.hex().upper(),
                "replace": replacement.hex().upper(),
            }
        )
    return {
        "status": "main-exe-audit-only",
        "reason": (
            "This audit mode reports only ScriptTextDisplay/ScriptMenuAlign. "
            "Normal retranslation generation separately rebuilds 61 stock "
            "outer records from 82 owned s02 subassets."
        ),
        "owned_main_exe_writes": writes,
        "owned_main_exe_write_count": len(writes),
        "owned_main_exe_bytes": sum(item["size"] for item in writes),
        "asset_mapping_status": "implemented-by-nested-record-repacker",
    }


def validate_composition(
    stock: RawMode2Image, patches: list[Patch], overlays: list[Overlay]
) -> dict:
    """Validate stock guards and compatible partial overlaps before packaging."""
    identical_overlap_bytes = 0
    ordered_overlays = sorted(overlays, key=lambda item: item.user_offset)
    for item in ordered_overlays:
        actual = stock.read_user(item.user_offset, len(item.expected))
        if actual != item.expected:
            raise AssertionError(f"stock guard failed for {item.label}")
    for index, left in enumerate(ordered_overlays):
        left_end = left.user_offset + len(left.replace)
        for right in ordered_overlays[index + 1 :]:
            if right.user_offset >= left_end:
                break
            right_end = right.user_offset + len(right.replace)
            begin = max(left.user_offset, right.user_offset)
            end = min(left_end, right_end)
            left_bytes = left.replace[
                begin - left.user_offset : end - left.user_offset
            ]
            right_bytes = right.replace[
                begin - right.user_offset : end - right.user_offset
            ]
            if left_bytes != right_bytes:
                raise AssertionError(
                    f"disc collision at 0x{begin:X}: "
                    f"{left.feature}/{left.label} vs "
                    f"{right.feature}/{right.label}"
                )
            identical_overlap_bytes += end - begin

    ordered_patches = sorted(patches, key=lambda item: item.address)
    for index, left in enumerate(ordered_patches):
        left_end = left.address + len(left.replace)
        for right in ordered_patches[index + 1 :]:
            if right.address >= left_end:
                break
            right_end = right.address + len(right.replace)
            begin = max(left.address, right.address)
            end = min(left_end, right_end)
            left_bytes = left.replace[
                begin - left.address : end - left.address
            ]
            right_bytes = right.replace[
                begin - right.address : end - right.address
            ]
            if left_bytes != right_bytes:
                raise AssertionError(
                    f"main-EXE collision at 0x{begin:08X}: "
                    f"{left.label} vs {right.label}"
                )
            identical_overlap_bytes += end - begin

    fingerprint_input = [
        (
            "patch",
            item.feature,
            item.address,
            len(item.replace),
            sha256(item.expected),
            sha256(item.replace),
        )
        for item in ordered_patches
    ] + [
        (
            "overlay",
            item.feature,
            item.user_offset,
            len(item.replace),
            sha256(item.expected),
            sha256(item.replace),
        )
        for item in ordered_overlays
    ]
    fingerprint = sha256(
        json.dumps(fingerprint_input, separators=(",", ":")).encode()
    )
    return {
        "patch_operations": len(patches),
        "patch_bytes": sum(len(item.replace) for item in patches),
        "overlay_operations": len(overlays),
        "overlay_bytes": sum(len(item.replace) for item in overlays),
        "identical_overlap_bytes": identical_overlap_bytes,
        "incompatible_overlap_bytes": 0,
        "plan_fingerprint": fingerprint,
        "stock_guards_verified": True,
    }


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_manifest(
    features: set[str],
    patches: list[Patch],
    overlays: list[Overlay],
    asset_paths: dict[int, str],
) -> str:
    lines = [
        "format_version = 1",
        'id = "mmx6.tweaks.native"',
        'version = "1.0.0"',
        'name = "Mega Man X6 Tweaks"',
        'author = "acediez, DuoDynamo, NectarHime; PSXRecomp integration"',
        'description = "Independent native MMX6 Tweaks features."',
        'license = "Generated locally; original credits retained"',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {q(GAME_ID)}",
        f"disc_sha256 = {q(STOCK_SHA256)}",
    ]
    if "title_screen" in features:
        lines += [
            "",
            "[[feature]]",
            'id = "title_screen"',
            'name = "Title Screen"',
            'description = "Choose the stock or original Japanese title artwork."',
            'group = "Localization"',
            "default_enabled = false",
            "",
            "[[option]]",
            'feature = "title_screen"',
            'id = "variant"',
            'label = "Title artwork"',
            'description = "Artwork used by the title-screen asset requests."',
            'group = "Localization"',
            'type = "choice"',
            'default = "rockman_japan"',
            "",
            "[[option.choice]]",
            'value = "rockman_japan"',
            'label = "Rockman X6 (Japan)"',
        ]
    if "retranslation" in features:
        lines += [
            "",
            "[[feature]]",
            'id = "retranslation"',
            'name = "Retranslation"',
            'description = "English retranslation, VFW font, and menu alignment."',
            'group = "Localization"',
            "default_enabled = false",
            "",
            "[[option]]",
            'feature = "retranslation"',
            'id = "script"',
            'label = "English script"',
            'description = "English script used by dialogue and menus."',
            'group = "Localization"',
            'type = "choice"',
            'default = "english_retranslation"',
            "",
            "[[option.choice]]",
            'value = "english_retranslation"',
            'label = "English Retranslation"',
        ]
    for patch in patches:
        lines += [
            "",
            "[[patch]]",
            f"feature = {q(patch.feature)}",
            'target = "main_exe"',
            f"address = {patch.address}",
            f"expected = {q(patch.expected.hex().upper())}",
            f"replace = {q(patch.replace.hex().upper())}",
            "order = 0",
            'when = { script = "english_retranslation" }',
        ]
    for index, overlay in enumerate(overlays):
        condition = (
            'variant = "rockman_japan"'
            if overlay.feature == "title_screen"
            else 'script = "english_retranslation"'
        )
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
            f"when = {{ {condition} }}",
        ]
    return "\n".join(lines) + "\n"


def write_package(
    out: Path,
    features: set[str],
    patches: list[Patch],
    overlays: list[Overlay],
    report: dict,
) -> None:
    asset_paths = {
        index: f"assets/{overlay.feature}/{index:03d}-{overlay.label}.bin"
        for index, overlay in enumerate(overlays)
    }
    manifest = build_manifest(features, patches, overlays, asset_paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr("manifest.toml", manifest)
        for index, overlay in enumerate(overlays):
            archive.writestr(asset_paths[index], overlay.replace)
        archive.writestr(
            "conversion-report.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        archive.writestr(
            "README.txt",
            "Generated locally from a verified stock MMX6 image and a "
            "user-supplied MMX6 Tweaks extraction.\n"
            "This package contains native stock-disc record overlays and "
            "guarded executable patches. It contains no derived disc or "
            "VCDIFF runtime recipe.\n",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=DEFAULT_STOCK)
    parser.add_argument(
        "--title-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "rockman-jp-title.bin",
    )
    parser.add_argument(
        "--combined-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "rockman-jp-title-retranslation.bin",
    )
    parser.add_argument(
        "--script-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "retranslation.bin",
    )
    parser.add_argument(
        "--s02-base",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "s02-base.bin",
        help="local result of applying data/xdelta3/s02.xdelta3 to stock",
    )
    parser.add_argument("--patcher-data", type=Path, default=DEFAULT_PATCHER_DATA)
    parser.add_argument(
        "--patcher-source", type=Path, default=DEFAULT_PATCHER_SOURCE
    )
    parser.add_argument(
        "--feature",
        choices=("all", "title_screen", "retranslation"),
        default="all",
    )
    parser.add_argument("--audit-retranslation", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    require_file(args.stock, "stock MMX6 BIN")
    stock_digest = file_sha256(args.stock)
    if stock_digest != STOCK_SHA256:
        raise ValueError(
            f"unsupported stock image: {stock_digest}; expected {STOCK_SHA256}"
        )
    require_file(args.title_oracle, "title-only conversion oracle")
    combined_path = args.combined_oracle if args.combined_oracle.is_file() else None
    wants_retranslation = args.feature in ("all", "retranslation")
    if wants_retranslation or args.audit_retranslation:
        require_file(args.script_oracle, "retranslation conversion oracle")
    if wants_retranslation:
        require_file(args.s02_base, "s02 base conversion oracle")
        require_file(args.patcher_source, "Tweaks _dat.ahk")
    script_path = (
        args.script_oracle
        if wants_retranslation or args.audit_retranslation
        else None
    )
    with RawMode2Image(args.stock) as stock, RawMode2Image(
        args.title_oracle
    ) as title:
        combined = RawMode2Image(combined_path) if combined_path else None
        script = RawMode2Image(script_path) if script_path else None
        s02_base = RawMode2Image(args.s02_base) if wants_retranslation else None
        try:
            title_overlays = build_title_overlays(
                stock, title, combined, args.patcher_data
            )
            enabled_features = (
                {"title_screen", "retranslation"}
                if args.feature == "all"
                else {args.feature}
            )
            patches: list[Patch] = []
            overlays = (
                list(title_overlays)
                if "title_screen" in enabled_features
                else []
            )
            report = {
                "status": "reviewed-native-feature-slice",
                "stock_sha256": stock_digest,
                "title_oracle_sha256": file_sha256(args.title_oracle),
                "combined_oracle_sha256": (
                    file_sha256(combined_path) if combined_path else None
                ),
                "features": {
                    "title_screen": {
                        "status": "ready",
                        "selection": {"TitleScreen02": 1},
                        "operations": [
                            {
                                "label": item.label,
                                "source": item.source,
                                "iso_file": item.iso_file,
                                "file_offset": item.file_offset,
                                "disc_user_offset": item.user_offset,
                                "raw_oracle_offset": item.raw_offset,
                                "size": len(item.replace),
                                "stock_sha256": sha256(item.expected),
                                "replacement_sha256": sha256(item.replace),
                                "title_only_read_path_verified": True,
                                "combined_read_path_verified": combined is not None,
                            }
                            for item in title_overlays
                        ],
                    }
                },
                "forbidden_runtime_payloads": {
                    "derived_disc": False,
                    "vcdiff": False,
                    "patched_oracle": False,
                },
            }
            if wants_retranslation:
                script_patches, script_overlays, evidence = (
                    build_retranslation_ops(
                        stock,
                        s02_base,
                        script,
                        args.patcher_source,
                        title_overlays,
                    )
                )
                patches += script_patches
                overlays += script_overlays
                report["features"]["retranslation"] = evidence
                report["s02_base_oracle_sha256"] = file_sha256(args.s02_base)
                report["script_oracle_sha256"] = file_sha256(args.script_oracle)
            elif script is not None:
                report["features"]["retranslation"] = audit_retranslation(
                    stock, script, args.patcher_source
                )
            report["composition"] = validate_composition(
                stock, patches, overlays
            )
        finally:
            if combined is not None:
                combined.close()
            if script is not None:
                script.close()
            if s02_base is not None:
                s02_base.close()

    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.verify_only:
        out = args.out or (
            ROOT
            / "build-mod-platform"
            / "test-psxmods"
            / "MMX6-Tweaks-Native.psxmod"
        )
        write_package(out, enabled_features, patches, overlays, report)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
