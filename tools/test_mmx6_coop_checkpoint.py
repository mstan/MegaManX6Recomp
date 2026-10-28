"""Inventory/source guards and transaction failures; never native game proof."""
import contextlib
import io
import copy
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import coop_debug as debug
import mmx6_coop_checkpoint as checkpoint
from qualify_mmx6_coop_checkpoint import make_parser, validate_options

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT/"docs/COOP_X6_CONTENT.json"


def publication(state=0, *, generation=0, nonce=0, entries=0, reason=0):
    data = bytearray(32)
    struct.pack_into("<II", data, 0, checkpoint.CAPABILITY, generation)
    data[8:13] = bytes((state, reason, 0, 0, 1))
    struct.pack_into("<III", data, 16, nonce, entries, 0x8007212C)
    data[28] = int(state != 0)
    return bytes(data)


def settled_entry(tick=221):
    native=bytearray(0x1E);native[0]=10;native[0x1D]=1
    player_camera=bytearray(0x1AC)
    player_camera[0]=player_camera[3]=player_camera[4]=1;player_camera[5]=2
    player_camera[0x5C]=32;player_camera[0x70]=8
    for at in (8,0x18):struct.pack_into("<ii",player_camera,at,2112<<16,1115<<16)
    struct.pack_into("<h",player_camera,0x158+0xA,1968)
    struct.pack_into("<h",player_camera,0x158+0xE,944)
    struct.pack_into("<hhhh",player_camera,0x158+0x1C,5120,1968,944,944)
    struct.pack_into("<hhhh",player_camera,0x158+0x24,5120,1968,944,944)
    for at in (0,3,4,0x44):player_camera[0x158+at]=1
    player_camera[0x158+0x47]=4
    struct.pack_into("<h",player_camera,0x158+0x2C,96)
    row=dict(tick=tick,ready=1,enrolled=1,failed=0,mailbox=0,scene_owner=0,scene_phase=0,
        native_mode=10,native_phase=0,pause_owner=0,lifecycle=[0,0],players=[
            dict(active=1,character=0,state=1,action=2,hp=32,x_raw=2112<<16,y_raw=1115<<16),
            dict(active=1,character=1,state=1,action=2,hp=32,x_raw=2136<<16,y_raw=1115<<16)])
    gpu=dict(width=320,height=240,disabled=0,ws=dict(x_margin=0))
    return row,bytes(native),bytes(player_camera),gpu


