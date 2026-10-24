"""Current-build native active-audio restore; original input and completed saves.

The owner supplies process/image/manifest validation. No guest writes, synthetic
pause, audio triggers or clock steps are used. Each load starts a new event epoch.
"""
import struct
import time

import coop_debug as debug
import mmx6_coop_body_audio as body
import mmx6_coop_jump_audio as audio
import qualify_mmx6_coop_state as state


SUCCESS = 'bounded_native_active_audio_state_observed'


def require(condition, message):
    if not condition:
        raise debug.DebugError(message)


def active_snapshot(inspection, selected):
    """Actual serialized activity plus source-selected static voice identity."""
    state.require_audio_owner_contract(inspection)
    event = selected['event'];slot = event['v']-24
    require(0 <= slot < 24, 'Source event is not a private voice')
    private = inspection['private_spu'];voice = private['voices'][slot]
    regs = struct.unpack('<8H', bytes.fromhex(private['registers_hex'][slot]))
    checks = dict(active=voice['active'] == 1, audible_envelope=voice['env_level'] > 0,
        source_bank=voice['sample_bank'] == event['sample_bank'],
        source_start=regs[3]*8 == event['addr'], pitch=regs[2] == event['pitch'],
        adsr=regs[4:6] == (event['adsr_lo'], event['adsr_hi']),
        owner=voice['owner_tag'] == f'0x{state.MMX6_AUDIO_OWNER:016x}')
    require(all(checks.values()), 'Saved active character voice differs from source event: '+str(checks))
    return dict(checks=checks,slot=slot,voice=voice,registers=list(regs))


def active_live(reply, selected):
    body.voice_leases(reply)
    voice = audio.parse_private_voices(reply)['voices'][selected['event']['v']-24]
    event = selected['event']
    checks = dict(active=voice['active'] == 1, audible_envelope=voice['env'] > 0,
        source_bank=voice['sample_bank'] == event['sample_bank'],
        source_start=voice['start'] == event['addr'],
        pitch_adsr=all(voice[k] == event[k] for k in ('pitch','adsr_lo','adsr_hi')))
    return all(checks.values()),dict(checks=checks,voice=voice)


def load_boundary_events(checkpoint, first_row):
    """Retain the complete recorder suffix through the first load observation."""
    total=first_row['event_total']
    require(type(checkpoint) is int and type(total) is int and 0<=checkpoint<=total,
        'SPU recorder reset across load; cannot establish an uninterrupted event boundary')
    suffix=[e for e in first_row['new_events'] if e['seq']>=checkpoint]
    require(len(suffix)==total-checkpoint and all(e['seq']==checkpoint+i for i,e in enumerate(suffix)),
        'SPU event suffix was lost across the completed load boundary')
    return suffix


def source_drained(voice, selected, events, first_sequence):
    event=selected['event']
    return (voice['env']==0 and voice['env_phase']==3 and
        voice['sample_bank']==event['sample_bank'] and voice['start']==event['addr'] and
        any(e['seq']>=first_sequence and e['v']==event['v'] and e['sample_bank']==event['sample_bank'] and
            e['kind']=='END_STOP' for e in events))


