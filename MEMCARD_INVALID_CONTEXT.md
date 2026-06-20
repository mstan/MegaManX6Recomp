# MMX6 memcard "This data is invalid" — context for external review

## TL;DR for the reviewer
We have a **static recompilation** of *Mega Man X6 (USA, SLUS-01395 v1.1)* to native code.
The **PSX BIOS (SCPH1001) is also statically recompiled** — there is **no MIPS interpreter for
ROM/BIOS code and no HLE BIOS**; hardware is simulated at the MMIO level (SIO/memcard, DMA, IRQ,
GPU, SPU). A small dirty-RAM interpreter runs only code the program writes into RAM at runtime
(the game's overlay `ROCK_X6.DAT` at `0x800E0000+`). Ground truth = a Beetle-PSX (mednafen) oracle
running the same disc + same memory-card file, queried over a parallel TCP debug server.

**Symptom:** On a validly-formatted but **empty** memory card, both **SAVE and LOAD** of the game's
save show **"This data is invalid."** The real hardware / oracle instead shows **"No save data found"**
(LOAD) and lets SAVE create a new file. User confirmed the oracle saves/loads fine on the *same* card,
so this is our recompilation bug, not card-image corruption.

**We have first-divergence'd it.** The question for you is the **last hop**: *why does the recompiled
BIOS/BU card library fail to deliver the terminal `EvSpTIMOUT` card event (or, why does the emulated
card respond where real hardware would time out), so the game's poll times out and reports "invalid"
instead of "no data".*

---

## Architecture / ground rules (hard constraints)
- No MIPS interpreter for ROM/BIOS, no HLE BIOS shims, no stubs. Fixes go in the **recompiler**
  (`recompiler/src/*`) or the **runtime/hardware sim** (`runtime/src/*`, e.g. `sio.c`, `interrupts.c`),
  or game `game.toml` — **never** edit generated C.
- The BIOS *is* the recompiled output of SCPH1001.BIN. If BIOS behavior is wrong, fix the recompiler
  or the MMIO simulation it touches.
- Oracle (Beetle PSX) is ground truth; we debug by first-divergence, not guessing.
- The boot EXE (`SLUS_013.95`) loads at `0x80010000`–`0x8008EFFF` and is **statically recompiled**
  (in Ghidra). The overlay region `0x800E0000+` is **dirty-RAM interpreted** (not in Ghidra; we
  disassemble live RAM).

## Memory card facts (verified, do NOT re-litigate)
- Card image is a correct empty DuckStation-layout card: `MC` header (cksum 0x0E), all dir entries
  `0xA0` (free) with valid frame checksums.
- Low-level card **reads are byte-perfect** vs PSX spec; card completion IRQ #7 fires; SIO transactions
  close `success` (terminal_state 12). Tomba (another title on this engine) saves/loads fine through the
  same SIO code — **but Tomba only ever issues the `0x42` (read pad/poll) pattern; MMX6 drives a fuller
  card command sequence.** This asymmetry is a strong hint.

---

## Confirmed first-divergence chain (recomp vs oracle, same empty card)

### Layer 0 — the message
Card-screen sub-state byte `[0x800CD3F9]`: `0x02`=continue-menu, `0x05`=warning ("invalid").
Diffed the entire 384-byte card-manager struct at `0x800CCED0` between recomp and oracle while both sat
on the identical "Continue the game? / Load from a MEMORY CARD" menu: **exactly one byte differs**:

| `[0x800CCED3]` (card-manager terminal state) | recomp | oracle |
|---|---|---|
| value | **0x12 (18)** | **0x02 (2)** |

`0x12` → "This data is invalid"; `0x02` → "No save data found".

### Layer 1 — card-manager state machine (overlay, interpreted) @ `0x800eab60`
```
a0 = [s0+6]
v1 = 0x8001c1ac(a0)            ; <-- card-status routine, returns 0/1/2/3
beq v1, 1  -> [0x800CCED3]=1
beq v1, 0  -> 0x800eabd0       ; status 0 = "in progress, keep doing card steps"
beq v1, 2  -> [0x800CCED3]=2   ; "no save data found"   (ORACLE lands here)
beq v1, 3  -> [0x800CCED3]=0x12; "this data is invalid"  (RECOMP lands here)
```
So the divergence is the return value of `0x8001c1ac`: **recomp 3, oracle 2.**

### Layer 2 — `0x8001c1ac` (STATIC boot-EXE; "wait for card outcome")
```
s1 = 3                               ; retry count
LOOP:
  v0 = 0x800698e4(s5<<4)             ; A0(0xAC) BU card op (issue/step)
  if (v0 == 0) goto DEC
  s0 = 0x8001c824()                  ; poll the 4 card events; which fired?
  if (s0 == 0) goto DONE(v1=0)       ; event0 (IOE) = step complete -> caller continues
DEC: s1--; if (s1) goto LOOP; v1 = s0
DONE: v0 = 2; if (v1 != 2) return v1 ; v1==2 -> success path also returns 2
```
Returns 0 while steps complete (IOE), and a terminal 1/2/3 when an outcome event fires.

### Layer 3 — `0x8001c824` (STATIC; poll 4 events) — **the timeout happens here**
```
s0 = 0x0003d08f                      ; ~250511 spin iterations
LOOP:
  if (TestEvent([0x800E2F70])) return 0   ; event0 handle 0xF1000000
  if (TestEvent([0x800E2F74])) return 1   ; event1 handle 0xF1000001
  if (TestEvent([0x800E2F78])) return 2   ; event2 handle 0xF1000002
  if (TestEvent([0x800E2F7C])) return 3   ; event3 handle 0xF1000003
  s0--; if (s0) goto LOOP
  return 3                            ; <-- TIMEOUT fallthrough returns 3
```
`TestEvent` = `0x80069e44` = BIOS B0(0x0B).

### The 4 events (kernel EvCB @ `0xA000E028`, ptr at `[0x000120]`, 0x1C bytes each)
All class `0xF4000001` (SwCARD), mode 0x2000:

| event | spec | meaning |
|---|---|---|
| 0 | 0x0004 | **EvSpIOE** (per-step I/O complete) |
| 1 | 0x0100 | EvSpNEW (new card) |
| 2 | **0x2000** | **EvSpTIMOUT** → status 2 → "no save data found" |
| 3 | 0x8000 | EvSpUNKNOWN/error |

### Runtime evidence (recomp)
- During the card op, **only event 0 (IOE) ever fires**. DeliverEvent (`0xBFC116FC`, `sw status,4(evcb)`)
  is called from BIOS card handler `ra=0xBFC0C038`; the game's `0x8001c824` TestEvent **does catch it**
  (consume `0xBFC119F8` reset 0x4000→0x2000, `ra=0x8001C854`) and returns 0 = "keep going".
- **Events 1/2/3 never fire.** The terminal outcome event (oracle uses **event 2 = EvSpTIMOUT**) is
  **never delivered** on the recomp.
- Measured the game's TestEvent call count for one card-check: **1,073,646** (= 250511×4 ≈ the full
  spin) → `0x8001c824` **genuinely times out** → returns 3 → `0x8001c1ac` returns 3 →
  `[0x800CCED3]=0x12` → **"invalid"**.
