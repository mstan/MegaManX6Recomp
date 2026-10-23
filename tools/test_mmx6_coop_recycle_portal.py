"""Strict read-only portal observation/reducer tests; no native/gameplay pass."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock

import mmx6_coop_recycle_portal as portal

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "a" * 64


def body(character=0):
    data = bytearray(0x158)
    data[0]=data[3]=data[4]=1;data[2]=character;data[5]=2;data[0x5C]=32;data[0x70]=8
    for at, value in ((8,1728<<16),(12,1456<<16),(0x38,0x801F0000),(0x3C,0x801F1000),(0x68,0x80075B9C)):
        struct.pack_into("<I",data,at,value)
    return data


def publication():
    data=bytearray(portal.debug.DIAGNOSTIC_BYTES)
    struct.pack_into("<II",data,0,0x434F4F50,1)
    struct.pack_into("<III",data,0x80,1,len(data),2)
    data[0x8C]=data[0x8D]=1;data[0x90]=10;struct.pack_into("<I",data,0x98,1)
    data[0x100:0x258]=body(1);data[0x1800:0x1958]=body(0)
    data[8:16]=data[0x108:0x110];data[24]=32
    return bytes(data)


def native(member=None):
    data=bytearray(portal.SIZE)
    def write(address,raw):data[address-portal.BASE:address-portal.BASE+len(raw)]=raw
    if member is not None:write(0x800E9860,member[:portal.END-0x800E9860])
    write(portal.PLAY,bytes((10,0)));write(portal.PLAY+12,bytes((4,0)))
    write(portal.PLAYER,body());write(portal.RECORD,struct.pack("<4B2h",1,28,1,0,1552,1584))
    write(0x800F308C,struct.pack("<I",0x800EC678))
    write(portal.BIN_TABLE+6*8,struct.pack("<II",211338,42944))
    actor=bytearray(portal.STRIDE);actor[0]=0x41;actor[1]=28;actor[2]=1;actor[3]=actor[4]=actor[5]=1
    struct.pack_into("<I",actor,0x10,portal.RECORD);write(portal.POOL,actor)
    return data


def response(address,raw):return dict(ok=True,addr=hex(address),len=len(raw),hex=bytes(raw).hex())


def native_record_state(exe, record, mode):
    """Execute only the pinned admission leaf's integer/branch/store subset.

    Bounded source proof, not a CPU/game emulator. Original instructions have
    explicit independent load-delay slots; branch delay slots execute below.
    Only record+3 and PLAY+68 memory accesses are permitted.
    """
    program=exe.data[exe.offset(0x80029E7C,0xBC):exe.offset(0x80029E7C,0xBC)+0xBC]
    if portal.sha(program)!="df6eff4115848b712fbc5f13bac169665422de1032a5e9544412af5d56e7da89":
        raise ValueError("Unpinned native admission leaf")
    raw=bytearray(record);regs=[0]*32;regs[4]=portal.RECORD;regs[31]=0x80000000
    pc=0x80029E7C;delayed=None;writes=[]
    signed=lambda n:n-0x100000000 if n&0x80000000 else n
    for _ in range(96):
        if pc==0x80000000:return bytes(raw),regs[2],writes
        if not 0x80029E7C<=pc<0x80029F38 or pc&3:raise ValueError("Admission PC escaped")
        word=exe.word(pc);op=word>>26;rs=(word>>21)&31;rt=(word>>16)&31;rd=(word>>11)&31
        imm=word&0xFFFF;short=imm-0x10000 if imm&0x8000 else imm;target=None
        if word==0:pass
        elif op==0 and word&63==0x21:regs[rd]=regs[rs]+regs[rt]
        elif op==0 and word&63==0x2B:regs[rd]=int(regs[rs]<regs[rt])
        elif op==0 and word&63==8:target=regs[rs]
        elif op==2:target=((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        elif op in (4,5):
            if (regs[rs]==regs[rt])==(op==4):target=pc+4+short*4
        elif op==9:regs[rt]=regs[rs]+short
        elif op==10:regs[rt]=int(signed(regs[rs])<short)
        elif op==11:regs[rt]=int(regs[rs]<(short&0xFFFFFFFF))
        elif op==12:regs[rt]=regs[rs]&imm
        elif op==15:regs[rt]=imm<<16
        elif op==0x24:
            address=(regs[rs]+short)&0xFFFFFFFF
            if address==portal.RECORD+3:regs[rt]=raw[3]
            elif address==portal.PLAY+0x68:regs[rt]=mode
            else:raise ValueError("Admission memory read escaped")
        elif op==0x28:
            address=(regs[rs]+short)&0xFFFFFFFF
            if address!=portal.RECORD+3:raise ValueError("Admission memory write escaped")
            raw[3]=regs[rt]&255;writes.append(pc)
        else:raise ValueError(f"Unsupported admission opcode {word:08X}")
        if delayed is not None and target is not None:raise ValueError("Branch in delay slot")
        regs=[n&0xFFFFFFFF for n in regs];regs[0]=0
        pc=delayed if delayed is not None else pc+4;delayed=target
    raise ValueError("Admission instruction bound exhausted")


class PortalObserverTests(unittest.TestCase):
    def test_exact_extent_pool_and_resident_attribution(self):
        raw=native();row=portal.parse_native(raw)
        self.assertEqual(row["raw_bytes"],portal.END-portal.BASE)
        self.assertEqual(row["portal"]["origin"],portal.RECORD)
        self.assertEqual((row["portal"]["phase"],row["portal"]["action"]),(1,1))
        self.assertTrue(row["source_record_match"])
        self.assertFalse(row["source_closure_present"]) # Synthetic code is not original proof.
        self.assertTrue(row["resident_player"]["native_ground_contact"])
        self.assertIn("not a private seat",row["resident_attribution"])
        with self.assertRaises(portal.debug.DebugError):portal.parse_native(raw[:-1])

    def test_freed_origin_is_ignored_duplicates_and_wrong_types_rejected(self):
        raw=native();raw[0]=0;self.assertIsNone(portal.parse_native(raw)["portal"])
        raw=native();raw[0]=0x20;self.assertIsNone(portal.parse_native(raw)["portal"])
        raw=native();raw[portal.STRIDE:portal.STRIDE*2]=raw[:portal.STRIDE]
        with self.assertRaisesRegex(portal.debug.DebugError,"Duplicate"):portal.parse_native(raw)
        for offset,value in ((1,27),(2,2),(4,4),(5,6),(6,3)):
            raw=native();raw[offset]=value
            with self.assertRaises(portal.debug.DebugError):portal.parse_native(raw)
        raw=native();raw[portal.PLAY+12-portal.BASE]=20;raw[portal.PLAY+13-portal.BASE]=1
        self.assertIsNone(portal.parse_native(raw)["portal"]) # No old-origin attribution on a new map.

    def test_record_has_only_four_complete_source_variants(self):
        for state in (0,0x10):
            for flags in range(256):
                raw=native();raw[portal.RECORD-portal.BASE]=flags;raw[portal.RECORD-portal.BASE+3]=state
                self.assertEqual(portal.parse_native(raw)["source_record_match"],flags in (0,1))
        for flags in (0,1):
            for state in range(256):
                raw=native();raw[portal.RECORD-portal.BASE]=flags;raw[portal.RECORD-portal.BASE+3]=state
                self.assertEqual(portal.parse_native(raw)["source_record_match"],state in (0,0x10))
        for offset in (1,2,4,5,6,7):
            raw=native();raw[portal.RECORD-portal.BASE+offset]^=1
            self.assertFalse(portal.parse_native(raw)["source_record_match"])

    def test_original_native_admission_leaf_produces_observed_byte3(self):
        path=os.environ.get("MMX6_CONTENT_EXE")
        if not path:self.skipTest("Supply original MMX6_CONTENT_EXE")
        exe=portal.checkpoint.original_executable(Path(path))
        original=struct.pack("<4B2h",0,28,1,0,1552,1584)
        for mode in (0,1,2):
            changed,result,writes=native_record_state(exe,original,mode)
            self.assertEqual(changed,bytes.fromhex("001c011010063006"))
            self.assertEqual((result,writes),(0,[0x80029EF8]))
            pending,result,writes=native_record_state(exe,changed,mode)
            self.assertEqual((pending,result,writes),(changed,1,[]))
        unchanged,result,writes=native_record_state(exe,original,3)
        self.assertEqual((unchanged,result,writes),(original,0,[]))
        for pc,word in ((0x8002A12C,0x0C00A79F),(0x8002A25C,0x34420001),
                        (0x8002A264,0xA2420000),(0x8002A380,0x30A2000F),(0x8002A384,0xA0820003)):
            self.assertEqual(exe.word(pc),word)
        self.assertIn(bytes.fromhex("011c011010063006"),portal.RECORD_VARIANTS)

    def test_read_only_callbacks_are_exact_and_cross_rpc_attribution_stays_missing(self):
        raw=native();diag=publication();calls=[]
        def request(command,**fields):
            calls.append((command,fields))
            address=int(fields["addr"],0)
            return response(address,raw if address==portal.BASE else diag)
        ctx=dict(candidate_exe_sha256=IMAGE,mode="local",read_only_requests=[request],report={})
        case=portal.observe_context(ctx,expected_exe_sha256=IMAGE)
        self.assertEqual([r[0]for r in calls],["read_ram","read_ram"])
        self.assertEqual(calls[0][1],dict(addr=hex(portal.BASE),len=portal.SIZE))
        self.assertEqual(case["status"],"unverified_setup_gap")
        self.assertFalse(any(case["checks"].values()))
        self.assertIn("separate RPCs",case["coherence_gap"])
        self.assertEqual(case["peers"][0]["publication"]["namespace"],"unavailable in this base publication")
        self.assertIs(ctx["report"]["recycle_portal_observer"][0],case)

    def test_failures_keep_prior_native_sample(self):
        request=Mock(side_effect=[response(portal.BASE,native()),dict(ok=True,len=0,hex="")])
        ctx=dict(candidate_exe_sha256=IMAGE,mode="local",read_only_requests=[request],report={})
        with self.assertRaises(portal.debug.DebugError):portal.observe_context(ctx,expected_exe_sha256=IMAGE)
        case=ctx["report"]["recycle_portal_observer"][0]
        self.assertEqual(case["status"],"failed_observation_setup_gap")
        self.assertIn("native",case["peers"][0]);self.assertNotIn("publication",case["peers"][0])

    def test_invalid_envelopes_and_unbound_context_do_not_become_evidence(self):
        for envelope in (dict(ok=True,addr=hex(portal.BASE),len=portal.SIZE,hex="00"),
                         dict(ok=True,addr=hex(portal.BASE+1),len=portal.SIZE,hex="00"*portal.SIZE),
                         dict(ok=False),dict(ok=True,addr=hex(portal.BASE),len=portal.SIZE,hex="gg"*portal.SIZE)):
            with self.assertRaises(portal.debug.DebugError):portal.observe_native(Mock(return_value=envelope))
        request=Mock();ctx=dict(candidate_exe_sha256=IMAGE,mode="local",read_only_requests=[request],report={})
        for image in (None,"b"*64,"not-an-image"):
            with self.assertRaises(ValueError):portal.observe_context(ctx,expected_exe_sha256=image)
        request.assert_not_called()
        ctx["mode"]="netplay"
        with self.assertRaises(ValueError):portal.observe_context(ctx,expected_exe_sha256=IMAGE)

    def test_publication_must_be_one_valid_completed_block(self):
        raw=bytearray(publication());struct.pack_into("<I",raw,0x88,3)
        with self.assertRaises(portal.debug.UnstableObservation):
            portal.observe_publication(Mock(return_value=response(portal.debug.DIAGNOSTIC_ADDRESS,raw)))
        with self.assertRaises(ValueError):portal.observe_publication(Mock(),0x800970A0)
        raw=body();raw[0x68:0x6C]=bytes(4)
        self.assertFalse(portal._body(raw)["native_ground_contact"])

    def transition_rows(self):
        row=portal.parse_native(native());row["source_closure_present"]=True
        rows=[row]
        row=copy.deepcopy(row);row["portal"].update(action=2,saved_body_box=0x80075B9C);row["freeze"]=2;rows.append(row)
        row=copy.deepcopy(row);row.update(transition=0x41,fade=-1);rows.append(row)
        row=copy.deepcopy(row);row.update(mode=8,stage=20,section=1,portal=None);rows.append(row)
        row=copy.deepcopy(row);row.update(mode=9,checkpoint=0);rows.append(row)
        row=copy.deepcopy(row);row.update(mode=10,phase=0,transition=0,fade=0,freeze=0,shared_entry_lock=0,loader_status=2)
        row["camera"]=dict(x=0,y=224,min_x=0,max_x=2576,min_y=224,max_y=224)
        row["native_bin_descriptors"]["28"]=[211776,40334];rows.append(row)
        plan=dict(destination=dict(camera=row["camera"]),destination_section=dict(source_member=dict(sector=591,size=40334)),
                  destination_code_windows=[dict(sha256=row["destination_code_prefix_sha256"])])
        return rows,plan

    def test_partial_native_sequence_never_grants_contact_or_arrival_qualification(self):
        rows,plan=self.transition_rows();result=portal.reduce_native_transition(rows,plan)
        self.assertTrue(all(result["checks"][name]for name in (
            "source_portal_seen","native_action2_seen","native_freeze_seen","native_41h_and_fade_seen",
            "major8_seen","major9_seen","destination_native_ready_seen")))
        self.assertEqual(result["status"],"unverified_setup_gap")
        self.assertFalse(result["checks"]["p1_outside_p2_contact"])
        self.assertFalse(result["checks"]["published_both_arrivals"])
        self.assertFalse(result["checks"]["independent_controls"])
        self.assertFalse(result["checks"]["composed_capture"])
        missing=portal.reduce_native_transition(rows[:4]+rows[5:],plan)
        self.assertFalse(missing["checks"]["destination_native_ready_seen"])
        rows[1]["portal"]["address"]+=portal.STRIDE
        rows[2]["portal"]["address"]+=portal.STRIDE
        self.assertFalse(portal.reduce_native_transition(rows,plan)["checks"]["native_action2_seen"])

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                         "Pinned original inputs not supplied")
    def test_actual_source_plan_nearest_checkpoint_and_presence(self):
        exe=Path(os.environ["MMX6_CONTENT_EXE"]);disc=Path(os.environ["MMX6_CONTENT_DISC"])
        plan=portal.source_plan(exe,disc)
        self.assertEqual(plan["nearest_authored_checkpoint"]["id"],"s04-a0-c03")
        self.assertEqual(plan["distance_squared"],47360)
        self.assertEqual(plan["nearest_authored_checkpoint"]["camera"],dict(x=1568,y=1440,min_x=1568,max_x=1568,min_y=1440,max_y=1440))
        self.assertEqual(plan["destination"]["id"],"s20-a1-c00")
        self.assertEqual(plan["automatic_actions"],[])
        raw=portal.content.RawDisc(disc)
        try:archive=raw.extent(211185,1665024)
        finally:raw.stream.close()
        member=archive[153*2048:153*2048+42944]
        observed=portal.parse_native(native(member))
        self.assertTrue(observed["source_closure_present"])
        for variant in portal.RECORD_VARIANTS:
            admitted=native(member)
            at=portal.RECORD-portal.BASE;admitted[at:at+8]=variant
            self.assertTrue(portal.parse_native(admitted)["source_closure_present"])
        self.assertEqual(plan["record_mutation"]["complete_record_variants"],
                         [v.hex() for v in portal.RECORD_VARIANTS])
        mutated=native(member);mutated[0x800EC780-portal.BASE]^=1
        self.assertFalse(portal.parse_native(mutated)["source_closure_present"])
        mutated=native(member);mutated[portal.BIN_TABLE+6*8-portal.BASE]^=1
        self.assertFalse(portal.parse_native(mutated)["source_closure_present"])


if __name__ == "__main__":unittest.main()
