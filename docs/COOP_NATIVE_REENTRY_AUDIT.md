# Original final Quit and primary campaign reentry

This source audit and reusable helper add no native execution evidence or
R15 pass. Root owns any eventual local and two-peer qualification, with both
peers on this same machine. The existing reviewed Quit/cancel scenarios are
separate. No game/title build, source card, guest write, success flag, plugin,
SDK, CMake, ledger or remote operation was used here.

The original USA1.1 EXE and ROCK_X6 archive identities are pinned by
`inventory_mmx6_coop_content`. The derived source-window hashes and route
metadata are in [COOP_NATIVE_REENTRY_SOURCE.json](COOP_NATIVE_REENTRY_SOURCE.json).
No original binaries are committed. Ghidra's read-only project open reported
an existing lock; it was left untouched. The mapping below was checked against
the original local bytes using read-only MIPS disassembly and literal source
instruction tests.

The frozen X5 design reference `9ed460e7b7e60769fa12bcab74e228ae19796214`,
`docs/COOP_PARITY_BURNDOWN.md`, records a concrete post-Quit retired-stage-hook
failure: world/timer progress alone did not make a guest menu work after native
new-game reentry. Its corrected case actually opens the guest menu, rejects
other-seat control and resumes independent guest motion. Those are test-design
requirements, not X6 addresses or inherited passes.

## Actual original route

| Native action | Source and observed readiness |
| --- | --- |
| P1 Start, Select, Down/Cross | Existing native two-page Quit path. First page choice1 opens second page choice1. Native mode0Ah/phase2, menu `800CF814` bytes `01/06/02/01`, page word `800CF844`, fade `80097424=0` and shared choice `80097427` identify the ready page. |
| P1 Up, Cross on second-page choice0 | `8001FDFC..8001FE2C` tears down the old world, calls `8001D25C`, then `800133A0` terminates the old game thread. This is actual final Quit, unlike first-page Continue/cancel. |
| New frontend thread | `8001D25C` sets frontend `800CD3F8` major1/substates0 and starts `8001D0E4` on native thread0. It does not itself start a new campaign. |
| Native title load | Frontend major1 dispatch `8001E024`, sub0 `8001DE10`, loads native stage14/section0. The original selector chooses archive member18: 32488 bytes, SHA256 `3ae703ad03b2bbc4b71fc09e5f418e1e87ffd49a4a6a4240e69172fb87036166`. This is different code at the same load address as BIN16. |
| Native title Start readiness | Frontend major1/sub3, blocking byte `+0D=0`, fade0 and stage14/section0. `8001DEB8` makes this input state; `8001D190..8001D204` accepts Start and advances via major5 to major6. A loader state or fade acknowledgement does not qualify it. |
| Main choices | Major6/sub1 input `8001CF78`; cursor is frontend+2, with values0..2. Up/Down native edge1000h/4000h change it; Start/Cross edge0840h confirms. These correspond to public masks0010h/0040h and0008h/4000h. |
| Choice0: New Game | `8001DB48..8001DB78` sets PLAY major0/substates0, starts native game thread1 at `8001E6E4` and ends the frontend thread. Major0 dispatches `8001E088`, a native defaults initializer. |
| Choice1: current-data/card route | `8001DB88..8001DB98` enters frontend major7/sub0. Member18 `800ED760` dispatches through table `800F08FC`. |
| Current-data eligibility | `800EA62C..800EA6AC` reads RAM buffer header `80070CC4`. Header other thanFFh offers sub1 with shared choice0. HeaderFFh skips this prompt and goes to the actual card UI. The helper rejects that missing prerequisite **before any Quit input**. |
| Actual current-data import | Sub1 `800EA76C` toggles choice0/1 with Up/Down. Cross records the choice and enters sub3. With choice0 and fade0, `800EA8FC..800EA960` calls `8001BA1C(80070CC4)`, starts the native game thread and ends the frontend thread. No card selection or card read is supplied by the helper. |
| Map versus scripted return | The import selects PLAY major3 if `PLAY+158=FFh`; otherwise it restores that native script index and selects13h. Native major3 `8001E8CC` loads stage13/section0, archive member16. Original scripted/briefing readiness must complete before `PLAY=04/04/00`. |
| Real character/form selector | BIN16 Cross at map `04/04/00` opens `04/04/05`. The list at `800F1CB0`, count `800F1CEB`, comes from original `800E9898`. The co-op replacement removes only native unit5/Zero, preserving unlocked X forms. Left/Right use `800EB080` and the phase6 animation; `800ECD80` returns to phase5. The helper observes the persistent cursor change, not a short phase6 sample. It selects real list index0/X, then native Cross confirms. |
| Fresh native gameplay and guest UI | Actual PLAY major0Ah/phase0 must be followed by a **subsequent** coherent diagnostic publication with enrolled X/P1 and Zero/P2, both living and idle. The existing personal-menu helper then opens Zero's native menu, rejects X's Start/cursor, changes/restores Zero's cursor with Down/Up, preserves resources, resumes, moves Zero independently and observes native Square action48. |

