#!/usr/bin/env python3
"""dbg.py - send a raw JSON debug command to the recomp TCP server.
Usage: python dbg.py [--port 4490] '<json>'  OR  python dbg.py cmd k=v k=v
Examples:
  python dbg.py ping
  python dbg.py sio_trace count=30
  python dbg.py screenshot path=_shot.bmp
  python dbg.py read_ram addr=0x800E5888 len=64
"""
import socket, sys, json, time

port = 4490
args = sys.argv[1:]
if args and args[0] == "--port":
    port = int(args[1]); args = args[2:]

if not args:
    print("need a command"); sys.exit(2)

if args[0].lstrip().startswith("{"):
    payload = args[0]
else:
    obj = {"cmd": args[0]}
    for kv in args[1:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            # addr/hex fields must be sent as STRINGS (server parses the hex
            # string); only len-like fields are ints.
            if k in ("addr", "hex", "lo", "hi", "target"):
                obj[k] = v
            else:
                try:
                    obj[k] = int(v, 0)
                except ValueError:
                    obj[k] = v
    payload = json.dumps(obj)

s = socket.socket()
s.settimeout(20)
try:
    s.connect(("127.0.0.1", port))
    s.sendall(payload.encode() + b"\n")
    time.sleep(0.15)
    buf = b""
    s.settimeout(3)
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            if buf.endswith(b"\n") and buf.count(b"{") <= buf.count(b"}"):
                break
    except socket.timeout:
        pass
    out = buf.decode(errors="replace").strip()
    try:
        print(json.dumps(json.loads(out), indent=2))
    except Exception:
        print(out)
except Exception as e:
    print(f"ERR: {e}")
