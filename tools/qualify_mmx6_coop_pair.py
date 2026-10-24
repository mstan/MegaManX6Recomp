"""Stage and qualify one owned, hidden, muted loopback X6 delay-sync pair.

Uses current shared tools from --tools-root, not the worker's older copies.
Never writes guest RAM/mailboxes/fixtures or copies source memory cards.
Only the two Popen processes created here can be stopped. Successful checks
cover the selected native cases; full campaign and cross-host parity remain
separate qualification gates.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import traceback


CONTACT_EXE_SHA = "37cdc4876f7e852b97ef5f14210809b0af7d4a8adaa1759c9e096017170e1fa9"


def same_machine_plan(peers):
    """Inspect the actual owned launch argv; no DNS or non-loopback peers."""
    if len(peers)!=2:
        raise ValueError("Same-machine native Quit needs exactly two owned launch plans")
    records=[]
    for seat,peer in enumerate(peers):
        argv=peer["argv"]
        def value(flag):
            if argv.count(flag)!=1 or argv.index(flag)+1>=len(argv):
                raise ValueError("Missing/duplicate native Quit network launch flag")
            return argv[argv.index(flag)+1]
        endpoints={}
        for flag in ("--net-bind","--net-peer"):
            text=value(flag)
            match=re.fullmatch(r"127\.0\.0\.1:([1-9][0-9]{0,4})",text)
            if match is None or not 1<=int(match[1])<=65535:
                raise ValueError("Native Quit pair endpoints must be numeric 127.0.0.1 with bounded ports")
            endpoints[flag]=text
        if value("--net-slot")!=str(seat) or value("--net-input-player")!="0" or value("--net-delay")!="3":
            raise ValueError("Native Quit requires original host mapping, seat0/1 and delay3")
        records.append(dict(seat=seat,bind=endpoints["--net-bind"],peer=endpoints["--net-peer"]))
    if (records[0]["bind"]==records[1]["bind"] or records[0]["peer"]!=records[1]["bind"] or
            records[1]["peer"]!=records[0]["bind"]):
        raise ValueError("Native Quit same-machine UDP plans must point to each other")
    return dict(scope="same_machine",numeric_host="127.0.0.1",peers=records,
        ownership="Both Popen handles and every debug listener are checked separately by the runner")


def exercise_native_quit_pair(ctx,*,native_quit,published_input,original_exe,expected_sha,scenario):
    """Adapt only accepted published host input; retain the helper's failure."""
    report=ctx["report"]
    report["checks"]["native_quit_automated_case_completed"]=False
    plan=same_machine_plan(report["peers"])
    if (report.get("candidate_exe_sha256")!=expected_sha or
            any(peer.get("preparation",{}).get("exe_sha256")!=expected_sha for peer in report["peers"])):
        raise ValueError("Native Quit published adapter requires two staged copies of the exact candidate")
    if (not report["checks"].get("host_profile_settled_before_guest") or
            not report["checks"].get("declared_build_manifest_bound_to_staged_images") or
            not report["checks"].get("default_resident_loader_committed") or not report.get("resolved_state_crc") or
            not report.get("host_profile_startup") or not report.get("host_profile_build_manifest")):
        raise ValueError("Native Quit needs committed default loader, actual pre-guest host profile and resolved state CRC evidence")
    adapter=published_input.PublishedHeldInput(ctx["clients"],ctx["network"],ctx["transport_window"],report)
    case=native_quit.native_quit_smoke(dict(mode="netplay",input_path="published_host",
        clients=ctx["clients"],both=ctx["both"],debug=ctx["debug"],report=report,output=ctx["output"],
        hold=adapter.hold,hold_observed=adapter.hold_observed,native_advance=ctx["native_advance"],transport_window=ctx["transport_window"],
        network=ctx["network"],matched=ctx["matched"],candidate_exe_sha256=expected_sha,same_machine=True,
        candidate_binding=dict(exe_sha256=expected_sha,host_profile=report["host_profile_startup"],
            network_plan=plan,declared_build=report["host_profile_build_manifest"])),
        original_exe=original_exe,expected_exe_sha256=expected_sha,scenario=scenario)
    report["native_quit_automated_status"]=case["status"]
    report["checks"]["native_quit_automated_case_completed"]=(case["status"]==native_quit.SUCCESS and
        bool(case["checks"]) and all(case["checks"].values()))
    return case


def enemy_targeting_smoke(ctx):
    """Original published peer1 input; read-only guest evidence on both peers."""
    enemy, clients, both = ctx["enemy"], ctx["clients"], ctx["both"]
    require, network, report = ctx["require"], ctx["network"], ctx["report"]
    case = dict(observations=[], initialized=[], action2=[], attack=[], captures=[],
                input_path="peer1 virtual host device through delay transport",
                limits=["Separate guest reads are not one atomic world sample",
                        "Independent exactly-once world-update counter remains unverified"])
    report["enemy_targeting"] = case
    histories, seen_action1, seen_action2 = [[], []], [False, False], [False, False]

    def sample(label):
        current = both(lambda seat: enemy.observe_case(clients[seat]))
        network()
        case["observations"].append(dict(label=label, peers=current))
        for seat, row in enumerate(current):
            histories[seat].append(dict(label=label, **row))
            require(row["observation"]["players"][0]["x_raw"] == 144 << 16,
                    "R13 primary moved from its fixed native X")
            target = row["instance"]
            if target and target["phase"] == 1 and target["hp"] == 12 and target["action"] == 1:
                seen_action1[seat] = True
            near = enemy.resident_targeting_sample(row)
            if near and near["action_plus5"] == 2:
                seen_action2[seat] = True
                case["action2"].append(dict(seat=seat, **near))
        return current

    def advance(count, label):
        initial = sample(label + " start")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            current = sample(label)
            if all(((row["observation"]["native_timer"] - old["observation"]["native_timer"]) & 0xFFFFFFFF) >= count
                   for old, row in zip(initial, current)):
                return current
            time.sleep(.02)
        raise RuntimeError("R13 native timers did not advance through the published-input window")

    def hold(buttons, count, label):
        clients[1].host_input(buttons)
        try:
            advance(count, label)
        finally:
            clients[1].host_input(0)
        # Let neutral input cross delay3 before the next geometric decision.
        return advance(5, label + " release")

    initial = sample("R13 preflight")
    require(all(enemy.preflight(row) for row in initial), "R13 source-derived preflight failed")
    view = both(lambda seat: clients[seat].request("gpu_state"))
    wide = both(lambda seat: clients[seat].request("ws_nw"))
    require(all(enemy.native_43(gpu, nw) for gpu, nw in zip(view, wide)), "R13 requires native 4:3/margin0")
    admitted = [None, None]
    for step in range(24):
        current = hold(0x20, 5, f"R13 admission right {step}")
        for seat, row in enumerate(current):
            if admitted[seat] is None and row["instance"]:
                admitted[seat] = row
            require(row["camera"][0] <= 80 or admitted[seat] is not None,
                    "R13 passed the admission window without its bound origin")
        if all(admitted):
            break
    require(all(admitted), "R13 bounded published P2 lead did not admit both native actors")
    case["admitted"] = admitted
    require(all(48 <= row["camera"][0] <= 80 for row in admitted), "R13 admission camera outside source window")
    initialized = advance(8, "R13 native initialization")
    require(all(row["instance"] and row["instance"]["phase"] == 1 and
                row["instance"]["hp"] == 12 and row["instance"]["subtype"] == 1
                for row in initialized), "R13 native phase1/HP12 initialization missing")
    case["initialized"] = initialized
    addresses = [row["instance"]["address"] for row in initialized]
    last_x, stalled, jumped = None, 0, False
    for step in range(32):
        current = sample("R13 approach")
        require(all(row["instance"] and row["instance"]["address"] == addresses[seat]
                    for seat, row in enumerate(current)), "R13 bound actor changed before attack")
        distances = [(row["instance"]["x_raw"] - row["observation"]["players"][1]["x_raw"]) / 65536
                     for row in current]
        if all(distance <= 40 for distance in distances):
            break
        positions = [row["observation"]["players"][1]["x_raw"] for row in current]
        stalled = stalled + 1 if last_x is not None and all(abs(a-b) < 65536 for a, b in zip(positions, last_x)) else 0
        last_x = positions
        if stalled >= 2 and not jumped:
            case["terrain_jump"] = dict(positions=positions, step=step)
            hold(0x4020, 24, "R13 single terrain jump-right")
            jumped = True
        else:
            hold(0x20, 5, f"R13 approach right {step}")
    else:
        raise RuntimeError("R13 published P2 input did not reach native attack range")
    require(all(seen_action1) and all(seen_action2), "R13 both native actors must transition action1->2 with only P2 near")
    before_attack = sample("R13 before native attack")
    require(all(row["instance"]["hp"] == 12 for row in before_attack), "R13 enemy HP changed before controlled attack")
    case["before_attack"] = before_attack
    if any(row["observation"]["players"][1]["y_raw"] > row["instance"]["y_raw"] + (16 << 16)
           for row in before_attack):
        hold(0x4000, 5, "R13 jump toward elevated enemy")
    attack_start = [len(history) for history in histories]
    clients[1].host_input(0x8000)
    try:
        advance(8, "R13 native Square")
    finally:
        clients[1].host_input(0)
    hits = [None, None]
    for step in range(20):
        for seat in range(2):
            hits[seat] = enemy.attack_evidence(before_attack[seat], histories[seat][attack_start[seat]:])
        if all(hits):
            break
        advance(3, f"R13 native attack result {step}")
    require(all(hits), "R13 lacked an origin-bound native HP drop on both peers")
    case["attack"] = hits
    advance(90, "R13 death and input settle")
    ctx["matched"]("R13 native target response and attack")

    # Original P1 Start freezes the native post-route scene for matching GL
    # captures. No local engine pause, RAM or simulation-success writes.
    clients[0].host_input(8)
    ctx["wait_observed"](lambda row: row.native_phase == 2 and row.pause_owner == 1,
                         "R13 post-route native pause did not open")
    clients[0].host_input(0)
    ctx["transport_window"](15)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        ready = both(lambda seat: clients[seat].read(0x800CF814, 1)[0] == 1)
        if all(ready):
            break
        time.sleep(.05)
    require(all(ready), "R13 native pause did not finish opening")
    case["captures"] = both(lambda seat: dict(seat=seat, **ctx["debug"].capture_present(
        clients[seat], ctx["output"]/f"peer-{seat}/logs/r13-paused-present.png")))
    require(case["captures"][0]["sha256"] == case["captures"][1]["sha256"],
            "R13 composed native post-route pause captures differ")
    clients[0].host_input(8)
    ctx["wait_observed"](lambda row: row.native_phase == 0, "R13 native pause did not resume")
    clients[0].host_input(0)
    advance(20, "R13 post-capture resume")
    ctx["matched"]("R13 post-capture native resume")
    report["checks"].update(r13_both_origin_bound_native_init=True,
        r13_both_action1_to2_only_p2_near=True, r13_both_native_p2_enemy_hp_drop=True,
        r13_p1_x_stayed_fixed=True, r13_composed_pause_captures_match=True)


