"""Bounded original-input jump audio observations; never launches or fixes audio.

The owning runner supplies an already validated private candidate, listener-
checked read RPCs and published host controls. No SIO override, RAM write,
event reset, guest call, device setting or audio-output command is used here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import time

import coop_debug as debug
from audit_mmx6_coop_audio import PLAYER_MEMBERS, bank_metadata, subassets
from inventory_mmx6_coop_content import EXE_SHA256
from mmx6_seamless_catalog import Disc
from prepare_mmx6_coop_playtest import sha256

SDK_COMMIT = "6212e68066a6977dc587e8fca71f27dac9b002fc"
CONTRACT_SHA256 = "ce11910561b56c85450c0c14d66333b0bddd50156235c76ff12bbeb4c902124a"
JUMP_RECORDS = {"X": (2, 3, 6), "Zero": (2, 4, 7)}
CROSS = 0x4000
PRIVATE_DIAGNOSTICS_SDK = "bfbfb920bfa509f6a31ec2e6b28411a01797427f"
PRIVATE_BANK_BODIES = ((30,1,12,0x020101,123408,"425516420dc6ff1d973edae265717a6ca237454631cdb4b7c829c96f6f7057a8"),
                       (31,3,14,0x020303,52096,"203c8e0e58ea4e55797445b7af76e7563528c21536ae8fd57e38566a89b38bdd"))


class AudioQualificationError(debug.DebugError):
    pass


def _uint(value, bits, label):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise AudioQualificationError(f"Invalid {label}")
    return value


def _hex(value, digits, label):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{"+str(digits)+"}", value):
        raise AudioQualificationError(f"Malformed {label}")
    return int(value, 16)


def parse_events(reply: dict, after: int | None = None, *, require_banks=False) -> tuple[int, list[dict]]:
    """SDK event seq is zero-based; total is the next sequence, never a frame.

    Reject a reset, missing requested suffix, reordered/duplicate rows, or a
    truncated response. Never reset or consume the runtime's event ring.
    """
    if not isinstance(reply,dict) or reply.get("ok") is not True:
        raise AudioQualificationError("SPU events unavailable")
    total = _uint(reply.get("total"), 64, "event total")
    count = _uint(reply.get("count"), 13, "event count")
    rows = reply.get("events")
    if not isinstance(rows, list) or not 0 <= count <= min(total, 4096) or len(rows) != count:
        raise AudioQualificationError("Truncated SPU event array")
    if total and not count:
        raise AudioQualificationError("Missing SPU event tail")
    if after is not None and (type(after) is not int or not total-count <= after <= total):
        raise AudioQualificationError("SPU event reset or requested suffix lost")
    result = []
    previous_frame = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or _uint(row.get("seq"), 64, "event sequence") != total-count+index:
            raise AudioQualificationError("Noncontiguous SPU events")
        kind, voice = row.get("kind"), _uint(row.get("v"), 8, "event voice")
        if kind not in ("KEYON", "KEYOFF", "END_STOP", "END_LOOP", "IRQ") or \
                (voice != 255 if kind == "IRQ" else voice >= 48):
            raise AudioQualificationError("Unknown SPU event kind/voice")
        parsed = dict(seq=row["seq"], frame=_uint(row.get("frame"), 32, "engine frame"),
                      kind=kind, v=voice, addr=_hex(row.get("addr"), 5, "SPU byte address"))
        if parsed["addr"] >= 0x80000:
            raise AudioQualificationError("SPU address escaped RAM")
        if previous_frame is not None and ((parsed["frame"]-previous_frame) & 0xFFFFFFFF) >= 0x80000000:
            raise AudioQualificationError("SPU engine frame regressed")
        previous_frame=parsed["frame"]
        for key in ("pitch", "adsr_lo", "adsr_hi", "vol_l", "vol_r"):
            parsed[key] = _hex(row.get(key), 4, key)
        if require_banks or "sample_bank" in row:
            parsed["sample_bank"] = _uint(row.get("sample_bank"),5,"event-time sample bank")
            if kind == "IRQ" and parsed["sample_bank"] != 0:
                raise AudioQualificationError("IRQ cannot name a sample bank")
        if after is None or parsed["seq"] >= after:
            result.append(parsed)
    return total, result


def _voice_rows(rows,base,require_banks):
    if not isinstance(rows,list) or len(rows)!=24:
        raise AudioQualificationError("Missing exact SPU voice set")
    voices=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or type(row.get("v")) is not int or row["v"]!=base+index:
            raise AudioQualificationError("Duplicate/missing voice index")
        voice=dict(v=base+index,active=_uint(row.get("active"),1,"active"))
        for key in ("vol_l","vol_r","pitch","adsr_lo","adsr_hi","phase","env"):
            voice[key]=_hex(row.get(key),4,key)
        for key in ("start","loop","cur_addr","repeat_addr"):
            voice[key]=_hex(row.get(key),5,key)
            if voice[key]>=0x80000:raise AudioQualificationError("Voice address escaped SPU RAM")
        voice["flags"]=_hex(row.get("flags"),2,"flags")
        voice["sample_idx"]=_uint(row.get("sample_idx"),5,"sample index")
        voice["env_phase"]=_uint(row.get("env_phase"),2,"envelope phase")
        if voice["sample_idx"]>28 or voice["env"]>0x7FFF:
            raise AudioQualificationError("Invalid live envelope/sample index")
        for key in ("vol_cur_l","vol_cur_r"):
            if type(row.get(key)) is not int or not -32768<=row[key]<=32767:
                raise AudioQualificationError("Invalid live voice volume")
            voice[key]=row[key]
        if require_banks or any(key in row for key in ("sample_bank","pending_bank","mode")):
            voice.update(sample_bank=_uint(row.get("sample_bank"),5,"decoder sample bank"),
                pending_bank=_uint(row.get("pending_bank"),5,"pending sample bank"),
                mode=_uint(row.get("mode"),2,"voice mode"))
        voices.append(voice)
    return voices


def parse_voices(reply: dict, *, require_banks=False) -> dict:
    if not isinstance(reply,dict) or reply.get("ok") is not True:
        raise AudioQualificationError("Missing hardware SPU voice snapshot")
    result={key:_hex(reply.get(key),4,key) for key in ("ctrl","main_l","main_r")}
    result.update({key:_hex(reply.get(key),6,key) for key in
                   ("kon","koff","pmon","non","eon","endx","active_mask")})
    voices=_voice_rows(reply.get("voices"),0,require_banks)
    result["voices"]=voices
    return result


def parse_private_voices(reply: dict) -> dict:
    if not isinstance(reply,dict) or reply.get("ok") is not True or type(reply.get("schema")) is not int or reply["schema"]!=1:
        raise AudioQualificationError("Missing schema1 private SPU snapshot")
    voices=_voice_rows(reply.get("voices"),24,True)
    mask=_hex(reply.get("active_mask"),6,"private active mask")
    if mask != sum(v["active"]<<i for i,v in enumerate(voices)):
        raise AudioQualificationError("Private active mask/rows disagree")
    return dict(schema=1,active_mask=mask,voices=voices)


def parse_bank_reply(reply,bank,address,count,*,expected_size=None):
    """Exact read-only envelope; clipped/absent reads never become sample proof."""
    _uint(bank,5,"requested bank");_uint(address,19,"requested bank offset")
    if type(count) is not int or not 0<=count<=4096:
        raise AudioQualificationError("Bank probe length exceeds4096")
    if not isinstance(reply,dict) or reply.get("ok") is not True or type(reply.get("bank")) is not int or reply["bank"]!=bank or \
            type(reply.get("addr")) is not int or reply["addr"]!=address or type(reply.get("resident")) is not bool:
        raise AudioQualificationError("Mismatched immutable bank envelope")
    size=_uint(reply.get("size"),32,"bank size")
    if size>0x80000 or reply["resident"] != bool(size) or (bank==0 and size!=0x80000):
        raise AudioQualificationError("Unsupported bank residency/size")
    got=_uint(reply.get("len"),13,"bank read length")
    if got!=count or address+count>size or not reply["resident"] or \
            not isinstance(reply.get("hex"),str) or not re.fullmatch(r"[0-9a-fA-F]{%d}"%(count*2),reply["hex"]) or \
            (expected_size is not None and size!=expected_size):
        raise AudioQualificationError("Absent, clipped, stale or malformed immutable bank read")
    return dict(bank=bank,size=size,addr=address,len=count,data=bytes.fromhex(reply["hex"]))


def native_pitch(note: int, shift: int, center: int, tuning: int, word) -> int:
    """Original8005DFA8 arithmetic for the bounded nonnegative player tones.

    word(addr) reads original EXE halfwords; tables never come from host math.
    This is expected calculation metadata, not native execution evidence.
    """
    if any(type(v) is not int or not 0 <= v <= 127 for v in (note, shift, center, tuning)):
        raise ValueError("Unsupported native pitch input")
    carry, fraction = divmod(shift+tuning, 128)
    octave, semitone = divmod(note+carry-center, 12)
    power = octave-2
    product = word(0x8007B674+2*semitone)*word(0x8007B68C+2*fraction)
    signed = product if product < 0x80000000 else product-0x100000000
    value = signed >> 16
    if power >= 0:
        return 0x3FFF
    if not 1 <= -power <= 31:
        raise ValueError("Native pitch shift outside bounded player case")
    return (((value+(1 << (-power-1))) & 0xFFFFFFFF) >> -power) & 0xFFFF


def build_contract(exe: Path, disc_path: Path) -> dict:
    """Read two bounded original DAT members; return metadata, no sample bytes."""
    executable = Path(exe).read_bytes()
    if hashlib.sha256(executable).hexdigest() != EXE_SHA256:
        raise ValueError("Require original SLUS01395 v1.1 EXE")
    base = struct.unpack_from("<I", executable, 24)[0]
    def word(address):
        return struct.unpack_from("<H", executable, 2048+address-base)[0]
    if executable[2048+0x80073CE4-base:2048+0x80073CEC-base] != bytes((2,3,6,6,2,4,7,7)):
        raise ValueError("Native jump selection table changed")
    contract = dict(schema=1, kind="source_only_jump_audio_contract", exe_sha256=EXE_SHA256,
                    sdk_commit=SDK_COMMIT, members={}, tones=[], native_windows=[],
                    local="unverified", netplay="unverified")
    for name,start,end in (("ground_jump",0x8003AF1C,0x8003AFF4),
            ("jump_animation_sound",0x800356C4,0x800356F4),
            ("voice_wrapper",0x8003CFE0,0x8003D014),
            ("hurt_sound_calls",0x8003963C,0x80039694),
            ("tone_metadata",0x8005A794,0x8005A9CC),
            ("sound_keyon_arguments",0x80016E70,0x80016F80),
            ("native_pitch",0x8005DF40,0x8005E0C8),
            ("voice_setup",0x8005BCA4,0x8005BE6C),
            ("sample_table_sizes",0x8006044C,0x800605B0)):
        span=executable[2048+start-base:2048+end-base]
        contract["native_windows"].append(dict(name=name,start=f"{start:08X}",
            end_exclusive=f"{end:08X}",sha256=hashlib.sha256(span).hexdigest()))
    disc = Disc(str(disc_path))
    try:
        lba, total = disc.files()["ROCK_X6.DAT"]
        table = disc.user(lba)
        for member, character in ((87, "X"), (85, "Zero")):
            sector, size = struct.unpack_from("<II", table, member*8)
            if not 2048 <= size <= 2_000_000 or sector < 1 or sector*2048+size > total:
                raise ValueError("Original player DAT extent escaped archive")
            payload = b"".join(disc.user(lba+sector+i) for i in range((size+2047)//2048))[:size]
            digest = hashlib.sha256(payload).hexdigest()
            if digest != PLAYER_MEMBERS[member][1]:
                raise ValueError("Original player DAT identity changed")
            contract["members"][character] = dict(member=member, sha256=digest)
            assets = subassets(payload)
            for group, hi, bi, records in ((1,11,12,(1,)), (3,13,14,(0,1,2,3,4,6,7,8))):
                header, samples = assets[hi][1], assets[bi][1]
                bank = bank_metadata(header, samples, group)
                pre = bank["preheader_bytes"]
                lengths = struct.unpack_from("<256H", header, len(header)-512)
                if lengths[0] or sum(lengths[:bank["sample_count"]+1])*8 != len(samples):
                    raise ValueError("Original native sample-size table differs")
                for record in records:
                    r = bank["sound_records"][record]
                    if r["empty"] or r["vab_handle"] != group or r["program"] or r["additional_voices"]:
                        raise ValueError("Selected player tone contract changed")
                    offset = pre+32+2048+r["tone_start"]*32
                    tone = header[offset:offset+32]
                    sample = struct.unpack_from("<H", tone, 22)[0]
                    if not 1 <= sample <= bank["sample_count"]:
                        raise ValueError("Original tone sample out of range")
                    begin, count = sum(lengths[:sample])*8, lengths[sample]*8
                    data = samples[begin:begin+count]
                    if not count or count % 16 or len(data) != count or tone[6] != tone[7]:
                        raise ValueError("Unsupported player sample/note range")
                    ends = [i for i in range(count//16) if data[i*16+1] & 1]
                    contract["tones"].append(dict(character=character, member=member, group=group,
                        record=record, vab_handle=r["vab_handle"], program=r["program"],
                        tone=r["tone_start"], voice=r["first_voice"], sample=sample, offset=begin,
                        bytes=count, sample_sha256=hashlib.sha256(data).hexdigest(),
                        header_sha256=bank["header_sha256"], adsr_lo=struct.unpack_from("<H",tone,16)[0],
                        adsr_hi=struct.unpack_from("<H",tone,18)[0], note=tone[6], shift=tone[5],
                        center=tone[4], pitch=native_pitch(tone[6],tone[5],tone[4],tone[5],word),
                        first_end_block=ends[0] if ends else None,
                        first_end_flags=data[ends[0]*16+1] if ends else None))
    finally:
        disc.f.close()
    return contract


def validate_contract(contract: dict) -> str:
    encoded=json.dumps(contract,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
    actual=hashlib.sha256(encoded).hexdigest()
    if actual!=CONTRACT_SHA256:
        raise ValueError("Jump audio source metadata changed; reproduce/review the pinned contract")
    return actual


def private_bank_contract(contract):
    """Companion schema; the frozen historical contract/hash stays unchanged."""
    validate_contract(contract)
    return dict(schema=1,kind="zero_private_sample_banks_v1",source_contract_sha256=CONTRACT_SHA256,
        diagnostics_sdk=PRIVATE_DIAGNOSTICS_SDK,source_member=85,
        source_member_sha256=PLAYER_MEMBERS[85][1],banks=[dict(bank=bank,character="Zero",group=group,
            body_subasset=index,body_type=kind,bytes=size,sha256=digest,offset_origin=0)
            for bank,group,index,kind,size,digest in PRIVATE_BANK_BODIES])


def validate_private_bank_contract(value,contract):
    encode=lambda v:json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
    if encode(value)!=encode(private_bank_contract(contract)):
        raise ValueError("Unreviewed private sample bank source metadata")


def build_private_bank_contract(disc_path,contract):
    expected=private_bank_contract(contract)
    disc=Disc(str(disc_path))
    try:
        lba,total=disc.files()["ROCK_X6.DAT"];table=disc.user(lba)
        sector,size=struct.unpack_from("<II",table,85*8)
        if not 2048<=size<=2_000_000 or sector<1 or sector*2048+size>total:
            raise ValueError("Original private player extent escaped archive")
        payload=b"".join(disc.user(lba+sector+i)for i in range((size+2047)//2048))[:size]
        if hashlib.sha256(payload).hexdigest()!=expected["source_member_sha256"]:
            raise ValueError("Original Zero private bank member differs")
        assets=subassets(payload)
        for record in expected["banks"]:
            kind,body=assets[record["body_subasset"]]
            if (kind,len(body),hashlib.sha256(body).hexdigest())!=(record["body_type"],record["bytes"],record["sha256"]):
                raise ValueError("Original private bank body differs")
    finally:
        disc.f.close()
    return expected


def lifetime(events: list[dict], keyon: dict) -> dict:
    """END_STOP means envelope0/release; SDK active may remain1 and loop silently."""
    for row in events:
        if row["seq"] > keyon["seq"] and row["v"] == keyon["v"] and \
                row["kind"] in ("KEYON", "KEYOFF", "END_STOP", "END_LOOP"):
            if "sample_bank" in keyon and row["kind"]!="KEYON" and row.get("sample_bank")!=keyon["sample_bank"]:
                raise AudioQualificationError("Lifetime terminal changed bank without a recorded replacement")
            delta=(row["frame"]-keyon["frame"]) & 0xFFFFFFFF
            if delta>=0x80000000:raise AudioQualificationError("Lifetime frame regressed")
            return dict(disposition={"KEYON":"replaced", "KEYOFF":"keyed_off",
                "END_STOP":"natural_end", "END_LOOP":"looped"}[row["kind"]],
                terminal=row, engine_frames=delta)
    return dict(disposition="unobserved", terminal=None, engine_frames=None)


def compare_overlap(events: list[dict], first: dict, second: dict,
                    identities: dict[int, dict], first_seat: int) -> dict:
    if type(first_seat) is not int or first_seat not in (0,1) or first["seq"] >= second["seq"] or \
            any(event.get("kind")!="KEYON" or event.get("v")!=20 or event not in events
                for event in (first,second)):
        raise ValueError("Expected ordered first/second jump KEYONs")
    first_life, second_life = lifetime(events,first), lifetime(events,second)
    overlap = first_life["terminal"] is not None and first_life["terminal"]["seq"] >= second["seq"]
    checks = dict(two_keyons=True, vocal_lifetime_overlap=overlap)
    results = []
    for seat, event, life in ((first_seat,first,first_life),(first_seat^1,second,second_life)):
        found = identities.get(event["seq"], {})
        source = found.get("tone")
        character = "X" if seat==0 else "Zero"
        match = bool(source and source["character"]==character and source["group"]==3 and
            source["record"] in JUMP_RECORDS[character] and source["voice"]==event["v"] and
                     found.get("sample_matches") is True)
        checks[f"p{seat+1}_source_sample"] = match
        checks[f"p{seat+1}_pitch_adsr"] = bool(match and all(
            event[k]==source[k] for k in ("pitch","adsr_lo","adsr_hi")))
        checks[f"p{seat+1}_natural_end"] = life["disposition"]=="natural_end"
        results.append(dict(seat=seat,keyon=event,identity=found,lifetime=life))
    return dict(checks=checks, actors=results, collision_observed=first_life["disposition"]=="replaced",
                limits=["No R4/R12 or ledger disposition", "Engine event frames are not native world ticks",
                        "END_STOP is envelope termination, not active0", "No PCM/output, private-bank or paired proof"])


def compare_private_overlap(events,first,second,identities,first_seat,contract):
    """Source identity, route, numeric DSP and lifetime are independent checks."""
    validate_contract(contract)
    if type(first_seat) is not int or first_seat not in (0,1) or first["seq"]>=second["seq"] or \
            any(e.get("kind")!="KEYON" or e not in events or "sample_bank" not in e or
                type(e.get("v")) is not int or not 0<=e["v"]<48 for e in (first,second)):
        raise ValueError("Expected ordered event-time-banked jump KEYONs")
    first_life,second_life=lifetime(events,first),lifetime(events,second)
    checks=dict(two_keyons=True,vocal_lifetime_overlap=first_life["terminal"] is not None and
                first_life["terminal"]["seq"]>=second["seq"])
    actors=[]
    for seat,event,life in ((first_seat,first,first_life),(first_seat^1,second,second_life)):
        found=identities.get(event["seq"],{});tone=found.get("tone")
        character="X" if seat==0 else "Zero"
        checks[f"p{seat+1}_source_sample"]=bool(tone and tone["character"]==character and
            tone["group"]==3 and tone["voice"]==20 and tone["record"] in JUMP_RECORDS[character] and
            found.get("sample_matches") is True and found.get("sample_bank")==event["sample_bank"])
        # The complete eligible original set, even when sample identity is
        # unknown/wrong. Numeric compatibility cannot establish its bank.
        numeric_keys=("pitch","adsr_lo","adsr_hi")
        eligible={tuple(t[k]for k in numeric_keys)for t in contract["tones"]if
                  t["character"]==character and t["group"]==3 and t["record"] in JUMP_RECORDS[character]}
        checks[f"p{seat+1}_pitch_adsr_numeric"]=tuple(event[k]for k in numeric_keys) in eligible
        checks[f"p{seat+1}_voice_route"]=(event["v"],event["sample_bank"])==((20,0)if seat==0 else(44,31))
        checks[f"p{seat+1}_natural_end"]=life["disposition"]=="natural_end"
        actors.append(dict(seat=seat,keyon=event,identity=found,lifetime=life,
            identified_tone_pitch_adsr_numeric=all(event[k]==tone[k]for k in numeric_keys)if tone else None))
    return dict(checks=checks,actors=actors,collision_observed=first_life["disposition"]=="replaced",
        limits=["Private-banks-v1 explicit scope; frozen hardware reports do not inherit it",
                "Event-time bank/source bytes are distinct from later DSP snapshots",
                "Engine event frames are not native world ticks or sample-accurate PCM duration",
                "No R4/R12, netplay, music, other audio families or audible-output pass"])


def final_dsp_checks(events,actors,hardware,private):
    """Do not attribute a reused channel's current envelope to an older note."""
    checks={};details=[]
    for actor in actors:
        event=actor["keyon"];v=event["v"]
        row=(hardware["voices"][v] if v<24 else private["voices"][v-24])
        later=any(e["v"]==v and e["kind"]=="KEYON" and e["seq"]>event["seq"]for e in events)
        consistent=not later and row["sample_bank"]==event["sample_bank"] and row["pending_bank"]==0 and row["start"]==event["addr"]
        prefix=f"p{actor['seat']+1}"
        checks[prefix+"_final_dsp_attribution"]=consistent
        checks[prefix+"_final_envelope_terminated"]=consistent and row["env"]==0 and row["env_phase"]==3
        checks[prefix+"_final_pitch_adsr_numeric"]=consistent and all(row[k]==event[k]for k in ("pitch","adsr_lo","adsr_hi"))
        checks[prefix+"_final_noise_off"]=consistent and not row["mode"]&1
        details.append(dict(seat=actor["seat"],voice=v,event_seq=event["seq"],later_keyon=later,
                            snapshot=row,attribution_consistent=consistent))
    return checks,details


