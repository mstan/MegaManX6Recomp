"""Offline native hurt/death audio reference using authored enemies and input.

No co-op diagnostic, HP/state/position write, synthetic hit or completion flag.
Enemy attribution and body/PLAY reads are retained as separate observations.
"""
from __future__ import annotations

from pathlib import Path
import struct
import time

import inventory_mmx6_coop_content as content
import mmx6_coop_contact as contact
import qualify_mmx6_coop_enemy_admission as enemies
import qualify_mmx6_native_audio as native

CONTACT, DEATH = 0x80030ECC, 0x8003D8A8
TARGETS = native.TRACE_TARGETS | {CONTACT, DEATH}
STAGE_BASE = 0x800E9860
TARGETS_BY_STAGE = {
    0: dict(member=2, member_sha256='d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607',
            record=0x800FA2DC, object_id=1, subtype=1, x=416, y=1080),
    1: dict(member=3, member_sha256='68e8b41b5618ccfced88057553597749513f4aeb25191004f886f9d881b633ea',
            record=0x800F6540, object_id=7, subtype=0, x=544, y=380),
}


def load_source(exe_path, disc_path, stage):
    native.require(stage in TARGETS_BY_STAGE, 'Native contact audio stage is unqualified')
    target = dict(TARGETS_BY_STAGE[stage],stage=stage,section=0)
    disc = content.RawDisc(Path(disc_path))
    try:
        files = disc.inventory_files()
    finally:
        disc.stream.close()
    native.require(native.original.sha(files['SLUS_013.95']) == content.EXE_SHA256 and
                   native.original.sha(files['ROCK_X6.BIN']) == content.BIN_SHA256,
                   'Native contact source EXE/BIN identities changed')
    native.require(Path(exe_path).read_bytes() == files['SLUS_013.95'], 'Native contact EXE differs from original disc')
    exe = content.Executable(files['SLUS_013.95'])
    archive = files['ROCK_X6.BIN']
    member = content.archive_members(archive)[target['member']]
    offset = member['sector']*2048
    payload = archive[offset:offset+member['size']]
    native.require(native.original.sha(payload) == target['member_sha256'], 'Authored native stage member changed')
    at = target['record']-STAGE_BASE
    native.require(0 <= at <= len(payload)-8, 'Authored native contact record escaped its stage member')
    record = payload[at:at+8]
    native.require(tuple(record[:4]) == (0,target['object_id'],target['subtype'],0) and
                   struct.unpack_from('<hh',record,4) == (target['x'],target['y']),
                   'Authored native contact placement changed')
    target['original_record_hex'] = record.hex()
    target['code_guards'] = []
    for name,start,end in (('native_hurt_audio',0x8003963C,0x80039694),
                           ('native_phase2_death_audio',DEATH,0x8003D9F8),
                           ('native_spawn_allocation_and_retry_bits',0x8002A254,0x8002A300)):
        raw=exe.data[2048+start-exe.base:2048+end-exe.base]
        target['code_guards'].append(dict(name=name,address=start,bytes=len(raw),
            sha256=native.original.sha(raw),source_hex=raw.hex()))
    return target


def placement_matches(expected, actual):
    # The original spawner ORs allocation bit0 at8002A25C/264 and updates the
    # high-nibble admission retry state at8002A2B8..2F4 (0h..50h). The category
    # low nibble, type/subtype and coordinates remain the authored values.
    return (len(expected) == len(actual) == 8 and actual[0]&~1 == expected[0] and
        actual[1:3] == expected[1:3] and actual[3]&15 == expected[3]&15 and
        actual[3]&0xF0 in range(0,0x60,0x10) and actual[4:] == expected[4:])


def target_actor(raw_pool, target):
    live,_ = enemies.parse_pool(raw_pool)
    matches = [a for a in live if int(a['origin'],16) == target['record'] and
               a['type'] == target['object_id'] and a['subtype'] == target['subtype']]
    native.require(len(matches) <= 1, 'Multiple native actors claim the authored contact placement')
    actor = matches[0] if matches else None
    pending = None
    if actor:
        body=bytes.fromhex(actor['body_hex'])
        pointer=struct.unpack_from('<I',body,0x50)[0]
        if actor['phase'] == 0 and actor['hp'] == actor['strength'] == pointer == 0:
            pending,actor=actor,None
        else:
            actor.update(contact_class=body[0x62],contact_pointer=pointer)
    return actor,pending,len(live)


def observe(session,target):
    row = native.native_sample(session)
    raw = session.read(enemies.POOL,enemies.STRIDE*enemies.SLOTS)
    actor,pending,live_count = target_actor(raw,target)
    record = session.read(target['record'],8)
    expected = bytes.fromhex(target['original_record_hex'])
    native.require(placement_matches(expected,record),
                   'Live native contact placement differs beyond original allocation/retry fields: '
                   +record.hex()+' expected '+expected.hex())
    if actor and actor['contact_pointer']:
        pointer=actor['contact_pointer']
        native.require(0x80010000 <= pointer <= 0x801FFFFC and not pointer&3,
                       'Native authored contact box escaped original RAM')
        actor['contact_box_hex'] = session.read(pointer,4).hex()
    return dict(player=row,actor=actor,pending_initialization=pending,live_enemy_count=live_count,
                record_hex=record.hex(),observation_method='separate owned body/PLAY, enemy-pool and placement RPCs')


