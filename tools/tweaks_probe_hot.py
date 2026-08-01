"""Characterize the hot functions: are the many tweaks touching them CF injections,
inline logic edits, or table/immediate writes (which want data/per-edit handling,
not per-combination code variants)?"""
import importlib.util, sys
from pathlib import Path
from collections import OrderedDict, defaultdict, Counter

TOOLS = Path("tools").resolve()
def load(name):
    s = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(s); sys.modules[name] = m; s.loader.exec_module(m); return m
pb = load("tweaks_prebake"); twr = pb.twr; eng = pb.eng
db = pb._db(); geom = pb.Geometry(twr.DEFAULT_VANILLA); cm = pb.CodeMap(pb.RANGES)
base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE)); base_set = pb._base_set(db, base)
cat = pb.cat_of(db)

def opname(w):
    op = (w >> 26) & 0x3F
    if op == 0:
        fn = w & 0x3F
        return {8:"jr",9:"jalr",0x20:"add",0x21:"addu",0x24:"and",0x25:"or",0:"sll",0x2a:"slt"}.get(fn, f"spc{fn:02x}")
    return {1:"regimm",2:"j",3:"jal",4:"beq",5:"bne",6:"blez",7:"bgtz",8:"addi",9:"addiu",
            0xa:"slti",0xb:"sltiu",0xc:"andi",0xd:"ori",0xf:"lui",0x23:"lw",0x2b:"sw",
            0x28:"sb",0x29:"sh",0x24:"lbu",0x25:"lhu"}.get(op, f"op{op:02x}")

def sel_for(o):
    t = o["type"]
    if t in ("checkbox","radio"): return {o["var"]: True}
    if t == "dropdownlist" and o.get("choices") and len(o["choices"])>1: return {o["var"]: "@1"}
    if t in ("edit","slider"): return {o["var"]: "5"}
    return None

HOT = [0x80079F2C, 0x8007693C, 0x8001E088, 0x8007A7AC, 0x80076340]

# gather, per hot func, the words each option writes and their opcodes
byvar = {o["var"]: o for o in cat}
func_writes = defaultdict(lambda: defaultdict(list))  # func -> var -> [(addr, van_op, pat_op, is_cf)]
for o in cat:
    v = o["var"]; sel = sel_for(o)
    if sel is None: continue
    try:
        c = pb.classify_writes(geom, cm, pb._writes_for(db, base, sel), base_set)
    except Exception:
        continue
    for wa, van_hex, pat_hex in c["guarded"]:
        f = cm.func_of(wa)
        if f in HOT:
            vw = int.from_bytes(bytes.fromhex(van_hex),"little")
            pw = int.from_bytes(bytes.fromhex(pat_hex),"little")
            cf = ((pw>>26)&0x3f) in (1,2,3,4,5,6,7) or (((pw>>26)&0x3f)==0 and (pw&0x3f) in (8,9))
            func_writes[f][v].append((wa, opname(vw), opname(pw), cf))

for f in HOT:
    fw = func_writes[f]
    allrows = [r for rows in fw.values() for r in rows]
    n_opts = len(fw)
    n_cf = sum(1 for r in allrows if r[3])
    van_ops = Counter(r[1] for r in allrows)
    pat_ops = Counter(r[2] for r in allrows)
    # distinct addresses vs total writes: do options write the SAME words (conflict)
    # or DIFFERENT words (additive/table)?
    addr_writers = defaultdict(set)
    for v, rows in fw.items():
        for wa,_,_,_ in rows: addr_writers[wa].add(v)
    shared_addrs = sum(1 for a,ws in addr_writers.items() if len(ws) > 1)
    print(f"\n=== func 0x{f:08X} : {n_opts} code opts, {len(allrows)} word-writes, "
          f"{len(addr_writers)} distinct words ===")
    o0 = byvar.get(next(iter(fw)))
    print(f"  first opt type={o0['type']} tab={o0.get('tab')!r} section={o0.get('section')!r}")
    print(f"  CF word-writes: {n_cf}/{len(allrows)}   words hit by >1 opt (conflict): {shared_addrs}/{len(addr_writers)}")
    print(f"  vanilla opcodes at sites: {dict(van_ops.most_common(6))}")
    print(f"  patched opcodes at sites: {dict(pat_ops.most_common(6))}")
