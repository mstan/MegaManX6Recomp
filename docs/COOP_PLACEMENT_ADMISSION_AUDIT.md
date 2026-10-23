# X6 R13: leading-partner enemy placement admission

**R13 remains unverified locally and over netplay.** This source lane adds no
runtime hook, changes no ledger status, launches no game and touches no card.
[The metadata](COOP_PLACEMENT_ADMISSION_AUDIT.json) pins original EXE and overlay
hashes, 15 native routine ranges, a real checkpoint/record and exact instance
identity. It provides the bounded case for a separate native input run.

There is no demonstrated placement-admission defect to patch in X6's current
fixed shared-camera design. Its native placement scanner consumes the shared
camera, and the existing co-op camera target includes living P2's position.
That source relationship supports a testable P2 admission path; it is not a
mechanic pass. A separate native enemy AI targeting nuance is identified below.

## Frozen reference and X6 admission inputs

Frozen X4 `50593bca772b600de6911cbfecd40b0f08721147` uses
`mmx4_coop_split.c` blob `d2afe037a9feb3c96f5dc0b3c80dd8bbd56fe8d5` and
`mmx4_coop_views.c` blob `480f211919d1972b5cd1ed1555074a4f91aa3c2f`.
Its split views require scans for each eligible living hero, script-owner
filtering, a shared visited set and selective supplemental admission. The
principle is progressing-hero admission with one shared native actor lifetime.
Those two-view mechanics, X4 stage IDs and addresses are not X6 requirements.

X6's original USA v1.1 EXE SHA-256 is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
Native primary scanner `80029F38..8002A33B` selects its list from
`8007349C + signed(PLAY+0c)*8 + signed(PLAY+0d)*4`, with
`PLAY=800CCED0`. Eight-byte records terminate on byte 3 **equal to 0fh**.

| Input or state | Native meaning |
| --- | --- |
| `a0,a1,a2,a3` and caller stack `+10h` | Signed 16-bit left/right/top/bottom and direction `0..4`. Admission requires **strict** `left<x<right`, `top<y<bottom`. |
| Layer0 `800971F8+0a/+0e` | Current integer camera X/Y: `80097202`, `80097206`. |
| Layer0 `+16/+1a` | Previous integer camera X/Y: `8009720E`, `80097212`. |
| Record byte0 `&81h` | Active/permanently disabled records skip allocation. Byte0 `&70h` selects a signed authored scan offset from `800733B8`. |
| Record byte3 | Low nibble allocation/difficulty category; high nibble native admission/rearm latch. |
| `PLAY+68h` / `800CCF38` | Difficulty gate used by `80029E7C` for categories 0..2. Authored record25 has category0, avoiding a higher-difficulty-only setup. |
| `8007347C[category]` | Native allocation dispatch. Categories0,1,2 all select `8002BBF4`; other categories have different pools/constructors. |

Movement driver `80029D18` compares current against previous camera, not P1
position. Moving right scans `(C+336,C+368)` by `(Y-48,Y+288)` with direction1;
left scans `(C-48,C-16)`, down scans `(Y+256,Y+288)`, up scans `(Y-48,Y-16)`.
The other axis uses the complete native extended rectangle. Authored offsets
translate the corresponding axis according to direction. Initial producer
`8002A3E8` scans the full `(C-48,C+368)` by `(Y-48,Y+288)` with direction0.

Scanner `80029F38` calls original eligibility `80029E7C`, then allocator
`8002A3AC`. Only successful allocation sets instance fields and record byte0
bit0. Inactive category0..2 records outside the **closed** native retention
rectangle can advance latches `10/30/50 -> 20/40/60`; do not erase these flags
to manufacture admission. Category0..2 eligibility itself changes latch state,
so a flag change alone does not prove allocation or initialization.

The secondary list is separate: `8002A438..8002A468` selects root `80073554`
by the same stage/section, then calls `8002A4E4`. That producer walks every
secondary record and allocates it without a camera rectangle. It is not an
extra per-player scan and must not be invoked twice to simulate P2 admission.

## Existing shared camera and limits

At game source `ebf3b11`, `shared_camera` requires both heroes ALIVE, normal
resident player gameplay, no scene owner and no shared script locks.
`camera_target` temporarily substitutes the X/Zero coordinate midpoint when
calling native X target `80029598` or Y target `80029658`, then restores P1.
The native target routines read PLAYER integer coordinates at `800970AA/AE`
and camera dead-zone offsets `+30/+32` (X), `+2c/+2e` (Y). Native camera limits,
speed caps and script ownership continue to apply.

`constrain_player` caps horizontal separation at `7/8` of
`320 + 2*widescreen_margin`; it does not add an independent placement view.
During the ordinary two-living-hero pass, moving P2 can therefore move the
authoritative midpoint camera while P1 remains still. Survivor and scene-owner
passes use their projected native owner and update the shared world once.
No separate P2 world pass is needed for ordinary primary placement admission.
This argument is bounded to eligible shared gameplay; it does not qualify
vertical separation, locked cameras, scenes or every campaign controller.

