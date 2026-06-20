# Mega Man X6 — 16:9 Widescreen (true wider FOV)

Status: **in progress** on branch `feat/mmx6-widescreen` (psxrecomp + MegaManX6Recomp).
Elective "diverge-from-native" enhancement, opt-in like Tomba. Renderer/runtime +
one gen-time recompiler hook (no gameplay logic changes).

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
