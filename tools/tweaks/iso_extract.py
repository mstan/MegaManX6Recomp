#!/usr/bin/env python3
# Extract a named file from a PSX MODE2/2352 BIN via ISO9660 walk.
# Usage: iso_extract.py <bin> <NAME> <out>
import sys, struct

SECT = 2352
USER = 2048
HDR  = 24     # 12 sync + 4 header + 8 subheader

def logical_sector(binf, lba):
    binf.seek(lba*SECT + HDR)
    return binf.read(USER)

def read_bytes(binf, lba, size):
    out = bytearray()
    n = lba
    while len(out) < size:
        out += logical_sector(binf, n)
        n += 1
    return bytes(out[:size])

def find_in_dir(binf, dir_lba, dir_size, target):
    data = read_bytes(binf, dir_lba, dir_size)
    i = 0
    target = target.upper()
    while i < len(data):
        rlen = data[i]
        if rlen == 0:
            # advance to next logical sector boundary
            i = ((i // USER) + 1) * USER
            if i >= len(data): break
            continue
        rec = data[i:i+rlen]
        ext_lba = struct.unpack('<I', rec[2:6])[0]
        ext_len = struct.unpack('<I', rec[10:14])[0]
        name_len = rec[32]
        name = rec[33:33+name_len].decode('latin1', 'replace')
        base = name.split(';')[0].upper()
        if base == target:
            return ext_lba, ext_len
        i += rlen
    return None

def main():
    binp, name, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(binp, 'rb') as f:
        pvd = logical_sector(f, 16)
        assert pvd[1:6] == b'CD001', "no ISO9660 PVD @ sector 16"
        root = pvd[156:156+34]
        root_lba = struct.unpack('<I', root[2:6])[0]
        root_len = struct.unpack('<I', root[10:14])[0]
        hit = find_in_dir(f, root_lba, root_len, name)
        if not hit:
            print(f"!! {name} not found in root dir (lba={root_lba} len={root_len})")
            sys.exit(1)
        lba, length = hit
        print(f"{name}: LBA={lba} size={length} bytes")
        data = read_bytes(f, lba, length)
    with open(outp, 'wb') as o:
        o.write(data)
    print(f"wrote {len(data)} bytes -> {outp}")
    # PS-X EXE header sanity
    print("magic:", data[:8])

main()
