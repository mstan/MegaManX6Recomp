"""Owned offline native Zero/P1 renderer reference; parent owns launch/stop.

Fresh real mod state disables co-op before process creation. The optional
unlock/screen prerequisite is source-guarded, reported and taints ordinary
campaign/input evidence. No cards, success flags, actor/form/table writes,
online fixture, private GPU bank, ledger status or artwork pass is produced.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time
import tomllib

import coop_debug as debug
import inventory_mmx6_coop_content as content
from mmx6_coop_private_effects import NativeEffect, TRAIL_CLUTS
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline

PLAY, PLAYER, TRAILS = 0x800CCED0, 0x800970A0, 0x800972F8
BODY_AND_TRAILS_BYTES = 0x378  # body158h + native camera100h + trails120h.
MENU_BASE, MENU_MEMBER, ZERO_MEMBER = 0x800E9860, 16, 1
MENU_TABLE, MENU_COUNT = 0x800F1CB0, 0x800F1CEB
MENU_SHA = "c9211aee86c5e7377b7716bd698102da1aed8c57a128e90507259cf9f6093ecf"
ZERO_SHA = "75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00"
DISABLED_STATE = "native-zero-reference-state.json"
EXE_GUARDS = ((0x8001E6E4,0x8001E730), (0x8001E8CC,0x8001E914),
              (0x80013BF0,0x80013D10), (0x8003BD24,0x8003C140),
              (0x80020DC8,0x800210D0), (0x80022960,0x80022BD8))
MENU_GUARDS = ((0x800E9898,0x800E99A4), (0x800EB174,0x800EB1A0))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _forward(old: int, new: int, minimum: int = 1) -> bool:
    return minimum <= ((new-old)&0xFFFFFFFF) < 0x80000000


def _window(payload: bytes, base: int, first: int, end: int) -> bytes:
    if first < base or end <= first or end-base > len(payload):
        raise ValueError("Native reference source window escaped pinned member")
    return payload[first-base:end-base]


def load_sources(original_disc: Path) -> dict:
    disc=content.RawDisc(Path(original_disc))
    try: files=disc.inventory_files()
    finally: disc.stream.close()
    if _sha(files["SLUS_013.95"]) != content.EXE_SHA256 or _sha(files["ROCK_X6.BIN"]) != content.BIN_SHA256:
        raise ValueError("Reference needs clean original SLUS-01395v1.1 EXE/BIN identity")
    exe=content.Executable(files["SLUS_013.95"])
    archive=files["ROCK_X6.BIN"]; members=content.archive_members(archive)
    result=dict(exe=exe.data[2048:2048+exe.size], exe_base=exe.base)
    for name,index,expected in (("menu",MENU_MEMBER,MENU_SHA),("zero",ZERO_MEMBER,ZERO_SHA)):
        member=members[index];start=member["sector"]*2048
        payload=archive[start:start+member["size"]]
        if _sha(payload) != expected:
            raise ValueError("Reference native menu/Zero member identity changed")
        result[name]=payload
    if exe.word(0x8007112C+2*4) != 0x8001E908:
        raise ValueError("Native screen2 dispatch contract changed")
    return result


def _catalog_features(candidate: Path) -> list[tuple[str,str,list[str]]]:
    rows=[];seen=set()
    for path in sorted((candidate/"mods/bundled").glob("*/*/manifest.toml")):
        record=tomllib.loads(path.read_text(encoding="utf-8-sig"))
        identifier,version=record["id"],record["version"]
        if identifier in seen:
            raise ValueError("Native reference catalog needs one explicit version per package")
        seen.add(identifier)
        rows.append((identifier,version,[f["id"] for f in record.get("feature",[])]))
    if not any(package=="mmx6.local-coop" and "prototype" in features for package,_,features in rows):
        raise ValueError("Reference catalog must explicitly contain the disabled co-op feature")
    return rows


def disable_reference_mods(candidate: Path) -> dict:
    """Before launch only: write real state, every catalog feature false."""
    candidate=preparation.local_output(candidate).resolve(strict=True)
    prepared=json.loads((candidate/"preparation.json").read_text(encoding="utf-8"))
    if prepared.get("source_card") is not None or prepared.get("source_card_sha256") is not None or prepared.get("automated_profile") is not True:
        raise ValueError("Reference needs a fresh automated private profile without source cards")
    for name in ("saves","data","appdata","resident","cache"):
        folder=(candidate/name).resolve(strict=True)
        if not folder.is_relative_to(candidate) or not folder.is_dir() or next(folder.iterdir(),None) is not None:
            raise ValueError("Reference profile must be pristine before real mod-state setup")
    if any((candidate/name).exists() for name in (DISABLED_STATE,"baseline","native-zero-reference")):
        raise ValueError("Retain earlier reference attempts; use a fresh profile")
    lines=["format_version = 2"]
    for package,version,features in _catalog_features(candidate):
        lines += ["[[package]]",f"id = {json.dumps(package)}",f"version = {json.dumps(version)}"]
        for feature in features:
            lines += ["[[feature]]",f"package_id = {json.dumps(package)}",f"id = {json.dumps(feature)}","enabled = false"]
    state="\n".join(lines)+"\n"
    (candidate/"mods/state.toml").write_bytes(state.encode("utf-8"))
    receipt=dict(kind="offline_native_zero_reference_mod_state",coop_enabled=False,
        all_catalog_features_disabled=True,state_sha256=_sha(state.encode()),
        candidate_exe_sha256=prepared["exe_sha256"],source_cards=False,
        limits=["Real offline mod state; netplay forced profiles are unsupported",
                "Staging and state do not establish runtime artwork correctness"])
    (candidate/DISABLED_STATE).write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    return receipt


def prepare_reference_profile(build: Path, source: Path, output: Path, disc: Path,
                              *, expected_exe_sha256: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}",expected_exe_sha256) or preparation.sha256(Path(build)/"mmx6-runtime.exe") != expected_exe_sha256:
        raise ValueError("Reference preparation needs the exact expected running-image SHA256")
    prepared=preparation.prepare(build,source,output,disc,automated=True)
    return dict(preparation=prepared,mod_state=disable_reference_mods(output))


def validate_reference_profile(candidate: Path, expected_sha: str) -> dict:
    candidate=preparation.local_output(candidate).resolve(strict=True)
    prepared=json.loads((candidate/"preparation.json").read_text(encoding="utf-8"))
    receipt=json.loads((candidate/DISABLED_STATE).read_text(encoding="utf-8"))
    if (not re.fullmatch(r"[0-9a-f]{64}",expected_sha) or prepared.get("exe_sha256") != expected_sha or
            preparation.sha256(candidate/"mmx6-runtime.exe") != expected_sha or
            receipt.get("candidate_exe_sha256") != expected_sha or receipt.get("coop_enabled") is not False or
            prepared.get("source_card") is not None or prepared.get("source_card_sha256") is not None or
            prepared.get("automated_profile") is not True):
        raise ValueError("Reference profile/image/private-card binding is invalid")
    state_data=(candidate/"mods/state.toml").read_bytes()
    if _sha(state_data) != receipt["state_sha256"]:
        raise ValueError("Reference real mod state changed after preparation")
    state=tomllib.loads(state_data.decode("utf-8"))
    features=state.get("feature",[])
    actual=[(f.get("package_id"),f.get("id")) for f in features]
    expected=[(package,feature) for package,_,items in _catalog_features(candidate) for feature in items]
    if (state.get("format_version") != 2 or len(set(actual)) != len(actual) or set(actual) != set(expected) or
            any(f.get("enabled") is not False for f in features)):
        raise ValueError("Reference must explicitly disable every catalog feature in real mod state")
    saves=(candidate/"saves").resolve(strict=True)
    if not saves.is_relative_to(candidate) or any(not p.resolve(strict=True).is_relative_to(candidate) for p in saves.glob("*.mcd")):
        raise ValueError("Reference native cards must remain inside its private profile")
    baseline.candidate_environment(candidate,prepared)
    return dict(preparation=prepared,mod_state=receipt)


def process_image_path(pid: int) -> Path:
    """Query the actual Windows process image; no argv/string identity guess."""
    if os.name != "nt":
        raise debug.DebugError("Native reference process-image proof is qualified on Windows only")
    from ctypes import wintypes
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=(wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        raise debug.DebugError("Cannot inspect owned native reference process image")
    try:
        length=wintypes.DWORD(32768);buffer=ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(length)):
            raise debug.DebugError("Cannot resolve owned process image")
        return Path(buffer.value).resolve(strict=True)
    finally:
        kernel.CloseHandle(handle)


class OwnedNativeSession:
    """Every RPC uses the original Popen handle and actual listener PID guard."""
    ALLOWED=frozenset(("read_ram","netplay_status","pad_status","press","clear_input",
                       "present_shot","present_shot_seq","vram_peek","gl_fbo_peek","gpu_state","write_ram"))

    def __init__(self,process,port: int,candidate: Path,expected_sha: str):
        self.process,self.port=process,port
        self.candidate=Path(candidate).resolve(strict=True)
        self.profile=validate_reference_profile(self.candidate,expected_sha)
        self.image_path=process_image_path(process.pid) if process.poll() is None else None
        if self.image_path != (self.candidate/"mmx6-runtime.exe").resolve(strict=True):
            raise debug.DebugError("Owned reference process is not the explicitly bound candidate image")
        self.image_sha256=preparation.sha256(self.image_path)
        if self.image_sha256 != expected_sha:
            raise debug.DebugError("Actual owned process image path differs from expected SHA256")
        self.client=debug.DebugClient(port)
        self.offline()

    def request(self,command,**fields):
        if command not in self.ALLOWED:
            raise debug.DebugError("Reference case requested an unsupported control")
        if self.process.poll() is not None or not baseline.owns_listener(self.port,self.process.pid):
            raise debug.DebugError("Owned reference process does not own the listener")
        if command=="write_ram":
            try: address,value=int(fields["addr"],0),int(fields["val"],0)
            except (KeyError,TypeError,ValueError):raise debug.DebugError("Invalid private prerequisite byte")
            if address not in (PLAY,PLAY+1,PLAY+2,PLAY+0x5F) or not 0<=value<=255:
                raise debug.DebugError("Reference refuses actor/progression/success writes")
        if command=="press" and (fields.get("port")!=1 or fields.get("frames")!=0):
            raise debug.DebugError("Reference uses only bounded original held NativePad P1 input")
        return self.client.request(command,**fields)

    def read(self,address,size):
        return debug.DebugClient.read(self,address,size)

    def offline(self):
        status=self.request("netplay_status")
        if type(status.get("active")) is not int or status["active"] != 0:
            raise debug.DebugError("Native reference requires an explicitly inactive offline session")
        return status


def read_native(session) -> dict:
    """Body/camera/three trails are ONE RPC; clock brackets are separate."""
    before=session.read(PLAY,0x94)
    raw=session.read(PLAYER,BODY_AND_TRAILS_BYTES)
    after=session.read(PLAY,0x94)
    if len(before) != 0x94 or len(after) != 0x94 or len(raw) != BODY_AND_TRAILS_BYTES:
        raise debug.DebugError("Truncated native reference observation")
    if before[:3] != after[:3] or before[0x90:0x94] != after[0x90:0x94]:
        raise debug.UnstableObservation("Native clock/mode advanced across separate clock/pool RPCs")
    body=raw[:0x158]
    pools=raw[TRAILS-PLAYER:]
    player=debug.Player.parse(body)
    return dict(native_mode=after[0],native_phase=after[1],native_subphase=after[2],
        stage=after[0x0C],section=after[0x0D],native_timer=struct.unpack_from("<I",after,0x90)[0],
        campaign_character=after[0x38],form=after[0x5E],unlocks=after[0x5F],
        body_form=body[0xE7],
        player=player.__dict__,body_hex=body.hex(),marker=struct.unpack_from("<b",body,0x8C)[0],
        animation_table=struct.unpack_from("<I",body,0x30)[0],
        compression=struct.unpack_from("<I",body,0x38)[0],assembly=struct.unpack_from("<I",body,0x3C)[0],
        page=struct.unpack_from("<H",body,0x40)[0],clut=struct.unpack_from("<H",body,0x42)[0],
        frame=body[0x47],facing=body[0x15],
        trails=[NativeEffect.parse(pools[i*0x60:(i+1)*0x60],"trails",i).__dict__ for i in range(3)],
        observation_limit="Body and pools share one RPC; PLAY clock/mode are separately bracketed, not one atomic cross-RPC snapshot")


def native_zero(row: dict) -> bool:
    p=row["player"]
    return (row["native_mode"]==10 and row["native_phase"]==0 and row["campaign_character"]==1 and
        row["form"]==row["body_form"]==5 and not row["unlocks"]&0x20 and p["active"] and p["character"]==1 and
        p["state"]==1 and 0<p["hp"]<128 and row["animation_table"]==0x801EF6D0 and
        all(0x80010000<=row[field]<0x80200000 for field in ("compression","assembly")))


def visible_dash(row: dict) -> bool:
    return (native_zero(row) and row["marker"]>0 and row["player"]["action"] in (6,0x0C) and
        len(row["trails"])==3 and all(t["visible"]==t["active"]==1 and t["phase"]==0 and
            (t["compression"],t["assembly"],t["frame"],t["facing"],t["clut"])==
            (row["compression"],row["assembly"],row["frame"],row["facing"],TRAIL_CLUTS[t["slot"]])
            for t in row["trails"]))


def _guard_code(session,sources,key,base,windows,receipt):
    for first,end in windows:
        expected=_window(sources[key],base,first,end)
        actual=session.read(first,end-first)
        record=dict(region=key,first=hex(first),end_exclusive=hex(end),sha256=_sha(actual),expected_sha256=_sha(expected))
        receipt.append(record)
        if actual != expected:
            raise debug.DebugError("Native reference live code guard differs from clean original source")


def _read_mode(session):
    return tuple(session.read(PLAY,3))


def _menu_press(session,bits,predicate,*,timeout=2):
    session.offline()
    try:
        session.request("press",port=1,buttons=bits^0xFFFF,frames=0)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.015)
        raise debug.DebugError("Original native menu input did not reach the bounded expected transition")
    finally:
        session.request("clear_input",port=1)


def select_native_zero(session,sources,receipt: dict,*,allow_private_prerequisite=False,timeout=60):
    """Uses the original menu, never assigns form/character/cursor/table bytes."""
    if type(allow_private_prerequisite) is not bool or not math.isfinite(timeout) or not 0<timeout<=180:
        raise ValueError("Native selection requires an explicit bypass boolean and bounded deadline")
    receipt.update(status="failed_setup",prerequisite_bypass=False,ordinary_input_evidence_tainted=False,
                   bypasses=[],code_guards=[],inputs=[])
    session.offline()
    session.request("clear_input",port=1)
    receipt["inputs"].append(dict(pressed=0,purpose="release parent boot input before native selection"))
    _guard_code(session,sources,"exe",sources["exe_base"],EXE_GUARDS,receipt["code_guards"])
    mode=_read_mode(session)
    flags=session.read(PLAY+0x5F,1)[0]
    if flags&0xE0:
        raise debug.DebugError("Reference supports base Zero only; do not clear a native Black Zero/unknown variant")
    if mode[0]!=4 or mode[1:]!=(4,0) or not flags&0x10:
        if not allow_private_prerequisite:
            raise debug.DebugError("Native Zero selector prerequisite absent; explicit private bypass permission required")
        body=debug.Player.parse(session.read(PLAYER,0x158))
        if mode[:2]!=(10,0) or not body.active or body.state!=1 or body.action!=2 or not 0<body.hp<128:
            raise debug.DebugError("Private native-selector prerequisite requires a living idle gameplay body")
        receipt.update(prerequisite_bypass=True,ordinary_input_evidence_tainted=True)
        for address,old,new,reason in ((PLAY+0x5F,flags,flags|0x10,"private Zero availability bit10"),
            (PLAY+1,mode[1],0,"native screen phase initialization"),
            (PLAY+2,mode[2],0,"native screen subphase initialization"),(PLAY,mode[0],2,"native screen2 loader prerequisite")):
            receipt["bypasses"].append(dict(address=hex(address),before=old,after=new,reason=reason))
            session.request("write_ram",addr=hex(address),val=hex(new))
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        mode=_read_mode(session)
        if mode==(4,4,0):break
        if mode[:2]==(4,11):
            old=mode
            _menu_press(session,0x4000,lambda:_read_mode(session)!=old,timeout=min(2,timeout))
            receipt["inputs"].append(dict(pressed=0x4000,purpose="native briefing dismissal"))
        else:time.sleep(.03)
    else:raise debug.DebugError("Native stage map did not become input-ready")
    _guard_code(session,sources,"menu",MENU_BASE,MENU_GUARDS,receipt["code_guards"])
    count=session.read(MENU_COUNT,1)[0]
    if not 1<=count<=6:raise debug.DebugError("Native unit count is invalid")
    choices=list(session.read(MENU_TABLE,count))
    flags=session.read(PLAY+0x5F,1)[0]
    expected=[unit for unit,mask in ((0,0),(1,1),(5,0x10),(2,2),(3,4),(4,8)) if not mask or flags&mask]
    receipt.update(native_choices=choices,native_unlocks=flags)
    if choices!=expected or 5 not in choices:
        raise debug.DebugError("Native unit5 list absent/filtered; reference co-op-disabled contract failed")
    _menu_press(session,0x4000,lambda:_read_mode(session)==(4,4,5))
    receipt["inputs"].append(dict(pressed=0x4000,purpose="open native unit selector"))
    for _ in range(count):
        cursor=session.read(PLAY+0x30,1)[0]
        if cursor>=count:raise debug.DebugError("Native unit cursor escaped source list")
        if choices[cursor]==5:break
        _menu_press(session,0x20,lambda:session.read(PLAY+0x30,1)[0]!=(cursor))
        receipt["inputs"].append(dict(pressed=0x20,purpose="native unit cursor",before=cursor))
    else:raise debug.DebugError("Native unit selector never reached Zero")
    _menu_press(session,0x4000,lambda:_read_mode(session)!=(4,4,5))
    receipt["inputs"].append(dict(pressed=0x4000,purpose="confirm native Zero"))
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if _read_mode(session)[:2]!=(10,0):
            time.sleep(.02)
            continue
        actor=debug.Player.parse(session.read(PLAYER,0x158))
        if actor.character!=1 or actor.state!=1 or actor.action!=2 or not actor.active:
            time.sleep(.02)
            continue
        try:row=read_native(session)
        except debug.UnstableObservation:continue
        if native_zero(row) and row["player"]["action"]==2:
            receipt.update(status="native_zero_selected",after=row)
            return row
        time.sleep(.02)
    raise debug.DebugError("Native stage confirmation never produced a living idle Zero/P1")


def read_trail_palettes(session) -> dict:
    x,y=(TRAIL_CLUTS[0]&63)*16,TRAIL_CLUTS[0]>>6
    result={}
    for command in ("vram_peek","gl_fbo_peek"):
        response=session.request(command,x=x,y=y,w=48,h=1)
        raw=response.get("hex")
        if (response.get("x"),response.get("y"),response.get("w"),response.get("h"))!=(x,y,48,1) or not isinstance(raw,str) or not re.fullmatch(r"[0-9a-fA-F]{192}",raw):
            raise debug.DebugError("Native trail palette peek omitted exact48 RGB555 words")
        colors=[int(raw[i:i+4],16) for i in range(0,192,4)]
        if any(not any(colors[i*16:(i+1)*16]) for i in range(3)):
            raise debug.DebugError("Native trail CLUT row is empty; resource/art reference unavailable")
        result[command]=dict(response=response,cluts=list(TRAIL_CLUTS),colors=colors,
            sha256=_sha(struct.pack("<48H",*colors)))
    result["limit"]="CPU and GL palette reads are separate RPCs, distinct from composed capture"
    return result


def reduce_native_reference(before,active,released,capture_window,*,max_drain_ticks=32) -> dict:
    checks=dict(native_zero_roster=False,accepted_positive_marker=False,all_native_trails_visible=False,
                capture_bracketed_by_visible_dash=False,negative_drain_phases=False,finite_retirement=False,
                native_resources_and_cluts_retained=False,ordered_native_clock=False)
    rows=[before,*active,*released]
    if not active or not released:return checks
    checks["native_zero_roster"]=all(native_zero(r) for r in rows)
    checks["ordered_native_clock"]=(all(_forward(a["native_timer"],b["native_timer"],0) for a,b in zip(rows,rows[1:])) and
        _forward(before["native_timer"],active[-1]["native_timer"]) and _forward(active[-1]["native_timer"],released[-1]["native_timer"]))
    checks["accepted_positive_marker"]=before["marker"]==0 and any(visible_dash(r) for r in active)
    checks["all_native_trails_visible"]=any(visible_dash(r) for r in active)
    checks["capture_bracketed_by_visible_dash"]=(len(capture_window)==2 and all(visible_dash(r) for r in capture_window) and
        _forward(capture_window[0]["native_timer"],capture_window[1]["native_timer"],0))
    draining=[r for r in released if r["marker"]<0]
    checks["negative_drain_phases"]=(bool(draining) and all(r["marker"]<=0 for r in released[released.index(draining[0]):]) and
        all(any(any(t["active"] and t["phase"]==phase for t in r["trails"]) for r in draining) for phase in (1,2)))
    last=released[-1]
    delta=(last["native_timer"]-draining[0]["native_timer"])&0xFFFFFFFF if draining else 0xFFFFFFFF
    checks["finite_retirement"]=(checks["negative_drain_phases"] and 0<delta<=max_drain_ticks and last["marker"]==0 and
                                  all(t["visible"]==t["active"]==0 for t in last["trails"]))
    resource=lambda r:(r["compression"],r["assembly"],r["page"],r["clut"],
        tuple((t["parent"],t["compression"],t["assembly"],t["page"],t["clut"]) for t in r["trails"]))
    checks["native_resources_and_cluts_retained"]=all(resource(r)==resource(before) and all(
        (t["compression"],t["assembly"],t["frame"],t["facing"])==(r["compression"],r["assembly"],r["frame"],r["facing"])
        for t in r["trails"]) for r in rows)
    return checks


def run_native_zero_reference(process,port: int,candidate: Path,original_disc: Path,
                              expected_exe_sha256: str,report: dict,*,
                              allow_private_prerequisite=False,hold_ticks=10,timeout=12) -> dict:
    """One bounded dash-jump on the original renderer; caller stops its Popen.

    Parent launches the fresh muted profile offline and reaches idle P1 first.
    This function creates a fresh evidence folder, retains partial failures,
    and always clears native P1 input. It never launches/stops any process.
    """
    if not 6<=hold_ticks<=30 or not math.isfinite(timeout) or not 0<timeout<=60:
        raise ValueError("Reference needs bounded6..30 native hold ticks and timeout0..60")
    output=preparation.local_output(Path(candidate)/"native-zero-reference")
    output.mkdir()  # Never overwrite a failed attempt.
    report.update(kind="offline_native_zero_p1_original_renderer_reference",status="failed_setup",
        expected_exe_sha256=expected_exe_sha256,source_exe_sha256=content.EXE_SHA256,
        source_archive_sha256=content.BIN_SHA256,original_disc=str(Path(original_disc).resolve()),sources_verified=False,
        source_menu_sha256=MENU_SHA,source_zero_sha256=ZERO_SHA,observations=[],inputs=[],captures=[],
        source_native_renderer_order=[hex(PLAYER),hex(TRAILS+0xC0),hex(TRAILS+0x60),hex(TRAILS)],
        checks={},cleanup_errors=[],artwork_review="pending",ledger_status="unverified",
        prerequisite_bypass=False,ordinary_input_evidence_tainted=False,
        tool_sha256={Path(module.__file__).name:preparation.sha256(Path(module.__file__))
                     for module in (debug,content,preparation,baseline)},
        helper_sha256=preparation.sha256(Path(__file__)),
        limits=["Reference native game packet-renderer path inside the bound recompiled image; not original hardware qualification",
                "Body/pools share oneRPC; separate PLAY, palette and composed-capture RPCs have explicit temporal limits",
                "Private prerequisite, if used, taints campaign/unlock/ordinary-input evidence",
                "No opposite-roster co-op, X/P2 charge, R9, campaign or native-card pass"])
    session=None
    private_cards={}
    try:
        sources=load_sources(original_disc)
        report["sources_verified"]=True
        session=OwnedNativeSession(process,port,candidate,expected_exe_sha256)
        private_cards={p.name:preparation.sha256(p) for p in (Path(candidate)/"saves").glob("*.mcd")}
        report["profile_binding"]=session.profile
        report.update(owned_pid=process.pid,running_image_path=str(session.image_path),running_image_sha256=session.image_sha256)
        report["offline_status"]=session.offline()
        pad=session.request("pad_status")
        if not pad.get("slot0",{}).get("connected"):
            raise debug.DebugError("Reference requires the fresh automated native P1 pad")
        report["selection"]={}
        selected=select_native_zero(session,sources,report["selection"],
            allow_private_prerequisite=allow_private_prerequisite,timeout=min(60,timeout*5))
        report["observations"].append(dict(label="native_zero_idle",row=selected))
        _guard_code(session,sources,"zero",0x801EA000,((0x801EA000,0x801EA020),),report["selection"]["code_guards"])
        report["captures"].append(debug.capture_present(session,output/"zero-native-idle.png",request=session.request))
        before=read_native(session)
        if not native_zero(before) or before["marker"] or any(t["visible"] or t["active"] for t in before["trails"]):
            raise debug.DebugError("Reference dash needs a clear native Zero/P1 marker/pool")
        active,released,capture_window=[],[],[]
        report.update(before=before,active=active,released=released,capture_window=capture_window,status="failed")
        start=before["native_timer"]
        session.offline()
        try:
            session.request("press",port=1,buttons=0xFFFF^(0x20|0x2000|0x4000),frames=0)
            report["inputs"].append(dict(path="offline_native",seat=0,pressed=0x6020,frames=0,before_timer=start,
                                         purpose="original Right+Circle+Cross dash-jump; acceptance requires native marker"))
            deadline=time.monotonic()+timeout
            def capture_control(command,**fields):
                clock=session.read(PLAY+0x90,4)
                delta=(struct.unpack("<I",clock)[0]-start)&0xFFFFFFFF
                if delta>=0x80000000 or delta>hold_ticks+12:
                    raise debug.DebugError("Composed capture exceeded the bounded native held-input window")
                return session.request(command,**fields)
            while time.monotonic()<deadline:
                try:now=read_native(session)
                except debug.UnstableObservation:continue
                active.append(now)
                delta=(now["native_timer"]-start)&0xFFFFFFFF
                if delta>=0x80000000 or delta>hold_ticks+12:
                    raise debug.DebugError("Native reference held-input clock escaped its bound")
                if visible_dash(now) and not capture_window:
                    capture_window.append(now)
                    report["captures"].append(debug.capture_present(session,output/"zero-native-positive-dash.png",
                        timeout=min(timeout,8),request=capture_control))
                    capture_window.append(read_native(session))
                    report["native_trail_palettes"]=read_trail_palettes(session)
                if delta>=hold_ticks and len(capture_window)==2:break
                time.sleep(.005)
            else:raise debug.DebugError("Native Zero original input never completed its bounded accepted dash/capture")
        finally:
            session.request("clear_input",port=1)
        report["inputs"].append(dict(path="offline_native",seat=0,pressed=0,purpose="neutral in finally"))
        release_start=read_native(session)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:now=read_native(session)
            except debug.UnstableObservation:continue
            released.append(now)
            delta=(now["native_timer"]-release_start["native_timer"])&0xFFFFFFFF
            if delta>=0x80000000 or delta>64:
                raise debug.DebugError("Native Zero reference did not retire within64 observed gameplay ticks")
            if now["marker"]==0 and all(t["visible"]==t["active"]==0 for t in now["trails"]):break
            time.sleep(.005)
        else:raise debug.DebugError("Native Zero reference drain/retirement deadline expired")
        report["checks"]=reduce_native_reference(before,active,released,capture_window)
        report["status"]="reference_observations_completed_artwork_pending" if all(report["checks"].values()) else "failed"
    except Exception as error:
        report.update(error=str(error),error_type=type(error).__name__)
    finally:
        if session is not None:
            try:session.request("clear_input",port=1)
            except Exception as error:report["cleanup_errors"].append(str(error))
        if report["cleanup_errors"]:report["status"]="failed"
        report["prerequisite_bypass"]=report.get("selection",{}).get("prerequisite_bypass",False)
        report["ordinary_input_evidence_tainted"]=report.get("selection",{}).get("ordinary_input_evidence_tainted",False)
        report["existing_private_cards_unchanged"]=all((Path(candidate)/"saves"/name).is_file() and
            preparation.sha256(Path(candidate)/"saves"/name)==digest for name,digest in private_cards.items())
        if not report["existing_private_cards_unchanged"]:report["status"]="failed"
        (output/"reference.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report
