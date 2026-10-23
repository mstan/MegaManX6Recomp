"""Native body-SFX observations; original input only, no audio/RAM writes."""
import hashlib
import json
from pathlib import Path
import time

import audit_mmx6_body_audio_routes as source_routes
import mmx6_coop_jump_audio as audio

SQUARE = 0x8000


def require(ok, message):
    if not ok: raise audio.AudioQualificationError(message)


def build_source(exe_path, disc_path):
    exe, zero, banks = source_routes.original.original_sources(exe_path, disc_path)
    record = source_routes.prove_routes(exe, zero, banks)
    for row in record['body_records']:
        tone = row['tones'][0]
        tone['pitch'] = audio.native_pitch(tone['note'], tone['shift'], tone['center'],
            tone['shift'], lambda address: exe.word(address) & 0xFFFF)
    return record


def source_digest(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()


def identify(observer, event, source):
    """Probe every sample byte with bounded reads, using its event-time bank."""
    if event['sample_bank'] != 30: raise audio.AudioQualificationError('Body SFX names a different immutable bank')
    matches = [r for r in source['body_records'] if r['tones'][0]['offset'] == event['addr']]
    if len(matches) != 1: raise audio.AudioQualificationError('Body sample address is absent or ambiguous')
    record = matches[0]; tone = record['tones'][0]
    descriptor = next(b for b in observer.private_banks['banks'] if b['bank'] == 30)
    start, count, size = tone['offset'], tone['bytes'], descriptor['bytes']
    if not 0 < count <= 131072 or start < 0 or start + count > size:
        raise audio.AudioQualificationError('Body sample escaped its source bank')
    digest = hashlib.sha256()
    for offset in range(0, count, 4096):
        digest.update(observer.bank_read(30, start+offset, min(4096, count-offset), size)['data'])
    observed = digest.hexdigest()
    checks = dict(private_voice_route=event['v'] == tone['voice']+24,
        source_sample=observed == tone['sample_sha256'],
        pitch_adsr_numeric=all(event[k] == tone[k] for k in ('pitch', 'adsr_lo', 'adsr_hi')),
        original_end_marker_present=tone['first_end_block'] is not None and bool(tone['first_end_flags'] & 1))
    return dict(record=record, event=event, observed_sha256=observed, checks=checks)


def final_checks(events, selected, private):
    key = selected['event']; row = private['voices'][key['v']-24]
    later = [e for e in events if e['seq'] > key['seq'] and e['v'] == key['v']]
    replaced = any(e['kind'] == 'KEYON' for e in later)
    stops = [e for e in later if e['kind'] == 'KEYOFF' and e['sample_bank'] == key['sample_bank']]
    attributed = not replaced and row['sample_bank'] == key['sample_bank'] and row['pending_bank'] == 0 and row['start'] == key['addr']
    checks = dict(private_native_stop_observed=bool(stops) and not replaced,
        final_dsp_attribution=attributed,
        stopped_volume_zero=attributed and row['vol_l'] == row['vol_r'] == 0,
        final_envelope_terminated=attributed and row['env'] == 0 and row['env_phase'] == 3,
        final_pitch_adsr_numeric=attributed and all(row[k] == key[k] for k in ('pitch', 'adsr_lo', 'adsr_hi')),
        final_noise_off=attributed and not row['mode'] & 1)
    return checks, dict(lifetime=audio.lifetime(events, key), keyoffs=stops, replaced=replaced, snapshot=row)


def exercise(ctx, contract, *, source, timeout=90, **unused):
    if type(timeout) not in (int, float) or not 0 < timeout <= 120:
        raise ValueError('Require a finite bounded body-audio observation deadline')
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'Body audio requires the owned local host route')
    observer = audio.AudioObserver(ctx['clients'][0], ctx['request'], contract, private_banks=ctx['private_banks'])
    report = ctx['report']; deadline = time.monotonic()+timeout
    case = dict(kind='native_zero_body_saber_audio', status='failed_setup', input_path='published_host',
        source_sha256=source_digest(source), helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        checks={}, observations=[], inputs=[], events=observer.events, limits=[
            'Ordinary Zero standing Square/neutral SFX only; no full R4/R12 or other action-family pass.',
            'Private KEYOFF and final volume observed in living gameplay; no individual STOP caller trace is inferred.',
            'Other observed character vocals retain their own unresolved disposition; no PCM/music/cross-machine result.'])
    report['body_audio'] = case

    def sample(label):
        require(time.monotonic() < deadline, 'Bounded body-audio deadline expired')
        row = observer.poll(); o = row['observation']
        require(o['ready'] == o['enrolled'] == 1 and not o['failed'] and not o['mailbox'] and
            o['native_mode'] == 10 and o['native_phase'] == 0 and not o['scene_owner'] and not o['pause_owner'] and
            tuple(o['lifecycle']) == (0, 0), 'Body audio left living native gameplay')
        require([(p['character'],p['form']) for p in row['players']] == [(0,1),(1,5)] and
            all(p['state'] == 1 and p['hp'] == 32 for p in row['players']), 'Body audio lost healthy native X/Zero')
        case['observations'].append(dict(label=label, **row)); return row

    def idle(label):
        for attempt in range(31):
            row = sample(label)
            if all(p['action'] == 2 and p['ground'] and not p['airborne'] for p in row['players']): return row
            require(attempt < 30, 'Original actors did not return to ground/idle')
            ctx['native_advance'](4, label)

    failure = None
    try:
        before = idle('body-audio-ground'); case['banks_before'] = observer.fingerprint_banks()
        case['hardware_before'] = audio.parse_voices(ctx['request']('spu_voices'), require_banks=True)
        before = sample('body-audio-before-input')
        start = observer.cursor; accepted = None
        try:
            acknowledgment = ctx['set_input'](1, SQUARE)
            for _ in range(240):
                row = sample('body-audio-Square-held')
                elapsed = (row['observation']['native_timer']-before['observation']['native_timer']) & 0xFFFFFFFF
                publications = (row['observation']['tick']-before['observation']['tick']) & 0xFFFFFFFF
                require(elapsed <= 120, 'Held Square exceeded its native observation bound')
                if (0 < elapsed < 0x80000000 and 0 < publications < 0x80000000 and
                        row['players'][1]['action'] in (0x30, 0x32) and
                        any(e['seq'] >= start and e['kind'] == 'KEYON' and e['v'] == 47 for e in observer.events)):
                    accepted = row; break
                time.sleep(.005)
            require(accepted is not None, 'No original saber action with private47 KEYON while Square held')
            receipt = dict(label='body-audio-Square', seat=1, pressed=SQUARE,
                acknowledgment=acknowledgment, start=before, end=accepted,
                actual_native_ticks=elapsed, actual_publications=publications)
            case['inputs'].append(receipt);report.setdefault('accepted_windows', []).append(receipt)
        finally:
            ctx['set_input'](1, 0)
        for attempt in range(31):
            row = sample('body-audio-neutral-stop')
            keys = [e for e in observer.events if e['seq'] >= start and e['kind'] == 'KEYON' and e['v'] == 47]
            require(len(keys) == 1, 'Saber SFX window has missing/reused private47')
            stopped = any(e['seq'] > keys[0]['seq'] and e['v'] == 47 and e['kind'] == 'KEYOFF' for e in observer.events)
            if stopped and all(p['action'] == 2 and p['ground'] for p in row['players']): break
            require(attempt < 30, 'Native Square/neutral did not produce a private47 stop and return to idle')
            ctx['native_advance'](4, 'body-audio-neutral-drain')
        case['selected'] = identify(observer, keys[0], source)
        case['checks'].update(case['selected']['checks'])
        for attempt in range(31):
            case['private_after'] = audio.parse_private_voices(ctx['request']('spu_private_voices'))
            voice = case['private_after']['voices'][keys[0]['v']-24]
            if voice['env'] == 0 and voice['env_phase'] == 3:break
            require(attempt < 30, 'Stopped saber DSP did not reach terminated envelope')
            ctx['native_advance'](4, 'body-audio-DSP-drain');sample('body-audio-DSP-drain')
        checks, details = final_checks(observer.events, case['selected'], case['private_after'])
        case['checks'].update(checks);case['terminal'] = details
        case['banks_after'] = observer.fingerprint_banks()
        case['checks']['immutable_private_banks_stable'] = case['banks_before'] == case['banks_after']
        case['other_character_voice_events'] = [e for e in observer.events if e['seq'] >= start and e['v'] in (20,44)]
        case['status'] = 'observations_complete' if all(case['checks'].values()) else 'comparison_failed'
        return case
    except BaseException as error:
        failure = error;case['error'] = dict(type=type(error).__name__, message=str(error));raise
    finally:
        try:ctx['set_input'](1,0)
        except Exception as error:
            case['neutral_error'] = str(error)
            if failure is None: raise
