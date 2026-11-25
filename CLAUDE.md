# MegaManX6Recomp Rules

Static recompilation of **Mega Man X6 (USA)** — serial **SLUS-01395**, disc
revision **v1.1** — to native code, built with the shared **psxrecomp v4**
framework. The end goal is a binary that plays without an emulator behind it,
exactly like TombaRecomp.

## Inheritance

This project inherits, in order:

1. `F:/Projects/recomp-template/PRINCIPLES.md` — system-agnostic recomp/debug
   discipline (ground truth = original EXE + emulator oracle; generated C is
   evidence, not authority; first-divergence; no guessing).
2. The shared framework instructions at `psxrecomp-v4/AGENTS.md` and
   `psxrecomp-v4/docs/HLE_EXECUTION.md`. Use host-native HLE builds and report
   coverage gaps; retain a separately selected accuracy reference. Fix the
   framework/runtime/config and **regenerate** when required — never hand-edit
   `generated/`. Current owner instructions take precedence over older notes.

## Project rules

- Game binaries (disc image, extracted boot EXE, the headerless Ghidra dump),
  Ghidra databases, memory cards, and build outputs are **local only** and must
  not be committed. See `.gitignore`.
- Tracked: `game.toml`, `seeds/`, `annotations/`, `ghidra/instructions.txt`,
  `ghidra/scripts/`, `ghidra/annotations/`, `CMakeLists.txt`, `tools/`, docs.
- Codegen/runtime fixes belong in the framework (`psxrecomp-v4/`) or in
  per-game `game.toml` config — never in `generated/*.c`. A fix that only this
  game needs is a smell; prefer a class fix that the next title inherits.
- After every run, resolve all dispatch misses before any other debugging.
- The framework version this project builds against is recorded as the
  `psxrecomp-v4` git submodule pointer (see `.gitmodules`); the former
  `psxrecomp-v4.pin` file was retired in favor of the submodule (its changelog
  is preserved in `docs/framework_pin_history.md`). The source disc is the
  **v1.1** revision — record its
  hashes (see `ghidra/instructions.txt`) so a future dump can be verified
  identical before blaming a regression.
