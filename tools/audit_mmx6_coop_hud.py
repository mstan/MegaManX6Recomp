"""Reproduce the bounded R5/R6/F18 source audit; never rendered qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tomllib

import inventory_mmx6_coop_content as content

BASE = "7b584a8b3c92fdf5c1d55471264098e6d5335385"
X4 = "50593bca772b600de6911cbfecd40b0f08721147"
MANIFEST = "mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml"
DEFINITIONS = {
    "R5": "81c74475e9d391a98494c02ea516e6222e23c0a9b7bc1723dd8d15d5b7081300",
    "R6": "816c41fd64f6c08f0849577909c0ad542885ad3c868f9c7920537214fc59097f",
    "F18": "a38d30aea85bf13c358cab9c6cb0c9b46a0a4d6479d2e3962c24864a943ff845",
}
NATIVE_SPANS = (
    (0x8001EC40,0x28,"aee643b145ec5bd0c6d84dd4f8447e55f0ca64515a61fd40d4d2dfb4c971f437"),
    (0x80022960,0x278,"862212d68137a152900696ba199e93db4e8017565d327cf08ba2556150ca48a9"),
    (0x800244C0,0x1F4,"3e1b867060fb5bd38652d79ad12da92664ea304396fce2673056ed1adac40bd1"),
    (0x800249D4,0x2EC,"3797c5955432124e9620ebb9109b91c9fb1ca65d40447d5ff15f12c85ae55bad"),
    (0x80024CC0,0x2D0,"5e2b6ff172ade564b01fa5594426cd8fa7c6b0b47ec0bccbe4e5e6d852bfcf2f"),
    (0x80024F90,0x2E4,"489a97312662688d2ea683198d71684ebb1de0c056357d6bc565d28fc146c0b7"),
    (0x80025FB0,0x28,"ca6ff6777914d5a599c965d9bb0769ffb0034c5bb38c5506bac948398cd44ff6"),
    (0x80034830,0x59C,"8a1596f363d0927f5727e9ca9db8e404628b4bfe638fa4aaa885384c63257fd1"),
    (0x80071184,0xC,"515f2fba970e24991663a5c9c9b9c1231eeecb0ff1ac609a5267594803c9f5bc"),
    (0x80071E40,8,"2befe2490a9c332ae210e21a07e7d2f711a2552a041763d960119b4c0f8a8d6e"),
    (0x80073998,0x90,"b46ebdb08ccedcc13da615c558619a8b621971c4dea9cad7dc8e443963a69e7a"),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def committed(repository: Path, revision: str, path: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or path.startswith(("/", "-")) or ".." in Path(path).parts:
        raise ValueError("Committed-source lookup requires an exact revision and repository path")
    result=subprocess.run(["git","-C",str(repository),"show",f"{revision}:{path}"],
        capture_output=True,check=True,timeout=30)
    if len(result.stdout)>1_000_000:
        raise ValueError("Source audit exceeded the bounded file size")
    return result.stdout


def function(text: str, name: str) -> dict:
    """Balanced C definition, ignoring comment/string braces; no preprocessor execution."""
    match=re.search(r"\b"+re.escape(name)+r"\s*\([^;{}]*\)\s*\{",text)
    if not match:
        raise ValueError(f"Missing function {name}")
    start=match.end()-1
    token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]')
    depth=0
    for part in token.finditer(text,start):
        if part.group()=="{":depth+=1
        elif part.group()=="}":
            depth-=1
            if not depth:
                source=text[match.start():part.end()]
                return dict(line=text.count("\n",0,match.start())+1,
                    sha256=sha(source.encode()),source=source)
    raise ValueError(f"Unterminated function {name}")


def audit(repository: Path, x4_repository: Path, executable: bytes) -> dict:
    if sha(executable)!=content.EXE_SHA256:
        raise ValueError("HUD audit requires the complete pinned original EXE")
    exe=content.Executable(executable)
    source_files={p:committed(repository,BASE,p) for p in (
        "src/mods/mmx6_coop_plugin.c",MANIFEST,"game.toml","docs/COOP_PARITY_LEDGER.json",
        "docs/COOP_X4_REFERENCE_SOURCES.json")}
    plugin=source_files["src/mods/mmx6_coop_plugin.c"].decode()
    manifest=tomllib.loads(source_files[MANIFEST].decode())
    ledger=json.loads(source_files["docs/COOP_PARITY_LEDGER.json"])
    rows=[]
    for identifier,expected in DEFINITIONS.items():
        matches=[row for row in ledger["comparisons"] if row["id"]==identifier]
        if len(matches)!=1 or matches[0]["frozen_row_sha256"]!=expected:
            raise ValueError("Frozen HUD/menu comparison definition drift")
        row=matches[0]
        rows.append(dict(id=identifier,frozen_row_sha256=expected,x4=row["x4"],
            x6_bounded_check=row["x6"]["bounded_check"],
            local="unverified",netplay="unverified",rendered_status="unverified"))
    catalogue=json.loads(source_files["docs/COOP_X4_REFERENCE_SOURCES.json"])
    x4_files={}
    for path in ("src/mods/mmx4_coop_plugin.c","docs/COOP_PLAYTEST_REGRESSIONS.md",
                 "docs/COOP_PLAYTEST_FEEDBACK_20261010.md"):
        data=committed(x4_repository,X4,path)
        pinned=next(row for row in catalogue["x4"]["files"] if row["path"]==path)
        if sha(data)!=pinned["sha256"]:
            raise ValueError("Frozen X4 source identity drift")
        x4_files[path]=data
    functions={name:function(plugin,name) for name in (
        "hud_tile_bank","hud_icon","hud_zero_packets","draw_coop_hud","render","render_survivor","stage_tick")}
    for row in functions.values():row.pop("source")
    native=[]
    for address,size,expected in NATIVE_SPANS:
        at=exe.offset(address,size);data=executable[at:at+size]
        if sha(data)!=expected:raise ValueError("Original HUD/menu source span drift")
        calls=[]
        for offset in range(0,size,4):
            word=struct.unpack_from("<I",data,offset)[0]
            if word>>26==3:
                pc=address+offset
                calls.append(dict(pc=f"{pc:08X}",target=f"{((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2):08X}"))
        native.append(dict(address=f"{address:08X}",size=size,sha256=expected,direct_calls=calls))
    y=int(re.search(r"P2_HUD_Y\s*=\s*(\d+)",plugin)[1])
    return dict(schema_version=1,scope=["R5","R6","F18"],source_only=True,
        game_commit=BASE,x4_commit=X4,source_exe_sha256=content.EXE_SHA256,
        sources=[dict(path=p,sha256=sha(data),bytes=len(data)) for p,data in source_files.items()],
        x4_sources=[dict(path=p,sha256=sha(data),bytes=len(data)) for p,data in x4_files.items()],
        functions=functions,native_spans=native,comparisons=rows,
        layout=dict(default="stacked",p2_translation=dict(x=0,y=y),explicit_p2_anchor=-1,
            native_hp_xy=list(struct.unpack_from("<2h",executable,exe.offset(0x80071E40,4))),
            package_option_count=len(manifest.get("option",[])),hud_layout_control="absent",
            optional_side_by_side="implementation_missing_at_frozen_game_commit"),
        ownership=dict(roster=["X/P1","Zero/P2"],native_p1_and_boss_hud_calls=1,
            private_p2_calls=["80024F90","800249D4"],shared_life_digit_icons_suppressed=[3,4],
            hp="PLAYER+5C & 7F; maximum PLAY+5B+PLAYER.character",
            ammo="PLAYER+93 selects signed-halfword PLAYER+A8+2*weapon; capacity PLAYER+14A",
            shared_lives="PLAY+39; shown once by original P1 path",
            private_art="original Zero UI pixels and current native CLUT retained in16x16 banks"),
        visibility=dict(hud_gate="enrolled && !failed && PLAY.major==0A; native PLAY+1F enables meters",
            p2_fade="LEAVING/ABSENT: -8 toward0; every other lifecycle: +8 toward128, per HUD call",
            body_gate="render() is skipped while inside; native visible bit +3 and actual PLAYER dispatch gate supplement",
            p2_owned_menu_prediction="zero_world original PLAYER dispatch renders projected P2; stored P1 only added for DYING or scene_passenger(0), excluding ordinary living P1",
            prediction_status="unverified_until_actual_completed_transition_packet_and_composed_capture",
            frontend_boundaries="R7/Quit owned separately; no frontend state is qualified here"),
        required_native_checks=[
            "R5: both composed meter anchors after genuine separate HP/ammo changes,4:3 and expanded/resized drawable",
            "R6: actual installed stacked and side_by_side controls, native portrait/HP/ammo ownership and original shared life display",
            "F18: both menu owners, opening/closing, retain completed world/UI packet provenance and composed frames; require both bodies/meters exactly when native world draws",
            "Each check needs exact candidate/build/settings/input/capture identity; local and netplay remain separate unverified results"],
        limits=["Committed source only; no X4/X5 pass transfer", "No native game/build/capture was performed by this audit",
            "Native table/call presence and capture acknowledgement cannot establish rendered visibility",
            "Native menu call windows are bounded locators, not a complete frontend/substate classification"])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--x4-repository",type=Path,required=True)
    parser.add_argument("--exe",type=Path,required=True)
    destination=parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output",type=Path)
    destination.add_argument("--check",type=Path)
    args=parser.parse_args(argv)
    if args.exe.stat().st_size!=522240:parser.error("Expected bounded original EXE")
    rendered=json.dumps(audit(args.repository,args.x4_repository,args.exe.read_bytes()),indent=2)+"\n"
    if args.check:
        if args.check.read_text(encoding="utf-8")!=rendered:raise SystemExit("HUD source audit differs")
    else:
        with args.output.open("x",encoding="utf-8",newline="\n") as stream:stream.write(rendered)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
