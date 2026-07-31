#!/usr/bin/env python3
"""Build the trusted MMX6 voice-hook package from reviewed stock identities.

The archive contains feature declarations only. Executable bytes stay in the
game-owned `builtin:mmx6.tweaks.hooks` resolver. This generator fail-closes
unless the local Tweaks source, isolated B01 base, and stock image still prove
every reviewed source write and full stock guard.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import tweaks_native_psxmod as native


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ID = "mmx6.tweaks.hooks"
PACKAGE_VERSION = "1.0.0"
RESOLVER = "builtin:mmx6.tweaks.hooks"
STOCK_SHA256 = native.STOCK_SHA256
B01_SHA256 = "7b3b7ad59fc2a3e936154685bf1062e8707188e37b182a9481c9d847397031e6"
DEFAULT_STOCK = (
    ROOT / "mmx6-tweaks" / "Mega Man X6 (USA) (v1.1).bin"
)
DEFAULT_SOURCE = (
    ROOT
    / "mmx6-tweaks"
    / "_patcher"
    / "src_extracted"
    / "Mega Man X6 Tweaks Patcher (v2.6.1)"
    / "_src"
    / "data"
    / "_dat.ahk"
)
DEFAULT_OUT = (
    ROOT
    / "build-mod-platform"
    / "test-psxmods"
    / "MMX6-Tweaks-Hooks.psxmod"
)


@dataclass(frozen=True)
class SourceWrite:
    raw_offset: int
    replacement_hex: str
    expected_hex: str
    target: str
    location: int
    member_id: int | None = None
    member_relative_offset: int | None = None


@dataclass(frozen=True)
class VoiceSpec:
    feature_id: str
    source_option: str
    name: str
    description: str
    writes: tuple[tuple[int, str], ...]


VOICE_SPECS = (
    VoiceSpec(
        "voice_title",
        "VoiceClip01",
        'Title Screen Voice ("Rockman X6")',
        'Play the "Rockman X6" voice clip on the title screen.',
        (
            (0x1D93077C, "1FD901081000B0AF"),
            (0x1D93080C, "14780008"),
            (
                0x1D995F64,
                "0500043400000534125B000C00000634B377000800001034",
            ),
        ),
    ),
    VoiceSpec(
        "voice_boss_intros",
        "VoiceClip02",
        "Boss Intro Voices",
        "Restore voice clips during boss introductions.",
        (
            (0x1DA97500, "16D9010801004224B3A60308"),
            (
                0x1D995F40,
                "010082A0260082800000063421104800FFFF4590125B000C"
                "00000434A0A7030800000000",
            ),
        ),
    ),
    VoiceSpec(
        "voice_low_health",
        "VoiceClip05",
        "Low Health Voices",
        "Restore the X and Zero low-health voice clips.",
        (
            (
                0x1D9543D8,
                "10D901081010000006006010030004340F000534125B000C"
                "00000634780002248D0002A242DE000800000000",
            ),
            (
                0x1D995F28,
                "23104300001602005C00C3800316020016F400082A186200",
            ),
        ),
    ),
    VoiceSpec(
        "voice_boss_warning",
        "VoiceClip06",
        "Boss Warning Voice",
        "Restore the voice clip on the boss warning screen.",
        (
            (0x1D96E16C, "25D90108"),
            (
                0x1D995F7C,
                "125B000C00000634000004342C000534125B000C00000634"
                "1F4E01083C000334",
            ),
        ),
    ),
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def parse_assignments(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    assignment = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")
    for line in path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        matched = assignment.match(line)
        if matched:
            result[matched.group(1)] = matched.group(2).strip()
    return result


def verify_source(path: Path) -> None:
    assignments = parse_assignments(path)
    for spec in VOICE_SPECS:
        if assignments.get(f"{spec.source_option}_Default") != "0":
            raise ValueError(f"{spec.source_option} source default changed")
        for index, (offset, replacement) in enumerate(spec.writes, 1):
            prefix = f"{spec.source_option}_ASM{index:02d}"
            if assignments.get(prefix, "").upper() != replacement:
                raise ValueError(f"{prefix} source payload changed")
            actual_offset = assignments.get(f"{prefix}_Offset", "")
            if actual_offset.upper() != f"{offset:X}":
                raise ValueError(f"{prefix} source offset changed")


def resolve_writes(stock_path: Path, b01_path: Path) -> dict[str, list[SourceWrite]]:
    if sha256_file(stock_path) != STOCK_SHA256:
        raise ValueError("stock image SHA-256 is not the supported USA v1.1 image")
    if sha256_file(b01_path) != B01_SHA256:
        raise ValueError("B01 base SHA-256 is not the reviewed isolated oracle")

    resolved: dict[str, list[SourceWrite]] = {}
    with native.RawMode2Image(stock_path) as stock, native.RawMode2Image(
        b01_path
    ) as b01:
        stock_exe = stock.read_file(native.SLUS_NAME)
        stock_load = int.from_bytes(stock_exe[0x18:0x1C], "little")
        b01_members = native.indexed_archive_members(
            b01.read_file("ROCK_X6.BIN")
        )
        stock_members = native.indexed_archive_members(
            stock.read_file("ROCK_X6.BIN")
        )

        for spec in VOICE_SPECS:
            feature_writes: list[SourceWrite] = []
            for raw_offset, replacement_hex in spec.writes:
                replacement = bytes.fromhex(replacement_hex)
                source_user = native.raw_to_user_offset(raw_offset)
                entry, file_offset = b01.containing_file(
                    source_user, len(replacement)
                )
                expected = native.read_iso_file_range(
                    b01, entry.name, file_offset, len(replacement)
                )
                stock_expected = native.read_iso_file_range(
                    stock, entry.name, file_offset, len(replacement)
                )
                if stock_expected != expected:
                    raise ValueError(
                        f"{spec.source_option} depends on an unowned B01 rewrite"
                    )

                if entry.name == native.SLUS_NAME:
                    feature_writes.append(
                        SourceWrite(
                            raw_offset,
                            replacement_hex,
                            expected.hex().upper(),
                            "main_exe",
                            stock_load + file_offset - native.USER_SECTOR,
                        )
                    )
                    continue
                if entry.name != "ROCK_X6.BIN":
                    raise ValueError(
                        f"{spec.source_option} targets unsupported {entry.name}"
                    )
                member, relative = native.containing_member(
                    b01_members, file_offset, len(replacement)
                )
                stock_member = stock_members.get(member.member_id)
                if (
                    stock_member is None
                    or stock_member.payload[
                        relative : relative + len(replacement)
                    ]
                    != expected
                ):
                    raise ValueError(
                        f"{spec.source_option} member stock guard changed"
                    )
                stock_file_offset = stock_member.file_offset + relative
                user_offset = (
                    stock.entries["ROCK_X6.BIN"].lba * native.USER_SECTOR
                    + stock_file_offset
                )
                feature_writes.append(
                    SourceWrite(
                        raw_offset,
                        replacement_hex,
                        expected.hex().upper(),
                        "disc_user",
                        user_offset,
                        member.member_id,
                        relative,
                    )
                )
            resolved[spec.feature_id] = feature_writes
    return resolved


def toml_quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def manifest_text() -> str:
    lines = [
        "format_version = 3",
        f"id = {toml_quote(PACKAGE_ID)}",
        f"version = {toml_quote(PACKAGE_VERSION)}",
        'name = "Mega Man X6 Voice Hooks"',
        'author = "acediez"',
        (
            'description = "Independent stock-disc voice restoration hooks."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {toml_quote(RESOLVER)}",
        'save_compatibility = "shared"',
        'source_name = "Mega Man X6 Tweaks"',
        'source_url = "https://www.romhacking.net/hacks/4035/"',
        "",
        "[[author_link]]",
        'name = "acediez"',
        'url = "https://twitter.com/acediez"',
        "",
        "[[target]]",
        f"game_id = {toml_quote(native.GAME_ID)}",
        f"disc_sha256 = {toml_quote(STOCK_SHA256)}",
    ]
    for spec in VOICE_SPECS:
        lines.extend(
            (
                "",
                "[[feature]]",
                f"id = {toml_quote(spec.feature_id)}",
                f"name = {toml_quote(spec.name)}",
                f"description = {toml_quote(spec.description)}",
                'group = "Audio"',
                "default_enabled = false",
            )
        )
    return "\n".join(lines) + "\n"


def conversion_report(
    stock: Path, b01: Path, source: Path,
    resolved: dict[str, list[SourceWrite]],
) -> dict:
    return {
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "stock_sha256": sha256_file(stock),
        "b01_sha256": sha256_file(b01),
        "source_sha256": sha256_file(source),
        "source_controls": sorted(
            spec.source_option for spec in VOICE_SPECS
        ),
        "foundation": {
            "id": "voice_code_foundation",
            "target": "main_exe",
            "address": 0x80076440,
            "size": 0x74,
            "expected": "00" * 0x74,
            "allocation_policy": "one composed write; fixed disjoint slices",
        },
        "features": {
            spec.feature_id: {
                "source_option": spec.source_option,
                "writes": [
                    {
                        "source_raw_offset": f"0x{write.raw_offset:X}",
                        "target": write.target,
                        "location": write.location,
                        "expected": write.expected_hex,
                        "replace": write.replacement_hex,
                        **(
                            {
                                "member_id": write.member_id,
                                "member_relative_offset":
                                    write.member_relative_offset,
                            }
                            if write.member_id is not None
                            else {}
                        ),
                    }
                    for write in resolved[spec.feature_id]
                ],
            }
            for spec in VOICE_SPECS
        },
    }


def archive_bytes(manifest: str, report: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {
            "README.txt": (
                "This package contains declarations only. The MMX6 runtime "
                "owns and validates all trusted hook bytes. It targets a "
                "stock USA v1.1 BIN/CUE and does not contain a derived disc.\n"
            ),
            "conversion-report.json": (
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            ),
            "manifest.toml": manifest,
        }
        for name in sorted(members):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name].encode("utf-8"))
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=DEFAULT_STOCK)
    parser.add_argument(
        "--b01-base",
        type=Path,
        required=True,
        help="isolated Tweaks B01 base image used only as a conversion oracle",
    )
    parser.add_argument("--patcher-source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    for path, label in (
        (args.stock, "stock image"),
        (args.b01_base, "B01 base oracle"),
        (args.patcher_source, "Tweaks source database"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")

    verify_source(args.patcher_source)
    resolved = resolve_writes(args.stock, args.b01_base)
    report = conversion_report(
        args.stock, args.b01_base, args.patcher_source, resolved
    )
    manifest = manifest_text()
    first = archive_bytes(manifest, report)
    second = archive_bytes(manifest, report)
    if first != second:
        raise AssertionError("package archive is not deterministic")

    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.verify_only:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(first)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AssertionError,
        FileNotFoundError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
