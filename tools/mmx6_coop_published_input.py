"""Owned pair's accepted host sampler; no direct SIO, RAM or mailbox access.

The caller supplies its existing PID-checked clients and validated transport
observer. Native behavior still needs independent game observations.
"""
from __future__ import annotations

import time


class PublishedInputError(RuntimeError):
    pass


class PublishedHeldInput:
    def __init__(self, clients, network, transport_window, report, *, timeout=20):
        if len(clients) != 2 or not callable(network) or not callable(transport_window):
            raise ValueError("Require two owned clients and validated transport callbacks")
        if not 0 < timeout <= 60:
            raise ValueError("Require a bounded input deadline")
        self.clients, self.network, self.window = clients, network, transport_window
        self.report, self.timeout = report, timeout
        report.setdefault("held_input_windows", [])
        report.setdefault("held_input_cleanup_errors", [])

    @staticmethod
    def validate(seat, bits, frames, observed=False):
        if (seat not in (0, 1) or type(bits) is not int or not 0 <= bits <= 0xFFFF or
                type(frames) is not int or not (6 if observed else 1) <= frames <= 120):
            raise ValueError("Expected a native seat/mask and bounded transport window")

    def _release(self, seat, label, original):
        try:
            self.clients[seat].host_input(0)
        except Exception as error:
            self.report["held_input_cleanup_errors"].append(dict(label=label, seat=seat,
                error=str(error), original_error=str(original) if original else None))
            if original is None:
                raise

    def hold(self, seat, bits, frames, label):
        self.validate(seat, bits, frames)
        failure = None
        try:
            self.clients[seat].host_input(bits)
            self.window(frames)
        except BaseException as error:
            failure = error
            raise
        finally:
            self._release(seat, label, failure)
        self.window(5)

    def hold_observed(self, seat, bits, frames, label, observe):
        self.validate(seat, bits, frames, observed=True)
        if not callable(observe):
            raise ValueError("Require an observer during held input")
        start, samples, failure = self.network(), [], None
        try:
            self.clients[seat].host_input(bits)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                status = self.network()
                if any(now["tick"] < old["tick"] or now["resolved_through"] < old["resolved_through"]
                       for now, old in zip(status, start)):
                    raise PublishedInputError("Transport counters moved backwards during held input")
                samples.append(observe())
                if len(samples) >= 3 and all(now["resolved_through"] >= old["tick"] + frames
                                            for now, old in zip(status, start)):
                    self.report["held_input_windows"].append(dict(label=label, seat=seat,
                        pressed=bits, requested_frames=frames, start=start, end=status,
                        observations=len(samples), input_path="published_host"))
                    break
                time.sleep(.015)
            else:
                raise PublishedInputError("Transport did not resolve the observed held-input window")
        except BaseException as error:
            failure = error
            raise
        finally:
            self._release(seat, label, failure)
        self.window(5)
        return samples
