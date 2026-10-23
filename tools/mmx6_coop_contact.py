"""Source-bound original-input R2 candidate; no launcher or ledger disposition.

The owning runner supplies accepted input, listener-checked RPCs and lifecycle.
This case has not been executed. Its strict evidence reducer rejects ambiguous
actor attribution instead of passing an HP change or hook counter alone.
"""
from __future__ import annotations

import hashlib
import ntpath
from pathlib import Path
import struct

import coop_debug as debug
import mmx6_coop_personal_menu as menu
import qualify_mmx6_coop_enemy_admission as enemy
from inventory_mmx6_coop_content import RawDisc, archive_members, BIN_SHA256, EXE_SHA256


EXE_SHA = "37cdc4876f7e852b97ef5f14210809b0af7d4a8adaa1759c9e096017170e1fa9"
ZERO_SHA = "75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00"
ZERO_BASE, ZERO_SIZE = 0x801EA000, 22964
CONTACT, CONTACT_RA = 0x80030ECC, 0x800EADC8


def load_zero_overlay(raw_disc: Path) -> bytes:
    """Read only the bounded inventory extents; retain no original binary copy."""
    disc = RawDisc(Path(raw_disc))
    try:
        files = disc.inventory_files()
    finally:
        disc.stream.close()
    if (hashlib.sha256(files["SLUS_013.95"]).hexdigest() != EXE_SHA256 or
            hashlib.sha256(files["ROCK_X6.BIN"]).hexdigest() != BIN_SHA256):
        raise ValueError("R2 original source identity changed")
    archive = files["ROCK_X6.BIN"]
    entry = archive_members(archive)[1]
    result = archive[entry["sector"] * 2048:entry["sector"] * 2048 + entry["size"]]
    validate_zero_overlay(result)
    return result


def validate_zero_overlay(payload: bytes) -> None:
    if len(payload) != ZERO_SIZE or hashlib.sha256(payload).hexdigest() != ZERO_SHA:
        raise ValueError("R2 hurtbox resolver needs the pinned original Zero overlay")


def zero_box(pointer: int, payload: bytes) -> dict | None:
    if not pointer:
        return None
    offset = pointer - ZERO_BASE
    if pointer & 3 or offset < 0 or offset + 4 > len(payload):
        raise ValueError("P2 hurtbox pointer escaped the qualified Zero member")
    values = payload[offset:offset + 4]
    x, y, width, height = struct.unpack("<bbBB", values)
    return dict(pointer=hex(pointer), bytes=values.hex(), x=x, y=y, width=width, height=height,
                source="immutable_original_zero_overlay")


def player_fields(body: bytes) -> dict:
    if len(body) != debug.BODY_BYTES:
        raise ValueError("Truncated coherent player body")
    return dict(hp_raw=body[0x5C], hp=body[0x5C] & 0x7F, pending_hit=bool(body[0x5C] & 0x80),
        iframes=body[0x61], reaction=body[0x63], reaction_lock=body[0xA4],
        direction=body[0xA5], facing=body[0x15], state=body[4], action=body[5],
        subaction=body[6], hit_pause=body[0xCC], hit_pause_request=body[0xCD],
        alternate_projection=bool(body[0xD5] & 0x80), native_restriction=body[0x7A],
        body_restriction=struct.unpack_from("<I", body, 0x144)[0],
        box_pointer=struct.unpack_from("<I", body, 0x54)[0],
        terrain=body[0x70], previous_terrain=body[0x89], armor=body[0xE7],
        parts=struct.unpack_from("<I", body, 0xEC)[0])


