# Native Quit Game and continuation ownership

R7 and R15 remain unverified. The new helper exercises source-backed native
confirmation/cancel behavior and a separate guest-authority probe; it does not
claim a complete Quit/current-data/character-selection cycle. No game, title
build, plugin/SDK change, card operation or ledger update was performed here.

The frozen X4 reference is Playtest42 commit
`50593bca772b600de6911cbfecd40b0f08721147`,
`docs/COOP_PLAYTEST_REGRESSIONS.md`, blob
`7619517d5ebd4c27e943f36fbb41ccb38357d410`. R7 requires hiding P2 on native
Quit pages. R15 prevents a guest Quit from promoting its character into the
primary campaign when continuing with current data. X4 blocks Select in the
guest's owned menu. Its `world_draw_visible()` separately excludes the native
Quit backdrop while retaining ordinary pause fades. These are ownership and
presentation requirements, not X6 addresses or inherited passes.

The frozen X5 definitions at `9ed460e7b7e60769fa12bcab74e228ae19796214`
preserve those separate checks. Their later bounded implementation receipts
are investigation leads only. The X6 helper uses two peers on the same machine
for any eventual netplay execution; no other machine or OS is qualified.

## Original X6 path

Original source is USA v1.1 `SLUS_013.95`, 522240 bytes, SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
Address-to-file offset is `address - 0x80010000 + 2048`. The helper verifies
that entire original EXE and the four source windows in its `SOURCE_REGIONS`.
No original binary or artwork is committed. Read-only original disassembly
and the existing menu cursor audit establish the following path.

The personal menu is `800CF810`: state+4, input substate+5, nested flow+6,
Quit flow+7, ordinary cursor+14h, previous input substate+30h and Quit page
word+34h. `80097424` is the fade/transition flag; `80097427` is the shared
two-choice cursor. Neither is the ordinary menu cursor at `800CF824`.

| Step | Native code and state | Accepted published input |
| --- | --- | --- |
| Open owned personal pause | Existing `stage_tick` arbitration; mode0Ah/phase2, menu state1 after native opening | Owner Start `0008h` |
| Open Quit | `800348B0..900` tests edge0100h with input substate0..2 or8, saves that substate to+30h, selects substate6 and clears+6 | Owner Select `0001h` |
| Wrapper | Substate6 table entry `80034B70`; native fade completes, then +6=2 calls `8001FFC0` | No further input during native setup |
| First page | `8001FF30` sets menu+7=1,+34h=0 and shared choice0, builds table`800711F4`; `8001FD10` handles input | Up/Down `0010h`/`0040h` toggle0/1 through `8001F5A0` |
| First-page Continue/cancel | `8001FD78..94`: choice0 requests fade, sets menu+7=2; `8001FF78` advances wrapper+6; `80034C20..40` restores saved input substate | Cross `4000h`, native edge0040h |
| Second page | First-page choice1 sets menu+34h=1, builds table`80071200`, keeps choice1 | Down, then Cross from first-page choice0 |
| Second-page Back | `8001FE38..58` rebuilds first page with page0 and choice0 | Cross while second-page choice1 |
| Actual native Quit | Second-page choice0 takes `8001FDFC..E2C`: driver/actor teardown, `8001D25C` starts the frontend thread, `800133A0` ends the current thread | Up, then Cross from second-page choice1; **not sent by this helper** |

Confirmation is Cross, not Circle: the native edge is0040h and the co-op input
route swaps the two pad bytes. Circle2000h belongs to the native dash case.
The lower ordinary nodes also must not be confused with Quit: node0Dh closes
and resumes, node0Eh enters the distinct `80034A88`/`8002AB58` path, and
node0Fh enters screen adjustment. This case does not depend on node0Eh's label.
The stage-exit node10h is a different, stage-clear-gated route. Select-to-Quit
does not require granting a stage clear, tank, weapon or ability.

Exact audited original windows:

| Address / bytes | SHA256 | Role |
| --- | --- | --- |
|800348B0h / ECh|543e10d9173c3ec75572ed5ae1a0e4ebea260df49ce1691c51af041e6a500728|Select admission and input dispatch|
|80034B70h / ECh|67e5b261733da1dfd5f3c3d699e48cf3cc7f561d14f78de7478a41669124cf54|Quit wrapper and pause return|
|8001FD10h / 164h|61d1a95c84ac1e20b87557a7ebc922487293485c7fe2e3bde54713dab41dfa97|Two-page choices and actual teardown branch|
|8001FFC0h / 4Ch|ba2dbd646de6fc434640f0309f397fec6db98d3de631b472e9335b78e2594b20|Nested Quit-flow dispatcher|

## X6 co-op observations and limits

