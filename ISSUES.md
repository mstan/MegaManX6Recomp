# MegaManX6Recomp — Issues

## #1 — Spin-wait before gameplay on BIOS A0(5Ch) chain — OPEN (2026-05-28)

**Symptom:** Recompiled MMX6 boots (BIOS → game), draws a boot screen, then
locks before entering gameplay. Display disabled, GPU idle since ~frame 2200,
but frames keep advancing (~56 fps) — a spin-wait, not a hard freeze.

**Recomp health:** Recompiles clean (3163 functions, exit 0). **0 dispatch
misses / 0 unknown dispatches** the whole way. This is NOT a codegen/discovery
bug.

**First divergence** (from a `quit` snapshot of `psx_last_run_report.json`):
- `dispatch_tail`: infinite ping-pong `0x5C4` ↔ `0x1FC03288` (KSEG `0xBFC03288`).
- `dirty_block_tail`: identical blocks — `target=0xA0` (A0 syscall vector),
  `ra=0x80061E3C` (game code), `a0=0x801FFEF8`, `a1=0x800E5E94`, `$t1=0x5C`.
- `0x5C4` = **TableA0Handler** — the RAM-installed A0 dispatcher run through
  `dirty_ram_interp` (`psxrecomp/docs/psx_bios_disasm.txt:940`).
- ⇒ game fn `0x80061E3C` loops on **A0(5Ch)** (ROM body `0xBFC03288`); the call
  returns the same value each iteration and the game's poll never exits.

**Class:** runtime / BIOS-AOT. Matches `psxrecomp/docs/CASE_A_AOT_GAP.md`
("RAM-installed BIOS handler chain doesn't deliver → consumer polls forever").
Not codegen.

**Next steps:**
1. Resolve A0(5Ch)'s identity from the BIOS disasm / BIOS Ghidra.
2. Build the Beetle PSX oracle (`psx-beetle`) for MMX6.
3. Diff native vs real BIOS `A0(5Ch)` return at the call site (`ra=0x80061E3C`).
4. Fix the runtime/BIOS-AOT chain (framework, not generated C).

**Launch recipe:** `psx-runtime --game <abs game.toml> --bios
F:\Projects\psxrecomp\psxrecomp\bios\SCPH1001.BIN --disc "<abs mmx6 cue>"`.
Pass `--bios` with the DIRECT framework path — through the `psxrecomp-v4`
junction the runtime's file-open fails and pops the BIOS file-picker. TCP debug
server on 4490; `quit` writes the dispatch/dirty tails to
`psx_last_run_report.json`.
