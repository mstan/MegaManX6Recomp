"""Original-source and adversarial native lookup tests; no game is launched."""
import copy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import audit_mmx6_recycle_terrain as audit
import test_mmx6_coop_recycle_portal as portal_fixture

ROOT=Path(__file__).resolve().parents[1]


def terrain(code=0x38):
    layout=bytes((1,0,1))
    blocks=bytearray(1024)
    for at in range(512,1024,2):struct.pack_into("<H",blocks,at,0xC001)
    return audit.Terrain(layout,bytes(blocks),bytes((0,0,0,0,code,0,0,0)),1,1)


def body(x=100,y=120,facing=0):
    data=bytearray(0x158);data[0]=1;data[0x15]=facing
    struct.pack_into("<I",data,0x68,0x80073D54)
    struct.pack_into("<h",data,0xA,x);struct.pack_into("<h",data,0xE,y)
    return data


class RecycleTerrainTests(unittest.TestCase):
    def test_original_selected_inputs_reproduce_durable_audit_and_scoped_reads(self):
        exe,disc=os.environ.get("MMX6_CONTENT_EXE"),os.environ.get("MMX6_CONTENT_DISC")
        if not exe or not disc:self.skipTest("Supply original MMX6_CONTENT_EXE and MMX6_CONTENT_DISC")
        calls=[];extent=audit.content.RawDisc.extent
        def observed(reader,lba,size):
            calls.append((lba,size));return extent(reader,lba,size)
        with patch.object(audit.content.RawDisc,"extent",observed):
            report=audit.audit(Path(exe),Path(disc))
        self.assertEqual(calls,[(211185,1665024),(211998,4096),(217680,937984)])
        self.assertEqual(report,json.loads((ROOT/"docs/COOP_RECYCLE_TERRAIN_AUDIT.json").read_text(encoding="utf-8")))
        self.assertEqual(report["checkpoint"]["player"],dict(x=1728,y=1456))
        self.assertEqual([r["sampled_tiles"]for r in report["findings"]],[34,456])
        self.assertEqual(report["downward_dispatch"],{"00":"8002FBCC","38":"8002FBA4","39":"8002FBA4"})
        self.assertEqual(report["left_dispatch"],{"38":"8003065C","39":"8003065C"})
        self.assertEqual(report["recommended_actions"],[])
        self.assertEqual(report["proven_safe_positions"],[])
        self.assertEqual((report["local_coop"],report["netplay"]),("unverified","unverified"))
        self.assertEqual({r["index"]for r in report["nearby_authored_objects"]},{2,18,19,117})
        _,_,native,_=audit.load_original(Path(exe),Path(disc))
        self.assertEqual(native.query(1552,1584)["code"],0)
        self.assertEqual(native.query(1552,1616)["code"],0x38)
        self.assertEqual(native.query(1568,1456)["code"],0x38)
        self.assertEqual(native.query(1728,1478)["code"],0)
        envelope=report["source_probe_envelope"]
        self.assertEqual(envelope["body_center_x_inclusive"],[1467,1557])
        self.assertEqual((envelope["predicted_native_contact_center_y"],envelope["one_pixel_air_center_y"]),(1594,1593))
        self.assertEqual(report["existing_offline_setup"]["command"],4)
        self.assertEqual(report["existing_offline_setup"]["seats"]["1"],"privateP2")

    def test_descriptor_mask_empty_cell_and_three_layer_bounds(self):
        source=terrain()
        hit=source.query(17,31)
        self.assertEqual((hit["tile"],hit["code"]),(1,0x38))
        empty=source.query(17,31,1)
        self.assertEqual((empty["cell"],empty["code"]),(0,0))
        self.assertIsNone(empty["tile"])
        self.assertEqual(source.query(255,255,2)["code"],0x38)
        for x,y in ((-1,0),(0,-1),(256,0),(0,256),(-32768,32767)):
            self.assertEqual(source.query(x,y)["code"],0)
            self.assertIsNone(source.query(x,y)["cell"])

    def test_native3b_remap_does_not_reclassify_other_codes_as_safe(self):
        self.assertEqual((terrain(0x3B).query(0,0)["raw_code"],terrain(0x3B).query(0,0)["code"]),(0x3B,0x38))
        for value in (0,1,0x10,0x21,0x39,0xFF):
            row=terrain(value).query(0,0)
            self.assertEqual(row["code"],value)
            self.assertEqual(row["runtime_status"],"unverified")
            self.assertNotIn("safe",row)

    def test_bad_extents_references_and_arguments_refuse(self):
        valid=terrain()
        cases=[(valid.layout[:-1],valid.metatiles,valid.descriptors,1,1),
            (bytes((2,0,0)),valid.metatiles,valid.descriptors,1,1),
            (valid.layout,valid.metatiles[:-1],valid.descriptors,1,1),
            (valid.layout,valid.metatiles,valid.descriptors[:-1],1,1),
            (valid.layout,valid.metatiles,bytes(4),1,1),
            (valid.layout,valid.metatiles,valid.descriptors,True,1)]
        for args in cases:
            with self.subTest(args=(len(args[0]),len(args[1]),len(args[2]),args[3])):
                with self.assertRaises(ValueError):audit.Terrain(*args)
        for args in ((32768,0),(0,-32769),(0,0,3),(0,0,-1),(True,0),(0,0,1.0)):
            with self.assertRaises(ValueError):valid.query(*args)

    def test_exact_actual_box_offsets_and_native_full_byte_facing(self):
        native=terrain()
        shape=struct.pack("<bbBB",3,-2,11,19)
        forward=audit.foot_probes(body(),shape,native)
        self.assertEqual([(r["x"],r["y"])for r in forward["probes"]],[(92,137),(113,137),(103,137)])
        for facing in (1,0x40,0xFF):
            reverse=audit.foot_probes(body(facing=facing),shape,native)
            self.assertEqual([(r["x"],r["y"])for r in reverse["probes"]],[(86,137),(107,137),(97,137)])
        self.assertEqual(forward["status"],"source_samples_only_not_grounded_or_safe")
        self.assertNotIn("grounded",forward)

    def test_probe_signed16_wrap_missing_body_box_and_empty_shape(self):
        sample=audit.foot_probes(body(32767,32767),struct.pack("<bbBB",2,2,11,19),terrain())
        self.assertEqual([(r["x"],r["y"])for r in sample["probes"]],[(32758,-32748),(-32757,-32748),(-32767,-32748)])
        source=body()
        invalid=[(source[:-1],bytes((0,3,11,19))),(source,bytes(3)),(bytes(0x158),bytes((0,3,11,19))),
                 (source,bytes((0,3,0,19))),(source,bytes((0,3,11,0)))]
        zero=copy.copy(source);struct.pack_into("<I",zero,0x68,0)
        invalid.append((zero,bytes((0,3,11,19))))
        for player,shape in invalid:
            with self.assertRaises(ValueError):audit.foot_probes(player,shape,terrain())

    def test_static_probe_requires_full_clear_rectangle_exact_floor_and_box(self):
        blocks=bytearray(1024)
        for col in range(16):struct.pack_into("<H",blocks,512+5*32+col*2,1)
        desc=bytes((0,0,0,0,0x38,0,0,0))
        source=audit.Terrain(bytes([1]*147),bytes(blocks),desc,7,7)
        shape=struct.pack("<bbBB",0,3,11,19)
        row=audit.portal_probe_envelope(source,shape)
        self.assertEqual(row["clear_rectangle"],dict(x=[1456,1567],y=[1577,1615]))
        self.assertNotIn("safe",row)
        with self.assertRaises(ValueError):audit.portal_probe_envelope(source,bytes((0,2,11,19)))
        with self.assertRaises(ValueError):audit.portal_probe_envelope(terrain(),shape)
        with self.assertRaises(ValueError):audit.portal_probe_envelope(
            audit.Terrain(source.layout,source.metatiles,bytes((0,0,0,0,0x39,0,0,0)),7,7),shape)
        struct.pack_into("<H",blocks,512+3*32+11*2,1) # Obstruction within the clear body rectangle.
        with self.assertRaises(ValueError):audit.portal_probe_envelope(
            audit.Terrain(source.layout,bytes(blocks),desc,7,7),shape)

    def test_read_only_preflight_retains_native_layout_without_placement_approval(self):
        original=terrain()
        raw=portal_fixture.native()
        at=0x80097438-audit.portal.BASE
        raw[at:at+len(original.layout)]=original.layout
        calls=[]
        def request(command,**fields):
            calls.append((command,fields));return portal_fixture.response(audit.portal.BASE,raw)
        row=audit.observe_source_preflight(request,original)
        self.assertEqual(calls,[("read_ram",dict(addr=hex(audit.portal.BASE),len=audit.portal.SIZE))])
        self.assertTrue(row["live_layout"]["matches_initial_original"])
        self.assertIsNone(row["source_probe_envelope"]) # Synthetic code does not satisfy original native guard.
        self.assertIn("native",row)
        self.assertNotIn("safe_position",row)
        raw[at+1]^=1
        changed=audit.observe_source_preflight(request,original)
        self.assertFalse(changed["live_layout"]["matches_initial_original"])
        self.assertEqual(changed["live_layout"]["changed_indices"],[1])
        self.assertEqual(changed["status"],"read_only_partial_preflight_not_position_approval")

    def test_changed_original_identity_rejected_before_disc_read(self):
        exe=os.environ.get("MMX6_CONTENT_EXE")
        if not exe:self.skipTest("Supply original MMX6_CONTENT_EXE")
        data=bytearray(Path(exe).read_bytes());data[-1]^=1
        with tempfile.TemporaryDirectory() as folder:
            candidate=Path(folder)/"changed-SLUS_013.95";candidate.write_bytes(data)
            with patch.object(audit.content,"RawDisc") as reader:
                with self.assertRaisesRegex(ValueError,"original SLUS"):audit.load_original(candidate,Path("unused"))
                reader.assert_not_called()


if __name__ == "__main__":unittest.main()
