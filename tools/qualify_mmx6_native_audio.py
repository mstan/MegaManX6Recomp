"""Owned, muted, co-op-disabled character audio reference; original inputs only.

This is an offline recompiled reference, not original-hardware qualification.
The optional Zero selector prerequisite is retained as an explicit setup bypass.
No voice/register/sample write, guest call, event reset or source card is used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

import audit_mmx6_private_action_audio as original
import coop_debug as debug
import coop_host_profile as manifests
import mmx6_coop_jump_audio as audio
import mmx6_native_zero_reference as reference
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_baseline as baseline
import qualify_mmx6_coop_jump_audio as bound_sources

SOUND, STOP = 0x80016C48, 0x8001750C
X_BUSTER_INIT = 0x80049270
TRACE_TARGETS = {SOUND, STOP, X_BUSTER_INIT}
READONLY_AUDIO = frozenset(("spu_events", "spu_ram", "spu_voices", "spu_private_voices"))
TRACE_COMMANDS = frozenset(("fntrace_arm_clear", "fntrace_arm", "fntrace_armed", "fntrace_clear", "fntrace_dump"))


def require(ok, message):
    if not ok:
        raise debug.DebugError(message)


def write_json(path, value):
    Path(path).write_bytes((json.dumps(value, indent=2) + "\n").encode("utf-8"))


def build_source(exe_path, disc_path, character):
    """Bounded original DAT member, both VAB banks and all populated records."""
    member = {"X": 87, "Zero": 85}[character]
    payload = Path(exe_path).read_bytes()
    require(original.sha(payload) == original.content.EXE_SHA256, "Original EXE identity changed")
    exe = original.content.Executable(payload)
    disc = original.Disc(str(disc_path))
    try:
        files = disc.files()
        exe_lba, exe_size = files["SLUS_013.95"]
        require(b"".join(disc.user(exe_lba+i) for i in range((exe_size+2047)//2048))[:exe_size] == payload,
                "Original disc/EXE identities differ")
        lba, total = files["ROCK_X6.DAT"]
        sector, size = struct.unpack_from("<II", disc.user(lba), member*8)
        require(sector >= 1 and 2048 <= size <= 2_000_000 and sector*2048+size <= total,
                "Character DAT member escaped its original archive")
        data = b"".join(disc.user(lba+sector+i) for i in range((size+2047)//2048))[:size]
        require(original.sha(data) == original.PLAYER_MEMBERS[member][1], "Original character member changed")
        assets, banks = original.subassets(data), {}
        for group, hi, bi, kind in ((1,11,12,0x20101), (3,13,14,0x20303)):
            require(assets[hi][0] == 6 and assets[bi][0] == kind, "Character VAB asset types changed")
            header, samples = assets[hi][1], assets[bi][1]
            banks[group] = dict(header=header, samples=samples,
                                metadata=original.bank_metadata(header, samples, group))
        records = original.resolve_records(banks)
        for record in records:
            for tone in record["tones"]:
                tone["pitch"] = audio.native_pitch(tone["note"], tone["shift"], tone["center"],
                                                    tone["shift"], lambda pc: exe.word(pc)&65535)
        child_routes = []
        if character == "X":
            # Original initializer saves its actor a0 in s2, derives presentation
            # from fixed PLAYER and calls SOUND(1, table_record, that same s2).
            for pc, expected in ((0x80049278,0x00809021),(0x80049358,0x260270A0),
                                 (0x80049384,0x260270A0),(0x800493C0,0x24040001),
                                 (0x800493CC,0x0C005B12),(0x800493D0,0x02403021)):
                require(exe.word(pc) == expected, "Original native X buster source route changed")
            start, end = X_BUSTER_INIT, X_BUSTER_INIT+416
            raw = payload[2048+start-exe.base:2048+end-exe.base]
            child_routes.append(dict(initializer=X_BUSTER_INIT, sound_return=0x800493D4,
                start=start, bytes=len(raw), sha256=original.sha(raw), source_hex=raw.hex(),
                attribution="source_guarded_native_X_buster_initializer_same_frame_same_actor"))
        return dict(character=character, member=member, member_sha256=original.sha(data),
                    exe_sha256=original.sha(payload), records=records,
                    banks={str(k):v["metadata"] for k,v in banks.items()},child_routes=child_routes)
    finally:
        disc.f.close()


def candidate_tones(event, calls, source, bases):
    """At most one queued hardware frame between body SOUND and native KEYON.

    This bound is explicit; ambiguous calls are rejected rather than guessed.
    Private immediate playback is covered by the separate co-op observer.
    """
    require(event.get("sample_bank") == 0 and 0 <= event["v"] < 24,
            "Offline native reference unexpectedly used a private voice/bank")
    result = []
    for call in calls:
        if int(call["target"],16) != SOUND:
            continue
        actor = int(call["a2"],16)
        attribution = "original_PLAYER_body_SOUND"
        if actor != reference.PLAYER:
            routes = [r for r in source.get("child_routes",[]) if int(call.get("ra","0"),16) == r["sound_return"]
                and any(int(c["target"],16) == r["initializer"] and c["frame"] == call["frame"]
                        and int(c["a0"],16) == actor for c in calls)]
            if len(routes) != 1:
                continue
            attribution = routes[0]["attribution"]
        lag = (event["frame"]-call["frame"]) & 0xFFFFFFFF
        if lag > 1:
            continue
        group, number = int(call["a0"],16)&127, int(call["a1"],16)&255
        for record in source["records"]:
            if (record["group"], record["record"]) != (group, number):
                continue
            bank = record["effective_bank_group"]
            for tone in record["tones"]:
                if (tone["voice"] == event["v"] and bases[bank]+tone["offset"] == event["addr"]):
                    result.append(dict(record=record, tone=tone, source_call=call, queued_engine_frames=lag,
                                       actor_attribution=attribution))
    require(len(result) <= 1, "Native reference sample has ambiguous event-time body SOUND calls")
    return result[0] if result else None


class Session(reference.OwnedNativeSession):
    """Keep the renderer helper's controls unchanged; add read-only audio/trace."""
    ALLOWED = reference.OwnedNativeSession.ALLOWED | READONLY_AUDIO | TRACE_COMMANDS

    def __init__(self, *args, log, **kwargs):
        self.log = log
        super().__init__(*args, **kwargs)

    def request(self, command, **fields):
        result = super().request(command, **fields)
        # Retain actual audio probes and trace pages, not megabytes of repeated RAM.
        if command in READONLY_AUDIO | TRACE_COMMANDS or command in ("press", "clear_input", "write_ram"):
            self.log.write(json.dumps(dict(command=command, fields=fields, response=result))+"\n")
            self.log.flush()
        return result


