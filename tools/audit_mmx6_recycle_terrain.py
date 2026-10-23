"""Bounded original R14 terrain lookup; source support is not a safe live route.

Reads the original EXE, BIN member6 and DAT member98 only (plus headers).
Emits metadata, never disc bytes, guest writes, movement or gameplay passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import inventory_mmx6_coop_content as content
import mmx6_coop_checkpoint as checkpoint
import mmx6_coop_recycle_portal as portal
from audit_mmx6_coop_audio import subassets
from audit_mmx6_coop_hud import committed, function
from audit_mmx6_death_particles import direct_calls

BIN_LBA, DAT_LBA = 211185, 211998
ADAPTER_BASE="b766ed1d7a698ec10bcdf9b793a82c4ca84aff10"
BIN_MEMBER_SHA = "c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5"
DAT_MEMBER_SHA = "f8798efe535ac46ca7ab2a7e4dfd99705c5624ae5c301627543c3d91d3bf6515"
LAYOUT_SHA = "f68a92a60270db16e4a82a10782d3bfa98643dc82e467122ef8aee31a49b985c"
ASSETS = ((7, 0, 87040, "a8a914262768bcf2b0310a5e4723f545ca4b840387900c1d78d3bd1de6a0b117"),
          (8, 1, 8000, "613dcf05adfc3810a7b13bf496f9fceae4b156acc00b9c78a9b635326eb6b192"))
SPANS = (("stage_resource_selection", 0x80013E54, 0x38),
         ("stage_member_start", 0x80014084, 0x24),
         ("typed_asset_pointer_publication", 0x800154D0, 0x4C),
         ("type0_type1_destinations", 0x8006E27C, 8),
         ("live_map_pointer", 0x80026888, 0x28),
         ("layout_copy", 0x8002798C, 0xC4),
         ("screen_lookup", 0x80028078, 0x7C),
         ("collision_lookup", 0x80030304, 0x108),
         ("body_probe_shape", 0x800304D8, 0x94),
         ("downward_probes", 0x8002F840, 0x19C),
         ("downward_resolution", 0x8002F9DC, 0x210),
         ("horizontal_resolution", 0x80030628, 0xC4),
         ("ground_resolution", 0x80030834, 0x84),
         ("default_body_boxes", 0x8003CCBC, 0x44),
         ("checkpoint_marker", 0x80052D30, 0x114))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def signed16(value):
    return (value + 0x8000) % 0x10000 - 0x8000


class Terrain:
    """Original 28078/30304 lookup; does not execute their body writes.

    This uses the initial authored map and immutable source assets. Live map,
    collision data, actors, hazards, camera policy and character state can differ.
    """
    def __init__(self, layout, metatiles, descriptors, width, height):
        if any(type(v) is not int or not 1 <= v <= 255 for v in (width, height)) or \
                len(layout) != width * height * 3 or len(metatiles) % 512 or \
                not metatiles or len(descriptors) % 4 or not descriptors:
            raise ValueError("Invalid native terrain extents")
        if any(cell * 512 + 512 > len(metatiles) for cell in layout if cell):
            raise ValueError("Authored map cell escapes metatile asset")
        for at in range(0, len(metatiles), 2):
            if (struct.unpack_from("<H", metatiles, at)[0] & 0x3FFF) * 4 + 4 > len(descriptors):
                raise ValueError("Metatile references an absent descriptor")
        self.layout, self.metatiles, self.descriptors = layout, metatiles, descriptors
        self.width, self.height = width, height

    def query(self, x, y, layer=0):
        if any(type(v) is not int for v in (x, y, layer)) or not 0 <= layer < 3 or \
                not -32768 <= x <= 32767 or not -32768 <= y <= 32767:
            raise ValueError("Expected native signed16 coordinates and layer0..2")
        row, col = y >> 8, x >> 8
        result = dict(x=x, y=y, layer=layer, screen_col=col, screen_row=row,
                      authored_only=True, runtime_status="unverified")
        if not 0 <= col < self.width or not 0 <= row < self.height:
            return result | dict(cell=None, tile=None, descriptor=None, raw_code=None, code=0,
                                 reason="28078 unsigned bounds reject screen")
        at = layer * self.width * self.height + row * self.width + col
        cell = self.layout[at]
        if not cell:
            return result | dict(cell=0, tile=None, descriptor=None, raw_code=None, code=0,
                                 reason="30304 skips cell0")
        tile_at = cell * 512 + ((y >> 4) & 15) * 32 + ((x >> 4) & 15) * 2
        tile = struct.unpack_from("<H", self.metatiles, tile_at)[0] & 0x3FFF
        code = self.descriptors[tile * 4]
        return result | dict(cell=cell, tile=tile, descriptor=tile, raw_code=code,
                             code=0x38 if code == 0x3B else code,
                             reason="30304 remaps3B to38" if code == 0x3B else "descriptor low byte")


def foot_probes(body, shape, terrain):
    """Three initial downward samples from304D8/2F840; never a grounded verdict.

    Caller must supply the actual body and bytes addressed by that body's +68.
    A source default box is not proof that a live character currently uses it.
    """
    if len(body) != 0x158 or len(shape) != 4 or not body[0] or \
            not struct.unpack_from("<I", body, 0x68)[0] or not shape[2] or not shape[3]:
        raise ValueError("Need an active native body and its nonempty current box")
    offset_x, offset_y, radius_x, radius_y = struct.unpack("<bbBB", shape)
    x, y = struct.unpack_from("<h", body, 0xA)[0], struct.unpack_from("<h", body, 0xE)[0]
    center = signed16(x - offset_x if body[0x15] else x + offset_x)
    bottom = signed16(y + offset_y + radius_y)
    layer = struct.unpack_from("<b", body, 0x14)[0]
    return dict(status="source_samples_only_not_grounded_or_safe", body_sha256=sha(body),
        body_box_pointer=struct.unpack_from("<I", body, 0x68)[0], shape_sha256=sha(shape),
        probes=[terrain.query(signed16(center-radius_x), bottom, layer),
                terrain.query(signed16(center+radius_x-1), bottom, layer),
                terrain.query(center, bottom, layer)],
        limits=["Native resolution changes the body and scratch state; this pure lookup does not",
                "Full-foot safety, hazards, actor solids and live map mutations are not established"])


def portal_probe_envelope(terrain, shape):
    """Derive a bounded static Zero air/foot probe, never approve live placement.

    The rectangle and floor are established from this selected original map.
    Every covered 16px tile is checked; the current live shape/map and dynamic
    actors still need independent native confirmation before any positioning.
    """
    if shape != struct.pack("<bbBB",0,3,11,19):
        raise ValueError("Probe envelope is limited to the source standing Zero box")
    x0,x1,floor=1456,1567,1616
    contact_y=floor-shape[1]-shape[3]
    air_y=contact_y-1
    top,bottom=air_y+shape[1]-shape[3],floor-1
    clear=[terrain.query(x,y)["code"] for x in range(x0,x1+1,16)
           for y in range(top//16*16,bottom+1,16)]
    support=[terrain.query(x,floor)["code"] for x in range(x0,x1+1,16)]
    if any(clear) or set(support)!={0x38}:
        raise ValueError("Source rectangle is not clear above the exact38h floor")
    return dict(status="source_probe_envelope_not_approved_live_placement",layer=0,
        standing_zero_box="80073D54",clear_rectangle=dict(x=[x0,x1],y=[top,bottom]),
        floor_y=floor,floor_code=0x38,body_center_x_inclusive=[x0+shape[2],x1-shape[2]+1],
        predicted_native_contact_center_y=contact_y,one_pixel_air_center_y=air_y,
        live_prerequisites=["Actual current Zero body+68 equals80073D54 and its four bytes match",
            "Live layout, metatiles and descriptors retain these collision results",
            "No dynamic hazard/solid or campaign/script lock invalidates the rectangle",
            "Actual current damage box and portal facing establish initial contact miss, with P1 outside",
            "A disclosed private position bypass is explicitly permitted and retained as tainted setup"],
        qualification_limits=["This predicts static geometry, not a native grounded outcome",
            "No exact X, input sequence or teleport action is selected",
            "Only original gravity/contact/input may establish landing, approach and portal admission"])


def observe_source_preflight(owned_request, original_terrain):
    """One existing native block read, retaining state even if source preflight fails.

    The source floor envelope is conditional metadata. This never approves a
    live position or combines this RPC with the private player publication.
    """
    raw=portal._read(owned_request,portal.BASE,portal.SIZE)
    native=portal.parse_native(raw)
    at=0x80097438-portal.BASE
    layout=raw[at:at+len(original_terrain.layout)]
    same=layout==original_terrain.layout
    source=native["stage"]==4 and native["section"]==0 and native["source_closure_present"]
    return dict(status="read_only_partial_preflight_not_position_approval",native=native,
        native_block_sha256=sha(raw),live_layout=dict(address="80097438",bytes=len(layout),
            sha256=sha(layout),matches_initial_original=same,
            changed_indices=[i for i,(a,b) in enumerate(zip(layout,original_terrain.layout)) if a!=b]),
        source_probe_envelope=portal_probe_envelope(original_terrain,struct.pack("<bbBB",0,3,11,19))
            if same and source else None,
        original_inputs_match_required=True,
        remaining_gaps=["Live scratch map/metatile/descriptor pointers and resource bytes are not read here",
            "Dynamic actor support/hazards and actual private-seat current box remain unverified",
            "Separate private publications do not establish same-tick P1-outside/P2-contact",
            "No live grounded-position, contact-miss, accepted-route or R14 pass is granted"])


def load_original(exe_path: Path, disc_path: Path):
    exe = checkpoint.original_executable(exe_path)
    disc = content.RawDisc(disc_path)
    try:
        archive = disc.extent(BIN_LBA, 1665024)
        if sha(archive) != content.BIN_SHA256:
            raise ValueError("Require original complete BIN identity")
        member = content.archive_members(archive)[6]
        if member["sha256"] != BIN_MEMBER_SHA:
            raise ValueError("Original Recycle BIN member differs")
        payload = archive[member["sector"]*2048:member["sector"]*2048+member["size"]]
        header = disc.extent(DAT_LBA, 4096)
        sector, size = struct.unpack_from("<II", header, 98*8)
        if (sector, size) != (5682, 937984):
            raise ValueError("Original DAT98 descriptor differs")
        data = disc.extent(DAT_LBA+sector, size)
        if sha(data) != DAT_MEMBER_SHA:
            raise ValueError("Original DAT98 payload differs")
    finally:
        disc.stream.close()
    assets = subassets(data)
    for index, kind, size, digest in ASSETS:
        if (assets[index][0], len(assets[index][1]), sha(assets[index][1])) != (kind, size, digest):
            raise ValueError("Original terrain subasset differs")
    at = exe.offset(0x800763A8, 2)
    width, height = exe.data[at:at+2]
    pointer = exe.word(0x80076300)
    if (width, height, pointer, exe.word(0x8006DA0C) & 0xFFFF) != (22, 8, 0x800F286C, 98):
        raise ValueError("Original stage4/sec0 terrain selector differs")
    at = pointer-content.OVERLAY_BASE
    layout = payload[at:at+width*height*3]
    if sha(layout) != LAYOUT_SHA:
        raise ValueError("Original authored layout differs")
    return exe, payload, Terrain(layout, assets[7][1], assets[8][1], width, height), dict(
        archive="ROCK_X6.DAT", member=98, lba=DAT_LBA, sector=sector, size=len(data),
        sha256=DAT_MEMBER_SHA, header_sha256=sha(header),
        assets=[dict(index=i, type=k, bytes=n, sha256=h) for i,k,n,h in ASSETS])


def audit(exe_path: Path, disc_path: Path):
    exe, member, terrain, resource = load_original(exe_path, disc_path)
    repository=Path(__file__).resolve().parents[1]
    inventory_path = repository/"docs/COOP_X6_CONTENT.json"
    inventory, locations, sections = checkpoint.verified_inventory(inventory_path, exe)
    nearby = []
    for key in ("placement_sections", "secondary_placement_sections"):
        section = next(s for s in inventory[key] if (s["stage"],s["section"]) == (4,0))
        for row in section["placements"]:
            if 1408 <= row["x"] <= 1920 and 1280 <= row["y"] <= 1728:
                at = int(row["address"],16)-content.OVERLAY_BASE
                if tuple(struct.unpack_from("<4B2h",member,at)) != tuple(row[k] for k in
                        ("flags","object_id","subtype","category","x","y")):
                    raise ValueError("Nearby authored record drift")
                table = exe.word(0x8006DC6C+row["category"]*0xB8+4*8)
                handler = struct.unpack_from("<I",member,table-content.OVERLAY_BASE+row["object_id"]*4)[0]
                nearby.append(row | dict(source_list=key, handler_table=f"{table:08X}",
                    handler=f"{handler:08X}", meaning_status="unverified_unless_described"))
    native = []
    for name,address,size in SPANS:
        at=exe.offset(address,size); data=exe.data[at:at+size]
        native.append(dict(name=name,address=f"{address:08X}",size=size,sha256=sha(data),
            direct_calls=direct_calls(data,address) if name != "type0_type1_destinations" else []))
    foot_dispatch = {f"{code:02X}":f"{exe.word(0x80010C70+code*4):08X}" for code in (0,0x38,0x39)}
    left_dispatch = {f"{code:02X}":f"{exe.word(0x80010D98+(code-0x38)*4):08X}" for code in (0x38,0x39)}
    boxes=[]
    for character,address in (("X",0x80073D50),("Zero",0x80073D54)):
        at=exe.offset(address,4); shape=exe.data[at:at+4]
        boxes.append(dict(character=character,address=f"{address:08X}",sha256=sha(shape),
            x_offset=struct.unpack_from("<b",shape)[0],y_offset=struct.unpack_from("<b",shape,1)[0],
            x_radius=shape[2],y_radius=shape[3], prerequisite="8003CCBC with body+D5 nonnegative; actual body+68 must match"))
    wall=[terrain.query(x,y) for x in (1568,1584) for y in range(1408,1680,16)]
    unsupported=[terrain.query(x,y) for x in range(1600,1792,16) for y in range(1440,2048,16)]
    if {r["code"] for r in wall} != {0x38,0x39} or any(r["code"] for r in unsupported):
        raise ValueError("Original bounded terrain finding differs")
    adapter=committed(repository,ADAPTER_BASE,"src/mods/mmx6_coop_plugin.c").decode()
    setup=function(adapter,"diagnostic_setup");gate=function(adapter,"diagnostic_mutation_allowed")
    if "if (command==4)" not in setup["source"] or "return !psx_mod_netplay_is_active();" not in gate["source"]:
        raise ValueError("Frozen offline position setup contract differs")
    for row in (setup,gate):row.pop("source")
    return dict(schema=1,source_only=True,original_exe_sha256=content.EXE_SHA256,
        original_bin_sha256=content.BIN_SHA256,original_bin_member6_sha256=BIN_MEMBER_SHA,
        inventory_sha256=checkpoint.INVENTORY_SHA256,resource=resource,native_spans=native,
        layout=dict(root="800762E0",selector="80076300",address="800F286C",bytes=528,
            sha256=LAYOUT_SHA,width_screens=22,height_screens=8,layers=3,
            runtime_copy="8002798C ->80097438 via1F800004",metatiles="type0 ->1F800008",
            descriptors="type1 ->1F80000C",lookup="80028078 then80030304"),
        checkpoint=checkpoint.select(locations,sections,4,0,3),nearby_authored_objects=nearby,
        native_default_boxes=boxes,downward_dispatch=foot_dispatch,left_dispatch=left_dispatch,
        findings=[dict(id="initial_solid_column",x_inclusive=[1568,1599],y_inclusive=[1408,1679],
            sampled_tiles=len(wall),codes=sorted({r["code"] for r in wall}),
            evidence="38/39 use8003065C left collision and8002FBA4 downward solid resolution",
            limit="Initial authored layer0 only; no proof of the live mutated map or a complete route"),
            dict(id="initial_no_static_support_corridor",x_inclusive=[1600,1791],y_inclusive=[1440,2047],
            sampled_tiles=len(unsupported),codes=[0],
            evidence="Every16px cell in this scoped initial corridor resolves0",
            limit="No static support in the initial sample, not proof that no dynamic actor can support a live body")],
        camera=dict(source=[1568,1440],x_bounds=[1568,1568],y_bounds=[1440,1440],
            limit="Authored view lock is not terrain, player clamping or reachability proof"),
        marker=dict(record="800F2A8C",category=3,type=6,subtype=3,position=[1600,1584],
            handler="80052D30",initialize="80052D6C",update="80052DB8",
            native_write="80052E18 writes PLAY+1D checkpoint=3 after original visibility/X threshold",
            limit="Checkpoint marker does not create a floor or alter the initial static map in this closure"),
        source_probe_envelope=portal_probe_envelope(terrain,struct.pack("<bbBB",0,3,11,19)),
        existing_offline_setup=dict(game_commit=ADAPTER_BASE,source="src/mods/mmx6_coop_plugin.c",
            function=setup,gate=gate,command=4,command_offset="50",seat_offset="52",
            x_fixed32_offset="54",y_fixed32_offset="58",seats={"0":"residentP1","1":"privateP2","2":"both"},
            writes="body+8/+C and previous+18/+1C only; preserves other native body fields",
            restriction="Development offline only; active netplay refuses, production debug-disabled refuses",
            taint="PSX_INPUT_TAINT_GAME_MAILBOX when input-taint API exists; bypass must also be disclosed in report",
            execution_status="not_executed_no_setup_authorized_by_this_audit"),
        conclusion="A completed CP3 does not yet justify a Left/fall route; a static portal-side probe envelope still needs live safety/contact checks",
        recommended_actions=[],proven_safe_positions=[],local_coop="unverified",netplay="unverified",
        next_native_check=["Initialize disclosed CP3 and first retain both actual bodies, current+68 boxes, native ground flags and completed terrain capture",
            "Read live80097438 map bytes528; compare original layout without rewriting differences",
            "Trace actual original30304 foot query arguments/returns and2F418 ground flags during neutral ticks; do not invoke helpers or write collision scratch",
            "If neutral support is absent or body falls, retain failure and stop; no blind Left into the column or fall beyond the map",
            "If dynamic support/map changes exist, identify their producer and actual safe movement before a bounded accepted-input test; CP2 remains an unqualified alternative"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",type=Path,required=True)
    parser.add_argument("--disc",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args(); report=audit(args.original,args.disc)
    if args.check:
        if not args.out or json.loads(args.out.read_text(encoding="utf-8")) != report:
            raise SystemExit("Original terrain audit differs")
    elif args.out:
        with args.out.open("x",encoding="utf-8",newline="\n") as output:
            json.dump(report,output,indent=2);output.write("\n")
    else:
        print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
