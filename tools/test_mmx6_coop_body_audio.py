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
        for slot,row in enumerate(private['voices']):
            row['owner_tag']=f"0x{subject.VOICE_OWNER if subject.VOICE_MASK&(1<<slot) else 0:016X}"
        class Observer(Bank):
            def __init__(self):super().__init__();self.events=[];self.cursor=0;self.count=0
            def fingerprint_banks(self):return [dict(bank=30,sha256='a'*64)]
            def driver(self):return {}
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
        def request(cmd,**fields):
            if cmd=='fntrace_armed':return dict(count=4,targets=[hex(t)for t in subject.TRACE_TARGETS])
            if cmd=='fntrace_dump':return dict(seq_lo=0,seq_hi=1,emitted=1,entries=[dict(seq=0,target='0x80016C48',
                a0='0x1',a1='0x7',a2='0x800970A0',ra='0x801EA040',frame=100)])
            if cmd.startswith('fntrace_'):return dict(ok=True)
            return hardware() if cmd=='spu_voices' else private
        ctx=dict(mode='local',input_path='published_host',clients=[object()],request=request,private_banks={},
            report=report,set_input=set_input,native_advance=lambda *args:None)
        with patch.object(subject.audio,'AudioObserver',return_value=observer):
            if never_accept:
                with self.assertRaises(subject.audio.AudioQualificationError):subject.exercise(ctx,{},source=source,timeout=5)
            else:
                result=subject.exercise(ctx,{},source=source,timeout=5)
                self.assertEqual(result['status'],'observations_partial');self.assertTrue(all(result['checks'].values()))
        return report,calls

    def test_square_remains_held_until_actual_saber_and_keyon(self):
        report,calls=self.run_case()
        self.assertLess(calls.index(('poll',4)),calls.index(('input',1,0)))
        self.assertEqual(report['accepted_windows'][0]['actual_native_ticks'],2)

    def test_voice_leases_require_all_nine_slots_by_owner_even_with_same_bank(self):
        reply=private_voices()
        for slot,row in enumerate(reply['voices']):
            row['owner_tag']=f"0x{subject.VOICE_OWNER if subject.VOICE_MASK&(1<<slot) else 0:016X}"
        self.assertEqual(len(subject.voice_leases(reply)),24)
        for slot,value in ((23,'0x0000000000000001'),(1,f'0x{subject.VOICE_OWNER:016X}'),(20,None)):
            changed=copy.deepcopy(reply);changed['voices'][slot]['owner_tag']=value
            with self.subTest(slot=slot),self.assertRaises(subject.audio.AudioQualificationError):subject.voice_leases(changed)

    def test_general_vocal_needs_exact_call_bank_bytes_and_numeric_registers(self):
        source,event=fixture();record=source['body_records'][0]
        record.update(group=3,record=3,effective_bank_group=3);record['tones'][0].update(voice=20,offset=0)
        event.update(v=44,sample_bank=31,addr=0)
        call=dict(target='0x80016C48',a0='0x83',a1='0x103',a2='0x800970A0',frame=100)
        class VocalBank:
            private_banks=dict(banks=[dict(bank=31,bytes=52096)])
            def bank_read(self,bank,address,count,size):
                if bank!=31 or not 0<count<=4096 or size!=52096:raise AssertionError('Wrong source bank probe')
                return dict(data=DATA[address:address+count])
        result=subject.identify_character(VocalBank(),event,source,[call])
        self.assertTrue(all(result['checks'].values()));self.assertEqual(result['record']['record'],3)
        for changed in (dict(call,frame=101),dict(call,a2='0x8008EF48'),dict(call,a1='0x4')):
            with self.assertRaises(subject.audio.AudioQualificationError):subject.identify_character(VocalBank(),event,source,[changed])
        wrong=dict(event,pitch=1145)
        self.assertFalse(subject.identify_character(VocalBank(),wrong,source,[call])['checks']['pitch_adsr_numeric'])

    def test_general_vocal_record17_retains_effective_effects_bank(self):
        source,event=fixture();record=source['body_records'][0]
        record.update(group=3,record=17,effective_bank_group=1);record['tones'][0]['voice']=3
        event['v']=27
        call=dict(target='0x80016C48',a0='0x3',a1='0x11',a2='0x800970A0',frame=100)
        self.assertTrue(all(subject.identify_character(Bank(),event,source,[call])['checks'].values()))

    def test_standing_terminal_does_not_require_an_unissued_stop(self):
        source,key=fixture();selected=subject.identify(Bank(),key,source)
        private=subject.audio.parse_private_voices(private_voices())
        private['voices'][23].update(sample_bank=30,start=key['addr'],pitch=1144,adsr_lo=33023,adsr_hi=8128,
            vol_l=100,vol_r=200,active=0,env=0,env_phase=3,mode=0)
        events=[key,dict(key,seq=11,frame=127,kind='END_STOP')]
        checks,_=subject.standing_checks(events,selected,private)
        self.assertTrue(all(checks.values()))
        self.assertNotIn('standing_saber_stopped_volume_zero',checks)
        private['voices'][23]['sample_bank']=31
        self.assertFalse(subject.standing_checks(events,selected,private)[0]['standing_saber_final_dsp_attribution'])

    def test_inactive_stop_obscured_by_death_play_is_pending_never_a_pass(self):
        source,key=fixture();selected=subject.identify(Bank(),key,source)
        before=subject.audio.parse_private_voices(private_voices());after=copy.deepcopy(before)
        before['voices'][23].update(sample_bank=30,start=key['addr'],active=0,env=0,env_phase=3)
        later=dict(key,seq=12,frame=208,kind='KEYON',sample_bank=31,addr=39152,pitch=1290)
        after['voices'][23].update(sample_bank=31,start=39152,pitch=1290,adsr_lo=33023,adsr_hi=8128)
        events=[key,dict(key,seq=11,frame=127,kind='END_STOP'),later]
        trace=dict(entries=[dict(target='0x8001750C',a0='0x1',a1='0x7',ra='0x8003D8D0',frame=200)])
        sample=dict(event=later,record=dict(group=3,record=14),checks=dict(private_voice_route=True,
            source_sample=True,pitch_adsr_numeric=True,original_end_marker_present=True))
        def hidden():return subject.obscured_inactive_stop7(events,selected,before,after,trace,[sample])
        self.assertTrue(hidden())
        before['voices'][23]['active']=1;self.assertFalse(hidden());before['voices'][23]['active']=0
        events.insert(2,dict(key,seq=11,frame=190));self.assertFalse(hidden());events.pop(2)
        sample['checks']['source_sample']=False;self.assertFalse(hidden());sample['checks']['source_sample']=True
        sample['checks']={};self.assertFalse(hidden())

    def test_missing_native_action_stops_at_bound_and_clears_input(self):
        report,calls=self.run_case(never_accept=True)
        self.assertEqual(calls[-1],('input',1,0));self.assertNotEqual(report['body_audio']['status'],'observations_complete')
        self.assertLess(len([x for x in calls if x[0]=='poll']),130)

    def test_phase2_stop_requires_exact_call_and_same_frame_private_keyoff(self):
        calls=[dict(target='0x8001750C',a0='0x1',a1=hex(record),ra=hex(ra),frame=200)
            for record,ra in ((5,0x8003D8C4),(7,0x8003D8D0))]
        calls.append(dict(target='0x8003D8A8',a0='0x800970A0',frame=200))
        events=[dict(v=v,kind='KEYOFF',sample_bank=30,frame=200)for v in (46,47)]
        self.assertTrue(all(subject.phase2_checks(dict(entries=calls),events).values()))
        delayed=copy.deepcopy(events);delayed[1]['frame']=201
        self.assertFalse(subject.phase2_checks(dict(entries=calls),delayed)['private23_phase2_stop'])
        self.assertFalse(subject.phase2_checks(dict(entries=calls),events+[dict(v=22,kind='KEYOFF',frame=200)])['p1_hardware22_23_not_stopped'])
        wrong=copy.deepcopy(calls);wrong[1]['ra']='0x8003F49C'
        self.assertFalse(subject.phase2_checks(dict(entries=wrong),events)['original_phase2_stop_calls'])

    def test_native_death_requires_eight_unmodified_strength4_contacts(self):
        def row(hp,counter):
            return dict(observation=dict(players=[dict(x_raw=144<<16),dict(x_raw=350<<16)],native_timer=counter*80),
                players=[dict(hp_raw=32,state=1),dict(hp=hp,terrain=0,previous_terrain=0)],p2_contact_counter=counter,
                expected_damage=4,expected_reaction=1,instance=dict(phase=1,hp=12,strength=4,subtype=1,
                    contact_class=0,address='0x8008ef48',x_raw=400<<16))
        for skipped,retirement in ((False,None),(True,None),(False,-1),(False,-2)):
            rows=[row(32-4*i,i)for i in range(9)]
            if skipped:rows.pop(3)
            if retirement is not None:rows[retirement]['instance']['phase']=3
            calls=[dict(seq=i,target='0x8001750C',a0='0x1',a1=hex(record),ra=hex(ra),frame=200)
                for i,(record,ra)in enumerate(((5,0x8003D8C4),(7,0x8003D8D0)))]
            calls.append(dict(seq=2,target='0x8003D8A8',a0='0x800970A0',frame=200))
            inputs=[];ctx=dict(clients=[object()],zero_overlay=b'',set_input=lambda s,b:inputs.append((s,b)),
                request=lambda *a,**k:dict(seq_lo=0,seq_hi=3,emitted=3,entries=calls))
            observer=type('Observer',(),{'events':[]})();case={}
            def sample(label):
                if label=='body-audio-phase2-stop':observer.events.append(dict(v=47,kind='KEYOFF',sample_bank=30,frame=200))
                return {}
            with patch.object(subject.contact,'observe_contact',side_effect=rows):
                if skipped or retirement==-2:
                    with self.assertRaises(subject.audio.AudioQualificationError):
                        subject.native_death(ctx,sample,observer,case,lambda *a:dict(observation={}))
                else:
                    subject.native_death(ctx,sample,observer,case,lambda *a:dict(observation={}))
                    self.assertEqual(len(case['native_death']['hp_changes']),8)
                    self.assertEqual(case['native_death']['enemy_retired_after_fatal'],retirement==-1)
            self.assertEqual(inputs[-1],(1,0))

    def test_inactive_stop_needs_owned_volume_transition_and_preserved_hardware(self):
        calls=[dict(target='0x8001750C',a0='0x1',a1=hex(record),ra=hex(ra),frame=200)
            for record,ra in ((5,0x8003D8C4),(7,0x8003D8D0))]
        calls.append(dict(target='0x8003D8A8',a0='0x800970A0',frame=200))
        before=subject.audio.parse_private_voices(private_voices());after=copy.deepcopy(before)
        before['voices'][23].update(sample_bank=30,start=33744,active=0,env=0,env_phase=3,vol_l=100,vol_r=200)
        after['voices'][23]=dict(before['voices'][23],vol_l=0,vol_r=0)
        hw=subject.audio.parse_voices(hardware(),require_banks=True);hw['voices'][22].update(vol_l=456,vol_r=789)
        events=[dict(v=47,kind='KEYON',sample_bank=30,frame=100),dict(v=47,kind='END_STOP',sample_bank=30,frame=127)]
        def checks():return subject.phase2_checks(dict(entries=calls),events,before_private=before,after_private=after,
            before_hardware=hw,after_hardware=copy.deepcopy(hw))
        self.assertTrue(all(checks().values()))
        before['voices'][23]['active']=1;self.assertFalse(checks()['private23_phase2_stop'])
        before['voices'][23]['active']=0;after['voices'][23]['vol_l']=100
        self.assertFalse(checks()['private23_phase2_stop'])
        after['voices'][23]['vol_l']=0;events.append(dict(v=47,kind='KEYON',sample_bank=30,frame=150))
        self.assertFalse(checks()['private23_phase2_stop'])

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

    def test_alias_record_needs_the_actual_same_frame_sound_call(self):
        source,event=fixture();alias=copy.deepcopy(source['body_records'][0]);alias['record']=8
        alias['tones'][0]['tone']=9;source['body_records'].append(alias)
        call=dict(target='0x80016C48',a0='0x1',a1='0x7',a2='0x800970A0',ra='0x801EBE90',frame=100)
        with self.assertRaises(subject.audio.AudioQualificationError):subject.identify(Bank(),event,source)
        selected=subject.identify(Bank(),event,source,sound_calls=[call])
        self.assertEqual(selected['record']['record'],7)
        self.assertEqual(selected['record_selection'],'event_time_original_sound_call')
        for changed in (dict(call,frame=101),dict(call,a2='0x8008EF48')):
            with self.assertRaises(subject.audio.AudioQualificationError):subject.identify(Bank(),event,source,sound_calls=[changed])

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
