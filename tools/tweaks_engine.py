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

apply_bin/apply_selection additionally reproduce patchapply.ahk in pure Python
(xdelta3 base + hex writes + error_recalc), so the launcher can build a patched
BIN with NO AutoHotkey. Proven byte-identical to the AHK engine by whole-BIN MD5
across the b01 and s02 bases. This is AHK-free for any selection the engine fully
covers; selections touching still-unported options (New Game/RescRep, Mugshot
file inserts — see TODO) must not be routed through it until those land.

Coverage so far (each increment guarded by a byte-for-byte, order-aware oracle diff):
  1. STATIC _ASMnn payloads (checkboxes, static radios), base prepend, ECC split.
  2. GuiControlAll VALUE-FORCING normalization (ArmorByPart/LivesSwitch/... control
     interlocks) + the empty-PatchList "No changes" guard; CreateList in TotalList
     order (payload-less selector checkboxes included); PreReqFilter + ReorderFilter;
     ordered (overlap-safe) WriteList.
  3. Checkbox-combo Exception_A transforms: LowerDef (LowerDef01/02 + ArmorByPart01
     -> LowerDef_<X|Zero|All>_<A|B> direct variant) and DashGlobal01+ArmorByPart01
     -> DashGlobal01_ArmorByPart. expand_entry now also emits `direct` value+offset
     writes (not just _ASMnn).
  4. Numeric/text input-conversion filters (filter.ahk): TextFilter (TextFilterTable
     lookup), NumWordFilter_Value+NumWordFilter_Offset (DEC2HEX(,8) then LE-swapped
     W1/W2 halfword pair at Offset/Offset+4), NumHalfwordFilter (DEC2HEX_LE(,4)),
     NumByteFilter (DEC2HEX(,2)). The GUI value becomes the BIN write.
     Plus the two numeric-consuming Exception_A transforms — NightmareMod01
     (assembled ASM blob at 4 offsets) and LivesValue04 (Max Lives cap: clamp 99,
     LivesDisplay01 when >9, companion LivesValue04b = DEC2HEX_LE(cap+1,4)) — via a
     `synth` side channel of exception-built writes.
  5. ScriptPatch s02/s03 (Localization base): ScriptPatch02/03 in the changed set
     selects the s02/s03 base xdelta3 and prepends PatchList_Script; vars with a
     _Offset_S02 variant then resolve to the S02 set. (ScriptPatchControl's Mugshot
     option edits are dead code — wrong var names — so no Mugshot coupling.)
  6. Pipeline reordered to match patch.ahk exactly (Exception_A -> value filters ->
     Exception_B -> PreReq -> Reorder). Exception_B started with Saber Animations:
     an Anim frame filtered to "00" -> "01" plus a companion "00" at each offset+2,
     with the AHK set/frame loop's break semantics (a first frame AnimSS01 set to 0
     is AHK-falsy and suppresses the whole set).
     with the AHK set/frame loop's break semantics (a first frame AnimSS01 set to 0
     is AHK-falsy and suppresses the whole set). Plus the DmgTableGateDmg01 HexSub
     (max-complement) scalar.
  7. New Game base (exception_b.ahk): any NewGameList option prepends the shared
     `NewGame` ASM foundation — this alone fully covers UnlockCode. Plus the Mach
     Dash hybrid Input03+Cancel03/04 combined-ASM variant (exception_a.ahk).
  8. AddFilter (filter.ahk): AddList groups (HeartTankAdd, SubtankAdd, CharAdd,
     PartsLifeUp/EnergyUp, PartsSetNN) collapse selected instances into one group
     var = little-endian bitmask (2^(i-1) per selected instance). HeartTankAdd is
     byte-identical on its own; SubtankAdd/CharAdd/PartsSet also need their
     Exception_B transforms (below) to finish.
  9. CreateList baseline fix + CharAdd/ArmorParts (exception_b.ahk:244-266).
     active_options now compares the submitted value against the `_dat` `_Default`
     (faithful CreateList) with AHK `=` semantics (numeric-aware, quote-normalized,
     empty->default) instead of the default profile — so the always-on CharAdd01
     sentinel is universally active. The CharAdd Exception_B removes the "01"-only
     group (net zero for non-New-Game selections) or, when CharStart01 is picked,
     builds ArmorParts = SH+BL (F if Shadow/Blade selected) + appends MenuDefaultSel01
     when Falcon (CharAdd01) is off. expand_entry now emits a var's direct/filtered
     write BEFORE its _ASMnn (ASMFilter order) — matters only for CharStart01, the
     one var carrying both. Oracle-validated byte-identical across 10 CharAdd/CharStart
     cases + whole-BIN MD5-identical to the AHK build.
Still TODO: the rest of the New Game/RescRep Exception_B block (SubTank swap,
LifeUp/EnergyUp, PartsSet packing, RescRep tables incl PartsRandom
[non-deterministic], RescRepStatus New-Game gating), other Exception_A (Mugshot
assembly, Zero hints, BossHealth), external file inserts.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

# PartsRandom (RescRep parts randomizer) is non-deterministic by design — it
# scrambles where reploid parts live, so byte-matching the AHK oracle is
# meaningless (the AHK itself re-rolls every run). We SEED the shuffle so a build
# is reproducible (stable variant id => one recompile, and shareable), overridable
# per-player via the MMX6_PARTS_SEED env var (the launcher's seed field / the
# resolver's --parts-seed set it). Faithful to Sort,,Random in shape, not in the
# exact permutation.
DEFAULT_PARTS_SEED = "mmx6-tweaks-default"


def _parts_seed() -> str:
    """The active PartsRandom seed, read at build time so a caller can set
    MMX6_PARTS_SEED (via --parts-seed / the launcher field) before apply."""
    return os.environ.get("MMX6_PARTS_SEED") or DEFAULT_PARTS_SEED

# Load the resolver as a module (it owns TweaksDB + the AHK dump oracle).
_spec = importlib.util.spec_from_file_location(
    "tweaks_resolver", Path(__file__).with_name("tweaks_resolver.py"))
twr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(twr)


def hex2dec(h: str) -> int:
    return int(str(h).strip(), 16)


# --------------------------------------------------------------------------
# Hex conversion primitives (port of _lib/_HexLib.ahk DEC2HEX/DEC2HEX_LE/
# EndianSwap/Padd). The value filters (filter.ahk) run every GUI-supplied
# number/text through these before it becomes a BIN write.
# --------------------------------------------------------------------------
def _dec2hex(num, padding: int = 0) -> str:
    """DEC2HEX(Num,Padding): uppercase hex, left zero-padded to `padding` chars
    (Padd only pads — never truncates, matching AHK)."""
    s = format(int(str(num).strip()), "X")
    return s.rjust(padding, "0") if padding else s


def _endian_swap(s: str) -> str:
    """EndianSwap: pad to even length, then reverse byte (2-char) order."""
    if len(s) % 2:
        s = "0" + s
    return "".join(s[i:i + 2] for i in range(len(s) - 2, -1, -2))


def _dec2hex_le(num, padding: int = 1) -> str:
    """DEC2HEX_LE(Input,Padding): DEC2HEX then EndianSwap (little-endian bytes)."""
    return _endian_swap(_dec2hex(num, padding))


def _hexsub(inp, padding: int = 4) -> str:
    """HexSub (filter.ahk): EndianSwap(DEC2HEX(HEX2DEC('F'*padding) - Input + 1,
    padding)) — a little-endian 'max - value' complement (used to invert a
    damage/gate scalar)."""
    top = hex2dec("F" * padding)
    return _endian_swap(_dec2hex(top - int(str(inp).strip()) + 1, padding))


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


def _radio_siblings(db):
    """{radio var: [other vars in its radio group]}. The AHK GUI auto-clears a
    radio group when one member is set (`GuiControl, Main:, radio, 1`); force()
    replicates that. Cached on db."""
    cache = getattr(db, "_radio_sib_cache", None)
    if cache is not None:
        return cache
    from collections import defaultdict
    groups = defaultdict(list)
    for c in twr.parse_gui_catalog(db.src_dir, db):
        if c.get("type") == "radio" and c.get("var") and c.get("group") is not None:
            groups[c["group"]].append(c["var"])
    cache = {}
    for members in groups.values():
        for v in members:
            cache[v] = [x for x in members if x != v]
    db._radio_sib_cache = cache
    return cache


