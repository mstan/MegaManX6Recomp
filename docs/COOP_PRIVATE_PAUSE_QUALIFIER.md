# P1-owned native pause and private-effect freeze helper

`tools/mmx6_coop_private_pause.py` provides
`private_pause_smoke(ctx, *, expected_exe_sha256, window_frames=12, timeout=12,
max_retirement_ticks=32)`. It has no launcher, CLI, input RPC implementation,
guest writes, cards, fixtures or ledger updates. The owning runner supplies
the exact candidate binding, original accepted controls and private evidence
paths. This helper has unit evidence only; no native game or title build was
launched for its implementation.

The scope is the fixed X/P1 + Zero/P2 roster in a safe native gameplay context:
a P1-owned pause must freeze the complete private P2 body and both fixed pools
while observations and, online, resolved transport continue. Native resume
must advance those effects again, followed by a genuinely accepted original
P2 dash-jump and finite retirement. It does not qualify the opposite roster,
X/P2 charge, P1's buster, the entire R9 contract or exactly-once world cadence.
It never calls Zero's Square reducer as evidence for P1.

## Actual native route and gates

The accepted-input mask for Circle is `2000h`. Native dash acceptance and the
positive signed marker at body `+8C` are mapped in
[the source closure](COOP_R9_EFFECT_CLOSURE.md): `80039EB0` accepts native dash
conditions; initializer `8003A9C4` takes ordinary action `0C`, or dash-jump
action6 with a simultaneous accepted jump. The ordinary animation can delay
or cancel the positive marker. Input acknowledgements therefore cannot prove
native acceptance. Source arithmetic for negative-marker drain is conditional
on own updates and is not a measured frame count.

The helper first requires living, idle fixed-roster actors and clear private
trails. It holds original P2 Circle+Left (`2080h`) to keep the intro preparation
away from the first authored enemy. An observer may issue exactly one nested
**other-seat** P1 Start only after actual positive-marker, ordinary-action,
three-visible-trail evidence appears on every peer. P2 remains held until the
outer adapter's finally-neutral release. P1's native phase2, wire owner1 and
input-ready first byte1 at `800CF814` must actually retain that active trail
window. No menu-open-during-dash assumption or invented delay substitutes for
the observation. Failure to obtain that window remains `failed_setup`.

Once input-ready pause with a positive visible private trail is observed,
failed checks are retained as `failed_behavior`, with the actual error type
and message. This status reports a case-contract failure, not an automatic
game-bug diagnosis. The helper holds P2 Circle, Right and Select separately.
Select is requested for at least 96 scheduler/transport intervals and its actual
**during-held** samples must span at least 90 publications, covering the source
departure threshold. It verifies every observed private body byte, all three
60h trail records and all three 50h attached-effect records remain identical
to the original paused baseline. Cursor, personal resources, lifecycle,
native timer and P1 ownership must also remain intact. Repeated equal polls
cannot substitute for at least three forward completed publications per peer.
Online, both real transport and resolved watermarks must advance without desync.

Only P1's original Start resumes. The helper observes actual native mode/phase,
effect advancement and the prior dash's retirement rather than waiting on a
world clock while still paused. It then requests fresh P2 Circle+Jump+Right
(`6020h`) from a retired pool. The source-bound effects reducer requires native
action6/positive marker, all three visible trails, negative-marker drain phases1
and2, then marker0 with all active/visible flags clear within the bounded native
timer window. An actual rising P2 position must also be observed. This is an
ordinary native dash-jump/airborne observation, not an air-dash unlock proof.
Native action7 can retain its positive marker after neutral input. The runner
retains that continuation explicitly, with a separate 120 native-tick diagnostic
deadline. The configured retirement window begins at the first observed
negative marker per peer. It still requires both drain phases and every trail
to become inactive and invisible; marker0 alone does not complete retirement.
The first v12 native attempt exposed the old neutral-anchored deadline while
passing the full paused-body/pool freeze and resume checks. That failed raw
attempt remains retained and is not rewritten into a pass.
Both heroes' personal resources and P1's X remain fixed throughout observed
history. The native timer is not presented as an independent helper counter.

