"""Pure source contact/setup calculator; no writes, inputs, launcher or QA passes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

import audit_mmx6_recycle_terrain as terrain_source
import inventory_mmx6_coop_content as content
import mmx6_coop_checkpoint as checkpoint
import mmx6_coop_recycle_portal as portal_source

CAPSULE_RECORD=0x800F2E24
CAPSULE_POOL,CAPSULE_STRIDE,CAPSULE_COUNT=0x800C1220,0xA4,80
CHARACTER_BASE=0x801EA000
CHARACTERS=((0,2,44588,"180175846cf8b1b650c405be8085b19417be033b4644a4034d70703124bf7871"),
            (1,24,22964,"75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00"))
REFERENCE_BOXES=(0x801F3F50,0x801EEA04)
SPANS=(("capsule_initialize",0x80051158,0x338),
       ("capsule_update",0x80051890,0x94),("capsule_trigger",0x80051924,0x120),
       ("capsule_action_table",0x80078E18,0x14),
       ("capsule_boxes",0x80078DF8,12),("portal_contact",0x8002D654,0x214),
       ("initial_admission",0x8002A3E8,0x90))


def sha(data):return hashlib.sha256(data).hexdigest()


def s16(value):return (value+0x8000)%0x10000-0x8000


def point(value):
    if len(value)!=2 or any(type(v) is not int or not -32768<=v<=32767 for v in value):
        raise ValueError("Expected native signed16 coordinate pair")
    return value


def capsule_region(cx,cy,px,py):
    """Original51924 center-coordinate predicate, including signed16 negation.

    No damage/terrain boxes, button or iframe gate participates in this test.
    Native wrap edge cases are reproduced, not recommended setup positions.
    """
    point((cx,cy));point((px,py))
    dx=s16(px-cx)
    if dx<0:dx=s16(-dx)
    dy=s16(py-cy)
    return dx<65 and (dy<17 if dy>0 else s16(-dy)<105)


def contact(actor,player,actor_box,player_box,camera=None):
    """Literal2D654 geometry for supplied current native fields/box bytes.

    actor: x,y,facing,layer,attack_pointer. player: x,y,facing,iframe,damage_pointer.
    Missing bytes for a nonnull pointer are unknown and rejected. A private
    Zero pointer must not be dereferenced in a restored resident-X overlay.
    """
    ax,ay=point((actor["x"],actor["y"]));px,py=point((player["x"],player["y"]))
    for field in (actor["facing"],player["facing"],player["iframe"]):
        if type(field) is not int or not 0<=field<=255:raise ValueError("Expected native byte field")
    if type(actor["layer"]) is not int or not -128<=actor["layer"]<=127:
        raise ValueError("Expected signed native actor layer")
    for pointer in (actor["attack_pointer"],player["damage_pointer"]):
        if type(pointer) is not int or not 0<=pointer<=0xFFFFFFFF:raise ValueError("Invalid native pointer")
    for condition,reason in ((player["iframe"]!=0,"player61_nonzero"),
            (not actor["attack_pointer"],"actor50_null"),(not player["damage_pointer"],"player54_null")):
        if condition:return dict(status="source_arithmetic_only",hit=False,gate=reason)
    if actor_box is None or player_box is None or len(actor_box)!=4 or len(player_box)!=4:
        raise ValueError("Current nonnull collision pointers require their exact four bytes")
    aox,aoy,aw,ah=struct.unpack("<bbBB",actor_box)
    pox,poy,pw,ph=struct.unpack("<bbBB",player_box)
    fa,fp=bool(actor["facing"]&0x40),bool(player["facing"]&0x40)
    sx=ax-aox if fa else ax+aox;tx=px-pox if fp else px+pox
    sy=ay+aoy;ty=py+poy
    if actor["layer"]<0:
        if camera is None:raise ValueError("Negative-layer actor requires actual native camera coordinates")
        cx,cy=point(camera);sx+=cx;sy+=cy
    if tx<sx:width=(aw if fp else aw+pw) if fa else (0 if fp else pw)
    else:width=(pw if fp else 0) if fa else (aw+pw if fp else aw)
    height=ph if ty<sy else ah
    horizontal=abs(tx-sx)<width;vertical=abs(ty-sy)<height
    return dict(status="source_arithmetic_only",hit=horizontal and vertical,
        horizontal=horizontal,vertical=vertical,actor_reference=[sx,sy],player_reference=[tx,ty],
        width_bound=width,height_bound=height,comparisons="strict_less_than",
        actor_box_sha256=sha(actor_box),player_box_sha256=sha(player_box))


def derive_setup(terrain,x_box,z_box,capsule=(1424,1604),portal=(1552,1584)):
    """Filter the existing finite static floor envelope, without issuing setup.

    Boxes are explicit conditions, not inferred from character/animation names.
    Both portal facings and both player facings must miss for both characters.
    """
    point(capsule);point(portal)
    if len(x_box)!=4 or len(z_box)!=4:raise ValueError("Two exact current damage boxes required")
    floor=terrain_source.portal_probe_envelope(terrain,bytes((0,3,11,19)))
    minimum,maximum=floor["body_center_x_inclusive"]
    air_y=min(1616-2-19,1616-3-19)-1
    accepted=[];excluded=dict(capsule=0,portal=0)
    attack=struct.pack("<bbBB",-18,-28,28,40)
    for x in range(minimum,maximum+1):
        if any(capsule_region(*capsule,x,y) for y in range(air_y,1596)):
            excluded["capsule"]+=1;continue
        hit=False
        for box,landing_y in ((x_box,1595),(z_box,1594)):
            for y in range(air_y,landing_y+1):
                for fa in (0,0x40):
                    for fp in (0,0x40):
                        a=dict(x=portal[0],y=portal[1],facing=fa,layer=0,attack_pointer=0x800F38BC)
                        p=dict(x=x,y=y,facing=fp,iframe=0,damage_pointer=1)
                        if contact(a,p,attack,box)["hit"]:hit=True
        if hit:excluded["portal"]+=1
        else:accepted.append(x)
    intervals=[]
    for x in accepted:
        if intervals and x==intervals[-1][1]+1:intervals[-1][1]=x
        else:intervals.append([x,x])
    widest=max(intervals,key=lambda row:(row[1]-row[0],-row[0])) if intervals else None
    return dict(status="conditional_source_setup_not_native_qualification" if widest else "unverified_no_common_source_interval",
        floor_y=1616,body_center_envelope=[minimum,maximum],capsule_position=list(capsule),
        portal_position=list(portal),source_miss_intervals=intervals,excluded_counts=excluded,
        x_damage_box=list(struct.unpack("<bbBB",x_box)),zero_damage_box=list(struct.unpack("<bbBB",z_box)),
        conditional_both_seat_probe=dict(x=(widest[0]+widest[1])//2,y=air_y,
            x_native_landing_y=1595,zero_native_landing_y=1594,command=4,seat=2,
            selection="midpoint_of_widest_proven_source_miss_interval") if widest else None,
        automatic_actions=[],local_coop="unverified",netplay="unverified",
        remaining_conditions=["Exact current per-seat damage box provenance and native terrain boxes must match these inputs",
            "Live layout, scratch pointers, full metatiles/descriptors and dynamic hazards/solids must pass preflight",
            "Use a fresh scene-free offline setup; never clear an existing capsule dialogue/portal lock",
            "Position both eligible living seats atomically, or before enrollment and then prove safe native joining",
            "Only original landing, idle, lock release, enrollment, camera and actor initialization may qualify readiness",
            "Original checkpoint-X mismatch and command4 are disclosed tainted prerequisite bypasses; no paired mailbox"])


def load_sources(exe_path,disc_path):
    exe,member,terrain,resource=terrain_source.load_original(Path(exe_path),Path(disc_path))
    disc=content.RawDisc(Path(disc_path));characters={}
    try:
        header=disc.extent(terrain_source.BIN_LBA,4096)
        for index,sector,size,digest in CHARACTERS:
            if struct.unpack_from("<II",header,index*8)!=(sector,size):raise ValueError("Character BIN descriptor differs")
            data=disc.extent(terrain_source.BIN_LBA+sector,size)
            if sha(data)!=digest:raise ValueError("Original character collision bank differs")
            characters[index]=data
    finally:disc.stream.close()
    return dict(exe=exe,member=member,terrain=terrain,resource=resource,characters=characters)


def source_box(sources,character,address):
    if type(character) is not int or character not in (0,1) or type(address) is not int or address&3:
        raise ValueError("Need explicit original character owner and aligned native box pointer")
    at=address-CHARACTER_BASE;data=sources["characters"][character]
    if at<0 or at+4>len(data):raise ValueError("Box is outside its owner's original character bank; no resident-overlay fallback")
    return data[at:at+4]


def parse_capsule(raw):
    if len(raw)!=portal_source.SIZE:raise ValueError("Need one complete coherent native block")
    result=None
    for slot in range(CAPSULE_COUNT):
        address=CAPSULE_POOL+slot*CAPSULE_STRIDE
        at=address-portal_source.BASE;actor=raw[at:at+CAPSULE_STRIDE]
        if not actor[0]&1 or struct.unpack_from("<I",actor,0x10)[0]!=CAPSULE_RECORD:continue
        if result is not None:raise ValueError("Duplicate active capsule origin")
        if actor[1:3]!=bytes((0x1A,4)) or actor[4]>3:raise ValueError("Incompatible capsule origin-bound actor")
        result=dict(slot=slot,address=address,origin=CAPSULE_RECORD,type=actor[1],subtype=actor[2],
            phase=actor[4],action=actor[5],subaction=actor[6],visible=actor[3],
            x=struct.unpack_from("<h",actor,0xA)[0],y=struct.unpack_from("<h",actor,0xE)[0],
            body_box=struct.unpack_from("<I",actor,0x68)[0],damage_box=struct.unpack_from("<I",actor,0x54)[0],
            trigger_action_ready=actor[4]==1 and actor[5]==0,raw_sha256=sha(actor),raw_hex=actor.hex())
    return result


def observe_setup(owned_request):
    raw=portal_source._read(owned_request,portal_source.BASE,portal_source.SIZE)
    return dict(status="read_only_native_setup_observation",native=portal_source.parse_native(raw),
        capsule=parse_capsule(raw),native_block_sha256=sha(raw),
        limit="No private-seat/body-box attribution from separate RPCs; no readiness or safe-position verdict")


def audit(sources):
    exe,member,terrain=sources["exe"],sources["member"],sources["terrain"]
    inventory_path=Path(__file__).resolve().parents[1]/"docs/COOP_X6_CONTENT.json"
    inventory,rows,sections=checkpoint.verified_inventory(inventory_path,exe)
    section=next(s for s in inventory["placement_sections"] if (s["stage"],s["section"])==(4,0))
    capsule=section["placements"][117]
    if tuple(capsule[k] for k in ("address","object_id","subtype","category","x","y")) != \
            ("800F2E24",26,4,4,1424,1592):raise ValueError("Original authored capsule identity differs")
    if exe.word(0x8006DF6C)!=0x800F338C or \
            struct.unpack_from("<I",member,0x800F33F4-content.OVERLAY_BASE)[0]!=0x800515B4 or \
            exe.word(0x80078E18)!=0x80051924:raise ValueError("Original capsule dispatch differs")
    box=lambda address:exe.data[exe.offset(address,4):exe.offset(address,4)+4]
    capsule_box=box(0x80078DF8)
    if capsule_box!=bytes((0,0,16,12)):raise ValueError("Capsule native terrain box differs")
    # Original initializer retries with +16 until native contact; this selected
    # flat38h floor gives two initial probe heights1604 and1620, then resolves4px.
    capsule_probes=[[terrain.query(x,y)["code"] for x in (1408,1439,1424)] for y in (1604,1620)]
    if capsule_probes!=[[0,0,0],[0x38]*3]:raise ValueError("Capsule original initial floor probes differ")
    x_box=source_box(sources,0,REFERENCE_BOXES[0]);z_box=source_box(sources,1,REFERENCE_BOXES[1])
    spans=[]
    for name,address,size in SPANS:
        at=exe.offset(address,size);spans.append(dict(name=name,address=f"{address:08X}",bytes=size,sha256=sha(exe.data[at:at+size])))
    return dict(schema=1,source_only=True,original_exe_sha256=content.EXE_SHA256,
        original_bin_sha256=content.BIN_SHA256,inventory_sha256=checkpoint.INVENTORY_SHA256,
        source_spans=spans,capsule=capsule,
        capsule_native=dict(handler="800515B4",initialize="80051158",update="80051890",
            action_table="80078E18[0] ->80051924",terrain_box="80078DF8",terrain_box_values=[0,0,16,12],
            damage_box="80078E00",damage_box_values=list(struct.unpack("<bbBB",box(0x80078E00))),
            initial_foot_probes=capsule_probes,predicted_grounded_y=1604,
            trigger="signed16 |dx|<=64 and -104<=dy<=16 in ordinary local coordinates; does not read damage boxes",
            trigger_limit="Native signed16 negation wrap reproduced by calculator; local source region only for setup"),
        reference_character_boxes=[dict(character=chr,index=i,sector=sector,bytes=size,sha256=digest,
            box_address=f"{REFERENCE_BOXES[chr]:08X}",box_values=list(struct.unpack("<bbBB",source_box(sources,chr,REFERENCE_BOXES[chr]))),
            condition="Explicit source reference, not an inferred current standing/idle box")
            for chr,(i,sector,size,digest) in enumerate(CHARACTERS)],
        conditional_reference_setup=derive_setup(terrain,x_box,z_box),
        checkpoint=checkpoint.select(rows,sections,4,0,2),
        original_camera_admission=dict(settled_camera=[1264,1424],viewport=[1264,1584,1424,1664],
            initial_expanded_rectangle=[1216,1632,1376,1712],scanner="8002A3E8 ->80029F38",
            requirements="Wait for original camera/admission and live capsule phase1/action0, portal phase1/action1 with source geometry; no flags/actor initialization writes"),
        local_coop="unverified",netplay="unverified")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",type=Path,required=True);parser.add_argument("--disc",type=Path,required=True)
    parser.add_argument("--out",type=Path);parser.add_argument("--check",action="store_true")
    args=parser.parse_args();report=audit(load_sources(args.original,args.disc))
    if args.check:
        if not args.out or json.loads(args.out.read_text(encoding="utf-8"))!=report:raise SystemExit("Recycle setup source audit differs")
    elif args.out:
        with args.out.open("x",encoding="utf-8",newline="\n") as output:json.dump(report,output,indent=2);output.write("\n")
    else:print(json.dumps(report,indent=2))


if __name__=="__main__":main()
