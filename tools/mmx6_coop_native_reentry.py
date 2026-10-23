"""Source-bound P1 final Quit/current-data or new-game reentry; no launcher.

The adapter owns persistent original input, process/listener/image checks,
private cards and cleanup. Online input must be the published host sampler.
This helper never writes game memory, loads a card or sets a success flag.
"""
from __future__ import annotations

import hashlib
import math
import ntpath
from pathlib import Path
import re
import struct
import time

import coop_debug as debug
import inventory_mmx6_coop_content as content
import mmx6_coop_native_quit as quit_ui
import mmx6_coop_personal_menu as menu
import mmx6_native_zero_reference as native

CURRENT, CURRENT_BYTES = 0x80070CC4, 0x3B7
PLAYER, GLOBALS, DECODE, PLAY, FRONT, MENU = 0x800970A0, 0x80097420, 0x800C456C, 0x800CCED0, 0x800CD3F8, 0x800CF810
READ_BASE, READ_END = CURRENT, MENU+0x3C
READ_BYTES = READ_END-READ_BASE  # 0x5EB88; 775952 hex chars fit the existing 1MiB reply cap.
TITLE_BASE, TITLE_MEMBER = 0x800E9860, 18
TITLE_SHA = "3ae703ad03b2bbc4b71fc09e5f418e1e87ffd49a4a6a4240e69172fb87036166"
SUCCESS = "automated_native_reentry_checks_passed_artwork_pending"
EXE_WINDOWS = ((0x8001CF78,0x8001D2A0),(0x8001D930,0x8001DBAC),
    (0x8001DE10,0x8001E1BC),(0x8001E6E4,0x8001E730),(0x8001E880,0x8001E914),
    (0x8001FD10,0x8001FE74),(0x8001BA1C,0x8001BD40),
    (0x80012A34,0x80012B44),(0x80021FC4,0x80022838))
TITLE_WINDOWS = ((0x800EA62C,0x800EA9D0),(0x800ED760,0x800ED87C),(0x800F08FC,0x800F0928))
# Source 8001BA1C..8001BD40. Volatile script/input fields are recorded, not
# treated as campaign inventory. No campaign character/armor is imported here.
PERSISTENT_IMPORTS = ((0x04,0x70,4),(0x08,0x74,8),(0x10,0x6C,4),(0x14,0x6A,2),
    (0x36,0x5B,2),(0x38,0x61,2),(0x3A,0x60,1),(0x3B,0x5F,1),(0x3C,0x69,1),
    (0x3D,0x8D,2),(0x40,0xCC,4),(0x44,0xD8,0x40),(0x84,0x9E,0x2A),
    (0xB8,0xD2,4),(0xBC,0x168,0x10),(0xCC,0xC9,1),(0xCD,0x438,1),
    (0xCE,0x178,0x2C0),(0x390,0x43C,0x24),(0x3B4,0x465,3))


class ReentryError(RuntimeError):
    pass


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def load_sources(original_disc):
    """Pinned original EXE/archive plus source-inventoried menu16/title18."""
    disc=content.RawDisc(Path(original_disc))
    try:files=disc.inventory_files()
    finally:disc.stream.close()
    if sha(files["SLUS_013.95"])!=content.EXE_SHA256 or sha(files["ROCK_X6.BIN"])!=content.BIN_SHA256:
        raise ValueError("Native reentry needs the exact original USA1.1 EXE/archive")
    exe=content.Executable(files["SLUS_013.95"]);archive=files["ROCK_X6.BIN"]
    members=content.archive_members(archive)
    result=dict(exe=exe.data[2048:2048+exe.size],exe_base=exe.base,
        original=dict(raw_disc=str(Path(original_disc).resolve()),exe_sha256=content.EXE_SHA256,
                      archive_sha256=content.BIN_SHA256,members=[]))
    for name,index,expected in (("menu",16,native.MENU_SHA),("title",18,TITLE_SHA)):
        member=members[index];start=member["sector"]*2048;payload=archive[start:start+member["size"]]
        if sha(payload)!=expected:raise ValueError("Native reentry source member identity changed")
        result[name]=payload;result["original"]["members"].append(dict(member,role=name))
    for stage,index in ((13,16),(14,18)):
        if struct.unpack_from("<H",exe.data,exe.offset(content.OVERLAY_SELECTOR+stage*4,2))[0]!=index:
            raise ValueError("Original native title/map overlay selector changed")
    return result