def gui_control_all(db, m: dict) -> dict:
    """Return a normalized copy of a merged profile, applying the value-forcing
    subs of GuiControlAll in their AHK order. `m` maps VarName -> string value."""
    m = dict(m)
    _sib = _radio_siblings(db)

    def val(v):
        return m.get(v, _dat_default(db, v))

    def on(v):
        return _truthy(val(v))

    def force(v, value):
        m[v] = str(value)
        if _truthy(value):                      # setting a radio clears its group,
            for s in _sib.get(v, ()):           # exactly like the AHK GUI does
                m[s] = "0"

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

    # ZeroYammarInput coupling (guicontrol ZeroYammarInput_Disable, 341-410): Yammar01
    # is forced on when the resolved input is ZeroEnsuizanInput02 or ZeroSentsuizanInput03
    # (they share Yammar's input button). Checked AFTER the cross-forcing above so a
    # ZeroSentsuizanInput02 selection — which cascades to ZeroEnsuizanInput02 — is seen.
    # (The buried force at ZeroEnsuizanInput02's elif above is missed when Input01 is
    # also on, since force() does not clear radio siblings the way the AHK GUI does.)
    if on("ZeroEnsuizanInput02") or on("ZeroSentsuizanInput03"):
        force("ZeroYammarInput01", 1)
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


def _offsets_for_direct(direct_entries: list, patchfile: str) -> list[str]:
    """Ordered offset-hex list for a DIRECT var (bare `Var = value` + `Var_Offset`
    [+ `_Offset2`/`_B01`/`_S02`]) — same set/nth/multi-line rules as _ASM offsets."""
    prefer = {"b01": "B01", "s02": "S02", "s03": "S02"}.get(patchfile, "COMMON")
    by_nth: dict[int, dict[str, str]] = {}
    for d in direct_entries:
        if d.get("kind") == "offset":
            by_nth.setdefault(d["nth"], {})[d["set"]] = d["offset"]
    out = []
    for nth in sorted(by_nth):
        sets = by_nth[nth]
        chosen = sets.get(prefer) or sets.get("COMMON") or next(iter(sets.values()))
        for off in str(chosen).splitlines():
            if off.strip():
                out.append(off.strip())
    return out


def _offsets_for_file(file_entries: list, slot: int, patchfile: str) -> list[str]:
    """Ordered offset-hex list for one file slot (Var_File0N_Offset[_B01|_S02]),
    choosing the SET by PATCHFILE like _offsets_for_slot."""
    prefer = {"b01": "B01", "s02": "S02", "s03": "S02"}.get(patchfile, "COMMON")
    by_nth: dict[int, dict[str, str]] = {}
    for f in file_entries:
        if f.get("kind") == "offset" and f["slot"] == slot:
            by_nth.setdefault(f["nth"], {})[f["set"]] = f["offset"]
    out = []
    for nth in sorted(by_nth):
        sets = by_nth[nth]
        chosen = sets.get(prefer) or sets.get("COMMON") or next(iter(sets.values()))
        for off in str(chosen).splitlines():
            if off.strip():
                out.append(off.strip())
    return out


# ExtDataDir (the patcher's art-asset root) — Var_File0N_Path values resolve here.
EXT_DATA_DIR = twr.DEFAULT_RUN_EXTRACTED / "data"


def _file_inserts(db, var: str, patchfile: str, merged: dict) -> list[tuple[str, str, int]]:
    """File inserts for one PatchList var: [(file_var, filepath, offset_dec), ...].
    A var with a `_File0N_Path` payload contributes one insert per slot; the source
    is ExtDataDir/<path> (Mugshot appends `_<OptionID>.bin`, OptionID = the last
    char of the var's value — SubStr(%Var%,0) in FileFilter)."""
    o = db.options.get(var)
    if not o:
        return []
    paths = {f["slot"]: f["path"] for f in o["files"] if f.get("kind") == "path"}
    if not paths:
        return []
    option_id = str(merged.get(var, "") or "")[-1:]
    is_mugshot = "Mugshot" in var
    out: list[tuple[str, str, int]] = []
    for slot in sorted(paths):
        rel = paths[slot].replace("\\", "/").strip()
        fp = EXT_DATA_DIR / (rel + "_" + option_id + ".bin" if is_mugshot else rel)
        for off_hex in _offsets_for_file(o["files"], slot, patchfile):
            out.append((f"{var}_File{slot:02d}", str(fp), hex2dec(off_hex)))
    return out


def expand_entry(db, var: str, patchfile: str, values: dict | None = None,
                 synth: dict | None = None) -> list[tuple[str, int]]:
    """Expand one PatchList var into its (hex data, decimal offset) writes.
    Handles synthesized exception vars (`synth[var]` — fully-resolved writes for
    vars an Exception_A transform builds, e.g. NightmareMod0100), static `_ASMnn`
    payloads (checkboxes, base hacks), static `direct` vars (a bare `Var = value`
    paired with `Var_Offset`, e.g. LowerDef_X_A), AND filtered-value vars — a
    numeric/text option whose write value came from the GUI and was converted by
    apply_value_filters (`values[var]`). Returns [] for vars with none of these."""
    synth = synth or {}
    if var in synth:            # exception-synthesized var: writes already resolved
        return list(synth[var])
    o = db.options.get(var)
    if not o:
        return []
    values = values or {}
    # Emit order = ASMFilter order: the var's OWN direct/filtered write (%Var% at
    # %Var%_Offset) comes FIRST, then its `_ASMnn` entries — ASMFilter inserts the
    # ASM lines *After* the base var, so PatchApply writes the base var before them.
    # CharStart01 is the only var carrying both (a TextFiltered code AND an ASM), so
    # this ordering only matters there; every other var has just one kind.
    direct_writes: list[tuple[str, int]] = []
    fv = values.get(var)
    if fv is not None:
        # Filtered GUI value (numeric/text option) written at the var's direct
        # offset(s). NumWord vars split into a W1/W2 halfword pair (LE-swapped) at
        # Var_Offset and Var_Offset+4 (filter.ahk NumWordFilter_Offset).
        data = str(fv).replace(" ", "")
        offs = _offsets_for_direct(o["direct"], patchfile)
        if var in db.num_word_vars:
            w1 = data[2:4] + data[0:2]
            w2 = data[6:8] + data[4:6]
            for off_hex in offs:
                base = hex2dec(off_hex)
                direct_writes.append((w1, base))
                direct_writes.append((w2, base + 4))
        else:
            for off_hex in offs:
                direct_writes.append((data, hex2dec(off_hex)))
    else:
        # Static direct value writes: a bare `Var = value` at each of its offset(s).
        static = [d["value"] for d in o["direct"] if d.get("kind") == "value"]
        if static:
            data = str(static[0]).replace(" ", "")
            for off_hex in _offsets_for_direct(o["direct"], patchfile):
                direct_writes.append((data, hex2dec(off_hex)))
    asm_writes: list[tuple[str, int]] = []
    byte_slots = {a["slot"]: a["hex"] for a in o["asm"] if a.get("kind") == "bytes"}
    # Replicate VarCount("<var>_ASM", 2) (createlist.ahk:54): enumerate slots from 1
    # and STOP at the first that doesn't "exist" — an empty ASMnn that is not "0" and
    # has no _Default / _01_ASM override. An empty ASMnn is the AHK author's list
    # terminator; slots after it are dead (e.g. HoverUnlock02_ASM10="" caps the list
    # at 9, dropping 10-18). Iterating all present slots over-produces those writes.
    slot = 1
    while slot in byte_slots:
        hexv = byte_slots[slot]
        exists = (bool(hexv) or hexv == "0"
                  or db.dat.get(f"{var}_ASM{slot:02d}_Default", "") != ""
                  or db.dat.get(f"{var}_ASM{slot:02d}_01_ASM", "") != "")
        if not exists:
            break
        data = hexv.replace(" ", "")
        for off_hex in _offsets_for_slot(o["asm"], slot, patchfile):
            asm_writes.append((data, hex2dec(off_hex)))
        slot += 1
    return direct_writes + asm_writes


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