def exercise(ctx, contract, source, *, output, phase, saved=None, selected=None, timeout=110):
    require(phase in ('warm','cold'), 'Unknown active state phase')
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host',
        'Active state observer needs the owned offline published-input route')
    output.mkdir(parents=True,exist_ok=False)
    case = dict(kind='current_build_active_private_voice_restore',phase=phase,status='failed_setup',
        checks={},observations=[],operations=[],captures=[],event_epochs=[],bypasses=[],
        limits=['Same-image local X/P1 + Zero/P2 intro only.',
            'Original authored enemy contact death; unpaused gameplay; completed save/load RPCs.',
            'Host bodies/clocks/cache may advance between native probe saves; their full differences are retained, not normalized into equality.',
            'No mapped hotkey, rewind, rollback, PCM or native malformed-state qualification.'])
    ctx['report']['active_audio_state'] = case
    deadline = time.monotonic()+timeout
    observer = audio.AudioObserver(ctx['clients'][0],ctx['request'],contract,private_banks=ctx['private_banks'])
    case['event_epochs'].append(dict(label='before-load',events=observer.events))
    request = ctx['request'];client = ctx['clients'][0]
    armed = False

    def sample(label):
        require(time.monotonic()<deadline, 'Bounded active-audio state deadline expired')
        row=observer.poll();o=row['observation']
        require(o['ready']==o['enrolled']==1 and not o['failed'] and not o['mailbox'] and
            o['native_mode']==10 and o['native_phase'] in (0,2) and not o['scene_owner'] and
            [(p['character'],p['form']) for p in row['players']]==[(0,1),(1,5)] and
            row['players'][0]['hp']==32 and row['players'][0]['state']==1,
            'Active state observer lost original roster or surviving primary')
        case['observations'].append(dict(label=label,**row))
        return row

    def wait(predicate,label):
        while time.monotonic()<deadline:
            row=sample(label)
            if predicate(row):return row
            time.sleep(.005)
        raise debug.DebugError(label+': timed out')

    def advance(frames,label):
        before=sample(label+' start')['observation']
        return wait(lambda row: state.forward(before['tick'],row['observation']['tick']) and
            frames <= ((row['observation']['native_timer']-before['native_timer'])&0xffffffff) < 0x80000000,label)

    def drain(label, first_sequence):
        rows=[]
        def quiet(row):
            require(row['observation']['native_phase']==0 and not row['observation']['pause_owner'],
                'Active voice left original unpaused gameplay')
            reply=request('spu_private_voices');body.voice_leases(reply)
            voice=audio.parse_private_voices(reply)['voices'][selected['event']['v']-24]
            rows.append(dict(observation=row['observation'],voice=voice))
            # The separate voice query may see END_STOP one frame after poll's
            # event query. Keep observing until both pieces of evidence exist.
            return source_drained(voice,selected,observer.events,first_sequence)
        wait(quiet,label)
        case.setdefault('drains',[]).append(dict(label=label,observations=rows))

    try:
        sample('healthy original intro')
        case['banks_before']=observer.fingerprint_banks()
        if phase=='warm':
            request('fntrace_arm_clear')
            for target in sorted(body.TRACE_TARGETS):request('fntrace_arm',target=hex(target))
            armed=True;request('fntrace_clear')
            body.native_death(ctx,sample,observer,case,advance)
            def vocal(row):
                calls=body.trace_page(ctx)['entries']
                candidates=[e for e in observer.events if e['kind']=='KEYON' and e['v']==44 and e['sample_bank']==31]
                for event in reversed(candidates):
                    found=body.identify_character(observer,event,source,calls)
                    if (found['record']['group'],found['record']['record'])==(3,16):
                        case['selected']=found
                        return True
                return False
            wait(vocal,'source-selected native Zero death vocal')
            selected=case['selected']
            require(all(selected['checks'].values()), 'Native death vocal source comparison failed')
            state.snapshot_operation(request,'save',8,case['operations'])
            image=state.copy_slot_image(ctx['candidate'],8,output/'snapshot.pst')
            case['saved_snapshot']=image;saved=image['inspection']
            case['saved_active_voice']=active_snapshot(saved,selected)
            case['checks']['source_matched_active_voice_saved']=True
            drain('original death voice drains before warm load',selected['event']['seq']+1)
            case['preload_source_lifetime']=audio.lifetime(observer.events,selected['event'])
            require(case['preload_source_lifetime']['disposition']=='natural_end',
                'Original source voice did not finish naturally before warm load')
            case['trace_before_load']=body.trace_page(ctx)
            request('fntrace_arm_clear');armed=False
        else:
            require(saved is not None and selected is not None,'Cold restore lacks exact warm snapshot/source event')
            case['selected']=selected
            case['saved_active_voice']=active_snapshot(saved,selected)
            reply=request('spu_private_voices')
            require(not active_live(reply,selected)[0], 'Fresh process already contains the selected active death voice')
            case['checks']['fresh_process_lacks_saved_active_voice']=True

        case['status']='failed_behavior'
        checkpoint=observer.cursor
        case['pre_load_event_checkpoint']=checkpoint
        state.snapshot_operation(request,'load',8,case['operations'])
        # Snapshot restore starts a separate diagnostic/event epoch. Never join
        # an old KEYON with a post-load terminal or assume event counters rewind.
        observer=audio.AudioObserver(client,request,contract,private_banks=ctx['private_banks'])
        case['event_epochs'].append(dict(label='after-load',events=observer.events))
        first=sample('first coherent observation after completed load')
        observer.events.extend(load_boundary_events(checkpoint,first))
        anchor=first['observation']['tick']
        case['load_anchor']=anchor
        live=[]
        def restored(row):
            o=row['observation'];reply=request('spu_private_voices');ok,details=active_live(reply,selected)
            live.append(dict(observation=o,**details))
            return o['native_phase']==0 and not o['pause_owner'] and state.forward(anchor,o['tick']) and state.forward(saved['publication_tick'],o['tick']) and ok
        case['restored']=wait(restored,'new gameplay publication with restored active voice')
        case['restored_live_voices']=live
        case['checks']['audible_voice_returns_after_completed_load']=True
        state.snapshot_operation(request,'save',7,case['operations'])
        probe=state.copy_slot_image(ctx['candidate'],7,output/'restored-probe.pst')
        case['restored_provider_probe']=probe
        case['restored_active_voice']=active_snapshot(probe['inspection'],selected)
        comparisons=state.reduce_provider_restore(saved,probe['inspection'])
        case['all_provider_comparisons']=comparisons
        # The simulation is running. Full body/clock/cache equality between
        # different native saves would incorrectly reject genuine progression.
        static_keys=('exact_current_build_key','same_provider_set','same_resource_and_original_asset_binding',
            'persistent_private_audio_priorities','private_spu_owner_tags','private_spu_modes',
            'private_spu_registers_hex','private_spu_bank_bindings')
        case['checks'].update({key:comparisons[key] for key in static_keys})
        before_voice=case['saved_active_voice']['voice'];after_voice=case['restored_active_voice']['voice']
        case['checks']['decoder_resumes_at_or_after_saved_cursor']=after_voice['addr']>=before_voice['addr']
        require(all(case['checks'].values()), 'Loaded static DSP identity or saved decoder cursor differs')
        drain('restored death voice drains naturally in original gameplay',checkpoint)
        terminals=[e for e in observer.events if e['v']==44 and e['sample_bank']==31 and e['kind']=='END_STOP']
        require(terminals and not any(e['v']==44 and e['kind'] in ('KEYON','KEYOFF') for e in observer.events),
            'Restored source voice did not end naturally without replacement or key-off')
        case['checks']['restored_voice_natural_end_without_retrigger']=True
        case['banks_after']=observer.fingerprint_banks()
        require(case['banks_before']==case['banks_after'], 'Immutable source banks changed during native restore')
        case['checks']['immutable_private_source_banks_preserved']=True
        case['captures'].append(debug.capture_present(client,output/'restored-gameplay-after-audio.png',request=request))
        case['status']=SUCCESS
        return case
    finally:
        for seat in (0,1):
            try:ctx['set_input'](seat,0)
            except Exception as error:case.setdefault('cleanup_errors',[]).append(str(error))
        if armed:
            try:request('fntrace_arm_clear')
            except Exception as error:case.setdefault('cleanup_errors',[]).append(str(error))
