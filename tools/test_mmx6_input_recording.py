"""Strict native-consumption codec negatives; no game, live cards or assets."""
from __future__ import annotations

import io
import json
import unittest

import mmx6_input_recording as trace


SETTINGS = b'{"effective":{"roster":"X+Zero","wide":false},"files":[]}\n'
CARD = bytes(range(256)) * 512
BASELINE = b"synthetic complete-machine-and-title-host fixture"


def blob(data):
    return {"sha256": trace.sha256(data), "bytes": len(data)}


def identity():
    return {"image_sha256": "1" * 64, "manifest_sha256": "2" * 64,
            "execution_id": "fixture-execution-contract", "settings_sha256": trace.sha256(SETTINGS),
            "content_sha256": "3" * 64, "simulation_contract_sha256": "4" * 64,
            "mode": "offline", "profile": None, "cards": [blob(CARD), None], "baseline": None}


def events():
    # Frame 20 remains unchanged while multiple native wait-loop/menu calls
    # consume fresh inputs. Preserve repeated/held P2 reads rather than dedup.
    return [
        {"type": "N", "order": 0, "native": 0, "cycles": 10, "sim_tick": None,
         "frame": 20, "caller": 0x80012220, "pads": [[0, 0, 0], [0, 0, 0]]},
        {"type": "C", "order": 1, "native": 0, "cycles": 12, "sim_tick": None,
         "seat": 1, "consumer": "stage", "buttons": 8},
        {"type": "C", "order": 2, "native": 0, "cycles": 13, "sim_tick": None,
         "seat": 1, "consumer": "controller-player", "buttons": 8},
        {"type": "N", "order": 3, "native": 1, "cycles": 30, "sim_tick": None,
         "frame": 20, "caller": 0x8001A834, "pads": [[0x800, 0, 0x800], [0, 0, 0]]},
        {"type": "C", "order": 4, "native": 1, "cycles": 32, "sim_tick": None,
         "seat": 1, "consumer": "stage", "buttons": 1},
        {"type": "C", "order": 5, "native": 1, "cycles": 33, "sim_tick": None,
         "seat": 1, "consumer": "controller-blocked", "buttons": 1},
        {"type": "N", "order": 6, "native": 2, "cycles": 50, "sim_tick": None,
         "frame": 20, "caller": 0x8001AB18, "pads": [[0x800, 0x800, 0], [0, 0, 0]]},
        {"type": "C", "order": 7, "native": 2, "cycles": 52, "sim_tick": None,
         "seat": 1, "consumer": "stage", "buttons": 0},
    ]


def encode(rows=None, startup=None, failure=None):
    out = io.BytesIO()
    writer = trace.Encoder(out, identity() if startup is None else startup)
    for row in events() if rows is None else rows:
        writer.append(row)
    writer.finish(failure=failure)
    return out.getvalue()


