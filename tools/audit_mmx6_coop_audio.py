#!/usr/bin/env python3
"""Read-only SLUS-01395 v1.1 character bank/driver audit; emits metadata only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from inventory_mmx6_coop_content import Executable, EXE_SHA256
from mmx6_seamless_catalog import Disc

PLAYER_MEMBERS = {
    85: ("Zero", "25f558d69e38e5f170b3325e27dc49a8232860f97d97dfeb6a0ce5306364f1c8"),
    86: ("Ultimate X", "2cb904ce44014592c5b881bc9f37a75262374eb74d601fffdb018eea9f856c4c"),
    87: ("Falcon X", "d41601a3c9a38463b3725fde5f01d7850af6d829b49dae1b162ddc3a7e3f88ac"),
    88: ("Shadow X", "b7d6eb7c0cc7abc97df61a7eedbdd3fe2ffc5fbbb237be905bd7b38341be0664"),
    89: ("Blade X", "43d65433299185f5ff6289a108d8f2d4f56769c9da2609252507f16e43f78e2f"),
}
CALLS = ((0x80015AFC, 0x800601A4, "native header-open wrapper"),
         (0x80016D0C, 0x80017008, "alternate record routing"),
         (0x80016D1C, 0x80016D34, "direct sound record routing"),
         (0x80016E7C, 0x8005A794, "VAB/program/tone metadata lookup"),
         (0x80016EF4, 0x80055B14, "original SPU voice status"),
         (0x80016F20, 0x8005A9D4, "explicit voice key-on path, idle slot"),
         (0x80016F78, 0x8005A9D4, "explicit voice key-on path, priority replacement"),
         (0x8005ACC4, 0x8005BCA4, "downstream driver mutation; isolation contract pending"),
         (0x8005ACEC, 0x8005DF40, "downstream pitch path; native qualification pending"),
         (0x8005ACF8, 0x8005E794, "downstream driver call; native qualification pending"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def subassets(data):
    if len(data) < 2048:
        raise ValueError("Truncated DAT member")
    count, total = struct.unpack_from("<II", data)
    if count > 255 or total != len(data):
        raise ValueError("Invalid DAT subasset table")
    at, assets = 2048, []
    for i in range(count):
        kind, size = struct.unpack_from("<II", data, 8 + i * 8)
        if size > len(data) - at:
            raise ValueError("DAT subasset escapes its member")
        assets.append((kind, data[at:at + size]))
        at += (size + 2047) & ~2047
    if at != len(data):
        raise ValueError("DAT member has unaccounted bytes")
    return assets


def bank_metadata(header, samples, group):
    if len(header) < 8:
        raise ValueError("Truncated sound preheader")
    tagged_offset, body_size = struct.unpack_from("<II", header)
    offset = tagged_offset & 0xFFFFFF
    if (tagged_offset >> 24 != group or offset < 8 or offset % 4
            or offset + 32 > len(header) or header[offset:offset + 4] != b"pBAV"):
        raise ValueError("Invalid sound preheader/VAB offset")
    if not samples or len(samples) % 16 or body_size != len(samples):
        raise ValueError("Original sample body size/alignment mismatch")
    version, vab_id, file_size = struct.unpack_from("<III", header, offset + 4)
    programs, tones, vags = struct.unpack_from("<HHH", header, offset + 18)
    if (version != 7 or not 1 <= programs <= 128 or vags > 255
            or offset + 32 + 2048 + programs * 512 + 512 != len(header)
            or file_size != len(header) - offset + len(samples)):
        raise ValueError("VAB metadata extent differs from original format")
    records = []
    for index, at in enumerate(range(8, offset, 4)):
        bank, program, tone_priority, voices = header[at:at + 4]
        records.append(dict(index=index, empty=not any(header[at:at + 4]),
            vab_handle=bank & 63, routing=bank >> 6, program=program & 127,
            program_high_bit=program >> 7, tone_start=tone_priority >> 4,
            priority=tone_priority & 15, first_voice=voices & 31,
            additional_voices=(voices >> 5) & 3, flags_high_bit=voices >> 7))
    return dict(group=group, preheader_bytes=offset, header_bytes=len(header),
        sample_bytes=len(samples), header_sha256=digest(header), sample_sha256=digest(samples),
        vab_version=version, original_vab_id=vab_id, program_count=programs,
        tone_count=tones, sample_count=vags,
        referenced_vab_handles=sorted({r["vab_handle"] for r in records if not r["empty"]}),
        cross_bank_records=[r["index"] for r in records if not r["empty"] and r["vab_handle"] != group],
        sound_records=records, status="unverified")


def audit(exe_path, disc_path):
    data = exe_path.read_bytes()
    if digest(data) != EXE_SHA256:
        raise ValueError("Require original SLUS-01395 USA v1.1 executable")
    exe = Executable(data)
    calls = []
    for site, target, role in CALLS:
        if exe.word(site) != 0x0C000000 | ((target >> 2) & 0x03FFFFFF):
            raise ValueError("Native audio call guard differs")
        calls.append(dict(site=f"{site:08X}", target=f"{target:08X}", role=role))
    report = dict(format_version=1, source="SLUS-01395 USA v1.1 original inputs",
        exe_sha256=digest(data), game_candidate="1d6f67c",
        frozen_x4=dict(commit="50593bca772b600de6911cbfecd40b0f08721147",
                       file="src/mods/mmx4_coop_audio.c", git_blob="f490a1725aac5775a3e6711305370c279362dceb"),
        native_calls=calls, player_banks=[],
        state_observations=dict(sound_group_status="80090D50",
            sound_record_end="80097738", sound_records="80097778",
            current_sound_record="800E155C", sound_priorities="800E25E0",
            vab_status="800E5690", selected_program_table="800E5654",
            selected_tone_table="800E5660", keyon_reentrancy_gate="800E459C",
            per_voice_record_base="800E4E40", per_voice_record_stride=56,
            per_voice_stride_evidence="8005ABF8..8005AC00: (voice*8-voice)*8",
            downstream_bitfield_base="800E5528",
            downstream_bitfield_evidence="8005BCEC..8005BD10 walks16 words; full ownership is unproven",
            spu_register_pointer_global="8007AD34",
            initial_spu_register_pointer=f"{exe.word(0x8007AD34):08X}"),
        implementation_status="audit_only_no_runtime_fix",
        local_coop="unverified", netplay="unverified",
        unresolved=[
            "Prove X6 VAB open at an explicit logical sample base and its exact completion/transfer-gate contract.",
            "Enumerate every mutable native key-on/stop/volume/flush record, dirty flag and mask before isolating P2.",
            "Retain cross-bank sound references when mapping groups1/3 to character-private VAB handles.",
            "Qualify hurt/death/action call ownership, concurrent lifetimes, pause/load/reset boundaries and snapshot replay against actual native muted captures."])
    disc = Disc(str(disc_path))
    try:
        files = disc.files()
        exe_lba, exe_size = files["SLUS_013.95"]
        disc_exe = b"".join(disc.user(exe_lba + i) for i in range((exe_size + 2047) // 2048))[:exe_size]
        if disc_exe != data:
            raise ValueError("Disc/EXE identity mismatch")
        lba, dat_size = files["ROCK_X6.DAT"]
        table = disc.user(lba)
        for member, (name, expected) in PLAYER_MEMBERS.items():
            sector, size = struct.unpack_from("<II", table, member * 8)
            if sector < 1 or not 2048 <= size <= 2_000_000 or sector * 2048 + size > dat_size:
                raise ValueError("Player DAT member extent is invalid")
            payload = b"".join(disc.user(lba + sector + i) for i in range((size + 2047) // 2048))[:size]
            if digest(payload) != expected:
                raise ValueError(f"Unsupported player source member {member}")
            assets = subassets(payload)
            banks = []
            for group, h, b, expected_type in ((1, 11, 12, 0x20101), (3, 13, 14, 0x20303)):
                if assets[h][0] != 6 or assets[b][0] != expected_type:
                    raise ValueError("Player VAB subasset types differ")
                bank = bank_metadata(assets[h][1], assets[b][1], group)
                bank.update(header_asset=h, sample_asset=b, sample_type=f"{expected_type:08X}")
                banks.append(bank)
            report["player_banks"].append(dict(member=member, character=name,
                archive="ROCK_X6.DAT", sector=sector, size=size, sha256=digest(payload), banks=banks))
    finally:
        disc.f.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit(args.exe, args.disc)
    if args.check:
        if json.loads(args.out.read_text(encoding="utf-8")) != report:
            raise SystemExit("Native audio inventory differs")
    else:
        with args.out.open("x", encoding="utf-8", newline="\n") as out:
            json.dump(report, out, indent=2)
            out.write("\n")
    print("5 character/form members, 10 original VAB banks; gameplay/audio outcomes unverified")


if __name__ == "__main__":
    main()
