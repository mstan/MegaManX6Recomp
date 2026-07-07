# Tweaks Pre-Bake — Design Doc

**Status:** design / scoped, not yet implemented.
**Goal:** make MMX6 Tweaks (and per-game option sets generally) apply **without any
player-side compilation**. Applying/toggling a tweak must be a config change, not a
GCC/TCC/sljit run.

This is a generalization of the existing **widescreen opt-in** pattern
(`psxrecomp-v4/WIDESCREEN.md`): *one build serves every state, byte-identical when a
feature is off; a runtime flag/value engages it.* Read WIDESCREEN.md first — the
recompiler machinery here mirrors it almost line-for-line.

---

## 1. The problem

The pure-Python Tweaks engine (`tools/tweaks_engine.py`) already builds a patched disc
image with no AutoHotkey. But the launcher's "Build" then says *"regen with
game.tweaks-XXXX.toml, then rebuild the runtime"* — a full recompile of the ~44 MB
generated C. **A player cannot be expected to run a compiler to change a setting.**

A recomp fundamentally must re-translate any patched *executable code*. The way out is
not to make the player compile, but to **pre-bake the code variants once (dev side) and
select them at runtime**, and to **parameterize values from a config file** so numbers
never touch the binary at all.

---

## 2. The two mechanisms (the core decision)

| Kind of tweak | Mechanism | Player cost | Dev cost |
|---|---|---|---|
| **Real code / behavior change** (boss AI, mechanics, New Game init logic) | **Guarded variant** baked into the binary, selected by a runtime flag | flip a flag in a toml | one-time regen bakes all variants |
| **Value tweak** (damage numbers, lives cap, orb speed, stat tables) | **Parameterization** — value read from a toml/param file at runtime | edit a toml line | none for data-section values; one-time regen to insert the read for instruction-immediates |
| **Large art asset** (mugshot / title-screen art) | disc-image patch (Python engine) or later a side-file asset loader | swap disc image | none |

**Slogan:** *real code changes become options; value tweaks become parameters.*

---

## 3. Measured scope (why this is small)

Inventory over all **332 interactive options** (`tools/tweaks_engine.py` writelist per
option, EXE-offset mapped against `generated-tweaks/SLUS_013.95_full.ranges`). SLUS
loads at `0x80010000`, size 522240 B, disc range `0x1D91FF60..0x1D9B2630`; 12,308
recompiled functions total.

| Bucket | Count | Recompiler work |
|---|---|---|
| **1 — Disc data** (outside the SLUS EXE: art, game-data tables) | 94 | none — patch disc / poke RAM |
| **3 — SLUS data-section** (tables/values, not instructions) | 15 | none — value param / boot poke |
| **2 — SLUS code** (instructions) | 158 | guarded variant (one-time bake) |
| *(no-op-when-toggled-alone — New Game combos; mostly bucket 2)* | 65 | — |

- **~109 options (buckets 1+3) need ZERO recompiler work** — pure config / disc data.
- Bucket 2's 158 options touch only **105 recompiled functions** (of 12,308),
  ~3,600 code bytes. That is the entire one-time pre-bake surface.

Regenerate the numbers: the inventory scripts are ad-hoc (scratch); rebuild from
`tweaks_engine.build_writelist` per option + the `.ranges` `R <lo> <len>` code map +
the SLUS geometry above.

---

## 4. Architecture facts this relies on (verified in the framework)

- **SLUS code bytes are BAKED.** The dispatcher (`SLUS_013.95_dispatch.c`,
  `main_psx.cpp:908-934`) runs the compiled `func_XXXXXXXX(CPUState*)`, not the RAM
  bytes. Changing code bytes on the disc has no effect without regen. ⇒ code tweaks
  need the guarded-variant bake.
- **SLUS data-section bytes are LOADED into RAM at boot** by the recompiled BIOS's EXE
  loader (`main.cpp:1545`), exactly like hardware; compiled code reads them via
  `cpu->read_*`. ⇒ data values can be changed at runtime with **no regen** (patch the
  disc, or poke RAM at boot).
