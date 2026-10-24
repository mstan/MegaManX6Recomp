"""Perturb personal HP with ordinary authored gameplay before a mapped load.

This observer owns no process and writes no guest memory. The parent owns the
exact image, original source binding, host pad route and completed state load.
"""
import time

import coop_debug as debug
import mmx6_coop_contact as zero_contact
import mmx6_native_contact_audio as native_contact
import mmx6_coop_primary_audio as primary
import qualify_mmx6_coop_state as state


def require(ok, message):
    if not ok:
        raise debug.DebugError(message)


def restored_resources(saved, damaged, restored):
    before, changed, after = [state.private_resources(row) for row in (saved, damaged, restored)]
    return dict(
        both_saved_heroes_alive=all(p[0] > 0 for p in before),
        genuine_hp_divergence_both_heroes=all(0 < q[0] < p[0] for p, q in zip(before, changed)),
        full_personal_resources_restored=after == before,
    )


def coherent_primary(client, case):
    row = case.sample('Published primary body before native resource contact')
    observation = row['observation']
    player = primary.player(bytes.fromhex(row['p1_body_hex']), observation)
    location = client.read(native_contact.native.reference.PLAY+12, 2)
    player.update(mode=[observation['native_mode'], observation['native_phase']],
                  stage=location[0], section=location[1],
                  observation_method='coherent published P1 body/mode/timer; common PLAY location separately read')
    return player


def exercise(ctx, case, sources, *, timeout=90):
    require(ctx['mode'] in ('local', 'netplay') and ctx['input_path'] == 'published_host',
            'Native resource route needs the owned published host sampler')
    if ctx['mode'] == 'netplay':
        require(len(ctx['clients']) == 2 and callable(ctx.get('network')),
                'Paired native resource route needs both owned peers and live transport validation')
    require(0 < timeout <= 120, 'Native resource route needs a bounded deadline')
    client = ctx['clients'][0]
    target, overlay = sources['target'], sources['zero_overlay']
    zero_contact.validate_zero_overlay(overlay)
    for guard in target['code_guards']:
        require(client.read(guard['address'], guard['bytes']).hex() == guard['source_hex'],
                'Live original contact/hurt code differs from pinned source')
    route = dict(status='failed_setup', p2_observations=[], p1_observations=[], controls=[],
                 source=target, checks={}, bypasses=[], limits=[
        'HP changes use ordinary host input and native gameplay; ammo spending is separate.',
        'P2 committed contact is source/counter/reaction matched. P1 committed native HP loss is observed; exact P1 damage caller is not claimed.',
        'P1 body/mode/timer use the coherent published diagnostic; common PLAY location, enemy pool and placement use separate RPCs.',
    ])
    case.evidence['native_resource_damage'] = route
    start = case.sample('Before actual native resource divergence')
    require([p[0] for p in state.private_resources(start)] == [32, 32],
            'Native resource route requires both saved heroes at full HP')
    deadline = time.monotonic() + timeout

    def hold(seat, bits, frames, label):
        require(time.monotonic() < deadline, 'Native resource route deadline expired')
        record = dict(seat=seat, pressed=bits, native_ticks=frames, label=label)
        route['controls'].append(record)
        try:
            record['acknowledgment'] = ctx['set_input'](seat, bits)
            advanced = ctx['native_advance'](frames, label)
            record['after'] = advanced.json()
        finally:
            ctx['set_input'](seat, 0)

    try:
        previous = None
        stalled, jumped = 0, False
        for step in range(250):
            require(time.monotonic() < deadline, 'P2 native contact deadline expired')
            row = zero_contact.observe_contact(client, overlay)
            route['p2_observations'].append(row)
            p1, p2 = row['players']
            require(p1['hp_raw'] == 32 and p1['state'] == p2['state'] == 1,
                    'P2 resource route damaged primary or lost a living hero')
            require(not zero_contact.hazardous(row) and row['expected_damage'] == 4,
                    'P2 resource route reached a hazard or changed source damage')
            if p2['hp'] < 32:
                history = route['p2_observations']
                accepted = next((before for before in reversed(history[:-1])
                                 if zero_contact.contact_evidence(before, [row])), None)
                if accepted:
                    route['p2_accepted'] = dict(before=accepted, after=row)
                    break
                require(p2['hp'] == 28, 'P2 resource route lost more than one ordinary contact')
                hold(1, 0, 1, 'Observe committed P2 hurt reaction')
                continue
            require(p2['hp'] == 32 and row['p2_contact_counter'] <= 1,
                    'P2 resource route began with unrelated damage')
            actor = row['instance']
            x = row['observation']['players'][1]['x_raw']
            stalled = stalled + 1 if previous and abs(x-previous['observation']['players'][1]['x_raw']) < 65536 else 0
            if stalled >= 2 and not jumped and x < 350 << 16:
                bits, frames, jumped = 0x4020, 24, True
            else:
                dx = actor['x_raw']-x if actor else 10 << 16
                bits = 0x20 if dx > 3 << 16 else 0x80 if dx < -(3 << 16) else 0
                frames = 4
            hold(1, bits, frames, 'Native P2 contact seek '+str(step))
            previous = row
        else:
            raise debug.DebugError('P2 native resource route exhausted its input bound')

        previous = native_contact.observe(client, target, player_sample=lambda: coherent_primary(client, case))
        require(previous['player']['hp'] == 32, 'P1 was damaged before its own resource route')
        last_x, stalled, jumps = None, 0, 0
        for step in range(250):
            require(time.monotonic() < deadline, 'P1 native contact deadline expired')
            row = native_contact.observe(client, target, player_sample=lambda: coherent_primary(client, case))
            route['p1_observations'].append(row)
            player, actor = row['player'], row['actor']
            require(player['mode'][:2] == [10, 0] and player['stage'] == player['section'] == 0 and
                    (player['character'], player['form'], player['state']) == (0, 1, 1) and
                    player['hp'] > 0 and not native_contact.hazardous(player),
                    'P1 resource route left living native intro or reached a terrain hazard')
            if not player['pending_hit']:
                changed = native_contact.hp_change(previous, row)
                if changed:
                    route['p1_accepted'] = dict(before=previous, after=row, change=changed)
                    break
                previous = row
            x = player['x']
            stalled = stalled + 1 if last_x is not None and abs(x-last_x) < 65536 else 0
            bits, frames = native_contact.seek_input(player, actor, target, stalled, jumps)
            if bits & 0x4000:
                jumps += 1
            hold(0, bits, frames, 'Native P1 contact seek '+str(step))
            last_x = x
        else:
            raise debug.DebugError('P1 native resource route exhausted its input bound')
        damaged = case.sample('Both heroes genuinely damaged before mapped load')
        route['damaged'] = damaged
        route['checks']['both_native_hp_values_diverged'] = all(
            0 < p[0] < 32 for p in state.private_resources(damaged))
        require(all(route['checks'].values()), 'Native route did not damage both surviving heroes')
        route['status'] = 'both_heroes_native_hp_perturbed'
        return damaged
    finally:
        for seat in (0, 1):
            ctx['set_input'](seat, 0)
