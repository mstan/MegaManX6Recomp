"""Private-SPU protocol/source/reducer fixtures; never a native title/audio pass."""
import copy
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import mmx6_coop_jump_audio as audio
from test_mmx6_coop_jump_audio import CONTRACT, voices, wire, reply


def event(seq,frame,voice,bank,kind="KEYON",address=0x1000):
    raw=wire(seq,frame,kind,voice);raw.update(sample_bank=bank,addr=f"0x{address:05X}")
    return raw


def private_voices():
    rows=voices()["voices"]
    for i,row in enumerate(rows):row.update(v=i+24,active=0,sample_bank=0,pending_bank=0,mode=0)
    return dict(ok=True,schema=1,active_mask="0x000000",voices=rows)


def hardware():
    value=voices()
    for row in value["voices"]:row.update(sample_bank=0,pending_bank=0,mode=0)
    return value


def bank_reply(bank,address,count,data,*,resident=True,size=None):
    return dict(ok=True,bank=bank,addr=address,len=len(data),resident=resident,
                size=52096 if size is None else size,hex=data.hex())


def tone(character,record):
    return next(t for t in CONTRACT["tones"]if (t["character"],t["group"],t["record"])==(character,3,record))


class ProtocolTests(unittest.TestCase):
    def test_event_time_bank_is_required_only_in_explicit_new_mode(self):
        legacy=audio.parse_events(reply(wire()))[1][0]
        self.assertNotIn("sample_bank",legacy)
        with self.assertRaises(audio.AudioQualificationError):audio.parse_events(reply(wire()),require_banks=True)
        row=audio.parse_events(reply(event(0,1,44,31)),require_banks=True)[1][0]
        self.assertEqual((row["v"],row["sample_bank"]),(44,31))
        for value in (32,True,-1):
            with self.assertRaises(audio.AudioQualificationError):audio.parse_events(reply(event(0,1,44,value)),require_banks=True)
        with self.assertRaises(audio.AudioQualificationError):audio.parse_events(reply(event(0,1,255,31,"IRQ")),require_banks=True)

    def test_hardware_fields_do_not_synthesize_legacy_bank_knowledge(self):
        self.assertNotIn("sample_bank",audio.parse_voices(voices())["voices"][20])
        with self.assertRaises(audio.AudioQualificationError):audio.parse_voices(voices(),require_banks=True)
        self.assertEqual(audio.parse_voices(hardware(),require_banks=True)["voices"][20]["sample_bank"],0)

    def test_private_rows_have_exact_indices_pending_banks_modes_and_mask(self):
        value=private_voices();value["voices"][20].update(active=1,sample_bank=31,pending_bank=30,mode=2)
        value["active_mask"]="0x100000"
        result=audio.parse_private_voices(value)
        self.assertEqual(result["voices"][20]["v"],44)
        self.assertEqual((result["voices"][20]["sample_bank"],result["voices"][20]["pending_bank"]),(31,30))
        for mutate in (lambda v:v.update(schema=True),lambda v:v.update(active_mask="0x000000"),
                       lambda v:v["voices"].pop(),lambda v:v["voices"][0].update(v=0),
                       lambda v:v["voices"][1].update(v=24),lambda v:v["voices"][20].update(sample_bank=32),
                       lambda v:v["voices"][20].update(pending_bank=True),lambda v:v["voices"][20].update(mode=4)):
            changed=copy.deepcopy(value);mutate(changed)
            with self.assertRaises(audio.AudioQualificationError):audio.parse_private_voices(changed)

    def test_bank_info_and_exact_read_envelopes(self):
        value=bank_reply(31,12368,4,b"abcd")
        self.assertEqual(audio.parse_bank_reply(value,31,12368,4,expected_size=52096)["data"],b"abcd")
        info=bank_reply(31,0,0,b"")
        self.assertEqual(audio.parse_bank_reply(info,31,0,0,expected_size=52096)["size"],52096)
        for change in (dict(ok=1),dict(bank=30),dict(bank=True),dict(addr=12369),dict(addr=True),
                       dict(len=3),dict(len=True),dict(resident=1),dict(resident=False,size=0,len=0,hex=""),
                       dict(size=52095),dict(hex="61 626364"),dict(hex="616263")):
            with self.subTest(change=change),self.assertRaises(audio.AudioQualificationError):
                audio.parse_bank_reply(dict(value,**change),31,12368,4,expected_size=52096)
        for count in (-1,True,4097):
            with self.assertRaises(audio.AudioQualificationError):audio.parse_bank_reply(value,31,12368,count)
        with self.assertRaises(audio.AudioQualificationError):audio.parse_bank_reply(None,31,0,0)
        with self.assertRaises(audio.AudioQualificationError):audio.parse_bank_reply(value,31,52094,4)