class AudioObserver:
    def __init__(self, client, request, contract, *, private_banks=None):
        validate_contract(contract)
        if private_banks is not None:validate_private_bank_contract(private_banks,contract)
        self.client,self.request,self.contract = client,request,contract
        self.private_banks=private_banks
        self.cursor = None
        self.events = []

    def driver(self):
        # One bounded table read covers headers, release adjustment, VAB status
        # and native logical sample bases. This is separate from body/events.
        raw = self.client.read(0x800E5588,0x1A8)
        records = self.client.read(0x80097738,0x80)
        if len(raw)!=0x1A8 or len(records)!=0x80:
            raise AudioQualificationError("Truncated native audio tables")
        return dict(headers=list(struct.unpack_from("<16I",raw,0x40)),
            release_adjust=struct.unpack_from("<H",raw,0x80)[0],
            vab_status=list(raw[0x108:0x118]), bases=list(struct.unpack_from("<16I",raw,0x168)),
            record_ends=list(struct.unpack_from("<16I",records)),
            record_pointers=list(struct.unpack_from("<16I",records,0x40)))

    def poll(self):
        raw = self.client.read(debug.DIAGNOSTIC_ADDRESS,debug.DIAGNOSTIC_BYTES)
        observation = debug.parse_diagnostic(raw).json()
        total, events = parse_events(self.request("spu_events",count=4096),self.cursor,
                                   require_banks=self.private_banks is not None)
        if self.cursor is not None:
            self.events.extend(events)
        self.cursor = total
        if len(self.events)>16384 or (self.private_banks is None and
                any(row["v"] in range(24,48) or row.get("sample_bank",0)!=0 for row in self.events)):
            raise AudioQualificationError("Private voice/event volume outside hardware-only case")
        bodies = [raw[0x1800:0x1958],raw[0x100:0x258]]
        # Actor+24 is native positive-up speed; the integrator subtracts it
        # from Y. Actor+1C is the prior Y copied by80034E30, not a velocity.
        players = [dict(character=b[2],form=b[0xE7],state=b[4],action=b[5],hp=b[0x5C],
            x=struct.unpack_from("<i",b,8)[0],y=struct.unpack_from("<i",b,12)[0],
            vy=struct.unpack_from("<i",b,0x24)[0],airborne=struct.unpack_from("<b",b,0x67)[0],
            ground=bool(b[0x70]&8),speech_gate=struct.unpack_from("<b",b,0x8D)[0]) for b in bodies]
        return dict(observation=observation,players=players,event_total=total,new_events=events)

    def identify(self,event,driver):
        if self.private_banks is not None:
            return self.identify_banked(event,driver)
        matches=[]
        for tone in self.contract["tones"]:
            if tone["group"]!=3 or tone["record"] not in (2,3,4,6,7):
                continue
            start=driver["bases"][tone["vab_handle"]]+tone["offset"]
            if start!=event["addr"]:
                continue
            count=tone["bytes"]
            if not 0<count<=4096 or start+count>0x80000:
                raise AudioQualificationError("Jump voice sample escaped bounded SPU probe")
            reply=self.request("spu_ram",addr=start,len=count)
            if reply.get("ok") is not True or reply.get("len")!=count or \
                    _hex(reply.get("addr"),5,"SPU probe address")!=start or \
                    not isinstance(reply.get("hex"),str) or not re.fullmatch(r"[0-9A-Fa-f]{"+str(count*2)+"}",reply["hex"]):
                raise AudioQualificationError("Truncated/mismatched SPU sample probe")
            digest=hashlib.sha256(bytes.fromhex(reply["hex"])).hexdigest()
            matches.append(dict(tone=tone,sample_matches=digest==tone["sample_sha256"],observed_sha256=digest))
        if len(matches)>1:
            raise AudioQualificationError("Ambiguous source tone at native sample address")
        return matches[0] if matches else dict(tone=None,sample_matches=False,reason="unmapped_native_sample_address")

    def bank_read(self,bank,address,count,size):
        return parse_bank_reply(self.request("spu_sample_bank",bank=bank,addr=address,len=count),
                                bank,address,count,expected_size=size)

    def fingerprint_banks(self):
        """At most44 bounded body reads; retain hashes, never ADPCM bytes."""
        result=[]
        for record in self.private_banks["banks"]:
            bank,size=record["bank"],record["bytes"]
            self.bank_read(bank,0,0,size)
            digest=hashlib.sha256()
            for at in range(0,size,4096):
                digest.update(self.bank_read(bank,at,min(4096,size-at),size)["data"])
            self.bank_read(bank,0,0,size)
            observed=digest.hexdigest()
            if observed!=record["sha256"]:
                raise AudioQualificationError("Resident immutable bank does not match original Zero body")
            result.append(dict(bank=bank,bytes=size,sha256=observed,source_member=85,
                               body_subasset=record["body_subasset"],matches_source=True))
        return result

    def identify_banked(self,event,driver):
        bank=_uint(event.get("sample_bank"),5,"selected event-time bank")
        descriptor=next((b for b in self.private_banks["banks"] if b["bank"]==bank),None)
        if bank and descriptor is None:
            raise AudioQualificationError("Event names an unqualified immutable bank")
        matches=[]
        for tone in self.contract["tones"]:
            if tone["group"]!=3 or tone["record"] not in (2,3,4,6,7):continue
            if descriptor and (tone["character"],tone["group"])!=(descriptor["character"],descriptor["group"]):continue
            start=tone["offset"]+(0 if bank else driver["bases"][tone["vab_handle"]])
            if start!=event["addr"]:continue
            size=descriptor["bytes"] if descriptor else 0x80000
            count=tone["bytes"]
            if not 0<count<=4096 or start+count>size:
                raise AudioQualificationError("Sample escaped its named bank")
            payload=self.bank_read(bank,start,count,size)["data"]
            digest=hashlib.sha256(payload).hexdigest()
            matches.append(dict(tone=tone,sample_bank=bank,sample_matches=digest==tone["sample_sha256"],
                observed_sha256=digest,bank_size=size,sample_offset=start,probe_bytes=count,
                attribution="event_time_bank_and_exact_source_bytes"))
        if len(matches)>1:raise AudioQualificationError("Ambiguous named-bank sample identity")
        return matches[0] if matches else dict(tone=None,sample_bank=bank,sample_matches=False,
                                               reason="unmapped_event_time_bank_sample")


