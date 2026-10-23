"""Pure offline portal runner boundaries; no runtime process, sockets or cards."""
import copy
import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

import qualify_mmx6_coop_recycle_portal as runner
from test_mmx6_coop_collision_boxes import publication as box_fixture
from test_mmx6_coop_recycle_portal import native as native_fixture


def publication(tick=7,timer=20,owner=0):
    raw = box_fixture()
    struct.pack_into("<I",raw,4,tick);struct.pack_into("<I",raw,0x88,tick*2)
    struct.pack_into("<I",raw,runner.boxes.HEADER+12,tick)
    struct.pack_into("<I",raw,36,timer);raw[0x3E]=owner
    for at,character,y in ((0x1800,0,1595),(0x100,1,1594)):
        raw[at+3]=1;raw[at+0x70]=8
        struct.pack_into("<ii",raw,at+8,1506<<16,y<<16)
        raw[at+0x18:at+0x20]=raw[at+8:at+16]
        struct.pack_into("<I",raw,at+0x54,0x801EEA04 if character else 0x801F3F50)
        struct.pack_into("<I",raw,at+0x68,0x80073D54 if character else 0x80073D50)
    for i,(pointer,origin,value) in enumerate(((0,0,bytes(4)),
            (0x801EEA04,2,bytes((246,239,21,39))),
            (0x80073D54,1,bytes((0,3,11,19))))):
        struct.pack_into("<I",raw,0x100+runner.boxes.FIELDS[i][1],pointer)
        struct.pack_into("<II4s",raw,runner.boxes.HEADER+16+i*12,pointer,origin,value)
    raw[8:16]=raw[0x108:0x110]
    return runner.boxes.parse_publication(bytes(raw))


def native():
    raw = native_fixture()
    def put(address,data):raw[address-runner.portal.BASE:address-runner.portal.BASE+len(data)]=data
    put(runner.portal.PLAY+0x1D,b"\2")
    player = bytes.fromhex(publication()["p1_body_hex"])
    put(runner.portal.PLAYER,player)
    actor=bytearray(raw[:runner.portal.STRIDE])
    struct.pack_into("<ii",actor,8,1552<<16,1584<<16)
    struct.pack_into("<I",actor,0x50,0x800F38BC)
    struct.pack_into("<I",actor,0x68,0x800F38B8)
    raw[:len(actor)]=actor
    capsule=bytearray(runner.setup.CAPSULE_STRIDE)
    capsule[0]=capsule[3]=capsule[4]=1;capsule[1:3]=bytes((26,4))
    struct.pack_into("<ii",capsule,8,1424<<16,1604<<16)
    struct.pack_into("<I",capsule,0x10,runner.setup.CAPSULE_RECORD)
    put(runner.setup.CAPSULE_POOL,capsule)
    return raw


def response(address,data):return dict(ok=True,addr=hex(address),len=len(data),hex=bytes(data).hex())


def observed():
    raw=native()
    row=runner.observe_native(lambda command,**fields:response(int(fields["addr"],0),raw))
    row["native"]["source_closure_present"]=True # Explicit synthetic source gate, not real original evidence.
    return row


