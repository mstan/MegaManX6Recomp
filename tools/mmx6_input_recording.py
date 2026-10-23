"""Strict schema-1 native-consumption trace codec; no runtime recorder/replayer.

N is one original 80012A34 post-decode boundary at 80012C44; C is one actual
co-op p2_input read. This module validates startup artifacts without touching SIO,
the game, memory-card paths, or controller ownership. See the R26 source audit.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import BinaryIO


MAX_LINE = 16384
MAX_BASELINE = 64 * 1024 * 1024
CARD_BYTES = 128 * 1024
CONTRACT = "mmx6.native-consumption.v1"
NATIVE_CALLERS = frozenset((0x80012220, 0x8001A834, 0x8001AB18))
P2_CONSUMERS = frozenset(("stage", "controller-scene", "controller-inactive",
                          "controller-blocked", "controller-player", "interaction"))


class InvalidRecording(ValueError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _keys(value, required):
    if not isinstance(value, dict) or set(value) != set(required.split()):
        raise InvalidRecording("missing or unexpected fields")


def _uint(value, bits=32):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise InvalidRecording(f"expected unsigned {bits}-bit integer")


def _text(value, limit=256):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.isascii():
        raise InvalidRecording("invalid bounded ASCII text")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise InvalidRecording("control character in text")


def _hex(value, digits=64):
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{digits}}}", value):
        raise InvalidRecording("invalid lowercase hexadecimal identity")


def _blob(value, size=None):
    _keys(value, "sha256 bytes")
    _hex(value["sha256"])
    _uint(value["bytes"])
    if size is not None and value["bytes"] != size:
        raise InvalidRecording("invalid card byte count")
    if not 0 < value["bytes"] <= MAX_BASELINE:
        raise InvalidRecording("invalid baseline/blob byte count")


def validate_identity(identity: dict) -> None:
    """Validate an envelope supplied by the resolved-startup exporter.

    Hashes bind bytes, not the truth/completeness of that export. Activation
    must gather these independently before guest execution; tree HEAD/version
    strings and a recorder's own header cannot substitute for that observation.
    """
    _keys(identity, "image_sha256 manifest_sha256 execution_id settings_sha256 "
          "content_sha256 simulation_contract_sha256 mode profile cards baseline")
    for key in ("image_sha256", "manifest_sha256", "settings_sha256",
                "content_sha256", "simulation_contract_sha256"):
        _hex(identity[key])
    _text(identity["execution_id"])
    if identity["mode"] not in ("offline", "netplay"):
        raise InvalidRecording("invalid session mode")
    profile = identity["profile"]
    if profile is None:
        if identity["mode"] != "offline":
            raise InvalidRecording("netplay requires selected profile identity")
    else:
        _keys(profile, "id revision selected_sha256")
        _text(profile["id"])
        _uint(profile["revision"])
        _hex(profile["selected_sha256"])
    cards = identity["cards"]
    if not isinstance(cards, list) or len(cards) != 2:
        raise InvalidRecording("exactly two card slots required")
    for card in cards:
        if card is not None:
            _blob(card, CARD_BYTES)
    if identity["baseline"] is not None:
        _blob(identity["baseline"])


def validate_startup_artifacts(identity: dict, *, settings: bytes,
                               cards: list[bytes | None], baseline: bytes | None) -> None:
    """Check exported initial bytes/absence; never open or flush live cards.

    settings must be the retained resolved-settings bundle, not merely an old
    preference file. None baseline means cold boot; restore segments require
    the full ready current-build machine AND title-host snapshot blob.
    """
    validate_identity(identity)
    if sha256(settings) != identity["settings_sha256"]:
        raise InvalidRecording("settings artifact mismatch")
    if not isinstance(cards, list) or len(cards) != 2:
        raise InvalidRecording("exactly two exported card slots required")
    for index, (expected, actual) in enumerate(zip(identity["cards"], cards)):
        if (actual is None) != (expected is None):
            raise InvalidRecording(f"card {index} presence mismatch")
        if actual is not None and (len(actual) != expected["bytes"] or
                                   sha256(actual) != expected["sha256"]):
            raise InvalidRecording(f"card {index} artifact mismatch")
    expected = identity["baseline"]
    if (baseline is None) != (expected is None):
        raise InvalidRecording("baseline presence mismatch")
    if baseline is not None and (len(baseline) != expected["bytes"] or
                                 sha256(baseline) != expected["sha256"]):
        raise InvalidRecording("baseline artifact mismatch")


class _Order:
    def __init__(self, identity):
        self.mode = identity["mode"]
        self.events = self.natives = self.p2_reads = 0
        self.cycles = 0

    def accept(self, row):
        if not isinstance(row, dict) or row.get("type") not in ("N", "C"):
            raise InvalidRecording("unknown native-consumption event")
        kind = row["type"]
        common = "type order native cycles sim_tick "
        _keys(row, common + ("frame caller pads" if kind == "N" else
                             "seat consumer buttons"))
        for key in ("order", "native", "cycles"):
            _uint(row[key], 64)
        if row["order"] != self.events:
            raise InvalidRecording("event order gap/duplicate")
        if row["cycles"] < self.cycles:
            raise InvalidRecording("guest cycles regressed; restore requires a new segment")
        if self.mode == "offline":
            if row["sim_tick"] is not None:
                raise InvalidRecording("offline event has network tick")
        else:
            _uint(row["sim_tick"])
        if kind == "N":
            if row["native"] != self.natives:
                raise InvalidRecording("native call order gap/duplicate")
            _uint(row["frame"])
            _uint(row["caller"])
            if row["caller"] not in NATIVE_CALLERS:
                raise InvalidRecording("unmapped native caller")
            if not isinstance(row["pads"], list) or len(row["pads"]) != 2:
                raise InvalidRecording("two decoded native pad triples required")
            for pad in row["pads"]:
                if not isinstance(pad, list) or len(pad) != 3:
                    raise InvalidRecording("invalid native pad triple")
                for word in pad:
                    _uint(word, 16)
                if pad[2] != (pad[0] ^ pad[1]) & pad[0]:
                    raise InvalidRecording("native pressed-edge invariant failed")
            self.natives += 1
        else:
            if not self.natives or row["native"] != self.natives - 1:
                raise InvalidRecording("P2 read outside its native interval")
            if type(row["seat"]) is not int or row["seat"] != 1:
                raise InvalidRecording("P2 consumer requires seat 1")
            if not isinstance(row["consumer"], str) or row["consumer"] not in P2_CONSUMERS:
                raise InvalidRecording("unknown P2 consumer")
            _uint(row["buttons"], 16)
            self.p2_reads += 1
        self.cycles = row["cycles"]
        self.events += 1


class Encoder:
    """Streaming codec for an already-owned output; not a realtime writer.

    The eventual runtime must enqueue owned POD events on the guest thread and
    perform this I/O on its bounded writer worker. This class never discovers
    output paths, captures state, creates cards, or activates recording.
    """
    def __init__(self, output: BinaryIO, identity: dict):
        validate_identity(identity)
        self.output = output
        self.order = _Order(identity)
        self.digest = hashlib.sha256()
        self.finished = False
        self.failed = False
        self._write({"type": "header", "schema": 1, "contract": CONTRACT,
                     "identity": identity})

    def _write(self, row, *, hashed=True):
        data = canonical(row)
        if len(data) > MAX_LINE:
            raise InvalidRecording("record exceeds line bound")
        written = self.output.write(data)
        if written != len(data):
            raise OSError("short recording write")
        if hashed:
            self.digest.update(data)

    def append(self, row: dict):
        if self.finished or self.failed:
            raise InvalidRecording("recording finalized or poisoned by an earlier failure")
        try:
            self.order.accept(row)
            self._write(row)
        except Exception:
            self.failed = True
            raise

    def finish(self, *, failure: str | None = None):
        if self.finished or self.failed:
            raise InvalidRecording("recording finalized or poisoned by an earlier failure")
        try:
            if failure is not None:
                _text(failure)
            self._write({"type": "end", "events": self.order.events,
                         "natives": self.order.natives, "p2_reads": self.order.p2_reads,
                         "stream_sha256": self.digest.hexdigest(), "failure": failure}, hashed=False)
        except Exception:
            self.failed = True
            raise
        self.finished = True


@dataclass(frozen=True)
class Summary:
    identity: dict
    events: int
    natives: int
    p2_reads: int
    stream_sha256: str
    failure: str | None


def _read(stream):
    raw = stream.readline(MAX_LINE + 1)
    if not raw:
        raise InvalidRecording("truncated recording; terminal marker required")
    if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
        raise InvalidRecording("oversized or truncated record")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidRecording("duplicate JSON key")
            result[key] = value
        return result
    try:
        row = json.loads(raw.decode("ascii"), object_pairs_hook=unique)
        if canonical(row) != raw:
            raise InvalidRecording("noncanonical record")
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError) as error:
        raise InvalidRecording(f"invalid record: {error}") from error
    return row, raw


def validate(stream: BinaryIO, *, expected_identity: dict | None = None,
             offline_replay=False, require_complete=True, max_events=10_000_000) -> Summary:
    """Validate before replay, never admit a truncated prefix as complete.

    A valid online trace is inspectable native-consumption data, not an offline
    replay or proof of completed/resolved network ticks. Runtime checkpoints,
    publication/resolution provenance and actual replay are separate work.
    """
    _uint(max_events, 64)
    header, raw = _read(stream)
    _keys(header, "type schema contract identity")
    if header["type"] != "header" or type(header["schema"]) is not int or \
            header["schema"] != 1 or header["contract"] != CONTRACT:
        raise InvalidRecording("unsupported header/contract")
    identity = header["identity"]
    validate_identity(identity)
    if expected_identity is not None:
        validate_identity(expected_identity)
        if identity != expected_identity:
            raise InvalidRecording("startup identity mismatch")
    if offline_replay and expected_identity is None:
        raise InvalidRecording("offline replay requires independently observed startup identity")
    if offline_replay and identity["mode"] != "offline":
        raise InvalidRecording("network trace cannot be replayed offline")
    digest = hashlib.sha256(raw)
    order = _Order(identity)
    while True:
        row, raw = _read(stream)
        if isinstance(row, dict) and row.get("type") == "end":
            _keys(row, "type events natives p2_reads stream_sha256 failure")
            for key, value in (("events", order.events), ("natives", order.natives),
                               ("p2_reads", order.p2_reads)):
                _uint(row[key], 64)
                if row[key] != value:
                    raise InvalidRecording("terminal count mismatch")
            _hex(row["stream_sha256"])
            if row["stream_sha256"] != digest.hexdigest():
                raise InvalidRecording("stream digest mismatch")
            if row["failure"] is not None:
                _text(row["failure"])
            if stream.read(1):
                raise InvalidRecording("data after terminal marker")
            if not order.natives:
                raise InvalidRecording("recording has no native calls")
            if (require_complete or offline_replay) and row["failure"] is not None:
                raise InvalidRecording("capture explicitly failed: " + row["failure"])
            return Summary(identity, order.events, order.natives, order.p2_reads,
                           digest.hexdigest(), row["failure"])
        if order.events >= max_events:
            raise InvalidRecording("event limit exceeded")
        order.accept(row)
        digest.update(raw)
