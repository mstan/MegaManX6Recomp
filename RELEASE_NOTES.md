# MMX v1.0.3

MMX v1.0.3 is a hotfix for the v1.0.2 player packages.

## Widescreen HUD fix

- Restored the MMX6 HUD packet range to the player-facing `game.toml`, so the
  health and ability meters anchor to the true widescreen corners.
- Restored the reveal initializer and intro-stage culling hooks that had also
  drifted out of the release config.
- Added a release-packaging parity check. Windows and Linux packaging now fail
  if the complete `[widescreen]` section differs from the development config.

The development config already contained these settings, which is why local
builds worked while the downloadable v1.0.2 packages did not.

## Carried forward from v1.0.2

- Windows and Linux x86_64 packages with prebuilt native overlay shards.
- Experimental Linux AppImage support.
- MIT-licensed OpenBIOS bundled and selected by default.
- The full acediez Tweaks catalog, including DuoDynamo's approved English
  retranslation, plus the framework-owned loading-speed mods.

All enhancements remain opt-in. Saves, memory cards, settings, and the player's
original disc image remain compatible with v1.0.2.
