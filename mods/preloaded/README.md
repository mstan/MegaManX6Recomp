# Preloaded Mega Man X6 mods

These packages describe default-disabled features whose trusted native
implementations are compiled into MegaManX6Recomp (`src/mods/`). Package
archives do not contain or load native code — a manifest selects an
implementation by its stable plugin id.

Both packages here own features that used to live in the launcher's generic
Settings pages:

| Package | Replaces |
|---|---|
| `mmx6.enhancement.widescreen` | Settings aspect-ratio row + the separate experimental 21:9 row |
| `mmx6.enhancement.frame-interpolation` | Settings frame-interpolation row |

`game.toml` sets `[widescreen] offer = false` and
`[video] offer_frame_interpolation = false` so the launcher omits those rows and
the runtime ignores any value a previous build persisted into `settings.toml`.
That keeps exactly one control per feature: a game-specific enhancement is
presented as an opt-in change to the game, not as a display preference.
