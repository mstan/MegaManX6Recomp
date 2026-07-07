"""Pure-Python port of acediez's MMX6 Tweaks patch engine (in progress).

Goal: reproduce the engine's WriteList — the list of (hex data, byte offset)
writes applied over the base xdelta3 patch — WITHOUT AutoHotkey, validated
byte-for-byte against the AHK engine's `dump` oracle (tweaks_resolver.py dump).

Pipeline being ported (see _src/_gui/{profile,guicontrol}.ahk and
_src/_patch/{createlist,exception_a,exception_b,filter,patchapply}.ahk):
  ProfileLoad  -> GuiControlAll: normalize conditional/dependent control values
  CreateList   -> PatchList = option instances whose value != default (TotalList order)
  Exception_A  -> pick PATCHFILE (b01/s02/s03); prepend PatchList_Base (+Script)
  filters      -> numeric/text value conversion (edit/slider) [not yet ported]
  Exception_B  -> value/combination-dependent transforms         [incremental]
  PreReq/Reorder -> dependency closure + write order
  ASMFilter    -> expand each base-var into its _ASMnn (hex, offset) entries
  PatchApply   -> write %entry% at HEX2DEC(%entry%_Offset)

Coverage so far (each increment guarded by a byte-for-byte, order-aware oracle diff):
  1. STATIC _ASMnn payloads (checkboxes, static radios), base prepend, ECC split.
  2. GuiControlAll VALUE-FORCING normalization (ArmorByPart/LivesSwitch/... control
     interlocks) + the empty-PatchList "No changes" guard; CreateList in TotalList
     order; PreReqFilter + ReorderFilter; ordered (overlap-safe) WriteList.
Still TODO: value-dependent Exception_A/_B (Lives cap, LowerDef, Mugshot assembly,
MachDash, Zero hints, BossHealth), numeric/text filters, ScriptPatch s02/s03,
external file inserts.
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


# --------------------------------------------------------------------------
# AHK truthiness + GUI-control normalization (ProfileLoad -> GuiControlAll).
# --------------------------------------------------------------------------
# ProfileLoad (profile.ahk) ends with `GoSub GuiControlAll`, which forces the
# values of conditional/dependent controls before the patch pipeline reads them
# via `Gui, Submit`. This is why e.g. `ArmorByPart04=1` with `ArmorByPart01=0`
# resolves to no changes: ArmorByPartControl zeroes 02/03/04 when 01 is off.
# We replicate the VALUE-FORCING half of GuiControlAll (Enable/Disable/Show/Hide
# don't change what Submit reads; FocusV-gated and ProfileLoad_Loop-gated ops
# don't fire during a headless profile load, so they're intentionally omitted).

_FALSY = {"", "0", "0.0", "00"}


def _truthy(v) -> bool:
    """AHK `If Var` truthiness: empty / "0" are false, everything else true."""
    return str(v).strip() not in _FALSY


def _dat_default(db, var: str) -> str:
    return str(db.dat.get(var + "_Default", ""))


def gui_control_all(db, m: dict) -> dict:
    """Return a normalized copy of a merged profile, applying the value-forcing
    subs of GuiControlAll in their AHK order. `m` maps VarName -> string value."""
    m = dict(m)

    def val(v):
        return m.get(v, _dat_default(db, v))

    def on(v):
        return _truthy(val(v))

    def force(v, value):
        m[v] = str(value)

    # ZeroGuardShellInputControl (called standalone at the end, and from the
    # ZeroEnsuizan* subs). FocusV is empty headless, so the focus-gated resets
    # are skipped; only the "nothing selected -> default" + Ensuizan interlock.
    def zero_guard_shell():
        if not (on("ZeroGuardShellInput01") or on("ZeroGuardShellInput02")
                or on("ZeroGuardShellInput04") or on("ZeroGuardShellInput05")):
            force("ZeroGuardShellInput01", 1)   # FocusV != "...01" headless
        if not on("ZeroEnsuizanMode01") and on("ZeroEnsuizanInput01"):
            if on("ZeroGuardShellInput04"):
                force("ZeroGuardShellInput01", 1)
                force("ZeroGuardShellInput04", 0)

    # 1. TitleLoadingControl
    if not on("TitleLoading01"):
        force("IntroSkip03", 1)

    # 2. ArmorByPartControl
    if on("ArmorByPart01"):
        if not on("ArmorByPart02") and not on("ArmorByPart03"):
            force("ArmorByPart02", 1)
    else:
        force("ArmorByPart02", 0)
        force("ArmorByPart03", 0)
        force("ArmorByPart04", 0)

    # 3. ScriptPatchControl (only the IngameOptions value-force; mugshot DDL
    #    option-list edits don't change option-var values for defaults)
    if not on("ScriptPatch02"):
        force("IngameOptions01", 0)

    # 4. MachDashInputControl
    set_a = set_b = None
    if on("MachDashInput01") or on("MachDashInput02"):
        if on("MachDashWait04"):
            set_a, set_b = "Disable", "Enable"
        else:
            set_a, set_b = "Enable", "Disable"
    elif on("MachDashInput03"):
        if on("MachDashWait04"):
            set_a, set_b = "Disable", "Enable"
        else:
            set_a, set_b = "Enable", "Enable"
    if set_a == "Disable":
        force("MachDashDuration01", _dat_default(db, "MachDashDuration01"))
        force("MachDashSpeed01", _dat_default(db, "MachDashSpeed01"))
    if set_b == "Disable":
        force("MachDashDuration02", _dat_default(db, "MachDashDuration02"))
        force("MachDashSpeed02", _dat_default(db, "MachDashSpeed02"))
        force("MachDashSpeed03", _dat_default(db, "MachDashSpeed03"))
    if on("MachDashWait04") and on("MachDashInput03"):
        force("MachDashInput01", 1)

    # 5. MachDashCancelControl
    if on("MachDashCancel01"):
        force("MachDashImmunity01", _dat_default(db, "MachDashImmunity01"))

    # 6. ZeroEnsuizanModeControl
    if on("ZeroEnsuizanMode01"):
        pass  # enable-only
    else:
        if on("ZeroSentsuizanInput02"):
            force("ZeroEnsuizanInput02", 1)
        else:
            force("ZeroEnsuizanInput01", 1)
        force("ZeroEnsuizanReps01", _dat_default(db, "ZeroEnsuizanReps01"))
    zero_guard_shell()

    # 7. ZeroSentsuizanInputControl
    if on("ZeroSentsuizanInput01"):
        if on("ZeroEnsuizanInput03"):
            force("ZeroEnsuizanInput01", 1)
    elif on("ZeroSentsuizanInput02"):
        if on("ZeroEnsuizanInput01"):
            force("ZeroEnsuizanInput02", 1)
    elif on("ZeroSentsuizanInput03"):
        if on("ZeroEnsuizanInput02"):
            force("ZeroEnsuizanInput01", 1)

    # 8. ZeroEnsuizanInputControl
    if on("ZeroEnsuizanInput01"):
        if on("ZeroSentsuizanInput02"):
            force("ZeroSentsuizanInput01", 1)
    elif on("ZeroEnsuizanInput02"):
        if on("ZeroSentsuizanInput03"):
            force("ZeroSentsuizanInput01", 1)
        force("ZeroYammarInput01", 1)
    elif on("ZeroEnsuizanInput03"):
        if on("ZeroSentsuizanInput01"):
            force("ZeroSentsuizanInput02", 1)
    zero_guard_shell()

    # 9. RescRepRandomControl
    if on("PartsRandomTitle01"):
        if not on("PartsRandom01") and not on("PartsRandom02"):
            force("PartsRandom01", 1)
    else:
        force("PartsRandom01", 0)
        force("PartsRandom02", 0)

    # 11. CharStartControl (10 DmgTableGate is show/hide only)
    cs = val("CharStart01")
    if cs == "Falcon Armor":
        force("CharAdd01", 1)
    elif cs == "Blade Armor":
        force("CharAdd03", 1)
    elif cs == "Shadow Armor":
        force("CharAdd02", 1)
    elif cs == "Ultimate Armor":
        force("CharAdd04", 1)

    # 13. HoverUnlockControl (12 SharedStat is FocusV-gated -> no-op headless)
    if val("HoverUnlock02") == "1":
        force("HoverUnlock01", 1)

    # 14. LivesSwitchControl: Infinite lives forces ExitButton03 on (an option var
    #     with its own ASM — "Anywhere" exit) and disables the ExitButton picker.
    if on("LivesSwitch01"):
        force("ExitButton03", 1)

    # 15. ZeroGuardShellInputControl
    zero_guard_shell()
    return m


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


def total_list_order(db) -> list[str]:
    """TotalList (createlist.ahk / _dat_init.ahk:298): the ORDERED var-set names
    CreateList iterates. Order determines PatchList order for changed options,
    which matters when writes overlap. = Text + NumWord + NumByte + NumHalf +
    Add + General filter lists, concatenated in that order."""
    order: list[str] = []
    seen: set[str] = set()
    for key in ("TextFilterList", "NumWordFilterList", "NumByteFilterList",
                "NumHalfwordFilterList", "AddList"):
        for vs in db._lines(key):
            if vs not in seen:
                seen.add(vs); order.append(vs)
    for vs in db.general_list:
        if vs not in seen:
            seen.add(vs); order.append(vs)
    return order


def _instances_ordered(db, varset: str) -> list[str]:
    """Choice instances of a var-set in numeric (01,02,...) order, as VarCount
    enumerates them."""
    def _suf(name):
        return int(name[len(varset):]) if name[len(varset):].isdigit() else 0
    return sorted(db.instances_of(varset), key=_suf)


def active_options(db, merged: dict, base: dict) -> list[str]:
    """CreateList: option instances whose value differs from default, in TotalList
    var-set order then numeric instance order. Reference is the shipped default
    profile (the true normalized "no changes" state) — the AHK engine compares
    against `_Default` after GuiControlAll normalization; comparing the already-
    normalized merged profile against the (normalized) default profile is
    equivalent and sidesteps the _dat default's formatting quirks."""
    active: list[str] = []
    for varset in total_list_order(db):
        for inst in _instances_ordered(db, varset):
            o = db.options.get(inst)
            if not o or (not o["asm"] and not o["direct"]):
                continue
            if str(merged.get(inst, "")).strip() != str(base.get(inst, "")).strip():
                active.append(inst)
    return active