def read_native(client, *, evidence=None, label="native reentry"):
    """One exact ordinary-RAM RPC, including all UI/input/current-data slices.

    The SDK services read_ram at its emulation-thread poll; this fixed large
    mapping uses its existing heap reply. Generic DebugClient.read stays64KiB.
    Diagnostic publication and composed presentation are separate observations.
    """
    receipt=dict(label=label,status="requested",address=hex(READ_BASE),bytes=READ_BYTES,
                 end_exclusive=hex(READ_END))
    if evidence is not None:evidence.append(receipt)
    try:
        response=client.request("read_ram",addr=hex(READ_BASE),len=READ_BYTES)
        encoded=response.get("hex");address=response.get("addr")
        receipt.update(response_address=address,response_bytes=response.get("len"),
                       response_hex_chars=len(encoded) if isinstance(encoded,str) else None)
        if (not isinstance(address,str) or not re.fullmatch(r"0x[0-9a-fA-F]{8}",address) or int(address,16)!=READ_BASE or
                type(response.get("len")) is not int or response["len"]!=READ_BYTES or
                not isinstance(encoded,str) or len(encoded)!=READ_BYTES*2):
            raise debug.DebugError("Native reentry reply escaped the exact fixed RAM mapping")
        try:raw=bytes.fromhex(encoded)
        except ValueError as error:raise debug.DebugError("Native reentry reply contains invalid hex") from error
        if len(raw)!=READ_BYTES:raise debug.DebugError("Native reentry decoded payload length changed")
        def part(address,size):return raw[address-READ_BASE:address-READ_BASE+size]
        play=part(PLAY,0x468);front=part(FRONT,0x18);globals_=part(GLOBALS,8);pad=part(DECODE,6)
        current=part(CURRENT,CURRENT_BYTES);body=part(PLAYER,0x158);ui=part(MENU,0x3C)
        record=dict(mode=list(play[:3]),native_timer=struct.unpack_from("<I",play,0x90)[0],
            stage=play[0xC],section=play[0xD],campaign_character=play[0x38],armor=play[0x5E],
            unlocks=play[0x5F],frontend=list(front[:4]),frontend_blocked=front[0xD],
            fade=globals_[4],choice=globals_[7],decoded=list(struct.unpack("<3H",pad)),
            menu=list(ui[4:8]),quit_page=struct.unpack_from("<I",ui,0x34)[0],
            current_header=current[0],current_data_hex=current.hex(),current_data_sha256=sha(current),
            play_hex=play.hex(),frontend_hex=front.hex(),native_player=debug.Player.parse(body).__dict__,
            native_body_hex=body.hex(),globals_hex=globals_.hex(),decoded_hex=pad.hex(),menu_hex=ui.hex(),
            dialogue_hex=part(native.DIALOGUE,0x10).hex(),
            snapshot_sha256=sha(raw),limit="Atomic ordinary RAM; diagnostic and composed capture are separate RPCs")
        receipt.update(status="accepted",snapshot_sha256=record["snapshot_sha256"])
        return record
    except Exception as error:
        receipt.update(status="rejected",error=str(error),error_type=type(error).__name__)
        raise


def neutral(row):return all(r["decoded"]==[0,0,0] for r in row.get("peers",[row]))
def title_ready(row):
    return row["frontend"][:2]==[1,3] and row["frontend_blocked"]==row["fade"]==0 and (row["stage"],row["section"])==(14,0)
