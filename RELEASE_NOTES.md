# v1.3.0-alpha

This Windows x64 prerelease introduces experimental simultaneous X + Zero
co-op, locally or through delay-based netplay. The bundled co-op mod remains
Experimental 0.0.1 and is disabled by default for local play.

## Playing together

- For local play, enable **X + Zero Co-op** in Mods and assign P1 and P2 in the
  launcher. P1 controls X; P2 controls Zero. Release builds require distinct
  physical controllers; controller plus keyboard is supported.
- For netplay, use identical builds, the supported USA v1.1 disc, and OpenGL.
  Select your local input on the P1/Netplay controller card, then host or join
  through Netplay. Co-op is enabled automatically for both peers.
- Netplay offers fixed 4:3, 16:9, and 21:9 views. The wide views use the enhanced
  renderer, including extended scenery/enemy visibility and both native HUDs.
  The host chooses the view before the session; adaptive resizing is excluded.
- Players have separate health, weapons, and native character progression,
  with one shared life pool. A surviving player continues after their partner
  dies. P2 can hold Select for 1.5 seconds to leave and tap Select to return
  with retained health; death prevents rejoining until a stage/team respawn.
- Native door/dialogue handling, pause/Sub Tank ownership, collectible ownership,
  Reploid rescue, Zero arrival animations, and independent pit deaths are included.
  Zero is reserved for P2 and omitted from P1's unit-selection menu.

OpenBIOS is bundled and selected by default. Netplay skips the BIOS shell
animation. Standard memory-card saves remain supported; co-op uses isolated
save storage. This package contains no game disc, retail BIOS, or player saves.

## Validation and limitations

Local co-op has owner playtest coverage. Two private peers on one Windows PC
passed transported P1/P2 movement, P2 leave/rejoin health retention, enhanced
16:9 scenery/enemy visibility, and both native HUDs. All 373 shared checksum
checkpoints matched in the refreshed development build. This does not establish
Internet, separate-machine, rematch, or full-campaign reliability.

- Co-op requires OpenGL, a fresh boot, and rewind disabled. Co-op save states,
  rewind, and rollback are not supported; netplay uses delay synchronization.
- Campaign-specific transitions, progression/report behavior, mod combinations,
  Internet latency/loss, and longer sessions still need testing.
- Zero's HUD badge currently uses the resident blue palette.
- Existing widescreen limitations include authored gaps in Amazon Forest and
  incomplete coverage of the combined rain/darkness mask.

The source is pinned to the co-op framework and launcher branches. The package
includes source provenance, license notices, an audited native overlay cache,
and the fallback overlay toolchain. v1.2.0 remains the stable release.

---

# v1.2.0

Game-code sprite and scrolling-background interpolation above 60 Hz, with stable HUD and current animation cells. Includes the current audited adaptive-widescreen renderer and object activation/retention bounds so visible scenery loads before entering the view. Keeps encounter and script-controller activation guards.

Enable the frame-rate and widescreen enhancements in Mods. Native game timing remains unchanged. These are playable preview builds; full-game completion is not recertified.

---

# MegaManX6Recomp v1.2.0-rc2

This Windows validation candidate includes the adaptive widescreen integration
and the Weapon Center / Ilumina rendering fixes, plus fullscreen and launcher
improvements from rc1. The latest stable release
remains v1.1.0. A full playthrough has not been recertified for this candidate.

## Changes

- Windows borderless fullscreen uses a desktop-sized window without switching
  display modes. Exclusive fullscreen remains a separate option, including
  after reopening the launcher.
- The launcher remembers its resized dimensions across launches and fits them
  to the display's scaling and work area. Hotkey settings remain scrollable
  when the window is small.
- Release packaging checks its framework and output paths and includes
  `BUILD_PROVENANCE.json`, preventing a stale development cache from silently
  selecting an older framework worktree.
- Optional widescreen now offers Adaptive, 16:9, 21:9, and 32:9, in that order.
  Adaptive follows the window's aspect ratio. Enable it in Mods; it is off by
  default.
- Extended enemy spawning and culling, Ride Armor visibility, moving trash
  blocks, and Recycle Lab background coverage into the widened view.
- Integrated the supporting framework changes, including fixes for crashes
  during mod activation and renderer transitions.
- Kept Ilumina's sprite parts aligned in both phases, including wide views.
  Weapon Center's backdrop stays centered with the boss and reflects its
  original panorama to cover the extra width without exposing an atlas gutter.
- Aligned release overlay compilation hooks with the development configuration
  and rebuilt the original-disc native overlay cache for this exact build.

## Performance revalidation requested

GitHub issues #31 (Ilumina's second phase) and #32 (intro-stage enemies) remain
open. Current tests with Ultimate X in Ilumina's second phase and active intro
encounters ran near 60 FPS on the validation machine using NVIDIA OpenGL.
Those results do not establish performance on the Intel hardware in the reports.

If you reported either slowdown, please retry this candidate and report the
encounter, renderer, supersampling, enabled mods, CPU/GPU, and observed FPS.

Issue #22's savestate failure was not reproduced: 132 save/load operations
across 11 locations and a separate 20-minute active session with F7-menu saves
and loads passed. Please report the exact stage, BIOS and settings if it
persists. Issue #2's flashing on the reported 360 Hz display and issue #1's
Steam Deck Gaming Mode controller selection/rumble need hardware revalidation;
they are not certified resolved by the local tests.

## Compatibility and known limitations

Standard PS1 memory-card saves remain supported. Back up your saves before
testing. Old savestates are not guaranteed to load across this framework update;
load from your memory card and create new states in this version.

Rare exposed gaps and local pillarboxing in Amazon Forest are accepted
widescreen limitations. The experimental combined rain/darkness mask also has
remaining limitations. These do not block this candidate.

This is a Windows-only candidate. The package includes OpenBIOS and its MIT
notice, the launcher, bundled mods, a freshly audited overlay cache, and the
overlay toolchain. Your legally obtained game disc is still required. It does
not include a game disc, retail BIOS, or save data.