# --------------------------------------------------------------------------
# Ordered PatchList operations (filter.ahk PatchListAdd/Remove + PreReq/Reorder).
# --------------------------------------------------------------------------
def _pl_remove(pl: list[str], var: str) -> None:
    """Remove the first occurrence of `var` (PatchListRemove)."""
    if var in pl:
        pl.remove(var)


def _pl_add(pl: list[str], addlist: list[str], breakvar=None,
            position: str = "After") -> None:
    """PatchListAdd: insert `addlist` relative to `breakvar`. If `breakvar` is
    absent, append (After) / prepend (Before) to the whole list."""
    if not addlist:
        return
    if breakvar is None or breakvar not in pl:
        if position == "After":
            pl.extend(addlist)
        else:
            pl[:0] = addlist
        return
    i = pl.index(breakvar)
    at = i + 1 if position == "After" else i
    pl[at:at] = addlist


def apply_prereq(db, pl: list[str]) -> None:
    """PreReqFilter: for each `dependant: dep1,dep2` line, if the dependant is in
    the list, insert each not-yet-present dep immediately before it (in order)."""
    for dependant, deps in db.prereq.items():
        if dependant not in pl:
            continue
        addlist = [d for d in deps if d not in pl]
        _pl_add(pl, addlist, dependant, "Before")


