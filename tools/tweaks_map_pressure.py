"""Combination-pressure map for dual-source function-variants.

For code-tier tweaks (inline + control-flow), a function touched by exactly one
tweak is trivial (bake vanilla + 1 variant). Cost only appears where MULTIPLE
COMBINABLE (not mutually-exclusive) code tweaks touch the SAME function -- those
need per-combination handling. This measures that distribution.
"""
import importlib.util, sys
from pathlib import Path
from collections import OrderedDict, defaultdict, Counter
from itertools import combinations

TOOLS = Path("tools").resolve()
def load(name):
    s = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(s); sys.modules[name] = m; s.loader.exec_module(m); return m
pb = load("tweaks_prebake"); twr = pb.twr; eng = pb.eng

db = pb._db(); geom = pb.Geometry(twr.DEFAULT_VANILLA); cm = pb.CodeMap(pb.RANGES)
base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE)); base_set = pb._base_set(db, base)
cat = pb.cat_of(db); SIB = eng._radio_siblings(db)

def is_cf(w):
    op = (w >> 26) & 0x3F
    return op in (1,2,3,4,5,6,7) or (op == 0 and (w & 0x3F) in (8,9))

def sel_for(o):
    t = o["type"]
    if t in ("checkbox", "radio"): return {o["var"]: True}
    if t == "dropdownlist" and o.get("choices") and len(o["choices"]) > 1: return {o["var"]: "@1"}
    if t in ("edit", "slider"): return {o["var"]: "5"}
    return None

# code-tier options -> set of functions they modify
code_funcs = {}   # var -> set(func_entry)
kind = {}
for o in cat:
    v = o["var"]; sel = sel_for(o)
    if sel is None: continue
    try:
        c = pb.classify_writes(geom, cm, pb._writes_for(db, base, sel), base_set)
    except Exception:
        continue
    cf = any(is_cf(int.from_bytes(bytes.fromhex(ph), "little")) for _,_,ph in c["guarded"])
    if c["guarded"] and cf:   kind[v] = "cf"
    elif c["guarded"]:        kind[v] = "inline"
    else:                     continue          # value/data tier: freely mixed, no variant
    if c["funcs"]:
        code_funcs[v] = set(c["funcs"])

def mutex(a, b):
    return b in SIB.get(a, ()) or a in SIB.get(b, ())

# function -> code options touching it
func_opts = defaultdict(set)
for v, fs in code_funcs.items():
    for f in fs: func_opts[f].add(v)

print(f"code-tier options: {len(code_funcs)}  ({Counter(kind.values())})")
print(f"distinct functions touched by code tweaks: {len(func_opts)}")

# per function: how many COMBINABLE code options (max set that can be simultaneously ON)
def max_combinable(opts):
    """largest subset with no mutex pair (greedy over mutex graph; groups are small)."""
    opts = list(opts)
    best = 1 if opts else 0
    # brute force is fine: these sets are tiny
    for r in range(len(opts), 1, -1):
        for combo in combinations(opts, r):
            if all(not mutex(a, b) for a, b in combinations(combo, 2)):
                return r
    return best

dist = Counter()
hot = []
for f, opts in func_opts.items():
    n = len(opts)
    mc = max_combinable(opts) if n > 1 else n
    dist[mc] += 1
    if mc >= 2:
        hot.append((mc, f, sorted(opts)))

print("\n== combination pressure (variants forced by ONE function) ==")
print("  max-simultaneous-tweaks  ->  #functions")
for k in sorted(dist):
    tag = "(trivial: vanilla+1)" if k <= 1 else f"(up to 2^{k}={2**k} combos worst-case)"
    print(f"    {k:2d}  ->  {dist[k]:4d}   {tag}")

hot.sort(reverse=True)
print(f"\n  functions with >=2 combinable code tweaks: {len(hot)}")
print("  worst offenders:")
for mc, f, opts in hot[:20]:
    show = ", ".join(opts[:5]) + (" ..." if len(opts) > 5 else "")
    print(f"    2^{mc} @ func 0x{f:08X}  [{len(opts)} opts]  {show}")

# total variant bodies if we bake every reachable combination per function (upper bound)
ub = sum(2**mc for mc in (max_combinable(o) if len(o)>1 else 1 for o in func_opts.values()))
lin = len(func_opts)  # if every shared func were just packaged (1 patched variant each)
print(f"\n  variant bodies -- packaged (1 patched/func): {lin}")
print(f"  variant bodies -- full independence (worst-case combos): {ub}")
