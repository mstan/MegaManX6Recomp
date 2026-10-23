"""Drive the actual-module replay fixture; no game/window or original assets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def verify(fixture: Path, output: Path) -> None:
    output = output.resolve() / f"native-replay-test-{time.time_ns()}"
    output.mkdir(parents=True, exist_ok=False)
    refusals = ("settings", "card", "outside-card", "bundle", "marker", "status",
                "incomplete", "inactive", "image", "online", "failed-trace", "truncated")
    failures = ("cycle", "caller", "frame", "previous", "taint", "tag", "mailbox")
    for case in ("complete", *refusals, *failures, "early-end", "state-replaced"):
        profile = output / case
        result = subprocess.run([str(fixture.resolve()), str(profile), case],
                                capture_output=True, timeout=30)
        (output / f"{case}.stdout.log").write_bytes(result.stdout)
        (output / f"{case}.stderr.log").write_bytes(result.stderr)
        expected = 17 if case in refusals else 42 if case in failures else 0
        assert result.returncode == expected, (case, result.returncode, result.stderr)
        # Native cards are exported/copy-only; neither live private card nor
        # retained initial bytes may change even on failed replay admission.
        expected_card = bytes(range(256)) * 512
        assert (profile / "saves/card1.mcd").read_bytes() == expected_card
        assert (profile / "replay/card1.initial.mcd").read_bytes() == expected_card
        if case in refusals:
            assert (profile / "refused.txt").read_text().strip()
            assert not (profile / "replay-result.json").exists()
            continue
        status = json.loads((profile / "replay-result.json").read_text())
        assert status["events"] == 8
        assert status["trace_sha256"] == hashlib.sha256((profile / "replay/inputs.jsonl").read_bytes()).hexdigest()
        if case == "complete":
            assert status["status"] == "consumed" and status["consumed"] == 8 and not status["failure"]
        else:
            assert status["status"] == "failed" and status["failure"]
            assert status["consumed"] == (1 if case in ("taint", "tag", "mailbox") else 0)
    print(f"PASS: actual replay admission/supply/terminal ownership, {len(refusals)} startup refusals, "
          f"{len(failures)} runtime mismatches, early/state-replaced end ({output})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verify(args.fixture, args.output)
