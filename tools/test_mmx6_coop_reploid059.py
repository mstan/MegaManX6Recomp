"""Source/parser/exclusion regressions. No process, socket, game or RAM writes."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

import mmx6_coop_reploid059 as subject
import qualify_mmx6_coop_recycle_portal as runner
from test_qualify_mmx6_coop_recycle_portal import native, publication, response
from test_mmx6_coop_recycle_portal import native_record_state

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    raw = native()
    actor = bytearray(subject.STRIDE)
    actor[:8] = bytes((0x41,4,59,1,1,0,0,1))
    struct.pack_into("<ii",actor,8,subject.X<<16,subject.Y<<16)
    actor[0x18:0x20] = actor[8:16]
    struct.pack_into("<I",actor,0x10,subject.RECORD)
    struct.pack_into("<I",actor,0x68,subject.BOX_POINTER)
    actor[0x70] = 8
    address = subject.POOL+subject.STRIDE
    at = address-runner.portal.BASE
    raw[at:at+len(actor)] = actor
    for a,data in ((subject.RECORD,subject.ALLOCATED),(subject.DISPATCH_TABLE,subject.TABLE_BYTES)):
        at = a-runner.portal.BASE
        raw[at:at+len(data)] = data
    row = runner.observe_native(lambda command,**fields:response(int(fields["addr"],0),raw))
    row["native"]["source_closure_present"] = True # Synthetic source gate, not native proof.
    proof = dict(source_guards=dict(status="original_source_guards_verified"),
        body_box_probe=dict(address=subject.BOX_POINTER,bytes=4,hex=subject.BOX.hex(),
            provenance="separate_owned_read_ram_fixed_source_pointer"),
        dispatch_probe=dict(address=subject.DISPATCH_POINTER,bytes=4,value=subject.DISPATCH_TABLE,
            provenance="separate_owned_read_ram_fixed_scratch_slot"))
    evidence = [dict(pointer=p,hex=b.hex(),origin="resident_native_ram" if seat == 0 else "native_ram")
                for seat,(p,b) in enumerate(subject.BODY_BOXES)]
    return row,publication(),evidence,proof


def mutate_actor(row, offset, value):
    actor = row["nearby_actors"][-1]
    raw = bytearray.fromhex(actor["raw_hex"])
    raw[offset:offset+len(value)] = value
    actor["raw_hex"] = raw.hex()


def original_horizontal_overlap(exe, player_x, facing=0):
    """Execute original2DCF4 through its horizontal return/vertical boundary.

    Pure, read-only integer/branch prefix. It never calls the game and rejects
    every unexpected instruction/address rather than emulating side effects.
    """
    memory={};regs=[0]*32;regs[4]=subject.POOL;regs[5]=runner.portal.PLAYER
    def put(address,data):memory.update((address+i,b) for i,b in enumerate(data))
    for address,x,face,pointer in ((regs[4],subject.X,0,subject.BOX_POINTER),
            (regs[5],player_x,facing,subject.BODY_BOXES[0][0])):
        put(address+0x68,struct.pack("<I",pointer))
        put(address+0xA,struct.pack("<h",x));put(address+0x15,bytes((face,)))
    put(subject.BOX_POINTER,subject.BOX)
    put(subject.BODY_BOXES[0][0],subject.BODY_BOXES[0][1])
    pc=0x8002DCF4;delayed=None
    signed=lambda value:value-0x100000000 if value&0x80000000 else value
    for _ in range(128):
        if pc==0x8002DD08:return False
        if pc==0x8002DDE4:return True
        if not 0x8002DCF4<=pc<0x8002DDE4 or pc&3:
            raise ValueError("Original horizontal prefix escaped")
        word=exe.word(pc);op=word>>26;rs=(word>>21)&31;rt=(word>>16)&31;rd=(word>>11)&31
        sa=(word>>6)&31;fun=word&63;imm=word&0xFFFF;short=imm-0x10000 if imm&0x8000 else imm
        target=None
        if word==0:pass
        elif op==0 and fun==0x21:regs[rd]=regs[rs]+regs[rt]
        elif op==0 and fun==0x23:regs[rd]=regs[rs]-regs[rt]
        elif op==0 and fun==0x2A:regs[rd]=int(signed(regs[rs])<signed(regs[rt]))
        elif op==0 and fun==0:regs[rd]=regs[rt]<<sa
        elif op==0 and fun==3:regs[rd]=signed(regs[rt])>>sa
        elif op==2:target=((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        elif op in (4,5):
            if (regs[rs]==regs[rt])==(op==4):target=pc+4+short*4
        elif op==1 and rt==0:
            if signed(regs[rs])<0:target=pc+4+short*4
        elif op==9:regs[rt]=regs[rs]+short
        elif op in (0x23,0x24,0x25):
            address=(regs[rs]+short)&0xFFFFFFFF
            size={0x23:4,0x24:1,0x25:2}[op]
            regs[rt]=int.from_bytes(bytes(memory[address+i] for i in range(size)),"little")
        else:raise ValueError(f"Unexpected original prefix instruction{word:08X}")
        if delayed is not None and target is not None:raise ValueError("Branch in delay slot")
        regs=[value&0xFFFFFFFF for value in regs];regs[0]=0
        pc=delayed if delayed is not None else pc+4;delayed=target
    raise ValueError("Original prefix instruction bound exhausted")


class ReploidTests(unittest.TestCase):
    def test_one_block_full_shape_exact_record_and_conditional_radius_sum(self):
        row,pub,evidence,proof = fixture()
        actor = subject.find_actor(row)
        self.assertEqual(len(bytes.fromhex(actor["raw_hex"])),0xA4)
        self.assertEqual(actor["source_record_hex"],subject.ALLOCATED.hex())
        self.assertEqual(actor["atomic_provenance"]["record_address"],subject.RECORD)
        result = subject.validate_frame(row,pub,evidence,proof)
        self.assertEqual(result["minimum_observed_margin"],127)
        self.assertEqual([r["horizontal_distance"] for r in result["player_checks"]],[146]*3)
        self.assertEqual([r["radius_sum"] for r in result["player_checks"]],[19]*3)
        self.assertEqual(result["native_reploid_mechanics"],"unverified")
        self.assertFalse(actor["known_source_actor"]) # No broad raw-parser whitelist.

    def test_wrong_identity_partial_origin_record_duplicate_and_probe_refused(self):
        row,pub,evidence,proof = fixture()
        for offset,value in ((0,b"\0"),(1,b"\x1a"),(2,b"\x3a"),
                (0x10,struct.pack("<I",subject.RECORD+8)),(0x68,struct.pack("<I",0x8007891C))):
            bad = copy.deepcopy(row);mutate_actor(bad,offset,value)
            with self.subTest(offset=offset),self.assertRaises(subject.debug.DebugError):
                subject.validate_frame(bad,pub,evidence,proof)
        for change in ("truncated","record","provenance","duplicate","metadata"):
            bad = copy.deepcopy(row);actor=bad["nearby_actors"][-1]
            if change == "truncated":actor["raw_hex"] = actor["raw_hex"][:-2]
            elif change == "record":actor["source_record_hex"] = "01043b1450054006"
            elif change == "provenance":actor.pop("atomic_provenance")
            elif change == "metadata":actor["origin"] += 8
            else:bad["nearby_actors"].append(copy.deepcopy(actor))
            with self.subTest(change=change),self.assertRaises(subject.debug.DebugError):
                subject.validate_frame(bad,pub,evidence,proof)
        for key in ("source_guards","body_box_probe","dispatch_probe"):
            bad = copy.deepcopy(proof);bad.pop(key)
            with self.subTest(key=key),self.assertRaises(subject.debug.DebugError):
                subject.validate_frame(row,pub,evidence,bad)

    def test_collection_healing_infection_motion_bob_and_phase_changes_refused(self):
        row,pub,evidence,proof = fixture()
        for offset,value in ((3,0),(4,0),(4,2),(4,6),(4,7),(5,1),(6,1),(7,0),(7,2),
                (0x15,0x40),(0x20,1),(0x24,1),(0x28,1),(0x2C,1),(0x70,0),
                (0x7C,1),(0x7E,1),(0x82,1),(0x84,1),(0xA,0x51)):
            bad = copy.deepcopy(row);mutate_actor(bad,offset,bytes((value,)))
            with self.subTest(offset=offset,value=value),self.assertRaises(subject.debug.DebugError):
                subject.validate_frame(bad,pub,evidence,proof)

    def test_body_box_provenance_finite_bounds_ride_and_unknowns_refused(self):
        row,pub,evidence,proof = fixture()
        for change in ("left","right","p1moved","ride","badbox","wrongbank","dead","scene","nativeleft"):
            p = copy.deepcopy(pub);r = copy.deepcopy(row);e = copy.deepcopy(evidence)
            body = bytearray.fromhex(p["p2_body_hex"])
            if change in ("left","right"):
                struct.pack_into("<i",body,8,(1505 if change == "left" else 1696)<<16)
            elif change == "ride":body[0xD5] = 1
            elif change == "dead":body[0x5C] = 0
            elif change == "badbox":e[0]["hex"] = "00021413" # damage-box radius cannot substitute.
            elif change == "wrongbank":p["boxes"]["body"]["origin"] = "private_overlay"
            elif change == "scene":p["observation"]["scene_owner"] = 2
            elif change == "p1moved":
                b = bytearray.fromhex(p["p1_body_hex"]);struct.pack_into("<i",b,8,1507<<16);p["p1_body_hex"] = b.hex()
            elif change == "nativeleft":
                b = bytearray.fromhex(r["native"]["resident_player"]["raw_hex"])
                struct.pack_into("<i",b,8,1360<<16);r["native"]["resident_player"]["raw_hex"] = b.hex()
            p["p2_body_hex"] = body.hex()
            with self.subTest(change=change),self.assertRaises(subject.debug.DebugError):
                subject.validate_frame(r,p,e,proof)
        for origin in ("body_box_probe","dispatch_probe"):
            bad = copy.deepcopy(proof);bad[origin]["provenance"] = "guessed"
            with self.assertRaises(subject.debug.DebugError):subject.validate_frame(row,pub,evidence,bad)

    def test_changed_critical_state_rejected_but_animation_bytes_are_retained(self):
        row,pub,evidence,proof = fixture()
        proof["actor_baseline"] = subject.actor_state(subject.find_actor(row))[1]
        changed = copy.deepcopy(row);mutate_actor(changed,0x82,b"\x40")
        with self.assertRaisesRegex(subject.debug.DebugError,"changed"):
            subject.validate_frame(changed,pub,evidence,proof)
        changed = copy.deepcopy(row);mutate_actor(changed,0x44,bytes.fromhex("12345678"))
        subject.validate_frame(changed,pub,evidence,proof)
        self.assertIn("12345678",subject.find_actor(changed)["raw_hex"])

    def test_probe_uses_only_fixed_read_addresses_retains_brackets_and_no_write(self):
        row,pub,evidence,proof = fixture();control=Mock();receipt={}
        replies = {subject.BOX_POINTER:subject.BOX,
                   subject.DISPATCH_POINTER:struct.pack("<I",subject.DISPATCH_TABLE)}
        with patch.object(runner.portal,"_read",side_effect=lambda c,a,n:replies[a]), \
             patch.object(runner,"observe_native",return_value=copy.deepcopy(row)), \
             patch.object(runner.boxes,"observe_owned",return_value=pub):
            result = runner.probe_reploid_exclusion(control,{"reploid059_guards":proof["source_guards"]},row,pub,evidence,receipt)
        self.assertEqual(result["status"],"conditional_source_bound_contact_exclusion")
        self.assertIs(result["before_native"],row)
        self.assertIsNot(result["after_native"],row)
        self.assertFalse(result["continuous_frame_coverage"])
        control.assert_not_called() # reads mocked above; never a mutation path.
        changed = copy.deepcopy(row);mutate_actor(changed,0x82,b"\x40")
        with patch.object(runner.portal,"_read",side_effect=lambda c,a,n:replies[a]), \
             patch.object(runner,"observe_native",return_value=changed), \
             patch.object(runner.boxes,"observe_owned",return_value=pub), \
             self.assertRaisesRegex(subject.debug.DebugError,"changed"):
            runner.probe_reploid_exclusion(control,{"reploid059_guards":proof["source_guards"]},row,pub,evidence,{})

    def test_bad_actor_refused_before_any_pointer_probe(self):
        row,pub,evidence,proof = fixture();mutate_actor(row,0x68,struct.pack("<I",0x801FFFF0))
        with patch.object(runner.portal,"_read") as read,self.assertRaises(subject.debug.DebugError):
            runner.probe_reploid_exclusion(Mock(),{"reploid059_guards":proof["source_guards"]},row,pub,evidence,{})
        read.assert_not_called()

    def test_critical_change_during_held_right_stops_and_neutralizes_owned_seat(self):
        row,pub,evidence,proof = fixture()
        proof.update(body_evidence=evidence,
                     actor_baseline=subject.actor_state(subject.find_actor(row))[1])
        trial=runner.Trial(Mock(),Mock(),Path("G:/unused"),{}, {},{},1,1)
        trial.reploid_scope=proof
        changed=copy.deepcopy(row);mutate_actor(changed,7,b"\2")
        trial.sample=Mock(return_value=(changed,pub))
        actual=dict(body=evidence,damage=[dict(hex="f6ef1326",pointer=0x801F3F50),{}])
        with patch.object(runner.boxes,"observe_owned",return_value=pub), \
             patch.object(runner,"current_boxes",return_value=actual), \
             patch.object(runner,"observe_native",return_value=row), \
             patch.object(runner,"probe_reploid_exclusion",return_value=proof), \
             patch.object(runner,"outside",return_value={}), \
             self.assertRaisesRegex(subject.debug.DebugError,"eligible idle"):
            trial.hold(1,24,"native Right",activation=True)
        self.assertEqual(trial.control.call_args_list[-1].args,("clear_input",))
        self.assertEqual(trial.control.call_args_list[-1].kwargs,dict(port=2))
        self.assertEqual(len(trial.report["input_windows"][0]["samples"]),1)

    def test_retained_actual_metadata_stays_insufficient(self):
        receipt=json.loads((ROOT/"docs/evidence/mmx6-portal/reploid059-preflight-v17.json").read_bytes())
        self.assertEqual(receipt["original_status"],"failed")
        self.assertEqual(receipt["nearby_actor"]["origin"],subject.RECORD)
        self.assertEqual(receipt["nearby_actor"]["address"],subject.POOL+subject.STRIDE)
        with self.assertRaisesRegex(subject.debug.DebugError,"full A4"):
            subject.actor_state(receipt["nearby_actor"])
        self.assertEqual(receipt["classification"],"unverified_missing_live_fields_not_a_mechanic_failure")

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),"Supply original EXE/raw BIN")
    def test_original_code_guards_and_exact_source_record_table(self):
        sources=runner.setup.load_sources(Path(os.environ["MMX6_CONTENT_EXE"]),Path(os.environ["MMX6_CONTENT_DISC"]))
        result=subject.source_guards(sources)
        self.assertEqual(result["dispatch"]["entry4"],0x8004F834)
        self.assertEqual(result["placement"]["hex"],subject.AUTHORED.hex())
        bad=dict(sources);bad["member"]=bytes(len(sources["member"]))
        with self.assertRaisesRegex(subject.debug.DebugError,"member6 identity"):
            subject.source_guards(bad)
        # Execute the untouched original horizontal prefix at every proposed
        # coordinate/facing. Near-contact cases prove strict radius-sum19 and
        # prevent a constant-false emulator from making the exclusion pass.
        for x in range(subject.MIN_X,subject.MAX_X+1):
            for facing in (0,0x40,0x41):
                self.assertFalse(original_horizontal_overlap(sources["exe"],x,facing),(x,facing))
        for offset,expected in ((-20,False),(-19,False),(-18,True),(0,True),(18,True),(19,False),(20,False)):
            self.assertEqual(original_horizontal_overlap(sources["exe"],subject.X+offset),expected,offset)
        for record in (subject.AUTHORED,subject.ALLOCATED):
            for mode in range(4):
                after,result,writes=native_record_state(sources["exe"],record,mode)
                self.assertEqual((after,result,writes),(record,0,[]))


if __name__ == "__main__":
    unittest.main()
