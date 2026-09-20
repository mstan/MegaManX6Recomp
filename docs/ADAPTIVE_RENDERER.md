# Adaptive Custom Renderer review

September 19, 2026. Local feature branches: `feat/mmx6-adaptive-renderer`
in the game and framework. Framework pin: `95a97795`. This is an experimental
review build, not a release or a completed whole-game compatibility claim.

## Player behavior

The mod remains off by default, with stock 4:3 presentation. Enable **Custom
Renderer** under Mods. **Fit to Window** follows live resizing without a
16:9, 21:9 or 32:9 ceiling. Fixed 16:9, 21:9 and 32:9 choices are also available.
Room-edge anchoring is the default; centered anchoring remains selectable.

The requested review targets are 32:9 and 64:9. The opening wreckage panorama
does not contain enough art to cover these widths. Its extra reveal now repeats
with mirrored edges, as selected by the owner, retaining pixel size and parallax.
Foreground terrain and actors retain their authored world positions.

## Implementation

- Native background producers retain their 21-column loops, 64-column rings
  and 1000-packet budget. The host reads extra 16px tiles directly from the
  current map/metatiles/descriptors and appends them to the original texture
  bucket lists. Tiles beyond 1024px cannot alias the guest ring.
- A checked 6MiB enhancement DMA arena provides a 1MiB slice per layer and
  guest display buffer. Each 32-byte packet contains the standard SPRT16,
  view shift/padding and signature/optional X-reflection flag. Pending packets
  preserve their own metadata across snapshot restores. Storage/coordinate
  bounds are checked; there is no fixed aspect-ratio cap.
- Explicit world roles permit signed 16-bit X for expanded terrain/actors.
  Ordinary hardware packets retain PS1 signed 11-bit coordinates. The four
  object producers classify UI by their signed camera selector; dialogue
  stays centered and HUD meters keep their existing edge anchoring.
- Background generations clear the revealed strips once per submission and
  draw band, including centered mode. Independent parallax layers retain
  their own scroll and map bounds. Finite rooms can have symmetric padding.
- Lifetime, draw, initial placement, moving placement and respawn bounds all
  use the live activation envelope. A stationary expansion invokes the retail
  placement scanner for newly exposed strips, preserving registers, load
  pipeline, stack arguments and charged hardware timing.
- The intro panorama profile recognizes stage/area zero and the live far
  layer's mode, base scroll and parent selector. It reflects the opening
  far strip at 640px and nearer wreckage at 1088px. This avoids looking into
  empty or unselected atlas cells. It does not change palettes or borrow art
  from another stage. Other scenes retain direct authored-map lookup.
- All changes are source-owned hooks/configuration. Generated game and BIOS
  code were regenerated with matching tools and were not hand-edited.

## Validation

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
`cg13_2fd4824f_gcc5a1db89_f0`.

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

Updated executable: `build-review/review-next/mmx6-runtime.exe`.
SHA256: `18862B70C82259AAE596AE5D4544DD6F63A136CFE83D3D12065CEC735C738B8E`.
Use `build-review/review-next/Play MMX6 Adaptive.lnk` for the isolated owner
review configuration: enabled Custom Renderer, Fit, room edges, port 4512
and separate review memory cards. It boots normally and does not load a state.
Resize the window to the desired aspect; 64:9 is an extreme coverage check.

Captures and measurements are under `build-review/review-next/`:
`panorama-matrix.json`, `panorama-32x9.png`, `panorama-64x9.png`,
`panorama-after-motion.png`, `panorama-move-9.png`,
`interpreter-validation.json`, `stock-validation.json` and `stock-final.png`.
Original-disc AOT provenance is under `build-aot/disc-aot-5k_llucn/`.
These private artifacts and game assets are not committed.

## Remaining review scope

The reported intro gap is fixed and measured. The entire game, every narrow
room, boss arena, transition, respawn path and alternate character has not
been played through at these widths. Other finite panoramas may need their
own scene profiles. Mirrored wreckage is deliberately repetitive at 64:9;
it is not newly authored scenery. Vulkan has not received a gameplay review.
Keep the renderer experimental until broader owner review is complete.

Central tracking remains `beads-eio.1.9` (game) and `beads-eio.3.168`
(framework). Local updates are durable; central Dolt push encountered a
missing remote data ref. This source task did not alter the tracker remote.
