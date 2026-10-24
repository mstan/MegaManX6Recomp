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



def refused_open(before, after):
    old, new = (r['overlay'].get('save_open_refusal_generation') for r in (before, after))
    return (type(old) is int and type(new) is int and
            0 < ((new-old) & 0xffffffff) < 0x80000000 and
            not after['overlay']['save_menu_open'] and after['overlay']['save_unavailable'] and
            not after['overlay']['rewind_open'] and unchanged_operation(before['state'], after['state']))


def exercise(ctx, *, expected_sha, dwell_seconds=12):
    binding.validate_context(ctx, expected_sha)
    require(type(dwell_seconds) in (int,float) and 0 <= dwell_seconds <= 15,
            'Online refused-browser dwell must stay within its native observation bound')
    report, output = ctx['report'], Path(ctx['output'])
    evidence = dict(status='failed_behavior', peers=[], checks={}, limits=[
        'Two owned Windows peers on one host, exact build/profile and delay mode only.',
        'Actual local preferences enable rewind; unsupported state browser entry must be refused before a modal pause.',
        'Posted Win32/SDL keyboard events and published local host controller samples are tested; physical hardware is separate.',
        'Completed UI-refusal counters prove mapped handler consumption; explicit backend requests independently verify save/load refusal.',
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
        record = dict(peer=seat, checks={}, observations=[], controller_inputs=[], backend_refusals=[])
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
                return wait(predicate, label) if predicate else ctx['transport_window'](4)
            finally:
                client.host_input(0)
                ctx['transport_window'](2)

        def entry_refusal(route, label):
            before = observe()
            def refused():
                after = observe()
                return after if refused_open(before, after) else None
            if route == 'keyboard':
                result = keys.until('F7', refused, wait, label)
            else:
                result = host(0x801, refused, label)
            record.setdefault('completed_entry_refusals',[]).append(dict(route=route,before=before,after=result))
            return result

        initial, before_files = observe(), files()
        record['initial'] = initial
        require(initial['rewind']['enabled'] and not initial['overlay']['rewind_open'],
                'Online refusal needs an enabled rewind implementation with no open timeline')
        require(type(initial['overlay'].get('save_open_refusal_generation')) is int,
                'Native image lacks completed browser-entry refusal diagnostics')
        require(initial['state']['pending'] == 0, 'State policy started during a pending operation')

        for operation in ('save','load'):
            try:
                client.request('savestate',op=operation,slot=0)
            except debug.DebugError as error:
                message=str(error)
                require('runtime rejected command' in message and 'refused' in message,
                        'Backend state request failed without an explicit native policy refusal: '+message)
                record['backend_refusals'].append(dict(operation=operation,error=message))
            else:
                raise debug.DebugError('Unsupported online backend state operation was staged')
        require(unchanged_operation(initial['state'],observe()['state']),
                'Refused backend state request changed its completion generation')
        record['checks']['backend_save_and_load_refused']=len(record['backend_refusals'])==2

        for route in ('keyboard','controller'):
            entry_refusal(route,'Actual online browser entry refused '+route)
            start_network=ctx['network']()
            start_native=debug.observe(client).json()
            dwell=dict(route=route,seconds=dwell_seconds,start_monotonic_ns=time.monotonic_ns(),
                       network_before=start_network,native_before=start_native,network_samples=[])
            record.setdefault('disabled_browser_dwell',[]).append(dwell)
            deadline=time.monotonic()+dwell_seconds
            while time.monotonic()<deadline:
                time.sleep(min(.5,max(0,deadline-time.monotonic())))
                dwell['network_samples'].append(ctx['network']())
            dwell.update(end_monotonic_ns=time.monotonic_ns(),network_after=ctx['network'](),
                         native_after=debug.observe(client).json())
            advancing=all(b['resolved_through']>a['resolved_through'] for a,b in
                          zip(start_network,dwell['network_after']))
            native_delta=(dwell['native_after']['native_timer']-start_native['native_timer'])&0xffffffff
            after=observe()
            record['checks'][route+'_entry_refused_without_pausing_match']=(advancing and
                0<native_delta<0x80000000 and not after['overlay']['save_menu_open'] and
                unchanged_operation(initial['state'],after['state']) and files()==before_files)
            capture=directory/'logs'/('online-'+route+'-refused-browser-gameplay.png')
            record.setdefault('captures',[]).append(debug.capture_present(client,capture,request=client.request))
            if route=='keyboard':
                keys.post('F8',False)
                keys.post('F8',True)
            else:
                host(5)
            entry_refusal('keyboard','Positive F7 refusal barrier after rewind '+route)
            after=observe()
            record['checks'][route+'_rewind_refused_after_input_barrier']=(
                not after['overlay']['rewind_open'] and after['rewind']['enabled'] and
                unchanged_operation(initial['state'],after['state']) and files()==before_files)
            ctx['transport_window'](16)
            ctx['matched']('State/rewind refusal peer'+str(seat)+' '+route)
        record['final']=observe()
        require(all(record['checks'].values()),'Online refusal changed native operation state or stopped match progress')
    evidence['checks']['both_peers_all_mapped_refusals']=all(all(p['checks'].values())for p in evidence['peers'])
    evidence['checks']['fresh_resolved_crc_after_each_refusal_route']=True
    require(all(evidence['checks'].values()),'Paired state policy qualification failed')
    report['checks']['state_policy_both_peers_completed']=True
    evidence['status']='paired_mapped_state_rewind_refusal_observed'
    return evidence
