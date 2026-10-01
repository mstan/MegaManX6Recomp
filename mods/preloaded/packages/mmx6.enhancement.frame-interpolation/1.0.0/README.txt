Mega Man X6 Temporal Frame Blending

This mod leaves Mega Man X6's executable, VSync waits, simulation, timers,
input, and audio untouched. It combines the two most recent completed game
frames in PSXrecomp's OpenGL presentation path at the display refresh or a
fixed 60, 120, 144, or 165 presentation rate.

The motion-adaptive clarity blend avoids crossfading large pixel changes to
reduce double-image trails. It is presentation-only temporal blending, not
motion-vector frame generation, so it cannot reconstruct true in-between
positions.
