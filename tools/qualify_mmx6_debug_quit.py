"""Owned startup/quit protocol regression; no gameplay qualification.

Prepare one new private F:/G: profile, preserve the exact raw quit reply and
wait for natural exit even when that reply is invalid. Launch hidden/muted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import time

import qualify_mmx6_coop_baseline as baseline
from prepare_mmx6_coop_playtest import local_output, prepare, sha256


def run(args):
    output = local_output(args.output)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", args.port))
    prepared = prepare(args.build, args.source, output, args.disc, automated=True)
    report = dict(kind="owned_debug_quit_response", status="failed_setup", expected_id=424242,
        exe_sha256=prepared["exe_sha256"], runner_sha256=sha256(Path(__file__)),
        limits=["Startup and quit only; no gameplay or native card progress qualification",
                "Source observations at staging are not compilation provenance"])
    process = None
    try:
        if prepared["exe_sha256"] != args.expected_exe_sha256:
            raise ValueError("Candidate executable differs from the explicitly expected SHA256")
        environment = baseline.candidate_environment(output, prepared)
        with (output / "logs/probe-stdout.log").open("w") as stdout, \
                (output / "logs/probe-stderr.log").open("w") as stderr:
            process = subprocess.Popen([str(output / "mmx6-runtime.exe"), "--game",
                str(output / "game.toml"), "--memcard-dir", str(output / "saves"),
                "--hidden-window", "--debug-port", str(args.port)], cwd=output,
                env=environment, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            report["owned_pid"] = process.pid
            deadline = time.monotonic() + 30
            while not baseline.owns_listener(args.port, process.pid):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Owned debug listener unavailable")
                time.sleep(.1)
            with socket.create_connection(("127.0.0.1", args.port), timeout=5) as connection:
                connection.settimeout(5)
                connection.sendall(b'{"id":424242,"cmd":"quit"}\n')
                response = bytearray()
                while b"\n" not in response and len(response) < 4096:
                    chunk = connection.recv(4096 - len(response))
                    if not chunk:
                        break
                    response.extend(chunk)
                report["raw_response"] = response.decode("utf-8", errors="replace")
            # An invalid ACK must not make the harness race to terminate an
            # otherwise normally exiting process. Record both independently.
            try:
                process.wait(timeout=5)
                report["shutdown"] = "natural_exit"
            except subprocess.TimeoutExpired:
                report["shutdown"] = "owned_process_terminated"
                process.terminate()
                process.wait(timeout=5)
            report["exit_code"] = process.poll()
            try:
                report["response"] = json.loads(report["raw_response"])
            except ValueError:
                report["response"] = None
            reply = report["response"]
            report["checks"] = dict(
                matching_ack=isinstance(reply, dict) and type(reply.get("id")) is int and
                    reply["id"] == report["expected_id"] and reply.get("ok") is True,
                natural_exit_zero=report["shutdown"] == "natural_exit" and process.poll() == 0)
            report["status"] = "passed" if all(report["checks"].values()) else "failed"
    except Exception as error:
        report["error"] = str(error)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            report.update(shutdown="owned_process_terminated", exit_code=process.poll())
        report["process_gone"] = process.poll() is not None if process is not None else None
        report["listener_released"] = (not baseline.owns_listener(args.port, process.pid)
                                       if process is not None else None)
        (output / "probe-source.py").write_bytes(Path(__file__).read_bytes())
        (output / "qualification.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "source", "disc", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--port", type=int, default=24895)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_exe_sha256) or not 1 <= args.port <= 65535:
        parser.error("Expected a lowercase SHA256 and a port in1..65535")
    result = run(args)
    print(json.dumps(dict(status=result["status"], checks=result.get("checks"),
                         error=result.get("error"), report=str(args.output / "qualification.json"))))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
