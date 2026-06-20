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

## #2 — Controller input does not register — ✅ FIXED (2026-06-19)

**Root cause (framework SIO bug, not MMX6-specific):** MMX6 probes the pad with
the DualShock **config command `0x43`** at init and will NOT poll buttons (`0x42`)
until it detects an analog-capable controller. `runtime/src/sio.c` answered `0x43`
with `0xF3` (config-mode ID) **unconditionally** — i.e. the emulated pad always
looked "in config mode." MMX6's detect/exit handshake therefore never completed:
the SIO TX stream looped `01 43 00 00 …` forever and never reached `0x42`, so no
input was ever delivered. (Tomba was unaffected — it only sends the plain `0x42`
poll, never `0x43`.)

**Fix:** proper DualShock config state machine in `sio.c` — track in/out of config
per slot, report the real pad ID (`0x41` digital / `0x73` analog) when NOT in
config and `0xF3` only when actually in config, honor the `0x43` enter(0x01)/
exit(0x00) flag, and gate the config-only commands (0x44–0x4F) so a digital pad
ignores them like real hardware. MMX6 also defaults to a DualShock now
(`game.toml [controller] default_analog=true`; launcher can override). Verified:
SIO went `0x43`-only → `0x42` reads returning `0x73` + 8-byte analog response;
held CROSS reflected as `73 5A FF BF 80 80 80 80`; game state advanced on input;
intro story now playable. Runtime-only change (no regen). Original notes below.

## #2 (original) — Controller input does not register (keyboard + SDL gamepad) — was OPEN (2026-06-04)

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

## #3 — Intro never advances to title; boot thread-scheduler livelock — OPEN (2026-06-11)

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
- BUT the boot still wedges: starvation watchdog aborts after 4s
  (`starvation_dump.jsonl`), ~74M interp insns burned, VBlank never fires.