def hazardous(player):
    return any((v&0x0C) == 0x0C or (v&3) == 3 for v in (player['terrain'],player['previous_terrain']))


def hp_change(before,after):
    """Only committed masked HP losses; a pending-hit bit is not damage."""
    old,new=before['player'],after['player']
    if old['pending_hit'] or new['pending_hit'] or new['hp'] == old['hp']:
        return None
    native.require(new['hp'] < old['hp'], 'Native contact audio health increased or retried during route')
    native.require(not hazardous(old) and not hazardous(new), 'Terrain hazard confounds native contact audio reference')
    return dict(before=old['hp'],after=new['hp'],loss=old['hp']-new['hp'],
                before_timer=old['timer'],after_timer=new['timer'],
                reaction=new['reaction'],action=new['action'],state=new['state'],
                actor_before=before['actor'],actor_after=after['actor'],
                exact_contact_caller_identity='unverified until retained native trace is assessed')


def seek_input(player,actor,source,stalled,jumps):
    dx=(actor['x_raw'] if actor else source['x']<<16)-player['x']
    bits=0x20 if dx > 3<<16 else 0x80 if dx < -(3<<16) else 0
    # A projectile can interrupt the first ledge jump. Committed damage does
    # not remove the original player's ability to try another ordinary jump.
    jump=(stalled >= 2 and player['hp'] > 0 and player['ground'] and not player['airborne']
          and not player['pending_hit'] and not player['reaction_lock'] and jumps < 8 and abs(dx) > 24<<16)
    return bits | (0x4000 if jump else 0),24 if jump else 4


def death_audio(matched):
    """Character vocal3/16 and shared effect3/14 are separate contracts."""
    def original(number,ret):
        return [m for m in matched if (m['record']['group'],m['record']['record']) == (3,number)
            and int(m['source_call']['target'],16) == native.SOUND
            and int(m['source_call']['a2'],16) == native.reference.PLAYER
            and int(m['source_call']['ra'],16) == ret]
    vocals,effects=original(16,0x8003D9BC),original(14,0x8003D9CC)
    native.require(vocals and effects, 'Native death lacks distinct original vocal3/16 and effect3/14 SOUND identities')
    native.require(all(m['lifetime']['disposition'] == 'natural_end' for m in vocals),
                   'Native death vocal3/16 natural lifetime was not observed')
    native.require(all(m['lifetime']['disposition'] in ('natural_end','keyed_off') for m in effects),
                   'Native death effect3/14 terminal disposition was not observed')
    return vocals,effects


