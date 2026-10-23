"""Prepare an isolated LOCAL X6 candidate; never launch, publish or modify cards.

Every destination must be new and on F: or G: on Windows. Automated runners
must use environment.json; owner handoffs use the normal-audio launcher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib

FORBIDDEN = {"psx.enhancement.cd-speed", "psx.enhancement.fast-loading"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_output(path: Path) -> Path:
    path = path.resolve()
    if os.name == "nt" and path.drive.upper() not in {"F:", "G:"}:
        raise ValueError("Generated output must be on F: or G:")
    return path


def prepare(build: Path, source: Path, output: Path, disc: Path,
            card: Path | None = None, *, automated: bool = False) -> dict:
    output = local_output(output)
    if output.exists():
        raise ValueError("Output already exists; choose a fresh candidate directory")
    build, source, disc = build.resolve(), source.resolve(), disc.resolve(strict=True)
    exe = build / "mmx6-runtime.exe"
    if not exe.is_file() or not (build / "bios/openbios.bin").is_file():
        raise ValueError("Build must contain mmx6-runtime.exe and bios/openbios.bin")
    if output == build or output.is_relative_to(build) or build.is_relative_to(output):
        raise ValueError("Candidate must be outside the source build")
    config_path = source / "game.toml"
    config_text = config_path.read_text(encoding="utf-8-sig")
    config = tomllib.loads(config_text)
    boot_exe = disc.parent / Path(config["game"]["exe"]).name
    if not boot_exe.is_file():
        raise ValueError(f"Original boot executable missing beside disc: {boot_exe}")
    # Enumerate and validate the staged catalog before writing the candidate.
    catalog = build / "mods/bundled"
    packages = []
    for manifest in sorted(catalog.glob("*/*/manifest.toml")):
        item = tomllib.loads(manifest.read_text(encoding="utf-8-sig"))
        if item["id"] not in FORBIDDEN:
            packages.append((manifest, item))
    if not any(item["id"] == "mmx6.local-coop" for _, item in packages):
        raise ValueError("Staged co-op catalog missing")
    if card is not None:
        card = card.resolve(strict=True)
        if card.stat().st_size != 128 * 1024:
            raise ValueError("Native card must be a raw 128 KiB PlayStation card")
    output.mkdir(parents=True)
    shutil.copy2(exe, output / exe.name)
    for dll in build.glob("*.dll"):
        shutil.copy2(dll, output / dll.name)
    for folder in ("assets", "bios"):
        if (build / folder).is_dir():
            shutil.copytree(build / folder, output / folder)
    for manifest, item in packages:
        relative = manifest.parent.relative_to(catalog)
        shutil.copytree(manifest.parent, output / "mods/bundled" / relative)
    for folder in ("saves", "temp", "cache", "data", "appdata", "resident", "logs"):
        (output / folder).mkdir()
    if card is not None:
        shutil.copy2(card, output / "saves/card1.mcd")
    # Settings, controller choices and keyboard overrides are deliberately not
    # copied from someone else's playtest. Both controllers start unassigned.
    settings = '''[video]
renderer = "opengl"
fullscreen = 0
window_width = 960
aspect_ratio = "4:3"
rewind = false
frame_interpolation = false
[controller]
p1_device = "none"
p2_device = "none"
[launcher]
skip_launcher = false
'''
    if automated:
        # The sampler requires a connected P1 device even for debug overrides.
        # Keyboard here is a virtual local pad; the runner owns its inputs.
        settings = settings.replace('p1_device = "none"', 'p1_device = "keyboard"')
    (output / "settings.toml").write_text(settings, encoding="utf-8")
    # No loading/video skip cheats are enabled for the default baseline.
    (output / "mods/state.toml").write_text('''format_version = 2
[[package]]
id = "mmx6.local-coop"
version = "0.0.1"
[[feature]]
package_id = "mmx6.local-coop"
id = "prototype"
enabled = true
''', encoding="utf-8")
    # Absolute resource paths are explicit even though the executable receives
    # --disc and --memcard-dir. Other original title settings stay intact.
    import re
    config_text = re.sub(r'(?m)^exe\s*=.*$', 'exe = '+json.dumps(boot_exe.as_posix()), config_text)
    config_text = re.sub(r'(?m)^disc\s*=.*$', 'disc = '+json.dumps(disc.as_posix()), config_text)
    config_text = re.sub(r'(?m)^memcard_dir\s*=.*$', 'memcard_dir = '+json.dumps((output / "saves").as_posix()), config_text)
    # Autocompilation requires the full developer tree. Qualification begins
    # with the original interpreter fallback rather than a broken relative tool.
    config_text = re.sub(r'(?m)^overlay_autocompile_cmd\s*=.*$', 'overlay_autocompile_cmd = ""', config_text)
    (output / "game.toml").write_text(config_text, encoding="utf-8")
    env = {
        "TEMP": str(output / "temp"), "TMP": str(output / "temp"),
        "LOCALAPPDATA": str(output / "data"), "APPDATA": str(output / "appdata"),
        "XDG_CACHE_HOME": str(output / "cache"),
        "PSX_RESIDENT_CACHE": str(output / "resident"),
        "PSX_OVERLAY_CACHE_DIR": str(output / "cache"),
        "PSX_OVERLAY_CAPTURE_ROOT": str(output / "cache"),
        "PSX_OVERLAY_CAPTURES": str(output / "cache/overlay_captures.json"),
        "PSX_OVERLAY_AUTOCOMPILE_OFF": "1", "PSX_DEV_INPUT": "0",
    }
    (output / "environment.json").write_text(json.dumps(env, indent=2)+"\n", encoding="utf-8")
    launch_lines = ["$ErrorActionPreference = 'Stop'", "Set-Location -LiteralPath $PSScriptRoot"]
    for key, value in env.items():
        launch_lines.append(f"$env:{key} = '{value.replace(chr(39), chr(39)*2)}'")
    launch_lines += ["Remove-Item Env:SDL_AUDIODRIVER -ErrorAction SilentlyContinue",
                     "Remove-Item Env:PSX_HEADLESS -ErrorAction SilentlyContinue",
                     "& (Join-Path $PSScriptRoot 'mmx6-runtime.exe') --game (Join-Path $PSScriptRoot 'game.toml') --memcard-dir (Join-Path $PSScriptRoot 'saves') --launcher"]
    (output / "Play X6 Co-op.ps1").write_text("\n".join(launch_lines)+"\n", encoding="utf-8")
    receipt = {
        "format_version": 1, "kind": "local_candidate_preparation",
        "runtime_qualified": False, "build": str(build), "source": str(source),
        "output": str(output), "disc": str(disc),
        "automated_profile": automated,
        "exe_sha256": sha256(exe), "game_config_sha256": sha256(output / "game.toml"),
        "packages": [item["id"] for _, item in packages],
        "source_card": str(card) if card else None,
        "source_card_sha256": sha256(card) if card else None,
        "limitations": ["No gameplay, controller or network qualification from staging",
                         "Overlay compilation disabled; no AOT performance claim",
                         "Owner must assign both local controllers in the launcher"],
    }
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--card", type=Path)
    parser.add_argument("--automated", action="store_true", help="Connect a private virtual P1 pad for muted automated QA")
    args = parser.parse_args()
    try:
        result = prepare(args.build, args.source, args.out, args.disc, args.card, automated=args.automated)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        parser.exit(1, f"Preparation failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
