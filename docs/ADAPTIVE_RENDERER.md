# Adaptive Custom Renderer review

September 30, 2026. The framework integration is merged in
[psxrecomp PR #448](https://github.com/RetroPortingToolKit/psxrecomp/pull/448),
and the game pins master commit `93f2a709`. The renderer remains experimental
and off by default. Integration does not claim whole-game compatibility.

## Player behavior

The mod remains off by default, with stock 4:3 presentation. Enable **Custom
Renderer** under Mods. **Adaptive** follows live resizing without a
16:9, 21:9 or 32:9 ceiling. Fixed 16:9, 21:9 and 32:9 choices are also available.
Room-edge anchoring is the default; centered anchoring remains selectable.

The requested review targets are 32:9 and 64:9. The opening wreckage panorama
does not contain enough art to cover these widths. Its distant backdrop repeats
with mirrored edges, as selected by the owner, retaining pixel size and parallax.
Foreground terrain and actors retain their authored world positions.

## Implementation

- Native background producers retain their 21-column loops, 64-column rings
  and 1000-packet budget. The host reads 16px tiles directly from the current
  map/metatiles/descriptors and replaces that layer's current texture bucket
  lists with a continuous expanded view, including the center. Tiles beyond
  1024px cannot alias the guest ring. The other display buffer remains intact.
- A checked 6MiB enhancement DMA arena provides a 1MiB slice per layer and
  guest display buffer. Each 32-byte packet contains the standard SPRT16,
  view shift/padding, optional retained bank ID and X-reflection flag. Pending packets
  preserve their own metadata across snapshot restores. Storage/coordinate
  bounds are checked; there is no fixed aspect-ratio cap.
- Explicit world roles permit signed 16-bit X for expanded terrain/actors.
  Ordinary hardware packets retain PS1 signed 11-bit coordinates. The four
  object producers classify UI by their signed camera selector; dialogue
  stays centered and HUD meters keep their existing edge anchoring.
- Background generations clear the revealed strips once per submission and
  draw band, including centered mode. Independent parallax layers retain
  their own scroll and map bounds. Finite rooms can have symmetric padding.
- Enemy lifetime, draw and respawn-reset bounds use the live activation
  envelope. Original placement strips remain unchanged. Each frame, separate
  supplemental strips invoke the retail scanner for ordinary enemies in the
  extra view, preserving registers, load pipeline, stack arguments and charged
  hardware timing. A scoped eligibility filter defers unaudited controllers
  and the intro boss to the original strips. Audited visible exceptions are
  resident type8 doors, intro type2 breakable blocks and the intro type8 NPC.
  Doors keep their native contact trigger. The NPC initializes/animates its
  sprite early; only the phase that takes control of X waits for its original
  placement rectangle. That guard also survives resizing back to 4:3.
- Doors and frozen actors use additional fixed-radius draw classifiers
  (`8002CB50`, `8002CD6C`). While widened, they delegate to the existing native
  parameterized classifier (`8002CCB0`) with their original 32x32 and 96x80
  radii, then apply the shared horizontal extension. Vertical bounds, live
  display width and screen-space UI retain their native behavior.
- Framework entry filters are opt-in; existing entry observers keep their
  callback contract. Generated code, native overlays and the interpreter honor
  handled returns consistently. Overlay ABI 24 rejects the old callback signature.
  Save/load operations defer while an entry callback retains host stack state;
  device and interrupt timing continue normally.
- The intro panorama profile recognizes stage/area zero and the live far
  layer's mode, base scroll and parent selector. It reflects the opening
  far strip at 640px. The near layer stays in authored order: wreckage gives
  way to factory machinery at x=1088. The foreground's texture ownership
  changes inside the shared pillar at x=2048. Both intro texture sets are
  retained from the mounted disc's ROCK_X6.DAT record 94, with active sector
  mods applied. Type 0x10000 uses page-major upload layout; type 0x16 uses
  row-major layout. Live guest CLUTs preserve fades/colour animation. Banks
  are reconstructed on demand after loading a save in a fresh process.
- Intro camera locks inside the continuous exterior/factory scene no longer
  redefine its visible edges. The renderer reads the original foreground map
  bounds (x=0..6656, maximum camera X=6336) while that parallax setup is active.
  Near and far layers map the host camera's left edge through their native
  half-speed and quarter-speed scroll, including rounding phase. This avoids
  excess motion and one-pixel crawling at a clamped view edge. Native camera
  state is unchanged; other rooms retain their normal anchoring.
- Framework `04c6dc38` caches loaded-DLL path membership per indexed artifact
  until the append-only loaded set grows. This removes repeated long path
  comparisons during lazy overlay discovery, preserving all live-byte and
  manifest checks, candidate ordering and interpreter fallback.
- All changes are source-owned hooks/configuration. Generated game and BIOS
  code were regenerated with matching tools and were not hand-edited.

## Validation

### Roaming stage-select, rain and narrow-room fixes

Latest owner UI slots 1–5 are copied under `build-review/stage-fixes/`.
The interactive roaming process and memory cards were left untouched during
testing; port 4520, a separate settings file, copied cards and copied states
were used by hidden test processes.

- Stage select uses native 4:3 presentation. Retail main state `800CCED0=0A`
  selects gameplay; the stage-select carousel (`0404`) no longer exposes its
  neighboring menu pages. Development and packaged configs agree, including
  the native placement-strip sites fixed in the previous review.
- Recurring ring initialization cleared both framebuffer bands. With a host
  tile arena, cleanup now waits for that backbuffer's first draw. Turtloid's
  exterior and the museum edge no longer alternate between art and black.
  Before/after frame sequences reproduce the fault and its correction; museum
  edge pixels stayed present in all 15 captures at both 32:9 and 64:9.
- Turtloid's layer1/mode5 is a 320px weather-frame atlas, not world scenery.
  Only its selected frame repeats across the visible room, so blank weather
  frames cannot expose neighboring inactive rain. Its five texture frames
  are retained from the stage's guest VRAM upload for immutable-bank batching;
  row animation, live CLUT fades, semi-transparency and OT order remain native.
  A fresh-process snapshot can rebuild bank `6003` from restored VRAM.
- Stage6 enemy type0A water pursuers keep native activation, lifetime and
  respawn-reset bounds. Type0E rain-generator encounters also keep native
  activation/reset/lifetime bounds: starting a later generator early overwrote
  the shared weather index at `800F6BA0`, disabling rain in the current room.
  Draw bounds remain expanded for actors that have legitimately activated.
- Replaying the approach from owner UI3 reaches the first generator room with
  rain flag `800CCEF6=1`, generator index 0, and animated rain across the view.
  **Old UI4 already contains two initialized generators and the wrong shared
  index.** That saved guest state is preserved, not silently rewritten. Replay
  from UI3 or re-enter the stage to test rain. Private UI6 records the normal
  approach (test-only HP healing); it is not installed over an owner slot.

Seven CTest cases and release-config parity pass. The rain optimization moved
the two-second 64:9 slot3 check from about 19 to 60 submitted frames/second;
the active-rain room also reached 60. These are local paced measurements,
not an isolated GPU benchmark. Short snapshot/capture sweeps include debugger
overhead. Original-disc AOT audit: 71 valid pairs, 21,342 manifest rows, 57
recipes, all guards verified; full static coverage is not claimed. Cache tag
remains `cg13_2caa7102_gc90252311_f0` because code generation did not change.
Evidence: `build-review/stage-fixes/final-matrix.json`, `rain-approach.json`,
before/after PNG sequences and `build-aot/stage-fixes/disc-aot-6ua71pvo/`.

### Latest prop visibility and NPC preview regression pass

The next owner review identified missing props in new UI slots 1/2 and a
disappearing boss door in new UI slot 4. The blanket nonenemy placement filter
also excluded harmless visible props. The door additionally used a fixed-radius
draw helper that had not been widened.

Native code was inspected from captured RAM for SLUS-01395 v1.1. The intro
breakable block is category4/type2 at placement `800FA374` (X=5488); its native
constructor/update handles ordinary damage and lifetime. Category4/type8 doors
at X=5744 and 6064 initialize their graphics separately and start transitions
only on player contact (`80050C88`). Category5/type8 at placement `800FA29C`
initializes its NPC graphics in `800F90FC`; phase0 at `800F9334` immediately
requests control of X. The new guard holds that phase outside the original
open scan rectangle, camera X-48..X+368 and Y-48..Y+288. Animation and draw
classification continue through the surrounding native update.

| Check | Result |
|---|---|
| New UI slots 1/2, 32:9 and 64:9 | Breakable block visible before entering native view |
| New UI slot 4, walk left | Door remains drawn in expanded view |
| Early NPC, wide and resize back to 4:3 | Sprite initialized; sequence stays at phase0; X remains controllable |
| Original 4:3 placement/draw | Block/NPC remain unspawned where the original scan has not reached |
| Same three saves, 32:9/64:9/4:3 | About 60 gameplay submissions/s (1.2s samples, 59.15-60.69 range) |
| Early-spawned block, normal saber attacks | Destroyed; X walks through to X=5516 |
| Normal approach from new UI4 at 64:9 | Door transition, NPC dialogue, second door and boss fight complete |
| NPC preview save/load | Three cycles and fresh-process restore pass without starting the sequence |

The separate no-native-overlay run also reproduced the corrected block/door
visibility and NPC deferral. Unit coverage includes allowed actor categories,
original-scan fallthrough, both fixed-radius helpers, UI/4:3 identity, native
trigger X/Y boundaries and a previously-previewed NPC after shrinking the view.
All seven game CTest cases pass. Original-disc AOT was rebuilt and audited:
71 valid pairs / 21,342 manifest rows, tag `cg13_2caa7102_gc90252311_f0`.

The owner process was left interactive throughout this investigation. Latest
save copies were backed up under `build-review/prop-fixes/original-saves`;
their bytes need no ABI/header migration for this build. Private combat checks
restored HP to avoid drill deaths; they used no warps or trigger-state patches.
Gameplay progress and diagnostic saves stay in the separate test directory.

### Earlier parallax and scene-trigger regression pass

The owner's subsequent slot 3 wall-climb reproduction isolated premature
activation: widened original placement strips spawned the NPC around X=5115
and put X into forced-walk state 0x1d before the climb. That sequence waits
for X>=5824, leaving X stranded on the earlier geometry. The same inputs
with native placement bounds climbed normally without activating the NPC.
The intro boss controller had the same early-activation exposure.

With separate filtered supplemental strips, normal injected controls completed
the wall climb, breakable barrier, NPC dialogue and boss entry in the proper
arena. HP was periodically restored in the private combat run to avoid drill
deaths; the route used no position warps or trigger patches. A native-overlay
fallback climb also reached X=5430 without premature NPC activation.

| Check | Result |
|---|---|
| UI slots 1, 3, 5 and recovered 6 at 32:9 | 59.85-59.89 gameplay submissions/s |
| Same four saves at 64:9 | 59.06-60.68 gameplay submissions/s |
| Same four saves at 4:3 | About 59.8 gameplay submissions/s |
| Foreground camera X=4322 to 4431 | Near scroll 2161 to 2215; far scroll 1080 to 1107 |
| Repeated load, move, save and reload | Six cycles passed with callback snapshot guards |
| Recovered slot 6, fresh process | Movement works; X=5130 to 5101 after left input |

Cadence samples are approximately 1.2 seconds, with one-frame boundary
variation. All seven game CTest cases pass. Function-filter registry execution,
overlay callback forwarding, interpreter entry guards, snapshot protocol guards
and all five overlay publication/dedup scenarios pass. The earlier GL readback
results below cover the unchanged retained-bank rendering implementation.

Private copies of the owner's latest UI slots 1-5 were migrated from codegen
`2fd4824f` / ABI 23 to `2caa7102` / ABI 24 after auditing that CPU, hardware and
arena snapshot layouts are identical. Only header bytes 16-23 changed; snapshot
payloads are byte-identical. `save-migration.json` records old/new and payload
hashes. Runtime compatibility guards remain intact. Original saves and an
additional backup remain unchanged.

Original slot 4 already serializes the faulty forced-walk sequence. The new
activation policy prevents that sequence starting early, but does not rewrite
an already-stuck snapshot. UI slot 6 is a recovered copy: cancel the premature
NPC with its native respawnable-delete effects, clear its forced-control flags
and return X to normal idle state. No health, camera or position fields were
patched in that recovery. The original slot 4 remains available for reproduction.
Slots 7-9 are private diagnostics, not the requested player review route.

### Earlier scene-artwork and performance regression pass

The first intro-only review missed a seam between native and mirrored tiles,
the factory's texture replacement, internal camera locks and a later runtime
hotspot. The following checks supersede that limited acceptance. Copies of
owner UI slots 1-5 (files/RPC slots 0-4) were used; the active owner process,
executable and original saves were left untouched.

| Check | Result |
|---|---|
| All five saves at 32:9 | 59.5-60.4 gameplay submissions/s |
| All five saves at 64:9 | 59.6-60.4 gameplay submissions/s |
| Slot 1, moving panorama edge | Continuous reflection across center and reveal; no black seam |
| Ladder descent | Native camera Y changes 896 to 944; horizontal view shift stays zero |
| Slot 2, walking into factory | Correct hanging bar/texture pages; stable horizontal origin through locks |
| Slot 5 | Before 50-52 FPS, after about 60; approach/input intervals also about 60 |
| New retained-bank save loaded in fresh process | Reconstructed banks, correct artwork; no forced compatibility |
| Interpreter fallback, native overlays disabled | 181 submissions / 182 vblanks in 3.07s at 64:9; 4.45M interpreted instructions |

Intervals are roughly two seconds per save/aspect and 3.5-6.6 seconds for
movement; boundary sampling can differ by one frame. This is gameplay
submission cadence, not just host presentation FPS. Disabling the additional
wide GPU pass did not fix the original slowdown. Private host instruction
sampling identified lazy overlay discovery/path comparison overhead; the
membership cache restored cadence without changing guest timing.

Seven CTest cases pass (six game cases plus staged mod catalog). GPU tests
cover bank metadata, ordinary packet isolation, stable scene bounds and a
pending wide OT during resize back to 4:3. GL readback passes 157 checks at
each of 1x and 4x, including live CLUT updates and switching the same bank
between retained/live palette modes. Real overlay publication/dedup tests
pass all five scenarios, including aliases, mismatched manifests/provenance,
cross-tier selection and partial exports. Release config parity passes.

The broader framework structural script `test_interpreter_perf_guards.py`
still fails its pre-existing `psx_devices_mmio_sync` inline-limit assertion;
both that test and `psx_cycles.c` are unchanged from the feature baseline.
This review does not claim that broader script passes.

### Earlier intro baseline

Windows, OpenGL, RTX 3080 Ti, internal scale 1x, ordinary 59.94Hz pacing.
Each interval below is approximately three seconds during the intro dialogue.
Game counts use the background submission counter independently of vblank.
The one-frame sampling difference at interval boundaries is expected.

| Fit aspect | Native view width | Game submissions | Vblanks | Game fps |
|---|---:|---:|---:|---:|
| 4:3 | 320 | 181 | 180 | 60.25 |
| 16:9 | 428 | 180 | 180 | 59.97 |
| 21:9 | 560 | 180 | 180 | 59.93 |
| 32:9 | 854 | 180 | 180 | 59.95 |
| 64:9 | 1706 | 181 | 180 | 60.22 |
| Resize back to 4:3 | 320 | 179 | 180 | 59.63 |

Full interpreter fallback (`PSX_FORCE_INTERP=1`, native overlay execution off)
produced 180 game submissions and 180 vblanks: 59.96fps at 64:9, with the same
filled panorama. Native execution logs include actual game-overlay calls.
Disabled-mod cold boot reached the intro at 320x240 with mode/margins zero;
a native producer trace measured 180 frames, 59.93fps. A mod-enabled snapshot
was correctly rejected by the disabled-mod run; no compatibility check was
bypassed. The stock test continued from a fresh boot.

Normal injected movement, jumping and shooting traversed from the wreckage
into the factory, reaching camera X=1813 without warping. HUD, dialogue,
enemy visibility and background coverage were visually inspected. Earlier
diagnostic warp captures are not evidence of normal stage progression.

Checks passed:

- All six game CTest cases, including background, hook/view and catalog tests;
  release/development config parity.
- Host packet bounds, texture buckets, reflection orientation, scene gates,
  native ring preservation and disabled 4:3 identity.
- GPU packet-role/coordinate tests and SW framing/pixel tests, including both
  stage edges and narrow rooms at 32:9, 64:9 and wider.
- Real GL readback suite: 147 checks at each of 1x and 4x, zero failures,
  including every texel of forward and reflected 16px strips.
- Recompiler patch and interpreter mod-entry guard regressions.

Raw frame-performance telemetry is retained locally, but its paced CPU/GPU
times are not an isolated renderer-cost benchmark. The measurements establish
game cadence, not a claimed CPU/GPU speedup. No clock or gameplay-speed
changes were introduced.

The original-disc AOT audit covers 56 extracted images, 57 recipes, 71 valid
published pairs and 21,342 manifest rows. All guards match known input bytes;
`full_static_coverage_proven` remains false. Cache tag:
`cg13_2fd4824f_gcc5a1db89_f0` for that earlier build. The latest build repeats
the original-disc audit with the same coverage counts under
`cg13_2caa7102_gc961830ce_f0`; all published pairs and guards validate.

## Local review artifacts and worktrees

Game worktree: `F:/Projects/psxrecomp/_wt-mmx6-adaptive-20260919`.
Framework worktree: `F:/Projects/psxrecomp/_wt-mmx6-adaptive-fw-20260919`.
The game's `psxrecomp-v4` is a real detached Git worktree at the same framework
commit, not a junction. The build explicitly uses the framework feature
worktree through `PSXRECOMP_V4_ROOT`; `recomp-ui` stays pinned to `2298545`.

Existing original checkouts and their working changes were preserved. WIP
rescue refs include game `2d227b9`, framework `d94fd537`, nested runtime
`4660d044` and game master-pin state `b210715`. The framework feature base
`41e92d8a` merges current origin/master with the accepted local MMX6 changes.
No source was pushed, released or merged into master for this review.

Current executable: `build-review/playtest-6/mmx6-runtime.exe`.
SHA256: `B26F1143646727D2DB600DE99CB71314D445904A4B154213EDC7080F83C1728A`.
Use **MMX6 Adaptive** on the desktop or `F:/Projects/psxrecomp/Play MMX6 Adaptive.lnk`.
It opens recomp-ui with the current roaming memory-card copy, PS5 controller
settings and `game.adaptive-roaming-local.toml`. No state loads automatically.
The original non-worktree card and all owner slots remain preserved.

Previous prop executable: `build-review/playtest-4/mmx6-runtime.exe`.
SHA256: `849B04CF1D22F0A643B401F2EF03DAEFFB6AAE440E5DE04A57715947963043E4`.
Use the desktop **MMX6 Prop Fixes** shortcut, or
`F:/Projects/psxrecomp/Play MMX6 Prop Fixes.lnk`. It selects the isolated
`game.adaptive-prop-review-local.toml`: enabled Custom Renderer, Fit,
room edges, port 4519 and copies of the latest owner saves/memory cards under
`build-review/prop-fixes/test-saves`. Window title: **MMX6 Prop Review**.
It boots normally and does not load a state. Close the older review first.
For review, use latest slots 1/2 for the block, and slot 4 for door visibility
while walking left and the NPC/boss approach. Historical slot numbers above
refer to saves as they existed during each earlier review. The older
executables and shortcuts remain available and unchanged.
Resize the window to the desired aspect; 64:9 is an extreme coverage check.

Captures and measurements are under `build-review/review-next/`:
`panorama-matrix.json`, `panorama-32x9.png`, `panorama-64x9.png`,
`panorama-after-motion.png`, `panorama-move-9.png`,
`interpreter-validation.json`, `stock-validation.json` and `stock-final.png`.
Original-disc AOT provenance is under `build-aot/disc-aot-5k_llucn/`.
The new regression evidence is under `build-review/scene-fixes/`:
`aspects.json`, `motion.json`, `fixed2-slots.json`, `host-sample.json`,
`interp-restored.json`, `verified-64-slot1.png` through `verified-64-slot5.png`.
These private artifacts and game assets are not committed.

Earlier trigger evidence is under `build-review/trigger-fixes/`:
`final-validation.json`, `final-{32,64,43}-slot{1,3,5,6}.png`,
`parallax-motion.json`, `fallback-climb.png`, `trigger-ab.json`,
`proper-npc-16.png`, `npc-after-dialogue.png`, `proper-boss-19.png`,
`save-migration.json` and `slot4-recovery.json`. Original-disc AOT provenance
is under `build-aot/trigger-fixes/disc-aot-xphfq3me/`; the staged receipt is
`build-review/playtest-3/AOT_CACHE_AUDIT.json`.

Latest prop evidence is under `build-review/prop-fixes/`: `baseline.json`,
`interp-baseline.json`, `interp-left.json`, `native-aspects.json`,
`native-approach.json`, `native-dialogue.json`, `native-boss-route.json`,
`block-destruction.json`, `native-overlay-status.json`, corresponding PNGs
and the original RAM captures. Original-disc provenance is under
`build-aot/prop-fixes/disc-aot-tjhetrki/`; the staged audit receipt is
`build-review/playtest-4/AOT_CACHE_AUDIT.json`.

## September 20 effects review (playtest 6)

These slot numbers refer to the owner's new saves from September 20 at
11:31–11:36, preserved separately from all earlier reviews.

- UI2: Turtloid's Nightmare darkness uses category6/type5 screen polygons,
  subtypes 13/23/33/43. Their fixed outer edges were -96 and 416. A guarded
  framework tag extends those vertical edges with subtractive bands at the
  same ordering-table position. The moving light openings, fade strength,
  canonical framebuffer and HUD are preserved. Tags expire and reset on load.
- UI3: Amazon's layer2 jungle art ends at x896. Reflect that finite panorama
  and its individual tile pixels, using the foreground camera's half-speed
  projection. Near scenery and terrain still come from their original maps.
- UI4: X state4D's yellow attack uses six native screen sprites (effect
  type11/subtype2). A pure native-scene predicate temporarily presents this
  sequence at 4:3, then restores adaptive gameplay. Simulation and camera RAM
  are unchanged. The predicate is inactive when Custom Renderer is off.
