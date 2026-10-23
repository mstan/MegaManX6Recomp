"""Bounded original R3/F4 source reproduction; never native/artwork qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

from audit_mmx6_coop_hud import committed, function
import inventory_mmx6_coop_content as content

BASE="d1263e0acc75ae33368b6110a07d95d23e2d0987"
DEFINITIONS={"R3":"fe414d5fc0d4959b059e49d17593e36ccd9894b66536a647ae69ff926949e8d4",
             "F4":"f6583dbd4f3ff376f8a5232a67ef9e288cf928f9b6fd88ad4ed2f820973e42d1"}
MEMBERS={1:"75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00",
         2:"d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607"}
SPANS=(
 (0x8003CC78,0x3C,"10188abaf6ccb6d94a537c07b76a3836524ab81bf831b7559253443a6d1480f7"),
 (0x80034DCC,0x1EC,"db13690cac03abb675fbbf316f430f16034c175f4dd18671b4b0b4f315b0f2cb"),
 (0x8003D8A8,0x334,"0acb744f6b17ddc5abd76c437b7eb862f02e60c3dd57985b7cc068d8b6e1b02c"),
 (0x80047E34,0x1FC,"deef90ae2da4cd7d3dca105f966945ab00b40538345c472da45d822f3ffc67c8"),
 (0x8002C530,0x60,"9bb1ebe6d89446e08525884b81b9289f5f64ddc2b3388a05855c7e49482be2e5"),
 (0x800206C0,0x114,"537c3d2eca94eee410554c054b08bb049562190e4c0f435e364544c293118ffb"),
 (0x80020C40,0xC4,"0420ce4f4df1aa2567b932ec9af2524a174f99b07c0b99d85dd6b64646090a97"),
 (0x80022D00,0x60,"cbe25621d8576c75ae0bbe0a6797af378db4c7a5c57cbd7276cc70b2fd088b98"),
 (0x8002CBFC,0x170,"dbf1d709e13fb55fd9a0dcf1cc1065f4357e63a2002b5a0ff6186f0356909c43"),
 (0x800179A4,0xA4,"5c20240edf12b2a5163779c23b686ca8363678966d8c7d41a1d68ab971b65987"),
 (0x8002D2B0,0x24,"27a83fee52c62b7f4a185b41056e43b5a60e2f28525f99a487853d5a7366979a"),
 (0x8002D3B4,0xA0,"dfa4a4ad9d3cdbb3fad35ff1c2f1fe858f9db7e30c8e27e77c45395d62043664"),
 (0x8002C9B0,0x24,"46cbc9828aa67de8b5cb54342b05138bed1ad1f9b6b3a777a978748035b883d1"),
 (0x80073ABC,0x10,"4b5885c27c56c6350076ed02c211cab88eccf381b3ff6d31a1cb36d09456f665"),
 (0x80073D20,0x30,"ff43cffe394d5ef25edf1c174919e88c26a03d4ee157a2a2a52387e03508b25b"),
 (0x8007789C,0x20,"3502724f536f1596ebee536eb64b405542fa63426a0f1c76c7068e4643f0d981"),
 (0x80076BDC,0x24,"fae4b995d86f7b48a69f07e5a585afd3496cd40afc9429e55e06533ee064cea6"),
 (0x80077B20,4,"61aa5ff2e9f00a11d14da08c8b422b8d5d873e242280cadcdb91bcaeb0dadf5d"),
)


def sha(data):return hashlib.sha256(data).hexdigest()


def direct_calls(data: bytes,base: int) -> list[dict]:
    if len(data)%4 or base&3:raise ValueError("Aligned native code extent required")
    return [dict(pc=f"{base+at:08X}",target=f"{((base+at+4)&0xF0000000)|((word&0x3FFFFFF)<<2):08X}")
        for at in range(0,len(data),4)
        if (word:=struct.unpack_from("<I",data,at)[0])>>26==3]


def emission_schedule(exe: content.Executable) -> dict:
    """Static D6/D7 accounting from pinned MIPS immediates; not a frame emulator.

    Counts attempts before allocator success; camera motion/freeze/slot capacity
    are deliberately outside this original one-entry emission contract.
    """
    mask,random_count,terminal,wait,radial_count=(exe.word(pc)&0xFFFF for pc in
        (0x8003DA14,0x8003DA3C,0x8003DA4C,0x8003DA8C,0x8003DBB0))
    if (mask,random_count,terminal,wait,radial_count)!=(3,4,3,18,8):
        raise ValueError("Unsupported original death-counter contract")
    group=timer=0;events=[]
    for invocation in range(256):
        random=random_count if not timer&mask else 0
        radial=[]
        if group!=terminal and not timer:
            radial=[group]+([3] if group==2 else [])
        if random or radial:events.append(dict(invocation=invocation,random_attempts=random,
            radial_groups=radial,radial_attempts=len(radial)*radial_count))
        if group==terminal:
            return dict(initial_group=0,initial_timer=0,invocations=invocation+1,
                random_attempts=sum(r["random_attempts"] for r in events),
                radial_attempts=sum(r["radial_attempts"] for r in events),events=events,
                unit="accepted_native_emitter_invocations_not_wall_clock_frames",
                runtime_status="unverified")
        if timer:timer-=1
        else:timer=wait;group+=1
    raise ValueError("Original emitter did not terminate within bounded source accounting")


def audit(repository: Path,executable: bytes,archive: bytes) -> dict:
    if sha(executable)!=content.EXE_SHA256 or sha(archive)!=content.BIN_SHA256:
        raise ValueError("Death audit requires the pinned complete original EXE/archive")
    exe=content.Executable(executable);members=content.archive_members(archive)
    selected=[]
    for index,expected in MEMBERS.items():
        member=members[index]
        if member["sha256"]!=expected:raise ValueError("Original selected member identity differs")
        selected.append(member)
    intro=selected[1];start=intro["sector"]*2048
    if exe.word(0x8006E004)!=0x800FA814 or \
       struct.unpack_from("<I",archive,start+0x800FA858-0x800E9860)[0]!=0x80047F78:
        raise ValueError("Intro native FX11 handler table differs")
    native=[]
    for address,size,expected in SPANS:
        at=exe.offset(address,size);data=executable[at:at+size]
        if sha(data)!=expected:raise ValueError("Original death code/data extent differs")
        native.append(dict(address=f"{address:08X}",size=size,sha256=expected,
            direct_calls=direct_calls(data,address)))
    files={path:committed(repository,BASE,path) for path in (
        "src/mods/mmx6_coop_plugin.c","src/mods/mmx6_coop_lifecycle.c",
        "src/mods/mmx6_coop_snapshot.inc","docs/COOP_PARITY_LEDGER.json")}
    ledger=json.loads(files["docs/COOP_PARITY_LEDGER.json"]);rows=[]
    for identifier,expected in DEFINITIONS.items():
        matches=[r for r in ledger["comparisons"] if r["id"]==identifier]
        if len(matches)!=1 or matches[0]["frozen_row_sha256"]!=expected:raise ValueError("Frozen death definition drift")
        row=matches[0];rows.append(dict(id=identifier,frozen_row_sha256=expected,x4=row["x4"],
            bounded_check=row["x6"]["bounded_check"],local="unverified",netplay="unverified"))
    plugin=files["src/mods/mmx6_coop_plugin.c"].decode()
    functions={name:function(plugin,name) for name in ("death_effect_allocate","death_effect_init",
        "player_tick","stage_tick","controller","render_survivor","render_actor","sprite_bank")}
    for row in functions.values():row.pop("source")
    angles=list(struct.unpack_from("<32B",executable,exe.offset(0x80073D30,32)))
    animations=[]
    for animation,count in ((6,5),(7,4)):
        address=exe.word(0x8007789C+animation*4)
        words=[exe.word(address+index*4) for index in range(count)]
        animations.append(dict(animation=animation,address=f"{address:08X}",
            frames=[w>>24 for w in words],delays=[w&255 for w in words],
            final_signed_stride=((words[-1]>>16)&255)-256))
    return dict(schema_version=1,scope=["R3","F4"],source_only=True,game_commit=BASE,
        source_exe_sha256=content.EXE_SHA256,archive_sha256=content.BIN_SHA256,
        selected_members=selected,native_spans=native,
        sources=[dict(path=p,bytes=len(data),sha256=sha(data)) for p,data in files.items()],
        functions=functions,comparisons=rows,
        native_dispatch=dict(player_phase2="80073ABC[2] ->8003CC78",death_subphases="80073D20",
            phases=[f"{exe.word(0x80073D20+i*4):08X}" for i in range(4)],
            fx_root="8006E004 ->800FA814",fx11_handler="800FA858 ->80047F78",
            fx_update="800206C0; native controller JAL80020C98",fx_draw="80022D30 ->800232D4 (visible1);80022D48 ->800239CC (visible2)"),
        pool=dict(base="800CD410",end="800CF810",count=96,stride=96,allocator="8002C530",
            allocation_field="+0",type_field="+1=11h",subtype_field="+2",visible_field="+3",
            phase_field="+4",position_fields=["+8 wordfixedX","+C wordfixedY"],
            velocity_fields=["+20 wordVX","+24 wordVY"],parent="none: initialization copies singleton PLAYER origin",
            initializer="80047E34",update="80047FB8"),
        emission=emission_schedule(exe),radial_angles=[angles[i:i+8] for i in range(0,32,8)],
        native_resource=dict(animation_table="8007789C",animations=animations,
            compression_pointer="+38=0",assembly="SCRATCH+1C + word[+4] -> effect+3C",
            tile_page="+40=0",clut="+42=7802h (VRAM x32,y480,16colors)",priority="+16=10h",
            origin="PLAYER+8/+C and layer+14 copied at initialization, not allocation",
            random="subtype80h|RNG&1Fh; native velocity multiplied by8; animation7",
            radial="angle&1Fh; velocity scaled using[1,3,2,3] by low2bits; animation6"),
        retirement=dict(random="80047FDC tests fixed320x240+8px bounds; true ->8002C9B0 clears allocated/visible",
            radial="no explicit deallocation in this update;8002CCB0 recalculates visible against native camera/width, allocated slots may persist",
            animation="6/7 loop native glyph frames; not a lifetime timer",freeze="PLAY+17 gates global update; paused/frozen publications are not particle updates"),
        adapter=dict(origin="allocation RA8003DB0C/8003DB8C captures X/Y/layer/assembly per96slots; any wrapped allocation invalidates prior slot receipt",
            delayed_init="80047E34 replacement consumes valid receipt once, projects only origin/layer/assembly, calls original once and restores",
            snapshot="pending origin receipts participate in existing host snapshot/digest; no new state added by audit",
            once_world="private player/attack/contact/attached/trail pass does not add800206C0; survivor/scene calls original world once",
            death_entry="fatal accepts a living actor once; private nativeD6/D7/body context retained; no source-proven repeat-emitter defect",
            atlas_gap="global death pool excluded from private render_survivor/render actor bank admission; original native shared atlas/CLUT remains in use"),
        findings=[dict(id="native76",classification="source_proven_native_behavior",text="44random+32radial are original attempts per one ordinary zeroedD6/D7 emitter; successful allocations may be fewer"),
            dict(id="radial-allocation",classification="source_proven_native_behavior",text="allocated-but-invisible radial slots do not alone prove a leak"),
            dict(id="origin-adapter",classification="source_proven_existing_ownership_adapter",text="allocation origin/layer/assembly retained for delayed init; native runtime origin/restoration remains unverified"),
            dict(id="atlas-color",classification="unverified_resource_gap",text="private global particles keep native atlas/7802CLUT path; wrong pixels/colors cannot be concluded without original Zero and X reference"),
            dict(id="repeat-burst",classification="unverified_runtime_obligation",text="no source-proven excess emitter repetition; actual scene-owner death allocation/update/retirement/progress trace needed")],
        required_native_checks=["Separate-seat distinct-position original X/P1 and Zero/P2 fatal admissions with native body phase/timers and survivor input",
            "Count producer-specific allocation attempts by true caller; normalize wrapper/original duplicates and exclude unrelated globalFX",
            "Native global updates, visibility and deallocation separately; count no frozen/menu ticks as lifetime progress",
            "Original co-op-off Zero/X particle glyph/CLUT/atlas reference plus completed composed death captures and source palette samples",
            "Actual scene owner fatal before release; bounded world progress and passenger recovery; both local/netplay on exact candidate"],
        limits=["No native game/build/capture or ledger update by this audit","Source accounting is not native frame cadence, ordinary60FPS performance or rendered qualification",
            "Selected Zero/intro members only; no full-disc content crawl or opposite-roster claim","No X4/X5 counts, palette addresses or passed results transferred"])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--exe",type=Path,required=True);parser.add_argument("--disc",type=Path,required=True)
    destination=parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output",type=Path);destination.add_argument("--check",type=Path)
    args=parser.parse_args(argv)
    if args.exe.stat().st_size!=522240:parser.error("Expected bounded original EXE")
    raw=content.RawDisc(args.disc)
    try:archive=raw.extent(211185,1665024)
    finally:raw.stream.close()
    rendered=json.dumps(audit(args.repository,args.exe.read_bytes(),archive),indent=2)+"\n"
    if args.check:
        if args.check.read_text(encoding="utf-8")!=rendered:raise SystemExit("Death source audit differs")
    else:
        with args.output.open("x",encoding="utf-8",newline="\n") as stream:stream.write(rendered)
    return 0


if __name__=="__main__":raise SystemExit(main())