class IdentityTests(unittest.TestCase):
    def observer(self,request):return audio.AudioObserver(None,request,CONTRACT,private_banks=audio.private_bank_contract(CONTRACT))

    def test_named_event_bank_not_voice_number_selects_probe(self):
        t=tone("Zero",7);calls=[]
        def request(command,**fields):
            calls.append((command,fields))
            return bank_reply(fields["bank"],fields["addr"],fields["len"],bytes(fields["len"]))
        observer=self.observer(request)
        found=observer.identify(dict(v=44,sample_bank=31,addr=t["offset"]),{})
        self.assertEqual(calls,[("spu_sample_bank",dict(bank=31,addr=t["offset"],len=t["bytes"]))])
        self.assertEqual(found["tone"]["character"],"Zero")
        self.assertFalse(found["sample_matches"]) # A private channel/name alone is insufficient.
        self.assertEqual(found["observed_sha256"],hashlib.sha256(bytes(t["bytes"])).hexdigest())
        self.assertNotIn("hex",found)

    def test_wrong_absent_stale_short_and_unmapped_banks_do_not_fall_back(self):
        t=tone("Zero",7)
        calls=[]
        def forbidden(*args,**kwargs):calls.append(args);raise AssertionError("No fallback read")
        observer=self.observer(forbidden)
        self.assertFalse(observer.identify(dict(v=44,sample_bank=30,addr=t["offset"]),{})["sample_matches"])
        with self.assertRaises(audio.AudioQualificationError):observer.identify(dict(v=44,sample_bank=29,addr=t["offset"]),{})
        self.assertEqual(calls,[])
        for response in (bank_reply(31,t["offset"],0,b"",resident=False,size=0),
                         bank_reply(31,t["offset"],1,b"\0"),
                         bank_reply(31,t["offset"],t["bytes"],bytes(t["bytes"]),size=123408)):
            observer=self.observer(lambda *a,**k:response)
            with self.assertRaises(audio.AudioQualificationError):observer.identify(dict(v=44,sample_bank=31,addr=t["offset"]),{})

    def test_unreviewed_source_bank_metadata_refused(self):
        value=audio.private_bank_contract(CONTRACT);value["banks"][1]["bank"]=30
        with self.assertRaises(ValueError):audio.AudioObserver(None,None,CONTRACT,private_banks=value)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.x,self.z=tone("X",6),tone("Zero",7)
        first=event(0,100,20,0,address=338464);second=event(1,105,44,31,address=self.z["offset"])
        self.events=audio.parse_events(reply(first,second,event(2,115,20,0,"END_STOP",338480),
                                             event(3,125,44,31,"END_STOP",self.z["offset"]+16)),require_banks=True)[1]
        self.first,self.second=self.events[:2]
        self.identities={0:dict(tone=self.x,sample_matches=True,sample_bank=0),
                         1:dict(tone=self.z,sample_matches=True,sample_bank=31)}

    def compare(self):return audio.compare_private_overlap(self.events,self.first,self.second,self.identities,0,CONTRACT)

    def test_exact_hardware_x_and_private_zero_overlap_without_replacement(self):
        result=self.compare()
        self.assertTrue(all(result["checks"].values()),result["checks"])
        self.assertFalse(result["collision_observed"])
        self.assertEqual([a["lifetime"]["engine_frames"]for a in result["actors"]],[15,20])
        with self.assertRaises(ValueError):audio.compare_overlap(self.events,self.first,self.second,self.identities,0)

    def test_identity_numeric_route_and_lifetime_are_independent(self):
        self.identities[1]["tone"]=tone("X",7)
        result=self.compare()
        self.assertFalse(result["checks"]["p2_source_sample"])
        self.assertTrue(result["checks"]["p2_pitch_adsr_numeric"])
        self.assertTrue(result["checks"]["p2_natural_end"])
        self.identities[1]["tone"]=self.z;self.second["sample_bank"]=30
        self.events[-1]["sample_bank"]=30
        self.assertFalse(self.compare()["checks"]["p2_voice_route"])
        self.identities[1]["tone"]=None
        self.assertTrue(self.compare()["checks"]["p2_pitch_adsr_numeric"])
        self.assertFalse(self.compare()["checks"]["p2_source_sample"])
        self.second["pitch"]^=1
        self.assertFalse(self.compare()["checks"]["p2_pitch_adsr_numeric"])

    def test_private_replacement_and_wrong_terminal_bank_are_not_natural_end(self):
        replacement=dict(self.events[3],kind="KEYON",sample_bank=30)
        result=audio.lifetime([*self.events[:3],replacement],self.second)
        self.assertEqual(result["disposition"],"replaced")
        with self.assertRaises(audio.AudioQualificationError):audio.lifetime([self.second,dict(self.events[3],sample_bank=30)],self.second)
        self.assertEqual(audio.lifetime([self.second],self.second)["disposition"],"unobserved")

    def test_stale_dsp_binding_pending_bank_or_later_keyon_cannot_qualify_old_note(self):
        hw=audio.parse_voices(hardware(),require_banks=True);pv=audio.parse_private_voices(private_voices())
        for row,e in ((hw["voices"][20],self.first),(pv["voices"][20],self.second)):
            row.update(start=e["addr"],sample_bank=e["sample_bank"],pending_bank=0)
        actors=self.compare()["actors"]
        checks,_=audio.final_dsp_checks(self.events,actors,hw,pv)
        self.assertTrue(all(checks.values()),checks)
        for field,value in (("sample_bank",30),("pending_bank",30),("pending_bank",31),("mode",1),("pitch",1000),("env",1)):
            old=pv["voices"][20][field];pv["voices"][20][field]=value
            checks,_=audio.final_dsp_checks(self.events,actors,hw,pv)
            self.assertFalse(all(checks.values()),(field,checks));pv["voices"][20][field]=old
        later=dict(self.events[-1],seq=4,frame=126,kind="KEYON")
        checks,_=audio.final_dsp_checks([*self.events,later],actors,hw,pv)
        self.assertFalse(checks["p2_final_dsp_attribution"])
        self.assertTrue(self.compare()["checks"]["p2_natural_end"]) # Original event lifetime is separate.


