# Mega Man X6 — 16:9 Widescreen (true wider FOV)

Status: **validated prototype** on branch `feat/mmx6-widescreen` (psxrecomp + MegaManX6Recomp).
Elective "diverge-from-native" enhancement, opt-in like Tomba. Renderer/runtime +
one gen-time recompiler hook (no gameplay logic changes).

---

## Stage-entry stale reveal cleanup (2026-07-09 spike)

The native-wide compositor persists like VRAM, but its synthetic side margins
have no PS1-owned pixels underneath them. If MMX6 does not redraw those columns
on the first frames of a stage transition, the margins can retain pixels from
the previous scene. This is distinct from the tile-ring freshness bug below.

The prototype adds `[widescreen] clear_reveal = true` plus the exact MMX6
`[widescreen.bg2d] init_func = "0x800269f4"` stage-generation hook. The hook
clears both synthetic margins once when a background generation begins. The
later finite-map side mask was removed: at the intro boundary it could not
distinguish authored layers entering the reveal from stale ring slots and
produced a moving black trim over real stage art. The conservative policy now
prefers a possible stale reveal tile over suppressing valid content. The
canonical 320-wide image is untouched. The health/ability assembly is identified
by its stable packet pool `[0x000E3400,0x000E4100)` and corner-anchored by side.

Screenshot validation on OpenGL (1280-wide window):

- 16:9 stage entry: no black boundary mask over authored stage pixels.
- 16:9 gameplay: HUD at the true left edge; valid right reveal intact.
- 21:9 gameplay: larger invalid left reveal black, HUD at the true ultrawide
  edge, canonical/right region intact. A 20-frame motion burst stayed live.

The launcher exposes 21:9 as a separate `Ultrawide (EXPERIMENTAL)` option only
when `[widescreen] offer_ultrawide = true`; 16:9 remains its own toggle.

---

## 1. The premise correction (read this first)

An earlier handoff claimed MMX6 "over-draws" the world to X=512 and we just had to
**reveal** the GPU-clipped overscan. **That is false.** Proven 2026-06-20 with pixels:

- Built a `wide_full` debug command (`debug_server.c` + `sw_wide_dump_full` in
  `gpu_sw_renderer.c`) that dumps the ENTIRE native-wide compositor surface — both
  vertical-double-buffer y-bands and both reveal margins. The compositor mirror
  rasterizes EVERY submitted primitive full-width (no 320 clip), so it shows exactly
  what the game draws.
- In a 320-wide gameplay scene, the 426px surface holds real content only in columns
  **[43,383] (~340px)** with **~43px BLACK margins each side**. Title/full-screen
  images fill fine (not camera-windowed).
- The raw SPRT16 vertex X spans [0,512], but that is a **scrolling tilemap encoded with
  a per-tile screen position**; the actual on-screen extent is **~4:3 + ~10px bleed**.

So MMX6 renders a TRUE 4:3 view. There is **no hidden FOV to reveal**. "Real 16:9 from
the stage perspective" requires making the engine RENDER MORE. (Also: no off-the-shelf
MMX6 widescreen code exists — the PS1 widescreen-patch scene widens 3D games by hooking
the GTE projection, a no-op for a 2D sprite engine.)

---

## 2. The lever (found + proven)

The background tilemap renderer is **`FUN_800270d0`** (called per layer from a 3-layer
driver loop at `0x80026dd0`; per-layer struct stride `0x54`). Decompiled inner loop:

```c
uVar19 = 0x21;                 // 33 columns
if (_DAT_80090d6a == 0)
    uVar19 = 0x15;             // 21 columns  (= 320/16 + 1)
...
do {                           // outer: 16 rows (uVar18 < 0x10)
  do {                         // inner: uVar19 COLUMNS
    ... emit one 16x16 tile SPRT into the OT (skips empty tiles) ...
    if (999 < sprite_count) return;   // hard cap — watch for truncation
  } while (uVar16 < uVar19);
} while (uVar18 < 0x10);
```

- Column count `uVar19` = **21 (`0x15`) normally, 33 (`0x21`) when `_DAT_80090d6a != 0`**.
- That global (`0x80090d6a`) is read **only** by this renderer and by the screen-mode
  setter's dedup check (xrefs to 0x80090d6a: READ 0x80012894, WRITE 0x800128c0).