Choice1 of the current-data prompt proceeds to real memory-card UI; that route
is intentionally never selected. Choice2 of the main choices is another
native frontend route and is not exercised. No UI text label is used as a state
predicate. Arrival dialogue Cross is allowed only for an actually active
native dialogue in phase3, under the original EXE text input decoder; map
briefing also requires native `04/0B/01` and original BIN16 code guards. The
helper does not advance arbitrary guessed screen states or complete an entire
campaign.

## What current data preserves

`8001BA1C..8001BD40` imports a native RAM snapshot, not the abandoned live player
body. The helper compares source-mapped persistent fields at the actual map
before selector or mission input: clear/tank/availability/resource fields,
native campaign arrays, souls and the imported per-stage records. Every
expected/actual mismatching slice is retained. The complete 951-byte current
buffer must also remain unchanged. These are strict comparisons; a legitimate
native difference would require source review, not silently relaxing a check.

The import does **not** write campaign character `PLAY+38` or armor `PLAY+5E`.
It is therefore insufficient to inspect imported unlocks or a correct menu
portrait. The helper separately requires X as the primary at the completed
title and map, then actually selects original X through the native unit list.
Live gameplay raw PLAYER/PLAY can be temporarily projected by a P2 callback;
the canonical published roster is used for gameplay ownership. No raw
projection byte alone is treated as promotion evidence.

`8001BD40` exports native current data to `80070CC4`. Member18 calls it at
`800ED15C` after actual card-data import. The audit has not derived every other
producer of that buffer across all overlays. A valid header proves that the
native prompt is eligible, not that the buffer was earned in the current run
or belongs to an independently qualified native card.

New Game is a separate contract. `8001E088` sets native maximum HP fields32/32,
armor1/Falcon and availability1, among other defaults, then selects native
story arrival. The helper checks those defaults after fresh native reentry.
It does not call that acquired-progress preservation, require spent live HP
to survive a native reset/import, or claim that New Game visits the map's unit
selector. The New Game receipt explicitly records that no such selector was
visited.
The defaults check waits for an actually observed native primary context:
ordinary PLAYER character0 and PLAY character0 in gameplay. It then checks
native body form1 against armor1. Samples taken during a legitimate private
Zero projection remain raw observations; they are not normalized into primary
form evidence. Failure to observe that context stays a failed qualification.

## Helper and adapter contract

```python
native_reentry_smoke(ctx, original_disc=raw_original_bin,
    expected_exe_sha256=frozen_candidate_sha,
    route="current_data", timeout=12, reentry_timeout=180)
# Separate fresh process/pair:
native_reentry_smoke(ctx, original_disc=raw_original_bin,
    expected_exe_sha256=frozen_candidate_sha,
    route="new_game", timeout=12, reentry_timeout=180)
```

