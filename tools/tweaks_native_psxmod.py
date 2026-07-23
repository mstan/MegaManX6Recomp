#!/usr/bin/env python3
"""Convert reviewed MMX6 Tweaks features to native stock-disc .psxmods.

This is deliberately fail-closed.  A feature is emitted only after its Tweaks
changes have been assigned to stable stock-disc ranges or guarded executable
operations.  Reference patched images are conversion oracles, never runtime
payloads.

The reviewed slice contains independent title, script, intro/demo, and
Nightmare-effect features. The retranslation is converted as logical
ROCK_X6.DAT records, not as the s02 rebuilt container, and includes only its
owned ScriptTextDisplay/ScriptMenuAlign executable edits. Every simple Tweaks
option is re-resolved from the patcher's source database at conversion time;
PatchList_Base writes are evidence only and are never inherited implicitly.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

RAW_SECTOR = 2352
USER_SECTOR = 2048
USER_HEADER = 24
GAME_ID = "SLUS-01395"
SLUS_NAME = "SLUS_013.95"
STOCK_SHA256 = (
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318"
)

ROOT = Path(__file__).absolute().parent.parent
MAIN_CHECKOUT = ROOT.parent / "MegaManX6Recomp"


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


DEFAULT_TWEAKS = first_existing(
    MAIN_CHECKOUT / "mmx6-tweaks",
    ROOT / "mmx6-tweaks",
)
DEFAULT_STOCK = DEFAULT_TWEAKS / "Mega Man X6 (USA) (v1.1).bin"
DEFAULT_ORACLE_DIR = ROOT / "build-mod-platform" / "test-mod-variants"
DEFAULT_MATRIX_DIR = DEFAULT_ORACLE_DIR / "tweaks-matrix"
DEFAULT_PATCHER_DATA = DEFAULT_TWEAKS / "_patcher" / "run_extracted" / "data"
DEFAULT_PATCHER_SOURCE = (
    DEFAULT_TWEAKS
    / "_patcher"
    / "src_extracted"
    / "Mega Man X6 Tweaks Patcher (v2.6.1)"
    / "_src"
    / "data"
    / "_dat.ahk"
)


@dataclass(frozen=True)
class IsoEntry:
    name: str
    lba: int
    size: int
    is_directory: bool


class RawMode2Image:
    """Minimal ISO9660 reader over a MODE2/2352 track."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._file = self.path.open("rb")
        self.raw_size = self.path.stat().st_size
        self.user_size = (self.raw_size // RAW_SECTOR) * USER_SECTOR
        self.entries = self._read_root_entries()

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def read_user(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > self.user_size:
            raise ValueError(
                f"disc-user read outside {self.path.name}: {offset}+{size}"
            )
        result = bytearray()
        while size:
            lba, within = divmod(offset, USER_SECTOR)
            count = min(size, USER_SECTOR - within)
            self._file.seek(lba * RAW_SECTOR + USER_HEADER + within)
            chunk = self._file.read(count)
            if len(chunk) != count:
                raise RuntimeError(f"short read from {self.path}")
            result += chunk
            offset += count
            size -= count
        return bytes(result)

    def read_file(self, name: str) -> bytes:
        entry = self.entries[name.upper()]
        if entry.is_directory:
            raise ValueError(f"{name} is a directory")
        return self.read_user(entry.lba * USER_SECTOR, entry.size)

    def containing_file(self, offset: int, size: int) -> tuple[IsoEntry, int]:
        for entry in self.entries.values():
            begin = entry.lba * USER_SECTOR
            if not entry.is_directory and begin <= offset:
                if offset + size <= begin + entry.size:
                    return entry, offset - begin
        raise ValueError(
            f"disc-user range 0x{offset:X}+0x{size:X} is not inside an ISO file"
        )

    def _read_root_entries(self) -> dict[str, IsoEntry]:
        pvd = self.read_user(16 * USER_SECTOR, USER_SECTOR)
        if pvd[1:6] != b"CD001":
            raise ValueError(f"{self.path} has no ISO9660 PVD")
        root = pvd[156:190]
        root_lba = struct.unpack("<I", root[2:6])[0]
        root_size = struct.unpack("<I", root[10:14])[0]
        directory = self.read_user(root_lba * USER_SECTOR, root_size)
        entries: dict[str, IsoEntry] = {}
        cursor = 0
        while cursor < len(directory):
            length = directory[cursor]
            if length == 0:
                cursor = ((cursor // USER_SECTOR) + 1) * USER_SECTOR
                continue
            record = directory[cursor : cursor + length]
            cursor += length
            if len(record) < 34:
                continue
            raw_name = record[33 : 33 + record[32]].decode(
                "latin1", errors="replace"
            )
            if raw_name in ("\x00", "\x01"):
                continue
            name = raw_name.split(";", 1)[0].upper()
            entries[name] = IsoEntry(
                name=name,
                lba=struct.unpack("<I", record[2:6])[0],
                size=struct.unpack("<I", record[10:14])[0],
                is_directory=bool(record[25] & 2),
            )
        return entries


@dataclass(frozen=True)
class Overlay:
    feature: str
    label: str
    user_offset: int
    expected: bytes
    replace: bytes
    source: str = ""
    raw_offset: int | None = None
    iso_file: str = ""
    file_offset: int | None = None
    when: tuple[str, str] | None = None


@dataclass(frozen=True)
class Patch:
    feature: str
    label: str
    address: int
    expected: bytes
    replace: bytes
    when: tuple[str, str] | None = None


@dataclass(frozen=True)
class FeatureSpec:
    """One user-facing feature and its exact reviewed Tweaks source closure."""

    feature_id: str
    name: str
    description: str
    group: str
    source_option: str
    target: str
    expected_writes: tuple[tuple[int, str], ...]
    source_value: str = "1"


@dataclass(frozen=True)
class ExpectedSourceWrite:
    raw_offset: int
    size: int
    payload_hex: str = ""
    payload_sha256: str = ""


@dataclass(frozen=True)
class ConfigVariant:
    value: str
    label: str
    selection: tuple[tuple[str, str], ...]
    expected_owned: tuple[str, ...]
    expected_writes: tuple[ExpectedSourceWrite, ...]


@dataclass(frozen=True)
class ConfigFeatureSpec:
    feature_id: str
    name: str
    description: str
    group: str
    target: str
    variants: tuple[ConfigVariant, ...]
    option_id: str = ""
    option_label: str = ""


@dataclass(frozen=True)
class DatRoute:
    raw_offset: int
    record_id: int
    subasset_index: int
    asset_type: int
    relative_offset: int
    size: int
    stock_sha256: str


@dataclass(frozen=True)
class IndexedMember:
    member_id: int
    file_offset: int
    payload: bytes


INTRO_FEATURES = (
    FeatureSpec(
        "skip_capcom_video",
        "Skip Capcom Video",
        "Skip the Capcom logo video during boot.",
        "Game Intro",
        "IntroSkip01",
        "main_exe",
        (
            (0x1D92F1B8, "00000000"),
            (0x1D92F200, "00000000"),
        ),
    ),
    FeatureSpec(
        "skip_opening_video",
        "Skip Opening Video",
        "Skip the opening movie during boot.",
        "Game Intro",
        "IntroSkip02",
        "main_exe",
        ((0x1D92FB78, "00000000"),),
    ),
    FeatureSpec(
        "disable_title_demos",
        "Disable Title Demos",
        "Keep the title-screen demo countdown from starting attract-mode demos.",
        "Game Intro",
        "IntroSkip03",
        "main_exe",
        ((0x1D93082C, "00000000"),),
    ),
)

NIGHTMARE_FEATURES = (
    FeatureSpec(
        "disable_nightmare_bug",
        "Disable Nightmare Bug",
        "Disable the Nightmare Bug stage effect.",
        "Nightmare Effects",
        "NightmareDisable01",
        "rock_x6_bin",
        ((0x1DA95A0C, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_ice",
        "Disable Nightmare Ice",
        "Disable the Nightmare Ice stage effect.",
        "Nightmare Effects",
        "NightmareDisable02",
        "rock_x6_bin",
        ((0x1DA95A0F, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_fire",
        "Disable Nightmare Fire",
        "Disable the Nightmare Fire effect, including the North Pole walls.",
        "Nightmare Effects",
        "NightmareDisable03",
        "rock_x6_bin",
        (
            (0x1DA95A12, "000000"),
            (0x1D9F3AD8, "2FBC030800000000"),
            (0x1DB00414, "A1B50308"),
        ),
    ),
    FeatureSpec(
        "disable_nightmare_iron",
        "Disable Nightmare Iron",
        "Disable the Nightmare Iron stage effect.",
        "Nightmare Effects",
        "NightmareDisable04",
        "rock_x6_bin",
        ((0x1DA95A15, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_cube",
        "Disable Nightmare Cube",
        "Disable the Nightmare Cube stage effect.",
        "Nightmare Effects",
        "NightmareDisable05",
        "rock_x6_bin",
        ((0x1DA95A18, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_rain",
        "Disable Nightmare Rain",
        "Disable the Nightmare Rain stage effect.",
        "Nightmare Effects",
        "NightmareDisable06",
        "rock_x6_bin",
        ((0x1DA95A1B, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_mirror",
        "Disable Nightmare Mirror",
        "Disable the Nightmare Mirror stage effect.",
        "Nightmare Effects",
        "NightmareDisable07",
        "rock_x6_bin",
        ((0x1DA95A1E, "000000"),),
    ),
    FeatureSpec(
        "disable_nightmare_dark",
        "Disable Nightmare Dark",
        "Disable the Nightmare Dark stage effect.",
        "Nightmare Effects",
        "NightmareDisable08",
        "rock_x6_bin",
        ((0x1DA95A21, "000000"),),
    ),
)

QOL_FEATURES = (
    FeatureSpec(
        "alternate_default_controls",
        "Alternate Default Controls",
        "Use the MMX6 Tweaks alternate controller layout as the default.",
        "Controls",
        "DefOptions01",
        "main_exe",
        (
            (
                0x1D98BB90,
                "8000100008004000040002000100",
            ),
        ),
    ),
    FeatureSpec(
        "faster_cutscene_text",
        "Faster Cutscene Text",
        "Reduce the delay between voiced cutscene text characters.",
        "Dialogue",
        "CutsceneVoice02",
        "main_exe",
        ((0x1D935A40, "02000224"),),
    ),
    FeatureSpec(
        "mute_navigator_alerts",
        "Mute Navigator Alerts",
        "Mute the Navigator voice call used for stage alerts.",
        "Dialogue",
        "DialogueDisable07",
        "main_exe",
        ((0x1D96D92C, "00000000"),),
    ),
    FeatureSpec(
        "disable_rescue_extra_lives",
        "No Extra Lives From Reploids",
        "Rescuing a Reploid does not add an extra life.",
        "Lives and Pickups",
        "LivesSwitch02",
        "main_exe",
        ((0x1D968C74, "00000000"),),
    ),
    FeatureSpec(
        "disable_pickup_extra_lives",
        "No Extra Lives From Pickups",
        "Extra-life pickups do not increase the life counter.",
        "Lives and Pickups",
        "LivesSwitch03",
        "main_exe",
        ((0x1D96807C, "00000000"),),
    ),
    FeatureSpec(
        "disable_rescue_health_refill",
        "No Health Refill From Reploids",
        "Rescuing a Reploid does not refill the active character's health.",
        "Lives and Pickups",
        "LivesSwitch04",
        "main_exe",
        ((0x1D968968, "463B0108"),),
    ),
)

MOVEMENT_FEATURES = (
    FeatureSpec(
        "air_moves_after_dash_jump",
        "Air Moves After Dash Jump",
        "Allow air actions after a ground or wall dash jump.",
        "Movement",
        "DashGlobal02",
        "main_exe",
        (
            (0x1D951D0C, "860020A2"),
            (0x1D952358, "860020A2"),
        ),
    ),
    FeatureSpec(
        "unlimited_air_moves",
        "Unlimited Air Moves",
        "Remove the normal once-per-airtime movement limit.",
        "Movement",
        "DashGlobal03",
        "main_exe",
        ((0x1D94FA9C, "00000000"),),
    ),
    FeatureSpec(
        "disable_double_tap_dash",
        "Disable Double-Tap Dash",
        "Disable dashing from double-tapping a direction; the dash button remains.",
        "Movement",
        "DashGlobal04",
        "main_exe",
        ((0x1D950ADC, "0000023400000334"),),
    ),
    FeatureSpec(
        "unlimited_dash_duration",
        "Unlimited Dash Duration",
        "Prevent dash-duration counters from expiring.",
        "Movement",
        "DashDurationUnlimited01",
        "mixed",
        (
            (0x1D950CE8, "00000000"),
            (0x1D950DD4, "00000000"),
            (0x1D9B60D8, "00000000"),
        ),
    ),
    FeatureSpec(
        "unlock_x_hover",
        "Unlock X's Hover",
        "Allow X's hover action without its normal armor restriction.",
        "Movement",
        "HoverUnlock01",
        "main_exe",
        ((0x1D956A60, "00000000"),),
    ),
    FeatureSpec(
        "unlimited_high_jump",
        "Unlimited High Jump",
        "Prevent the High Jump attachment's duration counters from expiring.",
        "Movement",
        "HighJumpUnlimited01",
        "mixed",
        (
            (0x1D94C988, "00000000"),
            (0x1D9C33E4, "00000000"),
        ),
    ),
    FeatureSpec(
        "always_drop_nightmare_orbs",
        "Always Drop Nightmare Orbs",
        "Make defeated Nightmare Viruses drop orbs on every defeat.",
        "Nightmare Effects",
        "OrbSwitch01",
        "main_exe",
        ((0x1D95AE2C, "000080A0"),),
    ),
)

SMALL_DATA_FEATURES = (
    FeatureSpec(
        "shadow_saber_cancellable",
        "Shadow Saber Cancellable",
        "Enable cancellation flags on Shadow Armor's four saber attacks.",
        "Combat",
        "SaberCancellable02",
        "rock_x6_bin",
        (
            (0x1D9BFAE1, "42"),
            (0x1D9BFAE5, "41"),
            (0x1D9BFAE9, "40"),
            (0x1D9BFAED, "40"),
        ),
    ),
    FeatureSpec(
        "restore_x_charged_shot_voice",
        "Restore X Charged-Shot Voice",
        "Use the restored voice clip ID for X's charged shot.",
        "Audio",
        "VoiceClip03",
        "main_exe",
        ((0x1D957460, "08"),),
    ),
    FeatureSpec(
        "restore_zero_giga_attack_voice",
        "Restore Zero Giga-Attack Voice",
        "Use the restored voice clip ID for Zero's Giga Attack.",
        "Audio",
        "VoiceClip04",
        "rock_x6_bin",
        ((0x1D9C09F4, "0A"),),
    ),
    FeatureSpec(
        "yammark_firefly_resistance",
        "Increase Yammark Firefly Resistance",
        "Increase the resistance value used by Commander Yammark's fireflies.",
        "Bosses",
        "BossMod0106",
        "rock_x6_bin",
        (
            (0x1D9E5AB4, "60"),
            (0x1DB31104, "60"),
        ),
    ),
    FeatureSpec(
        "indestructible_yammark_orbs",
        "Indestructible Yammark Green Orbs",
        "Use the no-contact damage table for Yammark's green orbs.",
        "Bosses",
        "BossMod0102",
        "rock_x6_bin",
        (
            (0x1D9E80B8, "1C4A"),
            (0x1DB33708, "1C4A"),
        ),
    ),
)

STATIC_SPIKE_FEATURES = (
    FeatureSpec(
        "blade_mach_dash_unlimited_repetitions",
        "Unlimited Blade Mach Dash Repetitions",
        "Allow Blade Armor to repeat Mach Dash without landing first.",
        "Movement",
        "MachDashUnlimited01",
        "main_exe",
        ((0x1D956BE4, "00000000"),),
    ),
    FeatureSpec(
        "disable_falcon_jump_air_dash",
        "Disable Falcon Jump Air Dash",
        "Prevent Falcon Armor's jump input from starting an air dash.",
        "Movement",
        "FalconDash01",
        "main_exe",
        ((0x1D956AE4, "00000234"),),
        source_value="0",
    ),
    FeatureSpec(
        "higher_ceiling_jump",
        "Higher Ceiling Jump",
        "Use the reviewed MMX6 Tweaks preset for a higher ceiling jump.",
        "Movement",
        "HighJumpHeight01",
        "main_exe",
        ((0x1D94C884, "C000"),),
        source_value="192",
    ),
    FeatureSpec(
        "disable_x_saber_cancelling",
        "Disable X Saber Cancelling",
        "Disable cancellation flags on X's four standard saber attacks.",
        "Combat",
        "SaberCancellable01",
        "rock_x6_bin",
        (
            (0x1D9BFAC1, "02"),
            (0x1D9BFAC5, "00"),
            (0x1D9BFAC9, "00"),
            (0x1D9BFACD, "00"),
        ),
        source_value="0",
    ),
    FeatureSpec(
        "allow_xtreme_item_drops",
        "Allow Item Drops on Xtreme",
        "Allow enemies to drop health and weapon-energy items on Xtreme.",
        "Game Rules",
        "DifficultySwitch01",
        "main_exe",
        ((0x1D9682A8, "00000000"),),
        source_value="0",
    ),
    FeatureSpec(
        "prevent_nightmare_orb_reversion",
        "Prevent Nightmare Orb Reversion",
        "Keep Nightmare Viruses from reverting after their orb is left alone.",
        "Nightmare Effects",
        "OrbSwitch02",
        "main_exe",
        ((0x1D95A3D0, "31000234"),),
        source_value="0",
    ),
    FeatureSpec(
        "yammark_speed_orbs_easy_normal",
        "Faster Yammark Orbs on Easy and Normal",
        "Increase green-orb movement speed in Yammark fights on Easy and Normal.",
        "Bosses",
        "BossMod0103",
        "rock_x6_bin",
        (
            (0x1D9E8118, "0400"),
            (0x1DB33768, "0400"),
            (0x1D9E812C, "FCFF"),
            (0x1DB3377C, "FCFF"),
        ),
    ),
    FeatureSpec(
        "yammark_speed_orbs_xtreme",
        "Faster Yammark Orbs on Xtreme",
        "Increase green-orb movement speed in Yammark fights on Xtreme.",
        "Bosses",
        "BossMod0104",
        "rock_x6_bin",
        (
            (0x1D9E81B0, "80180200"),
            (0x1DB33800, "80180200"),
        ),
    ),
    FeatureSpec(
        "wolfang_debris_all_difficulties",
        "Wolfang Debris on All Difficulties",
        "Enable Blizzard Wolfang's falling ice debris on every difficulty.",
        "Bosses",
        "BossMod0201",
        "rock_x6_bin",
        (
            (0x1D9F80D4, "00000000"),
            (0x1DB38B2C, "00000000"),
        ),
    ),
    FeatureSpec(
        "wolfang_ice_spikes_all_levels",
        "Wolfang Ice Spikes at All Levels",
        "Enable Blizzard Wolfang's ice-spike attack at every boss level.",
        "Bosses",
        "BossMod0202",
        "rock_x6_bin",
        (
            (0x1D9F6814, "03000234"),
            (0x1DB3739C, "03000234"),
        ),
    ),
    FeatureSpec(
        "wolfang_indestructible_ice_blocks",
        "Indestructible Wolfang Ice Blocks",
        "Make Blizzard Wolfang's ice blocks and debris indestructible.",
        "Bosses",
        "BossMod0203",
        "rock_x6_bin",
        (
            (0x1D9F7C64, "3C43"),
            (0x1DB387EC, "3C43"),
            (0x1D9F7E84, "3C43"),
            (0x1DB388DC, "3C43"),
        ),
    ),
    FeatureSpec(
        "wolfang_indestructible_ice_spikes",
        "Indestructible Wolfang Ice Spikes",
        "Make Blizzard Wolfang's ice-spike projectiles indestructible.",
        "Bosses",
        "BossMod0204",
        "rock_x6_bin",
        (
            (0x1D9F6834, "00000000"),
            (0x1DB373BC, "00000000"),
        ),
    ),
)


def _expected_byte(raw_offset: int, value: int) -> ExpectedSourceWrite:
    return ExpectedSourceWrite(raw_offset, 1, f"{value:02X}")


def _nearest_nonstock(stock_value: int, values: range) -> tuple[int, ...]:
    return tuple(
        sorted(
            (value for value in values if value != stock_value),
            key=lambda value: (abs(value - stock_value), value),
        )
    )


RANK_CONFIG = (
    ("uh", "UH", 4, 1),
    ("pa", "PA", 3, 1),
    ("ga", "GA", 2, 1),
    ("sa", "SA", 2, 0),
    ("a", "A", 1, 0),
    ("b", "B", 0, 0),
    ("c", "C", 0, 0),
    ("d", "D", 0, 0),
)

RANK_NORMAL_PART_FEATURES = tuple(
    ConfigFeatureSpec(
        f"normal_part_slots_rank_{rank_id}",
        f"Normal Part Slots at Rank {rank_label}",
        f"Change the number of normal Parts available at rank {rank_label}.",
        "Rank and Progression",
        "rock_x6_bin",
        tuple(
            ConfigVariant(
                str(value),
                f"{value} Part" if value == 1 else f"{value} Parts",
                ((f"RankNPart{index:02d}", str(value)),),
                (f"RankNPart{index:02d}",),
                (
                    _expected_byte(
                        0x1DA959CB + index,
                        value,
                    ),
                ),
            )
            for value in _nearest_nonstock(stock_normal, range(5))
        ),
        option_id="slots",
        option_label="Normal Part slots",
    )
    for index, (rank_id, rank_label, stock_normal, _stock_limited) in enumerate(
        RANK_CONFIG, 1
    )
)

RANK_LIMITED_PART_FEATURES = tuple(
    ConfigFeatureSpec(
        (
            f"disable_limited_parts_rank_{rank_id}"
            if stock_limited
            else f"enable_limited_parts_rank_{rank_id}"
        ),
        (
            f"Disable Limited Parts at Rank {rank_label}"
            if stock_limited
            else f"Enable Limited Parts at Rank {rank_label}"
        ),
        (
            f"Prevent Limited Parts from being equipped at rank {rank_label}."
            if stock_limited
            else f"Allow one Limited Part to be equipped at rank {rank_label}."
        ),
        "Rank and Progression",
        "rock_x6_bin",
        (
            ConfigVariant(
                "",
                "",
                ((f"RankLPart{index:02d}", str(1 - stock_limited)),),
                (f"RankLPart{index:02d}",),
                (
                    _expected_byte(
                        0x1DA959D3 + index,
                        1 - stock_limited,
                    ),
                ),
            ),
        ),
    )
    for index, (rank_id, rank_label, _stock_normal, stock_limited) in enumerate(
        RANK_CONFIG, 1
    )
)

BOSS_RANK_CONFIG = (
    ("d", "D", 1),
    ("c", "C", 1),
    ("b", "B", 1),
    ("a", "A", 1),
    ("sa", "SA", 2),
    ("ga", "GA", 3),
    ("pa", "PA", 4),
    ("uh", "UH", 4),
)

BOSS_RANK_FEATURES = tuple(
    ConfigFeatureSpec(
        f"boss_level_rank_{rank_id}",
        f"Boss Level at Rank {rank_label}",
        f"Change the boss level used while the Hunter Rank is {rank_label}.",
        "Rank and Progression",
        "main_exe",
        tuple(
            ConfigVariant(
                f"level_{level}",
                f"Level {level}",
                ((f"BossRank{index:02d}", f"Lv. {level}"),),
                (f"BossRank{index:02d}",),
                (
                    _expected_byte(
                        0x1D990DC0 - index,
                        level - 1,
                    ),
                ),
            )
            for level in _nearest_nonstock(stock_level, range(1, 5))
        ),
        option_id="level",
        option_label="Boss level",
    )
    for index, (rank_id, rank_label, stock_level) in enumerate(
        BOSS_RANK_CONFIG, 1
    )
)

STAGE_CONFIG_FEATURES = (
    ConfigFeatureSpec(
        "amazon_area_extended_ceiling",
        "Extend Amazon Area Ceiling",
        "Extend the ceiling above Amazon Area's blind-jump section.",
        "Stages",
        "mixed",
        (
            ConfigVariant(
                "",
                "",
                (("StageMod01", "1"),),
                ("StageMod01",),
                (
                    ExpectedSourceWrite(
                        0x1E644298,
                        320,
                        payload_sha256=(
                            "f52e5b0264519565d5742b130d1fbdc457bd193385a5dcce4"
                            "f383faae9f34349"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1E6469C8,
                        160,
                        payload_sha256=(
                            "4e15f65d6458c1caa5945906251c492af97ed0c06c3933767"
                            "2c46dee4c662207"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1D9EB058,
                        24,
                        "00040000EA09E00600040000A00A600700040000700A3007",
                    ),
                ),
            ),
        ),
    ),
    ConfigFeatureSpec(
        "secret_lab_2_platform",
        "Add Secret Lab 2-2 Platform",
        "Add the platform that removes the Parts or Armor requirement for X.",
        "Stages",
        "mixed",
        (
            ConfigVariant(
                "",
                "",
                (("StageMod02", "1"),),
                ("StageMod02",),
                (
                    ExpectedSourceWrite(
                        0x1F7068D8,
                        512,
                        payload_sha256=(
                            "82ca44f60f2c271224aaefbfd8e10db36caa5fad4ad0c19d"
                            "f1d4aeddd0a60712"
                        ),
                    ),
                ),
            ),
        ),
    ),
    ConfigFeatureSpec(
        "secret_lab_1_spikes",
        "Secret Lab 1 Spikes",
        "Choose how many spikes to remove from Secret Lab 1.",
        "Stages",
        "mixed",
        (
            ConfigVariant(
                "remove_some",
                "Remove Some",
                (
                    ("StageMod0301", "0"),
                    ("StageMod0302", "1"),
                    ("StageMod0303", "0"),
                ),
                ("StageMod0301", "StageMod0302"),
                (
                    ExpectedSourceWrite(
                        0x1F517208,
                        512,
                        payload_sha256=(
                            "5785b17d0a897a13b7f5b33e916d668dc9acdcbbce795227"
                            "797ae4c0a48cda98"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1F518998,
                        512,
                        payload_sha256=(
                            "ca0d30ef0f5a354a6e0fa3a6fa7c2c98c5ac4775003362b"
                            "5a871cabc23be4fc0"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1F519DF8,
                        512,
                        payload_sha256=(
                            "6c016c855cc0b78e11b73ec235ab220e608fade7f510f9c3"
                            "4e144aa1697f92eb"
                        ),
                    ),
                ),
            ),
            ConfigVariant(
                "remove_more",
                "Remove More",
                (
                    ("StageMod0301", "0"),
                    ("StageMod0302", "0"),
                    ("StageMod0303", "1"),
                ),
                ("StageMod0301", "StageMod0303"),
                (
                    ExpectedSourceWrite(
                        0x1F517208,
                        512,
                        payload_sha256=(
                            "1f8d55f821b42e3eefca48054e21c201db54dd7e3a9788ff"
                            "e8549a266ae0324a"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1F518998,
                        512,
                        payload_sha256=(
                            "d8fc60f73ba4811e514a43aac8e4ca282ca27065fcd4ff7a"
                            "a64f8f3c18dc7c04"
                        ),
                    ),
                    ExpectedSourceWrite(
                        0x1F519DF8,
                        512,
                        payload_sha256=(
                            "b570c2108d63baf40a8de523cd9cf0efd68a28fb538819ae"
                            "ee6153bfb57fd044"
                        ),
                    ),
                ),
            ),
        ),
        option_id="removal",
        option_label="Spike layout",
    ),
    ConfigFeatureSpec(
        "recycle_lab_ceiling_extension",
        "Recycle Lab Ceiling Extension",
        "Extend the Recycle Lab ceiling section by one or two tiles.",
        "Stages",
        "mixed",
        (
            ConfigVariant(
                "one_tile",
                "One Tile",
                (
                    ("StageMod0401", "0"),
                    ("StageMod0402", "1"),
                    ("StageMod0403", "0"),
                ),
                ("StageMod0401", "StageMod0402"),
                (
                    ExpectedSourceWrite(
                        0x1E956388,
                        288,
                        payload_sha256=(
                            "d3ded7ce0793b63af79fb256994554e2eff21d06e6111fd75"
                            "97bc7e2c4370a32"
                        ),
                    ),
                ),
            ),
            ConfigVariant(
                "two_tiles",
                "Two Tiles",
                (
                    ("StageMod0401", "0"),
                    ("StageMod0402", "0"),
                    ("StageMod0403", "1"),
                ),
                ("StageMod0401", "StageMod0403"),
                (
                    ExpectedSourceWrite(
                        0x1E956388,
                        288,
                        payload_sha256=(
                            "7e67eaafac9ec652854dbce9901aae528a00a0761d0768d3d"
                            "8d3a5e46ab938d1"
                        ),
                    ),
                ),
            ),
        ),
        option_id="extension",
        option_label="Extension",
    ),
)

CONFIG_FEATURES = (
    RANK_NORMAL_PART_FEATURES
    + RANK_LIMITED_PART_FEATURES
    + BOSS_RANK_FEATURES
    + (
        ConfigFeatureSpec(
            "yammark_xtreme_behavior",
            "Yammark Xtreme Behavior",
            "Make Commander Yammark always use the Xtreme behavior path.",
            "Bosses",
            "rock_x6_bin",
            (
                ConfigVariant(
                    "",
                    "",
                    (("BossMod0101", "1"),),
                    ("BossMod0101",),
                    (
                        ExpectedSourceWrite(0x1D9E80F4, 4, "02000434"),
                        ExpectedSourceWrite(0x1DB33744, 4, "02000434"),
                    ),
                ),
            ),
        ),
    )
    + STAGE_CONFIG_FEATURES
)

STAGE_DAT_ROUTES = {
    route.raw_offset: route
    for route in (
        DatRoute(
            0x1E644298,
            95,
            7,
            0,
            0x7EC0,
            320,
            "bc43bab0635f0965bbd696e68111d3ce11d9987fdfed462591421ebae6b2778f",
        ),
        DatRoute(
            0x1E6469C8,
            95,
            7,
            0,
            0xA000,
            160,
            "52c8425a2753ab3496a71ba240212fc8e584d1d8f02627d4cf60088fad43c097",
        ),
        DatRoute(
            0x1F7068D8,
            114,
            9,
            0,
            0x7C00,
            512,
            "c5cb8ee4196dc5184cd734a4fd460c06016cd74fdf5f20dbc772639c4bce1fac",
        ),
        DatRoute(
            0x1F517208,
            112,
            9,
            0,
            0x8E00,
            512,
            "7d50a6d50120affb4a5537b0ba89b6effaa61e5188915c7c239afbb3f6ea494e",
        ),
        DatRoute(
            0x1F518998,
            112,
            9,
            0,
            0xA200,
            512,
            "224f2929bd8f6fc4c909d8d7a533f9e17c9ca6b33b5306114cf2cb51e1767537",
        ),
        DatRoute(
            0x1F519DF8,
            112,
            9,
            0,
            0xB400,
            512,
            "c19f938c9627ffea3c985ee0ba327a27560e79e26e9a30c31d8b91e0e183f44f",
        ),
        DatRoute(
            0x1E956388,
            98,
            7,
            0,
            0x9600,
            288,
            "2cd2cf021e2afa4e2eeedfba2765163ed1a164203ebf59c55f4b2f09de5c215b",
        ),
    )
}

SIMPLE_FEATURES = (
    INTRO_FEATURES
    + NIGHTMARE_FEATURES
    + QOL_FEATURES
    + MOVEMENT_FEATURES
    + SMALL_DATA_FEATURES
    + STATIC_SPIKE_FEATURES
)
EXIT_STAGE_VARIANTS = {
    "main_stages": {
        "label": "Main Stages",
        "source_option": "ExitButton02",
        "writes": ((0x1D948BE8, "00000000"),),
    },
    "everywhere": {
        "label": "Everywhere",
        "source_option": "ExitButton03",
        "writes": (
            (0x1D948BCC, "00000000"),
            (0x1D948BE8, "00000000"),
        ),
    },
}
FEATURE_SPECS = {item.feature_id: item for item in SIMPLE_FEATURES}
CONFIG_FEATURE_SPECS = {item.feature_id: item for item in CONFIG_FEATURES}
EXIT_STAGE_FEATURE_ID = "exit_stage_availability"
ALL_FEATURE_IDS = (
    "title_screen",
    "retranslation",
    *(item.feature_id for item in SIMPLE_FEATURES),
    *(item.feature_id for item in CONFIG_FEATURES),
    EXIT_STAGE_FEATURE_ID,
)


TITLE_SCREEN_VARIANTS = (
    ("rockman_japan", "Rockman (Japan)", "TitleScreen02"),
    ("rockman_china", "Rockman (China)", "TitleScreen05"),
    ("mega_man_custom_a", "Mega Man (Custom A)", "TitleScreen04"),
    ("mega_man_custom_b", "Mega Man (Custom B)", "TitleScreen03"),
)

TITLE_ASSET_ROUTES = {
    0x1F165968: ("background_tileset", 107, 8, 0x10014),
    0x1DC0DE58: ("background_palette", 26, 0, 0x5),
    0x1F112538: ("press_start_tileset", 107, 1, 0x10016),
    0x1F12E768: ("press_start_assembly", 107, 3, 0xA),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def raw_to_user_offset(raw_offset: int) -> int:
    lba, within = divmod(raw_offset, RAW_SECTOR)
    if not USER_HEADER <= within < USER_HEADER + USER_SECTOR:
        raise ValueError(
            f"raw offset 0x{raw_offset:X} is outside sector user data"
        )
    return lba * USER_SECTOR + within - USER_HEADER


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path}")


def indexed_archive_members(data: bytes) -> dict[int, IndexedMember]:
    """Parse the strict {id,size} table used by ROCK_X6.BIN.

    The table occupies the first 0x800-byte sector. Payloads follow in table
    order and are independently rounded up to 0x800 bytes. Requiring the entire
    layout prevents a plausible-looking raw offset from becoming ownership.
    """
    if len(data) < 2 * USER_SECTOR or len(data) % USER_SECTOR:
        raise ValueError("indexed archive is not sector aligned")
    entries: list[tuple[int, int]] = []
    for offset in range(0, USER_SECTOR, 8):
        member_id, size = struct.unpack_from("<II", data, offset)
        if member_id == 0 and size == 0:
            break
        if (
            member_id == 0
            or size < 4
            or size > 2_000_000
            or (entries and member_id <= entries[-1][0])
        ):
            raise ValueError("invalid indexed archive table")
        entries.append((member_id, size))
    if len(entries) < 4:
        raise ValueError("indexed archive has too few members")
    cursor = USER_SECTOR
    members: dict[int, IndexedMember] = {}
    for member_id, size in entries:
        if cursor + size > len(data):
            raise ValueError(f"indexed member {member_id} is truncated")
        members[member_id] = IndexedMember(
            member_id, cursor, data[cursor : cursor + size]
        )
        cursor = (cursor + size + USER_SECTOR - 1) // USER_SECTOR * USER_SECTOR
    if cursor > len(data) or len(data) - cursor > USER_SECTOR:
        raise ValueError("indexed archive layout does not account for the file")
    return members


def containing_member(
    members: dict[int, IndexedMember], file_offset: int, size: int
) -> tuple[IndexedMember, int]:
    for member in members.values():
        begin = member.file_offset
        if begin <= file_offset and file_offset + size <= begin + len(member.payload):
            return member, file_offset - begin
    raise ValueError(
        f"ROCK_X6.BIN range 0x{file_offset:X}+0x{size:X} has no member owner"
    )


def read_iso_file_range(
    image: RawMode2Image, name: str, file_offset: int, size: int
) -> bytes:
    entry = image.entries[name]
    if file_offset < 0 or file_offset + size > entry.size:
        raise ValueError(
            f"{name} range 0x{file_offset:X}+0x{size:X} is outside the file"
        )
    return image.read_user(entry.lba * USER_SECTOR + file_offset, size)


def resolve_source_writes(
    specs: tuple[FeatureSpec, ...],
    patcher_source: Path,
    patcher_data: Path,
) -> dict[str, list[tuple[int, bytes]]]:
    """Resolve each feature through the ported Tweaks engine, fail closed.

    The source closure must be exactly the selected option after removing the
    patcher's shared B01 base list. This is the guard against accidentally
    converting common hacks merely because they appear in a patched image.
    """
    if not specs:
        return {}
    try:
        import tweaks_engine as engine
    except ImportError as error:
        raise RuntimeError("cannot import tools/tweaks_engine.py") from error

    src_dir = patcher_source.parent.parent
    profile_path = patcher_data.parent / "profiles" / "default.x6tweaksprofile"
    require_file(profile_path, "Tweaks default profile")
    db = engine.twr.TweaksDB(src_dir)
    base = engine.twr.load_profile(profile_path)
    result: dict[str, list[tuple[int, bytes]]] = {}
    for spec in specs:
        merged = dict(base)
        merged[spec.source_option] = spec.source_value
        _normalized, patchfile, patch_list, values, synth = engine._assemble(
            db, merged, base
        )
        inherited = set(db.patchlist_base) | set(db.patchlist_script)
        owned = [name for name in patch_list if name not in inherited]
        if patchfile != "b01" or owned != [spec.source_option]:
            raise AssertionError(
                f"{spec.source_option} source closure changed: "
                f"patchfile={patchfile!r}, owned={owned!r}"
            )
        if synth:
            raise AssertionError(
                f"{spec.source_option} unexpectedly synthesizes "
                f"{sorted(synth)!r}"
            )
        _file_patch, file_entries = engine.build_filelist(db, merged, base)
        if file_entries:
            raise AssertionError(
                f"{spec.source_option} unexpectedly inserts files: "
                f"{file_entries!r}"
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
        expected = tuple(
            (offset, bytes.fromhex(payload))
            for offset, payload in spec.expected_writes
        )
        if tuple(writes) != expected:
            actual = [(f"0x{o:X}", data.hex().upper()) for o, data in writes]
            raise AssertionError(
                f"{spec.source_option} source writes changed: {actual!r}"
            )
        result[spec.feature_id] = writes
    return result


def build_simple_feature_ops(
    stock: RawMode2Image,
    b01_base: RawMode2Image,
    intro_oracles: tuple[RawMode2Image, ...],
    nightmare_oracles: tuple[RawMode2Image, ...],
    qol_oracles: tuple[RawMode2Image, ...],
    movement_oracles: tuple[RawMode2Image, ...],
    small_data_oracles: tuple[RawMode2Image, ...],
    static_spike_oracles: tuple[RawMode2Image, ...],
    specs: tuple[FeatureSpec, ...],
    patcher_source: Path,
    patcher_data: Path,
) -> tuple[list[Patch], list[Overlay], dict]:
    """Convert reviewed single-option features by semantic stock identity."""
    source_writes = resolve_source_writes(specs, patcher_source, patcher_data)
    stock_load = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    b01_bin = b01_base.read_file("ROCK_X6.BIN")
    stock_bin = stock.read_file("ROCK_X6.BIN")
    b01_members = indexed_archive_members(b01_bin)
    stock_members = indexed_archive_members(stock_bin)
    oracle_member_cache: dict[Path, dict[int, IndexedMember]] = {}
    patches: list[Patch] = []
    overlays: list[Overlay] = []
    evidence: dict[str, dict] = {}
    for spec in specs:
        operations = []
        if spec in INTRO_FEATURES:
            feature_oracles = intro_oracles
        elif spec in NIGHTMARE_FEATURES:
            feature_oracles = nightmare_oracles
        elif spec in QOL_FEATURES:
            feature_oracles = qol_oracles
        elif spec in MOVEMENT_FEATURES:
            feature_oracles = movement_oracles
        elif spec in SMALL_DATA_FEATURES:
            feature_oracles = small_data_oracles
        elif spec in STATIC_SPIKE_FEATURES:
            feature_oracles = static_spike_oracles
        else:
            raise AssertionError(f"no oracle group for {spec.feature_id}")
        for raw_offset, replacement in source_writes[spec.feature_id]:
            b01_user_offset = raw_to_user_offset(raw_offset)
            entry, b01_file_offset = b01_base.containing_file(
                b01_user_offset, len(replacement)
            )
            if entry.name == SLUS_NAME and spec.target in ("main_exe", "mixed"):
                expected = read_iso_file_range(
                    b01_base, entry.name, b01_file_offset, len(replacement)
                )
                stock_expected = read_iso_file_range(
                    stock, entry.name, b01_file_offset, len(replacement)
                )
                if stock_expected != expected:
                    raise AssertionError(
                        f"{spec.source_option} depends on a B01 SLUS rewrite"
                    )
                for oracle in feature_oracles:
                    if (
                        read_iso_file_range(
                            oracle, entry.name, b01_file_offset, len(replacement)
                        )
                        != replacement
                    ):
                        raise AssertionError(
                            f"{oracle.path.name} lacks {spec.source_option}"
                        )
                address = stock_load + b01_file_offset - USER_SECTOR
                patches.append(
                    Patch(
                        spec.feature_id,
                        spec.source_option,
                        address,
                        expected,
                        replacement,
                    )
                )
                operations.append(
                    {
                        "kind": "guarded-main-exe-patch",
                        "source_raw_offset": raw_offset,
                        "iso_file": entry.name,
                        "file_offset": b01_file_offset,
                        "guest_address": address,
                        "size": len(replacement),
                        "expected": expected.hex().upper(),
                        "replace": replacement.hex().upper(),
                    }
                )
                continue

            if (
                entry.name != "ROCK_X6.BIN"
                or spec.target not in ("rock_x6_bin", "mixed")
            ):
                raise AssertionError(
                    f"{spec.source_option} has unsupported target {entry.name}"
                )
            source_member, relative_offset = containing_member(
                b01_members, b01_file_offset, len(replacement)
            )
            stock_member = stock_members.get(source_member.member_id)
            if stock_member is None:
                raise AssertionError(
                    f"stock lacks ROCK_X6.BIN member {source_member.member_id}"
                )
            expected = source_member.payload[
                relative_offset : relative_offset + len(replacement)
            ]
            stock_expected = stock_member.payload[
                relative_offset : relative_offset + len(replacement)
            ]
            if stock_expected != expected:
                raise AssertionError(
                    f"{spec.source_option} depends on a B01 member rewrite"
                )
            for oracle in feature_oracles:
                members = oracle_member_cache.get(oracle.path)
                if members is None:
                    members = indexed_archive_members(
                        oracle.read_file("ROCK_X6.BIN")
                    )
                    oracle_member_cache[oracle.path] = members
                oracle_member = members.get(source_member.member_id)
                if (
                    oracle_member is None
                    or oracle_member.payload[
                        relative_offset : relative_offset + len(replacement)
                    ]
                    != replacement
                ):
                    raise AssertionError(
                        f"{oracle.path.name} lacks {spec.source_option} at "
                        f"member {source_member.member_id}+0x{relative_offset:X}"
                    )
            file_offset = stock_member.file_offset + relative_offset
            user_offset = (
                stock.entries["ROCK_X6.BIN"].lba * USER_SECTOR + file_offset
            )
            overlays.append(
                Overlay(
                    spec.feature_id,
                    spec.source_option,
                    user_offset,
                    expected,
                    replacement,
                    source=spec.source_option,
                    raw_offset=raw_offset,
                    iso_file="ROCK_X6.BIN",
                    file_offset=file_offset,
                )
            )
            operations.append(
                {
                    "kind": "guarded-indexed-member-overlay",
                    "source_raw_offset": raw_offset,
                    "iso_file": "ROCK_X6.BIN",
                    "member_id": source_member.member_id,
                    "member_relative_offset": relative_offset,
                    "file_offset": file_offset,
                    "disc_user_offset": user_offset,
                    "size": len(replacement),
                    "expected": expected.hex().upper(),
                    "replace": replacement.hex().upper(),
                    "stock_member_sha256": sha256(stock_member.payload),
                }
            )
        evidence[spec.feature_id] = {
            "status": "ready-pending-live-smoke"
            if (
                spec in INTRO_FEATURES
                or spec in QOL_FEATURES
                or spec in MOVEMENT_FEATURES
                or spec in SMALL_DATA_FEATURES
                or spec in STATIC_SPIKE_FEATURES
            )
            else "ready",
            "source_selection": {spec.source_option: spec.source_value},
            "common_base_writes_inherited": 0,
            "semantic_operations": operations,
            "oracle_count": (
                len(feature_oracles)
            ),
        }
    return patches, overlays, evidence


def resolve_config_source_writes(
    specs: tuple[ConfigFeatureSpec, ...],
    patcher_source: Path,
    patcher_data: Path,
) -> dict[tuple[str, str], list[tuple[int, bytes]]]:
    """Resolve every bounded configuration variant through Tweaks itself."""
    if not specs:
        return {}
    try:
        import tweaks_engine as engine
    except ImportError as error:
        raise RuntimeError("cannot import tools/tweaks_engine.py") from error

    src_dir = patcher_source.parent.parent
    profile_path = patcher_data.parent / "profiles" / "default.x6tweaksprofile"
    require_file(profile_path, "Tweaks default profile")
    db = engine.twr.TweaksDB(src_dir)
    base = engine.twr.load_profile(profile_path)
    result: dict[tuple[str, str], list[tuple[int, bytes]]] = {}
    for spec in specs:
        for variant in spec.variants:
            merged = dict(base)
            merged.update(variant.selection)
            _normalized, patchfile, patch_list, values, synth = engine._assemble(
                db, merged, base
            )
            inherited = set(db.patchlist_base) | set(db.patchlist_script)
            owned = tuple(
                name for name in patch_list if name not in inherited
            )
            if patchfile != "b01" or owned != variant.expected_owned:
                raise AssertionError(
                    f"{spec.feature_id}/{variant.value} closure changed: "
                    f"patchfile={patchfile!r}, owned={owned!r}"
                )
            if synth:
                raise AssertionError(
                    f"{spec.feature_id}/{variant.value} unexpectedly "
                    f"synthesizes {sorted(synth)!r}"
                )
            _file_patch, file_entries = engine.build_filelist(db, merged, base)
            if file_entries:
                raise AssertionError(
                    f"{spec.feature_id}/{variant.value} unexpectedly inserts "
                    f"files: {file_entries!r}"
                )
            writes: list[tuple[int, bytes]] = []
            for name in owned:
                for data_hex, raw_offset in engine.expand_entry(
                    db, name, patchfile, values, synth
                ):
                    for split_hex, split_offset in engine.ecc_split(
                        data_hex, raw_offset
                    ):
                        writes.append(
                            (split_offset, bytes.fromhex(split_hex))
                        )
            if len(writes) != len(variant.expected_writes):
                raise AssertionError(
                    f"{spec.feature_id}/{variant.value} write count changed: "
                    f"{len(writes)} != {len(variant.expected_writes)}"
                )
            for (raw_offset, payload), expected in zip(
                writes, variant.expected_writes
            ):
                if (
                    raw_offset != expected.raw_offset
                    or len(payload) != expected.size
                ):
                    raise AssertionError(
                        f"{spec.feature_id}/{variant.value} write identity "
                        f"changed at 0x{raw_offset:X}+0x{len(payload):X}"
                    )
                if (
                    expected.payload_hex
                    and payload != bytes.fromhex(expected.payload_hex)
                ):
                    raise AssertionError(
                        f"{spec.feature_id}/{variant.value} payload changed at "
                        f"0x{raw_offset:X}"
                    )
                if (
                    expected.payload_sha256
                    and sha256(payload) != expected.payload_sha256
                ):
                    raise AssertionError(
                        f"{spec.feature_id}/{variant.value} payload hash "
                        f"changed at 0x{raw_offset:X}"
                    )
            result[(spec.feature_id, variant.value)] = writes
    return result


def build_config_feature_ops(
    stock: RawMode2Image,
    b01_base: RawMode2Image,
    config_oracles: tuple[tuple[RawMode2Image, str], ...],
    specs: tuple[ConfigFeatureSpec, ...],
    patcher_source: Path,
    patcher_data: Path,
) -> tuple[list[Patch], list[Overlay], dict]:
    """Convert bounded choices and semantic stage edits without interpolation."""
    source_writes = resolve_config_source_writes(
        specs, patcher_source, patcher_data
    )
    stock_load = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    b01_bin = b01_base.read_file("ROCK_X6.BIN")
    stock_bin = stock.read_file("ROCK_X6.BIN")
    b01_members = indexed_archive_members(b01_bin)
    stock_members = indexed_archive_members(stock_bin)
    stock_dat_records = dat_records(stock.read_file("ROCK_X6.DAT"))
    stock_dat_start = stock.entries["ROCK_X6.DAT"].lba * USER_SECTOR
    oracle_member_cache: dict[Path, dict[int, IndexedMember]] = {}
    oracle_dat_cache: dict[Path, dict[int, DatRecord]] = {}
    patches: list[Patch] = []
    overlays: list[Overlay] = []
    evidence: dict[str, dict] = {}

    def variant_selected(
        spec: ConfigFeatureSpec, variant_index: int, mode: str
    ) -> bool:
        if len(spec.variants) == 1:
            return True
        return (
            variant_index == 0
            if mode == "first"
            else variant_index == len(spec.variants) - 1
        )

    for spec in specs:
        feature_operations = []
        for variant_index, variant in enumerate(spec.variants):
            when = (
                (spec.option_id, variant.value)
                if spec.option_id
                else None
            )
            variant_operations = []
            for raw_offset, replacement in source_writes[
                (spec.feature_id, variant.value)
            ]:
                route = STAGE_DAT_ROUTES.get(raw_offset)
                if route is not None:
                    if len(replacement) != route.size:
                        raise AssertionError(
                            f"{spec.feature_id} stage route size changed at "
                            f"0x{raw_offset:X}"
                        )
                    b01_user_offset = raw_to_user_offset(raw_offset)
                    b01_entry, b01_file_offset = b01_base.containing_file(
                        b01_user_offset, len(replacement)
                    )
                    if b01_entry.name != "ROCK_X6.DAT":
                        raise AssertionError(
                            f"{spec.feature_id} stage source left ROCK_X6.DAT"
                        )
                    b01_expected = read_iso_file_range(
                        b01_base,
                        b01_entry.name,
                        b01_file_offset,
                        len(replacement),
                    )
                    if sha256(b01_expected) != route.stock_sha256:
                        raise AssertionError(
                            f"{spec.feature_id} B01 stage identity changed at "
                            f"0x{raw_offset:X}"
                        )
                    record = stock_dat_records[route.record_id]
                    subassets = parse_subassets(record)
                    subasset = subassets[route.subasset_index]
                    if subasset.asset_type != route.asset_type:
                        raise AssertionError(
                            f"{spec.feature_id} stock DAT type changed for "
                            f"{route.record_id}:{route.subasset_index}"
                        )
                    end = route.relative_offset + len(replacement)
                    if end > len(subasset.payload):
                        raise AssertionError(
                            f"{spec.feature_id} stage range exceeds semantic "
                            f"subasset {route.record_id}:{route.subasset_index}"
                        )
                    expected = subasset.payload[
                        route.relative_offset : end
                    ]
                    if sha256(expected) != route.stock_sha256:
                        raise AssertionError(
                            f"{spec.feature_id} stock stage guard changed for "
                            f"{route.record_id}:{route.subasset_index}"
                        )
                    for oracle, mode in config_oracles:
                        if not variant_selected(spec, variant_index, mode):
                            continue
                        records = oracle_dat_cache.get(oracle.path)
                        if records is None:
                            records = dat_records(
                                oracle.read_file("ROCK_X6.DAT")
                            )
                            oracle_dat_cache[oracle.path] = records
                        oracle_subasset = parse_subassets(
                            records[route.record_id]
                        )[route.subasset_index]
                        if (
                            oracle_subasset.payload[
                                route.relative_offset : end
                            ]
                            != replacement
                        ):
                            raise AssertionError(
                                f"{oracle.path.name} lacks "
                                f"{spec.feature_id}/{variant.value}"
                            )
                    payload_offset = subasset_payload_offset(
                        record, route.subasset_index
                    )
                    user_offset = (
                        stock_dat_start
                        + record.sector * USER_SECTOR
                        + payload_offset
                        + route.relative_offset
                    )
                    overlays.append(
                        Overlay(
                            spec.feature_id,
                            (
                                f"{variant.value}-"
                                if variant.value
                                else ""
                            )
                            + f"record-{route.record_id:03d}-"
                            + f"subasset-{route.subasset_index:02d}-"
                            + f"{route.relative_offset:05X}",
                            user_offset,
                            expected,
                            replacement,
                            source=",".join(variant.expected_owned),
                            raw_offset=raw_offset,
                            iso_file="ROCK_X6.DAT",
                            file_offset=(
                                record.sector * USER_SECTOR
                                + payload_offset
                                + route.relative_offset
                            ),
                            when=when,
                        )
                    )
                    variant_operations.append(
                        {
                            "kind": "guarded-dat-subasset-overlay",
                            "source_raw_offset": raw_offset,
                            "record_id": route.record_id,
                            "subasset_index": route.subasset_index,
                            "subasset_type": route.asset_type,
                            "subasset_relative_offset": route.relative_offset,
                            "disc_user_offset": user_offset,
                            "size": len(replacement),
                            "expected_sha256": sha256(expected),
                            "replacement_sha256": sha256(replacement),
                        }
                    )
                    continue

                b01_user_offset = raw_to_user_offset(raw_offset)
                entry, b01_file_offset = b01_base.containing_file(
                    b01_user_offset, len(replacement)
                )
                if (
                    entry.name == SLUS_NAME
                    and spec.target in ("main_exe", "mixed")
                ):
                    expected = read_iso_file_range(
                        b01_base,
                        entry.name,
                        b01_file_offset,
                        len(replacement),
                    )
                    stock_expected = read_iso_file_range(
                        stock,
                        entry.name,
                        b01_file_offset,
                        len(replacement),
                    )
                    if stock_expected != expected:
                        raise AssertionError(
                            f"{spec.feature_id} depends on a B01 SLUS rewrite"
                        )
                    for oracle, mode in config_oracles:
                        if (
                            variant_selected(spec, variant_index, mode)
                            and read_iso_file_range(
                                oracle,
                                entry.name,
                                b01_file_offset,
                                len(replacement),
                            )
                            != replacement
                        ):
                            raise AssertionError(
                                f"{oracle.path.name} lacks "
                                f"{spec.feature_id}/{variant.value}"
                            )
                    address = stock_load + b01_file_offset - USER_SECTOR
                    patches.append(
                        Patch(
                            spec.feature_id,
                            ",".join(variant.expected_owned),
                            address,
                            expected,
                            replacement,
                            when=when,
                        )
                    )
                    variant_operations.append(
                        {
                            "kind": "guarded-main-exe-patch",
                            "source_raw_offset": raw_offset,
                            "file_offset": b01_file_offset,
                            "guest_address": address,
                            "size": len(replacement),
                            "expected": expected.hex().upper(),
                            "replace": replacement.hex().upper(),
                        }
                    )
                    continue

                if (
                    entry.name != "ROCK_X6.BIN"
                    or spec.target not in ("rock_x6_bin", "mixed")
                ):
                    raise AssertionError(
                        f"{spec.feature_id} has unsupported target "
                        f"{entry.name}"
                    )
                source_member, relative_offset = containing_member(
                    b01_members, b01_file_offset, len(replacement)
                )
                stock_member = stock_members.get(source_member.member_id)
                if stock_member is None:
                    raise AssertionError(
                        f"stock lacks ROCK_X6.BIN member "
                        f"{source_member.member_id}"
                    )
                expected = source_member.payload[
                    relative_offset : relative_offset + len(replacement)
                ]
                stock_expected = stock_member.payload[
                    relative_offset : relative_offset + len(replacement)
                ]
                if stock_expected != expected:
                    raise AssertionError(
                        f"{spec.feature_id} depends on a B01 member rewrite"
                    )
                for oracle, mode in config_oracles:
                    if not variant_selected(spec, variant_index, mode):
                        continue
                    members = oracle_member_cache.get(oracle.path)
                    if members is None:
                        members = indexed_archive_members(
                            oracle.read_file("ROCK_X6.BIN")
                        )
                        oracle_member_cache[oracle.path] = members
                    oracle_member = members.get(source_member.member_id)
                    if (
                        oracle_member is None
                        or oracle_member.payload[
                            relative_offset :
                            relative_offset + len(replacement)
                        ]
                        != replacement
                    ):
                        raise AssertionError(
                            f"{oracle.path.name} lacks "
                            f"{spec.feature_id}/{variant.value}"
                        )
                file_offset = stock_member.file_offset + relative_offset
                user_offset = (
                    stock.entries["ROCK_X6.BIN"].lba * USER_SECTOR
                    + file_offset
                )
                overlays.append(
                    Overlay(
                        spec.feature_id,
                        (
                            f"{variant.value}-"
                            if variant.value
                            else ""
                        )
                        + ",".join(variant.expected_owned),
                        user_offset,
                        expected,
                        replacement,
                        source=",".join(variant.expected_owned),
                        raw_offset=raw_offset,
                        iso_file="ROCK_X6.BIN",
                        file_offset=file_offset,
                        when=when,
                    )
                )
                variant_operations.append(
                    {
                        "kind": "guarded-indexed-member-overlay",
                        "source_raw_offset": raw_offset,
                        "member_id": source_member.member_id,
                        "member_relative_offset": relative_offset,
                        "disc_user_offset": user_offset,
                        "size": len(replacement),
                        "expected": expected.hex().upper(),
                        "replace": replacement.hex().upper(),
                    }
                )
            feature_operations.append(
                {
                    "value": variant.value or "enabled",
                    "label": variant.label or spec.name,
                    "source_selection": dict(variant.selection),
                    "semantic_operations": variant_operations,
                }
            )
        evidence[spec.feature_id] = {
            "status": "ready-pending-live-smoke",
            "bounded_choice": bool(spec.option_id),
            "variants": feature_operations,
            "common_base_writes_inherited": 0,
            "oracle_modes": [mode for _oracle, mode in config_oracles],
        }
    return patches, overlays, evidence


def resolve_exit_stage_writes(
    patcher_source: Path, patcher_data: Path
) -> dict[str, list[tuple[int, bytes]]]:
    """Resolve the three-state ExitButton radio group without exposing helpers."""
    try:
        import tweaks_engine as engine
    except ImportError as error:
        raise RuntimeError("cannot import tools/tweaks_engine.py") from error

    src_dir = patcher_source.parent.parent
    profile_path = patcher_data.parent / "profiles" / "default.x6tweaksprofile"
    require_file(profile_path, "Tweaks default profile")
    db = engine.twr.TweaksDB(src_dir)
    base = engine.twr.load_profile(profile_path)
    result: dict[str, list[tuple[int, bytes]]] = {}
    for value, variant in EXIT_STAGE_VARIANTS.items():
        merged = dict(base)
        for name in ("ExitButton01", "ExitButton02", "ExitButton03"):
            merged[name] = "1" if name == variant["source_option"] else "0"
        _normalized, patchfile, patch_list, values, synth = engine._assemble(
            db, merged, base
        )
        inherited = set(db.patchlist_base) | set(db.patchlist_script)
        owned = [name for name in patch_list if name not in inherited]
        expected_closure = ["ExitButton01", variant["source_option"]]
        if patchfile != "b01" or owned != expected_closure:
            raise AssertionError(
                f"Exit Stage {value} closure changed: "
                f"patchfile={patchfile!r}, owned={owned!r}"
            )
        if engine.expand_entry(
            db, "ExitButton01", patchfile, values, synth
        ):
            raise AssertionError("stock ExitButton01 helper gained a payload")
        writes: list[tuple[int, bytes]] = []
        for data_hex, raw_offset in engine.expand_entry(
            db, variant["source_option"], patchfile, values, synth
        ):
            for split_hex, split_offset in engine.ecc_split(
                data_hex, raw_offset
            ):
                writes.append((split_offset, bytes.fromhex(split_hex)))
        expected = [
            (offset, bytes.fromhex(payload))
            for offset, payload in variant["writes"]
        ]
        if writes != expected:
            raise AssertionError(
                f"Exit Stage {value} source writes changed: "
                f"{[(hex(o), b.hex()) for o, b in writes]!r}"
            )
        result[value] = writes
    return result


def build_exit_stage_ops(
    stock: RawMode2Image,
    b01_base: RawMode2Image,
    variant_oracles: dict[str, tuple[RawMode2Image, ...]],
    patcher_source: Path,
    patcher_data: Path,
) -> tuple[list[Patch], dict]:
    """Build one configurable feature from the ExitButton radio group."""
    writes = resolve_exit_stage_writes(patcher_source, patcher_data)
    main_by_offset = dict(writes["main_stages"])
    everywhere_by_offset = dict(writes["everywhere"])
    common_raw = 0x1D948BE8
    everywhere_raw = 0x1D948BCC
    if (
        main_by_offset != {common_raw: bytes(4)}
        or everywhere_by_offset
        != {everywhere_raw: bytes(4), common_raw: bytes(4)}
    ):
        raise AssertionError("Exit Stage reviewed choice relationship changed")

    stock_load = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    patches: list[Patch] = []
    operations = []
    for raw_offset, replacement, condition, label in (
        (common_raw, bytes(4), None, "main-stages-and-everywhere"),
        (
            everywhere_raw,
            bytes(4),
            ("availability", "everywhere"),
            "everywhere-extra",
        ),
    ):
        source_user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = b01_base.containing_file(
            source_user_offset, len(replacement)
        )
        if entry.name != SLUS_NAME:
            raise AssertionError(f"Exit Stage targets {entry.name}, expected SLUS")
        expected = read_iso_file_range(
            b01_base, SLUS_NAME, file_offset, len(replacement)
        )
        if (
            read_iso_file_range(stock, SLUS_NAME, file_offset, len(replacement))
            != expected
        ):
            raise AssertionError("Exit Stage depends on a B01 SLUS rewrite")

        for value, oracles in variant_oracles.items():
            wanted = (
                replacement
                if raw_offset == common_raw or value == "everywhere"
                else expected
            )
            for oracle in oracles:
                actual = read_iso_file_range(
                    oracle, SLUS_NAME, file_offset, len(replacement)
                )
                if actual != wanted:
                    state = "replacement" if wanted == replacement else "stock"
                    raise AssertionError(
                        f"{oracle.path.name} does not contain Exit Stage "
                        f"{value} {state} bytes at 0x{file_offset:X}"
                    )

        address = stock_load + file_offset - USER_SECTOR
        patches.append(
            Patch(
                EXIT_STAGE_FEATURE_ID,
                label,
                address,
                expected,
                replacement,
                condition,
            )
        )
        operations.append(
            {
                "kind": "guarded-main-exe-patch",
                "label": label,
                "source_raw_offset": raw_offset,
                "iso_file": SLUS_NAME,
                "file_offset": file_offset,
                "guest_address": address,
                "size": len(replacement),
                "expected": expected.hex().upper(),
                "replace": replacement.hex().upper(),
                "when": (
                    {condition[0]: condition[1]} if condition is not None else None
                ),
            }
        )
    return patches, {
        "status": "ready-pending-live-smoke",
        "source_selections": {
            value: {variant["source_option"]: 1}
            for value, variant in EXIT_STAGE_VARIANTS.items()
        },
        "payloadless_stock_helper": "ExitButton01",
        "common_base_writes_inherited": 0,
        "semantic_operations": operations,
        "oracle_count_per_choice": {
            value: len(oracles) for value, oracles in variant_oracles.items()
        },
        "deferred_interaction": (
            "LivesSwitch01 forces Everywhere in the source patcher and remains "
            "deferred until that relationship has an explicit product policy."
        ),
    }


def build_title_overlays(
    stock: RawMode2Image,
    title_oracle: RawMode2Image,
    combined_oracle: RawMode2Image | None,
    patcher_source: Path,
    patcher_data: Path,
) -> list[Overlay]:
    """Map every bundled title variant by semantic DAT identity.

    Tweaks' offsets describe its B01-derived image.  Record 107 is relocated in
    that image, so those offsets are conversion evidence only and must never be
    reused as stock-disc destinations.
    """
    try:
        import tweaks_engine as engine
    except ImportError as error:
        raise RuntimeError("cannot import tools/tweaks_engine.py") from error

    src_dir = patcher_source.parent.parent
    profile_path = patcher_data.parent / "profiles" / "default.x6tweaksprofile"
    require_file(profile_path, "Tweaks default profile")
    db = engine.twr.TweaksDB(src_dir)
    base = engine.twr.load_profile(profile_path)
    stock_dat_entry = stock.entries["ROCK_X6.DAT"]
    stock_records = dat_records(stock.read_file("ROCK_X6.DAT"))
    title_records = dat_records(title_oracle.read_file("ROCK_X6.DAT"))
    combined_records = (
        dat_records(combined_oracle.read_file("ROCK_X6.DAT"))
        if combined_oracle is not None
        else None
    )
    overlays: list[Overlay] = []
    title_group = (
        "TitleScreen01",
        "TitleScreen02",
        "TitleScreen03",
        "TitleScreen04",
        "TitleScreen05",
    )
    for value, variant_label, source_option in TITLE_SCREEN_VARIANTS:
        merged = dict(base)
        for name in title_group:
            merged[name] = "1" if name == source_option else "0"
        _normalized, patchfile, patch_list, _values, synth = engine._assemble(
            db, merged, base
        )
        inherited = set(db.patchlist_base) | set(db.patchlist_script)
        owned = [name for name in patch_list if name not in inherited]
        if (
            patchfile != "b01"
            or owned != ["TitleScreen01", source_option]
            or synth
        ):
            raise AssertionError(
                f"{source_option} title closure changed: "
                f"patchfile={patchfile!r}, owned={owned!r}, "
                f"synth={sorted(synth)!r}"
            )
        _file_patch, file_entries = engine.build_filelist(db, merged, base)
        expected_count = 2 if source_option == "TitleScreen05" else 4
        if len(file_entries) != expected_count:
            raise AssertionError(
                f"{source_option} title file count changed: "
                f"{len(file_entries)} != {expected_count}"
            )
        occupied: list[tuple[int, int, str]] = []
        for file_var, source, raw_offset in file_entries:
            route = TITLE_ASSET_ROUTES.get(raw_offset)
            if route is None:
                raise AssertionError(
                    f"{source_option} has unknown title route 0x{raw_offset:X}"
                )
            label, record_id, subasset_index, asset_type = route
            source_path = Path(source)
            require_file(source_path, f"title asset {file_var}")
            payload = source_path.read_bytes()
            try:
                stock_record = stock_records[record_id]
                stock_subasset = parse_subassets(stock_record)[subasset_index]
            except (KeyError, IndexError) as error:
                raise AssertionError(
                    f"{variant_label}/{label} semantic DAT identity "
                    f"{record_id}:{subasset_index} is missing"
                ) from error
            if stock_subasset.asset_type != asset_type:
                raise AssertionError(
                    f"{variant_label}/{label} stock type is "
                    f"0x{stock_subasset.asset_type:X}, expected "
                    f"0x{asset_type:X}"
                )
            if len(stock_subasset.payload) != len(payload):
                raise AssertionError(
                    f"{variant_label}/{label} stock size is "
                    f"0x{len(stock_subasset.payload):X}, payload is "
                    f"0x{len(payload):X}"
                )
            if source_option == "TitleScreen02":
                title_subasset = parse_subassets(
                    title_records[record_id]
                )[subasset_index]
                if (
                    title_subasset.asset_type != asset_type
                    or title_subasset.payload != payload
                ):
                    raise AssertionError(
                        f"title-only oracle lacks {variant_label}/{label}"
                    )
                if combined_records is not None:
                    combined_subasset = parse_subassets(
                        combined_records[record_id]
                    )[subasset_index]
                    if (
                        combined_subasset.asset_type != asset_type
                        or combined_subasset.payload != payload
                    ):
                        raise AssertionError(
                            f"combined oracle lacks {variant_label}/{label}"
                        )
            subasset_offset = subasset_payload_offset(
                stock_record, subasset_index
            )
            file_offset = stock_record.sector * USER_SECTOR + subasset_offset
            user_offset = stock_dat_entry.lba * USER_SECTOR + file_offset
            expected = stock_subasset.payload
            if not any(expected):
                raise AssertionError(
                    f"{variant_label}/{label} stock range is empty"
                )
            if expected == payload:
                raise AssertionError(
                    f"{variant_label}/{label} does not change stock"
                )
            begin, end = user_offset, user_offset + len(payload)
            for other_begin, other_end, other_label in occupied:
                if begin < other_end and other_begin < end:
                    raise AssertionError(
                        f"{variant_label}/{label} overlaps {other_label}"
                    )
            occupied.append((begin, end, label))
            overlays.append(
                Overlay(
                    feature="title_screen",
                    label=f"{value}-{label}",
                    source=str(source_path),
                    raw_offset=raw_offset,
                    user_offset=user_offset,
                    expected=expected,
                    replace=payload,
                    iso_file=stock_dat_entry.name,
                    file_offset=file_offset,
                    when=("variant", value),
                )
            )
    return overlays


def parse_owned_script_writes(source_path: Path) -> list[tuple[str, int, bytes]]:
    """Parse only active ScriptTextDisplay/ScriptMenuAlign AHK assignments."""
    require_file(source_path, "Tweaks _dat.ahk")
    text = source_path.read_text(encoding="utf-8-sig", errors="strict")
    # Remove block comments before matching.  The inactive IngameOptions block
    # intentionally reuses ScriptMenuAlign names.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    values: dict[str, str] = {}
    offsets: dict[str, int] = {}
    value_re = re.compile(
        r"^(Script(?:TextDisplay|MenuAlign)_ASM\d+)\s*=\s*([0-9A-F]+)\s*$",
        re.MULTILINE,
    )
    offset_re = re.compile(
        r"^(Script(?:TextDisplay|MenuAlign)_ASM\d+)_Offset\s*=\s*([0-9A-F]+)\s*$",
        re.MULTILINE,
    )
    for match in value_re.finditer(text):
        values[match.group(1)] = match.group(2)
    for match in offset_re.finditer(text):
        offsets[match.group(1)] = int(match.group(2), 16)
    names = sorted(values, key=lambda name: (name.split("_")[0], name))
    if len(names) != 15 or set(names) != set(offsets):
        raise AssertionError(
            "expected exactly 15 active ScriptTextDisplay/ScriptMenuAlign writes"
        )
    return [(name, offsets[name], bytes.fromhex(values[name])) for name in names]


@dataclass(frozen=True)
class DatRecord:
    record_id: int
    sector: int
    size: int
    payload: bytes


SCRIPT_SUBASSETS: dict[int, dict[int, tuple[int, int | None]]] = {
    **{
        record_id: {7: (0x10001, 0x8000), 9: (0x12, 0x2600)}
        for record_id in range(85, 90)
    },
    106: {0: (0x10001, 0x8000), 14: (0x15, 0x1600)},
    110: {0: (0x10001, 0x8000), 12: (0x15, 0x3000)},
    111: {0: (0x10001, 0x8000), 12: (0x15, 0x3000)},
    **{
        record_id: {
            0: (0x10001, 0x8000),
            (
                15
                if record_id in (149, 153, 157)
                else 12
                if record_id == 158
                else 11
                if record_id in (152, 161)
                else 14
            ): (0x15, 0x12000),
        }
        for record_id in range(149, 162)
    },
    **{
        record_id: {0: (0x15, None)}
        for record_id in range(203, 243)
    },
}

SCRIPT_IN_PLACE_IDS = frozenset(
    (
        *range(85, 90),
        *range(203, 207),
        *range(208, 213),
        *range(214, 221),
        *range(223, 227),
        *range(229, 235),
        *range(236, 239),
        240,
        242,
    )
)
SCRIPT_RELOCATED_IDS = frozenset(
    (
        106,
        110,
        111,
        *range(149, 162),
        207,
        213,
        221,
        222,
        227,
        228,
        235,
        239,
        241,
    )
)


@dataclass(frozen=True)
class Subasset:
    asset_type: int
    payload: bytes


def dat_records(data: bytes) -> dict[int, DatRecord]:
    records = {}
    for record_id in range(256):
        sector, size = struct.unpack_from("<II", data, record_id * 8)
        if sector == 0 and size == 0:
            continue
        begin = sector * USER_SECTOR
        end = begin + size
        if end > len(data):
            raise ValueError(
                f"DAT record {record_id} extends past its container: "
                f"0x{begin:X}+0x{size:X}"
            )
        records[record_id] = DatRecord(
            record_id, sector, size, data[begin:end]
        )
    return records


def parse_subassets(record: DatRecord) -> list[Subasset]:
    if len(record.payload) < USER_SECTOR:
        raise ValueError(f"DAT record {record.record_id} has no subasset header")
    count, outer_size = struct.unpack_from("<II", record.payload, 0)
    if outer_size != len(record.payload):
        raise ValueError(
            f"DAT record {record.record_id} outer size is "
            f"0x{outer_size:X}, expected 0x{len(record.payload):X}"
        )
    if 8 + count * 8 > USER_SECTOR:
        raise ValueError(f"DAT record {record.record_id} table is too large")
    cursor = USER_SECTOR
    result = []
    for index in range(count):
        asset_type, size = struct.unpack_from(
            "<II", record.payload, 8 + index * 8
        )
        end = cursor + size
        if end > len(record.payload):
            raise ValueError(
                f"DAT record {record.record_id} subasset {index} is truncated"
            )
        result.append(Subasset(asset_type, record.payload[cursor:end]))
        cursor = (end + USER_SECTOR - 1) // USER_SECTOR * USER_SECTOR
    if cursor != len(record.payload):
        raise ValueError(
            f"DAT record {record.record_id} subassets end at 0x{cursor:X}, "
            f"outer ends at 0x{len(record.payload):X}"
        )
    return result


def subasset_payload_offset(record: DatRecord, wanted_index: int) -> int:
    """Return a subasset's byte offset within its outer DAT record."""
    subassets = parse_subassets(record)
    if not 0 <= wanted_index < len(subassets):
        raise IndexError(wanted_index)
    cursor = USER_SECTOR
    for index, subasset in enumerate(subassets):
        if index == wanted_index:
            return cursor
        cursor += len(subasset.payload)
        cursor = (cursor + USER_SECTOR - 1) // USER_SECTOR * USER_SECTOR
    raise AssertionError("unreachable subasset lookup")


def build_outer_record(subassets: list[Subasset]) -> bytes:
    if 8 + len(subassets) * 8 > USER_SECTOR:
        raise ValueError("subasset table does not fit one sector")
    result = bytearray(USER_SECTOR)
    for index, subasset in enumerate(subassets):
        struct.pack_into(
            "<II",
            result,
            8 + index * 8,
            subasset.asset_type,
            len(subasset.payload),
        )
        result += subasset.payload
        result += bytes((-len(result)) % USER_SECTOR)
    struct.pack_into("<II", result, 0, len(subassets), len(result))
    return bytes(result)


def coalesce_patches(patches: list[Patch]) -> list[Patch]:
    """Merge adjacent/compatible source writes into canonical guarded ranges."""
    result: list[Patch] = []
    for item in sorted(patches, key=lambda patch: patch.address):
        if not result:
            result.append(item)
            continue
        previous = result[-1]
        previous_end = previous.address + len(previous.replace)
        if item.address > previous_end:
            result.append(item)
            continue
        begin = previous.address
        end = max(previous_end, item.address + len(item.replace))
        expected: list[int | None] = [None] * (end - begin)
        replace: list[int | None] = [None] * (end - begin)
        for patch in (previous, item):
            offset = patch.address - begin
            for index, value in enumerate(patch.expected):
                at = offset + index
                if expected[at] is not None and expected[at] != value:
                    raise AssertionError(
                        f"incompatible expected bytes at 0x{begin + at:08X}"
                    )
                expected[at] = value
            for index, value in enumerate(patch.replace):
                at = offset + index
                if replace[at] is not None and replace[at] != value:
                    raise AssertionError(
                        f"incompatible replacements at 0x{begin + at:08X}"
                    )
                replace[at] = value
        if any(value is None for value in expected + replace):
            raise AssertionError("patch coalescing created an unguarded gap")
        result[-1] = Patch(
            feature=previous.feature,
            label=f"{previous.label}+{item.label}",
            address=begin,
            expected=bytes(expected),
            replace=bytes(replace),
        )
    return result


def build_retranslation_ops(
    stock: RawMode2Image,
    s02_base: RawMode2Image,
    script_oracle: RawMode2Image,
    patcher_source: Path,
    title_overlays: list[Overlay],
) -> tuple[list[Patch], list[Overlay], dict]:
    """Build custom stock outers containing only owned s02 subassets."""
    stock_dat_entry = stock.entries["ROCK_X6.DAT"]
    stock_dat_start = stock_dat_entry.lba * USER_SECTOR
    stock_dat = stock.read_file("ROCK_X6.DAT")
    s02_dat = s02_base.read_file("ROCK_X6.DAT")
    if stock.read_file("ROCK_X6.BIN") != s02_base.read_file("ROCK_X6.BIN"):
        raise AssertionError("s02 base unexpectedly changes ROCK_X6.BIN")
    stock_records = dat_records(stock_dat)
    s02_records = dat_records(s02_dat)
    script_records = dat_records(script_oracle.read_file("ROCK_X6.DAT"))
    if len(SCRIPT_SUBASSETS) != 61:
        raise AssertionError("reviewed script outer-record count changed")
    if sum(len(items) for items in SCRIPT_SUBASSETS.values()) != 82:
        raise AssertionError("reviewed script subasset count changed")
    if (
        set(SCRIPT_SUBASSETS)
        != SCRIPT_IN_PLACE_IDS | SCRIPT_RELOCATED_IDS
        or SCRIPT_IN_PLACE_IDS & SCRIPT_RELOCATED_IDS
    ):
        raise AssertionError("reviewed script record modes are inconsistent")

    custom_records: dict[int, bytes] = {}
    owned_replacements: dict[int, dict[int, Subasset]] = {}
    subasset_evidence = []
    for record_id, owned in sorted(SCRIPT_SUBASSETS.items()):
        original = stock_records[record_id]
        source = s02_records[record_id]
        oracle = script_records[record_id]
        stock_subassets = parse_subassets(original)
        s02_subassets = parse_subassets(source)
        oracle_subassets = parse_subassets(oracle)
        # Prove the canonical builder preserves a stock outer exactly before
        # changing any feature-owned nested asset.
        if build_outer_record(stock_subassets) != original.payload:
            raise AssertionError(
                f"stock outer record {record_id} is not canonical"
            )
        custom_subassets = list(stock_subassets)
        owned_replacements[record_id] = {}
        for index, (expected_type, expected_size) in sorted(owned.items()):
            replacement = s02_subassets[index]
            if replacement.asset_type != expected_type:
                raise AssertionError(
                    f"record {record_id} subasset {index} type is "
                    f"0x{replacement.asset_type:X}, expected 0x{expected_type:X}"
                )
            if (
                expected_size is not None
                and len(replacement.payload) != expected_size
            ):
                raise AssertionError(
                    f"record {record_id} subasset {index} size is "
                    f"0x{len(replacement.payload):X}, "
                    f"expected 0x{expected_size:X}"
                )
            try:
                oracle_replacement = oracle_subassets[index]
            except IndexError as error:
                raise AssertionError(
                    f"script oracle lacks record {record_id} subasset {index}"
                ) from error
            if (
                oracle_replacement.asset_type != replacement.asset_type
                or oracle_replacement.payload != replacement.payload
            ):
                raise AssertionError(
                    f"script oracle does not contain owned record "
                    f"{record_id} subasset {index}"
                )
            custom_subassets[index] = replacement
            owned_replacements[record_id][index] = replacement
            subasset_evidence.append(
                {
                    "record_id": record_id,
                    "subasset_index": index,
                    "type": replacement.asset_type,
                    "size": len(replacement.payload),
                    "sha256": sha256(replacement.payload),
                }
            )
        custom_records[record_id] = build_outer_record(custom_subassets)

    protected = [
        (item.user_offset, item.user_offset + len(item.replace), item.label)
        for item in title_overlays
    ]
    overlays: list[Overlay] = []
    equal_size_ids = []
    relocated_ids = []
    record_evidence = []

    if stock_dat_entry.size % USER_SECTOR:
        raise AssertionError("stock ROCK_X6.DAT is not sector aligned")
    pack_sector = stock_dat_entry.size // USER_SECTOR
    pack_first_sector = pack_sector
    for record_id, target_payload in sorted(custom_records.items()):
        original = stock_records[record_id]
        if len(target_payload) == original.size:
            equal_size_ids.append(record_id)
            record_start = stock_dat_start + original.sector * USER_SECTOR
            stock_subassets = parse_subassets(original)
            target_record = DatRecord(
                record_id, original.sector, original.size, target_payload
            )
            for subasset_index, replacement in sorted(
                owned_replacements[record_id].items()
            ):
                stock_payload_offset = subasset_payload_offset(
                    original, subasset_index
                )
                target_payload_offset = subasset_payload_offset(
                    target_record, subasset_index
                )
                if stock_payload_offset != target_payload_offset:
                    raise AssertionError(
                        f"in-place record {record_id} subasset "
                        f"{subasset_index} shifts later assets"
                    )
                expected = stock_subassets[subasset_index].payload
                stock_allocation = (
                    len(expected) + USER_SECTOR - 1
                ) // USER_SECTOR * USER_SECTOR
                target_allocation = (
                    len(replacement.payload) + USER_SECTOR - 1
                ) // USER_SECTOR * USER_SECTOR
                if stock_allocation != target_allocation:
                    raise AssertionError(
                        f"in-place record {record_id} subasset "
                        f"{subasset_index} changes its allocation"
                    )
                expected_slot = original.payload[
                    stock_payload_offset : stock_payload_offset + stock_allocation
                ]
                replacement_slot = target_payload[
                    target_payload_offset : target_payload_offset + target_allocation
                ]
                overlays.append(
                    Overlay(
                        feature="retranslation",
                        label=(
                            f"record-{record_id:03d}-"
                            f"subasset-{subasset_index:02d}"
                        ),
                        user_offset=record_start + stock_payload_offset,
                        expected=expected_slot,
                        replace=replacement_slot,
                        iso_file="ROCK_X6.DAT",
                        file_offset=(
                            original.sector * USER_SECTOR + stock_payload_offset
                        ),
                    )
                )
                if len(expected) != len(replacement.payload):
                    size_offset = 8 + subasset_index * 8 + 4
                    overlays.append(
                        Overlay(
                            feature="retranslation",
                            label=(
                                f"record-{record_id:03d}-"
                                f"subasset-{subasset_index:02d}-size"
                            ),
                            user_offset=record_start + size_offset,
                            expected=struct.pack("<I", len(expected)),
                            replace=struct.pack("<I", len(replacement.payload)),
                            iso_file="ROCK_X6.DAT",
                            file_offset=(
                                original.sector * USER_SECTOR + size_offset
                            ),
                        )
                    )
            record_evidence.append(
                {
                    "id": record_id,
                    "mode": "owned-subassets-in-place",
                    "stock_sector": original.sector,
                    "owned_subasset_indices": sorted(
                        owned_replacements[record_id]
                    ),
                    "owned_bytes": sum(
                        len(item.payload)
                        for item in owned_replacements[record_id].values()
                    ),
                }
            )
            continue

        relocated_ids.append(record_id)
        packed_offset = stock_dat_start + pack_sector * USER_SECTOR
        expected_backing = stock.read_user(packed_offset, len(target_payload))
        overlays.append(
            Overlay(
                feature="retranslation",
                label=f"record-{record_id:03d}-relocated",
                user_offset=packed_offset,
                expected=expected_backing,
                replace=target_payload,
                iso_file="ZNULL.DAT",
                file_offset=packed_offset
                - stock.entries["ZNULL.DAT"].lba * USER_SECTOR,
            )
        )
        old_table = stock_dat[record_id * 8 : record_id * 8 + 8]
        new_table = struct.pack("<II", pack_sector, len(target_payload))
        overlays.append(
            Overlay(
                feature="retranslation",
                label=f"record-{record_id:03d}-table",
                user_offset=stock_dat_start + record_id * 8,
                expected=old_table,
                replace=new_table,
                iso_file="ROCK_X6.DAT",
                file_offset=record_id * 8,
            )
        )
        record_evidence.append(
            {
                "id": record_id,
                "mode": "relocated",
                "stock_sector": original.sector,
                "packed_sector": pack_sector,
                "size": len(target_payload),
                "sha256": sha256(target_payload),
            }
        )
        pack_sector += len(target_payload) // USER_SECTOR

    znull_sectors = (
        stock.entries["ZNULL.DAT"].size + USER_SECTOR - 1
    ) // USER_SECTOR
    packed_sectors = pack_sector - pack_first_sector
    if packed_sectors != 0x1ABE:
        raise AssertionError(
            f"reviewed relocated payload was 0x{packed_sectors:X} sectors, "
            "expected 0x1ABE"
        )
    if packed_sectors > znull_sectors:
        raise AssertionError("relocated script records do not fit stock ZNULL")
    if (
        set(equal_size_ids) != SCRIPT_IN_PLACE_IDS
        or set(relocated_ids) != SCRIPT_RELOCATED_IDS
    ):
        raise AssertionError(
            "reviewed nested record modes changed: got in-place "
            f"{equal_size_ids}, relocated {relocated_ids}"
        )
    # The guest ISO lookup must expose the virtual DAT extent through the final
    # relocated record. Keep the stock LBA and update both ISO9660 byte orders.
    logical_dat_size = pack_sector * USER_SECTOR
    if logical_dat_size != 0x03DED000:
        raise AssertionError(
            f"reviewed virtual DAT extent changed: 0x{logical_dat_size:08X}"
        )
    iso_size_offset = 0xB0A6
    iso_size_expected = stock.read_user(iso_size_offset, 8)
    if iso_size_expected != bytes.fromhex("00E008030308E000"):
        raise AssertionError(
            "stock ROCK_X6.DAT ISO size record does not match USA v1.1"
        )
    overlays.append(
        Overlay(
            feature="retranslation",
            label="rock-x6-dat-logical-size",
            user_offset=iso_size_offset,
            expected=iso_size_expected,
            replace=bytes.fromhex("00D0DE0303DED000"),
            iso_file="ISO9660 root directory",
            file_offset=iso_size_offset,
        )
    )

    load_address = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    source_patches = []
    for name, raw_offset, replacement in parse_owned_script_writes(
        patcher_source
    ):
        user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = stock.containing_file(user_offset, len(replacement))
        if entry.name != SLUS_NAME:
            raise AssertionError(f"{name} targets {entry.name}, expected {SLUS_NAME}")
        expected = stock.read_user(user_offset, len(replacement))
        if script_oracle.read_user(user_offset, len(replacement)) != replacement:
            raise AssertionError(f"script oracle does not contain {name}")
        source_patches.append(
            Patch(
                feature="retranslation",
                label=name,
                address=load_address + file_offset - 2048,
                expected=expected,
                replace=replacement,
            )
        )
    patches = coalesce_patches(source_patches)
    if len(source_patches) != 15 or len(patches) != 12:
        raise AssertionError(
            "reviewed script patch canonicalization changed: expected "
            f"15 source writes -> 12 ranges, got "
            f"{len(source_patches)} -> {len(patches)}"
        )

    # Prove every operation is disjoint from the title feature, except identical
    # bytes (none are expected in this slice).
    for overlay in overlays:
        begin, end = overlay.user_offset, overlay.user_offset + len(overlay.replace)
        for p_begin, p_end, label in protected:
            if begin < p_end and p_begin < end:
                raise AssertionError(
                    f"retranslation {overlay.label} claims title asset {label}"
                )
    evidence = {
        "status": "ready",
        "selection": {"ScriptPatch02": 1},
        "logical_record_ids": sorted(custom_records),
        "owned_subasset_count": len(subasset_evidence),
        "owned_subassets": subasset_evidence,
        "in_place_record_ids": equal_size_ids,
        "relocated_record_ids": relocated_ids,
        "relocated_start_sector": pack_first_sector,
        "relocated_sectors": packed_sectors,
        "stock_znull_sectors": znull_sectors,
        "composition_limit": (
            "The 25 growing records share one reviewed ZNULL allocation and "
            "logical DAT-size redirect. Features that grow or touch these "
            "records remain deferred until the resolver owns a container "
            "composer/allocator."
        ),
        "owned_source_main_exe_writes": len(source_patches),
        "canonical_main_exe_ranges": len(patches),
        "owned_main_exe_bytes": sum(len(item.replace) for item in patches),
        "records": record_evidence,
        "no_rock_x6_bin_changes": True,
        "title_ranges_unclaimed": True,
        "omitted_base_outer_record_ids": [107, 243, 244, 245, 246, 247],
    }
    return patches, overlays, evidence


def audit_retranslation(
    stock: RawMode2Image,
    script_oracle: RawMode2Image,
    patcher_source: Path,
) -> dict:
    """Prove the source-level executable edits without building assets."""
    load_address = struct.unpack("<I", stock.read_file(SLUS_NAME)[0x18:0x1C])[0]
    writes = []
    for name, raw_offset, replacement in parse_owned_script_writes(
        patcher_source
    ):
        user_offset = raw_to_user_offset(raw_offset)
        entry, file_offset = stock.containing_file(user_offset, len(replacement))
        if entry.name != SLUS_NAME:
            raise AssertionError(f"{name} targets {entry.name}, expected {SLUS_NAME}")
        expected = stock.read_user(user_offset, len(replacement))
        actual = script_oracle.read_user(user_offset, len(replacement))
        if actual != replacement:
            raise AssertionError(
                f"retranslation oracle does not contain owned write {name}"
            )
        address = load_address + file_offset - 2048
        writes.append(
            {
                "name": name,
                "raw_offset": raw_offset,
                "disc_user_offset": user_offset,
                "main_exe_address": address,
                "size": len(replacement),
                "expected": expected.hex().upper(),
                "replace": replacement.hex().upper(),
            }
        )
    return {
        "status": "main-exe-audit-only",
        "reason": (
            "This audit mode reports only ScriptTextDisplay/ScriptMenuAlign. "
            "Normal retranslation generation separately rebuilds 61 stock "
            "outer records from 82 owned s02 subassets."
        ),
        "owned_main_exe_writes": writes,
        "owned_main_exe_write_count": len(writes),
        "owned_main_exe_bytes": sum(item["size"] for item in writes),
        "asset_mapping_status": "implemented-by-nested-record-repacker",
    }


def validate_composition(
    stock: RawMode2Image, patches: list[Patch], overlays: list[Overlay]
) -> dict:
    """Validate stock guards and compatible partial overlaps before packaging."""
    def can_coexist(left, right) -> bool:
        return not (
            left.feature == right.feature
            and left.when is not None
            and right.when is not None
            and left.when[0] == right.when[0]
            and left.when[1] != right.when[1]
        )

    identical_overlap_bytes = 0
    ordered_overlays = sorted(overlays, key=lambda item: item.user_offset)
    for item in ordered_overlays:
        actual = stock.read_user(item.user_offset, len(item.expected))
        if actual != item.expected:
            raise AssertionError(f"stock guard failed for {item.label}")
    for index, left in enumerate(ordered_overlays):
        left_end = left.user_offset + len(left.replace)
        for right in ordered_overlays[index + 1 :]:
            if right.user_offset >= left_end:
                break
            if not can_coexist(left, right):
                continue
            right_end = right.user_offset + len(right.replace)
            begin = max(left.user_offset, right.user_offset)
            end = min(left_end, right_end)
            left_bytes = left.replace[
                begin - left.user_offset : end - left.user_offset
            ]
            right_bytes = right.replace[
                begin - right.user_offset : end - right.user_offset
            ]
            if left_bytes != right_bytes:
                raise AssertionError(
                    f"disc collision at 0x{begin:X}: "
                    f"{left.feature}/{left.label} vs "
                    f"{right.feature}/{right.label}"
                )
            identical_overlap_bytes += end - begin

    ordered_patches = sorted(patches, key=lambda item: item.address)
    stock_slus = stock.read_file(SLUS_NAME)
    load_address = struct.unpack("<I", stock_slus[0x18:0x1C])[0]
    for item in ordered_patches:
        file_offset = item.address - load_address + USER_SECTOR
        if (
            file_offset < 0
            or file_offset + len(item.expected) > len(stock_slus)
        ):
            raise AssertionError(
                f"main-EXE patch {item.label} is outside {SLUS_NAME}"
            )
        actual = stock_slus[file_offset : file_offset + len(item.expected)]
        if actual != item.expected:
            raise AssertionError(
                f"stock main-EXE guard failed for {item.feature}/{item.label}"
            )
    for index, left in enumerate(ordered_patches):
        left_end = left.address + len(left.replace)
        for right in ordered_patches[index + 1 :]:
            if right.address >= left_end:
                break
            if not can_coexist(left, right):
                continue
            right_end = right.address + len(right.replace)
            begin = max(left.address, right.address)
            end = min(left_end, right_end)
            left_bytes = left.replace[
                begin - left.address : end - left.address
            ]
            right_bytes = right.replace[
                begin - right.address : end - right.address
            ]
            if left_bytes != right_bytes:
                raise AssertionError(
                    f"main-EXE collision at 0x{begin:08X}: "
                    f"{left.label} vs {right.label}"
                )
            identical_overlap_bytes += end - begin

    fingerprint_input = [
        (
            "patch",
            item.feature,
            item.address,
            len(item.replace),
            sha256(item.expected),
            sha256(item.replace),
            item.when,
        )
        for item in ordered_patches
    ] + [
        (
            "overlay",
            item.feature,
            item.user_offset,
            len(item.replace),
            sha256(item.expected),
            sha256(item.replace),
            item.when,
        )
        for item in ordered_overlays
    ]
    fingerprint = sha256(
        json.dumps(fingerprint_input, separators=(",", ":")).encode()
    )
    return {
        "patch_operations": len(patches),
        "patch_bytes": sum(len(item.replace) for item in patches),
        "overlay_operations": len(overlays),
        "overlay_bytes": sum(len(item.replace) for item in overlays),
        "identical_overlap_bytes": identical_overlap_bytes,
        "incompatible_overlap_bytes": 0,
        "plan_fingerprint": fingerprint,
        "stock_guards_verified": True,
        "stock_main_exe_guards_verified": True,
    }


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_manifest(
    features: set[str],
    patches: list[Patch],
    overlays: list[Overlay],
    asset_paths: dict[int, str],
    package_version: str,
) -> str:
    lines = [
        "format_version = 1",
        'id = "mmx6.tweaks.native"',
        f"version = {q(package_version)}",
        'name = "Mega Man X6 Tweaks"',
        'author = "acediez, DuoDynamo, NectarHime; PSXRecomp integration"',
        'description = "Independent native MMX6 Tweaks features."',
        'license = "Generated locally; original credits retained"',
        'resolver = "declarative"',
        'save_compatibility = "shared"',
        "",
        "[[target]]",
        f"game_id = {q(GAME_ID)}",
        f"disc_sha256 = {q(STOCK_SHA256)}",
    ]
    if "title_screen" in features:
        lines += [
            "",
            "[[feature]]",
            'id = "title_screen"',
            'name = "Title Screen"',
            'description = "Replace the stock title-screen artwork."',
            'group = "Localization"',
            "default_enabled = false",
            "",
            "[[option]]",
            'feature = "title_screen"',
            'id = "variant"',
            'label = "Artwork"',
            'description = "Choose the replacement title-screen artwork."',
            'group = "Localization"',
            'type = "choice"',
            f"default = {q(TITLE_SCREEN_VARIANTS[0][0])}",
        ]
        for value, label, _source_option in TITLE_SCREEN_VARIANTS:
            lines += [
                "",
                "[[option.choice]]",
                f"value = {q(value)}",
                f"label = {q(label)}",
            ]
    if "retranslation" in features:
        lines += [
            "",
            "[[feature]]",
            'id = "retranslation"',
            'name = "Retranslation"',
            'description = "English retranslation, VFW font, and menu alignment."',
            'group = "Localization"',
            "default_enabled = false",
        ]
    for spec in SIMPLE_FEATURES:
        if spec.feature_id not in features:
            continue
        lines += [
            "",
            "[[feature]]",
            f"id = {q(spec.feature_id)}",
            f"name = {q(spec.name)}",
            f"description = {q(spec.description)}",
            f"group = {q(spec.group)}",
            "default_enabled = false",
        ]
    for spec in CONFIG_FEATURES:
        if spec.feature_id not in features:
            continue
        lines += [
            "",
            "[[feature]]",
            f"id = {q(spec.feature_id)}",
            f"name = {q(spec.name)}",
            f"description = {q(spec.description)}",
            f"group = {q(spec.group)}",
            "default_enabled = false",
        ]
        if spec.option_id:
            lines += [
                "",
                "[[option]]",
                f"feature = {q(spec.feature_id)}",
                f"id = {q(spec.option_id)}",
                f"label = {q(spec.option_label)}",
                f"description = {q(spec.description)}",
                f"group = {q(spec.group)}",
                'type = "choice"',
                f"default = {q(spec.variants[0].value)}",
            ]
            for variant in spec.variants:
                lines += [
                    "",
                    "[[option.choice]]",
                    f"value = {q(variant.value)}",
                    f"label = {q(variant.label)}",
                ]
    if EXIT_STAGE_FEATURE_ID in features:
        lines += [
            "",
            "[[feature]]",
            f"id = {q(EXIT_STAGE_FEATURE_ID)}",
            'name = "Exit Stage Availability"',
            (
                'description = "Choose where Exit Stage is available while '
                'the feature is enabled."'
            ),
            'group = "Stage Rules"',
            "default_enabled = false",
            "",
            "[[option]]",
            f"feature = {q(EXIT_STAGE_FEATURE_ID)}",
            'id = "availability"',
            'label = "Available in"',
            'description = "Stages where the Exit Stage command is available."',
            'group = "Stage Rules"',
            'type = "choice"',
            'default = "main_stages"',
            "",
            "[[option.choice]]",
            'value = "main_stages"',
            'label = "Main Stages"',
            "",
            "[[option.choice]]",
            'value = "everywhere"',
            'label = "Everywhere"',
        ]
    for patch in patches:
        lines += [
            "",
            "[[patch]]",
            f"feature = {q(patch.feature)}",
            'target = "main_exe"',
            f"address = {patch.address}",
            f"expected = {q(patch.expected.hex().upper())}",
            f"replace = {q(patch.replace.hex().upper())}",
            "order = 0",
        ]
        if patch.when is not None:
            lines.append(
                f"when = {{ {patch.when[0]} = {q(patch.when[1])} }}"
            )
    for index, overlay in enumerate(overlays):
        lines += [
            "",
            "[[overlay]]",
            f"feature = {q(overlay.feature)}",
            'target = "disc_user"',
            f"offset = {overlay.user_offset}",
            f"file = {q(asset_paths[index])}",
            f"sha256 = {q(sha256(overlay.replace))}",
            f"expected_sha256 = {q(sha256(overlay.expected))}",
            "order = 0",
        ]
        if overlay.when is not None:
            lines.append(
                f"when = {{ {overlay.when[0]} = {q(overlay.when[1])} }}"
            )
    return "\n".join(lines) + "\n"


def write_package(
    out: Path,
    features: set[str],
    patches: list[Patch],
    overlays: list[Overlay],
    report: dict,
    package_version: str,
) -> None:
    asset_paths = {
        index: f"assets/{overlay.feature}/{index:03d}-{overlay.label}.bin"
        for index, overlay in enumerate(overlays)
    }
    manifest = build_manifest(
        features, patches, overlays, asset_paths, package_version
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    def member(name: str, payload: bytes | str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(
            info, payload.encode("utf-8") if isinstance(payload, str) else payload
        )
        return info

    with zipfile.ZipFile(
        out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        member("manifest.toml", manifest)
        for index, overlay in enumerate(overlays):
            member(asset_paths[index], overlay.replace)
        member(
            "conversion-report.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        member(
            "README.txt",
            "Generated locally from a verified stock MMX6 image and a "
            "user-supplied MMX6 Tweaks extraction.\n"
            "This package contains native stock-disc record overlays and "
            "guarded executable patches. It contains no derived disc or "
            "VCDIFF runtime recipe.\n",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", type=Path, default=DEFAULT_STOCK)
    parser.add_argument(
        "--b01-base",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "base.bin",
        help="isolated B01 base oracle used only to resolve source identities",
    )
    parser.add_argument(
        "--title-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "rockman-jp-title.bin",
    )
    parser.add_argument(
        "--combined-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "rockman-jp-title-retranslation.bin",
    )
    parser.add_argument(
        "--script-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "retranslation.bin",
    )
    parser.add_argument(
        "--s02-base",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "s02-base.bin",
        help="local result of applying data/xdelta3/s02.xdelta3 to stock",
    )
    parser.add_argument(
        "--intro-oracle",
        type=Path,
        default=DEFAULT_MATRIX_DIR
        / "mega_man_usa__original__skip_intros.bin",
    )
    parser.add_argument(
        "--combined-intro-oracle",
        type=Path,
        default=DEFAULT_MATRIX_DIR
        / "rockman_japan__retranslation__skip_intros.bin",
    )
    parser.add_argument(
        "--nightmare-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "no-nightmare-effects.bin",
    )
    parser.add_argument(
        "--combined-nightmare-oracle",
        type=Path,
        default=DEFAULT_MATRIX_DIR
        / "rockman_japan__retranslation__no_nightmare_effects.bin",
    )
    parser.add_argument(
        "--qol-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "qol-core.bin",
    )
    parser.add_argument(
        "--combined-qol-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "qol-current-combined.bin",
    )
    parser.add_argument(
        "--movement-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "movement-core.bin",
    )
    parser.add_argument(
        "--combined-movement-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "movement-current-combined.bin",
    )
    parser.add_argument(
        "--small-data-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "small-data-core.bin",
    )
    parser.add_argument(
        "--combined-small-data-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "small-data-current-combined.bin",
    )
    parser.add_argument(
        "--static-spike-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "static-spike-core.bin",
    )
    parser.add_argument(
        "--combined-static-spike-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "static-spike-current-combined.bin",
    )
    parser.add_argument(
        "--easy-config-first-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "easy-config-first.bin",
    )
    parser.add_argument(
        "--easy-config-last-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "easy-config-last.bin",
    )
    parser.add_argument(
        "--combined-easy-config-first-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "easy-config-current-combined-first.bin",
    )
    parser.add_argument(
        "--combined-easy-config-last-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "easy-config-current-combined-last.bin",
    )
    parser.add_argument(
        "--exit-main-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "exit-main-stages.bin",
    )
    parser.add_argument(
        "--combined-exit-main-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "exit-current-combined-main-stages.bin",
    )
    parser.add_argument(
        "--exit-everywhere-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "exit-everywhere.bin",
    )
    parser.add_argument(
        "--combined-exit-everywhere-oracle",
        type=Path,
        default=DEFAULT_ORACLE_DIR / "exit-current-combined-everywhere.bin",
    )
    parser.add_argument("--patcher-data", type=Path, default=DEFAULT_PATCHER_DATA)
    parser.add_argument(
        "--patcher-source", type=Path, default=DEFAULT_PATCHER_SOURCE
    )
    parser.add_argument(
        "--feature",
        choices=("all", *ALL_FEATURE_IDS),
        default="all",
    )
    parser.add_argument("--package-version", default="1.7.0")
    parser.add_argument("--audit-retranslation", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    require_file(args.stock, "stock MMX6 BIN")
    stock_digest = file_sha256(args.stock)
    if stock_digest != STOCK_SHA256:
        raise ValueError(
            f"unsupported stock image: {stock_digest}; expected {STOCK_SHA256}"
        )
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.package_version):
        raise ValueError("--package-version must be numeric semantic version X.Y.Z")
    enabled_features = (
        set(ALL_FEATURE_IDS) if args.feature == "all" else {args.feature}
    )
    wants_title = "title_screen" in enabled_features
    wants_retranslation = "retranslation" in enabled_features
    wants_exit = EXIT_STAGE_FEATURE_ID in enabled_features
    simple_specs = tuple(
        spec for spec in SIMPLE_FEATURES if spec.feature_id in enabled_features
    )
    config_specs = tuple(
        spec for spec in CONFIG_FEATURES if spec.feature_id in enabled_features
    )
    wants_intro = any(spec in INTRO_FEATURES for spec in simple_specs)
    wants_nightmare = any(spec in NIGHTMARE_FEATURES for spec in simple_specs)
    wants_qol = any(spec in QOL_FEATURES for spec in simple_specs)
    wants_movement = any(spec in MOVEMENT_FEATURES for spec in simple_specs)
    wants_small_data = any(
        spec in SMALL_DATA_FEATURES for spec in simple_specs
    )
    wants_static_spike = any(
        spec in STATIC_SPIKE_FEATURES for spec in simple_specs
    )
    wants_config = bool(config_specs)
    if wants_title:
        require_file(args.title_oracle, "title-only conversion oracle")
    combined_path = (
        args.combined_oracle
        if wants_title and args.combined_oracle.is_file()
        else None
    )
    if wants_retranslation or args.audit_retranslation:
        require_file(args.script_oracle, "retranslation conversion oracle")
    if wants_retranslation:
        require_file(args.s02_base, "s02 base conversion oracle")
        require_file(args.patcher_source, "Tweaks _dat.ahk")
    if simple_specs or config_specs or wants_exit:
        require_file(args.b01_base, "B01 base conversion oracle")
        require_file(args.patcher_source, "Tweaks _dat.ahk")
        require_file(
            args.patcher_data.parent / "profiles" / "default.x6tweaksprofile",
            "Tweaks default profile",
        )
    if wants_intro:
        require_file(args.intro_oracle, "intro conversion oracle")
        require_file(
            args.combined_intro_oracle, "combined intro conversion oracle"
        )
    if wants_nightmare:
        require_file(args.nightmare_oracle, "Nightmare conversion oracle")
        require_file(
            args.combined_nightmare_oracle,
            "combined Nightmare conversion oracle",
        )
    if wants_qol:
        require_file(args.qol_oracle, "QoL conversion oracle")
        require_file(
            args.combined_qol_oracle, "combined QoL conversion oracle"
        )
    if wants_movement:
        require_file(args.movement_oracle, "movement conversion oracle")
        require_file(
            args.combined_movement_oracle,
            "combined movement conversion oracle",
        )
    if wants_small_data:
        require_file(args.small_data_oracle, "small-data conversion oracle")
        require_file(
            args.combined_small_data_oracle,
            "combined small-data conversion oracle",
        )
    if wants_static_spike:
        require_file(args.static_spike_oracle, "static-spike conversion oracle")
        require_file(
            args.combined_static_spike_oracle,
            "combined static-spike conversion oracle",
        )
    if wants_config:
        for path, description in (
            (args.easy_config_first_oracle, "easy-config first oracle"),
            (args.easy_config_last_oracle, "easy-config last oracle"),
            (
                args.combined_easy_config_first_oracle,
                "combined easy-config first oracle",
            ),
            (
                args.combined_easy_config_last_oracle,
                "combined easy-config last oracle",
            ),
        ):
            require_file(path, description)
    if wants_exit:
        for path, description in (
            (args.exit_main_oracle, "Exit Stage Main Stages oracle"),
            (
                args.combined_exit_main_oracle,
                "combined Exit Stage Main Stages oracle",
            ),
            (args.exit_everywhere_oracle, "Exit Stage Everywhere oracle"),
            (
                args.combined_exit_everywhere_oracle,
                "combined Exit Stage Everywhere oracle",
            ),
        ):
            require_file(path, description)

    with ExitStack() as stack:
        stock = stack.enter_context(RawMode2Image(args.stock))
        title = (
            stack.enter_context(RawMode2Image(args.title_oracle))
            if wants_title
            else None
        )
        combined = (
            stack.enter_context(RawMode2Image(combined_path))
            if combined_path
            else None
        )
        script = (
            stack.enter_context(RawMode2Image(args.script_oracle))
            if wants_retranslation or args.audit_retranslation
            else None
        )
        s02_base = (
            stack.enter_context(RawMode2Image(args.s02_base))
            if wants_retranslation
            else None
        )
        b01_base = (
            stack.enter_context(RawMode2Image(args.b01_base))
            if simple_specs or config_specs or wants_exit
            else None
        )
        intro_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (args.intro_oracle, args.combined_intro_oracle)
                if wants_intro
                else ()
            )
        )
        nightmare_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (args.nightmare_oracle, args.combined_nightmare_oracle)
                if wants_nightmare
                else ()
            )
        )
        qol_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (args.qol_oracle, args.combined_qol_oracle)
                if wants_qol
                else ()
            )
        )
        movement_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (args.movement_oracle, args.combined_movement_oracle)
                if wants_movement
                else ()
            )
        )
        small_data_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (args.small_data_oracle, args.combined_small_data_oracle)
                if wants_small_data
                else ()
            )
        )
        static_spike_oracles = tuple(
            stack.enter_context(RawMode2Image(path))
            for path in (
                (
                    args.static_spike_oracle,
                    args.combined_static_spike_oracle,
                )
                if wants_static_spike
                else ()
            )
        )
        config_oracles = tuple(
            (
                stack.enter_context(RawMode2Image(path)),
                mode,
            )
            for path, mode in (
                (
                    args.easy_config_first_oracle,
                    "first",
                ),
                (
                    args.combined_easy_config_first_oracle,
                    "first",
                ),
                (
                    args.easy_config_last_oracle,
                    "last",
                ),
                (
                    args.combined_easy_config_last_oracle,
                    "last",
                ),
            )
        ) if wants_config else ()
        exit_variant_oracles = {
            "main_stages": tuple(
                stack.enter_context(RawMode2Image(path))
                for path in (
                    args.exit_main_oracle,
                    args.combined_exit_main_oracle,
                )
            ),
            "everywhere": tuple(
                stack.enter_context(RawMode2Image(path))
                for path in (
                    args.exit_everywhere_oracle,
                    args.combined_exit_everywhere_oracle,
                )
            ),
        } if wants_exit else {}

        title_overlays = (
            build_title_overlays(
                stock,
                title,
                combined,
                args.patcher_source,
                args.patcher_data,
            )
            if wants_title
            else []
        )
        patches: list[Patch] = []
        overlays = list(title_overlays)
        report = {
            "status": "reviewed-native-feature-slice",
            "package_version": args.package_version,
            "stock_sha256": stock_digest,
            "converter_sha256": file_sha256(Path(__file__)),
            "enabled_features": [
                feature
                for feature in ALL_FEATURE_IDS
                if feature in enabled_features
            ],
            "provenance": {
                "title_oracle_sha256": (
                    file_sha256(args.title_oracle) if wants_title else None
                ),
                "combined_title_script_oracle_sha256": (
                    file_sha256(combined_path) if combined_path else None
                ),
                "patcher_source_sha256": (
                    file_sha256(args.patcher_source)
                    if args.patcher_source.is_file()
                    else None
                ),
            },
            "features": {},
            "forbidden_runtime_payloads": {
                "derived_disc": False,
                "vcdiff": False,
                "patched_oracle": False,
            },
        }
        if wants_title:
            report["features"]["title_screen"] = {
                "status": "ready",
                "variants": {
                    value: {"source_selection": {source_option: 1}}
                    for value, _label, source_option in TITLE_SCREEN_VARIANTS
                },
                "operations": [
                    {
                        "label": item.label,
                        "source": item.source,
                        "iso_file": item.iso_file,
                        "file_offset": item.file_offset,
                        "disc_user_offset": item.user_offset,
                        "dat_record_id": TITLE_ASSET_ROUTES[
                            item.raw_offset
                        ][1],
                        "subasset_index": TITLE_ASSET_ROUTES[
                            item.raw_offset
                        ][2],
                        "subasset_type": TITLE_ASSET_ROUTES[
                            item.raw_offset
                        ][3],
                        "when": (
                            {item.when[0]: item.when[1]}
                            if item.when is not None
                            else None
                        ),
                        "raw_oracle_offset": item.raw_offset,
                        "size": len(item.replace),
                        "stock_sha256": sha256(item.expected),
                        "replacement_sha256": sha256(item.replace),
                        "title_only_read_path_verified": (
                            item.when == ("variant", "rockman_japan")
                        ),
                        "combined_read_path_verified": (
                            combined is not None
                            and item.when == ("variant", "rockman_japan")
                        ),
                    }
                    for item in title_overlays
                ],
            }
        if wants_retranslation:
            script_patches, script_overlays, evidence = build_retranslation_ops(
                stock,
                s02_base,
                script,
                args.patcher_source,
                title_overlays,
            )
            patches += script_patches
            overlays += script_overlays
            report["features"]["retranslation"] = evidence
            report["provenance"]["s02_base_oracle_sha256"] = file_sha256(
                args.s02_base
            )
            report["provenance"]["script_oracle_sha256"] = file_sha256(
                args.script_oracle
            )
        elif script is not None:
            report["features"]["retranslation"] = audit_retranslation(
                stock, script, args.patcher_source
            )
        if simple_specs:
            simple_patches, simple_overlays, simple_evidence = (
                build_simple_feature_ops(
                    stock,
                    b01_base,
                    intro_oracles,
                    nightmare_oracles,
                    qol_oracles,
                    movement_oracles,
                    small_data_oracles,
                    static_spike_oracles,
                    simple_specs,
                    args.patcher_source,
                    args.patcher_data,
                )
            )
            patches += simple_patches
            overlays += simple_overlays
            report["features"].update(simple_evidence)
            report["provenance"]["b01_base_oracle_sha256"] = file_sha256(
                args.b01_base
            )
            if wants_intro:
                report["provenance"]["intro_oracle_sha256"] = file_sha256(
                    args.intro_oracle
                )
                report["provenance"][
                    "combined_intro_oracle_sha256"
                ] = file_sha256(args.combined_intro_oracle)
            if wants_nightmare:
                report["provenance"]["nightmare_oracle_sha256"] = file_sha256(
                    args.nightmare_oracle
                )
                report["provenance"][
                    "combined_nightmare_oracle_sha256"
                ] = file_sha256(args.combined_nightmare_oracle)
            if wants_qol:
                report["provenance"]["qol_oracle_sha256"] = file_sha256(
                    args.qol_oracle
                )
                report["provenance"][
                    "combined_qol_oracle_sha256"
                ] = file_sha256(args.combined_qol_oracle)
            if wants_movement:
                report["provenance"][
                    "movement_oracle_sha256"
                ] = file_sha256(args.movement_oracle)
                report["provenance"][
                    "combined_movement_oracle_sha256"
                ] = file_sha256(args.combined_movement_oracle)
            if wants_small_data:
                report["provenance"][
                    "small_data_oracle_sha256"
                ] = file_sha256(args.small_data_oracle)
                report["provenance"][
                    "combined_small_data_oracle_sha256"
                ] = file_sha256(args.combined_small_data_oracle)
            if wants_static_spike:
                report["provenance"][
                    "static_spike_oracle_sha256"
                ] = file_sha256(args.static_spike_oracle)
                report["provenance"][
                    "combined_static_spike_oracle_sha256"
                ] = file_sha256(args.combined_static_spike_oracle)
        if config_specs:
            config_patches, config_overlays, config_evidence = (
                build_config_feature_ops(
                    stock,
                    b01_base,
                    config_oracles,
                    config_specs,
                    args.patcher_source,
                    args.patcher_data,
                )
            )
            patches += config_patches
            overlays += config_overlays
            report["features"].update(config_evidence)
            report["provenance"].update(
                {
                    "easy_config_first_oracle_sha256": file_sha256(
                        args.easy_config_first_oracle
                    ),
                    "easy_config_last_oracle_sha256": file_sha256(
                        args.easy_config_last_oracle
                    ),
                    "combined_easy_config_first_oracle_sha256": file_sha256(
                        args.combined_easy_config_first_oracle
                    ),
                    "combined_easy_config_last_oracle_sha256": file_sha256(
                        args.combined_easy_config_last_oracle
                    ),
                }
            )
        if wants_exit:
            exit_patches, exit_evidence = build_exit_stage_ops(
                stock,
                b01_base,
                exit_variant_oracles,
                args.patcher_source,
                args.patcher_data,
            )
            patches += exit_patches
            report["features"][EXIT_STAGE_FEATURE_ID] = exit_evidence
            report["provenance"].update(
                {
                    "exit_main_oracle_sha256": file_sha256(
                        args.exit_main_oracle
                    ),
                    "combined_exit_main_oracle_sha256": file_sha256(
                        args.combined_exit_main_oracle
                    ),
                    "exit_everywhere_oracle_sha256": file_sha256(
                        args.exit_everywhere_oracle
                    ),
                    "combined_exit_everywhere_oracle_sha256": file_sha256(
                        args.combined_exit_everywhere_oracle
                    ),
                }
            )
        report["composition"] = validate_composition(stock, patches, overlays)

    print(json.dumps(report, indent=2, sort_keys=True))
    if not args.verify_only:
        out = args.out or (
            ROOT
            / "build-mod-platform"
            / "test-psxmods"
            / "MMX6-Tweaks-Native.psxmod"
        )
        write_package(
            out,
            enabled_features,
            patches,
            overlays,
            report,
            args.package_version,
        )
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
