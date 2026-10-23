"""Strict evidence checks for the optional same-host Windows Clang lab gate.

These consume the installed startup logger, not a claimed OS/build version.
The capability line is emitted only after the runtime checks features_known,
canonical FP controls, a sealed interpreter overlay policy and real offers.
String presence binds declared manifest bytes; it does not prove complete
dependency closure, native qualification or reproducible executable bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


class HostProfileError(ValueError):
    pass


class MissingHostProfile(HostProfileError):
    """A live log has not committed both required startup records yet."""


_SHA = r"[0-9a-f]{64}"
_NAME = r"[a-z0-9_.-]{1,31}"  # SDK netplay_host_profile.c name_ok(), including its 32-byte NUL.
_CAP_MARKER = "actual-image-sha256"
_SETTLED_MARKER = "host profile settled"
_CAP = re.compile(r"psxrecomp: actual-image-sha256=(" + _SHA + r") cpu-arch=([0-9]+) "
                  r"features=([0-9a-f]+) backend=([0-9]+) fp=([0-9]+) "
                  r"overlays=interpreted offers=([0-9]+)")
_SETTLED = re.compile(r"psxrecomp: host profile settled profile=(" + _NAME + r") "
                      r"revision=([0-9]+) selected_sha256=(" + _SHA + r") "
                      r"cycles=([0-9]+) sim_tick=([0-9]+) before-enter-guest=1")


def _uint(value: str, bits: int, field: str, base: int = 10) -> int:
    # Bound text before int() as well as the actual runtime integer range.
    if len(value) > (20 if base == 10 else 16):
        raise HostProfileError(f"Host profile {field} exceeds its integer contract")
    number = int(value, base)
    if number >= 1 << bits:
        raise HostProfileError(f"Host profile {field} exceeds its integer contract")
    return number


def parse_host_profile(text: str, *, final: bool = True) -> dict:
    """Exactly one complete capability and settlement record, in that order."""
    capabilities, settlements = [], []
    for index, raw in enumerate(text.splitlines(keepends=True)):
        relevant = _CAP_MARKER in raw or _SETTLED_MARKER in raw
        if not relevant:
            continue
        if not raw.endswith("\n"):
            if final:
                raise HostProfileError("Unterminated host profile record")
            continue  # Do not mistake an in-progress fprintf for malformed evidence.
        line = raw.rstrip("\r\n")
        if _CAP_MARKER in line:
            match = _CAP.fullmatch(line)
            if match is None:
                raise HostProfileError("Malformed host capability record")
            capabilities.append((index, dict(actual_image_sha256=match[1],
                cpu_arch=_uint(match[2], 32, "CPU architecture"),
                features=_uint(match[3], 64, "CPU features", 16),
                backend=_uint(match[4], 32, "backend"), fp=_uint(match[5], 32, "FP"),
                overlays="interpreted", offers=_uint(match[6], 32, "offers"))))
        else:
            match = _SETTLED.fullmatch(line)
            if match is None:
                raise HostProfileError("Malformed host profile settlement record")
            settlements.append((index, dict(profile=match[1],
                revision=_uint(match[2], 32, "revision"), selected_sha256=match[3],
                cycles=_uint(match[4], 64, "cycles"),
                sim_tick=_uint(match[5], 32, "simulation tick"), before_enter_guest=1)))
    if len(capabilities) > 1 or len(settlements) > 1:
        raise HostProfileError("Duplicate host capability or settlement records")
    if not capabilities or not settlements:
        raise MissingHostProfile("Missing host capability or settlement record")
    if capabilities[0][0] >= settlements[0][0]:
        raise HostProfileError("Host settlement preceded its capability installation")
    return dict(capabilities=capabilities[0][1], settlement=settlements[0][1])


def verify_host_profile_pair(logs: list[str], executable_sha256: list[str],
                             profile: str, revision: int, *, final: bool = True) -> dict:
    if len(logs) != 2 or len(executable_sha256) != 2:
        raise HostProfileError("Require exactly two owned peers")
    if (not isinstance(profile, str) or re.fullmatch(_NAME, profile) is None or type(revision) is not int or
            not 1 <= revision <= 0xFFFFFFFF):
        raise HostProfileError("Expected a bounded explicit profile name and revision")
    if (any(not isinstance(value, str) or re.fullmatch(_SHA, value) is None for value in executable_sha256) or
            len(set(executable_sha256)) != 1):
        raise HostProfileError("Staged peers must have one identical actual executable SHA256")
    peers = [parse_host_profile(text, final=final) for text in logs]
    for seat, peer in enumerate(peers):
        cap, selected = peer["capabilities"], peer["settlement"]
        if cap["actual_image_sha256"] != executable_sha256[seat]:
            raise HostProfileError(f"Peer {seat} actual image differs from its staged candidate")
        # This gate covers the deliberately narrow local lab contract only.
        # Match the current conservative lab rule, including its one offer.
        # Broader feature masks/catalogs require their own reviewed evidence.
        if (cap["cpu_arch"] != 2 or cap["features"] != 0x7F or
                cap["backend"] != 2 or cap["fp"] != 2 or cap["offers"] != 1):
            raise HostProfileError(f"Peer {seat} does not meet the x64/ENHANCED/FP2 lab contract")
        if selected["profile"] != profile or selected["revision"] != revision:
            raise HostProfileError(f"Peer {seat} settled an unexpected host profile or revision")
        if selected["cycles"] or selected["sim_tick"]:
            raise HostProfileError(f"Peer {seat} host agreement occurred after guest execution")
    if peers[0]["settlement"] != peers[1]["settlement"]:
        raise HostProfileError("Peers settled different host profile identities")
    if peers[0]["capabilities"] != peers[1]["capabilities"]:
        raise HostProfileError("Same-host peers reported different installed capabilities")
    return dict(profile=profile, revision=revision,
                selected_sha256=peers[0]["settlement"]["selected_sha256"], peers=peers)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HostProfileError(f"Duplicate build manifest JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise HostProfileError(f"Invalid JSON constant: {value}")


def _contains(path: Path, needle: bytes) -> bool:
    tail = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            data = tail + chunk
            if needle in data:
                return True
            tail = data[-(len(needle) - 1):]
    return False


def validate_build_manifest(build: Path, staged_executables: list[Path],
                            *, evidence_directory: Path | None = None) -> dict:
    """Validate the actual psx-runtime manifest/header and each staged image."""
    base = build / "psx_build_manifest/psx-runtime"
    candidates = [path for path in [base / "manifest.json", *base.glob("*/manifest.json")]
                  if path.is_file()]
    if len(candidates) != 1:
        raise HostProfileError("Require one unambiguous psx-runtime build manifest")
    manifest_path = candidates[0]
    header_path = manifest_path.with_name("manifest.h")
    try:
        manifest_bytes, header_bytes = manifest_path.read_bytes(), header_path.read_bytes()
    except OSError as error:
        raise HostProfileError("Declared build manifest/header is unavailable") from error
    try:
        item = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HostProfileError("Malformed build manifest JSON") from error
    if (not isinstance(item, dict) or type(item.get("schema")) is not int or item["schema"] != 1 or
            item.get("coverage") != "declared-build-inputs-v1" or item.get("whole_binary") is not False or
            item.get("heterogeneous_qualified") is not False or
            not isinstance(item.get("files"), dict) or not item["files"] or
            not any(isinstance(item.get(key), dict) and item[key]
                    for key in ("configuration", "configuration_by_language"))):
        raise HostProfileError("Unsupported or empty declared build manifest")
    for path, entry in item["files"].items():
        if (not path or not isinstance(entry, dict) or set(entry) != {"sha256", "bytes"} or
                not isinstance(entry["sha256"], str) or re.fullmatch(_SHA, entry["sha256"]) is None or
                type(entry["bytes"]) is not int or entry["bytes"] < 0):
            raise HostProfileError("Malformed declared build file metadata")
    digest = item.pop("sha256", None)
    if not isinstance(digest, str) or re.fullmatch(_SHA, digest) is None:
        raise HostProfileError("Malformed declared build SHA256")
    canonical = json.dumps(item, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    if hashlib.sha256(canonical).hexdigest() != digest:
        raise HostProfileError("Build manifest canonical SHA256 mismatch")
    try:
        header = header_bytes.decode("ascii")
    except UnicodeError as error:
        raise HostProfileError("Malformed build manifest header") from error
    sha_lines = [line for line in header.splitlines() if "PSX_BUILD_MANIFEST_SHA256" in line]
    schema_lines = [line for line in header.splitlines() if "PSX_BUILD_MANIFEST_SCHEMA" in line]
    if (sha_lines != [f'#define PSX_BUILD_MANIFEST_SHA256 "{digest}"'] or
            schema_lines != ["#define PSX_BUILD_MANIFEST_SCHEMA 1"]):
        raise HostProfileError("Build manifest header does not match validated JSON")
    try:
        bound = len(staged_executables) == 2 and all(_contains(path, digest.encode("ascii"))
                                                   for path in staged_executables)
    except OSError as error:
        raise HostProfileError("Staged host-profile executable is unavailable") from error
    if not bound:
        raise HostProfileError("A staged executable lacks the compiled declared manifest SHA256")
    record = dict(declared_sha256=digest, manifest_path=str(manifest_path), header_path=str(header_path),
        manifest_file_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        header_file_sha256=hashlib.sha256(header_bytes).hexdigest(),
        declared_files=len(item["files"]), staged_images_contain_compiled_sha256=True,
        whole_binary=False, heterogeneous_qualified=False)
    if evidence_directory is not None:
        evidence_directory.mkdir(parents=True, exist_ok=True)
        (evidence_directory / "host-profile-build-manifest.json").write_bytes(manifest_bytes)
        (evidence_directory / "host-profile-build-manifest.h").write_bytes(header_bytes)
    return record
