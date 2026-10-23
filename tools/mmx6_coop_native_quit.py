"""Native X6 Quit pages/cancel and guest authority probes using owned input.

No process lifecycle, debug quit, guest writes, source cards or ledger updates.
Full Quit/current-data reentry is deliberately outside this bounded module.
"""
from __future__ import annotations

import hashlib
import math
import ntpath
from pathlib import Path
import re
import struct
import time

import mmx6_coop_personal_menu as menu

ORIGINAL_SHA256 = "dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046"
MENU_BASE, PLAY, UI_GLOBAL = 0x800CF810, 0x800CCED0, 0x80097420
SELECT, START, UP, DOWN, CROSS = 1, 8, 0x10, 0x40, 0x4000
SUCCESS = "automated_native_quit_bounded_checks_passed_artwork_pending"
SOURCE_REGIONS = (
    (0x800348B0,0xEC,"543e10d9173c3ec75572ed5ae1a0e4ebea260df49ce1691c51af041e6a500728"),
    (0x80034B70,0xEC,"67e5b261733da1dfd5f3c3d699e48cf3cc7f561d14f78de7478a41669124cf54"),
    (0x8001FD10,0x164,"61d1a95c84ac1e20b87557a7ebc922487293485c7fe2e3bde54713dab41dfa97"),
    (0x8001FFC0,0x4C,"ba2dbd646de6fc434640f0309f397fec6db98d3de631b472e9335b78e2594b20"),
)


class NativeQuitError(RuntimeError):
    pass


