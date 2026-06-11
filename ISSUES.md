# MegaManX6Recomp — Issues

## #1 — Pre-gameplay spin: root-dir LBA parsed as 1 (disc=22) → can't load ROCK_X6.DAT — OPEN (2026-05-28)

**Symptom:** Recompiled MMX6 boots (BIOS → game), draws a boot screen, then
locks before gameplay. Display disabled, GPU idle since ~frame 2200, frames keep
advancing (~56 fps) — a spin-wait, not a hard freeze. **0 dispatch misses.** Not
a codegen bug.

**Root cause (traced via Ghidra decompiles + live CD/RAM dumps + disc compare):**
The game can't find its main data file `ROCK_X6.DAT;1` because the ISO9660
**path-table parse records the ROOT directory's extent LBA as 1 instead of 22.**

Chain:
```
CdSearchFile(FUN_80061824)  resolve "\ROCK_X6.DAT;1"
 └ FUN_80061b1c "CD newmedia"  read PVD(LBA16) → path table(LBA18, from PVD+140)
                               → build dir-tree cache @0x800E5E8C (dirs + parent links)
 └ FUN_80061e84 "CD cachefile"  read resolved dir's files into file table @0x800E5888
     reads 1 sector at dir-tree[idx].LBA   ← uses LBA 1 for root (should be 22)
```
- **Disc path table (LBA 18, verified):** root extent=**22**, STR=23, XA=24 (all parent=1).
- **Our dir-tree cache @0x800E5E8C:** root `.` LBA=**1** (WRONG), STR=23 (ok), XA=24 (ok).
  Only the **first/root path-table entry's extent is corrupted**; later entries fine.
- Consequence: `FUN_80061e84(root)` reads the "root directory" at **LBA 1** (disc
  system area) instead of 22 → 0 file records parsed → file table `0x800E5888`
  stays empty → `ROCK_X6.DAT` lookup returns "not found" → the caller
  (FUN_80016780 / FUN_800147d0) retries every frame → spin.
- `cdrom_state` at the spin: `seek_msf=[0,2,1]`/`read_msf=[0,2,2]` = LBA 1–2, i.e.
  the bogus root-dir read. No CD activity since ~frame 711 (the read "succeeded"
  with garbage). Search token @0x801FFEF8 = `"ROCK_X6.DAT;1"`.

**Earlier mis-diagnoses (retracted):** memcard/CASE_A (stale `$t1=0x5C` snapshot),
A0(5Ch) dev_tty, "CD read totally fails", "strcmp". The CD read *works* for
STR/XA; the defect is specifically the **root/first path-table entry's extent**.

**Update (live DMA-trace capture):** `cdrom.c` delivers the **correct path-table
bytes** — the LBA-18 read's non-zero DMA words are exactly
`00160001(root ext=22) 00010000 00030000 00000017(STR=23) 54530001 00020052 00000018(XA=24) 41580001`.
BUT they arrive at DMA word **6** (`sector_buffer[24]`), preceded by
`[hdr 4][subhdr 8][12 ZERO bytes]`. A clean whole-sector buffer is
`[hdr 4][subhdr 8][data @ +12]` (since `WHOLE_SECTOR_OFFSET=12`,
`RAW_USER_DATA_OFFSET=24`), so the user data should start at `sector_buffer[12]`,
not `[24]`. That extra 12-byte gap desyncs `FUN_80061b1c`'s parse so the **root
(first) entry's extent** lands on the wrong field (→ 1), while STR/XA happen to
realign (→ 23/24 correct). `maybe_deliver_xa_audio` is ruled out (const,
mode&0x40 unset, early-return).

