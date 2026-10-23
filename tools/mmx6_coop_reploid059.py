"""Bounded Recycle portal approach exclusion, never a Reploid mechanic pass.

The Reploid is collectible and can alter campaign/resources. Only its exact
source-bound grounded idle instance, left of both players, is admitted here.
Native pool and private-player publications retain their separate RPC origins.
"""
from __future__ import annotations

import hashlib
import struct

import coop_debug as debug
import inventory_mmx6_coop_content as content
import mmx6_coop_recycle_portal as portal

POOL, STRIDE, COUNT = 0x800C1220, 0xA4, 80
RECORD, X, Y = 0x800F2B7C, 1360, 1600
AUTHORED = bytes.fromhex("00043b0450054006")
ALLOCATED = bytes.fromhex("01043b0450054006")
BOX_POINTER, BOX = 0x80078910, bytes.fromhex("00000810")
DISPATCH_POINTER, DISPATCH_TABLE = 0x1F800094, 0x800F338C
TABLE_BYTES = bytes.fromhex("2048058028480580304805803848058034f80480")
BODY_BOXES = ((0x80073D50, bytes((0, 2, 11, 19))),
              (0x80073D54, bytes((0, 3, 11, 19))))
MIN_X, MAX_X = 1506, 1695
SOURCE_WINDOWS = (
    ("solid_update", 0x800205A0, 0x120, "b08512ecebd6885080e14a3f3362c465049c1de842bf00b4b4fbedb1d27d653d"),
    ("phase_dispatch", 0x8004F834, 0x4C, "b3484109156a7c8864090485d5a770d288ad1f4c02946a564b709fa6409f8039"),
    ("phase_table", 0x80078C7C, 0x24, "4046311ada07ad864c23e96ceb6af641db3aca7c624aa8e0b31b1bb18f258953"),
    ("initialize", 0x8004E800, 0x278, "78e21a80c5e597237bc0c39eb5756113f67c4133bc820572a89a7ed318613b41"),
    ("idle", 0x8004EA78, 0x1B8, "1768c7f52375b3b4daa50da1d0be94c99ba9c98916f47963964fa77112da920a"),
    ("contact", 0x8004EECC, 0x104, "f0a519246ca8a2d9c70525f64ec9cb57dfa77daa4d870cb285211ec6684e8cc3"),
    ("body_contact_geometry", 0x8002DCF4, 0x160, "ae9156b379e618a48716e4d1efe1bbde05183f1185cfa72e63c94cb93294591e"),
    ("facing_animation_selection", 0x8004FE8C, 0x70, "454d6bddece44ce0eefb6a79b4be28e093a498718ef10e8745bbd3a5e62d585b"),
    ("animation", 0x800179A4, 0xA0, "6446292a3a708036d6fb8d8d3db5bc82f9f1cc56641648b6abda93800d31cd75"),
    ("offscreen_visibility", 0x8002CBFC, 0x170, "dbf1d709e13fb55fd9a0dcf1cc1065f4357e63a2002b5a0ff6186f0356909c43"),
    ("body_box", BOX_POINTER, 4, "6d7afb8070febf7b6c4adda4905fba44091e4d0a38c13b7c7d50e6bd45db8dfe"),
    ("scanner_record_mutation", 0x80029E7C, 0x27C, "b2ac7f6c590d26b454dee356fcacd8dd9c78ba5be7b728ebd8229b6983758b5c"),
    ("category4_allocator", 0x8002C4C4, 0x6C, "4669bef7a4cc12596f4e2aa63d4aa2cbec058c69b49b6a85339ddd70437c7990"),
)