class Observer:
    def __init__(self, session, source):
        self.session, self.source = session, source
        self.cursor, self.events = None, []
        self.event_window = 4096

    def poll(self):
        total, rows = audio.parse_events(self.session.request("spu_events", count=self.event_window),
                                        self.cursor, require_banks=True)
        if self.cursor is not None:
            require(all(r["v"] < 24 or r["kind"] == "IRQ" for r in rows),
                    "Co-op-disabled reference emitted private DSP events")
            self.events.extend(rows)
        self.cursor = total
        require(len(self.events) <= 16384, "Native reference event bound exhausted")
        return rows

    def driver(self):
        raw = self.session.read(0x800E5588, 0x1A8)
        return dict(headers=list(struct.unpack_from("<16I",raw,0x40)),
                    bases=list(struct.unpack_from("<16I",raw,0x168)))

    def sample_bytes(self, start, size):
        require(type(start) is int and type(size) is int and 0 < size <= 0x80000 and
                0 <= start < start+size <= 0x80000, "Native SPU sample escaped its bank")
        chunks = []
        for offset in range(0,size,4096):
            count = min(4096,size-offset)
            reply = self.session.request("spu_ram", addr=start+offset, len=count)
            require(reply.get("len") == count and int(reply.get("addr","-1"),16) == start+offset,
                    "Native SPU sample response changed its requested range")
            raw = bytes.fromhex(reply.get("hex", ""))
            require(len(raw) == count, "Native SPU sample response was truncated")
            chunks.append(raw)
        return b"".join(chunks)

    def fingerprint_banks(self, driver):
        rows = []
        for group, bank in self.source["banks"].items():
            start, count = driver["bases"][int(group)], bank["sample_bytes"]
            digest = original.sha(self.sample_bytes(start,count))
            require(digest == bank["sample_sha256"], "Native resident character bank differs from original DAT")
            rows.append(dict(group=int(group), start=start, bytes=count, sha256=digest, matches_source=True))
        return rows

    def identify(self, event, calls, driver):
        matched = candidate_tones(event,calls,self.source,driver["bases"])
        if matched is None:
            return None
        tone = matched["tone"]
        digest = original.sha(self.sample_bytes(event["addr"],tone["bytes"]))
        checks = dict(source_sample=digest == tone["sample_sha256"],
                      pitch_adsr_numeric=all(event[k] == tone[k] for k in ("pitch","adsr_lo","adsr_hi")),
                      original_end_marker_present=tone["first_end_block"] is not None and
                          bool(tone["first_end_flags"]&1))
        require(all(checks.values()), "Native source sample or numeric DSP mismatch")
        return dict(event=event, observed_sha256=digest, checks=checks, **matched)

    def identify_sample_only(self, event, driver):
        """Keep waveform identity separate from an unobserved SOUND record.

        Several native records alias the same sample. No initializer, body
        owner or record identity is inferred from the address or wave alone.
        """
        require(event.get("sample_bank") == 0 and 0 <= event["v"] < 24,
                "Native sample-only reference unexpectedly used a private route")
        candidates = []
        for record in self.source["records"]:
            for tone in record["tones"]:
                if tone["voice"] == event["v"] and driver["bases"][record["effective_bank_group"]]+tone["offset"] == event["addr"]:
                    candidates.append((record,tone))
        if not candidates:
            return None
        candidates = [(r,t) for r,t in candidates if all(event[k] == t[k] for k in ("pitch","adsr_lo","adsr_hi"))]
        require(candidates, "Native known sample address has unexpected numeric DSP")
        identities = {(t["bytes"],t["sample_sha256"]) for r,t in candidates}
        require(len(identities) == 1, "Native sample-only probe has ambiguous source extents")
        count, expected = next(iter(identities))
        observed = original.sha(self.sample_bytes(event["addr"],count))
        require(observed == expected, "Native sample-only bytes differ from original character bank")
        return dict(event=event, observed_sha256=observed,
            record_candidates=[dict(group=r["group"],record=r["record"],effective_bank_group=r["effective_bank_group"],
                                    program=t["program"],tone=t["tone"]) for r,t in candidates],
            checks=dict(source_sample=True,pitch_adsr_numeric=True),exact_sound_record_identity=False,
            actor_attribution="unverified; waveform only within original-input action window")


