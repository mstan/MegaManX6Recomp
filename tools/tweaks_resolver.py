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
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

DEFAULT_PATCHER_SRC = Path(
    r"F:\Projects\psxrecomp\MegaManX6Recomp\mmx6-tweaks\_patcher\src_extracted"
    r"\Mega Man X6 Tweaks Patcher (v2.6.1)\_src"
)

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


def cmd_apply(db: TweaksDB, args) -> int:
    # TODO(next session): the apply pipeline. Steps, all data already parsed:
    #   1. base image: xdelta3 -d -s vanilla.bin (b01|s02 by ScriptPatch) -> work.bin
    #      (mmx6-tweaks/_patcher/run_extracted/data/xdelta3/{b01,s02}.xdelta3,
    #       tools/xdelta3/xdelta3-3.0.11-i686.exe — needs WINDOWS paths)
    #   2. selection -> resolve_dependencies -> + PatchList_Base
    #      (+ PatchList_Script when ScriptPatch selected) -> write_order
    #   3. per option: ASM slots paired by slot number (bytes + offset,
    #      offset chosen by set: COMMON or B01/S02 to match the base patch);
    #      direct values converted per Text/NumWord/NumHalfword/NumByte/Add
    #      filters, written little-endian at Var_Offset (+ mirror at
    #      offset+4 for halfword-with-echo cases per patchapply.ahk);
    #      File slots copy asset payloads from _patcher/run_extracted/data/.
    #   4. error_recalc.exe over work.bin (EDC/ECC).
    #   5. iso_extract.py -> SLUS_013.95, crc32 -> variant id, emit
    #      game.<variant>.toml, optionally kick regen.
    # VALIDATION GATE before this ships: applying the "everything" selection
    # must reproduce the standalone [Tweaks+Loc+Art v2.6].bin byte-for-byte.
    print("apply: not implemented yet — parse/deps layer only. "
          "See TODO in cmd_apply.", file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--patcher-src", type=Path, default=DEFAULT_PATCHER_SRC,
                    help="path to the extracted patcher _src dir")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="print the option catalog")
    sub.add_parser("audit", help="database coverage statistics")
    p = sub.add_parser("deps", help="dependency closure + write order")
    p.add_argument("--select", default="", help="comma-separated option instances")
    p = sub.add_parser("apply", help="produce a patched BIN (not implemented)")
    p.add_argument("--select", default="")
    args = ap.parse_args()

    db = TweaksDB(args.patcher_src)
    return {"list": cmd_list, "audit": cmd_audit,
            "deps": cmd_deps, "apply": cmd_apply}[args.cmd](db, args)


if __name__ == "__main__":
    sys.exit(main())
