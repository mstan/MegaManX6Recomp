#!/usr/bin/env python3
"""ramclaim.py - verify that a guest-RAM range is unclaimed by the running game.

Before an enhancement can park new state at a fixed guest address (a second
player actor, a relocated buffer, a scratch block), it must be proven that the
game itself never writes there. A static occupancy sample is not proof: the
dangerous writers are stage/overlay loads and boss transitions that a single
gameplay stretch never exercises.

This consumes the runtime's ALWAYS-ON RAM-write trace ring rather than arming a
capture around a workload. `arm` installs an address FILTER on that ring (up to
8 ranges) and should be run immediately at boot, before any stage load, so the
window covers everything that follows. `report` then queries the ring for what
it caught. There is no arm-run-dump race: the ring records continuously and is
read after the fact.

Generic - no per-game logic. Any game, any range.

Usage:
  python ramclaim.py arm 0x80180000:0x801B9000 [0x800EA000:0x800EB000 ...]
  python ramclaim.py report [--count 2048]
  python ramclaim.py ranges
  python ramclaim.py disarm
  python ramclaim.py --port 4490 report

Verdict semantics (report):
  CLEAN   - ring caught zero writes inside the armed ranges.
  CLAIMED - at least one write landed; every distinct writer PC is listed so the
            owning code can be identified before the address is trusted.
"""
import argparse
import json
import socket
import sys
import time
from collections import Counter

DEFAULT_PORT = 4490
PHYS_MASK = 0x1FFFFFFF