class CommandTests(unittest.TestCase):
    def test_only_atomic_two_seat_payload_then_command_byte(self):
        control=Mock(return_value=dict(ok=True,active=0,rollback=0,desync=0))
        client=Mock();client.read.return_value=b"\0"
        plan=dict(conditional_both_seat_probe=dict(x=1506,y=1593,seat=2,command=4),source_miss_intervals=[[1489,1523]])
        receipt={};runner.place_both(control,client,plan,receipt)
        writes=[c.kwargs for c in control.call_args_list if c.args==("write_ram",)]
        self.assertEqual(len(writes),10)
        self.assertEqual(writes[0],dict(addr=hex(runner.debug.DIAGNOSTIC_ADDRESS+0x52),val="0x2"))
        self.assertEqual(writes[-1],dict(addr=hex(runner.debug.DIAGNOSTIC_ADDRESS+0x50),val="0x4"))
        self.assertEqual(set(int(w["addr"],0)-runner.debug.DIAGNOSTIC_ADDRESS for w in writes),
                         {0x50,0x52,*range(0x54,0x5C)})
        self.assertTrue(receipt["ordinary_input_evidence_tainted"])

    def test_invalid_command_or_payload_rejected_before_any_rpc(self):
        for opcode,payload in ((1,{}),(4,{0x52:1}),(8,dict(enumerate(bytes((4,0,3,1,0,0,0)),0x51))),
                               (4,{0x54:1}),(True,{})):
            control=Mock()
            with self.assertRaises(runner.debug.DebugError):runner.command(control,Mock(),opcode,payload,{})
            control.assert_not_called()

    def test_online_pending_and_bad_floor_refused_without_write(self):
        good=dict(conditional_both_seat_probe=dict(x=1506,y=1593,seat=2,command=4),source_miss_intervals=[[1489,1523]])
        for status,pending in ((dict(ok=True,active=1,rollback=0,desync=0),b"\0"),
                               (dict(ok=True,active=0,rollback=0,desync=0),b"\4")):
            control=Mock(return_value=status);client=Mock();client.read.return_value=pending
            with self.assertRaises(runner.debug.DebugError):runner.place_both(control,client,good,{})
            self.assertFalse(any(c.args==("write_ram",) for c in control.call_args_list))
        for x,y in ((1530,1593),(1506,1594),(2000,1593)):
            plan=copy.deepcopy(good);plan["conditional_both_seat_probe"].update(x=x,y=y)
            with self.assertRaises(runner.debug.DebugError):runner.place_both(Mock(),Mock(),plan,{})

    def test_last_precommit_death_check_prevents_command_after_payload(self):
        control=Mock(return_value=dict(ok=True,active=0,rollback=0,desync=0));client=Mock();client.read.return_value=b"\0"
        plan=dict(conditional_both_seat_probe=dict(x=1506,y=1593,seat=2,command=4),source_miss_intervals=[[1489,1523]])
        with self.assertRaisesRegex(runner.debug.DebugError,"dying"):
            runner.place_both(control,client,plan,{},before_commit=Mock(side_effect=runner.debug.DebugError("P2 dying")))
        writes=[c for c in control.call_args_list if c.args==("write_ram",)]
        self.assertEqual(len(writes),9)
        self.assertNotIn(hex(runner.debug.DIAGNOSTIC_ADDRESS+0x50),[c.kwargs["addr"]for c in writes])

    def test_initializer_receipt_is_not_authored_readiness_and_conflicting_nonce_rejected(self):
        before=dict(generation=2,state=0)
        target=dict(stage=4,section=0,checkpoint=2,record="80072444")
        completion=dict(generation=3,nonce=1,state=3,stage=4,section=0,checkpoint=2,
                        record=target["record"],initializer_entries=1,tainted=1)
        with patch.object(runner.checkpoint,"fixture_status",side_effect=[before,completion]), \
             patch.object(runner,"command"),patch.object(runner.time,"monotonic_ns",return_value=1):
            receipt={};runner.request_checkpoint(Mock(),Mock(),target,receipt,1)
        self.assertEqual(receipt["status"],"initializer_completed_readiness_pending")
        self.assertFalse(receipt["ordinary_authored_checkpoint_readiness"])
        completion["nonce"]=2
        with patch.object(runner.checkpoint,"fixture_status",side_effect=[before,completion]), \
             patch.object(runner,"command"),patch.object(runner.time,"monotonic_ns",return_value=1), \
             self.assertRaisesRegex(runner.debug.DebugError,"another"):
            runner.request_checkpoint(Mock(),Mock(),target,{},1)


