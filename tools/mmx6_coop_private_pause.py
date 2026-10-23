"""Native P1-owned menu/private-pool freeze, supplied with owned input adapters.

No launcher, guest writes, fixture/mailbox input, cards or ledger mutation.
Native acceptance, completed composed captures and artwork review are separate.
"""
from __future__ import annotations

import hashlib
import math
import ntpath
from pathlib import Path
import re
import time

import mmx6_coop_personal_menu as menu

START, SELECT, RIGHT, LEFT, CIRCLE, JUMP = 8, 1, 0x20, 0x80, 0x2000, 0x4000


class PrivatePauseError(RuntimeError):
    pass


def _forward(first, last, minimum=1):
    return minimum <= ((last-first) & 0xFFFFFFFF) < 0x80000000


def _pools(row):
    return (row["marker"], tuple(e["raw_hex"] for e in row["trails"]),
            tuple(e["raw_hex"] for e in row["attached"]))


def _visible(row):
    return (row["available"] and row["marker"] > 0 and
            row["observation"]["players"][1]["action"] in (0x0C, 6) and
            len(row["trails"]) == 3 and all(e["visible"] == e["active"] == 1 and
                e["allocation"] == 0x11 and e["phase"] == 0 for e in row["trails"]))


def _retired(row):
    return row["available"] and row["marker"] == 0 and len(row["trails"]) == 3 and all(
        e["visible"] == e["active"] == 0 for e in row["trails"])


def reduce_private_freeze(samples, *, networked=False, minimum_progress=6, reference=None):
    """Reject transient P2 state/input leaks even when endpoints match.

    Samples are JSON-safe outputs of the one-publication effects observer with
    separate native menu/cursor reads. Native bytes, not acknowledgements or
    hashes alone, establish the private-body/pool comparisons.
    """
    base = menu.reduce_frozen_window(samples, 0, networked=networked,
                                     minimum_progress=minimum_progress)
    checks = dict(base, visible_preexisting_private_trails=False,
                  exact_private_body_frozen=False, exact_private_pools_frozen=False,
                  personal_resources_preserved=False, original_menu_clock_retained=False,
                  original_cursor_retained=False, ordered_publications=False,
                  fixed_native_roster_ready=False)
    if len(samples) < 3 or not samples[0].get("peers"):
        return checks
    initial = reference or samples[0]
    count = len(initial["peers"])
    if any(len(sample.get("peers", [])) != count for sample in samples):
        return checks
    try:
        checks["fixed_native_roster_ready"] = all(
            row["observation"]["ready"]==row["observation"]["enrolled"]==1 and
            row["observation"]["failed"]==row["observation"]["mailbox"]==row["observation"]["scene_owner"]==0 and
            [p["character"] for p in row["observation"]["players"]]==[0,1] and
            all(p["active"] and p["state"]==1 and 0<p["hp"]<128 for p in row["observation"]["players"])
            for sample in samples for row in sample["peers"])
        checks["visible_preexisting_private_trails"] = all(_visible(row) for row in initial["peers"])
        checks["exact_private_body_frozen"] = all(
            row["available"] and len(bytes.fromhex(row["p2_body_hex"])) == 0x158 and
            row["p2_body_hex"] == initial["peers"][peer]["p2_body_hex"]
            for sample in samples for peer, row in enumerate(sample["peers"]))
        checks["exact_private_pools_frozen"] = all(
            len(row["trails"]) == len(row["attached"]) == 3 and
            all(len(bytes.fromhex(e["raw_hex"])) == size for key,size in (("trails",0x60),("attached",0x50)) for e in row[key]) and
            _pools(row) == _pools(initial["peers"][peer])
            for sample in samples for peer, row in enumerate(sample["peers"]))
        checks["personal_resources_preserved"] = all(
            menu.resources_preserved(initial["peers"], sample["peers"]) for sample in samples)
        checks["original_menu_clock_retained"] = all(
            row["observation"]["native_timer"] == initial["peers"][peer]["observation"]["native_timer"]
            for sample in samples for peer, row in enumerate(sample["peers"]))
        checks["original_cursor_retained"] = all(
            row["cursor"] == initial["peers"][peer]["cursor"]
            for sample in samples for peer, row in enumerate(sample["peers"]))
        checks["ordered_publications"] = (all(
            len({row["peers"][peer]["observation"]["tick"] for row in samples})>=3 for peer in range(count)) and all(
            a["peers"][peer]["observation"]["tick"]==b["peers"][peer]["observation"]["tick"] or
            _forward(a["peers"][peer]["observation"]["tick"], b["peers"][peer]["observation"]["tick"])
            for a, b in zip(samples, samples[1:]) for peer in range(count)))
    except (KeyError, TypeError, ValueError):
        pass
    return checks


