# Preloaded Mega Man X6 mods

This directory contains the built-in, default-disabled Mega Man X6 mod catalog.
CMake and the release packager copy it to `mods/packages` beside the runtime.

Two enhancement packages own features that used to live in the launcher's generic
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

The catalog also contains the latest converted runtime package for each
supported Mega Man X6 Tweaks feature family. Every Tweaks feature remains
disabled until the player enables it.

Mega Man X6 Tweaks was authored by acediez. The converted packages also retain
the contributor and PSXRecomp integration credits recorded in their manifests.
See `ATTRIBUTION.md` for source links and permission status.

Generated conversion reports are intentionally excluded because they contain
development-machine paths. Superseded versions, launcher state, and temporary
manifest backups are also excluded.
