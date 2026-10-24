"""Online refusal requires unchanged completed state and full pair admission gates."""
import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_state_policy as subject
import qualify_mmx6_coop_pair as runner


class StatePolicyTests(unittest.TestCase):
    def test_pending_or_changed_operation_cannot_qualify_refusal(self):
        initial=dict(generation=0,pending=0,last_op='none',last_slot=-1,last_ok=0)
        self.assertTrue(subject.unchanged_operation(initial,dict(initial)))
        for changes in (dict(generation=1),dict(pending=1),dict(last_op='save'),dict(last_slot=0),dict(last_ok=1)):
            self.assertFalse(subject.unchanged_operation(initial,dict(initial,**changes)))
        self.assertFalse(subject.unchanged_operation({},{}))

    def test_policy_cannot_skip_image_manifest_source_profile_or_crc_gates(self):
        parser=runner.make_parser()
        argv=['--tools-root','tools','--build','build','--disc','disc.cue','--out','out',
              '--state-policy-smoke','--require-state-crc','--require-host-profile',
              '--expected-host-profile','mmx6.win64-clang22.loopback','--expected-host-profile-revision','2',
              '--expected-exe-sha256','a'*64,'--expected-manifest-sha256','b'*64,
              '--original-exe','SLUS_013.95','--original-disc','disc.bin']
        args=parser.parse_args(argv);runner.validate_options(parser,args)
        for key,value in [('expected_exe_sha256',None),('expected_manifest_sha256',None),
                          ('original_exe',None),('original_disc',None),('require_host_profile',False),
                          ('require_state_crc',False),('native_loader_diagnostic',True),
                          ('admission_only',True),('jump_audio_smoke',True)]:
            changed=parser.parse_args(argv);setattr(changed,key,value)
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                runner.validate_options(parser,changed)


if __name__=='__main__':unittest.main()
