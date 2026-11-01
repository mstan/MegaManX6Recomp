"""Named intro-door observations after an explicitly negotiated lab prerequisite.

The only input mutation is ordinary accepted host-pad input. No command8/RAM,
door, HP, position, camera or outcome writes. The agreed initializer is a setup
bypass: strict native recording and ordinary-route qualification remain refused.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import time
import traceback

import coop_debug as debug
import mmx6_coop_checkpoint as checkpoint
import mmx6_coop_hud_presentation as hud


OPTION = 'intro_cp2'
NONCE = 0x4C435032
RECORD = '80072150'


def receipt(client):
    data = client.read(debug.DIAGNOSTIC_ADDRESS + 0xA0, 32)
    if len(data) != 32 or struct.unpack_from('<I', data)[0] != checkpoint.CAPABILITY:
        raise ValueError('Missing native checkpoint publication')
    return dict(generation=struct.unpack_from('<I', data, 4)[0], state=data[8], reason=data[9],
        stage=data[10], section=data[11], checkpoint=data[12], nonce=struct.unpack_from('<I', data, 16)[0],
        initializer_entries=struct.unpack_from('<I', data, 20)[0],
        record=f'{struct.unpack_from("<I", data, 24)[0]:08X}', tainted=data[28],
        authority=data[29], latch=data[30], prior_chord=data[31], raw_hex=data.hex())


def exercise_scene_owner_fatal(ctx, *, output, original_exe, leader, success):
    """F4/F103: agreed prerequisite, original native death/beam outcomes only."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    clients=ctx['clients'];choice=ctx['scene_owner_fatal'];option=3 if choice=='before_release' else 4
    state_tail=bool(ctx.get('scene_owner_state_tail'))
    deadline=time.monotonic()+180
    e=dict(kind='native_scene_owner_fatal',choice=choice,status='failed_setup',samples=[],inputs=[],captures=[],
        checks={},snapshot_operations=[],effects=[dict(births=[],retirements=[],ever_visible=[],visible_retired=[]) for _ in clients],
        bypasses=['Agreed intro_cp2 and predeclared original lock/release/HP80 sequence; all death/beam/recovery outcomes remain native.'],
        limits=['Asynchronous body/pool reads; observed slot transitions are not exact allocation-attempt totals.'])
    ctx['report']['scene_owner_fatal']=e
    previous=[set() for _ in clients];visible=[set() for _ in clients];ever=[set() for _ in clients];retired=[set() for _ in clients]
    def need(ok,why):
        if not ok:raise ValueError(why)
    def inp(seat,bits,label):
        e['inputs'].append(dict(seat=seat,bits=bits,label=label,ack=ctx['set_input'](seat,bits)))
    def sample(label):
        need(time.monotonic()<deadline and len(e['samples'])<2000,'Native scene-fatal deadline')
        row=dict(index=len(e['samples']),label=label,peers=[]);e['samples'].append(row)
        for i,c in enumerate(clients):
            q=hud.state.private_sample(c);o=q['observation'];play=c.read(0x800CCED0,0xE0)
            state=c.read(debug.DIAGNOSTIC_ADDRESS+0xC8,1)[0];pool=c.read(0x800CD410,0x2400)
            allocated={j for j in range(96) if pool[j*0x60]&1 and pool[j*0x60+1]==0x11}
            shown={j for j in allocated if pool[j*0x60+3]}
            eff=e['effects'][i];eff['births']+= [dict(slot=j,tick=o['tick']) for j in sorted(allocated-previous[i])]
            eff['retirements']+=[dict(slot=j,tick=o['tick']) for j in sorted(previous[i]-allocated)]
            ever[i]|=shown;retired[i]|=visible[i]-shown;previous[i]=allocated;visible[i]=shown
            eff.update(ever_visible=sorted(ever[i]),visible_retired=sorted(retired[i]))
            row['peers'].append(dict(peer=i,observation=o,p1_body_hex=q['p1_body_hex'],p2_body_hex=q['p2_body_hex'],
                play_hex=play.hex(),tuple=[play[n] for n in (0,1,12,13,0x1D)],lives=play[0x39],
                native_timer=struct.unpack_from('<I',play,0x90)[0],fixture=receipt(c),fatal_raw=state,
                fatal_option=state&7,fatal_state=state>>3,native_fx_pool=pool.hex(),type11_slots=sorted(allocated),visible_type11_slots=sorted(shown)))
        if len(e['samples'])%16==0 and ctx.get('network'):ctx['network']()
        return row
    def wait(label,predicate,seconds=20):
        stop=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<stop:
            row=sample(label)
            need(not any(p['fixture']['state'] in (4,5) or p['observation']['failed'] for p in row['peers']),'Native prerequisite refused or co-op failed')
            if predicate(row):return row
            time.sleep(.015)
        raise ValueError(label+' timed out')
    def healthy(p):
        o=p['observation'];return o['ready']==o['enrolled']==1 and tuple(o['lifecycle'])==(0,0) and all(a['hp']&127 and a['state']==1 for a in o['players'])
    def recovered(p):
        o=p['observation'];return o['ready']==o['enrolled']==1 and tuple(o['lifecycle'])==(0,5) and not o['scene_owner'] and not o['scene_phase'] and not o['pause_owner'] and o['players'][0]['state']==1 and o['players'][0]['hp']==32 and o['players'][0]['action']==2 and o['players'][1]['hp']==0
    def native_fatal(p):
        o=p['observation']
        # Source-bound option3 requests HP80 only at phase3 and waits native
        # DYING before original release. Correct recovery can prime phase4 in
        # that same pass; asynchronous reads need not retain transient phase3.
        phases=(3,4,5) if option==3 else (4,)
        return p['fatal_option']==option and p['fatal_state']==2 and o['scene_owner']==2 and o['scene_phase'] in phases and o['lifecycle'][1] in (4,5) and o['players'][1]['hp']==0
    def capture(label,row):
        for i,c in enumerate(clients):e['captures'].append(dict(peer=i,label=label,row=row['index'],**debug.capture_present(c,output/f'peer-{i}-{label}.png',request=c.request)))
    def updates(label,count=8):
        old=sample(label+' start')
        return wait(label,lambda r:all((p['observation']['tick']-a['observation']['tick'])&0xffffffff>=count for p,a in zip(r['peers'],old['peers'])))
    try:
        need(hashlib.sha256(Path(original_exe).read_bytes()).hexdigest()=='dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE changed')
        for seat in (0,1):inp(seat,0,'original baseline neutral')
        wait('original fresh idle before agreed checkpoint',lambda r:all(healthy(p) and p['tuple']==[10,0,0,0,0] and all(a['action']==2 for a in p['observation']['players']) for p in r['peers']))
        inp(1,6,'accepted original checkpoint chord')
        try:wait('original checkpoint request consumed',lambda r:all(p['fixture']['latch'] in (1,2) for p in r['peers']))
        finally:inp(1,0,'neutral release between original chords')
        ready=wait('original intro CP2 healthy native arrival',lambda r:all(healthy(p) and p['tuple']==[10,0,0,0,2] and p['fixture']['state']==3 and p['fixture']['generation']==1 and p['fixture']['initializer_entries']==1 and p['fixture']['record']==RECORD and p['fixture']['nonce']==NONCE and p['fixture']['authority']==1 and p['fatal_option']==option and p['fatal_state']==1 and not p['observation']['scene_owner'] for p in r['peers']),90)
        e['ready']=ready['index'];baseline=[(p['lives'],p['tuple'][2:]) for p in ready['peers']]
        inp(1,6,'fresh accepted agreed native scene-fatal chord')
        try:wait('original scene lock admitted',lambda r:all(p['observation']['scene_owner']==2 and p['fatal_state']>=3 for p in r['peers']))
        finally:inp(1,0,'release scene-fatal chord')
        if not state_tail:
            fatal=wait('source-bound original owner native fatal after required sequence',lambda r:all(native_fatal(p) for p in r['peers']))
            e['native_fatal']=fatal['index'];e['native_fatal_observed_phases']=[p['observation']['scene_phase'] for p in fatal['peers']]
            if any(p['visible_type11_slots'] for p in fatal['peers']):capture('native-fatal-effects',fatal)
        else:
            need(len(clients)==1 and option==3,'State tail requires LOCAL before-release selection')
            e['limits'].append('Only missing current-build state/control tail; root must bind retained same-image LOCAL3 native fatal/effect/recovery components separately.')
        row=wait('living original passenger finishes beam and regains native control',lambda r:all(recovered(p) and p['fatal_state']==2 for p in r['peers']),40)
        capture('native-recovered-survivor',row)
        x=[p['observation']['players'][0]['x_raw'] for p in row['peers']]
        inp(0,0x20,'ordinary survivor Right after original scene release')
        try:row=updates('survivor native accepted walk')
        finally:inp(0,0,'release survivor Right')
        need(all(p['observation']['players'][0]['x_raw']>a for p,a in zip(row['peers'],x)),'Survivor control did not move')
        if option==3 and not state_tail:
            quiet=wait('native death effects visibly retire',lambda r:all(recovered(p) and not p['visible_type11_slots'] for p in r['peers']),40)
            births=[len(z['births']) for z in e['effects']]
            row=updates('quiet original world cadence',64)
            for i,(p,a) in enumerate(zip(row['peers'],quiet['peers'])):
                need(e['effects'][i]['births'] and e['effects'][i]['retirements'] and ever[i] and ever[i]<=retired[i] and not p['visible_type11_slots'],'Original effect birth/retirement incomplete')
                need(len(e['effects'][i]['births'])==births[i],'Original death effects keep allocating after recovery')
                dt=(p['observation']['tick']-a['observation']['tick'])&0xffffffff;dw=(p['native_timer']-a['native_timer'])&0xffffffff
                need(dt-2<=dw<=dt+2,'Native free-world cadence changed')
            e['checks']['native_effect_birth_retirement_and_world_cadence']=True
        need(all(recovered(p) and (p['lives'],p['tuple'][2:])==a for p,a in zip(row['peers'],baseline)),'Native lives/checkpoint or survivor state changed')
        if len(clients)==1:
            from qualify_mmx6_coop_state import snapshot_operation
            c=clients[0];saved=row['peers'][0]
            snapshot_operation(c.request,'save',7,e['snapshot_operations'],timeout=20)
            inp(0,0x20,'native survivor movement after current-build SAVE')
            try:updates('native survivor control after SAVE')
            finally:inp(0,0,'release survivor after SAVE')
            snapshot_operation(c.request,'load',7,e['snapshot_operations'],timeout=20)
            wait('current-build scene disposition restored',lambda r:all(recovered(p) and p['observation']['players'][0]['x_raw']==saved['observation']['players'][0]['x_raw'] for p in r['peers']))
            inp(0,0x20,'fresh native survivor walk after LOAD')
            try:row=updates('native survivor control after LOAD')
            finally:inp(0,0,'release survivor after LOAD')
            need(row['peers'][0]['observation']['players'][0]['x_raw']>saved['observation']['players'][0]['x_raw'],'Post-LOAD survivor control absent')
        e['checks'].update(native_passenger_beam_recovery=True,native_survivor_controls=True,no_life_or_checkpoint_reset=True)
        e['checks']['current_build_state_tail' if state_tail else 'source_bound_before_release_native_death' if option==3 else 'native_phase4_owner_death']=True
        e['status']=success;return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc());raise
    finally:
        for seat in (0,1):
            try:inp(seat,0,'final native neutral')
            except Exception:pass
        (output/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf8',newline='\n')


def exercise_subtank_policy(ctx, *, output, original_exe, leader, success):
    """F180: declared supplies cross original CP2, then native owner heals.

    No RAM/mailbox writes or unilateral NET state operations. The selected
    one-shot game prerequisite owns setup; all tested results use native input.
    """
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    clients = ctx['clients']; deadline = time.monotonic()+180
    e = dict(kind='F180_native_independent_subtanks', status='failed_setup',
        samples=[], inputs=[], captures=[], checks={}, snapshot_operations=[],
        bypasses=['Agreed intro_subtank_cp2: first tank acquired, P1 energy16/P2 energy8 before original initializer; HP13/11 afterward.'],
        limits=['Private disposable LAB prerequisites; no naturally earned acquisition, ordinary capture or replay claim.'])
    ctx['report']['F180_subtanks'] = e

    def need(ok, message):
        if not ok: raise ValueError(message)

    def inp(seat, bits, label):
        e['inputs'].append(dict(seat=seat, bits=bits, label=label, ack=ctx['set_input'](seat,bits)))

    def sample(label):
        row=dict(index=len(e['samples']),label=label,peers=[]); e['samples'].append(row)
        need(time.monotonic()<deadline and len(e['samples'])<1800,'F180 native deadline')
        for i,c in enumerate(clients):
            s=hud.state.private_sample(c); play=c.read(0x800CCED0,0xE0)
            bank=c.read(debug.DIAGNOSTIC_ADDRESS+0x1FF0,6)
            row['peers'].append(dict(peer=i,observation=s['observation'],
                p1_body_hex=s['p1_body_hex'],p2_body_hex=s['p2_body_hex'],play_hex=play.hex(),
                tuple=[play[n] for n in (0,1,12,13,0x1D)],bank_hex=bank.hex(),
                policy=list(bank[:2]),banks=list(bank[2:]),acquired=play[0x6B],
                hp=[a['hp'] for a in s['observation']['players']],fixture=receipt(c),
                starting_hp=starting_hp_receipt(c),menu=list(c.read(0x800CF814,2)),cursor=c.read(0x800CF824,1)[0]))
        if len(e['samples'])%16==0 and ctx.get('network'): ctx['network']()
        return row

    def wait(label,predicate,seconds=15):
        stop=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<stop:
            row=sample(label)
            need(all(p['fixture']['state'] not in (4,5) for p in row['peers']),'Agreed Sub Tank prerequisite refused')
            if predicate(row): return row
            time.sleep(.025)
        raise ValueError(label+' timed out')

    def updates(label,count=6):
        old=sample(label+' start')
        return wait(label,lambda r:all((p['observation']['tick']-a['observation']['tick'])&0xFFFFFFFF>=count
            for p,a in zip(r['peers'],old['peers'])))

    def pulse(seat,bits,label):
        inp(seat,bits,label)
        try: updates(label+' accepted input window')
        finally: inp(seat,0,label+' neutral')
        updates(label+' fresh neutral')

    def capture(label,row):
        for i,c in enumerate(clients):
            e['captures'].append(dict(peer=i,label=label,row_index=row['index'],
                **debug.capture_present(c,output/f'peer-{i}-{label}.png',request=c.request)))

    def idle(row,cp):
        return all(p['tuple']==[10,0,0,0,cp] and p['observation']['ready']==p['observation']['enrolled']==1
            and not p['observation']['failed'] and not p['observation']['scene_owner']
            and not p['observation']['pause_owner'] and tuple(p['observation']['lifecycle'])==(0,0)
            and all(a['state']==1 and a['action']==2 and 0<a['hp']<128 for a in p['observation']['players'])
            for p in row['peers'])

    try:
        need(hashlib.sha256(Path(original_exe).read_bytes()).hexdigest()==
            'dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE changed')
        for seat in (0,1): inp(seat,0,'initial neutral')
        wait('actual intro idle before prerequisite',lambda r:idle(r,0),30)
        inp(1,6,'one agreed Sub Tank CP2 chord')
        try: wait('one-shot accepted chord',lambda r:all(p['fixture']['latch'] in (1,2) for p in r['peers']))
        finally: inp(1,0,'release chord')
        ready=wait('actual native CP2 supplies and post-initializer HP',lambda r:idle(r,2)
            and authored_checkpoint_arrivals(r['peers']) and all(p['fixture']['state']==3
                and p['starting_hp']['status']==2 and p['hp']==[13,11] for p in r['peers']),75)
        wanted=dict(generation=1,state=3,reason=0,stage=0,section=0,checkpoint=2,
            nonce=0x4C535432,initializer_entries=1,record=RECORD,tainted=1,authority=1,latch=2)
        need(all(all(p['fixture'].get(k)==v for k,v in wanted.items()) and p['policy']==[1,1]
            and p['banks'][0]==0x90 and p['banks'][2]==0x88 and p['acquired']&0x10
            for p in ready['peers']),'Declared native/private supplies did not survive original initializer')
        e['ready']=ready['index']; capture('native-CP2-filled-private-supplies',ready)
        e['checks']['declared_supplies_acquisition_survive_original_initializer']=True
        for seat,target,energy in ((1,19,8),(0,29,16)):
            before=sample(f'P{seat+1} before native heal')
            pulse(seat,8,f'P{seat+1} native Start')
            wait('settled owned native menu',lambda r:all(p['tuple'][1]==2 and p['menu']==[1,0]
                and p['observation']['pause_owner']==seat+1 for p in r['peers']))
            pulse(seat,0x20,'original Sub Tank cursor Right')
            selected=wait('native Sub Tank selected',lambda r:all(p['cursor']==10 for p in r['peers']))
            capture(f'P{seat+1}-native-tank-selected',selected)
            pulse(seat,0x4000,'original Cross uses only menu owner tank')
            healed=wait('native owner heal and private energy drain',lambda r:all(p['hp'][seat]==target
                and p['banks'][seat*2]==0x80 and p['menu'] in ([1,0],[1,1]) for p in r['peers']),25)
            for p,old in zip(healed['peers'],before['peers']):
                need(p['hp'][seat^1]==old['hp'][seat^1] and p['banks'][(seat^1)*2:(seat^1)*2+2]==old['banks'][(seat^1)*2:(seat^1)*2+2]
                    and p['banks'][seat*2+1]==old['banks'][seat*2+1] and p['acquired']==old['acquired'],
                    'Native heal altered other HP/bank/acquisition')
                need((old['banks'][seat*2]&127)-(p['banks'][seat*2]&127)==energy,'Wrong native energy spend')
            capture(f'P{seat+1}-native-owner-healed',healed)
            pulse(seat,8,'owner resumes original gameplay')
            wait('native owned menu closed',lambda r:all(p['tuple'][1]==0 and not p['observation']['pause_owner'] for p in r['peers']))
            e['checks'][f'P{seat+1}_native_heal_private_drain_and_isolation']=True
        final=sample('both actual native heals complete')
        need(all(p['hp']==[29,19] and p['banks'][0]==p['banks'][2]==0x80
            and all(p['fixture'].get(k)==v for k,v in wanted.items()) for p in final['peers']),
            'Final native private heal result or one-shot receipt changed')
        if len(clients)==1:
            from qualify_mmx6_coop_state import snapshot_operation
            c=clients[0]; saved=final['peers'][0]
            snapshot_operation(c.request,'save',8,e['snapshot_operations'],timeout=20)
            pulse(1,0x80,'native guest movement after warm SAVE')
            snapshot_operation(c.request,'load',8,e['snapshot_operations'],timeout=20)
            restored=wait('warm native supplies and guest position restored',lambda r:all(p['hp']==saved['hp']
                and p['banks']==saved['banks'] and p['observation']['players'][1]['x_raw']==saved['observation']['players'][1]['x_raw']
                for p in r['peers']))
            pulse(1,0x80,'fresh guest control after current-build LOAD')
            moved=sample('restored guest accepted native Left')
            need(moved['peers'][0]['observation']['players'][1]['x_raw']<restored['peers'][0]['observation']['players'][1]['x_raw'],
                'Guest control did not resume after current-build LOAD')
            e['checks']['current_build_warm_restore_and_fresh_guest_control']=True
        e['status']=success;return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc())
        if e['samples']:
            try:capture('terminal-observation',e['samples'][-1])
            except Exception as extra:e['capture_error']=str(extra)
        raise
    finally:
        for seat in (0,1):
            try:inp(seat,0,'final native neutral')
            except Exception as error:e.setdefault('cleanup_errors',[]).append(str(error))
        (output/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf-8')


def exercise_distant_explosion(ctx, *, output, original_exe, leader, success):
    """F158 only: original local burst with a genuinely distant second view."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    clients = ctx['clients']; deadline = time.monotonic()+150
    e = dict(kind='F158_distant_native_explosion', status='failed_setup', samples=[],
        inputs=[], captures=[], checks={}, comparison_admissions=0,
        bypasses=['Existing agreed intro_before_explosion CP1/position/scanner prerequisite; '
                  'hostile-contact protection. Separation and explosion remain native.'],
        limits=['Composed art needs visual review; asynchronous camera/body/effect reads '
                'do not establish instruction-atomic or same-frame peer observations.'])
    ctx['report']['distant_explosion'] = e

    def need(ok, why):
        if not ok: raise ValueError(why)

    def inp(seat, bits):
        e['inputs'].append(dict(seat=seat, bits=bits, ack=ctx['set_input'](seat, bits)))

    def sample(label):
        row = dict(index=len(e['samples']), label=label, peers=[]); e['samples'].append(row)
        need(time.monotonic()<deadline and len(e['samples'])<600, 'F158 native deadline')
        for i, c in enumerate(clients):
            o = hud.state.private_sample(c)['observation']; play = c.read(0x800CCED0, 0xE0)
            pool = c.read(0x8008EF48, 0x1D40); actors=[]
            for at in range(0, len(pool), 0x9C):
                a=pool[at:at+0x9C]
                if len(a)==0x9C and a[0]&1 and a[1:3]==bytes((0,1)) and struct.unpack_from('<I',a,0x10)[0]==0x800FA384:
                    actors.append(dict(address=0x8008EF48+at, hex=a.hex(), action=a[5], phase=a[6]))
            fx = c.read(0x800CD410, 0x2400); effects=[]
            for at in range(0, len(fx), 0x60):
                a=fx[at:at+0x60]
                if a[0]&1 and a[1]==3 and a[0x58] in (7,8,9):
                    effects.append(dict(address=0x800CD410+at, hex=a.hex(), origin=struct.unpack_from('<I',a,0x54)[0]))
            row['peers'].append(dict(peer=i, observation=o, tuple=[play[n] for n in (0,1,12,13,0x1D)],
                fixture=receipt(c), producers=actors, effects=effects))
        if len(e['samples'])%16==0 and ctx.get('network'): ctx['network']()
        return row

    def healthy(row):
        return all(not p['observation']['failed'] and not p['observation']['mailbox']
            and tuple(p['observation']['lifecycle'])==(0,0)
            and all(a['active'] and a['state']==1 and a['hp']&127 for a in p['observation']['players'])
            for p in row['peers'])

    def wait(label, predicate, seconds):
        stop=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<stop:
            row=sample(label)
            need(not any(p['fixture']['state'] in (4,5) for p in row['peers']), 'Original fixture refused')
            if predicate(row): return row
            time.sleep(.02)
        raise ValueError(label+' timed out')

    def capture(label, row):
        for i,c in enumerate(clients):
            trace=c.request('fn_entry_dump',seq_lo='0',count=256)
            e.setdefault('draw_contexts',[]).append(dict(peer=i,label=label,trace=trace))
            e['captures'].append(dict(peer=i,label=label,row_index=row['index'],
                **debug.capture_present(c,output/f'peer-{i}-{label}.png',request=c.request)))
            c.request('fn_clear')

    try:
        need(hashlib.sha256(Path(original_exe).read_bytes()).hexdigest()==
             'dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE changed')
        for seat in (0,1): inp(seat,0)
        wait('original idle before agreed setup',lambda r:healthy(r) and all(p['tuple']==[10,0,0,0,0]
            and all(a['action']==2 for a in p['observation']['players']) for p in r['peers']),20)
        inp(1,6)
        try: wait('one agreed chord',lambda r:all(p['fixture']['latch'] in (1,2) for p in r['peers']),15)
        finally: inp(1,0)
        ready=wait('original explosion prerequisite ready',lambda r:healthy(r) and all(p['fixture']['state']==3
            and p['tuple']==[10,0,0,0,1] for p in r['peers']),30)
        for c in clients:
            need(hashlib.sha256(c.read(0x800E9F1C,0x2BC)).hexdigest()==
                 '5704e34728d15883afe3d557d1b27bfd97e78ec138a04160612d42a44283db90','Original explosion source changed')
            c.request('fn_disable'); c.request('fn_clear'); c.request('fn_filter',lo='80025FB0',hi='80025FB4')
        e['ready']=ready['index']
        # Standard host pad Right+Circle. This is original dash travel, never a body write.
        inp(1,0x2020)
        try:
            separated=wait('guest native dash to distant viewport',lambda r:healthy(r) and all(
                p['observation']['players'][1]['x_raw']>=5120*65536 for p in r['peers']),25)
        finally: inp(1,0)
        need(healthy(separated),'Distant approach lost a hero')
        e['separated']=separated['index']; capture('distant-before-burst',separated)
        seen=0
        stop=min(deadline,time.monotonic()+35)
        while time.monotonic()<stop and seen<4:
            row=sample('distant original burst'); need(healthy(row),'Native burst lost a hero')
            if all(any(a['origin'] in {p['address'] for p in peer['producers']} for a in peer['effects'])
                   for peer in row['peers']):
                capture('distant-burst-'+str(seen),row); seen+=1
            time.sleep(.02)
        need(seen>=2,'No source-owned original burst while views were distant')
        final=sample('distant native final'); capture('distant-after-burst',final)
        need(all(p['observation']['players'][0]['x_raw']==ready['peers'][i]['observation']['players'][0]['x_raw']
            for i,p in enumerate(final['peers'])),'Neutral primary moved during distant burst')
        for record in e['draw_contexts']:
            seats={((x['context']['flags']>>1)&1) for x in record['trace']['entries']
                if x['context']['available'] and x['context']['provider']==0x36564350 and x['context']['flags']&1}
            need(seats=={0,1},'Missing actual independent draw cameras')
        e['checks']=dict(native_guest_separation=True,source_owned_native_burst=True,
            primary_stays_fixed=True,both_native_draw_views_observed=True)
        e['status']=success
        return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc())
        try: capture('terminal-observation',e['samples'][-1])
        except Exception as extra: e['capture_error']=str(extra)
        raise
    finally:
        for seat in (0,1):
            try: inp(seat,0)
            except Exception: pass
        for c in clients:
            try: c.request('fn_disable')
            except Exception: pass
        (output/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf-8')


def exercise_final_retry_continue(ctx, *, output, original_exe, leader, success):
    """F136: actual Sigma retry/Continue, using the existing owned pad routes."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    clients = ctx['clients']; deadline = time.monotonic()+1800
    e = dict(kind='F136_native_final_retry_GameOver_Continue', status='failed_setup',
        samples=[], inputs=[], captures=[], checks={}, controls=[], network_windows=[],
        comparison_admissions=0,
        bypasses=['One agreed Sigma12/1CP1 entry and initial HP1/1 only; contact protection off.'],
        limits=['Asynchronous native observations; no instruction-atomic peer sampling.',
                'Same-image LOCAL current-build save/load is retained separately; no unilateral NET state load, replay or rollback qualification.'])
    ctx['report']['final_retry_continue'] = e

    def need(ok, why):
        if not ok: raise ValueError(why)

    def inp(seat, bits, label):
        need(seat in (0, 1) and bits in (0, 6, 8, 0x20, 0x80, 0x4000), 'Only ordinary named host-pad buttons')
        e['inputs'].append(dict(seat=seat, bits=bits, label=label, ack=ctx['set_input'](seat, bits)))

    def sample(label):
        row = dict(index=len(e['samples']), label=label, peers=[])
        e['samples'].append(row)
        need(time.monotonic()<deadline, 'F136 progressing native observation deadline')
        for i, c in enumerate(clients):
            raw=c.read(debug.DIAGNOSTIC_ADDRESS, debug.DIAGNOSTIC_BYTES)
            o=debug.parse_diagnostic(raw).json(); p=c.read(0x800CCED0, 0xE0)
            ptr=struct.unpack_from('<I',p,0x20)[0]; boss=None
            if 0x8008EF48<=ptr<0x80090C88 and (ptr-0x8008EF48)%0x9C==0:
                a=c.read(ptr,0x9C)
                if a[0]&1 and a[1]==61 and struct.unpack_from('<I',a,0x10)[0]==0x800F57EC:
                    boss=dict(address=ptr,type=a[1],state=a[4],action=a[5],hp=a[0x5C],hex=a.hex())
            row['peers'].append(dict(peer=i,observation=o,play_hex=p.hex(),
                tuple=[p[n] for n in (0,1,12,13,0x1D)],lives=struct.unpack_from('<b',p,0x39)[0],
                fixture=receipt(c),starting_hp=starting_hp_receipt(c),boss=boss,
                native_ui_hold=c.read(0x80097424,1)[0],
                dialogue_hex=c.read(0x8008EAF0,16).hex(),
                p1_body_hex=raw[0x1800:0x1958].hex(),p2_body_hex=raw[0x100:0x258].hex()))
            need(not o['failed'] and not o['mailbox'], 'Native plugin failure or diagnostic mutation')
        if len(e['samples'])%16==0 and ctx.get('network'):
            e['network_windows'].append(dict(row=row['index'],peers=ctx['network']()))
        return row

    def healthy(p):
        o=p['observation']
        return (o['ready']==o['enrolled']==1 and tuple(o['lifecycle'])==(0,0)
            and all(a['active'] and a['state']==1 and 0<a['hp']<=127 for a in o['players']))

    def wait(label, predicate, seconds):
        stop=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<stop:
            row=sample(label)
            need(not any(p['fixture']['state'] in (4,5) for p in row['peers']), 'Agreed original prerequisite refused')
            if predicate(row): return row
            time.sleep(.04)
        raise ValueError(label+' timed out')

    def updates(label, count=8):
        # Dialogue holds stop the world clock. Consume actual emulation frames,
        # including the negotiated pad delay, before making another input edge.
        online=len(clients)==2 and ctx.get('network')
        starts=ctx['network']() if online else [c.request('freeze_check',window=1)['frame_count'] for c in clients]
        stop=min(deadline,time.monotonic()+20)
        while time.monotonic()<stop:
            row=sample(label)
            now=ctx['network']() if online else [c.request('freeze_check',window=1)['frame_count'] for c in clients]
            consumed=(all(n['resolved_through']>=s['tick']+count for n,s in zip(now,starts)) if online
                else all(((n-s)&0xFFFFFFFF)>=count for n,s in zip(now,starts)))
            if consumed: return row
            time.sleep(.025)
        raise ValueError(label+' did not consume native frames')

    def capture(label, row):
        for i,c in enumerate(clients):
            e['captures'].append(dict(peer=i,label=label,row_index=row['index'],
                **debug.capture_present(c,output/f'peer-{i}-{label}.png',request=c.request)))

    def released(row):
        return all(p['tuple']==[10,0,12,1,1] and healthy(p)
            and not p['observation']['scene_owner'] and not p['observation']['scene_phase']
            and p['boss'] and p['boss']['state']==1 and p['boss']['hp']==48 for p in row['peers'])

    def controls(label):
        for seat in (0,1):
            accepted=None
            # Right is the already-qualified post-intro route; Left can meet
            # original room admission/collision bounds and is only a fallback.
            for bits in (0x20,0x80):
                before=sample(label+f' seat{seat} before ordinary walk')
                starts=[c.request('freeze_check',window=1)['frame_count'] for c in clients]
                inp(seat,bits,label+' actual owned movement')
                stop=min(deadline,time.monotonic()+8)
                try:
                    while time.monotonic()<stop:
                        row=sample(label+f' seat{seat} native movement')
                        good=[]
                        for old,p in zip(before['peers'],row['peers']):
                            a=old['observation']['players'][seat]; b=p['observation']['players'][seat]
                            dx=b['x_raw']-a['x_raw']
                            good.append(healthy(p) and not p['observation']['scene_owner']
                                and b['hp']==a['hp'] and b['action'] in (3,4,5)
                                and (dx < -2*65536 if bits==0x80 else dx > 2*65536))
                        if all(good): accepted=row; break
                        if any(p['observation']['players'][seat]['hp'] != old['observation']['players'][seat]['hp']
                                for old,p in zip(before['peers'],row['peers'])):
                            before=row  # A hurt displacement is not our movement witness.
                        now=[c.request('freeze_check',window=1)['frame_count'] for c in clients]
                        if all(((n-s)&0xFFFFFFFF)>=32 for n,s in zip(now,starts)):
                            break
                        time.sleep(.025)
                finally: inp(seat,0,label+' release actual movement')
                if accepted is not None: break
            need(accepted is not None,label+' missing accepted control for seat'+str(seat))
            e['controls'].append(dict(label=label,seat=seat,before=before['index'],accepted=accepted['index'],bits=bits))
            updates(label+' neutral input separation')
        row=sample(label+' both accepted controls complete'); capture(label+'-both-controls',row)
        return row

    def enter_final(label, require_controls):
        inp(0,0x20,label+' original primary Right door approach')
        try:
            row=wait(label+' original door/scene',lambda r:any(p['observation']['scene_owner']
                or p['boss'] for p in r['peers']),45)
        finally: inp(0,0,label+' release original approach')
        e.setdefault('scene_entries',[]).append(dict(label=label,row=row['index']))
        stop=min(deadline,time.monotonic()+150)
        while time.monotonic()<stop:
            row=sample(label+' original Sigma intro/fill/release')
            if released(row): break
            # The first HP1 pair may die immediately on original release. Its
            # purpose is the real retry; post-retry/Continue require both controls.
            if not require_controls and all(p['boss'] and p['boss']['hp']==48 for p in row['peers']): break
            owner=row['peers'][0]['observation']['scene_owner']
            if owner in (1,2) and all(p['observation']['scene_owner']==owner
                    and p['observation']['players'][owner-1]['action']==20
                    and bytes.fromhex(p['dialogue_hex'])[12:14]==bytes((255,3)) for p in row['peers']):
                inp(owner-1,0x4000,label+' original owning Cross dialogue edge')
                try: updates(label+' consumed original dialogue Cross')
                finally: inp(owner-1,0,label+' release original dialogue Cross')
                updates(label+' consumed dialogue neutral')
            time.sleep(.04)
        else: raise ValueError(label+' original final intro did not release')
        e.setdefault('boss_activations',[]).append(dict(label=label,row=row['index']))
        if require_controls:
            need(released(row),label+' did not release actual first61/full48HP with both living heroes')
            return controls(label)
        return row

    def wipe(old_lives, label, retry):
        for seat in (0,1): inp(seat,0x20,label+' native boss contact; no attacks')
        try:
            row=wait(label+' actual native team death/life decrement',lambda r:all(
                p['lives']==old_lives-1 for p in r['peers']),240)
        finally:
            for seat in (0,1): inp(seat,0,label+' release contact approach')
        e.setdefault('native_wipes',[]).append(dict(label=label,old_lives=old_lives,row=row['index']))
        if retry:
            row=wait(label+' original fresh checkpoint pair',lambda r:all(p['tuple']==[10,0,12,1,1]
                and p['lives']==old_lives-1 and healthy(p) and all(a['hp']==32
                    for a in p['observation']['players']) for p in r['peers']),90)
            e.setdefault('native_retries',[]).append(dict(label=label,row=row['index']))
        return row

    try:
        exe=Path(original_exe).read_bytes()
        need(hashlib.sha256(exe).hexdigest()=='dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE changed')
        for address,size in ((0x8001E634,0x18),(0x80050250,0x324),(0x80050C88,0x174)):
            expected=exe[address-0x80010000+2048:address-0x80010000+2048+size]
            need(all(c.read(address,size)==expected for c in clients),'Original retry/door source changed')
        for seat in (0,1): inp(seat,0,'original baseline neutral')
        wait('original intro idle before once-only Sigma setup',lambda r:all(healthy(p)
            and p['tuple']==[10,0,0,0,0] and all(a['action']==2 for a in p['observation']['players'])
            and p['fixture']['generation']==p['fixture']['latch']==0 for p in r['peers']),30)
        inp(1,6,'one accepted guest L3+R3 Sigma prerequisite')
        try: wait('once-only Sigma chord consumed',lambda r:all(p['fixture']['latch'] in (1,2) for p in r['peers']),20)
        finally: inp(1,0,'release the only checkpoint chord')
        wanted=dict(generation=1,state=3,reason=0,stage=12,section=1,checkpoint=1,
            nonce=0x4C534731,initializer_entries=1,record='80072C00',tainted=1,authority=1,latch=2)
        row=wait('original Sigma CP1 initial native HP1 pair',lambda r:all(healthy(p)
            and p['tuple']==[10,0,12,1,1] and all(p['fixture'].get(k)==v for k,v in wanted.items())
            and p['starting_hp']==dict(status=2,requested=[1,1],applied_mask=3,raw_hex='02010103')
            and all(a['hp']==1 for a in p['observation']['players']) for p in r['peers']),120)
        need(all(p['lives']==2 for p in row['peers']),'Expected genuine original two-life budget')
        e['initial']=row['index']; enter_final('initial-final',False)
        wipe(2,'first-team-retry',True); enter_final('after-team-retry',True)
        wipe(1,'remaining-team-retry',True); enter_final('zero-life-final',False)
        wipe(0,'literal-GameOver',False)
        row=wait('literal native GameOver Continue page',lambda r:all(p['tuple'][:2]==[13,1]
            and p['lives']==-1 and p['native_ui_hold']==0 for p in r['peers']),60)
        e['literal_GameOver']=row['index']; capture('literal-GameOver-Continue',row)
        updates('original Continue ready neutral input separation')
        inp(0,0x4000,'primary selects actual default Continue the game')
        try: updates('actual original Continue confirmation')
        finally: inp(0,0,'release original Continue')
        row=wait('actual Continue fresh final checkpoint',lambda r:all(p['tuple']==[10,0,12,1,1]
            and p['lives']==2 and healthy(p) and all(a['hp']==32 for a in p['observation']['players'])
            for p in r['peers']),120)
        e['actual_Continue']=row['index']; enter_final('after-Continue',True)
        final=sample('F136 final native endpoint')
        need(all(all(p['fixture'].get(k)==v for k,v in wanted.items()) for p in final['peers']),
            'A repeated checkpoint initializer or changed prerequisite was observed')
        e['checks']=dict(actual_team_retry=True,original_final_intro_after_retry=True,
            first61_fullHP_and_both_controls_after_retry=True,literal_GameOver_Continue=True,
            actual_native_Continue=True,original_final_intro_after_Continue=True,
            first61_fullHP_and_both_controls_after_Continue=True,no_repeated_initializer=True)
        e['status']=success
        return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc())
        if e['samples']:
            try: capture('terminal-native-observation',e['samples'][-1])
            except Exception as extra: e['capture_error']=str(extra)
        raise
    finally:
        for seat in (0,1):
            try: inp(seat,0,'final native neutral')
            except Exception as error: e.setdefault('cleanup_errors',[]).append(str(error))
        (output/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf-8')


def exercise_midboss_forward(ctx, *, output, original_exe, leader, success):
    """F166/F187 separately: fresh Both midboss fight, door, then CP plane."""
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    clients=ctx['clients']; deadline=time.monotonic()+1800
    e=dict(kind='F166_F187_native_Magma_midboss_forward',status='failed_setup',samples=[],
        inputs=[],captures=[],checks={},comparison_admissions=0,comparisons={'F166':{'status':'unverified'},'F187':{'status':'unverified'}},
        bypasses=['One agreed original Magma3/0CP0 entry; contact protection and earned weapons only. Doors Both.'],
        limits=['Independent row dispositions; a passenger warp cannot qualify F166.',
                'Asynchronous native observations, not instruction-atomic samples. No NET state load.'])
    ctx['report']['midboss_forward']=e; seen_main=[False]*len(clients)

    def need(ok,why):
        if not ok: raise ValueError(why)

    def inp(seat,bits,label):
        need(seat in (0,1) and bits in (0,6,0x20,0x80,0x200,0x4000,0x8000,0x2020,0x4020,0x6020,0x8020,0x8080),'Ordinary declared host-pad input only')
        e['inputs'].append(dict(seat=seat,bits=bits,label=label,ack=ctx['set_input'](seat,bits)))

    def sample(label):
        row=dict(index=len(e['samples']),label=label,peers=[]); e['samples'].append(row)
        need(time.monotonic()<deadline,'Midboss native progress hard deadline')
        for i,c in enumerate(clients):
            raw=c.read(debug.DIAGNOSTIC_ADDRESS,debug.DIAGNOSTIC_BYTES);o=debug.parse_diagnostic(raw).json()
            play=c.read(0x800CCED0,0xE0);pool=c.read(0x8008EF48,48*0x9C);snake=[]
            for n in range(48):
                a=pool[n*0x9C:(n+1)*0x9C]
                if a[1]==0x19 and a[2]<=5:
                    snake.append(dict(address=0x8008EF48+n*0x9C,active=bool(a[0]&1),subtype=a[2],
                        visible=a[3],state=a[4],action=a[5],phase=a[6],hp=a[0x5C],
                        x=struct.unpack_from('<i',a,8)[0]/65536,y=struct.unpack_from('<i',a,12)[0]/65536,hex=a.hex()))
            main=[a for a in snake if a['subtype']==5 and a['active']]
            if any(a['hp']>0 and a['state']==1 for a in main): seen_main[i]=True
            door=c.read(0x800C1220,0xA4)
            row['peers'].append(dict(peer=i,observation=o,tuple=[play[n] for n in (0,1,12,13,0x1D)],
                play_hex=play.hex(),fixture=receipt(c),snake=snake,main=main,
                door=dict(address=0x800C1220,active=bool(door[0]&1),type=door[1],subtype=door[2],
                    state=door[4],action=door[5],hex=door.hex()),
                p1_body_hex=raw[0x1800:0x1958].hex(),p2_body_hex=raw[0x100:0x258].hex(),
                dialogue_hex=c.read(0x8008EAF0,16).hex()))
            need(not o['failed'] and not o['mailbox'],'Native plugin failure or diagnostic mutation')
        if len(e['samples'])%16==0 and ctx.get('network'): ctx['network']()
        return row

    def healthy(p):
        o=p['observation']
        return o['ready']==o['enrolled']==1 and tuple(o['lifecycle'])==(0,0) and all(
            a['active'] and a['state']==1 and 0<a['hp']<=127 for a in o['players'])

    def wait(label,predicate,seconds):
        stop=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<stop:
            row=sample(label)
            if predicate(row): return row
            time.sleep(.04)
        raise ValueError(label+' timed out')

    def updates(label,count):
        online=len(clients)==2 and ctx.get('network')
        start=ctx['network']() if online else [c.request('freeze_check',window=1)['frame_count'] for c in clients]
        stop=min(deadline,time.monotonic()+40)
        while time.monotonic()<stop:
            row=sample(label)
            now=ctx['network']() if online else [c.request('freeze_check',window=1)['frame_count'] for c in clients]
            if (all(n['resolved_through']>=s['tick']+count for n,s in zip(now,start)) if online
                    else all(((n-s)&0xFFFFFFFF)>=count for n,s in zip(now,start))): return row
            time.sleep(.025)
        raise ValueError(label+' native input window did not progress')

    def hold(seat,bits,count,label):
        inp(seat,bits,label)
        try: return updates(label,count)
        finally: inp(seat,0,label+' neutral')

    def capture(label,row):
        for i,c in enumerate(clients):
            e['captures'].append(dict(peer=i,label=label,row_index=row['index'],
                **debug.capture_present(c,output/f'peer-{i}-{label}.png',request=c.request)))

    def defeated(row):
        result=[]
        for i,p in enumerate(row['peers']):
            main=p['main']; weak=[a for a in p['snake'] if a['subtype']<4]
            main_done=not main or all(a['hp']==0 and (a['state'],a['action'],a['phase'])==(3,8,4) for a in main)
            result.append(seen_main[i] and main_done and not any(a['active'] and a['visible'] for a in weak))
        return all(result)

    try:
        need(hashlib.sha256(Path(original_exe).read_bytes()).hexdigest()==
            'dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE changed')
        for seat in (0,1): inp(seat,0,'original baseline neutral')
        wait('original intro idle before Magma prerequisite',lambda r:all(healthy(p)
            and p['tuple']==[10,0,0,0,0] and all(a['action']==2 for a in p['observation']['players'])
            and p['fixture']['generation']==p['fixture']['latch']==0 for p in r['peers']),30)
        inp(1,6,'one agreed heatnix_cp0 chord')
        try: wait('Magma chord accepted',lambda r:all(p['fixture']['latch'] in (1,2) for p in r['peers']),20)
        finally: inp(1,0,'release the only checkpoint chord')
        row=wait('original Magma CP0 pair and earned weapons ready',lambda r:all(healthy(p)
            and p['tuple']==[10,0,3,0,0] and p['fixture']['generation']==p['fixture']['initializer_entries']==1
            and p['fixture']['state']==3 and p['fixture']['nonce']==0x4C484E30
            and p['observation']['players'][1]['ammo'][5]==288 for p in r['peers']),120)
        e['initial']=row['index']
        for window in range(2):
            for seat in (0,1): inp(seat,0x2020,'native dual Right Circle approach'+str(window))
            try: updates('actual original Magma approach',60)
            finally:
                for seat in (0,1): inp(seat,0,'release approach for native HELP')
        stop=min(deadline,time.monotonic()+150)
        while time.monotonic()<stop:
            row=sample('original HELP intro and actual Snake activation')
            if all(healthy(p) and not p['observation']['scene_owner'] and p['main']
                    and any(a['hp']>0 and a['state']==1 and a['action']==3 for a in p['main'])
                    and any(a['subtype']<4 and a['active'] and a['visible'] and a['state']==1 and a['hp']>0 for a in p['snake'])
                    for p in row['peers']): break
            owner=row['peers'][0]['observation']['scene_owner']
            if owner in (1,2) and all(bytes.fromhex(p['dialogue_hex'])[12:14]==bytes((255,3)) for p in row['peers']):
                hold(owner-1,0x4000,8,'original owning HELP dialogue Cross'); updates('HELP neutral separation',8)
            time.sleep(.04)
        else: raise ValueError('Actual native HELP did not release the active midboss')
        e['actual_activation']=row['index'];capture('actual-native-midboss-active',row)
        for cast in range(3):
            if defeated(row): break
            if all(not any(a['subtype']<4 and a['active'] and a['visible'] and a['hp']>0
                    for a in p['snake']) and all(a['hp']==0 for a in p['main']) for p in row['peers']):
                row=wait('original main death completes after weakpoints retire',defeated,45);break
            wait('Zero native idle before active Giga',lambda r:all(healthy(p)
                and p['observation']['players'][1]['action']==2 for p in r['peers']),60)
            hold(1,0x200,12,'actual active guest R2 Giga'+str(cast));updates('release Giga edge',8)
            row=wait('native Giga action completes',lambda r:defeated(r) or all(healthy(p)
                and p['observation']['players'][1]['action']==2 for p in r['peers']),90)
        if not defeated(row):
            hold(1,0x6020,60,'proven guest Right Cross Circle to arena melee floor')
            updates('native melee approach neutral',8)
            for attack in range(80):
                row=sample('native surviving weakpoint contact')
                if defeated(row): break
                need(all(healthy(p) for p in row['peers']),'Combat lost a living actor')
                weak=[a for a in row['peers'][0]['snake'] if a['subtype']<4 and a['active'] and a['visible'] and a['hp']>0]
                if not weak:
                    row=wait('original Snake death/retirement',defeated,45);break
                x=row['peers'][0]['observation']['players'][1]['x_raw']/65536
                target=min(weak,key=lambda a:abs(a['x']-x));direction=0x20 if target['x']>=x else 0x80
                hold(1,direction|0x8000,12,'owned moving Zero Square contact'+str(attack))
                hold(1,direction,12,'original movement and fresh Square separation')
        need(defeated(row),'No complete original main/weakpoint native defeat')
        e['actual_defeat']=row['index'];capture('original-midboss-defeat-and-cleanup',row)
        hold(0,0x20,30,'proven native primary approach after defeat')
        for seat in (0,1):inp(seat,0x2020,'proven dual Right Circle to first exit ledge')
        try:updates('actual post-defeat dual dash60',60)
        finally:
            for seat in (0,1):inp(seat,0,'neutral first exit ledge')
        for seat in (0,1):inp(seat,0x20,'native approach to first platform at661')
        try:wait('both feet at first exit platform',lambda r:all(healthy(p)
            and min(a['x_raw'] for a in p['observation']['players'])>=660*65536 for p in r['peers']),45)
        finally:
            for seat in (0,1):inp(seat,0,'neutral first platform approach')
        for seat in (0,1):inp(seat,0x4020,'proven first dual Right Cross50')
        try:updates('original first exit platform jump50',50)
        finally:
            for seat in (0,1):inp(seat,0,'release first platform jump')
        for seat in (0,1): inp(seat,0x20,'native approach to exit platform at821')
        try:wait('both native feet at exit-platform approach',lambda r:all(healthy(p)
            and min(a['x_raw'] for a in p['observation']['players'])>=820*65536 for p in r['peers']),60)
        finally:
            for seat in (0,1):inp(seat,0,'neutral exit-platform approach')
        for seat in (0,1):inp(seat,0x4020,'proven dual Right Cross to actual door ledge')
        try:updates('original dual platform jump50',50)
        finally:
            for seat in (0,1):inp(seat,0,'release original platform jump')
        start=sample('both before original forward door'); door_rows=[]
        for seat in (0,1): inp(seat,0x20,'actual both forward door approach')
        try:
            stop=min(deadline,time.monotonic()+120)
            while time.monotonic()<stop:
                row=sample('original Both door foot crossing');door_rows.append(row['index'])
                # A passenger scene disqualifies F166, not an independently
                # reachable later F187 foot/checkpoint observation.
                if all(healthy(p) and min(a['x_raw'] for a in p['observation']['players'])>=985*65536
                        for p in row['peers']): break
                time.sleep(.025)
            else: raise ValueError('Original forward door did not admit the pair')
        finally:
            for seat in (0,1): inp(seat,0,'release after original door')
        foot=[]
        for peer in range(len(clients)):
            rows=[e['samples'][i]['peers'][peer] for i in door_rows]
            for seat in (0,1):
                key=f'p{seat+1}_body_hex'
                relevant=[p for p in rows if 900*65536<=p['observation']['players'][seat]['x_raw']<=985*65536]
                good=(start['peers'][peer]['observation']['players'][seat]['x_raw']<=943*65536
                    and row['peers'][peer]['observation']['players'][seat]['x_raw']>943*65536
                    and any(p['observation']['players'][seat]['action']==19 for p in relevant)
                    and all(p['observation']['lifecycle'][seat]==0 and bytes.fromhex(p[key])[3]
                        and p['observation']['scene_phase']==0 for p in relevant))
                foot.append(dict(peer=peer,seat=seat,foot_crossing=bool(good)))
        e['comparisons']['F166']=dict(status='observed' if all(x['foot_crossing'] for x in foot) else 'unverified',
            witnesses=foot,door_rows=door_rows,limit='Only actual both-foot native door passage qualifies; passenger warps excluded')
        capture('post-midboss-original-door-result',row)
        try:
            # Position with ordinary inputs below the authored CP plane. No map,
            # checkpoint, collision or result writes and no additional initializer.
            for seat in (0,1):
                inp(seat,0x20,'native corridor alignment below checkpoint plane')
                try: wait('native corridor approach1040',lambda r:all(p['observation']['players'][seat]['x_raw']>=1040*65536 for p in r['peers']),30)
                finally: inp(seat,0,'corridor approach neutral')
                updates('corridor neutral delay separation',8)
            before=sample('guest before original CP0 to1 plane')
            need(all(p['tuple']==[10,0,3,0,0] and p['observation']['players'][1]['x_raw']<1072*65536 for p in before['peers']),
                'Native CP plane was already crossed before the named foot window')
            for seat in (0,1): inp(seat,0x20,'genuine corridor Right across authored CP plane')
            try:
                after=wait('guest actual foot CP0 to1 same-area commitment',lambda r:all(healthy(p)
                    and p['tuple']==[10,0,3,0,1] and not p['observation']['scene_owner']
                    and p['observation']['players'][1]['x_raw']>=1078*65536
                    and p['observation']['players'][1]['action'] in (3,4,5) for p in r['peers']),45)
            finally:
                for seat in (0,1): inp(seat,0,'final native corridor neutral')
            e['comparisons']['F187']=dict(status='observed',before=before['index'],after=after['index'],
                scope='Actual guest foot passage and original3/0CP0to1, not a separate section loader')
            capture('guest-native-CP1-forward-passage',after)
        except Exception as error:
            e['comparisons']['F187']=dict(status='unverified',error=str(error),traceback=traceback.format_exc(),
                scope='Failed CP observation retained for review; no game/observer cause is assumed')
            if e['comparisons']['F166']['status']!='observed': raise
            after=sample('F166 door retained; F187 forward observation failed')
            try:capture('F187-forward-observation-failed',after)
            except Exception as extra:e['comparisons']['F187']['capture_error']=str(extra)
        need(all(p['fixture']['generation']==p['fixture']['initializer_entries']==1 for p in after['peers']),
            'Repeated prerequisite initializer')
        e['checks']=dict(actual_native_midboss_defeat=True,original_weakpoints_retired=True,
            guest_actual_same_area_forward_checkpoint=e['comparisons']['F187']['status']=='observed',
            no_repeated_initializer=True)
        e['status']=success;return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc())
        if e['samples']:
            try:capture('terminal-native-midboss-observation',e['samples'][-1])
            except Exception as extra:e['capture_error']=str(extra)
        raise
    finally:
        for seat in (0,1):
            try:inp(seat,0,'final native neutral')
            except Exception as error:e.setdefault('cleanup_errors',[]).append(str(error))
        (output/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf-8')


def starting_hp_receipt(client):
    data = client.read(debug.DIAGNOSTIC_ADDRESS + 0xC0, 4)
    if len(data) != 4 or data[0] > 2 or data[1] > 32 or data[2] > 32 or data[3] > 3:
        raise ValueError('Invalid native starting-HP setup publication')
    return dict(status=data[0], requested=list(data[1:3]), applied_mask=data[3], raw_hex=data.hex())


def validate_completion(receipts):
    """Ordinary fixture taint alone never establishes negotiated admission."""
    if not 1 <= len(receipts) <= 2:
        raise ValueError('Require one owned local process or two owned peers')
    wanted = dict(generation=1, state=3, reason=0, stage=0, section=0, checkpoint=2,
        nonce=NONCE, initializer_entries=1, record=RECORD, tainted=1, authority=1, latch=2)
    if any(any(type(r.get(k)) is not type(v) or r[k] != v for k, v in wanted.items()) for r in receipts):
        raise ValueError('Checkpoint lacks matching completed one-shot negotiated receipts')
    return wanted


def independent_walk(before, after, seat):
    if len(before['peers']) != len(after['peers']) or len(before['peers']) not in (1, 2):
        return None
    witnesses = []
    for old, current in zip(before['peers'], after['peers']):
        prior = old['observation']['players']; now = current['observation']['players']
        actor, other = now[seat], now[1-seat]
        if (not all(0 < p['hp'] <= 127 and p['state'] == 1 for p in now)
                or actor['character'] != seat or actor['action'] not in (3, 4)
                or actor['x_raw'] >= prior[seat]['x_raw']-2*65536):
            return None
        stationary = other['x_raw'] == prior[1-seat]['x_raw']
        damaged = other['hp'] < prior[1-seat]['hp']
        native_hurt = other['action'] == 17 or prior[1-seat]['action'] == 17
        if not stationary and not (damaged or native_hurt):
            return None
        witnesses.append(dict(peer=current['peer'], controlled_native_action=actor['action'],
            other_stationary=stationary, other_HP_drop=damaged, other_native_hurt=native_hurt,
            interpretation='stationary' if stationary else 'independent native damage response'))
    return witnesses



def native_admission_health(observation, leader):
    actor = observation['players'][leader]; passenger = observation['players'][1-leader]
    if not 0 < actor['hp'] <= 127 or observation['lifecycle'][leader] != 0:
        return False
    native_transport = (observation['scene_owner'] == leader+1
        and observation['scene_phase'] in (2, 3) and observation['lifecycle'][1-leader] == 0)
    return observation['lifecycle'][1-leader] in (0, 3) and (
        0 < passenger['hp'] <= 127 or native_transport)


def authored_checkpoint_arrivals(peers):
    # CP metadata can publish before the old player's body is reinitialized.
    return len(peers) in (1, 2) and all(len(p['observation']['players']) == 2 and
        all(abs(a['x_raw']-x*65536) < 65536 for a, x in
            zip(p['observation']['players'], (5904, 5928))) for p in peers)


def exercise(ctx, *, output, original_exe, leader, success):
    if type(leader) is not int or leader not in (0, 1):
        raise ValueError('Require an explicit native door leader')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    clients = ctx['clients']; report = ctx['report']
    e = dict(kind='agreed_lab_intro_native_door', status='failed_setup', leader=leader,
        mode='netplay' if len(clients) == 2 else 'offline', option=OPTION, samples=[], inputs=[],
        captures=[], checks={}, network_windows=[], ordinary_route_qualified=False,
        finalized_capture_admitted=False, replay_admitted=False,
        baseline_scope=('ordinary paired P2 walk/P1 jump before fixture' if len(clients) == 2
                        else 'native local initial idle; no separate pre-fixture walk/jump claim'),
        bypasses=['Pre-agreed LAB intro CP2 initializer replaces unrelated intro traversal; '
                  'native door contact, boss activation, passenger landing and controls are exercised afterward.'])
    report['intro_admission'] = e
    deadline = time.monotonic() + 150

    def need(ok, message):
        if not ok:
            raise ValueError(message)

    def inputs(seat, bits, label):
        e['inputs'].append(dict(seat=seat, pressed=bits, label=label, ack=ctx['set_input'](seat, bits)))

    def sample(label):
        peers = []
        for peer, client in enumerate(clients):
            s = hud.state.private_sample(client); play = client.read(0x800CCED0, 0xE0)
            camera = client.read(0x800971F8, 0x54); pointer = struct.unpack_from('<I', play, 0x20)[0]
            boss = None
            if 0x8008EF48 <= pointer < 0x8008EF48 + 0x9C*48 and (pointer-0x8008EF48) % 0x9C == 0:
                body = client.read(pointer, 0x9C)
                if body[0] and body[1:3] == bytes((48, 0)):
                    boss = dict(address=pointer, type=body[1], subtype=body[2], state=body[4],
                        action=body[5], phase=body[6], hp=body[0x5C], hex=body.hex())
            peers.append(dict(peer=peer, observation=s['observation'], p1_body_hex=s['p1_body_hex'],
                p2_body_hex=s['p2_body_hex'], actual_mode=play[0], actual_phase=play[1], stage=play[12],
                section=play[13], checkpoint=play[0x1D], play_hex=play.hex(), boss=boss,
                camera_x=struct.unpack_from('<h', camera, 10)[0],
                camera_y=struct.unpack_from('<h', camera, 14)[0], camera_hex=camera.hex(), fixture=receipt(client)))
        row = dict(index=len(e['samples']), label=label, peers=peers)
        e['samples'].append(row)  # Retain offending raw state BEFORE any guard.
        need(len(e['samples']) < 1800 and time.monotonic() < deadline, 'Bounded intro observation expired')
        if len(e['samples']) % 16 == 0 and ctx.get('network'):
            e['network_windows'].append(dict(row_index=row['index'], peers=ctx['network']()))
        return row

    def idle(row, cp):
        return all(p['actual_mode'] == 10 and p['actual_phase'] == p['stage'] == p['section'] == 0
            and p['checkpoint'] == cp and not p['observation']['scene_owner']
            and not p['observation']['pause_owner'] and not p['observation']['failed']
            and not p['observation']['mailbox'] and p['observation']['ready'] == p['observation']['enrolled'] == 1
            and tuple(p['observation']['lifecycle']) == (0, 0)
            and all(a['state'] == 1 and a['action'] == 2 and 0 < a['hp'] <= 127
                    for a in p['observation']['players']) for p in row['peers'])

    def capture(label):
        row = sample(label+' capture')
        for peer, client in enumerate(clients):
            e['captures'].append(dict(peer=peer, label=label, row_index=row['index'],
                **debug.capture_present(client, output/f'peer-{peer}-{label}.png', request=client.request)))
        return row

    try:
        exe = Path(original_exe).read_bytes(); guards = []
        for address, size in ((0x80050250, 0x324), (0x80050C88, 0x174)):
            expected = exe[address-0x80010000+2048:address-0x80010000+2048+size]
            need(len(expected) == size and all(c.read(address, size) == expected for c in clients),
                'Original native door source differs')
            guards.append(dict(address=hex(address), bytes=size, sha256=hashlib.sha256(expected).hexdigest()))
        e['original_door_source'] = guards
        for seat in (0, 1):
            inputs(seat, 0, e['baseline_scope'])
        end = time.monotonic()+15
        while True:
            row = sample('safe native CP0 before agreed prerequisite')
            if idle(row, 0):
                break
            need(time.monotonic() < end, 'No safe native CP0 boundary after ordinary baseline')
            time.sleep(.025)
        need(all(p['fixture']['generation'] == p['fixture']['latch'] == p['fixture']['tainted'] == 0
                 for p in row['peers']), 'Fixture was used before the explicit accepted chord')
        inputs(1, 0x0006, 'accepted P2 L3+R3 arms pre-agreed one-shot checkpoint')
        end = time.monotonic()+15
        try:
            while True:
                armed = sample('accepted chord one-shot receipt')
                if all(p['fixture']['latch'] in (1, 2) for p in armed['peers']):
                    break
                need(time.monotonic() < end, 'Both peers did not accept the agreed checkpoint chord')
                time.sleep(.025)
        finally:
            inputs(1, 0, 'release accepted arming chord')
        end = time.monotonic()+60
        while True:
            row = sample('original checkpoint initializer and native arrival')
            if (idle(row, 2) and authored_checkpoint_arrivals(row['peers'])
                    and all(p['fixture']['state'] == 3 for p in row['peers'])):
                break
            need(all(p['fixture']['state'] not in (4, 5) for p in row['peers']),
                'Original checkpoint pipeline rejected the agreed prerequisite')
            need(time.monotonic() < end, 'Native CP2 arrival did not finish')
            time.sleep(.025)
        e['agreed_completion'] = validate_completion([p['fixture'] for p in row['peers']])
        need(all(p['boss'] is None for p in row['peers']), 'Need pre-boss CP2 before encounter allocation')
        e['initial'] = capture('safe-native-CP2')
        e['status'] = 'failed_native_observation'
        inputs(leader, 0x20, 'native leader Right into authored intro door')
        scene = [False]*len(clients); contact = [False]*len(clients)
        end = time.monotonic()+32
        try:
            released = False
            while True:
                row = sample('native door contact and scene admission')
                for peer, p in enumerate(row['peers']):
                    o = p['observation']; owner = o['scene_owner']
                    need(native_admission_health(o, leader), 'Actor lacks health outside its actual native transport context')
                    if owner:
                        need(owner == leader+1, 'Original door selected a different scene owner')
                        if not scene[peer]:
                            e.setdefault('scene_begin', []).append(dict(peer=peer, row_index=row['index']))
                        scene[peer] = True
                    contact[peer] |= o['players'][leader]['x_raw'] >= 6037*65536
                if any(scene) and not released:
                    inputs(leader, 0, 'original door owns traversal'); released = True
                    capture('original-door-scene-begin')
                if all(p['boss'] is not None for p in row['peers']):
                    e['boss_allocated'] = row
                    break
                need(time.monotonic() < end, 'Native door did not allocate the original D-1000 boss')
                time.sleep(.025)
        finally:
            inputs(leader, 0, 'release native approach')
        end = time.monotonic()+65
        while True:
            row = sample('native boss HP fill and passenger landing')
            if idle(row, 2) and all(p['boss'] and p['boss']['state'] == 1
                    and p['boss']['action'] >= 4 and p['boss']['hp'] == 32 for p in row['peers']):
                e['battle_ready'] = row
                break
            need(time.monotonic() < end, 'Native boss initialization/passenger landing did not release both controls')
            time.sleep(.025)
        need(all(scene) and all(contact) and all(p['camera_x'] >= 6064 for p in row['peers']),
            'Missing original owner, contact or native camera opening on a peer')
        for seat in (0, 1):
            before = sample(f'seat{seat} before independent Left')
            inputs(seat, 0x80, 'fresh independent post-door Left')
            end = time.monotonic()+6
            try:
                while True:
                    row = sample(f'seat{seat} accepted native Left')
                    witness = independent_walk(before, row, seat)
                    if witness:
                        break
                    need(time.monotonic() < end, 'Post-door independent control was not observed on both peers')
                    time.sleep(.02)
            finally:
                inputs(seat, 0, 'release independent native Left')
            e.setdefault('controls', []).append(dict(seat=seat, before=before['index'], accepted=row['index'],
                native_walk_and_nonparticipant=witness))
            start = sample('native neutral release start'); end = time.monotonic()+12
            while True:
                settled = sample('eight original updates after accepted neutral')
                if all((p['observation']['native_timer']-old['observation']['native_timer']) & 0xFFFFFFFF >= 8
                        for p, old in zip(settled['peers'], start['peers'])):
                    break
                need(time.monotonic() < end, 'Native world did not advance after neutral release')
                time.sleep(.02)
        capture('native-boss-both-controls-restored')
        validate_completion([p['fixture'] for p in e['samples'][-1]['peers']])
        e['checks'] = dict(agreed_checkpoint_complete=True, original_leader_selected=all(scene),
            actual_native_contact=all(contact), original_boss_fullHP_released=True,
            passenger_landed_both_healthy=True, independent_native_controls=True,
            no_repeated_initializer=True)
        e['status'] = success
        return e
    except Exception as error:
        e.update(error=str(error), traceback=traceback.format_exc())
        # Capture raw failure directly: a gameplay guard must not erase it.
        for peer, client in enumerate(clients):
            try:
                e.setdefault('failure_captures', []).append(dict(peer=peer,
                    **debug.capture_present(client, output/f'peer-{peer}-terminal.png', request=client.request)))
            except Exception as capture_error:
                e.setdefault('failure_capture_errors', []).append(str(capture_error))
        raise
    finally:
        for seat in (0, 1):
            try:
                inputs(seat, 0, 'final native neutral')
            except Exception as error:
                e.setdefault('cleanup_errors', []).append(str(error))
        (output/'observations.json').write_bytes((json.dumps(e, indent=2)+'\n').encode('utf-8'))