def accepted_ground_jump(before: dict, after: dict, seat: int, receipt: dict) -> bool:
    """Require native ascent while held, then only its normal6/7 air phases.

    Native actor+24 is positive-up speed, subtracted from Y at8002D078.
    Releasing Cross at8003565C..70 zeroes it;80035760..8C then sets
    action7/airborne=-1. The post-release RPC can therefore observe a valid
    falling short jump. Its earlier held endpoint must prove action6 and
    upward displacement; a generic falling action alone is insufficient.
    """
    try:
        if type(seat) is not int or seat not in (0,1) or not isinstance(receipt,dict):return False
        initial,final=before["players"][seat],after["players"][seat]
        start,end=receipt["start"]["players"][seat],receipt["end"]["players"][seat]
        progress=(receipt["actual_native_ticks"],receipt["actual_publications"])
        return bool(type(receipt["seat"]) is int and receipt["seat"]==seat and receipt["pressed"]==CROSS and
            all(type(n) is int and 0<n<0x80000000 for n in progress) and
            initial["action"]==2 and initial["ground"] and initial["airborne"]==0 and
            start["active"]==end["active"]==1 and start["state"]==end["state"]==1 and
            start["character"]==end["character"]==initial["character"] and
            start["hp"]==end["hp"]==initial["hp"] and start["action"]==2 and
            start["y_raw"]==initial["y"] and end["action"]==6 and end["y_raw"]<initial["y"] and
            final["state"]==1 and final["character"]==initial["character"] and final["hp"]==initial["hp"] and
            (final["action"],final["airborne"]) in ((6,1),(7,-1)) and not final["ground"] and
            final["y"]<initial["y"])
    except (KeyError,TypeError,IndexError):
        return False


