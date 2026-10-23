"""Bounded paired ground-jump observations using two independent audio probes.

No launch, RAM/SIO/mailbox write, event reset, guest call or sound output. The
owner stages and validates both processes before installing published routes.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import mmx6_coop_jump_audio as audio
import mmx6_coop_native_reentry_pair as ownership
import qualify_mmx6_coop_jump_audio as sources


INCONCLUSIVE = "inconclusive_native_rng_no_shared_two_voice_window"
SUCCESS = "paired_jump_audio_observations_complete_outcomes_unverified"


def load_sources(original_exe, raw_disc, cue, contract_path):
    binding = ownership.bind_original_disc(cue, raw_disc)
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    audio.validate_contract(contract)
    if audio.build_contract(original_exe, raw_disc) != contract:
        raise ValueError("Original EXE/raw BIN does not reproduce the pinned jump-audio contract")
    banks = audio.build_private_bank_contract(raw_disc, contract)
    if ownership.bind_original_disc(cue, raw_disc) != binding:
        raise ValueError("Original source changed while deriving the audio contract")
    return dict(disc=binding, contract=contract, private_banks=banks,
        original_exe_sha256=ownership.preparation.sha256(Path(original_exe)))


def install_routes(clients, processes, ports, report, output, handles):
    if not len(clients) == len(processes) == len(ports) == 2:
        raise ValueError("Audio needs two separately owned peer/listener pairs")
    report["jump_audio_published_routes"] = records = []
    for seat, client in enumerate(clients):
        path = Path(output)/f"peer-{seat}/logs/jump-audio-host-input.jsonl"
        transcript = path.open("w", encoding="utf-8"); handles.append(transcript)
        record = dict(logical_seat=seat, local_port=1, debug_port=ports[seat],
                      owned_pid=processes[seat].pid, transcript=str(path))
        records.append(record)
        # The existing OwnedClient routes logical seatN through peerN's LOCAL
        # port1. HostRoute's report must remain separate from pair checks.
        client.reentry_route = ownership.Route(ownership.host.control_for(
            processes[seat], ports[seat], client, transcript), record)


def validate_context(ctx, expected_sha):
    report, clients = ctx["report"], ctx["clients"]
    checks = ("host_profile_settled_before_guest", "declared_build_manifest_bound_to_staged_images",
              "default_resident_loader_committed", "jump_audio_original_source_bound",
              "jump_audio_declared_sources_match")
    if (len(clients) != 2 or len(report.get("peers", [])) != 2 or
            report.get("candidate_exe_sha256") != expected_sha or
            any(p.get("preparation", {}).get("exe_sha256") != expected_sha for p in report["peers"]) or
            any(not isinstance(getattr(c, "reentry_route", None), ownership.Route) for c in clients)):
        raise ValueError("Audio requires two exact staged images and owned localport1 published routes")
    if (not all(report["checks"].get(k) is True for k in checks) or
            not report.get("resolved_state_crc") or not report.get("host_profile_startup") or
            not report.get("host_profile_build_manifest") or len(report.get("jump_audio_prepared", [])) != 2):
        raise ValueError("Audio lacks actual source/settings/profile/manifest/CRC startup proof")
    for peer in report["peers"]:
        directory = Path(peer["directory"])
        if (ownership.preparation.sha256(directory/"mmx6-runtime.exe") != expected_sha or
                json.loads((directory/"preparation.json").read_text(encoding="utf-8"))["exe_sha256"] != expected_sha):
            raise ValueError("A prepared audio executable changed")


def require(ok, message):
    if not ok:
        raise audio.AudioQualificationError(message)


def living_sample(row):
    o, players = row["observation"], row["players"]
    require(o["ready"] == o["enrolled"] == 1 and not o["failed"] and not o["mailbox"] and
        o["native_mode"] == 10 and o["native_phase"] == 0 and not o["scene_owner"] and
        not o["pause_owner"] and tuple(o["lifecycle"]) == (0, 0),
        "Audio pair left ordinary living gameplay")
    require([(p["character"], p["form"]) for p in players] == [(0, 1), (1, 5)] and
        all(p["state"] == 1 and p["hp"] == 32 and p["speech_gate"] == 0 for p in players),
        "Audio needs healthy original Falcon X/Zero with native speech allowed on each peer")


def held_receipt(before, held, seat, acknowledgment, network_start, network_end, label):
    """Use actual actor ascent and actual clocks, never requested debug duration."""
    start, end = before["observation"], held["observation"]
    native = (end["native_timer"]-start["native_timer"]) & 0xFFFFFFFF
    publications = (end["tick"]-start["tick"]) & 0xFFFFFFFF
    require(0 < native < 0x80000000 and 0 < publications < 0x80000000,
            "Jump lacks forward native/publication evidence")
    return dict(label=label, seat=seat, pressed=audio.CROSS, acknowledgment=acknowledgment,
        start=start, end=end, actual_native_ticks=native, actual_publications=publications,
        network_start=network_start, network_end=network_end,
        scope="Actual held ascent; clocks are separately identified, not assumed equal")


def compare_peer(observer, record, chosen, first_seat, contract):
    """Each result uses only this peer's events, probes and DSP responses."""
    identities = {event["seq"]: observer.identify(event, record["driver_after"]) for event in chosen}
    result = audio.compare_private_overlap(observer.events, *chosen, identities, first_seat, contract)
    checks, details = audio.final_dsp_checks(observer.events, result["actors"],
        record["voices_after"], record["private_voices_after"])
    result["checks"].update(checks, private_source_banks_stable=True)
    # The local reducer's scope warning is replaced only for this independently
    # observed pair. Other audio families/output remain outside the proof.
    result["limits"] = ["One ground-jump vocal overlap on this peer only",
        "Event-time bank/sample identity differs from later DSP snapshots",
        "No full R4/R12, PCM, audible output, music or independent sample-clock proof"]
    record.update(result)
    record["status"] = "observations_complete" if all(record["checks"].values()) else "comparison_failed"