class ProvenanceTests(unittest.TestCase):
    def test_exact_private_source_and_legitimate_entry_null(self):
        control=Mock()
        def read(control,address,size):return {runner.X_BODY[0]:runner.X_BODY[1],0x801F3F50:bytes((246,239,19,38))}[address]
        def original(sources,owner,pointer):return bytes((246,239,21 if owner else 19,39 if owner else 38))
        with patch.object(runner.portal,"_read",side_effect=read),patch.object(runner,"original_box",side_effect=original):
            result=runner.current_boxes(control,{},publication(),settled=True)
            self.assertEqual(result["damage"][1]["origin"],"private_overlay")
            p=publication();body=bytearray.fromhex(p["p2_body_hex"]);struct.pack_into("<I",body,0x54,0)
            p["p2_body_hex"]=body.hex();p["boxes"]["damage"]=dict(pointer=0,available=False,origin="unavailable",hex=None)
            self.assertIsNone(runner.current_boxes(control,{},p)["damage"][1])
            with self.assertRaises(runner.debug.DebugError):runner.current_boxes(control,{},p,settled=True)

    def test_wrong_private_bank_missing_bytes_dying_or_menu_never_falls_back(self):
        for change in ("wrong_bank","missing","dying","menu"):
            p=publication()
            if change=="wrong_bank":p["boxes"]["damage"]["origin"]="native_ram"
            elif change=="missing":p["boxes"]["damage"]["available"]=False
            elif change=="dying":p["observation"]["lifecycle"]=[0,1]
            else:p["observation"]["scene_owner"]=1
            def read(control,address,size):return {runner.X_BODY[0]:runner.X_BODY[1],0x801F3F50:bytes((246,239,19,38))}[address]
            def original(sources,owner,pointer):return bytes((246,239,21 if owner else 19,39 if owner else 38))
            with patch.object(runner.portal,"_read",side_effect=read), \
                 patch.object(runner,"original_box",side_effect=original), \
                 self.assertRaisesRegex(runner.debug.DebugError,"provenance|dying|settle"):
                runner.current_boxes(Mock(),{},p,settled=True)

    def test_p1_misses_are_native_only_and_overlap_or_uninitialized_refused(self):
        row=observed();box=bytes((246,239,19,38))
        result=runner.outside(row,box,0x801F3F50)
        self.assertTrue(result["p1_capsule_miss"] and result["p1_portal_miss"])
        self.assertIn("no P2",result["attribution"])
        for x in (1467,1530):
            modified=copy.deepcopy(row);modified["native"]["resident_player"]["x_raw"]=x<<16
            with self.assertRaises(runner.debug.DebugError):runner.outside(modified,box,0x801F3F50)
        with self.assertRaisesRegex(runner.debug.DebugError,"pointer changed"):
            runner.outside(row,box,0x801F3F54)
        row["native"]["portal"]["phase"]=0
        with self.assertRaises(runner.debug.DebugError):runner.outside(row,box,0x801F3F50)

    def test_visibility_needs_actual_display_view_and_both_resource_pointers(self):
        row=observed();row["native"]["camera"].update(x=1264,y=1424)
        pub=publication();gpu=dict(disabled=0,width=320,height=240)
        for field in ("p1_body_hex","p2_body_hex"):
            body=bytearray.fromhex(pub[field]);struct.pack_into("<II",body,0x38,0x801F0000,0x801F1000);pub[field]=body.hex()
        self.assertEqual(runner.viewport(row,pub,gpu)["artwork_review"],"pending")
        with self.assertRaises(runner.debug.DebugError):runner.viewport(row,pub,dict(gpu,disabled=1))
        row["native"]["camera"]["x"]=1568
        with self.assertRaisesRegex(runner.debug.DebugError,"viewport"):runner.viewport(row,pub,gpu)

    def test_disclosed_source_floor_keeps_original_authored_x_readiness_false(self):
        row=observed()["native"];pub=publication()
        camera=bytearray(0x54)
        struct.pack_into("<h",camera,0xA,1264);struct.pack_into("<h",camera,0xE,1424)
        struct.pack_into("<4h",camera,0x1C,1264,320,1424,1424)
        target=dict(stage=4,section=0,checkpoint=2,player=dict(x=480),
                    camera=dict(x=320,y=1424,min_x=320,max_x=1264,min_y=1424,max_y=1424))
        checks=runner.checkpoint.reduce_entry_readiness(target,6,pub["observation"],
            bytes.fromhex(row["play_hex"])[:0x1E],bytes.fromhex(row["resident_player"]["raw_hex"])+camera,
            dict(disabled=0,width=320,height=240,ws=dict(x_margin=0)))
        self.assertFalse(checks["p1_at_authored_x"])
        self.assertTrue(all(value for key,value in checks.items() if key!="p1_at_authored_x"),checks)

    def test_full_asset_mismatch_and_unknown_actor_retained(self):
        terrain=Mock(layout=bytes(528),metatiles=b"M"*87040,descriptors=b"D"*8000)
        data={0x1F800004:struct.pack("<III",*runner.SCRATCH)}
        row=observed();row["live_layout_hex"]=terrain.layout.hex()
        def read(control,address,size):
            if address in data:return data[address]
            for base,payload in ((runner.SCRATCH[1],terrain.metatiles),(runner.SCRATCH[2],terrain.descriptors)):
                if base<=address<base+len(payload):return payload[address-base:address-base+size]
            self.fail("Unexpected asset read")
        receipt={}
        with patch.object(runner.portal,"_read",side_effect=read):
            runner.source_preflight(Mock(),dict(terrain=terrain),row,receipt)
        self.assertEqual([a["bytes"]for a in receipt["collision_assets"]],[87040,8000])
        self.assertTrue(all(a["matches_source"]for a in receipt["collision_assets"]))
        with patch.object(runner.portal,"_read",side_effect=lambda c,a,n: data[a] if a in data else b"?"*n):
            with self.assertRaises(runner.debug.DebugError):runner.source_preflight(Mock(),dict(terrain=terrain),row,{})
        row["nearby_actors"].append(dict(known_source_actor=False))
        with self.assertRaisesRegex(runner.debug.DebugError,"nearby"):
            runner.source_preflight(Mock(),dict(terrain=terrain),row,{})


