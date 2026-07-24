#!/usr/bin/env python3
"""Produce an exact source-control ledger from generated conversion reports."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import tweaks_resolver as resolver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "reports",
        nargs="+",
        type=Path,
        help="conversion-report.json files whose source_controls are complete",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    db = resolver.TweaksDB(resolver.DEFAULT_PATCHER_SRC)
    catalog = resolver.parse_gui_catalog(resolver.DEFAULT_PATCHER_SRC, db)
    by_id: dict[str, dict] = {}
    duplicate_entries: Counter[str] = Counter()
    for row in catalog:
        duplicate_entries[row["var"]] += 1
        by_id.setdefault(row["var"], row)

    represented: set[str] = set()
    report_packages = []
    for path in args.reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        controls = report.get("source_controls")
        if not isinstance(controls, list) or not all(
            isinstance(value, str) for value in controls
        ):
            raise ValueError(f"{path} lacks a string source_controls ledger")
        represented.update(controls)
        report_packages.append(
            {
                "path": str(path),
                "package_version": report.get("package_version"),
                "source_controls": len(set(controls)),
            }
        )

    catalog_ids = set(by_id)
    remaining = catalog_ids - represented
    grouped = Counter(by_id[var]["tab_title"] for var in remaining)
    result = {
        "catalog_entries": len(catalog),
        "catalog_unique_source_controls": len(catalog_ids),
        "duplicate_catalog_entries": {
            var: count
            for var, count in sorted(duplicate_entries.items())
            if count > 1
        },
        "represented_source_controls": len(represented & catalog_ids),
        "remaining_source_controls": len(remaining),
        "remaining_by_tab": dict(sorted(grouped.items())),
        "unknown_report_controls": sorted(represented - catalog_ids),
        "reports": report_packages,
        "remaining": [
            {
                "var": var,
                "tab": by_id[var]["tab_title"],
                "section": by_id[var]["section"],
                "subsection": by_id[var]["subsection"],
                "type": by_id[var]["type"],
                "label": by_id[var]["label"],
            }
            for var in sorted(remaining)
        ],
    }
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
