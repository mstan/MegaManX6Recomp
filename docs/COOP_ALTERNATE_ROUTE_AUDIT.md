# R14: original Recycle hidden-area teleport

This is a bounded **source audit** of frozen R14, against game commit
`952bb4b7b684b9bf05dc9777ce37738b053247dd`. Local co-op and netplay remain
unverified. No game, build, memory write, save change or ledger update was made.
The reproducible metadata is [COOP_ALTERNATE_ROUTE_AUDIT.json](COOP_ALTERNATE_ROUTE_AUDIT.json).

## Native identity and authored location

The original USA v1.1 executable SHA256 is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
Only the existing `ROCK_X6.BIN` extent (LBA211185, 1,665,024 bytes, SHA256
`55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f`)
and its selected Recycle member6 are interpreted. That member begins at archive
sector153, is42,944 bytes and has SHA256
`c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5`.
Its guest base is `800E9860`. No copyrighted payload is included in this audit.

The frozen inventory's stage4/section0 primary record18, `800F2B0C`, is
category0/type1C/subtype1 at `(1552,1584)`, flags0. Original bytes bind it to
`8006DC6C[stage*2+section] ->800F301C`, whose slot1C at `800F308C` points to
the overlay controller `800EC678`. The workbook's `ObjectOriginTable!C7`
labels this object “Hidden Area teleport.” Its semantic label is a research
index; the executable/archive establish the native contract. Workbook replacement
bytes are not stock guards. The workbook SHA and immutable inventory SHA are
retained in the JSON.

`80052F64` is a different common event/dialogue-zone path. Its optional input,
authored bounds and once-only event bits do not establish portal admission.
The current co-op wrapper at that address cannot be counted as R14 coverage.

## Original contact, ownership and transition

The phase table `800F3900` selects initializer `800EBD80`, active phase
`800EC6C4`, then retirement `800EC740`. Subtype1 initialization reaches
phase1/action1/subaction0. The active action table `800F3910[1]` calls
`800EC780`. Its `JAL800EC79C` calls `8002D654(portal,800970A0)`: the second
argument is explicitly the singleton resident `PLAYER`.

The portal attack box is `actor+50 ->800F38BC`: signed offsets `(-18,-28)`
and unsigned extents `(28,40)`. The helper requires `PLAYER+54` and tests
`PLAYER+61` immunity. Native facing, signed centers and directional half-open
comparisons matter; an actor-center radius or shared camera position is not
equivalent. Contact does not require Select. On subtype1 contact, the portal
stores resident integerX in `+84`, changes action to2 and clears subaction.
Subtype2 and fortress subtypes are separate paths outside this audit.

Action2's substate table `800F3928` runs `800EBEC0`, `800EC8F8`, then
`800EBFB4`. Setup requires nonzero resident HP, sets shared PLAY flags
`10,11,12,13,14,15,16,17,19` to2, and clears camera bytes `+44/+98/+EC`.
It saves `PLAYER+68` in `actor+88`, clears the player's box pointer, sets the
player action to2 and retains residentX in `actor+80/+82`. These are mutable
ownership effects, not a pure proximity helper.

`800EC8F8` increments the portal's halfword timer `+7C`, adjusts the resident
player integerX through `+80/+82` according to native frame parity, and at
timer29 calls `800139F4(8)` from `800EC964`. `800EC978` writes
`PLAY+0F = subtype |40h`, hence `41h` here. “29” counts accepted native helper
invocations; frozen/menu publications do not prove that many gameplay updates.

The original stage-transition routine `8001E32C` explicitly handles flag41h
within Investigator stages1..8. `8001E3D4` calls
`80042F7C(stage,&PLAY+0C,&PLAY+0D)`. Its signed arithmetic produces
`stage=19+(oldStage-1)/2`, `section=(oldStage-1)&1`. Recycle stage4 therefore
becomes alternate stage20/section1. New major8 initialization at `8001E1BC`
calls native checkpoint initialization `80029B8C` and camera routines
`8002927C/8002935C/800293CC`, resets the transition flag and enters major0A.

The destination has two authored checkpoint records: `s20-a1-c00` at
`80072FCC` and `s20-a1-c01` at `80072FF0`. They are candidates, not an assertion
that the actual portal chooses checkpoint0. Selected checkpoint, completed
streaming/overlay identity and live camera bounds still require native evidence.
The original restore substate waits for fade idle, restores saved residentX and
box pointer, re-enables the camera bytes and clears its shared freeze flags.

## Current co-op coverage gap

The current adapter registers door `80050250`, interaction `80051924`,
event/dialogue `80052F64` and script-entry `8003D308` paths. It has no explicit
type1C portal admission wrapper at `800EC780` or its `8002D654` contact helper.
During ordinary living two-player gameplay, `stage_tick` advances the original
world once with resident X/P1. The additional projected Zero pass advances its
private body, shots, contact and attached/trail pools; it does not repeat this
portal actor. Survivor, personal-menu and established scene contexts can place
Zero in the native world, which is distinct from an either-player portal policy.

The explicit resident-player argument and missing adapter are source-proven.
An actual P1-far/P2-only failure is **not measured** here. The existing shared
camera hooks do not replace the portal collision argument. Existing scene
passenger release waits for a grounded, controllable owner with native locks
clear, but has no explicit portal destination-generation check.

A future fix must cover the pure contact decision and the owning portal's
multi-update body/box/camera/freeze/transition closure. Projecting only X as in
the intro enemy near-target fix is insufficient. Running the whole world or
portal AI twice would duplicate shared state. No runtime patch is proposed as
proven by this audit.

## Reproduction and native checks

With `TEMP`, `TMP` and `PYTHONPYCACHEPREFIX` redirected to G:

```powershell
python tools/audit_mmx6_alternate_route.py --exe <original-SLUS_013.95> --disc <original-raw-bin> --check docs/COOP_ALTERNATE_ROUTE_AUDIT.json
$env:MMX6_CONTENT_EXE='<original-SLUS_013.95>'
$env:MMX6_CONTENT_DISC='<original-raw-bin>'
python -m unittest discover -s tools -p test_mmx6_alternate_route_audit.py -v
```

`--output <new-file>` initializes a new report and refuses an existing path.
`--check` is read-only. The audit reads committed source at the exact base,
validates original identities and reproduces the native record/tables/extents.
It never rewrites the frozen inventory or live coverage ledger.

Obtain native co-op-off X/P1 and co-op P1 controls first. Bind the live portal's
origin pointer `+10` to record18. Then keep X outside the actual collision boxes
and approach with a living Zero, retaining native call/result, phase/action,
box/immunity/facing and once-world context. Observe one original setup and fade,
actual stage20/section1 load, selected checkpoint and completed composed image.
Require safe full-foot destination terrain, released controls and separate real
input acceptance for both actors. Exercise the real native return/exit separately.
Repeat local and netplay on one exact candidate with resolved input/core/mod
evidence. Positioning bypasses must be explicit; never write portal action,
transition or success flags. Missing/absent/fallen/menu/passenger cases need
separate negatives. No native, rendered, campaign or R21 refight pass follows
from this source audit.
