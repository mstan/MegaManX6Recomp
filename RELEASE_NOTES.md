# v1.0.4-borderless-test.1

This is a Windows diagnostic pre-release for investigating issue #2. It is not
intended to replace v1.0.3 yet.

Tentative fixes:

- Borderless uses a monitor-sized undecorated window without the SDL fullscreen
  flag, preventing drivers from treating Borderless like Exclusive.
- Exclusive requests an explicit desktop-sized display mode.
- The cursor is hidden while a fullscreen game window has focus and restored
  when focus is lost.
- Alt+Enter and Ctrl+F track the applied tri-state mode correctly.

Diagnostics:

- The runtime keeps a bounded history of window, focus, minimize, restore,
  display-change, pixel-size, and fullscreen transition events.
- Reports include SDL/Win32 window flags and styles, logical and pixel sizes,
  monitor bounds, desktop/current modes and refresh rates, DPI, and cursor state.
- Run `COLLECT_FULLSCREEN_DIAGNOSTICS.bat` while the game is open to create an
  attachable JSON report. The collector excludes disc, BIOS, save, controller,
  and user-directory paths.

This diagnostic package intentionally omits the prebuilt overlay cache. Its
bundled self-contained toolchain fills the cache during play, so first visits
to game areas may load more slowly than in v1.0.3.