def verify_original(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size != 522240:
        raise ValueError("Native Quit requires the exact original SLUS_013.95 executable")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError("Native Quit original EXE identity mismatch")
    regions = []
    for address,size,expected in SOURCE_REGIONS:
        offset = address-0x80010000+2048
        actual = hashlib.sha256(raw[offset:offset+size]).hexdigest()
        if expected and actual != expected:
            raise ValueError("Native Quit source span does not match the pinned original")
        regions.append(dict(address=hex(address),bytes=size,sha256=actual))
    return dict(path=str(path),sha256=digest,bytes=len(raw),regions=regions)


def observe_native_quit(client, debug):
    """Canonical actor publication plus explicitly separate native UI reads.

    PLAY+38 may be temporarily projected during a P2-owned callback. Retain it
    for diagnosis, never treat one raw character byte as campaign promotion.
    """
    observed = debug.observe(client).json()
    raw = client.read(MENU_BASE,0x3C)
    globals_ = client.read(UI_GLOBAL,8)
    play = client.read(PLAY,0x6C)
    if len(raw)!=0x3C or len(globals_)!=8 or len(play)!=0x6C:
        raise NativeQuitError("Truncated native Quit menu/global/campaign observation")
    return dict(observation=observed, menu=list(raw[4:6]), cursor=raw[0x14],
        menu_phase=raw[6], quit_phase=raw[7], quit_page=struct.unpack_from("<I",raw,0x34)[0],
        previous_input_substate=struct.unpack_from("<I",raw,0x30)[0], choice=globals_[7],
        fade=globals_[4], native_menu_hex=raw.hex(), native_ui_globals_hex=globals_.hex(),
        native_play_mode=play[0], native_play_phase=play[1],
        projected_campaign_character=play[0x38], shared_stage_clear_byte=play[0x60],
        shared_tank_flags=struct.unpack_from("<H",play,0x6A)[0])


def owned_ready(row, owner, *, page=None, choice=None):
    base = row["observation"]
    eligible = (base["ready"] == base["enrolled"] == 1 and not base["failed"] and not base["mailbox"] and
        not base["scene_owner"] and base["native_mode"] == 10 and base["native_phase"] == 2 and
        base["pause_owner"] == owner+1 and tuple(base["lifecycle"]) == (0,0) and
        [p["character"] for p in base["players"]] == [0,1] and all(
            p["active"] and p["state"] == 1 and 0<p["hp"]<128 for p in base["players"]) and
        row["native_play_mode"] == 10 and row["native_play_phase"] == 2 and row["fade"] == 0 and row["menu"][0] == 1)
    if page is None:
        return eligible and row["menu"][1] in (0,1,2,8)
    return (eligible and row["menu"][1] == 6 and row["menu_phase"] == 2 and row["quit_phase"] == 1 and
            row["quit_page"] == page and row["choice"] in (0,1) and (choice is None or row["choice"] == choice))


def reduce_quit_window(samples, *, owner, page, choice, reference, networked=False, minimum_progress=6):
    """A UI-ready state and continuing observations, not a hidden-sprite claim."""
    checks = menu.reduce_frozen_window(samples,owner,reference_timers=[
        row["observation"]["native_timer"] for row in reference["peers"]],
        expected_cursors=[row["cursor"] for row in reference["peers"]],
        networked=networked,minimum_progress=minimum_progress)
    checks.update(exact_native_quit_page_ready=False, personal_resources_and_roster_retained=False,
                  observed_shared_progress_retained=False, distinct_ordered_publications=False)
    if len(samples)<3 or any(len(sample.get("peers",[]))!=len(reference.get("peers",[])) for sample in samples):
        return checks
    peers = [row for sample in samples for row in sample["peers"]]
    checks["exact_native_quit_page_ready"] = all(owned_ready(row,owner,page=page,choice=choice) for row in peers)
    checks["personal_resources_and_roster_retained"] = all(menu.resources_preserved(reference["peers"],sample["peers"])
        and all([p["character"] for p in row["observation"]["players"]]==[0,1] for row in sample["peers"]) for sample in samples)
    checks["observed_shared_progress_retained"] = all(
        row["shared_stage_clear_byte"] == reference["peers"][peer]["shared_stage_clear_byte"] and
        row["shared_tank_flags"] == reference["peers"][peer]["shared_tank_flags"]
        for sample in samples for peer,row in enumerate(sample["peers"]))
    checks["distinct_ordered_publications"] = all(
        all(menu._forward(a["peers"][peer]["observation"]["tick"],b["peers"][peer]["observation"]["tick"])
            for a,b in zip(samples,samples[1:])) for peer in range(len(reference["peers"])))
    return checks


def native_quit_smoke(ctx, *, original_exe, expected_exe_sha256, scenario="p1_pages_cancel", timeout=12, window_frames=12):
    """Use the personal-menu accepted-input ctx; root owns all launches.

    New ctx keys: candidate_exe_sha256, and same_machine=True online. Netplay
    also needs matched(label) for actual resolved core/mod comparisons. The
    runner must establish loopback ownership/two matching builds before entry.
    scenario='guest_authority' never confirms an unexpectedly admitted guest
    Quit page. scenario='p1_pages_cancel' exercises both P1 pages and cancels.
    """
    required = ("mode","input_path","clients","both","debug","report","output","hold",
                "native_advance","transport_window","candidate_exe_sha256")
    if any(key not in ctx for key in required):
        raise ValueError("Incomplete native Quit accepted-input context")
    if (not isinstance(expected_exe_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",expected_exe_sha256) or
            ctx["candidate_exe_sha256"] != expected_exe_sha256):
        raise ValueError("Native Quit requires the adapter's exact candidate image binding")
    if scenario not in ("guest_authority","p1_pages_cancel") or ctx["mode"] not in ("local","netplay"):
        raise ValueError("Expected an explicit bounded guest-authority or P1-page/cancel case")
    online = ctx["mode"] == "netplay"
    if ctx["input_path"] != ("published_host" if online else "offline_native") or len(ctx["clients"]) != (2 if online else 1):
        raise ValueError("Native Quit requires owned original offline input or two published-host peers")
    if online and (ctx.get("same_machine") is not True or any(not callable(ctx.get(key)) for key in ("network","matched"))):
        raise ValueError("Two-peer Quit qualification requires same-machine ownership, transport and resolved CRC callbacks")
    if any(not callable(ctx[key]) for key in ("both","hold","native_advance","transport_window")) or any(
            not callable(getattr(ctx["debug"],key,None)) for key in ("observe","capture_present")):
        raise ValueError("Expected callable owned controls, native observation and completed capture")
    if not math.isfinite(timeout) or not 0<timeout<=60 or not 6<=window_frames<=120:
        raise ValueError("Native Quit observation windows exceed bounded limits")
    source = verify_original(original_exe)
    output = Path(ctx["output"]).resolve()/scenario.replace("_","-")
    if ntpath.splitdrive(str(output))[0].lower() == "c:" or output.exists():
        raise ValueError("Native Quit needs a fresh evidence directory off C:")
    output.mkdir()
    owner = 1 if scenario=="guest_authority" else 0
    case = dict(kind="native_quit_bounded_case",scenario=scenario,owner=owner,mode=ctx["mode"],
        input_path=ctx["input_path"],machine_scope="same_machine",candidate_exe_sha256=expected_exe_sha256,
        candidate_binding=ctx.get("candidate_binding"),original=source,helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        status="failed_setup",observations=[],inputs=[],windows=[],captures=[],checks={},ledger_status="unverified",artwork_review="pending",
        remaining_requirements=["Composed absence of both gameplay bodies/HUD and preexisting effects on both native pages",
            "Primary final native Quit, current-data/title character selection, campaign ownership and guest menu reentry",
            "Opposite roster, acquired campaign progress and all other native UI contexts"])
    ctx["report"].setdefault("native_quit",[]).append(case)

    def require(ok,message):
        if not ok:raise NativeQuitError(message)
    def sample(label):
        current = dict(label=label,peers=ctx["both"](lambda peer:observe_native_quit(ctx["clients"][peer],ctx["debug"])))
        if online:current["network"]=ctx["network"]()
        case["observations"].append(current)
        require(len(current["peers"])==len(ctx["clients"]),"Native Quit observer omitted an owned process")
        require(all(row["observation"]["ready"]==row["observation"]["enrolled"]==1 and
            not row["observation"]["failed"] and not row["observation"]["mailbox"] for row in current["peers"]),
            "Native Quit lost ready co-op publication or armed a fixture")
        return current
    def wait(predicate,label):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            current=sample(label)
            if all(predicate(row) for row in current["peers"]):return current
            ctx["transport_window"](2)
        raise NativeQuitError(label+": native transition timed out")
    def press(seat,bits,label):
        before=sample(label+" before")
        receipt=dict(path=ctx["input_path"],seat=seat,pressed=bits,accepted=False,bypasses=[],label=label,
            before_ticks=[row["observation"]["tick"] for row in before["peers"]])
        case["inputs"].append(receipt)
        ctx["hold"](seat,bits,4,label)
        after=sample(label+" after neutral")
        receipt.update(accepted=True,after_ticks=[row["observation"]["tick"] for row in after["peers"]])
        return after
    def capture(label):
        case["captures"].extend(ctx["both"](lambda peer:dict(peer=peer,label=label,
            **ctx["debug"].capture_present(ctx["clients"][peer],output/f"peer-{peer}-{label}.png"))))
    def window(label,page,choice,reference):
        samples=[sample(label+" start")]
        for _ in range(3):
            ctx["transport_window"](window_frames);samples.append(sample(label))
        checks=reduce_quit_window(samples,owner=owner,page=page,choice=choice,reference=reference,
                                  networked=online,minimum_progress=window_frames)
        case["windows"].append(dict(label=label,samples=samples,checks=checks))
        require(all(checks.values()),label+": native ownership, resources, clock or transport failed")
        return samples[-1]

    try:
        initial=sample("Native Quit healthy fixed-roster preflight");case["before"]=initial
        require(all(row["observation"]["native_mode"]==10 and row["observation"]["native_phase"]==0 and
            row["observation"]["pause_owner"]==0 and tuple(row["observation"]["lifecycle"])==(0,0) and
            [p["character"] for p in row["observation"]["players"]]==[0,1] and
            all(p["active"] and p["state"]==1 and p["action"]==2 and p["hp"]==32 for p in row["observation"]["players"])
            for row in initial["peers"]),"Native Quit needs healthy, settled original X/P1 + Zero/P2 intro actors")
        press(owner,START,"Owner original Start opens personal pause")
        paused=wait(lambda row:owned_ready(row,owner),"Original owner pause input readiness")
        case["status"]="failed_behavior"
        press(owner,SELECT,"Owner original Select requests native Quit UI")
        if scenario=="guest_authority":
            # Observe the complete refusal window. An admitted guest cannot
            # make the later confirmation/reset accidentally appear successful.
            samples=[]
            for _ in range(4):
                current=sample("Guest Select authority observation");samples.append(current)
                if any(row["menu"][1]==6 for row in current["peers"]):
                    case["guest_quit_admitted"]=current
                    case["checks"]["guest_select_cannot_enter_native_quit"]=False
                    try:
                        capture("guest-native-quit-page-admitted")
                    except Exception as capture_error:
                        # Preserve the observed ownership failure even if the
                        # secondary composed-artifact request also fails.
                        case.setdefault("capture_errors",[]).append(str(capture_error))
                    raise NativeQuitError("Guest Select entered the native Quit UI; no confirmation was sent")
                require(all(owned_ready(row,1) for row in current["peers"]),"Guest Select left its owned native pause")
                require(all(row["menu"]==old["menu"] and row["cursor"]==old["cursor"]
                    for old,row in zip(paused["peers"],current["peers"])),
                    "Guest Select changed its personal-menu input state or cursor")
                ctx["transport_window"](window_frames)
            # The general menu reducer verifies native freeze/transport while
            # source-mapped refusal is a separate positive ownership check.
            checks=menu.reduce_frozen_window(samples,1,reference_timers=[r["observation"]["native_timer"] for r in paused["peers"]],
                expected_cursors=[r["cursor"] for r in paused["peers"]],
                networked=online,minimum_progress=window_frames)
            case["checks"].update(checks,guest_select_cannot_enter_native_quit=True)
            require(all(checks.values()),"Guest Quit refusal did not preserve native freeze/transport")
            capture("guest-owned-pause-after-select-refusal")
        else:
            wait(lambda row:owned_ready(row,0,page=0,choice=0),"Native first Quit page")
            window("Native first-page retention",0,0,paused);capture("p1-native-quit-page-one")
            # Exercise actual native Continue/cancel, then both confirmation pages.
            press(0,CROSS,"Primary first-page choice0 returns to owned pause")
            wait(lambda row:owned_ready(row,0),"Native first-page cancel returns personal pause")
            press(0,SELECT,"Primary Select reopens native first page")
            wait(lambda row:owned_ready(row,0,page=0,choice=0),"Native first page reopened")
            press(0,DOWN,"Primary native Down selects Quit request")
            wait(lambda row:owned_ready(row,0,page=0,choice=1),"Native first-page choice changed")
            press(0,CROSS,"Primary Cross opens native second confirmation page")
            wait(lambda row:owned_ready(row,0,page=1,choice=1),"Native second Quit page")
            window("Native second-page retention",1,1,paused);capture("p1-native-quit-page-two")
            # Wrong-seat confirm must not execute the native final-quit branch.
            for bits,label in ((UP,"Guest Up cannot select primary final Quit"),(CROSS,"Guest Cross cannot confirm primary Quit")):
                press(1,bits,label);window(label,1,1,paused)
            press(0,CROSS,"Primary second-page choice1 returns native first page")
            wait(lambda row:owned_ready(row,0,page=0,choice=0),"Native second-page cancel returns first page")
            press(0,CROSS,"Primary first-page choice0 cancels to personal pause")
            wait(lambda row:owned_ready(row,0),"Native two-page cancellation restores primary pause")
            case["checks"].update(primary_native_first_page_continue=True,primary_second_page_cancel=True,
                                  guest_cannot_control_primary_confirmation=True)
        press(owner,START,"Original owner Start resumes native gameplay")
        wait(lambda row:row["observation"]["native_phase"]==0 and row["observation"]["pause_owner"]==0,
                     "Native owner resume after Quit cancellation/refusal")
        ctx["native_advance"](6,"Original world resumes after bounded native Quit case")
        after=sample("Native resumed ownership and personal resources");case["resumed"]=after
        checks=dict(personal_resources_preserved=menu.resources_preserved(initial["peers"],after["peers"]),
            native_roster_preserved=all([p["character"] for p in r["observation"]["players"]]==[0,1] for r in after["peers"]),
            original_world_resumed=all(menu._forward(a["observation"]["native_timer"],b["observation"]["native_timer"])
                for a,b in zip(paused["peers"],after["peers"])))
        case["checks"].update(checks);require(all(checks.values()),"Native cancel/resume resources or roster failed")
        before_move=after
        after=press(1,0x20,"Original P2 Right remains independent after native Quit cancel/refusal")
        independent=all(new["observation"]["players"][1]["x_raw"]>old["observation"]["players"][1]["x_raw"] and
            new["observation"]["players"][0]["x_raw"]==old["observation"]["players"][0]["x_raw"]
            for old,new in zip(before_move["peers"],after["peers"]))
        case["checks"]["genuine_independent_guest_input_after_cancel"]=independent
        require(independent,"Actual P2 native input did not resume independently")
        require(all(menu.resources_preserved(initial["peers"],sample_row["peers"])
                    for sample_row in case["observations"]),"Native UI/input history changed personal resources")
        capture("native-resumed-after-quit-cancel-or-refusal")
        if online:
            ctx["matched"]("Native Quit "+scenario+" resolved core/mod comparison")
            case["checks"]["resolved_core_mod_crc_comparison_completed"]=True
        case["status"]=SUCCESS
        return case
    except Exception as error:
        case.update(error=str(error),error_type=type(error).__name__)
        raise
