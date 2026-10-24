"""State controls must use host input and real operation completion."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_mapped_state as subject
from test_coop_private_state_protocol import image


class MappedStateTests(unittest.TestCase):
    def test_rewind_profile_is_explicit_and_default_audio_guard_stays_off(self):
        import qualify_mmx6_coop_jump_audio as owner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=root/'original.exe';disc=root/'original.bin'
            exe.write_bytes(b'original');disc.write_bytes(b'disc')
            (root/'game.toml').write_text('[game]\nexe='+json.dumps(str(exe))+'\ndisc='+json.dumps(str(disc))+
                '\n[runtime]\nopenbios=true\nbios_hle=true\nbios_hle_keep_intro=false\ndisc_speed="1x"\n',encoding='utf-8')
            settings='[video]\nrewind={}\naspect_ratio="4:3"\nrenderer="opengl"\nfullscreen=0\n'
            (root/'settings.toml').write_text(settings.format('true'),encoding='utf-8')
            with self.assertRaises(ValueError):owner.verify_prepared_originals(root,exe,disc)
            owner.verify_prepared_originals(root,exe,disc,expected_rewind=True)
            self.assertTrue(owner.native_capture_required(root))
            self.assertFalse(owner.native_capture_required(root,rewind_state_case=True,custom_observer=lambda ctx:None))
            with self.assertRaises(ValueError):owner.native_capture_required(root,rewind_state_case=True)
            (root/'settings.toml').write_text(settings.format('false'),encoding='utf-8')
            owner.verify_prepared_originals(root,exe,disc)
            with self.assertRaises(ValueError):owner.verify_prepared_originals(root,exe,disc,expected_rewind=True)
            with self.assertRaises(ValueError):owner.native_capture_required(root,rewind_state_case=True,custom_observer=lambda ctx:None)

    def test_gameplay_adapter_uses_host_input_without_native_overrides(self):
        ctx=dict(set_input=Mock(return_value={'accepted':True}),request=Mock(return_value={'ok':True}))
        adapter=subject.PublishedAdapter(ctx,{})
        adapter.control('press',port=2,buttons=0xdf7f,frames=0)
        ctx['set_input'].assert_called_once_with(1,0x2080);ctx['request'].assert_not_called()
        adapter.control('clear_input',port=1)
        self.assertEqual(ctx['set_input'].call_args.args,(0,0))
        for fields in (dict(port=3,buttons=0xffff,frames=0),dict(port=1,buttons=0xffff,frames=5)):
            with self.assertRaises(subject.debug.DebugError):adapter.control('press',**fields)

    def test_old_or_pending_receipt_cannot_qualify_mapped_action(self):
        before=dict(generation=7,pending=0)
        row=dict(generation=7,pending=0,last_op='save',last_slot=0,last_ok=1)
        self.assertFalse(subject.operation_result(before,row,'save',0,True))
        self.assertFalse(subject.operation_result(before,dict(row,generation=8,pending=1),'save',0,True))
        self.assertTrue(subject.operation_result(before,dict(row,generation=8),'save',0,True))
        for changed in (dict(row,generation=8,last_op='load'),dict(row,generation=8,last_slot=1),dict(row,generation=8,last_ok=0)):
            with self.assertRaises(subject.debug.DebugError):subject.operation_result(before,changed,'save',0,True)
        self.assertTrue(subject.operation_result(before,dict(row,generation=8,last_op='load',last_slot=1,last_ok=0),'load',1,False))

    def test_current_build_forgery_changes_only_internal_provider_version(self):
        for compressed in (False,True):
            valid=image(compress=compressed);invalid=subject.malformed_current_wire(valid)
            self.assertEqual(valid[:36],invalid[:36])
            with self.assertRaises(subject.debug.DebugError):subject.state.parse_state_image(invalid)
            def sections(raw):
                at=36;result={}
                for _ in range(struct.unpack_from('<I',raw,28)[0]):
                    tag,flags,size=struct.unpack_from('<IIQ',raw,at);at+=16
                    data=raw[at:at+size];at+=size
                    result[tag]=zlib.decompress(data[4:]) if flags else data
                self.assertEqual(at,len(raw));return result
            old,new=sections(valid),sections(invalid)
            self.assertEqual(old[2],new[2]);self.assertEqual(old[9],new[9])
            differences=[i for i,(a,b) in enumerate(zip(old[0x16],new[0x16])) if a!=b]
            self.assertEqual(len(differences),1)
            self.assertEqual((old[0x16][differences[0]],new[0x16][differences[0]]),
                             (subject.state.HOST_WIRE_SCHEMA,subject.state.HOST_WIRE_SCHEMA+1))


if __name__=='__main__':unittest.main()