class InputTests(unittest.TestCase):
    def trial(self):
        return runner.Trial(Mock(),Mock(),Path("G:/unused"),{}, {},{},1,1)

    def test_input_is_held_until_native_window_then_always_released(self):
        trial=self.trial();start=publication();end=publication(10,23)
        trial.sample=Mock(return_value=(observed(),end))
        with patch.object(runner.boxes,"observe_owned",return_value=start):trial.hold(0,3,"independent")
        calls=trial.control.call_args_list
        self.assertIn((("press",),dict(port=1,buttons=0xFFDF,frames=0)),[(c.args,c.kwargs)for c in calls])
        self.assertEqual((calls[-1].args,calls[-1].kwargs),(("clear_input",),dict(port=1)))
        self.assertEqual(trial.report["input_windows"][0]["stop"],"bounded_native_world_window")

    def test_scene_and_counter_failures_keep_partial_window_and_release(self):
        for end in (publication(10,19),publication(10,23,owner=1)):
            trial=self.trial();trial.sample=Mock(return_value=(observed(),end))
            with patch.object(runner.boxes,"observe_owned",return_value=publication()),self.assertRaises(runner.debug.DebugError):
                trial.hold(1,3,"negative")
            self.assertEqual(trial.control.call_args_list[-1].args,("clear_input",))
            self.assertEqual(len(trial.report["input_windows"][0]["samples"]),1)
        trial=self.trial();trial.sample=Mock(return_value=(observed(),publication()))
        with patch.object(runner.boxes,"observe_owned",return_value=publication()), \
             patch.object(runner.time,"monotonic",side_effect=[0,0,2]),patch.object(runner.time,"sleep"), \
             self.assertRaisesRegex(runner.debug.DebugError,"timed out"):
            trial.hold(1,3,"stalled")
        self.assertEqual(trial.control.call_args_list[-1].args,("clear_input",))

    def test_original_error_preserved_when_release_also_fails(self):
        trial=self.trial();trial.sample=Mock(side_effect=ValueError("native failed"))
        trial.control.side_effect=lambda command,**fields: (_ for _ in ()).throw(RuntimeError("release failed")) if command=="clear_input" else {}
        with patch.object(runner.boxes,"observe_owned",return_value=publication()),self.assertRaisesRegex(ValueError,"native failed"):
            trial.hold(0,3,"release negative")
        self.assertEqual(trial.report["input_cleanup_errors"][0]["original_error"],"native failed")

    def test_incomplete_transition_never_infers_load_or_both_arrivals(self):
        row=observed()["native"]
        reduced=runner.portal.reduce_native_transition([row],{})
        self.assertFalse(reduced["checks"]["destination_native_ready_seen"])
        self.assertFalse(reduced["checks"]["published_both_arrivals"])

    def test_waits_for_original_enrollment_before_any_relocation(self):
        trial=self.trial();old=publication();old["observation"]["enrolled"]=0
        enrolled=publication(8,21)
        body=bytearray.fromhex(enrolled["p2_body_hex"]);body[5]=0;body[0x70]=0
        struct.pack_into("<I",body,0x54,0);enrolled["p2_body_hex"]=body.hex()
        with patch.object(runner.boxes,"observe_owned",side_effect=[old,enrolled]),patch.object(runner.time,"sleep"):
            result=trial.wait_entry_enrollment()
        self.assertEqual(result["observation"]["enrolled"],1)
        self.assertEqual(len(trial.report["entry_enrollment_wait"]),2)
        trial.control.assert_not_called() # P2 native entry remains untouched.


