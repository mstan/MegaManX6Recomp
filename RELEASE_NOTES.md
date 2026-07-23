# Mega Man X6 Recompiled - v0.0.7-alpha

This release focuses on the fullscreen launch path. The launcher now exposes the
shared tri-state fullscreen picker for MMX6: windowed, borderless windowed
fullscreen, or exclusive fullscreen.

## New in v0.0.7-alpha

- **Borderless windowed fullscreen.** MMX6 now uses the same multi-option
  fullscreen picker as the shared launcher surface, with borderless windowed and
  exclusive fullscreen available separately.
- **CUE startup fallback.** If a selected `.cue` has a same-named `.bin` beside
  it, the runtime launches with that `.bin` path. This avoids startup failures
  from CUE files that validate but do not mount cleanly in the runtime path.

All existing alpha caveats and game-compatibility notes below still apply.

# Mega Man X6 Recompiled — v0.0.2-alpha

A maintenance release on top of the first public build. Mega Man X6 still boots
from the real PlayStation BIOS and **plays** as a native Windows program with no
emulator behind it, on the [PSXRecomp](https://github.com/mstan/psxrecomp)
framework — now with a self-contained overlay toolchain (no developer tools
required) and broader controller support.

## ✨ New in v0.0.2-alpha

- **Self-contained overlay compilation (no toolchain required).** As you explore
  new areas, the runtime converts the game's overlay code to native code in the
  background. Previously that needed a developer toolchain on your PC; this
  release bundles a fully self-contained one (an embedded Python + TinyCC), so
  newly visited areas are accelerated on any machine with nothing to install.
- **Xbox controller fix.** Physical Xbox One / Series pads now work. They were
  previously claimed by no driver (the runtime forces HIDAPI for Steam virtual
  controllers, and HIDAPI's Xbox sub-driver is off by default on Windows); the
  runtime now enables it. PlayStation DualSense pads continue to work.
- **Software renderer is the default this release.** The OpenGL backend shows
  intermittent flicker in this build, so the clean software renderer ships as the
  default. OpenGL is still selectable in the launcher. See **Known issues** below
  and `ISSUES.md` #7.

## ✅ What works (unchanged from v0.0.1)

- **Boots and plays.** PS1 BIOS → disc detect → engine load (`ROCK_X6.DAT`) →
  opening → stage gameplay, with **no known crashes**.
- **Memory-card save / load.** Standard PS1 `.mcd` images, emulator-compatible.
- **Controller input.** MMX6 requires an analog pad before it reads buttons, so
  the runtime presents a DualShock by default. Keyboard and SDL gamepads both
  work; per-player override in the launcher.
- **Fast loading (turbo loads)**, **FMV auto-skip**, **experimental 16:9
  widescreen** (opt-in), supersampling + anti-aliasing, and the **graphical
  launcher** for BIOS / disc / memory-card selection and settings.

## ⚠️ Known issues

- **OpenGL flicker (worked around).** The OpenGL renderer shows intermittent
  black-frame flicker in this build (most visible around Zero). The software
  renderer is clean and is the default; OpenGL remains selectable if you want to
  try it. Root-cause is tracked in `ISSUES.md` #7.
- **Not yet verified end-to-end.** Gameplay works with no known crashes, but a
  full start-to-finish playthrough hasn't been confirmed — please report where it
  happened if you hit something deep in a stage or boss.
- **Widescreen is experimental** and off by default — expect some 2D / HUD / FMV
  / background rough edges.

## 📝 Setup

- As always, **bring your own** PlayStation BIOS and Mega Man X6 (USA, v1.1,
  SLUS-01395) disc image — the launcher asks for each. Verify your disc against
  `DISC.md`.
- Options live in the launcher's **Settings** and are remembered between
  launches.
- The overlay cache grows as you play; please keep `overlay_captures.json`
  private — it contains game code read from your disc (see README).

# Mega Man X6 Recompiled — v0.0.6-alpha

This release replaces the old in-tree launcher with the shared Dear ImGui
`recomp-ui` launcher. Its DPI-independent layout keeps launcher text, settings,
and the Launch button readable and reachable on Steam Deck and high-resolution
or scaled Windows displays, addressing issues #1 and #3.

## Launcher and packaging

- Uses the current shared `recomp-ui` PSX profile for BIOS, disc, controller,
  renderer, memory-card, and game-option configuration.
- Bundles the matching launcher fonts and game-specific art beside the
  executable.
- Keeps the complete settings surface accessible without relying on the old
  fixed-size legacy document layout.

All existing alpha caveats and game-compatibility notes above still apply.
