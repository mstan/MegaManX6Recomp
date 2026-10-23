"""Source/identity tests for R14, not native alternate-route qualification."""
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

import audit_mmx6_alternate_route as route

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/COOP_ALTERNATE_ROUTE_AUDIT.json"


class AlternateRouteTests(unittest.TestCase):
    def report(self):
        return json.loads(REPORT.read_text())

    def test_scope_is_one_original_route_without_runtime_passes(self):
        data = self.report()
        self.assertEqual(data["scope"], ["R14"])
        self.assertTrue(data["source_only"])
        self.assertEqual(data["comparison"]["frozen_row_sha256"], route.R14_SHA)
        self.assertEqual(data["comparison"]["local"], "unverified")
        self.assertEqual(data["comparison"]["netplay"], "unverified")
        self.assertEqual(data["origin"]["record"]["status"], "unverified")
        self.assertEqual(data["original"]["selected_member"]["index"], 6)
        self.assertIn("not stock guards", data["research_label"]["limits"])

    def test_authored_record_dispatch_and_transition_are_distinct_from_dialogue(self):
        data = self.report()
        record = data["origin"]["record"]
        self.assertEqual([record[k] for k in ("address", "index", "object_id", "subtype", "category", "x", "y")],
                         ["800F2B0C", 18, 28, 1, 0, 1552, 1584])
        self.assertEqual(data["origin"]["handler_slot"], "800F308C")
        self.assertEqual(data["contact"]["arguments"], ["a0=portal", "a1=800970A0 resident PLAYER"])
        self.assertEqual(data["contact"]["portal_box"], [-18, -28, 28, 40])
        self.assertEqual(data["dispatch"]["action2_substates"], ["800EBEC0", "800EC8F8", "800EBFB4"])
        self.assertEqual((data["transition"]["destination_stage"], data["transition"]["destination_section"]), (20, 1))
        self.assertEqual([p["id"] for p in data["transition"]["authored_destination_locations"]],
                         ["s20-a1-c00", "s20-a1-c01"])
        self.assertIn("does not prove which checkpoint", data["transition"]["checkpoint_limit"])

    def test_member_boundaries_do_not_alias_other_overlays_or_accept_partial_words(self):
        member = route.Member(b"\x01\x02\x03\x04")
        self.assertEqual(member.word(0x800E9860), 0x04030201)
        self.assertEqual(member.read(0x800E9864, 0), b"")
        for address, size in ((0x800E985F, 1), (0x800E9864, 1),
                              (0x800E9862, 4), (0x800E9860, -1)):
            with self.assertRaisesRegex(ValueError, "outside original extent"):
                member.read(address, size)

    def test_wrong_original_is_rejected_before_source_access(self):
        with patch.object(route, "committed") as source:
            with self.assertRaisesRegex(ValueError, "pinned complete original"):
                route.audit(ROOT, b"not a game", b"not an archive")
            source.assert_not_called()

    def test_source_findings_preserve_counterexample_and_destination_limits(self):
        data = self.report()
        findings = {f["id"]: f for f in data["findings"]}
        self.assertEqual(findings["resident-contact"]["classification"], "source_proven_adapter_coverage_gap")
        self.assertIn("counterexample remains unverified", findings["resident-contact"]["text"])
        self.assertEqual(findings["destination-release"]["classification"], "unverified_native_obligation")
        self.assertIn("never execute the shared portal AI twice", data["proposed_fix_boundary"])
        self.assertIn("not wall-clock frames", data["transition"]["timer"])

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                         "Pinned original EXE/raw disc not supplied")
    def test_actual_original_source_reproduces_and_rejects_drift(self):
        executable = Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes()
        raw = route.content.RawDisc(Path(os.environ["MMX6_CONTENT_DISC"]))
        try:
            archive = raw.extent(211185, 1665024)
        finally:
            raw.stream.close()
        self.assertEqual(route.audit(ROOT, executable, archive), self.report())
        exe = route.content.Executable(executable)
        self.assertEqual([route.alternate_destination(exe, s) for s in range(1, 9)],
                         [(19, 0), (19, 1), (20, 0), (20, 1), (21, 0), (21, 1), (22, 0), (22, 1)])
        for stage in (-1, 0, 9, 19, True, 4.0):
            with self.assertRaises(ValueError):
                route.alternate_destination(exe, stage)
        altered = bytearray(executable)
        altered[exe.offset(0x80042F94, 4)] ^= 1
        with self.assertRaisesRegex(ValueError, "arithmetic differs"):
            route.alternate_destination(route.content.Executable(bytes(altered)), 4)
        with self.assertRaisesRegex(ValueError, "pinned complete"):
            route.audit(ROOT, bytes(altered), archive)
        corrupted = bytearray(archive)
        corrupted[153 * 2048 + 0x800F2B0C - route.content.OVERLAY_BASE] ^= 1
        with self.assertRaises(ValueError):
            route.audit(ROOT, executable, bytes(corrupted))
        calls = {c["pc"]: c["target"] for span in self.report()["native_spans"] for c in span["direct_calls"]}
        self.assertEqual(calls["800EC79C"], "8002D654")
        self.assertEqual(calls["800EC964"], "800139F4")
        self.assertEqual(calls["8001E3D4"], "80042F7C")
        self.assertEqual(exe.word(0x8001E3C4), 0x24020041)
        # Definition drift cannot silently change this audit's comparison.
        original = route.committed
        def changed(repository, revision, path):
            data = original(repository, revision, path)
            if path == "docs/COOP_PARITY_LEDGER.json":
                doc = json.loads(data)
                next(r for r in doc["comparisons"] if r["id"] == "R14")["frozen_row_sha256"] = "0" * 64
                return json.dumps(doc).encode()
            return data
        with patch.object(route, "committed", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "frozen R14"):
                route.audit(ROOT, executable, archive)

    def test_cli_never_clobbers_existing_results_and_closes_disc(self):
        base = Path(os.environ["TEMP"]).resolve(strict=True)
        self.assertNotEqual(base.drive.lower(), "c:")
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            executable = root / "original.exe"
            executable.write_bytes(bytes(522240))
            output = root / "retained.json"
            output.write_text("retained failed attempt")
            raw = Mock()
            raw.extent.return_value = b""
            with patch.object(route.content, "RawDisc", return_value=raw), \
                 patch.object(route, "audit", return_value={}):
                with self.assertRaises(FileExistsError):
                    route.main(["--exe", str(executable), "--disc", "unused", "--output", str(output)])
                raw.stream.close.assert_called_once()
            self.assertEqual(output.read_text(), "retained failed attempt")


if __name__ == "__main__":
    unittest.main()
