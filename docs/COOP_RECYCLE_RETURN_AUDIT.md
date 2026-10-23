# Recycle alternate-area return policy: source audit

The outbound portal enters stage20/section1/CP0. Its authored destination has
**no category0/type1C reverse portal**. A Left movement at the entrance is not
a source-proven return route. The normal positive exit consumer goes through
variant-specific story/other loaders, rather than restoring stage4/section0.
This audit does not complete R14 or grant an accepted native input sequence.

There are three separate meanings of return: the passenger appearing after
the outbound load; movement back to the source room; and leaving the alternate
area through its native campaign progression. The existing outbound receipt
must retain its exact scope. Later scene/selector completion, other boss
variants and netplay are independent obligations.

## Original destination closure

`tools/audit_mmx6_recycle_return.py` reproduces the
[machine-readable source record](COOP_RECYCLE_RETURN_AUDIT.json). It requires
the pinned original EXE, complete original ROCK_X6.BIN identity, immutable
inventory digest, and selected DAT118 identity. It reads only the1,665,024-byte
BIN,4096-byte DAT header and655,360-byte DAT118. No disc bytes are committed.

| Item | Original source |
| --- | --- |
| Destination overlay | BIN28, sector591,40334bytes; SHA `7f49ac29077a76c6dc0aaafc474ad4d4eece65402282549de2f1ff2b5d748aef` |
| Initial layout | EXE80076384 ->800F2388;15×6 screens×3 layers,270bytes; SHA `2fdd0042cb39a7945c51ac2b872df790132b0ab33ecd1afa577d0947aecc85c1` |
| Collision resource | DAT118, relative sector13092; SHA `791ea8758ab8e936d3dd44d3b4d1ac8a7123bfed6f2d334f4b818a46091debfc` |
| Metatiles/descriptors | DAT118 subassets8/type0,30720bytes and9/type1,4512bytes; these differ from outbound DAT98's indices7/8 |
| CP0 | source80072FCC: player79/224, camera0/224, X bounds0..2576, Y bounds224..224 |
| CP1 | source80072FF0: player3024/224, camera2848/224, both X bounds2848 |

The complete31 primary and27 secondary authored records are checked losslessly
against the frozen inventory. The absence of a reverse portal applies to those
lists; it does not close every dynamic producer or indirect callback.

The category3 table is selected by EXE8006DF38 ->800F2940. Its important
records are:

| Origin | Type/subtype | Position | Native meaning established here |
| --- | --- | --- | --- |
|800F2498|6/1|3026/375|Checkpoint marker;52DB8 requires the original visibility helper to return0 and **resident** X>=3026 before writing CP1. P2-only advancement is not established.|
|800F24A0|0E/84h|32/256|Interaction/message controller5335C. Native region table selects strict0<X<224,240<Y<416. Native pressed0100h requests the interaction; it is not return-warp evidence.|
|800F2580|0D/0|3312/384|52E44 selects original boss member43/44/45 through PLAY+43B, waits for the native loader, allocates the boss then removes the controller.|
|800F2588|1E/1|32/354|EBEE8 copies subtype/origin/position to native singleton800CD340 and removes its placement actor: RideArmor initialization, not a reverse portal.|

The generic full initial scan uses strict cameraX-48<X<cameraX+368 and
cameraY-48<Y<cameraY+288. Moving-camera scans use narrower leading strips.
Neither this geometry nor a record center establishes live allocation,
camera-policy changes, a safe approach or original boss activation.

The entrance interaction additionally requires its original event bit4 clear
in PLAY+9E+2*group (group16 here), native97428=0, resident PLAYER+E0 neither1
nor2, action>=2, signed HP neither0 nor80h, and PLAYER+D4=0. These resident
singleton checks do not establish P2 ownership. Pressing Up here may select a
native message; it must not be reported as an accepted return warp.

## Native exit consumer, not a fabricated trigger

Original8001E32C consumes the actual native PLAY+0F after the native transition
and fade flow. For stage20/section1, its positive branch is:

| Actual PLAY+43B | Immediate original state | Following original loader |
| --- | --- | --- |
|0|major13h, CP2, PLAY+5F OR10h|1ED88 ->major14h, stage11/section0, CP2|
|1|major13h, CP4|1ED88 ->major14h, stage11/section0, CP4|
|other|major0Bh|1E81C ->major0Ch, stage15/section0/CP0|

The immediate state retains the old stage/section until the next loader.
Those are native modes/namespaces, not proof that their assets, story, unlock,
report or selector completed. The branch does not map back to4/0. No reverse
portal, forced exit or manufactured clear flag is added by this work.

A **negative** signed transition goes to major9 in the same20/1/checkpoint
namespace and preserves resident HP/ammo/weapon through PLAY+1E=-1. It is a
retry/resource policy, not campaign-return success. Transition0 follows the
native death/lives path and cannot be classified without the actual lives
state. These paths must not be substituted for a completed alternate exit.

The boss-defeat/clear producer, complete terrain/RideArmor traversal, arena
admission and later story/selector scripts are not closed here. The audit
models the exit consumer only. A native qualifier must let the original
producer run and observe each actual variant; writing PLAY+0F, boss HP,
progress flags or a destination would invalidate that claim.

## Conditional positioning and next native observations

Initial layer0 has an entrance ledge x0..95 at y384 with38h response and empty
space above it from y224. With the **actual current** source standing body
boxes X(0,2,11,19), Zero(0,3,11,19), full-foot centers11..85 give predicted
contact Y363/362. The CP0 X79 fits that conditional envelope. A +24 private
join offset does not automatically fit it. At x96/y416 the response is3Ah;
this audit does not classify it as safe terrain. RideArmor and other dynamic
actors also participate in the actual scene.

Consequently no blind Left/Right/fall, guessed floor teleport or complete
route is approved. The next owner-run observation should:

1. Require genuine20/1/CP0 load completion, both living grounded actors, exact
   live270-byte map and both collision assets, actual current+68 box provenance,
   cleared entry locks and completed composed captures.
2. Observe neutral first. Use separately attributed private geometry; never
   dereference a private Zero overlay pointer in resident X RAM. Preserve
   failures rather than refilling HP or forcing ground/action/locks.
3. Only after a current safe envelope exists, use bounded original held-frame0
   inputs with neutral cleanup to test independent control and room limits.
   Source bounds alone do not predict a frame count or safe traversal.
4. Close the native RideArmor/terrain/arena prerequisites before testing the
   alternate boss exit. Observe its original producer, actual PLAY+43B branch,
   intermediate namespace and both players' lifecycle through the eventual
   story/selector return. Disclose prerequisite/position/equipment bypasses.

No process, game/title build, input, guest write/call, native card, mutable
coverage ledger or compatibility profile was changed. Source tests establish
reproduction, strict arithmetic and policy distinctions only.

## Reproduce

Set process TEMP/TMP/PYTHONPYCACHEPREFIX to owned G/F paths first.

```powershell
python tools/audit_mmx6_recycle_return.py --original <original-EXE> --disc <raw-BIN> --out docs/COOP_RECYCLE_RETURN_AUDIT.json --check
$env:MMX6_CONTENT_EXE='<original-EXE>'
$env:MMX6_CONTENT_DISC='<raw-BIN>'
python -m unittest discover -s tools -p test_mmx6_recycle_return_audit.py -v
```

Creation refuses an existing output. Checking never overwrites the record.
