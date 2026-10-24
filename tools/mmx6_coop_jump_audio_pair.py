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
BODY_SUCCESS = "paired_body_audio_observations_complete_outcomes_unverified"
BODY_PARTIAL = "paired_body_audio_observations_partial_stops_unverified"


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


def exercise(ctx, *, expected_sha, source, first_seat=0, max_attempts=32, timeout=120):
    if (type(first_seat) is not int or first_seat not in (0, 1) or type(max_attempts) is not int or
            not 1 <= max_attempts <= 32 or type(timeout) not in (int, float) or not 0 < timeout <= 120):
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
        after, after_network = sample(label+" released")
        case["inputs"].append(dict(label=label, logical_seat=seat, peers=held))
        for peer in (0, 1):
            require(audio.accepted_ground_jump(before[peer], after[peer], seat, held[peer]),
                    f"Peer{peer} native ground jump was not accepted")
        keys = [[e for e in observer.events if e["seq"] >= starts[peer] and
                 e["kind"] == "KEYON" and e["v"] in (20, 44)] for peer, observer in enumerate(observers)]
        return keys, after, after_network

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
            first, before_second, second_start = jump(first_seat, before, start, "audio-first-jump")
            row = dict(attempt=attempt, first_keys=first); case["attempts"].append(row)
            require(all(len(keys) <= 1 for keys in first), "Ambiguous first jump voice window")
            if not all(first):
                row["skip"] = "native_rng_first_voice_missing_on_at_least_one_peer"; continue
            # Reuse the actual post-release observation just collected. It
            # includes the still-grounded second actor; another full poll here
            # unnecessarily spends the first vocal's short remaining lifetime.
            second, _, _ = jump(first_seat ^ 1, before_second, second_start, "audio-second-jump")
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


def contact_history(rows):
    """Require eight independently observed ordinary losses, not a counter alone."""
    from mmx6_coop_contact import hazardous
    require(bool(rows) and rows[0]['players'][1]['hp']==32 and rows[0]['p2_contact_counter']==0,
        'Secondary contact history lacks its initial full-health observation')
    changes=[];selected=None;previous=rows[0]
    for row in rows:
        p1,p2=row['players'];actor=row['instance']
        require(p1['hp_raw']==32 and p1['state']==1 and row['observation']['players'][0]['x_raw']==144<<16,
            'Secondary primary moved or lost health')
        require(row['expected_damage']==4 and row['expected_reaction']==1,'Secondary damage configuration changed')
        require(not hazardous(row) or p2['hp']==0,'Secondary terrain hazard confounds contact damage')
        if actor:
            require((actor['phase']==1 or p2['hp']==0 and actor['phase']==3) and actor['hp']==12 and
                actor['strength']==4 and actor['subtype']==1 and actor['contact_class']==0,
                'Secondary authored contact enemy changed')
            if selected is None:selected=actor['address']
            require(selected==actor['address'],'Secondary contact actor changed')
        require(actor is not None or selected is None or p2['hp']==0,'Secondary contact actor disappeared before fatal damage')
        old=previous['players'][1]['hp']
        if old!=p2['hp']:
            require(old-p2['hp']==4 and row['p2_contact_counter']==len(changes)+1,
                'Secondary contact history skipped or misattributed a loss')
            changes.append(dict(before=old,after=p2['hp'],counter=row['p2_contact_counter'],
                native_timer=row['observation']['native_timer']))
        previous=row
    require(selected is not None and len(changes)==8 and rows[-1]['players'][1]['hp']==0 and rows[-1]['p2_contact_counter']==8,
        'Secondary contact history lacks eight observed losses and fatal damage')
    return changes,selected


