#!/usr/bin/env python3
"""Audit why the remaining Zero-technique controls are not independent mods."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_engine as engine
import tweaks_resolver as resolver


DAT_SHA256 = (
    "6e78b35142f30548c5bf6760a835773110d0cece863052a4b278722476a46707"
)
PROFILE_SHA256 = (
    "5070be21fbcb3a277925eb6f7b3d06699355f37d562f3f55d9bfec1d34130c0a"
)
REJECTED_CONTROLS = (
    *(f"ZeroSentsuizanInput{index:02d}" for index in range(1, 4)),
    *(f"ZeroSentsuizanMode{index:02d}" for index in range(1, 4)),
    *(f"ZeroEnsuizanInput{index:02d}" for index in range(1, 5)),
    "ZeroEnsuizanMode01",
    "ZeroEnsuizanReps01",
    "ZeroGuardShellInput01",
    "ZeroGuardShellInput02",
    "ZeroGuardShellInput04",
    "ZeroGuardShellInput05",
    "ZeroYammarInput01",
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _radio(changes: dict[str, str], prefix: str, chosen: int, count: int):
    for index in range(1, count + 1):
        changes[f"{prefix}{index:02d}"] = "1" if index == chosen else "0"


def _case(db, profile, label: str, changes: dict[str, str]) -> dict:
    merged = OrderedDict(profile)
    merged.update(changes)
    normalized, patchfile, patch_list, values, synth = engine._assemble(
        db, merged, profile
    )
    changed_by_gui = {
        control: {
            "submitted": changes.get(control, profile.get(control)),
            "normalized": normalized.get(control),
        }
        for control in REJECTED_CONTROLS
        if normalized.get(control) != changes.get(
            control, profile.get(control)
        )
    }
    return {
        "case": label,
        "submitted": changes,
        "patchfile": patchfile,
        "gui_cross_forcing": changed_by_gui,
        "zero_patch_list": [
            item for item in patch_list if item.startswith("Zero")
        ],
        "zero_synthesized_writes": sorted(
            item for item in synth if item.startswith("Zero")
        ),
        "filtered_values": {
            key: value for key, value in values.items()
            if key.startswith("Zero")
        },
    }


def build_audit(source_dir: Path, profile_path: Path) -> dict:
    if sha256_file(source_dir / "data" / "_dat.ahk") != DAT_SHA256:
        raise ValueError("MMX6 Tweaks _dat.ahk is not reviewed v2.6.1")
    if sha256_file(profile_path) != PROFILE_SHA256:
        raise ValueError("MMX6 Tweaks default profile identity changed")
    db = resolver.TweaksDB(source_dir)
    profile = resolver.load_profile(profile_path)

    sentsuizan_down: dict[str, str] = {}
    _radio(sentsuizan_down, "ZeroSentsuizanInput", 2, 3)
    ensuizan_up: dict[str, str] = {}
    _radio(ensuizan_up, "ZeroEnsuizanInput", 2, 4)
    guard_down: dict[str, str] = {}
    _radio(guard_down, "ZeroGuardShellInput", 3, 4)
    # Guard Shell IDs are 01,02,04,05 rather than a contiguous radio suffix.
    guard_down = {
        "ZeroGuardShellInput01": "0",
        "ZeroGuardShellInput02": "0",
        "ZeroGuardShellInput04": "1",
        "ZeroGuardShellInput05": "0",
    }
    air_special = {"ZeroEnsuizanMode01": "1"}
    _radio(air_special, "ZeroEnsuizanInput", 4, 4)
    hold_sentsuizan: dict[str, str] = {}
    _radio(hold_sentsuizan, "ZeroSentsuizanMode", 3, 3)
    _radio(hold_sentsuizan, "ZeroSentsuizanInput", 2, 3)
    translated_hint = dict(sentsuizan_down)
    translated_hint.update({"ScriptPatch01": "0", "ScriptPatch02": "1"})

    cases = [
        _case(db, profile, "sentsuizan-down-special", sentsuizan_down),
        _case(db, profile, "ensuizan-up-special", ensuizan_up),
        _case(db, profile, "guard-shell-down-special", guard_down),
        _case(db, profile, "air-ensuizan-special", air_special),
        _case(db, profile, "hold-sentsuizan", hold_sentsuizan),
        _case(db, profile, "retranslation-input-hint", translated_hint),
    ]
    by_name = {item["case"]: item for item in cases}
    if not {
        "ZeroEnsuizanInput02", "ZeroYammarInput01"
    }.issubset(by_name["sentsuizan-down-special"]["gui_cross_forcing"]):
        raise AssertionError("Sentsuizan cross-forcing evidence changed")
    if (
        by_name["guard-shell-down-special"]["gui_cross_forcing"].get(
            "ZeroGuardShellInput04", {}
        ).get("normalized") != "0"
    ):
        raise AssertionError("Guard Shell/Ensuizan interlock evidence changed")
    if not {
        "ZeroEnsuizanAirDirection",
        "ZeroEnsuizanAirButton",
    }.issubset(by_name["air-ensuizan-special"]["zero_synthesized_writes"]):
        raise AssertionError("Air Ensuizan synthesis evidence changed")
    if not {
        "ZeroSentsuizanInput_AND_1",
        "ZeroSentsuizanInput_AND_2",
    }.issubset(by_name["hold-sentsuizan"]["zero_synthesized_writes"]):
        raise AssertionError("Hold Sentsuizan synthesis evidence changed")
    if "ZeroInputHint_Sentsuizan" not in (
        by_name["retranslation-input-hint"]["zero_synthesized_writes"]
    ):
        raise AssertionError("retranslation hint synthesis evidence changed")

    return {
        "audit": "MMX6 Zero technique independent-mod boundary",
        "patcher_dat_sha256": sha256_file(
            source_dir / "data" / "_dat.ahk"
        ),
        "default_profile_sha256": sha256_file(profile_path),
        "rejected_source_controls": sorted(REJECTED_CONTROLS),
        "decision": {
            "status": "deferred",
            "reason": (
                "The current package resolver receives only its own selection. "
                "A single Zero-techniques feature could contain the upstream "
                "Sentsuizan, Ensuizan, Guard Shell, and Yammar input coupling, "
                "but it still cannot faithfully reproduce the conditional "
                "Retranslation input-hint writes without seeing the resolved "
                "localization/script feature state."
            ),
            "product_boundary": (
                "Do not expose the original four input groups as independent "
                "left-pane rows. They silently force each other in Tweaks. The "
                "acceptable UX is one coherent Zero-techniques feature with "
                "validated option combinations, once cross-feature hint "
                "composition exists."
            ),
            "required_primitive": (
                "cross-package resolved context or a typed input-hint provider, "
                "followed by a product decision that removes silent GUI forcing"
            ),
        },
        "cases": cases,
        "coverage_note": (
            "This is a rejection audit, not a conversion report; it deliberately "
            "does not publish source_controls."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--patcher-source", type=Path, required=True)
    parser.add_argument("--default-profile", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = build_audit(args.patcher_source, args.default_profile)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
