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
