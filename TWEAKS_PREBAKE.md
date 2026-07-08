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

Refined by `tools/tweaks_prebake.py` (Phase 1, built) — it splits "SLUS code" into
value-immediates (parameterizable) vs logic (guarded) via a per-word MIPS check (a
diff confined to bytes 0-1, the immediate field, is a value; a diff in bytes 2-3,
opcode/rs/rt, is logic):

| Bucket | Count | Recompiler work |
|---|---|---|
| **disc** — write outside the SLUS EXE (art, game-data) | 90 | none — disc-image patch |
| **poke** — SLUS data-section value (game reads from RAM) | 15 | none — boot-time RAM poke |
| **param** — value that is an instruction immediate | 28 | none per change (one regen to insert the read) |
| **guarded** — SLUS code logic change | 130 | one-time bake (guarded variant) |
| *(no-op-when-alone — New Game/combo context)* | 66 | mostly guarded in context |

- **105 options (disc + poke) work with the CURRENT binary** — pure config / disc patch.
- **+28 param + 130 guarded** unlock with **one** dev-side regen (which inserts the
  param reads AND bakes the guarded variants), after which all are runtime config.
- The guarded surface is only **95-105 recompiled functions** of 12,308. **39 of ~95
  functions are touched by >1 guarded option** — but mostly composable (different
  byte regions, e.g. New Game init), not same-instruction conflicts.
- Finding: **the entire Boss Attacks tab (17 options) is disc-data** — zero recompile.

Regenerate anytime: `python tools/tweaks_prebake.py summary` (buckets) /
`manifest --out m.json` (per-option) / `selection '{...}'` (emit the `[tweaks]` toml).

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

## 7a. Phase 2 status — BUILT + mechanism-validated

`runtime/src/tweak_runtime.{c,h}` + `main.cpp` wiring + a `tweaks` debug command +
`tweaks_prebake.py state` (emits the state-file grammar). Validated live over the
debug server (own instance on a private `--debug-port`, never the default — another
game may hold it): state parsed (`have=1`), `flags`/`param`/`poke` loaded, a 512-byte
table correctly chunked to 32-byte poke lines (`n_poke=17`), `applied=1` at game
start, and a scratch poke **landed in guest RAM** (`0x80180000` → `deadbeef`), proving
`psx_write_byte` from the apply path works.

**Poke-timing finding (the recompute-vs-read gotcha, confirmed):** the apply runs
*post-frame* once `fntrace_is_game_started()` is true, i.e. after the game has already
executed its entry frame. A data value the game **reads/copies during that first boot
frame** (e.g. DefOptions) is consumed *before* the poke lands, so its RAM reads vanilla.
Three fixes, in preference order:
1. **Apply BEFORE game entry** — poke right after the BIOS EXE loader fills the data
   section into RAM but before the first game instruction. Overwrites the loaded
   defaults before any game code reads them; makes every "game reads it" value work.
   Needs a pre-entry hook (the EXE-handoff point near `main.cpp:2611`), not the
   post-frame `fntrace_is_game_started` gate. **Recommended.**
2. **Store-intercept** (`init_store_pc`, the existing `game_options` mechanism) for
   values the game *recomputes* each boot — the recompiler rewrites that store to
   substitute our value. Needed only for recomputed values, not plain reads.
3. Disc-image patch (always works; the fallback the Python engine already produces).

Values the game reads LATE (menus, New Game) already work with the current post-frame
apply. Improving to (1) is the next Phase-2 refinement.

## 7b. Runtime loader (extend `game_options.c`)

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

## 8. Metadata bridge (Python → recompiler) — **BUILT (Phase 1)**

`tools/tweaks_prebake.py` classifies every option's writes (`tweaks_engine.build_writelist`
→ EXE-addr map → `.ranges` code map → per-word MIPS immediate check) into
disc / poke / param / guarded, and emits:
- `summary` — the bucket counts (validates the split).
- `manifest --out m.json` — per-option `{bucket, n_disc/poke/param/guarded, funcs}`.
- `selection '{...}'` — the `[tweaks]` toml fragment for a build: `[[tweak.param]]`
  (addr/index/value, with the vanilla immediate), `[[tweak.poke]]` (addr/size/value),
  the guarded-variant sites (addr, vanilla→patched word, owning func), and a note of the
  disc-patch runs.

