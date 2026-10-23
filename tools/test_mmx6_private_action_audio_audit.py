"""Source differential audio metadata/STOP fixtures; no game or audio device."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest

import audit_mmx6_private_action_audio as subject

ROOT=Path(__file__).resolve().parents[1]


def original_stop(exe, *, group=1, flags=22):
    """Execute original1750C; record volume/stop CALL ABIs instead of devices.

    Callback results are deliberately nonzero to prove original return values.
    Every unexpected PC/opcode/memory access is rejected. This is an isolated
    source execution test, not runtime playback or driver/DSP qualification.
    """
    memory={};regs=[0]*32;regs[4]=group;regs[5]=5;regs[29]=0x801FF000;regs[31]=0x80000000
    def put(address,data):memory.update((address+i,b)for i,b in enumerate(data))
    put(0x80097778+group*4,struct.pack("<I",0x80100000));put(0x80100000+5*4+3,bytes((flags,)))
    pc=subject.STOP;delayed=None;events=[]
    signed=lambda x:x-0x100000000 if x&0x80000000 else x
    for _ in range(2048):
        if pc==0x80000000:return events,regs[2]
        if pc in (0x8005BC14,0x8005AD40):
            events.append(dict(target=pc,voice=regs[4],left=regs[5] if pc==0x8005BC14 else None,
                               right=regs[6] if pc==0x8005BC14 else None))
            regs[2]=0x12345678;pc=regs[31];continue
        if not subject.STOP<=pc<0x800175F0 or pc&3:raise ValueError("Original STOP escaped bounded code")
        word=exe.word(pc);op=word>>26;rs=(word>>21)&31;rt=(word>>16)&31;rd=(word>>11)&31
        sa=(word>>6)&31;fun=word&63;imm=word&0xFFFF;short=imm-0x10000 if imm&0x8000 else imm;target=None
        if word==0:pass
        elif op==0 and fun==0x21:regs[rd]=regs[rs]+regs[rt]
        elif op==0 and fun==0:regs[rd]=regs[rt]<<sa
        elif op==0 and fun==2:regs[rd]=regs[rt]>>sa
        elif op==0 and fun==8:target=regs[rs]
        elif op==2:target=((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        elif op==3:regs[31]=pc+8;target=((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        elif op in (4,5):
            if (regs[rs]==regs[rt])==(op==4):target=pc+4+short*4
        elif op==1:
            if (signed(regs[rs])>=0) if rt==1 else (signed(regs[rs])<0):target=pc+4+short*4
        elif op==9:regs[rt]=regs[rs]+short
        elif op==11:regs[rt]=int(regs[rs]<(short&0xFFFFFFFF))
        elif op==12:regs[rt]=regs[rs]&imm
        elif op==15:regs[rt]=imm<<16
        elif op in(0x23,0x24):
            address=(regs[rs]+short)&0xFFFFFFFF;size=4 if op==0x23 else 1
            regs[rt]=int.from_bytes(bytes(memory[address+i]for i in range(size)),"little")
        elif op==0x2B:
            address=(regs[rs]+short)&0xFFFFFFFF
            if not 0x801FEFE0<=address<0x801FF000:raise ValueError("Original STOP nonstack mutation")
            put(address,struct.pack("<I",regs[rt]))
        else:raise ValueError(f"Unsupported original STOP instruction{word:08X}")
        if delayed is not None and target is not None:raise ValueError("Branch in delay slot")
        regs=[v&0xFFFFFFFF for v in regs];regs[0]=0
        pc=delayed if delayed is not None else pc+4;delayed=target
    raise ValueError("Original STOP instruction bound exhausted")


class AudioAuditTests(unittest.TestCase):
    def test_voice_range_rejects_empty_or_crosses_native24(self):
        self.assertEqual(subject.voice_range(dict(empty=False,first_voice=20,additional_voices=1)),[20,21])
        for row in (dict(empty=True,first_voice=0,additional_voices=0),
                dict(empty=False,first_voice=23,additional_voices=1),
                dict(empty=False,first_voice=31,additional_voices=0),
                dict(empty=False,first_voice=True,additional_voices=0),
                dict(empty=False,first_voice=22,additional_voices="0"),
                dict(empty=False,first_voice=0,additional_voices=4)):
            with self.assertRaises(ValueError):subject.voice_range(row)

    def test_pinned_audit_retains_overlay_and_nonjump_scope(self):
        r=json.loads((ROOT/"docs/COOP_PRIVATE_ACTION_AUDIO_AUDIT.json").read_bytes())
        self.assertEqual(r["callers"]["zero_overlay_counts"],{"80016C48":38,"8001750C":0,"8003CFE0":19})
        self.assertFalse(r["native_stop_contract"]["transitive_stop_absence_proven"])
        self.assertFalse(r["zero_assets"]["executable_code"])
        self.assertFalse(r["native_runs"])
        self.assertEqual(r["retained_failure"]["mode_status"],dict(local="failed",netplay="unverified"))
        self.assertNotEqual(r["r4"],"passed");self.assertNotEqual(r["r12"],"passed")
        rows={(v["group"],v["record"]):v for v in r["zero_records"]}
        self.assertEqual(rows[3,17]["effective_bank_group"],1)
        self.assertEqual(rows[3,17]["voice_range"],[3])
        self.assertEqual(rows[3,17]["tones"],rows[1,12]["tones"])
        self.assertEqual(rows[1,13]["voice_range"],[20,21])
        self.assertEqual([v["tone"]for v in rows[1,13]["tones"]],[14,15])
        self.assertEqual(rows[1,5]["voice_range"],[22]);self.assertEqual(rows[1,7]["voice_range"],[23])

    @unittest.skipUnless(os.environ.get("MMX6_AUDIO_EXE") and os.environ.get("MMX6_AUDIO_DISC"),"Supply original EXE/disc")
    def test_original_stop_executes_volume_then_keyoff_without_assumed_return(self):
        exe,_,_=subject.original_sources(Path(os.environ["MMX6_AUDIO_EXE"]),Path(os.environ["MMX6_AUDIO_DISC"]))
        for first,count in ((22,1),(23,1),(20,2),(2,3),(2,4)):
            events,result=original_stop(exe,flags=first|((count-1)<<5))
            self.assertEqual(result,0xFF000000)
            self.assertEqual([v["voice"]for v in events],[v for v in range(first,first+count)for _ in range(2)])
            self.assertEqual([v["target"]for v in events],[0x8005BC14,0x8005AD40]*count)
            self.assertTrue(all(v["left"]==v["right"]==0 for v in events if v["target"]==0x8005BC14))
        events,result=original_stop(exe,group=255)
        self.assertEqual(result,0);self.assertEqual(len(events),48)
        self.assertEqual([v["voice"]for v in events],[v for v in range(24)for _ in range(2)])

    @unittest.skipUnless(os.environ.get("MMX6_AUDIO_EXE") and os.environ.get("MMX6_AUDIO_DISC"),"Supply original EXE/disc")
    def test_malformed_body_or_cross_bank_handle_never_becomes_a_tone(self):
        _,_,banks=subject.original_sources(Path(os.environ["MMX6_AUDIO_EXE"]),Path(os.environ["MMX6_AUDIO_DISC"]))
        bad=copy.deepcopy(banks);bad[1]["samples"]=bad[1]["samples"][:-16]
        with self.assertRaisesRegex(ValueError,"sample-size"):subject.resolve_records(bad)
        bad=copy.deepcopy(banks);bad[3]["metadata"]["sound_records"][17]["vab_handle"]=2
        with self.assertRaisesRegex(ValueError,"unretained"):subject.resolve_records(bad)
        rollover=copy.deepcopy(banks);rollover[1]["metadata"]["sound_records"][13]["tone_start"]=15
        resolved=next(r for r in subject.resolve_records(rollover)if(r["group"],r["record"])==(1,13))
        self.assertEqual([(t["program"],t["tone"])for t in resolved["tones"]],[(0,15),(1,0)])
        bad=copy.deepcopy(banks);bad[1]["metadata"]["sound_records"][13]["program"]=127
        with self.assertRaisesRegex(ValueError,"program/tone"):subject.resolve_records(bad)

    @unittest.skipUnless(os.environ.get("MMX6_AUDIO_EXE") and os.environ.get("MMX6_AUDIO_DISC") and os.environ.get("MMX6_AUDIO_X4_REPO"),"Supply original sources/local frozen X4 repository")
    def test_original_sources_and_frozen_x4_reproduce_audit(self):
        actual=subject.audit(Path(os.environ["MMX6_AUDIO_EXE"]),Path(os.environ["MMX6_AUDIO_DISC"]),Path(os.environ["MMX6_AUDIO_X4_REPO"]))
        self.assertEqual(actual,json.loads((ROOT/"docs/COOP_PRIVATE_ACTION_AUDIO_AUDIT.json").read_bytes()))
        self.assertEqual(actual["frozen_x4"]["blob"],subject.X4_BLOB)
        self.assertEqual(len(actual["zero_records"]),45)


if __name__=="__main__":unittest.main()