- The screen-mode setter `0x80012890` (a0 = mode): a0==0 → width `0x140`=320; a0!=0 →
  width `0x200`=512 (the engine's hi-res mode, used by the **title screen**). The width
  lives in a SEPARATE var (`0x8009b79c`); the flag and the width are independent.

**Proven live (2026-06-20):** poking `_DAT_80090d6a = 1` during 320 gameplay (without
the resolution change) drew 33 columns → the right black margin went **37px → 0**, real
coherent stage content, no corruption (`ws_rightfill_proof.png`). With the compositor's
+53 centering the player sits dead-center. The left ~53px (≈4 columns) stays black,
because the 33 columns extend **rightward** from the 320 camera's left edge:

```c
start_col       = scrollX >> 4;        // first tile column
start_screen_x  = -(scrollX & 0xf);    // sub-tile start (≈0)
// loop draws uVar19 columns rightward from there
```

A RAM poke can't add LEFT columns: the single `scrollX` drives both `>>4` (tile index)
and `&0xf` (sub-pixel), so subtracting from it shifts existing content (desyncs from
objects) instead of adding aligned columns. → needs a code hook.

---

## 3. The plan (ChatGPT-validated; option #1 of 3)

Keep camera / gameplay / collision / HUD at native **320**. Render extra BG columns on
BOTH sides, widen only the object render-cull, and present through the existing 426-wide
sidecar compositor. (Forcing the full 512 screen mode during gameplay was ranked
high-risk — it changes framebuffer/display assumptions without fixing camera/cull/HUD —
and is rejected.)

### 3a. Background — hook `FUN_800270d0` to add columns both sides

Replace the three setup values so existing columns stay pixel-aligned with objects while
new columns are prepended (left) and appended (right). Target the centered 16:9 window
`screen ∈ [-53, 373)` (426px = 320 + 2·53):

```c
const int wide_left = 53, wide_width = 426;
int render_left_world = camera_x - wide_left;
int start_col       = floor_div(render_left_world, 16);
int start_screen_x   = start_col*16 - camera_x;        // ≤ 0
int column_count     = ceil_div((wide_width - wide_left) - start_screen_x, 16);
```

Gated on the widescreen-2D flag; identity (21 cols, original start) at 4:3. The renderer
is GAME code (recompiled), so this is a **gen-time recompiler hook** at the three
instructions that set the col count, start screen x, and start tile col — the same
site-list mechanism Tomba's widescreen uses (`[widescreen]` config + `code_generator.cpp`).
A **regen** is required.

**Exact hook PCs in `FUN_800270d0`** (combined scrollX is in `v0` at 0x80027174):
- **col count** `s6`: `0x800271d4 li s6,0x15` (the 320 path; `0x800271d0 li s6,0x21` is the
  flag!=0 path). Force the widened count here (≈29–33).
- **start tile col** `v1`: `0x80027188 andi v1,v1,0x3f` → `0x8002718c sw v1,0x0(sp)`. Adjust
  `v1 = (v1 - LEFT) & 0x3f` (LEFT≈4 columns).
- **start screen x** `s4`: `0x800271a0 sra s4,v0,0x10` (= sign-extended `-(scrollX&0xf)`).
  Adjust `s4 -= LEFT*16`.

Net: shift start left by LEFT columns + raise the count so the loop covers `[-53,373)`,
existing columns staying pixel-aligned with objects.
Watch the `if (999 < sprite_count) return;` cap (33 cols × 16 rows × 3 layers ⇒ more
tiles; empty tiles are skipped, but verify no truncation — bump the guest cap via the
same hook if needed).

### 3b. Objects — widen the screen-X spawn/cull

Enemies/objects are culled to the 320 window, so the revealed margins show background but
no actors. Find the per-object screen-X activation/draw cull (Capcom 2D engines usually
compare `objX − camX` against a half-width / margin constant) and widen it by ±53 (the
framework already has `psx_ws_x_margin()` for exactly this, used by Tomba's
`[widescreen.cull]`). Verify widening doesn't trip off-screen-activation or object-pool
bugs. **TODO: locate the cull sites.**

### 3c. Present / centering — already done

The native-wide compositor (mode 2) presents 426 from a separate wide surface (textures
sampled from VRAM, canonical VRAM untouched), offset +53 = player centered. Vertical
double-buffer handled (both y-bands maintained identically). No change needed.

---

## 4. Opt-in / extensibility (DONE)

`[widescreen] full_2d = true` in `game.toml` opts a pure-2D sprite game into the
widescreen present path (it never emits the 3D sprite-tag hook the gameplay detector
keys on). End-to-end, runtime-only, verified engaging widescreen from config alone:
`config_loader.{h,cpp}` `ws_full_2d` → `gpu_ws_set_full_2d()` (`gpu.c`/`gpu.h`) →
`ws_game_mode()`. `main.cpp` applies it at config load. Env `PSX_WS_FORCE_2D=1` kept as a
test override. Pair with `[video] aspect_ratio = "16:9"` (settings.toml / launcher); at
4:3 the flag is inert.

The BG-widen + cull hooks will be gated on the same widescreen state, so the whole
feature is one opt-in toggle.

---

## 5. Engine facts / addresses

- BG renderer: `FUN_800270d0`; 3-layer driver at `0x80026dd0` (per-layer struct stride
  `0x54`, base region around `0x80097202` for the per-layer scroll shorts; per-layer
  "parent" byte at `0x80097...` selects a combined scroll).
- Column-count flag: `_DAT_80090d6a` (halfword). Screen-mode setter: `0x80012890`
  (a0=mode). Display width var: `0x8009b79c` (0x140=320 / 0x200=512).
- 999-sprite OT cap inside the renderer.
- Display: vertical double-buffer — `display_y` & `draw_offset_y`/`draw_area_top`
  alternate 0↔240 each frame; `draw_area_left = 0` for both buffers. Width varies by
  scene: gameplay 256/320, title 512 (offset/extra scale with width).
- Tiles are DMA'd from a libgpu ordering table (~`0xbe000`); emit PC = BIOS DMA
  `0xbfc02b7c`. wtrace `ra` = `0x80026df0` (the game OT-fill driver) is how the renderer
  was located.

## 6. Tooling (psxrecomp debug server, port 4490)

- `wide_full` — dump entire compositor surface (both DB bands + margins) to PNG.
- `wide_shot` — dump the displayed-band 426 present.
- `gpu_state` — `ws` block (mode/nw_extra/x_margin/game_mode/present_native_43) + display
  geometry.
- `gpu_frame_dump frame=N` — per-command op/src/pc (attribute prims).
- `wtrace_range`+`wtrace_dump` — writer-func + `ra` attribution (how the renderer was
  found through the BIOS-DMA indirection).
- `write_ram` — byte poke (proved the column flag).
- `/tmp` py helpers: wsmon / wsflip / wshot / wdiff / spritex (recreate if cleared).

## 7. Next steps

1. Build the gen-time renderer hook (3-value widen on `FUN_800270d0`), gated on
   widescreen-2D. Regen MMX6, validate the left margin fills + stays aligned.
2. Locate + widen the object screen-X cull; validate enemies populate the margins.
3. Verify the 999-sprite cap; bump if truncating.
4. Mid-stage symmetry + HUD check; broader scene validation; GL renderer path.
5. Wire the launcher toggle; user sign-off before any master merge (exploratory branch).

---

## 8. BG budget-overflow artifact + host-side reveal-column fix (2026-06-21)

### Status of §7
- Step 1 (BG widen): DONE + committed. `ws_mmx6_left_cols()`=4 → 21→29 cols.
- Step 2 (object cull): **NON-ISSUE — closed.** Proven via rings + Ghidra: none of
  the 4 object render funcs (FUN_800232d4/239cc/241d4/23ed8) have a screen-X cull;
  the SW renderer mirrors every prim to the full-width wide surface; a 120-frame
  census shows object prim origin-X spans [-50,363]. Objects already populate both
  margins. The old "[-4,316]" was the sprite-only `spritex` helper missing quad objects.
- Step 3 (999 cap): **THIS IS THE ACTIVE BUG.**

### The artifact (16:9-only)
Vertical column-aligned BG glitches — void (black) columns + stale tiles shifted
up-left, worse in dense stages. ROOT CAUSE: BG renderer `FUN_800270d0` emits 16×16
tile prims into a double-buffered packet buffer (driver sets base **0x800B91C0**,
stride **0x4000** = `bufidx<<14` at 0x80026db0-dcc → exactly **1024 tile slots/buf**),
guarded by per-frame cap **`if (999 < iRam1f80011c) return`** (counter scratchpad
**0x1F80011C**, reset at driver 0x80026d68), accumulated across all 3 BG layers.
The 21→29 widen (+38%) pushes BG tiles over 1024 in dense stages → renderer returns
early → dropped tiles/layers = void; transient unstreamed widened ring cols = stale
strips. Measured **925 BG tiles/frame** mid-stage (cap 1000). Buffers are PACKED
(buf0→buf1→object OT ~0x800C4xxx) so bumping the cap in-place overruns into the
object OT = RAM corruption. 4:3 stays 21 cols (~670 tiles) → 16:9-only.

### Fix (ChatGPT-recommended #1, user-approved 2026-06-21): host-side wide-only reveal columns
Constraint: elective opt-in; **4:3 byte-identical for this and ANY game**; no game-
behavior change. Plan:
1. **Revert the guest column widen** — `psx_ws_mmx6_bg_cols/startcol/startx` (gpu.c)
   → IDENTITY so the guest renders its native 21 cols (buffer/OT/cap untouched, can
   never overflow). **Keep** `psx_ws_mmx6_bg_stream_left/right` (ring stays populated
   for the reveal cols). Runtime-only revert (no regen for this part).
2. **Emit the ±4 reveal columns host-side into the wide surface only.** Reveal tiles
   live in the MARGINS (disjoint from native content) so they only need to be
   BACKMOST — objects draw over them via the normal OT mirror. Emit all 3 layers
   (in layer order, for inter-layer transparency) right after the per-frame wide-band
   clear (`sw_wide_clear`, gpu_sw_renderer.c:1578), reading the guest's LIVE scroll +
   tilemap ring + attr table.

### Decode chain (gathered 2026-06-21)
- Per-layer scroll: layer struct `0x800971f8 + layer*0x54`, scrollX +0xa, scrollY +0xe,
  "parent" byte +0x52 (if ≥0, add parent layer's scroll for linked layers).
- start_col = scrollX>>4, start_screen_x = -(scrollX&0xf); rows: scrollY>>4 / -(scrollY&0xf).
- Tilemap ring: `ring16[(col&0x3f)*2 + (row&0x1f)*0x80 + layer*0x1000 + 0x800a21b8]`;
  entry 0 = empty (skip). bit 0x4000 = flipX, 0x8000 = priority/page group (+3).
- Tile attr word: `*(u32*)((entry&0x3fff)*4 + [0x1F80000C])`; if (attr>>0x18)==0xFF skip.
  SPRT16 fields: u0=(attr>>0xc)&0xf0, v0=(attr>>0x10)&0xf0, clut16=((attr&0xf000)>>6)+0x7980
  +((attr>>0x18)&0x40)*0x10 | (attr>>8)&0xf.
- **TPAGE INDIRECTION (the wrinkle):** tile texpage is NOT in the packet; it's selected by
  the OT slot `layer*0x11 + (attr>>0x18 & 0x3f)` (each OT slot carries a pre-set DR_TPAGE).
  So a from-scratch decoder must also replicate the OT-slot→tpage table.
- SW raster: `sw_draw_textured_rect(x,y,16,16,u,v,clut_x,clut_y,texpage)`; `raster_textured_rect`
  (gpu_sw_renderer.c:1207) takes an RTarget → call with `rt_wide()` ONLY (texels always come
  from native VRAM). GP0 SPRT16 decode reference: gpu.c:1650 (clut_x=(clut&0x3F)*16,
  clut_y=(clut>>6)&0x1FF, texpage=current_texpage()).

### Two implementation strategies
- **A. Faithful from-scratch decode** in the runtime — must also RE + replicate the
  OT-slot→tpage table. More code, more coupling, error-prone. REJECTED.
- **B. RE-INVOKE the guest renderer into a scratch GPU context (CHOSEN, confirmed buildable).**
  **CONFIRMED 2026-06-21: the BG renderer IS a callable compiled C symbol `func_800270D0(CPUState* cpu)`**
  (generated/SLUS_013.95_full.c:68304; a0=layer=cpu->gpr[4]; already a CPS jal target at :67985).
  So the runtime can re-invoke it directly. Sketch:
  1. **Scratch reveal-pass mode:** add runtime state `gpu_ws_bg_reveal_pass(side)`; the existing
     hooks `psx_ws_mmx6_bg_cols/startcol/startx` read it and, in reveal mode, return JUST the 4
     reveal cols for the given side (left: startcol-4/startx-64/cols=4; right: startcol+21/
     startx+21·16/cols=4) instead of the 29-col widen. Native (non-reveal) path = identity after
     the revert (step 1 of §8 fix), so guest renders 21 cols, never overflows.
  2. **Redirect packet storage, snapshot OT heads:** save scratchpad 0x108 (BG packet ptr) + 0x11c
     (counter); point 0x108 at a host scratch packet buffer, 0x11c=0. The OT base is hardcoded
     (0x80098C18 + bufidx·0x198), so DON'T redirect it — instead SNAPSHOT the OT head words before
     the pass and RESTORE them after (the reveal packets land in the scratch buffer; the OT heads
     transiently point into it).
  3. For each layer 0..2 and side L/R: set reveal mode, `cpu->gpr[4]=layer; func_800270D0(cpu);`
     (~6 calls). Reveal tiles = 4·16·3·2 ≈ 384 slots, well under the baked-in 999 cap → no truncation.
  4. **Traverse the (scratch-populated) OT exactly as the GPU DMA would** — per slot, follow the
     linked list in Z order; DR_TPAGE prims set current tpage, SPRT16 prims draw — but rasterize
     **wide-only** (`raster_textured_rect(rt_wide(), …)`). This consumes the OT-slot→tpage naturally
     (same as real DMA), so NO tpage re-derivation. Reuse/extend the runtime's existing OT-DMA+GP0
     decode with a wide-only flag.
  5. Restore OT heads + 0x108 + 0x11c. Hook point: right after `sw_wide_clear` (per-frame wide band
     reset) so reveal tiles are backmost; objects then draw over them via the normal mirror.
  Risk: func_800270D0 re-entrancy/restore correctness — verify it only touches 0x108/0x11c + OT +
  (read-only) tilemap/scroll, and that the scratch pass leaves guest state byte-identical.

### CHOSEN FIX (2026-06-21, user-approved): BUFFER RELOCATION (#2), not host-side
Host-side (Strategy A) was BUILT but is the WRONG approach — re-deriving the engine render
got two things wrong: (1) tpage via clut-cache = garbled tiles; (2) reading the tile ring at
the GP0 fill (frame start) is BEFORE the streamer refreshes it = stale margins (reintroduced
the bug the stream hooks fixed). Code left INERT (g_mmx6_hostside default 0). The engine's OWN
guest-widen render is correct + fresh; its ONLY flaw is the 1024-slot buffer overflow. So KEEP
it and enlarge the buffer.

**Plan (gen-time, gated on widescreen, 4:3 byte-identical):**
- **Free RAM PROVEN** (2026-06-21, 133-sample wtrace occupancy union over 0x80090000-0x80200000):
  big unwritten heap→stack gap **[0x800EA000, 0x801B9000) = 828KB**. Use e.g. RELOC_BASE
  0x80140000 (mid-gap), STRIDE 0x6000 (1536 slots/buf, was 0x4000=1024), 2 bufs = 0xC000.
  Red-zone with guard bytes + per-frame assert (ChatGPT); also re-check across boss/menu/
  transition scenes (this proof was one gameplay stretch). Tool: /tmp/freeram2.py.
- **Hook 1 — buffer base** at PC **0x80026DCC** (`write_word(gpr[1]+0x108, gpr[3])`; gpr[3] =
  0x800B91C0 + bufidx·0x4000): wrap `gpr[3] = psx_ws_mmx6_bg_bufbase(gpr[3])` → recover
  bufidx=(gpr[3]-0x800B91C0)>>14, return RELOC_BASE + bufidx·STRIDE when active, else gpr[3].
- **Hook 2 — cap compare** at PC **0x80027278** (`gpr[2] = ((int32)gpr[3] < 1000)`, gpr[3] =
  BG tile counter 0x1F80011C): wrap `gpr[2] = psx_ws_mmx6_bg_undercap(gpr[3])` → counter < 1450
  when active (≤ STRIDE slots), else < 1000.
- **⚠ TEMPLATE WRINKLE (must handle):** FUN_800270d0 only updates xy/uv/clut/tpage + read-modify
  -writes packet+7 bit1; the SPRT **opcode (packet+7) + color (packet+4..6) are a TEMPLATE** set
  up ONCE at the OLD base (NOT by FUN_800269f4 = tile-ring loader). A relocated buffer has GARBAGE
  opcodes. FIX: seed the relocated buffer's templates — verify the template is uniform across slots
  (read packet+4..7 live from 0x800B91C0), then have the bufbase hook one-time-fill RELOC_BASE
  slots with it (guard with a done-flag); OR find + also-relocate the template-init writes.
- Both hooks are [widescreen.bg2d]-style register wraps (same mechanism as bg_cols/startcol/startx);
  add the 2 PCs to MMX6 game.toml + helpers in gpu.c (+ recompiler emit if the wrap shape is new) →
  **REGEN**. Helpers IDENTITY at 4:3 (4:3 + any other game byte-identical).

### Overflow policy (ChatGPT) + validation
- The scratch render gets its OWN budget; native path is untouched, so no overflow on the
  real buffer. If the scratch path nears its own cap, drop the FARTHEST reveal cols first
  (clip the reveal) — never abort a layer.
- Gate everything on the widescreen flag (identity at 4:3 → byte-identical for any game).
- Validate: 320 region pixel-identical to pre-change (diff wide_full center band); margins
  fill coherently; no void/stale across dense stages (re-check prims/frame ≤ native cap).
- Don't size any cap from math — instrument max BG tiles across stages first.
