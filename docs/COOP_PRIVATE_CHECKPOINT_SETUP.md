# Private offline checkpoint entry setup

This is a development fixture for campaign QA, not a retry, progression,
checkpoint reachability or mechanic pass. The first native v12 attempt reached
the requested initializer but exposed an incomplete completion predicate. The
[reviewed receipt](evidence/mmx6-checkpoint/manifest-bound-e2e47e6-incomplete.json)
rejects its automated completion status: both diagnostic actor positions were
still from the old stage and the composed capture was black. This fixture is
not yet qualified for campaign setup.

The immutable [content inventory](COOP_X6_CONTENT.json) retains all 115 tuples.
Only 94 tuples in its 23 authored placement sections are permitted. The other 21
menu, cutscene and unresolved namespace records are explicitly unsupported setup;
they remain unverified. Neither membership in a stage number range nor a
screen load establishes a playable route.

The runner verifies the complete original USA v1.1 EXE SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and frozen inventory SHA256
`67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad`.
The generated guard table retains every original stage/section/checkpoint,
pointer table, record pointer and record hash. At acceptance and again at
mode9 entry the actual plugin checks its selected native pointers/record plus
the original dispatcher, mode8 loader, mode9 initializer and checkpoint-selector
instruction spans. Resident FNV32 guards detect mismatched code/data; they are
not cryptographic identity and do not replace the runner's full EXE check.

## Native ordering and restrictions

At the existing outer `stage_tick(8001E9EC)` boundary, command8 is permitted
only offline in a debug build, with healthy enrolled actors, no menu/scene,
no projected or nested callback, and normal native gameplay. It installs the
inventoried stage/section, selects native mode8 and returns handled immediately.
It does not execute the stale stage's original world pass or grant HP/resources.
The native mode8 loader `8001E914` owns loading and its checkpoint reset.

The new function-entry observer at `8001E1BC` requires mode9, the selected
stage/section, checkpoint0 from mode8, `a0=800CCED0` and return address
`8001E720`, proven by the original dispatcher's `jalr` at `8001E718`. It then
installs only the requested checkpoint before returning to ordinary dispatch.
It never calls the initializer, replaces it, uploads an overlay or writes
native tables. A repeated/out-of-order observer fails the pending operation.
The native receipt reaches completion at the subsequent mode0A stage entry
with the selected tuple. That receipt alone does not establish playable entry.
The original runner's publication check was anchored before the payload RPCs,
which could accept a later old-stage publication. Qualification additionally
needs freshness anchored after the completion receipt, actual new actor
initialization/placement and native control readiness, followed by inspected
composed output. The source-bound readiness checks below are implemented and
unit tested; a corrected native run and composed inspection remain unverified.

Pending state is cleared by activation/reset and by detected plugin,
source/context/order or offline-policy failure. Queued command8 and both
pending phases reject current-build snapshots. No old-state conversion is
provided. A loader that never reaches the next boundary remains incomplete;
the runner preserves that bounded timeout and stops its owned process.

All online and `PSX_NO_DEBUG_TOOLS` paths reject before authoritative game
mutation. Existing commands1..7 retain their rejection policy. No success,
unlock, rescue, clear or persistent native-save flag is written. The fixture
is an explicit stage/checkpoint prerequisite bypass, and accepted setup sets a
sticky diagnostic taint marker until activation. It cannot qualify strict
ordinary-input capture. When the SDK exposes `session_input_taint.h`, acceptance
also calls `psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX)` before game
mutation. The game never resets those host flags; only the SDK session owner
may reset them. Older SDKs retain the diagnostic marker but lack this capture
API taint integration and remain unsuitable for strict recording qualification.

## Diagnostic transaction

The client writes stage, section and checkpoint bytes at `diagnostic+51/+52/+53`,
a nonzero uint32 request nonce at `+54`, then commits command8 at `+50` last.
Only the outer stage boundary consumes an offline command; the controller's
projected/post-player boundary leaves it queued. Invalid tuples, unsupported
namespaces and zero nonces are rejected before any game state write.