class ContextTests(unittest.TestCase):
    def test_complete_explicit_private_path_retains_scope_and_original_jump_predicate(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"]) as directory:
            candidate=Path(directory);image=b"synthetic pure runner identity"
            digest=hashlib.sha256(image).hexdigest();(candidate/"mmx6-runtime.exe").write_bytes(image)
            (candidate/"preparation.json").write_text(__import__("json").dumps(dict(exe_sha256=digest)))
            metadata=audio.private_bank_contract(CONTRACT);state=dict(air=set(),observer=None);controls=[]
            x,z=tone("X",6),tone("Zero",7)
            selected=audio.parse_events(reply(event(0,100,20,0,address=338464),event(1,105,44,31,address=z["offset"]),
                event(2,115,20,0,"END_STOP",338480),event(3,125,44,31,"END_STOP",z["offset"]+16)),require_banks=True)[1]
            class Observer:
                def __init__(self,*args,**kwargs):
                    self.events=[];self.pending=[];self.source=kwargs["private_banks"];state["observer"]=self
                def poll(self):
                    players=[dict(character=c,form=f,state=1,action=6 if c in state["air"] else 2,hp=32,
                        speech_gate=0,airborne=1 if c in state["air"] else 0,ground=c not in state["air"],
                        y=90 if c in state["air"] else 100,vy=1,x=100)for c,f in ((0,1),(1,5))]
                    rows=self.pending;self.pending=[];self.events.extend(rows)
                    return dict(observation=dict(ready=1,enrolled=1,failed=0,mailbox=0,native_mode=10,
                        native_phase=0,scene_owner=0,pause_owner=0,lifecycle=(0,0)),players=players,
                        event_total=len(self.events),new_events=rows)
                def driver(self):return dict(release_adjust=0,vab_status=[1]*16)
                def fingerprint_banks(self):return [dict(bank=b["bank"],sha256=b["sha256"])for b in self.source["banks"]]
                def identify(self,e,driver):return dict(tone=x if e["v"]==20 else z,sample_matches=True,sample_bank=e["sample_bank"])
            hw,pv=hardware(),private_voices()
            hw["voices"][20].update(start="0x52A20") #338464, not the END_STOP repeat address.
            pv["voices"][20].update(start=f"0x{z['offset']:05X}",sample_bank=31,pending_bank=0)
            def request(command,**fields):
                self.assertIn(command,("spu_voices","spu_private_voices"))
                return hw if command=="spu_voices" else pv
            def hold(seat,bits,frames,label):
                controls.append((seat,bits,frames,label))
                if bits:
                    state["air"].add(seat);state["observer"].pending.append(selected[seat])
                    start=[dict(active=1,state=1,character=c,action=2,hp=32,y_raw=100)for c in (0,1)]
                    end=copy.deepcopy(start);end[seat].update(action=6,y_raw=90)
                    return dict(seat=seat,pressed=bits,actual_native_ticks=1,actual_publications=1,
                                start=dict(players=start),end=dict(players=end))
            def advance(*args):
                state["air"].clear();state["observer"].pending.extend(selected[2:])
            report={}
            ctx=dict(mode="local",input_path="published_host",clients=[None],request=request,hold=hold,
                native_advance=advance,report=report,candidate=candidate,expected_sha256=digest,private_banks=metadata)
            with patch.object(audio,"AudioObserver",Observer):result=audio.jump_overlap_smoke(ctx,CONTRACT,max_attempts=1)
            self.assertEqual(result["status"],"observations_complete",result["checks"])
            self.assertEqual(result["diagnostics_scope"],"private_banks_v1")
            self.assertEqual([a["keyon"]["v"]for a in result["actors"]],[20,44])
            self.assertTrue(all(result["checks"].values()))
            self.assertEqual([(c[0],c[1])for c in controls[-2:]],[(0,0),(1,0)])
            self.assertEqual(report["jump_audio"],[result])


@unittest.skipUnless(os.getenv("MMX6_AUDIO_DISC"),"Supply original read-only raw BIN for exact-byte probes")
class OriginalBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata=audio.build_private_bank_contract(Path(os.environ["MMX6_AUDIO_DISC"]),CONTRACT)
        disc=audio.Disc(os.environ["MMX6_AUDIO_DISC"]);cls.banks={}
        try:
            lba,total=disc.files()["ROCK_X6.DAT"];table=disc.user(lba)
            for member in (85,87):
                sector,size=struct.unpack_from("<II",table,member*8)
                payload=b"".join(disc.user(lba+sector+i)for i in range((size+2047)//2048))[:size]
                assert hashlib.sha256(payload).hexdigest()==audio.PLAYER_MEMBERS[member][1]
                assets=audio.subassets(payload)
                if member==85:cls.banks={30:assets[12][1],31:assets[14][1]}
                else:cls.xbody=assets[14][1]
        finally:disc.f.close()

    def test_actual_named_bank_fingerprints_and_zero_sample_bytes(self):
        calls=[]
        def request(command,**fields):
            calls.append((command,fields))
            body=self.banks[fields["bank"]];at,count=fields["addr"],fields["len"]
            return bank_reply(fields["bank"],at,count,body[at:at+count],size=len(body))
        observer=audio.AudioObserver(None,request,CONTRACT,private_banks=self.metadata)
        fingerprints=observer.fingerprint_banks()
        self.assertEqual([f["sha256"]for f in fingerprints],[r["sha256"]for r in self.metadata["banks"]])
        zero=tone("Zero",7)
        found=observer.identify(dict(v=44,sample_bank=31,addr=zero["offset"]),{})
        self.assertTrue(found["sample_matches"])
        self.assertEqual(found["observed_sha256"],zero["sample_sha256"])
        self.assertEqual({command for command,_ in calls},{"spu_sample_bank"})
        self.assertTrue(all(f["len"]<=4096 for _,f in calls))
        self.assertEqual(len(calls),49) #44body +4metadata +1exactselectedsample.

    def test_exact_hardware_x_probe_and_mutated_immutable_bank_rejected(self):
        x=tone("X",6);start=0x4F4B0+x["offset"];bases=[0]*16;bases[3]=0x4F4B0
        def request(command,**fields):
            if fields["bank"]==0:
                at=fields["addr"]-bases[3];data=self.xbody[at:at+fields["len"]];size=0x80000
            else:
                body=bytearray(self.banks[fields["bank"]]);body[0]^=1
                data=body[fields["addr"]:fields["addr"]+fields["len"]];size=len(body)
            return bank_reply(fields["bank"],fields["addr"],fields["len"],data,size=size)
        observer=audio.AudioObserver(None,request,CONTRACT,private_banks=self.metadata)
        found=observer.identify(dict(v=20,sample_bank=0,addr=start),dict(bases=bases))
        self.assertTrue(found["sample_matches"])
        self.assertEqual(found["tone"]["character"],"X")
        with self.assertRaisesRegex(audio.AudioQualificationError,"does not match"):observer.fingerprint_banks()


class NativeAudioHookIntegrationTests(unittest.TestCase):
    def test_development_and_release_emit_each_required_driver_hook(self):
        root=Path(__file__).resolve().parents[1]
        required={0x80016C48,0x8005A9D4,0x80055B14,0x8001750C}
        for name in ("game.toml","packaging/release/game.toml"):
            with self.subTest(config=name):
                config=tomllib.loads((root/name).read_text(encoding="utf-8"))
                entries=[int(value,16) for value in config["recompiler"]["mod_function_entry_funcs"]]
                self.assertTrue(required.issubset(entries))
                for address in required:self.assertEqual(entries.count(address),1)


if __name__=="__main__":unittest.main()
