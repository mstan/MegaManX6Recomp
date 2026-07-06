#!/usr/bin/env python3
"""MMX6 Tweaks resolver — port of acediez's "Mega Man X6 Tweaks" patcher engine.

Replaces the AutoHotkey GUI patcher (RHDN utility #1414, v2.6.1) with a
headless pipeline the launcher can drive:

    tickbox selection -> validated option set (PreReq/Reorder)
                      -> base xdelta3 (b01, or s02 when ScriptPatch is on)
                      -> hex writes at BIN offsets (_dat.ahk database)
                      -> error_recalc (EDC/ECC)
                      -> patched BIN + cue + extracted SLUS EXE
                      -> variant id "tweaks-<crc32(exe)>" -> game.<variant>.toml -> regen

Data sources (extracted patcher, secured under mmx6-tweaks/_patcher/):
  _src/data/_dat.ahk       option hex database:  Var_ASMnn / Var_ASMnn_Offset,
                           direct Var / Var_Offset writes, Var_Default,
                           Filenn / Filenn_Offset asset insertions
  _src/data/_dat_init.ahk  GeneralList (catalog), PreReqList, ReorderList,
                           PatchList_Base / PatchList_Script, value filters
  _src/_gui/gui.ahk        tickbox tree labels/grouping (for the RmlUi tab)

Attribution: all option research and patch payloads are acediez's work.
This tool only re-implements the *applicator* so selections integrate with
the recompiler's variant pipeline. Payload data is never redistributed —
users supply the patcher archive; we read its data files in place.

Current state: PARSE + CATALOG complete (list/audit/deps).  APPLY pipeline
is scaffolded but intentionally refuses to run until validated against the
standalone [Tweaks+Loc+Art v2.6].xdelta output byte-for-byte (see TODO in
apply_selection).
"""

from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from collections import OrderedDict, defaultdict
from pathlib import Path

# Project root = parent of tools/ (this file lives in <root>/tools/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The user-supplied, extracted patcher tree. Local-only (mmx6-tweaks/ is not
# tracked); the resolver reads acediez's engine + payloads in place.
DEFAULT_PATCHER_BASE = PROJECT_ROOT / "mmx6-tweaks" / "_patcher"
DEFAULT_PATCHER_SRC = (
    DEFAULT_PATCHER_BASE / "src_extracted"
    / "Mega Man X6 Tweaks Patcher (v2.6.1)" / "_src"
)
DEFAULT_RUN_EXTRACTED = DEFAULT_PATCHER_BASE / "run_extracted"
DEFAULT_VANILLA = PROJECT_ROOT / "mmx6-tweaks" / "Mega Man X6 (USA) (v1.1).bin"
VANILLA_MD5 = "237b6feddd1a88e86ab1cddc8822f03f"

# The tracked headless driver (copied into the patcher _src at apply time so its
# relative #Include lines resolve). See tools/tweaks/_headless.ahk.
HEADLESS_DRIVER = PROJECT_ROOT / "tools" / "tweaks" / "_headless.ahk"

# Baseline profile (all option vars at their GUI defaults) — selections overlay it.
DEFAULT_PROFILE = DEFAULT_RUN_EXTRACTED / "profiles" / "default.x6tweaksprofile"

# The SLUS boot EXE inside the disc image (ISO9660 name; ';1' stripped).
SLUS_NAME = "SLUS_013.95"
# ISO extractor: prefer the tracked copy under tools/tweaks/, fall back to the
# lab copy that ships with the extracted patcher.
_ISO_TRACKED = PROJECT_ROOT / "tools" / "tweaks" / "iso_extract.py"
ISO_EXTRACT = _ISO_TRACKED if _ISO_TRACKED.exists() else (DEFAULT_PATCHER_BASE / "iso_extract.py")

PRESET_PROFILES = {"default", "tweaks", "tweaks_l", "tweaks_l_c"}

# --------------------------------------------------------------------------
# AHK data parsing
# --------------------------------------------------------------------------

_ASSIGN_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")
_BLOCK_VAR_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*$")


