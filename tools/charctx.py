#!/usr/bin/env python3
"""charctx.py - capture and install an MMX6 playable CHARACTER as a data blob.

On MMX6 a character is not a flag. Setting the player struct's character byte
(+0x02: X=0, Zero=1) while the other character's data is loaded wedges the
machine into an exception storm, because the character really IS the data set
the loader installs at stage entry.

That data set is measurable. Running the same stage as X and as Zero and diffing
guest RAM gives 830 KB over 84 disjoint regions -- and the X-vs-X control diffs
by 866 bytes, so it is signal, not run-to-run noise. None of it is code (no
overlay covers it, the dirty-RAM interpreter never executes there), so it can
simply be captured and replayed.

  python charctx.py regions            # declare the 84 regions on the runtime
  python charctx.py save zero.ctx      # run as ZERO, then capture
  python charctx.py load zero.ctx      # run as X, then install over the LIVE player
  python charctx.py seed zero.ctx      # ... or make co-op actor 0 that character

REGIONS is generated from the measured diff, not hand-written; see
scratchpad ramdiff2.py for the derivation.
"""
import json
import os
import socket
import sys
import time

PORT = 4490
REGIONS_FILE = os.path.join(os.path.dirname(__file__), "mmx6_char_regions.json")


def apath(p):
    """Blob paths are passed VERBATIM and resolve against the RUNTIME's working
    directory (the build dir), not the shell's. Absolute Windows paths do not
    survive the debug server's JSON reader, so keep these to bare filenames."""
    if os.path.isabs(p):
        sys.exit("use a bare filename: blob paths resolve against the runtime cwd")
    return p


def send(obj, settle=0.02, t=60):
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect(("127.0.0.1", PORT))
        s.sendall(json.dumps(obj).encode() + b"\n")
        time.sleep(settle)
        buf = b""
        while True:
            c = s.recv(1 << 20)
            if not c:
                break
            buf += c
            if buf.endswith(b"\n") and buf.count(b"{") <= buf.count(b"}"):
                break
    finally:
        s.close()
    return json.loads(buf.decode(errors="replace").strip())


def declare():
    regions = json.load(open(REGIONS_FILE))
    send({"cmd": "ctx_region", "clear": 1})
    for base, length in regions:
        r = send({"cmd": "ctx_region", "base": hex(base), "len": length})
        if not r.get("ok"):
            sys.exit("region %#x len %d rejected: %s" % (base, length, r))
    total = sum(l for _, l in regions)
    print("declared %d regions, %d bytes (%.0f KB)"
          % (len(regions), total, total / 1024.0))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "regions":
        declare()
    elif cmd == "save":
        declare()
        print(send({"cmd": "ctx_save", "path": apath(sys.argv[2])}))
    elif cmd == "load":
        print(send({"cmd": "ctx_load", "path": apath(sys.argv[2])}, t=120))
    elif cmd == "seed":
        print(send({"cmd": "coop_seed", "idx": 0,
                    "path": apath(sys.argv[2])}, t=120))
    else:
        sys.exit(__doc__)
