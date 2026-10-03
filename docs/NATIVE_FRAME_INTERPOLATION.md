# Native frame interpolation

Enable **Frame Interpolation** under **Mods** and choose display refresh or a
fixed output rate. The feature defaults off and uses OpenGL. Game logic,
animation, input, VBlank and audio retain their normal cadence.

The SLUS-01395 renderer redraws world sprites and three background layers with
intermediate 16.16 positions. Absolute screen-space sprites keep their current
coordinates; animation cells use the current game frame. Addresses and sprite
bank identities match history, and gaps over eight ticks or moves over 96 pixels
per tick retain the current position.

The replay captures the CPU, RAM and scratchpad at `80025FB0`, then reruns the
world wrapper through `80025FD0` inside the framework's machine/VRAM sandbox.
Background positions are applied at `80026DA4`, after initialization and before
streaming. Sprite positions are applied at `800232D4`.

At the main loop's `80060964` VSync call (`ra=80012104`), the original wait runs
once before passes are planned. Completing that intercepted function avoids a
second wait. This allows the preceding display generation to be promoted before
the next one is queued.

Replay draws into the pending display bank. Both SDK DRAWENV and the game's
linked E3/E4/E5 prefixes must select that bank; retaining the original prefixes
clips away the scene and produces black intermediate images. Prefix payloads
change only inside replay, while their OT links remain intact. Fades and other
packets added after the world wrapper are captured as bounded OT prefixes and
reattached above the rebuilt world in their original buckets. Unrecognised or
cyclic prefixes decline replay.

`tests/test_mmx6_frame_interpolation.cpp` exercises the actual plugin callbacks:
sprite/camera midpoints, stable HUD coordinates, current animation cells,
identity changes, large moves, stale history, SDK ordering, bank-specific
prefixes, late-overlay links, rejected cycles and the single original wait.
Live runs use `PSX_RENDER_PASS_VERIFY=1`; phase image dumps additionally verify
that intermediate images contain the rendered scene.

Final live checks exercised 4:3 and 16:9 rendering, including the attract-mode
world, title fades and screen-space overlays. The combined verification run
completed 718 extra passes and state checks with zero mismatches, VRAM leaks,
watchdogs or guest-span failures. The 120 Hz, 16:9 production check completed
4,626 extra passes, promoted 2,360 frames and presented 4,443 replay images;
extra passes averaged 1.32 ms at the 1080p setting. This run disabled the costly
state-verification readbacks. Phase captures in
`analysis/native-production-wide/phases/` show actual intermediate sprite
positions with intact backgrounds and overlays. These are local smoke checks,
not an exhaustive stage audit or a frame-rate guarantee for every machine.

The same production run then reached the playable opening stage with working
Start/dialogue input, movement, jumping and shooting. HUD and dialogue overlays
remained present in replay images. By the end of
`analysis/native-playable-final/`, cumulative passes reached 47,729 with zero
aborts, discarded passes, VRAM leaks, watchdogs or span failures; average extra
pass cost was 1.39 ms. This later count includes the preceding title/demo run.

The framework uses base `9c1e716a61e0b01bbcd4e6d50f4940dfc1829895` plus local
shared interpolation/UI/journal changes. Recomp-ui is aligned to `03d58aa`.
The previous owner runtime edits are preserved in `analysis/owner-*` backups
and the framework stash. Their growing SDL presentation texture, disc-before-
mod activation and preservation of mod state are already present in this base.
The owner's recomp-net checkout remains unchanged. The local validation build
is `build-native-interpolation/mmx6-runtime.exe`, with netplay disabled for testing.