def apply_reorder(db, pl: list[str]) -> None:
    """ReorderFilter: for each `first: follower1,follower2` line, if `first` is in
    the list, every follower that currently sits BEFORE `first` is moved to just
    after `first` (preserving ReorderList follower order)."""
    for first, followers in db.reorder.items():
        if first not in pl:
            continue
        fi = pl.index(first)
        moved: list[str] = []
        for f in followers:
            if f in pl and pl.index(f) < fi:
                _pl_remove(pl, f)
                moved.append(f)
                fi = pl.index(first)     # index shifts after removal
        _pl_add(pl, moved, first, "After")


def build_patchlist(db, merged: dict, base: dict) -> tuple[str, list[str]]:
    """Assemble the ordered PatchList (var names) the way the AHK pipeline does,
    for the COMMON case: CreateList (TotalList order) -> Exception_A base prepend
    + PATCHFILE -> PreReqFilter -> ReorderFilter. BaseFilter is debug-only.
    (Value-dependent Exception_A/_B transforms and numeric/script filters are
    added in later increments.)"""
    active = active_options(db, merged, base)
    # PatchList Check 1 (patch.ahk): no changed options (or only the always-on
    # CharAdd01 sentinel) -> "No changes made"; Exception_A never runs, so the
    # base list is NOT prepended and PATCHFILE stays unset.
    if not active or active == ["CharAdd01"]:
        return "", []
    # PATCHFILE + base prepend (Exception_A). No ScriptPatch support yet -> b01.
    patchfile = "b01"
    pl = list(db.patchlist_base) + active
    apply_prereq(db, pl)
    apply_reorder(db, pl)
    return patchfile, pl