- **Instruction immediates** (`lui/addiu` constants, scalars in a `li`) are frozen into
  the emitted C. A "value" that is actually an immediate is a code change ⇒ needs the
  one-time parameterization regen. (Same reason widescreen cull constants are a
  recompiler feature, not a disc patch — `WIDESCREEN.md:161-169`.)
- **Every basic-block leader is re-enterable** (CPS; `code_generator.cpp:2034-2094`), so
  a guarded variant can branch at block entry with canonical `cpu->gpr[]`/RAM state.
- **`overlay_mode` already emits "same address, alternate code, fall through to vanilla
  on mismatch"** (`code_generator.cpp:801-828`) — the closest existing model for
  guarded variants.

---

## 5. The `[tweaks]` config surface (single source of truth)

One toml drives everything except the baked code bodies. The launcher writes it; the
runtime reads it at boot. "The file decides what's active."

```toml
[tweaks]
# on/off CODE-behavior tweaks -> which baked guarded variant runs (g_tweak_flags bits)
flags = ["boss_indestructible_orbs", "mach_dash_hold_release", "newgame_unlockcode"]

# VALUE tweaks that are instruction immediates -> recompiler emits g_tweak_param[index]
[[tweak.param]]  name = "orb_explosion"   index = 3   value = 4
[[tweak.param]]  name = "max_lives"       index = 7   value = 99

# VALUE tweaks in the DATA section (game reads from RAM) -> poked into RAM at boot
[[tweak.poke]]   addr = 0x800A1234  size = 1  value = 0x63   # game just reads this
[[tweak.poke]]   addr = 0x8009F008  size = 2  value = 0x0100 init_store_pc = 0x800xxxxx
                                                             # game re-writes it -> intercept the store
```

- `flags` — bit set into `g_tweak_flags`; selects baked guarded variants.
- `[[tweak.param]]` — fills `g_tweak_param[index]`; the recompiled code reads it (see §6).
- `[[tweak.poke]]` — written into guest RAM after EXE load. If the game *recomputes* the
  value each boot, add `init_store_pc` and the recompiler intercepts that store (the
  existing `game_options.toml` mechanism, §7). If the game only *reads* it, a plain boot
  poke suffices.

This mirrors `game_options.toml` (`config_loader.cpp:762-795`); reuse its parser,
range-validation, and `format_version` guard.

---

## 6. Recompiler pass (gen-time, one-time dev regen)

New `CodeGenConfig` fields parsed from `[tweaks]` (model on the widescreen site-lists,
`config_loader.h:372-484`, `config_loader.cpp:624-747`), consumed in:

**A. Guarded code variants** — in `generate_function` / `translate_basic_block`
(`code_generator.cpp:1224`, `:1976`): for a function/block that a `flags` tweak patches,
emit **both** instruction streams:
```c
if (g_tweak_flags & TWEAK_BOSS_INDESTRUCTIBLE_ORBS) { /* translate(patched bytes) */ }
else                                                { /* translate(vanilla bytes) */ }
```
Feed the patched bytes from the tweaks metadata (§8). Byte-identical to today when the
flag is off. Overlapping options patching the *same* instruction are a true conflict —
the tool's radios/PreReq/exceptions already enforce exclusivity; bound + assert on it.

**B. Value parameterization** — in `translate_instruction` (`code_generator.cpp:743`,
the widescreen `psx_ws_x_margin()` site pattern): for a `[[tweak.param]]` site, emit the
immediate as a runtime read:
```c
cpu->gpr[rt] = g_tweak_param[3];   // was: cpu->gpr[rt] = 4;
```
Default value = the vanilla immediate ⇒ identity when the toml doesn't override it. After
this one regen, the value is pure config forever.

**C. Data-section pokes** — no codegen; handled purely at runtime (§7). Optionally a
store-intercept (`init_store_pc`) reusing `psx_game_option_store`
(`code_generator.cpp:992-1008`).

---

## 7. Runtime loader (extend `game_options.c`)