- UI5: the first cave panorama occupies x768–1408 in the same distant-layer
  atlas. Reflect that panel rather than exposing its gutter/neighboring art.
  Apply the same half-speed projection, including room-edge padding. During
  a short leftward movement at 64:9, the clamped scenery crop remained pixel
  identical while the native camera moved from 1598 to 1595.

Validation: private copies of current cards/states, controller disconnected,
port 4520; 4:3, 32:9 and 64:9 captures; approximately 60 FPS in two-second Amazon
samples at both wide aspects; native attack and return to wide gameplay;
fresh-process darkness/attack/cave restore and native overlay dispatch;
stage-select remains pillarboxed; previous intro prop scene smoke check.
All seven game CTests and release-config parity pass. Framework mask geometry,
packet-reuse guards and production scene-classifier tests also pass.

Framework commit: `39ee7d79400e500eeb3ea26e3d2c35d889e9d5b5`.
Evidence: `build-review/effects-fixes/`, including `fixed-validation.json`,
`motion-validation.json`, `attack-duration.json`, `final-smoke.json` and PNGs.
Original-disc AOT provenance: `build-aot/effects-fixes/disc-aot-t8rqi8nz/`.
All 71 native pairs / 21342 manifest rows pass hash and original-byte guards;
tag `cg13_2caa7102_gc90252311_f0`, static coverage still not complete.
The first staging attempt encountered a DLL locked by the private test; after
closing it, the audited cache was staged and every artifact hash rechecked.
Current receipt: `build-review/playtest-6/AOT_CACHE_AUDIT.json`.

