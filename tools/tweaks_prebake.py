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
# Guarded-variant bake (Phase 3): deterministic option->flag-bit assignment +
# per-site patched-word rows. v1 scope = checkbox/radio options that produce a
# GUARDED (logic) diff; dropdown multi-choice + edit/slider (param) are the
# documented follow-up on the same machinery.
# --------------------------------------------------------------------------
def _guarded_catalog(db, geom, cm, base, base_set):
    """Return (bits, rows): bits = {var: flag_bit} for every checkbox/radio option
    whose 'on' value patches instruction logic; rows = [(addr, van_word, bit,
    pat_word)] the recompiler bakes. Bit assignment is the sorted var order, so
    the bake manifest and the runtime `flag <n>` lines agree without a side channel."""
    def _is_cf(w):
        # Control-flow words cannot be represented as a per-instruction guarded
        # variant: translate_instruction emits mid-block statements only, and the
        # block structure is baked from vanilla, so a patched j/jal/branch can't
        # restructure control flow. Options that inject such words (acediez hooks
        # into new routines) must use the disc-patch / function-variant path.
        op = (w >> 26) & 0x3F
        if op in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            return True                       # regimm / j / jal / beq / bne / blez / bgtz
        if op == 0x00 and (w & 0x3F) in (0x08, 0x09):
            return True                       # jr / jalr
        return False

    cat = cat_of(db)
    per_opt = {}     # var -> [(addr, van_word, pat_word)]
    for o in cat:
        v, t = o["var"], o["type"]
        if t not in ("checkbox", "radio"):
            continue
        try:
            c = classify_writes(geom, cm, _writes_for(db, base, {v: True}), base_set)
        except Exception:
            continue
        if not c["guarded"]:
            continue
        sites = []
        cf = False
        for wa, van_hex, pat_hex in c["guarded"]:
            van_word = int.from_bytes(bytes.fromhex(van_hex), "little")
            pat_word = int.from_bytes(bytes.fromhex(pat_hex), "little")
            if _is_cf(pat_word):
                cf = True
                break
            sites.append((wa, van_word, pat_word))
        if cf:
            continue    # whole option excluded (has a control-flow injection site)
        per_opt[v] = sites
    bits = {v: i for i, v in enumerate(sorted(per_opt))}
    rows = []
    for v in sorted(per_opt):
        for addr, van_word, pat_word in per_opt[v]:
            rows.append((addr, van_word, bits[v], pat_word))
    rows.sort(key=lambda r: (r[0], r[2]))
    return bits, rows


def _param_catalog(db, geom, cm, base, base_set):
    """Return {addr: (index, imm_raw_u16, default_i32)} for every parameterizable
    value-immediate site across all options. Only real value opcodes are taken
    (addiu/addi/slti/sltiu/ori-li); masks, load/store offsets, control flow, and
    register-form (opcode 0) words are excluded. Index = sorted-addr order, so the
    bake manifest and the runtime `param <index>` lines agree without a side channel.
    The default is sign- or zero-extended per opcode so an unset param == vanilla."""
    SAFE = {0x08, 0x09, 0x0A, 0x0B}   # addi, addiu, slti, sltiu  (value opcodes)
    sites = {}   # addr -> (imm_raw, default)
    for o in cat_of(db):
        v, t = o["var"], o["type"]
        if t in ("checkbox", "radio"):
            sels = [{v: True}]
        elif t == "dropdownlist" and o.get("choices") and len(o["choices"]) > 1:
            sels = [{v: "@1"}]
        elif t in ("edit", "slider"):
            sels = [{v: "5"}]
        else:
            continue
        for sel in sels:
            try:
                c = classify_writes(geom, cm, _writes_for(db, base, sel), base_set)
            except Exception:
                continue
            for wa, van_hex, _pat in c["param"]:
                vw = int.from_bytes(bytes.fromhex(van_hex), "little")
                op = (vw >> 26) & 0x3F
                rs = (vw >> 21) & 0x1F
                imm = vw & 0xFFFF
                if op in SAFE:
                    default = imm - 0x10000 if (imm & 0x8000) else imm   # sign-extend
                elif op == 0x0D and rs == 0:                              # ori li-form
                    default = imm                                        # zero-extend
                else:
                    continue                                             # not parameterizable
                sites.setdefault(wa, (imm, default))
    return {wa: (i, sites[wa][0], sites[wa][1]) for i, wa in enumerate(sorted(sites))}