| Offset | Receipt |
| --- | --- |
| `+A0` | `CKP1` capability, little endian `31504B43` |
| `+A4` | Request generation, increments when command8 is consumed |
| `+A8` | 0 idle,1 loading,2 initializing,3 complete,4 failed,5 rejected |
| `+A9` | Reason:0 okay,1 forbidden,2 unknown/invalid,3 unsupported namespace,4 unsafe,5 source,6 order,7 context,8 plugin failure |
| `+AA/+AB/+AC` | Requested stage/section/checkpoint |
| `+B0` | Request nonce |
| `+B4` | Guarded initializer entry count; success requires1 |
| `+B8` | Inventoried native record pointer |
| `+BC` | Sticky prerequisite-bypass taint marker |

An acknowledgement alone cannot pass. The runner requires a new generation,
the exact nonce/tuple/record, count1, taint1, completed state, actual native
mode/tuple and a new enrolled publication **after the first observed completed
state**. The pre-request publication is retained only as history. Every
completed-state probe records its own native bytes, coherent diagnostic,
GPU state and readiness reduction under `completion_waiting`.

The original mode9 sequence calls checkpoint selector `80029B8C` at `8001E244`
and native player initialization `8003BD24` at `8001E264`. The selector writes
PLAYER current/previous XY at `80029BD8/BE0/BE8/BEC` and primary-camera current,
previous and bounds. The co-op native-init observer clears enrollment; only a
subsequent native idle handoff can enroll the new private actor. Mode0A can
therefore coexist with a diagnostic publication from before that handoff.

The completed-state anchor fixes the concrete race: pre-request tick215 and
later old-world tick220 from payload processing cannot pass merely because
mode0A/CP1 is now present. First completed state anchors220; only a strictly
later publication may satisfy readiness. A repeat of220 or a backward tick is
incomplete, even when every other readiness field looks correct.

Source guards additionally require normal mode0A/phase0 with the requested
tuple, living idle X/P1 and Zero/P2, no scene/menu/mailbox, and native
`PLAY+0F/+10/+1C` clear. Mode9 explicitly sets `+1C=1`; the existing controller
and native pause gates reject those blocking states. The runner reads the
resident P1 body and primary camera together in one bounded native read. It
requires visible native X identity, idle state, the existing co-op safe-landing
condition (`+67==0`, `+70 & 8`), equal current/previous position, and agreement
with the newly published P1 position. A temporary Zero projection cannot stand
in for native P1.

P1's X must equal the authored checkpoint X exactly. Its Y must be the actual
settled native Y inside the current camera/GPU viewport; the authored Y is the
initial spawn and can change under native arrival/gravity. No guessed pixel
tolerance is used. The actual primary-camera bounds must equal the selected
record, except for the narrow original intro CP1 dynamic region described below:
maxX/minX/maxY/minY at camera `+1C/+1E/+20/+22`, current XY at `+0A/+0E`.
Both actors must lie inside that camera's actual reported display width/height
and widescreen margin, with display enabled. Scripted entries that move X,
moving supports or actors not reaching idle remain incomplete under this
conservative contract until their source-backed readiness is separately mapped.

The immutable inventory field named `arrival` is not used as a readiness
state: original record byte `+18` is copied to PLAYER `+15` at `80029BF8`.
Native entry blocking state is observed directly. The existing owned CLI
requests its completed composed GL capture only after readiness; that capture
still needs inspection. A nonempty PNG alone is not proof of a visible playable
scene. Separate PLAY/GPU, coherent diagnostic and native body/camera reads are
retained separately, not claimed as one atomic world snapshot.

## Reproduction and current validation

`tools/qualify_mmx6_coop_checkpoint.py` reuses the baseline's process lifecycle,
PID/listener checks, hidden muted profile and cleanup. It uses the existing
offline input adapter to settle the intro before the fixture. It requires a
fresh private candidate or explicit build/source/disc/output arguments, an
expected executable SHA256, original source and inventoried selectors. Output
paths remain arguments; no source cards or old caches are copied.

