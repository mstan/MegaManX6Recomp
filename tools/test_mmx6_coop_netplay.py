"""Observe an existing private X6 pair; optionally exercise host controller input.

This script never launches/stops a process, writes RAM, loads a state or issues
fixtures. Default mode observes only. An optional pad smoke requires an active
two-player delay session and both heroes idle in a safe, clear intro location.

Equal diagnostic publication counts and host hashes are partial observations,
not matching framework simulation ticks or proof of whole-machine determinism.
No burndown gameplay row should be closed from observation-only output.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import re
import sys
import time
import traceback

from coop_debug import DebugClient, DebugError, Observation, observe


class FailedSetup(RuntimeError):
    """The requested native situation or required diagnostics were unavailable."""


class ValidationFailure(RuntimeError):
    """A check failed after setup was established."""


def require(condition, reason):
    if not condition:
        raise ValidationFailure(reason)


def native_ready(row: Observation) -> bool:
    return (row.ready == 1 and row.enrolled == 1 and row.failed == 0 and
            row.native_mode == 10 and row.native_phase == 0 and
            row.lifecycle == (0, 0) and row.scene_owner == 0 and row.mailbox == 0 and
            all(player.active and player.state == 1 and player.action == 2
                for player in row.players))


def require_framework_digest(rows: list[Observation]) -> None:
    if any(row.framework_digest_registered != 1 for row in rows):
        raise FailedSetup("Both candidates must report a registered framework host-state digest")


def pair_match(left: Observation, right: Observation) -> dict:
    """Compare one publication count; never compare different asynchronous ticks."""
    require(left.schema == right.schema == 1, "Paired checks require diagnostic schema 1")
    require(left.tick == right.tick, "Cannot compare different diagnostic publication counts")
    require(left.sequence == right.sequence, "Diagnostic sequences differ at equal publication count")
    require(left.host_digest_algorithm == right.host_digest_algorithm == 1,
            "Paired host digest algorithm is unavailable")
    require(left.host_digest == right.host_digest, f"Host digest differs at diagnostic tick {left.tick}")
    require(left.players == right.players and left.lifecycle == right.lifecycle,
            f"Published players/lifecycle differ at diagnostic tick {left.tick}")
    require((left.native_mode, left.native_phase, left.scene_owner, left.scene_phase,
             left.pause_owner, left.native_timer) ==
            (right.native_mode, right.native_phase, right.scene_owner, right.scene_phase,
             right.pause_owner, right.native_timer),
            f"Published world/scene ownership differs at diagnostic tick {left.tick}")
    return dict(diagnostic_tick=left.tick, diagnostic_sequence=left.sequence,
                host_digest=f"{left.host_digest:08x}",
                evidence="partial host-state observation; not a framework simulation tick")


def validate_status(status: list[dict]) -> None:
    for seat, row in enumerate(status):
        if not all(key in row for key in ("active", "rollback", "players", "desync", "host")):
            raise FailedSetup(f"Peer {seat}: incomplete netplay_status schema")
        if row["active"] != 1 or row["rollback"] != 0 or row["players"] != 2:
            raise FailedSetup(f"Peer {seat}: require active two-player delay-sync: {row}")
        require(row["desync"] == 0, f"Peer {seat}: input contract desynchronized: {row}")
    if [row["host"] for row in status] != [1, 0]:
        raise FailedSetup("--host-port/--guest-port do not identify host and guest respectively")


def non_c_path(raw: str) -> Path:
    path = Path(raw).resolve()
    if path.drive.upper() == "C:":
        raise argparse.ArgumentTypeError("Generated evidence must be stored off C:")
    return path


def bounded_positive(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or not 0 < value <= 60:
        raise argparse.ArgumentTypeError("Expected a finite duration in (0, 60]")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-port", type=int, required=True)
    parser.add_argument("--guest-port", type=int, required=True)
    parser.add_argument("--host-diagnostic", type=lambda value: int(value, 0), default=0x9F080000)
    parser.add_argument("--guest-diagnostic", type=lambda value: int(value, 0), default=0x9F080000)
    parser.add_argument("--output", type=non_c_path, required=True)
    parser.add_argument("--candidate", required=True, help="Exact game/framework/UI/build identity")
    parser.add_argument("--seconds", type=bounded_positive, default=6.0)
    parser.add_argument("--timeout", type=bounded_positive, default=3.0)
    parser.add_argument("--exercise-pads", action="store_true",
                        help="Move each hero right through host input in safe idle intro gameplay")
    args = parser.parse_args(argv)
    if args.host_port == args.guest_port:
        parser.error("Host and guest ports must differ")
    if not args.candidate.strip():
        parser.error("Candidate identity cannot be empty")
    if (args.output / "result.json").exists():
        parser.error("Output already contains result.json; choose a fresh evidence directory")
    args.output.mkdir(parents=True, exist_ok=True)
    report = dict(schema=1, candidate=args.candidate, result="failed_setup",
                  requested_pad_scenario=args.exercise_pads, observations=[], checks=[],
                  network_status="unverified", whole_machine_determinism="unverified",
                  save_load_rewind_rollback="unverified", core_mod_simulation_crc="unverified",
                  warnings=["Host digest excludes framework CPU/device/guest RAM state.",
                            "Diagnostic tick is a publication count, not a netplay simulation tick.",
                            "Pinned framework core logs have no host-mod digest partition."])
    peers = [DebugClient(port, timeout=args.timeout) for port in (args.host_port, args.guest_port)]
    addresses = (args.host_diagnostic, args.guest_diagnostic)
    changed_input = False
    setup_complete = False
    result = 2
    executor = ThreadPoolExecutor(max_workers=2)

    def both(method, *values):
        jobs = [executor.submit(method, i, *values) for i in range(2)]
        results, errors = [], []
        for job in jobs:
            try:
                results.append(job.result())
            except Exception as error:
                results.append(None)
                errors.append(error)
        if errors:
            raise errors[0]
        return results

    def rows():
        observations = both(lambda i: observe(peers[i], addresses[i]))
        if any(row.failed for row in observations):
            raise ValidationFailure("Co-op diagnostic reports failed initialization")
        if any(row.mailbox for row in observations):
            raise FailedSetup("Raw P2 input mailbox is armed; require real transport input")
        report["observations"].append([row.json() for row in observations])
        return observations

    def status(required=False):
        try:
            result = both(lambda i: peers[i].request("netplay_status"))
        except DebugError as error:
            if required:
                raise FailedSetup(f"Required netplay_status unavailable: {error}") from error
            # Only an explicit unknown command permits observation-only use.
            if not re.search(r"unknown|not found|unsupported", str(error), re.I):
                raise
            report["network_status_error"] = str(error)
            return None
        validate_status(result)
        report["network_status"] = "validated_active_two_peer_delay_session"
        report["last_network_status"] = result
        return result

    def sample(label, seconds):
        deadline = time.monotonic() + seconds
        history = [{}, {}]
        matched = set()
        comparisons = []
        while time.monotonic() < deadline:
            observations = rows()
            for seat, row in enumerate(observations):
                history[seat][row.tick] = row
                # Bound memory even if one peer stops or drifts indefinitely.
                if len(history[seat]) > 256:
                    del history[seat][next(iter(history[seat]))]
            for tick in sorted((set(history[0]) & set(history[1])) - matched):
                comparisons.append(pair_match(history[0][tick], history[1][tick]))
                matched.add(tick)
            time.sleep(.01)
        if len(comparisons) < 2:
            raise FailedSetup(f"{label}: fewer than two matching diagnostic publication counts; asynchronous reads are not equality evidence")
        status(required=args.exercise_pads)
        report["checks"].append(dict(name=label, result="pass", comparisons=comparisons))
        return observations

    def advance(count, timeout=12):
        start = rows()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = rows()
            if all(((row.tick - old.tick) & 0xFFFFFFFF) >= count for row, old in zip(current, start)):
                return current
            time.sleep(.02)
        raise ValidationFailure("Diagnostic publications stopped advancing")

    try:
        status(required=args.exercise_pads)
        initial = rows()
        if not all(row.ready == 1 and row.enrolled == 1 for row in initial):
            raise FailedSetup("Both co-op plugins must already be ready and enrolled")
        if args.exercise_pads and not all(native_ready(row) for row in initial):
            raise FailedSetup("Pad smoke requires both live heroes idle in safe unlocked intro gameplay")
        setup_complete = True
        sample("initial coherent paired host state", args.seconds)
        if args.exercise_pads:
            changed_input = True  # Cleanup must run even if the second peer rejects input.
            both(lambda i: peers[i].host_input(0))
            advance(10)
            for seat in (1, 0):
                before = rows()
                peers[seat].host_input(0x20)
                try:
                    advance(20)
                finally:
                    peers[seat].host_input(0)
                after = advance(12)
                for peer in (0, 1):
                    require(after[peer].players[seat].x_raw > before[peer].players[seat].x_raw + (15 << 16),
                            f"Peer {peer}: seat {seat + 1} did not move right through the transport")
                    require(after[peer].players[seat ^ 1].x_raw == before[peer].players[seat ^ 1].x_raw,
                            f"Peer {peer}: moving seat {seat + 1} also moved its idle partner")
                report["checks"].append(dict(name=f"seat {seat + 1} host pad movement", result="pass",
                                              before=[row.json() for row in before],
                                              after=[row.json() for row in after]))
                status(required=True)
                sample(f"seat {seat + 1} post-input coherent paired host state", args.seconds)
        report["result"] = "pass"
        report["qualification"] = "bounded diagnostic/input smoke only; parity remains unverified"
        result = 0
    except (FailedSetup, DebugError, ValueError) as error:
        report.update(result="failed_setup", error=str(error), traceback=traceback.format_exc())
        result = 2
    except ValidationFailure as error:
        report.update(result="fail" if setup_complete else "failed_setup", error=str(error),
                      traceback=traceback.format_exc())
        result = 1 if setup_complete else 2
    except Exception as error:
        report.update(result="fail" if setup_complete else "failed_setup", error=str(error),
                      traceback=traceback.format_exc())
        result = 1 if setup_complete else 2
    finally:
        if changed_input:
            cleanup_errors = []
            for peer in peers:
                try:
                    peer.release()
                except DebugError as error:
                    cleanup_errors.append(str(error))
            if cleanup_errors:
                report["cleanup_errors"] = cleanup_errors
                if report["result"] == "pass":
                    report["result"] = "fail"
                    result = 1
        executor.shutdown(wait=True)
        (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(result=report["result"], report=str(args.output / "result.json"),
                         error=report.get("error"))))
    return result


if __name__ == "__main__":
    sys.exit(main())
