"""Original-title native player-init caller audit; no game/runtime mutations."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

import inventory_mmx6_coop_content as content

INIT, MAJOR9, GAME_LOOP, PLAY = 0x8003BD24, 0x8001E1BC, 0x8001E6E4, 0x800CCED0
SPANS = (
    ("game_root",0x8001E6E4,0x4C),("major_table",0x8007112C,0x38),
    ("major9",MAJOR9,0x170),("major8",0x8001E914,0xD8),
    ("stage_dispatch",0x8001E9EC,0x3C),("checkpoint_select",0x80029B8C,0xE0),
    ("native_init",INIT,0x488),("attract_dispatch",0x8001D424,0x3C),
    ("attract_init",0x8001D51C,0xF0),("attract_table",0x800710AC,12),
    ("final_quit",0x8001FD10,0x164),("frontend_install",0x8001D25C,0x44),
    ("task_open_close_change",0x80013300,0xF0),("bios_stubs",0x80069E74,0x80),
    ("ordinary_door",0x8003D308,0x44),
)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def direct_references(payload,base,target):
    """Aligned encoded J/JAL and literal pointer census, not a call-graph oracle."""
    result=[]
    for at in range(0,len(payload)-3,4):
        word=struct.unpack_from("<I",payload,at)[0];pc=base+at
        if word==target:result.append(dict(address=pc,kind="literal_word"))
        elif word>>26 in (2,3) and (((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2))==target:
            result.append(dict(address=pc,kind="jal" if word>>26==3 else "j",return_address=pc+8))
    return result


def canonical_entry_checks(*, address, registers, play, saved_major9_ra):
    """Source signature at the function-entry hook, before INIT's prologue.

    Deliberately does NOT return safe_to_clear: a matching source signature
    cannot on its own certify whether a host callback frame was abandoned.
    Phase0/X are the narrowly reviewed NewGame context, not all native callers.
    """
    if len(registers)!=32 or len(play)<0x39:
        raise ValueError("Need actual32 CPU registers and PLAY through campaign character")
    sp=registers[29]
    return dict(exact_entry=address==INIT,canonical_call_ra=registers[31]==0x8001E26C,
        major9_saved_play_register=registers[16]==PLAY,
        bounded_native_stack=type(sp)is int and not sp&3 and 0x80000000<=sp<=0x801FFFE8,
        original_root_saved_ra=saved_major9_ra==0x8001E720,
        major9=play[0]==9,bounded_new_game_phase0=play[1]==0,
        bounded_fixed_x_campaign_character=play[0x38]==0)


def expected_retired_primary_menu_shape(frames):
    """Check only the owned two-frame shape; this is NOT retirement proof."""
    if len(frames)!=2:return False
    stage,guest=frames
    if (stage.get("tag"),stage.get("bytes"),stage.get("words"))!=(29,16,1) or \
       (guest.get("tag"),guest.get("bytes"),guest.get("words"))!=(1,408,1):return False
    try:a=bytes.fromhex(stage["saved_hex"]);b=bytes.fromhex(guest["saved_hex"])
    except (KeyError,ValueError,TypeError):return False
    if len(a)!=16 or len(b)!=408:return False
    stage_words=struct.unpack("<4I",a);guest_words=struct.unpack("<102I",b)
    return stage_words[1]==2 and stage_words[3]==0 and guest_words[31]==0x8001E720 and \
        guest_words[99]==0x8001E9EC and guest_words[100]==PLAY


def audit(exe_path,disc_path):
    raw=Path(exe_path).read_bytes()
    if sha(raw)!=content.EXE_SHA256:raise ValueError("Requires pinned original USA1.1 EXE")
    exe=content.Executable(raw)
    disc=content.RawDisc(Path(disc_path))
    try:archive=disc.extent(211185,1665024)
    finally:disc.stream.close()
    if sha(archive)!=content.BIN_SHA256:raise ValueError("Requires pinned original ROCK_X6.BIN")
    members=content.archive_members(archive)
    images=[dict(name="EXE",base=exe.base,data=raw[2048:2048+exe.size])]
    images += [dict(name=f"member{m['index']}",base=content.OVERLAY_BASE,
                   data=archive[m['sector']*2048:m['sector']*2048+m['size']]) for m in members]
    census={}
    for target in (INIT,MAJOR9,GAME_LOOP):
        rows=[]
        for image in images:
            rows += [dict(image=image["name"],**r) for r in direct_references(image["data"],image["base"],target)]
        census[f"{target:08X}"]=rows
    if census[f"{INIT:08X}"]!=[
        dict(image="EXE",address=0x8001D57C,kind="jal",return_address=0x8001D584),
        dict(image="EXE",address=0x8001E264,kind="jal",return_address=0x8001E26C)]:
        raise ValueError("Original init direct/literal caller census differs")
    if census[f"{MAJOR9:08X}"]!=[dict(image="EXE",address=0x80071150,kind="literal_word")]:
        raise ValueError("Original major9 reference differs")
    if census[f"{GAME_LOOP:08X}"]:raise ValueError("Game loop has an unexpected synchronous/literal reference")
    spans=[]
    for name,address,size in SPANS:
        at=exe.offset(address,size)
        spans.append(dict(name=name,address=f"{address:08X}",bytes=size,sha256=sha(raw[at:at+size])))
    constructs=[]
    for image in images:
        data=image["data"]
        for at in range(0,len(data)-3,4):
            word=struct.unpack_from("<I",data,at)[0]
            if word>>26 in (9,13) and word&0xFFFF==GAME_LOOP&0xFFFF:
                constructs.append(dict(image=image["name"],address=image["base"]+at,
                    instruction=f"{word:08X}",window_sha256=sha(data[max(0,at-20):at+20])))
    expected=[("EXE",0x8001DB64),("EXE",0x8001DDC4),("EXE",0x8001DDF4),
              ("member18",0x800EA958),("member18",0x800ED85C)]
    if [(c["image"],c["address"]) for c in constructs]!=expected:
        raise ValueError("Original game-loop address-construction census differs")
    return dict(schema=1,kind="original_native_player_init_caller_audit",source_only=True,
        original_exe_sha256=content.EXE_SHA256,original_archive_sha256=content.BIN_SHA256,
        members_scanned=len(members),census=census,spans=spans,game_loop_constructors=constructs,
        source_signature=dict(entry="8003BD24",ra="8001E26C",s0="800CCED0",major=9,
            enclosing_saved_ra="[SP+14]=8001E720 before init prologue",
            argument_gate="Incoming a0 is not a native caller identity; init overwrites it immediately",
            body_gate="Old resident HP/character/action/visibility are not init-completion evidence"),
        resource_policy=dict(signed_play_1e={"0_or_minus2":"native campaign max HP/ammo",
            "minus1":"native preserved HP/ammo/weapon","other":"does not take those refill/restore branches"},
            campaign_character="native3BE10 copies PLAY+38 into resident PLAYER+2"),
        retired_frame_shape=dict(observed_host_count=2,observed_host_error=0,
            source_inferred_expected_tags=[29,1],frame_payload_observed=False,
            expected_tag29=dict(bytes=16,words=1,phase=2,survivor=0),
            expected_tag1=dict(bytes=408,words=1,saved31="8001E720",saved99="8001E9EC",saved100="800CCED0")),
        host_retirement="Matching source/native/owned-frame shape is necessary but not a public-depth0 proof; require original closed-task/scheduler escape contract",
        runtime_fix_scope="Root-owned: discard only proven retired owned copies; never restore old CPU/body over fresh native initialization",
        native_validation="unverified_no_new_game_or_title_build",ledger_unchanged=True,
        limits=["Aligned source census includes all59 archive members; it is not a proof against arbitrary corrupted/computed guest PCs",
            "Canonical source entry is not successful init completion or fresh co-op enrollment",
            "Phase0/fixed-X character are bounded NewGame context; major9 itself does not dispatch or clear PLAY+1",
            "Public callback-active/host-depth0 do not universally exclude direct game hooks",
            "Two exact frame tags/payloads are source-inferred expectations, not observed in the retained host probe"])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-exe",type=Path,required=True);p.add_argument("--original-disc",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--check",action="store_true")
    a=p.parse_args();result=audit(a.original_exe,a.original_disc)
    encoded=json.dumps(result,indent=2)+"\n"
    if a.check:
        if a.out.read_text(encoding="utf-8")!=encoded:raise SystemExit("Source audit differs")
    else:a.out.write_text(encoded,encoding="utf-8",newline="\n")


if __name__=="__main__":main()