## Draft status and remaining work

PR #33 remains an experimental draft. The September 30 follow-up is on the
same `feat/mmx6-adaptive-renderer` branch:

- Game commit `c936396` keeps the Recycle Lab ride armor visible in the wide
  view and anchors its half-speed distant machinery so walking right does not
  expose a growing black strip on the left. The previously reported trash
  block remains visible. Owner playtest 7 and isolated OpenGL/software checks
  covered adaptive, 16:9, 21:9 and 32:9 views at the affected saves.
- Framework commit `ca14a118` grows the software-present staging buffer and
  texture for wide frames instead of relying on the original 640-pixel canvas.
  Game commit `60b34ca` pins that framework fix. This removes the buffer
  overflow behind the adaptive startup crash observed before playtest 7.
- The widescreen mod picker now defaults to Adaptive, followed by 16:9, 21:9
  and 32:9, without the old experimental labels.

The earlier owner results from playtest 6 are:

- UI2: the saved darkness section now fills the adaptive width. Continuing
  into the **next section with darkness and rain together** restores the old
  roughly 16:9-sized mask. The darkness fix is partial. Reproduce by advancing
  from slot 2 into that combined effect, then identify its producer/profile;
  the four polygons covered by the current fix are not sufficient evidence
  for every darkness variant.