def run(args) -> dict:
    tools_root = args.tools_root.resolve(strict=True)
    staging_source = (getattr(args,"source",None) or tools_root.parent).resolve(strict=True)
    sys.path.insert(0, str(tools_root))
    debug = importlib.import_module("coop_debug")
    preparation = importlib.import_module("prepare_mmx6_coop_playtest")
    baseline = importlib.import_module("qualify_mmx6_coop_baseline")
    paired = importlib.import_module("test_mmx6_coop_netplay")
    state_crc = importlib.import_module("coop_state_crc")
    modules = (debug, preparation, baseline, paired, state_crc)
    host_profiles = None
    if getattr(args, "require_host_profile", False):
        host_profiles = importlib.import_module("coop_host_profile")
        modules += (host_profiles,)
    enemy = None
    if getattr(args, "enemy_targeting_smoke", False):
        enemy = importlib.import_module("qualify_mmx6_coop_enemy_admission")
        modules += (enemy,)
    personal_menu = None
    if getattr(args, "personal_menu_smoke", False):
        personal_menu = importlib.import_module("mmx6_coop_personal_menu")
        modules += (personal_menu,)
    private_pause = effects = published_input = native_quit = None
    reentry_pair = source_validation = audio_pair = state_policy = hud_pair = None
    if getattr(args,'hud_presentation_smoke',False):
        hud_pair=importlib.import_module('mmx6_coop_hud_pair')
        modules+=(hud_pair,hud_pair.hud,hud_pair.hud.resources,hud_pair.hud.state,hud_pair.hud.mapped,
                  hud_pair.hud.mapped.keyboard_input)
    if getattr(args,"state_policy_smoke",False):
        state_policy=importlib.import_module("mmx6_coop_state_policy")
        modules+=(state_policy,state_policy.keyboard)
    if getattr(args,"jump_audio_smoke",False) or state_policy is not None or hud_pair is not None:
        audio_pair=importlib.import_module("mmx6_coop_jump_audio_pair")
        source_validation=audio_pair.sources
        modules+=(audio_pair,audio_pair.audio,audio_pair.ownership,audio_pair.ownership.host,source_validation)
        modules+=tuple(importlib.import_module(name) for name in
            ("audit_mmx6_coop_audio","inventory_mmx6_coop_content","mmx6_seamless_catalog"))
        if getattr(args,'primary_audio_smoke',False):
            primary_observer=importlib.import_module('mmx6_coop_primary_audio')
            modules+=(primary_observer,primary_observer.native,primary_observer.contact)
    if getattr(args,"native_reentry",None):
        reentry_pair=importlib.import_module("mmx6_coop_native_reentry_pair")
        source_validation=importlib.import_module("qualify_mmx6_coop_jump_audio")
        modules+=(reentry_pair,reentry_pair.helper,reentry_pair.published,reentry_pair.host,
            reentry_pair.helper.quit_ui,reentry_pair.helper.menu,reentry_pair.helper.content,
            reentry_pair.helper.native,source_validation)
    if getattr(args,"native_quit_scenario",None):
        native_quit=importlib.import_module("mmx6_coop_native_quit")
        published_input=importlib.import_module("mmx6_coop_published_input")
        modules+=(native_quit,native_quit.menu,published_input)
        if args.native_quit_scenario=="p1_pages_cancel_live_effects":modules+=(native_quit.private_pause,native_quit.private_effects)
    if getattr(args, "private_pause_smoke", False):
        private_pause = importlib.import_module("mmx6_coop_private_pause")
        effects = importlib.import_module("mmx6_coop_private_effects")
        published_input = importlib.import_module("mmx6_coop_published_input")
        modules += (private_pause, effects, published_input)
    contact, zero_overlay, original_disc = None, None, None
    if getattr(args, "contact_pause_contact_smoke", False):
        contact = importlib.import_module("mmx6_coop_contact")
        inventory = importlib.import_module("inventory_mmx6_coop_content")
        modules += (contact, contact.menu, contact.enemy, inventory)
    if any(Path(module.__file__).resolve().parent != tools_root for module in modules):
        raise ValueError("A shared tool resolved outside --tools-root")
    candidate_sha = preparation.sha256(args.build / "mmx6-runtime.exe")
    if getattr(args, "expected_exe_sha256", None) and candidate_sha != args.expected_exe_sha256:
        raise ValueError("Paired executable does not match the explicitly expected SHA256")
    quit_original=native_quit.verify_original(args.original_exe) if native_quit is not None else None
    reentry_original=reentry_binding=None
    if reentry_pair is not None:
        reentry_binding=reentry_pair.bind_original_disc(args.disc,args.original_disc)
        reentry_original=reentry_pair.helper.load_sources(args.original_disc)["original"]
    audio_source=None
    if audio_pair is not None:
        audio_source=audio_pair.load_sources(args.original_exe,args.original_disc,args.disc,
            tools_root.parent/"docs/COOP_JUMP_AUDIO_CONTRACT.json")
    if contact is not None:
        if candidate_sha != CONTACT_EXE_SHA or candidate_sha != contact.EXE_SHA:
            raise ValueError("R2 paired executable is not the selected frozen37cdc487 candidate")
        original_disc = args.original_disc.resolve(strict=True)
        zero_overlay = contact.load_zero_overlay(original_disc)
    output = preparation.local_output(args.out)
    if output.exists():
        raise ValueError("Output exists; retain earlier evidence and choose a fresh directory")
    output.mkdir(parents=True)
    (output/"runner-source.py").write_bytes(Path(__file__).read_bytes())
    admission_only = getattr(args, "admission_only", False)
    report = dict(schema=1, kind="owned_loopback_delay_admission" if admission_only else "owned_loopback_delay_intro", status="failed_setup",
                  candidate_exe_sha256=candidate_sha,
                  runner_source_sha256=preparation.sha256(Path(__file__)),
                  loading_policy="original_disc_loader_diagnostic_bypass" if args.native_loader_diagnostic
                                 else "default_seamless_loading",
                  default_intro_qualified=False,
                  default_launch_qualified=False,
                  tools_root=str(tools_root), staging_source=str(staging_source), tool_sha256={Path(m.__file__).name:
                  preparation.sha256(Path(m.__file__)) for m in modules},
                  session=args.session, input_delay=3, peers=[], setup=[], observations=[],
                  host_profile_required=host_profiles is not None,
                  host_profile_expected=dict(profile=args.expected_host_profile,
                      revision=args.expected_host_profile_revision) if host_profiles is not None else None,
                  checks={}, matched_host_observations=[], resolved_state_crc=[], limits=[
                      "Intro only; no campaign, physical-controller, audible or real-network pass",
                      "Diagnostic FNV is bounded host state, not a framework core/mod CRC",
                      "Diagnostic publication counts are not netplay simulation ticks",
                      "Overlay autocompilation is off; no AOT or performance claim",
                      "No source memory cards were supplied or copied"])
    if contact is not None:
        report["contact_original_source"] = dict(raw_disc=str(original_disc),
            exe_sha256=inventory.EXE_SHA256, archive_sha256=inventory.BIN_SHA256,
            zero_overlay_sha256=contact.ZERO_SHA,
            scope="Verified bounded EXE/archive/Zero members, not a whole-raw-disc hash")
        report["contact_source_snapshots"] = []
        for name, module in (("contact-helper-source.py", contact), ("contact-menu-helper-source.py", contact.menu)):
            path = output/name
            path.write_bytes(Path(module.__file__).read_bytes())
            report["contact_source_snapshots"].append(dict(path=str(path), sha256=preparation.sha256(path)))
    if native_quit is not None:
        report.update(native_quit_scenario=args.native_quit_scenario,native_quit_original=quit_original,
                      artwork_review="pending",ledger_status="unverified")
        path=output/"native-quit-helper-source.py";path.write_bytes(Path(native_quit.__file__).read_bytes())
        report["native_quit_source_snapshot"]=dict(path=str(path),sha256=preparation.sha256(path))
        report["checks"]["native_quit_automated_case_completed"]=False
    if reentry_pair is not None:
        report.update(native_reentry_route="new_game",native_reentry_original=reentry_original,
            native_reentry_disc_binding=reentry_binding,native_reentry_prepared=[],artwork_review="pending",ledger_status="unverified")
        report["checks"]["native_reentry_original_source_bound"]=True
        report["checks"]["native_reentry_automated_case_completed"]=False
        report["native_reentry_source_snapshots"]=[]
        for module in (reentry_pair,reentry_pair.helper,reentry_pair.helper.menu,reentry_pair.host):
            path=output/(Path(module.__file__).stem+"-executed-source.py");path.write_bytes(Path(module.__file__).read_bytes())
            report["native_reentry_source_snapshots"].append(dict(path=str(path),sha256=preparation.sha256(path)))
    if audio_pair is not None:
        report.update(jump_audio_source=audio_source,jump_audio_prepared=[],ledger_status="unverified",
            r4="unverified",r12="unverified",audible_output="not_tested",jump_audio_source_snapshots=[])
        report["checks"]["jump_audio_original_source_bound"]=True
        key='hud_presentation_both_peers_completed' if hud_pair is not None else 'state_policy_both_peers_completed' if state_policy is not None else 'jump_audio_both_peers_completed'
        report['checks'][key]=False
        for module in (audio_pair,audio_pair.audio,audio_pair.ownership,audio_pair.ownership.host,source_validation):
            path=output/(Path(module.__file__).stem+"-executed-source.py");path.write_bytes(Path(module.__file__).read_bytes())
            report["jump_audio_source_snapshots"].append(dict(path=str(path),sha256=preparation.sha256(path)))
    if state_policy is not None:
        report["kind"]="owned_loopback_delay_state_policy"
        for module in (state_policy,state_policy.keyboard):
            (output/(Path(module.__file__).stem+"-executed-source.py")).write_bytes(Path(module.__file__).read_bytes())
        report["limits"].append("State policy uses enabled rewind preferences; no ordered recording or audio qualification is claimed")
    if hud_pair is not None:
        report['kind']='owned_loopback_delay_hud_presentation'
        for module in (hud_pair,hud_pair.hud,hud_pair.hud.resources,hud_pair.hud.state,hud_pair.hud.mapped,hud_pair.hud.mapped.keyboard_input):
            (output/(Path(module.__file__).stem+'-executed-source.py')).write_bytes(Path(module.__file__).read_bytes())
    handles, processes, clients, reservations = [], [], [], []
    executor = ThreadPoolExecutor(max_workers=2)
    runtime_ready = False

    def both(function):
        jobs = [executor.submit(function, seat) for seat in range(2)]
        values, errors = [], []
        for job in jobs:
            try:
                values.append(job.result())
            except Exception as error:
                values.append(None)
                errors.append(error)
        if errors:
            raise errors[0]
        return values

    def require(condition, message):
        if not condition:
            raise paired.ValidationFailure(message)

    def host_profile_checkpoint(*, final):
        expected = [peer["preparation"]["exe_sha256"] for peer in report["peers"]]
        require(len(expected) == 2 and all(value == candidate_sha for value in expected),
                "A staged host-profile executable differs from the candidate")
        evidence = host_profiles.verify_host_profile_pair([
            (Path(peer["directory"])/"logs/stderr.log").read_text(encoding="utf-8", errors="replace")
            for peer in report["peers"]], expected,
            args.expected_host_profile, args.expected_host_profile_revision, final=final)
        # Hash images only after complete records, not on each pending-log poll.
        require(all(preparation.sha256(Path(peer["directory"])/"mmx6-runtime.exe") == expected[seat]
                    for seat, peer in enumerate(report["peers"])),
                "A staged host-profile executable changed after staging")
        return evidence

    def network():
        status = both(lambda seat: clients[seat].request("netplay_status"))
        paired.validate_status(status)
        report["last_network_status"] = status
        return status

    def rows():
        observed = both(lambda seat: debug.observe(clients[seat]))
        require(all(row.mailbox == 0 for row in observed), "Raw P2 mailbox became armed")
        require(all(row.ready == row.enrolled == 1 and row.failed == 0 for row in observed),
                "A co-op plugin left its ready/enrolled state")
        report["observations"].append([row.json() for row in observed])
        return observed

    def advance(count, timeout=20):
        start = rows()
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            current = rows()
            if all(((row.native_timer-old.native_timer) & 0xFFFFFFFF) >= count
                   for row, old in zip(current, start)):
                network()
                return current
            time.sleep(.025)
        raise paired.ValidationFailure("Native timers did not consume the input window")

    def matched(label, seconds=4):
        if getattr(args, "require_state_crc", False):
            paired.require_framework_digest(rows())
        first_simulation_tick = max(row["tick"] for row in network())
        deadline, history, common = time.monotonic()+seconds, [{}, {}], set()
        matches = []
        while time.monotonic() < deadline:
            observed = rows()
            for seat, row in enumerate(observed):
                history[seat][row.tick] = row
                if len(history[seat]) > 256:
                    del history[seat][next(iter(history[seat]))]
            for tick in sorted((set(history[0]) & set(history[1])) - common):
                matches.append(paired.pair_match(history[0][tick], history[1][tick]))
                common.add(tick)
            time.sleep(.015)
        if len(matches) < 2:
            raise paired.FailedSetup(f"{label}: insufficient common diagnostic publication counts")
        report["matched_host_observations"].append(dict(label=label, matches=matches))
        status = network()
        if getattr(args, "require_state_crc", False):
            digests = [state_crc.parse_state_crc(
                (output/f"peer-{seat}/logs/stderr.log").read_text(errors="replace"))
                for seat in range(2)]
            try:
                samples = state_crc.resolved_state_crc(
                    *digests, min(row["resolved_through"] for row in status),
                    after=first_simulation_tick)
            except state_crc.MissingStateCrc as error:
                raise paired.FailedSetup(f"{label}: {error}") from error
            report["resolved_state_crc"].append(dict(label=label, samples=samples,
                resolved_through=[row["resolved_through"] for row in status]))

    def wait_observed(predicate, message, seconds=30):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            current = rows()
            network()
            if all(predicate(row) for row in current):
                return current
            time.sleep(.05)
        raise paired.ValidationFailure(message)

    def transport_window(count, seconds=20):
        # Paused gameplay stops the native timer. Use resolved transport ticks
        # here, without equating them with diagnostic publication counts.
        start = network()
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            status = network()
            if all(row["resolved_through"] >= old["tick"]+count
                   for row, old in zip(status, start)):
                return rows()
            time.sleep(.05)
        raise paired.ValidationFailure("Transport did not resolve the held-input window")

    try:
        ports = [args.host_port, args.guest_port, args.host_udp, args.guest_udp]
        if len(set(ports)) != 4 or any(not 1 <= port <= 65535 for port in ports):
            raise ValueError("Require four distinct ports in 1..65535")
        for port, kind in zip(ports, (socket.SOCK_STREAM, socket.SOCK_STREAM,
                                     socket.SOCK_DGRAM, socket.SOCK_DGRAM)):
            reservation = socket.socket(socket.AF_INET, kind)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            reservation.bind(("127.0.0.1", port))
            reservations.append(reservation)
        for seat in range(2):
            directory = output/f"peer-{seat}"
            receipt = preparation.prepare(args.build, staging_source, directory, args.disc,
                                          automated=True)
            # The executable-owned profile supplies co-op. Preserve the normal
            # default-on loader unless the caller explicitly asks to bypass it
            # for diagnosis; such a run cannot qualify default netplay.
            (directory/"mods/state.toml").write_text(f'''format_version = 2
[[package]]
id = "mmx6.local-coop"
version = "0.0.1"
[[feature]]
package_id = "mmx6.local-coop"
id = "prototype"
enabled = false
[[package]]
id = "mmx6.enhancement.seamless-loading"
version = "0.1.0"
[[feature]]
package_id = "mmx6.enhancement.seamless-loading"
id = "seamless-loading"
enabled = {str(not args.native_loader_diagnostic).lower()}
''', encoding="utf-8")
            require(receipt["source_card"] is None, "Unexpected source card")
            if hud_pair is not None and args.hud_layout=='side_by_side':
                path=directory/'mods/state.toml';text=path.read_text(encoding='utf-8')
                old='id = "prototype"\nenabled = false\n'
                require(text.count(old)==1,'Unexpected fresh co-op HUD preference')
                path.write_text(text.replace(old,old+'[feature.values]\nhud_layout = "side_by_side"\n'),encoding='utf-8')
            require(receipt["exe_sha256"] == report["candidate_exe_sha256"],
                    "Build changed during paired staging")
            if reentry_pair is not None:
                report["native_reentry_prepared"].append(reentry_pair.prepare_profile(directory,args.disc,args.original_disc))
            if audio_pair is not None:
                prepared=audio_pair.ownership.prepare_profile(directory,args.disc,args.original_disc)
                if state_policy is not None:
                    prepared=state_policy.enable_rewind(directory,prepared)
                report["jump_audio_prepared"].append(prepared)
                audio_pair.sources.verify_prepared_originals(directory,args.original_exe,args.disc,
                    expected_rewind=state_policy is not None)
            environment = baseline.candidate_environment(directory, receipt)
            # Discard inherited developer/session controls, then reapply only
            # the validated private paths and fixed LAN/delay policies.
            environment = {key: value for key, value in environment.items()
                           if not key.upper().startswith(("PSX_", "RNET_"))}
            environment.update(json.loads((directory/"environment.json").read_text()))
            environment.update(PSX_NET_TRANSPORT="lan", PSX_NET_MODE="delay",
                               SDL_AUDIODRIVER="dummy", PSX_NETPLAY="1")
            argv = [str(directory/"mmx6-runtime.exe"), "--game", str(directory/"game.toml"),
                    "--bios", str(directory/"bios/openbios.bin"), "--disc", str(args.disc.resolve()),
                    "--memcard-dir", str(directory/"saves"), "--no-launcher", "--hidden-window",
                    "--renderer", "opengl", "--netplay", "--net-slot", str(seat),
                    "--net-input-player", "0", "--net-bind", f"127.0.0.1:{ports[2+seat]}",
                    "--net-peer", f"127.0.0.1:{ports[3-seat]}", "--net-delay", "3",
                    "--net-session-id", str(args.session), "--debug-port", str(ports[seat])]
            report["peers"].append(dict(seat=seat, directory=str(directory), argv=argv,
                                        preparation=receipt, runtime_environment={key: environment[key]
                                        for key in ("TEMP", "TMP", "LOCALAPPDATA", "APPDATA",
                                        "PSX_RESIDENT_CACHE", "PSX_OVERLAY_CACHE_DIR",
                                        "PSX_OVERLAY_AUTOCOMPILE_OFF", "PSX_NET_TRANSPORT",
                                        "PSX_NET_MODE", "SDL_AUDIODRIVER")}))
            report["peers"][-1]["network_selection_sha256"] = preparation.sha256(directory/"mods/state.toml")
        if host_profiles is not None:
            report["host_profile_build_manifest"] = host_profiles.validate_build_manifest(
                args.build, [Path(peer["directory"])/"mmx6-runtime.exe" for peer in report["peers"]],
                evidence_directory=output/"logs")
            report["checks"]["declared_build_manifest_bound_to_staged_images"] = True
        if native_quit is not None:
            report["native_quit_same_machine_plan"]=same_machine_plan(report["peers"])
        if reentry_pair is not None:
            report["native_reentry_same_machine_plan"]=same_machine_plan(report["peers"])
            report["native_reentry_declared_sources"]=source_validation.validate_sources(
                args.build,staging_source,report["host_profile_build_manifest"])
            report["checks"]["native_reentry_declared_sources_match"]=True
            require(reentry_pair.bind_original_disc(args.disc,args.original_disc)==reentry_binding,
                    "Original CUE/raw source changed during paired preparation")
        if audio_pair is not None:
            report["jump_audio_same_machine_plan"]=same_machine_plan(report["peers"])
            require(report["host_profile_build_manifest"]["declared_sha256"]==args.expected_manifest_sha256,
                    "Audio compiled manifest differs from the explicitly expected SHA256")
            report["jump_audio_declared_sources"]=source_validation.validate_sources(
                args.build,staging_source,report["host_profile_build_manifest"])
            report["checks"]["jump_audio_declared_sources_match"]=True
            require(audio_pair.ownership.bind_original_disc(args.disc,args.original_disc)==audio_source["disc"],
                    "Original audio CUE/raw source changed during paired preparation")
        # Reservations establish availability; owned-listener checks close the
        # release-to-launch race before every debug command, including quit.
        for reservation in reservations:
            reservation.close()
        reservations.clear()
        for seat, peer in enumerate(report["peers"]):
            directory = Path(peer["directory"])
            stdout = (directory/"logs/stdout.log").open("w", encoding="utf-8")
            stderr = (directory/"logs/stderr.log").open("w", encoding="utf-8")
            handles.extend((stdout, stderr))
            environment = baseline.candidate_environment(directory, peer["preparation"])
            environment = {key: value for key, value in environment.items()
                           if not key.upper().startswith(("PSX_", "RNET_"))}
            environment.update(json.loads((directory/"environment.json").read_text()))
            environment.update(PSX_NET_TRANSPORT="lan", PSX_NET_MODE="delay",
                               SDL_AUDIODRIVER="dummy", PSX_NETPLAY="1")
            process = subprocess.Popen(peer["argv"], cwd=directory, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            processes.append(process)
            peer["owned_pid"] = process.pid

            class OwnedClient(debug.DebugClient):
                def __init__(self, port, owner):
                    super().__init__(port, timeout=3)
                    self.owner = owner
                    self.reentry_route = None

                def request(self, command, **fields):
                    if self.owner.poll() is not None or not baseline.owns_listener(self.port, self.owner.pid):
                        raise debug.DebugError("Owned process does not own this debug listener")
                    return super().request(command, **fields)

                def host_input(self, pressed=0):
                    if self.reentry_route is None:
                        if reentry_pair is not None or audio_pair is not None:raise debug.DebugError("Owned published host route is unavailable")
                        return super().host_input(pressed)
                    return self.reentry_route.set(0,pressed)

                def release(self):
                    if self.reentry_route is None:
                        if reentry_pair is not None or audio_pair is not None:return self.request("clear_input",layer="host",port=1)
                        return super().release()
                    return self.reentry_route.clear()

            clients.append(OwnedClient(ports[seat], process))
        if reentry_pair is not None:
            reentry_pair.install_routes(clients,processes,ports[:2],report,output,handles)
        if audio_pair is not None:
            audio_pair.install_routes(clients,processes,ports[:2],report,output,handles)
        print(json.dumps(dict(event="launched_owned_pair", pids=[p.pid for p in processes],
                              output=str(output))), flush=True)
        deadline, next_input, release_input, step = time.monotonic()+args.timeout, 0., 0., 0
        neutralized = False
        admission_start = None
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in processes):
                raise debug.DebugError("An owned peer exited during native boot")
            try:
                if not all(baseline.owns_listener(ports[seat], process.pid)
                           for seat, process in enumerate(processes)):
                    time.sleep(.1)
                    continue
                if host_profiles is not None and "host_profile_startup" not in report:
                    try:
                        report["host_profile_startup"] = host_profile_checkpoint(final=False)
                    except host_profiles.MissingHostProfile:
                        time.sleep(.05)
                        continue
                    report["checks"]["host_profile_settled_before_guest"] = True
                net = network()
                if admission_only:
                    if admission_start is None:
                        admission_start = [row["tick"] for row in net]
                    if all(row["tick"] >= start+60 and start+30 <= row["resolved_through"] <= row["tick"]
                           for row, start in zip(net, admission_start)):
                        loader_markers = [(output/f"peer-{seat}/logs/stdout.log").read_text(errors="replace")
                                          for seat in range(2)]
                        if not all("title netplay loading = resident assets" in text for text in loader_markers):
                            time.sleep(0.05)
                            continue  # Allow buffered startup logs within the setup deadline.
                        report["checks"]["default_resident_loader_committed"] = True
                        report["checks"]["active_delay_session_advances"] = True
                        report["default_launch_qualified"] = not args.native_loader_diagnostic
                        report["status"] = "passed"
                        report["limits"].append("Admission only: no native gameplay, movement or host-FNV qualification")
                        return report
                    time.sleep(0.05)
                    continue
                pads = both(lambda seat: clients[seat].request("pad_status"))
                if not all(pad.get("slot0", {}).get("connected") for pad in pads):
                    raise paired.FailedSetup("A private virtual P1 keyboard pad is disconnected")
                if not neutralized:
                    both(lambda seat: clients[seat].host_input(0))
                    neutralized = True
                modes = both(lambda seat: list(clients[seat].read(0x800CCED0, 2)))
                actions = both(lambda seat: clients[seat].read(0x800970A5, 1)[0])
                report["setup"].append(dict(modes=modes, actions=actions,
                                           network_ticks=[row["tick"] for row in net]))
                if len(report["setup"]) > 512:
                    del report["setup"][0]
                if all(mode[0] == 10 and action == 2 for mode, action in zip(modes, actions)):
                    observed = both(lambda seat: debug.observe(clients[seat]))
                    if all(paired.native_ready(row) for row in observed):
                        break
                now = time.monotonic()
                if release_input and now >= release_input:
                    clients[0].host_input(0)
                    release_input = 0.
                if now >= next_input and not release_input:
                    button = 0x0008 if modes[0][0] != 10 and step % 3 == 0 else 0x4000
                    clients[0].host_input(button)
                    release_input, next_input = time.monotonic()+.20, time.monotonic()+.9
                    step += 1
                    if step % 10 == 1:
                        print(json.dumps(dict(event="native_boot", modes=modes, actions=actions,
                                              network_ticks=[row["tick"] for row in net])), flush=True)
            except (debug.DebugError, OSError) as error:
                report["latest_setup_error"] = str(error)
            time.sleep(.10)
        else:
            raise paired.FailedSetup("Native boot did not reach two idle live heroes within the setup deadline")
        both(lambda seat: clients[seat].host_input(0))
        runtime_ready = True
        report["status"] = "failed"
        start = advance(10)
        report["initial"] = [row.json() for row in start]
        matched("initial idle")
        before = rows()
        clients[1].host_input(0x20)
        try:
            advance(12)
        finally:
            clients[1].host_input(0)
        moved = advance(8)
        report["checks"]["p2_right_reaches_both_peers"] = all(
            after.players[1].x_raw > old.players[1].x_raw for old, after in zip(before, moved))
        report["checks"]["p2_right_preserves_p1_x"] = all(
            after.players[0].x_raw == old.players[0].x_raw for old, after in zip(before, moved))
        matched("P2 right then release")
        before = rows()
        clients[0].host_input(0x4000)
        try:
            jumped = advance(6)
        finally:
            clients[0].host_input(0)
        report["checks"]["p1_jump_reaches_both_peers"] = all(
            after.players[0].y_raw < old.players[0].y_raw for old, after in zip(before, jumped))
        report["checks"]["p1_jump_preserves_p2_y"] = all(
            after.players[1].y_raw == old.players[1].y_raw for old, after in zip(before, jumped))
        settled = advance(45)
        report["checks"]["both_alive_healthy"] = all(row.lifecycle == (0, 0) and
            all(player.hp == 32 for player in row.players) for row in settled)
        report["checks"]["mailbox_unused"] = all(row.mailbox == 0 for row in settled)
        matched("P1 jump then settle")
        if state_policy is not None:
            loader_logs=[(output/f"peer-{seat}/logs/stdout.log").read_text(errors="replace") for seat in range(2)]
            require(all("title netplay loading = resident assets" in text for text in loader_logs),
                    "State policy default resident loader did not commit on both peers")
            report["checks"]["default_resident_loader_committed"]=True
            state_policy.exercise(dict(clients=clients,report=report,output=output,
                transport_window=transport_window,matched=matched,network=network),expected_sha=args.expected_exe_sha256)
        if hud_pair is not None:
            loader_logs=[(output/f'peer-{seat}/logs/stdout.log').read_text(errors='replace') for seat in range(2)]
            require(all('title netplay loading = resident assets' in text for text in loader_logs),
                    'HUD default resident loader did not commit on both peers')
            report['checks']['default_resident_loader_committed']=True
            sources=dict(zero_overlay=hud_pair.hud.resources.zero_contact.load_zero_overlay(args.original_disc),
                target=hud_pair.hud.resources.native_contact.load_source(args.original_exe,args.original_disc,0))
            hud_pair.exercise(dict(clients=clients,both=both,report=report,output=output,network=network,
                transport_window=transport_window,matched=matched,advance=advance),
                expected_sha=args.expected_exe_sha256,layout=args.hud_layout,source=sources)
        if audio_pair is not None and state_policy is None and hud_pair is None:
            loader_logs=[(output/f"peer-{seat}/logs/stdout.log").read_text(errors="replace") for seat in range(2)]
            require(all("title netplay loading = resident assets" in text for text in loader_logs),
                    "Audio default resident loader did not commit on both peers")
            report["checks"]["default_resident_loader_committed"]=True
            case=audio_pair.exercise(dict(clients=clients,both=both,report=report,output=output,
                network=network,native_advance=lambda frames,label:advance(frames)),
                expected_sha=args.expected_exe_sha256,source=audio_source,
                first_seat=args.audio_first_seat if args.audio_first_seat is not None else 0,
                max_attempts=args.audio_max_attempts if args.audio_max_attempts is not None else 32)
            matched("paired ground-jump audio then settle")
            report["checks"]["jump_audio_resolved_crc_after_case"]=True
            report["jump_audio_automated_status"]=case["status"]
            require(case["status"] in (audio_pair.SUCCESS,audio_pair.INCONCLUSIVE),
                    "Paired jump audio did not complete both independent comparisons: "+case["status"])
            report["limits"].append("The ground-jump phase covers one order only; no full R4/R12, PCM, audible, music or cross-host pass")
            if getattr(args,"body_audio_smoke",False):
                report["checks"]["body_audio_resolved_crc_after_case"]=False
                body_case=audio_pair.exercise_body(dict(clients=clients,both=both,report=report,output=output,
                    network=network,native_advance=lambda frames,label:advance(frames)),
                    expected_sha=args.expected_exe_sha256,source=audio_source,
                    original_exe=args.original_exe,original_disc=args.original_disc)
                report["body_audio_automated_status"]=body_case["status"]
                require(body_case["status"] in (audio_pair.BODY_SUCCESS,audio_pair.BODY_PARTIAL),
                    "Paired body audio did not complete both independent comparisons: "+body_case["status"])
                matched("paired saber hurt death audio then settle")
                report["checks"]["body_audio_resolved_crc_after_case"]=True
                report["limits"].append("Paired body samples/contact death are separate bounded observations; pending inactive STOP7 never becomes a pass")
            if getattr(args,'primary_audio_smoke',False):
                report['checks']['primary_audio_resolved_crc_after_case']=False
                primary_case=audio_pair.exercise_primary(dict(clients=clients,both=both,report=report,
                    output=output,network=network,native_advance=lambda frames,label:advance(frames)),
                    expected_sha=args.expected_exe_sha256,source=audio_source,
                    original_exe=args.original_exe,original_disc=args.original_disc)
                report['primary_audio_automated_status']=primary_case['status']
                require(primary_case['status'] in ('primary_audio_observations_complete_outcomes_unverified',
                    'primary_audio_observations_partial_missing_overlap'),
                    'Paired primary audio did not complete independent source/lifecycle comparisons: '+primary_case['status'])
                matched('paired X hurt death, Zero survival and vocal overlap')
                report['checks']['primary_audio_resolved_crc_after_case']=True
                report['limits'].append('Primary X audio and observed one-direction vocal overlaps only; no full R4/R12, active STOP7 or cross-host pass')
        if reentry_pair is not None:
            loader_logs=[(output/f"peer-{seat}/logs/stdout.log").read_text(errors="replace") for seat in range(2)]
            require(all("title netplay loading = resident assets" in text for text in loader_logs),
                    "Native reentry default resident loader did not commit on both peers")
            report["checks"]["default_resident_loader_committed"]=True
            reentry_pair.exercise(dict(clients=clients,both=both,debug=debug,report=report,output=output,
                network=network,transport_window=transport_window,matched=matched,
                native_advance=lambda frames,label:advance(frames)),expected_sha=args.expected_exe_sha256,
                original_disc=args.original_disc,plan=report["native_reentry_same_machine_plan"])
            report["limits"].append("New Game defaults only; no acquired-current-data/card-load/Continue/opposite-roster/cross-host pass")
        if native_quit is not None:
            # No native-world-timer wait inside a pause: the shared accepted
            # host adapter uses resolved transport, with neutral in finally.
            loader_logs=[(output/f"peer-{seat}/logs/stdout.log").read_text(errors="replace") for seat in range(2)]
            require(all("title netplay loading = resident assets" in text for text in loader_logs),
                    "Native Quit default resident loader did not commit on both peers")
            report["checks"]["default_resident_loader_committed"]=True
            before_cards=[{p.name:preparation.sha256(p) for p in (output/f"peer-{seat}/saves").glob("*.mcd")} for seat in range(2)]
            report["native_quit_private_cards_before"]=before_cards
            quit_error=None
            try:
                exercise_native_quit_pair(dict(clients=clients,both=both,debug=debug,report=report,output=output,
                    network=network,transport_window=transport_window,matched=matched,
                    native_advance=lambda frames,label:advance(frames)),native_quit=native_quit,
                    published_input=published_input,original_exe=args.original_exe,expected_sha=args.expected_exe_sha256,
                    scenario=args.native_quit_scenario)
            except BaseException as error:
                quit_error=error
                raise
            finally:
                try:
                    after_cards=[{p.name:preparation.sha256(p) for p in (output/f"peer-{seat}/saves").glob("*.mcd")} for seat in range(2)]
                    report["native_quit_private_cards_after"]=after_cards
                    report["checks"]["native_quit_private_cards_unchanged"]=before_cards==after_cards
                except OSError as error:
                    report["native_quit_private_card_error"]=str(error)
                    report["checks"]["native_quit_private_cards_unchanged"]=False
                    if quit_error is None:raise
            require(report["checks"]["native_quit_automated_case_completed"],"Native Quit bounded case failed")
            require(report["checks"]["native_quit_private_cards_unchanged"],"Native Quit changed a private native card")
            report["limits"].append("Native Quit pages/refusal/cancel only; artwork and full final Quit/current-data reentry remain unverified")
        if personal_menu is not None:
            # Start can freeze the world during the hold itself. Measure every
            # accepted input interval using transport, including the neutral
            # release crossing delay3; native_advance remains a world-timer wait.
            def menu_hold(seat, bits, frames, label):
                try:
                    clients[seat].host_input(bits)
                    transport_window(frames)
                finally:
                    clients[seat].host_input(0)
                transport_window(5)

            (output/"personal-menu").mkdir()
            # Native 80033214/800337EC: pristine Zero uses Down 0->0x0D,
            # Up 0x0D->0. Right scans only unavailable tanks in this inventory.
            # See docs/COOP_PERSONAL_MENU_CURSOR_AUDIT.{md,json}.
            case = personal_menu.personal_menu_smoke(dict(mode="netplay", input_path="published_host",
                clients=clients, both=both, debug=debug, report=report, output=output,
                hold=menu_hold, native_advance=lambda frames, label: advance(frames),
                transport_window=transport_window, network=network), owner=1,
                cursor_buttons=(0x40, 0x10))
            report["personal_menu_automated_status"] = case["status"]
            report["personal_menu_artwork_review"] = case["artwork_review"]
            report["checks"]["p2_personal_menu_automated_checks"] = bool(case["checks"]) and all(
                case["checks"].values()) and case["status"] == "automated_checks_passed_artwork_review_pending"
            require(report["checks"]["p2_personal_menu_automated_checks"],
                    "P2 personal-menu automated checks did not complete")
            matched("P2 personal menu, composed captures and resumed native controls")
            report["limits"].append(
                "P2 personal-menu automated checks retain composed artwork review pending; no R8 ledger pass")
        if private_pause is not None:
            input_adapter = published_input.PublishedHeldInput(clients, network, transport_window, report)
            case = private_pause.private_pause_smoke(dict(mode="netplay", input_path="published_host",
                clients=clients, both=both, debug=debug, report=report, output=output,
                effects=effects, hold=input_adapter.hold, hold_observed=input_adapter.hold_observed,
                native_advance=lambda frames,label:advance(frames), transport_window=transport_window,
                network=network, matched=matched, candidate_exe_sha256=candidate_sha),
                expected_exe_sha256=args.expected_exe_sha256)
            report["private_pause_automated_status"] = case["status"]
            report["checks"]["private_effect_pause_automated_checks"] = (
                bool(case.get("checks")) and all(case["checks"].values()) and
                case["status"] == "automated_private_pause_checks_passed_artwork_pending")
            require(report["checks"]["private_effect_pause_automated_checks"],
                    "Native P1 private-effect pause case did not complete")
            report["limits"].append("Private-effect pause case retains composed artwork review pending; no R9 ledger pass")
        if contact is not None:
            # Only the owning peer's published host sampler feeds transport.
            # Paused menu spacing uses resolved transport ticks, never the
            # deliberately frozen native world timer. Keep original errors if
            # neutral cleanup also fails after an owned endpoint disappears.
            def contact_hold(seat, bits, frames, label):
                failure = None
                try:
                    clients[seat].host_input(bits)
                    transport_window(frames)
                except BaseException as error:
                    failure = error
                    raise
                finally:
                    try:
                        clients[seat].host_input(0)
                    except Exception as error:
                        report.setdefault("contact_input_cleanup_errors", []).append(dict(
                            label=label, seat=seat, error=str(error),
                            original_error=str(failure) if failure else None))
                        if failure is None:
                            raise
                transport_window(5)

            case = contact.contact_pause_contact(dict(mode="netplay", input_path="published_host",
                clients=clients, both=both, debug=debug, report=report, output=output,
                hold=contact_hold, native_advance=lambda frames, label: advance(frames),
                transport_window=transport_window, network=network, matched=matched,
                candidate_exe_sha256=candidate_sha, zero_overlay=zero_overlay,
                rpc=lambda peer, command, **fields: clients[peer].request(command, **fields)),
                expected_exe_sha256=args.expected_exe_sha256)
            report["contact_automated_status"] = case["status"]
            report["contact_artwork_review"] = case["artwork_review"]
            report["checks"]["r2_contact_pause_contact_automated_checks"] = bool(case["checks"]) and all(
                case["checks"].values()) and case["status"] == "automated_contact_checks_passed_artwork_review_pending"
            require(report["checks"]["r2_contact_pause_contact_automated_checks"],
                    "R2 contact/menu/contact automated checks did not complete")
            report["limits"].append(
                "R2 source-derived contact route retains composed artwork review pending; no R2 ledger pass")
        if getattr(args, "enemy_targeting_smoke", False):
            enemy_targeting_smoke(dict(enemy=enemy, clients=clients, both=both, require=require,
                network=network, report=report, matched=matched, wait_observed=wait_observed,
                transport_window=transport_window, output=output, debug=debug))
        if getattr(args, "lifecycle_smoke", False):
            saved = rows()
            clients[1].host_input(1)  # Original Select hold, never a fixture.
            absent = wait_observed(lambda row: row.lifecycle == (0, 2),
                                   "P2 did not complete native voluntary departure")
            held = transport_window(20)
            require(all(row.lifecycle == (0, 2) for row in held),
                    "Held departure Select immediately rejoined")
            clients[1].host_input(0)
            transport_window(10)
            clients[0].host_input(8)
            wait_observed(lambda row: row.native_phase == 2 and row.pause_owner == 1,
                          "Primary native pause did not open")
            clients[0].host_input(0)
            transport_window(10)
            # A blocked press must be consumed as history, not replayed as a
            # fresh rejoin edge when the primary resumes its own native menu.
            clients[1].host_input(1)
            transport_window(12)
            clients[0].host_input(8)
            wait_observed(lambda row: row.native_phase == 0,
                          "Primary native menu did not resume")
            clients[0].host_input(0)
            resumed = transport_window(25)
            report["checks"]["blocked_select_does_not_rejoin"] = all(
                row.lifecycle == (0, 2) for row in resumed)
            require(report["checks"]["blocked_select_does_not_rejoin"],
                    "Select held from native pause fabricated a rejoin edge")
            clients[1].host_input(0)
            transport_window(10)
            clients[1].host_input(1)
            wait_observed(lambda row: row.lifecycle[1] in (3, 0),
                          "Fresh Select did not request native rejoin")
            clients[1].host_input(0)
            joined = wait_observed(lambda row: paired.native_ready(row),
                                   "P2 did not finish native rejoin")
            report["checks"]["leave_rejoin_retains_resources"] = all(
                (old.players[1].hp, old.players[1].ammo, old.players[1].weapon) ==
                (new.players[1].hp, new.players[1].ammo, new.players[1].weapon)
                for old, new in zip(saved, joined))
            report["checks"]["held_departure_stays_absent"] = all(
                row.lifecycle == (0, 2) for row in absent+held)
            matched("P2 leave, blocked Select in P1 menu, fresh rejoin")
            report["limits"].append(
                "Lifecycle smoke uses healthy intro resources; spent ammo, death, unsafe landing and campaign retry remain unverified")
        report["captures"] = []
        for seat, client in enumerate(clients):
            path = output/f"peer-{seat}/logs/intro.png"
            response = client.request("screenshot", path=str(path))
            require(path.is_file() and path.stat().st_size > 0, "Render screenshot was not written")
            report["captures"].append(dict(seat=seat, surface="game_render_buffer",
                path=str(path), sha256=preparation.sha256(path), response=response))
            composed = debug.capture_present(client, output/f"peer-{seat}/logs/intro-present.png")
            report["captures"].append(dict(seat=seat, **composed))
        report["final"] = [row.json() for row in rows()]
        network()
        report["status"] = "passed" if all(report["checks"].values()) else "failed"
        if audio_pair is not None and report.get("jump_audio_automated_status")==audio_pair.INCONCLUSIVE:
            report["status"]=audio_pair.INCONCLUSIVE
        if audio_pair is not None and report["status"]=="passed" and report.get("body_audio_automated_status")==audio_pair.BODY_PARTIAL:
            report["status"]=audio_pair.BODY_PARTIAL
        if audio_pair is not None and report['status']=='passed' and report.get('primary_audio_automated_status')=='primary_audio_observations_partial_missing_overlap':
            report['status']='primary_audio_observations_partial_missing_overlap'
        report["default_intro_qualified"] = report["status"] == "passed" and not args.native_loader_diagnostic
    except Exception as error:
        report.update(error=str(error), traceback=traceback.format_exc())
        if not runtime_ready:
            report["status"] = "failed_setup"
        for seat, client in enumerate(clients):
            diagnostics = {}
            for command in ("netplay_status", "pad_status", "gpu_state"):
                try:
                    diagnostics[command] = client.request(command)
                except Exception as diagnostic_error:
                    diagnostics[command] = dict(error=str(diagnostic_error))
            try:
                path = output/f"peer-{seat}/logs/failure.png"
                diagnostics["screenshot"] = client.request("screenshot", path=str(path))
                if path.is_file():
                    diagnostics["screenshot_sha256"] = preparation.sha256(path)
            except Exception as diagnostic_error:
                diagnostics["screenshot_error"] = str(diagnostic_error)
            report["peers"][seat]["failure_diagnostics"] = diagnostics
    finally:
        for reservation in reservations:
            reservation.close()
        for seat, process in enumerate(processes):
            peer = report["peers"][seat]
            try:
                peer.update(baseline.stop_owned_runtime(process,
                    clear_inputs=(lambda: clients[seat].release(),),
                    request_quit=lambda: clients[seat].request("quit")))
            except Exception as error:
                if reentry_pair is None and audio_pair is None:raise
                peer.update(shutdown="owned_cleanup_error",cleanup_error=str(error))
            if peer["shutdown"] == "already_exited":
                if report["status"] == "passed":
                    report["status"] = "failed"
            try:
                peer["private_card_files"] = [dict(name=path.name, sha256=preparation.sha256(path))
                    for path in (Path(peer["directory"])/"saves").glob("*.mcd")]
            except OSError as error:
                if reentry_pair is None and audio_pair is None:raise
                peer["private_card_error"]=str(error)
        executor.shutdown(wait=True)
        for handle in handles:
            handle.close()
        if reentry_pair is not None:
            reentry_pair.finalize(report,output,runtime_ready=runtime_ready,owned_processes=len(processes))
        if audio_pair is not None:
            audio_pair.finalize(report,output,runtime_ready=runtime_ready,owned_processes=len(processes))
        if host_profiles is not None:
            # Read the complete owned logs after both writers stop. A later
            # duplicate/restart/malformed record must revoke an earlier pass.
            try:
                report["host_profile_final"] = host_profile_checkpoint(final=True)
                report["checks"]["host_profile_settled_before_guest"] = True
            except Exception as error:
                report["checks"]["host_profile_settled_before_guest"] = False
                report["status"] = "failed" if runtime_ready else "failed_setup"
                report["default_intro_qualified"] = report["default_launch_qualified"] = False
                prior = report.get("error", "")
                report["error"] = (prior + "; " if prior else "") + f"Host profile verification: {error}"
        (output/"qualification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-root", type=Path, required=True)
    parser.add_argument("--source",type=Path,
                        help="Game config staging source; defaults to --tools-root parent, independently of executing helper hashes")
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--host-port", type=int, default=24901)
    parser.add_argument("--guest-port", type=int, default=24902)
    parser.add_argument("--host-udp", type=int, default=29901)
    parser.add_argument("--guest-udp", type=int, default=29902)
    parser.add_argument("--session", type=int, default=20261023)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--native-loader-diagnostic", action="store_true",
                        help="Explicitly bypass default Seamless Loading; never qualifies defaults")
    parser.add_argument("--admission-only", action="store_true",
                        help="Qualify default loader admission and advancing delay transport only; no gameplay pass")
    parser.add_argument("--lifecycle-smoke", action="store_true",
                        help="Also exercise native P2 departure, blocked Select during P1 pause and fresh rejoin")
    parser.add_argument("--personal-menu-smoke", action="store_true",
                        help="Also check original published P2/Zero personal-menu ownership, controls and resources; composed artwork review remains pending")
    parser.add_argument("--private-pause-smoke", action="store_true",
                        help="Original published P1 pause while P2 native dash effects are retained; fresh exact image, host profile and resolved CRC required")
    parser.add_argument("--contact-pause-contact-smoke", action="store_true",
                        help="Original published P2 body contact before/after its own menu; exact frozen37 candidate, source BIN, host profile and resolved CRC required")
    parser.add_argument("--native-quit-scenario",choices=("guest_authority","p1_pages_cancel","p1_pages_cancel_live_effects"),
                        help="Separate fresh native Quit authority or primary pages/cancel case; exact image, original EXE, host profile and resolved CRC required")
    parser.add_argument("--original-exe",type=Path,help="Original SLUS_013.95 source for --native-quit-scenario or --jump-audio-smoke")
    parser.add_argument("--state-policy-smoke",action="store_true",
                        help="Verify keyboard/controller state and rewind refusal on both admitted peers with local rewind enabled")
    parser.add_argument('--hud-presentation-smoke',action='store_true',
                        help='Capture both menu owners and changed-HP HUD anchors at actual drawable aspects on two exact-image peers')
    parser.add_argument('--hud-layout',choices=('stacked','side_by_side'),
                        help='Presentation layout for a separate --hud-presentation-smoke pair; default stacked')
    parser.add_argument("--jump-audio-smoke",action="store_true",
                        help="Separate same-machine paired ground-jump private-bank/sample/DSP/lifetime observation; strict original/image/manifest/profile/CRC proof required")
    parser.add_argument("--body-audio-smoke",action="store_true",
                        help="After paired ground jumps, independently check saber/hurt/death and eight ordinary contacts on both peers; requires --jump-audio-smoke")
    parser.add_argument("--audio-first-seat",type=int,choices=(0,1),
                        help="First jumping logical seat (default0), only with --jump-audio-smoke")
    parser.add_argument("--audio-max-attempts",type=int,
                        help="Bounded native RNG attempts1..32 (default32), only with --jump-audio-smoke")
    parser.add_argument("--expected-manifest-sha256",
                        help="Exact compiled declared-manifest SHA256, required by --jump-audio-smoke")
    parser.add_argument('--primary-audio-smoke',action='store_true',
                        help='Observe X buster/hurt/death, surviving Zero and vocal overlap; requires full jump-audio startup gates and a separate fresh pair')
    parser.add_argument("--native-reentry",choices=("new_game",),
                        help="Separate same-machine original final Quit/New Game and fresh P2 menu recovery; strict image/source/profile/CRC proof required")
    parser.add_argument("--original-disc", type=Path,
                        help="Original raw BIN for R2, --native-reentry or --jump-audio-smoke, separate from runtime --disc CUE")
    parser.add_argument("--require-state-crc", action="store_true",
                        help="Require modern same-simulation-tick core/mod logs below both resolved watermarks; candidate must register complete host digest")
    parser.add_argument("--require-host-profile", action="store_true",
                        help="Require declared build evidence and one identical pre-guest x64 ENHANCED/FP2 host agreement per peer")
    parser.add_argument("--expected-host-profile",
                        help="Explicit expected settled profile name; required with --require-host-profile")
    parser.add_argument("--expected-host-profile-revision", type=int,
                        help="Explicit expected profile revision; required with --require-host-profile")
    parser.add_argument("--enemy-targeting-smoke", action="store_true",
                        help="Also exercise original P2 route, native enemy targeting/HP and matching composed pause captures")
    parser.add_argument("--expected-exe-sha256")
    return parser


