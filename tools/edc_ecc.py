"""CD-ROM Mode 2 Form 1 EDC/ECC recompute - clean-room, pure Python.

Written from the published CD-ROM standard (ECMA-130, 2nd edition: clause 14
"Data field of a sector" and Annex A "Error detection and correction codes"),
not from any existing implementation. The EDC CRC polynomial and the P/Q
Reed-Solomon product-code geometry are specified in that standard; a
from-specification implementation is not a derivative work of anyone's code.

This replaces the external error_recalc.exe (GPLv3-or-later, derived from
Neill Corlett's EDC/ECC code) that the MMX6 Tweaks apply path used to invoke,
leaving that path with no GPL dependency.

Sector layout, Mode 2 Form 1 (ECMA-130 clause 14.4), 2352 bytes:

    0    .. 11    sync            00 FF FF FF FF FF FF FF FF FF FF 00
    12   .. 15    header          min, sec, frame, mode(=2)
    16   .. 23    subheader       file, channel, submode, coding  (twice)
    24   .. 2071  user data       2048 bytes
    2072 .. 2075  EDC             CRC-32, little endian
    2076 .. 2247  P parity        172 bytes
    2248 .. 2351  Q parity        104 bytes

EDC covers bytes 16..2071 (subheader + user data). The ECC covers bytes
12..2075 (header + subheader + user data + EDC) with the 4 header bytes taken
as zero, which is what makes a Mode 2 Form 1 sector's ECC independent of its
own address.
"""

from __future__ import annotations

__all__ = [
    "SECTOR_SIZE", "recompute_sector", "recompute_image", "recompute_ranges",
    "is_mode2_form1", "edc_block", "SYNC",
]

SECTOR_SIZE = 2352
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"

# --------------------------------------------------------------------------
# EDC: CRC-32 with the ECMA-130 Annex A generator polynomial
#
#   P(x) = (x^16 + x^15 + x^2 + 1) * (x^16 + x^2 + x + 1)
#        =  x^32 + x^31 + x^16 + x^15 + x^4 + x^3 + x + 1
#
# which is 0x8001801B with the x^32 term implicit. The standard processes the
# data least-significant-bit first and stores the remainder little-endian, so
# the table is built from the bit-reversed polynomial.
# --------------------------------------------------------------------------
_EDC_POLY_REFLECTED = 0xD8018001


def _build_edc_table() -> list[int]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ (_EDC_POLY_REFLECTED if crc & 1 else 0)
        table.append(crc)
    return table


_EDC_TABLE = _build_edc_table()


def edc_block(data: bytes) -> int:
    """CRC-32 (ECMA-130 Annex A) over data; initial and final value zero."""
    crc = 0
    table = _EDC_TABLE
    for byte in data:
        crc = table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc & 0xFFFFFFFF


# --------------------------------------------------------------------------
# GF(2^8) with the ECMA-130 Annex A primitive polynomial
#
#   p(x) = x^8 + x^4 + x^3 + x^2 + 1   (0x11D)
# --------------------------------------------------------------------------
_GF_POLY = 0x11D


def _xtime(value: int) -> int:
    """Multiply by the field generator alpha (i.e. by x), reducing mod p(x)."""
    value <<= 1
    if value & 0x100:
        value ^= _GF_POLY
    return value & 0xFF


_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_acc = 1
for _i in range(255):
    _GF_EXP[_i] = _acc
    _GF_LOG[_acc] = _i
    _acc = _xtime(_acc)
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _gf_inv(a: int) -> int:
    return _GF_EXP[255 - _GF_LOG[a]]


# alpha^1 ^ alpha^0 == 3; the two-symbol parity solve divides by this constant.
_INV_ALPHA_PLUS_ONE = _gf_inv(0x03)

# Multiply-by-alpha as a table; the inner parity loop is the hot path.
_XTIME = [_xtime(i) for i in range(256)]


