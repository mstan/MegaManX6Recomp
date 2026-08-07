# MegaManX6Recomp v1.0.5

v1.0.5 is a controller and video-behavior patch release.

## Controller rumble

- Implemented the PlayStation DualShock `0x4D` motor-map negotiation used by
  Mega Man X6 and routed subsequent small/large motor values to SDL3.
- Added per-controller stop, disconnect, and capability handling so vibration
  cannot remain active after the game stops requesting it.
- Preserved compatibility with v1.0.4 and older savestates; older states load
  with the standard DualShock motor map and both motors safely stopped.

## FMV defaults

- The Capcom logo and opening video now play normally when their skip mods are
  disabled.
- Removed the deprecated generic **Skip FMVs** launcher setting from this game.
  The separate opt-in Capcom and opening skip features under **Mods** are now
  the only controls for this behavior.
- Added a release-config regression check so packaged builds cannot silently
  re-enable the legacy auto-skip value.

Windows x64 and Linux x86_64 AppImage packages are provided. Existing memory
cards, settings, legally obtained disc images, and older savestates remain
compatible with v1.0.5.
