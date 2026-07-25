#!/usr/bin/env python3
"""nav.py - drive Mega Man X6 from a cold boot to live in-stage gameplay.

Reaching gameplay by hand costs a dozen round-trips every time the runtime is
rebuilt, and a co-op / enhancement session rebuilds constantly. This walks the
whole path and PROVES liveness at the end (inject a direction, watch the X
position change) rather than trusting a scene byte -- in-stage cutscenes report
the same scene id with the player pipeline idle.

  python nav.py                 # boot -> stage, then prove the player moves
  python nav.py --char zero     # pick ZERO at the PLAYER SELECT prompt
  python nav.py --shot out.png  # also screenshot when it lands

Scene byte 0x800CD3F8: 0=opening movie, 1=title, 2=attract demo, 6=title menu,
7=stage select AND in-stage. It is NOT fine-grained enough to detect gameplay
on its own -- hence the liveness probe.
"""
import argparse
import json
import socket
import sys
import time

PORT = 4490
SCENE = 0x800CD3F8
PLAYER_X = 0x800970A8          # 16.16 world X of the player actor
CHAR_ID = 0x800CCEF8           # PLAYER SELECT character id: X=0, ZERO=5
CHARS = {"x": 0, "falcon": 1, "shadow": 2, "blade": 3, "ultimate": 4, "zero": 5}

BUTTONS = {"select": 0x0001, "start": 0x0008, "up": 0x0010, "right": 0x0020,
           "down": 0x0040, "left": 0x0080, "triangle": 0x1000,
           "circle": 0x2000, "cross": 0x4000, "square": 0x8000}


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


def tap(name, wait=0.6, frames=3):
    send({"cmd": "set_input", "buttons": 0xFFFF & ~BUTTONS[name]})
    time.sleep(frames / 60.0)
    send({"cmd": "clear_input"})
    time.sleep(wait)


def byte(addr):
    r = send({"cmd": "read_ram", "addr": hex(addr), "len": 1})
    return int(r["hex"], 16) if r.get("ok") else -1


def word(addr):
    r = send({"cmd": "read_ram", "addr": hex(addr), "len": 4})
    return r["hex"] if r.get("ok") else ""


def wait_scene(vals, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        if byte(SCENE) in vals:
            return True
        time.sleep(0.5)
    return False


def alive(tries=6):
    """Inject RIGHT and require the world X to change. The only honest test:
    the scene byte reads the same during the stage-entry cutscene, when the
    player pipeline has not started yet -- hence the retries."""
    before = after = word(PLAYER_X)
    for _ in range(tries):
        before = word(PLAYER_X)
        send({"cmd": "set_input", "buttons": 0xFFFF & ~BUTTONS["right"]})
        time.sleep(1.0)
        after = word(PLAYER_X)
        send({"cmd": "clear_input"})
        if before != after:
            return True, before, after
        time.sleep(1.5)
    return False, before, after


def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="x", choices=sorted(CHARS))
    ap.add_argument("--shot")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args()
    PORT = a.port

    if not send({"cmd": "ping"}).get("ok"):
        sys.exit("no debug server on port %d" % PORT)

    # Re-entrant: a session already past the title (scene 7 covers everything
    # from FILE SELECT to in-stage) resumes at the probe-driven stage below
    # rather than demanding a fresh boot.
    if byte(SCENE) == 7:
        print("[nav] already past the title; resuming at the select screens")
        return finish(a)

    # 1. Opening movie -> title. START skips; the title also times out into the
    #    attract demo, so keep tapping until the title is actually up.
    print("[nav] skipping to title ...")
    for _ in range(30):
        if byte(SCENE) == 1:
            break
        tap("start", wait=0.5)
    if not wait_scene({1}, 30):
        sys.exit("[nav] never reached the title screen")

    # 2. The title takes a few seconds to finish loading before it accepts
    #    START; too early and it falls through into the attract demo.
    time.sleep(5.0)
    tap("start", wait=1.2)
    if byte(SCENE) != 6:
        print("[nav] title press missed (scene %d); retrying" % byte(SCENE))
        for _ in range(12):
            tap("start", wait=1.0)
            if byte(SCENE) == 6:
                break
            if byte(SCENE) == 2:            # fell into the demo -- break out
                tap("start", wait=1.5)
                wait_scene({1}, 25)
                time.sleep(5.0)
    if byte(SCENE) != 6:
        sys.exit("[nav] never reached the title menu")

    # 3. GAME START / CONTINUE / OPTION -> CONTINUE -> load from memory card.
    print("[nav] title menu -> continue from memory card ...")
    tap("down", wait=0.4)
    tap("cross", wait=1.0)      # "Continue the game?"
    tap("cross", wait=1.5)      # "Load from a MEMORY CARD."
    if not wait_scene({7}, 30):
        sys.exit("[nav] card check never completed")
    time.sleep(4.0)             # FILE SELECT draw

    return finish(a)


def finish(a):
    # 4. FILE SELECT -> DATA 1 -> the confirm (whose cursor starts on "Load
    #    cancel", so LEFT first) -> stage-select globe -> PLAYER SELECT.
    #
    #    None of those screens change the scene byte, so drive by PROBE instead
    #    of by sleep: only PLAYER SELECT reacts to RIGHT by changing the
    #    character id. Advancing with CROSS is safe to repeat -- a stray CROSS
    #    on the confirm picks "Load cancel" and lands back on FILE SELECT.
    print("[nav] file select -> stage select -> player select ...")
    tap("cross", wait=1.2)      # DATA 1 -> "OK to load?"
    tap("left", wait=0.6)       # onto "Yes"
    tap("cross", wait=3.0)
    at_player_select = False
    for _ in range(8):
        time.sleep(2.5)
        was = byte(CHAR_ID)
        tap("right", wait=0.5)
        if byte(CHAR_ID) != was:
            at_player_select = True
            break
        tap("cross", wait=1.5)
    if not at_player_select:
        sys.exit("[nav] never reached PLAYER SELECT")

    # 5. Cycle to the requested character, then enter the stage.
    want = CHARS[a.char]
    for _ in range(8):
        if byte(CHAR_ID) == want:
            break
        tap("right", wait=0.4)
    if byte(CHAR_ID) != want:
        print("[nav] WARNING: character id is %d, wanted %d" % (byte(CHAR_ID), want))
    tap("cross", wait=4.0)
    for _ in range(20):         # stage load
        if word(PLAYER_X) not in ("00000000", ""):
            break
        time.sleep(1.0)
    time.sleep(2.0)

    ok, before, after = alive()
    print("[nav] scene=%d char=%d playerX %s -> %s  %s"
          % (byte(SCENE), byte(CHAR_ID), before, after,
             "LIVE" if ok else "NOT RESPONDING"))
    if a.shot:
        print(send({"cmd": "screenshot", "path": a.shot}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
