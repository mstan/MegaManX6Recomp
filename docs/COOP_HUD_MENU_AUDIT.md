# X6 HUD/menu presentation source audit

Scope is exactly frozen comparisons R5, R6 and F18. All local/netplay/rendered
results remain **unverified**. This audit launched no game and built no title.
The machine record is [COOP_HUD_MENU_AUDIT.json](COOP_HUD_MENU_AUDIT.json),
reproduced from committed X6 `7b584a8b3c92fdf5c1d55471264098e6d5335385`,
frozen X4 `50593bca772b600de6911cbfecd40b0f08721147` and the original
SLUS_013.95 EXE SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
It records complete file identities, function-locator hashes, original bounded
code/data hashes and directly decoded MIPS JAL PCs. No original disc bytes
are committed. X4/X5 passes do not transfer to X6.

| Comparison | Exact frozen requirement | Bounded source finding |
| --- | --- | --- |
| R5 | P2 HUD anchoring matches P1. | Both use a native left column. P2 retained GT3 triangles and native G4 bars are explicitly tagged anchor−1. Native P1/boss packets are classified by the configured native HUD packet range. Actual final-window/aspect equivalence remains unverified. |
| R6 | Stacked default HUD with side-by-side option. | Baseline X6 translates P2 by X0/Y104 unconditionally. Its owning package has zero options and the plugin does not read `hud_layout`. The elective alternative is missing at this frozen commit. This is a missing implementation, not an inapplicable native absence. |
| F18 | P2 character and HUD pop out/in during pause transitions. | Both menu owners must be captured through actual native world draws and menu-only intervals. Source predicts an omitted living P1 in P2-owned world draws; it does not establish an actual rendered failure. |

## Native drawing and ownership

The original `80022960` world renderer initializes HUD packet cursors, calls
`800244C0` at `80022A28` when the original display gate at `80097428` is zero,
then dispatches the visible resident PLAYER at `80022AC8` to `800232D4`.
The native player-visible byte is PLAYER+3. HUD visibility is separately
controlled by PLAY+1F at `800244E4..800244EC`.

Original HUD `800244C0` calls health draw `80024F90` once, chooses X weapon
HUD `800246B4` or Zero `800249D4` by PLAYER+2, then retains its original
boss/other native meter work. X6's replacement calls that original top-level
path exactly once for X/P1 and the boss, then calls only `80024F90` and
`800249D4` for projected private Zero/P2. Resource projection selects Zero's
native body, assembly and UI assembly; it restores original PLAYER and scratch
pointers afterward, including when the native world is already Zero-owned.
This is the fixed X/P1+Zero/P2 roster; no opposite-roster support is inferred.

Native health takes PLAYER+5C masked with7F (`80024FB8..80024FC4`), and
maximum HP from PLAY+5B+PLAYER.character (`80024FD0..80024FDC`). The coordinate
table `80071E40` contains player X22/Y80 and boss X288/Y19. Native health bars
use those native coordinates and preserve the native low-HP/flash behavior.
Zero's selected weapon is PLAYER+93 (`800249F8`); nonzero selects a signed
halfword at PLAYER+A8+2*weapon (`80024A74..80024A7C`), with native capacity
at PLAYER+14A and weapon-unit conversion via `8003EB0C`.
Shared life digits use PLAY+39. The private `hud_icon()` suppresses only
native icon calls3/4 for P2, avoiding duplicate shared-life digits while
retaining original frames/weapon icons.

P2 sprites retain original16×16 UI pixels, current CLUT and page/UV identity
in host banks; frames use the current shared native UI palette, and private
weapon icons use the retained Zero menu palette. They become two retained GT3
triangles per native sprite. Native G4 bar packets preserve shape/color and
receive the same Y104 translation. Both packet kinds are explicitly tagged
as left HUD primitives. `game.toml` independently bounds native HUD anchoring
to half-open physical packet range `E3400..E4100`; scenery is excluded from
the broad heuristic. These source tags do not prove final-window composition,
portrait color, clipping or resize behavior.

The replacement's outer gates are enrolled, not failed and native major0A.
The private meter draw additionally requires PLAY+1F and nonzero private fade.
LEAVING/ABSENT subtract8 toward0; every other lifecycle adds8 toward128 **per
HUD callback**, not per proven simulation frame. Dead players retain meters.
The fade is not keyed to pause owner/phase and must not be mistaken for native
pause-fade brightness, which also reaches current palette values.

## Menu draw boundary and F18 prediction

PLAY+1 dispatches via native table `80071184`; phase2 is `8001EC40`, which
calls controller `8003CD44`, then native personal-menu dispatcher `80034830`.
That dispatcher uses MENU `800CF810`+4 and table `80073998`:
state0=`80034874`, state1=`800348B0`, state2=`8003499C`. There are further
native substate tables. The bounded window contains original world draw
`80025FB0` at `800349FC`, which calls background draw `80026D44` and world
renderer `80022960`; other paths call the distinct menu draw `80026028`.
This is a source locator, not a complete classification of every opening,
closing, Continue or Quit substate. Native Quit authority/work is owned by a
separate lane and is not changed or qualified here.

