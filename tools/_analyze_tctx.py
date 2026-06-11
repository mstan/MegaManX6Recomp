import json
from collections import Counter
lines = open("starvation_dump.jsonl", encoding="utf-8", errors="replace").read().splitlines()
tctx = [json.loads(l) for l in lines if '"tctx_seq"' in l]
print("tctx entries:", len(tctx), "seq range:", tctx[0]["tctx_seq"], "->", tctx[-1]["tctx_seq"])
print("distinct tcb:", Counter(e["tcb"] for e in tctx))
print("op counts:", Counter(e["op"] for e in tctx))
print("resume_pc counts:", Counter(e["resume_pc"] for e in tctx))
print("frame range:", min(e["frame"] for e in tctx), "->", max(e["frame"] for e in tctx))
# per tcb: distinct (resume_pc, sp) pairs to see inconsistency
from collections import defaultdict
d = defaultdict(set)
for e in tctx:
    d[e["tcb"]].add((e["resume_pc"], e["sp"]))
for tcb, s in d.items():
    print(f"\ntcb {tcb}: {len(s)} distinct (resume_pc,sp):")
    for rp, sp in sorted(s):
        print(f"    resume_pc={rp} sp={sp}")
# first 12 entries (start of captured window)
print("\n=== earliest 12 ===")
for e in tctx[:12]:
    print({k: e[k] for k in ("tctx_seq","op","frame","tcb","resume_pc","sp","ra")})
