#!/usr/bin/env python3
"""Remove permission-gated MMX6 Tweaks content from the public catalog.

The conversion tooling remains in the repository so the packages can be
regenerated after direct redistribution approval is recorded.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "mods" / "preloaded" / "packages"
WITHHELD_PACKAGES = (
    "mmx6.tweaks.assets",
    "mmx6.tweaks.extra-mugshots",
    "mmx6.tweaks.ingame-options",
)
NATIVE = PACKAGES / "mmx6.tweaks.native" / "1.10.5"
RETRANSLATION_ASSETS = NATIVE / "assets" / "retranslation"
NATIVE_MANIFEST = NATIVE / "manifest.toml"


def checked_remove_tree(path: Path, expected_parent: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != expected_parent.resolve():
        raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
        print(f"withheld {resolved.relative_to(ROOT)}")


def strip_retranslation_manifest() -> None:
    text = NATIVE_MANIFEST.read_text(encoding="utf-8")
    blocks = re.split(r"(?=^\[\[)", text, flags=re.MULTILINE)
    kept: list[str] = []
    for block in blocks:
        header = block.splitlines()[0] if block else ""
        is_duo_link = (
            header == "[[author_link]]"
            and re.search(r'^name = "DuoDynamo"$', block, re.MULTILINE)
        )
        is_retranslation_feature = (
            header == "[[feature]]"
            and re.search(r'^id = "retranslation"$', block, re.MULTILINE)
        )
        owns_retranslation_payload = re.search(
            r'^feature = "retranslation"$', block, re.MULTILINE
        )
        if is_duo_link or is_retranslation_feature or owns_retranslation_payload:
            continue
        kept.append(block)

    filtered = "".join(kept)
    parsed = tomllib.loads(filtered)
    if any(
        feature.get("id") == "retranslation"
        for feature in parsed.get("feature", [])
    ):
        raise RuntimeError("retranslation feature survived manifest filtering")
    for table in ("patch", "overlay", "constraint", "option"):
        if any(
            item.get("feature") == "retranslation"
            for item in parsed.get(table, [])
        ):
            raise RuntimeError(
                f"retranslation-owned [[{table}]] survived manifest filtering"
            )
    if "DuoDynamo" in filtered:
        raise RuntimeError("retranslation-only author link survived filtering")

    NATIVE_MANIFEST.write_text(filtered, encoding="utf-8", newline="\n")
    print(f"withheld retranslation from {NATIVE_MANIFEST.relative_to(ROOT)}")


def main() -> None:
    if not NATIVE_MANIFEST.is_file():
        raise RuntimeError(f"missing native manifest: {NATIVE_MANIFEST}")

    strip_retranslation_manifest()
    for package_id in WITHHELD_PACKAGES:
        checked_remove_tree(PACKAGES / package_id, PACKAGES)
    checked_remove_tree(RETRANSLATION_ASSETS, NATIVE / "assets")


if __name__ == "__main__":
    main()
