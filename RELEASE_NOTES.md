# MegaManX6Recomp v1.0.7

v1.0.7 is a patch release for launcher hotkeys and audio settings.

## Hotkey rebinding fixes

Launcher hotkey rebinding now applies to the PSX runtime actions players can
actually use:

- Fullscreen
- Fast-forward
- Volume up / down
- FPS readout
- Rewind
- Save states menu

Defaults no longer continue firing after a hotkey is rebound. For example,
rebinding fast-forward from Tab to Q makes Q fast-forward and stops Tab from
doing it.

The unsupported Reset, Pause, and Toggle Renderer rows have been removed from
the PlayStation hotkey list.

## Visible FPS readout

The FPS readout now appears in the in-game OSD instead of only changing the
native window title. This makes it visible in fullscreen and in window modes
where the title bar is not visible.

## Audio sample rate persistence

Changing the launcher audio sample rate now persists correctly. Selecting
48 kHz and reopening the launcher should keep 48 kHz selected.

## Rewind build contract

Rewind remains available in this release. The framework now requires the rewind
snapshot backend whenever Rewind is exposed, so future builds cannot ship a
visible F8 rewind hotkey that silently does nothing.

## Compatibility

Save files, memory cards and savestates from v1.0.6 continue to work. Your disc
image is unchanged and is still not included.
