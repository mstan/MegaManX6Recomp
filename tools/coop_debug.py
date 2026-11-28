"""Bounded localhost observations of a private X6 development process.

No process lifecycle, RAM writes, save loads or fixture commands live here.
Controller injection uses the host sampler, never the simulation override.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import hashlib
from pathlib import Path
import socket
import struct
import time

DIAGNOSTIC_ADDRESS = 0x9F080000  # Legacy default; override from the runtime log.
DIAGNOSTIC_BYTES = 0x1958
DIAGNOSTIC_VERSION = 1
DIAGNOSTIC_SEQUENCE = 0x88
BODY_BYTES = 0x158


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'psxrecomp-v4/tools'))
from debug_transport import DebugClient as SharedDebugClient, DebugError


class UnstableObservation(DebugError):
    """The published diagnostic block changed while being observed."""


def capture_present(client, path: Path, *, timeout: float = 8.0, request=None) -> dict:
    """Wait for actual composed-GL capture completion, never just its ack.

    Owned-process runners should pass their ownership-checked request callback.
    Canonical screenshot/screenshot_hires at scale one may instead read software
    VRAM, which excludes retained GL texture banks.
    """
    path = Path(path)
    if not path.is_absolute() or path.exists() or not path.parent.is_dir():
        raise ValueError("Present capture needs a fresh absolute path in an existing directory")
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("Present capture timeout must be in (0,60]")
    rpc = request or client.request
    before = rpc("present_shot_seq")
    if type(before.get("seq")) is not int:
        raise DebugError("present_shot_seq omitted its completion sequence")
    acknowledgement = rpc("present_shot", path=str(path))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        completed = rpc("present_shot_seq")
        if type(completed.get("seq")) is int and completed["seq"] != before["seq"]:
            if completed.get("wrote") != 1 or not path.is_file() or path.stat().st_size == 0:
                raise DebugError("Composed capture completed without a written artifact")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            return dict(surface="composed_renderer_output", path=str(path), sha256=digest,
                        before=before, acknowledgement=acknowledgement, completion=completed)
        time.sleep(.02)
    raise DebugError("Composed capture acknowledgement never reached completed generation")


class DebugClient(SharedDebugClient):
    def read(self, address: int, size: int) -> bytes:
        if not isinstance(address, int) or not 0 <= address <= 0xFFFFFFFF:
            raise ValueError("Expected a 32-bit guest address")
        if not isinstance(size, int) or not 1 <= size <= 65536 or address + size > 0x100000000:
            raise ValueError("Expected a bounded guest read of 1..65536 bytes")
        response = self.request("read_ram", addr=hex(address), len=size)
        encoded = response.get("hex")
        if not isinstance(encoded, str) or len(encoded) != size * 2:
            raise DebugError(f"read_ram: expected exactly {size} bytes")
        try:
            data = bytes.fromhex(encoded)
        except ValueError as error:
            raise DebugError("read_ram: invalid hexadecimal payload") from error
        if len(data) != size:
            raise DebugError("read_ram: decoded payload has the wrong length")
        return data

    def host_input(self, pressed: int = 0) -> None:
        if not isinstance(pressed, int) or not 0 <= pressed <= 0xFFFF:
            raise ValueError("Expected a 16-bit pressed-button mask")
        self.request("set_input", layer="host", buttons=hex(0xFFFF ^ pressed))
        status = self.request("pad_status")
        try:
            applied = int(status.get("host_buttons", ""), 0)
        except (TypeError, ValueError):
            applied = -1
        if status.get("host_layer") is not True or applied != (0xFFFF ^ pressed):
            raise DebugError("pad_status: runtime did not acknowledge host sampler input")

    def release(self) -> None:
        self.request("clear_input")


@dataclass(frozen=True)
class Player:
    active: int
    character: int
    state: int
    action: int
    hp: int
    x_raw: int
    y_raw: int
    weapon: int = 0
    ammo: tuple[int, ...] = ()

    @classmethod
    def parse(cls, body: bytes) -> "Player":
        if len(body) != BODY_BYTES:
            raise DebugError("Truncated native player body")
        x, y = struct.unpack_from("<ii", body, 8)
        return cls(body[0], body[2], body[4], body[5], body[0x5C], x, y,
                   body[0x93], struct.unpack_from("<9H", body, 0xA8))


@dataclass(frozen=True)
class Observation:
    schema: int
    tick: int  # Plugin publication count, NOT the netplay simulation tick.
    sequence: int | None
    native_timer: int
    lifecycle: tuple[int, int]
    pause_owner: int  # Wire encoding: 0=none, 1=P1, 2=P2.
    scene_owner: int
    scene_phase: int
    mailbox: int
    ready: int | None
    enrolled: int | None
    failed: int | None
    native_mode: int | None
    native_phase: int | None
    host_digest: int | None
    host_digest_algorithm: int | None
    players: tuple[Player, Player]
    framework_digest_registered: int | None = None

    def json(self) -> dict:
        return asdict(self)


def parse_diagnostic(data: bytes, *, allow_legacy: bool = False) -> Observation:
    if len(data) != DIAGNOSTIC_BYTES:
        raise DebugError(f"Expected exactly {DIAGNOSTIC_BYTES} diagnostic bytes")
    if struct.unpack_from("<I", data)[0] != 0x434F4F50:
        raise DebugError("Active X6 co-op diagnostic block not found (bad magic)")
    version, declared_size, sequence = struct.unpack_from("<III", data, 0x80)
    if version == 0 and allow_legacy:
        # Frozen baseline inspection only; legacy publications have no schema,
        # size, seqlock or simulation digest and cannot qualify paired runs.
        sequence = None
        ready = enrolled = failed = mode = phase = digest = algorithm = None
    elif version == DIAGNOSTIC_VERSION and declared_size == DIAGNOSTIC_BYTES:
        if sequence & 1:
            raise UnstableObservation("Diagnostic publication is in progress")
        if sequence != (struct.unpack_from("<I", data, 4)[0]*2) & 0xFFFFFFFF:
            raise UnstableObservation("Diagnostic tick and publication sequence disagree")
        ready, enrolled, failed = data[0x8C:0x8F]
        mode, phase = data[0x90:0x92]
        digest, algorithm = struct.unpack_from("<II", data, 0x94)
        if any(flag not in (0, 1) for flag in (ready, enrolled, failed, data[0x9C])):
            raise DebugError("Invalid diagnostic ready/enrolled/failed flag")
        if algorithm != 1:
            raise DebugError(f"Unsupported host digest algorithm {algorithm}")
    else:
        raise DebugError(f"Unsupported diagnostic schema/size {version}/{declared_size}")
    lifecycle = tuple(data[0x38:0x3A])
    if any(status > 5 for status in lifecycle) or data[0x3C] > 2 or data[0x3E] > 2:
        raise DebugError("Invalid diagnostic player/scene ownership")
    p1 = Player.parse(data[0x1800:0x1958])
    p2 = Player.parse(data[0x100:0x258])
    if data[8:16] != data[0x108:0x110] or data[24] != p2.hp:
        raise UnstableObservation("Diagnostic player mirrors disagree")
    return Observation(version, struct.unpack_from("<I", data, 4)[0], sequence,
                       struct.unpack_from("<I", data, 36)[0], lifecycle,
                       data[0x3C], data[0x3E], data[0x3F], data[0x30],
                       ready, enrolled, failed, mode, phase, digest, algorithm, (p1, p2),
                       data[0x9C] if version == 1 else None)


def observe(client: DebugClient, address: int = DIAGNOSTIC_ADDRESS, *,
            attempts: int = 4, allow_legacy: bool = False) -> Observation:
    """Read one atomic emulation-thread response; reject torn publications.

    The pinned runtime executes read_ram inside debug_server_poll on the
    emulation thread, without guest execution during the copy. Three separate
    RPCs may span three frames and cannot form a usable seqlock transaction.
    The in-block even sequence and redundant body fields validate this single
    published snapshot. Transport/schema errors remain failures.
    """
    if not 1 <= attempts <= 16:
        raise ValueError("Expected 1..16 observation attempts")
    for _ in range(attempts):
        data = client.read(address, DIAGNOSTIC_BYTES)
        try:
            result = parse_diagnostic(data, allow_legacy=allow_legacy)
            if result.schema == 0:
                return result
            if not result.sequence & 1:
                return result
        except UnstableObservation:
            pass
    raise UnstableObservation(f"No coherent X6 publication in {attempts} attempts")
