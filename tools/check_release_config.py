#!/usr/bin/env python3
"""Reject release game.toml drift in codegen/runtime-sensitive sections."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEV_CONFIG = ROOT / "game.toml"
RELEASE_CONFIG = ROOT / "packaging" / "release" / "game.toml"
PARITY_SECTIONS = ("widescreen",)
MOD_OWNED_VIDEO_KEYS = {
    "auto_skip_fmv": False,
    "offer_skip_fmv": False,
    "offer_frame_interpolation": False,
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def flatten(value: Any, prefix: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}

    result: dict[str, Any] = {}
    for key, child in value.items():
        child_prefix = f"{prefix}.{key}" if prefix else key
        result.update(flatten(child, child_prefix))
    return result


def main() -> int:
    dev = load_toml(DEV_CONFIG)
    release = load_toml(RELEASE_CONFIG)
    failures: list[str] = []

    for section in PARITY_SECTIONS:
        dev_values = flatten(dev.get(section, {}), section)
        release_values = flatten(release.get(section, {}), section)
        for key in sorted(dev_values.keys() | release_values.keys()):
            if key not in release_values:
                failures.append(f"{key}: missing from release config")
            elif key not in dev_values:
                failures.append(f"{key}: release-only value {release_values[key]!r}")
            elif dev_values[key] != release_values[key]:
                failures.append(
                    f"{key}: dev={dev_values[key]!r}, "
                    f"release={release_values[key]!r}"
                )

    for key, expected in MOD_OWNED_VIDEO_KEYS.items():
        for label, config in (("dev", dev), ("release", release)):
            actual = config.get("video", {}).get(key)
            if actual != expected:
                failures.append(
                    f"video.{key}: {label}={actual!r}, expected {expected!r}"
                )

    if failures:
        print(
            "release game.toml has drifted from game.toml in a "
            "codegen/runtime-sensitive section:",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    sections = ", ".join(f"[{name}]" for name in PARITY_SECTIONS)
    print(f"release config parity passed for {sections} and mod-owned video keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
