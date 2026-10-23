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
    ("pitch_lookup", 0x8005DF40, 0x8005DFA8),
    ("pitch_convert", 0x8005DFA8, 0x8005E0C8),
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
    calls, indirect, indirect_jumps, external_jumps, external_branches, traps = [], [], [], [], [], []
    for offset in range(0, len(data), 4):
        word = struct.unpack_from("<I", data, offset)[0]
        address = start + offset
        if word >> 26 == 3:  # Direct JAL, including its instruction address.
            target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            calls.append(dict(site=f"{address:08X}", target=f"{target:08X}"))
        elif word >> 26 == 0 and word & 63 == 9:
            indirect.append(f"{address:08X}")
        elif word >> 26 == 0 and word & 63 == 8 and (word >> 21) & 31 != 31:
            indirect_jumps.append(f"{address:08X}")
        elif word >> 26 == 2:
            target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            if not start <= target < end:
                external_jumps.append(dict(site=f"{address:08X}", target=f"{target:08X}"))
        elif word >> 26 in (1, 4, 5, 6, 7):
            signed = (word & 65535) - (65536 if word & 32768 else 0)
            target = (address + 4 + signed * 4) & 0xFFFFFFFF
            if word >> 26 == 1 and (word >> 16) & 31 in (16, 17):
                calls.append(dict(site=f"{address:08X}", target=f"{target:08X}"))
            elif not start <= target < end:
                external_branches.append(dict(site=f"{address:08X}", target=f"{target:08X}"))
        elif word >> 26 == 0 and word & 63 in (12, 13):
            traps.append(dict(site=f"{address:08X}", kind="syscall" if word & 63 == 12 else "break"))
    return dict(name=name, start=f"{start:08X}", end_exclusive=f"{end:08X}",
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                direct_calls=calls, indirect_call_sites=indirect,
                indirect_jumps=indirect_jumps, external_jumps=external_jumps,
                external_branches=external_branches, trap_sites=traps)


def callback_evidence(exe):
    # Decode the actual startup LUI/ADDIU address pairs, not guessed BSS bounds.
    bounds = []
    for address, register in ((0x80054AD8, 2), (0x80054AE0, 3)):
        hi, low = exe.word(address), exe.word(address + 4)
        if (hi >> 26 != 15 or (hi >> 16) & 31 != register or low >> 26 != 9
                or (low >> 21) & 31 != register or (low >> 16) & 31 != register):
            raise ValueError("Startup address construction differs")
        signed = (low & 65535) - (65536 if low & 32768 else 0)
        bounds.append((((hi & 65535) << 16) + signed) & 0xFFFFFFFF)
    result = []
    for slot, activation, site in ((0x800E5520, 0x1E, 0x8005C0A8),
                                   (0x800E5398, 0x2A, 0x8005C0D4)):
        references = []
        for offset in range(0, exe.size, 4):
            word = struct.unpack_from("<I", exe.data, 2048 + offset)[0]
            # This is an encoded-immediate scan, not alias analysis. Do not
            # mistake its absence of stores for proof against computed writes.
            if word >> 26 in (8, 9, 12, 13, 14, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B) and word & 65535 == slot & 65535:
                references.append(dict(site=f"{exe.base + offset:08X}", opcode=word >> 26))
        result.append(dict(slot=f"{slot:08X}", startup_value=0,
            startup_zero_start=f"{bounds[0]:08X}", startup_zero_end_exclusive=f"{bounds[1]:08X}",
            zero_loop_store="80054AE8", conditional_call=f"{site:08X}",
            activation_metadata_offset=activation, argument="a0=voice (0..23)",
            return_value="ignored", encoded_immediate_references=references,
            later_nonzero_target="unresolved: computed/overlay writes not excluded"))
    return result


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
    return dict(format_version=2, exe_sha256=EXE_SHA256,
        evidence="Original native instructions manually traced; hashes and call sites reproduced mechanically",
        implementation_status="audit_only_no_runtime_fix", local_coop="unverified", netplay="unverified",
        routines=[routine_metadata(exe, *row) for row in ROUTINES],
        callback_evidence=callback_evidence(exe),
        ordinary_calculation_closure=dict(
            key_on=["explicit_key_on", "select_vab_program", "key_on_setup", "pitch_lookup", "pitch_convert", "sample_key_on_queue"],
            stop=["explicit_stop", "stop_queue"], volume=["explicit_volume"],
            excluded_branch="8005ACDC -> noise_key_on only when selected sample is 255; absent from frozen character tone slots",
            indirect_calls=[], flush_calls=[],
            trap_obligation="KEYON has native BREAK guards around gain division; require original nonnegative gains and valid guest inputs",
            scope="Native direct closure only; SDK replacement/dispatch failures and later computed writes are not proved absent"),
        native_regions=[dict(name=name, base=f"{base:08X}", stride=stride, count=count,
            end_exclusive=f"{base + stride * count:08X}", evidence=source)
            for name, base, stride, count, source in REGIONS],
        character_tones=tone_metadata(disc_path),
        remaining=["Callback slots are startup-zero with no explicit encoded-immediate assignments in the base EXE; resolve later computed/overlay assignments and nonzero targets if their metadata activation fields become nonzero.",
            "Native ordinary closure has no flush/indirect calls; qualify SDK uncharged dispatch and abnormal-escape handling before enabling an adapter.",
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
    print("20 native routine extents, ordinary call closure, 2 startup-zero callback slots; audio outcomes unverified")


if __name__ == "__main__":
    main()
