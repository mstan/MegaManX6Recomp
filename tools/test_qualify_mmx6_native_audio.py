"""Fail-closed native audio attribution/route tests, not gameplay evidence."""
import unittest
from unittest.mock import Mock

import qualify_mmx6_native_audio as native


def fixture():
    tone = dict(voice=20,offset=16,bytes=16,sample_sha256=native.original.sha(bytes(16)),
                pitch=4096,adsr_lo=3,adsr_hi=4,first_end_block=0,first_end_flags=1)
    record = dict(group=3,record=4,effective_bank_group=3,tones=[tone])
    event = dict(v=20,addr=0x10010,sample_bank=0,frame=100,kind='KEYON',
                 pitch=4096,adsr_lo=3,adsr_hi=4)
    call = dict(target=hex(native.SOUND),a0='0x00000003',a1='0x00000004',
                a2=hex(native.reference.PLAYER),frame=100)
    bases = [0]*16
    bases[3] = 0x10000
    return event,call,dict(records=[record]),bases


class AttributionTests(unittest.TestCase):
    def test_source_call_and_next_frame_hardware_queue_are_explicit(self):
        event,call,source,bases = fixture()
        for lag in (0,1):
            event['frame'] = call['frame']+lag
            self.assertEqual(native.candidate_tones(event,[call],source,bases)['queued_engine_frames'],lag)

    def test_other_actor_group_record_voice_address_and_late_event_are_not_attributed(self):
        event,call,source,bases = fixture()
        for field,value in (('a2','0x80097200'),('a0','0x00000001'),('a1','0x00000007'),
                            ('target',hex(native.STOP)),('frame',98),('frame',101)):
            changed=dict(call,**{field:value})
            self.assertIsNone(native.candidate_tones(event,[changed],source,bases))
        for field,value in (('v',21),('addr',0x10020)):
            self.assertIsNone(native.candidate_tones(dict(event,**{field:value}),[call],source,bases))

    def test_private_event_is_rejected_and_ambiguous_calls_are_not_guessed(self):
        event,call,source,bases = fixture()
        for field,value in (('v',44),('sample_bank',31)):
            with self.assertRaises(native.debug.DebugError):
                native.candidate_tones(dict(event,**{field:value}),[call],source,bases)
        with self.assertRaises(native.debug.DebugError):
            native.candidate_tones(event,[call,dict(call)],source,bases)

    def test_effective_cross_bank_alias_preserves_original_call_identity(self):
        event,call,source,bases = fixture()
        source['records'][0].update(group=3,record=17,effective_bank_group=1)
        bases[1]=bases[3]
        call['a1']='0x00000011'
        self.assertEqual(native.candidate_tones(event,[call],source,bases)['record']['effective_bank_group'],1)

    def test_child_requires_source_route_same_frame_initializer_and_exact_actor(self):
        event,call,source,bases = fixture()
        call.update(a2='0x80091298',ra='0x800493D4')
        route=dict(sound_return=0x800493D4,initializer=native.X_BUSTER_INIT,attribution='source_guarded_child')
        source['child_routes']=[route]
        init=dict(target=hex(native.X_BUSTER_INIT),frame=call['frame'],a0=call['a2'])
        result=native.candidate_tones(event,[init,call],source,bases)
        self.assertEqual(result['actor_attribution'],'source_guarded_child')
        for changed in ([],[dict(init,frame=99)],[dict(init,a0='0x800912F8')]):
            self.assertIsNone(native.candidate_tones(event,[*changed,call],source,bases))
        self.assertIsNone(native.candidate_tones(event,[init,dict(call,ra='0x800493D8')],source,bases))
        source['child_routes']=[]
        self.assertIsNone(native.candidate_tones(event,[init,call],source,bases))

    def test_sample_bytes_and_numeric_dsp_must_both_match(self):
        event,call,source,bases = fixture()
        observer=native.Observer(Mock(),source)
        observer.sample_bytes=Mock(return_value=bytes(16))
        result=observer.identify(event,[call],dict(bases=bases))
        self.assertTrue(all(result['checks'].values()))
        observer.sample_bytes.return_value=b'bad sample bytes'
        with self.assertRaises(native.debug.DebugError):
            observer.identify(event,[call],dict(bases=bases))
        observer.sample_bytes.return_value=bytes(16)
        with self.assertRaises(native.debug.DebugError):
            observer.identify(dict(event,pitch=1024),[call],dict(bases=bases))

    def test_sample_probe_chunks_large_native_x_bank_and_rejects_truncation(self):
        session=Mock()
        session.request.side_effect=lambda command,**kw:dict(addr=hex(kw['addr']),len=kw['len'],hex=bytes(kw['len']).hex())
        observer=native.Observer(session,{})
        self.assertEqual(len(observer.sample_bytes(0x10000,182064)),182064)
        self.assertEqual(session.request.call_count,45)
        self.assertLessEqual(max(c.kwargs['len'] for c in session.request.call_args_list),4096)
        session.request.side_effect=lambda command,**kw:dict(addr=hex(kw['addr']),len=kw['len'],hex='00')
        with self.assertRaises(native.debug.DebugError):
            observer.sample_bytes(0x10000,4096)

    def test_shared_wave_identity_never_establishes_sound_record_or_actor_identity(self):
        event,call,source,bases = fixture()
        source['records'][0]['tones'][0].update(program=0,tone=3)
        other=dict(source['records'][0],record=8)
        source['records'].append(other)
        observer=native.Observer(Mock(),source)
        observer.sample_bytes=Mock(return_value=bytes(16))
        row=observer.identify_sample_only(event,dict(bases=bases))
        self.assertEqual([r['record'] for r in row['record_candidates']],[4,8])
        self.assertFalse(row['exact_sound_record_identity'])
        self.assertIn('unverified',row['actor_attribution'])
        self.assertNotIn('source_call',row)
        with self.assertRaises(native.debug.DebugError):
            observer.identify_sample_only(dict(event,pitch=1024),dict(bases=bases))

    def test_new_session_commands_add_no_audio_mutation_or_guest_execution(self):
        additions=native.Session.ALLOWED-native.reference.OwnedNativeSession.ALLOWED
        self.assertEqual(additions,native.READONLY_AUDIO|native.TRACE_COMMANDS)
        self.assertFalse({'call','spu_write','spu_keyon','load_state','save_state'} & additions)

    def test_evicted_trace_is_rejected(self):
        session=Mock()
        session.request.return_value=dict(seq_lo=1,seq_hi=1,emitted=0,entries=[])
        with self.assertRaises(native.debug.DebugError):
            native.trace_page(session)


if __name__ == '__main__':
    unittest.main()