def exercise(session,observer,source,case,*,timeout=150,max_steps=500):
    native.require(0 < timeout <= 180 and 1 <= max_steps <= 500, 'Native contact deadline/step bound invalid')
    case.update(kind='offline_authored_native_contact_hurt_death_audio',status='failed_setup',
        observations=[],inputs=[],hp_changes=[],checks={},bypasses=[],limits=[
            'R4 audio reference only; no co-op contact, enemy AI, R2, campaign or full R4/R12 pass.',
            'Native player HP is read coherently; PLAY, enemy pool, placement and audio trace remain separate RPCs.',
            'Observed HP losses do not alone prove an exact contact caller or damage calculator; source calls are retained separately.',
            'Native primary death ends character vocal3/16 naturally; later global STOP may KEYOFF shared effect3/14. These are separate native reference dispositions, not a private co-op lifecycle contract.',
            'No active Saber is held at death, so the native death STOP7 calls do not qualify an active STOP7 lifetime.'])
    case['source'] = source
    for guard in source['code_guards']:
        native.require(session.read(guard['address'],guard['bytes']).hex() == guard['source_hex'],
                       'Live native hurt/death code differs from the original EXE')
    session.request('fntrace_arm_clear')
    for target in sorted(TARGETS):session.request('fntrace_arm',target=hex(target))
    armed=session.request('fntrace_armed')
    native.require(armed['count'] == len(TARGETS) and {int(v,16) for v in armed['targets']} == TARGETS,
                   'Native contact audio trace targets differ')
    session.request('fntrace_clear')
    session.request('clear_input',port=1)
    observer.poll()
    cursor,driver=observer.cursor,observer.driver()
    deadline=time.monotonic()+timeout
    initial=observe(session,source)
    before=initial
    native.require(initial['player']['hp'] == 32 and initial['player']['state'] == 1 and
                   initial['player']['mode'][:2] == [10,0] and initial['player']['stage'] == source['stage'],
                   'Native contact audio needs its fresh full-health selected native body')
    expected_character=(initial['player']['character'],initial['player']['form'])
    selected,stalled,jumps,last_x=None,0,0,None

    def sample():
        native.require(time.monotonic() < deadline, 'Native contact audio deadline expired')
        observer.poll()
        row=observe(session,source)
        player=row['player']
        native.require(player['mode'][:2] == [10,0] and player['stage'] == source['stage'] and
                       player['section'] == source['section'] and
                       (player['character'],player['form']) == expected_character,
                       'Native contact audio left its stage/character context before fatal observation')
        case['observations'].append(row)
        native.require(not hazardous(player), 'Native contact route reached a terrain hazard')
        return row

    def advance(frames):
        start=native.native_sample(session)['timer']
        for _ in range(200):
            row=sample()
            elapsed=(row['player']['timer']-start)&0xFFFFFFFF
            native.require(elapsed < 0x80000000 and elapsed <= 120, 'Native contact input clock regressed/escaped')
            if row['player']['hp'] == 0 or elapsed >= frames:return row
            time.sleep(.006)
        raise native.debug.DebugError('Native contact input failed to consume its bounded timer window')

    try:
        for step in range(max_steps):
            row=sample();player=row['player'];actor=row['actor']
            if not player['pending_hit']:
                changed=hp_change(before,row)
                if changed:case['hp_changes'].append(changed)
                before=row
            if actor and player['hp'] > 0:
                native.require(actor['phase'] == 1, 'Native contact target left its live authored phase before fatal damage')
                if selected is None:selected=actor['address']
                native.require(actor['address'] == selected, 'Native contact target changed its authored instance')
            if player['hp'] == 0 and not player['pending_hit']:
                native.require(case['hp_changes'] and case['hp_changes'][-1]['after'] == 0,
                               'Native death lacks an observed committed fatal HP loss')
                case['fatal_observation']=row
                break
            native.require(player['state'] == 1, 'Native body left its living phase without observed fatal HP loss')
            x=player['x']
            stalled=stalled+1 if last_x is not None and abs(x-last_x) < 65536 else 0
            bits,frames=seek_input(player,actor,source,stalled,jumps)
            if bits&0x4000:jumps+=1
            acknowledgment=session.request('press',port=1,buttons=bits^65535,frames=0)
            try:
                end=advance(frames)
                case['inputs'].append(dict(pressed=bits,requested_native_ticks=frames,
                    acknowledgment=acknowledgment,before=player,after=end['player']))
            finally:session.request('clear_input',port=1)
            last_x=x
        else:
            raise native.debug.DebugError('Native authored contact route exhausted its input-step bound')
        session.request('clear_input',port=1)
        # Native phase2/3 and its one-shot death sounds can run after the fatal
        # body sample. Use a wall bound, not the world timer after primary death.
        drain_deadline=min(deadline,time.monotonic()+3)
        while time.monotonic() < drain_deadline:
            observer.poll()
            death_keys=[e for e in observer.events if e['seq'] >= cursor and e['kind'] == 'KEYON' and
                any(r['group'] == 3 and r['record'] == 14 and any(e['v'] == t['voice'] and
                    e['addr'] == driver['bases'][r['effective_bank_group']]+t['offset'] and
                    all(e[k] == t[k] for k in ('pitch','adsr_lo','adsr_hi')) for t in r['tones'])
                    for r in observer.source['records'])]
            if death_keys and all(native.audio.lifetime(observer.events,e)['disposition'] in ('natural_end','keyed_off')
                                  for e in death_keys):break
            time.sleep(.015)
        observer.poll()
        case['trace']=native.trace_page(session,targets=TARGETS)
        case['events']=[e for e in observer.events if e['seq'] >= cursor]
        case['matched']=[];case['sample_only']=[]
        for event in case['events']:
            if event['kind'] != 'KEYON':continue
            matched=observer.identify(event,case['trace']['entries'],driver)
            if matched:
                matched['lifetime']=native.audio.lifetime(case['events'],event)
                case['matched'].append(matched)
            else:
                matched=observer.identify_sample_only(event,driver)
                if matched:
                    matched['lifetime']=native.audio.lifetime(case['events'],event)
                    case['sample_only'].append(matched)
        hurt=[m for m in case['matched'] if m['record']['group'] == 3 and m['record']['record'] in (0,1)
              and int(m['source_call']['ra'],16) == 0x80039684]
        native.require(hurt, 'Native contact route lacks original hurt SOUND/sample identity')
        death_vocals,death_effects=death_audio(case['matched'])
        case['death_vocal_dispositions']=[m['lifetime'] for m in death_vocals]
        case['death_effect_dispositions']=[m['lifetime'] for m in death_effects]
        case['checks']=dict(original_native_hurt_audio=True,original_native_death_audio=True,
            actual_committed_fatal_HP_loss=True,original_placement_source=True,terrain_hazards_excluded=True,
            death_vocal_natural_end=True,death_effect_terminal_observed=True,
            stable_character_driver=observer.driver() == driver)
        native.require(all(case['checks'].values()), 'Native contact audio driver/context changed')
        case['status']='bounded_native_hurt_death_reference_observed'
    finally:
        session.request('clear_input',port=1)
        if 'trace' not in case:
            try:case['trace']=native.trace_page(session,targets=TARGETS)
            except Exception as error:case['trace_error']=str(error)
        if 'events' not in case:case['events']=[e for e in observer.events if e['seq'] >= cursor]