def _ahk_number(s):
    """AHK numeric coercion: float if `s` is a pure number (optional sign/decimal),
    else None. Empty and hex-with-letters (offsets) coerce to None -> string compare."""
    s = str(s).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cmp_dequote(v: str) -> str:
    """Strip surrounding quotes + whitespace. AHK stores `Var = "RESCUED"` WITH the
    quotes on BOTH the profile value and the _dat _Default, so the AHK compare is
    quote-vs-quote (equal). The resolver's parser strips quotes from _dat only, so
    strip both sides here to reproduce the AHK equality."""
    v = str(v).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def _ahk_eq(a, b) -> bool:
    """AHK `=` equality: numeric compare when both look numeric (so `+0` == `0`,
    `01` == `1`), else case-insensitive string compare (quote/space-normalized)."""
    a, b = _cmp_dequote(a), _cmp_dequote(b)
    na, nb = _ahk_number(a), _ahk_number(b)
    if na is not None and nb is not None:
        return na == nb
    return a.lower() == b.lower()


def active_options(db, merged: dict, base: dict = None) -> list[str]:
    """CreateList (createlist.ahk): option instances whose SUBMITTED value differs
    from its `_dat` `_Default`, in TotalList var-set order then numeric instance
    order. Faithful to the AHK loop: an empty value is treated as its default (so
    it is not counted), and the compare uses AHK `=` semantics (numeric-aware,
    case-insensitive, quote-normalized — see `_ahk_eq`).

    The reference is the `_dat` `_Default`, NOT the default profile: they diverge
    for a handful of instances (GUI 'Checked Disabled' + `+0`/quoted/empty profile
    artifacts). Only ONE of those diverging instances survives normalization as
    genuinely active — the always-on CharAdd01 sentinel (submitted `1`, _dat
    default `0`) — which the CharAdd Exception_B (removes the "01"-only group) and
    the no-change guard absorb, keeping every non-New-Game selection byte-identical.
    `base` is accepted but ignored (kept for existing callers)."""
    active: list[str] = []
    for varset in total_list_order(db):
        for inst in _instances_ordered(db, varset):
            # CreateList adds ANY changed instance, even payload-less "selector"
            # checkboxes whose effect is applied by an exception — expand_entry
            # yields no write for those and VerifyFilter drops them, so faithful.
            if inst not in db.options:
                continue
            val = str(merged.get(inst, "")).strip()
            dflt = str(db.dat.get(inst + "_Default", "")).strip()
            if val == "":                       # AHK: empty -> treat as _Default
                val = dflt
            if not _ahk_eq(val, dflt):
                active.append(inst)
    return active


# --------------------------------------------------------------------------
# Coverage gate (Phase C): which changed options the pure-Python engine does
# NOT yet reproduce byte-identically. cmd_apply consults this before routing a
# selection through apply_bin, so a parked option is refused (with a pointer to
# --engine ahk) rather than silently emitting a divergent / incomplete BIN.
# --------------------------------------------------------------------------
# Option-name PREFIXES whose Exception_B / file-insert handling is still
# unported or only oracle-PENDING (see the module docstring "Still TODO" and the
# port memo). A changed option whose name starts with any of these is PARKED.
# The ENTIRE tool is now ported + oracle-validated (whole-BIN MD5 == AHK): the full
# New Game Status tab (CharAdd/CharStart/ArmorParts, SubtankAdd, LifeUp/EnergyUp,
# RescRepStatus, PartsSet packing + RescRepFoundTable), the PartsRandom randomizer
# (seeded), the Title/Load-screen art-file inserts, AND the Mugshot custom-portrait
# assembly (MugshotAssembly StringRewrite + per-mugshot ASM + art inserts). No option
# family is parked by name any more; the only residual gate is on file-insert vars
# whose art source is missing on disk (e.g. a custom mugshot the user hasn't supplied).
PARKED_PREFIXES = ()


def coverage_gaps(db, merged: dict, base: dict) -> list[tuple[str, str]]:
    """Return [(option_instance, reason)] for changed options the pure-Python
    engine cannot yet build byte-identically. Empty list => fully covered, safe
    to route through apply_bin. `merged` is the raw merged profile (this
    normalizes it the same way build_writelist does before comparing)."""
    merged_n = gui_control_all(db, merged)
    gaps: list[tuple[str, str]] = []
    for inst in active_options(db, merged_n, base):
        pref = next((p for p in PARKED_PREFIXES if inst.startswith(p)), None)
        if pref:
            gaps.append((inst, f"{pref}: unported / non-deterministic"))
            continue
        # File-insert vars (Title/Load screens) are supported, but only if their
        # art sources exist on disk (Mugshot custom art is parked above by prefix).
        o = db.options.get(inst)
        if o and any(f.get("kind") == "path" for f in o.get("files", [])):
            for _fv, fp, _off in _file_inserts(db, inst, "b01", merged_n):
                if not Path(fp).exists():
                    gaps.append((inst, f"art-insert source missing: {Path(fp).name}"))
                    break
    return gaps


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


def apply_exception_a(db, merged: dict, pl: list[str], synth: dict,
                      patchfile: str) -> None:
    """Value/combination-dependent Exception_A transforms (the ones ported so far;
    exception_a.ahk runs AFTER the base prepend, BEFORE PreReq/Reorder). Mutates
    the ordered PatchList and `synth` (exception-built writes) in place, and may
    clamp values in `merged`. `merged` is the normalized profile."""
    def on(v):
        return _truthy(merged.get(v, _dat_default(db, v)))

    def _num(v):
        return int(str(merged.get(v, _dat_default(db, v))).strip())

    # NightmareMod01 (max Nightmare "dark" intensity). Assemble a tiny ASM blob
    # embedding the value and value-1 as immediates: <val>00422802004014<val-1>000224,
    # written at every NightmareMod01 offset. The synthesized var NightmareMod0100
    # replaces NightmareMod01 in the list. (exception_a.ahk:28-52)
    if "NightmareMod01" in pl:
        nm = _num("NightmareMod01")
        hi, lo = _dec2hex(nm), _dec2hex(nm - 1)
        if len(hi) != 2:
            hi = "0" + hi
        if len(lo) != 2:
            lo = "0" + lo
        val = hi + "00422802004014" + lo + "000224"
        offs = _offsets_for_direct(db.options["NightmareMod01"]["direct"], patchfile)
        synth["NightmareMod0100"] = [(val, hex2dec(o)) for o in offs]
        _pl_add(pl, ["NightmareMod0100"], "NightmareMod01", "After")
        _pl_remove(pl, "NightmareMod01")

    # LivesValue04 (Max Lives cap). Clamp to 99; when >9, also patch the 2-digit
    # lives display (LivesDisplay01, static ASM). Write a companion "cap+1" limit
    # var LivesValue04b = DEC2HEX_LE(cap+1,4). LivesValue04 itself stays in the list
    # and is NumHalfword-filtered downstream (it sees the clamped value via merged).
    # (exception_a.ahk:55-64)
    if "LivesValue04" in pl:
        cap = _num("LivesValue04")
        if cap > 99:
            cap = 99
        merged["LivesValue04"] = str(cap)
        if cap > 9:
            _pl_add(pl, ["LivesDisplay01"], "LivesValue04", "Before")
        b_val = _dec2hex_le(cap + 1, 4)
        offs = _offsets_for_direct(db.options["LivesValue04b"]["direct"], patchfile)
        synth["LivesValue04b"] = [(b_val, hex2dec(o)) for o in offs]
        _pl_add(pl, ["LivesValue04b"], "LivesValue04", "After")

    # LowerDef (Lower Defense): LowerDef01 (X) / LowerDef02 (Zero) default ON;
    # turning either off selects a defense variant, keyed by the two values and
    # by whether ArmorByPart01 is on (_A: no armor-by-part, _B: with it). The
    # chosen LowerDef_<X|Zero|All>_<A|B> is a direct value+offset var. LowerDef01
    # and LowerDef02 are replaced by it. (Both-on can't reach here — then neither
    # is in the PatchList.)
    if "LowerDef01" in pl or "LowerDef02" in pl:
        d01, d02 = on("LowerDef01"), on("LowerDef02")
        variant = None
        if not d01 and d02:
            variant = "LowerDef_X"
        elif d01 and not d02:
            variant = "LowerDef_Zero"
        elif not d01 and not d02:
            variant = "LowerDef_All"
        if variant:
            variant += "_B" if on("ArmorByPart01") else "_A"
            _pl_add(pl, [variant], "LowerDef01", "After")
            _pl_remove(pl, "LowerDef01")
            _pl_remove(pl, "LowerDef02")

    # Dash unlock + Armor by part: X's Air Dash unlock has a distinct payload when
    # incomplete armors are active -> swap DashGlobal01 for the combined variant.
    if "ArmorByPart01" in pl and "DashGlobal01" in pl:
        _pl_add(pl, ["DashGlobal01_ArmorByPart"], "DashGlobal01", "After")
        _pl_remove(pl, "DashGlobal01")

    # Mugshot custom-portrait assembly (exception_a.ahk:100-172).
    _mugshot_assembly(db, merged, pl, synth, patchfile)

    # Mach Dash hybrid (Hold/Release): Input03 combined with Cancel03/04 adds a
    # distinct combined-ASM variant. (exception_a.ahk:178-183)
    if "MachDashInput03" in pl and ("MachDashCancel03" in pl or "MachDashCancel04" in pl):
        _pl_add(pl, ["MachDashInput03_Cancel03"], "MachDashInput03", "After")

    _zero_input_hints(db, pl, synth, patchfile, on)
    _zero_move_exceptions(db, merged, pl, synth, on)


