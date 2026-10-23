"""Inventory/source guards and transaction failures; never native game proof."""
import contextlib
import io
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


class FrozenInventoryTests(unittest.TestCase):
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

    def run_request(self, statuses, *, active=0, clock=None):
        class Reader:
            def __init__(inner):
                inner.states = iter(statuses)

            def read(inner, address, count):
                if (address, count) == (debug.DIAGNOSTIC_ADDRESS+0xA0, 32):
                    return next(inner.states)
                if (address, count) == (debug.DIAGNOSTIC_ADDRESS+0x50, 1):
                    return b"\0"
                if address == 0x800CCED0:
                    data = bytearray(0x1E);data[0]=10;data[0x1D]=1
                    return data
                if address == 0x800971F8:
                    return bytes(64)
                raise AssertionError((address, count))

        def control(command, **fields):
            self.calls.append((command, fields))
            return dict(active=active) if command == "netplay_status" else dict(ok=True)

        def observe(client):
            self.next_tick += 1
            return SimpleNamespace(tick=self.next_tick, ready=1, enrolled=1, failed=0, native_mode=10,
                lifecycle=(0, 0), players=[SimpleNamespace(active=1, hp=32)]*2,
                json=lambda: dict(tick=self.next_tick))

        with patch.object(debug, "observe", observe), patch.object(checkpoint.time, "sleep"):
            if clock:
                with patch.object(checkpoint.time, "monotonic", side_effect=clock):
                    return checkpoint.enter_checkpoint(control, Reader(), self.target, self.receipt, nonce=77)
            return checkpoint.enter_checkpoint(control, Reader(), self.target, self.receipt, nonce=77)

    def test_payload_then_commit_only_mailbox_and_actual_completion_required(self):
        result = self.run_request([publication(), publication(1, generation=1, nonce=77),
                                  publication(2, generation=1, nonce=77, entries=1),
                                  publication(3, generation=1, nonce=77, entries=1)])
        writes = [fields for cmd, fields in self.calls if cmd == "write_ram"]
        self.assertEqual([int(w["addr"], 16) for w in writes],
                         list(range(debug.DIAGNOSTIC_ADDRESS+0x51, debug.DIAGNOSTIC_ADDRESS+0x58)) +
                         [debug.DIAGNOSTIC_ADDRESS+0x50])
        self.assertEqual(int(writes[-1]["val"], 16), 8)
        self.assertEqual(result["status"], "prerequisite_bypass_setup_completed_artwork_pending")
        self.assertTrue(result["prerequisite_bypass"] and result["ordinary_input_evidence_tainted"])
        self.assertEqual(result["ledger_status"], "unverified")

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
