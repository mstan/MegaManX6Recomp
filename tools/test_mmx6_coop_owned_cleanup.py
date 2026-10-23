"""Owned shutdown outcomes with mock Popen objects; no game is launched."""
import subprocess
import unittest

from coop_debug import DebugError
from qualify_mmx6_coop_baseline import stop_owned_runtime


class MockProcess:
    """Script actual exit separately from quit RPC success or failure."""
    def __init__(self, events, wait_results=(), *, returncode=None):
        self.events = events
        self.wait_results = iter(wait_results)
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.events.append(("wait", timeout))
        outcome = next(self.wait_results)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired("owned-runtime", timeout)
        self.returncode = outcome
        return outcome

    def terminate(self):
        self.events.append("terminate")

    def kill(self):
        self.events.append("kill")


class OwnedShutdownTests(unittest.TestCase):
    def run_cleanup(self, wait_results, *, quit_error=None, returncode=None):
        events = []
        process = MockProcess(events, wait_results, returncode=returncode)

        def request_quit():
            events.append("quit")
            if quit_error:
                raise quit_error

        result = stop_owned_runtime(process,
            clear_inputs=(lambda: events.append("clear"),), request_quit=request_quit)
        return result, events

    def test_invalid_ack_still_waits_for_normal_exit_without_termination(self):
        message = "quit: invalid or mismatched response id"
        result, events = self.run_cleanup([0], quit_error=DebugError(message))
        self.assertEqual(events, ["clear", "quit", ("wait", 5)])
        self.assertEqual(result, dict(
            shutdown="natural_exit_after_quit_protocol_error", exit_code=0,
            quit_protocol_error=dict(type="DebugError", message=message)))

    def test_invalid_ack_timeout_waits_before_terminating_only_owned_process(self):
        result, events = self.run_cleanup(["timeout", 0],
                                         quit_error=DebugError("quit: busy ACK id 0"))
        self.assertEqual(events, ["clear", "quit", ("wait", 5), "terminate", ("wait", 5)])
        self.assertEqual(result["shutdown"], "owned_popen_terminated")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["quit_protocol_error"],
                         dict(type="DebugError", message="quit: busy ACK id 0"))
        self.assertEqual(result["natural_exit_timeout"]["type"], "TimeoutExpired")

    def test_earlier_process_exit_never_sends_controls_quit_or_signals(self):
        for code in (0, 1):
            with self.subTest(code=code):
                result, events = self.run_cleanup([], returncode=code)
                self.assertEqual(events, [])
                self.assertEqual(result, dict(shutdown="already_exited", exit_code=code))

    def test_good_ack_and_exit_is_graceful_with_exact_exit_code(self):
        result, events = self.run_cleanup([0])
        self.assertEqual(events, ["clear", "quit", ("wait", 5)])
        self.assertEqual(result, dict(shutdown="graceful_owned_debug", exit_code=0))

    def test_good_ack_does_not_substitute_for_actual_exit(self):
        result, events = self.run_cleanup(["timeout", 1])
        self.assertEqual(events, ["clear", "quit", ("wait", 5), "terminate", ("wait", 5)])
        self.assertEqual(result["shutdown"], "owned_popen_terminated")
        self.assertEqual(result["exit_code"], 1)
        self.assertNotIn("quit_protocol_error", result)

    def test_owned_termination_timeout_has_bounded_kill_fallback(self):
        result, events = self.run_cleanup(["timeout", "timeout", -9])
        self.assertEqual(events, ["clear", "quit", ("wait", 5), "terminate", ("wait", 5),
                                  "kill", ("wait", 5)])
        self.assertEqual(result["shutdown"], "owned_popen_killed")
        self.assertEqual(result["exit_code"], -9)

    def test_release_error_retained_and_other_release_and_quit_still_attempted(self):
        events = []
        process = MockProcess(events, [0])

        def failed_release():
            events.append("failed_clear")
            raise DebugError("Owned runtime does not own the debug listener")

        result = stop_owned_runtime(process,
            clear_inputs=(failed_release, lambda: events.append("second_clear")),
            request_quit=lambda: events.append("quit"))
        self.assertEqual(events, ["failed_clear", "second_clear", "quit", ("wait", 5)])
        self.assertEqual(result["shutdown"], "natural_exit_after_input_release_error")
        self.assertEqual(result["input_release_errors"], [dict(index=0, type="DebugError",
                         message="Owned runtime does not own the debug listener")])

    def test_listener_guard_rejection_never_bypassed_to_retry_unowned_quit(self):
        events = []
        process = MockProcess(events, [0])

        def guarded_quit():
            events.append("listener_check")
            raise DebugError("Owned process does not own this debug listener")

        result = stop_owned_runtime(process, clear_inputs=(), request_quit=guarded_quit)
        self.assertEqual(events, ["listener_check", ("wait", 5)])
        self.assertEqual(result["shutdown"], "natural_exit_after_quit_protocol_error")
        self.assertEqual(result["quit_protocol_error"]["message"],
                         "Owned process does not own this debug listener")


if __name__ == "__main__":
    unittest.main()