The guarded sites carry `(word_addr, vanilla_word, patched_word, func)` — exactly the
input the Phase-3 recompiler pass needs to translate the patched bytes under a flag. The
disc/poke/param outputs are what the Phase-2 runtime loader consumes.

Caveat: per-option classification toggles each option ALONE, so New Game/combo options
that need context show as `no-op`; the real per-build classification (the `selection`
command) is correct. The param-vs-guarded split is conservative — an ambiguous word
(any diff outside the immediate field) is `guarded`.

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

---

# 13. SUPERSEDING DESIGN — dual-source function-variants (2026-07-08)

**Status:** §§2–12 above describe the shipped Model-1 subset (values + inline guards +
poke/disc/art), which capped code tweaks at the ~24–28 *control-flow-clean* options and
left the 104 control-flow-injection options stranded. This section supersedes that scope.
It is the AUTHORITATIVE plan going forward. The Phase-1/2/3 machinery below it still ships
and is reused wholesale; this only changes how the **104 CF options** get baked and, with
them, the whole delivery model. Product decisions are LOCKED (see auto-memory
`tweaks_delivery_model_locked`).

## 13.1 Delivery model (locked)
- **Two builds.** *Stock* = pure vanilla recompile (no tweak machinery). *Tweaks* = ONE
  superset holding the vanilla base + every option's code; player mixes freely; **all-off =
  true vanilla.**
- **Apply = RELAUNCH** (no mid-session toggling). Toggle in launcher → flags/values file →
  relaunch. Code/value tweaks instant; art tweaks = one-time few-min `.tweaks` disc rebuild.
- **Non-destructive disc (invariant):** never patch the stock ISO in place; always
  regenerate `<name>.tweaks.{iso,bin,cue}` FROM stock; `resolve_tweaks_disc_sibling` loads
  it when present, stock otherwise. Stock is read-only forever.
- **Why dual-source at all:** a static recomp bakes code at build time, so every selectable
  code behavior must be pre-baked. Recompiling the *patched* ISO alone is all-or-nothing —
  it discards the vanilla substrate, so un-selected tweaks can't fall back to vanilla.
  Mix-and-match REQUIRES holding vanilla + each variant and selecting at runtime.

## 13.2 The clean reduction (kills the "2^68" fear)
Every acediez patch is one (or both) of:
- **Case A — edit to an EXISTING function F** (an inline logic change, OR a hook that
  overwrites an in-F instruction with a `j/jal` into an injected routine). F exists in
  vanilla; patched F differs. → emit F with a **guarded entry**: vanilla body vs patched
  body, chosen by `psx_tweak_on(bit)`. Multiple tweaks on one F → ordered chain.
- **Case B — an INJECTED routine G** placed in scratch/nop-padding (did not exist in
  vanilla). → compile G **unconditionally** as its own func at its entry address. G is only
  ever reached via a Case-A hook, so it is dead code when that hook's bit is off. **No guard,
  no variant.**

The apparent `2^68`/`2^71` hot functions (CharAdd/Unlockables) are **Case B**: scratch
arenas (vanilla = `sll $0` = nop) where many options' injected routines live. They were
mis-attributed to a shared *edited* function. Under this reduction they cost **one func
each**, not `2^k`. So the only combinatorial surface is Case-A functions touched by >1
COMBINABLE tweak — the bounded ~27 (see 13.6).

## 13.3 Delta-ingestion pipeline (chosen build strategy — internal, invisible to product)
No physical "superset ISO" is built (that would collide in shared scratch). Instead:

**Producer (Python, extend `tools/tweaks_prebake.py`):** from each option's writelist emit a
bake manifest entry:
- `bit` (deterministic sorted-var → flag bit, as `_guarded_catalog` already does),
- Case-A sites: `[(func_entry, word_addr, van_word, pat_word)]` (reuse `classify_writes`;
  a site whose patched opcode `_is_cf` is a hook, still Case A — it edits F),
- Case-B routines: `[(entry_addr, bytes)]` — a contiguous injected run whose vanilla bytes
  are nop/scratch (or outside exec ranges) and that a Case-A hook targets; `entry_addr` =
  the hook's jump target.
- (values/art/poke unchanged — existing buckets.)

