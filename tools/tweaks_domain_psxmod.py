#!/usr/bin/env python3
"""Build exact stock-targeted MMX6 General, Stage, and Boss packages.

Only reviewed source closures are admitted. The converter reads the stock
USA v1.1 image and the user-supplied Tweaks source database directly; it does
not consume a patched disc, B01 image, or behavioral oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import tweaks_engine as engine
import tweaks_native_psxmod as native


ROOT = Path(__file__).resolve().parent.parent
STOCK_SHA256 = native.STOCK_SHA256
VERSION = "1.0.0"
DEFAULT_STOCK = (
    ROOT / "mmx6-tweaks" / "Mega Man X6 (USA) (v1.1).bin"
)
DEFAULT_SOURCE = engine.twr.DEFAULT_PATCHER_SRC
DEFAULT_PROFILE = engine.twr.DEFAULT_PROFILE
DEFAULT_OUT_DIR = ROOT / "build-mod-platform" / "test-psxmods"


@dataclass(frozen=True)
class Variant:
    value: str
    label: str
    selection: tuple[tuple[str, str], ...]
    closure: tuple[str, ...]


@dataclass(frozen=True)
class Feature:
    feature_id: str
    name: str
    description: str
    group: str
    source_controls: tuple[str, ...]
    variants: tuple[Variant, ...]
    option_id: str = ""
    option_label: str = ""
    option_type: str = "choice"
    option_min: int = 0
    option_max: int = 0
    option_step: int = 1
    option_default: str = ""


@dataclass(frozen=True)
class Domain:
    package_id: str
    name: str
    filename: str
    features: tuple[Feature, ...]
    deferred: tuple[tuple[str, str], ...] = ()
    excluded: tuple[tuple[str, str], ...] = ()
    resolver: str = "declarative"
    version: str = VERSION


@dataclass(frozen=True)
class Patch:
    feature_id: str
    variant: str
    target: str
    location: int
    expected: bytes
    replacement: bytes


def toggle(
    feature_id: str, source: str, name: str, description: str,
    group: str, closure: tuple[str, ...] | None = None,
) -> Feature:
    return Feature(
        feature_id,
        name,
        description,
        group,
        (source,),
        (
            Variant(
                "enabled",
                "Enabled",
                ((source, "1"),),
                closure or (source,),
            ),
        ),
    )


GENERAL = Domain(
    "mmx6.tweaks.general",
    "Mega Man X6 General Tweaks",
    "MMX6-Tweaks-General.psxmod",
    (
        toggle(
            "continue_from_stage_start",
            "LivesSwitch05",
            "Continues Restart Stage",
            "Continue from the beginning of the current stage.",
            "Lives and Health",
        ),
        toggle(
            "skip_navigator_dialogues",
            "DialogueDisable01",
            "Skip Navigator Dialogues",
            "Disable Navigator stage dialogues and alerts.",
            "Dialogue",
        ),
        toggle(
            "skip_stage_dialogues",
            "DialogueDisable02",
            "Skip Stage Dialogues",
            "Skip other dialogue sequences during stages.",
            "Dialogue",
        ),
        toggle(
            "skip_nightmare_souls_explanation",
            "DialogueDisable04",
            "Skip Nightmare Souls Explanation",
            "Skip the Mission Report Nightmare Souls explanation.",
            "Dialogue",
        ),
        toggle(
            "skip_stage_select_briefings",
            "DialogueDisable03",
            "Skip Stage Select Briefings",
            "Skip Stage Select screen briefing dialogue.",
            "Dialogue",
        ),
        toggle(
            "share_life_energy_upgrades",
            "SharedStats01",
            "Share Life and Energy Upgrades",
            "Share Life Up and weapon-energy upgrades between X and Zero.",
            "Shared Character Stats",
        ),
        toggle(
            "share_souls_rank",
            "SharedStats02",
            "Share Nightmare Souls and Rank",
            "Share Nightmare Souls and Hunter Rank between X and Zero.",
            "Shared Character Stats",
        ),
        toggle(
            "code_one_unlocks_secret_armors",
            "UnlockCode01",
            "Code #1 Unlocks Both Secret Armors",
            "Make the first title-screen code unlock both secret armors.",
            "Unlockables",
            ("NewGame", "UnlockCode01"),
        ),
        toggle(
            "code_two_starts_with_zero",
            "UnlockCode02",
            "Code #2 Starts With Zero",
            "Make the second title-screen code unlock Zero from the start.",
            "Unlockables",
            ("NewGame", "ZeroStart01", "UnlockCode02"),
        ),
        toggle(
            "combine_secret_codes",
            "UnlockCode03",
            "Combine Secret Codes",
            "Allow title-screen codes #1 and #2 to be combined.",
            "Unlockables",
            ("NewGame", "UnlockCode03"),
        ),
        toggle(
            "black_zero_unlock_effect",
            "UnlockEffect01",
            "Black Zero Unlock Effect",
            "Show the unlock effect when Black Zero is unlocked in-game.",
            "Unlockables",
        ),
        toggle(
            "continuous_cutscene_voice",
            "CutsceneVoice01",
            "Continuous Cutscene Voice",
            "Continue voiced dialogue after the first page-complete press.",
            "Cutscenes",
        ),
        toggle(
            "remember_character_armor",
            "MenuDefaultSel01",
            "Remember Character and Armor",
            "Remember the previous Stage Select character and armor choice.",
            "Menus",
        ),
    ),
    (
        (
            "ArmorByPart01",
            "Incomplete armor requires the unowned B01 ArmorByPart_Common "
            "foundation and ordered shared unlock rewrites.",
        ),
        (
            "ArmorByPart02",
            "Intrinsic incomplete-armor mode selector; deferred with "
            "ArmorByPart01 rather than exposed as an independent row.",
        ),
        (
            "ArmorByPart03",
            "Intrinsic incomplete-armor mode selector; deferred with "
            "ArmorByPart01 rather than exposed as an independent row.",
        ),
        (
            "ArmorByPart04",
            "Conditional incomplete-armor palette option; deferred with its "
            "owning feature.",
        ),
        (
            "LivesSwitch01",
            "Silently adds lives-display and Exit Stage helpers and needs a "
            "cross-domain composer.",
        ),
        (
            "IngameOptions01",
            "Source normalization makes the standalone selection payloadless; "
            "it needs typed ownership with its dependent settings.",
        ),
    ),
)

STAGES = Domain(
    "mmx6.tweaks.stage-modes",
    "Mega Man X6 Stage Modes",
    "MMX6-Tweaks-Stage-Modes.psxmod",
    (
        Feature(
            "falling_ceiling_behavior",
            "Falling Ceiling Behavior",
            "Choose crouching behavior under the Recycle Lab falling ceiling.",
            "Recycle Lab",
            (
                "AutoCrouching01",
                "AutoCrouching02",
                "AutoCrouching03",
                "RecycleCeiling01",
            ),
            (
                Variant(
                    "automatic",
                    "Automatic Crouching",
                    (("AutoCrouching02", "1"),),
                    ("AutoCrouching02",),
                ),
                Variant(
                    "manual",
                    "Hold Manual Crouch",
                    (("AutoCrouching03", "1"),),
                    ("AutoCrouching02", "AutoCrouching03"),
                ),
                Variant(
                    "disable_ceiling",
                    "Disable Ceiling Movement",
                    (("RecycleCeiling01", "1"),),
                    ("RecycleCeiling01",),
                ),
            ),
            "mode",
            "Behavior",
        ),
        toggle(
            "move_recycle_lab_hidden_teleport",
            "StageMod0404",
            "Move Hidden Area Teleport",
            (
                "Move the Recycle Lab hidden-area teleport to the left side "
                "of the long jump."
            ),
            "Recycle Lab",
        ),
    ),
    (),
)

BOSS_ATTACKS = Domain(
    "mmx6.tweaks.boss-attacks",
    "Mega Man X6 Boss Attack Tweaks",
    "MMX6-Tweaks-Boss-Attacks.psxmod",
    (
        toggle(
            "yammark_reduce_idle_time",
            "BossMod0105",
            "Commander Yammark: Reduce Idle Time",
            "Reduce idle time between Commander Yammark attacks.",
            "Commander Yammark",
        ),
    ),
)

DAMAGE_RULES = Domain(
    "mmx6.tweaks.damage-rules",
    "Mega Man X6 Damage Rules",
    "MMX6-Tweaks-Damage-Rules.psxmod",
    (
        toggle(
            "gate_vulnerable_to_normal_attacks",
            "DmgTableGate01",
            "Gate Vulnerable to Normal Attacks",
            "Allow ordinary attacks to damage Gate.",
            "Gate",
        ),
        Feature(
            "gate_orb_explosion_damage",
            "Gate Orb Explosion Damage",
            "Set the damage dealt by Gate's own orb explosions.",
            "Gate",
            ("DmgTableGateDmg01",),
            (
                Variant(
                    "4",
                    "Stock",
                    (("DmgTableGateDmg01", "4"),),
                    (),
                ),
                Variant(
                    "1",
                    "Minimum",
                    (("DmgTableGateDmg01", "1"),),
                    ("DmgTableGateDmg01",),
                ),
                Variant(
                    "127",
                    "Maximum",
                    (("DmgTableGateDmg01", "127"),),
                    ("DmgTableGateDmg01",),
                ),
            ),
            "damage",
            "Damage",
            "integer",
            1,
            127,
            1,
            "4",
        ),
    ),
    (),
    (
        *tuple(
            (
                f"DmgTableCurrent{index}",
                "Damage-table category navigation selector; not a game "
                "configuration value.",
            )
            for index in range(1, 6)
        ),
        (
            "DmgTableInput_S",
            "Damage-table editor selection plumbing; not a game control.",
        ),
        (
            "DmgTableInput_V",
            "Dynamic 33-by-63 table cell editor template; not one scalar "
            "launcher control.",
        ),
        (
            "ErrorRecalc",
            "Patcher error-recalculation action; not a game control.",
        ),
        (
            "PatchList_BaseHacks",
            "Internal patch-list sentinel; not a game control.",
        ),
        (
            "HelpButton",
            "GUI help action; not a game control.",
        ),
    ),
    "builtin:mmx6-damage-rules",
    "1.1.0",
)

DOMAINS = (GENERAL, STAGES, BOSS_ATTACKS, DAMAGE_RULES)


def sha256_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def source_plan(
    db: engine.twr.TweaksDB,
    base: dict[str, str],
    variant: Variant,
) -> list[tuple[int, bytes]]:
    if not variant.closure:
        return []
    selected = dict(base)
    selected.update(variant.selection)
    _normalized, patchfile, patch_list, values, synth = engine._assemble(
        db, selected, base
    )
    inherited = set(db.patchlist_base) | set(db.patchlist_script)
    owned = tuple(name for name in patch_list if name not in inherited)
    if patchfile != "b01" or owned != variant.closure:
        raise AssertionError(
            f"{variant.value} source closure changed: "
            f"patchfile={patchfile!r}, owned={owned!r}"
        )
    if synth:
        raise AssertionError(
            f"{variant.value} unexpectedly synthesized {sorted(synth)!r}"
        )
    _file_patch, files = engine.build_filelist(db, selected, base)
    if files:
        raise AssertionError(
            f"{variant.value} unexpectedly inserts files: {files!r}"
        )
    writes: list[tuple[int, bytes]] = []
    for name in owned:
        for data_hex, raw_offset in engine.expand_entry(
            db, name, patchfile, values, synth
        ):
            for split_hex, split_offset in engine.ecc_split(
                data_hex, raw_offset
            ):
                writes.append((split_offset, bytes.fromhex(split_hex)))
    return writes


def semantic_write(
    stock: native.RawMode2Image,
    members: dict[int, native.IndexedMember],
    load_address: int,
    raw_offset: int,
    replacement: bytes,
) -> tuple[str, int, bytes]:
    user_offset = native.raw_to_user_offset(raw_offset)
    entry, file_offset = stock.containing_file(
        user_offset, len(replacement)
    )
    expected = native.read_iso_file_range(
        stock, entry.name, file_offset, len(replacement)
    )
    if entry.name == native.SLUS_NAME:
        return (
            "main_exe",
            load_address + file_offset - native.USER_SECTOR,
            expected,
        )
    if entry.name != "ROCK_X6.BIN":
        raise ValueError(
            f"raw source range 0x{raw_offset:X} targets unsupported "
            f"{entry.name}"
        )
    member, relative = native.containing_member(
        members, file_offset, len(replacement)
    )
    if member.payload[relative : relative + len(replacement)] != expected:
        raise AssertionError("indexed-member stock identity changed")
    disc_user = (
        stock.entries["ROCK_X6.BIN"].lba * native.USER_SECTOR
        + member.file_offset
        + relative
    )
    return "disc_user", disc_user, expected


def compose_variant(
    stock: native.RawMode2Image,
    members: dict[int, native.IndexedMember],
    load_address: int,
    feature_id: str,
    variant: Variant,
    raw_writes: list[tuple[int, bytes]],
) -> list[Patch]:
    replacement_bytes: dict[tuple[str, int], int] = {}
    expected_bytes: dict[tuple[str, int], int] = {}
    for raw_offset, replacement in raw_writes:
        target, location, expected = semantic_write(
            stock, members, load_address, raw_offset, replacement
        )
        for index, value in enumerate(replacement):
            key = (target, location + index)
            previous_expected = expected_bytes.get(key)
            if (
                previous_expected is not None
                and previous_expected != expected[index]
            ):
                raise AssertionError("overlap has inconsistent stock guards")
            expected_bytes[key] = expected[index]
            replacement_bytes[key] = value

    patches: list[Patch] = []
    keys = sorted(expected_bytes, key=lambda item: (item[0], item[1]))
    at = 0
    while at < len(keys):
        target, begin = keys[at]
        end = at + 1
        while (
            end < len(keys)
            and keys[end][0] == target
            and keys[end][1] == keys[end - 1][1] + 1
        ):
            end += 1
        span = keys[at:end]
        patches.append(
            Patch(
                feature_id,
                variant.value,
                target,
                begin,
                bytes(expected_bytes[key] for key in span),
                bytes(replacement_bytes[key] for key in span),
            )
        )
        at = end
    return patches


def build_domain(
    domain: Domain,
    stock_path: Path,
    source_path: Path,
    profile_path: Path,
) -> tuple[list[Patch], dict]:
    if sha256_file(stock_path) != STOCK_SHA256:
        raise ValueError("stock image is not supported USA v1.1")
    db = engine.twr.TweaksDB(source_path)
    base = engine.twr.load_profile(profile_path)
    patches: list[Patch] = []
    evidence: dict[str, dict] = {}
    with native.RawMode2Image(stock_path) as stock:
        exe = stock.read_file(native.SLUS_NAME)
        load_address = int.from_bytes(exe[0x18:0x1C], "little")
        members = native.indexed_archive_members(
            stock.read_file("ROCK_X6.BIN")
        )
        for feature in domain.features:
            variant_evidence = {}
            for variant in feature.variants:
                raw = source_plan(db, base, variant)
                resolved = compose_variant(
                    stock,
                    members,
                    load_address,
                    feature.feature_id,
                    variant,
                    raw,
                )
                patches.extend(resolved)
                variant_evidence[variant.value] = {
                    "selection": dict(variant.selection),
                    "closure": list(variant.closure),
                    "source_write_count": len(raw),
                    "resolved_patch_count": len(resolved),
                }
            evidence[feature.feature_id] = {
                "source_controls": ", ".join(feature.source_controls),
                "variants": variant_evidence,
            }
    report = {
        "package": {
            "id": domain.package_id,
            "version": domain.version,
            "feature_rows": len(domain.features),
        },
        "source_controls": sorted(
            control
            for feature in domain.features
            for control in feature.source_controls
        ),
        "excluded_source_controls": [
            {
                "source_control": source_control,
                "reason": reason,
            }
            for source_control, reason in domain.excluded
        ],
        "deferred_source_controls": [
            {
                "source_control": source_control,
                "reason": reason,
            }
            for source_control, reason in domain.deferred
        ],
        "provenance": {
            "stock_sha256": sha256_file(stock_path),
            "source_dat_sha256": sha256_file(source_path / "data" / "_dat.ahk"),
            "default_profile_sha256": sha256_file(profile_path),
            "patched_disc_oracle_used": False,
        },
        "features": evidence,
        "validation": {
            "source_closures_exact": True,
            "stock_guards_direct": True,
            "internal_overlaps_composed": True,
            "external_files_rejected": True,
        },
    }
    return patches, report


def manifest_text(domain: Domain, patches: list[Patch]) -> str:
    lines = [
        "format_version = 3",
        f"id = {toml_quote(domain.package_id)}",
        f"version = {toml_quote(domain.version)}",
        f"name = {toml_quote(domain.name)}",
        (
            'author = "acediez; PSXRecomp integration by '
            'DuoDynamo and NectarHime"'
        ),
        (
            'description = "Independent exact stock-disc MMX6 Tweaks '
            'features."'
        ),
        'license = "Generated locally; original credits retained"',
        f"resolver = {toml_quote(domain.resolver)}",
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {toml_quote(native.GAME_ID)}",
        f"disc_sha256 = {toml_quote(STOCK_SHA256)}",
    ]
    by_feature = {feature.feature_id: feature for feature in domain.features}
    for feature in domain.features:
        lines.extend(
            (
                "",
                "[[feature]]",
                f"id = {toml_quote(feature.feature_id)}",
                f"name = {toml_quote(feature.name)}",
                f"description = {toml_quote(feature.description)}",
                f"group = {toml_quote(feature.group)}",
                "default_enabled = false",
            )
        )
        if feature.option_id:
            lines.extend(
                (
                    "",
                    "[[option]]",
                    f"feature = {toml_quote(feature.feature_id)}",
                    f"id = {toml_quote(feature.option_id)}",
                    f"label = {toml_quote(feature.option_label)}",
                    f"description = {toml_quote(feature.description)}",
                    f"group = {toml_quote(feature.group)}",
                    f"type = {toml_quote(feature.option_type)}",
                )
            )
            if feature.option_type == "choice":
                lines.append(
                    f"default = {toml_quote(feature.option_default or feature.variants[0].value)}"
                )
                for variant in feature.variants:
                    lines.extend(
                        (
                            "",
                            "[[option.choice]]",
                            f"value = {toml_quote(variant.value)}",
                            f"label = {toml_quote(variant.label)}",
                        )
                    )
            elif feature.option_type == "integer":
                lines.extend(
                    (
                        f"min = {feature.option_min}",
                        f"max = {feature.option_max}",
                        f"step = {feature.option_step}",
                        f"default = {feature.option_default or feature.variants[0].value}",
                    )
                )
            else:
                raise ValueError(
                    f"unsupported option type {feature.option_type!r}"
                )
    if domain.resolver != "declarative":
        return "\n".join(lines) + "\n"
    for patch in patches:
        feature = by_feature[patch.feature_id]
        lines.extend(
            (
                "",
                "[[patch]]",
                f"feature = {toml_quote(patch.feature_id)}",
                f"target = {toml_quote(patch.target)}",
                (
                    f"address = {patch.location}"
                    if patch.target == "main_exe"
                    else f"offset = {patch.location}"
                ),
                f"expected = {toml_quote(patch.expected.hex().upper())}",
                f"replace = {toml_quote(patch.replacement.hex().upper())}",
                "order = 0",
            )
        )
        if feature.option_id:
            lines.append(
                "when = { "
                + feature.option_id
                + " = "
                + toml_quote(patch.variant)
                + " }"
            )
    return "\n".join(lines) + "\n"


def archive_bytes(manifest: str, report: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {
            "README.txt": (
                "Generated from the supported stock USA v1.1 image and "
                "user-supplied MMX6 Tweaks source. No patched disc, derived "
                "disc, or behavioral oracle is included or required.\n"
            ),
            "conversion-report.json":
                json.dumps(report, indent=2, sort_keys=True) + "\n",
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
    parser.add_argument("--patcher-source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--default-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    reports = []
    for domain in DOMAINS:
        patches, report = build_domain(
            domain, args.stock, args.patcher_source, args.default_profile
        )
        manifest = manifest_text(domain, patches)
        first = archive_bytes(manifest, report)
        if first != archive_bytes(manifest, report):
            raise AssertionError(f"{domain.package_id} is not deterministic")
        reports.append(report)
        if not args.verify_only:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            output = args.out_dir / domain.filename
            output.write_bytes(first)
            print(f"wrote {output}")
    print(json.dumps(reports, indent=2, sort_keys=True))
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