## Adapter contract

Use the [personal-menu context](COOP_PERSONAL_MENU_QUALIFIER.md): `mode`,
`input_path`, `clients`, `both`, `debug`, `report`, `output`, `hold`,
`native_advance`, `transport_window`, and actual `network()` online. Add:

| Key | Requirement |
| --- | --- |
| `candidate_exe_sha256` | Actual runtime SHA256 verified by the owning runner; must exactly equal the explicit `expected_exe_sha256` argument. No old candidate hash is hardcoded. |
| `candidate_binding` | Optional JSON manifest/build/config evidence, retained unchanged. Image verification and compilation provenance remain the runner's responsibility. |
| `effects` | Current `mmx6_coop_private_effects` module with `observe_effects`, `reduce_effect_menu_freeze` and `reduce_zero_dash`; its file hash is retained. Frozen images without the extension fail setup. |
| `hold_observed(seat,bits,frames,label,observe)` | Publish only accepted original input for that seat. Invoke `observe()` at least three times **while input remains held**, returning those JSON-safe rows in order. Respect a bounded wall deadline, always neutralize in `finally`, then neutral-space before returning. |
| Nested other-seat input | The observed-hold callback may perform one other-seat synchronous `hold` for P1 Start. Holds must clear only their own seat. Sample at least three times even when the nested menu operation advances the outer window. Same-seat nested writes are not used. |
| `matched(label)` | Required online: retain actual resolved core/mod CRC comparisons after the complete case. A generic acknowledgement cannot implement this callback. |

Offline controls use `offline_native`; online controls must use
`published_host` through the matching peer. Direct online SIO/mailbox adapters
are rejected. Process/listener ownership, correct input mappings, profile/build
checks, card isolation and neutral cleanup remain the runner's responsibility.
The helper does not create input threads or call input/memory debug RPCs itself.

The returned observer rows are `{sample_index,label,peers,network?}`. Each peer
contains the effects module's JSON output plus separately read menu/cursor
bytes. Effects/body/pool state comes from one completed diagnostic publication;
menu bytes follow separately and are not claimed to be one atomic world read.
The helper keeps parsed live objects internally for the source reducers, while
all retained report fields are JSON safe.

The post-dash reducer receives per-peer accepted-input receipts with original
path, seat1, pressed mask, no bypasses and forward `before_tick/after_tick`
publication brackets. The press interval is bracketed by the pre-hold and
first forward held sample; neutral is bracketed by the final held and first
post-neutral sample. These are sampled bounds, not invented exact command ticks.
They retain the adapter's successful original-input transaction; native marker,
action, pools and retirement remain mandatory independent evidence.

## Receipts and review

Cases append to `report['private_pause']` before controls. Keep the complete
report on every exception. `PrivatePauseError` derives from `RuntimeError`;
an offline baseline exercise must record it and wrap it as `DebugError` so the
baseline's existing result/owned-cleanup path runs. Root owns those adapters.

Evidence goes into a fresh `output/private-pause` directory off C:. The helper
retains the original accepted-input requests, coherent observations, frozen
window reductions, source-effect resume/dash reductions and completed composed
captures before and after resume. Earlier paths are not overwritten. A queued
capture acknowledgement or canonical VRAM screenshot cannot satisfy the GL
capture callback.

Automated completion returns
`automated_private_pause_checks_passed_artwork_pending`. `artwork_review` stays
`pending` and `ledger_status` stays `unverified`. Review the actual P1 menu,
native resources, retained trail colors/ownership and restored heroes/HUD on
the exact bound image separately. Actual local and paired runs remain required.

All 18 pure/negative tests pass, including transient full-body/pool mutation,
wrong owner/clock/cursor/roster, frozen engines, stalled resolution, source
threshold duration, stale or wrapped publications, missing capability, and an
acknowledged dash with no native marker that must never request P1's menu.
These tests establish evidence and callback rejection behavior, not gameplay.
No plugin, checkpoint, CMake, SDK, CLI, paired runner or ledger changes accompany
this helper.