def _zero_input_hints(db, pl, synth, patchfile, on):
    """ZeroHints (exception_a.ahk:184-220): on the Localization base (s02/s03, i.e.
    PatchFile != b01), add on-screen input-hint glyph strings for each Zero air move
    present in the PatchList, keyed by the resolved input. Written at the move's
    _Offset_S02. Runs BEFORE the Mode blocks (which remove the input from the list)."""
    if patchfile == "b01":
        return

    def _d(n):
        return (db.dat.get(n) or "").strip()

    up, down, air = _d("ZeroInputHint_Up"), _d("ZeroInputHint_Down"), _d("ZeroInputHint_Air")
    plus = _d("ZeroInputHint_Plus")
    atk, spc, giga = (_d("ZeroInputHint_Attack"), _d("ZeroInputHint_Special"),
                      _d("ZeroInputHint_Giga"))

    def has(prefix):
        return any(v.startswith(prefix) for v in pl)

    def add_hint(name, value):
        synth[name] = [(value, hex2dec(_d(f"{name}_Offset_S02")))]
        _pl_add(pl, [name], None, "After")

    if has("ZeroSentsuizanInput"):
        v = (up + plus + atk if on("ZeroSentsuizanInput01")
             else down + plus + spc if on("ZeroSentsuizanInput02")
             else up + plus + spc if on("ZeroSentsuizanInput03") else "")
        add_hint("ZeroInputHint_Sentsuizan", v)
    if has("ZeroEnsuizanInput"):
        v = (down + plus + spc if on("ZeroEnsuizanInput01")
             else up + plus + spc if on("ZeroEnsuizanInput02")
             else up + plus + atk if on("ZeroEnsuizanInput03")
             else air + plus + spc if on("ZeroEnsuizanInput04") else "")
        add_hint("ZeroInputHint_Ensuizan", v)
    if has("ZeroGuardShellInput"):
        v = (down + plus + spc if on("ZeroGuardShellInput04")
             else up + plus + giga if on("ZeroGuardShellInput05") else "")
        add_hint("ZeroInputHint_GuardShell", v)
    if "ZeroYammarInput01" in pl:
        add_hint("ZeroInputHint_Yammar", _d("ZeroInputHint_Yammar"))


def _zero_move_exceptions(db, merged, pl, synth, on):
    """Zero air-move exceptions (exception_a.ahk:226-289): ZeroSentsuizanMode03 and
    ZeroEnsuizanMode01 synthesize input-dependent direction/button writes on top of
    the move's base code. The selected input defaults to 01 (the input radios are
    default-on, so `on()` reflects the gui-control forcing done upstream)."""
    def _d(name):                                     # _dat constant, stripped
        return (db.dat.get(name) or "").strip()

    def _sum_byte(a, b):                              # DEC2HEX(HEX2DEC(a)+HEX2DEC(b),1)
        h = _dec2hex(int(a, 16) + int(b, 16))
        return ("0" + h) if len(h) < 2 else h

    dir_up, dir_down = _d("Direction_Up"), _d("Direction_Down")
    btn_attack, btn_special = _d("Button_Attack"), _d("Button_Special")

    # ZeroSentsuizanMode03: AND-trigger + AND-to-hold, keyed by the Sentsuizan input
    # (exception_a.ahk:226-242). Added AFTER ZeroSentsuizanMode03 in the list.
    if on("ZeroSentsuizanMode03"):
        if on("ZeroSentsuizanInput01"):
            and1, and2 = btn_attack, _sum_byte(dir_up, btn_attack)
        elif on("ZeroSentsuizanInput02"):
            and1, and2 = btn_special, _sum_byte(dir_down, btn_special)
        elif on("ZeroSentsuizanInput03"):
            and1, and2 = btn_special, _sum_byte(dir_up, btn_special)
        else:
            and1 = and2 = None
        if and1 is not None:
            synth["ZeroSentsuizanInput_AND_1"] = [(and1, hex2dec(_d("ZeroSentsuizanInput_AND_1_Offset")))]
            synth["ZeroSentsuizanInput_AND_2"] = [(and2, hex2dec(_d("ZeroSentsuizanInput_AND_2_Offset")))]
            _pl_add(pl, ["ZeroSentsuizanInput_AND_1", "ZeroSentsuizanInput_AND_2"],
                    "ZeroSentsuizanMode03", "After")

    # ZeroEnsuizanMode01: identify the Ensuizan input (default 01, written anyway),
    # remove it from normal processing, and add the air direction/button (+ a fixed
    # "direction required" instruction for inputs 01-03). (exception_a.ahk:244-289)
    if on("ZeroEnsuizanMode01"):
        ens = next((n for n in ("01", "02", "03", "04") if on("ZeroEnsuizanInput" + n)), None)
        if ens is None:
            ens = "01"                                # default, but needs to be written
        else:
            _pl_remove(pl, "ZeroEnsuizanInput" + ens)
        dir_off = hex2dec(_d("ZeroEnsuizanAirDirection_Offset"))
        btn_off = hex2dec(_d("ZeroEnsuizanAirButton_Offset"))
        add_req = True
        if ens == "01":
            air_dir, air_btn = dir_down, btn_special
        elif ens == "02":
            air_dir, air_btn = dir_up, btn_special
        elif ens == "03":
            air_dir, air_btn = dir_up, btn_attack
        else:                                          # "04": Sentsuizan-dependent dir, no Req
            air_dir = dir_down if "ZeroSentsuizanInput01" in pl else dir_up
            air_btn = _d("ZeroEnsuizanAirButton_Special")  # undefined in _dat -> empty (no write)
            add_req = False
        synth["ZeroEnsuizanAirDirection"] = [(air_dir, dir_off)]
        synth["ZeroEnsuizanAirButton"] = [(air_btn, btn_off)]
        adds = ["ZeroEnsuizanAirDirection", "ZeroEnsuizanAirButton"]
        if add_req:
            synth["ZeroEnsuizanAirDirectionReq"] = [
                (_d("ZeroEnsuizanAirDirectionReq"), hex2dec(_d("ZeroEnsuizanAirDirectionReq_Offset")))]
            adds = ["ZeroEnsuizanAirDirectionReq"] + adds
        _pl_add(pl, adds, None, "After")


