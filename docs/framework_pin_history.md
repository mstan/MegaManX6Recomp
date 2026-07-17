# Framework pin history (historical)

The `psxrecomp` framework used to be pinned via this hand-maintained
`psxrecomp-v4.pin` file. That mechanism has been **replaced by a real git
submodule**: the framework commit this repo builds against is now recorded as
the `psxrecomp-v4` submodule pointer (see `.gitmodules`). Bump it the normal
way:

    git -C psxrecomp-v4 fetch && git -C psxrecomp-v4 checkout <new-sha>
    git add psxrecomp-v4 && git commit -m "bump psxrecomp-v4 to <new-sha>"

At migration time the pointer moved to master `d2006e0`, superseding the pin
recorded below.

The notes below are kept only as a historical changelog of which framework
build each release was cut against.

---

# Pinned commit of github.com/mstan/psxrecomp (the shared framework) used to
# build this repo. Bumping this is a deliberate, reviewable change — psxrecomp
# is a separate repo evolving on its own cadence. Update via:
#   git -C ../psxrecomp rev-parse master > /tmp/sha && \
#     sed -i "s|^sha=.*|sha=$(cat /tmp/sha)|" psxrecomp-v4.pin
branch=master
sha=c3f4aab
# Bumped 2026-07-10 (MMX6 true-wide completion, merged framework c3f4aab): stage init clears synthetic
#   reveal margins once, but the uncertain finite-map packet mask was removed
#   after screenshot validation exposed black trim over authored stage art.
#   Targeted HUD packets now anchor by side (player left, enemy right), and the
#   intro overlay actor cull carries an aspect margin plus a 32px guard. Launcher
#   retains distinct opt-in 16:9 and 21:9 modes. OpenGL user-validated.
# Bumped 2026-07-09 (GL/VK mirrored-sprite sliver fix, ISSUES #8): 03c3f79 =
#   010a281 + exactly four runtime-only commits (merged to psxrecomp master as
#   184a18a; pinned at the pre-merge head so the tree stays 010a281-lineage —
#   it excludes master's stb-launcher link blocker and any post-010a281
#   emitter drift). Fix: modern-GPU center-sampled interpolation floored one
#   texel low on u/v-DECREASING (X/Y-flipped) 2D sprites — thin stray
#   sprite-colored lines around right-facing/crouching X, effect sprites, the
#   wheel mechaniloids; GL/VK only, software was always correct. Two fix sites
#   (gpu.c converts axis-aligned mirrored quads to rect_scaled, so the poly
#   AND rect paths), then the whole uv model extracted to one shared gpu_uv.h
#   for GL/VK/SW so the backends can't drift again. Also: always-on display
#   ring (display_ring_get/aux) for frame-exact cross-renderer forensics.
#   Validation: frame-exact GL-vs-software diff 3707px -> 0px in the gameplay
#   area at the deterministic attract frame; MMX6 GL USER-VALIDATED clean;
#   cross-title gate Tomba GL boot+attract PASS against this exact tree.
#   Runtime-only; codegen (MIPS->C) UNCHANGED -> NO regen, overlay caches valid.
# Bumped 2026-07-03 (renderer arc merged): psxrecomp master 010a281 = 4cc757f +
#   the OpenGL black-frame-flicker fix (exact pending-upload rects, ISSUES #7 —
#   the reason MMX6 shipped software), native-wide 16:9 GL perf/band fixes, the
#   Vulkan (3rd) backend, and the R3 validation sweep. Runtime-only; codegen
#   (MIPS->C) UNCHANGED -> hash 0cec55ab holds, NO regen, overlay caches valid.
#   Validation: MMX6 GL 4:3 PASS incl Rainy Turtloid (flicker gone); GL 16:9 +
#   Vulkan = YELLOW (rain-area perf). Vulkan hidden by default (dev/CLI-only);
#   widescreen EXPERIMENTAL in launcher. MMX6 shipping default still SOFTWARE —
#   flip to opengl + close ISSUES #7 is the pending follow-up. No release cut.
#   See psxrecomp ENHANCEMENTS.md R1/R1b/R2/R3.
# Bumped 2026-07-02 (card "not found" ROOT FIX + loud dispatch): psxrecomp
#   master 4cc757f = c3c43e6 + 30 ROM-resident kernel-table seeds (A0:2B
#   memset @0xBFC02B8C was undiscovered -> dispatch silently no-op'd ->
#   MMX6 save-scan died before firstfile; card I/O + events were always
#   correct). BIOS regen 4406->4439 dispatch entries; CONTINUE lists+loads
#   saves (user-validated). Unknown dispatch is now FATAL by default
#   (PSX_FAIL_FAST_UNKNOWN_DISPATCH=0 to opt out). runtime.cmake gains
#   EXE_NAME: this repo builds mmx6-runtime.exe so Tomba2/other dev sweeps
#   of psx-runtime.exe no longer kill MMX6 instances. BIOS image regen
#   required after pulling (seeds are recompile-time input).
# Bumped 2026-07-02 (HLE tier + coherent-regen stability): psxrecomp master
#   c3c43e6 = 496d1db + launcher "Skip PSX BIOS" toggle removal (boot skip is
#   automatic now via bios_hle=true in the shipped game.toml).
#   496d1db = 0ecf552 + stale-shard guard (13c5e0c) + opt-in HLE BIOS tier
#   (582aecc: call-HLE B0 event family + HLE boot shell-skip replacing
#   fast_boot snapshots; LLE stays dev default + oracle) + tier wiring
#   (496d1db). Codegen hash 0cec55ab (emitter changed -> images + caches
#   regenerated together). The coherent regen cleared the card-LOAD
#   regressions ("not found"/"data invalid" — staleness class). Releases ship
#   bios_hle=true (user directive 2026-07-02).
# Bumped 2026-06-25 (overlay cache unification + ws_cull DLL fix): psxrecomp
#   master e7f7fb6 = 1915b5c + two framework fixes for the overlay path. (1) The
#   runtime injects PSX_OVERLAY_CACHE_DIR/PSX_OVERLAY_CAPTURES so the autocompile
#   WRITE cache + READ captures are always the loader's canonical <exe>/cache --
#   the cache location can never drift from where the loader reads (it was a
#   per-game-config footgun across all titles). (2) The overlay DLL preamble
#   defines psx_ws_cull_sltiu (only matters for GTE titles with auto_screen_x;
#   MMX6 is 2D so this is a no-op here, but it ships the unified framework).
#   Runtime/tooling only; codegen unchanged (cache stays cg4_7db781d9).
# Bumped 2026-06-25 (tcc overlay tier replacing sljit + Xbox controller fix):
#   psxrecomp master 1915b5c = c7939b7 + the toolchain-free TinyCC overlay tier and
#   the SDL HIDAPI-Xbox input fix. Tier order is now static > gcc shard > tcc shard >
#   (sljit, deprecated/gated-off) > interp; backend "auto" picks gcc when a gcc
#   toolchain is present (dev/prod shard authoring) else tcc. The tcc tier is fully
#   self-contained: the runtime spawns a bundled overlay_toolchain/ (embedded Python
#   + TinyCC + recompiler + compile_overlays.py + headers) -> no system python/gcc on
#   a player box. Backend policy extracted to overlay_backend.{c,h}. Xbox fix:
#   SDL_HINT_JOYSTICK_HIDAPI_XBOX=1 (Xbox One/Series pads were dead with RAWINPUT off
#   + HIDAPI-Xbox off; PS5 worked). v0.0.2-alpha ships the bundle; regenerated against
#   this master (codegen cg4_7db781d9).
# Bumped 2026-06-21 (launcher allow_hybrid + turbo-hint removal): psxrecomp master
#   c7939b7 = bb1d990 + per-game [controller] allow_hybrid (hides the launcher's
#   "Hybrid" pad mode, leaving Analog | D-Pad — MMX6 hard-requires a DualShock) and
#   removal of the "much faster loading, audio plays through" turbo-loads subtext.
#   Launcher/config only, no regen (config_loader parses the flag; emitters unchanged).
# Bumped 2026-06-21 (MMX6 widescreen BG ring-freshness fix): psxrecomp master
#   bb1d990 = 1951dc2 + the MMX6 16:9 reveal-margin "staircase" fix. The widened
#   BG drew 4 extra tile columns/side but the engine streamed only 1 col/side/frame,
#   so on scene entry / fast scroll the inner reveal columns held stale tiles ->
#   up-left staircase (NOT the packet-budget overflow). Fix re-streams the whole
#   widened window each frame from a byte-exact clone of the engine's tile-ring fill
#   (validated 0 mismatch / 1113 cells), gated native-wide so 4:3 is byte-identical.
#   Also: removed the 2-col reveal cap (full 53px reveal restored). Runtime-only for
#   the fix; the [widescreen.bg2d] bufbase/cap relocation hooks (parked, gated off)
#   ride along for the separate dense-stage budget concern. USER-VALIDATED clean 16:9.
# Bumped 2026-06-19 (turbo default ON + launcher UI): psxrecomp master 1951dc2 =
#   15f5d60 + turbo-loads defaults to ON (mute removed, so it is the right default:
#   fast loads, audio plays through, guest timing preserved) and the launcher hint
#   updated. Runtime/launcher only, no regen.
# Bumped 2026-06-19 (GL sprite Z-order fix): psxrecomp master 15f5d60 = dbfd92f
#   + the OpenGL opaque-batch draw-order fix. The textured-prim batch split colour
#   by the per-texel STP bit across the whole batch (for the PSX mask bit), which
#   reordered overlapping OPAQUE prims (player drew in front of an AP item-block's
#   letters / behind a save post on GL only). Opaque batches now draw colour in one
#   ordered pass + a stencil-only mask fixup; semi prims keep the blended two-pass,
#   isolated per prim. USER-VALIDATED on Tomba GL. Runtime-only, no regen.
# Bumped 2026-06-19 (turbo-loads fast-load model): psxrecomp master dbfd92f =
#   prior + turbo-during-loads as the production fast-load path. game.toml ships
#   disc_speed="1x" (authentic CD timing) + turbo_loads=true: the guest runs every
#   authentic frame at host speed during CD loads (all guest timing preserved, audio
#   intact), so real load time shrinks with zero timing breakage. Also: CD response
#   arbiter + authentic command latencies (dormant at 1x, for accelerated modes) and
#   no turbo audio mute. Runtime/config only, no regen. Supersedes 035a9fa9681873887e0de94d65369bbcd3e87d7d.
# Bumped 2026-06-09: psxrecomp master = Bug B frame-pacing fix (ffc1521) +
# release hygiene (035a9fa). MMX6 verified against it: builds clean
# (build-master), boots BIOS -> game to the X-vs-Zero intro cutscene,
# frame-exact 59.94 fps pacing (was ~56), 0 dispatch misses, no watchdog
# false-positives over a 2-minute soak. ISSUES.md #2 (input) still open.