class OptionsTests(unittest.TestCase):
    def test_invalid_options_refused_before_any_launch(self):
        base=["--candidate","G:/unused","--original-exe","original","--original-disc","original.bin", "--expected-exe-sha256","a"*64]
        for extra in (["--entry-timeout","nan"],["--entry-timeout","181"],["--progress-timeout","0"],
                      ["--expected-exe-sha256","bad"],["--port","0"],["--original-disc","original.cue"]):
            p=runner.make_parser()
            with patch("sys.stderr",new=io.StringIO()),self.assertRaises(SystemExit):runner.validate_options(p,p.parse_args(base+extra))

    def test_freshness_refusal_precedes_any_runner_overwrite_or_launch(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"]) as folder:
            root=Path(folder);existing=root/"runner-source.py";existing.write_bytes(b"prior evidence")
            args=runner.make_parser().parse_args(["--candidate",str(root),"--original-exe",str(existing),
                "--original-disc",str(existing),"--expected-exe-sha256","a"*64])
            with patch.object(runner.setup,"load_sources",return_value={}),patch.object(runner.portal,"source_plan",return_value={}), \
                 patch.object(runner.preparation,"local_output",return_value=root), \
                 patch.object(runner.offline,"pristine_candidate",side_effect=ValueError("retain prior")), \
                 patch.object(runner.baseline,"run") as launch,self.assertRaisesRegex(ValueError,"retain prior"):
                runner.run(args)
            launch.assert_not_called();self.assertEqual(existing.read_bytes(),b"prior evidence")

    def test_runtime_cue_must_reference_exact_single_original_raw_disc(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TEMP"]) as folder:
            root=Path(folder);exe=root/"original.exe";exe.write_bytes(b"source")
            disc=root/"source.bin";disc.write_bytes(b"source")
            cue=root/"source.cue";cue.write_text('FILE "source.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n')
            config=root/"game.toml"
            config.write_text('[game]\nexe='+repr(exe.as_posix())+'\ndisc='+repr(cue.as_posix())+'\n')
            self.assertEqual(runner.runtime_sources(root,exe,disc)["raw_bin"],str(disc.resolve()))
            cue.write_text('FILE "source.bin" BINARY\n TRACK 01 AUDIO\n')
            with self.assertRaisesRegex(runner.debug.DebugError,"single-track"):runner.runtime_sources(root,exe,disc)
            other=root/"other.bin";other.write_bytes(b"other")
            cue.write_text('FILE "other.bin" BINARY\n TRACK 01 MODE2/2352\n')
            with self.assertRaisesRegex(runner.debug.DebugError,"differs"):runner.runtime_sources(root,exe,disc)


if __name__ == "__main__":unittest.main()