- UI3: the main Amazon jungle panorama is fixed. A **lower row to the right**,
  barely visible in the expanded view, still has a black background. The owner
  accepts this as a rare out-of-bounds view; it is not a merge blocker.
- UI4: the special-attack presentation is confirmed good.
- UI5: the cave backdrop and scrolling correction are confirmed good.

Additional September 30 Amazon Forest saves 05, 06 and 07 reproduce at a
2048×521 adaptive window. The first two expose rectangular empty map regions
while X falls vertically. Slot 07 shows black on both sides of the cave,
although the native-wide renderer is active; it is not a 4:3 present. The
read-only map census found no layer-2 tiles through the relevant 512–768 Y
band, and only a short 880–944 Y strip in the later cave panel. These are
authored map limits that 4:3 usually hides. The owner explicitly accepts all
three as rare, suboptimal views and does not want them fixed or treated as
merge blockers. A cosmetic fill would need deeper scene work; repeating the
foreground map would imply platforms or walls where the game has none. The
pause menu still correctly uses native 4:3; it is unrelated to slot 07's
black sides.

The entire game, every narrow room, boss arena, transition, respawn path and
alternate character has not been played through at these widths. Other finite
panoramas may need their own scene profiles. Mirrored wreckage is deliberately
repetitive at 64:9; it is not newly authored scenery. Retained texture banks
currently require OpenGL; other renderers have not received the same
scene-residency review. Central tracking remains `beads-eio.1.9` (game) and
`beads-eio.3.168` (framework).