- Oracle on the *same* empty card: `[0x800CCED3]=0x02`, screen "No save data found" → its BU path
  delivers **EvSpTIMOUT (event 2)**.

### `[0x80070cc4]==0xFF` was a RED HERRING
An earlier menu-entry gate (`if [0x80070cc4]==0xFF then phase=1`) looked causal but the **oracle has the
identical `0xFF`** — it is *not* the divergence. The divergence is purely the missing terminal card event.

---

## The narrowed root cause (what we believe)
On an empty card, the game performs a BU "load save file" op. The real hardware path eventually fires
**EvSpTIMOUT** (event 2) — interpreted by the game as "no save data found." Our recompiled BIOS/BU card
library performs the per-step reads (firing IOE/event0 correctly) but **never delivers the terminal
EvSpTIMOUT event**, so the game's busy-wait exhausts and the routine falls through to its `return 3`
("unknown/invalid") path.

`0x800698e4` is the BU op the loop issues — a 3-instruction BIOS thunk:
```
0x800698e4: li t2, 0xA0 ; jr t2 ; li t1, 0xAC   => A0(0xAC)
```
(`0x80069e44` similarly = B0(0x0B) TestEvent; `0x80069934` = B0(0x4E).) We have not yet confirmed which
documented BU/card function `A0(0xAC)` is, nor traced where the real path would call
`DeliverEvent(0xF4000001, 0x2000)`.

