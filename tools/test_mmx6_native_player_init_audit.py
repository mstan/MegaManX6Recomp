"""Pure source/signature checks; synthetic contexts never become runtime proof."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest

import audit_mmx6_native_player_init as subject


def context():
    regs=[0]*32;regs[16]=subject.PLAY;regs[29]=0x801FF000;regs[31]=0x8001E26C
    play=bytearray(0x39);play[0]=9
    return dict(address=subject.INIT,registers=regs,play=play,saved_major9_ra=0x8001E720)


def frames():
    saved=[0]*102;saved[31]=0x8001E720;saved[99]=0x8001E9EC;saved[100]=subject.PLAY
    return [dict(tag=29,bytes=16,words=1,saved_hex=struct.pack("<4I",0,2,0,0).hex()),
            dict(tag=1,bytes=408,words=1,saved_hex=struct.pack("<102I",*saved).hex())]


class InitAuditTests(unittest.TestCase):
    def test_canonical_source_signature_ignores_incoming_a0(self):
        c=context()
        for a0 in (0,subject.PLAY,0x800970A0,0xFFFFFFFF):
            c["registers"][4]=a0
            self.assertTrue(all(subject.canonical_entry_checks(**c).values()))

    def test_attract_projected_door_wrong_root_and_partial_context_refused(self):
        for change in ("attract","projected","door","stageA","nested","wrong_s0","badstack","phase","roster"):
            c=context()
            if change=="attract":c["registers"][31]=0x8001D584
            elif change=="projected":c["registers"][31]=0x80020C70
            elif change=="door":c["address"]=0x8003D308
            elif change=="stageA":c["play"][0]=10
            elif change=="nested":c["saved_major9_ra"]=0x8001EA18
            elif change=="wrong_s0":c["registers"][16]=0x800970A0
            elif change=="badstack":c["registers"][29]=0xA0000000
            elif change=="phase":c["play"][1]=2
            else:c["play"][0x38]=1
            with self.subTest(change=change):self.assertFalse(all(subject.canonical_entry_checks(**c).values()))

    def test_only_exact_two_primary_menu_frames_match_shape_not_retirement(self):
        self.assertTrue(subject.expected_retired_primary_menu_shape(frames()))
        for change in ("extra","tag","bytes","truncated","phase","projected","wrong_guest"):
            f=frames()
            if change=="extra":f.append(copy.deepcopy(f[-1]))
            elif change=="tag":f[0]["tag"]=13
            elif change=="bytes":f[1]["bytes"]=404
            elif change=="truncated":f[1]["saved_hex"]=f[1]["saved_hex"][:-2]
            elif change=="phase":f[0]["saved_hex"]=struct.pack("<4I",0,0,0,0).hex()
            else:
                raw=bytearray.fromhex(f[1]["saved_hex"])
                struct.pack_into("<I",raw,4*(31 if change=="projected" else 99),0x80020C70)
                f[1]["saved_hex"]=raw.hex()
            with self.subTest(change=change):self.assertFalse(subject.expected_retired_primary_menu_shape(f))

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),"Supply original source inputs")
    def test_actual_original_source_reproduces_frozen_census(self):
        actual=subject.audit(Path(os.environ["MMX6_CONTENT_EXE"]),Path(os.environ["MMX6_CONTENT_DISC"]))
        expected=json.loads((Path(__file__).resolve().parents[1]/"docs/COOP_NATIVE_PLAYER_INIT_CALLER_AUDIT.json").read_bytes())
        self.assertEqual(actual,expected)
        self.assertEqual(actual["members_scanned"],59)
        self.assertFalse(actual["retired_frame_shape"]["frame_payload_observed"])


if __name__=="__main__":unittest.main()