**Next step:** the 12-byte gap means `read_sector_at`'s `memcpy(sector_buffer,
raw+12, 2340)` is producing data at +24, so either `iso_read_raw_sector` returns
this disc's raw sector with user data at raw+36 (not +24), or the raw framing
differs. Read `iso_reader.cpp`'s raw-sector layout, OR add a `cdrom`
sector-buffer dump command and compare to the disc. Fix the whole-sector data
layout in `runtime/src/cdrom.c` (or `iso_reader`), rebuild, re-measure — expect
the failure to move past the disc-load into title/intro.

**Launch:** `psx-runtime --game <abs game.toml> --bios
F:\Projects\psxrecomp\psxrecomp\bios\SCPH1001.BIN --disc "<abs mmx6 cue>"`
(direct BIOS path, not the junction). TCP 4490; `cdrom_state` / `cdrom_trace_dump`
/ `read_ram` for inspection. MMX6 Ghidra: `psx_ghidra` SSE localhost:4444,
program `SLUS_013.95_no_header.bin`.

NOTE: pass the `--disc` path **quoted as one argument** — `Mega Man X6 (USA)
(v1.1).cue` has spaces; an unquoted/array arg splits at "Mega" and the runtime
exits with "no disc image selected".

---

## #2 — Controller input does not register (keyboard + SDL gamepad) — OPEN (2026-06-04)

**Symptom:** In the recompiled MMX6, **no pad input registers at all** — neither
the keyboard map nor an SDL game controller (tested with a PS5 controller).
Reproduced on both the dev build (RelWithDebInfo, TCP 4490) and the retail
Release build (`build-mmx6-release`, no debug tools). The intro FMV plays but
cannot be advanced/skipped.

**Verified (so the obvious causes are ruled out):**
- Keyboard mapping exists and is sampled every frame — `pad_from_keyboard()` in
  `runtime/src/main.cpp` (Arrows=D-pad, Enter=Start, RShift=Select, X=✕, S=○,
  Z=□, A=△, Q/W=L1/R1, E/R=L2/R2), merged with the controller in the event loop
  (`merge_controller_pad(pad_from_keyboard())`, ~line 936) → `sio_set_pad_state(...)`.
- On the dev build, `pad_status` (port 4490) reported `override:-1`,
  `pad:0xFFFF` — i.e. NO stuck debug input-override is masking the keyboard, and
  the runtime layer is forwarding the (all-released) pad normally.
- `input.ini` configures only the *controller* mapping; keyboard map is the
  hardcoded default above (so a missing input.ini is not the cause).

**NOT yet isolated (the set_input/press injection test was interrupted):**
whether the **SIO pad protocol actually delivers the pad word to the game's pad
read**, or the game rejects the presented controller, or input is only consumed
after the FMV.

**Hypotheses (in priority order):**
1. SIO pad presents a controller type/ID the game doesn't accept. MMX6 may
   expect analog/DualShock (cf. Ape Escape's "DualShock required" screen); if the
   SIO emulation returns a digital-pad ID or an incomplete poll/ack sequence, the
   game may treat "no usable controller" and ignore input.
2. `sio_set_pad_state()` value isn't reaching the game's pad-read path (SIO
   transfer/ack timing in the mmx6 `sio.c`/`cdrom.c` deltas).
3. Game only polls the pad after the intro/FMV completes.

**Next steps:** on a dev build, inject `set_input <mask>` / `press <btn>` on
4490 and watch (a) whether the FMV skips and (b) the game's pad-read RAM for a
change; compare the SIO pad init/poll/ack byte sequence against the Beetle
oracle; and check whether **Tomba** (which reaches an interactive menu) also
fails input — if Tomba input works, this is MMX6/controller-type-specific; if it
also fails, it's a framework-wide SIO pad-delivery bug.

---

## #3 — Intro never advances to title; dispatch crash + SIO IRQ storm — OPEN (2026-06-11)

Deep re-investigation against the Beetle oracle (psxref @4380) reframed #1/#2.
The "input doesn't register" symptom is downstream: **MMX6 never reaches the
interactive title screen at all.**

**Ground truth (oracle):** boots to the **title screen ("PRESS START BUTTON",
X6 logo)** by ~frame 2000, *without any input*. Main-mode byte `0x800CD3F8`=0,
title sub-state `0x800CD3F9`=6, object pool `0x800CD410` (96 slots × 0x60)
**empty**. The intro→title transition is automatic (timer/scripted), not
input-gated. So input is NOT what blocks the title.

**Recomp boot/title flow (statically mapped):**
- `func_8001D0E4` = top-level title/menu state machine. Reads main-mode byte
  `0x800CD3F8`, dispatches via fn-ptr table `0x800710E8` (`lb state; <<2; +table;
  lw; jalr`). Sets `[0x800CD405]=1` at entry. Sub-handlers via table `0x8007108C`
  (sub-state `0x800CD3F9`); sub-state 6 = "PRESS START".
- `func_8001F65C` = intro object-list spawner (parses a byte list, allocs type
  0x1F objects via allocator `0x8002C530`). Loop bug: when alloc returns 0 (pool
  full) it does NOT advance the list pointer → spins.
- Both reached only via runtime fn-ptr dispatch (no static jal / table ref in
  the EXE).

**Symptom A — old framework (pin 035a9fa, build-master pre-2026-06-11):**
`DISPATCH FATAL: misaligned target 0x00000003`, `$ra=0x8001D180` (the `jalr v1`
in `func_8001D0E4`) — the mode table read a garbage entry (wild jumptable
dispatch). Same bug *class* as Tomba Bug D.

**Symptom B — runtime-only rebuild against current master (34561b5):** no crash,
but stuck in the intro: `func_8001D0E4` never runs (`[0x800CD405]`=0), pool
96/96 full of type-0x1F objects, `ra` parked at `0x8001F6F0` (the spawner's
alloc call). **Cause of the behavior change:** commit **2439d4d "dispatch call
contract"** changes BOTH emitters (regen-required) AND runtime. Rebuilding only
the runtime left stale generated code (no `(ra,sp)` contract checks) mismatched
against the new runtime. **Lesson: a framework bump REQUIRES regen of BIOS+game,
never runtime-only.**

**Symptom C — full regen against current master (BIOS+game, contract-aware):**
- The contract now **catches the `func_8001D0E4` wild dispatch**: telemetry
  `bail_first=3, bail_flattened=3, bail_anomaly=0`. **No more DISPATCH FATAL.**
  This is real progress — the crash (#1/Symptom A) is fixed by the contract.
- BUT exposes the next bug: an **MMX6-specific SIO IRQ storm** during boot/intro.
  The BIOS spins in `func 0x1794 @ pc 0xBFC112A0` (`in_exc=1`) issuing endless
  SELECT_ASSERT/BAUD/TX/RX/STAT SIO ops, never making forward progress on the
  main thread (`current_func 0x3A60`). VBlank heartbeat starves → starvation
  watchdog aborts after 4s (`starvation_dump.jsonl`). Sometimes hangs at boot,
  sometimes ~frame 1200 (race-ish). **Tomba boots fine on the same contract+BIOS
  regen** (commit verified Tomba boot/title/attract, bail counters 0), so this is
  MMX6-specific.

**Leading hypothesis for the SIO storm:** the contract's dirty_ram_interp change
("bail aborts the interp run") can abort the **RAM-installed SIO byte handler at
RAM 0xCF0** (run by `dirty_ram_interp`) mid-execution when a bail fires during
boot SIO activity → SIO IRQ left unacked → BIOS re-enters the SIO exception
forever. The 3 boot-time bails coincide with heavy SIO. Needs: confirm a bail
fires inside the 0xCF0 interp run, and make bail unwind ACK/complete the SIO
transaction (or never bail inside the SIO handler) — a framework fix that must
be regression-tested against Tomba.

**State of the branch (`feat/mmx6-input`):** pin left at 035a9fa (validated
boot-to-intro baseline); `generated/` (gitignored) currently holds a
current-master contract regen that reaches Symptom C. To reproduce Symptom C:
build recompiler tools from psxrecomp current master, regen BIOS
(`psxrecomp-bios --config bios/SCPH1001.toml`) + game
(`psxrecomp-game --config game.toml`), rebuild `build-master`.

**Tooling added (`tools/`):** `run_mmx6.ps1` (autonomous launcher — BIOS/disc
baked + quoted, cached to bios.cfg/disc.cfg), `dbg.py` (raw TCP cmd; addr must be
a hex STRING), `pool.py`/`checkstate.py` (boot-progress probes), `stackwalk.py`,
`dumpgrep.py`. Oracle: `F:\Projects\psxref\run-mmx6.bat` (Beetle @4380).

**Recommended next step:** fix the contract×SIO-handler interaction (framework),
re-verify MMX6 reaches the title with bail counters clean AND no SIO storm, THEN
resume #2 (input) — which can only be tested once the title screen is reached.