# --------------------------------------------------------------------------
# P/Q parity geometry (ECMA-130 clause 14.4.3 and Annex A)
#
# The 2064 protected bytes are read as 1032 16-bit words, and the code is
# applied independently to the low and the high byte of every word (two
# "planes"). Working directly on the interleaved bytes, a vector's members
# are reached by starting at (major // 2) * major_mult + (major % 2) and
# stepping minor_inc, wrapping at major_count * minor_count:
#
#   P: 43 columns x 2 planes = 86 vectors of 24 bytes, stride 86 (one row),
#      over the 2064 protected bytes.
#   Q: 26 diagonals x 2 planes = 52 vectors of 43 bytes, stride 88 (44 words),
#      over the 2064 protected bytes plus the 172 P-parity bytes = 2236.
#
# Each vector gets two Reed-Solomon parity bytes appended, giving 86*2 = 172
# P bytes and 52*2 = 104 Q bytes.
# --------------------------------------------------------------------------
_P_GEOM = (86, 24, 2, 86)     # major_count, minor_count, major_mult, minor_inc
_Q_GEOM = (52, 43, 86, 88)

_ECC_BASE = 12                # first protected byte (the header)
_P_DEST = 2076
_Q_DEST = 2248


def _parity_pass_scalar(buf: bytearray, base: int, dest: int, geom) -> None:
    """Reference implementation: solve each vector's parity one at a time.

    Kept as the readable statement of the code and as the oracle the fast
    path below is tested against; ``recompute_sector`` uses the fast path.

    buf[base : base + major_count*minor_count] holds the protected bytes.
    """
    major_count, minor_count, major_mult, minor_inc = geom
    size = major_count * minor_count
    xt = _XTIME
    for major in range(major_count):
        index = (major // 2) * major_mult + (major % 2)
        # sum_d  = sum(d_i)                  -> syndrome S0 contribution
        # horner = sum(alpha^(k-1-i) * d_i)  -> syndrome S1 contribution
        sum_d = 0
        horner = 0
        for _ in range(minor_count):
            value = buf[base + index]
            sum_d ^= value
            horner = xt[horner] ^ value
            index += minor_inc
            if index >= size:
                index -= size
        # Codeword v = (d_0 .. d_{k-1}, p_0, p_1) must satisfy
        #     S0: p_0 ^ p_1       = sum_d
        #     S1: alpha*p_0 ^ p_1 = alpha^2 * horner
        # so  (alpha ^ 1) * p_0 = sum_d ^ alpha^2*horner, i.e. 3 * p_0 = ...
        s1 = xt[xt[horner]]
        p0 = _gf_mul(sum_d ^ s1, _INV_ALPHA_PLUS_ONE)
        buf[dest + major] = p0
        buf[dest + major + major_count] = p0 ^ sum_d


# --------------------------------------------------------------------------
# Fast path: same arithmetic, one whole parity row at a time.
#
# Every vector of a pass consumes its k-th member at the same step, so the
# Horner recurrence can run across all of a pass's vectors at once, on rows
# of major_count bytes: multiply-by-alpha becomes bytes.translate over a
# 256-byte table and the XOR becomes one big-integer XOR. That turns ~4300
# interpreted iterations per sector into ~70 C-level operations, which is
# what makes a whole-image recompute practical in pure Python.
# --------------------------------------------------------------------------
_XTIME_TABLE = bytes(_XTIME)
_MUL_INV3_TABLE = bytes(_gf_mul(i, _INV_ALPHA_PLUS_ONE) for i in range(256))


def _build_gathers(geom):
    """Per-step byte gatherers for one pass, as (kind, payload) pairs.

    A step whose members are consecutive in the buffer is a plain slice; the
    rest use an operator.itemgetter over precomputed absolute indices.
    """
    from operator import itemgetter

    major_count, minor_count, major_mult, minor_inc = geom
    size = major_count * minor_count
    steps = []
    for minor in range(minor_count):
        indices = []
        for major in range(major_count):
            index = (major // 2) * major_mult + (major % 2)
            index = (index + minor * minor_inc) % size
            indices.append(_ECC_BASE + index)
        first = indices[0]
        if indices == list(range(first, first + major_count)):
            steps.append(("slice", slice(first, first + major_count)))
        else:
            steps.append(("gather", itemgetter(*indices)))
    return tuple(steps)


_P_STEPS = _build_gathers(_P_GEOM)
_Q_STEPS = _build_gathers(_Q_GEOM)


def _parity_pass(buf: bytearray, dest: int, steps, major_count: int) -> None:
    """Fill the two parity rows at ``dest`` for one code pass."""
    width = major_count
    sum_d = 0
    horner = bytes(width)
    for kind, payload in steps:
        row = bytes(buf[payload]) if kind == "slice" else bytes(payload(buf))
        value = int.from_bytes(row, "big")
        sum_d ^= value
        horner = (int.from_bytes(horner.translate(_XTIME_TABLE), "big")
                  ^ value).to_bytes(width, "big")
    # s1 = alpha^2 * horner
    s1 = horner.translate(_XTIME_TABLE).translate(_XTIME_TABLE)
    sum_row = sum_d.to_bytes(width, "big")
    p0 = (sum_d ^ int.from_bytes(s1, "big")).to_bytes(width, "big")
    p0 = p0.translate(_MUL_INV3_TABLE)
    buf[dest:dest + width] = p0
    buf[dest + width:dest + 2 * width] = (
        int.from_bytes(p0, "big") ^ sum_d).to_bytes(width, "big")


def is_mode2_form1(sector) -> bool:
    """True if sector is a Mode 2 Form 1 sector carrying EDC/ECC."""
    if len(sector) < SECTOR_SIZE:
        return False
    if bytes(sector[0:12]) != SYNC:
        return False
    if sector[15] != 0x02:
        return False
    # Subheader submode bit 5 selects Form 2, which has no P/Q parity.
    return not (sector[18] & 0x20)


def recompute_sector(sector: bytearray) -> bool:
    """Recompute EDC and P/Q parity for one Mode 2 Form 1 sector, in place.

    Returns True if the sector was rewritten, False if it is not a Mode 2
    Form 1 sector (audio, Form 2, or an unrecognised sector is left alone).
    """
    if len(sector) != SECTOR_SIZE:
        raise ValueError(f"sector must be {SECTOR_SIZE} bytes, got {len(sector)}")
    if not is_mode2_form1(sector):
        return False

    crc = edc_block(bytes(sector[16:2072]))
    sector[2072:2076] = crc.to_bytes(4, "little")

    # The ECC treats the 4 header bytes as zero; stash and restore them.
    header = bytes(sector[12:16])
    sector[12:16] = b"\x00\x00\x00\x00"
    try:
        _parity_pass(sector, _P_DEST, _P_STEPS, _P_GEOM[0])  # P over header+data+EDC
        _parity_pass(sector, _Q_DEST, _Q_STEPS, _Q_GEOM[0])  # Q over that plus P
    finally:
        sector[12:16] = header
    return True


def recompute_sector_reference(sector: bytearray) -> bool:
    """``recompute_sector`` via the scalar reference parity pass (test oracle)."""
    if len(sector) != SECTOR_SIZE:
        raise ValueError(f"sector must be {SECTOR_SIZE} bytes, got {len(sector)}")
    if not is_mode2_form1(sector):
        return False
    crc = edc_block(bytes(sector[16:2072]))
    sector[2072:2076] = crc.to_bytes(4, "little")
    header = bytes(sector[12:16])
    sector[12:16] = b"\x00\x00\x00\x00"
    try:
        _parity_pass_scalar(sector, _ECC_BASE, _P_DEST, _P_GEOM)
        _parity_pass_scalar(sector, _ECC_BASE, _Q_DEST, _Q_GEOM)
    finally:
        sector[12:16] = header
    return True


def recompute_image(path, *, verify_only: bool = False, progress=None) -> dict:
    """Recompute (or, with verify_only, check) every sector of a BIN image.

    Returns {"sectors", "form1", "changed", "skipped"}. changed counts Form 1
    sectors whose EDC/ECC bytes differed from the recomputed values - with
    verify_only nothing is written, which makes this a self-check against any
    known-good image.
    """
    import os

    mode = "rb" if verify_only else "r+b"
    stats = {"sectors": 0, "form1": 0, "changed": 0, "skipped": 0}
    total = os.path.getsize(path)
    if total % SECTOR_SIZE:
        raise ValueError(f"{path}: size {total} is not a multiple of {SECTOR_SIZE}")
    count = total // SECTOR_SIZE
    with open(path, mode) as handle:
        for index in range(count):
            handle.seek(index * SECTOR_SIZE)
            raw = handle.read(SECTOR_SIZE)
            stats["sectors"] += 1
            sector = bytearray(raw)
            if not recompute_sector(sector):
                stats["skipped"] += 1
                continue
            stats["form1"] += 1
            if sector != raw:
                stats["changed"] += 1
                if not verify_only:
                    handle.seek(index * SECTOR_SIZE + 2072)
                    handle.write(bytes(sector[2072:]))
            if progress and index and index % 20000 == 0:
                progress(index, count, stats)
    return stats


def recompute_ranges(path, ranges, *, require_form1: bool = True) -> dict:
    """Recompute EDC/ECC for exactly the sectors that ``ranges`` touch.

    ``ranges`` is an iterable of ``(offset, length)`` byte spans that were
    written into the image. Every sector any span overlaps is recomputed; no
    other sector in the image is read or written, so sectors the caller did
    not modify keep their original bytes even if they were already
    inconsistent (a deliberately corrupt protection sector, say).

    ``require_form1`` raises if a touched sector is not Mode 2 Form 1, which
    means the caller wrote somewhere it did not intend to.

    Returns ``{"sectors", "changed"}``.
    """
    import os

    total = os.path.getsize(path)
    count = total // SECTOR_SIZE
    todo = set()
    for offset, length in ranges:
        if length <= 0:
            continue
        first = offset // SECTOR_SIZE
        last = (offset + length - 1) // SECTOR_SIZE
        if last >= count:
            raise ValueError(
                f"{path}: write at {offset}+{length} runs past the last sector")
        todo.update(range(first, last + 1))

    stats = {"sectors": len(todo), "changed": 0}
    if not todo:
        return stats
    with open(path, "r+b") as handle:
        for index in sorted(todo):
            handle.seek(index * SECTOR_SIZE)
            raw = handle.read(SECTOR_SIZE)
            sector = bytearray(raw)
            if not recompute_sector(sector):
                if require_form1:
                    raise ValueError(
                        f"{path}: sector {index} was written but is not Mode 2 "
                        "Form 1; the write landed outside a data region")
                continue
            if sector != raw:
                stats["changed"] += 1
                handle.seek(index * SECTOR_SIZE + 2072)
                handle.write(bytes(sector[2072:]))
    return stats


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Recompute CD-ROM Mode 2 Form 1 EDC/ECC in a BIN image "
                    "(clean-room replacement for error_recalc).")
    parser.add_argument("image", help="raw 2352-byte-sector BIN image")
    parser.add_argument("--verify", action="store_true",
                        help="report mismatching sectors without writing")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    def progress(done, count, stats):
        if not args.quiet:
            print(f"  {done}/{count} sectors, {stats['changed']} differing",
                  flush=True)

    stats = recompute_image(args.image, verify_only=args.verify,
                            progress=progress)
    if not args.quiet:
        verb = "mismatched" if args.verify else "rewritten"
        print(f"{args.image}: {stats['sectors']} sectors, "
              f"{stats['form1']} Mode 2 Form 1, {stats['skipped']} skipped, "
              f"{stats['changed']} {verb}")
    if args.verify and stats["changed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