def require(condition, message):
    if not condition:
        raise debug.DebugError("Reploid059 exclusion: " + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_guards(sources):
    """Verify original bytes before a process is launched; never inspect guesses."""
    exe, member = sources["exe"], sources["member"]
    require(sha(exe.data) == content.EXE_SHA256, "original EXE identity differs")
    require(sha(member) == portal.SOURCE_MEMBER_SHA, "original member6 identity differs")
    windows = []
    for name, address, size, digest in SOURCE_WINDOWS:
        at = exe.offset(address, size)
        actual = sha(exe.data[at:at+size])
        require(actual == digest, "original " + name + " differs")
        windows.append(dict(name=name, address=address, bytes=size, sha256=actual))
    def source(address, size):
        at = address-content.OVERLAY_BASE
        require(0 <= at <= len(member)-size, "member source extent differs")
        return member[at:at+size]
    require(source(RECORD, 8) == AUTHORED, "authored placement32 differs")
    require(source(DISPATCH_TABLE, 20) == TABLE_BYTES, "member6 type4 dispatcher differs")
    require(exe.word(0x8006DF6C) == DISPATCH_TABLE, "stage4 category4 dispatcher root differs")
    return dict(status="original_source_guards_verified", original_exe_sha256=content.EXE_SHA256,
                original_member6_sha256=portal.SOURCE_MEMBER_SHA, windows=windows,
                placement=dict(index=32, address=RECORD, hex=AUTHORED.hex()),
                dispatch=dict(address=DISPATCH_TABLE, hex=TABLE_BYTES.hex(), entry4=0x8004F834))


def enrich(actor, *, address, category, record_hex):
    """Called from the runner's existing single native-block reader only."""
    require(len(actor) == STRIDE and category == 4, "full category4 A4 instance required")
    return dict(raw_hex=actor.hex(), phase=actor[4], action=actor[5], subaction=actor[6],
        eligibility=actor[7], facing=actor[0x15], facing_animation=actor[0x82],
        variant=actor[0x84], airborne_bob=actor[0x7E], contacts=actor[0x70],
        x_raw=struct.unpack_from("<i",actor,8)[0], y_raw=struct.unpack_from("<i",actor,12)[0],
        previous_hex=actor[0x18:0x20].hex(), motion_hex=actor[0x20:0x30].hex(),
        motion_words=dict(zip(("velocity_x","velocity_y","acceleration_x","acceleration_y"),
                             struct.unpack_from("<4i",actor,0x20))),
        body_box=struct.unpack_from("<I",actor,0x68)[0], source_record_hex=record_hex,
        atomic_provenance=dict(kind="same_native_block",address=address,bytes=STRIDE,
                               record_address=RECORD if record_hex is not None else None))


def actor_state(actor):
    """Reject arbitrary category/type whitelists and stale or partial instances."""
    require(isinstance(actor,dict), "instance is missing")
    try:
        raw = bytes.fromhex(actor["raw_hex"])
    except (KeyError,ValueError,TypeError) as error:
        raise debug.DebugError("Reploid059 exclusion: missing full A4 instance") from error
    address = actor.get("address")
    require(type(address) is int and POOL <= address < POOL+COUNT*STRIDE and
            (address-POOL)%STRIDE == 0 and actor.get("category") == 4,
            "instance is outside the exact category4 pool")
    require(len(raw) == STRIDE, "truncated A4 instance")
    require(raw[0] == 0x41 and raw[1:3] == bytes((4,59)) and
            struct.unpack_from("<I",raw,0x10)[0] == RECORD,
            "exact live type/subtype/origin differs")
    require((actor.get("type"),actor.get("subtype"),actor.get("origin"),actor.get("x"),actor.get("y")) ==
            (4,59,RECORD,X,Y), "nearby metadata differs from the bound instance")
    require(actor.get("source_record_hex") == ALLOCATED.hex(), "live authored record must be allocated category4 placement32")
    require(actor.get("atomic_provenance") == dict(kind="same_native_block",address=address,
            bytes=STRIDE,record_address=RECORD), "instance/record lacks one-block provenance")
    require(raw[3] == 1 and raw[4:8] == bytes((1,0,0,1)) and
            raw[0x15] == 0 and raw[0x82] in (0,0x40) and raw[0x84] == raw[0x7E] == 0 and raw[0x70]&8,
            "requires visible grounded eligible idle; healing/infection/despawn/bob are unsupported")
    require(struct.unpack_from("<ii",raw,8) == (X<<16,Y<<16) and raw[8:16] == raw[0x18:0x20] and
            raw[0x20:0x30] == bytes(16) and raw[0x7C:0x80] == bytes(4),
            "authored position/previous/zero motion/grounded state differs")
    require(struct.unpack_from("<I",raw,0x68)[0] == BOX_POINTER,
            "exact subtype59 body-box pointer differs; no pointer fallback")
    # Animation timer/pointers may naturally change. These are all fields used
    # by the narrowly admitted state and geometry, and must remain unchanged.
    signature = b"".join(raw[a:b] for a,b in
        ((0,0x16),(0x18,0x30),(0x68,0x6C),(0x70,0x71),(0x7C,0x85)))
    return raw, dict(address=address, critical_sha256=sha(signature), origin=RECORD,
                     record_hex=actor["source_record_hex"])


def find_actor(row):
    unknown = [a for a in row["nearby_actors"] if not a["known_source_actor"]]
    require(len(unknown) == 1, "exactly one otherwise-unknown actor is required")
    actor_state(unknown[0])
    return unknown[0]


def validate_frame(row, publication, body_evidence, proof):
    """Conditional horizontal miss; private and native observations stay separate.

    The stored actual box probe is immutable EXE data, not a same-tick read of
    this publication. The caller may use this proof only in its bounded original
    Right window and rechecks the critical actor state at each observation.
    """
    require(proof.get("source_guards",{}).get("status") == "original_source_guards_verified",
            "verified source guards required")
    require(proof.get("body_box_probe") == dict(address=BOX_POINTER,bytes=4,hex=BOX.hex(),
            provenance="separate_owned_read_ram_fixed_source_pointer"), "actual source-bound four-byte box probe required")
    require(proof.get("dispatch_probe") == dict(address=DISPATCH_POINTER,bytes=4,value=DISPATCH_TABLE,
            provenance="separate_owned_read_ram_fixed_scratch_slot"), "actual category4 dispatch binding required")
    n = row["native"]
    require((n["mode"],n["phase"],n["stage"],n["section"],n["checkpoint"]) == (10,0,4,0,2) and
            n["source_closure_present"] and not any(n[k] for k in ("transition","fade","freeze","shared_entry_lock")),
            "requires unchanged ready source namespace")
    require(row.get("reploid059_source",{}).get("dispatch_table_hex") == TABLE_BYTES.hex(),
            "live member6 type4 code table differs")
    actor = find_actor(row)
    raw, state = actor_state(actor)
    if proof.get("actor_baseline") is not None:
        require(state == proof["actor_baseline"], "critical actor state changed across probe/window")
    p = publication["observation"]
    require(p["ready"] == p["enrolled"] == 1 and p["failed"] == p["mailbox"] == 0 and
            tuple(p["lifecycle"]) == (0,0) and p["native_mode"] == 10 and
            p["native_phase"] == p["pause_owner"] == p["scene_owner"] == p["scene_phase"] == 0,
            "private publication is not a living scene-free source observation")
    observed_players = [bytes.fromhex(publication[k]) for k in ("p1_body_hex","p2_body_hex")]
    native_p1 = bytes.fromhex(n["resident_player"]["raw_hex"])
    checks = []
    for seat,body in enumerate(observed_players+[native_p1]):
        owner = seat if seat < 2 else 0
        expected_pointer,expected_box = BODY_BOXES[owner]
        require(len(body) == debug.BODY_BYTES and body[0] and body[4] == 1 and body[2] == owner and
                0 < body[0x5C] < 0x80 and body[0xD5] == 0 and
                not (body[0x7A]|body[0xD0]|body[0xD4]) and
                struct.unpack_from("<I",body,0x68)[0] == expected_pointer,
                "current fixed-roster player/ride/body-box gates differ")
        evidence = body_evidence[owner]
        require(evidence == dict(pointer=expected_pointer,hex=expected_box.hex(),
                origin="resident_native_ram" if owner == 0 else "native_ram"),
                "actual per-seat body-box provenance differs")
        if owner == 1:
            actual = publication["boxes"]["body"]
            require(actual.get("available") and actual.get("pointer") == expected_pointer and
                    actual.get("origin") == "native_ram" and actual.get("hex") == expected_box.hex(),
                    "current private body box lost its owning publication provenance")
        x_raw = struct.unpack_from("<i",body,8)[0]
        require(MIN_X<<16 <= x_raw <= MAX_X<<16 and
                (owner != 0 or x_raw == MIN_X<<16),
                "player left fixed-X/right-only finite approach envelope")
        px = struct.unpack_from("<h",body,0xA)[0]
        # 2DCF4 compares body boxes at+68, flips signed x offset only when
        # facing byte==40h, and uses strict radius-sum contact. Offsets are0
        # in all three qualified boxes; no signed16 wrap is possible here.
        aox,_,ar,_ = struct.unpack("<bbBB",BOX)
        pox,_,pr,_ = struct.unpack("<bbBB",expected_box)
        ac = X-aox if raw[0x15] == 0x40 else X+aox
        pc = px-pox if body[0x15] == 0x40 else px+pox
        distance, radius = abs(pc-ac), ar+pr
        require(distance >= radius, "actual body boxes overlap horizontally")
        checks.append(dict(attribution="native_resident_block" if seat == 2 else "private_publication",
            seat=owner,x_raw=x_raw,horizontal_distance=distance,radius_sum=radius,
            horizontal_miss=True,separation_margin=distance-radius))
    return dict(status="conditional_source_bound_contact_exclusion", actor=state, player_checks=checks,
        minimum_observed_margin=min(c["separation_margin"] for c in checks),
        scope="Only exact idle placement32 while X remains1506 and Zero stays in1506..1695 during original Right",
        attribution="Actor/native P1 one block; private players separate publication; box/scratch probes separate RPCs",
        native_reploid_mechanics="unverified", artwork_review="pending")
