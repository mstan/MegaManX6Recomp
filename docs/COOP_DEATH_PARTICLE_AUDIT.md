# X6 death-particle source audit: R3/F4

This audit covers only the frozen R3 requirement (own death origin/color) and
F4 requirement (finite death emission during scene admission). Both local and
netplay remain **unverified**. No title build, game launch, native damage,
capture, plugin edit or coverage-ledger change was performed here.

[COOP_DEATH_PARTICLE_AUDIT.json](COOP_DEATH_PARTICLE_AUDIT.json) reproduces
committed X6 `d1263e0acc75ae33368b6110a07d95d23e2d0987`, preserving the exact
frozen definitions and their row SHA256s. Original EXE SHA256 is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`;
the PS-X payload is at file+800, base80010000, length7F000. The archive is
LBA211185,1665024 bytes, SHA256
`55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f`.
Selected members are Zero overlay1 (sector24,size22964,SHA256
`75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00`)
and intro overlay2 (sector36,size74784,SHA256
`d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`).
The particle driver below is shared original EXE code. No X4/X5 addresses,
counts, palette identities or passed results are used as X6 proof. No original
binary payload is bundled; only source identities, addresses and table metadata.

## Ordinary native death entry and producers

The source chain is native player update`80034DCC`, PLAYER+4 phase2 via
table`80073ABC[2]`→`8003CC78`, then PLAYER+5 through table`80073D20`:

| Subphase | Original routine | Bounded behavior |
| --- | --- | --- |
| 0 | `8003D8A8` | Native stop/pose setup; vehicle+ D5 branch can hide the body and use a short countdown. Ordinary branch freezes PLAY+12..1A, requests native pose21 and sets D7=8. |
| 1 | `8003D954` | Decrement D7; at zero clear freeze bytes, hide PLAYER+3, issue native group3 sounds10h/Eh, zero D6/D7 and call the emitter immediately. |
| 2 | `8003D9F8` | Original random/radial emitters, indexed by body-owned D6/D7. |
| 3 | `8003DACC` | Native post-burst countdown20; at zero set PLAYER.phase+4=3 and action+5=0. |

The ordinary emitter calls random constructor`8003DAF4` at`8003DA34` four
times whenever `(D7 &3)==0`. Each uses `RNG &1Fh |80h` as subtype. It calls
radial constructor`8003DB44` at`8003DA68` when D7=0; D6=2 also calls it
at`8003DA80` for group3. Each radial group attempts eight allocations, using
the actual32-byte angle table`80073D30`:

```text
group0:  0  4  8 12 16 20 24 28
group1:  2  6 10 14 18 22 26 30
group2:  1  5  9 13 17 21 25 29
group3:  3  7 11 15 19 23 27 31
```

Static accounting from the original immediates gives radial groups at emitter
invocations0,19,38, then subphase advance at39. Eleven random groups of four
and four radial groups of eight total **44 random +32 radial allocation
attempts**, over40 accepted emitter invocations. These are original X6 counts,
independently derived here. They are not wall-clock frames, successful live
slots or a measured60FPS workload. The immediate first call from subphase1
is included. Frozen/blocked calls and entering with altered counters are not
the same contract. The allocator can fail and other actors share the pool.
A large76-attempt burst alone does not establish F4's excessive-burst failure.

The two constructors call allocator`8002C530` at`8003DB04/8003DB84`; their
return addresses are`8003DB0C/8003DB8C`. Successful slots receive flags21h,
type11h, supplied subtype, and zero phase/action/subaction. The allocator scans
`800CD410..800CF810`,96 slots of stride60h; it returns a zeroed free slot or0.
Do not count all global allocations as deaths or count replacement-wrapper and
original-call trace entries as separate attempts.

## Native pool update, glyphs and retirement

Intro FX root`8006E004` points to overlay table`800FA814`; type11h slot
`800FA858` points to`80047F78`. That routine initializes phase0 with
`80047E34`, otherwise updates with`80047FB8`. Other stages must retain their
own observed handler identity; this selected intro table is not all-stage
qualification.

| Field/helper | Original contract |
| --- | --- |
| Effect+8/+C | Copy resident PLAYER fixed X/Y at initialization, not allocation (`80047E98..80047EB4`). |
| +14 | Copy resident PLAYER layer at`80047E54..80047E60`. No parent pointer is installed. |
| +30 | Original animation table`8007789C`. |
| +38 | Zero: this is static glyph art, not a compressed character-frame pointer. |
| +3C | Current SCRATCH+1C assembly plus its word at+4 (`80047E64..80047E94`). |
| +40/+42 | Native tile/page0 and CLUT7802h; the latter addresses16 colors at VRAM x32/y480. |
| +16/+15 | Native priority10h and facing0. |
| +20/+24 | Velocity from original angle helper`8002D3B4`. Random subtypes multiply both by8; radial scaling uses actual table`80077B20`=[1,3,2,3]. |
| Animation6 | Frames105..109, two-call duration entries and final stride−4. |
| Animation7 | Frames110..113, three-call duration entries and final stride−3. |

Both glyph animations loop; they are not lifetime timers. Motion helper
`8002D2B0` adds VX to X and subtracts VY from Y. Random particles first test
`8002CBFC` against original320×240 camera bounds with8px padding; outside
returns1, and`80047FF0` calls`8002C9B0` to clear allocation/visibility.
Otherwise the native update advances animation/motion and calls`8002CCB0`,
which recalculates visible+3 against the actor's layer camera and native
display width (and240 height), again with8px padding. Radial particles have
no explicit deallocation branch in this update: allocated-but-invisible radial
slots can persist until another native reset. This is source-proven original
behavior, not by itself a leak. Actual motion, camera follow and source bounds
must be retained before claiming a finite observed lifetime.

Global update`800206C0` visits allocated slots once per native pool pass and
dispatches type through scratchpad+90. PLAY+17 freeze can suppress the real
update; its fallback visibility helper is not equivalent to particle aging.
Normal native controller`80020C40` calls the global update at`80020C98`.
World renderer`80022960` visits this same shared pool: visible1 dispatches
`800232D4` at`80022D30`, and visible2 uses`800239CC` at`80022D48`.
Death initialization and visibility helpers use0/1; the visible2 path is a
generic pool alternative, not a second death draw.

## Current co-op ownership and unresolved resource proof

`death_effect_allocate()` wraps`8002C530` once and invalidates any prior
receipt for the returned slot. For the two exact death return addresses it
captures current PLAYER X/Y/layer and SCRATCH+1C assembly in96 host records.
`death_effect_init()` wraps`80047E34`: a matching valid slot consumes that
receipt once, temporarily projects only origin/layer/assembly, calls the
original initializer once and restores those fields. This is the source-backed
adapter for initialization occurring after a private player projection ends.
Pending records already participate in host snapshot/digest. No new state is
introduced by this audit. Registered callbacks and source functions still need
actual hook/call receipts to establish runtime execution.

Private body/shot/contact/attached/trail updates do not add a second global
`800206C0` pass. Survivor/scene ownership uses one original native world pass;
the manual X death continuation calls the player routine and restores shared
freeze/clocks before Zero owns that world pass. `mmx6_coop_fatal()` accepts a
living actor once, and native D6/D7 remain in each retained body. No repeated
emitter or doubled global update defect is proven by this bounded source audit.
F4 still needs an actual scene-owner fatal episode, allocation/update counts,
passenger recovery and world-progress observations.

The distinct unresolved resource path is concrete: global death-pool actors
are excluded from the private `render_survivor()` body/shot/trail/attached
admission filter, and the ordinary `render()` supplement handles PLAYER only.
Death particles therefore keep the original native glyph/VRAM/CLUT path; the
private retained compressed sprite-bank path does not cover them. The origin
adapter retains assembly but does not retain/upload a private glyph atlas or
palette. This is an **unverified resource gap**, not a demonstrated wrong-color
bug: CLUT7802h alone does not prove different X/Zero colors, nor whether the
required glyph pixels are already common. An original co-op-off Zero/X death
reference and actual atlas/CLUT/composed comparison must answer that question
before choosing a rendering fix. Do not manufacture gold/blue colors from X5
references or reuse its native palette offsets.

## Native checks and reproduction

Root's bounded checks should use actual native fatal entry with disclosed
position/protection/HP prerequisites, preserve original-input and candidate
identity, and never set success/clear/rescue flags. Separate X/P1 and Zero/P2
at distinct positions. Retain native body phase/action/D6/D7, constructor
return-address allocation attempts, every bound effect's original initialization
and assembly/layer/CLUT, actual global-update progress, visible/allocated expiry,
completed composed frames and surviving-player input/recovery. Include an actual
scene-owner fatal before release for F4. Capture original co-op-off Zero/X
particle art first. Local/netplay remain separate exact-candidate obligations;
normal60FPS performance is a separate measurement.

```powershell
python tools/audit_mmx6_death_particles.py --exe <original-SLUS_013.95> `
  --disc <original-raw-BIN> --check docs/COOP_DEATH_PARTICLE_AUDIT.json
```

Only the known bounded archive extent and selected member metadata are read;
there is no full-disc crawl. `--output` creates a new file exclusively and
refuses to clobber evidence. Set non-C TEMP/TMP/Python cache paths and
`MMX6_CONTENT_EXE`/`MMX6_CONTENT_DISC` for the focused Python tests. Seven
tests pass, including actual original EXE/archive and committed-source
reproduction, native control/call/table checks, counter-contract drift, complete
angle/schedule accounting, unchanged frozen scope, strict non-pass limits and
no-clobber behavior. Source CLI reproduction and whitespace checks pass. These
tests and code registration do not qualify native death, art or F4 cadence.