Use the existing personal-menu ctx plus `set_input(seat, pressed_bits)` and
the adapter's exact `candidate_exe_sha256`/`candidate_binding`. Persistent
`set_input` must verify its owned listener/PID before every request: native
pad port `seat+1`, active-low mask and frames0 offline; original owned
`clients[seat].host_input(mask)` **only** online. Zero releases the same seat.
No SIO/mailbox/RAM input is permitted online. No direct writes are emitted by
the helper. Its P1 pulses always release to neutral in `finally` and require
actual decoded held input plus the native response, then the decoded
held/previous/edge triple to reach0/0/0. A request acknowledgement is not input
acceptance. Original errors survive a secondary neutral-release error.

Frontend pulses intentionally do not use `OfflineMenuAdapter.hold` or its
plugin-publication clock: the old game thread and stage diagnostic can stop
after final Quit. `hold`, `native_advance` and `transport_window` remain the
existing adapters for the later, fresh guest-menu case. Online additionally
requires `same_machine=True`, actual validated `network()` and resolved
`matched(label)`. The runner must retain its normal exact executable/compiled
manifest, default loader, actual host-profile/state-CRC, numeric127 same-machine,
fresh private profiles/cards and owned-process cleanup guards. This module
does not launch a process, copy cards or claim those runner guards from a ctx
string.

The one exact ordinary-RAM mapping is `80070CC4..800CF84C` (end exclusive),
387976 bytes. Its 775952 hex characters plus the existing reply envelope fit
the client's 1 MiB response bound. This is the existing emulation-thread
`read_ram` handler/heap reply used by the qualified native-reference reader;
the generic 64 KiB `DebugClient.read` bound is unchanged. One read covers current
data, body, fade/choice globals, decoded pad, dialogue, PLAY, frontend and native
personal-menu state. Wrong address/length, malformed/truncated data and RPC
errors fail closed, preserving the rejected receipt. Each accepted receipt
retains its full-payload hash and the exact relevant native slices. No pause,
scatter sampling, RAM write or diagnostic success counter supplies coherence.

Diagnostic and composed captures are separate RPC observations. The first
diagnostic seen after actual native gameplay arrival is an anchor, which may
still be the old publication. Only a strictly later eligible publication can
establish reentry. An old count that advanced between preflight and Quit is
insufficient. Thus native world/timer movement with a retired co-op callback
cannot pass. Both peers must independently satisfy native response/neutral
predicates; no atomic cross-peer snapshot is claimed.

All partial cases remain in `report['native_reentry']`; the reused guest menu
has its separate `personal_menu` receipt. Success is
`automated_native_reentry_checks_passed_artwork_pending`, with ledger status
unverified. The runner must wrap `ReentryError` for its existing baseline
cleanup and preserve its original failure. Native-card hashes must be checked
by that owning runner before/after and on failure. Artwork still requires
review of both Quit pages, actual title and reentered bodies/HUD/menu captures.
The existing guest-Select authority probe can be run separately after reentry;
this helper's reused personal-menu case does not send Select.

## Remaining native qualification

Run each route locally and with two same-machine peers on the exact selected
candidate. An empty current-data header remains an explicit missing native
prerequisite; do not create one with a fixture. A fresh zero-progress run can
qualify final Quit, New Game, callback recovery and menu/roster ownership in
that context. It cannot prove acquired armor/weapons, rescued Reploids,
nightmare souls, real card cold-Continue or primary campaign preservation for
an earned card. Those need an owned native earned-data route and separate
before/after source/private-card and content receipts. R15 status remains
root-owned and unverified until its exact required native evidence is reviewed.

Validation: 16 new pure tests cover the fixed atomic protocol and negative
replies, source-ready title/prompt predicates, decoder/neutral input proof,
two-peer consumed input, original-error preservation, source-imported campaign
and resource corruption, stale diagnostic rejection, separate defaults and
refusal of an empty buffer before any input. A deterministic new-game protocol
fixture checks the actual final-choice sequence and fresh-arrival anchor before
invoking the existing guest-menu helper. It is not native or artwork evidence.
Literal original EXE/BIN18 source words are checked when the local original
disc is available; the focused source check passed here.
