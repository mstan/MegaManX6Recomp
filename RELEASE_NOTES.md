# Mega Man X6 Recompiled — v0.0.1-alpha

The **first public tech preview**. Mega Man X6 boots from the real PlayStation
BIOS, plays its opening, and reaches the introductory story dialogue with working
controller input — running as a native Windows program with no emulator behind
it, on the [PSXRecomp](https://github.com/mstan/psxrecomp) framework.

This is an **early** cut. It is a first look, not a way to play the game through.

## ✅ What works

- **Boots and runs the opening.** PS1 BIOS → disc detect → engine load
  (`ROCK_X6.DAT`) → X-vs-Zero / Space Colony intro → opening story dialogue.
- **Controller input.** MMX6 requires an analog pad before it will read buttons,
  so the runtime presents a DualShock by default. Keyboard and SDL gamepads both
  work; per-player override in the launcher.
- **Fast loading (turbo loads).** The machine fast-forwards during disc loads so
  they finish quickly, with authentic 1× CD timing preserved underneath — audio
  plays through normally and nothing desyncs. On by default; toggleable.
- **FMV auto-skip.** The opening movie can be skipped the instant it starts. On
  by default; toggleable in the launcher (Settings → "Skip FMVs").
- **Experimental 16:9 widescreen.** A genuine wider field of view for the 2D
  stage engine (opt-in). See `WIDESCREEN.md`.
- **Two renderers.** GPU OpenGL (default) and a CPU software rasterizer, with
  supersampling + anti-aliasing.
- **Graphical launcher** for BIOS / disc / memory-card selection and settings.

## ⚠️ Known limitations

- **Saving does not work yet.** Mega Man X6's card validation rejects its own
  data as "invalid"; save/load is not functional in this build (tracked in
  `ISSUES.md`).
- **Full in-stage gameplay is not yet confirmed end-to-end.** Bring-up past the
  opening is ongoing.
- Widescreen is experimental — expect some 2D/HUD/FMV/background rough edges.

## 📝 Notes

- As always, **bring your own** PlayStation BIOS and Mega Man X6 (USA, v1.1,
  SLUS-01395) disc image — the launcher asks for each. Verify your disc against
  `DISC.md`.
- Options live in the launcher's **Settings** and are remembered between
  launches.
- The overlay cache grows as you play; please keep `overlay_captures.json`
  private — it contains game code read from your disc (see README).
