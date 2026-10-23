"""Native body-SFX observations; original input only, no audio/RAM writes."""
import hashlib
import json
import re
from pathlib import Path
import time

import audit_mmx6_body_audio_routes as source_routes
import mmx6_coop_jump_audio as audio
import mmx6_coop_contact as contact

SQUARE = 0x8000
TRACE_TARGETS = {0x80016C48,0x8001750C,contact.CONTACT,0x8003D8A8}
VOICE_OWNER = 0x4D4D583650320001
VOICE_MASK = 0xF00B09


def require(ok, message):
    if not ok: raise audio.AudioQualificationError(message)


def build_source(exe_path, disc_path):
    exe, zero, banks = source_routes.original.original_sources(exe_path, disc_path)
    record = source_routes.prove_routes(exe, zero, banks)
    record['all_records'] = source_routes.original.resolve_records(banks)
    for rows in (record['body_records'], record['all_records']):
        for row in rows:
            for tone in row['tones']:
                tone['pitch'] = audio.native_pitch(tone['note'], tone['shift'], tone['center'],
                    tone['shift'], lambda address: exe.word(address) & 0xFFFF)
    return record


def source_digest(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()


def voice_leases(reply):
    audio.parse_private_voices(reply)
    owners=[]
    for row in reply['voices']:
        tag=row.get('owner_tag')
        require(isinstance(tag,str) and re.fullmatch(r'0x[0-9a-fA-F]{16}',tag) is not None,
            'Private voice ownership tag is absent or malformed')
        owners.append(int(tag,16))
    require(sum(1<<slot for slot,owner in enumerate(owners) if owner==VOICE_OWNER)==VOICE_MASK,
        'Private character voice reservations differ from the source-derived mask')
    return owners


def probe_sample(observer,event,tone):
    descriptors=[b for b in observer.private_banks['banks'] if b['bank']==event['sample_bank']]
    require(len(descriptors)==1,'Character event lacks a unique retained source bank')
    descriptor=descriptors[0]
    start,count,size=tone['offset'],tone['bytes'],descriptor['bytes']
    require(0<count<=131072 and start>=0 and start+count<=size,'Character sample escaped its source bank')
    digest=hashlib.sha256()
    for offset in range(0,count,4096):
        digest.update(observer.bank_read(event['sample_bank'],start+offset,min(4096,count-offset),size)['data'])
    observed=digest.hexdigest()
    checks=dict(private_voice_route=event['v']==tone['voice']+24,
        source_sample=observed==tone['sample_sha256'],
        pitch_adsr_numeric=all(event[k]==tone[k] for k in ('pitch','adsr_lo','adsr_hi')),
        original_end_marker_present=tone['first_end_block'] is not None and bool(tone['first_end_flags']&1))
    return observed,checks


def identify_character(observer,event,source,sound_calls):
    require(event['sample_bank'] in (30,31) and 24<=event['v']<48,'Character event is not a retained private-bank voice')
    calls=[r for r in sound_calls if int(r['target'],16)==0x80016C48 and int(r['a2'],16)==0x800970A0 and r['frame']==event['frame']]
    matches=[]
    for record in source.get('all_records',source.get('body_records',[])):
        bank=30 if record.get('effective_bank_group',record['group'])==1 else 31
        if bank!=event['sample_bank']:continue
        if not any((int(c['a0'],16)&127)==record['group'] and (int(c['a1'],16)&255)==record['record'] for c in calls):continue
        for tone in record['tones']:
            if tone['voice']+24==event['v'] and tone['offset']==event['addr']:matches.append((record,tone))
    require(len(matches)==1,'Character event lacks an unambiguous same-frame original body SOUND call')
    record,tone=matches[0];observed,checks=probe_sample(observer,event,tone)
    return dict(record=record,tone=tone,event=event,source_calls=calls,observed_sha256=observed,checks=checks,
        record_selection='event_time_original_sound_call')


def identify(observer, event, source, *, sound_calls=None):
    """Probe every sample byte with bounded reads, using its event-time bank."""
    if event['sample_bank'] != 30: raise audio.AudioQualificationError('Body SFX names a different immutable bank')
    matches = [r for r in source['body_records'] if r['tones'][0]['offset'] == event['addr']]
    calls=[]
    if sound_calls is not None:
        calls=[r for r in sound_calls if int(r['target'],16)==0x80016C48 and int(r['a0'],16)==1 and
            int(r['a2'],16)==0x800970A0 and r['frame']==event['frame'] and
            0x801EA000<=int(r['ra'],16)<0x801EA000+contact.ZERO_SIZE]
        matches=[r for r in matches if any(int(c['a1'],16)==r['record'] for c in calls)]
    if len(matches) != 1: raise audio.AudioQualificationError('Body sample address is absent or ambiguous')
    record = matches[0]; tone = record['tones'][0]
    observed,checks=probe_sample(observer,event,tone)
    return dict(record=record, event=event, observed_sha256=observed, checks=checks,
        source_calls=calls,record_selection='event_time_original_sound_call' if sound_calls is not None else 'unique_sample_source')


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


def trace_page(ctx):
    page=ctx['request']('fntrace_dump',count=4096,seq_lo='0')
    rows=page['entries']
    require(page['seq_lo']==0 and 0<=page['seq_hi']<=4096 and page['emitted']==len(rows) and
        [r['seq'] for r in rows]==list(range(page['seq_hi'])), 'Body audio trace was evicted or incomplete')
    require(all(int(r['target'],16) in TRACE_TARGETS for r in rows),'Body audio trace has an unarmed target')
    return page


def phase2_checks(page,events,*,before_private=None,after_private=None,before_hardware=None,after_hardware=None):
    """Both SDK recorders use the same extern s_frame_count; no clock guess."""
    rows=page['entries'];calls=[]
    for record,ra in ((5,0x8003D8C4),(7,0x8003D8D0)):
        calls.append([r for r in rows if int(r['target'],16)==0x8001750C and
            int(r['a0'],16)==1 and int(r['a1'],16)==record and int(r['ra'],16)==ra])
    frames={r['frame'] for group in calls for r in group}
    checks=dict(original_phase2_stop_calls=all(calls),
        original_phase2_handler=any(int(r['target'],16)==0x8003D8A8 and int(r['a0'],16)==0x800970A0 for r in rows),
        private22_phase2_stop=any(e['v']==46 and e['kind']=='KEYOFF' and e['sample_bank'] in (0,30) and
            any(e['frame']==r['frame']for r in calls[0])for e in events),
        private23_phase2_stop=any(e['v']==47 and e['kind']=='KEYOFF' and e['sample_bank']==30 and
            any(e['frame']==r['frame']for r in calls[1])for e in events),
        p1_hardware22_23_not_stopped=not any(e['v']in (22,23) and e['kind']=='KEYOFF' and e['frame']in frames for e in events))
    if before_private is not None and after_private is not None:
        old=before_private['voices'][23];new=after_private['voices'][23]
        # END_STOP deactivates a silent Release voice. Native STOP still zeros
        # its registers, but SDK correctly emits no KEYOFF for an inactive slot.
        inactive23=(old['active']==0 and old['env']==0 and old['env_phase']==3 and
            old['sample_bank']==30 and (old['vol_l']!=0 or old['vol_r']!=0))
        same23=all(old[k]==new[k]for k in ('sample_bank','start','pitch','adsr_lo','adsr_hi'))
        keys23=[e for e in events if e['v']==47 and e['kind']=='KEYON']
        checks['private23_phase2_stop']|=(bool(calls[1]) and inactive23 and same23 and len(keys23)==1 and
            new['vol_l']==new['vol_r']==new['env']==0 and new['env_phase']==3)
        if before_hardware is not None and after_hardware is not None:
            old22=before_hardware['voices'][22];new22=after_hardware['voices'][22]
            preserved=all(old22[k]==new22[k]for k in ('sample_bank','start','vol_l','vol_r','pitch','adsr_lo','adsr_hi','mode'))
            checks['p1_hardware22_registers_preserved']=preserved and (old22['vol_l']!=0 or old22['vol_r']!=0)
            p22=after_private['voices'][22]
            checks['private22_phase2_stop']|=(bool(calls[0]) and preserved and p22['active']==0 and
                p22['vol_l']==p22['vol_r']==p22['env']==0 and p22['env_phase']==3)
    return checks


def native_death(ctx, sample, observer, case, advance):
    """Seek the original strength4 enemy using input; never write HP/flags."""
    client=ctx['clients'][0];previous=None;selected=None;stalled=0;jumped=False
    route=dict(kind='original_record25_contact_death',observations=[],hp_changes=[],bypasses=[])
    case['native_death']=route
    for step in range(400):
        sample('body-audio-native-contact')
        row=contact.observe_contact(client,ctx['zero_overlay']);route['observations'].append(row)
        o=row['observation'];p1,p2=row['players'];hp=p2['hp'];actor=row['instance']
        require(o['players'][0]['x_raw']==144<<16 and p1['hp_raw']==32 and p1['state']==1,
            'Native death route moved or damaged the surviving primary')
        require(not contact.hazardous(row) or hp==0,'Terrain hazard confounds the native contact death')
        require(row['expected_damage']==4 and row['expected_reaction']==1,'Native contact configuration changed')
        if step==0:
            require(hp==32 and row['p2_contact_counter']==0,'Native death route requires fresh full-health Zero')
        if actor:
            require(actor['phase']==1 and actor['hp']==12 and actor['strength']==4 and actor['subtype']==1 and
                actor['contact_class']==0,'Native authored contact enemy changed')
            if selected is None:selected=actor['address']
            require(actor['address']==selected,'Native contact enemy changed its original slot')
        require(actor is not None or selected is None or hp==0,'Native contact enemy was lost before fatal damage')
        if previous and hp!=previous['players'][1]['hp']:
            require(previous['players'][1]['hp']-hp==4,'Native contact HP loss was not ordinary strength4 damage')
            route['hp_changes'].append(dict(before=previous['players'][1]['hp'],after=hp,
                counter=row['p2_contact_counter'],native_timer=o['native_timer']))
        if hp==0:
            require(row['p2_contact_counter']==8 and len(route['hp_changes'])==8,
                'Native fatal HP loss lacks eight accepted ordinary contacts')
            route['fatal_observation']=row
            ctx['set_input'](1,0)
            for _ in range(31):
                sample('body-audio-phase2-stop')
                observed=phase2_checks(trace_page(ctx),observer.events)
                if observed['original_phase2_stop_calls'] and observed['original_phase2_handler']:return
                advance(2,'body-audio-phase2-stop-drain')
            raise audio.AudioQualificationError('Original phase2 source STOP5/7 calls were not observed')
        positions=o['players'];x=positions[1]['x_raw']
        stalled=stalled+1 if previous and abs(x-previous['observation']['players'][1]['x_raw'])<65536 else 0
        if stalled>=2 and not jumped and x<350<<16 and hp==32:
            bits,frames=0x4020,24;jumped=True
        else:
            dx=(actor['x_raw']-x) if actor else 10<<16
            bits=0x20 if dx>3<<16 else 0x80 if dx<-(3<<16) else 0
            frames=4
        try:
            acknowledgment=ctx['set_input'](1,bits)
            advanced=advance(frames,f'body-audio-contact-seek-{step}')
            route.setdefault('controls',[]).append(dict(pressed=bits,acknowledgment=acknowledgment,
                before=o,after=advanced['observation'],requested_native_ticks=frames))
        finally:ctx['set_input'](1,0)
        previous=row
    raise audio.AudioQualificationError('Bounded original contact route did not reach native phase2 death')


def exercise(ctx, contract, *, source, timeout=90, death=False, **unused):
    if type(timeout) not in (int, float) or not 0 < timeout <= 120:
        raise ValueError('Require a finite bounded body-audio observation deadline')
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'Body audio requires the owned local host route')
    observer = audio.AudioObserver(ctx['clients'][0], ctx['request'], contract, private_banks=ctx['private_banks'])
    report = ctx['report']; deadline = time.monotonic()+timeout
    damage_allowed=False;trace_armed=False
    case = dict(kind='native_zero_body_saber_and_contact_death_audio' if death else 'native_zero_body_saber_audio', status='failed_setup', input_path='published_host',
        source_sha256=source_digest(source), helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        checks={}, observations=[], inputs=[], events=observer.events, limits=[
            'Ordinary Zero saber plus requested contact-death route only; no full R4/R12 or other action-family pass.',
            'Original SOUND/STOP arguments and return addresses traced; s0 is enforced by the compiled guard, not claimed as a trace field.',
            'Inactive STOP may zero volume without KEYOFF. Such evidence never qualifies an active STOP7 lifetime.',
            'Observed character samples require exact original body SOUND and bank bytes; unseen records/PCM/music/cross-machine remain unverified.'])
    report['body_audio'] = case

    def sample(label):
        require(time.monotonic() < deadline, 'Bounded body-audio deadline expired')
        row = observer.poll(); o = row['observation']
        require(o['ready'] == o['enrolled'] == 1 and not o['failed'] and not o['mailbox'] and
            o['native_mode'] == 10 and o['native_phase'] == 0 and not o['scene_owner'] and not o['pause_owner'] and
            o['lifecycle'][0]==0 and (damage_allowed or tuple(o['lifecycle'])==(0,0)), 'Body audio left the owned native gameplay context')
        require([(p['character'],p['form']) for p in row['players']] == [(0,1),(1,5)] and
            row['players'][0]['state']==1 and row['players'][0]['hp']==32 and
            (damage_allowed or row['players'][1]['state']==1 and row['players'][1]['hp']==32),
            'Body audio lost the required native actors or primary health')
        case['observations'].append(dict(label=label, **row)); return row

    def idle(label):
        for attempt in range(31):
            row = sample(label)
            if all(p['action'] == 2 and p['ground'] and not p['airborne'] for p in row['players']): return row
            require(attempt < 30, 'Original actors did not return to ground/idle')
            advance(4, label)

    def advance(frames,label):
        require(type(frames)is int and 1<=frames<=120,'Body audio needs bounded native progress')
        start=sample(label+' start')['observation']
        for _ in range(400):
            row=sample(label);o=row['observation']
            native=(o['native_timer']-start['native_timer'])&0xFFFFFFFF
            publications=(o['tick']-start['tick'])&0xFFFFFFFF
            require(native<0x80000000 and publications<0x80000000,'Body audio clocks regressed')
            if native>=frames and publications>0:return row
            time.sleep(.005)
        raise audio.AudioQualificationError('Body audio native progress bound exhausted')

    failure = None
    try:
        before = idle('body-audio-ground'); case['banks_before'] = observer.fingerprint_banks()
        case['leases_before']=voice_leases(ctx['request']('spu_private_voices'))
        case['hardware_before'] = audio.parse_voices(ctx['request']('spu_voices'), require_banks=True)
        before = sample('body-audio-before-input')
        ctx['request']('fntrace_arm_clear')
        for target in sorted(TRACE_TARGETS):ctx['request']('fntrace_arm',target=hex(target))
        armed=ctx['request']('fntrace_armed')
        require(armed['count']==len(TRACE_TARGETS) and {int(t,16)for t in armed['targets']}==TRACE_TARGETS,
            'Body audio source-call trace arm differs')
        trace_armed=True;ctx['request']('fntrace_clear')
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
        keys = [e for e in observer.events if e['seq'] >= start and e['kind'] == 'KEYON' and e['v'] == 47]
        require(len(keys)==1,'Saber SFX window has missing/reused private47')
        case['sample_trace']=trace_page(ctx)
        case['selected'] = identify(observer, keys[0], source,sound_calls=case['sample_trace']['entries'])
        case['checks'].update(case['selected']['checks'])
        for attempt in range(31):
            row = sample('body-audio-neutral-stop')
            keys = [e for e in observer.events if e['seq'] >= start and e['kind'] == 'KEYON' and e['v'] == 47]
            require(len(keys) == 1, 'Saber SFX window has missing/reused private47')
            ended=audio.lifetime(observer.events,keys[0])['disposition'] in ('natural_end','keyed_off')
            if ended and all(p['action'] == 2 and p['ground'] for p in row['players']): break
            require(attempt < 30, 'Native saber did not terminate and return to idle')
            advance(4, 'body-audio-neutral-drain')
        case['standing_saber_terminal']=audio.lifetime(observer.events,keys[0])
        case['private_before_death']=audio.parse_private_voices(ctx['request']('spu_private_voices'))
        case['standing_saber_vocals']=[]
        driver=observer.driver();case['driver_after_saber']=driver
        for event in observer.events:
            if event['seq']>=start and event['kind']=='KEYON' and event['v']==20:
                try:identity=observer.identify(event,driver)
                except audio.AudioQualificationError as error:identity=dict(sample_matches=False,reason=str(error))
                case['standing_saber_vocals'].append(dict(event=event,identity=identity,
                    scope='Separate vocal ownership observation; does not pass from body SFX'))
        if death:
            damage_allowed=True
            native_death(ctx,sample,observer,case,advance)
        for attempt in range(31):
            case['private_after'] = audio.parse_private_voices(ctx['request']('spu_private_voices'))
            voice = case['private_after']['voices'][keys[0]['v']-24]
            if voice['env'] == 0 and voice['env_phase'] == 3:break
            require(attempt < 30, 'Stopped saber DSP did not reach terminated envelope')
            advance(4, 'body-audio-DSP-drain');sample('body-audio-DSP-drain')
        checks, details = final_checks(observer.events, case['selected'], case['private_after'])
        if death and case['private_before_death']['voices'][23]['active']==0:
            checks.pop('private_native_stop_observed');case['active_phase2_stop7']='unverified: saber naturally ended before death'
        case['checks'].update(checks);case['terminal'] = details
        case['trace']=trace_page(ctx)
        case['character_samples']=[identify_character(observer,event,source,case['trace']['entries'])
            for event in observer.events if event['seq']>=start and event['kind']=='KEYON' and event['sample_bank'] in (30,31) and event['v']>=24]
        case['checks']['observed_character_samples_source_matched']=bool(case['character_samples']) and all(
            all(row['checks'].values()) for row in case['character_samples'])
        case['character_vocals']=[row for row in case['character_samples'] if row['record']['group']==3]
        case['character_vocal_disposition']='observed_source_matched' if case['character_vocals'] else 'unverified_native_rng_no_vocal'
        case['leases_after']=voice_leases(ctx['request']('spu_private_voices'))
        case['checks']['private_voice_leases_stable']=case['leases_before']==case['leases_after']
        case['checks']['original_zero_saber_sound_call']=any(int(r['target'],16)==0x80016C48 and
            int(r['a0'],16)==1 and int(r['a1'],16)==case['selected']['record']['record'] and
            int(r['a2'],16)==0x800970A0 and 0x801EA000<=int(r['ra'],16)<0x801EA000+contact.ZERO_SIZE
            for r in case['trace']['entries'])
        if death:
            case['hardware_after']=audio.parse_voices(ctx['request']('spu_voices'),require_banks=True)
            case['checks'].update(phase2_checks(case['trace'],observer.events,before_private=case['private_before_death'],
                after_private=case['private_after'],before_hardware=case['hardware_before'],after_hardware=case['hardware_after']))
            actor=case['native_death']['fatal_observation']['instance']
            actor=actor or next(r['instance']for r in reversed(case['native_death']['observations'])if r['instance'])
            contacts=[r for r in case['trace']['entries']if int(r['target'],16)==contact.CONTACT]
            case['checks']['original_contact_actor_caller']=bool(contacts) and all(
                int(r['a0'],16)==int(actor['address'],16) and int(r['ra'],16)==contact.CONTACT_RA for r in contacts)
        case['banks_after'] = observer.fingerprint_banks()
        case['checks']['immutable_private_banks_stable'] = case['banks_before'] == case['banks_after']
        case['other_character_voice_events'] = [e for e in observer.events if e['seq'] >= start and e['v'] in (20,44)]
        case['status'] = 'observations_partial' if not death else 'observations_complete' if all(case['checks'].values()) else 'comparison_failed'
        if not death:case['pending_checks']=['Native phase2 STOP5/7; ordinary Square/neutral naturally ends without that trigger']
        return case
    except BaseException as error:
        failure = error;case['error'] = dict(type=type(error).__name__, message=str(error));raise
    finally:
        if trace_armed:
            try:
                if 'trace' not in case:case['trace']=trace_page(ctx)
                ctx['request']('fntrace_arm_clear')
            except Exception as error:
                case['trace_error']=str(error)
                if failure is None:raise
        try:ctx['set_input'](1,0)
        except Exception as error:
            case['neutral_error'] = str(error)
            if failure is None: raise