**Recompiler (C++, extend `load_tweak_bake` + `code_generator.cpp`, `tweak_sites.h` in
recompiler/src):**
1. Add every Case-B `entry_addr` to the function worklist and translate it from PATCHED
   bytes → an ordinary `func_<entry>`. Its internal absolute refs (`j/jal`, `lui/ori`
   address pairs, data pointers) are fixed up by the normal translator because it's compiled
   at its true guest address — **linear, not combinatorial**.
2. For each Case-A function F: synthesize each patched variant body by applying the relevant
   option deltas onto F's vanilla bytes, then translate BOTH; emit F as
   `if (psx_tweak_on(bitF)) { <patched> } else { <vanilla> }` at function entry (chain for
   combos). Dispatch at ENTRY avoids all mid-block CFG-guard surgery.

## 13.4 Runtime (unchanged — reuse Phase-2/3 verbatim)
`g_tweak_flags[4]` (256-bit) + `psx_tweak_on(bit)`; `tweaks.state` grammar `flag <n>` /
`param <i> <v>` / `poke <addr> <hex>`, read at boot (relaunch model), applied at the
`s_game_started` gate (fntrace.c) with `dirty_ram_text_bless` for pokes. Disc via
`resolve_tweaks_disc_sibling`.

## 13.5 Combo handling for shared Case-A functions (~27 funcs, 2–5 tweaks each)
Ordered entry chain; radio/PreReq mutex ⇒ ≤1 active (use `_radio_siblings`). For genuinely
combinable pairs on the same F, the producer enumerates the REACHABLE combinations (mutex
graph prunes them) and emits a combined patched body per reachable combo, selected when all
its bits are on. Bounded: worst real case is single-digit combos per function.

## 13.6 Mapping evidence (2026-07-08) — recompute if stale
`tools/tweaks_map_pressure.py` + `tools/tweaks_probe_hot.py` (run from repo root; reuse
`tweaks_prebake.py` internals). Findings: **132 code-tier options
(28 inline, 104 CF)** touching **93 distinct funcs** → **61 single-tweak (trivial),
~27 with 2–5 combinable, the rest are Case-B scratch arenas** (the `2^68` artifact).
Value tier (~43 param/poke) + the 28 inline already mix at runtime today.

## 13.7 Milestones
1. **Prove one CF option end-to-end** — a single hook: delta → Case-B routine emitted as a
   func → Case-A guarded entry in F → validate `off = vanilla`, `on = tweak`. De-risks the
   whole subsystem before scaling.
2. **Scale to all 104** + the ~27 combo functions.
3. **Launcher (stb — see memory `launcher_rmlui_stb_divergence`)**: tweaks menu → flags/
   values file + trigger `.tweaks` art-disc rebuild.
4. **Full-catalog validation** (per-option + representative combos; user does final play).

## 13.8 Code sites to touch
- Framework: `recompiler/src/code_generator.cpp` (`translate_instruction`/`_raw`,
  `generate_function`), `load_tweak_bake` + `codegen_config`, `recompiler/src/tweak_sites.h`;
  runtime `tweak_runtime.{c,h}` (already supports the grammar); `main.cpp`
  `resolve_tweaks_disc_sibling`; `fntrace.c` apply gate.
- Game: `tools/tweaks_prebake.py` (add Case-A/Case-B manifest + `bake` extension),
  `tweaks_engine.py`/`tweaks_resolver.py` (writelists — DONE, AHK-parity), the art producer
  `artdisc`.

## 13.9 Risks specific to dual-source
- **Case-B entry discovery:** an injected routine may sit in the tail-padding of an existing
  func range (so `func_of` mislabels it) — the producer must declare its entry explicitly
  from the hook target, not infer from `.ranges`.
- **Delta application correctness:** synthesizing a patched function body = applying the
  right subset of deltas to vanilla bytes; must match the byte-identical Python engine
  output (oracle: `tweaks_engine.apply_bin`). Cross-check the synthesized bytes vs the
  engine's patched image before translating.
- **Binary size / compile time:** +~93 guarded bodies +N injected routines on top of the
  34–42 MB superset; expected negligible but measure (prod-emit is on).
- **Same-word combinable conflict** (two combinable tweaks write the SAME instruction word
  differently): rare after mutex; where real, needs the combined-body path (13.5), not a
  chain. Producer must flag these explicitly.
