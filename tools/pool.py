#!/usr/bin/env python3
"""Analyze the MMX6 object pool (0x800CD410, 96 slots x 0x60).
Reads slot headers over TCP and reports occupancy + type histogram.
Usage: python pool.py <port>
"""
import socket, sys, json, time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 4490
BASE = 0x800CD410
SLOT = 0x60
N = 96

def cmd(obj):
    s = socket.socket(); s.settimeout(8)
    s.connect(("127.0.0.1", port))
    s.sendall(json.dumps(obj).encode() + b"\n")
    time.sleep(0.1)
    buf = b""
    s.settimeout(3)
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            buf += c
            if buf.endswith(b"\n"): break
    except socket.timeout:
        pass
    s.close()
    txt = buf.decode(errors="replace").strip()
    # may be multiple json lines; take last complete
    for line in reversed(txt.splitlines()):
        try:
            return json.loads(line)
        except Exception:
            continue
    return {"raw": txt}

# read whole pool in one read_ram if allowed, else per-slot
total = N * SLOT
r = cmd({"cmd": "read_ram", "addr": f"0x{BASE:08X}", "len": total})
hx = r.get("hex")
if not hx or len(hx) < total*2:
    # fall back to per-slot reads of 4 bytes
    headers = []
    for i in range(N):
        rr = cmd({"cmd": "read_ram", "addr": f"0x{BASE + i*SLOT:08X}", "len": 4})
        h = rr.get("hex", "00000000")
        headers.append(bytes.fromhex(h))
    b = b"".join(h.ljust(SLOT, b"\x00") for h in headers)
else:
    b = bytes.fromhex(hx[:total*2])

used = 0
types = {}
used_slots = []
for i in range(N):
    off = i*SLOT
    f = b[off]; t = b[off+1]
    if f != 0:
        used += 1
        types[t] = types.get(t, 0) + 1
        used_slots.append(i)
print(f"port {port}: used {used}/{N}")
print(f"  type histogram (byte1): {dict(sorted(types.items()))}")
print(f"  used slot indices: {used_slots}")
