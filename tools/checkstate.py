#!/usr/bin/env python3
"""Quick MMX6 boot-progress check: frame, display, title sub-state, pool, func entry flag.
Usage: python tools/checkstate.py [port]
"""
import socket, sys, json, time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 4490

def cmd(obj):
    s = socket.socket(); s.settimeout(8)
    try:
        s.connect(("127.0.0.1", port))
    except Exception as e:
        print(f"connect fail: {e}"); sys.exit(1)
    s.sendall(json.dumps(obj).encode() + b"\n")
    time.sleep(0.1); buf=b""; s.settimeout(3)
    try:
        while True:
            c=s.recv(65536)
            if not c: break
            buf+=c
            if buf.endswith(b"\n"): break
    except socket.timeout: pass
    s.close()
    for line in reversed(buf.decode(errors="replace").strip().splitlines()):
        try: return json.loads(line)
        except Exception: continue
    return {}

ping = cmd({"cmd":"ping"})
print("frame:", ping.get("frame"), "miss:", ping.get("dispatch_miss_total"))
g = cmd({"cmd":"gpu"})
print("display disabled:", g.get("disabled"), "gpustat:", g.get("gpustat"))
st = cmd({"cmd":"read_ram","addr":"0x800CD3F8","len":16}).get("hex","")
if st:
    b=bytes.fromhex(st)
    print(f"main-mode[0x800CD3F8]={b[0]:#04x} title-substate[+1]={b[1]:#04x} D0E4-ran[+0xd]={b[13]:#04x}")
# pool occupancy
BASE=0x800CD410; SLOT=0x60; N=96
r=cmd({"cmd":"read_ram","addr":f"0x{BASE:08X}","len":N*SLOT}).get("hex","")
if r and len(r)>=N*SLOT*2:
    b=bytes.fromhex(r); used=sum(1 for i in range(N) if b[i*SLOT]!=0)
    print(f"object pool: {used}/{N} used")
else:
    print("pool read short")