def _strip_comment(line: str) -> str:
    """Drop AHK ';' comments (not inside quotes — the data files never quote ';')."""
    out = []
    for ch in line:
        if ch == ";":
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_ahk_assignments(path: Path) -> "OrderedDict[str, str]":
    """Parse flat `Name = value` assignments plus `Name =\\n( ... )` blocks.

    Returns raw string values; block values keep internal newlines. /* */
    comment blocks and ';' line comments are ignored.
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    # strip /* ... */ blocks
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    result: "OrderedDict[str, str]" = OrderedDict()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i])
        if not line.strip():
            i += 1
            continue
        m = _BLOCK_VAR_RE.match(line)
        # Continuation block: `Var =` then `(` ... `)`. Comment/blank lines may
        # sit between the assignment and the `(` (PreReqList does this).
        block_open = 0
        if m:
            j = i + 1
            while j < len(lines):
                nxt = _strip_comment(lines[j]).strip()
                if nxt.startswith("("):
                    block_open = j
                    break
                if nxt:  # real content that isn't '(' — not a block
                    break
                j += 1
        if m and block_open:
            name = m.group(1)
            i = block_open + 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith(")"):
                bl = _strip_comment(lines[i]).strip()
                if bl:
                    block.append(bl)
                i += 1
            result[name] = "\n".join(block)
            i += 1
            continue
        m = _ASSIGN_RE.match(line)
        if m:
            name, val = m.group(1), m.group(2)
            # `TotalList := ...` style expressions are skipped (derived)
            if not name.endswith(":") and not val.startswith("="):
                result[name] = val.strip().strip('"')
        i += 1
    return result


# --------------------------------------------------------------------------
# Database model
# --------------------------------------------------------------------------

class TweaksDB:
    """The full option database: payloads, catalog, dependencies, filters."""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.dat = parse_ahk_assignments(src_dir / "data" / "_dat.ahk")
        self.init = parse_ahk_assignments(src_dir / "data" / "_dat_init.ahk")

        self.general_list = self._lines("GeneralList")
        self.patchlist_base = self._lines("PatchList_Base")
        self.patchlist_script = self._lines("PatchList_Script")
        self.text_filter_vars = set(self._lines("TextFilterList"))
        self.num_word_vars = set(self._lines("NumWordFilterList"))
        self.num_half_vars = set(self._lines("NumHalfwordFilterList"))
        self.num_byte_vars = set(self._lines("NumByteFilterList"))
        self.add_vars = set(self._lines("AddList"))
        self.newgame_list = self._lines("NewGameList")

        self.text_filter_table = self._parse_text_filter()
        self.prereq = self._parse_pairs("PreReqList")     # dependant -> [deps]
        self.reorder = self._parse_pairs("ReorderList")   # dependency -> [dependants]

        self.options = self._build_options()

    # -- raw list helpers ---------------------------------------------------
    def _lines(self, key: str) -> list[str]:
        raw = self.init.get(key, "")
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]

    def _parse_text_filter(self) -> dict[str, str]:
        table = {}
        for ln in self._lines("TextFilterTable"):
            if "=" in ln:
                k, v = ln.rsplit("=", 1)
                table[k.strip().strip('"')] = v.strip()
        return table

    def _parse_pairs(self, key: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for ln in self._lines(key):
            if ":" not in ln:
                continue
            lhs, rhs = ln.split(":", 1)
            out[lhs.strip()].extend(x.strip() for x in rhs.split(",") if x.strip())
        return dict(out)

    # -- option payload assembly ---------------------------------------------
    def _build_options(self) -> "OrderedDict[str, dict]":
        """Group _dat.ahk keys into per-option payload records.

        An *option instance* is e.g. ArmorByPart01 (a GeneralList var-set name
        plus a 2-digit choice suffix) or a base/injected var like ShadowBase01.
        Each carries: asm writes [(seq, hex, offset_hex, offset_variant)],
        direct writes, file insertions, and its GUI default.
        """
        opts: "OrderedDict[str, dict]" = OrderedDict()

        def opt(name: str) -> dict:
            if name not in opts:
                opts[name] = {
                    "asm": [],       # (slot, hexbytes, offset, offset_set)
                    "direct": [],    # (value, offset, offset_set)
                    "files": [],     # (slot, filename, offset, offset_set)
                    "default": None,
                }
            return opts[name]

        asm_re = re.compile(r"^(.*?)_ASM(\d+)$")
        asm_off_re = re.compile(r"^(.*?)_ASM(\d+)_Offset(\d*)(?:_(B01|S02))?$")
        file_re = re.compile(r"^(.*?)_File(\d+)$")
        file_off_re = re.compile(r"^(.*?)_File(\d+)_Offset(\d*)(?:_(B01|S02))?$")
        direct_off_re = re.compile(r"^(.*?)_Offset(\d*)(?:_(B01|S02))?$")

        for key, val in self.dat.items():
            m = asm_off_re.match(key)
            if m:
                opt(m.group(1))["asm"].append(
                    {"slot": int(m.group(2)), "kind": "offset",
                     "offset": val, "set": m.group(4) or "COMMON",
                     "nth": int(m.group(3) or 1)})
                continue
            m = asm_re.match(key)
            if m:
                opt(m.group(1))["asm"].append(
                    {"slot": int(m.group(2)), "kind": "bytes", "hex": val})
                continue
            m = file_off_re.match(key)
            if m:
                opt(m.group(1))["files"].append(
                    {"slot": int(m.group(2)), "kind": "offset",
                     "offset": val, "set": m.group(4) or "COMMON",
                     "nth": int(m.group(3) or 1)})
                continue
            m = file_re.match(key)
            if m:
                opt(m.group(1))["files"].append(
                    {"slot": int(m.group(2)), "kind": "name", "file": val})
                continue
            if key.endswith("_Default"):
                opt(key[: -len("_Default")])["default"] = val
                continue
            m = direct_off_re.match(key)
            if m and not key.endswith("_Default"):
                opt(m.group(1))["direct"].append(
                    {"kind": "offset", "offset": val,
                     "set": m.group(3) or "COMMON", "nth": int(m.group(2) or 1)})
                continue
            # bare `Var = value` (direct value; pairs with Var_Offset)
            opt(key)["direct"].append({"kind": "value", "value": val})

        return opts

    # -- queries --------------------------------------------------------------
    def instances_of(self, varset: str) -> list[str]:
        """Choice instances for a GeneralList var-set (ArmorByPart -> [ArmorByPart01, ...])."""
        pat = re.compile(re.escape(varset) + r"\d{2}$")
        return [k for k in self.options if pat.match(k)]

    def resolve_dependencies(self, selection: list[str]) -> list[str]:
        """Closure of PreReq dependencies over a selection, in stable order."""
        needed: list[str] = []
        seen: set[str] = set()

        def add(name: str):
            if name in seen:
                return
            for dep in self.prereq.get(name, []):
                add(dep)
            seen.add(name)
            needed.append(name)

        for s in selection:
            add(s)
        return needed

    def write_order(self, selection: list[str]) -> list[str]:
        """Apply ReorderList: every dependency writes before its dependants."""
        order = list(selection)
        for dependency, dependants in self.reorder.items():
            if dependency not in order:
                continue
            di = order.index(dependency)
            for d in dependants:
                if d in order and order.index(d) < di:
                    order.remove(dependency)
                    order.insert(order.index(d), dependency)
                    di = order.index(dependency)
        return order


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# GUI catalog (parse _gui/gui.ahk into the launcher's tickbox tree)
# --------------------------------------------------------------------------
#
# gui.ahk is a hand-laid AHK GUI: 8 tabs, each a block after `Gui, Main:Tab, N`.
# Section headers are Text controls emitted while font is %f1% (section) or %f2%
# (subsection). Interactive options are Add lines of type Checkbox / Radio /
# DropDownList / Edit / Slider carrying a `v<Var>` token. See the structural
# spec this parser was written against (tab order is physical 1,2,3,8,4,5,6,7).

GUI_TAB_TITLES = {
    1: "General Tweaks", 2: "Player Mechanics", 3: "Balance",
    4: "New Game Status", 5: "Localization + Custom Art", 6: "Stages",
    7: "Damage Tables", 8: "Boss Attacks",
}
_OPTION_TYPES = {"checkbox", "radio", "droplist", "dropdownlist", "edit", "slider", "combobox"}
_TYPE_NORM = {"dropdownlist": "dropdownlist", "droplist": "dropdownlist",
              "combobox": "dropdownlist"}


def _strip_ahk_comments(text: str) -> list[str]:
    """Drop /* */ line-anchored blocks, full-line ; comments, and trailing ' ;'."""
    text = re.sub(r"(?ms)^[ \t]*/\*.*?^[ \t]*\*/[ \t]*$", "", text)
    out = []
    for ln in text.splitlines():
        s = ln.lstrip()
        if s.startswith(";"):
            out.append("")
            continue
        # trailing ' ;' comment (AHK: ';' preceded by whitespace)
        m = re.search(r"\s;", ln)
        if m:
            ln = ln[:m.start()]
        out.append(ln)
    return out


def _ahk_add_match(line: str):
    """Return (type, opts, text) for a `Gui, Main:Add, Type, opts[, text]` line."""
    m = re.match(r"\s*Gui,\s*Main:Add,\s*(\w+)\s*,\s*(.*)$", line, re.I)
    if not m:
        return None
    ctype = m.group(1).lower()
    rest = m.group(2)
    opts, _, text = rest.partition(",")
    return ctype, opts.strip(), text.strip()


def _var_of(opts: str) -> str | None:
    m = re.search(r"(?:^|\s)v([A-Za-z_]\w*)", opts)
    return m.group(1) if m else None


def _ddl_choices(text: str):
    """(choices, default) from an AHK DropDownList item string ('a||b|c'). The
    item before the first '||' (empty split) is the default. Items are kept RAW
    (quotes included where present) because the profile stores the exact item
    string (e.g. `"RESCUED"` vs `Lv. 1`); a UI may strip quotes for display.
    Returns (None,%Var%) when the list is a dynamic %Var% reference."""
    t = text.strip()
    if t.startswith("%") and t.endswith("%"):
        return None, t.strip("%")
    default = None
    if "||" in t:
        default = t.split("||", 1)[0].split("|")[-1].strip()
    items = [p.strip() for p in t.split("|") if p.strip()]
    return items, default


def parse_gui_catalog(src_dir: Path, db: "TweaksDB") -> list[dict]:
    """Parse gui.ahk into an ordered option catalog grouped by tab & section."""
    gui = src_dir / "_gui" / "gui.ahk"
    lines = _strip_ahk_comments(gui.read_text(encoding="utf-8-sig", errors="replace"))

    cur_tab = None
    font = None            # 'section' | 'subsection' | None
    section = subsection = None
    last_label = None      # nearest preceding Text (labels numeric inputs)
    radio_group = 0
    prev_was_radio = False
    opts_out: list[dict] = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue

        mf = re.match(r"\s*Gui,\s*Main:Font(?:,\s*(.*))?$", line, re.I)
        if mf:
            arg = (mf.group(1) or "").strip()
            if arg in ("%f1%", "s10") or arg.startswith("%f1%"):
                font = "section"
            elif arg in ("%f2%", "Underline") or arg.startswith("%f2%"):
                font = "subsection"
            elif arg == "":
                font = None
            else:
                font = None  # cosmetic (colors, sizes)
            continue

        mt = re.match(r"\s*Gui,\s*Main:Tab,\s*(\d+)", line, re.I)
        if mt:
            cur_tab = int(mt.group(1))
            section = subsection = None
            prev_was_radio = False
            continue

        add = _ahk_add_match(line)
        if not add:
            continue
        ctype, opts, text = add

        if ctype == "text":
            if font == "section":
                section, subsection = text.strip(), None
            elif font == "subsection":
                subsection = text.strip()
            else:
                last_label = text.strip()
            prev_was_radio = False
            continue

        if ctype not in _OPTION_TYPES:
            prev_was_radio = False
            continue

        var = _var_of(opts)
        if not var:
            prev_was_radio = False
            continue

        ntype = _TYPE_NORM.get(ctype, ctype)
        rec = {"tab": cur_tab, "tab_title": GUI_TAB_TITLES.get(cur_tab, str(cur_tab)),
               "section": section, "subsection": subsection,
               "type": ntype, "var": var}

        if ntype in ("checkbox", "radio"):
            rec["label"] = text.strip()
            rec["default_on"] = bool(re.search(r"(?:^|\s)Checked(?:\s|$)", opts, re.I))
            if ntype == "radio":
                if not prev_was_radio:
                    radio_group += 1
                rec["group"] = radio_group
        elif ntype == "dropdownlist":
            rec["label"] = last_label
            choices, default = _ddl_choices(text)
            rec["choices"] = choices
            rec["default"] = default
        else:  # edit / slider (numeric)
            rec["label"] = last_label
            # default / range are usually %Var_Default% / %Var_Range% -> _dat.ahk
            dv = db.dat.get(var + "_Default")
            rec["default"] = dv if dv is not None else (text.strip() or None)
            rng = db.dat.get(var + "_Range")
            if rng:
                rec["range"] = rng

        opts_out.append(rec)
        prev_was_radio = (ntype == "radio")

    return opts_out


def cmd_catalog(db: TweaksDB, args) -> int:
    cat = parse_gui_catalog(Path(args.patcher_src), db)
    if args.json:
        print(json.dumps(cat, indent=2))
        return 0
    # human summary
    by_tab: dict = OrderedDict()
    for o in cat:
        by_tab.setdefault(o["tab"], []).append(o)
    print(f"# GUI catalog: {len(cat)} interactive options across {len(by_tab)} tabs")
    for tab in sorted(by_tab):
        opts = by_tab[tab]
        print(f"\n=== Tab {tab}: {GUI_TAB_TITLES.get(tab, tab)} ({len(opts)} options) ===")
        cur = None
        for o in opts:
            sec = f"{o['section'] or ''}" + (f" › {o['subsection']}" if o['subsection'] else "")
            if sec != cur:
                print(f"  [{sec}]")
                cur = sec
            extra = ""
            if o["type"] == "dropdownlist" and o.get("choices"):
                extra = f"  choices={o['choices']} default={o.get('default')}"
            elif o["type"] in ("checkbox", "radio"):
                extra = "  (on)" if o.get("default_on") else ""
                if o["type"] == "radio":
                    extra += f"  grp={o.get('group')}"
            elif o.get("default") is not None:
                extra = f"  default={o.get('default')}"
            print(f"    {o['type']:12s} {o['var']:26s} {o.get('label') or ''}{extra}")
    return 0


def cmd_list(db: TweaksDB, args) -> int:
    print(f"# MMX6 Tweaks catalog ({len(db.general_list)} var-sets, "
          f"{len(db.options)} payload records)")
    for varset in db.general_list:
        inst = db.instances_of(varset)
        if not inst:
            print(f"{varset:32s}  (no payload records — GUI-only/derived)")
            continue
        marks = []
        for i in inst:
            o = db.options[i]
            n_writes = len([a for a in o["asm"] if a.get("kind") == "bytes"]) \
                + len([d for d in o["direct"] if d.get("kind") == "value"]) \
                + len([f for f in o["files"] if f.get("kind") == "name"])
            d = f" default={o['default']}" if o["default"] is not None else ""
            deps = db.prereq.get(i)
            dd = f" needs={','.join(deps)}" if deps else ""
            marks.append(f"  {i:36s} writes={n_writes}{d}{dd}")
        print(f"{varset}")
        print("\n".join(marks))
    return 0


def cmd_audit(db: TweaksDB, args) -> int:
    total_bytes = 0
    offset_sets = defaultdict(int)
    no_offset = []
    for name, o in db.options.items():
        for a in o["asm"]:
            if a.get("kind") == "bytes":
                total_bytes += len(a["hex"]) // 2
            else:
                offset_sets[a["set"]] += 1
        for d in o["direct"]:
            if d.get("kind") == "offset":
                offset_sets[d["set"]] += 1
        bytes_slots = {a["slot"] for a in o["asm"] if a.get("kind") == "bytes"}
        off_slots = {a["slot"] for a in o["asm"] if a.get("kind") == "offset"}
        if bytes_slots - off_slots:
            no_offset.append((name, sorted(bytes_slots - off_slots)))
    print(json.dumps({
        "payload_records": len(db.options),
        "general_varsets": len(db.general_list),
        "base_patchlist": db.patchlist_base,
        "script_patchlist": db.patchlist_script,
        "prereq_edges": sum(len(v) for v in db.prereq.values()),
        "reorder_edges": sum(len(v) for v in db.reorder.values()),
        "total_asm_payload_bytes": total_bytes,
        "offset_records_by_set": dict(offset_sets),
        "asm_slots_missing_offset": no_offset[:20],
    }, indent=2))
    return 0


def cmd_deps(db: TweaksDB, args) -> int:
    sel = args.select.split(",") if args.select else []
    closure = db.resolve_dependencies(sel)
    ordered = db.write_order(closure)
    print("selection :", sel)
    print("closure   :", closure)
    print("write order:", ordered)
    return 0


# --------------------------------------------------------------------------
# Profile generation (UI selection -> .x6tweaksprofile)
# --------------------------------------------------------------------------
#
# A .x6tweaksprofile is `VarName=value` for every option var (the GUI's VarList).
# The shipped default profile is the baseline (all vars at their defaults); an
# arbitrary selection = default profile with the user's changed vars overridden.
# Value encoding (from the shipped profiles): checkbox/radio = 0|1 (one 1 per
# radio group), dropdown = the exact item string (quoted iff quoted in gui.ahk,
# e.g. "RESCUED" vs D vs Lv. 1), edit/slider = the number.

def load_profile(path: Path) -> "OrderedDict[str,str]":
    od: "OrderedDict[str,str]" = OrderedDict()
    for ln in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if "=" in ln and not ln.lstrip().startswith(";"):
            k, _, v = ln.partition("=")
            od[k.strip()] = v.strip()
    return od


def emit_profile(od: "OrderedDict[str,str]") -> str:
    return "\n".join(f"{k}={v}" for k, v in od.items())


def generate_profile(base: Path, overrides: dict) -> str:
    """default profile + {var: value} overrides -> profile text (ProfileLoad reads
    lines order-independently, so emit order is irrelevant to the apply)."""
    od = load_profile(base)
    for k, v in overrides.items():
        od[str(k)] = str(v)
    return emit_profile(od)


def selection_to_overrides(catalog: list[dict], selection: dict) -> dict:
    """Translate a UI selection into profile var overrides.

    selection maps an option var -> the user's chosen value in UI terms:
      checkbox -> bool/0/1;  radio -> the chosen radio var (sets it 1, its
      group siblings 0);  dropdown -> the chosen item string;  edit/slider ->
      number. Only options present in `selection` are changed; everything else
      stays at the base profile's default.
    """
    by_var = {o["var"]: o for o in catalog}
    # radio groups: (tab, group) -> [vars]
    groups: dict = defaultdict(list)
    for o in catalog:
        if o["type"] == "radio":
            groups[(o["tab"], o.get("group"))].append(o["var"])

    ov: dict = {}
    for var, val in selection.items():
        o = by_var.get(var)
        if o is None:
            ov[var] = val            # pass-through (caller knows what it's doing)
            continue
        t = o["type"]
        if t == "checkbox":
            ov[var] = "1" if (val in (True, 1, "1", "on", "true")) else "0"
        elif t == "radio":
            # `val` truthy => this radio is the selected one in its group.
            if val in (True, 1, "1", "on", "true"):
                for sib in groups[(o["tab"], o.get("group"))]:
                    ov[sib] = "0"
                ov[var] = "1"
        elif t == "dropdownlist":
            ov[var] = str(val)       # exact item string (with quotes if quoted)
        else:                         # edit / slider
            ov[var] = str(val)
    return ov


# --------------------------------------------------------------------------
# APPLY pipeline
# --------------------------------------------------------------------------
#
# Rather than re-derive acediez's ~2000-line exception-heavy AHK applicator in
# Python (a byte-for-byte debug loop with permanent divergence risk), we drive
# his ACTUAL engine headlessly via AutoHotkey (tools/tweaks/_headless.ahk). It
# is byte-identical by construction and covers arbitrary selections, not just
# the shipped presets. Proven byte-identical (MD5) against all three v2.6
# standalone patches, incl. the maximal mugshot-assembly + art-file-insert path.
#
# Pipeline:  profile -> [engine: base xdelta3 + hex writes + error_recalc]
#                    -> patched BIN -> extract SLUS -> crc32 -> variant id
#                    -> stage variants/<id>/{rom/SLUS, disc.bin, disc.cue}
#                    -> emit game.<id>.toml  -> (optional) regen

# Path forms differ by Python flavor. A NATIVE Windows python (mingw / python.org)
# execs Windows paths and str(Path) is already Windows-form. An msys2/cygwin
# python execs POSIX paths. Either way the NATIVE AutoHotkey exe needs its file
# ARGS in Windows form. Detect the flavor and convert only when needed (cygpath
# is available under msys/cygwin; under native python no conversion is needed, so
# cygpath's absence there never matters).
IS_WIN_NATIVE = (sys.platform == "win32")


def _cygpath(mode: str, p) -> str:
    try:
        r = subprocess.run(["cygpath", mode, str(p)],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    return str(p)


def _exec(p) -> str:
    """Path form to exec (argv[0]) under the running Python."""
    return str(p) if IS_WIN_NATIVE else _cygpath("-u", p)


def _win(p) -> str:
    """Windows-form path for the native AutoHotkey / tool exes' args."""
    return str(p) if IS_WIN_NATIVE else _cygpath("-w", p)


