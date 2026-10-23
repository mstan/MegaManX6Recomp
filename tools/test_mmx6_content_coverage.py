"""Live-ledger policy/IO tests use synthetic receipts, never gameplay passes.

Redirect TEMP/TMP (or MMX6_COVERAGE_TEST_TMP) off C: before running. No original
disc, game process, native card, network, SDK or title build is required.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import mmx6_content_coverage as coverage


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = coverage.load_inventory()
        cls.initial = coverage.initial_ledger(cls.report)
        cls.scratch = Path(os.environ.get("MMX6_COVERAGE_TEST_TMP", tempfile.gettempdir())).resolve()
        coverage.reject_c_path(str(cls.scratch))
        cls.scratch.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="x6-coverage-", dir=self.scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "fixture-image.bin"
        self.image.write_bytes(b"synthetic test image; not an X6 candidate")
        self.log = self.root / "fixture-observation.txt"
        self.log.write_bytes(b"native good\n")
        self.sequence = 0

    def artifact(self, path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def receipt(self, mode="local_coop", result="passed", candidate="a" * 40, case_id="X6-001"):
        self.sequence += 1
        return {"case_id": case_id, "mode": mode, "result": result,
                "candidate": candidate, "recorded_at": f"2026-10-23T00:00:{self.sequence:02}Z",
                "build_identity": {"name": "synthetic unit fixture only", "image": self.artifact(self.image)},
                "settings": {"fixture": True, "mode": mode},
                "action": "synthetic checker exercise; no native action was performed",
                "outcome": "synthetic policy result; this is not gameplay qualification",
                "artifacts": [self.artifact(self.log)], "limits": ["unit fixture only"], "bypasses": []}

    def append(self, ledger, receipt):
        return coverage.append_receipt(ledger, receipt, self.report, self.root)

    def check(self, ledger):
        return coverage.validate_ledger(ledger, self.report, self.root)

    def test_exact_existing_cases_and_empty_mode_results(self):
        self.check(self.initial)
        self.assertEqual(len(self.initial["cases"]), 1665)
        families = coverage.Counter(row["definition"]["family"] for row in self.initial["cases"])
        self.assertEqual(families, {"campaign_obligations": 23, "mechanics_obligations": 56,
                                    "locations": 690, "reploids": 896})
        self.assertEqual(sum(len(row["modes"]) for row in self.initial["cases"]), 3330)
        for row in self.initial["cases"]:
            self.assertEqual(set(row["modes"]), set(coverage.MODES))
            self.assertEqual(coverage.aggregate(row)[0], "unverified")
            for mode in row["modes"].values():
                self.assertEqual(mode, {"status": "unverified", "attempts": []})

    def test_original_inventory_drift_and_truncated_json_are_refused(self):
        path = self.root / "drift.json"
        original = coverage.INVENTORY.read_bytes()
        path.write_bytes(original + b"\n")
        with self.assertRaisesRegex(coverage.CoverageError, "inventory SHA256 drift"):
            coverage.load_inventory(path)
        self.assertEqual(coverage.digest(coverage.INVENTORY.read_bytes()), coverage.INVENTORY_SHA256)
        for data in (b'{"cases":', b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'{"a":NaN}', b'{"a":1e9999}'):
            with self.subTest(data=data), self.assertRaises(coverage.CoverageError):
                coverage.decode(data)

    def test_missing_duplicate_invented_reordered_and_changed_definitions_fail(self):
        variants = []
        missing = copy.deepcopy(self.initial); missing["cases"].pop(); variants.append(missing)
        added = copy.deepcopy(self.initial); added["cases"].append(copy.deepcopy(added["cases"][0])); variants.append(added)
        duplicate = copy.deepcopy(self.initial); duplicate["cases"][1] = copy.deepcopy(duplicate["cases"][0]); variants.append(duplicate)
        changed = copy.deepcopy(self.initial); changed["cases"][0]["definition"]["native"]["procedure"] = "invented replacement"; variants.append(changed)
        changed = copy.deepcopy(self.initial); changed["cases"][-1]["definition"]["native"]["native_id"] = 128; variants.append(changed)
        changed = copy.deepcopy(self.initial); changed["cases"][79]["definition"]["check_key"] = "screen_loaded"; variants.append(changed)
        reordered = copy.deepcopy(self.initial); reordered["cases"][0], reordered["cases"][1] = reordered["cases"][1], reordered["cases"][0]; variants.append(reordered)
        for ledger in variants:
            with self.subTest(case=len(ledger["cases"])), self.assertRaises(coverage.CoverageError):
                self.check(ledger)

    def test_missing_mode_and_unreceipted_status_and_forged_aggregate_fail(self):
        for mutation in (lambda row: row["modes"].pop("netplay"),
                         lambda row: row["modes"]["local_coop"].update(status="passed"),
                         lambda row: row.update(aggregate="passed")):
            ledger = copy.deepcopy(self.initial); mutation(ledger["cases"][0])
            with self.assertRaises(coverage.CoverageError):
                self.check(ledger)

    def test_complete_same_candidate_and_image_modes_are_required_for_aggregate_pass(self):
        local = self.append(self.initial, self.receipt())
        self.assertEqual(coverage.aggregate(local["cases"][0])[0], "unverified")
        paired = self.append(local, self.receipt("netplay"))
        self.assertEqual(coverage.aggregate(paired["cases"][0])[0], "passed")
        different = self.append(local, self.receipt("netplay", candidate="b" * 40))
        self.check(different)
        self.assertEqual(coverage.aggregate(different["cases"][0]), ("unverified", "latest modes use different candidates"))
        image = self.root / "other-image.bin"; image.write_bytes(b"different synthetic build")
        other = self.receipt("netplay"); other["build_identity"]["image"] = self.artifact(image)
        different = self.append(local, other)
        self.assertEqual(coverage.aggregate(different["cases"][0])[0], "unverified")
        self.assertIn("different actual build images", coverage.render(different))

    def test_failed_attempts_retained_and_older_common_pass_cannot_mask_latest_result(self):
        failed = self.receipt(result="failed")
        ledger = self.append(self.initial, failed)
        ledger = self.append(ledger, self.receipt(candidate="b" * 40))
        ledger = self.append(ledger, self.receipt("netplay", candidate="b" * 40))
        mode = ledger["cases"][0]["modes"]["local_coop"]
        self.assertEqual(len(mode["attempts"]), 2)
        self.assertEqual(mode["attempts"][0]["receipt"], failed)
        self.assertEqual(coverage.aggregate(ledger["cases"][0])[0], "passed")
        self.assertIn("attempt 1: **failed**", coverage.render(ledger))
        ledger = self.append(ledger, self.receipt(result="failed", candidate="c" * 40))
        self.assertEqual(coverage.aggregate(ledger["cases"][0])[0], "failed")
        ledger = self.append(ledger, self.receipt(candidate="c" * 40))
        self.assertEqual(coverage.aggregate(ledger["cases"][0])[0], "unverified")

    def test_all_receipt_fields_and_mode_binding_are_enforced(self):
        good = self.receipt()
        for field in good:
            bad = copy.deepcopy(good); del bad[field]
            with self.subTest(field=field), self.assertRaises(coverage.CoverageError):
                coverage.validate_receipt(bad, "X6-001", "local_coop", set(), coverage.Artifacts(self.root))
        for key, value in (("candidate", "a" * 39), ("candidate", "0" * 40), ("mode", "netplay"),
                           ("case_id", "R8"), ("settings", {}), ("limits", "none"),
                           ("bypasses", None), ("action", ""), ("outcome", ""),
                           ("artifacts", []), ("recorded_at", "2026-99-99T00:00:00Z")):
            bad = copy.deepcopy(good); bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(coverage.CoverageError):
                coverage.validate_receipt(bad, "X6-001", "local_coop", set(), coverage.Artifacts(self.root))

    def test_forged_missing_and_changed_artifacts_fail_even_with_restored_mtime(self):
        receipt = self.receipt(); receipt["artifacts"][0]["sha256"] = "f" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "SHA256 mismatch"):
            self.append(self.initial, receipt)
        receipt = self.receipt(); receipt["artifacts"][0]["path"] = str(self.root / "missing.txt")
        with self.assertRaises((coverage.CoverageError, FileNotFoundError)):
            self.append(self.initial, receipt)
        ledger = self.append(self.initial, self.receipt())
        before = self.log.stat()
        self.log.write_bytes(b"native evil\n")  # Exact same length; metadata does not authorize reuse.
        os.utime(self.log, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(coverage.CoverageError, "SHA256 mismatch"):
            self.check(ledger)

    def test_c_drive_paths_and_alias_spellings_are_refused_before_read(self):
        for path in ("C:/evidence/run.txt", "c:\\evidence\\run.txt", "C:run.txt",
                     "\\\\?\\C:\\evidence\\run.txt", "\\\\localhost\\C$\\evidence.txt", "file:///C:/run.txt"):
            receipt = self.receipt(); receipt["artifacts"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(coverage.CoverageError):
                self.append(self.initial, receipt)

    def test_relative_artifacts_bind_to_explicit_root(self):
        receipt = self.receipt()
        receipt["build_identity"]["image"]["path"] = self.image.name
        receipt["artifacts"][0]["path"] = self.log.name
        ledger = self.append(self.initial, receipt)
        self.check(ledger)
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_ledger(ledger, self.report, self.root / "wrong-root")

    def test_inapplicable_needs_verified_native_source_and_case_specific_absence(self):
        receipt = self.receipt(result="inapplicable")
        with self.assertRaisesRegex(coverage.CoverageError, "native_absence"):
            self.append(self.initial, receipt)
        source = self.root / "synthetic-native-source.bin"; source.write_bytes(b"synthetic original only for unit policy")
        receipt["native_absence"] = {"kind": "authored_native_content_absent", "case_id": "X6-001",
            "source": self.artifact(source), "audit": self.artifact(self.log),
            "source_reference": "fixture table entry0", "reason": "fixture represents an authored absence"}
        # The isolated receipt validator accepts only its caller's trusted native
        # identity. Production derives that set from the SHA-pinned inventory.
        coverage.validate_receipt(receipt, "X6-001", "local_coop",
                                  {self.artifact(source)["sha256"]}, coverage.Artifacts(self.root))
        with self.assertRaisesRegex(coverage.CoverageError, "frozen original EXE/BIN"):
            self.append(self.initial, receipt)
        for bad_kind in ("unknown", "missing_implementation", "unsupported"):
            bad = copy.deepcopy(receipt); bad["native_absence"]["kind"] = bad_kind
            with self.subTest(kind=bad_kind), self.assertRaisesRegex(coverage.CoverageError, "native absence"):
                coverage.validate_receipt(bad, "X6-001", "local_coop", {self.artifact(source)["sha256"]}, coverage.Artifacts(self.root))
        bad = copy.deepcopy(receipt); bad["native_absence"]["source"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "SHA256 mismatch"):
            coverage.validate_receipt(bad, "X6-001", "local_coop", {"f" * 64}, coverage.Artifacts(self.root))
        other_audit = self.root / "other-audit.txt"; other_audit.write_bytes(b"another audit")
        bad = copy.deepcopy(receipt); bad["native_absence"]["audit"] = self.artifact(other_audit)
        with self.assertRaisesRegex(coverage.CoverageError, "audit must be retained"):
            coverage.validate_receipt(bad, "X6-001", "local_coop", {self.artifact(source)["sha256"]}, coverage.Artifacts(self.root))

    def test_duplicate_or_modified_retained_attempts_are_rejected(self):
        receipt = self.receipt(); ledger = self.append(self.initial, receipt)
        with self.assertRaisesRegex(coverage.CoverageError, "duplicate retained attempt"):
            self.append(ledger, receipt)
        ledger["cases"][0]["modes"]["local_coop"]["attempts"][0]["receipt"]["outcome"] = "edited historical outcome"
        with self.assertRaisesRegex(coverage.CoverageError, "receipt SHA256 mismatch"):
            self.check(ledger)

    def test_initialize_never_clobbers_existing_or_empty_files(self):
        path = self.root / "ledger.json"; coverage.initialize(path, self.report)
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            coverage.initialize(path, self.report)
        self.assertEqual(path.read_bytes(), before)
        empty = self.root / "empty.json"; empty.touch()
        with self.assertRaises(FileExistsError):
            coverage.initialize(empty, self.report)
        self.assertEqual(empty.read_bytes(), b"")

    def test_record_appends_and_failed_record_or_lock_preserves_bytes(self):
        path = self.root / "ledger.json"; coverage.initialize(path, self.report)
        first = self.receipt(result="failed"); coverage.record(path, first, self.report, self.root)
        coverage.record(path, self.receipt(), self.report, self.root)
        ledger = coverage.read_json(path)
        self.assertEqual(ledger["cases"][0]["modes"]["local_coop"]["attempts"][0]["receipt"], first)
        self.assertEqual(len(ledger["cases"][0]["modes"]["local_coop"]["attempts"]), 2)
        before = path.read_bytes(); bad = self.receipt(); bad["artifacts"][0]["sha256"] = "f" * 64
        with self.assertRaises(coverage.CoverageError):
            coverage.record(path, bad, self.report, self.root)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(path.with_name(path.name + ".lock").exists())
        lock = path.with_name(path.name + ".lock"); lock.write_bytes(b"another healthy operation")
        with self.assertRaisesRegex(coverage.CoverageError, "locked"):
            coverage.record(path, self.receipt(), self.report, self.root)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(lock.read_bytes(), b"another healthy operation")

    def test_check_and_render_preserve_json_and_refuse_evidence_or_other_files(self):
        path = self.root / "ledger.json"; coverage.initialize(path, self.report)
        coverage.record(path, self.receipt(result="failed"), self.report, self.root)
        before = path.read_bytes(); ledger = coverage.read_json(path); checked = self.check(ledger)
        view = self.root / "coverage.md"
        coverage.write_render(view, path, coverage.INVENTORY, ledger, checked)
        expected = view.read_bytes()
        coverage.write_render(view, path, coverage.INVENTORY, ledger, checked)
        self.assertEqual(view.read_bytes(), expected)
        self.assertEqual(path.read_bytes(), before)
        for output in (path, coverage.INVENTORY, self.log):
            with self.subTest(output=output), self.assertRaisesRegex(coverage.CoverageError, "overwrite"):
                coverage.write_render(output, path, coverage.INVENTORY, ledger, checked)
        unrelated = self.root / "notes.md"; unrelated.write_text("keep owner notes", encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "generated-view marker"):
            coverage.write_render(unrelated, path, coverage.INVENTORY, ledger, checked)
        self.assertEqual(unrelated.read_text(), "keep owner notes")
        self.assertEqual(path.read_bytes(), before)
        self.log.write_bytes(b"native evil\n")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            coverage.main(["--ledger", str(path), "--artifact-root", str(self.root), "render", "--out", str(view)])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(view.read_bytes(), expected)

    def test_mutable_ledger_cannot_be_its_own_artifact(self):
        path = self.root / "ledger.json"; coverage.initialize(path, self.report)
        before = path.read_bytes(); receipt = self.receipt(); receipt["artifacts"] = [self.artifact(path)]
        with self.assertRaisesRegex(coverage.CoverageError, "own evidence"):
            coverage.record(path, receipt, self.report, self.root)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
