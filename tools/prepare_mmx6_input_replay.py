"""Prepare a fresh private offline replay profile; never launch or import cards.

The candidate must be the exact recorded executable with its original resolved
configuration sources. Resolved settings.json is evidence, not a settings file
that this tool can reconstruct. Actual startup compares every retained bundle
again and refuses unsupported/unsealed offline setup before guest entry.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tomllib

from mmx6_input_recording import canonical, validate, validate_startup_artifacts
from prepare_mmx6_coop_playtest import local_output

MAX_EVENTS = 262144
MAX_BYTES = 128 * 1024 * 1024
STATUS_SCOPE = "native-consumption diagnostics; replay unimplemented"


def bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"Oversized replay artifact: {path.name}")
    return data


def prepare(recording: Path, candidate: Path, output: Path) -> dict:
    recording, candidate = recording.resolve(strict=True), candidate.resolve(strict=True)
    output = local_output(output)
    if output.exists():
        raise ValueError("Replay profile must be new; preserve existing output")
    if any(output.is_relative_to(source) or source.is_relative_to(output)
           for source in (recording, candidate)):
        raise ValueError("Replay output must be separate from its sources")
    trace = bounded(recording / "inputs.jsonl", MAX_BYTES)
    summary = validate(io.BytesIO(trace), max_events=MAX_EVENTS)
    identity = summary.identity
    if identity["mode"] != "offline" or identity["baseline"] is not None:
        raise ValueError("Only complete offline cold-boot native-consumption traces are supported")
    artifacts = {name: bounded(recording / name, 1024 * 1024)
                 for name in ("settings.json", "content.json", "simulation-contract.json")}
    cards = []
    for slot, expected in enumerate(identity["cards"], 1):
        path = recording / f"card{slot}.initial.mcd"
        if expected is None:
            if path.exists():
                raise ValueError("Absent recorded card has an artifact")
            cards.append(None)
        else:
            cards.append(bounded(path, 131072))
    validate_startup_artifacts(identity, settings=artifacts["settings.json"], cards=cards, baseline=None)
    for name, key in (("content.json", "content_sha256"),
                      ("simulation-contract.json", "simulation_contract_sha256")):
        if hashlib.sha256(artifacts[name]).hexdigest() != identity[key]:
            raise ValueError(f"Retained {name} does not match the recorded identity")
    status_bytes = bounded(recording / "status.json", 4096)
    status = json.loads(status_bytes)
    if (type(status) is not dict or set(status) != {"contract", "epoch", "failure", "schema", "scope", "status"}
            or status_bytes != canonical(status) or type(status["schema"]) is not int or type(status["epoch"]) is not int
            or not 0 < status["epoch"] <= 0xFFFFFFFFFFFFFFFF
            or status != dict(contract="mmx6.native-consumption.v1", epoch=status["epoch"], failure="",
                              schema=1, scope=STATUS_SCOPE, status="finalized")):
        raise ValueError("Recording status must be canonical, finalized and untainted")
    exe = bounded(candidate / "mmx6-runtime.exe", 1024 * 1024 * 1024)
    if hashlib.sha256(exe).hexdigest() != identity["image_sha256"]:
        raise ValueError("Candidate executable differs from the recorded actual image")
    if identity["manifest_sha256"].encode("ascii") not in exe:
        raise ValueError("Candidate lacks the declared compiled manifest SHA bytes")
    # These are real runtime file names. No launcher reconstruction, user-card
    # imports or generated state is copied. The --memcard-dir argument below
    # clears explicit slot paths at both ordinary runtime override boundaries.
    config = candidate / "game.toml"
    tomllib.loads(config.read_text(encoding="utf-8-sig"))
    if not (candidate / "settings.toml").is_file():
        raise ValueError("Original candidate settings.toml is required; never invent resolved preferences")
    output.mkdir(parents=True, exist_ok=False)
    (output / "mmx6-runtime.exe").write_bytes(exe)
    for source in candidate.glob("*.dll"):
        shutil.copy2(source, output / source.name)
    for name in ("assets", "bios", "mods"):
        if (candidate / name).is_dir():
            shutil.copytree(candidate / name, output / name)
    for name in ("game.toml", "settings.toml", "keybinds.ini", "disc.cfg", "bios.cfg"):
        if (candidate / name).is_file():
            shutil.copy2(candidate / name, output / name)
    for name in ("replay", "saves", "temp", "cache", "data", "appdata", "resident", "logs"):
        (output / name).mkdir(exist_ok=False)
    (output / "replay/inputs.jsonl").write_bytes(trace)
    (output / "replay/status.json").write_bytes(status_bytes)
    for name, data in artifacts.items():
        (output / "replay" / name).write_bytes(data)
    for slot, card in enumerate(cards, 1):
        if card is not None:
            (output / f"replay/card{slot}.initial.mcd").write_bytes(card)
            (output / f"saves/card{slot}.mcd").write_bytes(card)
    trace_sha = hashlib.sha256(trace).hexdigest()
    (output / "replay-profile.txt").write_text(
        f"mmx6-native-replay-private-v1\n{identity['image_sha256']}\n{trace_sha}\n", encoding="ascii")
    environment = {
        "TEMP": str(output / "temp"), "TMP": str(output / "temp"),
        "LOCALAPPDATA": str(output / "data"), "APPDATA": str(output / "appdata"),
        "XDG_CACHE_HOME": str(output / "cache"), "PYTHONPYCACHEPREFIX": str(output / "cache/pycache"),
        "PSX_RESIDENT_CACHE": str(output / "resident"), "PSX_OVERLAY_CACHE_DIR": str(output / "cache"),
        "PSX_OVERLAY_CAPTURE_ROOT": str(output / "cache"),
        "PSX_OVERLAY_CAPTURES": str(output / "cache/overlay_captures.json"),
        "MMX6_INPUT_REPLAY": str(output / "replay/inputs.jsonl"), "MMX6_INPUT_REPLAY_PROFILE": str(output),
        "MMX6_INPUT_RECORDING_DIR": str(output / "input-recordings"), "SDL_AUDIODRIVER": "dummy",
    }
    receipt = {
        "schema": 1, "kind": "private_offline_native_consumption_replay_preparation",
        "runtime_qualified": False, "recording": str(recording), "candidate": str(candidate),
        "image_sha256": identity["image_sha256"], "trace_sha256": trace_sha, "events": summary.events,
        "executable": str(output / "mmx6-runtime.exe"), "cwd": str(output), "environment": environment,
        "arguments": ["--game", str(output / "game.toml"), "--memcard-dir", str(output / "saves"),
                      "--seal-interpreted-overlays", "--no-launcher"],
        "required_environment_cleanup_prefixes": ["PSX_", "MMX6_INPUT_", "RNET_", "LNG_"],
        "startup_prerequisite": "caller must select supported immutable interpreted offline configuration before guest0; observer never seals",
        "limits": ["Preparation never executes the runtime", "Full raw SIO/publication replay and outcome comparison are unqualified",
                   "Resolved settings are compared at actual startup, not reconstructed from JSON",
                   "Compiled manifest SHA presence is an additional declared-byte check, not exhaustive binary provenance"],
    }
    (output / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    (output / "replay-preparation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.recording, args.candidate, args.output), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Replay preparation refused: {error}\n")
