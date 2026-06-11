#!/usr/bin/env python3
"""Read the recomp/oracle stack and print return-address candidates."""
import socket, sys, json, time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 4490
base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x801FEC00
length = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x200

def cmd(obj):
    s = socket.socket(); s.settimeout(8)
    s.connect(("127.0.0.1", port))
    s.sendall(json.dumps(obj).encode() + b"\n")
    time.sleep(0.1)
    buf = b""; s.settimeout(3)
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            buf += c
            if buf.endswith(b"\n"): break
    except socket.timeout:
        pass
    s.close()
    for line in reversed(buf.decode(errors="replace").strip().splitlines()):
        try: return json.loads(line)
        except Exception: continue
    return {}

r = cmd({"cmd": "read_ram", "addr": f"0x{base:08X}", "len": length})
hx = r.get("hex", "")
b = bytes.fromhex(hx)
print(f"stack {hex(base)}..{hex(base+length)} return-addr candidates:")
for i in range(0, len(b)-3, 4):
    w = int.from_bytes(b[i:i+4], "little")
    if 0x80010000 <= w <= 0x80090000:
        print(f"  [0x{base+i:08X}] = 0x{w:08X}")
