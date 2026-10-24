"""Owned published-input X hurt/death and Zero overlap observations.

The parent owns staging, exact-image/manifest binding and process lifecycle.
This module does no launch, guest call, synthetic hit, RAM/audio write or reset.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import time

import coop_debug as debug
import mmx6_coop_body_audio as body
import mmx6_coop_jump_audio as audio
import mmx6_native_contact_audio as contact
import qualify_mmx6_native_audio as native

OBSERVED='primary_audio_observations_complete_outcomes_unverified'
PARTIAL='primary_audio_observations_partial_missing_overlap'
TARGETS={native.SOUND,native.STOP,native.X_BUSTER_INIT,contact.DEATH}
X_REQUIRED={(1,8),(3,0),(3,1),(3,2),(3,3),(3,6),(3,14),(3,16),(3,17)}


def require(ok,message):
    if not ok:raise audio.AudioQualificationError(message)


def sources(exe,disc):
    return dict(x=native.build_source(exe,disc,'X'),zero=body.build_source(exe,disc),
                target=contact.load_source(exe,disc,0))


def player(raw,observation):
    p=body.contact.player_fields(raw)
    p.update(character=raw[2],form=raw[0xE7],x=struct.unpack_from('<i',raw,8)[0],
        y=struct.unpack_from('<i',raw,12)[0],vy=struct.unpack_from('<i',raw,0x24)[0],
        ground=bool(raw[0x70]&8),airborne=struct.unpack_from('<b',raw,0x67)[0],
        previous_terrain=raw[0x89],timer=observation['native_timer'],tick=observation['tick'])
    return p


def context_checks(row):
    o=row['observation'];x,z=row['players']
    require(o['ready']==o['enrolled']==1 and not o['failed'] and not o['mailbox'] and
        o['native_mode']==10 and o['native_phase']==0 and not o['pause_owner'] and not o['scene_owner'],
        'Primary audio left ready native gameplay or armed a mailbox/menu')
    require(o['lifecycle'][0] in (0,4,5) and o['lifecycle'][1]==0 and
        [(p['character'],p['form']) for p in (x,z)]==[(0,1),(1,5)] and 0<z['hp']<=32 and
        z['state']==1,'Primary audio lost fixed roster or living surviving Zero')
    require(x['state'] in (1,2,3) and not contact.hazardous(x) and not contact.hazardous(z),
        'Primary audio reached a terrain hazard or invalid primary phase')


class Observer(audio.AudioObserver):
    def poll(self):
        raw=self.client.read(debug.DIAGNOSTIC_ADDRESS,debug.DIAGNOSTIC_BYTES)
        observation=debug.parse_diagnostic(raw).json()
        total,events=audio.parse_events(self.request('spu_events',count=1024),self.cursor,require_banks=True)
        if self.cursor is not None:self.events.extend(events)
        self.cursor=total
        require(len(self.events)<=16384,'Primary audio event bound exhausted')
        return dict(observation=observation,
            players=[player(raw[0x1800:0x1958],observation),player(raw[0x100:0x258],observation)],
            event_total=total,new_events=events)


def hp_history(rows):
    out=[];last=32
    for row in rows:
        p=row['players'][0]
        if p['pending_hit']:continue
        require(p['hp']<=last,'Primary HP increased/retried during contact route')
        if p['hp']!=last:
            out.append(dict(before=last,after=p['hp'],loss=last-p['hp'],timer=p['timer'],tick=p['tick']))
            last=p['hp']
    require(out and out[-1]['after']==0 and sum(r['loss'] for r in out)==32,
        'Primary contact route lacks complete committed HP32->0 history')
    return out


def overlap_pairs(x_matches,zero_matches,events):
    result={'jump_hurt':[],'saber_hurt':[]}
    hurts=[m for m in x_matches if m['record']['group']==3 and m['record']['record'] in (0,1)]
    for z in zero_matches:
        r=z['record'];family='jump_hurt' if r['group']==3 and r['record'] in (2,4,7) else \
            'saber_hurt' if (r['group'],r['record'])==(3,3) else None
        if family is None:continue
        require(z['event']['v']==44 and z['event']['sample_bank']==31,'Zero overlap vocal lost its private source route')
        zl=audio.lifetime(events,z['event'])
        for x in hurts:
            require(x['event']['v']==20 and x['event']['sample_bank']==0,'Primary hurt vocal lost its native source route')
            xl=audio.lifetime(events,x['event'])
            if xl['disposition']!='natural_end' or zl['disposition']!='natural_end':continue
            start=(z['event']['frame']-x['event']['frame'])&0xFFFFFFFF
            if start>=xl['engine_frames']:continue
            require(x['event']['v']==20 and x['event']['sample_bank']==0 and
                z['event']['v']==44 and z['event']['sample_bank']==31,'Vocal overlap lost independent source routes')
            result[family].append(dict(primary_record=x['record']['record'],zero_record=r['record'],
                primary_event=x['event'],zero_event=z['event'],primary_sha256=x['observed_sha256'],
                zero_sha256=z['observed_sha256'],primary_lifetime=xl,zero_lifetime=zl,
                overlap_engine_frames=min(xl['engine_frames']-start,zl['engine_frames'])))
    return result


def exercise(ctx,contract,source,*,timeout=150):
    mode=ctx['mode'];clients=ctx['clients'];report=ctx['report']
    require(mode in ('local','netplay') and ctx['input_path']=='published_host',
        'Primary audio requires owned published host input')
    require(0<timeout<=180 and re.fullmatch(r'[0-9a-f]{64}',ctx.get('expected_sha256','')),
        'Primary audio needs exact image and bounded deadline')
    if mode=='netplay':
        import mmx6_coop_jump_audio_pair as paired
        paired.validate_context(ctx,ctx['expected_sha256'])
        require(len(clients)==2 and callable(ctx.get('request_peer')),'Primary paired ownership adapter missing')
    else:require(len(clients)==1 and callable(ctx.get('request')),'Primary local ownership adapter missing')
    output=Path(ctx['output']);output.mkdir()
    native.write_json(output/'source-records.json',source)
    (output/'primary-observer-executed-source.py').write_bytes(Path(__file__).read_bytes())
    case=dict(kind='co_op_primary_X_audio_with_surviving_Zero',mode=mode,status='failed_setup',
        candidate_sha256=ctx['expected_sha256'],helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        peers=[dict(peer=i,observations=[],checks={}) for i in range(len(clients))],
        inputs=[],accepted_windows=[],checks={},pending_checks=[],bypasses=[],limits=[
            'Selected X jump/buster, authored intro hurt/death and Zero jump/Saber overlap only; this observer alone does not qualify full R4/R12 or campaign.',
            'Body/lifecycle fields use one coherent diagnostic. Enemy pool, placement, event stream and driver probes are separate owned RPCs.',
            'Waveform/pitch/ADSR and overlapping event lifetimes are observed; no PCM, spatial-volume or independent sample-clock equality claim.',
            'Zero may receive native damage during the route; its full-health preservation and exact damage-caller attribution are not qualified.',
            'No active Saber is held at death; this does not qualify active STOP7 or native state/rewind.'])
    report['primary_audio']=case
    logs=[(output/f'peer-{i}-rpc.jsonl').open('w',encoding='utf-8',newline='\n') for i in range(len(clients))]
    def request(peer,command,**fields):
        result=(ctx['request_peer'](peer,command,**fields) if mode=='netplay' else ctx['request'](command,**fields))
        logs[peer].write(json.dumps(dict(command=command,fields=fields,response=result),separators=(',',':'))+'\n')
        logs[peer].flush();return result
    class ReadClient:
        def __init__(self,index):self.index=index
        def request(self,command,**fields):return request(self.index,command,**fields)
        def read(self,address,count):return debug.DebugClient.read(self,address,count)
    reads=[ReadClient(i) for i in range(len(clients))]
    observers=[Observer(c,c.request,contract,private_banks=ctx['private_banks']) for c in reads]
    x_source=dict(source['x'],records=[r for r in source['x']['records'] if (r['group'],r['record']) in X_REQUIRED])
    probes=[native.Observer(c,x_source) for c in reads]
    target=source['target'];deadline=time.monotonic()+timeout;hold=None;trigger_index=0;last_hp=32

    def take(label):
        require(time.monotonic()<deadline,'Primary audio bounded observation deadline expired')
        rows=[]
        for i,(obs,client) in enumerate(zip(observers,reads)):
            row=obs.poll();row['label']=label;case['peers'][i]['observations'].append(row)
            context_checks(row)
            require(client.read(0x800CCEDC,2)==b'\0\0','Primary audio left original intro stage/section')
            actor,pending,count=contact.target_actor(client.read(contact.enemies.POOL,
                contact.enemies.STRIDE*contact.enemies.SLOTS),target)
            record=client.read(target['record'],8)
            require(contact.placement_matches(bytes.fromhex(target['original_record_hex']),record),
                'Primary audio placement differs beyond original allocation/retry states')
            if actor and row['players'][0]['hp']>0:
                require(actor['phase']==1 and actor['hp']==12 and actor['strength']==4,
                    'Primary contact target changed authored living stats')
            row.update(label=label,actor=actor,pending_initialization=pending,live_enemy_count=count,
                record_hex=record.hex())
            rows.append(row)
        return rows

    def set_input(seat,bits,label):
        receipt=ctx['set_input'](seat,bits)
        case['inputs'].append(dict(label=label,seat=seat,pressed=bits,acknowledgment=receipt))
        return receipt

    def update_hold(rows):
        nonlocal hold
        if hold is None:return
        p=rows[0]['players'][1];o=rows[0]['observation']
        elapsed=(p['timer']-hold['start']['native_timer'])&0xFFFFFFFF
        publications=(o['tick']-hold['start']['tick'])&0xFFFFFFFF
        require(elapsed<=120 and elapsed<0x80000000,'Zero overlap held input exceeded its bound')
        accepted=(p['action']==6 and p['vy']>0 and p['y']<hold['before_y']) if hold['pressed']==audio.CROSS else \
            p['action'] in (0x30,0x32) and any(e['seq']>=hold['event_start'] and e['kind']=='KEYON' and
                e['v']==47 and e['sample_bank']==30 for e in observers[0].events)
        if elapsed>0 and publications>0 and accepted:
            receipt=dict(hold,end=o,actual_native_ticks=elapsed,actual_publications=publications)
            case['accepted_windows'].append(receipt);report.setdefault('accepted_windows',[]).append(receipt)
            set_input(1,0,'release Zero accepted overlap input');hold=None

    def advance(frames,label):
        before=take(label+' start');start=[r['observation'] for r in before]
        for _ in range(400):
            rows=take(label);update_hold(rows)
            deltas=[(r['observation']['native_timer']-s['native_timer'])&0xFFFFFFFF for r,s in zip(rows,start)]
            require(all(d<0x80000000 and d<=240 for d in deltas),'Primary audio native clock regressed/escaped')
            if all(d>=frames for d in deltas):return rows
            time.sleep(.006)
        raise audio.AudioQualificationError('Primary audio native progress bound exhausted')

    failure=None
    try:
        for i,(obs,probe,client) in enumerate(zip(observers,probes,reads)):
            for guard in target['code_guards']:
                require(client.read(guard['address'],guard['bytes']).hex()==guard['source_hex'],
                    'Primary hurt/death/spawner code differs from original source')
            for route in source['x']['child_routes']:
                require(client.read(route['start'],route['bytes']).hex()==route['source_hex'],
                    'Primary X buster initializer differs from original source')
            p=case['peers'][i];p['hardware_banks_before']=probe.fingerprint_banks(probe.driver())
            p['private_banks_before']=obs.fingerprint_banks()
            p['owners_before']=body.voice_leases(request(i,'spu_private_voices'))
            p['driver_before']=probe.driver()
            request(i,'fntrace_arm_clear')
            for t in sorted(TARGETS):request(i,'fntrace_arm',target=hex(t))
            armed=request(i,'fntrace_armed')
            require(armed['count']==len(TARGETS) and {int(t,16) for t in armed['targets']}==TARGETS,
                'Primary audio trace targets differ')
            request(i,'fntrace_clear');obs.poll();p['event_start']=obs.cursor
        initial=take('primary audio initial');case['initial']=initial
        require(all(all(p['hp']==32 for p in r['players']) and r['observation']['lifecycle']==(0,0) and
            all(p['action']==2 and p['ground'] and not p['airborne'] for p in r['players']) for r in initial),
            'Primary audio requires both full-health ground-idle actors')
        ack=set_input(0,body.SQUARE,'standing X buster held')
        held=advance(4,'standing X buster')
        receipt=dict(label='primary-audio-X-Square',seat=0,pressed=body.SQUARE,acknowledgment=ack,
            start=initial[0]['observation'],end=held[0]['observation'])
        case['accepted_windows'].append(receipt);report.setdefault('accepted_windows',[]).append(receipt)
        set_input(0,0,'release standing X buster');advance(60,'standing X buster drain')
        last_x=None;stalled=0;jumps=0
        for step in range(500):
            rows=take('primary authored contact seek');update_hold(rows)
            x,z=rows[0]['players'];actor=rows[0]['actor']
            if not x['pending_hit'] and x['hp']<last_hp:
                last_hp=x['hp']
                if last_hp>0 and hold is None and z['action']==2 and z['ground'] and not z['airborne']:
                    bits=audio.CROSS if trigger_index%2==0 else body.SQUARE;trigger_index+=1
                    ack=set_input(1,bits,'Zero vocal during committed X hurt')
                    hold=dict(label='primary-audio-Zero-'+('Cross' if bits==audio.CROSS else 'Square'),
                        seat=1,pressed=bits,acknowledgment=ack,start=rows[0]['observation'],
                        before_y=z['y'],event_start=observers[0].cursor)
            if all(r['players'][0]['hp']==0 and not r['players'][0]['pending_hit'] for r in rows):
                case['fatal']=rows;break
            stalled=stalled+1 if last_x is not None and abs(x['x']-last_x)<65536 else 0
            bits,frames=contact.seek_input(x,actor,target,stalled,jumps)
            if hold is not None or z['action']!=2 or z['airborne']:
                bits&=~audio.CROSS;frames=4
            if bits&audio.CROSS:jumps+=1
            set_input(0,bits,'X original contact seek')
            try:advance(frames,'primary contact input window')
            finally:set_input(0,0,'release X contact input')
            last_x=x['x']
        else:raise audio.AudioQualificationError('Primary original-input contact route exhausted its step bound')
        set_input(0,0,'primary fatal neutral');set_input(1,0,'survivor neutral');hold=None
        advance(70,'primary death audio drain1');final=advance(70,'primary death audio drain2')
        require(all(r['observation']['lifecycle']==(5,0) and r['players'][0]['hp']==0 for r in final),
            'X did not finish falling while Zero remained alive')
        case['survivor_before_control']=final
        set_input(1,audio.CROSS,'surviving Zero jump')
        hold=dict(label='primary-audio-surviving-Zero-Cross',seat=1,pressed=audio.CROSS,
            start=final[0]['observation'],before_y=final[0]['players'][1]['y'],
            event_start=observers[0].cursor,acknowledgment=case['inputs'][-1]['acknowledgment'])
        advance(8,'surviving Zero jump acceptance')
        require(hold is None,'Surviving Zero did not accept original jump input')
        case['final']=advance(60,'surviving Zero settle')
        for i,(obs,probe,client) in enumerate(zip(observers,probes,reads)):
            p=case['peers'][i];obs.poll();p['events']=obs.events
            p['trace']=native.trace_page(client,targets=TARGETS)
            p['x_samples']=[];p['zero_samples']=[]
            for event in obs.events:
                if event['seq']<p['event_start'] or event['kind']!='KEYON':continue
                if event['sample_bank'] in (30,31):
                    p['zero_samples'].append(body.identify_character(obs,event,source['zero'],p['trace']['entries']))
                elif event['sample_bank']==0 and event['v']<24:
                    m=probe.identify(event,p['trace']['entries'],p['driver_before'])
                    if m:m['lifetime']=audio.lifetime(obs.events,event);p['x_samples'].append(m)
            vocal,effect=contact.death_audio(p['x_samples'])
            hurts=[m for m in p['x_samples'] if m['record']['group']==3 and m['record']['record'] in (0,1)]
            busters=[m for m in p['x_samples'] if (m['record']['group'],m['record']['record'])==(1,8)]
            require(hurts and busters,'Primary case lacks source-matched X hurt or original buster')
            p['hp_changes']=hp_history(p['observations'])
            p['overlaps']=overlap_pairs(p['x_samples'],p['zero_samples'],obs.events)
            p['hardware_banks_after']=probe.fingerprint_banks(probe.driver())
            p['private_banks_after']=obs.fingerprint_banks();p['owners_after']=body.voice_leases(request(i,'spu_private_voices'))
            globals_=[t for t in p['trace']['entries'] if int(t['target'],16)==native.STOP and int(t['a0'],16)==255]
            p['checks']=dict(X_buster_source=True,X_hurt_source=True,X_character_death_vocal_source=True,
                X_character_death_vocal_natural_end=all(m['lifetime']['disposition']=='natural_end' for m in vocal),
                X_death_effect_natural_end_without_global_STOP=all(m['lifetime']['disposition']=='natural_end' for m in effect) and not globals_,
                original_X_banks_preserved=p['hardware_banks_before']==p['hardware_banks_after'],
                private_Zero_banks_preserved=p['private_banks_before']==p['private_banks_after'],
                private_Zero_owners_preserved=p['owners_before']==p['owners_after'],
                Zero_survived_and_accepted_jump=True,complete_primary_HP_history=True)
            require(all(p['checks'].values()),'Primary audio source/bank/owner/death comparison failed')
            for family,matches in p['overlaps'].items():
                if not matches:case['pending_checks'].append(f'peer{i}_{family}_unobserved')
        case['checks']['all_peer_required_checks']=True
        case['status']=PARTIAL if case['pending_checks'] else OBSERVED
        return case
    except BaseException as error:
        failure=error;case.update(error=str(error),error_type=type(error).__name__)
        raise
    finally:
        for seat in (0,1):
            try:set_input(seat,0,'final primary case neutral')
            except Exception as error:
                case.setdefault('input_cleanup_errors',[]).append(str(error))
                if failure is None:case['status']='cleanup_failed'
        for i,(obs,client) in enumerate(zip(observers,reads)):
            p=case['peers'][i]
            if 'events' not in p:p['events']=obs.events
            if 'trace' not in p:
                try:p['trace']=native.trace_page(client,targets=TARGETS)
                except Exception as error:p['trace_error']=str(error)
            try:request(i,'fntrace_arm_clear')
            except Exception as error:
                p['disarm_error']=str(error);case['status']='cleanup_failed'
        for log in logs:log.close()
        native.write_json(output/'observations.json',case)