def _mugshot_assembly(db, merged: dict, pl: list[str], synth: dict, patchfile: str) -> None:
    """Mugshot custom-portrait assembly (exception_a.ahk:100-172). When any
    MugshotCustom is active, read the two assembly blobs (assembly.bin/assembly_07
    .bin), StringRewrite each selected mugshot's blink/talk tile addresses into
    them, then write ASM01 at its 22 disc offsets + ASM02 at its 1 (per PATCHFILE).
    StringRewrite = positional OVERWRITE of len(insert) hex chars at a char index.
    The per-mugshot ASM (MugshotCustomNN_ASM) and the [FILES] art inserts are
    handled by the normal expand_entry / build_filelist paths."""
    if not any(v.startswith("MugshotCustom") for v in pl):
        return
    ma = db.options.get("MugshotAssembly")
    if not ma:
        return
    f1 = EXT_DATA_DIR / db.dat["MugshotAssembly_File01"].replace("\\", "/").strip()
    f2 = EXT_DATA_DIR / db.dat["MugshotAssembly_File02"].replace("\\", "/").strip()
    asm01 = f1.read_bytes().hex().upper()
    asm02 = f2.read_bytes().hex().upper()

    def rewrite(s, insert, pos):              # StringRewrite: overwrite at char pos
        return s[:pos] + insert + s[pos + len(insert):]

    n = 1
    while True:
        lst = db.dat.get(f"MugshotAssembly_List{n}")
        if not lst:
            break
        blink = (db.dat.get(f"MugshotAssembly_List{n}_Blink") or "").strip()
        talk = (db.dat.get(f"MugshotAssembly_List{n}_Talk") or "").strip()
        rb = (db.dat.get(f"MugshotAssembly_List{n}_RelOffset_Blink") or "").strip()
        rt = (db.dat.get(f"MugshotAssembly_List{n}_RelOffset_Talk") or "").strip()
        for mid in [x.strip() for x in lst.split(",") if x.strip()]:
            if f"MugshotCustom{mid}" not in pl:
                continue
            set_off = hex2dec(db.dat[f"MugshotAssembly_RelOffset_Mugshot{mid}"])
            if blink and rb:
                for bo in [x.strip() for x in rb.split(",") if x.strip()]:
                    pos = (set_off + hex2dec(bo) * 4 + 2) * 2
                    asm01 = rewrite(asm01, blink, pos)
                    asm02 = rewrite(asm02, blink, pos)
            if talk and rt:
                for to in [x.strip() for x in rt.split(",") if x.strip()]:
                    pos = (set_off + hex2dec(to) * 4 + 2) * 2
                    asm01 = rewrite(asm01, talk, pos)
                    asm02 = rewrite(asm02, talk, pos)
        n += 1
    writes = []
    for slot, data in ((1, asm01), (2, asm02)):
        for off_hex in _offsets_for_slot(ma["asm"], slot, patchfile):
            writes.append((data, hex2dec(off_hex)))
    synth["MugshotAssembly"] = writes
    _pl_add(pl, ["MugshotAssembly"], None, "After")


def apply_add_filter(db, merged: dict, pl: list[str], values: dict) -> None:
    """AddFilter (filter.ahk:101-207) — the last value filter, before Exception_B.
    Each AddList group (HeartTankAdd, SubtankAdd, CharAdd, PartsLifeUp,
    PartsEnergyUp, PartsSetNN) collapses its selected instances into ONE group var
    whose value is a little-endian bitmask: instance i (1-based) contributes 2^(i-1)
    when it is in the PatchList or its _Default is 1, counting up to the highest
    selected instance. The instances are removed and the group var appended to the
    list end. Mutates pl and writes the group value into `values`."""
    for group in db._lines("AddList"):
        present = [v for v in pl
                   if v[:-2] == group and v[len(group):].isdigit()]
        if not present:
            continue
        last = max(int(v[len(group):]) for v in present)
        total = 0
        for i in range(1, last + 1):
            inst = f"{group}{i:02d}"
            if inst in pl or _dat_default(db, inst) == "1":
                total += 1 << (i - 1)
        values[group] = _endian_swap(_dec2hex(total, 2))
        for v in present:
            _pl_remove(pl, v)
        _pl_add(pl, [group], None, "After")     # append group to list end


def _text_filter_value(db, raw: str) -> str:
    """TextFilter: map a var's GUI value through TextFilterTable (case-insensitive
    `=` compare, like AHK). The resolver stores the table with quotes stripped
    from keys, so a quoted profile value (e.g. `"RESCUED"`) is matched both raw
    and unquoted. Unmapped values pass through unchanged (AHK leaves %Var% as-is)."""
    tbl = db.text_filter_table
    lower = {k.lower(): v for k, v in tbl.items()}
    cands = [raw]
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        cands.append(raw[1:-1])
    for c in cands:
        if c in tbl:
            return tbl[c]
        if c.lower() in lower:
            return lower[c.lower()]
    return raw


def apply_value_filters(db, merged: dict, pl: list[str]) -> dict:
    """Numeric/text input-conversion filters (filter.ahk TextFilter,
    NumWordFilter_Value, NumHalfwordFilter, NumByteFilter). Returns
    {var: post-filter WRITE VALUE (hex string)} for every PatchList var that
    belongs to a filter list. The value is the GUI-submitted value (in `merged`)
    converted to the BIN's byte form:
      * NumWord (individual vars): DEC2HEX(dec, 8)  -> later split W1/W2 in expand
      * NumHalfword (var-sets):    DEC2HEX_LE(dec, 4)
      * NumByte (var-sets):        DEC2HEX(dec, 2)
      * Text (var-sets):           TextFilterTable lookup
    AddFilter is intentionally deferred (it collapses instances into a group var
    and is Exception_B/New-Game coupled)."""
    values: dict = {}
    for var in pl:
        raw = merged.get(var)
        if raw is None:
            continue
        vs2 = var[:-2]                       # var-set = instance minus 2-digit suffix
        if var in db.num_word_vars:          # NumWordFilterList = individual names
            values[var] = _dec2hex(raw, 8)
        elif vs2 in db.num_half_vars:
            values[var] = _dec2hex_le(raw, 4)
        elif vs2 in db.num_byte_vars:
            values[var] = _dec2hex(raw, 2)
        elif vs2 in db.text_filter_vars:
            values[var] = _text_filter_value(db, raw)
    return values


def _is_anim_frame(var: str) -> bool:
    """An Anim frame instance name AnimSSFF (8 chars: 'Anim' + 4 digits)."""
    return var.startswith("Anim") and len(var) == 8 and var[4:].isdigit()


def _anim_frame_value(db, merged: dict, var: str) -> str | None:
    """Post-NumByteFilter value of an Anim frame: DEC2HEX(GUI-or-default dec, 2).
    Returns None if the frame has no _Default (i.e. doesn't exist), matching the
    AHK loop's existence test."""
    dflt = db.dat.get(var + "_Default")
    if dflt is None:
        return None
    return _dec2hex(merged.get(var, dflt), 2)