def send(port, obj, timeout=20.0, settle=0.15):
    """One JSON command -> one JSON reply. Mirrors tools/dbg.py's convention."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        s.sendall(json.dumps(obj).encode() + b"\n")
        time.sleep(settle)
        buf = b""
        s.settimeout(5)
        try:
            while True:
                chunk = s.recv(1 << 16)
                if not chunk:
                    break
                buf += chunk
                if buf.endswith(b"\n") and buf.count(b"{") <= buf.count(b"}"):
                    break
        except socket.timeout:
            pass
    finally:
        s.close()
    txt = buf.decode(errors="replace").strip()
    try:
        return json.loads(txt)
    except Exception:
        return {"ok": False, "error": "unparsable reply", "raw": txt[:400]}


def parse_range(spec):
    if ":" not in spec:
        raise SystemExit(f"bad range {spec!r}: expected LO:HI (e.g. 0x80180000:0x801B9000)")
    lo_s, hi_s = spec.split(":", 1)
    lo, hi = int(lo_s, 16), int(hi_s, 16)
    if hi <= lo:
        raise SystemExit(f"bad range {spec!r}: hi must exceed lo")
    return lo, hi


def cmd_arm(port, specs):
    ranges = [parse_range(s) for s in specs]
    if len(ranges) > 8:
        raise SystemExit("runtime supports at most 8 wtrace ranges")
    r = send(port, {"cmd": "wtrace_disarm_all"})
    if not r.get("ok"):
        print(f"warn: wtrace_disarm_all -> {r}")
    # Slot 0 via wtrace_range (it also clears other slots), extras via wtrace_add.
    for i, (lo, hi) in enumerate(ranges):
        cmd = "wtrace_range" if i == 0 else "wtrace_add"
        r = send(port, {"cmd": cmd, "lo": f"0x{lo:08X}", "hi": f"0x{hi:08X}"})
        ok = "ok" if r.get("ok") else f"FAILED {r}"
        print(f"  armed [0x{lo:08X}, 0x{hi:08X})  phys [0x{lo & PHYS_MASK:08X}, "
              f"0x{hi & PHYS_MASK:08X})  {ok}")
    # Clear any pre-existing entries so the window starts now, at boot.
    r = send(port, {"cmd": "wtrace_clear"})
    print(f"  ring cleared: {'ok' if r.get('ok') else r}")
    print("ARMED. Ring now records every write into these ranges, continuously.")


def cmd_ranges(port):
    print(json.dumps(send(port, {"cmd": "wtrace_ranges"}), indent=2))


def cmd_disarm(port):
    print(json.dumps(send(port, {"cmd": "wtrace_disarm_all"}), indent=2))


def iv(v):
    if isinstance(v, str):
        return int(v, 16) if v.startswith("0x") else int(v, 0)
    return int(v)


def report_one(port, lo, hi, count):
    """Verdict for ONE range, using the server-side address filter so the
    per-range answer is not diluted by a noisier neighbour range sharing the
    ring (the filter is applied over the FULL ring before the emit cap)."""
    r = send(port, {"cmd": "wtrace_dump", "count": count, "newest": 1,
                    "addr_lo": f"0x{lo:08X}", "addr_hi": f"0x{hi:08X}"})
    if not r.get("ok"):
        print(f"  [0x{lo:08X}, 0x{hi:08X}) ERROR: {r}")
        return None
    entries = [e for e in (r.get("entries") or [])
               if lo & PHYS_MASK <= iv(e.get("addr", 0)) < hi & PHYS_MASK]
    if not entries:
        print(f"  CLEAN   [0x{lo:08X}, 0x{hi:08X})  no writes observed")
        return True

    writers = Counter()
    addrs = Counter()
    frames = []
    for e in entries:
        writers[(str(e.get("pc", e.get("cpu_pc", "?"))), str(e.get("ra", "?")))] += 1
        try:
            addrs[iv(e["addr"])] += 1
        except Exception:
            pass
        if isinstance(e.get("frame"), int):
            frames.append(e["frame"])
    a_lo, a_hi = min(addrs), max(addrs)
    print(f"  CLAIMED [0x{lo:08X}, 0x{hi:08X})  {len(entries)} sampled writes, "
          f"{len(addrs)} distinct addrs")
    print(f"          touched phys 0x{a_lo:08X}..0x{a_hi:08X}"
          + (f"  frames {min(frames)}..{max(frames)}" if frames else ""))
    for (pc, ra), n in writers.most_common(6):
        print(f"          writer pc={pc:<12} ra={ra:<12} x{n}")
    return False


def cmd_report(port, count):
    ranges_reply = send(port, {"cmd": "wtrace_ranges"})
    armed = ranges_reply.get("ranges") or []
    head = send(port, {"cmd": "wtrace_dump", "count": 1, "newest": 1})
    total = head.get("total", 0)
    print(f"ring lifetime entries across all armed ranges: {total}")
    if not armed:
        print("no ranges armed - run `arm` first (at boot, before stage loads)")
        return 2

    print(f"\nper-range verdict ({len(armed)} armed):")
    verdicts = []
    for rg in armed:
        lo, hi = iv(rg.get("lo", 0)), iv(rg.get("hi", 0))
        # wtrace_ranges reports masked physical addresses; restore KSEG0 for display.
        if lo < 0x80000000:
            lo |= 0x80000000
        if hi < 0x80000000:
            hi |= 0x80000000
        verdicts.append(report_one(port, lo, hi, count))

    clean = [v for v in verdicts if v is True]
    print(f"\nsummary: {len(clean)}/{len(verdicts)} armed ranges CLEAN")
    if all(v is True for v in verdicts):
        print("A range is only proven against the transitions actually driven")
        print("while armed. Record which ones (boot/menu/stage-load/boss) in")
        print("the reservation note; an unexercised path is not evidence.")
        return 0
    print("At least one range is claimed - do NOT place enhancement state in a")
    print("CLAIMED range. Narrow the reservation to a CLEAN sub-range.")
    return 1


def cmd_holes(port, lo, hi, step, min_size, count):
    """Map the UNWRITTEN sub-ranges of a wide region.

    `report` answers "is this exact range free?"; this answers the more useful
    "where in this region could anything live at all?". The ring's address
    filter is applied server-side over the whole ring, so we sweep the region
    in sub-windows and union what each one caught -- that reaches entries a
    single newest-N query would never page back to.
    """
    touched = set()
    dma_hits = 0
    cpu_hits = 0
    windows = 0
    saturated = []
    a = lo
    while a < hi:
        b = min(a + step, hi)
        r = send(port, {"cmd": "wtrace_dump", "count": count, "newest": 1,
                        "addr_lo": f"0x{a:08X}", "addr_hi": f"0x{b:08X}"})
        windows += 1
        got = len(r.get("entries") or [])
        # A window that returns exactly the emit cap was TRUNCATED: the rest of
        # its writes were never returned, so any "unwritten" bytes inside it are
        # an artifact of the cap, not evidence. Must be reported, never silently
        # folded into the hole map.
        if got >= count:
            saturated.append((a, b, got))
        for e in (r.get("entries") or []):
            try:
                ad = iv(e["addr"])
            except Exception:
                continue
            if not (a & PHYS_MASK) <= ad < (b & PHYS_MASK):
                continue
            width = e.get("w", 4) or 4
            for k in range(0, width):
                touched.add(ad + k)
            if e.get("dma_ch", -1) is not None and e.get("dma_ch", -1) >= 0:
                dma_hits += 1
            else:
                cpu_hits += 1
        a = b

    print(f"swept [0x{lo:08X}, 0x{hi:08X}) in {windows} windows of 0x{step:X}")
    print(f"bytes observed written: {len(touched)}   "
          f"(dma-attributed entries {dma_hits}, cpu {cpu_hits})")
    if saturated:
        print(f"\n*** UNRELIABLE: {len(saturated)}/{windows} windows hit the "
              f"{count}-entry emit cap. ***")
        print("Those windows returned only their newest entries, so unwritten")
        print("bytes inside them are an ARTIFACT, not evidence. Re-run with a")
        print(f"smaller --step (try 0x{max(0x400, step // 4):X}) or larger --count.")
        for a, b, got in saturated[:6]:
            print(f"    saturated 0x{a:08X}..0x{b:08X} ({got} entries)")
        print("Hole list below is suppressed while any window is saturated.")
        return 2

    # Contiguous untouched runs, in physical space, reported as KSEG0.
    plo, phi = lo & PHYS_MASK, hi & PHYS_MASK
    runs = []
    run_start = None
    for addr in range(plo, phi, 4):
        hit = any((addr + k) in touched for k in range(4))
        if hit:
            if run_start is not None:
                runs.append((run_start, addr))
                run_start = None
        elif run_start is None:
            run_start = addr
    if run_start is not None:
        runs.append((run_start, phi))

    big = [(s, e) for s, e in runs if (e - s) >= min_size]
    big.sort(key=lambda se: se[1] - se[0], reverse=True)
    print(f"\nunwritten runs >= 0x{min_size:X} bytes: {len(big)}")
    for s, e in big[:16]:
        print(f"   0x{s | 0x80000000:08X} .. 0x{e | 0x80000000:08X}   "
              f"{e - s} bytes (0x{e - s:X})")
    if not big:
        print("   (none - every candidate sub-range was written)")
    print("\nCAVEAT: absence of a write only covers the code paths actually")
    print("driven while armed. CD-DMA load targets in particular vary per")
    print("stage/asset, so a hole seen in one stage is NOT a general guarantee.")
    return 0 if big else 1


def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arm", help="install range filter(s) on the always-on write ring")
    a.add_argument("ranges", nargs="+", metavar="LO:HI")
    sub.add_parser("ranges", help="show currently armed ranges")
    sub.add_parser("disarm", help="clear all armed ranges")
    rp = sub.add_parser("report", help="query the ring and print a verdict")
    rp.add_argument("--count", type=int, default=2048)
    hp = sub.add_parser("holes", help="map unwritten sub-ranges of a wide region")
    hp.add_argument("range", metavar="LO:HI")
    hp.add_argument("--step", default="0x4000",
                    help="sweep window size (default 0x4000)")
    hp.add_argument("--min-size", default="0x400",
                    help="smallest run to report (default 0x400)")
    hp.add_argument("--count", type=int, default=2048)
    args = ap.parse_args()

    if args.cmd == "arm":
        cmd_arm(args.port, args.ranges)
        return 0
    if args.cmd == "ranges":
        cmd_ranges(args.port)
        return 0
    if args.cmd == "disarm":
        cmd_disarm(args.port)
        return 0
    if args.cmd == "holes":
        lo, hi = parse_range(args.range)
        return cmd_holes(args.port, lo, hi, int(args.step, 16),
                         int(args.min_size, 16), args.count)
    return cmd_report(args.port, args.count)


if __name__ == "__main__":
    sys.exit(main())
