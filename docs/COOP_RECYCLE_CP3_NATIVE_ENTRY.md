# Recycle CP3: native admission state and landing prerequisite

The observed portal record byte3=10h is an original native admission mutation.
The original-only guard rejected that normal first-admission state. This change
adds its exact producer guard and accepts four complete record variants. It
does not change portal ownership, gameplay, checkpoint readiness or transition
logic. The failed CP3 setup remains failed and R14 remains unverified.

## Retained observation

Root's owned offline candidate was game `c5fadead5296cb4bc53a5c283b04e5814e025f09`,
actual executable SHA256
`39c154966f9c12f939a8305551a910de9dbb97878dcf05c5935bed03c7ca7036`.
Its retained report is
`G:/Temp/Codex/psxrecomp/x6-parity/portal-cp3-v15-c5fadea-observation/qualification.json`,
SHA256 `e858a4d09a091417195cc874fe8adab8167656886ffdd80e402211d321b9c58d`.
This lane read it; it did not launch a game or modify that report.

The original initializer completed once at stage4/section0/CP3, record80072468.
Readiness never qualified: native X remained phase1/action0, shared entry lock1,
timer0, X1728 and falling Y. The readiness samples reached map height2048;
the subsequent separate preflight read Y2056. Those are separate observations,
not one merged actor sample. All528 live map bytes matched the initial authored
map. The source-bound portal existed in slot0, phase1/action1, with origin
800F2B0C and record `011c011010063006`. All three retained overlay code/table
windows matched their original SHA256; the record predicate was the sole failed
source-closure component. This is failed setup evidence, not portal gameplay.

## Exact native byte3 writer

Original USA v1.1 EXE SHA256:
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
The complete admission leaf `80029E7C..80029F38` is188 bytes, SHA256
`df6eff4115848b712fbc5f13bac169665422de1032a5e9544412af5d56e7da89`.
Primary scanner `80029F38..8002A33C` calls it at8002A12C before allocating an
actor. Its a0 is the authored eight-byte record. Relevant original flow:

- `80029E84` reads category as record+3 AND0Fh. Category0 passes its category
  gate against PLAY+68; retained PLAY+68 was1.
- `80029E9C` bypasses the state step when PLAY+68=3, returning admission0.
- Otherwise high state0 branches at80029EC8. Its delay slot80029ECC computes
  byte3+10h; `SB80029EF8` writes10h and returns0, allowing allocation.
- Scanner8002A180 binds the record pointer to actor+10. After allocation,
  `8002A25C/264` ORs1 into record byte0.
- Reset8002A380/384 keeps only byte3's low category nibble;8002A388/38C restores
  byte0's authored70h bits. Record stride remains8.

Supported complete record words are therefore byte0=0/1 crossed with byte3=00/10h:

```text
001c010010063006
011c010010063006
001c011010063006
011c011010063006
```

No mask accepts additional high states or changes the type/subtype/coordinates.
The generic scanner has later visibility/state transitions; those are outside
this narrow first-admission closure and remain rejected. The live actor must
still satisfy every existing pool, origin, phase/action, native pointer, stage,
caller and eligible-seat guard. The observer applies the same four complete
variants. Immutable inventory/extracted original bytes are unchanged.

## Original action0, gravity and entry lock

The original major9 initializer sets PLAY+1C=1 at8001E280. Native phase0 path
8003CBE4 selects initializer8003D850 through80073CF4[0]. That initializer sets
action0, body+67=FFh and signed VY=FFF80000h (-8.0) at8003D880..898.
`8002D5D0` integrates Y as `Y -= VY`, giving8px downward motion per accepted
native update on this entry path. No floor exists in the initial scoped
CP3-side corridor, consistent with the actual neutral fall.

Phase1 action0 dispatch is80073ACC[0] ->80035144. Previous/current contact
flags are ORed into body+89 at80035008. If body+89 lacks bit8,
800351AC branches to ordinary motion8002D5D0 and native probe8003D394; action0
persists. Ground contact instead enters the landing animation at800351B4,
clears body+67 and advances subaction at800351C8..E8. After animation byte+46
clears,80035238 clears PLAY+1C, and8003AD18 sets ordinary action2. No timeout
or automatic missing-floor release occurs in this closure.

The native world-clock eligibility byte80073A6C[action0] is0. Its check in
80034DCC skips the timer increment at80034F54 while action0 persists. Thus the
observed action0/lock1/timer0 follows original native entry requirements. The
co-op native-init hook resets enrollment/scene ownership, and the controller
deliberately waits for the native action2/lock release before enrolling P2.
There is no source basis here to call this a co-op scene-gate failure.

