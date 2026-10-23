"""Source-only remaining Zero audio ownership inventory. No native runner."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import inventory_mmx6_coop_content as content
from audit_mmx6_coop_audio import PLAYER_MEMBERS, Disc, bank_metadata, subassets

SOUND, STOP, WRAPPER = 0x80016C48,0x8001750C,0x8003CFE0
ZERO_BASE=0x801EA000
ZERO_CODE_SHA="75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00"
X4_COMMIT="50593bca772b600de6911cbfecd40b0f08721147"
X4_PATH="src/mods/mmx4_coop_audio.c"
X4_BLOB="f490a1725aac5775a3e6711305370c279362dceb"
FAILURE_CAPSULE="docs/evidence/mmx6-jump-audio/manifest-bound-beeae10-local-failure-reviewed.json"
FAILURE_SHA="5ca0d23ff531dbdb7fac7a25ab6faefd2b39bb49e7ae6c20019db22c5f477cd1"
SPANS=(
    ("sound_route",SOUND,0xEC),("sound_calculation",0x80016D34,0x2D4),("record_stop",STOP,0xE4),
    ("voice_wrapper",WRAPPER,0x34),("ground_jump_voice",0x8003AF1C,0xD8),
    ("hurt",0x8003963C,0x58),("fatal_launch",0x8003D850,0x58),
    ("death_stop_and_tones",0x8003D8A8,0x150),("phase2_dispatch",0x8003CC78,0x3C),
    ("phase_and_death_tables",0x80073ABC,0x18),("death_action_table",0x80073D20,0x10),
    ("jump_action",0x80035620,0x180),("same22_animation_sfx",0x80035874,0x4C),
    ("same22_stop_transition",0x8003B218,0x74),("stop_branch",0x800359AC,0x20),
    ("direction_countdown_stop",0x80038584,0xFC),("shared_menu_stop",0x800349D8,0x50))


def sha(raw):return hashlib.sha256(raw).hexdigest()


def voice_range(record):
    first,additional=record["first_voice"],record["additional_voices"]
    if type(first)is not int or type(additional)is not int or type(record["empty"])is not bool:
        raise ValueError("Invalid native voice metadata types")
    count=additional+1
    if record["empty"] or not 0<=first<24 or not 1<=count<=4 or first+count>24:
        raise ValueError("Empty/invalid original voice range cannot authorize private ownership")
    return list(range(first,first+count))


def calls(payload,base):
    result=[]
    for at in range(0,len(payload)-3,4):
        word=struct.unpack_from("<I",payload,at)[0];site=base+at
        if word>>26 not in(2,3):continue
        target=((site+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        if target not in(SOUND,STOP,WRAPPER):continue
        begin=max(0,at-24);window=payload[begin:at+8]
        result.append(dict(site=f"{site:08X}",target=f"{target:08X}",kind="jal" if word>>26==3 else "j",
            return_address=f"{site+8:08X}" if word>>26==3 else None,
            source_window=dict(address=f"{base+begin:08X}",bytes=len(window),sha256=sha(window))))
    return result


def resolve_records(banks):
    """Resolve each native record to its EFFECTIVE bank/program/tone/sample.

    Cross-bank aliases and additional consecutive voices/tones remain explicit.
    This validates metadata; a populated record is not a safe runtime caller.
    """
    out=[]
    for group in (1,3):
        for r in banks[group]["metadata"]["sound_records"]:
            if r["empty"]:continue
            effective=r["vab_handle"]
            if effective not in banks:raise ValueError("Original record aliases an unretained bank")
            b=banks[effective];header=b["header"];samples=b["samples"];meta=b["metadata"]
            pre=meta["preheader_bytes"];programs=pre+32;tones=programs+2048
            ranks={};rank=0
            for index in range(128):
                count=header[programs+index*16]
                if count:
                    if count>16:raise ValueError("Invalid populated native program")
                    ranks[index]=(rank,count);rank+=1
            if rank!=meta["program_count"]:raise ValueError("Native populated-program count differs")
            lengths=struct.unpack_from("<256H",header,len(header)-512)
            if lengths[0] or sum(lengths[:meta["sample_count"]+1])*8!=len(samples):
                raise ValueError("Invalid original sample-size table")
            resolved=[]
            for index,voice in enumerate(voice_range(r)):
                program=r["program"]+(r["tone_start"]+index)//16;tone=(r["tone_start"]+index)%16
                if program not in ranks or tone>=ranks[program][1]:raise ValueError("Record escapes populated program/tone")
                at=tones+ranks[program][0]*512+tone*32;t=header[at:at+32]
                sample=struct.unpack_from("<H",t,22)[0]
                if not 1<=sample<=meta["sample_count"]:raise ValueError("Record references unknown/noise sample")
                begin=sum(lengths[:sample])*8;size=lengths[sample]*8;body=samples[begin:begin+size]
                if not size or size%16 or len(body)!=size:raise ValueError("Record sample escaped original bank")
                ends=[i for i in range(size//16) if body[i*16+1]&1]
                resolved.append(dict(voice=voice,program=program,tone=tone,sample=sample,offset=begin,bytes=size,
                    sample_sha256=sha(body),note=t[6],shift=t[5],center=t[4],
                    adsr_lo=struct.unpack_from("<H",t,16)[0],adsr_hi=struct.unpack_from("<H",t,18)[0],
                    first_end_block=ends[0] if ends else None,
                    first_end_flags=body[ends[0]*16+1] if ends else None))
            out.append(dict(group=group,record=r["index"],effective_bank_group=effective,
                program_high_bit=r["program_high_bit"],routing=r["routing"],priority=r["priority"],
                voice_range=voice_range(r),tones=resolved))
    return out


def original_sources(exe_path,disc_path):
    data=Path(exe_path).read_bytes()
    if sha(data)!=content.EXE_SHA256:raise ValueError("Requires original USA1.1 EXE")
    exe=content.Executable(data);disc=Disc(str(disc_path))
    try:
        files=disc.files();lba,size=files["ROCK_X6.BIN"]
        archive=b"".join(disc.user(lba+i)for i in range((size+2047)//2048))[:size]
        if sha(archive)!=content.BIN_SHA256:raise ValueError("Original BIN identity differs")
        m=content.archive_members(archive)[1];zero=archive[m["sector"]*2048:m["sector"]*2048+m["size"]]
        if sha(zero)!=ZERO_CODE_SHA:raise ValueError("Original executable Zero overlay differs")
        lba,total=files["ROCK_X6.DAT"];table=disc.user(lba);sector,size=struct.unpack_from("<II",table,85*8)
        if sector<1 or size>2_000_000 or sector*2048+size>total:raise ValueError("Zero DAT extent escaped archive")
        member=b"".join(disc.user(lba+sector+i)for i in range((size+2047)//2048))[:size]
        if sha(member)!=PLAYER_MEMBERS[85][1]:raise ValueError("Original Zero DAT identity differs")
        assets=subassets(member);banks={}
        for group,h,b in((1,11,12),(3,13,14)):
            if assets[h][0]!=6 or assets[b][0]!=(0x20101 if group==1 else 0x20303):raise ValueError("Unexpected audio asset type")
            header,samples=assets[h][1],assets[b][1]
            banks[group]=dict(header=header,samples=samples,metadata=bank_metadata(header,samples,group))
    finally:disc.f.close()
    return exe,zero,banks


def frozen_x4(repo):
    blob=subprocess.run(["git","-C",str(repo),"cat-file","blob",f"{X4_COMMIT}:{X4_PATH}"],
                        check=True,capture_output=True).stdout
    actual=hashlib.sha1(f"blob {len(blob)}\0".encode()+blob).hexdigest()
    if actual!=X4_BLOB:raise ValueError("Frozen X4 audio object differs")
    return dict(commit=X4_COMMIT,path=X4_PATH,blob=actual,sha256=sha(blob),
        design=["Project group1/3 records through exact character bank, retaining native routing bits",
            "Save private priorities separately; select voices via private activity",
            "Run original calculation uncharged and restore native queue/meta/masks",
            "Character STOP redirects BOTH native volume-zero and KEYOFF into private slots",
            "Shared groupFF executes native once and also stops private voices"],
        port_limits=["X4 metadata34h/history48h are not X6 metadata38h/history16words",
            "X6 group3/17 aliases effectsVAB1; do not blanket-rewrite every group3 record to vocal bank",
            "X4 blanket private-stop mask is not a foreign-voice lease for X6",
            "X4 broad group filter is not proof of ownership for every X6 child-actor/shared-world caller"])


def audit(exe_path,disc_path,x4_repo):
    exe,zero,banks=original_sources(exe_path,disc_path)
    resident=calls(exe.data[2048:2048+exe.size],exe.base);overlay=calls(zero,ZERO_BASE)
    counts=lambda rows:{f"{target:08X}":sum(r["target"]==f"{target:08X}" for r in rows)for target in(SOUND,STOP,WRAPPER)}
    if counts(overlay)!={"80016C48":38,"8001750C":0,"8003CFE0":19}:raise ValueError("Zero code audio caller census differs")
    spans=[]
    for name,address,size in SPANS:
        at=exe.offset(address,size);spans.append(dict(name=name,address=f"{address:08X}",bytes=size,sha256=sha(exe.data[at:at+size])))
    if sha((Path(__file__).resolve().parents[1]/FAILURE_CAPSULE).read_bytes())!=FAILURE_SHA:
        raise ValueError("Retained historical failure capsule changed")
    return dict(schema=1,kind="remaining_private_zero_action_audio_source_audit",source_only=True,
        original_exe_sha256=content.EXE_SHA256,original_archive_sha256=content.BIN_SHA256,
        zero_code=dict(archive="ROCK_X6.BIN",member=1,base=f"{ZERO_BASE:08X}",bytes=len(zero),sha256=sha(zero)),
        zero_assets=dict(archive="ROCK_X6.DAT",member=85,sha256=PLAYER_MEMBERS[85][1],
            assembly_subasset=10,assembly_type=3,executable_code=False),
        banks=[{key:banks[g]["metadata"][key] for key in ("group","header_bytes","sample_bytes",
            "header_sha256","sample_sha256","program_count","tone_count","sample_count")} for g in (1,3)],
        frozen_x4=frozen_x4(x4_repo),spans=spans,
        callers=dict(resident_counts=counts(resident),resident=resident,zero_overlay_counts=counts(overlay),zero_overlay=overlay),
        zero_records=resolve_records(banks),
        combo_table=dict(address="801EE3BC",bytes=6,sha256=sha(zero[0x43BC:0x43C2]),
                         pairs=[list(zero[i:i+2])for i in range(0x43BC,0x43C2,2)]),
        native_stop_contract=dict(record_voices="first=(byte3&31), count=1+((byte3>>5)&3), contiguous",
            ordered_calls=["8005BC14(voice,0,0)","8005AD40(voice)"],
            valid_record_return="FF000000",global_ff_voices=list(range(24)),global_ff_return=0,
            character_1_5_sites=["800385FC","800386EC","800387E4","800388F8","8003B234","8003D8BC"],
            character_1_7_sites=["8003D8C8","8003F494","8003F60C"],
            overlay_direct_stops=0,transitive_stop_absence_proven=False),
        native_sound_contract=dict(additional_voices="Consecutive voices and tones; tone16 wraps to next program",
            raw_group="SOUND indexes group&7F but raw bit80 changes gain selection at80016D74; preserve the original raw request",
            program_high_bit="Skips actor-position gain adjustment at80016E90; preserve original tone stereo gains",
            selection="Original private-status and priority branch must run; retain RNG and wrapper PLAYER+8D suppression",
            transaction="X6 whole2304-byte driver span +priority24 +group128 +gate/current pointer; restore before DSP",
            warnings=["Group3/17 resolves bank1/program1/tone7/voice3, same tone as group1/12",
                "Group1/11 and1/13 use two voices20/21 and consecutive tones; current one-KEYON jump helper cannot accept them",
                "The same private voice20 legitimately switches between effects and vocals within P2; slot20->bank31 is not a general owner model",
                "Phase2 fatal/death requests are excluded by current phase1 jump-only admission",
                "Actor-associated a2 may be a child, not PLAYER; source ownership must be proved before extending that boundary"]),
        current_candidate_scope="8ad0301 ground_jump_only; no gameplay outcome transferred",
        retained_failure=dict(path=FAILURE_CAPSULE,sha256=FAILURE_SHA,
            candidate="beeae107efca2fddab2c279a9d48d5e7e00817b1",
            exe_sha256="a8f20cdcc4ac68cdc76bf8fa7f1b3a74b9db67788514468743a355284b2080b8",
            mode_status=dict(local="failed",netplay="unverified"),
            scope="Exact historical original-ground-jump ownership/replacement counterexample; raw report unchanged"),
        r4="unverified_full_jump_attack_hurt_death_family",r12="unverified_full_overlap_and_stop_family",
        native_runs=False,title_builds=False,ledger_unchanged=True,
        limits=["Direct aligned source census is not transitive/alias analysis or runtime event coverage",
            "Zero code and DAT85 sample assets are separately pinned; no absence claim comes from a resident-only scan",
            "Record/sample metadata is not original co-op-off reference playback or audible comparison",
            "Other rosters/forms, earned techniques, shared groups, child actor ownership and campaign contexts remain separate",
            "Historical jump-only source/native evidence is unchanged and cannot close fullR4/R12"])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in("original-exe","original-disc","x4-repo","out"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--check",action="store_true");a=p.parse_args()
    result=audit(a.original_exe,a.original_disc,a.x4_repo)
    if a.check:
        if json.loads(a.out.read_bytes())!=result:raise SystemExit("Source audio audit differs")
    else:a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":main()
