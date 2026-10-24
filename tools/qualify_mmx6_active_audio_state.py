"""Own serial warm/cold active-private-audio snapshot tests on an exact image."""
import argparse
import json
from pathlib import Path
import re
import shutil
import traceback

import mmx6_coop_active_audio_state as active
import mmx6_coop_body_audio as body
import mmx6_coop_contact as contact
import mmx6_coop_jump_audio_pair as binding
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_jump_audio as owner
import qualify_mmx6_coop_state as state


def run(args):
    output=preparation.local_output(args.out);output.mkdir(parents=True,exist_ok=False)
    report=dict(kind='owned_warm_cold_active_private_audio_state',status='failed_setup',phases={},checks={},
        ledger='unverified',limits=['Same-build local native active voice only; no full F33, rewind or rollback pass.'])
    try:
        original=binding.load_sources(args.original_exe,args.original_disc,args.disc,
            args.source/'docs/COOP_JUMP_AUDIO_CONTRACT.json')
        source=body.build_source(args.original_exe,args.original_disc)
        zero=contact.load_zero_overlay(args.original_disc)
        for module in (active,body,contact,owner,binding,state):
            path=Path(module.__file__)
            (output/(path.stem+'-executed-source.py')).write_bytes(path.read_bytes())
        (output/'runner-executed-source.py').write_bytes(Path(__file__).read_bytes())
        report['original_disc']=original['disc'];report['native_audio_source_digest']=body.source_digest(source)
        images={}
        for phase in ('warm','cold'):
            candidate=output/phase
            preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
            owner.host.configure_two_digital_slots(candidate)
            images[phase]=state.staged_image_binding(candidate,args.expected_exe_sha256)
            report['phases'][phase]={}
        if images['warm']!=images['cold']:raise ValueError('Warm/cold image/dependency/assets differ')
        report.update(state.validate_state_build(args.build,args.source,[output/'warm',output/'cold'],
            args.expected_manifest_sha256,output))
        report['originals']=owner.verify_prepared_originals(output/'warm',args.original_exe,args.disc)
        report['checks']['exact_image_manifest_declared_sources_and_originals']=True
        saved=selected=snapshot=None
        for index,phase in enumerate(('warm','cold')):
            candidate=output/phase
            if phase=='cold':
                target=candidate/'saves'/snapshot['slot_relative_path'];target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(snapshot['path'],target)
                if preparation.sha256(target)!=snapshot['sha256']:raise ValueError('Cold exact snapshot copy differs')
            def observe(ctx):
                ctx=dict(ctx,zero_overlay=zero)
                return active.exercise(ctx,original['contract'],source,output=output/(phase+'-state'),
                    phase=phase,saved=saved,selected=selected,timeout=args.case_timeout)
            runtime=report['phases'][phase]
            owner.run_owned(candidate,args.port+index,args.boot_timeout,12,runtime,original['contract'],
                expected_image=args.expected_exe_sha256,first_seat=0,max_attempts=8,audio_timeout=args.case_timeout,
                private_banks=original['private_banks'],custom_observer=observe)
            if runtime.get('cleanup')!=dict(shutdown='graceful_owned_debug',exit_code=0):
                raise ValueError(phase+' owned process did not exit naturally')
            if not runtime.get('existing_private_cards_unchanged'):raise ValueError(phase+' private native cards changed')
            case=runtime['audio']
            if case['status']!=active.SUCCESS or case.get('cleanup_errors'):raise ValueError(phase+' active state case did not complete')
            report['checks'][phase+'_active_voice_restore_and_natural_owned_exit']=True
            if state.staged_image_binding(candidate,args.expected_exe_sha256)!=images[phase]:
                raise ValueError(phase+' staged image/assets changed during qualification')
            if phase=='warm':
                snapshot=case['saved_snapshot'];saved=snapshot['inspection'];selected=case['selected']
        report['status']=active.SUCCESS
    except Exception as error:
        report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
        if any(p.get('active_audio_state',{}).get('status')=='failed_behavior' for p in report['phases'].values()):
            report['status']='failed_behavior'
    finally:
        (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','source','disc','original-disc','original-exe','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('expected-exe-sha256','expected-manifest-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--port',type=int,default=24913)
    parser.add_argument('--boot-timeout',type=int,default=200)
    parser.add_argument('--case-timeout',type=int,default=110)
    args=parser.parse_args()
    if not 1024<=args.port<65535 or not 1<=args.case_timeout<=120 or not 1<=args.boot_timeout<=600:
        parser.error('Require bounded ports and timeouts')
    if any(re.fullmatch('[0-9a-f]{64}',v) is None for v in (args.expected_exe_sha256,args.expected_manifest_sha256)):
        parser.error('Require exact lowercase image/manifest SHA256s')
    result=run(args)
    print(json.dumps({k:result[k] for k in ('status','checks','error') if k in result},indent=2))
    return 0 if result['status']==active.SUCCESS else 1


if __name__=='__main__':raise SystemExit(main())