def ordinary_damage(difficulty: int, armor: int, parts: int, shared_parts: int) -> tuple[int, int]:
    """Original strength4/class0 path only, never a synthetic damage write."""
    if difficulty not in (0, 1, 2):
        raise ValueError("R2 ordinary damage difficulty is unqualified")
    damage = (3, 4, 5)[difficulty]
    half = 1 <= armor <= 4 or (armor == 5 and shared_parts & 0x20) or bool(parts & 0x200)
    # Contact's reaction selector is separate from its damage calculator:
    # EC200 alone halves damage on any body, but selects reaction4 only for
    # armor5. Zero's shared20 flag selects reaction4 even on another armor.
    soft_reaction = 1 <= armor <= 4 or (armor == 5 and parts & 0x200) or bool(shared_parts & 0x20)
    return (max(1, damage // 2) if half else damage), (4 if soft_reaction else 1)


def observe_contact(client, zero_overlay: bytes) -> dict:
    # Full player fields, resources and the P2 acceptance counter come from
    # ONE coherent diagnostic RPC. Pool/box/config reads remain separate.
    data = client.read(debug.DIAGNOSTIC_ADDRESS, debug.DIAGNOSTIC_BYTES)
    observed = debug.parse_diagnostic(data).json()
    players = [player_fields(data[0x1800:0x1958]), player_fields(data[0x100:0x258])]
    raw_pool = client.read(enemy.POOL, enemy.STRIDE * enemy.SLOTS)
    live, actor = enemy.parse_pool(raw_pool)
    if actor:
        body = raw_pool[actor["slot"] * enemy.STRIDE:(actor["slot"] + 1) * enemy.STRIDE]
        pointer = struct.unpack_from("<I", body, 0x50)[0]
        if pointer != 0x800FAAE0:
            raise debug.DebugError("Record25 contact box is not the original authored descriptor")
        box = client.read(pointer, 4)
        if box.hex() != "f4ec1828":
            raise debug.DebugError("Record25 authored contact rectangle changed")
        actor.update(contact_class=body[0x62], contact_pointer=hex(pointer), contact_box=box.hex())
    config = client.read(0x800CCF2F, 10)  # PLAY+5F..68, shared parts and difficulty.
    damage, reaction = ordinary_damage(config[9], players[1]["armor"], players[1]["parts"], config[0])
    return dict(observation=observed, players=players, instance=actor, live_enemies=live,
        record=client.read(enemy.RECORD, 8).hex(),
        camera=list(struct.unpack("<h2xh", client.read(0x80097202, 6))),
        p2_contact_counter=struct.unpack_from("<I", data, 0x44)[0],
        p2_box=zero_box(players[1]["box_pointer"], zero_overlay),
        damage_configuration=[config[9], players[1]["armor"], players[1]["parts"], config[0]],
        expected_damage=damage, expected_reaction=reaction)


def eligible(row: dict) -> bool:
    player = row["players"][1]
    return (player["state"] == 1 and player["hp"] > 0 and not player["pending_hit"] and not player["iframes"] and
            not player["reaction_lock"] and not player["hit_pause"] and
            not player["alternate_projection"] and not player["native_restriction"] and
            player["body_restriction"] != 1 and row["p2_box"] is not None)


def hazardous(row: dict) -> bool:
    return any((value & 0x0C) == 0x0C or (value & 3) == 3
               for value in (row["players"][1]["terrain"], row["players"][1]["previous_terrain"]))


def complete_contact_trace(page: dict, actor: str) -> list[dict]:
    rows = page["entries"]
    if (page["seq_lo"] != 0 or not 1 <= page["seq_hi"] <= 4096 or page["emitted"] != len(rows) or
            [row["seq"] for row in rows] != list(range(page["seq_hi"]))):
        raise debug.DebugError("Contact trace window was empty, evicted or truncated")
    if any(int(row["target"], 16) != CONTACT or int(row["a0"], 16) != int(actor, 16) or
           int(row["ra"], 16) != CONTACT_RA for row in rows):
        raise debug.DebugError("Contact trace includes a foreign actor or unqualified native caller")
    return rows


def contact_evidence(before: dict, history: list[dict]) -> dict | None:
    actor = before["instance"]
    if (not actor or actor["flags"] == 0 or actor["type"] != 1 or actor["subtype"] != 1 or
            actor["hp"] != 12 or actor["phase"] != 1 or not eligible(before) or hazardous(before)):
        return None
    for row in history:
        player, native = row["players"][1], row["instance"]
        delta = (row["p2_contact_counter"] - before["p2_contact_counter"]) & 0xFFFFFFFF
        tick_delta = (row["observation"]["tick"] - before["observation"]["tick"]) & 0xFFFFFFFF
        if (0 < tick_delta < 0x80000000 and delta == 1 and native and native["flags"] and
                native["type"] == native["subtype"] == 1 and native["address"] == actor["address"] and
                native["origin"] == actor["origin"] == hex(enemy.RECORD) and
                native["phase"] == 1 and native["hp"] == 12 and not hazardous(row) and
                row["damage_configuration"] == before["damage_configuration"] and
                before["players"][1]["hp"] - player["hp"] == before["expected_damage"] and
                player["hp"] > 0 and player["reaction"] == before["expected_reaction"] and
                not player["pending_hit"] and
                player["state"] == 1 and player["action"] == 0x11 and
                1 <= player["iframes"] <= 75 and player["reaction_lock"] and
                menu.resources(before)[0] == menu.resources(row)[0]):
            return row
    return None


def contact_pause_contact(ctx: dict, *, expected_exe_sha256: str) -> dict:
    """Reusable candidate route; see source audit for provenance and limits.

    ctx is the personal-menu context plus pinned zero_overlay bytes and
    rpc(peer,command,**fields), checked by the owning runner. Online also
    supplies matched(label), backed by actual resolved core/mod CRC samples.
    """
    if expected_exe_sha256 != EXE_SHA or ctx.get("candidate_exe_sha256") != EXE_SHA:
        raise ValueError("R2 route requires the explicitly selected frozen executable")
    validate_zero_overlay(ctx["zero_overlay"])
    networked = ctx["mode"] == "netplay"
    if ctx["mode"] not in ("local", "netplay") or ctx["input_path"] != ("published_host" if networked else "offline_native"):
        raise ValueError("R2 controls require original native input locally or published host input online")
    if not callable(ctx.get("rpc")) or (networked and not callable(ctx.get("matched"))):
        raise ValueError("R2 needs owned trace RPCs and online resolved core/mod comparison")
    clients, both = ctx["clients"], ctx["both"]
    if len(clients) != (2 if networked else 1):
        raise ValueError("R2 needs one owned local process or two peers")
    output = Path(ctx["output"]).resolve() / "r2-contact"
    if ntpath.splitdrive(str(output))[0].lower() == "c:" or output.exists():
        raise ValueError("R2 evidence requires a fresh private directory off C:")
    output.mkdir()
    case = dict(kind="native_body_contact_pause_contact_candidate", status="failed_setup",
        helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        candidate_exe_sha256=EXE_SHA, mode=ctx["mode"], observations=[], trials=[], checks={},
        artwork_review="pending", ledger_status="unverified", limits=[
            "Source-derived route; only the retained actual trial can establish feasibility",
            "Only original intro record25 and an ordinary positive strength4 contact path",
            "Complete call arguments plus acceptance counter and HP/reaction are required; no return-v0 trace",
            "Pool/box/config reads are separate from the coherent body/counter publication",
            "Foreign actor/caller, terrain hazard or missed reaction windows remain failures",
            "Composed capture completion is not artwork approval"])
    ctx["report"]["r2_contact"] = case
    initial = None
    selected = []

    def require(ok, message):
        if not ok:
            raise debug.DebugError(message)

    def sample(label, *, need_actor=True):
        rows = both(lambda peer: observe_contact(clients[peer], ctx["zero_overlay"]))
        case["observations"].append(dict(label=label, peers=rows))
        if networked:
            ctx["network"]()
        for peer, row in enumerate(rows):
            observed = row["observation"]
            require(observed["ready"] == observed["enrolled"] == 1 and observed["failed"] == 0 and
                    not observed["mailbox"] and not observed["scene_owner"] and
                    observed["native_mode"] == 10 and observed["native_phase"] == 0 and
                    tuple(observed["lifecycle"]) == (0, 0), "R2 lost ordinary native gameplay")
            require(observed["players"][0]["x_raw"] == 144 << 16 and row["players"][0]["hp_raw"] == 32,
                    "R2 primary moved or lost its original HP")
            require(observed["players"][0]["character"] == 0 and observed["players"][1]["character"] == 1,
                    "R2 native seat identities changed")
            if initial:
                require(menu.resources(row)[0] == menu.resources(initial[peer])[0], "R2 changed X's resources")
            if need_actor:
                actor = row["instance"]
                require(actor and actor["phase"] == 1 and actor["hp"] == 12 and actor["subtype"] == 1 and
                        actor["strength"] == 4 and actor["contact_class"] == 0,
                        "R2 reserved authored enemy was lost, changed or damaged")
                if selected:
                    require(actor["address"] == selected[peer], "R2 authored origin moved to a different native slot")
            require(not hazardous(row), "R2 terrain hazard confounds contact attribution")
        return rows

    def advance(frames, label):
        ctx["native_advance"](frames, label)
        return sample(label)

    def hold(bits, frames, label):
        ctx["hold"](1, bits, frames, label)
        return sample(label)

    def capture(label):
        case.setdefault("captures", []).extend(both(lambda peer: dict(peer=peer, label=label,
            **ctx["debug"].capture_present(clients[peer], output / f"peer-{peer}-{label}.png"))))

    def recover(hits, counters, label):
        for step in range(80):
            rows = sample(label)
            require(all(row["p2_contact_counter"] == counters[peer] for peer, row in enumerate(rows)),
                    "R2 accepted another contact outside the controlled trial")
            if all(eligible(row) and row["players"][1]["action"] == 2 and
                   75 <= ((row["observation"]["native_timer"] - hits[peer]["observation"]["native_timer"]) & 0xFFFFFFFF) < 0x80000000
                   for peer, row in enumerate(rows)):
                return rows
            advance(3, f"{label} wait{step}")
        raise debug.DebugError("R2 did not recover native eligibility after75 ticks")

    def retreat(counters, label):
        # The first native trial retained the actor and counter but reached
        # x287.5625 after40 short offline pulses. Allow the original-input
        # retreat to reach the explicit safe position; waive no contact check.
        for step in range(60):
            rows = sample(label)
            require(all(row["p2_contact_counter"] == counters[peer] for peer, row in enumerate(rows)),
                    "R2 uncontrolled repeat contact during retreat")
            if all(row["observation"]["players"][1]["x_raw"] <= 280 << 16 for row in rows):
                # Retention is established by the same live origin/address
                # on every sampled step, not an invented lower X threshold.
                return rows
            hold(menu.LEFT, 4, f"{label} left{step}")
        raise debug.DebugError("R2 could not retreat safely while retaining the same actor")

    def approach(counters, label):
        last, stalled, jumped = None, 0, False
        for step in range(32):
            rows = sample(label)
            require(all(row["p2_contact_counter"] == counters[peer] for peer, row in enumerate(rows)),
                    "R2 contact occurred before the attributed trial was armed")
            positions = [row["observation"]["players"][1]["x_raw"] for row in rows]
            if all(x >= 350 << 16 for x in positions):
                require(all(x < 390 << 16 for x in positions), "R2 approach overshot the controlled window")
                return rows
            stalled = stalled + 1 if last and all(abs(a-b) < 65536 for a, b in zip(positions, last)) else 0
            last = positions
            if stalled >= 2 and not jumped:
                hold(0x4020, 24, f"{label} one native terrain jump")
                jumped = True
            else:
                hold(menu.RIGHT, 4, f"{label} right{step}")
        raise debug.DebugError("R2 bounded original-input terrain approach failed")

    def trial(label):
        before = sample(label + " before")
        require(all(eligible(row) for row in before), "R2 native body is ineligible before controlled contact")
        receipt = dict(label=label, before=before, observations=[], traces=[], evidence=[])
        receipt["armed"] = [None for _ in clients]
        case["trials"].append(receipt)
        def arm(peer):
            ctx["rpc"](peer, "fntrace_arm_clear")
            ctx["rpc"](peer, "fntrace_arm", target=hex(CONTACT))
            armed = ctx["rpc"](peer, "fntrace_armed")
            receipt["armed"][peer] = armed
            require(armed["count"] == 1 and {int(a, 16) for a in armed["targets"]} == {CONTACT},
                    "R2 exact native contact trace arm failed")
            ctx["rpc"](peer, "fntrace_clear")
        both(arm)
        histories = [[] for _ in clients]
        hits = [None for _ in clients]
        failure = None
        try:
            for step in range(30):
                rows = hold(menu.RIGHT, 2, f"{label} native body approach{step}")
                receipt["observations"].append(rows)
                for peer, row in enumerate(rows):
                    histories[peer].append(row)
                    require(((row["p2_contact_counter"] - before[peer]["p2_contact_counter"]) & 0xFFFFFFFF) <= 1,
                            "R2 multiple accepted contacts confound one trial")
                    hits[peer] = contact_evidence(before[peer], histories[peer])
                if all(hits):
                    break
            require(all(hits), "R2 lacked actual native HP/reaction/iframe contact evidence")
        except BaseException as error:
            failure = error
            receipt["error"] = str(error)
            raise
        finally:
            try:
                receipt["traces"] = both(lambda peer: ctx["rpc"](peer, "fntrace_dump", count=4096, seq_lo="0"))
            except Exception as error:
                receipt["trace_error"] = str(error)
                if failure is None:
                    raise
        for peer, page in enumerate(receipt["traces"]):
            complete_contact_trace(page, before[peer]["instance"]["address"])
        receipt["evidence"] = hits
        return hits

    try:
        ctx["native_advance"](45, "R2 settle baseline jump")
        initial = sample("R2 initial native preflight", need_actor=False)
        require(all(both(lambda peer: enemy.native_43(ctx["rpc"](peer, "gpu_state"), ctx["rpc"](peer, "ws_nw")))),
                "R2 authored approach requires native4:3/margin0")
        require(all(enemy.preflight(dict(row, record_allocated=bool(bytes.fromhex(row["record"])[0] & 1)))
                    for row in initial), "R2 source-derived authored preflight failed")
        require(all(row["players"][1]["hp_raw"] == 32 for row in initial), "R2 needs fresh full-health Zero")
        case["status"] = "failed"
        counters = [row["p2_contact_counter"] for row in initial]
        # Offline short SIO pulses can cover less ground than the paired
        # transport windows. Stop on native admission, with the same original
        # camera bound, rather than assuming24 pulses reach that boundary.
        for step in range(40):
            ctx["hold"](1, menu.RIGHT, 4, f"R2 native admission right{step}")
            rows = sample("R2 native admission", need_actor=False)
            require(all(row["camera"][0] <= 80 or row["instance"] for row in rows),
                    "R2 camera passed the source admission window without its bound native origin")
            if all(row["instance"] for row in rows):
                break
        else:
            raise debug.DebugError("R2 P2 lead did not admit the reserved enemy")
        initialized = advance(8, "R2 original HP12 initialization")
        selected = [row["instance"]["address"] for row in initialized]
        approach(counters, "R2 first terrain approach")
        first = trial("before-menu-contact")
        counters = [row["p2_contact_counter"] for row in first]
        retreat(counters, "R2 retreat before owned menu")
        capture("first-contact-safe-retreat-present")
        recovered = recover(first, counters, "R2 first native75-tick recovery")
        expected_hp = (32, recovered[0]["players"][1]["hp"])
        require(all(row["players"][1]["hp"] == expected_hp[1] for row in recovered),
                "R2 peers disagree on retained native health")
        (output / "personal-menu").mkdir()
        menu_ctx = dict(ctx, report=case, output=output)
        menu.personal_menu_smoke(menu_ctx, expected_hp=expected_hp, cursor_buttons=(0x40, 0x10))
        after_menu = sample("R2 same enemy after owned menu and safe controls")
        require(all(row["p2_contact_counter"] == counters[peer] for peer, row in enumerate(after_menu)),
                "R2 full menu case caused uncontrolled contact")
        ctx["native_advance"](80, "R2 post-menu saber expires away from reserved enemy")
        approach(counters, "R2 second terrain approach")
        second = trial("after-menu-contact")
        counters = [row["p2_contact_counter"] for row in second]
        retreat(counters, "R2 final safe retreat")
        capture("second-contact-safe-retreat-present")
        final = recover(second, counters, "R2 second native75-tick recovery")
        case["final"] = final
        case["checks"] = dict(two_actor_attributed_native_contacts=True,
            same_native_damage_and_reaction_before_after=all(
                a["expected_damage"] == b["expected_damage"] and
                a["damage_configuration"] == b["damage_configuration"] and
                a["players"][1]["reaction"] == b["players"][1]["reaction"]
                for a, b in zip(first, second)),
            x_resources_preserved=True, both_native_recoveries_observed=True,
            same_authored_enemy_retained_hp12=True,
            owned_menu_automated_checks_completed=case["personal_menu"][0]["status"] == "automated_checks_passed_artwork_review_pending")
        require(all(case["checks"].values()), "R2 before/after contact or owned menu differs")
        if networked:
            ctx["matched"]("R2 native body contact before/after owned menu")
        case["status"] = "automated_contact_checks_passed_artwork_review_pending"
        return case
    except Exception as error:
        case["error"] = str(error)
        raise
