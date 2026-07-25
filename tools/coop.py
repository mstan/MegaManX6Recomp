#!/usr/bin/env python3
"""coop.py - arm Mega Man X6's second player actor over the debug server.

The framework capability is generic (runtime/src/coop.c); everything MMX6 about
it is the handful of addresses below, all measured, each with the measurement
recorded next to it. Keeping them in one script means a rebuilt runtime is one
command away from a two-player scene instead of a dozen hand-typed commands.

  python coop.py on          # declare regions, configure, spawn actor 0
  python coop.py off
  python coop.py status
  python coop.py probe       # drive each pad in turn and report who moved
"""
import json
import socket
import sys
import time

PORT = 4490

# --- measured MMX6 addresses ------------------------------------------------
PLAYER      = 0x800970A0   # player actor struct ...
PLAYER_LEN  = 344          # ... 0x158 bytes, ending exactly where the BG layer
                           # struct 0x800971F8 begins.
PLAYER_X    = 0x800970A8   # 16.16 world X
SCENE       = 0x800CD3F8   # scene id; 7 = stage select AND in-stage
SCENE_LIVE  = 7
PAUSE       = 0x80097424   # must be 0 for the extra actor to run
LOCK        = 0x800C4568   # scripted-sequence lock; likewise

# The engine's per-frame controller globals. FUN_8003CD44 (the pipeline's
# pad-input stage) loads 0x800C456C and hands it to the decoder at 0x8003D7AC,
# which produces the actor's +0x7C/+0x7E/+0x80. Three consecutive halfwords are
# rewritten every frame by the game's own pad routine; the first two both track
# "currently held", so both are fed.
#
# Their contents are the pad's two button bytes in TRANSFER order, held-active-
# high -- byteswap(~sio). Verified for all 14 buttons, which is why the runtime
# feeds this in "wire" order rather than transcribing a per-game bit map.
PAD_GLOBALS = 0x800C456C
PAD_WORDS   = 2

SCRATCH     = 0x00800000   # enhancement scratch window (above the RAM mirror)


def send(obj, settle=0.05):
    s = socket.socket()
    s.settimeout(20)
    try:
        s.connect(("127.0.0.1", PORT))
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
        return {"ok": False}


def word(addr):
    r = send({"cmd": "read_ram", "addr": hex(addr), "len": 4})
    return r.get("hex", "")


def on():
    send({"cmd": "coop", "companions": 0})               # clear any prior arming
    r = send({"cmd": "coop_region", "base": hex(PAD_GLOBALS), "len": 2 * PAD_WORDS + 2})
    if not r.get("ok"):
        sys.exit("region rejected: %s" % r)
    r = send({"cmd": "coop", "primary": hex(PLAYER), "struct_len": PLAYER_LEN,
              "companions": 1, "scratch": hex(SCRATCH),
              "mode_addr": hex(SCENE), "mode_val": SCENE_LIVE,
              "zero1": hex(PAUSE), "zero2": hex(LOCK),
              "raw_pad": hex(PAD_GLOBALS), "raw_pad_words": PAD_WORDS,
              "raw_pad_wire": 1})
    if not r.get("ok"):
        sys.exit("configure rejected: %s" % r)
    print(json.dumps(r, indent=1))
    print(send({"cmd": "coop_spawn", "idx": 0}))


def status():
    print(json.dumps(send({"cmd": "coop"}), indent=1))
    print(json.dumps(send({"cmd": "coop_region"}), indent=1))


def probe():
    """Hold RIGHT on one port at a time and report which actor moved. The only
    honest check that the two are independent -- counters cannot show it."""
    actor0 = send({"cmd": "coop"}).get("actor0", "0x0")
    c_x = int(actor0, 16) + 8 if actor0 != "0x0" else 0
    # Try BOTH directions per port: an actor pinned against terrain does not
    # move when pushed into it, and reading that as "no control" is how a
    # working build gets diagnosed as broken.
    for slot, label in ((0, "player 1"), (1, "player 2")):
        for name, btn in (("RIGHT", 0xFFDF), ("LEFT", 0xFF7F)):
            p0, c0 = word(PLAYER_X), word(c_x) if c_x else ""
            send({"cmd": "set_input", "slot": slot, "buttons": btn})
            time.sleep(2.0)
            send({"cmd": "clear_input", "slot": slot})
            time.sleep(0.4)
            p1, c1 = word(PLAYER_X), word(c_x) if c_x else ""
            print(f"{name:5s} on {label}: P1 {p0}->{p1} {'MOVED' if p0 != p1 else '-'}   "
                  f"P2 {c0}->{c1} {'MOVED' if c0 != c1 else '-'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "on":
        on()
    elif cmd == "off":
        print(send({"cmd": "coop", "companions": 0}))
    elif cmd == "probe":
        probe()
    else:
        status()
