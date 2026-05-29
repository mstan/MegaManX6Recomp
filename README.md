# MegaManX6Recomp

Static recompilation of **Mega Man X6 (USA)** (SLUS-01395, disc revision
**v1.1**) to native code, built on the shared **psxrecomp v4** framework — the
same pipeline behind TombaRecomp. The goal is a native binary that runs the
game with no emulator behind it.

## Status

**Scaffolded.** Project layout, config, the disc image, the extracted boot EXE,
and the Ghidra dump are all in place. Not yet recompiled or booting — that is
the next phase.

## Required user-owned assets (not included in the repo)

- PlayStation BIOS `SCPH1001.BIN` — provided by the framework at
  `psxrecomp-v4/bios/SCPH1001.BIN`.
- The Mega Man X6 (USA) (v1.1) disc image
  (`mmx6/Mega Man X6 (USA) (v1.1).cue` + `.bin`) and the extracted boot EXE
  `mmx6/SLUS_013.95`. These are local-only and gitignored.

## Layout

| Path | Purpose |
|------|---------|
| `game.toml` | Game identity + recompiler/runtime config (entry point, load address, text size, disc path). |
| `mmx6/` | Disc image + extracted boot EXE `SLUS_013.95` + `SYSTEM.CNF` (local). |
| `seeds/` | Function-start seeds fed to the recompiler. |
| `annotations/` | CSV of human notes emitted as comments in the generated C. |
| `ghidra/` | Headerless dump + `instructions.txt` for reverse engineering. |
| `generated/` | Recompiled C (local; produced by `tools/regen.ps1`). |
| `psxrecomp-v4` | Junction to the shared framework (version pinned in `psxrecomp-v4.pin`). |

## Build (from source)

```
pwsh tools/regen.ps1            # generate C from the EXE (writes generated/)
cmake -S . -B build -G "Unix Makefiles"
cmake --build build -j16
./build/psx-runtime.exe --game game.toml
```

(The framework recompiler `psxrecomp-v4/recompiler/build/psxrecomp-game.exe`
must be built first; see the framework's own README.)

## Disc identity

`MODE2/2352` bin+cue, single data track, NTSC-U, **v1.1** revision. Verify a
fresh dump matches the recorded hashes before blaming a regression — the v1.1
vs v1.0 distinction matters for reproducibility.

## Rules

See `CLAUDE.md`. In short: fixes go in the framework or `game.toml`, never in
`generated/`; no stubs; binaries stay local.
