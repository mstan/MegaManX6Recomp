# MMX6 view anchoring review

Status: owner gameplay validation pending. Branch `feat/widescreen-view-anchor`
on game `ea39946`; framework branch `feat/mmx6-view-anchor` at `20286bd9`
(based on `0baf7bb1`);
UI `2298545959c30cf74defd1b8153b7fdeb6b2daa1`. Nothing pushed.
Tracking: `beads-eio.1.5` and framework `beads-eio.3.146`.

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
