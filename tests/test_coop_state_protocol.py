import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from coop_debug import DebugError
from qualify_mmx6_coop_state import snapshot_operation


class SnapshotReceiptTests(unittest.TestCase):
    def test_acknowledgement_waits_for_matching_completed_generation(self):
        statuses = iter([
            dict(generation=9, pending=0), dict(generation=9, pending=1),
            dict(generation=10, pending=0, last_ok=1, last_op="load", last_slot=8)])
        def control(command, **fields):
            return next(statuses) if command == "savestate_status" else dict(ok=True)
        records = []
        self.assertEqual(snapshot_operation(control, "load", 8, records)["generation"], 10)
        self.assertEqual(len(records[0]["observations"]), 2)

    def test_failed_or_wrong_operation_receipt_is_rejected_and_retained(self):
        for change in (dict(last_ok=0), dict(last_op="save"), dict(last_slot=7)):
            completed = dict(generation=3, pending=0, last_ok=1, last_op="load", last_slot=8)
            completed.update(change)
            statuses = iter([dict(generation=2, pending=0), completed])
            def control(command, **fields):
                return next(statuses) if command == "savestate_status" else dict(ok=True)
            records = []
            with self.assertRaises(DebugError):
                snapshot_operation(control, "load", 8, records)
            self.assertEqual(records[0]["completion"], completed)

    def test_acknowledgement_alone_is_not_success(self):
        def control(command, **fields):
            return dict(generation=2, pending=0) if command == "savestate_status" else dict(ok=True)
        with self.assertRaises(DebugError):
            snapshot_operation(control, "save", 8, [], timeout=.01)


if __name__ == "__main__":
    unittest.main()
