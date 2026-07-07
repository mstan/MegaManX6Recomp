"""Phase 1 of TWEAKS_PREBAKE.md — the metadata bridge.

Classify every Tweaks option's writes into the pre-bake buckets and emit the
`[tweaks]` manifest the recompiler pass (Phase 3) + runtime loader (Phase 2)
consume. For each write we map its disc offset to the SLUS EXE address and bucket
it:

  disc     write OUTSIDE the SLUS EXE (art, game-data)            -> disc-image patch
  poke     write in the SLUS DATA section (game reads from RAM)   -> boot-time RAM poke
  param    write that changes ONLY an instruction's immediate     -> g_tweak_param[]
  guarded  write that changes an instruction's opcode/regs (logic)-> flag-selected variant

`disc`/`poke`/`param` need NO recompile (config/patch only); `guarded` is the
one-time dev-side bake surface. The param-vs-guarded split is decided per 4-byte
MIPS word: a diff confined to the low halfword (bytes 0-1, the immediate field) is
`param`; any diff in bytes 2-3 (opcode/rs/rt) is `guarded`.

CLI:
  python tools/tweaks_prebake.py summary
  python tools/tweaks_prebake.py manifest [--out manifest.json]
  python tools/tweaks_prebake.py selection '{"Var":true}' [--out tweaks.toml]
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import struct
import sys
from collections import OrderedDict
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


twr = _load("tweaks_resolver")
eng = _load("tweaks_engine")

RANGES = _ROOT / "generated-tweaks" / "SLUS_013.95_full.ranges"
SLUS_NAME = "SLUS_013.95"
SECT, USER, HDR = 2352, 2048, 24


# --------------------------------------------------------------------------
# SLUS geometry (locate the EXE on the disc, read its bytes, learn its RAM base)
# --------------------------------------------------------------------------
class Geometry:
    def __init__(self, vanilla: Path):
        with open(vanilla, "rb") as f:
            def lsec(lba):
                f.seek(lba * SECT + HDR)
                return f.read(USER)

            pvd = lsec(16)
            assert pvd[1:6] == b"CD001", "no ISO9660 PVD @ sector 16"
            root = pvd[156:156 + 34]
            root_lba = struct.unpack("<I", root[2:6])[0]
            root_len = struct.unpack("<I", root[10:14])[0]
            dird = bytearray()
            n = root_lba
            while len(dird) < root_len:
                dird += lsec(n)
                n += 1
            self.lba = self.size = None
            i = 0
            while i < len(dird):
                rlen = dird[i]
                if rlen == 0:
                    i = ((i // USER) + 1) * USER
                    continue
                rec = dird[i:i + rlen]
                nm = rec[33:33 + rec[32]].decode("latin1", "replace").split(";")[0].upper()
                if nm == SLUS_NAME:
                    self.lba = struct.unpack("<I", rec[2:6])[0]
                    self.size = struct.unpack("<I", rec[10:14])[0]
                    break
                i += rlen
            if self.lba is None:
                raise RuntimeError(f"{SLUS_NAME} not found in root dir")
            self.nsect = (self.size + USER - 1) // USER
            exe = bytearray()
            n = self.lba
            while len(exe) < self.size:
                exe += lsec(n)
                n += 1
            self.exe = bytes(exe[: self.size])       # extracted SLUS (header + image)
        self.load_addr = struct.unpack("<I", self.exe[0x18:0x1C])[0]

    def disc_to_ram(self, off: int):
        """Disc byte offset -> SLUS EXE RAM address, or None if outside the EXE image."""
        n = off // SECT
        p = off - (n * SECT + HDR)
        if self.lba <= n < self.lba + self.nsect and 0 <= p < USER:
            file_off = (n - self.lba) * USER + p
            return self.load_addr + (file_off - 2048) if file_off >= 2048 else None
        return None

    def vanilla_byte(self, ram: int):
        """Vanilla SLUS byte at a RAM address (from the EXE image)."""
        fo = 2048 + (ram - self.load_addr)
        return self.exe[fo] if 0 <= fo < len(self.exe) else None


# --------------------------------------------------------------------------
# Code map (recompiled function ranges from the .ranges manifest)
# --------------------------------------------------------------------------
class CodeMap:
    def __init__(self, ranges_path: Path):
        import bisect
        self._bisect = bisect
        txt = ranges_path.read_text()
        self.ranges = []
        self.funcs = []
        for ln in txt.splitlines():
            if ln.startswith("R "):
                _, lo, length = ln.split()
                self.ranges.append((int(lo, 16), int(lo, 16) + int(length, 16)))
            elif ln.startswith("F "):
                self.funcs.append(int(ln.split()[1], 16))
        self.ranges.sort()
        self.funcs.sort()
        self._lows = [a for a, _ in self.ranges]

    def is_code(self, addr: int) -> bool:
        i = self._bisect.bisect_right(self._lows, addr) - 1
        return i >= 0 and self.ranges[i][0] <= addr < self.ranges[i][1]

    def func_of(self, addr: int):
        i = self._bisect.bisect_right(self.funcs, addr) - 1
        return self.funcs[i] if i >= 0 else None


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------
def _db():
    return twr.TweaksDB(twr.DEFAULT_PATCHER_SRC)


def _base_set(db, base):
    """Writes present in EVERY build (the always-injected PatchList_Base hacks) —
    excluded from per-option classification and reported once as the tweaks base."""
    def wl(sel):
        m = OrderedDict(base)
        for k, v in twr.selection_to_overrides(cat_of(db), sel, db.options).items():
            m[str(k)] = str(v)
        return set(o for _, o in eng.build_writelist(db, m, base)[1])
    return wl({"IntroSkip03": True}) & wl({"HighJumpUnlimited01": True})


_CAT = None
def cat_of(db):
    global _CAT
    if _CAT is None:
        _CAT = twr.parse_gui_catalog(twr.DEFAULT_PATCHER_SRC, db)
    return _CAT


def _writes_for(db, base, sel):
    m = OrderedDict(base)
    for k, v in twr.selection_to_overrides(cat_of(db), sel, db.options).items():
        m[str(k)] = str(v)
    return eng.build_writelist(db, m, base)[1]


def classify_writes(geom: Geometry, cm: CodeMap, writes, base_set):
    """Bucket a list of (hexdata, disc_off) writes. Returns dict with lists:
      disc  : [(disc_off, hexbytes)]
      poke  : [(ram_addr, hexbytes)]       (SLUS data section)
      param : [(word_addr, van_word_hex, patched_word_hex)]   (immediate-only diff)
      guarded: [(word_addr, van_word_hex, patched_word_hex)]  (logic diff)
      funcs : set(func_entry) touched by guarded/param code writes
    """
    # 1. gather per-RAM patched bytes for SLUS writes; disc writes pass through
    patched = {}          # ram -> byte
    disc = []
    poke_bytes = {}       # ram -> byte (data section)
    for hexdata, off in writes:
        if off in base_set:
            continue
        data = bytes.fromhex(hexdata)
        for k, bval in enumerate(data):
            ram = geom.disc_to_ram(off + k)
            if ram is None:
                disc.append((off + k, bval))
                continue
            if cm.is_code(ram):
                patched[ram] = bval
            else:
                poke_bytes[ram] = bval
    # 2. collapse consecutive disc bytes back into runs
    disc_runs = _runs(disc)
    poke_runs = [(a, bytes(b).hex().upper()) for a, b in _runs_ram(poke_bytes)]
    # 3. classify code writes per 4-byte MIPS instruction word
    param, guarded, funcs = [], [], set()
    words = {}            # word_addr -> list of (offset_in_word, patched_byte)
    for ram, bval in patched.items():
        wa = ram & ~3
        words.setdefault(wa, []).append((ram - wa, bval))
    for wa in sorted(words):
        van = bytes(geom.vanilla_byte(wa + i) or 0 for i in range(4))
        pat = bytearray(van)
        for oiw, bval in words[wa]:
            pat[oiw] = bval
        van_hex, pat_hex = van.hex().upper(), bytes(pat).hex().upper()
        # little-endian word: bytes 0-1 = immediate (low halfword); 2-3 = opcode/rs/rt
        immediate_only = van[2:] == pat[2:] and van[:2] != pat[:2]
        entry = (wa, van_hex, pat_hex)
        (param if immediate_only else guarded).append(entry)
        f = cm.func_of(wa)
        if f is not None:
            funcs.add(f)
    return {"disc": disc_runs, "poke": poke_runs, "param": param,
            "guarded": guarded, "funcs": funcs}


def _runs(pairs):
    """[(off, byte)] (unsorted) -> [(start_off, hexbytes)] coalescing consecutive."""
    pairs = sorted(pairs)
    out, cur, start, prev = [], bytearray(), None, None
    for off, b in pairs:
        if start is not None and off == prev + 1:
            cur.append(b)
        else:
            if start is not None:
                out.append((start, bytes(cur).hex().upper()))
            cur, start = bytearray([b]), off
        prev = off
    if start is not None:
        out.append((start, bytes(cur).hex().upper()))
    return out


def _runs_ram(d):
    """{addr: byte} -> [(start, [bytes])] coalescing consecutive addrs."""
    out, cur, start, prev = [], [], None, None
    for a in sorted(d):
        if start is not None and a == prev + 1:
            cur.append(d[a])
        else:
            if start is not None:
                out.append((start, cur))
            cur, start = [d[a]], a
        prev = a
    if start is not None:
        out.append((start, cur))
    return out


def build_manifest(db, geom, cm):
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    base_set = _base_set(db, base)
    cat = cat_of(db)
    manifest = OrderedDict()
    for o in cat:
        v = o["var"]
        if o["type"] in ("checkbox", "radio"):
            sel = {v: True}
        elif o["type"] == "dropdownlist" and o.get("choices") and len(o["choices"]) > 1:
            sel = {v: "@1"}
        elif o["type"] in ("edit", "slider"):
            sel = {v: "5"}
        else:
            continue
        try:
            writes = _writes_for(db, base, sel)
        except Exception:
            continue
        c = classify_writes(geom, cm, writes, base_set)
        # bucket the OPTION by its heaviest requirement
        if c["guarded"]:
            bucket = "guarded"        # needs the one-time code bake
        elif c["param"]:
            bucket = "param"          # value immediate -> parameterize (one regen to insert)
        elif c["poke"]:
            bucket = "poke"           # data-section value -> boot poke (no recompile)
        elif c["disc"]:
            bucket = "disc"           # outside SLUS -> disc patch (no recompile)
        else:
            bucket = "noop"           # produces nothing alone (New Game combo context)
        manifest[v] = {
            "type": o["type"], "tab": o["tab_title"], "bucket": bucket,
            "n_disc": len(c["disc"]), "n_poke": len(c["poke"]),
            "n_param": len(c["param"]), "n_guarded": len(c["guarded"]),
            "funcs": sorted(f"0x{f:08X}" for f in c["funcs"]),
        }
    return manifest, base_set


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_summary(args):
    db = _db()
    geom = Geometry(twr.DEFAULT_VANILLA)
    cm = CodeMap(RANGES)
    man, base_set = build_manifest(db, geom, cm)
    from collections import Counter
    b = Counter(m["bucket"] for m in man.values())
    allfuncs = set()
    for m in man.values():
        allfuncs |= set(m["funcs"])
    print(f"SLUS load=0x{geom.load_addr:08X} size={geom.size} "
          f"code-ranges={len(cm.ranges)} funcs={len(cm.funcs)}")
    print(f"tweaks-base writes (always-on set): {len(base_set)}")
    print(f"\nOPTION BUCKETS (of {len(man)} classified):")
    order = ["disc", "poke", "param", "guarded", "noop"]
    label = {"disc": "DISC-data patch (no recompile)",
             "poke": "SLUS data poke (no recompile)",
             "param": "value immediate -> param (no recompile after 1 insert)",
             "guarded": "SLUS CODE -> guarded variant (one-time bake)",
             "noop": "no writes alone (New Game combo context)"}
    for k in order:
        print(f"  {b.get(k,0):4d}  {label[k]}")
    print(f"\nno-recompile options (disc+poke+param): "
          f"{b.get('disc',0)+b.get('poke',0)+b.get('param',0)}")
    print(f"one-time-bake options (guarded): {b.get('guarded',0)}  "
          f"touching {len(allfuncs)} distinct functions")


def cmd_manifest(args):
    db = _db()
    geom = Geometry(twr.DEFAULT_VANILLA)
    cm = CodeMap(RANGES)
    man, _ = build_manifest(db, geom, cm)
    out = json.dumps(man, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(man)} options)")
    else:
        print(out)


def cmd_selection(args):
    db = _db()
    geom = Geometry(twr.DEFAULT_VANILLA)
    cm = CodeMap(RANGES)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    base_set = _base_set(db, base)
    sel = json.loads(args.selection)
    writes = _writes_for(db, base, sel)
    c = classify_writes(geom, cm, writes, base_set)
    # emit a [tweaks] toml fragment (Phase-2 runtime loader input)
    lines = ["[tweaks]"]
    if c["guarded"]:
        lines.append("# guarded CODE variants (need the one-time recompiler bake):")
        for wa, van, pat in c["guarded"]:
            lines.append(f'#   0x{wa:08X}: {van} -> {pat}  (func {("0x%08X"%cm.func_of(wa))})')
    if c["param"]:
        lines.append("")
        for i, (wa, van, pat) in enumerate(c["param"]):
            van_imm = int(van[0:2] + van[2:4], 16)   # LE low halfword (display)
            pat_imm = int(pat[0:2] + pat[2:4], 16)
            lines.append(f'[[tweak.param]]  addr = 0x{wa:08X}  index = {i}  '
                         f'value = 0x{pat_imm:04X}   # was 0x{van_imm:04X}')
    if c["poke"]:
        lines.append("")
        for ram, hexb in c["poke"]:
            lines.append(f'[[tweak.poke]]   addr = 0x{ram:08X}  size = {len(hexb)//2}  '
                         f'value = "0x{hexb}"')
    toml = "\n".join(lines) + "\n"
    if c["disc"]:
        toml += f"\n# + {len(c['disc'])} disc-image patch run(s) (art/game-data, applied to the .bin)\n"
    if args.out:
        Path(args.out).write_text(toml, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(toml)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary")
    p = sub.add_parser("manifest"); p.add_argument("--out", default="")
    p = sub.add_parser("selection"); p.add_argument("selection"); p.add_argument("--out", default="")
    args = ap.parse_args()
    {"summary": cmd_summary, "manifest": cmd_manifest, "selection": cmd_selection}[args.cmd](args)


if __name__ == "__main__":
    main()