The reviewed game source is `92509a5793139b9e5f5ab9107f694dc4bf93e0da`.
Its `stage_tick` consumes Select for lifecycle edge tracking during menus,
but still routes that same pad to the native Zero-owned menu through
`route_p2_input`. There is no source guest-Select refusal in that path. This
is a concrete reason to run the guest-authority probe, not a reported native
failure or proof of campaign promotion. The probe fails and captures the
admitted page before sending any confirmation if a guest actually enters
native substate6.

`enter_zero()` temporarily projects Zero's body and sets PLAY+38h=1 and
PLAY+5Eh=5. A normal `leave_zero_context(1)` restores the campaign identity
while retaining shared world/menu changes. One raw PLAY+38h read during an
owned guest callback can therefore be1 without any promotion. The observer
retains that raw byte as `projected_campaign_character`; reducers use the
canonical published X/P1 and Zero/P2 bodies for roster checks. Final native
Quit's terminating thread and later native current-data selection need a
separate source-bound reentry audit and actual runtime evidence. Merely
returning from the first confirmation page resumes the existing personal
menu; it does not qualify current-data loading or character selection.

The co-op render and HUD hooks gate on mode0Ah but do not themselves have an
explicit Quit-substate exclusion. Native Quit uses a distinct draw path;
presence or absence of a registered hook is insufficient to establish final
visibility. Logical P2 body+3 may remain1 while no gameplay sprite is drawn.
The helper therefore captures completed composed output on both native pages
and leaves body/HUD/effect suppression for explicit visual review. It does
not substitute canonical software VRAM, a logical visibility byte, a packet
counter or an empty starting effect pool for this presentation requirement.

## Reusable bounded helper

`tools/mmx6_coop_native_quit.py` exports:

```python
native_quit_smoke(ctx, original_exe=original_slus_path,
    expected_exe_sha256=exact_candidate_sha,
    scenario="guest_authority", timeout=12, window_frames=12)
# Separate fresh owned run:
native_quit_smoke(ctx, original_exe=original_slus_path,
    expected_exe_sha256=exact_candidate_sha,
    scenario="p1_pages_cancel", timeout=12, window_frames=12)
```

The context matches `mmx6_coop_personal_menu`'s owned accepted-input contract:
`mode`, `input_path`, `clients`, `both(fn)`, `debug.observe/capture_present`,
`report`, `output`, `hold(seat,bits,frames,label)`, `native_advance` and
`transport_window`. The runner must settle the existing baseline jump before
entry. Both heroes must be idle and healthy with HP32 in the original intro.
The new explicit `candidate_exe_sha256` must match the caller's expected image.
Online additionally requires `same_machine=True`, actual `network()` and
`matched(label)` callbacks. That declaration does not replace the runner's
loopback/listener/PID, matching-build, negotiated profile, default-loader and
resolved core/mod CRC proof. Online input must be `published_host`; direct
SIO, private mailbox and RAM fixture paths are rejected by contract.

The guest-authority scenario opens Zero's pause and attempts Select. It sends
no guest Cross if Quit is admitted. A refusal must preserve the owned native
pause, frozen world clock, progressing publications/transport, resources and
roster, then resume original independent controls. The P1 scenario opens and
captures the first page, actually Continues/cancels to pause, reopens it,
enters/captures the second page, rejects guest Up/Cross, and follows the two
native cancel branches back to pause. It then resumes and moves P2 natively
while X stays fixed. It never selects final-quit choice0 on the second page.

Every page window requires exact native UI state, fade0, at least three
distinct forward publications, frozen native world time, owner/roster,
personal HP/ammo/weapon and the observed shared clear/tank fields. Online
requires actual transport/resolved progress without desync and a resolved
core/mod comparison after the case. Menu/global/PLAY reads follow the coherent
actor publication and remain separate RPC observations; no atomic cross-peer
snapshot is claimed. All inputs and partial failures remain in
`report['native_quit']`. The owning runner must retain private card hashes,
all artifacts and the helper's failure, wrap `NativeQuitError` in its normal
cleanup-compatible error when necessary, and stop only its owned processes.
The helper itself never launches, stops or sends the debug-server `quit` RPC.

Automated success is
`automated_native_quit_bounded_checks_passed_artwork_pending`; this is not an
R7/R15 pass. Artwork and ledger status remain pending/unverified. Root must
run the scenarios on fresh private profiles in local and same-machine paired
modes. Primary final Quit/title/current-data/character reentry, non-empty
campaign progress, opposite roster, preexisting effect suppression and a
subsequent guest-owned menu remain separate requirements. No source card or
success/unlock/progression writes are allowed to supply those outcomes.

Twelve pure tests cover exact page/owner/substate/choice gates, stale or
stalled publications, native clock/resource/roster/progress leaks, actual
two-peer transport progress, transient projected identity, truncated reads,
wrong original/candidate/input/machine contracts and preservation of an
admitted guest failure without sending confirmation, including a secondary
capture failure. They do not execute the
game or qualify either comparison.
