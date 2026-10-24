"""Nonzero scene ownership across actual mapped state UI and rewind.

Dedicated offline mailbox commands invoke original script lock/release helpers.
The authored trigger is bypassed. No ownership, actor, resource or restoration
outcome is written by this observer; outcomes require coherent native samples.
"""
import hashlib
import math
from pathlib import Path
import time

import inventory_mmx6_coop_content as content
import mmx6_coop_mapped_state as mapped

state = mapped.state
require = mapped.require


def load_source(path):
    data = Path(path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == content.EXE_SHA256, 'Scene prerequisite original EXE changed')
    exe = content.Executable(data)
    helpers = []
    for address, size, sha in (
        (0x8003D308, 40, '9b5ce4e2f8ce7fde8a1ceeee2ade074d66b3ced5747a3ea9d55a6673b53825c1'),
        (0x8003D330, 28, 'f7a6295b23f5ee582b20035c9d35b5f3f58bf2b8a2492e4ace6add196f47f724'),
    ):
        start = exe.offset(address, size); code = data[start:start+size]
        require(hashlib.sha256(code).hexdigest() == sha, 'Original native script helper changed')
        helpers.append(dict(address=address, bytes=size, sha256=sha, code_hex=code.hex()))
    return dict(helpers=helpers, bypass='Authored script/door trigger bypassed; state ownership and continuation tested separately')


def scene_wire(image):
    """Read only the current schema3 scene record; reject unknown layouts."""
    require(image['internal_wire_schema'] == 3, 'Unsupported scene state wire')
    core = bytes.fromhex(image['semantic_core_hex'])
    require(len(core) == state.HOST_SEMANTIC_BYTES, 'Unexpected scene state wire length')
    at = state.HOST_PLAYER_BYTES + 19
    owner, phase = core[at:at+2]
    require(owner in (0, 1, 2) and phase <= 5 and (owner or not phase), 'Invalid scene ownership record')
    # owner + phase + destination Y + returning body + passenger scene body
    return dict(owner=owner, phase=phase, context_hex=core[at:at+6+2*0x158].hex())


def locked(row, seat):
    obs = row['observation']
    body = bytes.fromhex(row['p2_body_hex'] if seat else row['p1_body_hex'])
    return (obs['scene_owner'] == seat+1 and obs['scene_phase'] == 3 and
            obs['native_mode'] == 10 and obs['native_phase'] == 0 and
            body[0xD0] != 0 and body[0x7A] != 0)


def provider_checks(saved, restored, seat, *, rewind=False):
    # The native owner continues its idle script animation while the world
    # clock is frozen. Compare every non-actor host byte and retained pool;
    # do not mistake a later animation frame for the saved instant. Separate
    # paused-state cases qualify exact full actor restoration.
    checks = state.reduce_provider_restore(saved, restored)
    del checks['full_private_context_and_host_input_history']
    if rewind:
        # This is a later retained scene instant, not the earlier slot save.
        # Native idle animation may have admitted additional sprite frames.
        # Exact cache rewind equality is qualified by the paused-pool cases.
        del checks['full_retained_bank_payloads']
        del checks['saved_sprite_bank_count']
    a, b = (bytes.fromhex(x['semantic_core_hex']) for x in (saved, restored))
    checks['full_non_actor_host_context'] = a[state.HOST_PLAYER_BYTES:] == b[state.HOST_PLAYER_BYTES:]
    checks['full_private_effect_pools'] = all(saved[k] == restored[k] for k in ('shots_hex', 'trails_hex', 'attached_hex'))
    passenger = 'private_body_hex' if seat == 0 else 'p1_body_hex'
    checks['full_inactive_passenger_body'] = saved[passenger] == restored[passenger]
    for key in ('private_body_hex', 'p1_body_hex'):
        a, b = (bytes.fromhex(x[key]) for x in (saved, restored))
        checks[key+'_resources'] = a[0x5C] == b[0x5C] and a[0x93] == b[0x93] and a[0xA8:0xCA] == b[0xA8:0xCA]
    return checks