def native_sample(session):
    # Separate ordinary-RAM RPCs. The play timer paces input; it is not claimed
    # to be a coherent pairing with the earlier body or an SPU sample clock.
    body = session.read(reference.PLAYER,0x158)
    play = session.read(reference.PLAY,0x94)
    return dict(mode=list(play[:3]), stage=play[12], section=play[13],
                timer=struct.unpack_from("<I",play,0x90)[0], character=body[2],
                form=body[0xE7], state=body[4], action=body[5], hp=body[0x5C]&127,
                hp_raw=body[0x5C],pending_hit=bool(body[0x5C]&128),
                iframes=body[0x61],reaction=body[0x63],reaction_lock=body[0xA4],
                terrain=body[0x70],previous_terrain=body[0x89],
                difficulty=play[0x68],shared_parts=play[0x5F],parts=struct.unpack_from('<I',body,0xEC)[0],
                x=struct.unpack_from("<i",body,8)[0], y=struct.unpack_from("<i",body,12)[0],
                airborne=struct.unpack_from("<b",body,0x67)[0], ground=bool(body[0x70]&8),
                observation_method="separate body and PLAY RAM RPCs")


def trace_page(session, *, targets=TRACE_TARGETS):
    page = session.request("fntrace_dump", count=4096, seq_lo="0")
    rows = page["entries"]
    require(page["seq_lo"] == 0 and 0 <= page["seq_hi"] <= 4096 and page["emitted"] == len(rows)
            and [r["seq"] for r in rows] == list(range(page["seq_hi"]))
            and all(int(r["target"],16) in targets for r in rows), "Native reference trace is incomplete")
    return page


