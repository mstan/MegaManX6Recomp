#!/usr/bin/env python3
"""Remove permission-gated MMX6 Tweaks portrait content from the public catalog.

The portrait conversion tooling remains in the repository so the packages can
be regenerated after direct redistribution approval is recorded.
"""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "mods" / "preloaded" / "packages"
WITHHELD_PACKAGES = (
    "mmx6.tweaks.assets",
    "mmx6.tweaks.extra-mugshots",
)


def checked_remove_tree(path: Path, expected_parent: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != expected_parent.resolve():
        raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
        print(f"withheld {resolved.relative_to(ROOT)}")


def main() -> None:
    for package_id in WITHHELD_PACKAGES:
        checked_remove_tree(PACKAGES / package_id, PACKAGES)


if __name__ == "__main__":
    main()
