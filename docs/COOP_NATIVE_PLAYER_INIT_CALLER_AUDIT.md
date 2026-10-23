# Original native player-init boundary

This source audit supports a narrow root-owned repair of retired co-op callback
copies. No runtime, plugin, SDK, ledger, card or game build changes are included.
The retained exact-image native failure remains failed. The
[reproducible source census](COOP_NATIVE_PLAYER_INIT_CALLER_AUDIT.json) pins
original EXE SHA `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and ROCK_X6.BIN SHA `55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f`.

## All observed original static callers

The aligned encoded J/JAL and literal-pointer census covers the EXE and all59
archive members. It finds exactly two direct calls to8003BD24, no J/tail call,
no literal pointer and no overlay direct caller:

| Caller | Return address | Native context | Recovery disposition |
|---|---|---|---|
|8001D57C|8001D584|8001D51C; FRONT800CD3F8 root2, phase1 via800710E8[2] ->8001D424 ->800710AC[1]|Reject for the canonical gameplay repair.|
|8001E264|8001E26C|8001E1BC, selected by native PLAY.major9 through8007112C[9]|Canonical source signature; additional ownership/retirement requirements below.|

The only literal pointer to8001E1BC is major9's table entry80071150. The native
game loop8001E6E4 reads PLAY800CCED0.major at8001E700, dispatches the table at
8001E718 with a0=PLAY in the delay slot, and returns to8001E720. There is no
aligned direct call/jump or literal pointer to8001E6E4 in the EXE/archive.
Five constructed references install that loop with80013300(a0=1,
a1=8001E6E4): EXE8001DB64/8001DDC4/8001DDF4 and member18
800EA958/800ED85C. Each is followed by800133A0. These are native program/task
transitions, not synchronous calls from a stage phase into the game loop.
The source census is limited to the EXE and ROCK_X6.BIN; it is not a full
transitive call graph of other DAT/character banks or a proof against arbitrary
corrupted/computed PCs. Any foreign caller still fails the exact RA/stack/root
signature, which is the repair's boundary rather than a broad caller whitelist.

## Exact major9 order and entry CPU signature

8001E1BC saves incoming PLAY in s0 and its caller RA at[SP+14], then calls:
8002B838 /8002C2B8 pool initialization;80017E24 /800280F4;80029B8C
checkpoint position/camera selection;8002927C /8002935C /800293CC layer/camera
updates; **8001E264 ->8003BD24**;8002A33C /8002A3E8 record reset/admission;
entry/locks/fade setup; only then8001E304 writes majorA.

At the8003BD24 function-entry hook, **before its own prologue**, the source
portion of a narrow recovery predicate is:

1. Exact entry address8003BD24, native instruction8001E264 is its original
   JAL, and the original major/root code/table guards match.
2. CPU RA8001E26C; callee-saved s0=PLAY800CCED0; bounded aligned guest SP;
   actual word[SP+14]=8001E720, proving the enclosing major9 frame's native
   root return rather than an arbitrary direct initializer invocation.
3. PLAY.major=9. Phase0 and PLAY+38=0 bind the reviewed NewGame/X case, but
   **major9 itself neither dispatches on nor clears PLAY+1**. Those extra
   restrictions must not be advertised as universal properties of all native
   stage/checkpoint initialization.

Incoming a0 is not a useful gate:8003BD28 immediately overwrites it with a
physics constant. The initializer derives resident PLAYER800970A0 internally
and copies PLAY+38 into PLAYER+2 at8003BE10. Do not require pre-init resident
character, HP, action, visibility or resources: these may still describe the
old body. The earlier checkpoint selector already writes current/previous
position, while subsequent camera calls can run before the new body exists.
CPU.pc conventions belong to the SDK/generated callback contract; this audit
uses the explicit entry address and original architectural call/stack values.

This signature identifies entry, not successful completion. Failure or escape
inside the native initializer must leave enrollment invalid until actual
native landing/readiness admits the new body. It must not clear the existing
plugin failure flag or claim a fresh publication merely from the callback.

## Why the old stage cannot be an ordinary nested native caller

The normal majorA replacement wraps8001E9EC, whose phase table selects
8001EA28 /8001EB48 /8001EC40. No synchronous original call from those paths
installs a second8001E6E4 loop. A normal stage pass returns before the root can
dispatch the next major9. A new program loop instead follows task replacement.

For the observed final Quit path, original8001FD10 requires second page and
choice0;8001FE20 calls8001D25C, which installs frontend program8001D0E4
as task0;8001FE28 calls800133A0. That helper marks the current native task
inactive, calls B0/F **CloseTh** via80069E84 using the current task's TCB handle,
then B0/10 **ChangeTh** via80069E94. Later NewGame/title transitions install
task1's game loop through80013300 and call800133A0 themselves. The old final
Quit native task is closed, not suspended for a later normal return.

The SDK lane independently confirms its ChangeThread trap commits the new
TCB, skips saving a closed old TCB, and scheduler-longjmps. That runtime escape
contract is a prerequisite to discarding title-owned C callback copies.
**Public callback_active=false/host_call_depth=0 alone is insufficient:** direct
game netplay callbacks can bypass the package function-entry-depth tracker.
Source gates cannot fix an SDK that resumes a closed task or runs past a
nested dispatch return barrier. If that contract is uncertain, keep the case
blocked instead of treating a counter as proof of no live title frame.

## Narrow owned-frame retirement, never restoration

The retained probe observes stage_call1, STATE.count2/error0, inside0,
player_call0, zero_projected0 and zero_world0. It has **not** read the two
STATE frame tags/payloads. Source predicts this exact old primary-menu shape:

| Frame | Source | Required shape |
|---|---|---|
|0|stage_tick's stage_context|tag29,16bytes,words1; captured phase2 and survivor0|
|1|guest's architectural saved state|tag1,408bytes,words1; saved31=8001E720, saved99=8001E9EC, saved100=PLAY|

Before a repair uses that shape, validate those actual owned copies; count2
alone does not establish it. Reject error state, other tags/sizes, projected
Zero, additional frames, noncanonical/native-unknown calls and any still-live
invocation. Root owns the minimal implementation combining the source
signature, absence of projection and the closed/retired invocation contract.
If all required proofs hold, discard only these old owned copies and reset
their retired stage guard. **Do not execute their restore operations, restore
old architectural registers/body over the new X, clear unrelated guards,
repeat native initialization or grant resources.**

Projected Zero enrollment is a different host call: controller's original
post-player boundary has RA80020C70; enroll enters the Zero projection and
calls guest(8003BD24,0,0). Its inside/projection guards and RA fail the canonical
signature. Ordinary door8003D308 changes PLAYER script/control locks and
PLAY+1C; it is not a fresh3BD24 caller. Full stage/checkpoint transitions that
genuinely return through root major9 are a distinct lifecycle event.

The private checkpoint command8 also follows the original mode8 ->root9
initializer. Its entry observer requires address8001E1BC, RA8001E720,
a0=PLAY, no stage/projection/STATE frames and validated selected source. It
does not directly guest-call the initializer. Unit fixtures that invoke the
observer with synthetic registers test rejection/order, not real native
nesting or host retirement.

## Native campaign/resource ownership and retained failure

Signed PLAY+1E controls8003BD24's native resource policy:0/-2 initialize HP
and ammo from campaign maxima; -1 restores preserved HP/ammo/weapon from PLAY;
other values skip those branches. A host retirement repair must preserve all
of these native choices. The initializer also reconstructs native animation,
trail and attached-object resources; broad old-state restoration would undo it.
Current-build snapshots remain build-specific; this task adds no migration.

The reviewed [retired-stage failure capsule](evidence/mmx6-native-reentry/manifest-bound-beeae10-retired-stage-guard-reviewed.json)
SHA `dcadbe89143b13ca25aa5b97faa98af6ccc07cef5faab208689b30adb999087d`
binds sourcebeeae10, executablea8f20cdc and SDK6212e680. Native X is healthy
and idle while the old diagnostic publication is stale; actual P2 Start for
128 native updates fails to open its menu. That runtime failure remains
unchanged. Exact frame-payload observation, focused real-plugin guards and
fresh exact-image native local/paired reentry remain root-owned requirements.

Reproduce this source audit with non-C TEMP/TMP/PYTHONPYCACHEPREFIX:

```powershell
python tools/audit_mmx6_native_player_init.py --original-exe <original-EXE> --original-disc <raw-BIN> --out docs/COOP_NATIVE_PLAYER_INIT_CALLER_AUDIT.json --check
python -m unittest discover -s tools -p test_mmx6_native_player_init_audit.py -v
```

Four pure/source tests cover source reproduction, canonical/attract/projected/
door/wrong-root/phase/roster distinctions and exact frame-shape negatives.
Synthetic shape/signature success is not a native or host-retirement pass.

## Integrated repair and bounded native qualification

The title now checks the exact caller/stack signature, inactive projection
guards and both owned frame shapes at the original initializer boundary. It
discards only the retired stage guard and frame count; it never executes the
old restore operations or rewrites native RAM, CPU, resources or frame count.
Saved STATE_WORDS are read as host-order uint32_t through memcpy, matching
their capture format on both host byte orders.

The actual-plugin retirement fixture escapes stage_tick/guest through a
modeled scheduler longjmp, checks the two resulting copies, invokes the real
initializer callback and exercises fresh publication and P2 menu ownership.
Twenty-five negative cases reject foreign callers, unsafe stacks, active
projection, unknown phases and altered frame shapes/payloads. Focused Clang
debug/production and GCC production variants pass. This fixture does not
execute original CloseTh/ChangeTh or establish native artwork/gameplay success.
The preserved beeae10 failure remains an exact-image failed observation.
The [348a52c receipt](evidence/mmx6-native-reentry/manifest-bound-348a52c-new-game-reviewed.json)
now has completed native local and paired New Game reentry: the strict guard
accepts the original boundary, fresh enrollment/publications follow, and all11
guest menu/resume/movement/attack checks pass. The pair adds29 resolved matching
core/mod samples and matching reviewed paused/resumed composed images. This
does not independently dump the two old host frames or qualify native Continue,
unit selection or acquired campaign progress. Earlier incomplete capture and
wall-deadline attempts remain retained; full R15/F208 coverage is incomplete.
