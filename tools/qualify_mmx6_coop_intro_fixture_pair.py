"""Two owned loopback peers: agreed LAB checkpoint, then native intro door.

This distinct fixture lane retains strict recording failure and never qualifies
ordinary launch, intro traversal, replay, audio or a comparison by itself.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib

import mmx6_coop_intro_fixture as intro
import mmx6_coop_jump_audio_pair as binding
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_hud_inventory as failed_trace
import qualify_mmx6_coop_pair as parent


SUCCESS = 'agreed_fixture_native_intro_observations_complete_review_pending'


def select_checkpoint(directory, *, enabled, option=intro.OPTION, contact_protection='off', starting_hp=('off', 'off'), earned_weapons='off'):
    """Fresh prelaunch preferences only; the SDK negotiates this typed option."""
    directory = Path(directory)
    catalog = tomllib.loads((directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml').read_text(encoding='utf-8'))
    options = [o for o in catalog.get('option', []) if o.get('id') == 'lab_checkpoint']
    known_options = {'off', intro.OPTION, 'intro_subtank_cp2', 'amazon_cp0', 'amazon_cp2', 'intro_before_doors', 'intro_before_explosion', 'recycle_cp2', 'recycle_portal_cp2', 'recycle_distant_cp2', 'recycle_fallen_cp2', 'recycle_fallen_guest_cp2', 'secretlab2b_enemy_cp0', 'refight_portal_cp1', 'refight_distant_cp1', 'heatnix_cp7', 'sigma_cp1', 'northpole_ice_cp3', 'turtloid_rain_cp1', 'alternate_boss_cp1'}
    actual_options = {c['value'] for c in options[0].get('choice', [])} if len(options) == 1 else set()
    if (len(options) != 1 or options[0].get('default') != 'off' or options[0].get('feature') != 'prototype'
            or actual_options not in (known_options, known_options | {'heatnix_cp0'})
            or option == 'off' or option not in actual_options):
        raise ValueError('Staged image lacks the private typed LAB checkpoint catalog')
    protection = [o for o in catalog.get('option', []) if o.get('id') == 'lab_contact_protection']
    if (len(protection) != 1 or protection[0].get('default') != 'off'
            or protection[0].get('feature') != 'prototype' or protection[0].get('type') != 'choice'
            or {c['value'] for c in protection[0].get('choice', [])} != {'off', 'on'}
            or contact_protection not in ('off', 'on')):
        raise ValueError('Staged image lacks the private typed LAB contact-protection catalog')
    if (not isinstance(starting_hp, (tuple, list)) or len(starting_hp) != 2
            or any(type(v) is not str or v not in {'off', *(str(hp) for hp in range(1, 33))} for v in starting_hp)):
        raise ValueError('Require two explicit starting-HP choices off or1..32')
    for seat in (0, 1):
        hp_option = [o for o in catalog.get('option', []) if o.get('id') == f'lab_starting_hp_p{seat+1}']
        if (len(hp_option) != 1 or hp_option[0].get('default') != 'off'
                or hp_option[0].get('feature') != 'prototype' or hp_option[0].get('type') != 'choice'
                or [c['value'] for c in hp_option[0].get('choice', [])] != ['off', *(str(hp) for hp in range(1, 33))]):
            raise ValueError('Staged image lacks exact private starting-HP catalog')
    earned = [o for o in catalog.get('option', []) if o.get('id') == 'lab_earned_weapons']
    if (len(earned) != 1 or earned[0].get('default') != 'off'
            or earned[0].get('feature') != 'prototype' or earned[0].get('type') != 'choice'
            or {c['value'] for c in earned[0].get('choice', [])} != {'off', 'all'}
            or earned_weapons not in ('off', 'all')):
        raise ValueError('Staged image lacks exact private earned-weapon catalog')
    path = directory/'mods/state.toml'; text = path.read_text(encoding='utf-8')
    anchor = 'id = "prototype"\nenabled = '+str(enabled).lower()+'\n'
    if text.count(anchor) != 1 or any(k in text for k in ('lab_checkpoint', 'lab_contact_protection', 'lab_starting_hp_p1', 'lab_starting_hp_p2', 'lab_earned_weapons')):
        raise ValueError('Unexpected fresh co-op feature preferences')
    values = '[feature.values]\nlab_checkpoint = "'+option+'"\nlab_contact_protection = "'+contact_protection+'"\n'
    values += 'lab_starting_hp_p1 = "'+starting_hp[0]+'"\nlab_starting_hp_p2 = "'+starting_hp[1]+'"\n'
    values += 'lab_earned_weapons = "'+earned_weapons+'"\n'
    path.write_bytes(text.replace(anchor, anchor+values).encode('utf-8'))
    return dict(option=option, contact_protection=contact_protection, starting_hp=list(starting_hp), earned_weapons=earned_weapons, state_sha256=preparation.sha256(path),
        catalog_sha256=preparation.sha256(directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'))


def select_subtank_policy(directory, *, enabled, selector=select_checkpoint):
    selected = selector(directory, enabled=enabled, option='intro_subtank_cp2',
        contact_protection='on', starting_hp=('13','11'), earned_weapons='off')
    path = Path(directory)/'mods/state.toml'; text = path.read_text(encoding='utf-8')
    anchor = 'lab_checkpoint = "intro_subtank_cp2"\n'
    if text.count(anchor)!=1 or 'subtank_energy =' in text:
        raise ValueError('Unexpected fresh Sub Tank prerequisite preferences')
    updated = text.replace(anchor,anchor+'subtank_energy = "independent"\n')
    parsed = tomllib.loads(updated)
    features = [f for f in parsed.get('feature',[]) if f.get('package_id')=='mmx6.local-coop' and f.get('id')=='prototype']
    if len(features)!=1 or features[0].get('values',{}).get('subtank_energy')!='independent':
        raise ValueError('Sub Tank policy escaped prototype values')
    path.write_text(updated,encoding='utf-8')
    selected.update(subtank_energy='independent',state_sha256=preparation.sha256(path))
    return selected


def blank_card():
    """Existing SDK formatter translation; fresh fixture cards, never user data."""
    data = bytearray([255])*131072
    def frame(n, values):
        start = n*128; data[start:start+128] = bytes(128)
        for offset, value in values.items():
            data[start+offset] = value
        checksum = 0
        for value in data[start:start+127]:
            checksum ^= value
        data[start+127] = checksum
    frame(0, {0:ord('M'), 1:ord('C')})
    for n in range(1, 16): frame(n, {0:160, 8:255, 9:255})
    for n in range(16, 36): frame(n, {0:255, 1:255, 2:255, 3:255, 8:255, 9:255})
    for n in range(36, 63): frame(n, {})
    data[63*128:64*128] = data[:128]
    result = bytes(data)
    if hashlib.sha256(result).hexdigest() != '7706c7d43edaf8cb7618e574f03457105153e3bdc196db803a600ad96a8f58e8':
        raise ValueError('Fresh blank-card fixture changed')
    return result


def run(args):
    original_prepare = preparation.prepare
    original_profile = binding.ownership.prepare_profile
    original_exercise = binding.exercise
    original_success = binding.SUCCESS
    output = preparation.local_output(args.out)

    def prepare(*pos, **kw):
        result = original_prepare(*pos, **kw)
        if result['source_card'] is not None:
            raise ValueError('Fixture must not copy an owner progress card')
        for slot in (1, 2):
            with (Path(pos[2])/f'saves/card{slot}.mcd').open('xb') as stream:
                stream.write(blank_card())
        return result

    def prepare_profile(directory, *pos, **kw):
        result = original_profile(directory, *pos, **kw)
        result['agreed_checkpoint'] = select_checkpoint(directory, enabled=False)
        return result

    def observe(ctx, *, expected_sha, **unused):
        binding.validate_context(ctx, expected_sha)
        report = ctx['report']
        report['kind'] = 'owned_paired_agreed_lab_checkpoint_native_intro'
        report['jump_audio_private_cards_before'] = binding.ownership.cards(output)
        report['ordinary_route_qualified'] = False
        prepared = [p['agreed_checkpoint'] for p in report['jump_audio_prepared']]
        if prepared[0] != prepared[1]:
            raise ValueError('Peers did not predeclare the same private checkpoint option/catalog')
        exercise = (intro.exercise_subtank_policy if getattr(args, 'subtank_policy', False)
            else intro.exercise_midboss_forward if getattr(args, 'midboss_forward', False)
            else intro.exercise_final_retry_continue if getattr(args, 'final_retry_continue', False)
            else intro.exercise_distant_explosion if getattr(args, 'distant_explosion', False) else intro.exercise)
        case = exercise(dict(ctx, set_input=lambda seat, bits: ctx['clients'][seat].host_input(bits)),
            output=output/'intro-admission', original_exe=args.original_exe,
            leader=args.intro_leader, success=SUCCESS)
        report['checks']['jump_audio_both_peers_completed'] = True
        return case

    try:
        preparation.prepare = prepare; binding.ownership.prepare_profile = prepare_profile
        binding.exercise = observe; binding.SUCCESS = SUCCESS
        report = parent.run(args)
    finally:
        preparation.prepare = original_prepare; binding.ownership.prepare_profile = original_profile
        binding.exercise = original_exercise; binding.SUCCESS = original_success
    report.update(default_launch_qualified=False, default_intro_qualified=False,
        ordinary_route_qualified=False, finalized_capture_admitted=False, replay_admitted=False,
        ledger_status='unverified', artwork_review='pending')
    recordings = []
    for peer in report.get('peers', []):
        try:
            recordings.append(failed_trace.inspect_tainted_recording(Path(peer['directory']),
                args.expected_exe_sha256, args.expected_manifest_sha256,
                output/f'peer-{peer["seat"]}-recording-refusal', expected_mode='netplay'))
        except Exception as error:
            report.setdefault('recording_errors', []).append(dict(peer=peer['seat'], error=str(error)))
    report['fixture_recording_refusals'] = recordings
    if len(recordings) != 2 or report.get('recording_errors'):
        report['status'] = 'failed_fixture_recording_validation'
    elif recordings[0]['identity']['profile'] != recordings[1]['identity']['profile']:
        report['status'] = 'failed_fixture_profile_identity'
    elif report['status'] == 'passed':
        report['status'] = SUCCESS
    for module in (intro, parent, failed_trace):
        p = Path(module.__file__); (output/(p.stem+'-executed-source.py')).write_bytes(p.read_bytes())
    (output/'caller-executed-source.py').write_bytes(Path(__file__).read_bytes())
    (output/'qualification.json').write_bytes((json.dumps(report, indent=2)+'\n').encode('utf-8'))
    return report


def run_local(args):
    """The same exact candidate/mechanic, with one process and two local pads."""
    original_prepare = preparation.prepare
    original_exercise = failed_trace.ammo.exercise
    prepared = []

    def prepare(*pos, **kw):
        result = original_prepare(*pos, **kw)
        if result['source_card'] is not None:
            raise ValueError('Fixture must not copy an owner progress card')
        directory = Path(pos[2])
        for slot in (1, 2):
            with (directory/f'saves/card{slot}.mcd').open('xb') as stream:
                stream.write(blank_card())
        prepared.append(select_checkpoint(directory, enabled=True))
        return result

    def observe(ctx, *, output, **unused):
        exercise = (intro.exercise_subtank_policy if getattr(args, 'subtank_policy', False)
            else intro.exercise_midboss_forward if getattr(args, 'midboss_forward', False)
            else intro.exercise_final_retry_continue if getattr(args, 'final_retry_continue', False)
            else intro.exercise_distant_explosion if getattr(args, 'distant_explosion', False) else intro.exercise)
        return exercise(ctx, output=output/'intro-admission', original_exe=args.original_exe,
            leader=args.intro_leader, success=failed_trace.ammo.SUCCESS)

    args.layout = 'stacked'; args.port = args.host_port
    try:
        preparation.prepare = prepare; failed_trace.ammo.exercise = observe
        report = failed_trace.run(args)
    finally:
        preparation.prepare = original_prepare; failed_trace.ammo.exercise = original_exercise
    report.update(kind='owned_local_agreed_lab_checkpoint_native_intro',
        agreed_checkpoint_prepared=prepared, default_launch_qualified=False,
        default_intro_qualified=False, ordinary_route_qualified=False, ledger_status='unverified')
    if report['status'] == failed_trace.ammo.SUCCESS:
        report['status'] = SUCCESS
    output = preparation.local_output(args.out)
    (output/'intro-helper-executed-source.py').write_bytes(Path(intro.__file__).read_bytes())
    (output/'caller-executed-source.py').write_bytes(Path(__file__).read_bytes())
    (output/'qualification.json').write_bytes((json.dumps(report, indent=2)+'\n').encode('utf-8'))
    return report


def main():
    parser = parent.make_parser()
    parser.description = __doc__
    parser.add_argument('--intro-leader', type=int, choices=(0, 1), required=True)
    parser.add_argument('--local', action='store_true', help='Use the same candidate with two local pads')
    parser.add_argument('--distant-explosion', action='store_true', help='Observe F158 separated native explosion views')
    parser.add_argument('--final-retry-continue', action='store_true', help='F136 actual Sigma team retry and literal Game Over/Continue')
    parser.add_argument('--midboss-forward', action='store_true', help='F166/F187 actual Magma midboss defeat and original forward boundaries')
    parser.add_argument('--subtank-policy', action='store_true', help='F180 native owner heals after agreed private Sub Tank supplies cross original CP2')
    args = parser.parse_args(); args.jump_audio_smoke = True
    parent.validate_options(parser, args)
    if sum((args.final_retry_continue, args.distant_explosion, args.midboss_forward, args.subtank_policy)) > 1:
        parser.error('Select one named native scenario')
    if args.subtank_policy:
        globals()['select_checkpoint'] = select_subtank_policy
    if args.midboss_forward:
        original_select = select_checkpoint
        def select_midboss(directory, *, enabled):
            selected = original_select(directory, enabled=enabled, option='heatnix_cp0',
                contact_protection='on', earned_weapons='all')
            directory = Path(directory)
            catalog = tomllib.loads((directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml').read_text(encoding='utf-8'))
            doors = [o for o in catalog.get('option', []) if o.get('id') == 'doors']
            if (len(doors) != 1 or doors[0].get('default') != 'either' or doors[0].get('feature') != 'prototype'
                    or {c['value'] for c in doors[0].get('choice', [])} != {'either', 'both'}):
                raise ValueError('Missing exact existing Either/Both door option')
            path = directory/'mods/state.toml'; text = path.read_text(encoding='utf-8')
            if 'doors =' in text: raise ValueError('Unexpected pre-existing door choice')
            path.write_text(text+'doors = "both"\n', encoding='utf-8')
            selected.update(doors='both', state_sha256=preparation.sha256(path))
            return selected
        globals()['select_checkpoint'] = select_midboss
    if args.final_retry_continue and args.intro_leader != 0:
        parser.error('F136 reuses the primary-owned Sigma intro and Continue route')
    if args.final_retry_continue:
        original_select = select_checkpoint
        def select_final(directory, *, enabled):
            return original_select(directory, enabled=enabled, option='sigma_cp1',
                contact_protection='off', starting_hp=('1', '1'), earned_weapons='off')
        globals()['select_checkpoint'] = select_final
    if args.distant_explosion:
        original_select = select_checkpoint
        def select_distant(directory, *, enabled):
            selected = original_select(directory, enabled=enabled, option='intro_before_explosion', contact_protection='on')
            path = Path(directory)/'mods/state.toml'
            text = path.read_text(encoding='utf-8')
            anchor = 'lab_checkpoint = "intro_before_explosion"\n'
            if text.count(anchor) != 1:
                raise ValueError('Missing original explosion selection')
            path.write_text(text.replace(anchor, anchor+'local_cameras = "split"\ncameras = "split"\n'), encoding='utf-8')
            selected.update(state_sha256=preparation.sha256(path),local_cameras='split',cameras='split')
            return selected
        globals()['select_checkpoint'] = select_distant
    if not args.require_state_crc or not args.require_host_profile or args.admission_only or args.native_loader_diagnostic:
        parser.error('Agreed fixture requires full native source/image/manifest/profile/resolved-CRC gates')
    report = run_local(args) if args.local else run(args)
    print(json.dumps({k: report[k] for k in ('status', 'checks', 'error') if k in report}), flush=True)
    return int(report['status'] != SUCCESS)


if __name__ == '__main__':
    raise SystemExit(main())
