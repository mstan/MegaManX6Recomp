"""Verify mapped state/rewind refusal on two owned, admitted delay peers."""
import hashlib
from pathlib import Path
import time
import tomllib

import coop_debug as debug
import mmx6_coop_jump_audio_pair as binding
import mmx6_owned_keyboard as keyboard


def require(ok, message):
    if not ok:
        raise debug.DebugError(message)


def enable_rewind(directory, prepared):
    path = Path(directory)/'settings.toml'
    text = path.read_text(encoding='utf-8')
    require(text.count('rewind = false') == 1, 'State policy requires the fresh default rewind preference')
    text = text.replace('rewind = false', 'rewind = true\nrewind_depth = 20\nrewind_interval = 8')
    path.write_text(text, encoding='utf-8')
    settings = tomllib.loads(text)
    require(settings['video']['rewind'] is True, 'State policy did not enable the actual local rewind preference')
    return dict(prepared, settings_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                state_policy_local_rewind_preference=True, rewind_depth=20, rewind_interval=8)


def unchanged_operation(before, after):
    return (before.get('pending') == after.get('pending') == 0 and
            type(before.get('generation')) is int and
            all(before.get(k) == after.get(k) for k in ('generation', 'last_op', 'last_slot', 'last_ok')))


def exercise(ctx, *, expected_sha, dwell_seconds=12):
    binding.validate_context(ctx, expected_sha)
    require(type(dwell_seconds) in (int,float) and 0 <= dwell_seconds <= 15,
            'Online slot-browser dwell must stay within its native observation bound')
    report, output = ctx['report'], Path(ctx['output'])
    evidence = dict(status='failed_behavior', peers=[], checks={}, limits=[
        'Two owned Windows peers on one host, exact build/profile and delay mode only.',
        'Actual local preferences enable rewind; network policy must refuse user state jumps.',
        'Posted Win32/SDL keyboard events and published local host controller samples are tested; physical hardware is separate.',
        'No ordered native recording/replay with rewind, rollback, cross-build or heterogeneous qualification.',
    ])
    report['state_policy'] = evidence
    report['jump_audio_private_cards_before'] = binding.ownership.cards(output)

    def wait(predicate, label):
        deadline = time.monotonic()+12
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.025)
        raise debug.DebugError(label+': timed out')

    for seat, client in enumerate(ctx['clients']):
        peer = report['peers'][seat]
        directory = Path(peer['directory'])
        settings = tomllib.loads((directory/'settings.toml').read_text(encoding='utf-8'))
        require(settings['video']['rewind'] is True, 'An online refusal peer has rewind disabled in settings')
        record = dict(peer=seat, checks={}, observations=[], controller_inputs=[])
        evidence['peers'].append(record)
        keys = keyboard.OwnedKeyboard(dict(request=client.request, report=dict(owned_pid=peer['owned_pid'])), record)

        def observe():
            row = dict(overlay=client.request('overlay_status'), state=client.request('savestate_status'),
                       rewind=client.request('rewind_status'))
            record['observations'].append(row)
            return row

        def files():
            return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (directory/'saves').glob('**/*.pst')}

        def host(bits, predicate=None, label='Published controller UI hold'):
            try:
                acknowledgment = client.host_input(bits)
                record['controller_inputs'].append(dict(pressed=bits, acknowledgment=acknowledgment))
                if predicate:
                    return wait(predicate, label)
                # The slot browser pauses guest simulation. A native/transport
                # wait here deadlocks the test; the subsequent Right change is
                # the positive consumption barrier for Square/Cross instead.
                time.sleep(.12)
            finally:
                client.host_input(0)
                time.sleep(.04)

        initial, before_files = observe(), files()
        record['initial'] = initial
        require(initial['rewind']['enabled'] and not initial['overlay']['rewind_open'],
                'Online refusal needs an enabled rewind implementation with no open timeline')
        require(initial['state']['pending'] == 0, 'State policy started during a pending operation')

        for route in ('keyboard', 'controller'):
            if route == 'keyboard':
                keys.until('F7', lambda: observe()['overlay']['save_menu_open'], wait, 'Online F7 slot browser')
            else:
                host(0x801, lambda: observe()['overlay']['save_menu_open'], 'Online Select+R1 slot browser')
            opened = observe()
            require(opened['overlay']['save_unavailable'], 'Online slot browser did not report states unavailable')
            dwell=dict(route=route,seconds=dwell_seconds,start_monotonic_ns=time.monotonic_ns())
            record.setdefault('disabled_browser_dwell',[]).append(dwell)
            time.sleep(dwell_seconds)
            dwell['end_monotonic_ns']=time.monotonic_ns()
            capture = directory/'logs'/('online-'+route+'-state-blocked.png')
            reply = client.request('overlay_image', panel='save_states', path=str(capture))
            require(reply.get('ok') is True and capture.is_file(), 'Online blocked-state overlay capture failed')
            record.setdefault('captures', []).append(dict(path=str(capture), sha256=hashlib.sha256(capture.read_bytes()).hexdigest()))
            slot = opened['overlay']['save_slot']
            if route == 'keyboard':
                for key in ('S', 'L'):
                    keys.post(key, False)
                    keys.post(key, True)
                keys.until('Right', lambda: observe()['overlay']['save_slot'] != slot, wait,
                           'Positive keyboard input barrier after refused S/L')
            else:
                host(0x8000)
                host(0x4000)
                host(0x20, lambda: observe()['overlay']['save_slot'] != slot,
                     'Positive controller input barrier after refused Square/Cross')
            after = observe()
            record['checks'][route+'_save_load_refused_after_input_barrier'] = (
                after['overlay']['save_menu_open'] and after['overlay']['save_unavailable'] and
                unchanged_operation(initial['state'], after['state']) and files() == before_files)
            keys.until('F7', lambda: not observe()['overlay']['save_menu_open'], wait, 'Close online slot browser')
            if route == 'keyboard':
                keys.post('F8', False)
                keys.post('F8', True)
            else:
                host(5)
            keys.until('F7', lambda: observe()['overlay']['save_menu_open'], wait,
                       'Positive F7 event barrier after refused rewind')
            after = observe()
            record['checks'][route+'_rewind_refused_after_input_barrier'] = (
                not after['overlay']['rewind_open'] and after['rewind']['enabled'] and
                unchanged_operation(initial['state'], after['state']) and files() == before_files)
            keys.until('F7', lambda: not observe()['overlay']['save_menu_open'], wait, 'Close rewind-refusal barrier panel')
            ctx['transport_window'](16)
            ctx['matched']('State/rewind refusal peer'+str(seat)+' '+route)
        record['final'] = observe()
        require(all(record['checks'].values()), 'Online state/rewind refusal changed native operation state')
    evidence['checks']['both_peers_all_mapped_refusals'] = all(all(p['checks'].values()) for p in evidence['peers'])
    evidence['checks']['fresh_resolved_crc_after_each_refusal_route'] = True
    require(all(evidence['checks'].values()), 'Paired state policy qualification failed')
    report['checks']['state_policy_both_peers_completed'] = True
    evidence['status'] = 'paired_mapped_state_rewind_refusal_observed'
    return evidence
