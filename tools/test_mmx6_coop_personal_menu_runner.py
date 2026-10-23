"""CLI and owned-input adapter checks; no process, disc or game is launched."""
import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from qualify_mmx6_coop_personal_menu import (
    OfflineMenuAdapter, OwnedReadClient, make_parser, validate_options,
)


class MenuRunnerOptions(unittest.TestCase):
    sha = ["--expected-exe-sha256", "a" * 64]

    def parse(self, *options):
        parser = make_parser()
        args = parser.parse_args(list(options))
        validate_options(parser, args)
        return args

    def rejected(self, *options):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(*options)

    def test_fresh_candidate_requires_explicit_hash_and_has_no_implicit_staging(self):
        args = self.parse("--candidate", "prepared", *self.sha)
        self.assertIsNone(args.build)
        self.assertIsNone(args.source)
        self.assertIsNone(args.disc)
        self.assertIsNone(args.output)
        self.assertEqual(args.port, 24896)
        self.assertEqual((args.cursor_change, args.cursor_restore), ("right", "left"))
        self.rejected("--candidate", "prepared")

    def test_new_build_requires_source_disc_output_and_excludes_candidate_mode(self):
        base = ["--build", "compiled", *self.sha]
        self.rejected(*base)
        self.rejected(*base, "--source", "source", "--disc", "disc.cue")
        args = self.parse(*base, "--source", "source", "--disc", "disc.cue", "--output", "fresh")
        self.assertEqual(str(args.output), "fresh")
        self.rejected(*base, "--candidate", "prepared", "--source", "source", "--disc", "disc.cue", "--output", "fresh")

    def test_candidate_cannot_smuggle_restage_arguments(self):
        for flag in ("--source", "--disc", "--output"):
            self.rejected("--candidate", "prepared", *self.sha, flag, "unused")

    def test_exact_hash_rejects_short_or_uppercase_values(self):
        for value in ("a" * 40, "A" * 64, "g" * 64):
            self.rejected("--candidate", "prepared", "--expected-exe-sha256", value)

    def test_deadlines_progress_bounds_ports_and_native_direction_choices(self):
        base = ["--candidate", "prepared", *self.sha]
        for flag, value in (("--port", "0"), ("--port", "65536"), ("--timeout", "nan"),
                            ("--timeout", "601"), ("--progress-timeout", "inf"),
                            ("--progress-timeout", "0"), ("--window-frames", "5"),
                            ("--window-frames", "121"), ("--cursor-change", "square")):
            self.rejected(*base, flag, value)
        self.parse(*base, "--cursor-change", "down", "--cursor-restore", "up")