## Two competing hypotheses for the last hop
1. **Recompiled BIOS/BU library bug** — the BU file-read's not-found/timeout branch fails to
   `DeliverEvent(SwCARD, EvSpTIMOUT)`. Possibly a recompiler mistranslation of a BIOS card routine, or a
   missing timer/timeout interaction. (User-preferred direction.)
2. **SIO/memcard MMIO simulation** — when the game reads the *data block of a non-existent/free file*,
   real hardware NAKs / stops responding so the BIOS times out and fires EvSpTIMOUT; our emulated card
   instead *responds* (free-block data), so the BIOS keeps seeing IOE and never times out. This matches
   "Tomba only sends 0x42 and is fine; MMX6 drives a fuller sequence." We were told earlier "don't touch
   sio.c reads — byte-perfect," but byte-perfect *successful* reads don't preclude a missing *NAK/timeout*
   path for commands MMX6 issues that Tomba never does.

## Specific questions for the reviewer
1. What is **A0(0xAC)** in the SCPH1001 BIOS (and the surrounding `_card_*`/`_bu_*` callbacks
   A0(0xA7..0xAC))? Which call should ultimately `DeliverEvent(0xF4000001, EvSpTIMOUT=0x2000)`?
2. In the Sony BU library, on **"file not found on a present, formatted card,"** what is the canonical
   chain that ends in **EvSpTIMOUT** vs **EvSpIOE**? Is EvSpTIMOUT driven by a kernel **timer/RootCounter**
   (so a missing/!ticking timer in our sim would suppress it), by a card SIO **NAK/no-response**, or by a
   BU-internal retry-exhaustion counter?
3. Is it expected that reading a **free (0xA0) directory block's data frames** elicits a **NAK/timeout**
   from real hardware (vs a normal data response)? i.e. is hypothesis #2 (SIO response) plausible?
4. Any known recompilation foot-guns around the BIOS event/`DeliverEvent`/`TestEvent` path or the
   card IRQ acknowledge that would deliver IOE but drop the timeout event?

## How to reproduce / inspect (our side)
- Recomp debug server TCP **4490**; oracle (psxref/Beetle) TCP **4380**; identical JSON protocol
  (`read_ram`, `press`, `screenshot_file`, `wtrace_add`/`wtrace_dump`, `fntrace_arm`/`fntrace_dump`,
  `dirty_*`, etc.).
- Repro over TCP: at the continue menu, press CROSS (`0xBFFF`) to select "Load from a MEMORY CARD";
  the card-check re-runs and `[0x800CCED3]` goes to `0x12`. Dismiss (CROSS) returns to the menu to retry.
- `tools/mdis.py <addr> <len>` disassembles live RAM (MIPS-I, LE). `tools/oshot.py` screenshots the oracle.
- EvCB dump: ptr at `[0x000120]` → array of 0x1C-byte EvCBs `{class,+4 status,+8 spec,+0xC mode,+0x10 fn}`;
  TestEvent returns 1 iff status==0x4000 (EvStALREADY) and resets it to 0x2000 (EvStACTIVE).

---

# SESSION 2 UPDATE — narrowed to card-driver EvSpTIMOUT (timeout) delivery

Traced the oracle (psxref) directly (it supports `trace_arm`/`wtrace_dump` on phys addrs, and
`save_state`). New findings:

## Oracle vs recomp at the card op (same empty card)
- Card-manager struct `0x800CCED0` writes are **byte-for-byte identical** between oracle and recomp
  EXCEPT the terminal state byte: `[0x800CCED3]` = **0x02 (oracle)** vs **0x12 (recomp)**.
- EvCB ptr `[0x000120]=0xA000E028`, size `0x268`, and event handles `[0x800E2F70..7C]=0xF1000000..3`
  are **identical** on both. So same events, same EvCB layout, same game/BU code.
