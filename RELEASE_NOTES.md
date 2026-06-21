# Mega Man X6 Recompiled — v0.0.1-alpha

The **first public release**. Mega Man X6 boots from the real PlayStation BIOS and
**plays** — running as a native Windows program with no emulator behind it, on the
[PSXRecomp](https://github.com/mstan/psxrecomp) framework.

## ✅ What works

- **Boots and plays.** PS1 BIOS → disc detect → engine load (`ROCK_X6.DAT`) →
  opening → stage gameplay, with **no known crashes**.
- **Memory-card save / load.** Standard PS1 `.mcd` images, compatible with
  DuckStation, PCSX-Redux, Mednafen, ePSXe, and similar emulators.
- **Controller input.** MMX6 requires an analog pad before it will read buttons,
  so the runtime presents a DualShock by default. Keyboard and SDL gamepads both
  work; per-player override in the launcher.
- **Fast loading (turbo loads).** The machine fast-forwards during disc loads so
  they finish quickly, with authentic 1× CD timing preserved underneath — audio
  plays through normally and nothing desyncs. On by default; toggleable.
- **FMV auto-skip.** The opening movie can be skipped the instant it starts. On
  by default; toggleable in the launcher (Settings → "Skip FMVs").
- **Experimental 16:9 widescreen.** A genuine wider field of view for the 2D
  stage engine (opt-in, off by default). See `WIDESCREEN.md`.
- **Two renderers.** GPU OpenGL (default) and a CPU software rasterizer, with
  supersampling + anti-aliasing.
- **Graphical launcher** for BIOS / disc / memory-card selection and settings.

## ⚠️ Notes / known follow-ups

- **Not yet verified end-to-end.** Gameplay works with no known crashes, but a
  full start-to-finish playthrough hasn't been confirmed — if you hit something
  deep in a stage or boss, please report where it happened.
- **Widescreen is experimental** and off by default — expect some 2D / HUD / FMV
  / background rough edges.
- FMV auto-skip uses the generic (hold-START) path; a universal frame-count skip
  is a planned follow-up (see `ISSUES.md`).

## 📝 Setup

- As always, **bring your own** PlayStation BIOS and Mega Man X6 (USA, v1.1,
  SLUS-01395) disc image — the launcher asks for each. Verify your disc against
  `DISC.md`.
- Options live in the launcher's **Settings** and are remembered between
  launches.
- The overlay cache grows as you play; please keep `overlay_captures.json`
  private — it contains game code read from your disc (see README).
