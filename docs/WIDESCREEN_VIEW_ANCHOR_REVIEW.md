# MMX6 view anchoring review

Status: owner accepted camera/background/dialogue anchoring; enemy visibility
follow-up awaits owner validation. Branch `feat/widescreen-view-anchor`
on game `ea39946`; framework branch `feat/mmx6-view-anchor` at `20286bd9`
(based on `0baf7bb1`);
UI `2298545959c30cf74defd1b8153b7fdeb6b2daa1`. Nothing pushed.
Tracking: `beads-eio.1.5`, follow-up `beads-eio.1.7`, framework `beads-eio.3.146`.

The Widescreen mod defaults its camera option to room-edge anchoring. The
centered option retains the prior widescreen behavior. Guest camera values are
only read. The framework keeps the mirror width budget separate from the
world origin, including separate coverage for independent parallax layers.

## Retail evidence (SLUS-01395 v1.1)

- `FUN_8002820C` clamps layer0 scroll X at `80097202` between the signed shorts
  `80097216` (minimum) and `80097214` (maximum). Layer active byte: `800971F8`.
  Sample once at BG renderer setup, after the clamp. Intermediate writes must
  not move the presentation origin.
- Layer structs start at `800971F8`, stride `54`. Independent background layers
  1 and 2 have signed parent selector `+52 < 0`, scroll X `+A`, and inclusive
  screen-index map bounds `+4D/+4E`. Foreground camera50 / far scroll12 produced
  the owner's 38-pixel background gap under a shared origin. Clamp each
  independent layer's origin to its map coverage and refill its matching span.
- Producer entry `800270D0` and following setup `80026ECC` bracket each BG
  layer's packets; `a0` is the layer index and scratchpad `1F800108` its cursor.
- Object producers `800232D4/800239CC` use a signed camera selector at object
  `+14`; `80023ED8/800241D4` use `+37`. A negative selector means screen-space.
  `a0` is the object. Packet cursor `1F800100`, slot stride `28`. Final driver
  setup `80022E44` flushes the last producer. Tag screen-space packet spans with
  explicit center anchor zero. Alia text, portraits and box share this rule.
  OT rank 26 and the object packet arena also contain world props, so neither
  is a valid UI classifier by itself.

## Verification and review build

- Release build regenerated with the current compiler; both BIOS variants
  regenerated. Review executable: `build-anchor-next/mmx6-runtime.exe`.
- Private headless runtime on port4491, separate saves: actual 426x240 16:9.
  `_triage/anchor/headless/dialogue-fixed.png` shows the centered dialogue group.
  `backdrop-walk-0.png` through `backdrop-walk-5.png` show full background
  coverage from the left boundary into centered scrolling, with stable HUD.
- Four framework CTests pass: geometry/SW pixel identity, per-layer GPU
  coverage/sample stability, and the existing two HUD regressions.
- Two game CTests pass: object-producer UI/world classification and preloaded
  mod catalog. All four retail producer families are covered.
- Hidden real OpenGL context (RTX 3080 Ti): 87 checks pass at both 1x and 4x,
  including world origins, fixed dialogue center, both frame edges and the
  existing readback suite. The test also exposed missing flat-batch drainage
  before wide readback; readback now flushes both batch types.
- Vulkan compiles; real gameplay/backend validation remains with the owner.
  Real right-edge and narrow-room traversal have not been playtested; their
  geometry and clipping are covered by executable tests.

The owner's earlier run used `build-anchor` on port4490. Do not send owner
runs input, load states, stop or replace them. The review shortcut starts a fresh 16:9 run
on port4492 with separate `saves-anchor-review` storage; it loads no savestate.
The owner chooses when to switch and provides the final gameplay verdict.

The shared `game.toml` was held unchanged until read-only process inspection
confirmed the owner had closed the old run. The seven function-entry hooks
are now in tracked `game.toml`; normal `generated` is regenerated from it.
The separately built review uses the equivalent `game.anchor-next.toml` and
`generated-next`. Neither generated output, retail assets, evidence captures,
saves nor the local review shortcut belong in commits.

## Enemy cutoff follow-up (beads-eio.1.7)

The owner's next playtest showed an intro-stage robot disappearing while part
of it still occupied the left reveal. A read-only RAM capture found camera
X1092 and actor X1024. Private function tracing identified its actual calls:
`800EADD0 -> 8002CBFC` (lifetime check, horizontal radius64) and
`800EADE4 -> 8002CCB0` (draw visibility, horizontal radius32). The old
`801F2094` overlay-specific deactivation fix does not cover this actor path.

Retail `8002CBFC` returns outside the native 320-pixel rectangle;
`8002CCB0` writes object byte `+3` to control draw submission. Both copy `a1`
as horizontal radius and use `a2` independently for vertical bounds. New
function-entry callbacks add the constant widescreen margin to `a1` in both
classifiers, for world objects only (`object+14 >= 0`). Negative-selector UI,
vertical extents and margin-zero 4:3 calls are unchanged. The hooks apply to
both centered and edge-anchored widescreen and are absent when the mod is off.
Generated/interpreted function-entry paths share the existing plugin contract.

