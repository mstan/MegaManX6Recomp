"""Pinned, read-only Recycle alternate-area exit policy and terrain audit.

No launcher, guest calls/writes, inputs, card operations or gameplay passes.
The exit consumer is proven separately from its still-unqualified producers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import inventory_mmx6_coop_content as content
import mmx6_coop_checkpoint as checkpoint
from audit_mmx6_coop_audio import subassets
from audit_mmx6_recycle_terrain import Terrain

BIN_LBA, DAT_LBA = 211185, 211998
MEMBER_SHA = "7f49ac29077a76c6dc0aaafc474ad4d4eece65402282549de2f1ff2b5d748aef"
DAT_SHA = "791ea8758ab8e936d3dd44d3b4d1ac8a7123bfed6f2d334f4b818a46091debfc"
LAYOUT_SHA = "2fdd0042cb39a7945c51ac2b872df790132b0ab33ecd1afa577d0947aecc85c1"
ASSETS = ((8, 0, 30720, "7197d2c9f6ce6a0423559ab2ca461d7f4cba9a420f0989e79f7689a1029e8530"),
          (9, 1, 4512, "0fac81836f3e019ef5ac06449163a0ec1403e5f6fce7fff970e15842cb4fbf6b"))
SPANS = (("stage_exit_consumer", 0x8001E32C, 0x3B8),
         ("majorB_next_namespace", 0x8001E81C, 0x64),
         ("major13_next_namespace", 0x8001ED88, 0x54),
         ("major_table", 0x8007112C, 0x54),
         ("category3_update", 0x8002048C, 0x114),
         ("initial_admission_window", 0x8002A3E8, 0x90),
         ("primary_scanner", 0x80029F38, 0x400),
         ("checkpoint_marker", 0x80052D30, 0x114),
         ("boss_variant_loader", 0x80052E44, 0x120),
         ("interaction_admission_window", 0x80052F64, 0x3F8),
         ("interaction_region_selector", 0x8007A124, 0x30),
         ("destination_interaction_rectangle", 0x8007A974, 8),
         ("default_body_box_selection", 0x8003CCBC, 0x44),
         ("default_body_boxes", 0x80073D50, 8),
         ("layout_copy", 0x8002798C, 0xC4),
         ("collision_lookup", 0x80030304, 0x108))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exit_policy(transition, boss_variant, checkpoint_index=0):
    """Literal native1E32C consumer for stage20/section1 only.

    A predicted branch is neither a request to write its input nor proof that
    a boss/trigger produced it. Later story/selector scripts remain separate.
    """
    for value in (transition, boss_variant, checkpoint_index):
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError("Expected actual native unsigned byte")
    signed = transition if transition < 128 else transition - 256
    if signed < 0:
        return dict(kind="same_namespace_preserved_resource_retry", major=9,
                    stage=20, section=1, checkpoint=checkpoint_index,
                    resource_policy="native PLAY+1E=-1; preserve resident HP/ammo/weapon",
                    next_namespace=None)
    if not signed:
        return dict(kind="death_retry_or_game_over_requires_lives", major=None,
                    stage=20, section=1, checkpoint=checkpoint_index, next_namespace=None)
    if boss_variant in (0, 1):
        cp = 2 if boss_variant == 0 else 4
        return dict(kind="positive_alternate_exit_to_story_loader", major=0x13,
                    stage=20, section=1, checkpoint=cp,
                    native_play5f_or=0x10 if boss_variant == 0 else 0,
                    next_namespace=dict(major=0x14, stage=11, section=0, checkpoint=cp))
    return dict(kind="positive_alternate_exit_to_majorB_loader", major=0x0B,
                stage=20, section=1, checkpoint=checkpoint_index,
                next_namespace=dict(major=0x0C, stage=15, section=0, checkpoint=0))


def initial_scan_window(camera_x, camera_y, record_x, record_y):
    """Strict full initial scan rectangle; not allocation or movement proof."""
    for value in (camera_x, camera_y, record_x, record_y):
        if type(value) is not int or not -32768 <= value <= 32767:
            raise ValueError("Expected signed16 native coordinate")
    wrap = lambda value: (value + 32768) % 65536 - 32768
    return (wrap(camera_x - 48) < record_x < wrap(camera_x + 368) and
            wrap(camera_y - 48) < record_y < wrap(camera_y + 288))


def load_original(exe_path, disc_path):
    exe = checkpoint.original_executable(Path(exe_path))
    disc = content.RawDisc(Path(disc_path))
    try:
        archive = disc.extent(BIN_LBA, 1665024)
        if sha(archive) != content.BIN_SHA256:
            raise ValueError("Require pinned complete original BIN")
        member = content.archive_members(archive)[28]
        if member["sha256"] != MEMBER_SHA:
            raise ValueError("Original destination member28 differs")
        begin = member["sector"] * 2048
        payload = archive[begin:begin + member["size"]]
        header = disc.extent(DAT_LBA, 4096)
        sector, size = struct.unpack_from("<II", header, 118 * 8)
        if (sector, size) != (13092, 655360):
            raise ValueError("Original DAT118 descriptor differs")
        dat = disc.extent(DAT_LBA + sector, size)
        if sha(dat) != DAT_SHA:
            raise ValueError("Original DAT118 payload differs")
    finally:
        disc.stream.close()
    assets = subassets(dat)
    for index, kind, size, digest in ASSETS:
        if (assets[index][0], len(assets[index][1]), sha(assets[index][1])) != (kind, size, digest):
            raise ValueError("Original destination collision asset differs")
    if exe.word(0x80076384) != 0x800F2388 or \
            exe.data[exe.offset(0x800763EA, 2):exe.offset(0x800763EA, 2)+2] != bytes((15, 6)) or \
            struct.unpack_from("<H", exe.data, exe.offset(0x8006DA4E, 2))[0] != 118:
        raise ValueError("Original20/1 layout/resource selectors differ")
    layout = payload[0x800F2388-content.OVERLAY_BASE:0x800F2388-content.OVERLAY_BASE+270]
    if sha(layout) != LAYOUT_SHA:
        raise ValueError("Original destination authored layout differs")
    if exe.data[exe.offset(0x80073D50,8):exe.offset(0x80073D50,8)+8] != bytes((0,2,11,19,0,3,11,19)):
        raise ValueError("Original conditional standing boxes differ")
    return exe, payload, member, Terrain(layout, assets[8][1], assets[9][1], 15, 6), dict(
        member=118, sector=sector, size=len(dat), sha256=DAT_SHA,
        header_sha256=sha(header), assets=[dict(index=i, type=k, bytes=n, sha256=h) for i,k,n,h in ASSETS])


def audit(exe_path, disc_path):
    exe, payload, member, terrain, resources = load_original(exe_path, disc_path)
    root = Path(__file__).resolve().parents[1]
    inventory, locations, sections = checkpoint.verified_inventory(root/"docs/COOP_X6_CONTENT.json", exe)
    selected = []
    for key in ("placement_sections", "secondary_placement_sections"):
        section = next(r for r in inventory[key] if (r["stage"], r["section"]) == (20, 1))
        for row in section["placements"]:
            start = int(row["address"], 16) - content.OVERLAY_BASE
            if tuple(struct.unpack_from("<4B2h", payload, start)) != tuple(row[k] for k in
                    ("flags", "object_id", "subtype", "category", "x", "y")):
                raise ValueError("Frozen destination placement record differs")
        selected.append(section)
    primary = selected[0]["placements"]
    reverse = [r["address"] for r in primary if (r["category"], r["object_id"]) == (0, 28)]
    if reverse:
        raise ValueError("Unexpected authored destination portal")
    table = exe.word(0x8006DF38)
    if table != 0x800F2940:
        raise ValueError("Destination category3 dispatch root differs")
    handlers = []
    for kind in (6, 13, 14, 30):
        pointer = struct.unpack_from("<I", payload, table-content.OVERLAY_BASE+kind*4)[0]
        handlers.append(dict(category=3, type=kind, address=f"{pointer:08X}"))
    if [r["address"] for r in handlers] != ["80052D30", "80052E44", "8005335C", "800EBEE8"]:
        raise ValueError("Original destination handler mapping differs")
    # Source intervals, not pixel data or executable bytes.
    probes = [(x,y,terrain.query(x,y)["code"]) for y in range(224,384,16) for x in range(0,96,16)]
    floor = [terrain.query(x,384)["code"] for x in range(0,96,16)]
    if any(code for _,_,code in probes) or floor != [0x38]*6:
        raise ValueError("Conditional initial entry ledge differs")
    group = exe.data[exe.offset(0x8007A124+41,1)]
    rectangle_address = 0x8007A154 + group*128 + 4*8
    rectangle = list(struct.unpack_from("<4h", exe.data, exe.offset(rectangle_address,8)))
    spans = [dict(name=name, address=f"{address:08X}", bytes=size,
                  sha256=sha(exe.data[exe.offset(address,size):exe.offset(address,size)+size]))
             for name,address,size in SPANS]
    ride = payload[0x800EBEE8-content.OVERLAY_BASE:0x800EBF64-content.OVERLAY_BASE]
    spans.append(dict(name="ride_armor_placement",address="800EBEE8",bytes=len(ride),sha256=sha(ride)))
    return dict(schema=1, source_only=True, original_exe_sha256=content.EXE_SHA256,
        original_archive_sha256=content.BIN_SHA256, inventory_sha256=checkpoint.INVENTORY_SHA256,
        namespace=dict(stage=20, section=1), destination_member=member, resource=resources,
        layout=dict(address="800F2388",selector="80076384",dimensions_address="800763EA",
            width_screens=15,height_screens=6,layers=3,bytes=270,sha256=LAYOUT_SHA),
        checkpoints=[checkpoint.select(locations,sections,20,1,n) for n in (0,1)],
        placement_census=dict(primary_count=len(primary),secondary_count=len(selected[1]["placements"]),
            authored_category0_type1C=reverse,
            limit="Absence in these authored lists is not a complete dynamic producer or indirect-call census"),
        relevant_records=[r for r in primary if (r["category"],r["object_id"]) in ((3,6),(3,13),(3,14),(3,30))],
        handlers=handlers,native_spans=spans,
        entrance_interaction=dict(record="800F24A0",subtype=0x84,region_table="8007A124",
            group=group,rectangle_address=f"{rectangle_address:08X}",rectangle=rectangle,
            comparisons="strict xmin<X<xmax and ymin<Y<ymax; resident PLAYER only",
            input="native pressed bit0100h; action>=2, signed HP neither0 nor80h, PLAYER+D4=0",
            additional_gates=["Stage event halfword PLAY+9E+2*group lacks bit4; native97428=0",
                              "For subtype84h, resident PLAYER+E0 must be neither1 nor2"],
            effect="hint field PLAYER+14E=4; original interaction21760; not proof of a return warp"),
        ride_armor=dict(record="800F2588",handler="800EBEE8",singleton="800CD340",
            effect="Copies subtype/origin/position to native singleton then frees placement actor; not a reverse portal"),
        conditional_entry_floor=dict(layer=0,x_pixels_inclusive=[0,95],floor_y=384,code=0x38,
            air_rectangle=dict(x=[0,95],y=[224,383]),
            current_boxes_required=[dict(character="X",source="80073D50",bytes=[0,2,11,19],predicted_contact_y=363),
                                    dict(character="Zero",source="80073D54",bytes=[0,3,11,19],predicted_contact_y=362)],
            full_foot_center_x_inclusive=[11,85],
            adjacent_lower_response=dict(x=96,y=416,code=terrain.query(96,416)["code"]),
            limitations=["Actual current+68 boxes, live map/assets, dynamic RideArmor/actors and ground resolution required",
                         "No teleport, safe walking/jump sequence, complete-foot or damage safety is approved"]),
        admission=dict(initial_scan="8002A3E8 ->80029F38",bounds="strict cameraX-48<X<cameraX+368; cameraY-48<Y<cameraY+288",
            checkpoint_marker="80052DB8 requires visibility helper2CAB4=0 and resident X>=3026 before native CP1 write",
            boss_loader="80052E44 selects original member43/44/45 from actual PLAY+43B, waits14B78, allocates boss once then frees controller",
            limit="Initial scan geometry is not actor allocation, a full moving-camera scan, arena admission or either-seat support proof"),
        exit_consumer=dict(function="8001E32C",input="actual native PLAY+0F; no observer writes",
            variant_field="PLAY+43B",policies=[exit_policy(1,n) for n in (0,1,2)],
            negative_retry=exit_policy(255,0),zero_transition=exit_policy(0,0),
            consumer_only=True,reverse_to_stage4_in_this_consumer=False,
            limit="Boss defeat/clear producers, later scene/selector completion and all alternate variants remain unqualified"),
        recommended_native_checks=[
            "After real outbound load, require namespace20/1/CP0, both actual living grounded bodies, current private-bank box provenance, exact270-byte live layout and both collision assets",
            "Neutral observation first; initial X79 fits the conditional ledge, but a +24 P2 join offset need not. Refuse blind Right/Left or inferred floor",
            "If testing room limits, use short original held-frame0 inputs with neutral cleanup only after a current live safety envelope; retain independent control and composed captures",
            "For campaign exit, first close RideArmor/terrain/arena traversal and original boss producer; use native combat and retain actual transition+43B branch, major/namespace and both-player lifecycle",
            "Record any prerequisite/position/equipment bypass separately; never set portal, boss HP, clear/progression, exit flags, timers, ground or completion fields to claim this route",
            "Distinguish passenger return at destination from reverse room travel and later campaign/story/selector return"],
        accepted_input_route=None,proven_safe_positions=[],local_coop="unverified",netplay="unverified")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",type=Path,required=True)
    parser.add_argument("--disc",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    result=audit(args.original,args.disc)
    encoded=json.dumps(result,indent=2)+"\n"
    if args.check:
        if args.out.read_text(encoding="utf-8")!=encoded:
            raise SystemExit("Committed Recycle return audit differs")
    else:
        with args.out.open("x",encoding="utf-8",newline="\n") as stream:stream.write(encoded)
    print("Pinned Recycle destination/exit-consumer source audit matches; native route unverified")


if __name__=="__main__":main()
