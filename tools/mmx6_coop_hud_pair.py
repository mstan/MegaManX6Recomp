"""Exact-image loopback HUD anchors and both native menu owners.

Parent supplies two owned peers, ordinary input, profile/CRC gates and transport
pacing. No guest-memory or fixture writes occur in this observer.
"""
from pathlib import Path
import time

import coop_debug as debug
import mmx6_coop_hud_presentation as hud
import mmx6_coop_jump_audio_pair as binding

require = hud.require


def exercise(ctx, *, expected_sha, layout, source):
    binding.validate_context(ctx, expected_sha)
    report, clients = ctx['report'], ctx['clients']
    evidence = dict(status='failed_behavior', checks={}, peers=[dict(captures=[]) for _ in clients],
                    menus=[], observations=[], layout=layout, limits=[
        'Two owned Windows peers on one host; current exact image/profile only.',
        'Native composed menu artwork needs visual review. Physical devices and other hosts are separate.',
        'Actual native input changes HP; ammo ownership is a separate qualification.',
    ])
    report['hud_presentation'] = evidence
    report['jump_audio_private_cards_before'] = binding.ownership.cards(ctx['output'])
    windows = [hud.OwnedWindow(dict(request=client.request,
        report=dict(owned_pid=report['peers'][peer]['owned_pid'])), evidence['peers'][peer])
        for peer, client in enumerate(clients)]

    def sample(label):
        rows = ctx['both'](lambda peer: hud.state.private_sample(clients[peer]))
        for row in rows:
            o = row['observation']
            require(not o['scene_owner'] and tuple(o['lifecycle']) == (0, 0) and
                    all(p['hp'] > 0 and p['state'] == 1 for p in o['players']), 'HUD pair lost living native actors')
        evidence['observations'].append(dict(label=label, peers=rows))
        return rows

    def wait(predicate, label):
        deadline = time.monotonic()+18
        while time.monotonic() < deadline:
            rows = sample(label)
            if predicate(rows):
                return rows
            ctx['transport_window'](2)
        raise debug.DebugError(label+': native paired predicate timed out')

    def captures(label, *, before=None, meter=False):
        before = before if before is not None else sample(label+' before')
        receipts = ctx['both'](lambda peer: debug.capture_present(clients[peer],
            Path(ctx['output'])/f'peer-{peer}/logs'/(label+'.png'), request=clients[peer].request))
        after = sample(label+' after')
        records = []
        for peer, receipt in enumerate(receipts):
            record = dict(label=label, **receipt, native_before=before[peer], native_after=after[peer],
                          video=clients[peer].request('video_info'))
            evidence['peers'][peer]['captures'].append(record); records.append(record)
            if meter:
                record['measurement'] = m = hud.measure_meters(receipt['path'])
                record['checks'] = checks = hud.meter_anchors(m['boxes'], layout)
                require(m['image_size'] == [record['video']['drawable_w'], record['video']['drawable_h']] and
                        all(checks.values()), 'Paired final drawable HUD anchors differ from selected layout')
        return records

    def start(owner, label):
        before = sample(label+' pre-input')
        try:
            clients[owner].host_input(8)
            return captures(label+'-earliest', before=before)
        finally:
            clients[owner].host_input(0)

    for owner in (0, 1):
        before = sample('Owner'+str(owner)+' native menu preflight')
        require(all(r['observation']['native_phase'] == 0 and not r['observation']['pause_owner'] for r in before),
                'Paired menu needs original gameplay on both peers')
        menu = dict(owner=owner, opening=[], closing=[]); evidence['menus'].append(menu)
        menu['earliest_opening'] = start(owner, f'owner{owner}-opening')
        for i in range(4):
            menu['opening'].append(captures(f'owner{owner}-opening-{i}'))
        opened = wait(lambda rows: all(r['observation']['native_phase'] == 2 and
                      r['observation']['pause_owner'] == owner+1 and r['native_menu_state'][0] == 1 for r in rows),
                      'Both peers original menu input-ready')
        menu['paused'] = captures(f'owner{owner}-paused')
        menu['earliest_closing'] = start(owner, f'owner{owner}-closing')
        for i in range(6):
            menu['closing'].append(captures(f'owner{owner}-closing-{i}'))
        resumed = wait(lambda rows: all(r['observation']['native_phase'] == 0 and
                       not r['observation']['pause_owner'] for r in rows), 'Both peers resume original gameplay')
        require(all(hud.state.private_resources(a) == hud.state.private_resources(b) for a, b in zip(opened, resumed)),
                'Paired original menu presentation changed personal resources')
        captures(f'owner{owner}-resumed', meter=True)
        ctx['matched']('HUD both peers owner'+str(owner)+' menu and native resume')
    evidence['checks']['both_native_menu_owners_preserve_resources_and_resume'] = True

    # Peer0 source-guarded observations drive ordinary input; every hold
    # advances both peers and the resulting resources must agree on both.
    route_evidence = {}; evidence['native_resources'] = route_evidence
    route_ctx = dict(mode='netplay', input_path='published_host', clients=clients,
        request=clients[0].request, network=ctx['network'],
        set_input=lambda seat, bits: clients[seat].host_input(bits),
        native_advance=lambda frames, label: ctx['advance'](frames)[0])
    adapter = hud.mapped.PublishedAdapter(route_ctx, route_evidence, 18)
    case = hud.state.PrivateStateCase(clients[0].request, Path(ctx['output'])/'peer-0/logs', route_evidence,
                                     adapter=adapter, input_path='published_host', timeout=18)
    damaged = hud.resources.exercise(route_ctx, case, source)
    rows = sample('Both peers after native HP route')
    values = [hud.state.private_resources(row) for row in rows]
    require(values[0] == values[1] == hud.state.private_resources(damaged) and
            all(0 < p[0] < 32 for p in values[0]), 'Native HP changes did not agree on both peers')
    evidence['checks']['both_peers_genuine_native_hp_changes'] = True
    ctx['matched']('HUD native damage agrees on both peers')
    for index, (width, height) in enumerate(hud.SIZES):
        for window in windows:
            window.resize(width, height)
        captures(f'damaged-aspect-{index}-{width}x{height}', meter=True)
        ctx['matched']('HUD final drawable '+str(width)+'x'+str(height)+' both peers')
    evidence['checks']['both_peers_all_final_drawable_meter_anchors'] = True
    report['checks']['hud_presentation_both_peers_completed'] = True
    evidence['status'] = 'paired_hud_presentation_captured_review_pending'
    return evidence
