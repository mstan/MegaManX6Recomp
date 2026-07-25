#!/usr/bin/env python3
"""drive.py - scripted PSX pad input + screenshots over the debug TCP server.

Exists so an unattended validation soak can walk a game through boot ->
title -> menus -> gameplay reproducibly, instead of hand-typing raw button
words. PSX pad words are ACTIVE-LOW (a 0 bit means pressed), which is easy to
get wrong by hand; this maps names to bits.

Generic - no per-game logic. Button names and the pad encoding are PSX-wide.

Usage:
  python drive.py buttons                       # list names
  python drive.py press start x3 --frames 4     # tap START three times
  python drive.py hold right --ms 800           # hold, then release
  python drive.py shot out.png                  # screenshot (runtime encodes PNG)
  python drive.py seq "start*6:600,cross*3:400" # scripted sequence
  python drive.py --slot 1 press cross          # drive controller port 2

Screenshots are encoded by the runtime itself; no host image library is
needed. The file lands next to the runtime exe.
"""
import argparse
import json
import os
import socket
import sys
import time

DEFAULT_PORT = 4490
RELEASED = 0xFFFF

# PSX digital pad bit assignments. Active-low: clear the bit to press.
BUTTONS = {
    "select": 0x0001, "l3": 0x0002, "r3": 0x0004, "start": 0x0008,
    "up": 0x0010, "right": 0x0020, "down": 0x0040, "left": 0x0080,
    "l2": 0x0100, "r2": 0x0200, "l1": 0x0400, "r1": 0x0800,
    "triangle": 0x1000, "circle": 0x2000, "cross": 0x4000, "square": 0x8000,
}
ALIASES = {"x": "cross", "o": "circle", "a": "cross", "b": "circle",
           "sq": "square", "tri": "triangle"}


def send(port, obj, settle=0.12):
    s = socket.socket()
    s.settimeout(20)
    try:
        s.connect(("127.0.0.1", port))
        s.sendall(json.dumps(obj).encode() + b"\n")
        time.sleep(settle)
        buf = b""
        s.settimeout(5)
        try:
            while True:
                c = s.recv(1 << 16)
                if not c:
                    break
                buf += c
                if buf.endswith(b"\n") and buf.count(b"{") <= buf.count(b"}"):
                    break
        except socket.timeout:
            pass
    finally:
        s.close()
    try:
        return json.loads(buf.decode(errors="replace").strip())
    except Exception:
        return {"ok": False, "raw": buf.decode(errors="replace")[:300]}


def word_for(names):
    w = RELEASED
    for n in names:
        n = ALIASES.get(n.lower(), n.lower())
        if n not in BUTTONS:
            raise SystemExit(f"unknown button {n!r}; see `drive.py buttons`")
        w &= ~BUTTONS[n] & 0xFFFF
    return w


def do_press(port, slot, names, frames, times, gap_ms):
    w = word_for(names)
    for i in range(times):
        r = send(port, {"cmd": "press", "buttons": w, "frames": frames, "slot": slot})
        ok = "ok" if r.get("ok") else r
        print(f"  press {'+'.join(names)} -> 0x{w:04X} slot{slot} frames={frames} [{i+1}/{times}] {ok}")
        if gap_ms:
            time.sleep(gap_ms / 1000.0)


def do_hold(port, slot, names, ms):
    w = word_for(names)
    print(f"  hold {'+'.join(names)} -> 0x{w:04X} slot{slot} for {ms}ms")
    send(port, {"cmd": "set_input", "buttons": f"0x{w:04X}", "slot": slot})
    time.sleep(ms / 1000.0)
    send(port, {"cmd": "clear_input", "slot": slot})


def do_shot(port, out, runtime_cwd=None):
    """The runtime encodes PNG itself (debug_server.c handle_screenshot_file ->
    png_write_rgb), so no host-side image library is needed. Pass a BARE
    FILENAME: the runtime resolves it against its own working directory (next
    to the exe). Absolute paths have been observed to fail fopen here, so we
    deliberately send only the basename and report where it landed."""
    name = os.path.basename(out)
    if not name.lower().endswith(".png"):
        name = name.rsplit(".", 1)[0] + ".png"
    r = send(port, {"cmd": "screenshot", "path": name}, settle=0.5)
    if not r.get("ok"):
        print(f"  screenshot FAILED: {r}")
        return None
    landed = r.get("path", name)
    if runtime_cwd:
        landed = os.path.join(runtime_cwd, landed)
    print(f"  screenshot -> {landed}  {r.get('width')}x{r.get('height')}")
    return r


def do_seq(port, slot, spec, frames):
    """spec: comma-separated steps like 'start*6:600' = 6 taps, 600ms apart."""
    for step in spec.split(","):
        step = step.strip()
        if not step:
            continue
        gap = 400
        if ":" in step:
            step, g = step.rsplit(":", 1)
            gap = int(g)
        times = 1
        if "*" in step:
            step, t = step.split("*", 1)
            times = int(t)
        names = step.split("+")
        do_press(port, slot, names, frames, times, gap)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--slot", type=int, default=0, choices=(0, 1),
                    help="SIO slot: 0 = port 1, 1 = port 2")
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--runtime-cwd", default=None,
                    help="where the runtime writes screenshots (for reporting only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("buttons")
    p = sub.add_parser("press")
    p.add_argument("names", nargs="+")
    p.add_argument("--gap-ms", type=int, default=350)
    h = sub.add_parser("hold")
    h.add_argument("names", nargs="+")
    h.add_argument("--ms", type=int, default=500)
    s = sub.add_parser("shot")
    s.add_argument("out")
    q = sub.add_parser("seq")
    q.add_argument("spec")
    args = ap.parse_args()

    if args.cmd == "buttons":
        for k, v in BUTTONS.items():
            print(f"  {k:<9} 0x{v:04X}  pressed word 0x{RELEASED & ~v & 0xFFFF:04X}")
        return 0
    if args.cmd == "press":
        names, times = [], 1
        for n in args.names:
            if n.lower().startswith("x") and n[1:].isdigit():
                times = int(n[1:])
            else:
                names.append(n)
        do_press(args.port, args.slot, names, args.frames, times, args.gap_ms)
        return 0
    if args.cmd == "hold":
        do_hold(args.port, args.slot, args.names, args.ms)
        return 0
    if args.cmd == "shot":
        do_shot(args.port, args.out, args.runtime_cwd)
        return 0
    do_seq(args.port, args.slot, args.spec, args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