class FrozenInventoryTests(unittest.TestCase):
    def test_loaded_recycle_origin_declares_only_existing_fixed_destination(self):
        record=json.loads((ROOT/'docs/COOP_HOST_LAB_CONTRACT.json').read_text(encoding='utf8'))
        change=record['title_changes_v35']
        self.assertEqual(change['additional_origin'],dict(option='recycle_cp2',stage=4,section=0,checkpoint=0))
        self.assertEqual(change['destination'],dict(index=27,stage=4,section=1,checkpoint=2,
            record='800724D4',nonce='4C435232'))
        self.assertEqual(change['snapshot_schema'],12)
        self.assertEqual(record['revision'],21)
        self.assertEqual(record['session']['title_compatibility'],'mmx6-x-zero-delay-v38')

    def test_recycle_lab_destination_is_existing_original_campaign_record(self):
        _, rows, sections = checkpoint.inventory(INVENTORY)
        target = checkpoint.select(rows, sections, 4, 1, 2)
        self.assertEqual(rows.index(target), 27)
        self.assertEqual(target['table'], '80073198')
        self.assertEqual(target['record'], '800724D4')
        self.assertEqual(target['player'], dict(x=5920, y=326))
        self.assertEqual(target['camera'], dict(x=5760, y=224, min_x=5760, max_x=5760, min_y=224, max_y=224))

    def test_turtloid_rain_cp1_is_only_original_campaign_reachability(self):
        _, rows, sections = checkpoint.inventory(INVENTORY)
        target = checkpoint.select(rows, sections, 6, 0, 1)
        self.assertEqual(rows.index(target), 32)
        self.assertEqual(target['table'], '800731B0')
        self.assertEqual(target['record'], '80072588')
        self.assertEqual(target['player'], dict(x=1120, y=464))
        self.assertEqual(target['camera'], dict(x=1056, y=464, min_x=1056, max_x=1296, min_y=464, max_y=464))

    def test_all115_retained_only94_campaign_tuples_permitted(self):
        _, rows, sections = checkpoint.inventory(INVENTORY)
        self.assertEqual((len(rows), len(sections)), (115, 23))
        accepted = 0
        for row in rows:
            if (row["stage"], row["section"]) in sections:
                self.assertEqual(checkpoint.select(rows, sections, row["stage"], row["section"], row["checkpoint"]), row)
                accepted += 1
            else:
                with self.assertRaisesRegex(ValueError, "namespace"):
                    checkpoint.select(rows, sections, row["stage"], row["section"], row["checkpoint"])
        self.assertEqual(accepted, 94)

    def test_range_membership_cannot_admit_noninventoried_tuple(self):
        _, rows, sections = checkpoint.inventory(INVENTORY)
        for values in ((0, 0, 3), (0, 1, 0), (23, 0, 0), (256, 0, 0), (-1, 0, 0), (True, 0, 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                checkpoint.select(rows, sections, *values)

    def test_truncated_source_rejected_before_inventory_interpretation(self):
        temporary_root = Path(os.environ["TEMP"]).resolve(strict=True)
        if temporary_root.drive.upper() == "C:":
            self.fail("Set process TEMP/TMP to a verified non-C test directory")
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            path = Path(directory)/"SLUS_013.95"
            path.write_bytes(b"PS-X EXE")
            with self.assertRaisesRegex(ValueError, "bounded original"):
                checkpoint.original_executable(path)

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE"), "Pinned original EXE not supplied")
    def test_generated_guard_header_matches_original_exe_and_frozen_inventory(self):
        exe = checkpoint.original_executable(Path(os.environ["MMX6_CONTENT_EXE"]))
        self.assertEqual(checkpoint.render_header(INVENTORY, exe),
                         (ROOT/"src/mods/mmx6_coop_checkpoint_data.h").read_text(encoding="utf-8"))


class CheckpointTransactionTests(unittest.TestCase):
    def setUp(self):
        _, rows, sections = checkpoint.inventory(INVENTORY)
        self.target = checkpoint.select(rows, sections, 0, 0, 1)
        self.calls = []
        self.receipt = {}
        self.next_tick = 10

    def run_request(self, statuses, *, active=0, clock=None, ticks=None):
        native_entry=settled_entry()
        publication_ticks=iter(ticks) if ticks else None
        class Reader:
            def __init__(inner):
                inner.states = iter(statuses)

            def read(inner, address, count):
                if (address, count) == (debug.DIAGNOSTIC_ADDRESS+0xA0, 32):
                    return next(inner.states)
                if (address, count) == (debug.DIAGNOSTIC_ADDRESS+0x50, 1):
                    return b"\0"
                if address == 0x800CCED0:
                    return native_entry[1]
                if (address,count)==(0x800970A0,0x1AC):
                    return native_entry[2]
                if address==checkpoint.CAMERA_SOURCE_SPANS[0][0]:return bytes(count)
                raise AssertionError((address, count))

        def control(command, **fields):
            self.calls.append((command, fields))
            if command=="netplay_status":return dict(active=active)
            if command=="gpu_state":return native_entry[3]
            return dict(ok=True)

        def observe(client):
            self.next_tick=next(publication_ticks) if publication_ticks else self.next_tick+1
            row=settled_entry(self.next_tick)[0]
            return SimpleNamespace(tick=self.next_tick,json=lambda:row)

        with patch.object(debug, "observe", observe), patch.object(checkpoint.time, "sleep"):
            if clock:
                with patch.object(checkpoint.time, "monotonic", side_effect=clock):
                    return checkpoint.enter_checkpoint(control, Reader(), self.target, self.receipt, nonce=77)
            return checkpoint.enter_checkpoint(control, Reader(), self.target, self.receipt, nonce=77)

    def test_payload_then_commit_only_mailbox_and_actual_completion_required(self):
        result = self.run_request([publication(), publication(1, generation=1, nonce=77),
                                  publication(2, generation=1, nonce=77, entries=1),
                                  publication(3, generation=1, nonce=77, entries=1),
                                  publication(3, generation=1, nonce=77, entries=1)],ticks=[215,220,221])
        writes = [fields for cmd, fields in self.calls if cmd == "write_ram"]
        self.assertEqual([int(w["addr"], 16) for w in writes],
                         list(range(debug.DIAGNOSTIC_ADDRESS+0x51, debug.DIAGNOSTIC_ADDRESS+0x58)) +
                         [debug.DIAGNOSTIC_ADDRESS+0x50])
        self.assertEqual(int(writes[-1]["val"], 16), 8)
        self.assertEqual(result["status"], "prerequisite_bypass_setup_completed_artwork_pending")
        self.assertTrue(result["prerequisite_bypass"] and result["ordinary_input_evidence_tainted"])
        self.assertEqual(result["ledger_status"], "unverified")
        self.assertFalse(result["completion_waiting"][0]["checks"]["publication_after_completed_receipt"])
        self.assertTrue(result["completion_waiting"][-1]["checks"]["publication_after_completed_receipt"])
        self.assertEqual(result["completion_anchor"]["publication"]["tick"],220)
        self.assertEqual(result["final_players"]["tick"],221)

    def test_online_and_ambiguous_status_rejected_before_any_write(self):
        for active in (1, True, None):
            self.calls.clear()
            with self.subTest(active=active), self.assertRaises(debug.DebugError):
                self.run_request([], active=active)
            self.assertEqual([cmd for cmd, _ in self.calls], ["netplay_status"])

    def test_unsupported_capability_and_busy_operation_rejected_before_write(self):
        for state in (bytes(32), publication(1)):
            self.calls.clear()
            with self.assertRaises(debug.DebugError):
                self.run_request([state])
            self.assertFalse(any(cmd == "write_ram" for cmd, _ in self.calls))

    def test_matching_ack_without_native_completion_times_out(self):
        with self.assertRaisesRegex(debug.DebugError, "deadline"):
            self.run_request([publication(), publication(1, generation=1, nonce=77)], clock=[0, 0, 1000])
        self.assertEqual(self.receipt["status"], "failed_setup")
        self.assertEqual(self.receipt["observations"][0]["state"], 1)

    def test_failed_source_or_context_preserved_as_rejection(self):
        for reason in (5, 7):
            with self.subTest(reason=reason), self.assertRaisesRegex(debug.DebugError, "failed/rejected"):
                self.run_request([publication(), publication(5, generation=1, nonce=77, reason=reason)])
            self.assertEqual(self.receipt["observations"][-1]["reason"], reason)

    def test_other_generation_nonce_or_duplicate_initializer_cannot_pass(self):
        for final in (publication(3, generation=2, nonce=77, entries=1),
                      publication(3, generation=1, nonce=78, entries=1),
                      publication(3, generation=1, nonce=77, entries=2)):
            with self.assertRaises(debug.DebugError):
                self.run_request([publication(), final])
            self.assertEqual(self.receipt["status"], "failed_setup")

    def test_later_old_publication_after_payload_cannot_satisfy_completed_anchor(self):
        done=publication(3,generation=1,nonce=77,entries=1)
        with self.assertRaisesRegex(debug.DebugError,"deadline"):
            self.run_request([publication(),done,done],ticks=[215,220,220],clock=[0,0,0,1000])
        self.assertEqual(self.receipt["completion_anchor"]["publication"]["tick"],220)
        self.assertTrue(all(not row["checks"]["publication_after_completed_receipt"]
                            for row in self.receipt["completion_waiting"]))
        self.assertEqual(self.receipt["status"],"failed_setup")


class NativeEntryReadiness(unittest.TestCase):
    def setUp(self):
        _,rows,sections=checkpoint.inventory(INVENTORY)
        self.target=checkpoint.select(rows,sections,0,0,1)

    def reduce(self,row=None,native=None,actor_camera=None,gpu=None,anchor=220,source=None):
        actual=settled_entry()
        return checkpoint.reduce_entry_readiness(self.target,anchor,row or actual[0],
            native if native is not None else actual[1],
            actor_camera if actor_camera is not None else actual[2],gpu if gpu is not None else actual[3],source)

    def test_new_grounded_actor_and_selected_camera_qualify_readiness_not_spawn_y_tolerance(self):
        self.assertEqual(self.target["player"]["y"],1072)
        self.assertTrue(all(self.reduce().values()))  # Synthetic settled Y; no CP1 landing is qualified here.

    def test_cached_pub_equal_anchor_or_backwards_cannot_pass(self):
        for tick in (220,219):
            row=settled_entry(tick)[0]
            self.assertFalse(self.reduce(row=row)["publication_after_completed_receipt"])

    def test_old_stage_body_outside_new_camera_cannot_pass_even_with_new_publication(self):
        row=settled_entry()[0];row["players"][0]["x_raw"]=144<<16;row["players"][1]["x_raw"]=181<<16
        checks=self.reduce(row=row)
        self.assertFalse(checks["native_p1_agrees_with_publication"])
        self.assertFalse(checks["actors_in_current_native_viewport"])

    def test_arrival_scene_and_stage_blocking_flags_are_not_playable_entry(self):
        for at in (0x0F,0x10,0x1C):
            raw=bytearray(settled_entry()[1]);raw[at]=5
            self.assertFalse(self.reduce(native=raw)["native_entry_gates_clear"])

    def test_projected_zero_unsettled_previous_position_or_airborne_p1_is_not_ready(self):
        for mutation in ("projection","previous","airborne"):
            raw=bytearray(settled_entry()[2])
            if mutation=="projection":raw[2]=1
            elif mutation=="previous":struct.pack_into("<i",raw,0x1C,1072<<16)
            else:raw[0x70]=0
            checks=self.reduce(actor_camera=raw)
            self.assertFalse(checks["native_previous_position_settled"] if mutation=="previous" else checks["native_p1_visible_idle_grounded"])

    def test_wrong_authored_x_camera_bounds_or_offscreen_partner_cannot_pass(self):
        raw=bytearray(settled_entry()[2]);struct.pack_into("<i",raw,8,(2112<<16)+1)
        self.assertFalse(self.reduce(actor_camera=raw)["p1_at_authored_x"])
        raw=bytearray(settled_entry()[2]);struct.pack_into("<h",raw,0x158+0x1E,0)
        self.assertFalse(self.reduce(actor_camera=raw)["selected_camera_bounds"])
        row=settled_entry()[0];row["players"][1]["y_raw"]=(944+240)<<16
        self.assertFalse(self.reduce(row=row)["actors_in_current_native_viewport"])

    def test_new_publication_without_enrolled_idle_roster_or_display_is_not_ready(self):
        for mutation in ("not_enrolled","joining","pending_hit","not_idle"):
            row=settled_entry()[0]
            if mutation=="not_enrolled":row["enrolled"]=0
            elif mutation=="joining":row["lifecycle"]=[0,3]
            elif mutation=="pending_hit":row["players"][1]["hp"]=0x9C
            else:row["players"][1]["action"]=6
            self.assertFalse(self.reduce(row=row)["enrolled_living_idle_roster"])
        gpu=settled_entry()[3];gpu["disabled"]=1
        self.assertFalse(self.reduce(gpu=gpu)["display_enabled"])


def source_evidence():
    return dict(verified=True,source_exe_sha256=checkpoint.content.EXE_SHA256,
        spans=[dict(address=f"{a:08X}",size=n,sha256=h) for a,n,h in checkpoint.CAMERA_SOURCE_SPANS])


class NativeDynamicCameraTests(unittest.TestCase):
    setUp=NativeEntryReadiness.setUp
    reduce=NativeEntryReadiness.reduce
    def dynamic(self,py=1115):
        row,native,raw,gpu=settled_entry();raw=bytearray(raw)
        for at in (0xC,0x1C):struct.pack_into("<i",raw,at,py<<16)
        row["players"][0]["y_raw"]=py<<16
        struct.pack_into("<h",raw,0x158+0x22,py-944-96)
        struct.pack_into("<h",raw,0x158+0x2A,896)
        raw[0x158+0x47]=2
        return row,native,raw,gpu

    def test_source_derived_fixed_point_changes_with_native_y_not_magic75(self):
        for py in (1040,1114,1115,1120):
            row,native,raw,gpu=self.dynamic(py)
            with self.subTest(py=py):
                self.assertTrue(all(self.reduce(row,native,raw,gpu,source=source_evidence()).values()))
                self.assertFalse(self.reduce(row,native,raw,gpu)["selected_camera_bounds"])

    def test_wrong_branch_target_or_camera_state_is_rejected(self):
        for offset,value,fmt in ((0x22,76,"h"),(0x2A,897,"h"),(0x2C,95,"h"),
                (0x47,4,"B"),(0x44,0,"B"),(4,0,"B"),(0x26,1967,"h"),
                (0x1C,5121,"h"),(0xE,943,"h")):
            row,native,raw,gpu=self.dynamic()
            struct.pack_into("<"+fmt,raw,0x158+offset,value)
            with self.subTest(offset=offset):
                self.assertFalse(self.reduce(row,native,raw,gpu,source=source_evidence())["selected_camera_bounds"])

    def test_source_mismatch_other_tuple_partial_camera_and_outside_region_fail_closed(self):
        row,native,raw,gpu=self.dynamic()
        for key in ("verified","source_exe_sha256","spans"):
            proof=source_evidence();proof[key]=None
            self.assertFalse(self.reduce(row,native,raw,gpu,source=proof)["selected_camera_bounds"])
        self.assertFalse(self.reduce(row,native,raw[:0x198],gpu,source=source_evidence())["selected_camera_bounds"])
        wrong=copy.deepcopy(self.target);wrong["checkpoint"]=2
        self.assertFalse(checkpoint.dynamic_cp1_camera(wrong,raw[:0x158],raw[0x158:],source_evidence()))
        wrong=copy.deepcopy(self.target);wrong["camera"]["max_x"]+=1
        self.assertFalse(checkpoint.dynamic_cp1_camera(wrong,raw[:0x158],raw[0x158:],source_evidence()))
        struct.pack_into("<h",raw,0xA,2111)
        self.assertFalse(self.reduce(row,native,raw,gpu,source=source_evidence())["selected_camera_bounds"])

    def test_dynamic_camera_does_not_bypass_other_readiness_gates(self):
        row,native,raw,gpu=self.dynamic();row["enrolled"]=0
        checks=self.reduce(row,native,raw,gpu,source=source_evidence())
        self.assertTrue(checks["selected_camera_bounds"])
        self.assertFalse(all(checks.values()))
        row["enrolled"]=1
        self.assertFalse(all(self.reduce(row,native,raw,gpu,anchor=row["tick"],source=source_evidence()).values()))
        gpu["disabled"]=1
        self.assertFalse(all(self.reduce(row,native,raw,gpu,source=source_evidence()).values()))

    def test_resident_short_changed_and_non_cp1_source_do_not_enable_policy(self):
        class Reader:
            def read(self,address,size):return bytes(size-1)
        self.assertFalse(checkpoint.camera_source_evidence(Reader(),self.target)["verified"])
        self.assertEqual(len(checkpoint.camera_source_evidence(Reader(),self.target)["spans"]),1)
        wrong=copy.deepcopy(self.target);wrong["checkpoint"]=0
        self.assertEqual(checkpoint.camera_source_evidence(Reader(),wrong)["spans"],[])

    def test_only_exact_admitted_record_variant_preserves_dynamic_policy(self):
        row,native,raw,gpu=self.dynamic()
        proof=source_evidence()
        entry=next(p for p in proof["spans"] if p["address"]==f"{checkpoint.PLACEMENT:08X}")
        entry["sha256"]=checkpoint.PLACEMENT_ADMITTED_SHA256
        self.assertTrue(all(self.reduce(row,native,raw,gpu,source=proof).values()))
        entry["sha256"]="0"*64
        self.assertFalse(self.reduce(row,native,raw,gpu,source=proof)["selected_camera_bounds"])
        proof=source_evidence();proof["spans"].pop(4)  # Native admission writer cannot be omitted.
        self.assertFalse(self.reduce(row,native,raw,gpu,source=proof)["selected_camera_bounds"])

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_DISC"),"Pinned original raw disc not supplied")
    def test_original_selected_member_reproduces_closure_and_resident_guards(self):
        disc=checkpoint.content.RawDisc(Path(os.environ["MMX6_CONTENT_DISC"]))
        try:files=disc.inventory_files()
        finally:disc.stream.close()
        archive=files["ROCK_X6.BIN"]
        self.assertEqual(checkpoint.content.sha256(archive),checkpoint.content.BIN_SHA256)
        member=checkpoint.content.archive_members(archive)[2];start=member["sector"]*2048
        intro=archive[start:start+member["size"]];exe=checkpoint.content.Executable(files["SLUS_013.95"])
        audit=checkpoint.camera_source_audit(exe,intro)
        self.assertEqual(audit["region"]["values"],list(checkpoint.CP1_REGION))
        self.assertEqual(exe.word(0x800791E8),0x80052294)
        self.assertEqual(exe.word(0x800791EC),0x8005211C)
        self.assertEqual(exe.word(0x80079D70)+7*16,0x80079260)
        self.assertEqual(struct.unpack_from("<4B2h",intro,0x800FA25C-0x800E9860),(0,0,7,3,2128,1088))
        self.assertEqual(struct.unpack_from("<I",intro,0x800FA6E0-0x800E9860)[0],0x80052258)
        # Actual original BGEZ a1 -> store, with a real delay-slot NOP.
        branch=exe.word(0x8002912C)
        self.assertEqual((branch>>26,(branch>>21)&31,(branch>>16)&31),(1,5,1))
        self.assertEqual(0x80029130+((branch&0xFFFF)<<2),0x8002917C)
        self.assertEqual(exe.word(0x8002917C),0xA4850022)
        self.assertEqual(exe.word(0x8002A25C),0x34420001) # ORI v0,v0,1.
        self.assertEqual(exe.word(0x8002A264),0xA2420000) # SB v0,0(s2=record).
        self.assertEqual(exe.word(0x8002A388),0x30630070) # Reset preserves only original high flags.
        class Reader:
            corrupt=False
            record=None
            def read(inner,address,size):
                payload=(intro[address-0x800E9860:address-0x800E9860+size] if address>=0x800E9860 else
                    exe.data[exe.offset(address,size):exe.offset(address,size)+size])
                if address==checkpoint.PLACEMENT and inner.record is not None:payload=inner.record
                return (bytes([payload[0]^1])+payload[1:]) if inner.corrupt else payload
        reader=Reader();self.assertTrue(checkpoint.camera_source_evidence(reader,self.target)["verified"])
        original=bytearray(reader.read(checkpoint.PLACEMENT,8))
        for flags in range(256):
            changed=original.copy();changed[0]=flags;reader.record=bytes(changed)
            with self.subTest(flags=flags):
                self.assertEqual(checkpoint.camera_source_evidence(reader,self.target)["verified"],flags in (0,1))
        for byte in range(1,8):
            changed=original.copy();changed[0]=1;changed[byte]^=1;reader.record=bytes(changed)
            self.assertFalse(checkpoint.camera_source_evidence(reader,self.target)["verified"])
        reader.record=None
        reader.corrupt=True;self.assertFalse(checkpoint.camera_source_evidence(reader,self.target)["verified"])
        broken=bytearray(intro);broken[0]^=1
        with self.assertRaises(ValueError):checkpoint.camera_source_audit(exe,bytes(broken))


class CheckpointOptions(unittest.TestCase):
    base = ["--candidate", "private", "--original", "SLUS_013.95", "--stage", "0x10",
            "--section", "0", "--checkpoint", "1", "--expected-exe-sha256", "a"*64]

    def parse(self, extra=()):
        parser = make_parser();args = parser.parse_args(self.base+list(extra))
        validate_options(parser, args)
        return args

    def test_explicit_original_target_identity_and_no_implicit_restaging(self):
        args = self.parse()
        self.assertEqual((args.stage, args.section, args.checkpoint, args.port), (16, 0, 1, 24898))
        self.assertIsNone(args.build)
        self.assertIsNone(args.output)

    def test_selector_deadline_port_hash_and_staging_guards(self):
        for flags in (("--stage", "256"), ("--section", "-1"), ("--checkpoint", "999"),
                      ("--entry-timeout", "nan"), ("--entry-timeout", "181"),
                      ("--port", "0"), ("--expected-exe-sha256", "wrong"), ("--disc", "ignored.cue")):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.parse(flags)


if __name__ == "__main__":
    unittest.main()
