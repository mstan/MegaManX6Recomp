"""Pure-Python port of acediez's MMX6 Tweaks patch engine (in progress).

Goal: reproduce the engine's WriteList — the list of (hex data, byte offset)
writes applied over the base xdelta3 patch — WITHOUT AutoHotkey, validated
byte-for-byte against the AHK engine's `dump` oracle (tweaks_resolver.py dump).

Pipeline being ported (see _src/_patch/{createlist,exception_a,exception_b,
filter,patchapply}.ahk):
  CreateList   -> PatchList = option vars whose value != _Default
  Exception_A  -> pick PATCHFILE (b01/s02/s03); prepend PatchList_Base (+Script)
  filters      -> numeric/text value conversion (edit/slider) [not yet ported]
  Exception_B  -> value/combination-dependent transforms         [incremental]
  PreReq/Reorder -> dependency closure + write order
  ASMFilter    -> expand each base-var into its _ASMnn (hex, offset) entries
  PatchApply   -> write %entry% at HEX2DEC(%entry%_Offset)

This module currently covers the COMMON case: options/base-hacks whose writes
are STATIC _ASMnn payloads (checkboxes, static radios) — no value-dependent
exceptions and no numeric-filter conversion yet. Those are added incrementally,
each guarded by an oracle diff.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import OrderedDict
from pathlib import Path

# Load the resolver as a module (it owns TweaksDB + the AHK dump oracle).
_spec = importlib.util.spec_from_file_location(
    "tweaks_resolver", Path(__file__).with_name("tweaks_resolver.py"))
twr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(twr)


def hex2dec(h: str) -> int:
    return int(str(h).strip(), 16)


# Raw CD-XA disc image geometry (Mode 2 / 2352-byte sectors).
_HEADER = 24        # BIN header before the first sector's user data
_SECTOR = 2352      # full sector
_DATA = 2048        # user data per sector
_ECC = 304          # EDC/ECC trailer per sector (skipped by writes)


def ecc_split(data_hex: str, offset: int) -> list[tuple[str, int]]:
    """Port of ECCSplitFilter (filter.ahk): a hex write that crosses a 2048-byte
    data-sector boundary is split so the 304-byte EDC/ECC trailer between data
    regions is skipped. Faithful byte-walk of the AHK loop: split whenever
    (offset - 24) mod 2352 == 2048; the continuation resumes 304 bytes later."""
    remaining = data_hex
    nbytes = len(data_hex) // 2
    voff_temp = offset
    voff_n = 0
    loop_n = nbytes
    seg_offset = offset
    segments: list[tuple[str, int]] = []
    while True:
        voff_n += 1
        voff_temp += 1
        if (voff_temp - _HEADER) % _SECTOR == _DATA:
            data_prev = remaining[: voff_n * 2]
            remaining = remaining[voff_n * 2:]
            if remaining == "":
                break                       # write ends at the boundary — no split
            segments.append((data_prev, seg_offset))
            seg_offset = voff_temp + _ECC
            voff_n = -_ECC
            loop_n += _ECC
        else:
            loop_n -= 1
        if loop_n <= 0:
            break
    if not segments:
        return [(data_hex, offset)]         # no boundary crossed
    segments.append((remaining, seg_offset))
    return segments


def _offsets_for_slot(asm_entries: list, slot: int, patchfile: str) -> list[str]:
    """Ordered offset-hex list for one ASM slot, choosing the offset SET by the
    selected PATCHFILE: b01 prefers a B01-specific offset (else COMMON), s02/s03
    prefer S02 (else COMMON). Multiple offsets per slot (_Offset, _Offset2, ...)
    each emit a write of the same data (nth ordering preserved)."""
    prefer = {"b01": "B01", "s02": "S02", "s03": "S02"}.get(patchfile, "COMMON")
    by_nth: dict[int, dict[str, str]] = {}
    for a in asm_entries:
        if a.get("kind") == "offset" and a["slot"] == slot:
            by_nth.setdefault(a["nth"], {})[a["set"]] = a["offset"]
    out = []
    for nth in sorted(by_nth):
        sets = by_nth[nth]
        chosen = sets.get(prefer) or sets.get("COMMON") or next(iter(sets.values()))
        # An offset value may itself be a newline-separated list — the same data
        # is written at each offset (acediez stores repeated writes this way).
        for off in str(chosen).splitlines():
            if off.strip():
                out.append(off.strip())
    return out


def expand_entry(db, var: str, patchfile: str) -> list[tuple[str, int]]:
    """Expand one base-var into its (hex data, decimal offset) writes from its
    static _ASMnn payloads. Returns [] for vars with no static ASM (those need a
    filter/exception — handled elsewhere)."""
    o = db.options.get(var)
    if not o:
        return []
    byte_slots = {a["slot"]: a["hex"] for a in o["asm"] if a.get("kind") == "bytes"}
    writes: list[tuple[str, int]] = []
    for slot in sorted(byte_slots):
        data = byte_slots[slot].replace(" ", "")
        for off_hex in _offsets_for_slot(o["asm"], slot, patchfile):
            writes.append((data, hex2dec(off_hex)))
    return writes


def active_options(db, merged: dict, base: dict) -> list[str]:
    """CreateList: option vars the selection actually changed. Reference is the
    shipped default profile (the true "no changes" state), NOT the _dat _Default
    — the profile stores semantically-equal values with formatting the _dat
    default lacks (quotes on DDL strings, `+0`, empty==0), which a raw _Default
    compare would misread as changes. The AHK engine normalizes these to equal;
    comparing against the base profile sidesteps the normalization entirely."""
    active = []
    for var, o in db.options.items():
        if o["default"] is None:
            continue                       # base/injected var, not a GUI option
        if not o["asm"] and not o["direct"]:
            continue
        if str(merged.get(var, "")).strip() != str(base.get(var, "")).strip():
            active.append(var)
    return active


def build_writelist(db, merged: dict, base: dict) -> tuple[str, list[tuple[str, int]]]:
    """Assemble (PATCHFILE, [(hexdata, offset_dec), ...]) for a merged profile.
    COMMON case only — see module docstring."""
    active = active_options(db, merged, base)
    # PATCHFILE: b01 unless a script/localization option is active (s02/s03).
    # TODO(port): detect ScriptPatch02/03 triggers; for now assume b01.
    patchfile = "b01"
    entries = list(db.patchlist_base) + active
    # TODO(port): + db.patchlist_script when s02/s03; PreReq deps; Reorder order.
    writes: list[tuple[str, int]] = []
    for var in entries:
        for data, off in expand_entry(db, var, patchfile):
            writes += ecc_split(data, off)      # split any write crossing an ECC boundary
    return patchfile, writes


# --------------------------------------------------------------------------
# Validation harness: build the WriteList in Python and diff (as a set, since
# the patched BIN is order-independent for non-overlapping offsets) against the
# AHK `dump` oracle for the same selection.
# --------------------------------------------------------------------------
def merged_profile(db, selection_json: str) -> "OrderedDict":
    """Build the same merged profile the oracle receives: shipped default
    profile + the UI selection's var overrides."""
    sel = json.loads(selection_json)
    merged = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    catalog = twr.parse_gui_catalog(twr.DEFAULT_PATCHER_SRC, db)
    for k, v in twr.selection_to_overrides(catalog, sel).items():
        merged[str(k)] = str(v)
    return merged