Add a `g_tweak_flags` (u64/bitset) + `g_tweak_param[]` array + a poke list as
`main.cpp` file-scope globals (alongside `g_video_aspect_*`, `g_ws_*`, etc.,
`main.cpp:147-266`). At boot, after the EXE loads:
1. Read `[tweaks]` from `game.toml` (default) then `settings.toml`/`game_options.toml`
   (launcher override, `main.cpp:2244-2273`).
2. Set `g_tweak_flags` from `flags`; fill `g_tweak_param[]` from `[[tweak.param]]`.
3. Apply `[[tweak.poke]]` into guest RAM; register `init_store_pc` intercepts for the
   recompute cases (reuse `psx_game_option_store`, `game_options.c:134-141`).
Persist/restore + range-validate exactly like `game_options.c` (`atexit` save,
`format_version` guard).

---

## 8. Metadata bridge (Python → recompiler)

`tools/tweaks_engine.py` already produces, per option, the exact `(EXE offset, patched
bytes)` writelist. Add an emitter that, per option, classifies each write (EXE-addr map +
`.ranges`) and emits the `[tweaks]` inputs:
- code-range write, on/off option → a `flags` entry + the `(addr, patched bytes)` for the
  guarded variant.
- code-range write that is an immediate in a value option → a `[[tweak.param]]` site.
- data-section write → a `[[tweak.poke]]` (with `init_store_pc` if the game recomputes).
- outside-SLUS write → disc-image patch (unchanged; the Python engine already does it) or
  a large-asset side-file loader (future).

This is the concrete low-risk first piece — it's pure Python over machinery that exists.

---

## 9. Launcher / player flow

**Build** stops meaning "stage a rebuild." It becomes:
1. Write the `[tweaks]` toml (flags + params + pokes) — the tweaks tab already collects
   the selection; map it through the metadata bridge.
2. For bucket-1 large art only: emit/point at the patched disc image (Python engine).
3. Launch. No compile, and for value/code tweaks no disc image either.

The dev ships **one** pre-baked binary (the superset with all 105 guarded functions +
the parameterized reads). Players never compile.

---

## 10. Generic abstraction

Factor widescreen + tweaks into one **opt-in feature-codegen** layer:
a *feature* = `{ flag, site-list, emit-strategy }`, strategy ∈
`{ guarded-block, identity-helper, param-read, data-poke }`.
- widescreen = `identity-helper` features (cull/backdrop/bg2d sites).
- tweaks = `guarded-block` (code) + `param-read` (immediates) + `data-poke` (data) features.
`WIDESCREEN.md` + this doc become the "feature-set" subsystem; future per-game option
sets register the same way.

---

## 11. Phasing

1. **Metadata bridge** (Python): emit the `[tweaks]` table from the engine's writelists +
   the code/data classifier. Low risk, no framework changes; validates the bucket split.
2. **Runtime loader**: extend `game_options.c` for `g_tweak_flags`/`g_tweak_param`/pokes.
   Get bucket-1/3 (values + data + art) working with **zero codegen** — that's ~109
   options playable with no recompile immediately.
3. **Recompiler guarded variants + param reads**: the one-time-bake codegen pass for
   bucket 2 (105 functions). Biggest piece; mirrors the widescreen codegen feature.
4. **Launcher**: Build → write toml (+ disc for art); flags/param UI from the tweaks tab.
5. **Generalize** into the feature-set abstraction; retrofit widescreen onto it.

---

## 12. Open questions / risks

- **Recompute-vs-read per value**: which data-section values does the game re-initialize
  each boot (need `init_store_pc` intercept) vs just read (plain poke)? Determine per
  value; disc-patch is the always-safe fallback.
- **Same-instruction conflicts** (two options patching one instruction): rare; enforce
  via the tool's existing exclusivity, assert at gen time.
- **Binary size**: +105 guarded function variants — negligible vs 12,308 functions / 44 MB.
- **Large art via disc image** is still a 600 MB file per art selection; a runtime
  "load asset from side-file" path would remove that (future, not required for v1).
- **Immediate detection**: reliably distinguishing "value immediate" from "code change"
  per site needs the decoder's view of the patched bytes; the metadata bridge must be
  conservative (treat ambiguous as a guarded variant).