def exercise(ctx, *, expected_sha, source, first_seat=0, max_attempts=8, timeout=120):
    if (type(first_seat) is not int or first_seat not in (0, 1) or type(max_attempts) is not int or
            not 1 <= max_attempts <= 8 or type(timeout) not in (int, float) or not 0 < timeout <= 120):
        raise ValueError("Audio requires bounded first-seat/attempt/deadline options")
    validate_context(ctx, expected_sha)
    report, clients = ctx["report"], ctx["clients"]
    contract, banks = source["contract"], source["private_banks"]
    audio.validate_contract(contract); audio.validate_private_bank_contract(banks, contract)
    case = dict(kind="paired_native_ground_jump_audio", mode="netplay", scope="same_machine",
        input_path="published_host", first_seat=first_seat, status="failed_setup", attempts=[],
        checks={}, observations=[], inputs=[], peers=[dict(peer=i, events=[], checks={}, status="not_compared") for i in (0, 1)],
        source_contract_sha256=audio.CONTRACT_SHA256, private_bank_source=banks,
        candidate_sha256=expected_sha, helper_sha256=ownership.preparation.sha256(Path(__file__)),
        observer_sha256=ownership.preparation.sha256(Path(audio.__file__)),
        limits=["Independent event/sample/DSP/lifetime evidence from each physical process",
                "One ground-jump order; no full R4/R12, other sounds, audible/PCM/music or cross-host pass"])
    report["jump_audio_pair"] = case
    report["checks"]["jump_audio_both_peers_completed"] = False
    report["jump_audio_private_cards_before"] = ownership.cards(ctx["output"])
    observers = [audio.AudioObserver(client, client.request, contract, private_banks=banks) for client in clients]
    deadline = time.monotonic()+timeout

    def sample(label):
        require(time.monotonic() < deadline, "Bounded paired audio deadline expired")
        rows = ctx["both"](lambda peer: observers[peer].poll())
        status = ctx["network"]() # Existing validator checks BOTH actual peers.
        case["observations"].append(dict(label=label, peers=rows, network=status))
        for row in rows: living_sample(row)
        return rows, status

    def ground(label):
        for attempt in range(21):
            rows, status = sample(label)
            if all(p["action"] == 2 and p["airborne"] == 0 and p["ground"] for r in rows for p in r["players"]):
                return rows, status
            require(attempt < 20, "Both peers failed to return both actors to original idle/ground")
            ctx["native_advance"](4, label)

    def jump(seat, before, network_start, label):
        # Keep the ordinary input held until each process independently shows
        # native action6 ascent. No configured-port change or direct SIO input.
        starts = [observer.cursor for observer in observers]
        held = [None, None]; acknowledgment = None; failure = None
        try:
            clients[seat].host_input(audio.CROSS)
            acknowledgment = dict(clients[seat].reentry_route.report["inputs"][-1],
                                  logical_seat=seat, local_port=1)
            end = min(deadline, time.monotonic()+8)
            while time.monotonic() < end:
                rows, status = sample(label+" held")
                for peer, row in enumerate(rows):
                    current, initial = row["players"][seat], before[peer]["players"][seat]
                    if (current["action"] == 6 and current["airborne"] == 1 and not current["ground"] and
                            current["y"] < initial["y"]):
                        held[peer] = held_receipt(before[peer], row, seat, acknowledgment,
                                                network_start, status, label)
                require(all(now["tick"] >= old["tick"] and now["resolved_through"] >= old["resolved_through"]
                            for now, old in zip(status, network_start)), "Audio transport counters regressed")
                if all(held) and all(now["resolved_through"] > old["resolved_through"] for now, old in zip(status, network_start)):
                    break
                time.sleep(.005)
            else:
                raise audio.AudioQualificationError("Both peers did not accept original held action6/ascent")
        except BaseException as error:
            failure = error; raise
        finally:
            try: clients[seat].host_input(0)
            except Exception as error:
                case.setdefault("neutral_errors", []).append(dict(seat=seat, label=label, error=str(error)))
                if failure is None: raise
        after, _ = sample(label+" released")
        case["inputs"].append(dict(label=label, logical_seat=seat, peers=held))
        for peer in (0, 1):
            require(audio.accepted_ground_jump(before[peer], after[peer], seat, held[peer]),
                    f"Peer{peer} native ground jump was not accepted")
        return [[e for e in observer.events if e["seq"] >= starts[peer] and
                 e["kind"] == "KEYON" and e["v"] in (20, 44)] for peer, observer in enumerate(observers)]

    failure = None
    try:
        ground("audio-initial-ground")
        for peer, observer in enumerate(observers):
            record = case["peers"][peer]
            record["private_banks_before"] = observer.fingerprint_banks()
            record["driver_before"] = driver = observer.driver()
            require(driver["release_adjust"] == 0 and all(driver["vab_status"][i] == 1 for i in (1, 3)),
                    f"Peer{peer} native release/VAB readiness unqualified")
            record["voices_before"] = audio.parse_voices(clients[peer].request("spu_voices"), require_banks=True)
            record["private_voices_before"] = audio.parse_private_voices(clients[peer].request("spu_private_voices"))
        chosen = None
        for attempt in range(max_attempts):
            before, start = ground(f"audio-attempt-{attempt}-ground")
            first = jump(first_seat, before, start, "audio-first-jump")
            row = dict(attempt=attempt, first_keys=first); case["attempts"].append(row)
            require(all(len(keys) <= 1 for keys in first), "Ambiguous first jump voice window")
            if not all(first):
                row["skip"] = "native_rng_first_voice_missing_on_at_least_one_peer"; continue
            # The second actor has not moved; use a fresh neutral observation
            # rather than attributing a prior sampled state to this hold.
            before, start = sample("audio-before-second-jump")
            second = jump(first_seat ^ 1, before, start, "audio-second-jump")
            row["second_keys"] = second
            require(all(len(keys) <= 1 for keys in second), "Ambiguous second jump voice window")
            if not all(second):
                row["skip"] = "native_rng_second_voice_missing_on_at_least_one_peer"; continue
            expired = [audio.lifetime(observers[p].events, first[p][0]) for p in (0, 1)]
            if any(life["disposition"] == "natural_end" and life["terminal"]["seq"] < second[p][0]["seq"]
                   for p, life in enumerate(expired)):
                row["skip"] = "no_shared_overlap_first_voice_already_ended"; continue
            chosen = [(first[p][0], second[p][0]) for p in (0, 1)]
            break
        ground("audio-final-ground")
        if chosen is not None:
            # Landing is independent of ADPCM/envelope lifetime. Observe each
            # selected voice's own terminal before taking final DSP snapshots.
            while any(audio.lifetime(observer.events, event)["terminal"] is None
                      for peer, observer in enumerate(observers) for event in chosen[peer]):
                sample("audio-vocal-lifetime-drain")
                if any(audio.lifetime(observer.events, event)["terminal"] is None
                       for peer, observer in enumerate(observers) for event in chosen[peer]):
                    ctx["native_advance"](2, "audio-vocal-lifetime-drain")
        for peer, observer in enumerate(observers):
            record = case["peers"][peer]
            record["private_banks_after"] = observer.fingerprint_banks()
            require(record["private_banks_before"] == record["private_banks_after"], f"Peer{peer} immutable bank changed")
            record["driver_after"] = observer.driver()
            require(record["driver_before"] == record["driver_after"], f"Peer{peer} native driver tables changed")
            record["voices_after"] = audio.parse_voices(clients[peer].request("spu_voices"), require_banks=True)
            record["private_voices_after"] = audio.parse_private_voices(clients[peer].request("spu_private_voices"))
        sample("audio-after-read-only-bank-and-dsp-probes")
        if chosen is None:
            case["status"] = INCONCLUSIVE
            return case
        for peer, observer in enumerate(observers):
            compare_peer(observer, case["peers"][peer], chosen[peer], first_seat, contract)
        case["checks"] = {f"peer{p}_{key}": value for p, record in enumerate(case["peers"])
                          for key, value in record["checks"].items()}
        completed = bool(case["checks"]) and all(case["checks"].values())
        case["status"] = SUCCESS if completed else "comparison_failed"
        report["checks"]["jump_audio_both_peers_completed"] = completed
        return case
    except BaseException as error:
        failure = error; case["error"] = dict(type=type(error).__name__, message=str(error)); raise
    finally:
        for peer, observer in enumerate(observers): case["peers"][peer]["events"] = observer.events
        errors = []
        for seat, client in enumerate(clients):
            try: client.host_input(0)
            except Exception as error: errors.append(dict(seat=seat, error=str(error)))
        report["jump_audio_input_cleanup_errors"] = errors
        report["checks"]["jump_audio_published_neutral_requests_completed"] = not errors
        if errors:
            case["status"] = "failed_cleanup"
            if failure is None: raise audio.AudioQualificationError("Paired audio neutral release failed")


def finalize(report, output, *, runtime_ready, owned_processes):
    """Late cleanup/profile failure cannot inherit an earlier observer success."""
    try:
        final = ownership.cards(output); report["jump_audio_private_cards_final"] = final
        unchanged = final == report.get("jump_audio_private_cards_before")
    except OSError as error:
        report["jump_audio_final_card_error"] = str(error); unchanged = False
    peers = report.get("peers", [])
    cleaned = owned_processes == len(peers) == 2 and all(p.get("shutdown") == "graceful_owned_debug" and
        p.get("exit_code") == 0 and not p.get("input_release_errors") and not p.get("private_card_error") for p in peers)
    report["checks"].update(jump_audio_final_private_cards_unchanged=unchanged, jump_audio_owned_pair_cleanup=cleaned)
    if not unchanged or not cleaned:
        report["status"] = "failed" if runtime_ready else "failed_setup"
        report["default_intro_qualified"] = report["default_launch_qualified"] = False