def private_pause_smoke(ctx, *, expected_exe_sha256, window_frames=12, timeout=12,
                        max_retirement_ticks=32):
    """Bounded fixed X/P1 + Zero/P2 menu freeze and post-resume dash-jump.

    Same personal-menu ctx, plus effects module, candidate_exe_sha256 and
    hold_observed(seat,bits,frames,label,observe). That callback returns >=3
    ordered samples WHILE held, always neutralizes, and allows the observer's
    one nested OTHER-seat Start hold. Online additionally supplies matched().
    """
    required = ("mode", "input_path", "clients", "both", "debug", "effects", "report", "output",
                "hold", "hold_observed", "native_advance", "transport_window", "candidate_exe_sha256")
    if any(key not in ctx for key in required):
        raise ValueError("Incomplete private-pause runner context")
    if (not isinstance(expected_exe_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_exe_sha256) or
            ctx["candidate_exe_sha256"] != expected_exe_sha256):
        raise ValueError("Private pause requires the adapter's explicitly verified candidate image binding")
    if ctx["mode"] not in ("local", "netplay"):
        raise ValueError("Expected local/netplay")
    online = ctx["mode"] == "netplay"
    if ctx["input_path"] != ("published_host" if online else "offline_native"):
        raise ValueError("Private pause requires original native input locally and published host input online")
    if len(ctx["clients"]) != (2 if online else 1):
        raise ValueError("Expected one owned offline process or two owned peers")
    if any(not callable(ctx[key]) for key in ("both", "hold", "hold_observed", "native_advance", "transport_window")):
        raise ValueError("Owned input/progress callbacks must be callable")
    if online and any(not callable(ctx.get(key)) for key in ("network", "matched")):
        raise ValueError("Online private pause requires actual transport status and resolved CRC comparison")
    if (not math.isfinite(timeout) or not 0 < timeout <= 60 or not 6 <= window_frames <= 120 or
            not 2 <= max_retirement_ticks <= 120):
        raise ValueError("Private pause windows/deadline exceed bounded limits")
    effects = ctx["effects"]
    if any(not callable(getattr(effects, key, None)) for key in
           ("observe_effects", "reduce_effect_menu_freeze", "reduce_zero_dash")):
        raise ValueError("Current private-effects observer/reducers are required")
    if not callable(getattr(ctx["debug"],"capture_present",None)):
        raise ValueError("Completed composed capture callback is required")
    effects_sha=hashlib.sha256(Path(effects.__file__).read_bytes()).hexdigest()
    output = Path(ctx["output"]).resolve()/"private-pause"
    if ntpath.splitdrive(str(output))[0].lower() == "c:" or output.exists():
        raise ValueError("Private pause requires fresh evidence paths off C:")
    output.mkdir()
    case = dict(kind="native_p1_pause_private_effect_freeze", status="failed_setup", mode=ctx["mode"],
        candidate_exe_sha256=expected_exe_sha256, candidate_binding=ctx.get("candidate_binding"),
        helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        effects_helper_sha256=effects_sha,
        input_path=ctx["input_path"], observations=[], inputs=[], frozen_windows=[], captures=[],
        checks=dict(p1_native_menu_freezes_private_state_under_original_p2_input=False,
                    native_resume_advances_private_effects=False,
                    genuine_post_resume_native_dash_and_finite_retirement=False,
                    personal_resources_preserved=False,p1_independent=False,composed_captures_completed=False),
        ledger_status="unverified", artwork_review="pending", limits=[
            "Fixed X/P1 and Zero/P2 only; no full R9, opposite roster or P1 attack qualification",
            "P1 menu timing must actually retain a positive marker and visible private trails",
            "Menu/cursor reads follow a coherent effects RPC and are separate observations",
            "Held input acknowledgment is not native dash acceptance",
            "Retirement uses observed native timer ticks, not exactly-once helper/world counts",
            "Simultaneous native Circle+Jump is a dash-jump, not an air-dash unlock proof",
            "Composed capture completion is not artwork approval; no ledger pass"])
    ctx["report"].setdefault("private_pause", []).append(case)
    if online:case["checks"]["resolved_crc_comparison_completed"]=False
    live = []

    def require(ok, message):
        if not ok:
            raise PrivatePauseError(message)

    def sample(label):
        raw = ctx["both"](lambda peer: effects.observe_effects(ctx["clients"][peer]))
        peers = []
        for peer, observed in enumerate(raw):
            row = observed.json()
            row.update(menu=list(ctx["clients"][peer].read(menu.MENU_STATE, 2)),
                       cursor=ctx["clients"][peer].read(menu.MENU_CURSOR, 1)[0])
            peers.append(row)
        current = dict(sample_index=len(live), label=label, peers=peers)
        if online:
            current["network"] = ctx["network"]()
        live.append(raw);case["observations"].append(current)
        return current

    def gameplay(row):
        base = row["observation"]
        return (row["available"] and base["ready"] == base["enrolled"] == 1 and not base["failed"] and
            not base["mailbox"] and not base["scene_owner"] and base["native_mode"] == 10 and
            base["native_phase"] == 0 and base["pause_owner"] == 0 and tuple(base["lifecycle"]) == (0, 0) and
            [p["character"] for p in base["players"]] == [0, 1] and
            all(p["active"] and p["state"] == 1 and 0 < p["hp"] < 128 for p in base["players"]))

    def held(seat, bits, frames, label, observer=None):
        before = sample(label+" before")
        receipt = dict(seat=seat, path=ctx["input_path"], pressed=bits, frames=frames,
                       bypasses=[], accepted=False, before_sample=before["sample_index"], label=label)
        case["inputs"].append(receipt)
        rows = ctx["hold_observed"](seat, bits, frames, label, observer or (lambda:sample(label+" held")))
        require(isinstance(rows, (list, tuple)) and len(rows) >= 3,
                "Owned observed hold omitted three during-input samples")
        receipt.update(accepted=True, held_samples=[row["sample_index"] for row in rows])
        after = sample(label+" after neutral")
        receipt["after_neutral_sample"] = after["sample_index"]
        return before, rows, after

    def press(seat, bits, frames, label):
        receipt = dict(seat=seat, path=ctx["input_path"], pressed=bits, frames=frames,
                       bypasses=[], accepted=False, label=label)
        case["inputs"].append(receipt);ctx["hold"](seat,bits,frames,label);receipt["accepted"]=True

    def capture(label):
        for peer, client in enumerate(ctx["clients"]):
            case["captures"].append(dict(peer=peer, label=label,
                **ctx["debug"].capture_present(client, output/f"peer-{peer}-{label}.png")))

    def unique(rows, peer, *, after=None):
        result=[];last=after
        for row in rows:
            value=live[row["sample_index"]][peer]
            if last is not None and value.observation.tick == last.observation.tick:
                require(value.json()==last.json(), "One completed publication changed without advancing its tick")
                continue
            if last is not None:
                require(_forward(last.observation.tick,value.observation.tick), "Effect publications moved backward")
            result.append(value);last=value
        return result

    try:
        ctx["native_advance"](6,"Private pause preflight settle")
        before=sample("Private pause native preflight");case["before"]=before
        require(all(gameplay(row) and _retired(row) and all(player["action"]==2 for player in row["observation"]["players"])
                    for row in before["peers"]), "Private pause needs idle, living fixed-roster heroes and clear private trails")
        opened=None;attempted=False

        def dash_then_open():
            nonlocal opened,attempted
            current=sample("Pre-menu P2 Circle+Left while held")
            if not attempted and all(gameplay(row) and _visible(row) for row in current["peers"]):
                attempted=True;case["accepted_before_menu"]=current
                press(0,START,4,"P1 Start during observed P2 native dash")
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    current=sample("P1 native menu entry while P2 dash remains held")
                    if all(row["observation"]["native_phase"]==2 and row["observation"]["pause_owner"]==1
                           and _visible(row) for row in current["peers"]):
                        opened=current
                        if all(row["menu"][0]==1 for row in current["peers"]):
                            break
                    ctx["transport_window"](2)
                require(opened is not None and all(row["menu"][0]==1 for row in current["peers"]),
                        "P1 menu did not retain an observed positive-marker trail into input-ready pause")
            return current

        held(1,CIRCLE|LEFT,8,"Prepare actual P2 ground dash and P1 pause",dash_then_open)
        require(attempted and opened is not None,"Native Circle did not expose an eligible trail window for P1 pause")
        case["status"]="failed_behavior";case["opened"]=opened
        reference=sample("P1-owned input-ready private-pool baseline")
        require(all(_visible(row) for row in reference["peers"]),"Private trails were lost before the frozen window")
        frozen=[reference]
        for bits,frames,label in ((CIRCLE,window_frames,"P2 Circle held in P1 pause"),
                                 (RIGHT,window_frames,"P2 Right held in P1 pause"),
                                 (SELECT,max(96,window_frames),"P2 Select held beyond departure threshold in P1 pause")):
            start,rows,after=held(1,bits,frames,label)
            window=[start,*rows,after]
            # Repeated reads of one completed publication add no progression.
            compact=[]
            for row in window:
                if compact and all(a["observation"]["tick"]==b["observation"]["tick"]
                                   for a,b in zip(compact[-1]["peers"],row["peers"])):
                    continue
                compact.append(row)
            checks=reduce_private_freeze(compact,networked=online,minimum_progress=window_frames,reference=reference)
            held_minimum=90 if bits==SELECT else max(2,frames-4)
            checks["during_held_publications_advanced"]=all(
                len({row["peers"][peer]["observation"]["tick"] for row in rows})>=3 and
                _forward(rows[0]["peers"][peer]["observation"]["tick"],
                         rows[-1]["peers"][peer]["observation"]["tick"],held_minimum)
                for peer in range(len(ctx["clients"])))
            case["frozen_windows"].append(dict(label=label,samples=compact,checks=checks))
            require(all(checks.values()),f"{label}: private body/pools, ownership, native clock or transport changed")
            frozen.extend(compact)
        capture("p1-menu-present")
        captured=sample("P1 pause after completed composed capture");frozen.append(captured)
        require(all(reduce_private_freeze([reference,*case["frozen_windows"][-1]["samples"],captured],
                    networked=online,minimum_progress=window_frames,reference=reference).values()),
                "Private pools changed while capturing the paused composed frame")
        case["checks"]["p1_native_menu_freezes_private_state_under_original_p2_input"]=True
        press(0,START,4,"P1 native Start resumes private effects")
        resume_history=[];case["resume_retirement"]=resume_history
        deadline=time.monotonic()+timeout;resume_timers=None
        while time.monotonic()<deadline:
            current=sample("P2 native private effect recovery after P1 resume");resume_history.append(current)
            if all(gameplay(row) and _retired(row) for row in current["peers"]):
                break
            if all(gameplay(row) for row in current["peers"]):
                timers=[row["observation"]["native_timer"] for row in current["peers"]]
                if resume_timers is None:resume_timers=timers
                require(all(((now-old)&0xFFFFFFFF)<=2*max_retirement_ticks for old,now in zip(resume_timers,timers)),
                        "Pre-menu dash did not retire within the bounded post-resume native window")
                ctx["native_advance"](1,"Native private-pool retirement after resume")
            else:ctx["transport_window"](2)
        require(all(gameplay(row) and _retired(row) for row in current["peers"]),"Native private pools did not retire after resume")
        case["effect_menu_reduction"]=[]
        for peer in range(len(ctx["clients"])):
            source=[]
            for row in frozen:
                value=live[row["sample_index"]][peer]
                if not source or value.observation.tick!=source[-1].observation.tick:source.append(value)
            resumed=next((value for row in resume_history for value in [live[row["sample_index"]][peer]]
                          if gameplay(value.json()) and _pools(value.json())!=_pools(reference["peers"][peer])),None)
            checks=effects.reduce_effect_menu_freeze(source,resumed=resumed,owner=0,minimum_progress=window_frames)
            case["effect_menu_reduction"].append(checks)
            require(all(checks.values()),"Source-bound native menu/private-effect resume reduction failed")
        case["checks"]["native_resume_advances_private_effects"]=True
        def observe_dash_art():
            current=sample("Fresh post-menu native dash held")
            if "dash_render_window" not in case and all(_visible(row) for row in current["peers"]):
                case["dash_render_window"]=current
                capture("p2-native-dash-present")
                completed=sample("Native dash after completed composed capture")
                case["dash_render_after_capture"]=completed
                require(all(_visible(row) for row in completed["peers"]),
                        "Native dash visible window ended before composed capture completed")
            return current
        dash_before,active,released_first=held(1,CIRCLE|JUMP|RIGHT,6,
            "Fresh post-menu native Circle+Jump+Right",observe_dash_art)
        require("dash_render_after_capture" in case,"No native visible dash window was captured")
        release=[released_first];deadline=time.monotonic()+timeout
        drain_timers=[None]*len(ctx["clients"])
        case["post_resume_dash"]=dict(before=dash_before,active=active,
            post_release=release,reductions=[],
            continuation_limit_ticks=120,
            limits=["Neutral input does not immediately end a native jump-dash.",
                    "Positive-marker continuation is retained separately from the negative-marker drain.",
                    "The finite drain bound starts at the first observed negative marker per peer."])
        while time.monotonic()<deadline:
            require(all(gameplay(row) for row in release[-1]["peers"]),"Native dash recovery left living gameplay")
            for peer,row in enumerate(release[-1]["peers"]):
                timer=row["observation"]["native_timer"]
                if drain_timers[peer] is None and row["marker"]<0:drain_timers[peer]=timer
                if drain_timers[peer] is None:
                    require(((timer-released_first["peers"][peer]["observation"]["native_timer"])&0xFFFFFFFF)<=120,
                            "Native post-release jump-dash continuation exceeded the bounded observation window")
                else:
                    require(row["marker"]<=0,"Native dash retriggered after the negative-marker drain began")
                    require(((timer-drain_timers[peer])&0xFFFFFFFF)<=max_retirement_ticks,
                            "Fresh native dash retirement exceeded its bounded negative-marker drain window")
            if all(_retired(row) for row in release[-1]["peers"]):break
            ctx["native_advance"](1,"Observe native dash-jump drain")
            release.append(sample("Post-menu native dash-jump retirement"))
        require(all(_retired(row) for row in release[-1]["peers"]),"Fresh native dash never completed its finite retirement")
        for peer in range(len(ctx["clients"])):
            first=live[dash_before["sample_index"]][peer]
            held_rows=unique(active,peer,after=first);require(bool(held_rows),"No forward native dash observation during held Circle")
            post=unique(release,peer,after=held_rows[-1]);require(bool(post),"No native publication after neutral input")
            drain_at=next((i for i,row in enumerate(post) if row.marker<0),None)
            require(drain_at is not None,"Native dash never entered its negative-marker drain")
            # Native jump-dash action7 legitimately continues after neutral;
            # only its negative-marker transition starts trail retirement.
            during=held_rows+post[:drain_at];drained=post[drain_at:]
            receipts=[dict(path=ctx["input_path"],seat=1,pressed=CIRCLE|JUMP|RIGHT,accepted=True,bypasses=[],
                           before_tick=first.observation.tick,after_tick=held_rows[0].observation.tick),
                      dict(path=ctx["input_path"],seat=1,pressed=0,accepted=True,bypasses=[],
                           before_tick=held_rows[-1].observation.tick,after_tick=post[0].observation.tick)]
            reduced=effects.reduce_zero_dash(first,during,drained,mode=ctx["mode"],input_path=ctx["input_path"],
                                              input_receipts=receipts,max_retirement_ticks=max_retirement_ticks)
            reduced.update(input_receipts=receipts,
                post_release_continuation_ticks=[row.observation.tick for row in post[:drain_at]],
                negative_drain_start_tick=drained[0].observation.tick)
            case["post_resume_dash"]["reductions"].append(reduced)
            require(all(reduced["checks"].values()),"Fresh native post-menu dash acceptance/drain/retirement failed")
            require(any(row.marker>0 and row.observation.players[1].action==6 and
                        row.observation.players[1].y_raw<first.observation.players[1].y_raw for row in during),
                    "Post-menu Circle+Jump did not expose an actual rising native dash-jump")
        final=sample("Private pause final native observation");case["final"]=final
        require(all(menu.resources_preserved(before["peers"],row["peers"]) for row in case["observations"]),
                "Private pause/dash route changed personal resources")
        require(all(row["observation"]["players"][0]["x_raw"]==old["observation"]["players"][0]["x_raw"]
                    for sample_row in case["observations"] for old,row in zip(before["peers"],sample_row["peers"])),
                "P1 moved during P2 native dash recovery")
        case["checks"].update(genuine_post_resume_native_dash_and_finite_retirement=True,personal_resources_preserved=True,p1_independent=True)
        capture("resumed-present")
        case["checks"]["composed_captures_completed"]=True
        if online:
            ctx["matched"]("P1 native menu/private-pool freeze and Zero native dash recovery")
            case["checks"]["resolved_crc_comparison_completed"]=True
        require(all(case["checks"].values()),"Private-pause case did not complete every required gate")
        case["status"]="automated_private_pause_checks_passed_artwork_pending"
        return case
    except Exception as error:
        case.update(error=str(error),error_type=type(error).__name__)
        raise
