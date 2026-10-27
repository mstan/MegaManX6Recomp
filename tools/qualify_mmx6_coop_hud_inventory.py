"""Own an explicit, tainted offline ammo-HUD fixture; never admit replay."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tomllib
import traceback

import mmx6_coop_hud_inventory as ammo
import mmx6_coop_jump_audio_pair as binding
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_jump_audio as owner

TAINT_FAILURE = 'unilateral debug or fixture input contaminated capture'


def inspect_tainted_recording(candidate, image, manifest, output, *, expected_mode='offline'):
    """Archive a structurally valid *failed* trace, refusing normal admission.

    require_complete=False is diagnostic inspection of a failed terminal only.
    Both ordinary capture validation and offline replay must still reject it.
    Unexpected corruption, failure reasons or untainted output fail this case.
    """
    if expected_mode not in ('offline', 'netplay'):
        raise ValueError('Fixture inspection requires an explicit supported session mode')
    paths = list(candidate.glob('saves/**/input-recordings/session-*/inputs.jsonl'))
    if len(paths) != 1:
        raise ValueError('Inventory fixture requires exactly one retained default native recording')
    path = paths[0]
    if not path.resolve(strict=True).is_relative_to((candidate/'saves').resolve(strict=True)):
        raise ValueError('Native recording escaped the owned private profile')
    raw = owner.artifacts.bounded(path, owner.artifacts.MAX_BYTES)
    summary = owner.codec.validate(io.BytesIO(raw), max_events=owner.artifacts.MAX_EVENTS, require_complete=False)
    identity = summary.identity
    if (identity['image_sha256'] != image or identity['manifest_sha256'] != manifest or
            identity['mode'] != expected_mode or identity['baseline'] is not None):
        raise ValueError('Tainted recording is not the exact '+expected_mode+' cold-boot image')
    status = owner.host.json_object(path.parent/'status.json', 4096)
    expected = dict(contract=owner.codec.CONTRACT, epoch=status.get('epoch'), failure=TAINT_FAILURE,
                    schema=1, scope=owner.artifacts.STATUS_SCOPE, status='failed')
    if (type(status.get('epoch')) is not int or not 0 < status['epoch'] <= 0xFFFFFFFFFFFFFFFF or
            status != expected or (path.parent/'status.json').read_bytes() != owner.codec.canonical(expected) or
            summary.failure != TAINT_FAILURE):
        raise ValueError('Inventory recording lacks the exact canonical failed fixture-taint terminal/status')
    bundles = {name: owner.artifacts.bounded(path.parent/name, 1024*1024)
               for name in ('settings.json', 'content.json', 'simulation-contract.json')}
    cards = []
    retained = dict(bundles, **{'inputs.jsonl': raw, 'status.json': owner.codec.canonical(status)})
    for slot, expected_card in enumerate(identity['cards'], 1):
        card = path.parent/f'card{slot}.initial.mcd'
        if expected_card is None:
            if card.exists():
                raise ValueError('Unexpected recorded private card artifact')
            cards.append(None)
        else:
            data = owner.artifacts.bounded(card, 131072)
            cards.append(data); retained[card.name] = data
    owner.codec.validate_startup_artifacts(identity, settings=bundles['settings.json'], cards=cards, baseline=None)
    for name, key in (('content.json', 'content_sha256'), ('simulation-contract.json', 'simulation_contract_sha256')):
        if hashlib.sha256(bundles[name]).hexdigest() != identity[key]:
            raise ValueError('Tainted recording startup bundle changed: '+name)
    settings = json.loads(bundles['settings.json'])
    implementation = json.loads(bundles['simulation-contract.json'])
    if (settings.get('declared_scope_available') != 1 or implementation.get('interpreted_overlays_sealed') != 1 or
            implementation.get('oracle') != 0):
        raise ValueError('Inventory recording lacks ordinary sealed startup scope')
    ports = settings['input']['ports']
    for seat in (0, 1):
        wanted = dict(seat=seat, device_kind=1, configured_mode=2, connected=1, type=0)
        if len(ports) <= seat or any(type(ports[seat].get(k)) is not int or ports[seat][k] != v for k, v in wanted.items()):
            raise ValueError('Inventory fixture lacks stable published digital host devices')
    refusals = {}
    for name, check in (
        ('ordinary_capture', lambda: owner.inspect_capture(candidate, image, manifest, set())),
        ('offline_replay', lambda: owner.codec.validate(io.BytesIO(raw), max_events=owner.artifacts.MAX_EVENTS,
                                                       offline_replay=True, expected_identity=identity)),
    ):
        try:
            check()
        except owner.codec.InvalidRecording as error:
            expected_error = ('network trace cannot be replayed offline'
                if name == 'offline_replay' and expected_mode == 'netplay'
                else 'capture explicitly failed: '+TAINT_FAILURE)
            if str(error) != expected_error:
                raise ValueError('Recording was rejected for an unexpected reason') from error
            refusals[name] = dict(type=type(error).__name__, message=str(error))
        else:
            raise ValueError('Tainted inventory trace was incorrectly admitted by '+name)
    output.mkdir(parents=True, exist_ok=False)
    artifacts = []
    for name, data in retained.items():
        destination = output/name
        with destination.open('xb') as stream:
            stream.write(data)
        artifacts.append(dict(path=str(destination), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    return dict(status='failed_fixture_taint_retained_for_diagnostics', source=str(path), identity=identity,
        terminal_failure=summary.failure, native_status=status, events=summary.events, natives=summary.natives,
        p2_reads=summary.p2_reads, artifacts=artifacts, strict_refusals=refusals,
        finalized_capture_admitted=False, replay_admitted=False,
        scope='Failed native prefix and exact taint artifacts only; no finalized capture/replay claim')


def run(args):
    output = preparation.local_output(args.out); output.mkdir(parents=True, exist_ok=False)
    report = dict(kind='owned_local_native_ammo_hud_inventory_fixture', status='failed_setup', runtime={}, checks={},
        layout=args.layout, R6='unverified', netplay='unverified', artwork_review='pending', ledger_status='unverified',
        finalized_capture_admitted=False, replay_admitted=False)
    candidate = output/'candidate'
    try:
        original = binding.load_sources(args.original_exe, args.original_disc, args.disc,
                                        args.source/'docs/COOP_JUMP_AUDIO_CONTRACT.json')
        source = ammo.load_source(args.original_exe, args.original_disc)
        for module in (ammo, ammo.inventory, ammo.hud, ammo.hud.mapped, ammo.hud.mapped.menus,
                       ammo.hud.mapped.keyboard_input, ammo.hud.state, preparation, owner, binding, owner.codec,
                       owner.artifacts, owner.host):
            p = Path(module.__file__); (output/(p.stem+'-executed-source.py')).write_bytes(p.read_bytes())
        (output/'runner-executed-source.py').write_bytes(Path(__file__).read_bytes())
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
        owner.host.configure_two_digital_slots(candidate)
        modstate = candidate/'mods/state.toml'
        if args.layout == 'side_by_side':
            with modstate.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write('[feature.values]\nhud_layout = "side_by_side"\n')
        report['mod_state'] = tomllib.loads(modstate.read_text(encoding='utf-8'))
        report['settings'] = tomllib.loads((candidate/'settings.toml').read_text(encoding='utf-8'))
        report.update(ammo.hud.state.validate_state_build(args.build, args.source, [args.build, candidate],
                                                         args.expected_manifest_sha256, output))
        report['originals'] = owner.verify_prepared_originals(candidate, args.original_exe, args.disc)
        report['checks']['exact_image_manifest_declared_sources_originals'] = True
        error = None
        try:
            owner.run_owned(candidate, args.port, 200, 12, report['runtime'], original['contract'],
                expected_image=args.expected_exe_sha256, first_seat=0, max_attempts=8, audio_timeout=120,
                private_banks=original['private_banks'], rpc_timeout=15,
                custom_observer=lambda ctx: ammo.exercise(ctx, output=output/'ammo-hud', layout=args.layout, source=source))
        except Exception as caught:
            error = caught
        # Always retain the recording limitation even when the observation fails.
        try:
            report['recording'] = inspect_tainted_recording(candidate, args.expected_exe_sha256,
                args.expected_manifest_sha256, output/'recording-rejection')
        except Exception as caught:
            report['recording_error'] = dict(type=type(caught).__name__, message=str(caught))
            if error is None:
                raise
        if error is not None:
            raise error
        native = report['runtime']
        if (native.get('ordered_native_recording_required') is not True or
                native.get('cleanup') != dict(shutdown='graceful_owned_debug', exit_code=0) or
                native.get('existing_private_cards_unchanged') is not True):
            raise ValueError('Default recording, owned cleanup or private card preservation failed')
        case = native['audio']
        if case['status'] != ammo.SUCCESS or case.get('cleanup_errors') or not case['checks'] or not all(case['checks'].values()):
            raise ValueError('Native ammo-HUD fixture observation incomplete')
        report['checks'].update(native_resource_and_window_observations_complete=True,
            default_recording_taint_retained_and_replay_refused=True, owned_cleanup_private_cards=True)
        report['status'] = ammo.SUCCESS
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__, traceback=traceback.format_exc())
    finally:
        (output/'qualification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'source', 'disc', 'original-disc', 'original-exe', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('expected-exe-sha256', 'expected-manifest-sha256'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--layout', choices=('stacked', 'side_by_side'), default='stacked')
    p.add_argument('--port', type=int, default=24935)
    args = p.parse_args()
    if not 1024 <= args.port <= 65535 or any(re.fullmatch('[0-9a-f]{64}', v) is None for v in
            (args.expected_exe_sha256, args.expected_manifest_sha256)):
        p.error('Require a bounded port and exact lowercase SHA256 pins')
    result = run(args)
    print(json.dumps({k: result[k] for k in ('status', 'checks', 'error') if k in result}, indent=2))
    return 0 if result['status'] == ammo.SUCCESS else 1


if __name__ == '__main__':
    raise SystemExit(main())
