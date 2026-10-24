"""Own one muted, exact-image mapped state/rewind qualification."""
import argparse
import json
from pathlib import Path
import re
import tomllib
import traceback

import mmx6_coop_jump_audio_pair as binding
import mmx6_coop_mapped_state as mapped
import mmx6_coop_scene_state as scene
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_jump_audio as owner
import qualify_mmx6_coop_state as state


def run(args):
    output=preparation.local_output(args.out);output.mkdir(parents=True,exist_ok=False)
    report=dict(kind='owned_native_mapped_coop_state',status='failed_setup',runtime={},checks={},F33='unverified',
        control_route='owned_win32_keyboard' if args.keyboard else 'published_controller',
        limits=['Same-image local UI paths only. Physical keyboard hardware, netplay and full F33 remain separate.'])
    try:
        original=binding.load_sources(args.original_exe,args.original_disc,args.disc,
            args.source/'docs/COOP_JUMP_AUDIO_CONTRACT.json')
        for module in (mapped,state,owner,binding,mapped.menus,mapped.keyboard_input,mapped.resource_input,
                       mapped.resource_input.zero_contact,mapped.resource_input.native_contact,mapped.resource_input.primary):
            p=Path(module.__file__);(output/(p.stem+'-executed-source.py')).write_bytes(p.read_bytes())
        module=mapped.inventory_input
        (output/(Path(module.__file__).stem+'-executed-source.py')).write_bytes(Path(module.__file__).read_bytes())
        (output/(Path(scene.__file__).stem+'-executed-source.py')).write_bytes(Path(scene.__file__).read_bytes())
        (output/'runner-executed-source.py').write_bytes(Path(__file__).read_bytes())
        report['original_disc']=original['disc']
        candidate=output/'candidate'
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
        owner.host.configure_two_digital_slots(candidate)
        settings=candidate/'settings.toml';text=settings.read_text(encoding='utf-8')
        if text.count('rewind = false')!=1:raise ValueError('Unexpected prepared rewind preference')
        text=text.replace('rewind = false','rewind = true\nrewind_depth = 50\nrewind_interval = 8')
        settings.write_text(text,encoding='utf-8');report['settings']=tomllib.loads(text)
        images=state.staged_image_binding(candidate,args.expected_exe_sha256)
        report.update(state.validate_state_build(args.build,args.source,[args.build,candidate],args.expected_manifest_sha256,output))
        report['originals']=owner.verify_prepared_originals(candidate,args.original_exe,args.disc,expected_rewind=True)
        report['checks']['exact_image_manifest_declared_sources_originals']=True
        resource_sources=None
        if args.resource_damage:
            resource_sources=dict(zero_overlay=mapped.resource_input.zero_contact.load_zero_overlay(args.original_disc),
                target=mapped.resource_input.native_contact.load_source(args.original_exe,args.original_disc,0))
        inventory_source=mapped.inventory_input.load_source(args.original_exe) if args.inventory_ammo else None
        scene_source=scene.load_source(args.original_exe) if args.scene_owner is not None else None
        def observe(ctx):
            if scene_source is not None:
                return scene.exercise(ctx,output=output/'mapped-state',source=scene_source,seat=args.scene_owner,keyboard=args.keyboard)
            return mapped.exercise(ctx,output=output/'mapped-state',keyboard=args.keyboard,
                resource_sources=resource_sources,inventory_source=inventory_source)
        owner.run_owned(candidate,args.port,args.boot_timeout,12,report['runtime'],original['contract'],
            expected_image=args.expected_exe_sha256,first_seat=0,max_attempts=8,audio_timeout=120,
            private_banks=original['private_banks'],custom_observer=observe,rewind_state_case=True)
        runtime=report['runtime'];case=runtime['audio']
        if runtime.get('cleanup')!=dict(shutdown='graceful_owned_debug',exit_code=0):
            raise ValueError('Mapped state process did not exit naturally')
        if not runtime.get('existing_private_cards_unchanged'):raise ValueError('Private native cards changed')
        if case['status']!=mapped.SUCCESS or case.get('cleanup_errors'):raise ValueError('Mapped state case did not complete')
        if images!=state.staged_image_binding(candidate,args.expected_exe_sha256):raise ValueError('Staged image/assets changed')
        report['checks']['mapped_native_case_natural_exit_and_private_cards']=True
        report['status']=mapped.SUCCESS
    except Exception as error:
        report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
        if report['runtime'].get('mapped_state',{}).get('status')=='failed_behavior':report['status']='failed_behavior'
    finally:
        (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','source','disc','original-disc','original-exe','out'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('expected-exe-sha256','expected-manifest-sha256'):p.add_argument('--'+name,required=True)
    p.add_argument('--port',type=int,default=24923);p.add_argument('--boot-timeout',type=int,default=200)
    p.add_argument('--keyboard',action='store_true',help='Use owned Win32/SDL F7/S/L and F8/Left/Enter instead of controller UI shortcuts')
    p.add_argument('--resource-damage',action='store_true',help='Damage both heroes through native gameplay before mapped load0')
    p.add_argument('--inventory-ammo',action='store_true',help='Bypass earned-weapon prerequisites, then natively select/spend ammo before mapped load and rewind')
    p.add_argument('--scene-owner',type=int,choices=(0,1),help='Invoke original script lock for this seat; qualify nonzero scene ownership and continuation across mapped load/rewind')
    a=p.parse_args()
    if a.inventory_ammo and not a.resource_damage:p.error('--inventory-ammo requires the full --resource-damage case')
    if a.scene_owner is not None and (a.inventory_ammo or a.resource_damage):p.error('--scene-owner is a separate native scene state case')
    if not 1024<=a.port<=65535 or not 1<=a.boot_timeout<=600:p.error('Require bounded port and boot timeout')
    if any(re.fullmatch('[0-9a-f]{64}',v) is None for v in (a.expected_exe_sha256,a.expected_manifest_sha256)):
        p.error('Require exact lowercase image/manifest SHA256s')
    result=run(a)
    print(json.dumps({k:result[k]for k in ('status','checks','error') if k in result},indent=2))
    return 0 if result['status']==mapped.SUCCESS else 1


if __name__=='__main__':raise SystemExit(main())
