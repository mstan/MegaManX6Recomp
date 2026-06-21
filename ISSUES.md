# MegaManX6Recomp — Issues

Current state (v0.0.1-alpha): the game boots from the PS1 BIOS, plays the opening
FMV, and reaches the intro story dialogue with working controller input. Saving
does not work, and full in-stage gameplay is not yet confirmed end-to-end.

---

## #4 — Memory-card save / load rejected as "invalid" — OPEN (2026-06-19)

**Symptom:** MMX6 cannot save, and LOAD-from-card on the continue screen shows
**"ERROR: This data is invalid."** Drivable on a dev build by pressing X on the
continue→load screen (load → check → fail → X exits the modal).

**It is OUR bug, not card emulation.** The Beetle oracle (psxref) saves and loads
fine on the *same* shared `card1.mcd`. Ruled out (verified — do not re-tread):
- The card is correctly formatted (DuckStation layout, header checksum `0x0E`,
  directory free `0xA0/0xFFFF`, valid frame checksums).
- Our memory-card **reads are byte-perfect** vs the PSX spec (FLAG `0x00`, IDs
  `5A 5D`, MSB/LSB echo, 128 data bytes, correct checksum, `0x47` end).
- The card completion IRQ (#7) **fires** (mc_state=10, `i_stat` `0x00`→`0x80`).
- Tomba saves fine through the same memory-card code.

**So the defect is in MMX6's recompiled execution of its own card-validation /
save routine** — it reaches the wrong result on correct data (a CPU/codegen or
overlay dirty-RAM divergence). MMX6's card-UI code most likely lives in the
`ROCK_X6.DAT` overlay, not the boot EXE (its strings are tile-encoded, so they
don't appear in the Ghidra dump of the EXE). **Next:** instruction-level
first-divergence of MMX6's card-validation function vs the oracle (see the
`recomp-debug` skill). Repro: the press-X loop on the continue→load screen.

---

## #5 — Full in-stage gameplay bring-up — ONGOING

The game reaches the opening story dialogue with input working. Driving from
there through the title / stage-select into actual stage gameplay, and confirming
it end-to-end, is the next milestone. No specific blocker is isolated yet beyond
#4 (saving).

---

## #6 — Universal FMV skip (follow-up) — OPEN

`auto_skip_fmv=true` currently uses the framework's **generic** path: it holds
START so a movie whose handler polls the pad aborts itself. That works for the
pad-skippable opening but cannot reach movies the game won't let you skip.

The **complete** version is Tomba's universal frame-count path: write the active
movie's per-movie frame-total down so the game's OWN player tears the movie down
next frame. That reaches every movie. It needs MMX6's MDEC player RE'd — find the
per-movie frame-total table base, the current-movie-id byte, and the teardown
condition — then fill `fmv_skip_total_table` / `fmv_skip_movie_id` /
`fmv_skip_end_total` in `game.toml [video]` to match.

---

## Resolved

### #1 — Pre-gameplay spin: root-dir LBA parsed as 1 (should be 22) — ✅ FIXED (2026-06-04)
Early boot couldn't load `ROCK_X6.DAT` because the ISO9660 path-table parse
recorded the ROOT directory's extent LBA as 1 instead of 22 (a whole-sector
data-layout / framing issue in the CD read path). Fixed during the 2026-06-04
bring-up; the game now loads its data file and reaches the engine.

### #2 — Controller input does not register — ✅ FIXED (2026-06-19)
A framework SIO bug, not MMX6-specific: `runtime/src/sio.c` answered the
DualShock config command `0x43` with `0xF3` (config-mode ID) **unconditionally**,
so the emulated pad always looked "in config mode." MMX6 probes the pad with
`0x43` at init and will not poll buttons (`0x42`) until it detects an
analog-capable controller, so its handshake looped forever and no input was ever
delivered. (Tomba was unaffected — it only sends `0x42`.) Fixed with a proper
DualShock config state machine (real ID `0x41` digital / `0x73` analog when not
in config, `0xF3` only in config, enter/exit latch via the `0x43` data byte,
config commands `0x44`–`0x4F` gated to config mode). MMX6 also defaults to a
DualShock now (`game.toml [controller] default_analog=true`).

### #3 — Intro never advances to title; boot thread-scheduler livelock — ✅ RESOLVED
Against earlier framework pins the boot wedged at the intro→title handoff (a BIOS
thread-scheduler livelock; on the oldest pin a `DISPATCH FATAL` wild-jumptable
crash in the title state machine `func_8001D0E4`). The framework's
continuation-passing recompile (CPS) and single-owner mixed-dispatch fixes carry
MMX6 well past that wall — it now boots through the intro to the opening story
dialogue. Tracked historically; superseded by the current state above.