def title_choices(row):return row["frontend"][:2]==[6,1] and row["fade"]==0
def current_prompt(row):return row["frontend"][:2]==[7,1] and row["fade"]==0 and row["current_header"]!=0xFF
def map_ready(row):return row["mode"]==[4,4,0] and row["fade"]==0
def selector_ready(row):return row["mode"]==[4,4,5] and row["fade"]==0
def quit_page(row,page,choice):
    return row["mode"][:2]==[10,2] and row["menu"]==[1,6,2,1] and row["quit_page"]==page and row["choice"]==choice and not row["fade"]


def reduce_current_data(before,restored):
    """At the native map, before selector/mission inputs; no body refill claim."""
    saved=bytes.fromhex(before["current_data_hex"]);play=bytes.fromhex(restored["play_hex"])
    differences=[dict(saved_offset=hex(s),play_offset=hex(p),bytes=n,expected=saved[s:s+n].hex(),actual=play[p:p+n].hex())
                 for s,p,n in PERSISTENT_IMPORTS if saved[s:s+n]!=play[p:p+n]]
    return dict(checks=dict(current_data_eligible=before["current_header"]!=0xFF,
        original_current_buffer_retained=before["current_data_sha256"]==restored["current_data_sha256"],
        source_imported_campaign_fields_match=not differences,
        primary_campaign_is_x_at_native_map=map_ready(restored) and restored["campaign_character"]==0),
        differences=differences,limits=["Current buffer eligibility is not earned-progress or native-card coverage",
        "Native import does not restore PLAY+38 character or PLAY+5E armor; the real unit selector is checked separately",
        "HP/ammo spent in the abandoned world may be refilled by original native import/initialization"])


def fresh_reentry(anchor,diagnostics):
    """A second publication AFTER the first observed native arrival, not old
    publication progress between preflight and the final-Quit button."""
    return bool(anchor) and len(anchor)==len(diagnostics) and all(menu._forward(old["tick"],r["tick"]) and
        r["native_mode"]==10 and r["native_phase"]==0 and r["ready"]==r["enrolled"]==1 and
        not r["failed"] and not r["mailbox"] and not r["pause_owner"] and not r["scene_owner"] and
        tuple(r["lifecycle"])==(0,0) and [p["character"] for p in r["players"]]==[0,1] and
        all(p["active"] and p["state"]==1 and p["action"]==2 and 0<p["hp"]<128 for p in r["players"])
        for old,r in zip(anchor,diagnostics))


def new_game_defaults(row):
    return dict(campaign_character=row["campaign_character"],armor=row["armor"],unlocks=row["unlocks"],
                max_hp=list(bytes.fromhex(row["play_hex"])[0x5B:0x5D]),
                native_body_form=bytes.fromhex(row["native_body_hex"])[0xE7])


def primary_scope(row):
    return row["mode"][:2]==[10,0] and row["campaign_character"]==row["native_player"]["character"]==0


def dialogue_state(row):
    data=bytes.fromhex(row["dialogue_hex"])
    if len(data)!=16:raise ValueError("Native dialogue observation must contain exactly16 bytes")
    return dict(stage=row["stage"],section=row["section"],mode=list(row["mode"]),
        cursor=hex(struct.unpack_from("<I",data)[0]),control=struct.unpack_from("<H",data,4)[0],
        timer=struct.unpack_from("<H",data,10)[0],active=data[12],phase=data[13],page=data[14])


def scripted_dialogue_ready(row):
    # Parser800227F8..22804 publishes FF/3. Phase2 is automatic typing;
    # queued/closing80 is not a second input opportunity.
    source_mode=(row["stage"]==13 and row["mode"]==[4,11,1]) or (
        row["stage"]==11 and row["mode"][0] in (0x13,0x14))
    state=dialogue_state(row)
    return source_mode and (state["active"],state["phase"])==(0xFF,3)


