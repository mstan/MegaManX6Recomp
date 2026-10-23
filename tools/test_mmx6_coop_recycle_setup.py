"""Source differential geometry/placement tests; no native game, inputs or writes."""
import json
import os
from pathlib import Path
import random
import struct
import unittest

import mmx6_coop_recycle_setup as setup
import test_mmx6_coop_recycle_portal as fixture

ROOT=Path(__file__).resolve().parents[1]


def actor(x=1552,y=1584,facing=0,layer=0):
    return dict(x=x,y=y,facing=facing,layer=layer,attack_pointer=0x800F38BC)


def player(x=1506,y=1595,facing=0):
    return dict(x=x,y=y,facing=facing,iframe=0,damage_pointer=0x801F3F50)


def native_predicate(exe,entry,a,p,abox,pbox,camera=(0,0)):
    """Execute pinned original pure contact or capsule admission prefix.

    Small integer/branch interpreter for these source tests only; stops before
    capsule's first side-effectful native call. No runtime APIs are invoked.
    """
    mem={};regs=[0]*32;regs[4]=0x800C1220;regs[5]=0x800970A0
    regs[29]=0x801FF000;regs[31]=0x80000000
    def put(address,data):mem.update((address+i,b)for i,b in enumerate(data))
    def store_actor(address,row):
        put(address,bytes(0x158));put(address+0xA,struct.pack("<h",row["x"]));put(address+0xE,struct.pack("<h",row["y"]))
        put(address+0x15,bytes((row["facing"],)))
    store_actor(regs[4],a);store_actor(regs[5],p)
    put(regs[4]+0x14,struct.pack("<b",a["layer"]));put(regs[5]+0x61,bytes((p["iframe"],)))
    put(regs[4]+0x50,struct.pack("<I",0x80071000 if a["attack_pointer"] else 0))
    put(regs[5]+0x54,struct.pack("<I",0x80071004 if p["damage_pointer"] else 0))
    put(0x80071000,abox or bytes(4));put(0x80071004,pbox or bytes(4))
    put(0x80097202,struct.pack("<h",camera[0]));put(0x80097206,struct.pack("<h",camera[1]))
    pc=entry;delayed=None;signed=lambda n:n-0x100000000 if n&0x80000000 else n
    for _ in range(256):
        if entry==0x80051924 and pc==0x800519C4:return True
        if pc==0x80000000:return bool(regs[2]) if entry==0x8002D654 else False
        lo,hi=(0x8002D654,0x8002D868) if entry==0x8002D654 else (0x80051924,0x80051A44)
        if not lo<=pc<hi or pc&3:raise ValueError("Native predicate PC escaped")
        word=exe.word(pc);op=word>>26;rs=(word>>21)&31;rt=(word>>16)&31;rd=(word>>11)&31
        sa=(word>>6)&31;fun=word&63;imm=word&0xFFFF;short=imm-0x10000 if imm&0x8000 else imm;target=None
        if word==0:pass
        elif op==0 and fun==0x21:regs[rd]=regs[rs]+regs[rt]
        elif op==0 and fun==0x23:regs[rd]=regs[rs]-regs[rt]
        elif op==0 and fun==0x2A:regs[rd]=int(signed(regs[rs])<signed(regs[rt]))
        elif op==0 and fun==0:regs[rd]=regs[rt]<<sa
        elif op==0 and fun==3:regs[rd]=signed(regs[rt])>>sa
        elif op==0 and fun==8:target=regs[rs]
        elif op==2:target=((pc+4)&0xF0000000)|((word&0x3FFFFFF)<<2)
        elif op in (4,5):
            if (regs[rs]==regs[rt])==(op==4):target=pc+4+short*4
        elif op==1:
            if (signed(regs[rs])>=0) if rt==1 else (signed(regs[rs])<0):target=pc+4+short*4
        elif op==6:
            if signed(regs[rs])<=0:target=pc+4+short*4
        elif op==9:regs[rt]=regs[rs]+short
        elif op==10:regs[rt]=int(signed(regs[rs])<short)
        elif op==12:regs[rt]=regs[rs]&imm
        elif op==15:regs[rt]=imm<<16
        elif op in (0x20,0x21,0x23,0x24,0x25):
            address=(regs[rs]+short)&0xFFFFFFFF;n=4 if op==0x23 else (2 if op in (0x21,0x25) else 1)
            value=int.from_bytes(bytes(mem[address+i]for i in range(n)),"little",signed=op in (0x20,0x21))
            regs[rt]=value
        elif op==0x2B:
            address=(regs[rs]+short)&0xFFFFFFFF
            if not 0x801FEF00<=address<0x801FF000:raise ValueError("Unexpected native memory write")
            put(address,struct.pack("<I",regs[rt]))
        else:raise ValueError(f"Unsupported native predicate opcode {word:08X}")
        if delayed is not None and target is not None:raise ValueError("Branch in delay slot")
        regs=[n&0xFFFFFFFF for n in regs];regs[0]=0
        pc=delayed if delayed is not None else pc+4;delayed=target
    raise ValueError("Native predicate instruction bound exhausted")


