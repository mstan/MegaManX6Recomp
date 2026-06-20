#!/usr/bin/env python3
"""oshot.py - screenshot the oracle (psxref, port 4380) and convert to PNG in the recomp dir.
Optionally press buttons first.  Usage:
  python tools/oshot.py out.png                     # just screenshot
  python tools/oshot.py out.png 0xF7FF 6 3          # press mask for 6 frames, repeat 3x, then shot
"""
import socket, json, time, sys, os
from PIL import Image

PORT = 4380
PSXREF_DIR = r"F:\Projects\psxref"
OUT_DIR = r"F:\Projects\psxrecomp\MegaManX6Recomp"

def cmd(obj, port=PORT, wait=0.15):
    s = socket.socket(); s.settimeout(20)
    s.connect(("127.0.0.1", port))
    s.sendall(json.dumps(obj).encode()+b"\n")
    time.sleep(wait); buf=b""; s.settimeout(3)
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

def main():
    out = sys.argv[1] if len(sys.argv)>1 else "_orc.png"
    if len(sys.argv) > 2:
        mask = int(sys.argv[2],0)
        frames = int(sys.argv[3]) if len(sys.argv)>3 else 6
        reps = int(sys.argv[4]) if len(sys.argv)>4 else 1
        for _ in range(reps):
            cmd({"cmd":"press","buttons":mask,"frames":frames})
            time.sleep(0.4)
    bmp = os.path.join(PSXREF_DIR, "_oshot.bmp")
    r = cmd({"cmd":"screenshot_file","path":"_oshot.bmp"})
    time.sleep(0.2)
    dst = out if os.path.isabs(out) else os.path.join(OUT_DIR, out)
    try:
        Image.open(bmp).save(dst)
        print(f"saved {dst}  ({r.get('width')}x{r.get('height')})")
    except Exception as e:
        print("convert failed:", e, "raw:", r)

if __name__=="__main__":
    main()
