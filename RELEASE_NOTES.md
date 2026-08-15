# MegaManX6Recomp v1.0.8

v1.0.8 is a patch release for the save-state and rewind controls reported in
GitHub issue #18.

## Save-state and rewind controls

The save-state menu now shows controller-first PlayStation-style glyph prompts
for slot selection, load, save, and back. The Cross glyph has been cleaned up so
it reads as a thin button icon instead of a blocky X.

The rewind filmstrip now uses the same glyph prompt style for seek, load, and
close, so the in-game instructions are consistent across both overlays.

F7 remains the default save-state menu key and F8 remains the default rewind
key. The old F1-F12 quick-slot behavior is not restored.

## Fast-forward and FPS readout

Manual fast-forward is bounded by default so the game visibly advances while it
is held. Advanced users can still set `PSX_FAST_FORWARD_SPEED=max` to restore
the old unbounded behavior, or use values from 2 through 16 for a specific cap.

When the FPS readout is enabled, interpolation builds now distinguish game
speed from display refresh in the title and OSD instead of presenting one
ambiguous FPS value.

## Launcher settings

The PlayStation hotkeys section is kept reachable in the settings layout at the
reported launcher window size, instead of being pushed below the visible area.

## Compatibility

Save files, memory cards and savestates from v1.0.7 continue to work. Your disc
image is unchanged and is still not included.