def dialogue_response(before,after):
    """Native progress after one consumed Cross, not just phase!=3.

    Closing control8000 sets80/4 then retires through5 to inactive at
    800220F0..2231C. Otherwise2211C..22170 resumes the parser, increments
    page, and225E4..225F8 advances its text cursor. Polls may miss states.
    """
    if after["cursor"]!=before["cursor"]:return "native_text_cursor_advanced"
    if after["active"]==0:return "native_dialogue_retired"
    if before["control"]&0x8000:
        if after["active"]==0x80 and after["phase"] in (4,5):return "native_box_closing"
    elif after["page"]!=before["page"]:
        return "native_page_advanced"
    return None


def wait_scripted(ctx,inputs,receipts,predicate,observe,*,label,seconds,timeout=12,guard_map=lambda:None):
    """Bound by the route deadline, never an invented count of story boxes.

    Each accepted input still needs its original ready decoder, actual held
    Cross, native dialogue progress on every peer, and consumed neutral.
    observe retains the full ordinary-RAM rows in the owning case.
    """
    if (not math.isfinite(seconds) or not 0<seconds<=240 or
            not math.isfinite(timeout) or not 0<timeout<=60):raise ValueError("Invalid native scripted deadline")
    started=time.monotonic();deadline=started+seconds;guarded=False
    receipt=dict(label=label,status="waiting",deadline_seconds=seconds,inputs=[],
        limit="Native readiness deadline; no assumed dialogue page count")
    receipts.append(receipt)
    try:
        while time.monotonic()<deadline:
            rows=observe(label)
            if not rows:raise ReentryError(label+": native observation omitted every owned peer")
            if all(predicate(r) for r in rows):
                receipt["status"]="native_destination_observed";return rows
            if rows and all(scripted_dialogue_ready(r) for r in rows):
                if all(r["stage"]==13 for r in rows) and not guarded:guard_map();guarded=True
                offered=[];accepted=[]
                def ready(item):
                    if len(item["peers"])!=len(rows) or not all(scripted_dialogue_ready(r) for r in item["peers"]):return False
                    offered[:]=[dialogue_state(r) for r in item["peers"]]
                    return True
                def response(item):
                    after=[dialogue_state(r) for r in item["peers"]]
                    if len(after)!=len(offered):return False
                    reasons=[dialogue_response(old,new) for old,new in zip(offered,after)]
                    if not all(reasons):return False
                    accepted[:]=[dict(before=old,after=new,response=reason) for old,new,reason in zip(offered,after,reasons)]
                    return True
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                item=dict(input_index=len(inputs),status="pending");receipt["inputs"].append(item)
                try:
                    pulse(ctx,inputs,0x4000,response,lambda text:dict(peers=observe(text)),
                        label="Original phase3 scripted dialogue Cross",ready=ready,timeout=min(timeout,remaining/3))
                    item.update(status="native_response_and_neutral_observed",peers=accepted)
                except Exception as error:
                    item.update(status="failed",offered=offered,error=str(error));raise
            time.sleep(.015)
        raise ReentryError(label+": native scripted readiness timed out")
    except Exception as error:
        receipt.update(status="failed",error=str(error),error_type=type(error).__name__);raise
    finally:receipt["elapsed_seconds"]=time.monotonic()-started