def build_writelist(db, merged: dict, base: dict):
    """(PATCHFILE, ordered [(hexdata, offset_dec), ...]) for a merged profile.
    Order follows the assembled PatchList (matters for overlapping writes)."""
    merged = gui_control_all(db, merged)     # ProfileLoad normalization
    patchfile, pl = build_patchlist(db, merged, base)
    writes: list[tuple[str, int]] = []
    for var in pl:
        for data, off in expand_entry(db, var, patchfile):
            writes += ecc_split(data, off)      # split writes crossing an ECC boundary
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


def parse_plan(plan: str) -> tuple[str, list[tuple[str, int]]]:
    """Parse a dump plan into (PATCHFILE, ORDERED [(data, offset), ...]). Order is
    preserved — the oracle emits WriteList in PatchList order, which is what an
    order-sensitive (overlapping-write) compare needs."""
    patchfile = ""
    writes: list[tuple[str, int]] = []
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
            writes.append((data.strip(), int(off.strip())))
    return patchfile, writes


def _oracle_plan(selection_json: str, scratch: Path) -> tuple[str, list[tuple[str, int]]]:
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    scratch.mkdir(parents=True, exist_ok=True)
    gen = scratch / "_pc.x6tweaksprofile"
    gen.write_text(twr.emit_profile(merged_profile(db, selection_json)), encoding="utf-8")
    ahk = twr.find_autohotkey("")
    plan = twr.dump_engine(str(gen), twr.DEFAULT_VANILLA, scratch, twr.DEFAULT_PATCHER_SRC,
                           twr.DEFAULT_RUN_EXTRACTED, ahk)
    return parse_plan(plan)


def compare(pf_py, writes_py, pf_or, writes_or, label: str) -> bool:
    """Order-aware compare of a python WriteList against the oracle's. Reports the
    first ordering divergence plus set-level MISSING/EXTRA for diagnosis."""
    order_ok = (writes_py == writes_or)      # list ==: order-sensitive
    ok = (pf_py == pf_or) and order_ok
    print(f"selection: {label}")
    print(f"  PATCHFILE  python={pf_py!r}  oracle={pf_or!r}  "
          f"{'OK' if pf_py==pf_or else 'MISMATCH'}")
    print(f"  writes     python={len(writes_py)}  oracle={len(writes_or)}  "
          f"order={'OK' if order_ok else 'DIVERGENT'}")
    sp, so = set(writes_py), set(writes_or)
    missing = so - sp                       # oracle has, python missed
    extra = sp - so                         # python produced, oracle didn't
    if missing:
        print(f"  MISSING ({len(missing)}) — oracle has, port didn't produce:")
        for d, o in sorted(missing, key=lambda x: x[1])[:12]:
            print(f"    {o}  {d[:48]}{'...' if len(d)>48 else ''}")
    if extra:
        print(f"  EXTRA ({len(extra)}) — port produced, oracle didn't:")
        for d, o in sorted(extra, key=lambda x: x[1])[:12]:
            print(f"    {o}  {d[:48]}{'...' if len(d)>48 else ''}")
    if not missing and not extra and not order_ok:
        # same multiset, wrong order: show first mismatch (overlap-order bug)
        for i, (a, b) in enumerate(zip(writes_py, writes_or)):
            if a != b:
                print(f"  ORDER diverges at #{i}: python={a[1]} oracle={b[1]}")
                break
    print(f"  => {'BYTE-IDENTICAL' if ok else 'DIVERGENT'}")
    return ok


def check_against_plan(selection_json: str, plan_text: str, label: str = "") -> bool:
    """Compare the port against a CACHED oracle plan (offline; no AHK run)."""
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    merged = merged_profile(db, selection_json)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    pf_py, writes_py = build_writelist(db, merged, base)
    pf_or, writes_or = parse_plan(plan_text)
    return compare(pf_py, writes_py, pf_or, writes_or, label or selection_json)


def check(selection_json: str, scratch: Path) -> bool:
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    merged = merged_profile(db, selection_json)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    pf_py, writes_py = build_writelist(db, merged, base)
    pf_or, writes_or = _oracle_plan(selection_json, scratch)
    return compare(pf_py, writes_py, pf_or, writes_or, selection_json)


if __name__ == "__main__":
    scratch = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("./_portcheck")
    sel = sys.argv[1] if len(sys.argv) > 1 else '{"LivesSwitch03": true}'
    sys.exit(0 if check(sel, scratch) else 1)
