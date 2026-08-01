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

The catalog also contains the latest approved converted runtime package for
each supported Mega Man X6 Tweaks feature family. Every included Tweaks feature
remains disabled until the player enables it.

Mega Man X6 Tweaks was authored by
[acediez](https://twitter.com/acediez) ([RHDN project thread](https://www.romhacking.net/forum/index.php?topic=26507.0)).
acediez has approved this use. Portrait and palette artwork by
[Metalwario64](https://x.com/metalwario64) and retranslation work by
[DuoDynamo](https://twitter.com/DuoDynamo) have separate permissions that
remain TBD. Those package families, the retranslation feature and payload, and
the retranslation-dependent in-game Settings package are therefore withheld
from this public catalog and release. The conversion tooling remains available
for restoration after approval. See [`ATTRIBUTION.md`](ATTRIBUTION.md) for the
complete credit and permission ledger.

Generated conversion reports are intentionally excluded because they contain
development-machine paths. Superseded versions, launcher state, and temporary
manifest backups are also excluded.