def _from_win(s: str) -> Path:
    """A Windows path string (from AutoHotkey) -> Path usable by this Python."""
    return Path(s) if IS_WIN_NATIVE else Path(_cygpath("-u", s))


def find_autohotkey(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    candidates = [
        r"C:\Program Files\AutoHotkey\v1.1.37.02\AutoHotkeyU64.exe",
        r"C:\Program Files\AutoHotkey\AutoHotkeyU64.exe",
        r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
        r"C:\Program Files (x86)\AutoHotkey\AutoHotkeyU64.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    # any v1.1.* dir
    base = Path(r"C:\Program Files\AutoHotkey")
    if base.exists():
        for d in sorted(base.glob("v1.1.*"), reverse=True):
            for exe in ("AutoHotkeyU64.exe", "AutoHotkeyU32.exe"):
                if (d / exe).exists():
                    return d / exe
    return None


def _md5(path: Path) -> str:
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hardlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)           # instant on same NTFS volume
    except OSError:
        shutil.copy2(src, dst)


def run_engine(profile: str, vanilla: Path, work_dir: Path,
               src_dir: Path, run_extracted: Path, ahk: Path,
               dry_run: bool = False) -> Path:
    """Drive acediez's engine headlessly; return the produced BIN path.

    Output lands next to the input (the engine derives OutputDir from InputDir),
    so we run against a hardlinked vanilla inside work_dir.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    staged_vanilla = work_dir / "Mega Man X6 (USA) (v1.1).bin"
    _hardlink_or_copy(vanilla, staged_vanilla)
    # clear stale outputs
    for f in work_dir.glob("Mega Man X6 (USA) (v1.1) [Tweaks*"):
        f.unlink()

    driver = src_dir / "_headless.ahk"
    shutil.copy2(HEADLESS_DRIVER, driver)      # tracked driver -> in-place _src

    result_file = work_dir / "_apply_result.txt"
    if result_file.exists():
        result_file.unlink()

    # exec form for THIS python + Windows-form args (the native AHK parses them).
    # A profile PATH must be Windows-form for the native AHK; a preset name passes through.
    prof_arg = profile if profile in PRESET_PROFILES else _win(profile)
    env = dict(os.environ, MSYS2_ARG_CONV_EXCL="*")
    cmd = [_exec(ahk), _win(driver), prof_arg, _win(staged_vanilla),
           _win(result_file), _win(run_extracted)]
    if dry_run:
        cmd.append("nowrite")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if not result_file.exists():
        trace = src_dir / "_headless_trace.log"
        raise RuntimeError(
            f"engine failed (exit {proc.returncode}): {proc.stdout}{proc.stderr}\n"
            f"trace: {trace.read_text() if trace.exists() else '(none)'}")
    out = _from_win(result_file.read_text(encoding="utf-8-sig").strip())
    if not out.exists():
        raise RuntimeError(f"engine reported {out} but it does not exist")
    return out


def extract_slus(bin_path: Path, out_path: Path) -> bytes:
    """Extract the SLUS boot EXE from the patched disc image; return its bytes."""
    proc = subprocess.run(
        [sys.executable, str(ISO_EXTRACT), str(bin_path), SLUS_NAME, str(out_path)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"iso_extract failed: {proc.stdout}{proc.stderr}")
    return out_path.read_bytes()


def variant_id_for(slus_bytes: bytes) -> str:
    return "tweaks-%08x" % (zlib.crc32(slus_bytes) & 0xFFFFFFFF)


def emit_variant_toml(template: Path, out_toml: Path, variant: str,
                      exe_rel: str, disc_rel: str) -> None:
    """Derive game.<variant>.toml from game.tweaks.toml, repointing the variant
    identity + inputs + output dir, and de-absolutizing the overlay cmd."""
    text = template.read_text(encoding="utf-8")
    text = re.sub(r'^(\s*variant\s*=\s*")[^"]*(")',
                  rf'\g<1>{variant}\g<2>', text, count=1, flags=re.M)
    text = re.sub(r'^(\s*exe\s*=\s*")[^"]*(")',
                  rf'\g<1>{exe_rel}\g<2>', text, count=1, flags=re.M)
    text = re.sub(r'^(\s*disc\s*=\s*")[^"]*(")',
                  rf'\g<1>{disc_rel}\g<2>', text, count=1, flags=re.M)
    text = re.sub(r'^(\s*out_dir\s*=\s*")[^"]*(")',
                  rf'\g<1>generated-{variant}\g<2>', text, count=1, flags=re.M)
    # De-absolutize the overlay autocompile command onto the psxrecomp-v4 junction
    # so a variant toml is worktree-portable (issue #5 in the running log).
    text = text.replace("F:/Projects/psxrecomp/psxrecomp/", "psxrecomp-v4/")
    text = text.replace("--game-toml game.toml", f"--game-toml {out_toml.name}")
    out_toml.write_text(text, encoding="utf-8")


def cmd_apply(db: TweaksDB, args) -> int:
    # --- resolve the profile: a preset name, a .x6tweaksprofile file, or a UI
    #     selection JSON ({var: value}) turned into a generated profile --------
    work_dir = Path(args.work_dir) if args.work_dir else (DEFAULT_PATCHER_BASE / "_worktmp")
    if args.selection:
        base = Path(args.base_profile) if args.base_profile else DEFAULT_PROFILE
        if not base.exists():
            print(f"apply: base profile not found: {base} (needed for --selection)",
                  file=sys.stderr)
            return 2
        sel_path = Path(args.selection)
        try:
            selection = json.loads(sel_path.read_text() if sel_path.exists() else args.selection)
        except (OSError, json.JSONDecodeError) as e:
            print(f"apply: --selection must be a JSON object or a path to one: {e}",
                  file=sys.stderr)
            return 2
        catalog = parse_gui_catalog(Path(args.patcher_src), db)
        overrides = selection_to_overrides(catalog, selection)
        work_dir.mkdir(parents=True, exist_ok=True)
        gen = work_dir / "_selection.x6tweaksprofile"
        gen.write_text(generate_profile(base, overrides), encoding="utf-8")
        profile = str(gen)
        print(f"[apply] selection: {len(selection)} options -> {len(overrides)} "
              f"var overrides -> {gen.name}")
    elif args.profile in PRESET_PROFILES:
        profile = args.profile
    elif args.profile and Path(args.profile).exists():
        profile = str(Path(args.profile).resolve())
    else:
        print(f"apply: need --selection <json>, or --profile as a preset "
              f"{sorted(PRESET_PROFILES)} or a .x6tweaksprofile path "
              f"(got {args.profile!r})", file=sys.stderr)
        return 2

    vanilla = Path(args.vanilla) if args.vanilla else DEFAULT_VANILLA
    if not vanilla.exists():
        print(f"apply: vanilla BIN not found: {vanilla}", file=sys.stderr)
        return 2
    if not args.skip_md5_check:
        got = _md5(vanilla)
        if got != VANILLA_MD5:
            print(f"apply: vanilla MD5 mismatch: got {got}, need {VANILLA_MD5}\n"
                  f"       (need the REDUMP 'Mega Man X6 (USA) (v1.1).bin'; "
                  f"pass --skip-md5-check to override)", file=sys.stderr)
            return 2

    src_dir = Path(args.patcher_src)
    run_extracted = Path(args.run_extracted) if args.run_extracted else DEFAULT_RUN_EXTRACTED
    for label, p in [("patcher _src", src_dir), ("run_extracted", run_extracted),
                     ("iso_extract.py", ISO_EXTRACT), ("headless driver", HEADLESS_DRIVER)]:
        if not p.exists():
            print(f"apply: {label} not found: {p}", file=sys.stderr)
            return 2

    ahk = find_autohotkey(args.ahk)
    if ahk is None:
        print("apply: AutoHotkey v1.1 not found (needed to drive the patcher "
              "engine). Install AutoHotkey 1.1 or pass --ahk <path>.",
              file=sys.stderr)
        return 2

    # --- 1. drive the engine ---------------------------------------------
    print(f"[apply] engine via {ahk.name}")
    patched = run_engine(profile, vanilla, work_dir, src_dir, run_extracted, ahk)
    print(f"[apply] patched BIN: {patched} ({patched.stat().st_size} bytes)")

    # --- 2. extract SLUS + variant id ------------------------------------
    slus_tmp = work_dir / "SLUS_013.95"
    slus_bytes = extract_slus(patched, slus_tmp)
    variant = variant_id_for(slus_bytes)
    print(f"[apply] SLUS {len(slus_bytes)} bytes -> variant id {variant}")

    # --- 3. stage variants/<id>/ -----------------------------------------
    staging = Path(args.staging) if args.staging else (
        PROJECT_ROOT / "mmx6-tweaks" / "variants" / variant)
    (staging / "rom").mkdir(parents=True, exist_ok=True)
    disc_base = f"Mega Man X6 (USA) (v1.1) [{variant}]"
    disc_bin = staging / f"{disc_base}.bin"
    disc_cue = staging / f"{disc_base}.cue"
    slus_dst = staging / "rom" / SLUS_NAME

    shutil.move(str(patched), str(disc_bin))
    disc_cue.write_text(
        f'FILE "{disc_base}.bin" BINARY\n'
        f"  TRACK 01 MODE2/2352\n"
        f"    INDEX 01 00:00:00\n", encoding="utf-8")
    shutil.move(str(slus_tmp), str(slus_dst))
    # drop the engine's own .cue (references the build-dated name)
    for stray in work_dir.glob("Mega Man X6 (USA) (v1.1) [Tweaks*.cue"):
        stray.unlink()
    print(f"[apply] staged: {staging}")

    # --- 4. emit game.<variant>.toml -------------------------------------
    exe_rel = f"mmx6-tweaks/variants/{variant}/rom/{SLUS_NAME}"
    disc_rel = f"mmx6-tweaks/variants/{variant}/{disc_base}.cue"
    out_toml = PROJECT_ROOT / f"game.{variant}.toml"
    if args.emit_toml:
        template = PROJECT_ROOT / "game.tweaks.toml"
        if not template.exists():
            print(f"apply: template {template} missing; skipping toml emit",
                  file=sys.stderr)
        else:
            emit_variant_toml(template, out_toml, variant, exe_rel, disc_rel)
            print(f"[apply] wrote {out_toml.name}")

    # --- 5. optional regen -----------------------------------------------
    if args.regen:
        recompiler = Path(args.recompiler) if args.recompiler else (
            PROJECT_ROOT / "psxrecomp-v4" / "recompiler" / "build" / "psxrecomp-game.exe")
        if not recompiler.exists():
            print(f"apply: recompiler not found: {recompiler} (skipping regen)",
                  file=sys.stderr)
        else:
            print(f"[apply] regen: {recompiler.name} --config {out_toml.name}")
            rc = subprocess.run([str(recompiler), "--config", str(out_toml)],
                                cwd=str(PROJECT_ROOT))
            if rc.returncode != 0:
                print(f"apply: regen failed (exit {rc.returncode})", file=sys.stderr)
                return 1

    print(f"\n[apply] done. variant={variant}")
    print(f"        toml : game.{variant}.toml")
    print(f"        disc : {disc_rel}")
    print(f"        exe  : {exe_rel}")
    if not args.regen:
        print(f"        next : regen with  psxrecomp-game.exe --config game.{variant}.toml")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--patcher-src", type=Path, default=DEFAULT_PATCHER_SRC,
                    help="path to the extracted patcher _src dir")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="print the option catalog")
    sub.add_parser("audit", help="database coverage statistics")
    p = sub.add_parser("catalog", help="parse gui.ahk into the tickbox tree")
    p.add_argument("--json", action="store_true", help="emit JSON for the launcher")
    p = sub.add_parser("deps", help="dependency closure + write order")
    p.add_argument("--select", default="", help="comma-separated option instances")

    p = sub.add_parser(
        "apply",
        help="produce a patched BIN + variant toml by driving acediez's engine")
    p.add_argument("--profile", default="",
                   help="preset (default|tweaks|tweaks_l|tweaks_l_c) or a "
                        "path to a .x6tweaksprofile file")
    p.add_argument("--selection", default="",
                   help="UI selection: a JSON object {var: value} or a path to "
                        "one; overlaid on the default profile (--base-profile)")
    p.add_argument("--base-profile", default="",
                   help="baseline .x6tweaksprofile for --selection (default: "
                        "the shipped default.x6tweaksprofile)")
    p.add_argument("--vanilla", default="",
                   help=f"vanilla BIN (default: {DEFAULT_VANILLA})")
    p.add_argument("--run-extracted", default="",
                   help="patcher run-extracted dir (tools/ + data/)")
    p.add_argument("--staging", default="",
                   help="variant staging dir (default: mmx6-tweaks/variants/<id>)")
    p.add_argument("--work-dir", default="",
                   help="scratch dir for the engine run (default: _patcher/_worktmp)")
    p.add_argument("--ahk", default="", help="AutoHotkey v1.1 exe (autodetected)")
    p.add_argument("--recompiler", default="",
                   help="psxrecomp-game.exe for --regen")
    p.add_argument("--no-emit-toml", dest="emit_toml", action="store_false",
                   help="do not write game.<variant>.toml")
    p.add_argument("--regen", action="store_true",
                   help="run the recompiler on the emitted toml after staging")
    p.add_argument("--skip-md5-check", action="store_true",
                   help="do not verify the vanilla BIN MD5")

    args = ap.parse_args()

    db = TweaksDB(args.patcher_src)
    return {"list": cmd_list, "audit": cmd_audit, "catalog": cmd_catalog,
            "deps": cmd_deps, "apply": cmd_apply}[args.cmd](db, args)


if __name__ == "__main__":
    sys.exit(main())
