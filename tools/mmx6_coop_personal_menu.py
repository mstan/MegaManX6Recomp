"""Reusable native personal-menu case; the owning runner supplies accepted input.

This module never launches/stops a process, writes guest memory, sends direct
debug input, or updates a ledger. See COOP_PERSONAL_MENU_QUALIFIER.md for the
callback contract. Returned checks still require retained runtime receipts and
composed artwork review; importing or testing this module is not qualification.
"""
from __future__ import annotations

import hashlib
import ntpath
from pathlib import Path
import time


MENU_STATE = 0x800CF814
MENU_CURSOR = 0x800CF824
START, RIGHT, LEFT, SQUARE = 0x8, 0x20, 0x80, 0x8000


class MenuQualificationError(RuntimeError):
    pass


def _forward(old: int, new: int, minimum: int = 1) -> bool:
    delta = (new - old) & 0xFFFFFFFF
    return minimum <= delta < 0x80000000


def resources(row: dict) -> tuple:
    """Personal native resources from one coherent published diagnostic body."""
    return tuple((player["hp"], player["weapon"], tuple(player["ammo"]))
                 for player in row["observation"]["players"])


def resources_preserved(before: list[dict], after: list[dict]) -> bool:
    return bool(before) and len(before) == len(after) and all(
        resources(old) == resources(new) for old, new in zip(before, after))


def reduce_frozen_window(samples: list[dict], owner: int, *,
                         expected_cursors: list[int] | None = None,
                         reference_timers: list[int] | None = None,
                         networked: bool = False, minimum_progress: int = 6) -> dict:
    """Reject a frozen engine, wrong owner, changed world clock or cursor leak.

    Each sample contains peers[] (observation/menu/cursor) and, online, the
    actual network[] replies. Separate RPCs are not an atomic cross-peer state.
    Diagnostic progress proves observation continued, not once-world cadence.
    The native menu's first state byte must be1; its second byte is retained
    without assuming that every input-ready menu has the same substate.
    """
    if owner not in (0, 1) or not 1 <= minimum_progress <= 600:
        raise ValueError("Expected owner0/1 and bounded positive progress")
    checks = dict(enough_samples=False, native_pause_owned=False,
                  native_menu_input_state=False, world_timer_frozen=False,
                  diagnostic_publications_advanced=False)
    if expected_cursors is not None:
        checks["cursor_unchanged"] = False
    if networked:
        checks.update(network_active_without_desync=False,
                      transport_ticks_advanced=False, resolved_ticks_advanced=False)
    if len(samples) < 3 or not samples[0].get("peers"):
        return checks
    count = len(samples[0]["peers"])
    if count not in (1, 2) or (networked and count != 2):
        return checks
    if any(len(sample.get("peers", [])) != count for sample in samples):
        return checks
    if expected_cursors is not None and len(expected_cursors) != count:
        raise ValueError("One expected native cursor is required per peer")
    if reference_timers is not None and len(reference_timers) != count:
        raise ValueError("One original paused world timer is required per peer")
    peers = [sample["peers"] for sample in samples]
    if reference_timers is None:
        reference_timers = [row["observation"]["native_timer"] for row in peers[0]]
    observations = [row["observation"] for sample in peers for row in sample]
    checks["enough_samples"] = True
    checks["native_pause_owned"] = all(
        row["native_mode"] == 10 and row["native_phase"] == 2 and
        row["pause_owner"] == owner + 1 and tuple(row["lifecycle"]) == (0, 0)
        for row in observations)
    checks["native_menu_input_state"] = all(
        len(row["menu"]) == 2 and row["menu"][0] == 1
        for sample in peers for row in sample)
    checks["world_timer_frozen"] = all(
        row["observation"]["native_timer"] == reference_timers[peer]
        for sample in peers for peer, row in enumerate(sample))
    checks["diagnostic_publications_advanced"] = all(
        _forward(peers[0][peer]["observation"]["tick"],
                 peers[-1][peer]["observation"]["tick"], minimum_progress)
        for peer in range(count))
    if expected_cursors is not None:
        checks["cursor_unchanged"] = all(
            row["cursor"] == expected_cursors[peer]
            for sample in peers for peer, row in enumerate(sample))
    if networked:
        networks = [sample.get("network", []) for sample in samples]
        if any(len(status) != count for status in networks):
            return checks
        checks["network_active_without_desync"] = all(
            status.get("active") == 1 and status.get("players") == 2 and
            status.get("max_players") == 2 and status.get("rollback") == 0 and
            status.get("desync") == 0
            for statuses in networks for status in statuses)
        checks["transport_ticks_advanced"] = all(
            _forward(networks[0][peer]["tick"], networks[-1][peer]["tick"], minimum_progress)
            for peer in range(count))
        checks["resolved_ticks_advanced"] = all(
            networks[0][peer]["resolved_through"] >= 0 and
            _forward(networks[0][peer]["resolved_through"],
                     networks[-1][peer]["resolved_through"])
            for peer in range(count))
    return checks