def pulse(ctx,record,bits,predicate,observe,*,label,timeout=12,ready=lambda row:True):
    """P1 persistent sampler, witnessed native response and consumed neutral.

    No plugin-publication clock is used after teardown. The adapter's
    set_input(0,mask) must check ownership and use NativePad offline or the
    published host sampler online. Native decoder masks swap pad bytes.
    """
    if (type(bits) is not int or not 0<bits<=0xFFFF or not math.isfinite(timeout) or not 0<timeout<=60 or
            not callable(ctx.get("set_input")) or ctx.get("input_path") not in ("offline_native","published_host")):
        raise ValueError("Native reentry pulse requires bounded persistent original input")
    attempt=dict(label=label,seat=0,pressed=bits,path=ctx["input_path"],bypasses=[],status="failed",samples=[],
                 pressed_observed=False,edge_observed=False,transition_observed=False,neutral_consumed=False)
    record.append(attempt);failure=None
    def wait(stage,test):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            row=observe(label+" "+stage);attempt["samples"].append(dict(stage=stage,row=row))
            if test(row):return row
            time.sleep(.015)
        raise ReentryError(label+": native "+stage+" timed out")
    try:
        wait("neutral before",lambda row:neutral(row) and ready(row))
        ctx["set_input"](0,bits)
        native_bits=((bits&255)<<8)|(bits>>8)
        def response(row):
            rows=row.get("peers",[row])
            attempt["pressed_observed"]|=all((r["decoded"][0]&native_bits)==native_bits for r in rows)
            attempt["edge_observed"]|=all((r["decoded"][2]&native_bits)==native_bits for r in rows)
            return attempt["pressed_observed"] and predicate(row)
        result=wait("response",response);attempt["transition_observed"]=True
        return result
    except Exception as error:
        failure=error;attempt.update(error=str(error),error_type=type(error).__name__);raise
    finally:
        try:
            ctx["set_input"](0,0)
            wait("neutral after",neutral);attempt["neutral_consumed"]=True
            if failure is None:attempt["status"]="native_response_and_neutral_observed"
        except Exception as error:
            attempt["release_error"]=str(error)
            if failure is None:raise