| Original native extent | SHA256 |
| --- | --- |
| `80035144+130h`, complete action0 | `91b9828f0f48f99c656a94c2265bca160e21e88e28b98745c81ff46c7c4a575d` |
| `8003D850+58h`, entry initialization | `75c2be1b842225635daeed3106a879e7d51c3ae197f95aa31187dd3f23b85068` |
| `8002D5D0+84h`, position integration | `356e0ca61dbba2e987f4ac85ff51d6b4375aeb2b40dc2576390d114f8a225522` |
| `80034FBC+188h`, phase1 dispatch/contact history | `901bb59a96f4e1865be962469ce0e9a3e215496cf595265d8d370835925840b2` |
| `8003CCBC+44h`, current default body box | `537f24ae8672645fb7a217bcb99b0acadaa110d3dc01f84d33f24f53d3acad99` |

The frozen inventory's field named arrival comes from checkpoint record+18;
native80029BF8 writes it to facing byte PLAYER+15. CP3's value40h is not a
grounded/finished-arrival assertion. Record+22 supplies body+CE's initial native
countdown through80029D14; this record's value is1.

## Conditional X foot plane and portal boxes

Native8003CCBC selects standing X box80073D50=(signed offsets0,2; unsigned
radii11,19), or Zero80073D54=(0,3,11,19), when body+D5 is nonnegative. The live
resident X box was80073D50. Original floor1616 and the checked clear rectangle
from [the terrain audit](COOP_RECYCLE_TERRAIN_AUDIT.md) imply X contact centerY
`1616-2-19=1595`; one-pixel air is1594. The corresponding source body-center
X envelope is1467..1557. This is conditional static arithmetic, not a safe
live placement or an approved route.

Root's proposed **offline-only** command4 probe is a disclosed positioning
prerequisite bypass. It must retain exact live box, map, scratch pointers and
resource hashes, dynamic hazard/solid checks, and original landing/animation,
ground/action/entry-lock release and enrollment. No success, ground, phase,
lock or clock write substitutes for those native outcomes. CP3's locked
cameraX1568 leaves that envelope/portal offleft; using CP2's authored camera
range320..1264 remains a separate disclosed setup choice, not original route
reachability. This lane issues no positioning/input command.

Pinned Recycle member6 SHA256 is
`c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5`.
Its portal body+68 points to800F38B8=(0,0,16,24). **Contact does not use +68**:
original8002D654 uses actor+50 ->800F38BC=(-18,-28,28,40) and the player's
actual current+54 damage box. Portal+54 ->800F38C0 has the same four bytes.
These contact widths/heights have the directional rectangle semantics below;
do not reinterpret them as terrain radii. The retained actor layer was0 and
both actor/player facing had bit40h set.

For this nonnegative actor layer, let A/P be signed integer actor/player
coordinates, ax/ay and px/py signed box offsets, aw/ah and pw/ph unsigned box
widths/heights, and fa/fp the respective facing bit40h. Original arithmetic is:

```text
sx = Ax + (fa ? -ax : ax);  tx = Px + (fp ? -px : px)
if tx < sx:
    width = fa ? (fp ? aw : aw+pw) : (fp ? 0 : pw)
else:
    width = fa ? (fp ? pw : 0) : (fp ? aw+pw : aw)
horizontal = abs(tx-sx) < width
sy = Ay+ay;  ty = Py+py
vertical = abs(ty-sy) < (ty < sy ? ph : ah)
```

The native result also requires player+61=0, nonnull actor+50 and player+54.
All comparisons are strict; zero width means no hit. During the retained entry
preflight player+54 was0, so that snapshot cannot trigger portal admission.
After native landing installs a real damage box, use its actual bytes and
facing to establish the initial miss. Do not substitute the terrain +68 box.
The portal's reflected horizontal reference in the retained facing is
1552-(-18)=1570, and vertical reference1584-28=1556. Negative actor-layer
camera-relative handling lies outside this normal-world formula. Never invoke
guest collision helpers from the debugger or combine separate RPCs into a
same-tick P1-outside/P2-contact claim.

## Validation and remaining native work

Ten observer tests pass with actual original EXE/disc inputs, including bounded
execution of the admission leaf's original instructions and all256 byte0/byte3
values. Nine terrain tests still pass. Source audit reproduction is unchanged.
The actual-plugin C fixture now starts with the observed admitted record and
checks all four exact variants plus the existing ownership/lifecycle negatives.
Under this lane's no-build boundary, root owns compiling/running that fixture
and all title/native integration. No build or game ran in this lane.

R14 still needs a source-checked collision-ready setup, original accepted P2
contact with P1 outside, one native fade/load sequence, both grounded arrivals,
retained resources, independent controls and completed rendered evidence. The
failed CP3 attempt supplies none of those passes.