def jump_overlap_smoke(ctx: dict,contract: dict,*,first_seat: int=0,max_attempts: int=8,
                       timeout: float=90) -> dict:
    """One LOCAL X/Falcon-P1 + Zero-P2 overlap; owner handles lifecycle/muting.

    ctx: mode='local', input_path='published_host', clients=[owned client],
    request(cmd,**fields) (ownership checked), hold(seat,bits,frames,label)
    (ordinary host input, neutral release in its finally), native_advance
    (frames,label), report, candidate Path, expected_sha256. Both native digital
    devices/settings must already be stable before guest0. No topology changes.
    """
    required=("mode","input_path","clients","request","hold","native_advance","report","candidate","expected_sha256")
    if any(k not in ctx for k in required) or ctx["mode"]!="local" or \
            ctx["input_path"]!="published_host" or len(ctx["clients"])!=1:
        raise ValueError("Requires one owned LOCAL process and published host input")
    if type(first_seat) is not int or first_seat not in (0,1) or type(max_attempts) is not int or not 1<=max_attempts<=8 or \
            type(timeout) not in (int,float) or not 0<timeout<=120:
        raise ValueError("Unbounded/invalid jump audio case")
    if not isinstance(ctx["report"],dict) or any(not callable(ctx[k]) for k in ("request","hold","native_advance")):
        raise ValueError("Missing owned audio/control callback")
    candidate=Path(ctx["candidate"]).resolve()
    expected=ctx["expected_sha256"]
    if not isinstance(expected,str) or not re.fullmatch(r"[a-f0-9]{64}",expected) or \
            sha256(candidate/"mmx6-runtime.exe")!=expected or \
            json.loads((candidate/"preparation.json").read_text(encoding="utf-8"))["exe_sha256"]!=expected:
        raise ValueError("Prepared candidate image identity mismatch")
    private_banks=ctx.get("private_banks")
    if private_banks is not None:validate_private_bank_contract(private_banks,contract)
    observer=(AudioObserver(ctx["clients"][0],ctx["request"],contract,private_banks=private_banks)
              if private_banks is not None else AudioObserver(ctx["clients"][0],ctx["request"],contract))
    case=dict(kind="native_jump_audio_overlap",mode="local",input_path="published_host",
        candidate_sha256=expected,helper_sha256=sha256(Path(__file__)),
        source_contract_sha256=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        first_seat=first_seat,status="failed_setup",attempts=[],observations=[],inputs=[],checks={},events=[],
        diagnostics_scope="private_banks_v1" if private_banks is not None else "hardware_legacy")
    if private_banks is not None:case["private_bank_source"]=private_banks
    ctx["report"].setdefault("jump_audio",[]).append(case)
    deadline=time.monotonic()+timeout
    def require(ok,message):
        if not ok:raise AudioQualificationError(message)
    def sample(label):
        require(time.monotonic()<deadline,"Bounded jump audio deadline expired")
        row=observer.poll();o=row["observation"];p=row["players"]
        require(o["ready"]==o["enrolled"]==1 and not o["failed"] and not o["mailbox"] and
            o["native_mode"]==10 and o["native_phase"]==0 and not o["scene_owner"] and
            not o["pause_owner"] and tuple(o["lifecycle"])==(0,0),"Jump case left ordinary living gameplay")
        require([(v["character"],v["form"]) for v in p]==[(0,1),(1,5)] and
                all(v["state"]==1 and v["hp"]==32 and v["speech_gate"]==0 for v in p),
                "Jump case needs healthy original Falcon X/Zero with native speech allowed")
        row["label"]=label;case["observations"].append(row);return row
    def ground(label):
        for n in range(21):
            row=sample(label)
            if all(p["action"]==2 and not p["airborne"] and p["ground"] for p in row["players"]):return row
            require(n<20,"Both actors failed to return to native ground/idle")
            ctx["native_advance"](4,label)
    def hold(seat,label):
        receipt=ctx["hold"](seat,CROSS,1,label);case["inputs"].append(receipt);return receipt
    chosen=None
    try:
        ground("audio-initial-ground")
        if private_banks is not None:case["private_banks_before"]=observer.fingerprint_banks()
        before_driver=observer.driver();case["driver_before"]=before_driver
        require(before_driver["release_adjust"]==0 and all(before_driver["vab_status"][i]==1 for i in (1,3)),
                "Unqualified native release/VAB readiness")
        case["voices_before"]=parse_voices(ctx["request"]("spu_voices"),require_banks=private_banks is not None)
        if private_banks is not None:case["private_voices_before"]=parse_private_voices(ctx["request"]("spu_private_voices"))
        for attempt in range(max_attempts):
            before=ground(f"audio-attempt-{attempt}-ground");held=hold(first_seat,"audio-first-jump")
            first=sample("audio-first-jump")
            require(accepted_ground_jump(before,first,first_seat,held),"First native jump was not accepted")
            jump_voices=(20,44) if private_banks is not None else (20,)
            first_keys=[e for e in first["new_events"] if e["kind"]=="KEYON" and e["v"] in jump_voices]
            row=dict(attempt=attempt,first_keys=first_keys);case["attempts"].append(row)
            if not first_keys:continue # Native RNG may deliberately omit the voice.
            require(len(first_keys)==1,"Ambiguous first jump voice window")
            held=hold(first_seat^1,"audio-second-jump");second=sample("audio-second-jump")
            require(accepted_ground_jump(before,second,first_seat^1,held),"Second native jump was not accepted")
            second_keys=[e for e in second["new_events"] if e["kind"]=="KEYON" and e["v"] in jump_voices]
            row["second_keys"]=second_keys
            if not second_keys:continue
            require(len(second_keys)==1,"Ambiguous second jump voice window")
            first_end=lifetime(observer.events,first_keys[0])
            if first_end["disposition"]=="natural_end" and first_end["terminal"]["seq"]<second_keys[0]["seq"]:
                row["overlap"]="not_observed_first_voice_already_ended";continue
            ground("audio-overlap-drain")
            chosen=(first_keys[0],second_keys[0]);break
        ground("audio-final-ground")
        if private_banks is not None:
            case["private_banks_after"]=observer.fingerprint_banks()
            require(case["private_banks_before"]==case["private_banks_after"],"Private immutable bank identity changed")
            sample("audio-after-read-only-bank-probes")
        after_driver=observer.driver();case["driver_after"]=after_driver
        require(before_driver==after_driver,"Native audio resource tables changed during sample probes")
        case["voices_after"]=parse_voices(ctx["request"]("spu_voices"),require_banks=private_banks is not None)
        if private_banks is not None:
            case["private_voices_after"]=parse_private_voices(ctx["request"]("spu_private_voices"))
            sample("audio-after-separate-final-dsp-snapshots")
        case["events"]=observer.events
        if chosen is None:
            case["status"]="inconclusive_native_rng_no_two_voice_window";return case
        identities={e["seq"]:observer.identify(e,after_driver) for e in chosen}
        if private_banks is not None:
            case.update(compare_private_overlap(observer.events,*chosen,identities,first_seat,contract))
            final_checks,details=final_dsp_checks(observer.events,case["actors"],case["voices_after"],case["private_voices_after"])
            case["checks"].update(final_checks);case["final_dsp_observations"]=details
            case["checks"]["private_source_banks_stable"]=True
        else:
            case.update(compare_overlap(observer.events,*chosen,identities,first_seat))
            case["checks"]["last_voice_envelope_terminated"]=case["voices_after"]["voices"][20]["env"]==0 and \
                case["voices_after"]["voices"][20]["env_phase"]==3
        case["status"]="observations_complete" if all(case["checks"].values()) else "comparison_failed"
        return case
    except Exception as error:
        case["error"]=dict(type=type(error).__name__,message=str(error));case["events"]=observer.events
        raise
    finally:
        # Neutral ordinary host input only; owner callbacks preserve devices.
        for seat in (0,1):
            try:ctx["hold"](seat,0,1,"audio-finally-neutral")
            except Exception as error:
                case.setdefault("neutral_errors",[]).append(dict(seat=seat,message=str(error)))
                case["status"]="failed_cleanup"


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description="Prepare bounded original jump audio metadata; never connects to a runtime")
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--disc",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    destination=args.out.resolve()
    if destination.drive.lower() not in ("f:","g:"):
        parser.error("Metadata output must be a fresh F:/G: file")
    contract=build_contract(args.exe,args.disc)
    with destination.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(contract,stream,indent=2);stream.write("\n")
    print("Bounded original jump metadata prepared; native/audio outcomes remain unverified")