def native_reentry_smoke(ctx, *, original_disc, expected_exe_sha256, route="current_data", timeout=12, reentry_timeout=180):
    """Separate owned run: primary final Quit, real frontend, reentry/menu.

    Same personal-menu context plus set_input(seat,pressed_bits), exact image
    binding, same_machine=True online and mandatory resolved matched callback.
    No adapter or process lifecycle is implemented here.
    """
    if route not in ("current_data","new_game") or ctx.get("mode") not in ("local","netplay"):
        raise ValueError("Expected an explicit source-backed current_data or new_game route")
    if any(key not in ctx for key in ("debug","report","output")) or any(not callable(ctx.get(key))
            for key in ("hold","native_advance","transport_window")) or any(not callable(getattr(ctx.get("debug"),key,None))
            for key in ("observe","capture_present")):
        raise ValueError("Reentry also needs the existing owned personal-menu observation/input context")
    online=ctx["mode"]=="netplay"
    if (not isinstance(expected_exe_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",expected_exe_sha256) or ctx.get("candidate_exe_sha256")!=expected_exe_sha256 or
            ctx.get("input_path")!=("published_host" if online else "offline_native") or len(ctx.get("clients",[]))!=(2 if online else 1) or
            not callable(ctx.get("set_input")) or not callable(ctx.get("both"))):
        raise ValueError("Reentry requires exact image and owned persistent original input")
    if online and (ctx.get("same_machine") is not True or not callable(ctx.get("network")) or not callable(ctx.get("matched"))):
        raise ValueError("Paired reentry requires same-machine ownership, actual transport and resolved CRC")
    if not all(math.isfinite(t) for t in (timeout,reentry_timeout)) or not 0<timeout<=60 or not timeout<=reentry_timeout<=240:
        raise ValueError("Reentry deadlines exceed bounded limits")
    sources=load_sources(original_disc)
    output=Path(ctx["output"]).resolve()/f"native-final-quit-{route.replace('_','-')}"
    if ntpath.splitdrive(str(output))[0].lower()=="c:" or output.exists():raise ValueError("Reentry needs fresh evidence off C:")
    output.mkdir()
    case=dict(kind="native_primary_final_quit_reentry",route=route,status="failed_setup",original=sources["original"],
        candidate_exe_sha256=expected_exe_sha256,candidate_binding=ctx.get("candidate_binding"),mode=ctx["mode"],
        input_path=ctx["input_path"],helper_sha256=sha(Path(__file__).read_bytes()),observations=[],reads=[],inputs=[],
        dependency_sha256={Path(m.__file__).name:sha(Path(m.__file__).read_bytes()) for m in (debug,content,quit_ui,menu,native)},
        diagnostic_observations=[],scripted_waits=[],code_guards=[],captures=[],checks={},artwork_review="pending",ledger_status="unverified",limits=[
            "No native-card load/save or acquired-progress preservation is implied by an empty private profile",
            "New Game defaults are distinct from current-data preservation",
            "Ordinary RAM is atomic only within each fixed read; diagnostics/captures and peers are separate",
            "No opposite roster, all campaign routes, death/Continue or final release qualification"])
    ctx["report"].setdefault("native_reentry",[]).append(case)
    def require(ok,message):
        if not ok:raise ReentryError(message)
    def observe(label):
        rows=ctx["both"](lambda peer:read_native(ctx["clients"][peer],evidence=case["reads"],label=f"{label} peer{peer}"))
        require(len(rows)==len(ctx["clients"]),"Reentry lost an owned peer")
        case["observations"].append(dict(label=label,peers=rows))
        if online:case["observations"][-1]["network"]=ctx["network"]()
        return rows
    def single(label):
        rows=observe(label)
        # Response/neutral predicates must hold on both peers before release.
        return dict(peers=rows)
    def canonical_read(label):
        rows=ctx["both"](lambda peer:ctx["debug"].observe(ctx["clients"][peer]).json())
        require(len(rows)==len(ctx["clients"]),"Canonical reentry observation omitted an owned peer")
        case["diagnostic_observations"].append(dict(label=label,peers=rows))
        return rows
    def pressed(bits,predicate,label,ready=lambda row:True):
        # pulse consumes one JSON row; retain both peer snapshots in its row.
        return pulse(ctx,case["inputs"],bits,lambda item:all(predicate(r) for r in item["peers"]),single,
            label=label,timeout=timeout,ready=lambda item:all(ready(r) for r in item["peers"]))
    def wait(predicate,label,seconds=timeout):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            rows=observe(label)
            if all(predicate(r) for r in rows):return rows
            time.sleep(.015)
        raise ReentryError(label+": native readiness timed out")
    def guard(name,windows):
        base=sources["exe_base"] if name=="exe" else TITLE_BASE
        for first,end in windows:
            expected=sources[name][first-base:end-base]
            require(len(expected)==end-first,"Original source window escaped its member")
            for peer,client in enumerate(ctx["clients"]):
                actual=client.read(first,end-first)
                case["code_guards"].append(dict(peer=peer,member=name,address=hex(first),bytes=end-first,
                    expected_sha256=sha(expected),actual_sha256=sha(actual)))
                require(actual==expected,"Loaded native reentry code differs from original source")
    def capture(label):
        case["captures"].extend(ctx["both"](lambda peer:dict(peer=peer,label=label,
            **ctx["debug"].capture_present(ctx["clients"][peer],output/f"peer-{peer}-{label}.png"))))
    def scripted(predicate,label,seconds):
        return wait_scripted(ctx,case["inputs"],case["scripted_waits"],predicate,observe,label=label,
            seconds=seconds,timeout=timeout,guard_map=lambda:guard("menu",native.MENU_GUARDS))
    try:
        initial=observe("Healthy original-input reentry preflight");case["before"]=initial
        canonical=canonical_read("Canonical pre-Quit preflight");case["before_diagnostic"]=canonical
        require(all(r["mode"][:2]==[10,0] for r in initial) and all(r["ready"]==r["enrolled"]==1 and not r["failed"] and
            not r["mailbox"] and not r["pause_owner"] and not r["scene_owner"] and tuple(r["lifecycle"])==(0,0) and
            [p["character"] for p in r["players"]]==[0,1] and all(p["active"] and p["state"]==1 and p["action"]==2 and p["hp"]>0 for p in r["players"])
            for r in canonical),"Final Quit requires settled living original X/P1 and Zero/P2")
        if route=="current_data":
            require(all(r["current_header"]!=0xFF for r in initial),"Current-data header is empty; refused before any Quit input")
            require(len({r["current_data_sha256"] for r in initial})==1,"Peers disagree on eligible native current data")
        guard("exe",EXE_WINDOWS)
        pressed(8,lambda r:r["mode"][:2]==[10,2] and r["menu"][0]==1,"P1 original Start opens native pause")
        case["status"]="failed_behavior"
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            owned=canonical_read("Canonical P1-owned native pause readiness")
            if all(r["native_mode"]==10 and r["native_phase"]==2 and r["pause_owner"]==1 and
                r["ready"]==r["enrolled"]==1 and not r["failed"] and not r["mailbox"] for r in owned):break
            time.sleep(.015)
        else:raise ReentryError("Original Start did not establish actual P1-owned native pause")
        case["primary_pause_diagnostic"]=owned
        pressed(1,lambda r:quit_page(r,0,0),"P1 Select opens native first Quit page")
        capture("native-first-quit-page")
        pressed(0x40,lambda r:quit_page(r,0,1),"Primary Down selects first-page Quit")
        pressed(0x4000,lambda r:quit_page(r,1,1),"Primary Cross enters second confirmation page")
        capture("native-second-quit-page")
        pressed(0x10,lambda r:quit_page(r,1,0),"Primary Up selects actual final Quit")
        pressed(0x4000,title_ready,"Primary Cross executes original final Quit",ready=lambda r:quit_page(r,1,0))
        guard("title",TITLE_WINDOWS)
        title=wait(title_ready,"Original title ready after final Quit");case["title"]=title
        require(all(r["campaign_character"]==0 for r in title),"Guest character escaped into native primary campaign at title")
        capture("native-title-after-final-quit")
        pressed(8,lambda r:title_choices(r) and r["frontend"][2]==0,"Original title Start opens native choices",ready=title_ready)
        if route=="current_data":
            pressed(0x40,lambda r:title_choices(r) and r["frontend"][2]==1,"Original Down selects native Load route")
            pressed(0x4000,current_prompt,"Original Cross opens eligible current-data prompt")
            prompt=wait(current_prompt,"Native current-data prompt ready");case["current_prompt"]=prompt
            require(all(r["choice"]==0 and r["current_data_sha256"]==old["current_data_sha256"] for old,r in zip(initial,prompt)),
                    "Native current-data prompt did not retain primary current buffer/choice0")
            pressed(0x4000,lambda r:r["frontend"][:2]!=[7,1],"Original Cross imports native current data",ready=current_prompt)
            # No card-choice input is ever sent; headerFF never reaches here.
            mapped=scripted(map_ready,"Original current-data stage map readiness",reentry_timeout);case["native_map"]=mapped
            guard("menu",native.MENU_GUARDS)
            case["current_data_reductions"]=[reduce_current_data(old,row) for old,row in zip(initial,mapped)]
            require(all(all(item["checks"].values()) for item in case["current_data_reductions"]),"Original current-data campaign import/ownership mismatch")
            pressed(0x4000,selector_ready,"Original Cross opens native unit selector",ready=map_ready)
            for peer,client in enumerate(ctx["clients"]):
                choices=client.read(native.MENU_TABLE,6);count=client.read(native.MENU_COUNT,1)[0]
                case.setdefault("unit_lists",[]).append(dict(peer=peer,count=count,choices=list(choices[:count])))
                expected=[u for u,mask in ((0,0),(1,1),(2,2),(3,4),(4,8)) if not mask or mapped[peer]["unlocks"]&mask]
                require(len(choices)==6 and 1<=count<=6 and list(choices[:count])==expected,
                        "Co-op native unit list differs from original unlocked X forms with primary Zero excluded")
            # Source BIN16 input800EB080: Left/Right return to phase5 after
            # native phase6 animation. Bound the native cursor, never assign it.
            for _ in range(6):
                cursor=wait(selector_ready,"Native selector input phase5")
                cursor_values=[bytes.fromhex(r["play_hex"])[0x30] for r in cursor]
                require(len(set(cursor_values))==1,"Peers disagree on actual native unit cursor")
                if cursor_values[0]==0:break
                old_cursor=cursor_values[0]
                pressed(0x80,lambda r:bytes.fromhex(r["play_hex"])[0x30]!=old_cursor,
                        "Native Left selects previous unit",ready=selector_ready)
            else:raise ReentryError("Native unit cursor did not reach original X")
            pressed(0x4000,lambda r:r["mode"]!=[4,4,5],"Original Cross confirms X/P1",ready=selector_ready)
        else:
            pressed(0x4000,lambda r:not title_choices(r),"Original Cross starts native New Game",ready=title_choices)
            case["character_selection"]="Not visited: native New Game initializes its default X/Falcon campaign"
        # Let original scripted arrival progress. A dialogue Cross is allowed
        # only at the original phase3 input decoder, not a guessed screen.
        anchor=None;returned=None
        def arrived(row):return row["mode"][:2]==[10,0]
        deadline=time.monotonic()+reentry_timeout
        while time.monotonic()<deadline:
            rows=scripted(arrived,"Original native reentry/arrival",max(.001,deadline-time.monotonic()))
            if all(arrived(r) for r in rows):
                diagnostics=canonical_read("Canonical native arrival after ordinary-RAM gameplay")
                if anchor is None:
                    anchor=diagnostics;case["arrival_diagnostic_anchor"]=anchor
                elif fresh_reentry(anchor,diagnostics):
                    returned=diagnostics;case["reentered_native"]=rows;break
            time.sleep(.015)
        require(returned is not None,"Native arrival never produced a fresh settled co-op publication")
        case["reentered_diagnostic"]=returned
        if route=="new_game":
            # A raw GAMEPLAY read may land inside a legitimate P2 projection.
            # Retain it, then wait for an observed native primary scope; never
            # reinterpret Zero5 as the primary's default armor or normalize it.
            primary=wait(primary_scope,"Observed native primary context for New Game defaults")
            case["new_game_primary_scope"]=primary
            case["new_game_defaults"]=[new_game_defaults(r) for r in primary]
            require(all(r==dict(campaign_character=0,armor=1,unlocks=1,max_hp=[32,32],native_body_form=1) for r in case["new_game_defaults"]),
                    "Native New Game defaults do not match original initializer")
        capture("native-reentered-gameplay")
        menu_ctx=dict(ctx,output=output)
        hp=tuple(p["hp"] for p in returned[0]["players"])
        require(all(tuple(p["hp"] for p in row["players"])==hp for row in returned),"Peers disagree on reentered personal HP")
        guest=menu.personal_menu_smoke(menu_ctx,owner=1,expected_hp=hp,cursor_buttons=(0x40,0x10),timeout=timeout)
        case["guest_menu"]=guest
        require(bool(guest["checks"]) and all(guest["checks"].values()),"Actual guest-owned native menu/control did not recover after final Quit")
        if online:ctx["matched"]("Native final Quit "+route+" reentry and guest menu core/mod comparison")
        case["checks"].update(actual_primary_final_quit_and_title=True,source_bound_native_frontend_route=True,
            fresh_native_x_zero_reentry=True,guest_owned_menu_resources_and_controls_restored=True)
        if online:case["checks"]["resolved_core_mod_crc_completed"]=True
        case["status"]=SUCCESS
        return case
    except Exception as error:
        case.update(error=str(error),error_type=type(error).__name__);raise
