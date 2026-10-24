"""Stage/own one exact local X-primary audio and surviving-Zero observation."""
import argparse
import json
from pathlib import Path
import re
import traceback

import mmx6_coop_jump_audio_pair as binding
import mmx6_coop_primary_audio as primary
import prepare_mmx6_coop_playtest as preparation
import qualify_mmx6_coop_jump_audio as owner


def run(args):
    output=preparation.local_output(args.out);output.mkdir(parents=True,exist_ok=False)
    report=dict(kind='owned_local_primary_audio',status='failed_setup',r4='unverified',r12='unverified',
        runtime={},checks={},limits=['Local same-machine native co-op only; no paired, physical-input or full R4/R12 pass.'])
    try:
        original=binding.load_sources(args.original_exe,args.original_disc,args.disc,
            args.source/'docs/COOP_JUMP_AUDIO_CONTRACT.json')
        source=primary.sources(args.original_exe,args.original_disc)
        for module in (primary,owner,binding,primary.native,primary.contact):
            path=Path(module.__file__)
            (output/(path.stem+'-executed-source.py')).write_bytes(path.read_bytes())
        report['source_disc']=original['disc']
        candidate=output/'candidate'
        preparation.prepare(args.build,args.source,candidate,args.disc,automated=True)
        owner.host.configure_two_digital_slots(candidate)
        owner.host.verify_expected_image(candidate/'mmx6-runtime.exe',args.expected_exe_sha256)
        manifest=owner.manifests.validate_build_manifest(args.build,
            [args.build/'mmx6-runtime.exe',candidate/'mmx6-runtime.exe'],evidence_directory=output/'manifest')
        if manifest['declared_sha256']!=args.expected_manifest_sha256:
            raise ValueError('Primary audio compiled manifest differs from explicit expected identity')
        report['manifest']=manifest
        report['declared_sources']=owner.validate_sources(args.build,args.source,manifest)
        report['originals']=owner.verify_prepared_originals(candidate,args.original_exe,args.disc)
        report['checks']['exact_image_manifest_sources_and_originals']=True
        def observe(ctx):
            return primary.exercise(dict(ctx,output=output/'primary-audio'),original['contract'],source,
                timeout=args.case_timeout)
        runtime_error=None
        try:
            owner.run_owned(candidate,args.port,args.boot_timeout,12,report['runtime'],original['contract'],
                expected_image=args.expected_exe_sha256,first_seat=0,max_attempts=8,audio_timeout=args.case_timeout,
                private_banks=original['private_banks'],custom_observer=observe)
        except Exception as error:runtime_error=error
        runtime=report['runtime']
        if runtime.get('cleanup')!=dict(shutdown='graceful_owned_debug',exit_code=0) or not runtime.get('existing_private_cards_unchanged'):
            raise ValueError('Primary audio owned cleanup/private-card verification failed')
        report['checks']['owned_natural_exit_and_private_cards']=True
        if runtime_error is not None:raise runtime_error
        case=runtime['audio']
        if case['status'] not in (primary.OBSERVED,primary.PARTIAL):
            raise ValueError('Primary audio observer/late input cleanup did not complete')
        if case.get('input_cleanup_errors') or any(p.get('disarm_error') for p in case['peers']):
            raise ValueError('Primary audio left an input or source trace armed')
        report['square_capture']=owner.inspect_capture(candidate,args.expected_exe_sha256,
            args.expected_manifest_sha256,{0,1},button=0x8000)
        report['cross_capture']=owner.inspect_capture(candidate,args.expected_exe_sha256,
            args.expected_manifest_sha256,{1},button=0x4000)
        report['checks']['finalized_exact_native_input_capture']=True
        report['status']=case['status']
    except Exception as error:
        report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
    finally:
        primary.native.write_json(output/'qualification.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','source','disc','original-disc','original-exe','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('expected-exe-sha256','expected-manifest-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--port',type=int,default=24942)
    parser.add_argument('--boot-timeout',type=float,default=240)
    parser.add_argument('--case-timeout',type=float,default=150)
    args=parser.parse_args()
    if any(re.fullmatch(r'[0-9a-f]{64}',getattr(args,k)) is None for k in ('expected_exe_sha256','expected_manifest_sha256')):
        parser.error('Require explicit lowercase image/manifest hashes')
    if not 1024<=args.port<=65535 or not 0<args.boot_timeout<=600 or not 0<args.case_timeout<=180:
        parser.error('Require unprivileged port and bounded boot/case deadlines')
    r=run(args)
    print(json.dumps({k:r[k] for k in ('status','error','error_type') if k in r}))
    return 2 if r['status'] in (primary.OBSERVED,primary.PARTIAL) else 1


if __name__=='__main__':raise SystemExit(main())
