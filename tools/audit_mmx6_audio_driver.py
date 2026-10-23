#!/usr/bin/env python3
"""Read-only original X6 driver boundaries; metadata, never native audio assets."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from audit_mmx6_coop_audio import PLAYER_MEMBERS, digest, subassets
from inventory_mmx6_coop_content import Executable, EXE_SHA256
from mmx6_seamless_catalog import Disc

# End addresses are exclusive and include each return's delay slot. These are
# inspected original routines, not inferred X4 sizes or automatic function RE.
ROUTINES = (
    ("character_stop", 0x8001750C, 0x800175F0),
    ("explicit_key_on", 0x8005A9D4, 0x8005AD40),
    ("explicit_stop", 0x8005AD40, 0x8005ADB4),
    ("explicit_volume", 0x8005BC14, 0x8005BC98),
    ("key_on_setup", 0x8005BCA4, 0x8005BE6C),
    ("driver_flush", 0x8005BE94, 0x8005C358),
    ("mask_write", 0x8005C394, 0x8005C650),
    ("key_mask_write", 0x8005C714, 0x8005C8D0),
    ("transfer_gate", 0x8005D4A4, 0x8005D4E4),
    ("noise_key_on", 0x8005E0D4, 0x8005E63C),
    ("noise_clock", 0x8005E644, 0x8005E68C),
    ("stop_queue", 0x8005E6D4, 0x8005E794),
    ("sample_key_on_queue", 0x8005E794, 0x8005EC5C),
    ("select_vab_program", 0x8005FC94, 0x8005FD54),
    ("header_open_wrapper", 0x800601A4, 0x800601D8),
    ("header_open", 0x80060214, 0x80060600),
    ("body_transfer", 0x80060604, 0x80060788),
    ("transfer_complete", 0x80060884, 0x80060958),
)

REGIONS = (
    ("voice_metadata", 0x800E4E40, 0x38, 24, "8005ABF8..8005ACC8; init 8005D248..8005D36C"),
    ("voice_dirty", 0x800E5380, 1, 24, "8005BDBC,8005BE68,8005EB08; flush 8005C128..8005C238"),
    ("voice_register_mirror", 0x800E53A0, 0x10, 24, "8005BCA4/8005E794; init 8005D13C..8005D164"),
    ("voice_end_history", 0x800E5528, 4, 16, "8005BCEC..8005BD10; flush 8005BEC4..8005BFA8"),
    ("key_on_mask", 0x800E4E30, 2, 2, "8005EC10..8005EC2C; flush 8005C25C..8005C278"),
    ("noise_mask", 0x800E4E38, 2, 2, "8005EBE8..8005EC18; flush 8005C2CC..8005C2F8"),
    ("reverb_mask", 0x800E4E34, 2, 2, "8005EB70..8005EBCC; flush 8005C298..8005C2C8"),
    ("key_off_mask", 0x800E5568, 2, 2, "8005E758/8005E77C; flush 8005C23C..8005C258"),
)


def routine_metadata(exe, name, start, end):
    if start % 4 or end % 4 or end <= start:
        raise ValueError("Invalid audited routine extent")
    at = exe.offset(start, end - start)
    data = exe.data[at:at + end - start]
    if len(data) < 8 or struct.unpack_from("<I", data, len(data) - 8)[0] != 0x03E00008:
        raise ValueError("Audited extent must include terminal JR RA and delay slot")
    calls, indirect = [], []
    for offset in range(0, len(data), 4):
        word = struct.unpack_from("<I", data, offset)[0]
        address = start + offset
        if word >> 26 == 3:  # Direct JAL, including its instruction address.
            target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            calls.append(dict(site=f"{address:08X}", target=f"{target:08X}"))
        elif word >> 26 == 0 and word & 63 == 9:
            indirect.append(f"{address:08X}")
    return dict(name=name, start=f"{start:08X}", end_exclusive=f"{end:08X}",
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                direct_calls=calls, indirect_call_sites=indirect)


def tone_metadata(disc_path):
    result = []
    disc = Disc(str(disc_path))
    try:
        lba, dat_size = disc.files()["ROCK_X6.DAT"]
        table = disc.user(lba)
        for member, (name, expected) in PLAYER_MEMBERS.items():
            sector, size = struct.unpack_from("<II", table, member * 8)
            if sector < 1 or not 2048 <= size <= 2_000_000 or sector * 2048 + size > dat_size:
                raise ValueError("Player DAT extent is invalid")
            payload = b"".join(disc.user(lba + sector + i) for i in range((size + 2047) // 2048))[:size]
            if digest(payload) != expected:
                raise ValueError("Unsupported player member")
            assets = subassets(payload)
            for group, header_index in ((1, 11), (3, 13)):
                header = assets[header_index][1]
                pre = struct.unpack_from("<I", header)[0] & 0xFFFFFF
                programs = struct.unpack_from("<H", header, pre + 18)[0]
                # Native 8005AB98 reads tone+0x16; compact tone blocks are
                # 16 * 0x20 bytes per populated program in these VABs.
                values = [struct.unpack_from("<H", header, pre + 32 + 2048 + i * 32 + 22)[0]
                          for i in range(programs * 16)]
                result.append(dict(member=member, character=name, group=group,
                    header_sha256=digest(header), allocated_tone_slots=len(values),
                    sample_numbers=sorted(set(values)),
                    noise_sample_255_slots=[i for i, value in enumerate(values) if value == 255]))
    finally:
        disc.f.close()
    return result


def audit(exe_path, disc_path):
    data = Path(exe_path).read_bytes()
    if digest(data) != EXE_SHA256:
        raise ValueError("Require original SLUS-01395 USA v1.1 executable")
    exe = Executable(data)
    return dict(format_version=1, exe_sha256=EXE_SHA256,
        evidence="Original native instructions manually traced; hashes and call sites reproduced mechanically",
        implementation_status="audit_only_no_runtime_fix", local_coop="unverified", netplay="unverified",
        routines=[routine_metadata(exe, *row) for row in ROUTINES],
        native_regions=[dict(name=name, base=f"{base:08X}", stride=stride, count=count,
            end_exclusive=f"{base + stride * count:08X}", evidence=source)
            for name, base, stride, count, source in REGIONS],
        character_tones=tone_metadata(disc_path),
        remaining=["Resolve and bound flush callback targets at 800E5520 and 800E5398 and every scheduler entry to the flush.",
            "Prove uncharged isolated native calculation cannot flush/escape midway, including queued SPU write mode.",
            "Implement character-scoped status/stop/volume, global stop, VAB epoch and snapshot ownership, preserving music.",
            "Obtain native muted captures of sample identity, overlap, natural end, stop, load/retry/rematch and snapshot replay."])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--exe", type=Path, required=True)
    p.add_argument("--disc", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = audit(args.exe, args.disc)
    if args.check:
        if json.loads(args.out.read_text(encoding="utf-8")) != report:
            raise SystemExit("Driver evidence differs")
    else:
        with args.out.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
    print("18 native routine extents, 8 queue regions, 10 tone tables; audio outcomes unverified")


if __name__ == "__main__":
    main()
