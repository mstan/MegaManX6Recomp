"""One owned native R13 route with bounded read-only execution trace evidence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
import time
from unittest.mock import patch

import qualify_mmx6_coop_enemy_admission as enemy
from coop_debug import DIAGNOSTIC_ADDRESS, DebugError
from prepare_mmx6_coop_playtest import sha256

EXE_SHA = "43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7"
WORLD = 0x8002000C
DRIVER = 0x80020C40
RETURN = 0x80020C80
HANDLER = 0x800EAFB0
ALIVE = 0x800EAC8C
TARGETS = (0x8001E9EC, 0x8001EA18, DRIVER, 0x80020C68, 0x80020C70,
           0x80020C78, RETURN, WORLD, 0x8002003C, 0x8002005C, 0x8002006C,
           0x80020088, 0x80020098, 0x800200A8, 0x800200B0, 0x800200C0,
           0x800200C8, 0x800200D0, 0x800200F4, 0x80020110,
           0x8002012C, 0x80029D18, HANDLER, ALIVE)


def complete_page(page, start, *, prologue=False):
    """Unfiltered sequence pagination must account for every selected row."""
    end = page["seq_hi"]
    rows = page["entries"]
    if (page["seq_lo"] != start or end < start or page["emitted"] != len(rows) or
            [row["seq"] for row in rows] != list(range(start, end))):
        raise DebugError("Trace sequence page was evicted, omitted or truncated")
    if prologue and any(int(row["func"], 16) != WORLD for row in rows):
        raise DebugError("Unexpected function in exact world prologue filter")
    if not prologue and any(int(row["target"], 16) not in TARGETS for row in rows):
        raise DebugError("Unexpected target outside selected trace filter")
    return rows, end


def analyze(dispatch, prologue, dirty, alive_window):
    if not dispatch or not prologue:
        raise DebugError("Empty execution trace")
    frames = [row["frame"] for row in dispatch]
    if frames != sorted(frames):
        raise DebugError("Trace frame order moved backwards")
    lo, hi = max(min(frames), min(row["frame"] for row in prologue)) + 1, min(max(frames), max(row["frame"] for row in prologue)) - 1
    if hi - lo < 30:
        raise DebugError("Insufficient complete interior frames")
    by_frame = defaultdict(Counter)
    for row in dispatch:
        by_frame[row["frame"]][hex(int(row["target"], 16))] += 1
    direct = Counter(row["frame"] for row in prologue)
    records = []
    for frame in range(lo, hi + 1):
        counts = by_frame[frame]
        records.append(dict(frame=frame, dispatch=dict(counts), world_prologue=direct[frame]))
    frame_ok = all(row["dispatch"].get(hex(WORLD), 0) == row["world_prologue"] == 1 and
                   row["dispatch"].get(hex(DRIVER), 0) == row["dispatch"].get(hex(RETURN), 0) == 1
                   for row in records)
    starts = [i for i, row in enumerate(dispatch) if int(row["target"], 16) == DRIVER]
    cycles = []
    for start, end in zip(starts, starts[1:]):
        rows = dispatch[start:end]
        counts = Counter(int(row["target"], 16) for row in rows)
        cycles.append(dict(seq_lo=rows[0]["seq"], seq_hi=dispatch[end]["seq"],
                           frame=rows[0]["frame"], world=counts[WORLD],
                           world_return=counts[RETURN], attack_pool=counts[0x8002012C],
                           stage_wrapper=counts[0x8001E9EC]))
    cycle_ok = len(cycles) >= 30 and all(row["world"] == row["world_return"] == 1 for row in cycles)
    a_lo, a_hi = alive_window
    handlers = Counter(row["frame"] for row in dispatch if int(row["target"], 16) == HANDLER and
                       int(row["a0"], 16) == enemy.POOL)
    bodies = Counter(row["frame"] for row in dirty if int(row["target"], 16) == ALIVE and
                     int(row["a0"], 16) == enemy.POOL)
    alive = [dict(frame=frame, handler=handlers[frame], body=bodies[frame])
             for frame in range(max(lo, a_lo + 1), min(hi, a_hi - 1) + 1)]
    alive_ok = len(alive) >= 20 and all(row["handler"] == row["body"] == 1 for row in alive)
    return dict(checks=dict(one_world_dispatch_and_prologue_per_interior_frame=frame_ok,
                            one_world_per_complete_native_driver_cycle=cycle_ok,
                            one_origin_bound_alive_body_per_interior_frame=alive_ok),
                frame_range=[lo, hi], frames=records, cycles=cycles,
                alive_frame_range=[a_lo, a_hi], alive_frames=alive,
                note="World prologue is independent of dispatch tracing; attack-pool and stage-wrapper counts are separate")


class TraceCollector:
    def __init__(self, control, destination, report):
        self.control, self.destination, self.report = control, destination, report
        self.last, self.direct_last, self.last_dirty_total = 0, 0, None
        self.dispatch, self.prologue, self.dirty = [], [], {}
        self.pages, self.when, self.busy = [], 0., False
        self.alive_start, self.square_frame = None, None
        self.pre_alive_gaps = []

    def arm(self):
        self.control("fntrace_arm_clear")
        for address in TARGETS:
            self.control("fntrace_arm", target=hex(address))
        armed = self.control("fntrace_armed")
        if armed["count"] != len(TARGETS) or {int(t, 16) for t in armed["targets"]} != set(TARGETS):
            raise DebugError("Exact trace target arm failed")
        self.control("fntrace_clear")
        self.control("fn_filter", lo=hex(WORLD), hi=hex(WORLD + 4))
        self.control("fn_clear")
        self.capture("armed", force=True)

    def capture(self, label, *, force=False):
        if self.busy or (not force and time.monotonic() - self.when < .20):
            return
        self.busy = True
        try:
            fn = self.control("fntrace_dump", count=4096, seq_lo=str(self.last))
            entries, self.last = complete_page(fn, self.last)
            self.dispatch.extend(entries)
            direct = self.control("fn_entry_dump", count=2048, seq_lo=str(self.direct_last))
            entries, self.direct_last = complete_page(direct, self.direct_last, prologue=True)
            self.prologue.extend(entries)
            flow = self.control("dirty_flow_log", count=65536, target_lo=hex(ALIVE), target_hi=hex(ALIVE + 4))
            oldest = flow["total"] - flow["available"]
            if self.last_dirty_total is not None and oldest > self.last_dirty_total:
                if self.alive_start is not None:
                    raise DebugError("Dirty body trace coverage was evicted during the live-actor window")
                self.pre_alive_gaps.append([self.last_dirty_total, oldest])
            if flow["emitted"] != len(flow["entries"]) or flow["emitted"] >= 65536:
                raise DebugError("Dirty body trace dump is incomplete")
            for row in flow["entries"]:
                if row["seq"] in self.dirty and self.dirty[row["seq"]] != row:
                    raise DebugError("Conflicting dirty body sequence")
                self.dirty[row["seq"]] = row
            self.last_dirty_total = flow["total"]
            page = dict(label=label, fntrace=fn, prologue=direct, dirty_flow=flow)
            self.pages.append(page)
            (self.destination / f"trace-page-{len(self.pages):03}.json").write_text(json.dumps(page) + "\n")
            frame = max((row["frame"] for row in self.dispatch), default=0)
            if self.report.get("initialized") and self.alive_start is None:
                self.alive_start = frame
            if label == "before Square":
                self.square_frame = frame
            self.when = time.monotonic()
        finally:
            self.busy = False


def run(args):
    original_run = enemy.baseline.run
    trace_result = {}

    def traced_baseline(candidate, port, timeout, legacy, *, exercise):
        def traced_exercise(control, client, destination, report):
            (destination / "world-trace-tool-source.py").write_bytes(Path(__file__).read_bytes())
            trace = TraceCollector(control, destination, report)
            trace.arm()
            original_world = original_text(args.disc.parent / "SLUS_013.95", WORLD, 0x120)
            if client.read(WORLD, 0x120) != original_world:
                raise DebugError("World code differs from original EXE")

            class ObservedClient:
                def read(self, address, size):
                    if address == DIAGNOSTIC_ADDRESS:
                        trace.capture("native observation")
                    return client.read(address, size)

                def request(self, command, **fields):
                    return client.request(command, **fields)

            def observed_control(command, **fields):
                if command == "press" and fields.get("port") == 2 and fields.get("buttons") == 0xFFDF and fields.get("frames") == 4:
                    fields["frames"] = args.right_frames
                if command == "press" and fields.get("port") == 2 and fields.get("buttons") == 0x7FFF:
                    trace.capture("before Square", force=True)
                return control(command, **fields)

            try:
                exercise(observed_control, ObservedClient(), destination, report)
            finally:
                control("fn_disable")  # Close the independent prologue window.
                trace.capture("finished", force=True)
                stats = control("fn_stats")
                raw = dict(dispatch=trace.dispatch, prologue=trace.prologue,
                           dirty_body=sorted(trace.dirty.values(), key=lambda row: row["seq"]),
                           prologue_stats=stats, target_count=len(TARGETS), targets=[hex(t) for t in TARGETS],
                           world_code_matches_original=client.read(WORLD, 0x120) == original_world,
                           alive_window=[trace.alive_start, trace.square_frame], pages=len(trace.pages),
                           pre_alive_dirty_gaps=trace.pre_alive_gaps)
                (destination / "native-trace.json").write_text(json.dumps(raw, indent=2) + "\n")
                trace_result.update(raw_path=str(destination / "native-trace.json"),
                                    raw_sha256=sha256(destination / "native-trace.json"))
                if trace.alive_start is not None and trace.square_frame is not None:
                    trace_result.update(analyze(trace.dispatch, trace.prologue, raw["dirty_body"], raw["alive_window"]))
                    trace_result["checks"]["world_code_matches_original"] = raw["world_code_matches_original"]
                    trace_result["checks"]["prologue_rows_accounted"] = stats["entry_total"] == len(trace.prologue) == stats["direct_filtered"] and stats["direct_no_cpu"] == 0
                    report.setdefault("checks", {}).update(trace_result["checks"])
                else:
                    report.setdefault("checks", {})["complete_trace_actor_attack_window"] = False
        return original_run(candidate, port, timeout, legacy, exercise=traced_exercise)

    forwarded = argparse.Namespace(candidate=None, build=args.build, source=args.source, disc=args.disc,
        output=args.output, expected_exe_sha256=EXE_SHA, expect_targeting_action2=True)
    with patch.object(enemy.baseline, "run", traced_baseline):
        result = enemy.run(forwarded)
    result["native_world_trace"] = trace_result
    result["trace_tool_sha256"] = sha256(args.output / "baseline/world-trace-tool-source.py")
    (args.output / "world-qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def original_text(path, address, size):
    data = path.read_bytes()
    load, text_size = struct.unpack_from("<II", data, 0x18)
    offset = address - load
    if offset < 0 or offset + size > text_size:
        raise ValueError("Original code span is outside PS-X EXE text")
    return data[0x800 + offset:0x800 + offset + size]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "source", "disc", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--right-frames", type=int, choices=(4, 10), default=10,
                        help="Bounded native right pulse;10 corrects observed short-pulse undershoot with trace RPCs")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(dict(status=result["status"], error=result.get("error"),
                          checks=result.get("native_world_trace", {}).get("checks"),
                          report=str(args.output / "world-qualification.json"))))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
