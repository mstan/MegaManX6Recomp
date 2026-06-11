import json, sys
from collections import Counter

f = sys.argv[1] if len(sys.argv) > 1 else "starvation_dump.jsonl"
lines = open(f, encoding="utf-8", errors="replace").read().strip().splitlines()

meta = json.loads(lines[0])
print("META:", json.dumps(meta.get("meta", meta), indent=2)[:1200])

evs = []
for ln in lines[1:]:
    try:
        evs.append(json.loads(ln))
    except Exception:
        pass
print("events:", len(evs))

def top(key, n=12):
    c = Counter(str(e.get(key)) for e in evs)
    return c.most_common(n)

print("\nby kind:", top("kind"))
print("\nby func:", top("func"))
print("\nby pc:", top("pc"))
print("\nin_exc:", top("in_exc"))
print("\nstat:", top("stat"))
print("\nctrl:", top("ctrl"))
print("\ni_stat:", top("i_stat"))
print("\ni_mask:", top("i_mask"))
print("\nowner:", top("owner"))
print("\ndev:", top("dev"))

# Time span
us = [e.get("us") for e in evs if isinstance(e.get("us"), int)]
if us:
    print("\nus span:", min(us), "->", max(us), "dur_us=", max(us)-min(us))

# Last 12 events verbatim (the tail = most recent before abort)
print("\n=== TAIL (last 10) ===")
for e in evs[-10:]:
    print({k: e.get(k) for k in ("seq","kind","func","pc","ctrl","stat","tx","rx","in_exc","i_stat","i_mask","ack_pend","ack_rem")})

# First 6 events (start of captured window)
print("\n=== HEAD (first 6) ===")
for e in evs[:6]:
    print({k: e.get(k) for k in ("seq","kind","func","pc","ctrl","stat","tx","rx","in_exc","i_stat","i_mask","ack_pend","ack_rem")})
