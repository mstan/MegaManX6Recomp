"""Compare the actual C resolver with independent original-disc metadata.

This checks 45 records/47 voice calculations, not native sound playback.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from audit_mmx6_private_action_audio import original_sources, resolve_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--scratch-root", type=Path, required=True)
    args = parser.parse_args()
    exe, disc = os.environ.get("MMX6_AUDIO_EXE"), os.environ.get("MMX6_AUDIO_DISC")
    if not exe or not disc:
        print("SKIP: supply MMX6_AUDIO_EXE and MMX6_AUDIO_DISC originals")
        return 77
    scratch = args.scratch_root.resolve()
    if scratch.drive.casefold() == "c:":
        raise ValueError("Put original-data test scratch on a non-C drive")
    _, _, banks = original_sources(Path(exe), Path(disc))
    records = resolve_records(banks)
    expected = []
    mask = 0
    for record in records:
        effective = record["effective_bank_group"]
        bank, native_id = (30, 14) if effective == 1 else (31, 15)
        for tone in record["tones"]:
            mask |= 1 << tone["voice"]
            expected.append((record["group"], record["record"], tone["voice"], bank, native_id,
                tone["program"], tone["tone"], tone["offset"], tone["bytes"],
                tone["note"], tone["shift"], tone["adsr_lo"], tone["adsr_hi"]))
    if len(records) != 45 or len(expected) != 47 or mask != 0xF00B09:
        raise ValueError("Original source record census changed")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="records-", dir=scratch) as folder:
        paths = [Path(folder) / f"group{group}.bin" for group in (1, 3)]
        for path, group in zip(paths, (1, 3)):
            path.write_bytes(banks[group]["header"])
        result = subprocess.run([str(args.fixture.resolve()), str(paths[0]),
            str(len(banks[1]["samples"])), str(paths[1]), str(len(banks[3]["samples"]))],
            check=True, capture_output=True, text=True, timeout=30)
    lines = result.stdout.splitlines()
    if not lines or lines[0] != f"mask {mask}":
        raise ValueError("C private voice mask differs from original data")
    actual = [tuple(map(int, line.split())) for line in lines[1:]]
    if actual != expected:
        raise ValueError("C record/voice/bank/program/tone/sample/note/ADSR differs from original data")
    print("PASS: original-disc differential, 45 records / 47 voices / 9 private slots; no native playback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