def apply_exception_b(db, merged: dict, pl: list[str], synth: dict,
                      values: dict, patchfile: str) -> None:
    """Post-filter Exception_B transforms (exception_b.ahk), run AFTER the value
    filters and BEFORE PreReq/Reorder. Mutates pl / synth / values in place.
    Ported subset: Saber Animations. Deferred: DmgTableGateDmg HexSub, and the
    whole New Game block (PartsSet, PartsRandom/RescRep tables, Rank/Souls,
    SubTankAdd, CharAdd/ArmorParts, LifeUp/EnergyUp, NewGame base prepend)."""
    # Saber Animations (exception_b.ahk:6-36). Faithful port of the set/frame loop:
    #   for each set SS (01,02,...) WHILE its first frame AnimSS01 is truthy (a "00"
    #   value is AHK-falsy, so a first frame set to 0 STOPS all sets):
    #     for each frame FF (01,02,...) WHILE AnimSSFF exists:
    #       if AnimSSFF == "00": rewrite it to "01" and write a companion "00" byte
    #       at each of its offsets + 2 (an `AnimSSFF_OFF_i` entry after the frame).
    # Only fires when some Anim frame is in the list (the AHK `InStr(PatchList,Anim)`
    # gate); a "00" frame is always a user change (no Anim default is 0), so it is
    # in the PatchList and PatchListAdd's anchor exists.
    if any(_is_anim_frame(v) for v in pl):
        set_i = 1
        while True:
            ss = f"{set_i:02d}"
            first = _anim_frame_value(db, merged, f"Anim{ss}01")
            if not first or first == "00":       # first frame missing/falsy -> stop
                break
            frame_i = 1
            while True:
                var = f"Anim{ss}{frame_i:02d}"
                val = _anim_frame_value(db, merged, var)
                if val is None:                  # frame doesn't exist -> next set
                    break
                if val == "00":
                    values[var] = "01"
                    o = db.options.get(var)
                    offs = _offsets_for_direct(o["direct"], patchfile) if o else []
                    off_vars = []
                    for i, off_hex in enumerate(offs, 1):
                        ov = f"{var}_OFF_{i}"
                        synth[ov] = [("00", hex2dec(off_hex) + 2)]
                        off_vars.append(ov)
                    _pl_add(pl, off_vars, var, "After")
                frame_i += 1
            set_i += 1

    # Damage Table Gate damage scalar: HexSub the GUI value (a max-complement),
    # written at DmgTableGateDmg01_Offset. (exception_b.ahk:39-40)
    if "DmgTableGateDmg01" in pl:
        raw = merged.get("DmgTableGateDmg01", _dat_default(db, "DmgTableGateDmg01"))
        values["DmgTableGateDmg01"] = _hexsub(raw)

    # New Game: PartsSet packing + PartsRandom + RescRep "found reploids" table
    # (exception_b.ahk 44-224). AddFilter has already collapsed the PartsSet
    # instances into per-set group values (values["PartsSet0N"], a 2-hex bitmask)
    # and the PartsLifeUp/PartsEnergyUp groups (which write their own bitmask via
    # expand_entry); the individual instance flags are still in `merged`.
    partsset_in = any(v.startswith("PartsSet") for v in pl)
    # -- PartsSet packing: per-set low nibbles -> PartsSetA / PartsSetB --
    if partsset_in:
        nib = {}
        for i in range(1, 8):
            v = values.get(f"PartsSet0{i}") or ""
            if v == "" or _ahk_eq(v, "0"):        # AHK: !PartsSet0i or (=0) -> "00"
                v = "00"
            if len(v) == 2:                       # keep the low nibble (2nd char)
                v = v[1]
            nib[i] = v
        parts_a = nib[1] + nib[2] + nib[3] + nib[4]
        parts_b = nib[5] + nib[6] + "0" + nib[7]
        if not _ahk_eq(merged.get("RescRepFoundMarkOnly01", "0"), "1"):
            synth["PartsSetA"] = [(parts_a, hex2dec(db.dat["PartsSetA_Offset"]))]
            synth["PartsSetB"] = [(parts_b, hex2dec(db.dat["PartsSetB_Offset"]))]
            _pl_add(pl, ["PartsSetA", "PartsSetB"], None, "After")
    # -- PartsRandom (exception_b.ahk:69-122): shuffle where parts live. Seeded
    #    (see PARTS_RANDOM_SEED) so a build is reproducible. `resc_table` (128 codes)
    #    feeds the RescRepFoundTable build below; when unset it uses the fixed
    #    RescRepPartsTable_Original. The shuffled table is itself written (concatenated,
    #    no byte-swap) at RescRepPartsTable_Offset. --
    resc_table = None
    pr01 = _ahk_eq(merged.get("PartsRandom01", "0"), "1")
    pr02 = _ahk_eq(merged.get("PartsRandom02", "0"), "1")
    if ("PartsRandom01" in pl or "PartsRandom02" in pl) and (pr01 or pr02):
        rng = random.Random(_parts_seed())
        orig = [t.strip() for t in db.dat["RescRepPartsTable_Original"].splitlines() if t.strip()]
        if pr02:                                   # Random All: shuffle every slot
            resc_table = orig[:]
            rng.shuffle(resc_table)
        else:                                      # Random ignore no-parts slots
            only = [t.strip() for t in db.dat["RescRepPartsTable_OnlyParts"].splitlines() if t.strip()]
            rng.shuffle(only)
            npidx = {int(x) for x in db.dat["RescRepParts_NoPartsIndex"].split(",") if x.strip()}
            it = iter(only)
            resc_table = ["00000000" if m in npidx else next(it) for m in range(1, 129)]
        synth["RescRepPartsTable"] = [("".join(resc_table),
                                       hex2dec(db.dat["RescRepPartsTable_Offset"]))]
        _pl_add(pl, ["RescRepPartsTable"], None, "After")
    # -- RescRepFoundTable: 128 nibbles (mark / "0"), then byte-swap pairs --
    partslife_in = any(v.startswith("PartsLifeUp") for v in pl)
    partsenergy_in = any(v.startswith("PartsEnergyUp") for v in pl)
    noitem = _ahk_eq(merged.get("RescRepFoundNoItem01", "0"), "1")
    if partsset_in or partslife_in or partsenergy_in or noitem:
        _pl_add(pl, ["RescRepFoundTable"], "NewGame", "After")   # NewGame absent -> append
        mark = values.get("RescRepFoundMark01")
        if mark is None:
            mark = _text_filter_value(db, _dat_default(db, "RescRepFoundMark01"))
        if len(mark) > 1:                         # RescRepFoundMark01 code -> low nibble
            mark = mark[1]
        part_codes = set()
        for i in range(1, 8):
            for j in range(1, 5):
                inst = f"PartsSet0{i}0{j}"
                if _ahk_eq(merged.get(inst, "0"), "1"):
                    code = db.dat.get(inst + "_Code")
                    if code:
                        part_codes.add(code.strip())
        lifeup_sel = {k for k in range(1, 9)
                      if _ahk_eq(merged.get(f"PartsLifeUp{k:02d}", "0"), "1")}
        energy_sel = {k for k in range(1, 9)
                      if _ahk_eq(merged.get(f"PartsEnergyUp{k:02d}", "0"), "1")}
        table = resc_table if resc_table is not None else [
            t.strip() for t in db.dat.get("RescRepPartsTable_Original", "").splitlines()
            if t.strip()]
        out, li, ei = [], 0, 0
        for entry in table:
            if entry in part_codes:
                out.append(mark)
            elif entry == "00000000" and noitem:
                out.append(mark)
            elif entry == "01000000":             # LifeUp slot
                li += 1
                out.append(mark if li in lifeup_sel else "0")
            elif entry == "02000000":             # EnergyUp slot
                ei += 1
                out.append(mark if ei in energy_sel else "0")
            else:
                out.append("0")
        s = "".join(out)                          # 128 nibbles
        swapped = "".join(s[k + 1] + s[k] for k in range(0, len(s) - 1, 2))
        synth["RescRepFoundTable"] = [(swapped, hex2dec(db.dat["RescRepFoundTable_Offset"]))]
    else:
        _pl_remove(pl, "RescRepFoundMark01")
        _pl_remove(pl, "RescRepFoundMarkOnly01")
        _pl_remove(pl, "RescRepFoundNoItem01")

    # Rank -> Souls: each selected CharRank0X (its byte value is the TextFilter'd
    # rank code) also writes the matching soul count Souls0X = RankSouls<rank+1>
    # (a NumHalfword table value), inserted right after the rank. (exception_b:226)
    # The soul count is the RankSouls<n> EDIT field's CURRENT value (AHK reads the
    # live var, so an edited count wins) — falling back to its _Default when unset.
    for idx in (1, 2):
        cr = f"CharRank0{idx}"
        if cr in pl:
            rank_code = values.get(cr)
            if rank_code is None:
                rank_code = _text_filter_value(db, _dat_default(db, cr))
            rank_plus = int(rank_code) + 1
            souls_src = f"RankSouls{rank_plus:02d}"
            souls_var = f"Souls0{idx}"
            souls_val = merged.get(souls_src, _dat_default(db, souls_src))
            values[souls_var] = _dec2hex_le(int(souls_val), 4)
            _pl_add(pl, [souls_var], cr, "After")

    # SubTankAdd: nibble-swap the AddFilter bitmask (exception_b.ahk:239-242).
    if "SubtankAdd" in pl and values.get("SubtankAdd"):
        v = values["SubtankAdd"]
        values["SubtankAdd"] = v[1] + v[0]

    # CharAdd - Armor Pieces (exception_b.ahk:244-266). Reads the post-AddFilter
    # group value (values["CharAdd"], e.g. "01"/"03"/"07"), the still-set individual
    # CharAdd0N raw values (merged — AddFilter clears them from the PatchList, not the
    # profile), and the TextFiltered CharStart01 code (values["CharStart01"], e.g.
    # Shadow Armor -> "02"). CharAdd01 is the always-on sentinel (universally active),
    # so the group is present for EVERY selection: for a non-New-Game selection the
    # group is "01"-only and gets removed here (net zero), which is what keeps those
    # selections byte-identical after the CreateList baseline fix.
    charadd_in = "CharAdd" in pl
    charstart_in = "CharStart01" in pl

    def _cadd(n):     # individual CharAdd0N truthy (== 1), AHK-numeric
        return _ahk_eq(merged.get(f"CharAdd0{n}", _dat_default(db, f"CharAdd0{n}")), "1")

    if charadd_in and not charstart_in:
        if values.get("CharAdd") == "01":              # only the CharAdd01 bit set
            _pl_remove(pl, "CharAdd")
    elif charadd_in or charstart_in:                   # CharStart present (±CharAdd)
        cs = values.get("CharStart01")
        sh = "F" if (_cadd(2) or cs == "02") else "0"  # Shadow Armor pieces
        bl = "F" if (_cadd(3) or cs == "03") else "0"  # Blade Armor pieces
        offs = _offsets_for_direct(db.options["ArmorParts"]["direct"], patchfile)
        synth["ArmorParts"] = [(sh + bl, hex2dec(o)) for o in offs]
        _pl_add(pl, ["ArmorParts"], None, "After")     # append ArmorParts to end
    # MenuDefaultSel01 when Falcon (CharAdd01) is turned off — the game defaults the
    # stage-select cursor to Falcon, so remember-last-selection is patched in instead.
    if not _cadd(1) and "MenuDefaultSel01" not in pl:
        _pl_add(pl, ["MenuDefaultSel01"], None, "After")

    # LifeUp / EnergyUp: scale the NumByte value (x2 + base). LifeUp base 0x20,
    # EnergyUp base 0x30. (exception_b.ahk:268-284)
    for n in ("01", "02"):
        lu = f"LifeUp{n}"
        if lu in pl and lu in values:
            values[lu] = _dec2hex(hex2dec(values[lu]) * 2 + 0x20, 2)
        eu = f"EnergyUp{n}"
        if eu in pl and eu in values:
            values[eu] = _dec2hex(hex2dec(values[eu]) * 2 + 0x30, 2)

    # New Game base: any New Game option shares a foundation ASM block. If any
    # NewGameList var appears in the list, prepend the static `NewGame` var (3 ASM
    # writes) to the front of the whole PatchList. Must run LAST in Exception_B so
    # New-Game-added vars (Souls/ArmorParts/PartsSetA/...) are already present.
    # (exception_b.ahk:288-309; AHK PatchListAdd("NewGame","0","Before").)
    if any(ng in v for v in pl for ng in db.newgame_list):
        _pl_add(pl, ["NewGame"], None, "Before")


