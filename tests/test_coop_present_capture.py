import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from coop_debug import DebugError, capture_present


class FakeCapture:
    def __init__(self, wrote=1, complete=True):
        self.calls = []
        self.path = None
        self.wrote = wrote
        self.complete = complete

    def request(self, command, **fields):
        self.calls.append(command)
        if command == "present_shot":
            self.path = Path(fields["path"])
            return {"seq": 4, "staged": True}
        if self.path and self.complete:
            if self.wrote:
                self.path.write_bytes(b"completed capture fixture")
            return {"seq": 5, "wrote": self.wrote}
        return {"seq": 4, "wrote": 1}


class PresentCaptureTests(unittest.TestCase):
    def test_samples_sequence_before_request_and_requires_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeCapture()
            result = capture_present(client, Path(directory) / "present.png")
            self.assertEqual(client.calls, ["present_shot_seq", "present_shot", "present_shot_seq"])
            self.assertEqual(result["completion"]["seq"], 5)
            self.assertEqual(len(result["sha256"]), 64)

    def test_completed_write_failure_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DebugError):
                capture_present(FakeCapture(wrote=0), Path(directory) / "present.png")

    def test_ack_without_sequence_advance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DebugError):
                capture_present(FakeCapture(complete=False), Path(directory) / "present.png", timeout=.025)

    def test_existing_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "present.png"
            path.write_bytes(b"previous failure")
            with self.assertRaises(ValueError):
                capture_present(FakeCapture(), path)
            self.assertEqual(path.read_bytes(), b"previous failure")


if __name__ == "__main__":
    unittest.main()