Private before/after evidence in `_triage/anchor/enemy-pop`:

| Native camera X | Previous build | Fixed build |
|---|---|---|
| 1062–1068 | Actor alive, draw flag0 despite visible overlap | Draw flag1; visible sprite portion retained |
| 1093–1097 | Actor removed | Actor retained; remaining sprite clipped naturally at frame edge |
| 1165–1171 | Actor removed | Retained outside frame inside the guard region |
| 1236–1246 | Actor removed | Actor removed after leaving the guard region |

The reverse-direction check at camera658 also shows the robot drawing across
the right reveal edge. The game regression exercises both callbacks with
4:3/centered/anchored margins and world/UI selectors; it verifies that only
the horizontal argument changes, with no object-memory writes. This is
engineering verification. The owner subsequently validated the launched 16:9
build: "definitely fixed." The separate spawn follow-up below remains pending.

Review executable: `build-anchor-enemies/mmx6-runtime.exe`, built from
`generated-enemies` and the equivalent `game.enemies-review.toml`. The prior
owner run/config (`build-anchor-next`, `game.anchor-next.toml`, port4492)
remain untouched. Ask when the owner is ready to switch; never inject input
or load a state into their runtime. Private evidence used private save slots.

## Spawn activation follow-up (beads-eio.1.8)

The retail placement driver `80029D18` scans camera-relative strips: right
X+336..368, left X-48..-16, with full X bounds for vertical movement.
`8002A3E8` performs the initial full scan. Shared scanner `80029F38` also uses
an independent X-48..368 interval when advancing respawn latches. Widening
only the scanner arguments would leave this second interval inconsistent.

Ten configured ADDIU sites now expand the outer horizontal strip edges, both
X edges of initial/vertical scans, and both respawn-reset edges by the same
constant activation margin (138 pixels for 16:9 edge anchoring). Inner strip
edges remain native to retain scan coverage across jumps and reversals.
Placement offsets, active flags, difficulty/respawn rules and vertical bounds
execute the original instructions. The guest camera is read, never changed.

The framework adds the opt-in `widescreen.cull.bias_lower_sites` counterpart
to positive bias sites, including native/dirty-RAM parity and cache identity.
Both bias forms preserve native PGXP source capture and ALU shadow updates;
the original early-return emitter had skipped those even with margin zero.

Private write traces in `_triage/anchor/spawn` correlate the actual spawn
write at `8002A178` with camera writes, ordered by sequence number:

| Placement X | Previous spawn camera X | Updated spawn camera X |
|---|---:|---:|
| 560 | 194 | 58 |
| 608 | 244 | 103 |
| 800 | 436 | 297 |
| 1024 | 657 | 519 |

Returning left, the X608 and X416 robots spawn at camera790 and601,
respectively, approximately 130 pixels outside the visible left edge. Each
placement spawned once in that measured return pass. Screenshots accompany
both traversals; `baseline-spawns.json`, `fixed-spawns.json`, `reverse-spawns.json`
and their filtered traces retain the measurements. This is intro-stage
engineering evidence; other stages and the final gameplay verdict need the owner.

Validation: compiler parser/emission/cache tests pass, as do executable
ADDI/ADDIU checks for both endpoints, margin-zero identity, unrelated sites,
register preservation, and the GPU site registry. The existing game hook
regression passes. Zero dispatch misses occurred during private traversal;
native overlay dispatch was active. Comparing all 32 generated game shards
against the accepted enemy build finds exactly ten changed X-bound expressions:
setting the new margin terms to zero reproduces every original shard byte,
including PGXP instrumentation. Generated output is never hand-edited.

The compiler hash change makes older private checkpoints incompatible; a
fresh boot and new private checkpoints were used, with completion receipts
checked before input. The review boots normally with no state loading:
`build-anchor-spawns/mmx6-runtime.exe`, `game.spawns-review.toml`, port4494,
`saves-spawn-review`, widescreen mod enabled at fixed 16:9, camera `edges`.
The owner decides when to launch and performs final validation.

Spawn framework pin: `33e3ed78` on `feat/mmx6-view-anchor`; UI remains at
`2298545959c30cf74defd1b8153b7fdeb6b2daa1`. Review executable SHA256:
`69CE7489B6A31C4603F7C468A72D3F5ADEF234CF2FF45F50F8E6C2C4764C87A6`.

## Owner acceptance and local master integration

The owner accepted the final 16:9 spawn review ("this looks good enough for
now") and requested local-master integration before moving to Mega Man Zero.
The feature commits are `98b8f80`, `230f094` and `bc00025`. Framework master
now contains them through `8c53cb0ba704678670937c9485beac6762ebb06a`, preserving
its prior production history guards; the game pin follows that merge.

The game merge preserves master's existing frame-blending changes. The
obsolete second catalog copier was dropped because current shared staging
already handles both runtime variants. Merged game hook/catalog tests pass;
merged framework GPU geometry, activation, GP0 history, memory trace and
audio history checks pass. The older history fixtures were updated for the
new view API and current kernel patch-table dependency. Nothing was pushed
or released; the owner-approved review executable remains available.
