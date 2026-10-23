"""Bounded localhost observations of a private X6 development process.

No process lifecycle, RAM writes, save loads or fixture commands live here.
Controller injection uses the host sampler, never the simulation override.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import socket
import struct
import time

DIAGNOSTIC_ADDRESS = 0x9F080000  # Legacy default; override from the runtime log.
DIAGNOSTIC_BYTES = 0x1958
DIAGNOSTIC_VERSION = 1
DIAGNOSTIC_SEQUENCE = 0x88
BODY_BYTES = 0x158


class DebugError(RuntimeError):
    """A transport, framing, schema or runtime command failure."""


class UnstableObservation(DebugError):
    """The published diagnostic block changed while being observed."""


class DebugClient:
    def __init__(self, port: int, *, timeout: float = 3.0,
                 max_response_bytes: int = 1024 * 1024):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("Expected a localhost TCP port in 1..65535")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Expected a positive finite timeout")
        if not 64 <= max_response_bytes <= 2 * 1024 * 1024:
            raise ValueError("Response bound must be between 64 bytes and 2 MiB")
        self.port = port
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._sequence = 0

    def request(self, command: str, **fields) -> dict:
        if not isinstance(command, str) or not command or "id" in fields or "cmd" in fields:
            raise ValueError("Expected a command without reserved id/cmd fields")
        self._sequence += 1
        request_id = self._sequence
        payload = (json.dumps(dict(id=request_id, cmd=command, **fields),
                              allow_nan=False) + "\n").encode("utf-8")
        deadline = time.monotonic() + self.timeout
        try:
            with socket.create_connection(("127.0.0.1", self.port),
                                          timeout=self.timeout) as connection:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Connection consumed the request deadline")
                connection.settimeout(remaining)
                connection.sendall(payload)
                data = bytearray()
                while b"\n" not in data:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Response deadline exceeded")
                    connection.settimeout(remaining)
                    chunk = connection.recv(min(16384, self.max_response_bytes + 1 - len(data)))
                    if not chunk:
                        raise DebugError(f"{command}: peer closed before a complete response")
                    data.extend(chunk)
                    if len(data) > self.max_response_bytes:
                        raise DebugError(f"{command}: response exceeds {self.max_response_bytes} bytes")
                line, _, trailing = data.partition(b"\n")
                if trailing.strip():
                    raise DebugError(f"{command}: extra response data")
                result = json.loads(line)
        except (OSError, UnicodeError, ValueError) as error:
            raise DebugError(f"port {self.port}, {command}: {error}") from error
        if not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] != request_id:
            raise DebugError(f"{command}: invalid or mismatched response id")
        if result.get("ok") is not True:
            raise DebugError(f"{command}: runtime rejected command: {str(result)[:240]}")
        return result

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
        if any(flag not in (0, 1) for flag in (ready, enrolled, failed)):
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
                       ready, enrolled, failed, mode, phase, digest, algorithm, (p1, p2))


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
