"""Inventory/provenance and false-qualification regression tests; no game assets."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

import build_mmx6_coop_reference as reference


ROOT = Path(__file__).resolve().parents[1]


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads((ROOT / reference.LEDGER_PATH).read_bytes())
        cls.manifest = json.loads((ROOT / reference.MANIFEST_PATH).read_bytes())
        # Reconstruct source columns to exercise the parser against all frozen
        # records without depending on another developer's X5 checkout.
        cls.lines = []
        for row in cls.ledger["comparisons"]:
            values = list(row["x4"].values()) + list(row["x5_snapshot"].values())
            cls.lines.append("| " + " | ".join(values) + " |")
        cls.table = ("# Historical milestone\n| F37: earlier pass | ignored |\n\n"
                     "| Source / report | X4 state | Original symptom | Failure class / risk | X5 counterpart / bounded check | X5 burndown | X5 status | X5 evidence / limits |\n"
                     "| --- | --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(cls.lines) + "\n").encode()
        # Tests operate on a fresh import, so later real burndown updates do
        # not turn the initial-unverified assertions into permanent blockers.
        cls.initial = reference.initial_ledger(cls.manifest, reference.parse_table(cls.table))

    def setUp(self):
        self.expected = copy.deepcopy(self.initial)
        self.candidate = copy.deepcopy(self.initial)

    def assert_invalid(self, match):
        with self.assertRaisesRegex(ValueError, match):
            reference.validate_ledger(self.candidate, self.expected)

    def receipt(self, mode, candidate="a" * 40):
        return {"mode": mode, "result": "passed", "candidate": candidate,
                "build_identity": "private-test-fixture", "settings": {"coop": True},
                "action": "fixture native action", "outcome": "fixture outcome",
                "artifacts": [{"path": "qualification.json", "sha256": reference.sha256(b"fixture")}],
                "limits": [], "bypasses": []}

    def qualify_first(self):
        x6 = self.candidate["comparisons"][0]["x6"]
        x6.update(status="passed", mode_status={"local": "passed", "netplay": "passed"},
                  evidence=[self.receipt("local"), self.receipt("netplay")])
        return x6

    def test_all_ids_and_individual_x6_checks(self):
        rows = reference.parse_table(self.table)
        self.assertEqual([row["id"] for row in rows], reference.EXPECTED_IDS)
        self.assertEqual(len(rows), 234)
        self.assertEqual(len(reference.mappings()), 234)
        checks = [row["x6"]["bounded_check"] for row in self.ledger["comparisons"]]
        self.assertEqual(len(set(checks)), 234)
        for row in self.initial["comparisons"]:
            self.assertEqual(row["x6"]["status"], "unverified")
            self.assertEqual(row["x6"]["evidence"], [])
        reference.validate_ledger(self.candidate, self.expected)

    def test_milestone_tables_do_not_replace_original_reports(self):
        rows = reference.parse_table(self.table)
        self.assertEqual(rows[62]["id"], "F37")
        self.assertEqual(rows[62]["x4"]["original_symptom"], self.ledger["comparisons"][62]["x4"]["original_symptom"])
        self.assertNotEqual(rows[62]["x4"]["original_symptom"], "earlier pass")

    def test_missing_and_duplicate_rows_are_rejected(self):
        for lines in (self.lines[:-1], self.lines + self.lines[-1:], self.lines[:1] + self.lines[:]):
            with self.subTest(count=len(lines)):
                source = self.table.split(b"| COOP_", 1)[0] + "\n".join(lines).encode()
                with self.assertRaisesRegex(ValueError, "exactly R1"):
                    reference.parse_table(source)
        self.candidate["comparisons"][-1] = copy.deepcopy(self.candidate["comparisons"][0])
        self.assert_invalid("omission, duplicate")

    def test_each_frozen_column_cannot_drift(self):
        for group in ("x4", "x5_snapshot"):
            for field in self.ledger["comparisons"][0][group]:
                with self.subTest(group=group, field=field):
                    self.candidate = copy.deepcopy(self.initial)
                    self.candidate["comparisons"][0][group][field] += " modified"
                    self.assert_invalid("source drift")

    def test_row_digest_cannot_drift(self):
        self.candidate["comparisons"][0]["frozen_row_sha256"] = "0" * 64
        self.assert_invalid("source drift")

    def test_inherited_x5_pass_is_not_x6_evidence(self):
        row = next(row for row in self.candidate["comparisons"] if row["x5_snapshot"]["status"] == "passed")
        row["x6"]["status"] = "passed"
        self.assert_invalid("requires independent")

    def test_fabricated_mode_pass_without_receipts_is_rejected(self):
        self.candidate["comparisons"][0]["x6"].update(status="passed", mode_status={"local": "passed", "netplay": "passed"})
        self.assert_invalid("without individual evidence")

    def test_two_modes_require_same_exact_candidate(self):
        x6 = self.qualify_first()
        x6["evidence"][1]["candidate"] = "b" * 40
        self.assert_invalid("same exact candidate")

    def test_qualified_receipts_preserve_failed_attempts(self):
        x6 = self.qualify_first()
        failed = self.receipt("local", "c" * 40)
        failed["result"] = "failed"
        x6["evidence"].insert(0, failed)
        reference.validate_ledger(self.candidate, self.expected)
        self.assertEqual(len(x6["evidence"]), 3)

    def test_missing_artifact_and_modified_artifact_are_rejected(self):
        self.qualify_first()
        # TEMP is explicitly redirected by the task launcher; never choose an
        # implicit Windows/AppData default for this test's small fixture.
        scratch = os.environ.get("TEMP", "")
        if not scratch or Path(scratch).drive.lower() == "c:":
            self.skipTest("set TEMP to verified non-C scratch to test artifact validation")
        with tempfile.TemporaryDirectory(dir=scratch, prefix="x6-reference-test-") as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "does not exist"):
                reference.validate_ledger(self.candidate, self.expected, root)
            artifact = root / "qualification.json"
            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                reference.validate_ledger(self.candidate, self.expected, root)
            artifact.write_bytes(b"fixture")
            reference.validate_ledger(self.candidate, self.expected, root)

    def test_unknown_analogue_cannot_be_declared_inapplicable(self):
        x6 = next(row["x6"] for row in self.candidate["comparisons"] if row["x6"]["mapping_state"] == "unknown_native_analogue")
        x6.update(status="inapplicable", inapplicability_reason="not identified", native_content_evidence=["unsupported claim"])
        self.assert_invalid("unknown analogue cannot be inapplicable")

    def test_inapplicability_needs_native_content_evidence(self):
        self.candidate["comparisons"][0]["x6"]["status"] = "inapplicable"
        self.assert_invalid("native-content reason and evidence")

    def test_mapping_and_mode_omissions_are_rejected(self):
        del self.candidate["comparisons"][0]["x6"]["bounded_check"]
        self.assert_invalid("missing individual X6")
        self.candidate = copy.deepcopy(self.initial)
        del self.candidate["comparisons"][0]["x6"]["mode_status"]["netplay"]
        self.assert_invalid("invalid per-mode")

    def test_manifest_contains_all_frozen_identities(self):
        self.assertEqual(self.manifest["x4"]["commit"], reference.X4_COMMIT)
        self.assertEqual(len(self.manifest["x4"]["files"]), 15)
        self.assertEqual(self.manifest["x5"]["commit"], reference.X5_COMMIT)
        for item in self.manifest["x5"]["files"]:
            self.assertEqual(item["git_blob"], reference.SOURCE_BLOBS[item["path"]])
        self.assertTrue(self.manifest["x6_baseline"]["commit"].startswith(reference.X6_COMMIT))

    def test_markdown_is_authoritative_projection(self):
        rendered = reference.render_markdown(self.ledger).encode()
        self.assertEqual((ROOT / reference.TABLE_PATH).read_bytes(), rendered)
        self.assertEqual(sum(line.startswith("| R") or line.startswith("| F") for line in rendered.decode().splitlines()), 234)


if __name__ == "__main__":
    unittest.main()
