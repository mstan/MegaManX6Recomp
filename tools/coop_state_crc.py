"""Compare modern runtime core/mod breadcrumbs at resolved simulation ticks.

Diagnostic publication counts and the standalone co-op FNV are deliberately
absent. Callers must separately establish that the candidate registers its
complete authoritative host digest; a logged zero mod value cannot prove that.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


class StateCrcError(RuntimeError):
    pass


class MissingStateCrc(StateCrcError):
    pass


@dataclass(frozen=True)
class StateCrc:
    core: str
    mod: str


_PREFIX = re.compile(r"\brb live dig local sim=(\d+) (.*)")
_WORD = re.compile(r"([a-z]+)=([0-9a-fA-F]{8})(?:\s|$)")


def parse_state_crc(text: str) -> dict[int, StateCrc]:
    result = {}
    for line in text.splitlines(keepends=True):
        if not line.endswith(("\n", "\r")):
            continue  # A live writer may not have committed its final line yet.
        match = _PREFIX.search(line)
        if match is None:
            continue
        fields = dict(_WORD.findall(match[2]))
        if "core" not in fields or "mod" not in fields:
            continue  # Legacy logs do not qualify the modern host partition.
        tick = int(match[1])
        if tick > 0xFFFFFFFF:
            raise StateCrcError("Simulation tick exceeds the runtime's 32-bit contract")
        value = StateCrc(fields["core"].lower(), fields["mod"].lower())
        if tick in result and result[tick] != value:
            raise StateCrcError(f"Conflicting local core/mod CRCs at simulation tick {tick}")
        result[tick] = value
    return result


def resolved_state_crc(host: dict[int, StateCrc], guest: dict[int, StateCrc],
                       watermark: int, *, after: int = -1, minimum: int = 2) -> list[dict]:
    if type(watermark) is not int or not 0 <= watermark <= 0xFFFFFFFF:
        raise ValueError("Expected a bounded resolved-through watermark")
    if type(after) is not int or not -1 <= after <= 0xFFFFFFFF or minimum < 1:
        raise ValueError("Expected a bounded simulation range and positive sample count")
    # Strictly below both peers' resolved-through watermark. Never accept a
    # speculative/unresolved tip merely because its current CRC happens to match.
    ticks = sorted(tick for tick in host.keys() & guest.keys() if after < tick < watermark)
    for tick in ticks:
        if host[tick] != guest[tick]:
            raise StateCrcError(f"Core/mod CRC mismatch at resolved simulation tick {tick}")
    if len(ticks) < minimum:
        raise MissingStateCrc(f"Need {minimum} common resolved core/mod samples; found {len(ticks)}")
    return [dict(simulation_tick=tick, core=host[tick].core, mod=host[tick].mod) for tick in ticks]