Example after root builds and freezes a candidate containing the observer:

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/pycache-checkpoint'
python tools/qualify_mmx6_coop_checkpoint.py --candidate <fresh-private-profile> `
  --original <original-SLUS_013.95-or-raw-BIN> --stage 0x01 --section 0 --checkpoint 1 `
  --expected-exe-sha256 <exact-runtime-sha256>
```

The original baseline report/status stays hash-linked and unchanged. The
separate result is `prerequisite_bypass_setup_completed_artwork_pending` on
automated setup completion, with `ledger_status=unverified`. Partial errors,
command publication history, native bytes, camera, actors and composed capture
are retained. Artwork still needs inspection and no ledger row is changed.

Focused tests compile the actual plugin against isolated guest RAM, using only
read-only pinned original code/data. They do not emulate the native loader or
prove gameplay. They cover all 115 tuples, the 94/21 policy, guarded mode9 ordering,
pending reset/failure, duplicate entry, source/context mutations, deferred
controller handling, no stale original stage call, unchanged HP/body, and
online/production rejection. The existing snapshot fixture additionally checks
queued command8 and both pending phases reject snapshot creation. Python tests
cover frozen inventory/source identity, selectors, CLI guards and incomplete,
rejected, duplicate, stale or mismatched transaction completions.

Validation passed locally: the checkpoint fixture under Clang with `-O2` in
debug/production and the SDK taint header from `ef638ae184a0d0e3f2c389d26e6e16350bfbe57a`,
plus Clang `-O0` and GCC `-O2` without that optional header; the existing
snapshot fixture under Clang `-O2` debug/production; and the original 12 Python cases
with the pinned original EXE supplied. The optional API fixture supplies its
own host taint stub and verifies accepted setup taints, rejection does not,
and fixture reset never clears SDK taint. It does not qualify a linked game.
Header reproduction, Python syntax and whitespace checks also pass.

The subsequent completion fix passes all 20 Python cases, including the exact
old-publication race, required post-completion freshness, new actor/camera
agreement, blocking native entry flags, projection rejection, native grounded
settling and offscreen/disabled-display negatives. Synthetic positive fixtures
exercise the predicate only; they do not establish a CP1 landing or qualify
the earlier black native capture. The reviewed failure receipt and its original
automated status remain unchanged.

Root's integration registers the C and Python fixtures. This completion fix
changes only the Python predicate/tests and this document; no additional title
build, native run, coverage or 234-row parity-ledger change accompanies it.
A corrected actual entry and composed inspection remain required separately.

## Intro CP1 native dynamic minimum Y

This source audit pins the original USA v1.1 EXE SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
The PS-X payload is `80010000..8008F000` (file offset `800`). The bounded
intro BIN2 is archive descriptor 2, sector 36, size 74784, loaded at `800E9860`,
SHA256 `d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`.
The complete archive SHA256 remains
`55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f`.
No original executable/disc payload is distributed by this audit.

The native closure is reproducible from those inputs:

| Step | Original address and behavior |
| --- | --- |
| CP1 source | Stage0/section0 root `80073300` → table `80073134`, CP1 → record `8007212C`. Player spawn 2112/1072, camera1968/944, bounds minX1968/maxX5120/minY944/maxY944. |
| Initializer | `80029B8C..80029D18`: `80029C64` writes record+14 to camera+22, and `80029C70` to camera+2A. Both start at944. |
| Region placement | Intro primary root `8007349C` → `800FA214`; index9 at `800FA25C` is category3/type0/subtype7, position2128/1088. |
| Handler | Loader `80013EE0..80013F08` indexes root `8006DE94` and publishes the selected pointer at scratchpad`1F80008C`. Intro root → BIN2 table `800FA6E0`, whose type0 word is `80052258`. Phase dispatch reads `800791E8`: phase0=`80052294`, phase1=`8005211C`. |
| Region bind | `80052294..80052300` selects `80079D70[(stage*2+section)]`, masks subtype with7F and multiplies by16, stores its pointer at instance+18, then calls `8005211C`. Intro root=`800791F0`; subtype7 → `80079260`. |
| Authored region | Eight unsigned halfwords at `80079260`: `[2112,2143,1040,1135,FFFF,FFFF,896,FFFF]`. They mean inclusive X/Y rectangle, followed by minX/maxX/minY/maxY targets. FFFF means retain that target. |
| Target writer | `8005211C..80052258` rejects offscreen/retired context via `8002CAB4`, then tests resident P1 integer XY against that inclusive rectangle. Inside it sets camera+47=2. `800521F4` writes region+0C (=896) to camera+2A; the other targets remain unchanged. |
| Camera update | `8002927C..8002935C` checks camera+44, player+CC, character/player+E0 gate, calls the native camera mode, then `80028EBC` at `80029340`. |
| Native minY branch | `80029094..80029180`: equal current+22 and target+2A skip the write. When target is below cameraY, `80029104..80029128` computes signed16 `a1=P1.integerY-camera.integerY-camera[2C]`. At `8002912C`, nonnegative a1 branches directly to `8002917C`, `sh a1,22(a0)`. It does not add cameraY on that branch. |

Consequently P1 Y1115, camera Y944 and camera+2C=96 produce current minY75
while the authored target is896. The value is the original branch's arithmetic,
not an arbitrary tolerance or a replacement engine coordinate. With those
stable inputs the next native camera update stores the same value again.
The unchanged-944 initializer alone cannot produce it: the equal-bounds branch
does no minY store until a target changes.

Root's retained first narrow writer trace
`G:/Temp/Codex/psxrecomp/x6-parity/checkpoint-v12-e2e47e6-intro-cp1-camera-trace/qualification.json`
has SHA256`be79a39bb6cef5821d838c841901d9ae39b1b78f01da69a8791b8a8a2960b179`. It
contains the changed store at sequence35/frame2846: PC`8002917C`,
RA`80029348`, width2, current minY`03B0→004B`, A0`800971F8`,
A1`004B`, A2`0380`, T0`2`, T1`03B0`, V1`045B`, V0`004B0000`.
The saved prefix contains only the oldest2048 of4629 available writes; it is
not a complete trace. It identifies the current-bound writer and its native
target896. The subsequent owned target watch below corroborates the specific
earlier target writer at `800521F4`.
This audit does not claim that every possible writer/corruption path was ruled
out, nor that native CP1 readiness or a composed image has passed.

The helper now accepts that exact CP1 dynamic state only after read-only
resident SHA256 checks cover the original smoother, wrapper, initializer,
region routines, checkpoint/region/handler roots, placement and dispatch data.
The policy also requires that P1 is inside the exact authored region, all
other current and target bounds remain authored, target minY is the source
record's896, current cameraXY stays authored, mode/active/visible fields are1,
speed2, offset96, player blocking fields clear, and current minY is precisely
the nonnegative signed native formula. A guessed value75, missing source
evidence, partial camera read, changed target/code/table, other checkpoint or
other camera state does not enable this exception. Other checkpoint readiness
continues to use exact authored bounds.

P1 and the full primary camera are read together as `800970A0+1AC` bytes.
The old198-byte pure-codec input remains valid for the authored-bounds path,
and cannot enable the dynamic policy. Static guards are cached per transaction
only; the actual actor/camera/GPU and fresh completed publication are still
checked for every readiness sample. The legacy receipt key
`camera_inside_authored_bounds` means inside the verified native bounds on
this narrow path. It does not disable camera containment. All existing living
roster, source tuple, exact authored X, grounded/settled native body, completion,
publication, viewport and display checks remain required. The command remains
a tainted prerequisite bypass with ledger status unverified.

Reproduce machine-readable source metadata without a game launch or writes:

```powershell
python tools/mmx6_coop_checkpoint.py --original <original-raw-BIN> --camera-audit
```

The output records full-source identities, bounded code/data span SHA256s,
exact native IDs and PCs. It does not inspect unrelated disc members or change
the immutable content inventory. Set `MMX6_CONTENT_EXE` and `MMX6_CONTENT_DISC`
to the pinned read-only originals for the Python tests. The additional tests
cover actual native branch decoding/table/placement reconstruction, resident
guard drift, changed target/offset/mode/speed, missing guards, partial input,
wrong tuple/region, different native-Y results, and preserved non-camera
readiness failures. Synthetic positives test the rule only. No title build,
game launch, ledger pass or checkpoint predicate adjustment beyond this exact
source-derived dynamic path is evidence from this change.

Validation of this source/predicate change: all27 tests in
`python -m unittest discover -s tools -p test_mmx6_coop_checkpoint.py` pass with
both original-input environment variables set; source-audit CLI reproduction
and `git diff --check` pass. Native dynamic-policy validation remains unverified
until an owned fresh target/current-bound trace, new full-camera readiness
sample and completed composed capture are retained and reviewed.

## Native placement admission and target-writer corroboration

Root's healthy target retry is retained at
`G:/Temp/Codex/psxrecomp/x6-parity/checkpoint-v12-e2e47e6-intro-cp1-camera-target-trace-retry/qualification.json`,
SHA256`e45f9c23009c6738cd5e44bb4c061247a64505b9067d593cdb732328cb3f6d97`.
The whole narrow trace has total/available2009, with2006 address-filtered
entries emitted and no ring loss. Target halfword`80097222` changes0→944
at sequence13/native PC`80029C70`, then944→896 at sequence15/native
PC`800521F4`, frame2778, width2, A0=CAM, A1=PLAYER, A2=`80079D70`,
RA=`80052130`. This corroborates the authored dynamic-region writer. The
case still failed readiness and exited normally0; it produced no qualified
capture or ledger pass.

The failure was an intentionally strict resident placement check: the source
record at`800FA25C` has flags0, while the live record's full8-byte SHA was
`109e11f1f90c33a56affb92787293bf8a682ec5005fed673a882b9d3df118f72`.
The primary native placement scanner explains this mutation exactly:

| Original PC | Native operation |
| --- | --- |
| `8002A014..8002A018` | Skip records whose existing flags have bit0 or bit7 set (`flags &81`). |
| `8002A13C..8002A150` | Allocate the instance by the record's category; allocation failure skips admission. |
| `8002A158..8002A184` | Copy type/subtype and XY, and bind instance+10 to the exact original placement record. |
| `8002A254..8002A264` | Load record.flags, OR1, then store that byte back to the record. |
| `8002A188..8002A198` | Category3 skips the following category<3 resource initialization. The later offscreen category mutation also applies only to categories<3. |
| `8002A37C..8002A38C` | Fresh-stage placement reset keeps category low nibble and flags`&70`; this record's source flags therefore reset to0. |

The complete original scanner`80029F38..8002A33C` SHA256 is
`4cc5c282ba6f2a26f531dd282c241da0eab842c45d20653424c3e67fdba80de1`.
Applying only that documented admission OR1 to the original category3/type0/
subtype7 record derives the exact observed full8-byte SHA above. Bytes1..7
remain pinned to the source. The helper accepts only two exact whole-record
identities: original flags0, or native admitted flags1. It does not accept a
general flag mask, bit7, arbitrary type/subtype/category/position mutations,
or an unguarded code/table closure. Resident checks additionally pin the
original OR/store block and native reset routine. The full scanner hash and
mutation PCs are reproduced in `--camera-audit` source metadata; the scanner's
unrelated widescreen-bias sites need not be assumed immutable for this guard.

The extended actual-source test exercises all256 possible live flag bytes,
accepting only0/1, then independently corrupts each other record byte. It also
decodes the original OR1/SB/reset instructions and proves the admitted record
enables only the same exact dynamic-camera predicate; omitted writer guards
or forged hashes fail. The source audit and27 tests pass without a game.
Current-build native readiness and final composition still require a fresh
owned run; this source-derived guard correction does not convert the retained
failed setup into a pass.


## North Pole authored ice prerequisite

Title45/profile28 adds default-off `northpole_ice_cp3` for F111/F112. Both peers
agree before boot. Original stage2/0 checkpoint3 and both native grounded
arrivals precede one position/previous-position-only placement to X5016/Y1594
and X5120/Y1593. Original DAT96/layout, full22-pixel floors at1616 (code3C),
48-pixel air envelopes, body boxes, camera bounds and nearby actor absence are
guarded. Native camera/scanner and producer must reach their ordinary unarmed
phase8; both heroes must settle before readiness. No actor, phase, spawn,
camera, health or outcome is manufactured. This setup bypasses reachability
and taints recording qualification. Source/fixture tests establish no gameplay pass.

The product hooks extend original producer ED150's hero-position leaf to an
eligible guest and add only the missed guest contact after canonical child12
BF18 executes once. They retain native RNG, child allocation, attack ownership,
AI and lifetime. Guest contact history resets on allocator2BFD0 reuse.
Native early underside contact uses the original copied-body ground test and
parent-count/free tail. Top contact alone cannot force retirement.

Original North Pole actor F04B0 closes three tiles behind the approach when
canonical X>=4833/Y>=1217. After placement only, accept the original full
metatile bank or the exact full bank with source-table halfwords09C3/09C4/092E
copied to9448/944A/944C (world4672/4688/4704,Y1056). Guard original writer
and table as well. Partial copies, other collision changes, and the changed
bank before placement are refused; layout/descriptors and setup ground/air
remain exact. Two strict failed V100 setup runs retained this native change;
accepting arbitrary graphic/collision differences would be incorrect.

The nearby original Reploid22 (5096,1600, originF608C) is accepted only in its
exact source-bound native idle state, variant1/box7891C/ground8/zero motion.
Its actual contact uses horizontal radius8 plus standing-player11. Both
current bodies must miss the strict19-pixel overlap; setup distances80/24
miss. GuestRight increases separation. No future Left/contact/rescue claim is
implied. Other nearby actors and altered Reploid state/geometry stay refused.


## Recycle fallen-primary approach (development only)

`recycle_fallen_cp2` (option12, nonce`4C524631`) reuses original4/0CP2/index23/record`80072444`. Genuine native initialization and both healthy grounded arrivals precede one disclosed position/history-only approach: primary(1312,1593), guest(1506,1593). Exact original terrain supplies a clear primary fall tube and the guest floor1616. Native camera maxY1424 makes its original fatal branch eligible at primaryY1688; the setup guards that original code and never writes death/lifecycle/HP or any portal/loading result. At least two native updates must show actual primary falling before setup completion. Native fatal, primaryFALLEN, surviving guest control, original portal admission/loading and correct arrival/recovery remain separate runtime outcomes. Starting-HP and earned-weapons prerequisites are incompatible and must be off. This option is off by default and absent from release catalogs. No source/unit/build result qualifies F106.

The mirrored `recycle_fallen_guest_cp2` (option13, nonce`4C524632`) swaps only the initial X positions: primary(1506,1593), guest(1312,1593). Its exact source/air/body checks, incompatible HP/equipment options and native-fall readiness mirror option12; native guest death and subsequent primary-led recovery are independently observed.

Native standing arrivals retain downward velocity from the original beam handoff: `8003D850..8003D8A8` writes `body+24=FFF80000`, and original idle `8003AD18..8003ADB4` does not clear it. Both fallen approaches admit signed standing VY in `[-0x80000,0]` while retaining the exact idle, ground, zero-horizontal-motion, source and geometry guards. Placement preserves the actual velocity. This range describes this native handoff; it is not the general gravity clamp. The first LOCAL attempt remains retained as a setup failure caused by the earlier zero-VY guard.


`secretlab2b_enemy_cp0` (option14, nonce`4C474531`, titlev47/profile30) selects original SecretLab2B18/0 CP0/index94/record`80072E40`. Both original healthy native arrivals precede one position/history-only bypass to X(560,121)/Zero(576,121). Source-authenticated native updates must settle them toY123/122 on full floor144, while preserving VX0 and retained beam VY[-8,0]. The original type2/sub1 enemy at800/112, origin`800F5CE0`, must remain unallocated with no matching active native slot both before placement and readiness. The source air corridor549..821 and floor144 are checked, including the original64px recess704..767/floor176. Actual guest admission, traversal over that recess, combat and art remain separate runtime checks. Starting-HP and earned-weapons options are incompatible. No camera/scanner/velocity/HP/lifecycle/actor/outcome state is installed by this prerequisite; it is off by default and absent from release catalogs.
