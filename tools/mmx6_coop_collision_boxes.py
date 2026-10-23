"""Read actual private P2 collision boxes without projecting a guest bank.

One owned read contains the base players and additive X6BX extension. This
does not fuse native actor-pool or camera observations from another RPC.
"""
from __future__ import annotations

import hashlib
import re
import struct

import coop_debug as debug

HEADER = 0x1C20
SIZE = 0x40
END = HEADER + SIZE
MAGIC = 0x58423658
OVERLAY = 0x801EA000
OVERLAY_SIZE = 0xB000
FIELDS = (("attack", 0x50), ("damage", 0x54), ("body", 0x68))
ORIGINS = {0: "unavailable", 1: "native_ram", 2: "private_overlay"}


def parse_publication(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or len(raw) != END:
        raise debug.DebugError("Expected exactly one complete collision-box publication")
    observation = debug.parse_diagnostic(raw[:debug.DIAGNOSTIC_BYTES])
    magic, schema, size, tick = struct.unpack_from("<4I", raw, HEADER)
    if (magic, schema, size) != (MAGIC, 1, SIZE):
        raise debug.DebugError("Unsupported collision-box extension")
    if tick != observation.tick:
        raise debug.UnstableObservation("Collision-box and player publication ticks disagree")
    if any(raw[HEADER + 52:END]):
        raise debug.DebugError("Noncanonical collision-box reserved bytes")
    body = raw[0x100:0x258]
    boxes = {}
    for index, (name, offset) in enumerate(FIELDS):
        at = HEADER + 16 + index * 12
        pointer, origin = struct.unpack_from("<II", raw, at)
        value = raw[at + 8:at + 12]
        if pointer != struct.unpack_from("<I", body, offset)[0]:
            raise debug.UnstableObservation("Private box pointer and body disagree")
        if origin not in ORIGINS:
            raise debug.DebugError("Unsupported collision-box source")
        if origin == 0 and any(value):
            raise debug.DebugError("Unavailable collision box retained stale bytes")
        if origin == 1 and not 0x80010000 <= pointer <= OVERLAY - 4:
            raise debug.DebugError("Native collision box escapes its published source range")
        if origin == 2 and not OVERLAY <= pointer <= OVERLAY + OVERLAY_SIZE - 4:
            raise debug.DebugError("Private collision box escapes its code/data bank")
        if origin and (observation.ready != 1 or observation.failed):
            raise debug.DebugError("Collision bytes published without a ready private bank")
        boxes[name] = dict(pointer=pointer, origin=ORIGINS[origin], available=bool(origin),
                           hex=value.hex() if origin else None)
    return dict(kind="single_rpc_private_collision_boxes", raw_bytes=len(raw),
        raw_sha256=hashlib.sha256(raw).hexdigest(), observation=observation.json(),
        p1_body_hex=raw[0x1800:0x1958].hex(), p2_body_hex=body.hex(), boxes=boxes,
        limits=["Bytes describe the published cached P2 body; eligibility still needs living active pose checks.",
                "Native actor pools, actual contacts and camera state from other RPCs are not atomic with this block.",
                "No collision, guest call, input or gameplay pass is implied by source bytes."])


def observe_owned(request, address: int = debug.DIAGNOSTIC_ADDRESS) -> dict:
    if not callable(request) or type(address) is not int or not 0 <= address <= 0xFFFFFFFF - END:
        raise ValueError("Expected an owned read-only callback and bounded publication address")
    reply = request("read_ram", addr=hex(address), len=END)
    if not isinstance(reply, dict) or reply.get("ok") is not True or \
            type(reply.get("len")) is not int or reply["len"] != END or \
            not isinstance(reply.get("addr"), str) or \
            not re.fullmatch(r"0x[0-9a-fA-F]{8}", reply["addr"]) or int(reply["addr"], 16) != address:
        raise debug.DebugError("Malformed collision-box read envelope")
    payload = reply.get("hex")
    if not isinstance(payload, str) or not re.fullmatch(r"[0-9a-fA-F]{%d}" % (END * 2), payload):
        raise debug.DebugError("Malformed collision-box read payload")
    return parse_publication(bytes.fromhex(payload))