def cmd_bake(args):
    db = _db()
    geom = Geometry(twr.DEFAULT_VANILLA)
    cm = CodeMap(RANGES)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    base_set = _base_set(db, base)
    bits, rows = _guarded_catalog(db, geom, cm, base, base_set)
    params = _param_catalog(db, geom, cm, base, base_set)
    out = ["# tweaks_bake.toml — compile-free Tweaks guarded-variant manifest",
           "# (tweaks_prebake bake). Consumed by psxrecomp-game --tweaks-bake.",
           "format_version = 1", ""]
    out.append("# option -> flag bit (runtime `flag <n>` in tweaks.state selects it)")
    for v in sorted(bits):
        out.append(f"#   bit {bits[v]:3} = {v}")
    out.append("")
    for addr, van_word, bit, pat_word in rows:
        out.append("[[guarded]]")
        out.append(f'  addr = "0x{addr:08X}"')
        out.append(f'  van  = "0x{van_word:08X}"')
        out.append(f"  bit  = {bit}")
        out.append(f'  word = "0x{pat_word:08X}"')
    out.append("")
    out.append(f"# parameterized value immediates ({len(params)} sites): index -> addr")
    for addr, (idx, imm, default) in sorted(params.items(), key=lambda kv: kv[1][0]):
        out.append("[[param]]")
        out.append(f'  addr  = "0x{addr:08X}"')
        out.append(f"  index = {idx}")
        out.append(f'  imm   = "0x{imm:04X}"')
        out.append(f"  def   = {default}")
    text = "\n".join(out) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}  ({len(bits)} guarded options, {len(rows)} guarded rows, "
              f"{len(params)} param sites)")
    else:
        sys.stdout.write(text)


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


def cmd_state(args):
    """Emit the runtime `tweaks.state` file (the grammar tweak_runtime.c parses)
    for a selection. Guarded code variants are NOT applied at runtime (they need
    the Phase-3 bake) — their flag bits are emitted, plus param + poke directives
    that DO take effect immediately. Disc-only writes are noted, not emitted."""
    db = _db()
    geom = Geometry(twr.DEFAULT_VANILLA)
    cm = CodeMap(RANGES)
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    base_set = _base_set(db, base)
    sel = json.loads(args.selection)
    writes = _writes_for(db, base, sel)
    c = classify_writes(geom, cm, writes, base_set)
    out = ["# tweaks.state — runtime tweak directives (tweaks_prebake state).",
           "format_version=1"]
    # flags: one `flag <bit>` per ACTIVE guarded option, using the same bit
    # assignment the bake manifest baked (both from _guarded_catalog, so the
    # runtime selects exactly the variants the superset binary carries).
    bits, _rows = _guarded_catalog(db, geom, cm, base, base_set)
    def _active(val):
        if val in (False, 0, 0.0, None):
            return False
        if isinstance(val, str) and val.strip().lower() in ("", "0", "false", "off"):
            return False
        return True
    for v in sorted(sel):
        if v in bits and _active(sel[v]):
            out.append(f"flag {bits[v]}")
    # param overrides: use the SAME global index the bake assigned (so the runtime
    # writes the baked g_tweak_param[index] the superset reads), and sign/zero-extend
    # the patched value per opcode to match the emitted read.
    pcat = _param_catalog(db, geom, cm, base, base_set)   # {addr: (index, imm, default)}
    for wa, van, pat in c["param"]:
        if wa not in pcat:
            continue                                      # not a baked (safe-opcode) param site
        pw = int.from_bytes(bytes.fromhex(pat), "little")
        op = (pw >> 26) & 0x3F; rs = (pw >> 21) & 0x1F; pimm = pw & 0xFFFF
        if op in (0x08, 0x09, 0x0A, 0x0B):
            val = pimm - 0x10000 if (pimm & 0x8000) else pimm
        elif op == 0x0D and rs == 0:
            val = pimm
        else:
            continue
        out.append(f"param {pcat[wa][0]} {val}")
    # Chunk poke runs to <=32 bytes/line (bounded line length; the runtime applies
    # many pokes at consecutive addresses identically to one long run).
    CHUNK = 32
    for ram, hexb in c["poke"]:
        nb = len(hexb) // 2
        for off in range(0, nb, CHUNK):
            seg = hexb[off * 2:(off + CHUNK) * 2]
            out.append(f"poke 0x{ram + off:08X} {seg}")
    text = "\n".join(out) + "\n"
    if c["disc"]:
        text += f"# note: + {len(c['disc'])} disc-image patch run(s) (handled by the disc, not this file)\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}  (guarded={len(c['guarded'])} param={len(c['param'])} "
              f"poke={len(c['poke'])} disc={len(c['disc'])})")
    else:
        sys.stdout.write(text)