def exercise(session, observer, label, bits, *, case=None, hold_ticks=3, drain_ticks=75):
    if case is None:
        case = {}
    case.update(label=label, pressed=bits, status="failed_setup", observations=[], checks={})
    session.request("clear_input",port=1)
    before = native_sample(session)
    require(before["mode"][:2] == [10,0] and before["state"] == 1 and before["hp"] > 0
            and before["action"] == 2 and before["ground"] and not before["airborne"],
            "Native reference action requires living ground-idle body")
    session.request("fntrace_clear")
    observer.poll()
    start = observer.cursor
    driver = observer.driver()
    deadline = time.monotonic()+15
    released = False
    try:
        case["acknowledgment"] = session.request("press",port=1,buttons=bits^65535,frames=0)
        while time.monotonic() < deadline:
            observer.poll()
            row = native_sample(session)
            case["observations"].append(row)
            require(row["mode"][:2] == [10,0] and row["state"] == 1 and row["hp"] == before["hp"]
                    and (row["character"],row["form"]) == (before["character"],before["form"]),
                    "Native reference input left its living character context")
            elapsed = (row["timer"]-before["timer"]) & 0xFFFFFFFF
            require(elapsed < 0x80000000 and elapsed <= 240, "Native reference action clock escaped its bound")
            if not released and elapsed >= hold_ticks:
                session.request("clear_input",port=1)
                released = True
                case["release"] = row
            if released and elapsed >= drain_ticks and row["action"] == 2 and row["ground"] and not row["airborne"]:
                break
            time.sleep(.008)
        else:
            raise debug.DebugError("Native reference action did not drain to idle")
    finally:
        session.request("clear_input",port=1)
    observer.poll()
    case["trace"] = trace_page(session)
    case["events"] = [e for e in observer.events if e["seq"] >= start]
    case["matched"] = []
    case["sample_only"] = []
    for event in case["events"]:
        if event["kind"] != "KEYON":
            continue
        matched = observer.identify(event,case["trace"]["entries"],driver)
        if matched:
            matched["lifetime"] = audio.lifetime(case["events"],event)
            case["matched"].append(matched)
        else:
            sample_only = observer.identify_sample_only(event,driver)
            if sample_only:
                sample_only["lifetime"] = audio.lifetime(case["events"],event)
                case["sample_only"].append(sample_only)
    require(case["matched"] or case["sample_only"], "No native character sample identity in original-input reference window")
    if label == "ground_jump":
        require(any(r["airborne"] > 0 or not r["ground"] for r in case["observations"]),
                "Native jump was not observed")
        case["jump_vocal_observed"] = any(r["record"]["group"] == 3 for r in case["matched"])
    elif observer.source["character"] == "Zero":
        exact = any((r["record"]["group"],r["record"]["record"]) == (1,7) for r in case["matched"])
        wave = any(r["event"]["v"] == 23 and any((c["group"],c["record"]) == (1,7)
                   for c in r["record_candidates"]) for r in case["sample_only"])
        require(any(r["action"] in (0x30,0x32) for r in case["observations"]) and (exact or wave),
                "Native Zero Saber action and source SFX sample were not observed")
        case["saber_sfx_exact_sound_record_identity"] = exact
        if not exact:
            case["limits"] = ["Native Saber SFX waveform/numeric DSP match the listed source candidates; event-time SOUND record/caller remains unverified."]
    else:
        require(any(m["actor_attribution"] == "source_guarded_native_X_buster_initializer_same_frame_same_actor"
                    for m in case["matched"]), "Original X buster initializer/SOUND route was not observed")
    case["event_time_body_sound_observed"] = bool(case["matched"])
    case["checks"] = dict(source_matched_character_samples=True, original_input_observed=True,
                          returned_to_ground_idle=True, stable_native_driver=observer.driver() == driver,
                          living_health_preserved=True)
    require(all(case["checks"].values()), "Native reference driver changed within action")
    case["status"] = "bounded_source_matched_reference"
    return case


