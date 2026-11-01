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
        need(seat in (0,1) and bits in (0,6,0x20,0x80,0x200,0x4000,0x8000,0x2020,0x4020,0x4080,0x6020,0x8020,0x8080),'Ordinary declared host-pad input only')
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
        for cast in range(4):
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
                    if any(a['subtype']<4 and a['active'] and a['hp']>0
                            for p in row['peers'] for a in p['snake']):
                        updates('live weakpoint temporarily hidden; retain combat',12)
                        continue
                    row=wait('original Snake death/retirement',defeated,45);break
                x=row['peers'][0]['observation']['players'][1]['x_raw']/65536
                target=min(weak,key=lambda a:abs(a['x']-x));direction=0x20 if target['x']>=x else 0x80
                y=row['peers'][0]['observation']['players'][1]['y_raw']/65536
                if target['y']<y-48:
                    hold(1,direction|0x4000,12,'native jump toward elevated surviving weakpoint'+str(attack))
                hold(1,direction|0x8000,12,'owned moving Zero Square contact'+str(attack))
                hold(1,direction,12,'original movement and fresh Square separation')
        need(defeated(row),'No complete original main/weakpoint native defeat')
        e['actual_defeat']=row['index'];capture('original-midboss-defeat-and-cleanup',row)
        if len(clients)==1:
            e['postdefeat_snapshot']=[]
            try: hud.state.snapshot_operation(clients[0].request,'save',9,e['postdefeat_snapshot'])
            except Exception as error: e['postdefeat_snapshot_error']=str(error)
        hold(0,0x20,30,'proven native primary approach after defeat')
        for seat in (0,1):inp(seat,0x2020,'proven dual Right Circle to first exit ledge')
        try:updates('actual post-defeat dual dash60',60)
        finally:
            for seat in (0,1):inp(seat,0,'neutral first exit ledge')
        for seat in (0,1):inp(seat,0x4020,'native dual jump over first step at501')
        try:updates('original first arena exit step jump50',50)
        finally:
            for seat in (0,1):inp(seat,0,'release first arena exit step jump')
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
        # Native door action may begin during the preceding platform approach.
        door_rows=list(range(e['actual_defeat'],row['index']+1))
        foot=[]
        for peer in range(len(clients)):
            rows=[e['samples'][i]['peers'][peer] for i in door_rows]
            for seat in (0,1):
                key=f'p{seat+1}_body_hex'
                relevant=[p for p in rows if 900*65536<=p['observation']['players'][seat]['x_raw']<=985*65536]
                good=(any(p['observation']['players'][seat]['x_raw']<=943*65536 for p in rows)
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
                try: wait('native corridor approach1000',lambda r:all(p['observation']['players'][seat]['x_raw']>=1000*65536 for p in r['peers']),30)
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


def exercise_door_policy(ctx,*,output,original_exe,leader,success,scenario):
 """Reuse the original two-hatch case; only the declared fatal setup differs."""
 import mmx6_coop_native_reentry as dialogue
 h=hud
 ORIGINS=(0x800FA2A4,0x800FA2AC);DOOR_X=(5744,6064)
 def need(ok,message):
  if not ok:raise ValueError(message)
 if scenario=='either':
  return exercise(ctx,output=output,original_exe=original_exe,leader=leader,success=success)
 need(scenario in ('living','absent','fallen'),'Explicit original door policy scenario required')
 if (1280,480) not in h.SIZES:h.SIZES=tuple(h.SIZES)+((1280,480),)
 out=Path(output);out.mkdir(parents=True,exist_ok=False)
 clients=ctx['clients'];report=ctx['report'];online=len(clients)==2
 excluded=False
 def participants():return (0,1)if not excluded else (0,)
 e=dict(kind='two_original_Both_doors_private_views',status='failed_setup',samples=[],inputs=[],dialogue_inputs=[],dialogue_responses=[],captures=[],doors=[],checks={},source_guards=[],bypasses=['Explicit agreed intro_before_doors fixture initializes nativeCP1, then positions living heroes/camera on source-qualified predoor ground and calls the original primary placement scanner once with its native full-window envelope. Already resident secondary controllers are preserved. It bypasses unrelated approach traversal only. No native door admission, acknowledgement, CP2 grant, traversal or outcome is assigned.'],limits=['F101/F116 original intro subtype2 then subtype1 in one physical process/session per mode. No fortress/consecutive-boss-door/F83/F164 inference; no whole intro traversal, ordinary recording/replay, cross-host/OS or all-door-subtype claim.'])
 report['two_Both_doors']=e;deadline=time.monotonic()+210
 def inp(seat,bits,label):
  if excluded and seat not in participants() and bits:return
  e['inputs'].append(dict(seat=seat,bits=bits,label=label,ack=ctx['set_input'](seat,bits)))
 def pace():time.sleep(.015)
 def sample(label):
  need(time.monotonic()<deadline and len(e['samples'])<1600,'Bounded two-door observation exhausted')
  rows=[]
  for i,c in enumerate(clients):
   state=h.state.private_sample(c);o=state['observation'];play=c.read(0x800CCED0,0xE0);pool=c.read(0x800C1220,0x3340);actors={}
   for at in range(0,len(pool),0xA4):
    a=pool[at:at+0xA4];origin=struct.unpack_from('<I',a,0x10)[0]
    if a[0]&1 and a[1]==8 and origin in ORIGINS:
     need(str(origin)not in actors,'Duplicate original native door allocation')
     pointer=struct.unpack_from('<I',a,0x68)[0]
     actors[str(origin)]=dict(address=0x800C1220+at,hex=a.hex(),box=c.read(pointer,4).hex()if 0x80010000<=pointer<=0x801ffffc else None)
   bodies=[bytes.fromhex(state[k])for k in ('p1_body_hex','p2_body_hex')];boxes=[]
   for body in bodies:
    pointer=struct.unpack_from('<I',body,0x68)[0];boxes.append(c.read(pointer,4).hex()if 0x80010000<=pointer<=0x801ffffc else None)
   pointer=struct.unpack_from('<I',play,0x20)[0];boss=None
   if 0x8008EF48<=pointer<0x8008EF48+0x9C*48 and not (pointer-0x8008EF48)%0x9C:
    b=c.read(pointer,0x9C)
    if b[0]and b[1:3]==bytes((48,0)):boss=dict(address=pointer,state=b[4],action=b[5],hp=b[0x5C],hex=b.hex())
   f=receipt(c);raw=bytes.fromhex(f['raw_hex']);f.update(pose=raw[13],placement_calls=raw[14])
   npc_pool=c.read(0x800CD410,0x2400);npcs=[]
   for at in range(0,len(npc_pool),0x60):
    a=npc_pool[at:at+0x60]
    if a[0]&1 and a[1:3]==bytes((8,0))and struct.unpack_from('<I',a,0x10)[0]==0x800FA29C:npcs.append(dict(address=0x800CD410+at,hex=a.hex()))
   need(len(npcs)<=1,'Duplicate original following NPC allocation')
   rows.append(dict(peer=i,fatal_status=c.read(debug.DIAGNOSTIC_ADDRESS+0xC8,1)[0],state=state,play_hex=play.hex(),camera_hex=c.read(0x800971F8,0xFC).hex(),fixture=f,doors=actors,boxes=boxes,boss=boss,npc=npcs[0]if npcs else None,stage=play[12],section=play[13],mode=list(play[:3]),dialogue_hex=c.read(0x8008EAF0,16).hex(),decoded=list(struct.unpack('<3H',c.read(0x800C456C,6)))))
  r=dict(index=len(e['samples']),label=label,peers=rows);e['samples'].append(r)
  for p in rows:
   if dialogue.dialogue_state(p)['active']:
    # Pool, text and diagnostics are separate safe-point RPCs. The native
    # action2->3 transition can happen between the pool read and text queue.
    # Retain both raw observations, then recheck this same typed slot AFTER
    # the text read. This never writes an actor or normalizes its phase.
    need(p['npc']is not None,'Active dialogue has no original typed NPC')
    p['npc_before_dialogue_recheck']=dict(p['npc'])
    current=clients[p['peer']].read(p['npc']['address'],0x60)
    need(current[0]&1 and current[1:3]==bytes((8,0))and struct.unpack_from('<I',current,0x10)[0]==0x800FA29C,'Following NPC identity changed across dialogue read')
    p['npc']=dict(address=p['npc']['address'],hex=current.hex())
    if current[4:6]!=bytes((1,3)):
     p['dialogue_before_npc_recheck_hex']=p['dialogue_hex']
     p['dialogue_hex']=clients[p['peer']].read(0x8008EAF0,16).hex()
   if dialogue.dialogue_state(p)['active']:
    need(crossed(p,DOOR_X[0]+16)and camera_committed(p,DOOR_X[0]),'Actual first-door dialogue appeared before both full boxes/camera committed')
    need(p['npc']and bytes.fromhex(p['npc']['hex'])[4:6]==bytes((1,3)),'Following dialogue did not retain its original typed NPC controller')
  if online and len(e['samples'])%16==0:ctx['network']()
  return r
 def alive(r):
  expected=(0,0)if not excluded else(0,2)if scenario=='absent'else(0,5)
  return all(p['state']['observation']['native_mode']==10 and not p['state']['observation']['failed']and not p['state']['observation']['mailbox']and tuple(p['state']['observation']['lifecycle'])==expected and all(p['state']['observation']['players'][seat]['active']and p['state']['observation']['players'][seat]['state']==1 and 0<p['state']['observation']['players'][seat]['hp']<128 for seat in participants())for p in r['peers'])
 def idle(r,cp=None):
  return alive(r)and all(not p['state']['observation']['scene_owner']and not p['state']['observation']['pause_owner']and p['state']['observation']['native_phase']==0 and all(p['state']['observation']['players'][seat]['action']==2 for seat in participants())and(cp is None or bytes.fromhex(p['play_hex'])[0x1D]==cp)for p in r['peers'])
 def wait(label,predicate,seconds=18,ordinary=False):
  until=min(deadline,time.monotonic()+seconds)
  while time.monotonic()<until:
   r=sample(label)
   if ordinary:
    need(alive(r),'Two-door native living/no-passenger body contract failed')
    for p in r['peers']:
     o=p['state']['observation'];play=bytes.fromhex(p['play_hex'])
     need((play[12],play[13])==(0,0)and play[0x1D]in(1,2),'Native two-door stage/checkpoint changed unexpectedly')
     need(not o['scene_owner']or o['scene_phase']==0,'Both door entered passenger transport')
   if predicate(r):return r
   pace()
  raise ValueError(label+' timed out')
 def presentation():
  return [dict(counters=c.request('mod_counters'),stereo=c.request('stereo_stats'),video=c.request('video_info'),present=c.request('gl_present_ring',n=240))for c in clients]
 def counts(p):return {x['name']:x['count']for x in p['counters']['counters']}
 def capture(label):
  before=sample(label+' before composed capture');shots=[debug.capture_present(c,out/f'peer-{i}-{label}.png',request=c.request)for i,c in enumerate(clients)];after=sample(label+' after composed capture');ps=presentation()
  for i,shot in enumerate(shots):e['captures'].append(dict(peer=i,label=label,before_sample=before['index'],after_sample=after['index'],presentation=ps[i],**shot))
  return ps
 def ticks(n,label):
  r=sample(label+' before');start=[p['state']['observation']['native_timer']for p in r['peers']]
  return wait(label,lambda r:all(p['state']['observation']['native_timer']>=v+n for p,v in zip(r['peers'],start)),ordinary=True)
 def eligible(p,origin,seat):
  if p['state']['observation']['lifecycle'][seat]!=0:return False
  a=p['doors'].get(str(origin));b=bytes.fromhex(p['state']['p2_body_hex'if seat else'p1_body_hex']);shape=p['boxes'][seat]
  if not a or not a['box']or not shape or b[0xA4]or b[0x5C]&128 or b[5]==3 or b[0x8E if b[2]else 0x7A]:return False
  door=bytes.fromhex(a['hex']);x,y=struct.unpack_from('<ii',b,8);dx,dy=struct.unpack_from('<ii',door,8);x>>=16;y>>=16;dx>>=16;dy>>=16
  s=bytes.fromhex(shape);d=bytes.fromhex(a['box']);signed=lambda v:v if v<128 else v-256
  px=x+signed(s[0]);py=y+signed(s[1]);ax=dx+signed(d[0]);ay=dy+signed(d[1])
  return x<=dx and abs(px-ax)<=s[2]+d[2]and py-s[3]>=ay-d[3]and py+s[3]<=ay+d[3]
 def camera_committed(p,x):
  cam=bytes.fromhex(p['camera_hex'])
  return struct.unpack_from('<ii',cam,8)==(x<<16,224<<16)and all(struct.unpack_from('<H',cam,k)[0]==x for k in(0x1C,0x1E,0x24,0x26))and all(struct.unpack_from('<H',cam,k)[0]==224 for k in(0x20,0x22,0x28,0x2A))
 def crossed(p,right):
  for seat,(key,shape)in enumerate(zip(('p1_body_hex','p2_body_hex'),p['boxes'])):
   if seat not in participants():continue
   if not shape:return False
   body=bytes.fromhex(p['state'][key]);s=bytes.fromhex(shape);offset=s[0]if s[0]<128 else s[0]-256
   if (struct.unpack_from('<i',body,8)[0]>>16)+offset-s[2]<=right:return False
   if body[0xD4]or body[0x67]or not body[0x70]&8:return False
  return True
 def release_scene(number,x):
  until=min(deadline,time.monotonic()+65)
  while time.monotonic()<until:
   r=sample('door%d native scene release and original dialogue'%(number+1));need(alive(r),'Native post-door scene lost a living body')
   need(all(not p['state']['observation']['scene_phase']for p in r['peers']),'Post-door native scene used passenger transport')
   if idle(r)and all(crossed(p,x+16)and dialogue.dialogue_state(p)['active']==0 for p in r['peers']):return r
   def ready(item):
    return all((p['stage'],p['section'],p['mode'])==(0,0,[10,0,0])and (p['state']['observation']['scene_owner']==1 if not excluded else p['state']['observation']['scene_owner']in(0,1+participants()[0]))and p['state']['observation']['players'][0 if not excluded else participants()[0]]['action']==20 and (dialogue.dialogue_state(p)['active'],dialogue.dialogue_state(p)['phase'])==(255,3)for p in item['peers'])
   if ready(r):
    need(number==0,'Unexpected dialogue family after second door')
    need(all(crossed(p,x+16)and camera_committed(p,x)for p in r['peers']),'Actual native dialogue admitted before both full boxes/camera committed')
    if not e['dialogue_responses']:capture('first-door-following-original-dialogue-ready')
    offered=[];accepted=[]
    def pulse_ready(item):
     if not ready(item):return False
     offered[:]=[dialogue.dialogue_state(p)for p in item['peers']];return True
    def response(item):
     after=[dialogue.dialogue_state(p)for p in item['peers']]
     reasons=[dialogue.dialogue_response(a,z)for a,z in zip(offered,after)]
     if len(after)!=len(clients)or not all(reasons):return False
     accepted[:]=[dict(before=a,after=z,response=why)for a,z,why in zip(offered,after,reasons)];return True
    dialogue.pulse(dict(ctx,input_path='published_host',set_input=lambda seat,bits:inp(seat if not excluded else participants()[0],bits,'native NPC dialogue Cross/neutral')),e['dialogue_inputs'],0x4000,response,sample,label='Original NPC2 ready dialogue Cross',ready=pulse_ready,timeout=min(10,max(.1,(until-time.monotonic())/3)))
    e['dialogue_responses'].append(dict(sample=r['index'],native_response_and_neutral=True,peers=accepted))
   pace()
  raise ValueError('door%d original scene release and both control timed out'%(number+1))
 try:
  exe=Path(original_exe).read_bytes();need(hashlib.sha256(exe).hexdigest()=='dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046','Original EXE differs')
  for address,size in ((0x80050250,0x324),(0x80050C88,0x174),(0x80050DFC,0xFC),(0x80050EA0,0xB8),(0x8007212C,36),(0x8005211C,0x13C),(0x80079230,0x30),(0x80079290,0x20),(0x8002A3E8,0x50),(0x80029F38,0x404),(0x8003D308,0x44),(0x800219EC,0x30),(0x80021FC4,0x874)):
   raw=exe[address-0x80010000+2048:address-0x80010000+2048+size];need(all(c.read(address,size)==raw for c in clients),'Original setup/door source differs')
   e['source_guards'].append(dict(address=hex(address),bytes=size,sha256=hashlib.sha256(raw).hexdigest()))
  # Original BIN2/index2/sector36/baseE9860; parent pins the original archive.
  # F9334 queues D0, F936C waits action20, F93E8 opens ID2 after X>=5824;
  # F9548 calls original3D330 only after native NPC departure below Y192.
  for address,size,wanted in ((0x800F90FC,1140,'ef0f6d9cce2bdba994d07e35497dc32e88decee1c7a7ebd5c698caa7528662ab'),(0x800FBB3C,36,'2b9ec31ce03c897435ddae949b46ab810dc224e96e9101a18ee2b14988b814f0')):
   need(all(hashlib.sha256(c.read(address,size)).hexdigest()==wanted for c in clients),'Original typed NPC scene code/table differs')
   e['source_guards'].append(dict(address=hex(address),bytes=size,sha256=wanted,original_bin2_sha256='d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607'))
  for seat in(0,1):inp(seat,0,'ordinary native neutral before declared fixture')
  before=wait('original CP0 idle before accepted setup chord',lambda r:idle(r,0),20)
  need(all(p['fixture']['generation']==p['fixture']['tainted']==p['fixture']['latch']==0 for p in before['peers']),'Fixture used before accepted chord')
  inp(1,6,'accepted P2 L3+R3 arms declared intro_before_doors')
  try:wait('accepted agreed prerequisite latch',lambda r:all(p['fixture']['latch']in(1,2)for p in r['peers']),15)
  finally:inp(1,0,'release accepted prerequisite chord')
  def setup_ready(r):
   need(all(p['fixture']['state']not in(4,5)for p in r['peers']),'Declared native prerequisite rejected')
   return idle(r,1)and all(p['fixture']['state']==3 and p['fixture']['pose']==2 and p['fixture']['placement_calls']==1 and str(ORIGINS[0])in p['doors']for p in r['peers'])
  ready=wait('original CP1 then one-shot native-grounded predoor setup',setup_ready,65)
  wanted=dict(generation=1,state=3,reason=0,stage=0,section=0,checkpoint=1,nonce=0x4C434431,initializer_entries=1,record='8007212C',tainted=1,authority=1,latch=2,pose=2,placement_calls=1)
  need(all(all(p['fixture'].get(k)==v for k,v in wanted.items())for p in ready['peers']),'Full agreed one-shot CP1/pose/placement receipt differs')
  need(all(not eligible(p,ORIGINS[0],0)and not eligible(p,ORIGINS[0],1)for p in ready['peers']),'Setup already granted original door eligibility')
  e['prerequisite']=dict(sample=ready['index'],expected_receipt=wanted)
  if scenario=='absent':
   inp(1,1,'real guest Select90 native withdrawal before first door')
   leaving=wait('actual guest LEAVING',lambda r:all(p['state']['observation']['lifecycle'][1]==1 for p in r['peers']),30)
   inp(1,0,'release actual Select without fresh request')
   gone=wait('actual native guest completion ABSENT',lambda r:all(tuple(p['state']['observation']['lifecycle'])==(0,2)and bytes.fromhex(p['state']['p2_body_hex'])[4]==3 for p in r['peers']),45)
   e['exclusion_precondition']=dict(kind='real_Select_to_native_ABSENT',leaving=leaving['index'],completed=gone['index']);excluded=True
  elif scenario=='fallen':
   e['bypasses'].append('Predeclared lab_fatal=p2 requests only native HP80 after the checkpoint; original updates must earn death/FALLEN. Door, lifecycle, lives and progress results are never assigned.')
   inp(1,0,'neutral after completed checkpoint before separate fatal edge')
   armed=wait('agreed P2 fatal armed after neutral',lambda r:idle(r,1)and all(p['fatal_status']==6 for p in r['peers']),15)
   inp(1,6,'ordinary second P2 L3+R3 requests declared native fatal')
   try:requested=wait('one agreed P2 native fatal request consumed',lambda r:all(p['fatal_status']==10 for p in r['peers']),15)
   finally:inp(1,0,'release consumed native fatal chord')
   dying=wait('original P2 native fatal handling',lambda r:all(p['state']['observation']['lifecycle'][1]in(4,5)for p in r['peers']),30)
   fallen=wait('actual native guest death finishes FALLEN',lambda r:all(tuple(p['state']['observation']['lifecycle'])==(0,5)and bytes.fromhex(p['state']['p2_body_hex'])[4]==3 for p in r['peers']),45)
   e['exclusion_precondition']=dict(kind='agreed_P2_HP80_request_then_original_native_FATAL_FALLEN',armed=armed['index'],requested=requested['index'],dying=dying['index'],completed=fallen['index']);excluded=True
  else:need(scenario=='living','Explicit F61 scenario required')
  # Native door eligibility uses world/body boxes; capture the actual drawable.
  ticks(8,'actual predoor private pairs');capture('before-first-native-door')
  for number,(origin,x)in enumerate(zip(ORIGINS,DOOR_X)):
   leading=1-number if not excluded else participants()[0];trailing=leading^1;record=dict(number=number+1,origin=hex(origin),authored_x=x,leading=leading);e['doors'].append(record)
   initial=wait('original door%d allocated and both idle'%(number+1),lambda r:idle(r)and all(str(origin)in p['doors']for p in r['peers']),20,True)
   before_views=presentation();record['before']=initial['index'];record['presentation_before']=before_views
   for p in initial['peers']:
    actor=bytes.fromhex(p['doors'][str(origin)]['hex']);need((actor[1],actor[2])==(8,2 if number==0 else 1)and struct.unpack_from('<i',actor,8)[0]==x*65536,'Wrong original authored door')
   if not excluded:
    inp(leading,0x20,'one hero reaches door%d while partner stays outside'%(number+1))
    waiting=wait('only leading native body eligible at door%d'%(number+1),lambda r:all(eligible(p,origin,leading)and not eligible(p,origin,trailing)for p in r['peers']),20,True)
    inp(leading,0,'leading hero waits at original Both door');held=ticks(24,'Both door%d refuses single hero'%(number+1))
    need(all(not p['state']['observation']['scene_owner']and bytes.fromhex(p['doors'][str(origin)]['hex'])[5]==0 for p in held['peers']),'Both policy admitted only one eligible hero')
    for a,z in zip(initial['peers'],held['peers']):need(a['state']['observation']['players'][trailing]['x_raw']==z['state']['observation']['players'][trailing]['x_raw'],'Waiting door moved distant hero')
    record['waiting']=waiting['index'];record['held']=held['index'];record['waiting_presentation']=capture('door%d-only-leading-hero-waits'%(number+1))
    for a,z in zip(before_views,record['waiting_presentation']):
     need(z['stereo']['pairs']>a['stereo']['pairs'] and counts(z).get('mmx6.coop.private-committed',0)>counts(a).get('mmx6.coop.private-committed',0),'Waiting at native Both door stopped private drawing')
     need(z['stereo']['published']['mode']==2 and z['stereo']['published']['valid']==1 and z['stereo']['published']['width']*3==z['stereo']['published']['height']*4 and not counts(z).get('mmx6.coop.private-state-leak',0),'Waiting door lost native4:3 panes or leaked state')
     need(all(v[2]=='stereo' and not v[7] and v[5][2]*3==v[5][3]*8 for v in z['present']['events'][-2:]),'Waiting native door did not present independent8:3 canvas')
   inp(trailing,0x20,'partner approaches actual door%d'%(number+1));inp(leading,0x20,'leading hero crosses only after both admit')
   admitted=wait('original door%d Both admission'%(number+1),lambda r:all(p['state']['observation']['scene_owner']or (excluded and bytes.fromhex(p['doors'][str(origin)]['hex'])[5]in(1,2,3))for p in r['peers']),20,True);record['admitted']=admitted['index']
   seen=set();until=min(deadline,time.monotonic()+65);released=None
   while time.monotonic()<until:
    r=sample('door%d native opening/traversal'%(number+1));need(alive(r),'Door traversal lost living original bodies')
    for p in r['peers']:
     need(not p['state']['observation']['scene_owner']or p['state']['observation']['scene_phase']==0,'Door used passenger transport')
     if dialogue.dialogue_state(p)['active']:
      need(number==0 and crossed(p,x+16)and camera_committed(p,x),'Following dialogue began before native full-box/camera commitment')
    actor=r['peers'][0]['doors'].get(str(origin));phase=bytes.fromhex(actor['hex'])[5]if actor else-1
    if phase in(1,2,3)and phase not in seen:
     seen.add(phase);capture('door%d-native-phase%d'%(number+1,phase))
    if all(crossed(p,x+16)for p in r['peers']):
     for seat in(0,1):inp(seat,0,'release ordinary Right after full-box crossing')
     released=release_scene(number,x);break
    pace()
   need(released is not None,'Original door failed complete full-box traversal')
   after_views=capture('door%d-both-full-boxes-released'%(number+1));record.update(released=released['index'],presentation_after=after_views,observed_phases=sorted(seen))
   if not excluded:
    for a,z in zip(before_views,after_views):
     ac,zc=counts(a),counts(z);need(z['stereo']['pairs']>a['stereo']['pairs']and z['stereo']['published']['mode']==2 and not zc.get('mmx6.coop.private-state-leak',0),'Native door lost actual independent pairs or leaked context')
     for phase in ('opening','traversal'):need(zc.get('mmx6.coop.private-door-'+phase,0)>ac.get('mmx6.coop.private-door-'+phase,0),'No committed private views through native door '+phase)
   if number==0:need(all(bytes.fromhex(p['play_hex'])[0x1D]==2 for p in released['peers']),'Original CP2 marker was not crossed naturally')
  final=wait('native original boss readiness after second door',lambda r:idle(r,2)and all(p['boss']and p['boss']['state']==1 and p['boss']['action']>=4 and p['boss']['hp']==32 for p in r['peers']),65,True)
  e['final']=final['index'];capture('both-original-doors-complete-native-boss-ready')
  if not excluded:
   e['checks']=dict(one_session_two_distinct_original_doors=True,both_policy_refuses_single_hero_at_each=True,each_living_native_body_crosses_both_full_boxes=True,no_passenger_withdrawal_or_rejoin=True,native_opening_and_traversal_private_commits_each_door=True,actual_private_pairs_resume_each_door=True,native_checkpoint_marker_and_boss_progression=True,host_private_state_restored=True,actual_dialogue_follows_both_full_boxes_and_native_camera=bool(e['dialogue_responses'])and all(d['native_response_and_neutral']for d in e['dialogue_responses']))
  else:
   e['checks']=dict(actual_native_excluded_partner_precondition=True,one_session_two_original_hatches=True,sole_living_native_admission_and_full_box_clearance=True,native_original_NPC_dialogue_and_checkpoint_progression=bool(e['dialogue_responses']),native_D1000_full32HP_ready=True,excluded_partner_remains_excluded=alive(final),actual_native_release_controls=idle(final,2),native_results_not_seeded=True)
  e['status']=success;return e
 except Exception as error:
  e.update(error=str(error),traceback=traceback.format_exc())
  try:capture('terminal-observation')
  except Exception as extra:e['terminal_capture_error']=str(extra)
  raise
 finally:
  for seat in(0,1):
   try:inp(seat,0,'final owned neutral')
   except Exception as error:e.setdefault('cleanup_errors',[]).append(str(error))
  (out/'observations.json').write_bytes((json.dumps(e,indent=2)+'\n').encode())


def exercise_refight_policy(ctx,*,output,original_exe,leader,success,scenario):
    """Original F123 portal case with only the native fatal prerequisite replaced."""
    import importlib.util
    # This immutable helper owns original-disc parsing/terrain/source guards,
    # not a game build, profile or launcher binding.
    source_path=Path(original_exe).resolve().parent.parent/'mmx6_R21_distant_refight_v106_root_v1.py'
    source_sha='8860068f0219560ab039237cde1d81d552d0fbf2eb05bf776ad52993d5a7238b'
    if hashlib.sha256(source_path.read_bytes()).hexdigest()!=source_sha:
        raise ValueError('Retained original refight source helper changed')
    spec=importlib.util.spec_from_file_location('refight_retained_original_sources',source_path)
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    original_sources=base.original_sources;sha=base.sha;body=base.body;i32=base.i32;u32=base.u32;u16=base.u16
    PLAY=base.PLAY
    def need(value,message):
        if not value:raise ValueError(message)
    def contact(p,seat):
        b=body(p,seat);x=i32(b,8)>>16;y=i32(b,12)>>16
        return (u32(b,0x68)==0x80073D50+4*seat and b[2]==seat and b[5] in(2,3,4,20)
            and 1883<=x<=1893 and abs(1256-y-(2+seat))<=27)
    need(leader==1 and callable(ctx.get('set_input')),'Owned native guest input route required')
    need(scenario in('living','absent','fallen'),'Explicit F123 native participation scenario required')
    clients=ctx['clients'];need(len(clients)in(1,2),'Owned LOCAL or NET required')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    e=dict(kind='F123_Both_original_refight_'+scenario,scenario=scenario,
        frozen_rows={'F123':'9e89dc9c86606d8bd916ad40f360ad8e87b7673b9676d955dd57bb73710ce02c'},
        status='failed',samples=[],inputs=[],captures=[],source_guards=[],resource_reads=[],checks={},controls=[],
        limits=['Only the explicitly selected native participation component is observed; all three LOCAL+NET components required before comparison admission.',
            'Default-off originalCP1 and once source1852/1241 XY/history prerequisite bypasses reachability; Contact protection remains on; fallen uses the predeclared P1 native HP80 prerequisite only. Native original admission/loader/landing/control are earned.',
            'Original source geometry is evaluated against coherent body publications; portal/PLAY/captures are asynchronous, no same-instruction two-peer claim.',
            'Current exact candidate negotiated profile/delay NET or LOCAL split; no other portals, boss defeat/return, human, WAN or native3330 credit.'])
    e['retained_original_source_helper']=dict(path=str(source_path),sha256=source_sha)
    ctx['report']['F123_both_refight']=e
    deadline=time.monotonic()+420;source=None;trace_enabled=False

    def inp(seat,bits,label):
        need(bits in(0,1,6,0x20,0x80,0x4020),'Only declared ordinary pad input')
        e['inputs'].append(dict(seat=seat,bits=bits,label=label,ack=ctx['set_input'](seat,bits)))

    def sample(label):
        need(time.monotonic()<deadline and len(e['samples'])<6000,'F123 bounded420s deadline')
        row=dict(index=len(e['samples']),label=label,peers=[]);e['samples'].append(row)
        for peer,c in enumerate(clients):
            for _ in range(4):
                raw=c.read(debug.DIAGNOSTIC_ADDRESS,debug.DIAGNOSTIC_BYTES)
                try:
                    o=debug.parse_diagnostic(raw).json();o['lifecycle']=list(o['lifecycle']);break
                except debug.UnstableObservation:continue
            else:raise ValueError('No coherent F123 native publication')
            play=c.read(PLAY,0xE0)
            p=dict(peer=peer,observation=o,p1_body_hex=raw[0x1800:0x1958].hex(),p2_body_hex=raw[0x100:0x258].hex(),
                play_hex=play.hex(),tuple=[play[0],play[1],play[12],play[13],play[0x1D]],fixture=receipt(c),fatal_status=raw[0xC8],portal=None,boss=None)
            row['peers'].append(p)
            need(not o['failed'] and not o['mailbox'] and p['fixture']['state']not in(4,5),'Native failure/mailbox/prerequisite refusal')
            if p['tuple'][2:]==[12,0,1]:
                pool=c.read(0x800C1220,0x3340)
                matches=[dict(address=0x800C1220+at,hex=pool[at:at+0xA4].hex())for at in range(0,len(pool),0xA4)
                    if pool[at]&1 and pool[at+1:at+3]==bytes((23,2)) and u32(pool,at+0x10)==0x800ED040]
                need(len(matches)<=1,'Duplicate original portal2');p['portal']=matches[0]if matches else None
                p['original_contacts']=[contact(p,s)for s in(0,1)]
            if p['tuple'][2:]==[12,0,2]:
                ptr=u32(play,0x20)
                if 0x8008EF48<=ptr<0x80090C88 and (ptr-0x8008EF48)%0x9C==0:
                    b=c.read(ptr,0x9C)
                    if b[0]and b[1:3]==bytes((49,0))and u32(b,0x10)==0x800ECFD0:
                        p['boss']=dict(address=ptr,state=b[4],action=b[5],hp=b[0x5C],original_full_hp=play[0x8C])
        return row

    def wait(label,predicate,seconds,updates=18000):
        stop=min(deadline,time.monotonic()+seconds);previous=None;progress=[0]*len(clients)
        while time.monotonic()<stop:
            r=sample(label);now=[p['observation']['native_timer']for p in r['peers']]
            if previous is not None:
                for n,(a,b)in enumerate(zip(previous,now)):
                    delta=(b-a)&0xffffffff
                    if delta<0x80000000:progress[n]+=delta
                    need(progress[n]<=updates,label+': native update bound')
            previous=now
            if predicate(r):return r
            time.sleep(.008)
        raise ValueError(label+': native predicate timed out')

    def capture(label,row):
        for peer,c in enumerate(clients):
            need(len(str(out/f'p{peer}-{label}.png'))<248,'Native capture path bound')
            e['captures'].append(dict(peer=peer,label=label,before_row=row['index'],
                **debug.capture_present(c,out/f'p{peer}-{label}.png',request=c.request),after=debug.observe(c).json()))

    def unused(p):
        return(p['tuple']==[10,0,12,0,1]and p['portal']and bytes.fromhex(p['portal']['hex'])[4:7]==bytes((1,0,0))
            and not any(p['observation'][k]for k in('scene_owner','scene_phase','pause_owner'))
            and not any(bytes.fromhex(p['play_hex'])[n]for n in(0xF,0x10,0x1C)))

    def guest_at_center(p):
        return unused(p)and base.native_pedestal_supported(p)and contact(p,1)and not contact(p,0)and u16(body(p,1),0x7C)==0

    def center_guest(row):
        for _ in range(6):
            if all(guest_at_center(p)for p in row['peers']):return row
            x=i32(body(row['peers'][-1],1),8)
            inp(1,0x80 if x>1888*65536 else 0x20,'guest ordinary centerward pedestal correction')
            # The ten-pixel interval lasts only a few simulation updates.
            # Read one coherent control-peer publication while moving; the
            # full two-peer actor/resource read is deliberately outside this
            # input stop decision. Final settled contact still requires both.
            direction=0x80 if x>1888*65536 else 0x20
            stop=min(deadline,time.monotonic()+6);hit=False
            try:
                for _ in range(512):
                    need(time.monotonic()<stop,'Bounded native guest center approach expired')
                    o=debug.observe(clients[-1]).json();player=o['players'][1];xx=player['x_raw']
                    e.setdefault('fast_center_publications',[]).append(dict(peer=len(clients)-1,native_timer=o['native_timer'],sequence=o['sequence'],x_raw=xx,y_raw=player['y_raw'],action=player['action'],direction=direction))
                    if (direction==0x20 and xx>=1883*65536)or(direction==0x80 and xx<=1893*65536):hit=True;break
                    time.sleep(.005)
                need(hit,'No source-qualified native guest center approach')
            finally:inp(1,0,'neutral guest at control-peer interval; await both settled publications')
            row=wait('native pedestal support and consumed neutral',lambda r:all(unused(p)and body(p,1)[5]==2 and u16(body(p,1),0x7C)==0 for p in r['peers']),12,720)
        need(all(guest_at_center(p)for p in row['peers']),'Bounded native pedestal centering failed')
        return row

    def endpoint(p):
        if scenario=='living':return base.native_idle(p,2)and base.fullfeet(p,source['destination_terrain'])
        o=p['observation'];seat=0 if scenario=='absent'else 1;b=body(p,seat)
        if not(p['tuple']==[10,0,12,0,2]and o['ready']==o['enrolled']==1 and o['lifecycle']==([0,2]if scenario=='absent'else[5,0])and not any(o[k]for k in('scene_owner','scene_phase','pause_owner'))):return False
        x=i32(b,8)>>16;foot=(i32(b,12)>>16)+2+seat+19
        codes=[source['destination_terrain'].query(xx,foot)['code']for xx in range(x-11,x+11)]
        p['survivor_feet']=dict(seat=seat,x=x,foot=foot,codes=codes,native_ground=b[0x70])
        if not(b[0]and b[3]and b[4:6]==bytes((1,2))and b[2]==seat and 0<b[0x5C]<128 and u32(b,0x68)==0x80073D50+4*seat and not b[0x67]and b[0x70]&8 and foot==448 and set(codes)=={0x38}and not any(b[n]for n in(0x7A,0xD0,0xD4,0xE0))):return False
        if scenario=='absent':
            original=body(e['samples'][e['source_ready']]['peers'][p['peer']],1);other=body(p,1)
            return other[4]==3 and other[0x5C]==original[0x5C]and other[0xA8:0xBA]==original[0xA8:0xBA]
        return body(p,0)[4]==3

    def approach_portal(seat,label):
        def admitted(r):
            return all(p['portal']and bytes.fromhex(p['portal']['hex'])[4]==1 and bytes.fromhex(p['portal']['hex'])[6]in(1,2,3)
                and (body(p,seat)[5]in(20,22)or body(p,seat)[0xD1]in(20,22))for p in r['peers'])
        inp(seat,0x4020,label+' ordinary jump Right to pedestal left edge')
        try:over=wait('native traveler over pedestal edge or actual admission',lambda r:admitted(r)or i32(body(r['peers'][-1],seat),8)>=1877*65536,8,480)
        finally:inp(seat,0,'release jump Right over original pedestal')
        e.setdefault('ordinary_approaches',[]).append(dict(seat=seat,over_row=over['index']))
        if admitted(over):return over
        def supported(p):
            b=body(p,seat)
            return unused(p)and b[4:6]==bytes((1,2))and not b[0x67]and b[0x71]&8 and 1875*65536<=i32(b,8)<=1901*65536 and (i32(b,12)>>16)+2+seat+19==1248
        landed=wait('native traveler pedestal support or actual admission',lambda r:admitted(r)or all(supported(p)for p in r['peers']),15,900)
        if admitted(landed):return landed
        direction=0x80 if i32(body(landed['peers'][-1],seat),8)>1888*65536 else 0x20
        inp(seat,direction,label+' ordinary centerward native pedestal input')
        try:return wait('actual native original contact command20 and portal progression',admitted,20,1200)
        finally:inp(seat,0,'neutral after actual original admission')

    def guards(label,boss=False):
        for peer,c in enumerate(clients):
            for g in source['boss_proof']['guards']if boss else source['guards']:
                if g.get('name')in('portal2_placement','Yammark_CP2_placement'):continue
                a=int(g['address'],16);count=int(g['end'],16)-a if boss else g['bytes']
                wanted=source['boss'][a-0x800FA000:a-0x800FA000+count]if boss and a>=0x800FA000 else source['raw'](a,count)
                raw=c.read(a,count);need(raw==wanted,'Original native code differs '+hex(a))
                e['source_guards'].append(dict(peer=peer,label=label,address=hex(a),bytes=count,sha256=sha(raw),expected=sha(wanted)))

    def resources(label):
        t=source['destination_terrain']if label=='destination'else source['terrain']
        for peer,c in enumerate(clients):
            before=c.read(0x1F800004,12);records=[];values=[]
            for name,address,wanted in zip(('layout','meta','desc'),struct.unpack('<III',before),(t.layout,t.metatiles,t.descriptors)):
                need(not address&3 and 0x80010000<=address<=0x80200000-len(wanted),'Original resource pointer extent')
                raw=b''.join(c.read(address+n,min(65536,len(wanted)-n))for n in range(0,len(wanted),65536));p=out/f'p{peer}-{label}-{name}.bin';p.write_bytes(raw);values.append(raw)
                records.append(dict(path=str(p),sha256=sha(raw),original=sha(wanted)))
            need(before==c.read(0x1F800004,12)and values[0]==t.layout,'Native resource read bracket/layout differs')
            need(base.collision_projection(values[1],values[2])==base.collision_projection(t.metatiles,t.descriptors),'Original collision projection differs')
            e['resource_reads'].append(dict(peer=peer,label=label,resources=records,collision_equivalence=True))

    try:
        source=original_sources(original_exe)
        for seat in(0,1):inp(seat,0,'neutral original pads')
        initial=wait('fresh original baseline',lambda r:all(p['tuple']==[10,0,0,0,0]and p['observation']['lifecycle']==[0,0]for p in r['peers']),25)
        need(all(p['fixture']['generation']==p['fixture']['latch']==p['fixture']['tainted']==0 for p in initial['peers']),'Fresh one-shot prerequisite required')
        inp(1,6,'ordinary guest L3+R3 original CP1 prerequisite')
        try:wait('accepted one-shot chord',lambda r:all(p['fixture']['latch']in(1,2)for p in r['peers']),15)
        finally:inp(1,0,'release one-shot chord')
        ready=wait('native original CP1 standing after once XY setup',lambda r:all(base.native_idle(p,1)and p['fixture']['state']==3 and unused(p)
            and all((i32(body(p,s),8),i32(body(p,s),12))==(1852*65536,y*65536)for s,y in((0,1243),(1,1242)))for p in r['peers']),300)
        expected=dict(generation=1,state=3,reason=0,stage=12,section=0,checkpoint=1,nonce=0x4C524650,initializer_entries=1,record='80072978',tainted=1,authority=1,latch=2)
        for p in ready['peers']:need(all(p['fixture'].get(k)==v for k,v in expected.items()),'Exact original CP1 receipt changed')
        guards('source');resources('source');e['source_ready']=ready['index'];capture('source',ready)
        for c in clients:c.request('fn_disable');c.request('fn_clear');c.request('fn_filter',lo='8001E1BC',hi='8001E1C0')
        trace_enabled=True
        if scenario=='living':
            inp(1,0x4020,'guest alone ordinary jump Right onto native pedestal')
            try:over=wait('guest passes original pedestal left edge',lambda r:i32(body(r['peers'][-1],1),8)>=1877*65536,8,480)
            finally:inp(1,0,'neutral over pedestal')
            supported=wait('native pedestal landing',lambda r:all(base.native_pedestal_supported(p)for p in r['peers']),15,900)
            centered=center_guest(supported);capture('one-contact-wait',centered);e['wait_begin']=centered['index']
            start=[p['observation']['native_timer']for p in centered['peers']]
            waiting=wait('Both waits30 real native world updates',lambda r:all(((p['observation']['native_timer']-start[n])&0xffffffff)>=30 for n,p in enumerate(r['peers'])),20,1200)
            window=e['samples'][centered['index']:waiting['index']+1]
            need(all(guest_at_center(p)and i32(body(p,0),8)==1852*65536 and u16(body(p,0),0x7C)==0 for r in window for p in r['peers']),'Both admitted with only one living contact')
            e['wait_end']=waiting['index'];capture('one-contact-held',waiting)
            inp(1,0x80,'ordinary guest Left aborts its waiting native contact')
            try:aborted=wait('actual Left abort leaves original portal unused',lambda r:all(unused(p)and not contact(p,1)and i32(body(p,1),8)<1883*65536 for p in r['peers']),6,360)
            finally:inp(1,0,'neutral after genuine contact abort')
            e['abort']=aborted['index'];capture('abort',aborted)
            centered=center_guest(aborted);e['last_guest_contact']=centered['index']
            admit=approach_portal(0,'primary joins waiting living guest')
            e['admission']=admit['index'];capture('admit',admit)
        else:
            if scenario=='absent':
                original=[body(p,1)for p in ready['peers']]
                inp(1,1,'real guest Select90 native withdrawal')
                try:leaving=wait('native guest LEAVING from actual Select hold',lambda r:all(p['observation']['lifecycle'][1]==1 for p in r['peers']),30,1800)
                finally:inp(1,0,'release Select; no new request through portal arrival')
                absent=wait('genuine native outgoing finishes ABSENT',lambda r:all(p['observation']['lifecycle']==[0,2]and body(p,1)[4]==3 for p in r['peers']),45,2700)
                need(all(body(p,1)[0x5C]==original[n][0x5C]and body(p,1)[0xA8:0xBA]==original[n][0xA8:0xBA]for n,p in enumerate(absent['peers'])),'Withdrawal altered guest personal inventory')
                e['native_precondition']=dict(kind='Select_LEAVING_to_native_ABSENT',leaving=leaving['index'],completed=absent['index'],source_threshold=90)
                capture('native-absent',absent);traveler=0
            else:
                inp(1,0,'neutral after completed CP1 before agreed primary fatal edge')
                armed=wait('agreed P1 fatal armed after neutral',lambda r:all(base.native_idle(p,1)and p['fatal_status']==5 for p in r['peers']),15,900)
                inp(1,6,'ordinary second P2 L3+R3 requests declared P1 native fatal')
                try:requested=wait('one agreed primary fatal request consumed',lambda r:all(p['fatal_status']==9 for p in r['peers']),15,900)
                finally:inp(1,0,'release consumed native fatal chord')
                fatal=wait('actual original primary native fatal',lambda r:all(p['observation']['lifecycle'][0]in(4,5)and p['observation']['lifecycle'][1]==0 for p in r['peers']),30,1800)
                fallen=wait('original native death fully FALLEN with living guest',lambda r:all(p['observation']['lifecycle']==[5,0]and body(p,0)[4]==3 and body(p,1)[0x5C]>0 for p in r['peers']),70,4200)
                e['native_precondition']=dict(kind='agreed_P1_HP80_request_then_original_native_FATAL_FALLEN',armed=armed['index'],requested=requested['index'],fatal=fatal['index'],completed=fallen['index'],contact_protection='on')
                capture('native-fallen',fallen);traveler=1
            admit=approach_portal(traveler,'sole living participant excludes absent/fallen partner')
            e['admission']=admit['index'];capture('admit',admit)
        arrived=wait('actual CP2 loader then native released both arrivals',lambda r:all(endpoint(p)and p['boss']and p['boss']['hp']==p['boss']['original_full_hp']==48 and 4<=p['boss']['action']<=10 for p in r['peers']),300)
        e['arrival']=arrived['index'];guards('destination',True);resources('destination');capture('arrive',arrived)
        e['native_initializer_trace']=[]
        for peer,c in enumerate(clients):
            t=c.request('fn_entry_dump',seq_lo='0',count=256);need(t['oldest']==0 and len(t['entries'])==t['seq_hi']and any(int(x['func'],16)==0x8001E1BC and int(x['a0'],16)==PLAY for x in t['entries']),'Actual original CP2 initializer trace missing')
            e['native_initializer_trace'].append(dict(peer=peer,trace=t));c.request('fn_disable')
        for seat in ((1,0)if scenario=='living'else(0,)if scenario=='absent'else(1,)):
            before=sample('before separate native control');xs=[i32(body(p,seat),8)for p in before['peers']];other=[body(p,1-seat)[8:16]for p in before['peers']]
            inp(seat,0x80,'ordinary independent Left after native release')
            try:moved=wait('actual independent native movement',lambda r:any(i32(body(p,seat),8)<xs[n]-65536 for n,p in enumerate(r['peers'])),5,300)
            finally:inp(seat,0,'neutral at first observed movement')
            settled=wait('native fullfeet and consumed neutral',lambda r:all(endpoint(p)and i32(body(p,seat),8)<xs[n]-65536 and body(p,1-seat)[8:16]==other[n]and u16(body(p,seat),0x7C)==0 for n,p in enumerate(r['peers'])),15,900)
            e['controls'].append(dict(seat=seat,before=before['index'],moved=moved['index'],settled=settled['index']))
        final=sample('F123 living component final endpoint');e['final_endpoint']=final['index'];capture('controls',final)
        if scenario=='living':
            e['checks']=dict(original_CP1_source_and_native_ready=True,one_living_contact_waits30_native_updates=True,primary_neutral_outside_contact=True,
                actual_Left_aborts_without_admission=True,ordinary_primary_approach_then_original_Both_admission=True,actual_original_CP2_initializer=True,
                native_full48HP_boss_active_and_both_released=True,both_original_full22feet_floor448=True,separate_native_controls=len(e['controls'])==2,
                actual_composed_captures=len(e['captures'])==7*len(clients))
        else:
            e['checks']=dict(original_CP1_source_and_native_ready=True,actual_native_absent_or_fallen_precondition=True,
                Both_permits_genuine_sole_living_original_portal_admission=True,actual_original_CP2_initializer=True,
                native_full48HP_boss_active_and_survivor_released=True,source_full22feet_floor448_and_native_control=len(e['controls'])==1,
                excluded_partner_remains_absent_or_fallen_every_peer=all(endpoint(p)for p in final['peers']),actual_composed_captures=len(e['captures'])==5*len(clients))
        need(all(e['checks'].values()),'F123 living native component incomplete')
        if callable(ctx.get('network')):ctx['network']()
        e['status']=success;return e
    except Exception as error:
        e.update(error=str(error),traceback=traceback.format_exc())
        if e['samples']:
            try:capture('failure',e['samples'][-1])
            except Exception as capture_error:e['capture_error']=str(capture_error)
        raise
    finally:
        for seat in(0,1):
            try:inp(seat,0,'final owned neutral')
            except Exception as error:e.setdefault('cleanup_errors',[]).append(str(error))
        if trace_enabled:
            for c in clients:
                try:c.request('fn_disable')
                except Exception as error:e.setdefault('cleanup_errors',[]).append(str(error))
        (out/'observations.json').write_text(json.dumps(e,indent=2)+'\n',encoding='utf-8',newline='\n')