def cmd_artdisc(args):
    """Produce an ART-ONLY patched disc (<stock-stem>.tweaks.bin + .tweaks.cue) for
    a selection: vanilla + art file-inserts only, NO code. The recomp mounts it via
    disc-swap (resolve_tweaks_disc_sibling in main.cpp). Fail-closed on scratch-
    region inserts (code-injection class) unless --allow-scratch."""
    db = _db()
    base = OrderedDict(twr.load_profile(twr.DEFAULT_PROFILE))
    json.loads(args.selection)  # validate it is JSON before the heavy path
    merged = eng.merged_profile(db, args.selection)
    vanilla = Path(args.vanilla) if args.vanilla else Path(twr.DEFAULT_VANILLA)

    # Output next to the STOCK disc (--stock-disc) so disc-swap finds the sibling;
    # default = beside the vanilla the engine used. The sibling stem MUST equal the
    # stock disc filename stem the runtime resolves.
    stock = Path(args.stock_disc) if args.stock_disc else vanilla
    out_bin = stock.parent / (stock.stem + ".tweaks.bin")
    if args.out:
        out_bin = Path(args.out)

    report = eng.apply_art_only(db, merged, base, out_bin, vanilla=vanilla,
                                error_recalc=not args.no_ecc,
                                allow_scratch=args.allow_scratch)

    # Emit the sibling cue referencing the .tweaks.bin (single MODE2/2352 track,
    # matching the stock cue this game ships).
    cue = out_bin.with_suffix(".cue")
    cue.write_text(
        f'FILE "{out_bin.name}" BINARY\n'
        f'  TRACK 01 MODE2/2352\n'
        f'    INDEX 01 00:00:00\n', encoding="utf-8")

    print(f"wrote {out_bin}  ({out_bin.stat().st_size} bytes)")
    print(f"wrote {cue}")
    print(f"  inserts={len(report['inserts'])}  dropped_code_writes="
          f"{report['dropped_code_writes']}  scratch={report['scratch']}")
    for ins in report["inserts"]:
        print(f"    {ins['var']:22} off=0x{ins['off']:08X} size={ins['size']:7d} "
              f"[{ins['region']}]  {Path(ins['src']).name}")


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
    p = sub.add_parser("state"); p.add_argument("selection"); p.add_argument("--out", default="")
    p = sub.add_parser("bake"); p.add_argument("--out", default="")
    p = sub.add_parser("artdisc")
    p.add_argument("selection")
    p.add_argument("--out", default="", help="explicit output .bin path (default: <stock-stem>.tweaks.bin)")
    p.add_argument("--stock-disc", default="", help="stock disc the runtime mounts; sibling is written beside it")
    p.add_argument("--vanilla", default="", help="vanilla BIN source (default: engine DEFAULT_VANILLA)")
    p.add_argument("--allow-scratch", action="store_true", help="write scratch-region inserts anyway (will not render)")
    p.add_argument("--no-ecc", action="store_true", help="skip error_recalc EDC/ECC recompute (debug only)")
    args = ap.parse_args()
    {"summary": cmd_summary, "manifest": cmd_manifest,
     "selection": cmd_selection, "state": cmd_state, "bake": cmd_bake,
     "artdisc": cmd_artdisc}[args.cmd](args)


if __name__ == "__main__":
    main()