def validate_options(parser, args):
    if getattr(args,'hud_presentation_smoke',False):
        if (args.jump_audio_smoke or args.state_policy_smoke or args.body_audio_smoke or args.primary_audio_smoke or
            args.native_quit_scenario or args.native_reentry or args.private_pause_smoke or args.contact_pause_contact_smoke or
            args.enemy_targeting_smoke or args.personal_menu_smoke or args.lifecycle_smoke or
            args.audio_first_seat is not None or args.audio_max_attempts is not None):
            parser.error('HUD presentation requires a separate fresh pair without other optional routes')
        args.hud_layout=args.hud_layout or 'stacked'
    elif getattr(args,'hud_layout',None) is not None:
        parser.error('--hud-layout requires --hud-presentation-smoke')
    if getattr(args,"state_policy_smoke",False):
        if (args.jump_audio_smoke or args.body_audio_smoke or args.primary_audio_smoke or
                args.native_quit_scenario or args.native_reentry or args.private_pause_smoke or
                args.contact_pause_contact_smoke or args.enemy_targeting_smoke or
                args.personal_menu_smoke or args.lifecycle_smoke or
                args.audio_first_seat is not None or args.audio_max_attempts is not None):
            parser.error("State policy requires its own fresh pair without other optional routes/audio options")
    if getattr(args,'primary_audio_smoke',False):
        if not args.jump_audio_smoke:
            parser.error('Primary audio requires full --jump-audio-smoke source/image/profile/CRC gates')
        if getattr(args,'body_audio_smoke',False):
            parser.error('Primary X and fatal Zero audio cases require separate fresh pairs')
    if getattr(args,"body_audio_smoke",False) and not args.jump_audio_smoke:
        parser.error("Paired body audio requires the full --jump-audio-smoke source/profile/CRC gates")
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required by the shared staging tools")
    if not 0 < args.timeout <= 600:
        parser.error("Setup timeout must be in (0,600]")
    if args.admission_only and args.native_loader_diagnostic:
        parser.error("Default-loader admission requires Seamless Loading enabled")
    if args.admission_only and args.lifecycle_smoke:
        parser.error("Lifecycle smoke requires the native gameplay checks")
    if args.admission_only and args.require_state_crc:
        parser.error("State CRC qualification requires native gameplay")
    if args.enemy_targeting_smoke and (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc):
        parser.error("Enemy targeting requires native gameplay, default loader and --require-state-crc")
    if args.personal_menu_smoke and (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc):
        parser.error("Personal menu requires native gameplay, default loader and --require-state-crc")
    if args.native_quit_scenario:
        if (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc or
                not args.require_host_profile or not args.expected_exe_sha256 or args.original_exe is None):
            parser.error("Native Quit requires original EXE, exact SHA, native gameplay, default loader, host profile and resolved CRC")
        if (args.private_pause_smoke or args.contact_pause_contact_smoke or args.enemy_targeting_smoke or
                args.personal_menu_smoke or args.lifecycle_smoke or args.native_reentry or args.jump_audio_smoke):
            parser.error("Each native Quit scenario requires a separate fresh pair without other optional routes")
    elif args.original_exe is not None and not args.jump_audio_smoke and not getattr(args,"state_policy_smoke",False) and not getattr(args,'hud_presentation_smoke',False):
        parser.error("--original-exe belongs to --native-quit-scenario or --jump-audio-smoke")
    if args.native_reentry:
        if (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc or
                not args.require_host_profile or not args.expected_exe_sha256 or args.original_disc is None or
                args.original_disc.suffix.lower()!=".bin" or args.disc.suffix.lower()!=".cue"):
            parser.error("Native reentry requires raw original BIN, runtime CUE, exact image, default loader, host profile and resolved CRC")
        if (args.private_pause_smoke or args.contact_pause_contact_smoke or args.enemy_targeting_smoke or
                args.personal_menu_smoke or args.lifecycle_smoke or args.native_quit_scenario or args.jump_audio_smoke):
            parser.error("Native reentry requires a separate fresh pair without other optional routes")
    if args.jump_audio_smoke or getattr(args,"state_policy_smoke",False) or getattr(args,'hud_presentation_smoke',False):
        if (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc or
                not args.require_host_profile or not args.expected_exe_sha256 or not args.expected_manifest_sha256 or
                args.original_exe is None or args.original_disc is None or args.original_disc.suffix.lower()!=".bin" or
                args.disc.suffix.lower()!=".cue"):
            parser.error("Paired audio requires original EXE/raw BIN/runtime CUE, exact image/manifest, default loader, host profile and resolved CRC")
        if (args.private_pause_smoke or args.contact_pause_contact_smoke or args.enemy_targeting_smoke or
                args.personal_menu_smoke or args.lifecycle_smoke or args.native_quit_scenario or args.native_reentry):
            parser.error("Paired ground-jump audio requires a separate fresh pair without other optional routes")
        if args.audio_max_attempts is not None and not 1<=args.audio_max_attempts<=32:
            parser.error("Audio attempts must be1..32")
        if re.fullmatch(r"[a-f0-9]{64}",args.expected_manifest_sha256) is None:
            parser.error("Expected manifest SHA256 must contain64 lowercase hex digits")
    elif args.audio_first_seat is not None or args.audio_max_attempts is not None or args.expected_manifest_sha256 is not None:
        parser.error("Audio order/attempts/manifest options require --jump-audio-smoke")
    if args.private_pause_smoke:
        if (args.admission_only or args.native_loader_diagnostic or not args.require_state_crc or
                not args.require_host_profile or not args.expected_exe_sha256):
            parser.error("Private-effect pause requires native gameplay, default loader, exact SHA, resolved CRC and host profile")
        if (args.contact_pause_contact_smoke or args.enemy_targeting_smoke or
                args.personal_menu_smoke or args.lifecycle_smoke):
            parser.error("Private-effect pause requires a separate fresh authored-input case")
    if args.contact_pause_contact_smoke:
        if args.admission_only or args.native_loader_diagnostic or not args.require_state_crc or not args.require_host_profile:
            parser.error("Contact/menu/contact requires native gameplay, default loader, --require-state-crc and --require-host-profile")
        if args.expected_exe_sha256 != CONTACT_EXE_SHA:
            parser.error("Contact/menu/contact requires the exact frozen37cdc487 --expected-exe-sha256")
        if args.original_disc is None or args.original_disc.suffix.lower() != ".bin":
            parser.error("Contact/menu/contact requires --original-disc with the original raw BIN")
        if args.enemy_targeting_smoke:
            parser.error("Contact/menu/contact and enemy-targeting require separate fresh authored-enemy cases")
    elif args.original_disc is not None and not args.native_reentry and not args.jump_audio_smoke and not getattr(args,"state_policy_smoke",False) and not getattr(args,'hud_presentation_smoke',False):
        parser.error("--original-disc belongs to --contact-pause-contact-smoke, --native-reentry or --jump-audio-smoke")
    if args.expected_exe_sha256 is not None and (len(args.expected_exe_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in args.expected_exe_sha256)):
        parser.error("Expected executable SHA256 must contain 64 lowercase hex digits")
    if args.require_host_profile:
        if (args.expected_host_profile is None or
                re.fullmatch(r"[a-z0-9_.-]{1,31}", args.expected_host_profile) is None or
                args.expected_host_profile_revision is None or
                not 1 <= args.expected_host_profile_revision <= 0xFFFFFFFF):
            parser.error("--require-host-profile requires an explicit bounded --expected-host-profile and --expected-host-profile-revision")
    elif args.expected_host_profile is not None or args.expected_host_profile_revision is not None:
        parser.error("Expected host profile options require --require-host-profile")


def main():
    parser = make_parser()
    args = parser.parse_args()
    validate_options(parser, args)
    report = run(args)
    print(json.dumps(dict(status=report["status"], checks=report["checks"], error=report.get("error"),
                          report=str(args.out/"qualification.json"))), flush=True)
    if report["status"]=="passed":return 0
    if report["status"] in ("paired_body_audio_observations_partial_stops_unverified",
        'primary_audio_observations_partial_missing_overlap'):return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