class RecordingTests(unittest.TestCase):
    def test_roundtrip_keeps_same_frame_native_calls_and_repeated_reads(self):
        data = encode()
        got = trace.validate(io.BytesIO(data), expected_identity=identity(), offline_replay=True)
        self.assertEqual((got.events, got.natives, got.p2_reads), (8, 3, 5))
        self.assertIsNone(got.failure)
        self.assertEqual(data, encode())

    def test_all_truncation_offsets_are_rejected(self):
        data = encode()
        for end in range(len(data)):
            with self.subTest(end=end), self.assertRaises(trace.InvalidRecording):
                trace.validate(io.BytesIO(data[:end]))

    def test_each_removed_or_duplicated_event_is_rejected(self):
        lines = encode().splitlines(keepends=True)
        for index in range(1, len(lines) - 1):
            for altered in (lines[:index] + lines[index + 1:],
                            lines[:index] + [lines[index]] + lines[index:]):
                with self.subTest(index=index), self.assertRaises(trace.InvalidRecording):
                    trace.validate(io.BytesIO(b"".join(altered)))

    def test_swapped_events_are_rejected(self):
        lines = encode().splitlines(keepends=True)
        lines[2], lines[3] = lines[3], lines[2]
        with self.assertRaisesRegex(trace.InvalidRecording, "order"):
            trace.validate(io.BytesIO(b"".join(lines)))

    def test_native_counter_and_consumer_interval(self):
        for index, key, value in ((3, "native", 2), (1, "native", 1),
                                  (1, "consumer", "host-poll"), (1, "seat", 0),
                                  (0, "caller", 0x80012330), (1, "consumer", [])):
            rows = events()
            rows[index][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(trace.InvalidRecording):
                encode(rows)

    def test_no_p2_read_before_first_native_call(self):
        row = events()[1]
        row["order"] = 0
        with self.assertRaisesRegex(trace.InvalidRecording, "outside"):
            encode([row])

    def test_cycles_cannot_regress_inside_restore_segment(self):
        rows = events()
        rows[4]["cycles"] = 29
        with self.assertRaisesRegex(trace.InvalidRecording, "regressed"):
            encode(rows)

    def test_native_edge_and_word_bounds(self):
        for pad in ([0x800, 0, 0], [65536, 0, 0], [True, 0, 0]):
            rows = events()
            rows[0]["pads"][0] = pad
            with self.subTest(pad=pad), self.assertRaises(trace.InvalidRecording):
                encode(rows)

    def test_each_startup_identity_difference_is_rejected(self):
        changes = {"image_sha256": "a" * 64, "manifest_sha256": "b" * 64,
                   "execution_id": "another-build", "settings_sha256": "c" * 64,
                   "content_sha256": "d" * 64, "simulation_contract_sha256": "e" * 64,
                   "cards": [None, None], "baseline": blob(BASELINE),
                   "profile": {"id": "fixture", "revision": 1, "selected_sha256": "f" * 64}}
        for key, value in changes.items():
            expected = identity()
            expected[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(trace.InvalidRecording, "identity mismatch"):
                trace.validate(io.BytesIO(encode()), expected_identity=expected)

    def test_startup_artifacts_bind_actual_bytes_and_absence(self):
        trace.validate_startup_artifacts(identity(), settings=SETTINGS, cards=[CARD, None], baseline=None)
        cases = [(SETTINGS + b" ", [CARD, None], None),
                 (SETTINGS, [CARD[:-1] + b"!", None], None),
                 (SETTINGS, [CARD[:-1], None], None), (SETTINGS, [None, None], None),
                 (SETTINGS, [CARD, CARD], None), (SETTINGS, [CARD, None], BASELINE)]
        for settings, cards, baseline in cases:
            with self.subTest(cards=[c is not None for c in cards], baseline=baseline), \
                    self.assertRaises(trace.InvalidRecording):
                trace.validate_startup_artifacts(identity(), settings=settings, cards=cards, baseline=baseline)

    def test_restore_baseline_is_exact_and_required(self):
        startup = identity()
        startup["baseline"] = blob(BASELINE)
        trace.validate_startup_artifacts(startup, settings=SETTINGS, cards=[CARD, None], baseline=BASELINE)
        for data in (None, BASELINE + b"!", b"x" * len(BASELINE)):
            with self.subTest(data=data), self.assertRaises(trace.InvalidRecording):
                trace.validate_startup_artifacts(startup, settings=SETTINGS, cards=[CARD, None], baseline=data)

    def test_network_data_is_inspectable_but_cannot_replay_offline(self):
        startup = identity()
        startup.update(mode="netplay", profile={"id": "fixture", "revision": 1,
                                                "selected_sha256": "5" * 64})
        rows = events()
        for row in rows:
            row["sim_tick"] = 9
        data = encode(rows, startup)
        self.assertEqual(trace.validate(io.BytesIO(data)).natives, 3)
        with self.assertRaisesRegex(trace.InvalidRecording, "cannot be replayed offline"):
            trace.validate(io.BytesIO(data), expected_identity=startup, offline_replay=True)

    def test_offline_replay_requires_independently_observed_identity(self):
        with self.assertRaisesRegex(trace.InvalidRecording, "independently observed"):
            trace.validate(io.BytesIO(encode()), offline_replay=True)

    def test_network_ticks_and_profile_required_only_for_network(self):
        rows = events()
        rows[0]["sim_tick"] = 0
        with self.assertRaisesRegex(trace.InvalidRecording, "offline event"):
            encode(rows)
        startup = identity()
        startup["mode"] = "netplay"
        with self.assertRaisesRegex(trace.InvalidRecording, "selected profile"):
            encode(startup=startup)

    def test_terminal_counts_hash_and_trailing_data(self):
        original = encode()
        lines = original.splitlines(keepends=True)
        for key, value in (("events", 9), ("natives", 4), ("p2_reads", 6),
                           ("stream_sha256", "a" * 64)):
            end = json.loads(lines[-1])
            end[key] = value
            with self.subTest(key=key), self.assertRaises(trace.InvalidRecording):
                trace.validate(io.BytesIO(b"".join(lines[:-1]) + trace.canonical(end)))
        with self.assertRaisesRegex(trace.InvalidRecording, "after terminal"):
            trace.validate(io.BytesIO(original + b"\n"))

    def test_explicit_capture_failure_never_becomes_replay_success(self):
        data = encode(failure="queue full")
        with self.assertRaisesRegex(trace.InvalidRecording, "explicitly failed"):
            trace.validate(io.BytesIO(data))
        self.assertEqual(trace.validate(io.BytesIO(data), require_complete=False).failure, "queue full")
        with self.assertRaisesRegex(trace.InvalidRecording, "explicitly failed"):
            trace.validate(io.BytesIO(data), expected_identity=identity(), offline_replay=True,
                           require_complete=False)

    def test_unknown_schema_duplicate_keys_noncanonical_and_oversized(self):
        lines = encode().splitlines(keepends=True)
        header = json.loads(lines[0])
        header["schema"] = 2
        for first in (trace.canonical(header), b'{"type":"header","type":"header"}\n',
                      b" " + lines[0], b"x" * (trace.MAX_LINE + 1) + b"\n"):
            with self.subTest(first=first[:40]), self.assertRaises(trace.InvalidRecording):
                trace.validate(io.BytesIO(first + b"".join(lines[1:])))

    def test_empty_capture_and_bounded_event_count(self):
        with self.assertRaisesRegex(trace.InvalidRecording, "no native"):
            trace.validate(io.BytesIO(encode([])))
        with self.assertRaisesRegex(trace.InvalidRecording, "event limit"):
            trace.validate(io.BytesIO(encode()), max_events=3)

    def test_write_failure_poison_prevents_hidden_resume(self):
        class Broken(io.BytesIO):
            fail = False
            def write(self, data):
                if self.fail:
                    return super().write(data[:3])
                return super().write(data)
        output = Broken()
        writer = trace.Encoder(output, identity())
        output.fail = True
        with self.assertRaisesRegex(OSError, "short"):
            writer.append(events()[0])
        output.fail = False
        with self.assertRaisesRegex(trace.InvalidRecording, "poisoned"):
            writer.append(events()[1])
        with self.assertRaisesRegex(trace.InvalidRecording, "poisoned"):
            writer.finish()
        with self.assertRaises(trace.InvalidRecording):
            trace.validate(io.BytesIO(output.getvalue()))

    def test_validation_failure_and_double_finish_cannot_resume(self):
        output = io.BytesIO()
        writer = trace.Encoder(output, identity())
        row = events()[0]
        row["order"] = 1
        with self.assertRaises(trace.InvalidRecording):
            writer.append(row)
        with self.assertRaises(trace.InvalidRecording):
            writer.append(events()[0])
        writer = trace.Encoder(io.BytesIO(), identity())
        writer.append(events()[0])
        writer.finish()
        with self.assertRaises(trace.InvalidRecording):
            writer.finish()


if __name__ == "__main__":
    unittest.main()