def exercise_body(ctx, *, expected_sha, source, original_exe, original_disc, timeout=120):
    """One shared input route, with independent source/voice/contact probes."""
    import mmx6_coop_body_audio as body
    validate_context(ctx,expected_sha)
    require(type(timeout) in (int,float) and 0<timeout<=120,'Require bounded paired body audio deadline')
    report,clients=ctx['report'],ctx['clients'];output=Path(ctx['output'])/'body-audio';output.mkdir()
    body_source=body.build_source(original_exe,original_disc)
    zero_overlay=body.contact.load_zero_overlay(original_disc)
    (output/'source-records.json').write_text(json.dumps(body_source,indent=2)+'\n',encoding='utf-8')
    (output/'body-observer-executed-source.py').write_bytes(Path(body.__file__).read_bytes())
    case=dict(kind='paired_native_saber_hurt_death_audio',mode='netplay',scope='same_machine',
        status='failed_setup',peers=[{},dict(peer=1,checks={},contacts=[],observations=[])],
        source_sha256=body.source_digest(body_source),helper_sha256=ownership.preparation.sha256(Path(__file__)),
        candidate_sha256=expected_sha,checks={},pending_checks=[],limits=[
            'Both peer observations use source-bound original inputs; no full R4/R12, co-op-off reference, active STOP7 or cross-machine pass.',
            'Inactive STOP7 is pending if later source-matched death audio obscures its volume transition.'])
    report['body_audio_pair']=case;report['checks']['body_audio_both_peers_applicable_checks']=False
    logs=[(output/f'peer-{p}-audio-rpc.jsonl').open('w',encoding='utf-8')for p in (0,1)]
    secondary=case['peers'][1];live=False;captured=False
    def request(peer,command,**fields):
        response=clients[peer].request(command,**fields)
        logs[peer].write(json.dumps(dict(command=command,fields=fields,response=response),separators=(',',':'))+'\n')
        logs[peer].flush();return response
    observers=[None,audio.AudioObserver(clients[1],lambda cmd,**kw:request(1,cmd,**kw),source['contract'],private_banks=source['private_banks'])]
    observer=observers[1]
    secondary['events']=observer.events
    def capture_secondary():
        nonlocal captured
        if captured:return
        secondary['observations'].append(observer.poll())
        secondary['private_after']=audio.parse_private_voices(request(1,'spu_private_voices'))
        secondary['owners_after']=body.voice_leases(request(1,'spu_private_voices'))
        secondary['hardware_after']=audio.parse_voices(request(1,'spu_voices'),require_banks=True)
        secondary['contacts'].append(body.contact.observe_contact(clients[1],zero_overlay))
        secondary['trace']=body.trace_page(dict(request=lambda cmd,**kw:request(1,cmd,**kw)))
        secondary['events']=observer.events;captured=True
    def primary_request(command,**fields):
        nonlocal live
        if command=='fntrace_arm_clear' and live:capture_secondary();live=False
        response=request(0,command,**fields)
        if command in ('fntrace_arm_clear','fntrace_arm','fntrace_clear','fntrace_armed'):
            other=request(1,command,**fields)
            if command=='fntrace_armed':
                require(other['count']==response['count'] and set(other['targets'])==set(response['targets']),
                    'Secondary source trace targets differ')
            if command=='fntrace_clear':
                secondary['observations'].append(observer.poll());secondary['event_start']=observer.cursor;live=True
        return response
    def set_input(seat,bits):
        clients[seat].host_input(bits)
        return dict(clients[seat].reentry_route.report['inputs'][-1],logical_seat=seat,local_port=1)
    def standing(primary):
        row=observer.poll();living_sample(row);secondary['observations'].append(row)
        trace=body.trace_page(dict(request=lambda cmd,**kw:request(1,cmd,**kw)))
        keys=[e for e in observer.events if e['seq']>=secondary['event_start'] and e['kind']=='KEYON' and
            e['v']==47 and e['frame']==primary['selected']['event']['frame']]
        require(len(keys)==1,'Secondary lacks the same-frame native saber event')
        secondary['selected']=body.identify(observer,keys[0],body_source,sound_calls=trace['entries'])
        secondary['private_before_death']=audio.parse_private_voices(request(1,'spu_private_voices'))
        secondary['checks'].update(secondary['selected']['checks'])
        checks,terminal=body.standing_checks(observer.events,secondary['selected'],secondary['private_before_death'])
        secondary['checks'].update(checks);secondary['terminal']=terminal
        secondary['contacts'].append(body.contact.observe_contact(clients[1],zero_overlay))
    def contact_observation(row):
        secondary['contacts'].append(body.contact.observe_contact(clients[1],zero_overlay))
        case.setdefault('network_observations',[]).append(ctx['network']())
    failure=None
    try:
        secondary['banks_before']=observer.fingerprint_banks()
        secondary['owners_before']=body.voice_leases(request(1,'spu_private_voices'))
        secondary['hardware_before']=audio.parse_voices(request(1,'spu_voices'),require_banks=True)
        body.exercise(dict(ctx,mode='netplay',input_path='published_host',expected_sha256=expected_sha,
            request=primary_request,set_input=set_input,private_banks=source['private_banks'],zero_overlay=zero_overlay,
            on_standing_saber=standing,on_contact_observation=contact_observation),source['contract'],
            source=body_source,timeout=timeout,death=True)
        primary=report['body_audio'];case['peers'][0]=primary
        require(captured,'Secondary source trace was not captured before disarming')
        secondary['character_samples']=[body.identify_character(observer,e,body_source,secondary['trace']['entries'])
            for e in observer.events if e['seq']>=secondary['event_start'] and e['kind']=='KEYON' and
            e['sample_bank'] in (30,31) and e['v']>=24]
        secondary['checks']['observed_character_samples_source_matched']=bool(secondary['character_samples']) and all(
            all(r['checks'].values())for r in secondary['character_samples'])
        secondary['banks_after']=observer.fingerprint_banks()
        secondary['checks']['immutable_private_banks_stable']=secondary['banks_before']==secondary['banks_after']
        secondary['checks']['private_voice_leases_stable']=secondary['owners_before']==secondary['owners_after']
        secondary['hp_changes'],actor=contact_history(secondary['contacts'])
        secondary['checks']['eight_ordinary_contact_losses']=len(secondary['hp_changes'])==8
        contacts=[r for r in secondary['trace']['entries']if int(r['target'],16)==body.contact.CONTACT]
        secondary['checks']['original_contact_actor_caller']=bool(contacts) and all(
            int(r['a0'],16)==int(actor,16) and int(r['ra'],16)==body.contact.CONTACT_RA for r in contacts)
        checks=body.phase2_checks(secondary['trace'],observer.events,before_private=secondary['private_before_death'],
            after_private=secondary['private_after'],before_hardware=secondary['hardware_before'],after_hardware=secondary['hardware_after'])
        secondary['pending_checks']=[]
        if not checks['private23_phase2_stop'] and body.obscured_inactive_stop7(observer.events,secondary['selected'],
                secondary['private_before_death'],secondary['private_after'],secondary['trace'],secondary['character_samples']):
            checks.pop('private23_phase2_stop');secondary['pending_checks'].append('Inactive STOP7 obscured by source-matched death3/14')
        secondary['checks'].update(checks)
        secondary['status']='observations_complete' if all(secondary['checks'].values()) else 'comparison_failed'
        if secondary['status']=='observations_complete' and secondary['pending_checks']:secondary['status']='observations_partial'
        case['pending_checks']=[dict(peer=p,check=check)for p,row in enumerate(case['peers'])for check in row.get('pending_checks',[])]
        case['checks']={f'peer{p}_{k}':v for p,row in enumerate(case['peers'])for k,v in row['checks'].items()}
        complete=bool(case['checks']) and all(case['checks'].values())
        case['status']=(BODY_PARTIAL if case['pending_checks'] else BODY_SUCCESS)if complete else 'comparison_failed'
        report['checks']['body_audio_both_peers_applicable_checks']=complete
        return case
    except BaseException as error:
        failure=error;case['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if 'body_audio' in report:case['peers'][0]=report.pop('body_audio')
        errors=[]
        for p in (0,1):
            try:clients[p].host_input(0)
            except Exception as error:errors.append(dict(peer=p,error=str(error)))
            try:request(p,'fntrace_arm_clear')
            except Exception as error:errors.append(dict(peer=p,trace_error=str(error)))
        for log in logs:log.close()
        case['cleanup_errors']=errors
        if errors:
            case['status']='failed_cleanup'
            if failure is None:raise audio.AudioQualificationError('Paired body audio cleanup failed')


def exercise_primary(ctx,*,expected_sha,source,original_exe,original_disc,timeout=150):
    """Full paired startup gates, then two independent primary/overlap probes."""
    import mmx6_coop_primary_audio as primary
    validate_context(ctx,expected_sha)
    def set_input(seat,bits):
        ctx['clients'][seat].host_input(bits)
        return dict(ctx['clients'][seat].reentry_route.report['inputs'][-1],logical_seat=seat,local_port=1)
    return primary.exercise(dict(ctx,mode='netplay',input_path='published_host',
        expected_sha256=expected_sha,private_banks=source['private_banks'],set_input=set_input,
        request_peer=lambda peer,cmd,**kw:ctx['clients'][peer].request(cmd,**kw),
        output=Path(ctx['output'])/'primary-audio'),source['contract'],
        primary.sources(original_exe,original_disc),timeout=timeout)


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