def exercise(ctx, *, output, source, seat, keyboard=False, timeout=18):
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'Scene fixture is offline only')
    require(seat in (0, 1), 'Scene owner must be an actual enrolled seat')
    output.mkdir(parents=True, exist_ok=False)
    evidence = {}; ctx['report']['mapped_state'] = evidence
    adapter = mapped.PublishedAdapter(ctx, evidence, timeout)
    case = state.PrivateStateCase(ctx['request'], output, evidence, timeout=timeout,
                                  adapter=adapter, input_path='published_host')
    controls = mapped.SlotControls(ctx, evidence, output, keyboard=keyboard)
    evidence.update(scene_source=source, seat=seat, control_route='owned_win32_keyboard' if keyboard else 'published_controller',
                    limits=[source['bypass'], 'Current exact-image intro scene state only; full paused actor-byte checks are separate.',
                            'Scene owner native animation advances between operations. Its animation bytes are not compared as a frozen pose.'])

    def command(value):
        before = case.sample('Before original script helper mailbox')
        for offset, data in ((0x52, seat), (0x50, value)):
            response = ctx['request']('write_ram', addr=hex(mapped.debug.DIAGNOSTIC_ADDRESS+offset), val=hex(data))
            evidence.setdefault('prerequisite_writes', []).append(dict(command=value, offset=offset, value=data, response=response))
        controls.wait(lambda: ctx['clients'][0].read(mapped.debug.DIAGNOSTIC_ADDRESS+0x50, 1) == b'\0',
                      'Original script helper mailbox completes')
        return case.wait(lambda r: state.forward(before['observation']['tick'], r['observation']['tick']),
                         'Fresh native publication after original script helper')

    def ended(row):
        obs = row['observation']
        return (not obs['scene_owner'] and not obs['scene_phase'] and
                all(p['active'] and p['state'] == 1 and p['action'] == 2 and p['hp'] > 0 for p in obs['players']))

    def release(label):
        command(6)
        row = case.wait(ended, label+' native scene continuation returns both actors')
        case.capture(label+'-native-return')
        return row

    def probe(label, expected, saved_image, *, rewind=False):
        state.snapshot_operation(ctx['request'], 'save', 7, evidence['operations'])
        image = state.copy_slot_image(ctx['candidate'], 7, output/(label+'-probe.pst'))
        record = scene_wire(image['inspection'])
        checks = provider_checks(saved_image, image['inspection'], seat, rewind=rewind)
        evidence.setdefault('provider_probes', []).append(dict(label=label, **image, scene=record, checks=checks,
            excluded_dynamic_comparisons=['owner native animation pose']+(['sprite cache admitted by later native animation'] if rewind else [])))
        require(record == expected, label+': full saved scene context differs')
        require(all(checks.values()), label+': saved scene host context, pools, passenger or resources differ')
        return record

    try:
        for helper in source['helpers']:
            require(ctx['clients'][0].read(helper['address'], helper['bytes']).hex() == helper['code_hex'],
                    'Live original script helper differs from pinned source')
        adapter.settle_idle()
        initial = case.sample('Healthy idle before native script fixture')
        require(ended(initial), 'Scene fixture requires living, idle, independent actors')
        command(5)
        baseline = case.wait(lambda r: locked(r, seat), 'Original native script lock with outgoing passenger completed')
        evidence['scene_baseline'] = baseline
        case.capture('native-scene-owned')
        controls.operation('save', 0)
        image = state.copy_slot_image(ctx['candidate'], 0, output/'scene-save.pst')
        evidence['mapped_saved_snapshot'] = image
        saved = scene_wire(image['inspection'])
        require(saved['owner'] == seat+1 and saved['phase'] == 3, 'Mapped save missed the nonzero scene owner')
        evidence['checks']['mapped_save_nonzero_scene_owner'] = True
        evidence['status'] = 'failed_behavior'
        release('before-scene-load')
        controls.operation('load', 0)
        after = case.wait(lambda r: locked(r, seat), 'Mapped load restores nonzero native scene ownership')
        evidence['checks']['mapped_load_nonzero_scene_owner'] = True
        probe('mapped-scene-load', saved, image['inspection'])
        evidence['checks']['mapped_load_full_scene_context'] = True

        # Retain a long stable ownership interval; select inside it, then
        # require actual restored ownership/context instead of trusting time.
        anchor = case.sample('Begin retained native scene-owned rewind interval')['observation']['tick']
        case.wait(lambda r: locked(r, seat) and 240 <= ((r['observation']['tick']-anchor) & 0xffffffff) < 0x80000000,
                  'Retain nonzero scene ownership in native rewind history')
        paused = case.sample('End retained scene-owned rewind interval')
        require(locked(paused, seat), 'Scene lock did not remain stable for rewind setup')
        release('before-scene-rewind')
        changed = case.sample('Native scene finished before rewind')
        require(not changed['observation']['scene_owner'] and not changed['observation']['scene_phase'],
                'Scene ownership did not genuinely diverge')
        status = ctx['request']('rewind_status'); evidence['rewind_before_open'] = status
        require(status['enabled'] and not status['title_blocked'] and status['snaps'] >= 20, 'No retained native scene rewind history')
        if controls.keyboard:
            controls.keyboard.until('F8', lambda: controls.overlay()['rewind_open'], controls.wait, 'Keyboard F8 scene rewind')
        else:
            controls.hold_until(5, lambda: controls.overlay()['rewind_open'], 'Controller Select+R3 scene rewind')
        time.sleep(.1)
        delta = (changed['observation']['tick']-paused['observation']['tick']) & 0xffffffff
        steps = math.ceil(delta/8)+18
        require(12 <= steps <= 45, 'Scene rewind seek outside retained history')
        seconds = .28+.07*(steps-1)
        evidence['rewind_seek_heuristic'] = dict(publications_since_owned_window=delta, desired_steps=steps,
                                                held_seconds=seconds, qualification='Setup only; native ownership and full context gate pass')
        if controls.keyboard:
            controls.keyboard.held('Left', seconds)
        else:
            try:
                ctx['set_input'](0, 0x80); time.sleep(seconds)
            finally:
                ctx['set_input'](0, 0)
        controls.capture('rewind', 'scene-rewind-selected')
        if controls.keyboard:
            controls.keyboard.until('Enter', lambda: not controls.overlay()['rewind_open'], controls.wait, 'Keyboard accepts scene rewind')
        else:
            controls.hold_until(0x4000, lambda: not controls.overlay()['rewind_open'], 'Controller accepts scene rewind')
        case.wait(lambda r: locked(r, seat), 'Mapped rewind restores nonzero native scene ownership')
        evidence['checks']['mapped_rewind_nonzero_scene_owner'] = True
        probe('mapped-scene-rewind', saved, image['inspection'], rewind=True)
        evidence['checks']['mapped_rewind_full_scene_context'] = True
        release('after-scene-rewind')
        for actor in (0, 1):
            before = case.sample('Independent actor movement after restored scene continuation')
            case.hold(actor, 0x20, 8, 'Actual Right after scene continuation seat'+str(actor))
            after = case.sample('Independent actor movement result')
            a = before['observation']['players']; b = after['observation']['players']
            require(b[actor]['x_raw'] > a[actor]['x_raw'] and b[actor^1]['x_raw'] == a[actor^1]['x_raw'],
                    'Restored scene continuation did not return independent input ownership')
        evidence['checks']['both_actors_continue_with_independent_input'] = True
        evidence['status'] = mapped.SUCCESS
        return evidence
    finally:
        for actor in (0, 1):
            try:
                ctx['set_input'](actor, 0)
            except Exception as error:
                evidence.setdefault('cleanup_errors', []).append(str(error))
