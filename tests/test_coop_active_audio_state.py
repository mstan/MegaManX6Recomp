"""Reject silent/stale/wrong-owner audio as evidence of native active restore."""
import copy
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_active_audio_state as subject
from test_coop_private_state_protocol import image,spu_wire
from test_mmx6_coop_jump_audio_private import private_voices


def fixture():
    event=dict(v=44,sample_bank=31,addr=0x8000,pitch=0x1000,adsr_lo=0x80ff,adsr_hi=0x1fc0)
    selected=dict(event=event)
    raw=spu_wire();at=subject.state.SPU_BASE_BYTES+20*subject.state.SPU_PRIVATE_STRIDE
    struct.pack_into('<8H',raw,at,0x1000,0x1000,event['pitch'],event['addr']//8,event['adsr_lo'],event['adsr_hi'],0,0)
    struct.pack_into('<i4I',raw,at+25,1,0x8100,0x8000,31,0)
    struct.pack_into('<H',raw,at+25+95,0x2345)
    saved=subject.state.parse_state_image(image(spu=raw))
    reply=private_voices();reply['active_mask']='0x100000'
    for slot,row in enumerate(reply['voices']):
        row['owner_tag']=f'0x{subject.state.MMX6_AUDIO_OWNER if subject.state.MMX6_AUDIO_MASK&(1<<slot) else 0:016x}'
    reply['voices'][20].update(active=1,sample_bank=31,start='0x08000',pitch='0x1000',adsr_lo='0x80ff',adsr_hi='0x1fc0',env='0x2345')
    return selected,saved,reply


class ActiveAudioStateTests(unittest.TestCase):
    def test_quiet_voice_without_observed_terminal_does_not_finish_drain(self):
        selected,_,reply=fixture()
        voice=subject.audio.parse_private_voices(reply)['voices'][20]
        voice.update(env=0,env_phase=3)
        event=dict(seq=8,v=44,sample_bank=31,kind='END_STOP')
        self.assertFalse(subject.source_drained(voice,selected,[],8))
        self.assertFalse(subject.source_drained(voice,selected,[event],9))
        self.assertTrue(subject.source_drained(voice,selected,[event],8))
        for changed in (dict(event,sample_bank=30),dict(event,kind='KEYOFF'),dict(event,v=47)):
            self.assertFalse(subject.source_drained(voice,selected,[changed],8))

    def test_load_boundary_keeps_early_events_and_rejects_reset_or_eviction(self):
        rows=[dict(seq=i,kind='KEYON' if i==3 else 'END_STOP',v=44) for i in range(5)]
        self.assertEqual(subject.load_boundary_events(3,dict(event_total=5,new_events=rows)),rows[3:])
        self.assertEqual(subject.load_boundary_events(5,dict(event_total=5,new_events=rows)),[])
        for checkpoint,total,events in ((6,5,rows),(2,5,rows[3:]),(3,5,[rows[4],rows[3]]),(0,1<<50,[])):
            with self.subTest(checkpoint=checkpoint,total=total),self.assertRaises(subject.debug.DebugError):
                subject.load_boundary_events(checkpoint,dict(event_total=total,new_events=events))

    def test_serialized_and_live_source_voice_are_both_active(self):
        selected,saved,reply=fixture()
        self.assertEqual(subject.active_snapshot(saved,selected)['slot'],20)
        self.assertTrue(subject.active_live(reply,selected)[0])

    def test_inactive_or_zero_envelope_snapshot_is_not_active_restore(self):
        selected,saved,_=fixture()
        for key in ('active','env_level'):
            changed=copy.deepcopy(saved);changed['private_spu']['voices'][20][key]=0
            with self.subTest(key=key),self.assertRaises(subject.debug.DebugError):
                subject.active_snapshot(changed,selected)

    def test_same_bank_without_owner_cannot_qualify(self):
        selected,saved,reply=fixture()
        changed=copy.deepcopy(saved);changed['private_spu']['owner_tags'][20]=0
        with self.assertRaises(subject.debug.DebugError):subject.active_snapshot(changed,selected)
        reply['voices'][20]['owner_tag']='0x0000000000000000'
        with self.assertRaises(subject.audio.AudioQualificationError):subject.active_live(reply,selected)

    def test_wrong_bank_start_pitch_or_adsr_is_refused(self):
        selected,saved,reply=fixture()
        changed=copy.deepcopy(saved);changed['private_spu']['voices'][20]['sample_bank']=30
        with self.assertRaises(subject.debug.DebugError):subject.active_snapshot(changed,selected)
        for index in (2,3,4,5):
            changed=copy.deepcopy(saved);regs=list(struct.unpack('<8H',bytes.fromhex(changed['private_spu']['registers_hex'][20])))
            regs[index]^=1;changed['private_spu']['registers_hex'][20]=struct.pack('<8H',*regs).hex()
            with self.subTest(register=index),self.assertRaises(subject.debug.DebugError):
                subject.active_snapshot(changed,selected)
        for key,value in dict(sample_bank=30,start='0x08008',pitch='0x1001',adsr_lo='0x80fe',adsr_hi='0x1fc1',env='0x0000').items():
            changed=copy.deepcopy(reply);changed['voices'][20][key]=value
            with self.subTest(field=key):self.assertFalse(subject.active_live(changed,selected)[0])


if __name__=='__main__':unittest.main()