class RecycleSetupTests(unittest.TestCase):
    def test_capsule_exact_inclusive_edges_and_signed_wrap(self):
        self.assertTrue(setup.capsule_region(1424,1604,1467,1595))
        for dx in (-64,64):
            for dy in (-104,16):self.assertTrue(setup.capsule_region(1424,1604,1424+dx,1604+dy))
        for dx,dy in ((-65,0),(65,0),(0,-105),(0,17)):
            self.assertFalse(setup.capsule_region(1424,1604,1424+dx,1604+dy))
        self.assertTrue(setup.capsule_region(0,0,-32768,0)) # Exact original signed16 negation edge, never setup.
        with self.assertRaises(ValueError):setup.capsule_region(0,0,32768,0)

    def test_contact_pointer_iframe_unknown_box_and_camera_contract(self):
        abox=struct.pack("<bbBB",-18,-28,28,40);pbox=struct.pack("<bbBB",-10,-17,19,38)
        self.assertFalse(setup.contact(actor(),player(),abox,pbox)["hit"])
        self.assertTrue(setup.contact(actor(),player(1530),abox,pbox)["hit"])
        self.assertTrue(setup.contact(actor(),player(1530),abox,pbox)["horizontal"])
        for field in ("iframe","damage_pointer"):
            p=player(1530);p[field]=1 if field=="iframe" else 0
            self.assertFalse(setup.contact(actor(),p,None,None)["hit"])
        a=actor();a["attack_pointer"]=0
        self.assertFalse(setup.contact(a,player(),None,None)["hit"])
        with self.assertRaises(ValueError):setup.contact(actor(),player(),abox,None)
        with self.assertRaises(ValueError):setup.contact(actor(layer=-1),player(),abox,pbox)
        self.assertIn("actor_reference",setup.contact(actor(layer=-1),player(),abox,pbox,(0,0)))

    def test_contact_strict_edges_and_both_facing_bits(self):
        abox=struct.pack("<bbBB",0,0,10,10);pbox=struct.pack("<bbBB",0,0,5,5)
        self.assertTrue(setup.contact(actor(100,100),player(109,109),abox,pbox)["hit"])
        self.assertFalse(setup.contact(actor(100,100),player(110,109),abox,pbox)["hit"])
        self.assertFalse(setup.contact(actor(100,100),player(109,110),abox,pbox)["hit"])
        self.assertTrue(setup.contact(actor(100,100),player(96,96),abox,pbox)["hit"])
        self.assertFalse(setup.contact(actor(100,100),player(95,96),abox,pbox)["hit"])
        self.assertFalse(setup.contact(actor(100,100),player(96,95),abox,pbox)["hit"])
        self.assertFalse(setup.contact(actor(100,100),player(96,100,0x40),abox,pbox)["hit"])
        self.assertTrue(setup.contact(actor(100,100,0x40),player(96,100,0x40),abox,pbox)["hit"])

    def test_capsule_observer_ignores_stale_and_rejects_duplicate_or_wrong_origin_type(self):
        raw=fixture.native();at=setup.CAPSULE_POOL-setup.portal_source.BASE
        capsule=bytearray(setup.CAPSULE_STRIDE);capsule[0]=0x49;capsule[1]=26;capsule[2]=4;capsule[3]=capsule[4]=1
        struct.pack_into("<I",capsule,0x10,setup.CAPSULE_RECORD)
        struct.pack_into("<h",capsule,0xA,1424);struct.pack_into("<h",capsule,0xE,1604)
        raw[at:at+len(capsule)]=capsule
        row=setup.parse_capsule(raw);self.assertEqual((row["x"],row["y"]),(1424,1604));self.assertTrue(row["trigger_action_ready"])
        raw[at]&=~1;self.assertIsNone(setup.parse_capsule(raw))
        raw[at:at+len(capsule)]=capsule;raw[at+setup.CAPSULE_STRIDE:at+2*setup.CAPSULE_STRIDE]=capsule
        with self.assertRaises(ValueError):setup.parse_capsule(raw)
        raw[at+setup.CAPSULE_STRIDE]=0;raw[at+2]=5
        with self.assertRaises(ValueError):setup.parse_capsule(raw)
        with self.assertRaises(ValueError):setup.parse_capsule(raw[:-1])

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),"Supply original inputs")
    def test_actual_sources_complete_audit_solver_and_owner_specific_boxes(self):
        sources=setup.load_sources(Path(os.environ["MMX6_CONTENT_EXE"]),Path(os.environ["MMX6_CONTENT_DISC"]))
        report=setup.audit(sources)
        self.assertEqual(report,json.loads((ROOT/"docs/COOP_RECYCLE_TRIGGER_FREE_SETUP.json").read_text(encoding="utf-8")))
        plan=report["conditional_reference_setup"]
        self.assertEqual(plan["source_miss_intervals"],[[1489,1523]])
        self.assertEqual((plan["conditional_both_seat_probe"]["x"],plan["conditional_both_seat_probe"]["y"]),(1506,1593))
        self.assertEqual(plan["automatic_actions"],[]);self.assertEqual(plan["netplay"],"unverified")
        for character,pointer in ((1,0x801F3F50),(1,0x9F001000),(2,0x801F3F50),(0,0x801F3F51)):
            with self.assertRaises(ValueError):setup.source_box(sources,character,pointer)
        # Recalculate for changed actual damage shapes; do not retain an old midpoint.
        changed=setup.derive_setup(sources["terrain"],bytes((128,0,255,255)),bytes((128,0,255,255)))
        self.assertNotEqual(changed["source_miss_intervals"],plan["source_miss_intervals"])
        # A miss at final contact height cannot authorize the preceding fall.
        xb=struct.pack("<bbBB",-10,1,19,1);zb=struct.pack("<bbBB",-10,2,21,1)
        ab=struct.pack("<bbBB",-18,-28,28,40)
        self.assertFalse(setup.contact(actor(),player(1530,1595),ab,xb)["hit"])
        self.assertTrue(setup.contact(actor(),player(1530,1593),ab,xb)["hit"])
        falling=setup.derive_setup(sources["terrain"],xb,zb)
        self.assertFalse(any(low<=1530<=high for low,high in falling["source_miss_intervals"]))

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE"),"Supply original EXE")
    def test_calculators_match_original_native_instructions(self):
        exe=setup.checkpoint.original_executable(Path(os.environ["MMX6_CONTENT_EXE"]))
        rng=random.Random(0x51924)
        for index in range(600):
            a=actor(rng.randrange(1400,1580),rng.randrange(1530,1620),rng.choice((0,1,0x40,0xFF)),rng.choice((0,-1)))
            p=player(rng.randrange(1400,1580),rng.randrange(1530,1620),rng.choice((0,1,0x40,0xFF)))
            abox=struct.pack("<bbBB",rng.randrange(-30,20),rng.randrange(-30,20),rng.randrange(0,61),rng.randrange(0,61))
            pbox=struct.pack("<bbBB",rng.randrange(-30,20),rng.randrange(-30,20),rng.randrange(0,61),rng.randrange(0,61))
            camera=(rng.randrange(-20,20),rng.randrange(-20,20))
            if index%17==0:p["iframe"]=1
            if index%19==0:p["damage_pointer"]=0
            if index%23==0:a["attack_pointer"]=0
            expected=native_predicate(exe,0x8002D654,a,p,abox,pbox,camera)
            self.assertEqual(setup.contact(a,p,abox,pbox,camera)["hit"],expected,(a,p,abox,pbox))
        for px,py in [(1424+x,1604+y)for x in (-65,-64,0,64,65)for y in (-105,-104,0,16,17)]+[(-32768,0)]:
            a=actor(1424,1604);p=player(px,py)
            self.assertEqual(setup.capsule_region(a["x"],a["y"],px,py),
                native_predicate(exe,0x80051924,a,p,None,None))
        for px,py in ((-32768,0),(0,-32768)):
            a=actor(0,0);p=player(px,py)
            self.assertEqual(setup.capsule_region(0,0,px,py),native_predicate(exe,0x80051924,a,p,None,None))


if __name__=="__main__":unittest.main()
