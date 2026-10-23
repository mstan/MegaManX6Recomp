"""Accepted-input adapter ordering/error tests; no runtime launch or native proof."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mmx6_coop_published_input import PublishedHeldInput, PublishedInputError


class PublishedInputTests(unittest.TestCase):
    def adapter(self, network, *, fail_neutral=False):
        self.calls, self.active, self.windows, self.report = [], [0, 0], [], {}
        def publish(seat, bits):
            self.calls.append((seat, bits))
            if fail_neutral and bits == 0:
                raise RuntimeError("neutral failed")
            self.active[seat] = bits
        clients = [SimpleNamespace(host_input=lambda bits, seat=seat:publish(seat, bits)) for seat in range(2)]
        return PublishedHeldInput(clients, network, self.windows.append, self.report)

    @staticmethod
    def statuses(tick, resolved):
        return [dict(tick=tick, resolved_through=resolved) for _ in range(2)]

    def test_observes_while_held_until_both_resolved_and_keeps_nested_other_seat(self):
        history = iter([self.statuses(100, 98), self.statuses(102, 100),
                        self.statuses(124, 123), self.statuses(126, 125)])
        adapter = self.adapter(lambda:next(history))
        def observe():
            self.assertEqual(self.active[1], 0x2000)
            if not self.windows:
                adapter.hold(0, 8, 4, "P1 Start")
            self.assertEqual(self.active, [0, 0x2000])
            return self.active.copy()
        with patch("mmx6_coop_published_input.time.sleep"):
            samples = adapter.hold_observed(1, 0x2000, 12, "P2 dash", observe)
        self.assertEqual(len(samples), 3)
        self.assertEqual(self.active, [0, 0])
        self.assertEqual(self.calls, [(1, 0x2000), (0, 8), (0, 0), (1, 0)])
        self.assertEqual(self.windows, [4, 5, 5])
        self.assertEqual(self.report["held_input_windows"][0]["end"][0]["resolved_through"], 125)

    def test_neutral_error_does_not_replace_observer_error(self):
        adapter = self.adapter(lambda:self.statuses(100, 98), fail_neutral=True)
        def observe():
            raise ValueError("effect evidence rejected")
        with self.assertRaisesRegex(ValueError, "effect evidence rejected"):
            adapter.hold_observed(1, 0x2000, 12, "case", observe)
        self.assertEqual(self.calls[-1], (1, 0))
        self.assertEqual(self.report["held_input_cleanup_errors"][0]["original_error"], "effect evidence rejected")

    def test_regressed_resolved_tick_rejects_and_releases_without_observation(self):
        history = iter([self.statuses(100, 98), self.statuses(101, 97)])
        adapter = self.adapter(lambda:next(history))
        with self.assertRaises(PublishedInputError):
            adapter.hold_observed(1, 0x2000, 12, "case", lambda:self.fail("bad transport observed"))
        self.assertEqual(self.calls, [(1, 0x2000), (1, 0)])

    def test_transport_error_after_publish_still_releases_owned_seat(self):
        adapter = self.adapter(lambda:self.statuses(100, 98))
        def fail_window(count):
            raise RuntimeError("transport lost")
        adapter.window = fail_window
        with self.assertRaisesRegex(RuntimeError, "transport lost"):
            adapter.hold(1, 0x2000, 4, "case")
        self.assertEqual(self.calls, [(1, 0x2000), (1, 0)])


if __name__ == "__main__":
    unittest.main()
