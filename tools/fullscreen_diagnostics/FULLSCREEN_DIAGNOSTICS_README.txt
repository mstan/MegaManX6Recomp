MegaManX6Recomp fullscreen diagnostic build
================================================

This test build includes three tentative display fixes:

1. Borderless is now a monitor-sized, undecorated window. It does not set the
   SDL/driver fullscreen flag.
2. Exclusive now requests an explicit desktop-sized display mode.
3. The mouse cursor is hidden while a fullscreen game window has focus and is
   restored when focus is lost.

How to test Borderless
----------------------

1. Run MegaManX6Recomp.exe and choose Borderless in Display settings.
2. Launch the game and reproduce the problem. Alt+Tab away and back 3-5 times.
3. While the game is still running, double-click:
      COLLECT_FULLSCREEN_DIAGNOSTICS.bat
4. Attach the new fullscreen-diagnostic-*.json file to the GitHub issue.
5. In your comment, say whether:
   - the long black flash still happens;
   - the mouse cursor remains visible over the game;
   - Borderless minimizes or changes the monitor's display mode.

Please repeat with Exclusive if possible and attach its separate JSON report.

Privacy
-------

The report contains Windows version, computer model, GPU/display driver and
monitor identifiers, display resolution/refresh/DPI, safe video settings, and
the game's recent window/focus/display events. It deliberately excludes disc,
BIOS, save, controller, and user-directory paths. You can inspect the JSON in
Notepad before uploading it.
