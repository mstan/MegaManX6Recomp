"""Bisection parity audit: prove the Python tweaks port is byte-identical to the
live AHK `dump` oracle across the whole option catalog, WITHOUT a 1:1 per-option
run.

Strategy: test all options ON at once. If the port's plan (PATCHFILE + WRITELIST +
FILES) equals the oracle's, parity is proven in one shot. Otherwise split the option
set in half, test each half, and recurse into the divergent half(s) until the
culprit options are isolated. If a divergent set splits into two CLEAN halves, the
divergence is an interaction between the halves (not a single-option bug) — reported
separately.

Enum/family collapse: options that share a structural prefix (e.g. NightmareDisable01
..08) are the same code path with different data; once a representative passes we
don't re-drill its siblings. Bisection already amortizes this, but the family map is
printed so obvious enum groups can be pruned.

Usage:
  python tools/tweaks_parity_bisect.py                 # full checkbox+radio audit
  python tools/tweaks_parity_bisect.py --types checkbox,radio,dropdownlist
  python tools/tweaks_parity_bisect.py --vars A,B,C     # audit just these
  python tools/tweaks_parity_bisect.py --value-driven   # include dropdown/slider/edit reps
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


twr = _load("tweaks_resolver")
eng = _load("tweaks_engine")

DB = twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)
CAT = twr.parse_gui_catalog(twr.DEFAULT_PATCHER_SRC, DB)
AHK = twr.find_autohotkey("")
_SCRATCH = _TOOLS.parent / "_portcheck_bisect"
_SCRATCH.mkdir(exist_ok=True)
_run_counter = [0]


# -- plan model -------------------------------------------------------------
def _norm_path(p: str) -> str:
    """Canonicalize a file path for cross-engine comparison. The oracle emits
    Windows backslash absolute paths (F:\\...) and the port emits POSIX ones
    (/f/...); both live under run_extracted. Normalize to the lowercased relative
    tail after 'run_extracted/' so the same file compares equal regardless of the
    drive/slash form. (Do NOT Path.resolve() — under MSYS python it mangles the
    Windows drive letter to /:\\..., producing false path mismatches.)"""
    s = p.strip().replace("\\", "/").lower()
    key = "run_extracted/"
    i = s.find(key)
    return s[i + len(key):] if i >= 0 else s


def _parse_files(plan: str):
    """Multiset (Counter) of normalized art-insert PATHS. We compare by path count,
    NOT by the file-var NAME: the port names every offset of a file `<var>_File0N`
    while the oracle names them `<var>_File0N_<OptionID><nth>` — a cosmetic label
    difference. The real disc effect is which file is written how many times (each
    at its `_dat`-defined offset, identical between engines). See MugshotCustom."""
    files, section = Counter(), None
    for line in plan.splitlines():
        s = line.strip()
        if s == "[WRITELIST]":
            section = "w"
        elif s == "[FILES]":
            section = "f"
        elif section == "f" and "," in line:
            _var, path = line.split(",", 1)
            files[_norm_path(path)] += 1
    return files


def oracle_plan(sel: dict):
    """(patchfile, set(writes), set(files)) from a live AHK dump for `sel`."""
    _run_counter[0] += 1
    wd = _SCRATCH / f"o{_run_counter[0]:04d}"
    wd.mkdir(exist_ok=True)
    gen = wd / "_sel.x6tweaksprofile"
    gen.write_text(twr.emit_profile(eng.merged_profile(DB, json.dumps(sel))),
                   encoding="utf-8")
    plan = twr.dump_engine(str(gen), twr.DEFAULT_VANILLA, wd,
                           twr.DEFAULT_PATCHER_SRC, twr.DEFAULT_RUN_EXTRACTED, AHK)
    pf, writes = eng.parse_plan(plan)
    return pf, set(writes), _parse_files(plan)


def python_plan(sel: dict):
    from collections import OrderedDict
    merged = eng.merged_profile(DB, json.dumps(sel))
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    pf, writes = eng.build_writelist(DB, merged, base)
    _pf2, files = eng.build_filelist(DB, merged, base)
    fcount = Counter(_norm_path(fp) for _v, fp, _off in files)
    return pf, set(writes), fcount


def diff(sel: dict):
    """Return (ok, detail) comparing python vs oracle for selection `sel`."""
    po_pf, po_w, po_f = python_plan(sel)
    or_pf, or_w, or_f = oracle_plan(sel)
    d = {
        "pf_py": po_pf, "pf_or": or_pf, "pf_ok": po_pf == or_pf,
        "w_missing": or_w - po_w, "w_extra": po_w - or_w,
        "f_missing": or_f - po_f, "f_extra": po_f - or_f,
    }
    ok = d["pf_ok"] and not d["w_missing"] and not d["w_extra"] \
        and not d["f_missing"] and not d["f_extra"]
    return ok, d


# Non-deterministic by design: the PartsRandom randomizer uses AHK `Sort, Random`
# (exception_b.ahk:79/86), which shuffles differently every run — two oracle runs
# of PartsRandomTitle01 differ from each other at 0x1D98BBFC/0x1D98BEB8. These can
# never byte-match a single oracle dump and are excluded from the parity audit.
NONDETERMINISTIC = {"PartsRandom01", "PartsRandom02", "PartsRandomTitle01"}


# -- universe ---------------------------------------------------------------
def universe(types):
    return [c["var"] for c in CAT if c.get("type") in types and c.get("var")
            and c["var"] not in NONDETERMINISTIC]


def family(var: str) -> str:
    m = re.match(r"^(.*?)(\d+)$", var)
    return m.group(1) if m else var


def rep_value(c):
    """A representative NON-default value for a value-driven control, or None if we
    can't pick one safely. Dropdowns: first choice that isn't the default and isn't
    the 'No change' no-op. (Sliders/edits need range-aware numeric handling — TODO.)"""
    t = c.get("type")
    dflt = c.get("default")
    if t == "dropdownlist":
        for ch in c.get("choices") or []:
            if ch != dflt and ch.strip().lower() != "no change":
                return ch
        return None
    if t == "slider":
        try:
            lo, hi = (int(x) for x in str(c.get("range")).split("-"))
            d = int(dflt)
        except Exception:
            return None
        for cand in (lo, hi, (lo + hi) // 2):        # a distinct in-range value
            if cand != d and lo <= cand <= hi:
                return str(cand)
        return None
    if t == "edit":
        try:
            return str(int(dflt) + 1)                # a distinct numeric value
        except Exception:
            return None
    return None


# -- bisection --------------------------------------------------------------
def bisect(vars_list, log, valmap):
    """Return (culprits, interactions). culprits=[var]; interactions=[[vars]].
    valmap maps each var to the value to set it to (True for checkbox/radio, a
    representative value for value-driven controls)."""
    culprits, interactions = [], []
    stack = [list(vars_list)]
    while stack:
        s = stack.pop()
        ok, d = diff({v: valmap[v] for v in s})
        tag = "OK  " if ok else "DIFF"
        log(f"  [{tag}] n={len(s):3d}  "
            f"{'' if ok else _diff_brief(d)}  "
            f"{s[0]}..{s[-1] if len(s)>1 else ''}")
        if ok:
            continue
        if len(s) == 1:
            culprits.append((s[0], d))
            continue
        mid = len(s) // 2
        left, right = s[:mid], s[mid:]
        ok_l, _ = diff({v: valmap[v] for v in left})
        ok_r, _ = diff({v: valmap[v] for v in right})
        if ok_l and ok_r:
            interactions.append((s, d))            # neither half alone diverges
            log(f"       INTERACTION across split (n={len(s)}) — both halves clean")
            continue
        if not ok_l:
            stack.append(left)
        if not ok_r:
            stack.append(right)
    return culprits, interactions


def _diff_brief(d):
    bits = []
    if not d["pf_ok"]:
        bits.append(f"PF {d['pf_py']}!={d['pf_or']}")
    if d["w_missing"]:
        bits.append(f"-{len(d['w_missing'])}w")
    if d["w_extra"]:
        bits.append(f"+{len(d['w_extra'])}w")
    if d["f_missing"]:
        bits.append(f"-{len(d['f_missing'])}f")
    if d["f_extra"]:
        bits.append(f"+{len(d['f_extra'])}f")
    return " ".join(bits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default="checkbox,radio")
    ap.add_argument("--vars", default="")
    args = ap.parse_args()
    want = set(args.types.split(","))
    value_types = {"dropdownlist", "slider", "edit"}
    if args.vars:
        want_vars = set(v for v in args.vars.split(",") if v)
    else:
        want_vars = None
    # Build the (var -> value) map. Bool True for checkbox/radio; a representative
    # value for value-driven controls (skipping any we can't pick a value for).
    valmap, vars_list, skipped = {}, [], []
    for c in CAT:
        v = c.get("var")
        t = c.get("type")
        if not v or v in NONDETERMINISTIC or t not in want:
            continue
        if want_vars is not None and v not in want_vars:
            continue
        if t in value_types:
            rv = rep_value(c)
            if rv is None:
                skipped.append(v)
                continue
            valmap[v] = rv
        else:
            valmap[v] = True
        if v not in valmap:      # de-dup guard
            continue
        vars_list.append(v)
    print(f"universe: {len(vars_list)} options ({args.types})"
          f"{f'; skipped {len(skipped)} (no rep value)' if skipped else ''}")
    fams = {}
    for v in vars_list:
        fams.setdefault(family(v), []).append(v)
    print(f"families: {len(fams)}")

    def log(m):
        print(m, flush=True)

    culprits, interactions = bisect(vars_list, log, valmap)
    print("\n================ PARITY AUDIT RESULT ================")
    print(f"oracle runs: {_run_counter[0]}")
    if not culprits and not interactions:
        print("*** BYTE-IDENTICAL across the entire universe. ***")
        return 0
    if culprits:
        print(f"\nDIVERGENT OPTIONS ({len(culprits)}):")
        for v, d in culprits:
            print(f"  {v:28} {_diff_brief(d)}  (family {family(v)})")
    if interactions:
        print(f"\nINTERACTION DIVERGENCES ({len(interactions)}):")
        for s, d in interactions:
            print(f"  n={len(s)} {_diff_brief(d)}: {s}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