def boot(process, port, timeout, report):
    client = debug.DebugClient(port)
    deadline, next_input, release_at, step = time.monotonic()+timeout, 0., 0., 0
    while time.monotonic() < deadline:
        require(process.poll() is None, "Owned native reference exited during boot")
        if not baseline.owns_listener(port,process.pid):
            time.sleep(.05)
            continue
        pad = client.request("pad_status")
        require(pad.get("slot0",{}).get("connected"), "Native reference virtual P1 pad disconnected")
        row = native_sample(client)
        report["boot_latest"] = row
        if row["mode"][:2] == [10,0] and row["state"] == 1 and row["action"] == 2 and row["hp"] > 0:
            client.request("clear_input",port=1)
            return
        now = time.monotonic()
        if release_at and now >= release_at:
            client.request("clear_input",port=1)
            release_at = 0.
        if now >= next_input and not release_at:
            bits = 8 if row["mode"][0] != 10 and step%3 == 0 else 0x4000
            client.request("press",port=1,buttons=bits^65535,frames=0)
            step += 1
            release_at, next_input = now+.10, now+.8
        time.sleep(.04)
    raise debug.DebugError("Native reference boot did not reach idle gameplay")


def run(args):
    output = preparation.local_output(args.out)
    output.mkdir(parents=True,exist_ok=False)
    report = dict(kind="offline_coop_disabled_native_character_audio_reference",status="failed_setup",
                  character=args.character, expected_exe_sha256=args.expected_exe_sha256,
                  cases=[], checks={}, bypasses=[], limits=[
                      "Offline same-machine recompiled native reference; no original-hardware, audible or full R4/R12 pass.",
                      "Only ground jump and standing Square attack; hurt/death and other actions remain unverified.",
                      "Exact record matches require SOUND in the same or next engine frame; waveform-only observations keep record/actor identity unverified.",
                      "Separate body/PLAY RAM RPCs pace input; no coherent body/SPU clock or PCM claim."])
    report["executed_helpers"] = {}
    for module in (reference,audio,original,bound_sources,baseline):
        path = Path(module.__file__)
        report["executed_helpers"][path.name] = preparation.sha256(path)
    report["executed_helpers"][Path(__file__).name] = preparation.sha256(Path(__file__))
    (output/"qualify_mmx6_native_audio-executed-source.py").write_bytes(Path(__file__).read_bytes())
    contact_audio = None
    if args.contact_death:
        import mmx6_native_contact_audio as contact_audio
        module_path=Path(contact_audio.__file__)
        report['executed_helpers'][module_path.name]=preparation.sha256(module_path)
        (output/'mmx6_native_contact_audio-executed-source.py').write_bytes(module_path.read_bytes())
        report['limits'][1]='Original-input ground jump, standing attack and requested authored contact hurt/death reference only; other actions remain unverified.'
    process, session, stdout, stderr, rpc_log = None, None, None, None, None
    try:
        profile = output/"candidate"
        report["prepared"] = reference.prepare_reference_profile(args.build,args.source,profile,args.disc,
            expected_exe_sha256=args.expected_exe_sha256)
        report["manifest"] = manifests.validate_build_manifest(args.build,
            [args.build/"mmx6-runtime.exe",profile/"mmx6-runtime.exe"],evidence_directory=output/"manifest")
        require(report["manifest"]["declared_sha256"] == args.expected_manifest_sha256,
                "Native reference compiled manifest differs from expected identity")
        report["declared_sources"] = bound_sources.validate_sources(args.build,args.source,report["manifest"])
        report["originals"] = bound_sources.verify_prepared_originals(profile,args.original_exe,args.disc)
        report["source"] = build_source(args.original_exe,args.original_disc,args.character)
        write_json(output/"source-records.json",report["source"])
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1",args.port))
        prep = report["prepared"]["preparation"]
        env = baseline.candidate_environment(profile,prep)
        command = [str(profile/"mmx6-runtime.exe"),"--game",str(profile/"game.toml"),"--memcard-dir",
                   str(profile/"saves"),"--hidden-window","--debug-port",str(args.port)]
        stdout, stderr = (output/"stdout.log").open("w"), (output/"stderr.log").open("w")
        cards_before = {p.name:preparation.sha256(p) for p in (profile/"saves").glob("*.mcd")}
        report["args"] = command
        process = subprocess.Popen(command,cwd=profile,env=env,stdout=stdout,stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        report["owned_pid"] = process.pid
        boot(process,args.port,args.timeout,report)
        rpc_log = (output/"audio-rpc.jsonl").open("w",encoding="utf-8",newline="\n")
        session = Session(process,args.port,profile,args.expected_exe_sha256,log=rpc_log)
        report["actual_image"] = dict(path=str(session.image_path),sha256=session.image_sha256)
        report["actual_mod_state"] = session.profile
        if args.character == "Zero":
            report["selection"] = {}
            reference.select_native_zero(session,reference.load_sources(args.original_disc),report["selection"],
                allow_private_prerequisite=args.allow_private_prerequisite,timeout=min(args.timeout,90))
            report["bypasses"] = report["selection"]["bypasses"]
        row = native_sample(session)
        require((row["character"],row["form"]) == ((0,1) if args.character == "X" else (1,5)),
                "Reference selected an unsupported native character/form")
        report["before"] = row
        report["native_child_code_guards"] = []
        for route in report["source"]["child_routes"]:
            observed = session.read(route["start"],route["bytes"])
            require(observed.hex() == route["source_hex"], "Native reference child route differs from original executable")
            report["native_child_code_guards"].append(dict(address=route["start"],bytes=len(observed),
                sha256=original.sha(observed),matches_source=True))
        session.request("fntrace_arm_clear")
        for target in sorted(TRACE_TARGETS):
            session.request("fntrace_arm",target=hex(target))
        armed = session.request("fntrace_armed")
        require(armed["count"] == len(TRACE_TARGETS) and {int(t,16) for t in armed["targets"]} == TRACE_TARGETS,
                "Native audio reference trace targets differ")
        observer = Observer(session,report["source"])
        report["banks_before"] = observer.fingerprint_banks(observer.driver())
        report["private_before"] = session.request("spu_private_voices")
        audio.parse_private_voices(report["private_before"])
        require(all(int(v["owner_tag"],16) == 0 and not v["active"] for v in report["private_before"]["voices"]),
                "Co-op-disabled reference contains a private voice reservation")
        jump_records=set()
        required_jumps=set(audio.JUMP_RECORDS[args.character])
        for attempt in range(args.jump_attempts):
            case = dict(label="ground_jump",attempt=attempt+1,status="failed_setup")
            report["cases"].append(case)
            exercise(session,observer,"ground_jump",0x4000,case=case)
            jump_records.update(m['record']['record'] for m in case['matched'] if m['record']['group']==3)
            complete=(required_jumps<=jump_records) if args.all_jump_variants else case["jump_vocal_observed"]
            if complete:
                break
        for label, bits in (("standing_square_attack",0x8000),):
            case = dict(label=label,status="failed_setup")
            report["cases"].append(case)
            exercise(session,observer,label,bits,case=case)
        if contact_audio is not None:
            report['contact_audio']={}
            source=contact_audio.load_source(args.original_exe,args.original_disc,row['stage'])
            observer.event_window=1024  # Strict suffix checks still reject any evicted events.
            contact_audio.exercise(session,observer,source,report['contact_audio'],timeout=args.contact_timeout)
        report["banks_after"] = observer.fingerprint_banks(observer.driver())
        require(report["banks_before"] == report["banks_after"], "Native character bank changed during bounded reference")
        report["checks"] = dict(real_coop_disabled=True, offline=session.offline()["active"] == 0,
                                native_character_confirmed=True, source_matched_banks=True,
                                bounded_jump_attack_reference_actions=True,
                                native_jump_vocal_observed=any(c.get("jump_vocal_observed") for c in report["cases"]))
        report['jump_vocal_records_observed']=sorted(jump_records)
        if args.all_jump_variants:
            report['checks']['all_original_jump_vocal_variants_observed']=required_jumps<=jump_records
        report["final_mod_state"] = reference.validate_reference_profile(profile,args.expected_exe_sha256)
        report["status"] = "bounded_jump_attack_references_observed_hurt_death_unverified"
        if contact_audio is not None:
            report['status']='bounded_jump_attack_hurt_death_references_observed_outcomes_unverified'
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error))
    finally:
        if process is not None:
            client = debug.DebugClient(args.port)
            def owned(command,**fields):
                require(process.poll() is None and baseline.owns_listener(args.port,process.pid),
                        "Owned reference shutdown listener differs")
                return client.request(command,**fields)
            def quit_owned():
                reply = owned("quit")
                require(reply.get("ok") is True, "Owned reference quit was not acknowledged")
            report["cleanup"] = baseline.stop_owned_runtime(process,
                clear_inputs=[lambda:owned("clear_input",port=1)],request_quit=quit_owned)
            cards_after = {p.name:preparation.sha256(p) for p in (profile/"saves").glob("*.mcd")}
            report["native_cards"] = dict(before=cards_before,after=cards_after,
                preserved=all(cards_after.get(k) == v for k,v in cards_before.items()))
            if report["cleanup"].get("shutdown") != "graceful_owned_debug" or report["cleanup"].get("exit_code") != 0 or not report["native_cards"]["preserved"]:
                report["status"] = "cleanup_failed"
        for handle in (rpc_log,stdout,stderr):
            if handle:
                handle.close()
        write_json(output/"qualification.json",report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build","source","disc","original-disc","original-exe","out"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--expected-exe-sha256",required=True)
    parser.add_argument("--expected-manifest-sha256",required=True)
    parser.add_argument("--character",choices=("X","Zero"),required=True)
    parser.add_argument("--allow-private-prerequisite",action="store_true")
    parser.add_argument("--port",type=int,default=17936)
    parser.add_argument("--timeout",type=float,default=90)
    parser.add_argument("--jump-attempts",type=int,default=32)
    parser.add_argument('--all-jump-variants',action='store_true',help='Use bounded original jumps until every character-specific vocal record is observed')
    parser.add_argument('--contact-death',action='store_true')
    parser.add_argument('--contact-timeout',type=float,default=150)
    args = parser.parse_args()
    if not 0 < args.timeout <= 180 or not 1024 <= args.port <= 65535:
        parser.error("Require timeout in (0,180] and an unprivileged TCP port")
    if not 1 <= args.jump_attempts <= 32:
        parser.error("Require one to32 original-input jump attempts; no RNG writes")
    if not 0 < args.contact_timeout <= 180:
        parser.error('Require contact deadline in (0,180]')
    if args.allow_private_prerequisite and args.character != "Zero":
        parser.error("The bounded selector prerequisite applies to Zero only")
    report = run(args)
    print(json.dumps({k:report[k] for k in ("character","status","error","cleanup") if k in report}))
    return 2 if report["status"] in ("bounded_jump_attack_references_observed_hurt_death_unverified",
        'bounded_jump_attack_hurt_death_references_observed_outcomes_unverified') else 1


if __name__ == "__main__":
    raise SystemExit(main())
