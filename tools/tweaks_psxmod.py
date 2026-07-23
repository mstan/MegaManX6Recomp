#!/usr/bin/env python3
"""Convert any MMX6 Tweaks selection into a portable .psxmod package.

The output contains a sparse, expected-byte-guarded raw-disc overlay. It does
not modify the user's disc and it does not require rebuilding the static
recomp. The runtime routes changed executable code through its live-RAM
fallback, while unchanged code remains native.

The acediez patcher data/assets are not redistributed. Point the existing
Tweaks tools at a user-supplied patcher extraction, or provide a BIN already
produced by the reference patcher with --patched-bin.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

SECTOR_SIZE = 2352
GAME_ID = "SLUS-01395"


def _load_engine():
    path = Path(__file__).resolve().parent / "tweaks_engine.py"
    spec = importlib.util.spec_from_file_location("mmx6_tweaks_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_manifest(base_path: Path, patched_path: Path, *, package_id: str,
                   version: str, name: str, selection: dict) -> str:
    base_size = base_path.stat().st_size
    patched_size = patched_path.stat().st_size
    if base_size != patched_size:
        raise ValueError(
            "base and patched BIN sizes differ; use --base-bin with the common "
            "Tweaks xdelta base, or use --selection-file so it is generated")
    if base_size % SECTOR_SIZE:
        raise ValueError("raw BIN size is not a multiple of 2352 bytes")
    with base_path.open("rb") as source:
        base_sha256 = hashlib.file_digest(source, "sha256").hexdigest()

    lines = [
        "format_version = 1",
        f"id = {_quote(package_id)}",
        f"version = {_quote(version)}",
        f"name = {_quote(name)}",
        'author = "acediez (Tweaks); PSXRecomp package generated locally"',
        'description = "Local MMX6 Tweaks profile; applies at boot without changing the disc."',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {_quote(GAME_ID)}",
        f"disc_sha256 = {_quote(base_sha256)}",
        "",
        "[source]",
        'kind = "mmx6-tweaks-profile"',
        f"selection_json = {_quote(json.dumps(selection, sort_keys=True, separators=(',', ':')))}",
    ]
    changed = 0
    with base_path.open("rb") as base, patched_path.open("rb") as patched:
        for offset in range(0, base_size, SECTOR_SIZE):
            before = base.read(SECTOR_SIZE)
            after = patched.read(SECTOR_SIZE)
            if before == after:
                continue
            changed += 1
            lines += [
                "",
                "[[patch]]",
                'target = "disc_raw"',
                f"offset = {offset}",
                f"expected = {_quote(before.hex())}",
                f"replace = {_quote(after.hex())}",
            ]
    if not changed:
        raise ValueError("the selected profile produces no changes")
    lines += ["", "[package_stats]", f"changed_raw_sectors = {changed}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vanilla", required=True, type=Path,
                        help="Clean Mega Man X6 (USA v1.1) raw BIN")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--patched-bin", type=Path,
                        help="BIN produced by the reference Tweaks patcher")
    source.add_argument("--selection",
                        help="Tweaks selection JSON; uses the ported Python engine")
    source.add_argument("--selection-file", type=Path,
                        help="Path to Tweaks selection JSON; avoids shell quoting")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-bin", type=Path,
                        help="Tweaks common xdelta base used as the runtime disc")
    parser.add_argument("--base-out", type=Path,
                        help="Where --selection-file writes that common base")
    parser.add_argument("--id", dest="package_id")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--name", default="Mega Man X6 Tweaks Profile")
    args = parser.parse_args()

    selection_text = (args.selection_file.read_text(encoding="utf-8")
                      if args.selection_file else args.selection)
    selection = json.loads(selection_text) if selection_text else {}
    if args.patched_bin:
        patched_path = args.patched_bin
        base_path = args.base_bin or args.vanilla
    else:
        engine = _load_engine()
        with tempfile.TemporaryDirectory(prefix="mmx6-tweaks-") as temporary:
            produced = Path(temporary) / "patched.bin"
            patchfile, _ = engine.apply_selection(
                selection_text, produced, vanilla=args.vanilla)
            base_path = args.base_out or args.out.with_suffix(".base.bin")
            base_path.parent.mkdir(parents=True, exist_ok=True)
            patch = engine.BASE_PATCH_DIR / f"{patchfile}.xdelta3"
            result = subprocess.run(
                [str(engine.XDELTA3_EXE), "-f", "-n", "-d", "-s",
                 str(args.vanilla), str(patch), str(base_path)],
                capture_output=True, text=True)
            if result.returncode != 0 or not base_path.exists():
                raise RuntimeError(
                    f"xdelta3 base generation failed ({result.returncode}): "
                    f"{result.stdout}{result.stderr}")
            _write_package(args, base_path, produced, selection)
            print(f"runtime base disc: {base_path}")
            return 0
    _write_package(args, base_path, patched_path, selection)
    return 0


def _write_package(args, base_path: Path, patched_path: Path,
                   selection: dict) -> None:
    with patched_path.open("rb") as patched_file:
        patched_digest = hashlib.file_digest(patched_file, "sha256").digest()
    identity = hashlib.sha256(
        json.dumps(selection, sort_keys=True).encode("utf-8") +
        patched_digest).hexdigest()[:16]
    package_id = args.package_id or f"mmx6.tweaks.{identity}"
    manifest = build_manifest(
        base_path, patched_path, package_id=package_id, version=args.version,
        name=args.name, selection=selection)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        archive.writestr("manifest.toml", manifest)
        archive.writestr("selection.json",
                         json.dumps(selection, indent=2, sort_keys=True) + "\n")
        archive.writestr(
            "README.txt",
            "Generated locally from a user-supplied MMX6 Tweaks profile.\n"
            "Tweaks research and patch payloads are credited to acediez.\n")
    print(f"wrote {args.out} ({package_id} {args.version})")


if __name__ == "__main__":
    raise SystemExit(main())
