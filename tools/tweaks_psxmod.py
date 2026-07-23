#!/usr/bin/env python3
"""Convert any MMX6 Tweaks selection into a stock-targeted .psxmod package.

The output contains a data-only VCDIFF recipe from the verified stock image to
the selected Tweaks result. At launch the runtime materializes a fingerprinted
private cache and mounts it internally. The user's selected stock disc is never
changed or replaced in settings.

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


def build_manifest(vanilla_path: Path, patched_path: Path, delta_path: Path, *,
                   package_id: str, version: str, name: str,
                   selection: dict) -> str:
    with vanilla_path.open("rb") as source:
        vanilla_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    patched_size = patched_path.stat().st_size
    with patched_path.open("rb") as source:
        patched_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    with delta_path.open("rb") as source:
        delta_sha256 = hashlib.file_digest(source, "sha256").hexdigest()

    lines = [
        "format_version = 1",
        f"id = {_quote(package_id)}",
        f"version = {_quote(version)}",
        f"name = {_quote(name)}",
        'author = "acediez (Tweaks); PSXRecomp package generated locally"',
        'description = "Local MMX6 Tweaks profile; derives a private image from the verified stock disc."',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {_quote(GAME_ID)}",
        f"disc_sha256 = {_quote(vanilla_sha256)}",
        "",
        "[source]",
        'kind = "mmx6-tweaks-profile"',
        f"selection_json = {_quote(json.dumps(selection, sort_keys=True, separators=(',', ':')))}",
        "",
        "[[derived_disc]]",
        'kind = "vcdiff"',
        'patch = "assets/profile.xdelta3"',
        f"patch_sha256 = {_quote(delta_sha256)}",
        f"output_size = {patched_size}",
        f"output_sha256 = {_quote(patched_sha256)}",
    ]
    lines += ["", "[package_stats]", f"derived_image_bytes = {patched_size}", ""]
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
    parser.add_argument("--id", dest="package_id")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--name", default="Mega Man X6 Tweaks Profile")
    args = parser.parse_args()

    selection_text = (args.selection_file.read_text(encoding="utf-8")
                      if args.selection_file else args.selection)
    selection = json.loads(selection_text) if selection_text else {}
    engine = _load_engine()
    with tempfile.TemporaryDirectory(prefix="mmx6-tweaks-") as temporary:
        temporary_path = Path(temporary)
        if args.patched_bin:
            produced = args.patched_bin
        else:
            produced = temporary_path / "patched.bin"
            patchfile, _ = engine.apply_selection(
                selection_text, produced, vanilla=args.vanilla)
        delta = temporary_path / "profile.xdelta3"
        result = subprocess.run(
            [str(engine.XDELTA3_EXE), "-f", "-9", "-S", "lzma", "-e",
             "-s", str(args.vanilla), str(produced), str(delta)],
            capture_output=True, text=True)
        if result.returncode != 0 or not delta.exists():
            raise RuntimeError(
                f"xdelta3 package generation failed ({result.returncode}): "
                f"{result.stdout}{result.stderr}")
        _write_package(args, produced, delta, selection)
    return 0


def _write_package(args, patched_path: Path, delta_path: Path,
                   selection: dict) -> None:
    with patched_path.open("rb") as patched_file:
        patched_digest = hashlib.file_digest(patched_file, "sha256").digest()
    identity = hashlib.sha256(
        json.dumps(selection, sort_keys=True).encode("utf-8") +
        patched_digest).hexdigest()[:16]
    package_id = args.package_id or f"mmx6.tweaks.{identity}"
    manifest = build_manifest(
        args.vanilla, patched_path, delta_path, package_id=package_id,
        version=args.version, name=args.name, selection=selection)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        archive.writestr("manifest.toml", manifest)
        archive.writestr("selection.json",
                         json.dumps(selection, indent=2, sort_keys=True) + "\n")
        archive.write(delta_path, "assets/profile.xdelta3")
        archive.writestr(
            "README.txt",
            "Generated locally from a user-supplied MMX6 Tweaks profile.\n"
            "Tweaks research and patch payloads are credited to acediez.\n")
    print(f"wrote {args.out} ({package_id} {args.version})")


if __name__ == "__main__":
    raise SystemExit(main())