def build_patchlist(db, merged: dict, base: dict) -> tuple[str, list[str], dict]:
    """CreateList (TotalList order) + Exception_A (base prepend + PATCHFILE + the
    ported value/combo transforms). Returns (patchfile, patchlist, synth) where
    `synth` holds writes an exception built for a synthesized var. The value
    filters, Exception_B, and PreReq/ReorderFilter run in build_writelist to keep
    the AHK pipeline order. BaseFilter is debug-only."""
    active = active_options(db, merged, base)
    # PatchList Check 1 (patch.ahk): no changed options (or only the always-on
    # CharAdd01 sentinel) -> "No changes made"; Exception_A never runs, so the
    # base list is NOT prepended and PATCHFILE stays unset.
    if not active or active == ["CharAdd01"]:
        return "", [], {}
    # PATCHFILE + base prepend (Exception_A ScriptPatch block). ScriptPatch02 in
    # the changed set selects the s02 (Localization) base xdelta3 and prepends
    # PatchList_Script; ScriptPatch03 -> s03 (defined in the engine but absent from
    # v2.6.1's data). Otherwise the b01 base. The ScriptPatchNN selectors carry no
    # writes and are dropped by VerifyFilter (no offset). Offsets for vars with a
    # _Offset_S02 variant resolve to the S02 set under s02/s03 (see _offsets_for_*).
    if "ScriptPatch02" in active:
        patchfile = "s02"
        pl = list(db.patchlist_base) + list(db.patchlist_script) + active
    elif "ScriptPatch03" in active:
        patchfile = "s03"
        pl = list(db.patchlist_base) + list(db.patchlist_script) + active
    else:
        patchfile = "b01"
        pl = list(db.patchlist_base) + active
    synth: dict = {}
    apply_exception_a(db, merged, pl, synth, patchfile)
    # PreReq/Reorder are applied by build_writelist AFTER the value filters and
    # Exception_B, matching the AHK pipeline order (patch.ahk).
    return patchfile, pl, synth


def apply_selection_filter(db, merged: dict, pl: list, synth: dict, patchfile: str) -> None:
    """Port of SelFilter (filter.ahk:394-431). A dropdown var whose value's LAST
    character is an ID with a `<var>_SELECT_<ID>` block takes that block's ASM
    payloads — the per-choice data lives INSIDE the block (a continuation block),
    not as flat `<var>_ASMnn` keys, so expand_entry would otherwise emit nothing.
    Parse the matching block's `<var>_ASMnn = hex` lines and emit them as synth
    writes at the var's ASM offsets, VarCount-style (stop at the first empty slot)."""
    for var in list(pl):
        if var in synth:
            continue
        val = str(merged.get(var, _dat_default(db, var)))
        block = db.dat.get(f"{var}_SELECT_{val[-1:]}") if val else None
        if block is None:
            continue
        prefix = f"{var}_ASM"
        asm: dict[int, str] = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith(";") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k.startswith(prefix) and k[len(prefix):].isdigit():
                asm[int(k[len(prefix):])] = v.strip().replace(" ", "")
        o = db.options.get(var) or {}
        writes: list[tuple[str, int]] = []
        slot = 1
        while slot in asm:
            if not asm[slot]:                       # VarCount-style list terminator
                break
            for off_hex in _offsets_for_slot(o.get("asm", []), slot, patchfile):
                writes.append((asm[slot], hex2dec(off_hex)))
            slot += 1
        if writes:
            synth[var] = writes                     # expand_entry returns synth[var]


def _assemble(db, merged: dict, base: dict):
    """Run the full patch pipeline and return (merged_norm, patchfile, pl, values,
    synth) — the assembled PatchList state shared by build_writelist (hex writes)
    and build_filelist (art-file inserts). Order mirrors patch.ahk: ProfileLoad
    normalization -> CreateList+Exception_A -> value filters -> AddFilter ->
    Exception_B -> PreReq -> Reorder."""
    merged = gui_control_all(db, merged)
    patchfile, pl, synth = build_patchlist(db, merged, base)
    apply_selection_filter(db, merged, pl, synth, patchfile)
    values = apply_value_filters(db, merged, pl)
    apply_add_filter(db, merged, pl, values)
    apply_exception_b(db, merged, pl, synth, values, patchfile)
    apply_prereq(db, pl)
    apply_reorder(db, pl)
    return merged, patchfile, pl, values, synth


def build_writelist(db, merged: dict, base: dict):
    """(PATCHFILE, ordered [(hexdata, offset_dec), ...]) for a merged profile.
    Order follows the assembled PatchList (matters for overlapping writes)."""
    _m, patchfile, pl, values, synth = _assemble(db, merged, base)
    writes: list[tuple[str, int]] = []
    for var in pl:
        for data, off in expand_entry(db, var, patchfile, values, synth):
            writes += ecc_split(data, off)      # split writes crossing an ECC boundary
    return patchfile, writes


def build_filelist(db, merged: dict, base: dict):
    """(PATCHFILE, [(file_var, filepath, offset_dec), ...]) — the art-file inserts
    (Title/Load screens, Mugshot custom art) for a merged profile. Port of
    FileFilter (filter.ahk:436-500): a PatchList var carrying a `_File0N_Path`
    payload expands into one insert per slot, its source resolved under
    ExtDataDir (Mugshot appends `_<OptionID>.bin`, OptionID = the var value's last
    char). apply_bin streams each file into the BIN skipping ECC trailers."""
    m, patchfile, pl, _values, _synth = _assemble(db, merged, base)
    files: list[tuple[str, str, int]] = []
    for var in pl:
        files += _file_inserts(db, var, patchfile, m)
    return patchfile, files