The widescreen companion already supplements revealed side strips. Its
constructor filtering and bounds must be audited separately. Use **4:3 with
resolved margin zero** for the discriminator below: a positive margin could
admit the selected record during stationary initial supplemental scans.

## Concrete original checkpoint and initialized instance

Use original checkpoint `s00-a0-c00`, native record `80072108`: intro stage0,
section0, checkpoint0; P1 `(144,976)`, camera `(0,944)`.
Its initial strict rectangle is `(-48,368) x (896,1232)`.

Primary record index25 at **`800FA2DC`** is original category0, type1, subtype1,
flags0, position **`(416,1080)`**. Its X lies outside that initial rectangle.
It is an ordinary enemy allocation, with no unsupported semantic species name
assumed. The source is `ROCK_X6.BIN` member2, sector36, 74,784 bytes, loaded at
`800E9860`, SHA-256
`d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`.

| Instance evidence | Exact source |
| --- | --- |
| Pool | `8002BBF4` searches `[8008EF48,80090C88)` in `9ch` steps: **48 slots**. It clears all `9ch` bytes of the chosen free slot. |
| Authored identity | Scanner writes instance `+10h=800FA2DC`, `+1=1`, `+2=1`, integer X at `+0a`, Y at `+0e`, and `+0=41h`. Match live `+0!=0` **and** the origin pointer; a freed slot can retain stale fields. Never assume the first slot. |
| Native dispatch | Loader root `8006DC6C` selects intro handler table `800FA424`; type1 entry is `800EAFB0`. World loop `8002000C` visits the pool in `9ch` steps and dispatches type through `[1F800080]+type*4`. |
| Actual initialization | Type1 phase table `800FAB48`: phase0 `800EAFFC`, phase1 `800EAC8C`, phase2/3 `800EB10C`. Init writes HP `+5c=12` at `800EB014`; `+60=4`, `+61=0`; then `+4=1`, `+5=1`, `+6=0`, timer `+7c=1`. |
| Native interaction | Alive phase1 calls enemy-hit `80031474` at `800EAD20`, and player-contact `80030ECC` at `800EADC0`. Existing co-op replacements try P2 after a native P1 miss. A negative enemy-hit result enters phase2 at `800EADBC`. |

Byte `+3` may still be zero just after initialization; action routines set it
later. Do not reject a correctly initialized HP12 phase1 instance solely for
that byte. Position may settle through native terrain handling. Retain the
actual grounded observations instead of injecting a guessed ground Y.

There is a distinct source-backed AI limitation: subtype1 action1 helper
`800EB14C` compares enemy X against **resident native P1 X**, and changes
action `+5` to2 only within a strict 112-pixel horizontal distance. With P1 at
144 and this enemy at416, P2 proximity alone does not satisfy that predicate.
Facing and later action2 range checks also read the resident player. Successful
placement/HP initialization does not prove nearest-player AI. Do not invent
an action2 expectation for this bounded admission test or patch shared AI by
running the whole world a second time.

## Read-only observation procedure for the separate native run

1. Enter the original checkpoint normally, wait for real gameplay/co-op
   enrollment and release input. Require both heroes healthy/ALIVE, no scene,
   pause or locks, 4:3 margin0. Record candidate/build and accepted inputs.
2. Before moving P2, capture P1/P2 positions, current/previous camera, native
   stage/section/difficulty, the eight authored record bytes and all 48 slots.
   Require record25 inactive and no live origin-matching slot. If it already
   spawned, this case is failed setup; do not clear the latch or actor.
3. Hold P1 idle at144. Send only P2 Right through the normal accepted-input
   sampler, release after the record's region is reached. Log the moving shared
   camera and strict right-strip crossing. At camera X64, for example, the
   strip `(400,432)` contains416; the unchanged initial P1-only camera did not.
4. Require exactly one live origin-matching slot, then native phase1 and HP12
   initialization. Keep P1 stationary throughout; record bits or allocation
   alone do not satisfy this check. Do not demand native action2 from the
   known P1-based proximity gate.
5. Use P2 native attack/contact input while P1 remains idle. Bind HP/action
   trajectories to that same origin pointer and live slot, and correlate P2's
   actual native attack state/pool changes. A native HP decrease/death or actual
   player damage is interaction evidence; screenshots or fixture writes are not.
6. For netplay, repeat with accepted inputs on a fresh private pair, retain
   same-simulation-tick core/mod CRC evidence and origin-matched observations
   from both peers. Leave broader R13 scope open until both modes qualify.

The source world loop executes once per native stage pass, but this lane has
not qualified an independent runtime once-world tick counter. Publication
counts, timer deltas and screenshots alone cannot establish that property.
The historical HP12 enemy result cannot identify this record without the
origin pointer. No new implementation or implementation-mirroring tests are
added for this documentation-only finding.

Reproduce the checkpoint/record metadata with the existing
`inventory_mmx6_coop_content.py` original-source workflow. Verify the EXE and
member2 hashes above, then hash each exact range listed in the JSON (EXE file
offset `address-80010000h+800h`; overlay member offset `address-800E9860h`).
The original bytes were rechecked directly during this audit; no inherited
X4/X5 result or active worktree content was used as native evidence.
