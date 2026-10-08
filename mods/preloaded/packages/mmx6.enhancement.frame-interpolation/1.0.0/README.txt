Mega Man X6 Frame Interpolation

This default-disabled mod redraws intermediate world-sprite and scrolling-
background positions above 60Hz through the stable mmx6.frame-interpolation
plugin id. It replaces the earlier blending of completed images.

It is presentation only. Guest VBlank, game logic, timers, and audio keep their
stock cadence, so this changes how smooth the game looks and not how fast it
runs. Animation cells use the current frame, HUD elements keep their screen
positions, and scene changes or large jumps discard interpolation history.

Output rate selects the presentation cadence: 'Display refresh' paces
presentation at the measured monitor refresh rate, and the fixed rates pace it
at that many frames per second. Interpolation is an OpenGL presenter feature,
so enabling it selects the OpenGL renderer and runs without vsync.

'Display refresh' is the default because it is the ceiling that matches the
panel: presenting faster than the monitor can show cannot look smoother, and it
costs emulation-thread time that the game needs.

This replaces the launcher's former Settings row for frame interpolation, which
the shared PSX launcher profile offered on every title regardless of whether it
had been looked at for that game.

Credit

mstan — mod integration