For P2 ownership, `stage_tick()` sets `inside=1`, projects Zero, routes the
native menu input/resources and executes the one original stage/world pass
under `zero_world=1`. During such a pass `render()` refuses its supplemental
P2 projection because `inside` is set. `render_survivor()` replaces the native
PLAYER draw and draws the projected Zero. It additionally draws stored P1
only when P1 is DYING or `scene_passenger(0)`, and P1's native visible byte
is set. The ordinary living, non-passenger P1 is excluded from that condition.
Therefore source predicts a missing P1 **if that menu interval dispatches
the native world PLAYER**. Source cannot establish which completed frames
the user sees, nor authorize drawing a body on menu-only/frontend frames.

The frozen X4 implementation supplies the useful design distinction: preserve
both eligible bodies/pools on actual world dispatch; retain separate native
menu-only boundaries. Its elective unified HUD layout uses a second-group
offset while keeping the same left anchor; own-player local panes are a
different feature. No X4 native address is reused as an X6 address here.

## Bounded qualification still required

R5 requires actual completed composed captures after separate native HP/ammo
changes, including native4:3, expanded drawable and a resize. Retain actual
drawable size/margin, each body's HP/selected weapon/ammo and packet provenance
with the same exact candidate/settings. Each meter must retain its own art,
value and stable native corner relation. A screenshot without those ownership
observations cannot establish the R5 requirement.

R6 additionally requires the actual installed setting, stacked default and
side-by-side selection, separate native identities, shared-life digits once,
and final-window inspection for both layouts. Existing frozen source proves
the implementation gap; it does not qualify a future setting from compilation.

F18 requires both native menu owners, both opening/closing transitions, full
completed-frame coverage and actual world/body/HUD provenance. Whenever the
native world dispatches both eligible actors, both body/meter groups must be
retained. Menu-only intervals must keep their native suppression. Do not
infer that a capture ACK, progressing publication, PLAY.phase2 or a native
draw callback alone establishes the intended composed result. Reuse the
owned personal-menu input/lifecycle adapters; do not inject success flags or
duplicate the Quit lane. Local and netplay evidence remain separate.

Reproduce this immutable source audit:

```powershell
python tools/audit_mmx6_coop_hud.py --exe <original-SLUS_013.95> `
  --x4-repository <local-frozen-X4-repository> --check docs/COOP_HUD_MENU_AUDIT.json
```

`--output` initializes a new file exclusively and refuses to overwrite an
existing audit. `--check` is read-only. Set non-C TEMP/TMP/Python cache paths
and `MMX6_CONTENT_EXE`, `MMX6_X4_REPOSITORY` for the source tests. No mutable
coverage ledger or frozen comparison definition is modified by this workflow.

## Separate R6 presentation implementation

The follow-up implementation adds the owning `mmx6.local-coop` prototype's
`hud_layout` choice: **Stacked** defaults to the existing P2 translation0/104;
**Side by side** translates P2 by56/0. The56-pixel column separation is an
elective co-op layout choice, not an original single-player X6 setting. It
preserves the X6 native health/weapon group geometry and its left anchor.
Both original retained sprite triangles and every vertex of native G4 bars
receive the same translation. Frames, portraits, glyphs, HP/ammo values, CLUT
selection, fade modulation, shared-life suppression and P1/boss calls stay on
their existing paths. There is no local split-pane implementation implied.

The renderer reads the immutable committed package/feature option directly
with the existing portable SDK API. Missing, empty or unknown values keep
stacked. No new persistent simulation/host state, snapshot fields, guest input
path or live option mutation is introduced. The frozen source JSON continues
to describe the exact pre-implementation commit; it is deliberately not
rewritten to claim that the original audit already contained this setting.

`tests/test_mmx6_coop_hud.c` includes the actual plugin with isolated RAM and
bounded original native sprite/mode/G4 packet producers. It checks both
layouts, invalid/missing values, both DMA arenas, every translated bar vertex,
retained sprite geometry, original P1/boss once, private Zero ownership,
resident body/resource/pool restoration (including an already Zero-owned
world), CLUT content changes, fade colors, visibility gates, shared-life icon
suppression and malformed pool rejection. This is packet wiring evidence;
the fixture does not emulate original art, menus or final composition.

The fixture passes at C99/O2 under GCC15.2 and Clang22.1.8 in debug and
`PSX_NO_DEBUG_TOOLS` variants. The production plugin also compiles under both
compilers with the older a502 SDK headers. Clang reports the pre-existing
duplicate CPUState typedef warning in SDK headers. No title build/native
launch accompanied these checks. Root must register the new fixture (same
lifecycle/assets/SHA sources and section-GC flags as the private-effects
fixture), inspect the actual installed control, and run native local/netplay
composed validation before R6 can pass. R5 and F18 remain unverified.