def native_square_evidence(before: dict, history: list[dict], owner: int = 1) -> dict | None:
    """Native Zero action48 after Square; no input acknowledgment is evidence.

    X's buster does not share this action contract. A P1-owned case must supply
    a separately source-backed attack reducer through its runner context.
    """
    if owner != 1:
        raise ValueError("Default native Square reducer qualifies Zero only")
    old = before["observation"]
    if old["players"][owner]["action"] == 48:
        return None
    for row in history:
        now = row["observation"]
        if (not _forward(old["tick"], now["tick"]) or
                now["native_mode"] != 10 or now["native_phase"] != 0 or
                tuple(now["lifecycle"]) != (0, 0)):
            continue
        player = now["players"][owner]
        other = now["players"][owner ^ 1]
        if (player["active"] and player["character"] == 1 and
                player["state"] == 1 and player["hp"] > 0 and player["action"] == 48 and
                other["x_raw"] == old["players"][owner ^ 1]["x_raw"]):
            return row
    return None


def personal_menu_smoke(ctx: dict, owner: int = 1, *,
                        cursor_buttons: tuple[int, int] = (RIGHT, LEFT),
                        window_frames: int = 12, timeout: float = 12) -> dict:
    """Exercise a real owner's menu using a runner-owned input/advance adapter.

    Required ctx keys: mode, input_path, clients, both, debug, report, output,
    hold(seat,bits,frames,label), native_advance(frames,label), and
    transport_window(frames). Online also requires network() returning actual
    validated peer status. The adapter must check endpoint ownership before
    controls and release to neutral after each hold, including on error.
    """
    required = ("mode", "input_path", "clients", "both", "debug", "report", "output",
                "hold", "native_advance", "transport_window")
    if any(key not in ctx for key in required):
        raise ValueError("Incomplete personal-menu runner context")
    mode = ctx["mode"]
    if mode not in ("local", "netplay") or owner not in (0, 1):
        raise ValueError("Expected local/netplay and owner0/1")
    networked = mode == "netplay"
    if ctx["input_path"] != ("published_host" if networked else "offline_native"):
        raise ValueError("Online controls must use published host input; offline uses native pad input")
    if networked and not callable(ctx.get("network")):
        raise ValueError("Netplay menu qualification requires actual transport status")
    clients = ctx["clients"]
    if len(clients) != (2 if networked else 1):
        raise ValueError("Expected one offline process or two owned peers")
    if not 6 <= window_frames <= 120 or not 0 < timeout <= 60:
        raise ValueError("Menu window/deadline exceeds bounded case limits")
    if len(cursor_buttons) != 2 or any(value not in (0x10, RIGHT, 0x40, LEFT) for value in cursor_buttons):
        raise ValueError("Cursor change/restore use only native direction buttons")
    attack_reducer = ctx.get("attack_reducer", native_square_evidence)
    if owner == 0 and "attack_reducer" not in ctx:
        raise ValueError("P1 case requires its own source-backed native attack reducer")
    if any(not callable(ctx[key]) for key in ("both", "hold", "native_advance", "transport_window")):
        raise ValueError("Menu runner callbacks must be callable")
    if (not callable(getattr(ctx["debug"], "observe", None)) or
            not callable(getattr(ctx["debug"], "capture_present", None)) or
            not callable(attack_reducer)):
        raise ValueError("Menu observer/capture and attack reducer must be callable")
    output = Path(ctx["output"]).resolve()
    if ntpath.splitdrive(str(output))[0].lower() == "c:":
        raise ValueError("Generated menu evidence must stay off C:")
    capture_paths = {label: [output / "personal-menu" / f"p{owner+1}-peer-{peer}-{label}.png"
                             for peer in range(len(clients))]
                     for label in ("paused-present", "resumed-present")}
    if any(path.exists() for paths in capture_paths.values() for path in paths):
        raise ValueError("Retain earlier menu captures; use fresh evidence output")
    case = dict(kind="native_personal_menu", mode=mode, owner=owner,
                helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                input_path=ctx["input_path"], status="failed_setup", observations=[],
                inputs=[], frozen_windows=[], checks={}, captures=[],
                artwork_review="pending", limits=[
                    "No ledger result is produced by this helper",
                    "Native menu first state byte1 plus actual cursor response; second substate is retained without assuming1",
                    "Guest menu reads follow a coherent diagnostic RPC; they are not one atomic world snapshot",
                    "Diagnostic progress is not once-world cadence or a netplay simulation CRC",
                    "Composed capture completion does not establish artwork correctness",
                    "Default native Square reducer covers Zero action48 only"])
    ctx["report"].setdefault("personal_menu", []).append(case)
    pause_timers = None

    def require(ok, message):
        if not ok:
            raise MenuQualificationError(message)

    def read_peer(peer):
        observed = ctx["debug"].observe(clients[peer]).json()
        menu = clients[peer].read(MENU_STATE, 2)
        cursor = clients[peer].read(MENU_CURSOR, 1)
        require(len(menu) == 2 and len(cursor) == 1, "Truncated native menu state")
        require(observed["ready"] == observed["enrolled"] == 1 and observed["failed"] == 0 and
                observed["mailbox"] == 0 and observed["scene_owner"] == 0,
                "Menu case lost native co-op readiness or armed a mailbox/scene")
        return dict(observation=observed, menu=list(menu), cursor=cursor[0])

    def sample(label):
        current = dict(label=label, peers=ctx["both"](read_peer))
        if networked:
            current["network"] = ctx["network"]()
        case["observations"].append(current)
        return current

    def wait(predicate, label):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = sample(label)
            if predicate(current["peers"]):
                return current
            ctx["transport_window"](2)
        raise MenuQualificationError(label)

    def press(seat, bits, frames, label):
        case["inputs"].append(dict(seat=seat, pressed=bits, frames=frames, label=label))
        ctx["hold"](seat, bits, frames, label)

    def paused_window(label, cursors):
        samples = [sample(label + " start")]
        for _ in range(3):
            ctx["transport_window"](window_frames)
            samples.append(sample(label))
        checks = reduce_frozen_window(samples, owner, expected_cursors=cursors,
                                      reference_timers=pause_timers,
                                      networked=networked, minimum_progress=window_frames)
        case["frozen_windows"].append(dict(label=label, samples=samples, checks=checks))
        require(all(checks.values()), f"{label}: native ownership/cursor/frozen-time/transport check failed")
        return samples[-1]

    def capture(label):
        captures = ctx["both"](lambda peer: dict(peer=peer, label=label,
            **ctx["debug"].capture_present(clients[peer], capture_paths[label][peer])))
        case["captures"].extend(captures)
        return captures

    try:
        ctx["native_advance"](10, "Personal menu settle before original Start")
        before = sample("Personal menu native gameplay preflight")
        require(all(row["observation"]["native_mode"] == 10 and
                    row["observation"]["native_phase"] == 0 and
                    row["observation"]["pause_owner"] == 0 and
                    tuple(row["observation"]["lifecycle"]) == (0, 0) and
                    all(player["active"] and player["state"] == 1 and player["hp"] == 32
                        for player in row["observation"]["players"])
                    for row in before["peers"]), "Personal menu needs two healthy native intro heroes")
        case["before"] = before
        case["status"] = "failed"
        press(owner, START, 4, "Owner native Start")
        opened = wait(lambda peers: all(row["observation"]["native_phase"] == 2 and
                      row["observation"]["pause_owner"] == owner + 1 and row["menu"][0] == 1
                      for row in peers), "Owner native menu did not become input-ready")
        cursors = [row["cursor"] for row in opened["peers"]]
        pause_timers = [row["observation"]["native_timer"] for row in opened["peers"]]
        paused_window("Owner native menu idle", cursors)
        case["checks"]["owner_native_pause_and_frozen_world"] = True
        press(owner ^ 1, START, 4, "Other hero Start must not resume owner's menu")
        paused_window("Other hero Start rejected", cursors)
        case["checks"]["other_start_cannot_resume"] = True
        press(owner ^ 1, cursor_buttons[0], 4, "Other hero cursor input must be ignored")
        paused_window("Other hero cursor rejected", cursors)
        case["checks"]["other_cursor_cannot_change_owner_choice"] = True
        press(owner, cursor_buttons[0], 4, "Owner changes real native cursor")
        changed = wait(lambda peers: all(row["menu"][0] == 1 and row["cursor"] != cursors[peer]
                       for peer, row in enumerate(peers)), "Owner cursor did not actually change")
        changed_cursors = [row["cursor"] for row in changed["peers"]]
        paused_window("Owner changed cursor", changed_cursors)
        press(owner, cursor_buttons[1], 4, "Owner restores original native cursor")
        restored = wait(lambda peers: all(row["menu"][0] == 1 and row["cursor"] == cursors[peer]
                        for peer, row in enumerate(peers)), "Owner cursor did not restore")
        paused_window("Owner restored cursor", cursors)
        case["checks"]["owner_cursor_changes_and_restores"] = True
        case["checks"]["both_personal_resources_preserved_in_menu"] = resources_preserved(
            before["peers"], restored["peers"])
        require(case["checks"]["both_personal_resources_preserved_in_menu"], "Menu changed personal HP/ammo/weapon")
        capture("paused-present")
        press(owner, START, 4, "Owner native Start resumes")
        wait(lambda peers: all(row["observation"]["native_phase"] == 0 for row in peers),
             "Owner native menu did not resume")
        ctx["native_advance"](10, "Personal menu native gameplay resume")
        resumed = sample("Native gameplay after owner's resume")
        case["resumed"] = resumed
        case["checks"]["owner_resumes_native_world"] = all(
            row["observation"]["pause_owner"] == 0 and
            _forward(old["observation"]["native_timer"], row["observation"]["native_timer"])
            for old, row in zip(restored["peers"], resumed["peers"]))
        case["checks"]["both_personal_resources_preserved_after_resume"] = resources_preserved(
            before["peers"], resumed["peers"])
        require(all(case["checks"].values()), "Native resume or personal resources failed")
        press(owner, RIGHT, 6, "Owner independent native movement after menu")
        ctx["native_advance"](8, "Post-menu movement settle")
        moved = sample("Post-menu native movement")
        case["checks"]["continued_independent_native_movement"] = all(
            new["observation"]["players"][owner]["x_raw"] > old["observation"]["players"][owner]["x_raw"] and
            new["observation"]["players"][owner ^ 1]["x_raw"] == old["observation"]["players"][owner ^ 1]["x_raw"]
            for old, new in zip(resumed["peers"], moved["peers"]))
        require(case["checks"]["continued_independent_native_movement"], "Post-menu controls are not independent")
        press(owner, SQUARE, 2, "Owner native Square after menu")
        histories, attack = [[] for _ in clients], [None for _ in clients]
        for step in range(16):
            current = sample(f"Post-menu native Square observation {step}")
            for peer, row in enumerate(current["peers"]):
                histories[peer].append(row)
                attack[peer] = attack_reducer(moved["peers"][peer], histories[peer], owner)
            if all(attack):
                break
            ctx["native_advance"](1, "Post-menu native Square observation")
        case["native_attack"] = attack
        case["checks"]["continued_native_square_action"] = all(attack)
        require(case["checks"]["continued_native_square_action"], "No source-backed native attack state after Square")
        capture("resumed-present")
        case["checks"]["composed_captures_completed"] = True
        case["final"] = sample("Personal menu final native observation")
        require(all(row["observation"]["native_phase"] == 0 and
                    tuple(row["observation"]["lifecycle"]) == (0, 0) and
                    all(player["hp"] == 32 for player in row["observation"]["players"])
                    for row in case["final"]["peers"]), "Personal menu ended outside healthy native gameplay")
        case["checks"]["both_heroes_healthy_after_controls"] = True
        case["status"] = "automated_checks_passed_artwork_review_pending"
        return case
    except Exception as error:
        case["error"] = str(error)
        raise