# --------------------------------------------------------------------------
# Pure-Python apply (no AutoHotkey) — port of patchapply.ahk. Proven byte-
# identical to the AHK engine by whole-BIN MD5 across the b01 and s02 bases.
# error_recalc.exe is a separate EDC/ECC tool (not AHK); a clean-room Python
# replacement is a follow-up. Path constants come from the run-extracted patcher.
# --------------------------------------------------------------------------
_RUN_EXTRACTED = twr.DEFAULT_RUN_EXTRACTED
XDELTA3_EXE = _RUN_EXTRACTED / "tools" / "xdelta3" / "xdelta3-3.0.11-i686.exe"
ERROR_RECALC_EXE = _RUN_EXTRACTED / "tools" / "error_recalc" / "error_recalc.exe"
BASE_PATCH_DIR = _RUN_EXTRACTED / "data" / "xdelta3"


def apply_bin(db, merged: dict, base: dict, out, *, vanilla=None,
              error_recalc: bool = True, force: bool = False) -> tuple[str, int]:
    """Build the patched BIN entirely in Python (patchapply.ahk):
      1. apply the base xdelta3 (b01/s02) to vanilla -> `out`
      2. write each WriteList entry (hex data at its absolute BIN offset; the
         WriteList is already ECC-split so writes never land in a sector trailer)
      3. recompute EDC/ECC (error_recalc.exe, in place)
    Returns (patchfile, n_writes). Raises on a no-change selection, or (unless
    force=True) if the selection changes a PARKED option the port cannot yet
    build byte-identically (coverage_gaps — Mugshot/Title file inserts and the
    unported New Game transforms). The gate makes a wrong BIN impossible rather
    than silently dropping the unported writes/files."""
    if not force:
        gaps = coverage_gaps(db, merged, base)
        if gaps:
            names = ", ".join(f"{v} ({why})" for v, why in gaps)
            raise ValueError(
                "selection changes options the pure-Python engine does not yet "
                f"cover byte-identically: {names}. Build these with the reference "
                "engine (--engine ahk) until they are ported.")
    vanilla = Path(vanilla) if vanilla else twr.DEFAULT_VANILLA
    patchfile, writes = build_writelist(db, merged, base)
    if not patchfile:
        raise ValueError("selection makes no changes vs the default profile")
    out = Path(out)
    if out.exists():
        out.unlink()
    patch = BASE_PATCH_DIR / f"{patchfile}.xdelta3"
    r = subprocess.run([str(XDELTA3_EXE), "-f", "-n", "-d", "-s", str(vanilla),
                        str(patch), str(out)], capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"xdelta3 failed ({r.returncode}): {r.stdout}{r.stderr}")
    _pf2, files = build_filelist(db, merged, base)
    with open(out, "r+b") as f:
        for data, off in writes:
            f.seek(off)
            f.write(bytes.fromhex(data.replace(" ", "")))
        for _var, filepath, off in files:
            _write_file_insert(f, filepath, off)
    if error_recalc:
        r = subprocess.run([str(ERROR_RECALC_EXE), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"error_recalc failed ({r.returncode}): "
                               f"{r.stdout}{r.stderr}")
    return patchfile, len(writes)


def _write_file_insert(f, filepath, offset: int) -> None:
    """Stream an art file into the open BIN at `offset`, skipping the 304-byte
    EDC/ECC trailer between 2048-byte data regions (port of patchapply.ahk
    114-141). The first block fills the remainder of the data sector `offset`
    lands in; subsequent blocks are full 2048-byte data regions."""
    import math
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"art-insert source missing: {filepath}")
    size = filepath.stat().st_size
    sector_mult = math.ceil((offset - _HEADER) / _SECTOR)
    datablock_next = _HEADER + _SECTOR * sector_mult
    diff = _DATA - (datablock_next - _ECC - offset)
    if diff == _SECTOR:                 # exact start-of-sector (Ceil overshoot)
        diff = 0
    with open(filepath, "rb") as src:
        f.seek(offset)
        left = size
        while left > 0:
            chunk = src.read(_DATA - diff)
            diff = 0
            if not chunk:
                break
            f.write(chunk)
            f.seek(_ECC, 1)             # skip the EDC/ECC trailer
            left -= len(chunk)


def apply_selection(selection_json: str, out, *, vanilla=None,
                    error_recalc: bool = True) -> tuple[str, int]:
    """Convenience: build the merged profile from a UI selection JSON and apply it
    to a patched BIN at `out` — the launcher's AutoHotkey-free entry point."""
    db = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
    merged = merged_profile(db, selection_json)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    return apply_bin(db, merged, base, out, vanilla=vanilla, error_recalc=error_recalc)


# --------------------------------------------------------------------------
# Art-only disc producer (disc-swap-safe: data-only, never code)
# --------------------------------------------------------------------------
def _vanilla_region_class(vanilla_path, off: int, size: int, sample: int = 512) -> str:
    """Classify an insert target in the VANILLA image as 'inplace' or 'scratch'.

    'inplace' => vanilla already holds real data at `off` (the game's loader reads
    these sectors during normal play), so overwriting them swaps the asset the game
    actually shows. 'scratch' => vanilla is zero padding here (an unused region);
    the asset is only reachable via a loader-redirect code patch, so an art-only
    disc that drops the code would leave the game reading the ORIGINAL asset from
    its native LBA. Coarse zero/non-zero probe of the first `sample` user bytes at
    `off` (the insert always begins inside a data region, so no ECC skip needed for
    a probe this small)."""
    with open(vanilla_path, "rb") as f:
        f.seek(off)
        b = f.read(min(size, sample))
    nz = sum(1 for x in b if x)
    return "inplace" if nz > len(b) * 0.10 else "scratch"


def apply_art_only(db, merged: dict, base: dict, out, *, vanilla=None,
                   error_recalc: bool = True, allow_scratch: bool = False) -> dict:
    """Produce an ART-ONLY disc image: a raw copy of the vanilla BIN with ONLY the
    selection's art file-inserts written in place, then EDC/ECC recomputed.

    It deliberately DOES NOT apply the base xdelta3 or any hex code-writes — those
    are the acediez framework's code injection, which the recompiler cannot take
    via disc-swap (it surfaces as an unknown-dispatch crash). This producer changes
    only graphics/text DATA at fixed disc offsets; SLUS + overlay code stay vanilla,
    so the stock recompiled binary mounts it and runs.

    Fail-closed on scratch: an insert whose vanilla target is a SCRATCH region
    (zero padding the vanilla loader never reads — the data is reachable only via
    the dropped loader-redirect code) is REFUSED, because writing it is theater —
    the disc looks patched but the game still reads the original asset from its
    native LBA. Pass allow_scratch=True to write it anyway (it will NOT render).

    Returns a report dict: {patchfile, inserts:[{var,off,size,src,region}],
    dropped_code_writes, scratch:[var,...]}."""
    import shutil
    vanilla = Path(vanilla) if vanilla else twr.DEFAULT_VANILLA
    out = Path(out)
    _pf, files = build_filelist(db, merged, base)
    if not files:
        raise ValueError("selection carries no art file-inserts; there is nothing "
                         "to build as an art-only disc")
    _pf2, writes = build_writelist(db, merged, base)  # reported, never applied
    report = {"patchfile": _pf, "inserts": [], "dropped_code_writes": len(writes),
              "scratch": []}
    for var, fp, off in files:
        fp = Path(fp)
        if not fp.exists():
            raise FileNotFoundError(f"art-insert source missing: {fp}")
        sz = fp.stat().st_size
        region = _vanilla_region_class(vanilla, off, sz)
        report["inserts"].append({"var": var, "off": off, "size": sz,
                                   "src": str(fp), "region": region})
        if region == "scratch":
            report["scratch"].append(var)
    if report["scratch"] and not allow_scratch:
        raise ValueError(
            "art-only refused: these inserts target vanilla SCRATCH regions that "
            "only the dropped loader-redirect code reads, so they will NOT render "
            f"on an art-only disc: {', '.join(report['scratch'])}. This asset is "
            "code-injection class (needs the guarded-variant codegen path, not "
            "disc-swap). Pass allow_scratch=True to write it anyway (won't render).")
    if out.exists():
        out.unlink()
    shutil.copyfile(vanilla, out)
    with open(out, "r+b") as f:
        for _var, fp, off in files:
            _write_file_insert(f, Path(fp), off)
    if error_recalc:
        r = subprocess.run([str(ERROR_RECALC_EXE), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"error_recalc failed ({r.returncode}): "
                               f"{r.stdout}{r.stderr}")
    return report


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
    for k, v in twr.selection_to_overrides(catalog, sel, db.options).items():
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