- (Oracle EvCB status writes don't appear in its trace because the BIOS writes the EvCB via KSEG1
  `0xA000E028` uncached and the Beetle trace hook only logs cached/KUSEG writes; the KUSEG card-mgr
  struct at `0x800CCED0` is logged fine.)

## The decisive new signal: TIMING + the EvSpTIMOUT trigger
- **Oracle card op spans ~435 frames (~7 s)** (frame 6447→6882) before it sets `[0xCCED3]=0x02`.
  i.e. it **waits out the card timeout** and the BIOS delivers **EvSpTIMOUT (event 2)**.
- **Recomp card op is ~50 frames** and **never delivers EvSpTIMOUT** — the game's iteration-based
  poll `0x8001c824` (250511×4 ≈ 1.07M TestEvent calls, measured) **exhausts** and returns 3.
- The card driver delivers EvSpTIMOUT at **`0xBFC0B630`** (`jal 0xBFC0BFF0; ori a1,zero,0x2000`),
  **gated on its per-slot pending state `[0xA0009F20 + idx*4]` being nonzero** at a periodic check
  (`0xBFC0B620: lw t7,-24800(t7); 0xBFC0B628: beq t7,zero,skip`). `0xBFC0BFF0` =
  `DeliverEvent(0xF4000001 /*SwCARD*/, a1=spec)` and also clears the three per-slot arrays
  `[0xA0009F20/F28/F30 + idx*4]`. (Other deliveries seen: a1=0x8000 UNKNOWN @ B534/B5DC,
  a1=0x0100 NEW @ B588, a1=0x2000 TIMOUT @ B630.)
- Post-op driver state: oracle `[0xA0009F20..]` fully cleared; **recomp leaves `[0xA0009F28]=0x03`**.

## Refined root-cause statement
The recompiled BIOS card driver never satisfies the EvSpTIMOUT condition: on real HW the card op
stays *pending* long enough that the periodic timeout check (gated on `[0xA0009F20+idx*4]`) fires
**EvSpTIMOUT**; on the recomp the op completes/clears too early (or the game's tight BIOS busy-wait
exhausts before the frame-paced timeout fires), so EvSpTIMOUT is never delivered and the game
falls through to its `return 3` ("invalid"). **Not the SIO byte layer** — all SIO transactions are
normal (directory reads sectors 0x00–0x15 + presence probes, all ACK; the 2 `abort_other` 3-byte
txns are normal card-presence probes).

## Sharper questions for the reviewer
1. In SCPH1001, what drives the **card EvSpTIMOUT** (the `0xBFC0B630` path)? Is `[0xA0009F20+idx*4]`
   a retry/pending counter decremented per **SIO IRQ (#7)**, per **VBlank/RootCounter**, or per
   card-driver tick? i.e. is the timeout **wall-time/frame-paced** or **transaction-count-paced**?
2. Given a present, formatted, but **empty** card, what exactly keeps the BU op pending for ~7 s on
   real HW so the timeout fires (vs completing)? Is the BU library issuing reads that the real card
   eventually stops ACKing, or is it a fixed retry budget?
3. Classic recomp foot-gun check: if a recompiled BIOS **busy-wait** (here `0x8001c824`, ~1.07M
   TestEvent calls) advances emulated cycles but the **card driver's pending counter only decrements
   on an event the recomp never schedules** (or decrements differently), EvSpTIMOUT won't fire. Does
   this match a known PSX BIOS card-timeout structure?
4. Is the recomp leaving `[0xA0009F28]=3` (vs oracle 0) a symptom of the divergent path or a red
   herring from the earlier failed attempt?

## Concrete next probes (recomp side, no oracle needed)
- Read `[0xA0009F20..0xA0009F34]` *during* the recomp card op (re-trigger; wtrace phys 0x9F20..0x9F34)
  to see whether the pending state is ever set nonzero and what clears it / when.
- Disassemble the function containing `0xBFC0B630` (find its entry + caller) to learn how/when the
  timeout check runs and what increments/decrements `[0xA0009F20+idx*4]`.
- Find the setter of `[0xA0009F20+idx*4]` (card op start) and the per-IRQ/per-VBlank decrement.