class OwnedOfflineInputTests(unittest.TestCase):
    def test_observed_hold_samples_before_release_and_keeps_other_seat_independent(self):
        calls, held = [], {}
        def control(command, **fields):
            calls.append((command, fields))
            if command == "press":
                held[fields["port"]] = fields["buttons"]
            elif command == "clear_input":
                held.pop(fields["port"], None)
        adapter, report = self.adapter(control)
        ticks = iter((100, 102, 120, 122))
        adapter.sample = lambda label: SimpleNamespace(tick=(tick := next(ticks)), json=lambda:dict(tick=tick))
        def observe():
            self.assertEqual(held.get(2), 0xDFFF)
            # A P1 Start hold/release must leave the outer P2 dash held.
            if not calls[-1][0] == "clear_input":
                adapter.hold(0, 8, 4, "nested P1 pause")
                self.assertEqual(held, {2:0xDFFF})
            return dict(held=held.copy())
        with patch("qualify_mmx6_coop_personal_menu.time.sleep"):
            rows = adapter.hold_observed(1, 0x2000, 12, "P2 held dash", observe)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["held"] == {2:0xDFFF} for row in rows))
        self.assertEqual(held, {})
        self.assertEqual(calls[-1], ("clear_input", dict(port=2)))
        self.assertEqual(report["adapter_windows"][0]["end"]["tick"], 122)

    def test_observed_hold_releases_after_observer_failure_and_preserves_original_error(self):
        calls = []
        def control(command, **fields):
            calls.append(command)
            if command == "clear_input":
                raise RuntimeError("neutral unavailable")
        adapter, report = self.adapter(control)
        adapter.sample = lambda label: SimpleNamespace(tick=5)
        def observe():
            raise ValueError("observation rejected")
        with self.assertRaisesRegex(ValueError, "observation rejected"):
            adapter.hold_observed(1, 0x2000, 12, "case", observe)
        self.assertEqual(calls, ["press", "clear_input"])
        self.assertEqual(report["input_cleanup_errors"][0]["original_error"], "observation rejected")

    def test_observed_hold_counter_reversal_releases_without_accepting_samples(self):
        calls = []
        adapter, _ = self.adapter(lambda command, **fields:calls.append(command))
        ticks = iter((100, 99))
        adapter.sample = lambda label: SimpleNamespace(tick=next(ticks))
        with self.assertRaisesRegex(Exception, "counter moved backwards"):
            adapter.hold_observed(1, 0x2000, 12, "case", lambda:self.fail("stale observation accepted"))
        self.assertEqual(calls, ["press", "clear_input"])

    def adapter(self, control):
        report = {}
        adapter = OfflineMenuAdapter(control, report)
        self.windows = []
        adapter.wait_counter = lambda field, frames, label: self.windows.append((field, frames, label))
        return adapter, report

    def test_pressed_masks_map_to_each_original_active_low_sio_port_and_release(self):
        for seat, bits, active_low in ((0, 8, 0xFFF7), (1, 0x8000, 0x7FFF)):
            calls = []
            adapter, _ = self.adapter(lambda command, **fields: calls.append((command, fields)))
            adapter.hold(seat, bits, 4, "native case")
            self.assertEqual(calls, [("press", dict(port=seat + 1, buttons=active_low, frames=0)),
                                     ("clear_input", dict(port=seat + 1))])
            self.assertEqual([entry[:2] for entry in self.windows], [("tick", 6), ("tick", 3)])
            self.assertNotIn("native_timer", [entry[0] for entry in self.windows])

    def test_low_latency_override_reads_do_not_expire_before_the_publication_window(self):
        # Model the SDK getter's read-count expiration independently of the
        # runner's publication clock. Both one and multiple samples per frame
        # must retain the requested buttons until the explicit neutral clear.
        for reads_per_publication in (1, 2, 4):
            state = dict(buttons=None, remaining=0)
            windows = []

            def control(command, **fields):
                if command == "press":
                    state.update(buttons=fields["buttons"], remaining=fields["frames"])
                elif command == "clear_input":
                    state.update(buttons=None, remaining=0)

            def read_override():
                result = state["buttons"]
                if result is not None and state["remaining"] > 0:
                    state["remaining"] -= 1
                    if not state["remaining"]:
                        state["buttons"] = None
                return result

            adapter, _ = self.adapter(control)
            adapter.wait_counter = lambda field, count, label: windows.append(
                [read_override() for _ in range(count * reads_per_publication)])
            adapter.hold(1, 0x20, 4, "held native approach")
            self.assertTrue(windows[0])
            self.assertEqual(set(windows[0]), {0xFFDF})
            self.assertEqual(set(windows[1]), {None})
            self.assertIsNone(state["buttons"])

    def test_press_failure_still_attempts_neutral_clear_and_preserves_original_error(self):
        calls = []
        original = RuntimeError("owned press rejected")

        def control(command, **fields):
            calls.append(command)
            if command == "press":
                raise original
            raise RuntimeError("owned clear rejected")

        adapter, report = self.adapter(control)
        with self.assertRaises(RuntimeError) as raised:
            adapter.hold(1, 8, 4, "failure")
        self.assertIs(raised.exception, original)
        self.assertEqual(calls, ["press", "clear_input"])
        self.assertEqual(report["input_cleanup_errors"][0]["original_error"], str(original))

    def test_publication_wait_failure_also_releases_native_input(self):
        calls = []
        adapter, _ = self.adapter(lambda command, **fields: calls.append(command))

        def fail_wait(*args):
            raise RuntimeError("diagnostic publications stopped")

        adapter.wait_counter = fail_wait
        with self.assertRaisesRegex(RuntimeError, "publications stopped"):
            adapter.hold(1, 8, 4, "wait failure")
        self.assertEqual(calls, ["press", "clear_input"])

    def test_read_capture_view_rejects_control_fixture_and_memory_write_commands(self):
        calls = []
        client = OwnedReadClient(lambda command, **fields: calls.append(command))
        for command in ("press", "clear_input", "set_input", "write_ram", "coop_fixture", "quit"):
            with self.assertRaisesRegex(Exception, "cannot send"):
                client.request(command)
        self.assertEqual(calls, [])
        client.request("present_shot_seq")
        self.assertEqual(calls, ["present_shot_seq"])


if __name__ == "__main__":
    unittest.main()
