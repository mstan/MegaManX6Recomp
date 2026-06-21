# MegaManX6Recomp — Issues

Current state (v0.0.1-alpha): the game boots from the PS1 BIOS and plays — through
the opening, into stages, with working controller input and memory-card
save/load, and **no known crashes**. It has not yet been verified all the way to
the end.

---

## #5 — Full playthrough not yet verified end-to-end — OPEN

Stage gameplay works and there are no known crashes, but the game has not been
verified from start to finish. If you hit a hang, crash, or wrong behavior deep
in a stage or boss, that's the kind of thing worth reporting — capture where it
happened.

---

## #6 — Universal FMV skip (enhancement follow-up) — OPEN

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

### #1 — Pre-gameplay spin: root-dir LBA parsed as 1 (should be 22) — ✅ FIXED
Early boot couldn't load `ROCK_X6.DAT` because the ISO9660 path-table parse
recorded the ROOT directory's extent LBA as 1 instead of 22 (a whole-sector
data-layout / framing issue in the CD read path). Fixed during the 2026-06-04
bring-up; the game now loads its data file and reaches the engine.

### #2 — Controller input does not register — ✅ FIXED
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

### #3 — Intro never advances to title; boot thread-scheduler livelock — ✅ FIXED
Against earlier framework pins the boot wedged at the intro→title handoff (a BIOS
thread-scheduler livelock; on the oldest pin a `DISPATCH FATAL` wild-jumptable
crash in the title state machine `func_8001D0E4`). The framework's
continuation-passing recompile (CPS) and single-owner mixed-dispatch fixes carry
MMX6 well past that wall and on into gameplay.

### #4 — Memory-card save / load rejected as "invalid" — ✅ FIXED
Earlier builds rejected the game's own card data with "ERROR: This data is
invalid" so saving/loading didn't work. Save and load now function with standard
PS1 `.mcd` images.
