"""Own one muted exact-image HUD/layout/menu presentation capture run."""
import argparse
import json
from pathlib import Path
import re
import tomllib
import traceback

import mmx6_coop_hud_presentation as hud
import mmx6_coop_jump_audio_pair as binding
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_jump_audio as owner


def run(args):
    output = preparation.local_output(args.out); output.mkdir(parents=True, exist_ok=False)
    report = dict(kind='owned_native_hud_layout_and_menu_presentation', status='failed_setup', runtime={}, checks={},
                  layout=args.layout, R5='unverified', R6='unverified', F18='unverified')
    try:
        original = binding.load_sources(args.original_exe, args.original_disc, args.disc,
                                        args.source/'docs/COOP_JUMP_AUDIO_CONTRACT.json')
        for module in (hud, hud.mapped, hud.mapped.menus, hud.mapped.keyboard_input, hud.state,
                       hud.resources, hud.resources.primary, hud.resources.native_contact, hud.resources.zero_contact, owner, binding):
            p = Path(module.__file__); (output/(p.stem+'-executed-source.py')).write_bytes(p.read_bytes())
        (output/'runner-executed-source.py').write_bytes(Path(__file__).read_bytes())
        candidate = output/'candidate'
        preparation.prepare(args.build, args.source, candidate, args.disc, automated=True)
        owner.host.configure_two_digital_slots(candidate)
        modstate = candidate/'mods/state.toml'
        if args.layout == 'side_by_side':
            with modstate.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write('[feature.values]\nhud_layout = "side_by_side"\n')
        report['mod_state'] = tomllib.loads(modstate.read_text(encoding='utf-8'))
        report['settings'] = tomllib.loads((candidate/'settings.toml').read_text(encoding='utf-8'))
        report.update(hud.state.validate_state_build(args.build, args.source, [args.build, candidate], args.expected_manifest_sha256, output))
        report['originals'] = owner.verify_prepared_originals(candidate, args.original_exe, args.disc)
        report['checks']['exact_image_manifest_declared_sources_originals'] = True
        sources = dict(zero_overlay=hud.resources.zero_contact.load_zero_overlay(args.original_disc),
                       target=hud.resources.native_contact.load_source(args.original_exe, args.original_disc, 0))
        error = None
        try:
            owner.run_owned(candidate, args.port, 200, 12, report['runtime'], original['contract'],
                            expected_image=args.expected_exe_sha256, first_seat=0, max_attempts=8, audio_timeout=120,
                            private_banks=original['private_banks'],
                            custom_observer=lambda ctx: hud.exercise(ctx, output=output/'hud', layout=args.layout, resource_sources=sources))
        except Exception as caught:
            error = caught
        native = report['runtime']
        try:
            report['recording'] = owner.inspect_capture(candidate, args.expected_exe_sha256, args.expected_manifest_sha256, set())
        except Exception as caught:
            report['recording_error'] = dict(type=type(caught).__name__, message=str(caught))
            if error is None:
                raise
        if error is not None:
            raise error
        if native.get('cleanup') != dict(shutdown='graceful_owned_debug', exit_code=0) or not native.get('existing_private_cards_unchanged'):
            raise ValueError('Owned HUD process cleanup or private card preservation failed')
        case = native['audio']
        if case['status'] != hud.SUCCESS or case.get('cleanup_errors') or not all(case['checks'].values()):
            raise ValueError('Native HUD capture case incomplete')
        report['checks']['native_case_finalized_recording_cleanup_and_cards'] = True
        report['status'] = hud.SUCCESS
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
    p.add_argument('--port', type=int, default=24925)
    args = p.parse_args()
    if not 1024 <= args.port <= 65535 or any(re.fullmatch('[0-9a-f]{64}', v) is None for v in
        (args.expected_exe_sha256, args.expected_manifest_sha256)):
        p.error('Require bounded port and exact lowercase SHA256 pins')
    result = run(args)
    print(json.dumps({k: result[k] for k in ('status', 'checks', 'error') if k in result}, indent=2))
    return 0 if result['status'] == hud.SUCCESS else 1


if __name__ == '__main__':
    raise SystemExit(main())
