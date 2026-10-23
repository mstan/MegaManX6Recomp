"""Read-only native private-pool observations and bounded Zero/P2 reducers.

No launcher, guest writes, input injection, simulation counters or ledger
results. The owning runner validates its executable and original-input path.
Native visibility is separate from a completed composed capture/artwork review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import ntpath
from pathlib import Path
import struct
from typing import Sequence

import coop_debug as debug

HEADER, TRAILS, ATTACHED, END = 0x1A00, 0x1A10, 0x1B30, 0x1C20
MAGIC, SCHEMA, EXTENSION_BYTES = 0x58463658, 1, 0x220
PLAYER, NATIVE_TRAILS, NATIVE_ATTACHED = 0x800970A0, 0x800972F8, 0x800911A8
TRAIL_CLUTS = (0x780D, 0x780E, 0x780F)


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _forward(old: int, new: int, minimum: int = 1) -> bool:
    return minimum <= ((new - old) & 0xFFFFFFFF) < 0x80000000


def _between(old: int, value: int, end: int) -> bool:
    return ((value-old) & 0xFFFFFFFF) <= ((end-old) & 0xFFFFFFFF) < 0x80000000


def _resource_pointer(value: int) -> bool:
    # Original RAM, its uncached alias or the SDK's owned expanded guest RAM.
    return not value & 1 and (0x80000000 <= value < 0x80200000 or
                             0xA0000000 <= value < 0xA0200000 or
                             0x9F000000 <= value < 0xA0000000)


@dataclass(frozen=True)
class NativeEffect:
    pool: str
    slot: int
    address: int
    allocation: int
    subtype: int
    visible: int
    active: int
    phase: int
    subphase: int
    x_raw: int
    y_raw: int
    old_x_raw: int
    old_y_raw: int
    layer: int
    facing: int
    priority: int
    animation_table: int
    animation_cursor: int
    compression: int
    assembly: int
    page: int
    clut: int
    animation_command: tuple[int, ...]
    frame: int
    frame_pointer: int
    parent: int  # Attached ownership is implicit resident PLAYER, not +50.
    delay: int | None
    drain: int | None
    tail: int | None
    raw_hex: str  # Preserve every native field, including unknown/stale bytes.

    @classmethod
    def parse(cls, raw: bytes, pool: str, slot: int) -> "NativeEffect":
        trail = pool == "trails"
        if pool not in ("trails", "attached") or slot not in range(3) or len(raw) != (0x60 if trail else 0x50):
            raise debug.DebugError("Invalid native private-pool record boundary")
        address = (NATIVE_TRAILS + slot * 0x60 if trail else NATIVE_ATTACHED + slot * 0x50)
        parent = _u32(raw, 0x50) if trail else PLAYER
        if raw[3] > 1 or raw[3] and not raw[0]:
            raise debug.DebugError("Invalid native visibility/allocation")
        if raw[0]:
            if trail:
                expected_parent = NATIVE_TRAILS + (slot - 1) * 0x60 if slot else PLAYER
                if raw[0] != 0x11 or raw[2] != slot or parent != expected_parent:
                    raise debug.DebugError("Native trail type/index/parent chain changed")
                if raw[4] > 1 or raw[5] > 2 or raw[3] != raw[4]:
                    raise debug.DebugError("Invalid native trail visibility/phase")
                if raw[4] and (_u16(raw, 0x54) > 3 or _u16(raw, 0x56) > 8 or
                               _u16(raw, 0x58) > (5 - slot) * 2):
                    raise debug.DebugError("Native trail counters exceed source bounds")
            elif raw[2] != (0, 1, 3)[slot]:
                raise debug.DebugError("Native attached subtype/slot changed")
        elif any(raw):
            # Unknown inactive bytes are retained, but visible/active records
            # cannot borrow an unallocated actor. Zeroed third Falcon is valid.
            if raw[3] or raw[4]:
                raise debug.DebugError("Unallocated private effect is active")
        if raw[3]:
            if not _resource_pointer(_u32(raw, 0x3C)) or (trail and not _resource_pointer(_u32(raw, 0x38))):
                raise debug.DebugError("Visible native effect has invalid resource pointers")
            if raw[0x16] != (4 if trail else 2) or _u16(raw, 0x42) != (TRAIL_CLUTS[slot] if trail else 0x7802):
                raise debug.DebugError("Visible native effect priority/CLUT changed")
        return cls(pool, slot, address, raw[0], raw[2], raw[3], raw[4], raw[5], raw[6],
            *struct.unpack_from("<ii", raw, 8), *struct.unpack_from("<ii", raw, 0x18),
            raw[0x14], raw[0x15], raw[0x16], _u32(raw, 0x30), _u32(raw, 0x34),
            _u32(raw, 0x38), _u32(raw, 0x3C), _u16(raw, 0x40), _u16(raw, 0x42),
            tuple(raw[0x44:0x48]), raw[0x47], _u32(raw, 0x48), parent,
            _u16(raw, 0x54) if trail else None, _u16(raw, 0x56) if trail else None,
            _u16(raw, 0x58) if trail else None, raw.hex())


@dataclass(frozen=True)
class EffectsObservation:
    observation: debug.Observation
    available: bool
    unavailable_reason: str | None
    p2_body_hex: str
    marker: int
    native_held: int
    native_previous: int
    native_edges: int
    compression: int
    assembly: int
    page: int
    clut: int
    frame: int
    facing: int
    trails: tuple[NativeEffect, ...]
    attached: tuple[NativeEffect, ...]

    def json(self) -> dict:
        return asdict(self)


def parse_effect_diagnostic(data: bytes) -> EffectsObservation:
    """Parse one whole publication; never combine pools from a second RPC.

    An entirely zero extension is explicitly unavailable (e.g. frozen37).
    Partially written/unknown extensions are errors, not an absent capability.
    """
    if len(data) != END:
        raise debug.DebugError(f"Expected exactly {END} effect diagnostic bytes")
    base = debug.parse_diagnostic(data[:debug.DIAGNOSTIC_BYTES])
    magic, schema, size, tick = struct.unpack_from("<IIII", data, HEADER)
    absent = not any(data[HEADER:END])
    if not absent:
        if (magic, schema, size) != (MAGIC, SCHEMA, EXTENSION_BYTES):
            raise debug.DebugError("Unsupported/partial private-effects extension")
        if tick != base.tick:
            raise debug.UnstableObservation("Private-effects tick differs from base publication")
    body = data[0x100:0x258]
    return EffectsObservation(base, not absent, "extension_unavailable" if absent else None,
        body.hex(), struct.unpack_from("<b", body, 0x8C)[0],
        _u16(body, 0x7C), _u16(body, 0x7E), _u16(body, 0x80),
        _u32(body, 0x38), _u32(body, 0x3C), _u16(body, 0x40), _u16(body, 0x42),
        body[0x47], body[0x15],
        tuple(NativeEffect.parse(data[TRAILS+i*0x60:TRAILS+(i+1)*0x60], "trails", i)
              for i in range(3)) if not absent else (),
        tuple(NativeEffect.parse(data[ATTACHED+i*0x50:ATTACHED+(i+1)*0x50], "attached", i)
              for i in range(3)) if not absent else ())


def observe_effects(client: debug.DebugClient, address: int = debug.DIAGNOSTIC_ADDRESS) -> EffectsObservation:
    """Exactly one read_ram; an odd/stale publication must be resampled later."""
    return parse_effect_diagnostic(client.read(address, END))


def _eligible(row: EffectsObservation, phase: int = 0) -> bool:
    base = row.observation
    player = base.players[1]
    return (row.available and base.ready == base.enrolled == 1 and base.failed == 0 and
        not base.mailbox and not base.scene_owner and base.native_mode == 10 and
        base.native_phase == phase and tuple(base.lifecycle) == (0, 0) and
        player.active != 0 and player.character == 1 and player.state == 1 and
        0 < player.hp < 0x80 and base.players[0].character == 0)


def _resources(row: EffectsObservation) -> tuple:
    return (row.compression, row.assembly, row.page, row.clut,
            tuple((a.compression, a.assembly, a.page, a.clut, a.parent) for a in row.trails),
            tuple((a.compression, a.assembly, a.page, a.clut, a.parent) for a in row.attached))


def _owner_frames(rows: Sequence[EffectsObservation]) -> bool:
    return all(all((a.compression, a.assembly, a.frame, a.facing) ==
                   (r.compression, r.assembly, r.frame, r.facing)
                   for a in r.trails if a.allocation) for r in rows)


def reduce_zero_dash(before: EffectsObservation, active: Sequence[EffectsObservation],
                     released: Sequence[EffectsObservation], *, mode: str, input_path: str,
                     input_receipts: Sequence[dict], max_retirement_ticks: int = 32) -> dict:
    """Source-bound ordinary ground/jump dash, release, phase drain and hide.

    Runner receipts describe accepted ORIGINAL input, never marker/RAM writes.
    The publication/native-timer window is bounded; it is not a count of native
    helper invocations and does not prove once-world cadence or rendered art.
    """
    if mode not in ("local", "netplay") or not 2 <= max_retirement_ticks <= 120:
        raise ValueError("Expected local/netplay and bounded retirement window")
    expected_path = "published_host" if mode == "netplay" else "offline_native"
    if input_path != expected_path:
        raise ValueError("Dash qualification requires the original input path")
    checks = dict(extension_available=False, eligible_fixed_roster=False,
        original_input_receipts=False, ordered_publications=False,
        accepted_native_dash_marker=False, three_visible_native_trails=False,
        owner_frame_resources=False, native_links_and_cluts_retained=False,
        release_drains_without_retrigger=False, finite_native_retirement=False)
    rows = [before, *active, *released]
    result = dict(kind="zero_p2_native_private_dash", status="partial_evidence", checks=checks,
        limits=["Runner must verify actual executable, input provenance and bypasses",
                "Native visibility does not establish composed artwork or retained bank colors",
                "Publication/native timer progress is not once-world cadence or helper invocation count",
                "No X/P2 charge, opposite roster, R9 or ledger pass is produced"])
    checks["extension_available"] = all(r.available for r in rows)
    if not checks["extension_available"] or not active or not released:
        return result
    checks["eligible_fixed_roster"] = all(_eligible(r) for r in rows)
    checks["original_input_receipts"] = (len(input_receipts) >= 2 and
        all(isinstance(r, dict) and r.get("path") == input_path and r.get("seat") == 1 and
            type(r.get("pressed")) is int and 0 <= r["pressed"] <= 0xFFFF and
            r.get("accepted") is True and r.get("bypasses") == [] and
            all(type(r.get(k)) is int and 0 <= r[k] <= 0xFFFFFFFF for k in ("before_tick", "after_tick")) and
            _forward(r["before_tick"], r["after_tick"]) and
            _between(before.observation.tick, r["before_tick"], released[-1].observation.tick) and
            _between(before.observation.tick, r["after_tick"], released[-1].observation.tick)
            for r in input_receipts) and
        any(r["pressed"] != 0 for r in input_receipts[:-1]) and input_receipts[-1]["pressed"] == 0)
    if checks["original_input_receipts"]:
        checks["original_input_receipts"] = (all(_between(a["after_tick"], b["before_tick"],
            released[-1].observation.tick) for a, b in zip(input_receipts, input_receipts[1:])) and
            _between(before.observation.tick, input_receipts[0]["before_tick"], active[-1].observation.tick) and
            _between(active[0].observation.tick, input_receipts[-1]["before_tick"], released[-1].observation.tick))
    checks["ordered_publications"] = all(_forward(a.observation.tick, b.observation.tick) and
        _forward(a.observation.native_timer, b.observation.native_timer) for a, b in zip(rows, rows[1:]))
    checks["accepted_native_dash_marker"] = (before.marker == 0 and
        not any(t.visible or t.active for t in before.trails) and
        any(r.marker > 0 and r.observation.players[1].action in (0x0C, 6) for r in active))
    checks["three_visible_native_trails"] = any(r.marker > 0 and r.observation.players[1].action in (0x0C, 6) and
        all(t.allocation == 0x11 and t.visible == t.active == 1 and t.phase == 0 for t in r.trails)
        for r in active)
    checks["owner_frame_resources"] = _owner_frames(rows)
    checks["native_links_and_cluts_retained"] = (all(_resources(r) == _resources(before) for r in rows) and
        all(t.clut == TRAIL_CLUTS[t.slot] for r in rows for t in r.trails))
    draining = [r for r in released if r.marker < 0]
    checks["release_drains_without_retrigger"] = (bool(draining) and
        all(r.marker <= 0 for r in released) and
        any(any(t.active and t.phase == 1 for t in r.trails) for r in draining) and
        any(any(t.active and t.phase == 2 for t in r.trails) for r in draining))
    last = released[-1]
    delta = (last.observation.native_timer - released[0].observation.native_timer) & 0xFFFFFFFF
    checks["finite_native_retirement"] = (checks["release_drains_without_retrigger"] and
        0 < delta <= max_retirement_ticks and last.marker == 0 and
        all(t.visible == t.active == 0 for t in last.trails))
    return result


def reduce_effect_menu_freeze(samples: Sequence[EffectsObservation], *,
                              resumed: EffectsObservation | None = None,
                              minimum_progress: int = 6, owner: int = 1) -> dict:
    """Personal-menu pool freeze/resume; pair with the existing UI reducer.

    Require a visible pre-existing trail so an empty pool/frozen engine cannot
    stand in for effect retention. Menu input/cursor/network checks remain in
    mmx6_coop_personal_menu.reduce_frozen_window.
    """
    if not 1 <= minimum_progress <= 600 or owner not in (0, 1):
        raise ValueError("Expected bounded positive progress and owner0/1")
    checks = dict(visible_trail_window=False, native_personal_menu_owned=False,
        publications_advanced=False, native_timer_frozen=False,
        complete_private_pools_frozen=False, native_resources_and_cluts_retained=False,
        gameplay_resume_advances_private_effects=False)
    if len(samples) < 3 or not all(r.available for r in samples):
        return checks
    first, last = samples[0], samples[-1]
    checks["visible_trail_window"] = first.marker > 0 and any(t.visible for t in first.trails)
    checks["native_personal_menu_owned"] = all(_eligible(r, 2) and r.observation.pause_owner == owner+1 for r in samples)
    checks["publications_advanced"] = (_forward(first.observation.tick, last.observation.tick, minimum_progress) and
        all(_forward(a.observation.tick, b.observation.tick) for a, b in zip(samples, samples[1:])))
    checks["native_timer_frozen"] = all(r.observation.native_timer == first.observation.native_timer for r in samples)
    pools = lambda r: (r.marker, tuple(a.raw_hex for a in r.trails), tuple(a.raw_hex for a in r.attached))
    checks["complete_private_pools_frozen"] = all(pools(r) == pools(first) for r in samples)
    checks["native_resources_and_cluts_retained"] = (_owner_frames(samples) and
        all(_resources(r) == _resources(first) for r in samples))
    checks["gameplay_resume_advances_private_effects"] = (resumed is not None and _eligible(resumed) and
        _forward(last.observation.tick, resumed.observation.tick) and
        _forward(last.observation.native_timer, resumed.observation.native_timer) and
        pools(resumed) != pools(first) and _resources(resumed) == _resources(first) and _owner_frames([resumed]))
    return checks


def reduce_effect_render_review(row: EffectsObservation, capture: dict, review: dict) -> dict:
    """Keep capture completion/hash and explicit artwork review independent.

    The owning runner captures a stable visible window. RPC capture and pool
    sampling are separate operations, so this cannot prove same-frame packets.
    A reviewer must compare the named composed image with a native reference.
    """
    checks = dict(native_visible_window=False, composed_capture_artifact=False,
                  explicit_native_artwork_review=False)
    checks["native_visible_window"] = _eligible(row) and row.marker > 0 and all(t.visible for t in row.trails)
    try:
        path = Path(capture["path"])
        if (ntpath.splitdrive(str(path))[0].lower() == "c:" or not path.is_absolute() or
                not path.is_file() or not path.stat().st_size or
                capture.get("surface") != "composed_renderer_output" or
                capture["completion"].get("wrote") != 1 or
                type(capture["before"].get("seq")) is not int or
                type(capture["completion"].get("seq")) is not int or
                capture["completion"]["seq"] == capture["before"]["seq"]):
            return checks
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checks["composed_capture_artifact"] = capture.get("sha256") == digest
        checks["explicit_native_artwork_review"] = (checks["composed_capture_artifact"] and
            review.get("capture_sha256") == digest and review.get("status") == "matched_native_reference" and
            review.get("owner") == "Zero/P2" and review.get("visible_trail_slots") == [0, 1, 2] and
            review.get("cluts") == list(TRAIL_CLUTS) and
            isinstance(review.get("reference"), str) and bool(review["reference"].strip()) and
            review.get("retained_colors") == "matched" and review.get("limits") == [])
    except (KeyError, TypeError, ValueError, OSError):
        pass
    return checks
