"""Body audio sample and lifetime reducer regressions; no game/audio device."""
import copy
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import mmx6_coop_body_audio as subject
from test_mmx6_coop_jump_audio_private import private_voices,hardware


DATA = bytes(range(256))*16 + bytes(range(96))


def fixture():
    tone = dict(voice=23, program=0, tone=8, offset=33744, bytes=len(DATA),
        sample_sha256=hashlib.sha256(DATA).hexdigest(), pitch=1144, adsr_lo=33023,
        adsr_hi=8128, first_end_block=260, first_end_flags=1)
    source = dict(body_records=[dict(group=1,record=7,tones=[tone])])
    event = dict(seq=10,frame=100,kind='KEYON',v=47,sample_bank=30,addr=33744,
        pitch=1144,adsr_lo=33023,adsr_hi=8128)
    return source,event


class Bank:
    private_banks = dict(banks=[dict(bank=30,bytes=123408)])
    def __init__(self):self.reads=[]
    def bank_read(self,bank,address,count,size):
        if bank!=30 or size!=123408 or not 0<count<=4096:raise AssertionError('Unbounded source probe')
        self.reads.append((address,count));offset=address-33744
        return dict(data=DATA[offset:offset+count])


class BodyAudioTests(unittest.TestCase):
    def run_case(self,never_accept=False):
        source,key=fixture();calls=[]
        private=private_voices();private['voices'][23].update(sample_bank=30,pending_bank=0,start=f"0x{key['addr']:05X}",
            pitch='0x0478',adsr_lo='0x80FF',adsr_hi='0x1FC0',vol_l='0x0000',vol_r='0x0000',env='0x0000',env_phase=3,mode=0)
        class Observer(Bank):
            def __init__(self):super().__init__();self.events=[];self.cursor=0;self.count=0
            def fingerprint_banks(self):return [dict(bank=30,sha256='a'*64)]
            def poll(self):
                self.count+=1;calls.append(('poll',self.count))
                action=2
                if not never_accept:
                    if self.count==4:self.events.append(key);action=0x30;self.cursor=11
                    if self.count==5:self.events.append(dict(key,kind='KEYOFF',seq=11,frame=110));self.cursor=12
                o=dict(ready=1,enrolled=1,failed=0,mailbox=0,native_mode=10,native_phase=0,scene_owner=0,
                    pause_owner=0,lifecycle=[0,0],native_timer=self.count,tick=self.count)
                return dict(observation=o,players=[dict(character=0,form=1,state=1,hp=32,action=2,ground=True,airborne=0),
                    dict(character=1,form=5,state=1,hp=32,action=action,ground=True,airborne=0)])
        observer=Observer();report={}
        def set_input(seat,bits):calls.append(('input',seat,bits));return dict(ack=True)
        def request(cmd):return hardware() if cmd=='spu_voices' else private
        ctx=dict(mode='local',input_path='published_host',clients=[object()],request=request,private_banks={},
            report=report,set_input=set_input,native_advance=lambda *args:None)
        with patch.object(subject.audio,'AudioObserver',return_value=observer):
            if never_accept:
                with self.assertRaises(subject.audio.AudioQualificationError):subject.exercise(ctx,{},source=source,timeout=5)
            else:
                result=subject.exercise(ctx,{},source=source,timeout=5)
                self.assertEqual(result['status'],'observations_complete');self.assertTrue(all(result['checks'].values()))
        return report,calls

    def test_square_remains_held_until_actual_saber_and_keyon(self):
        report,calls=self.run_case()
        self.assertLess(calls.index(('poll',4)),calls.index(('input',1,0)))
        self.assertEqual(report['accepted_windows'][0]['actual_native_ticks'],2)

    def test_missing_native_action_stops_at_bound_and_clears_input(self):
        report,calls=self.run_case(never_accept=True)
        self.assertEqual(calls[-1],('input',1,0));self.assertNotEqual(report['body_audio']['status'],'observations_complete')
        self.assertLess(len([x for x in calls if x[0]=='poll']),130)

    def test_sample_larger_than_debug_read_limit_uses_exact_bounded_chunks(self):
        source,event=fixture();bank=Bank();result=subject.identify(bank,event,source)
        self.assertTrue(all(result['checks'].values()))
        self.assertEqual(bank.reads,[(33744,4096),(37840,96)])

    def test_wrong_bank_address_voice_pitch_or_sample_never_passes(self):
        for field,value in (('sample_bank',31),('addr',33745)):
            source,event=fixture();event[field]=value
            with self.assertRaises(subject.audio.AudioQualificationError):subject.identify(Bank(),event,source)
        for field,value in (('v',23),('pitch',1145),('adsr_hi',0)):
            source,event=fixture();event[field]=value
            self.assertFalse(all(subject.identify(Bank(),event,source)['checks'].values()))
        source,event=fixture();source['body_records'][0]['tones'][0]['sample_sha256']='0'*64
        self.assertFalse(subject.identify(Bank(),event,source)['checks']['source_sample'])

    def test_stop_does_not_borrow_a_replacement_notes_envelope(self):
        source,key=fixture();selected=subject.identify(Bank(),key,source)
        private=private_voices();row=private['voices'][23]
        row.update(sample_bank=30,pending_bank=0,start=key['addr'],pitch=1144,adsr_lo=33023,adsr_hi=8128,
            vol_l=0,vol_r=0,env=0,env_phase=3,mode=0)
        off=dict(key,seq=11,frame=110,kind='KEYOFF')
        checks,details=subject.final_checks([key,off],selected,private)
        self.assertTrue(all(checks.values()));self.assertEqual(details['lifetime']['disposition'],'keyed_off')
        checks,details=subject.final_checks([key,off,dict(key,seq=12,frame=111)],selected,private)
        self.assertFalse(checks['final_dsp_attribution']);self.assertFalse(checks['private_native_stop_observed'])
        self.assertTrue(details['replaced'])

    def test_natural_end_alone_does_not_claim_native_stop_or_volume_zero(self):
        source,key=fixture();selected=subject.identify(Bank(),key,source)
        private=private_voices();private['voices'][23].update(sample_bank=30,pending_bank=0,start=key['addr'],
            pitch=1144,adsr_lo=33023,adsr_hi=8128,vol_l=123,vol_r=456,env=0,env_phase=3,mode=0)
        checks,details=subject.final_checks([key,dict(key,seq=11,frame=110,kind='END_STOP')],selected,private)
        self.assertEqual(details['lifetime']['disposition'],'natural_end')
        self.assertFalse(checks['private_native_stop_observed']);self.assertFalse(checks['stopped_volume_zero'])

    def test_ambiguous_source_and_cross_bank_terminal_are_rejected(self):
        source,key=fixture();source['body_records'].append(copy.deepcopy(source['body_records'][0]))
        with self.assertRaises(subject.audio.AudioQualificationError):subject.identify(Bank(),key,source)
        source,key=fixture();selected=subject.identify(Bank(),key,source)
        with self.assertRaises(subject.audio.AudioQualificationError):
            subject.final_checks([key,dict(key,seq=11,frame=110,kind='KEYOFF',sample_bank=31)],selected,private_voices())

    @unittest.skipUnless(os.environ.get('MMX6_AUDIO_EXE') and os.environ.get('MMX6_AUDIO_DISC'),'Original EXE/disc required')
    def test_original_body_records_have_source_calculated_pitch(self):
        result=subject.build_source(Path(os.environ['MMX6_AUDIO_EXE']),Path(os.environ['MMX6_AUDIO_DISC']))
        self.assertEqual(len(result['body_records']),8)
        self.assertTrue(all(0<r['tones'][0]['pitch']<=0x3FFF for r in result['body_records']))
        self.assertEqual([r['tones'][0]['tone'] for r in result['body_records']],[1,3,4,5,6,7,8,9])


if __name__=='__main__':unittest.main()
