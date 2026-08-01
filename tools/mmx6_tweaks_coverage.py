#!/usr/bin/env python3
"""Produce an exact source-control ledger from generated conversion reports."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import tweaks_resolver as resolver


def semantic_version_key(path: Path) -> tuple[int, int, int]:
    parts = path.name.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(
            f"package version directory is not numeric X.Y.Z: {path}"
        )
    return tuple(int(part) for part in parts)


def discover_latest_reports(mods_root: Path) -> list[Path]:
    packages = mods_root / "packages"
    if not packages.is_dir():
        raise ValueError(f"mods root lacks packages directory: {mods_root}")
    reports: list[Path] = []
    for package in sorted(path for path in packages.iterdir() if path.is_dir()):
        versions = [
            version
            for version in package.iterdir()
            if version.is_dir()
            and (version / "conversion-report.json").is_file()
        ]
        if not versions:
            continue
        latest = max(versions, key=semantic_version_key)
        reports.append(latest / "conversion-report.json")
    return reports


def collect_report_ledgers(
    report_paths: list[Path],
) -> tuple[set[str], dict[str, str], list[dict]]:
    represented: set[str] = set()
    excluded: dict[str, str] = {}
    report_packages = []
    for path in report_paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        controls = report.get("source_controls")
        if not isinstance(controls, list) or not all(
            isinstance(value, str) for value in controls
        ):
            raise ValueError(f"{path} lacks a string source_controls ledger")
        represented.update(controls)
        exclusions = report.get("excluded_source_controls", [])
        if not isinstance(exclusions, list):
            raise ValueError(
                f"{path} has a non-list excluded_source_controls ledger"
            )
        for exclusion in exclusions:
            if (
                not isinstance(exclusion, dict)
                or not isinstance(exclusion.get("source_control"), str)
                or not isinstance(exclusion.get("reason"), str)
                or not exclusion["reason"].strip()
            ):
                raise ValueError(
                    f"{path} has an invalid excluded_source_controls entry"
                )
            control = exclusion["source_control"]
            reason = exclusion["reason"].strip()
            previous = excluded.get(control)
            if previous is not None and previous != reason:
                raise ValueError(
                    f"conflicting exclusion reasons for {control}"
                )
            excluded[control] = reason
        report_packages.append(
            {
                "path": str(path),
                "package_version": report.get("package_version"),
                "source_controls": len(set(controls)),
                "excluded_source_controls": len(exclusions),
            }
        )
    overlap = represented & set(excluded)
    if overlap:
        raise ValueError(
            "controls cannot be both represented and excluded: "
            + ", ".join(sorted(overlap))
        )
    return represented, excluded, report_packages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "reports",
        nargs="*",
        type=Path,
        help="conversion-report.json files whose source_controls are complete",
    )
    parser.add_argument(
        "--mods-root",
        type=Path,
        help="also use the latest installed version of every package",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report_paths = list(args.reports)
    if args.mods_root:
        report_paths.extend(discover_latest_reports(args.mods_root))
    report_paths = list(dict.fromkeys(path.resolve() for path in report_paths))
    if not report_paths:
        raise ValueError("provide reports or --mods-root")

    db = resolver.TweaksDB(resolver.DEFAULT_PATCHER_SRC)
    catalog = resolver.parse_gui_catalog(resolver.DEFAULT_PATCHER_SRC, db)
    by_id: dict[str, dict] = {}
    duplicate_entries: Counter[str] = Counter()
    for row in catalog:
        duplicate_entries[row["var"]] += 1
        by_id.setdefault(row["var"], row)

    represented, excluded, report_packages = collect_report_ledgers(
        report_paths
    )

    catalog_ids = set(by_id)
    remaining = catalog_ids - represented - set(excluded)
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
        "excluded_source_controls": len(set(excluded) & catalog_ids),
        "classified_source_controls": len(
            (represented | set(excluded)) & catalog_ids
        ),
        "remaining_source_controls": len(remaining),
        "remaining_by_tab": dict(sorted(grouped.items())),
        "unknown_report_controls": sorted(
            (represented | set(excluded)) - catalog_ids
        ),
        "excluded": [
            {
                "var": var,
                "tab": by_id[var]["tab_title"] if var in by_id else None,
                "reason": reason,
            }
            for var, reason in sorted(excluded.items())
        ],
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