**User-facing framing (don't misread as a regression):** every run
deterministically reaches **frame ~1241 (~20s of presented video — the X-vs-Zero
intro/FMV plays fine)**, then wedges at the **intro→title handoff** (`func_8001D0E4`
title state machine). The dev **starvation watchdog** then `exit()`s ~4s later,
which closes the window — that auto-close is the watchdog SURFACING the freeze,
not a new bug. The pinned 035a9fa build dies at the *same* transition via a hard
`DISPATCH FATAL` crash; the contract turned that crash into a freeze but did NOT
move the wall. So it's a failure-MODE change, not a playability regression — the
game has never reached an interactive, input-responsive title on either build.

**Root cause (2026-06-11, ring-evidenced — supersedes the earlier "SIO IRQ
storm / bail-aborts-RAM-0xCF0" hypothesis, which was WRONG):** the real failure
is a **BIOS thread-scheduler livelock at boot**, NOT an SIO bug and NOT
caused by the contract. Evidence from the always-on rings folded into
`starvation_dump.jsonl` (`bail_log`-style entries + thread-ctx ring + counters):
- The "SIO storm" at `func 0x1794 / pc 0xBFC112A0` is the BIOS **scheduler /
  event-poll loop** (kernel-part-2 RAM, ROM `0xBFC11294`: checks event flags at
  `*(0x6d40)`, calls DeliverEvent), not an SIO IRQ storm. `i_mask=0x0D`
  (controller IRQ bit 7 NOT enabled); `in_exc=1` throughout.
- The **thread-ctx ring** (256 caps, ALL at frames **1230–1241** = hundreds of
  switches in ~11 frames) shows 3 TCBs thrashing via `ChangeThread` (syscall 3,
  through the `syscall;jr ra` stub at RAM `0x650`=ROM `0xBFC10150`), all parked
  at the syscall-return PC **`0x2104`** (=ROM `0xBFC11C04`, after
  `jal 0xb0000650`,a0=3). 172 restores vs 84 saves (repeated/double restores =
  no forward progress). TCBs: `0xA000E29C` (parked@0x2104), `0xA000E35C`
  (game-main: resumes `0x8001D0E4` title machine / `0x2104`), `0xA000E41C`
  (`0x80013530` / `0x2104`).
- The **thrash STARTS ~frame 1230, the 3 bails are all at frame 1241** → the
  scheduler livelock PRECEDES the bails by ~11 frames. The contract bails are a
  LATE symptom: when game thread `0xE35C` momentarily resumes its title machine
  `0x8001D0E4`, it reads a garbage mode-table entry → wild jumptable dispatch
  (bail 1 target `0x800661A8`, a game addr; bail 0/2 at the syscall-return site
  with `$sp` legitimately shifted +0x48/+0x30 by the context switch). All 3
  bails have `interp_active=1`. **Fixing the contract would NOT fix the storm.**
- After ~frame 1241 thread-switching stops and the interp free-spins at RAM
  `0x46xx` (`func 0x3A60`=ROM `0xBFC12F60`) until the watchdog fires.

**The ultimate hang (concrete lead):** after frame 1241 thread-switching stops
and one thread free-spins at RAM `0x46C0` (ROM `0xBFC141C0`), a BIOS pad/card
**timeout-bounded poll**: loop ≤0x51 tries checking **bit 0x80 of `*s0`** (a
software completion flag the controller IRQ handler sets), retrying at a higher
level on timeout. It spins ~74M× because the completion bit never sets — and
`i_mask=0x0D` means the **controller/SIO IRQ (bit 7) is masked out**, so the
transfer-complete IRQ can never fire → the handler never sets `*s0` bit 0x80 →
infinite retry. Causal chain: controller IRQ (bit 7) not enabled/serviced → pad
completion flag never set → poll-spin at 0xBFC141C0 → threads block/thrash →
VBlank starves → watchdog. The oracle boots, so on real HW that IRQ IS delivered
for MMX6's transfer. **Next concrete step:** instrument the SIO/controller IRQ
raise+i_mask-write path (sio.c / interrupts.c), re-run, find why bit 7 is never
set in i_mask (or never raised in i_stat) for MMX6's boot transfer — compare the
i_mask write sequence vs Tomba's working boot.

**Earlier open question (still relevant):** WHY does the scheduler livelock —
what event are the 3 threads blocked on, and why does it never arrive (VBlank
can't fire while the interp never yields to the host frame pump; or the garbage
mode-table at `0x8001D0E4` is itself the first divergence). The garbage
mode-table read is the same latent bug as Symptom A — find where the table is
populated at boot and compare RAM against the oracle (first-divergence). The
contract is doing its job; do not weaken it.

**State of the branch (`feat/mmx6-input`):** pin left at 035a9fa; `generated/`
(gitignored) holds a current-master contract regen reaching Symptom C. Reproduce:
build recompiler tools from psxrecomp current master, regen BIOS
(`psxrecomp-bios --config bios/SCPH1001.toml`) + game
(`psxrecomp-game --config game.toml`), rebuild `build-master`. **psxrecomp
`feat/mmx6-input` has UNCOMMITTED observability work** (bail-site ring + thread-
ctx ring + dirty/bail counters folded into the starvation dump; `bail_log` TCP
cmd) — see below.

**Observability added this session (psxrecomp `feat/mmx6-input`, uncommitted):**
- `psx_bail_record` + 4K bail-site ring + `bail_log` TCP cmd (`debug_server.c`),
  recorded at BOTH bail-first sites: the `psx_call_contract` inline
  (`cpu_state.h`) and the emitted dispatch loop (`full_function_emitter.cpp` →
  BIOS regen). Captures site_ra/site_sp/cur_sp/target/cur_pc/cur_func/kind/
  **interp_active**/frame.
- `psx_bail_ring_dump_file` + `psx_thread_ctx_ring_dump_file` (`traps.c`) +
  bail/dirty counters folded into the watchdog dump meta (`starvation_ring.c`).
  Why: the TCP server is main-thread-pumped and CANNOT serve during the storm,
  so the watchdog dump (`starvation_dump.jsonl`) is the only thing that survives.
- Analysis: `tools/_analyze_sio.py`, `tools/_analyze_tctx.py`.

**Tooling (`tools/`):** `run_mmx6.ps1` (autonomous launcher), `dbg.py` (raw TCP
cmd; addr must be a hex STRING), `pool.py`/`checkstate.py`, `stackwalk.py`,
`dumpgrep.py`. Oracle: `F:\Projects\psxref\run-mmx6.bat` (Beetle @4380).
