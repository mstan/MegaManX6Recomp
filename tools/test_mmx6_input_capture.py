"""Run the actual C++ capture helper fixture and independently check its files.

The fixture is a helper executable with read-only engine doubles, never a game.
No build, card import, live source mutation, or output deletion happens here.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import time

import mmx6_input_recording as trace


def inspect(root: Path, *, exit_child: bool) -> None:
    folders = list((root / "input-recordings").glob("session-*"))
    expected = {1} if exit_child else {*range(1, 7), *range(8, 13)}
    by_epoch = {}
    for folder in folders:
        status = json.loads((folder / "status.json").read_bytes())
        epoch = status["epoch"]
        assert epoch not in by_epoch, "duplicate epoch output"
        by_epoch[epoch] = (folder, status)
    assert set(by_epoch) == expected, (set(by_epoch), expected)
    for epoch, (folder, status) in by_epoch.items():
        data = (folder / "inputs.jsonl").read_bytes()
        if epoch in (4, 5):
            try:
                trace.validate(io.BytesIO(data), require_complete=False)
            except trace.InvalidRecording:
                pass
            else:
                raise AssertionError("zero-native prefix unexpectedly admitted")
            assert status["status"] == "failed"
            continue
        summary = trace.validate(io.BytesIO(data), require_complete=epoch not in (3, 8, 11, 12))
        assert summary.identity["image_sha256"] == "1" * 64
        assert summary.identity["manifest_sha256"] == "2" * 64
        assert summary.identity["execution_id"] == "fixture-execution"
        settings = (folder / "settings.json").read_bytes()
        card = (folder / "card1.initial.mcd").read_bytes()
        assert card == bytes(range(256)) * 512
        assert not (folder / "card2.initial.mcd").exists()
        trace.validate_startup_artifacts(summary.identity, settings=settings,
                                        cards=[card, None], baseline=None)
        assert trace.sha256((folder / "content.json").read_bytes()) == summary.identity["content_sha256"]
        assert trace.sha256((folder / "simulation-contract.json").read_bytes()) == summary.identity["simulation_contract_sha256"]
        rows = [json.loads(line) for line in data.splitlines()]
        if epoch == 1:
            assert settings == b'{"actual":"settings"}\n', "borrowed metadata changed worker artifact"
            assert (summary.events, summary.natives, summary.p2_reads) == (9, 2, 7)
            assert [row["consumer"] for row in rows if row["type"] == "C"] == [
                "stage", "controller-scene", "controller-inactive", "controller-blocked",
                "controller-player", "interaction", "stage"]
            assert [row["frame"] for row in rows if row["type"] == "N"] == [20, 20]
            assert summary.identity["mode"] == "offline"
        elif epoch == 2:
            assert summary.identity["mode"] == "netplay"
            assert summary.identity["profile"] == {"id": "fixture-profile", "revision": 2, "selected_sha256": "6" * 64}
            assert rows[1]["native"] == 0 and rows[1]["sim_tick"] == 3
            try:
                trace.validate(io.BytesIO(data), expected_identity=summary.identity, offline_replay=True)
            except trace.InvalidRecording as error:
                assert "network" in str(error)
            else:
                raise AssertionError("network recording admitted for offline replay")
        elif epoch in (3, 8):
            assert summary.failure and ("unilateral" if epoch == 3 else "state replaced") in summary.failure
            try:
                trace.validate(io.BytesIO(data))
            except trace.InvalidRecording:
                pass
            else:
                raise AssertionError("contaminated capture admitted as complete")
        elif epoch in (9, 10):
            observed = json.loads((root / f"F143-idle-flush-{epoch}.json").read_bytes())
            assert observed["visible_before_close"] == observed["still_open"] == 1
            assert 0 <= observed["elapsed_ms"] < 2000
            assert summary.identity["mode"] == ("netplay" if epoch == 10 else "offline")
            assert (summary.events, summary.natives, summary.p2_reads) == (2, 1, 1)
        elif epoch in (11, 12):
            assert summary.failure == "bounded native-consumption queue full"
            assert 8192 <= summary.events < 100001
            assert summary.natives == 1 and summary.p2_reads == summary.events - 1
            assert summary.identity["mode"] == ("netplay" if epoch == 12 else "offline")
            assert all(row["consumer"] == "stage" and row["buttons"] == 8
                       for row in rows if row["type"] == "C")
            try:
                trace.validate(io.BytesIO(data), require_complete=True)
            except trace.InvalidRecording:
                pass
            else:
                raise AssertionError("full-queue prefix admitted as complete")
        else:
            assert epoch == 6 and summary.natives == 1
        assert status["status"] == ("failed" if epoch in (3, 8, 11, 12) else "finalized")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve() / f"capture-test-{time.time_ns()}"
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop("MMX6_INPUT_RECORDING", None)
    env.pop("MMX6_INPUT_RECORDING_DIR", None)
    for name, extra in (("ordinary", []), ("exit", ["--atexit"])):
        root = output / name
        result = subprocess.run([str(args.fixture.resolve()), str(root), *extra],
                                env=env, capture_output=True, text=True, timeout=30)
        (output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        assert result.returncode == 0, (result.returncode, result.stderr)
        if not extra:
            assert "capture unavailable/failed" in result.stderr
            assert (root / "not-a-directory").read_bytes() == b"preserve existing output\n"
            assert json.loads((root / "F143-flush-error.json").read_bytes()) == {
                "actual_flush_failure_visible": True}
        inspect(root, exit_child=bool(extra))
    print(f"PASS: actual native-consumption worker/codec interop, failure and std::exit ({output})")


if __name__ == "__main__":
    main()