def _oracle_writes(selection_json: str, scratch: Path) -> tuple[str, set]:
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    scratch.mkdir(parents=True, exist_ok=True)
    gen = scratch / "_pc.x6tweaksprofile"
    gen.write_text(twr.emit_profile(merged_profile(db, selection_json)), encoding="utf-8")
    ahk = twr.find_autohotkey("")
    plan = twr.dump_engine(str(gen), twr.DEFAULT_VANILLA, scratch, twr.DEFAULT_PATCHER_SRC,
                           twr.DEFAULT_RUN_EXTRACTED, ahk)
    patchfile, writes = "", set()
    section = None
    for line in plan.splitlines():
        if line.startswith("PATCHFILE="):
            patchfile = line.split("=", 1)[1].strip()
        elif line.strip() == "[WRITELIST]":
            section = "w"
        elif line.strip() == "[FILES]":
            section = "f"
        elif section == "w" and "," in line:
            data, off = line.rsplit(",", 1)
            writes.add((data.strip(), int(off.strip())))
    return patchfile, writes


def check(selection_json: str, scratch: Path) -> bool:
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    merged = merged_profile(db, selection_json)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    pf_py, writes_py = build_writelist(db, merged, base)
    writes_py = set(writes_py)
    pf_or, writes_or = _oracle_writes(selection_json, scratch)

    ok = (pf_py == pf_or) and (writes_py == writes_or)
    print(f"selection: {selection_json}")
    print(f"  PATCHFILE  python={pf_py!r}  oracle={pf_or!r}  {'OK' if pf_py==pf_or else 'MISMATCH'}")
    print(f"  writes     python={len(writes_py)}  oracle={len(writes_or)}")
    missing = writes_or - writes_py     # oracle has, python missed
    extra = writes_py - writes_or       # python produced, oracle didn't
    if missing:
        print(f"  MISSING ({len(missing)}) — oracle has, port didn't produce:")
        for d, o in sorted(missing, key=lambda x: x[1])[:12]:
            print(f"    {o}  {d[:48]}{'...' if len(d)>48 else ''}")
    if extra:
        print(f"  EXTRA ({len(extra)}) — port produced, oracle didn't:")
        for d, o in sorted(extra, key=lambda x: x[1])[:12]:
            print(f"    {o}  {d[:48]}{'...' if len(d)>48 else ''}")
    print(f"  => {'BYTE-IDENTICAL' if ok else 'DIVERGENT'}")
    return ok


if __name__ == "__main__":
    scratch = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("./_portcheck")
    sel = sys.argv[1] if len(sys.argv) > 1 else '{"LivesSwitch03": true}'
    sys.exit(0 if check(sel, scratch) else 1)