## Framework integration validation

The maintained framework pin combines the adaptive changes with current
segmented dispatch and active-plan mod hooks. Overlay ABI 25 preserves the
upstream store-PC pointer and adds handled function filters. Filters execute
only for enabled plugins; snapshots defer until their host callbacks return.
The matching reachable recomp-ui pin is `2991976`.

Windows validation passed 123 enabled compiler tests, the 126-case enabled
runtime suite (one existing platform skip), 27 UI tests, seven game tests and
release-config parity. Fresh original-disc AOT produced 71 audited native
pairs and 21,714 manifest rows with matching hashes and original-byte guards;
complete static coverage is not claimed. Clang Release builds and isolated
OpenGL/software restores covered all four aspect choices, Recycle Lab armor
and background, the first darkness section, the special attack and adaptive
recovery, stage select, intro snapshots, and fresh snapshot save/load.

The framework update changes cache and snapshot compatibility keys. Memory
cards are unchanged. Only private validation copies of compatible v7/v8 stage
snapshots were rekeyed; original user snapshots and normal runtime rejection
remain intact. Idle intro measurements were about 60 FPS and do not rule out
the enemy-triggered stutter in GitHub #32 or Ilumina phase-two slowdown in #31.
The combined darkness/rain mask remains a separate follow-up, `beads-eio.1.15`.
