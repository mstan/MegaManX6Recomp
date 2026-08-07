# MegaManX6Recomp v1.0.4

v1.0.4 is a patch release for the MMX6 Tweaks audio and retranslation
integrations.

## Boss warning voice

- Restored the spoken "Warning" voice used when X enters a boss encounter.
- Ported the complete three-part prototype sound bank from MMX6 Tweaks rather
  than only the sequence table. This avoids the loading softlock produced by
  the incomplete bank and supplies the missing sample data for sound index 44.
- Added stock-script and English-retranslation variants of all five affected
  stage banks so the voice composes correctly with either localization state.

## Retranslation portrait fix

- Removed the phantom Alia-shaped portrait shown for Hunter and Dr. Light
  dialogue when Retranslation was enabled but the optional custom portrait
  package was disabled.
- The translated scripts now retain the original no-portrait command until the
  separately permission-gated portrait assets are implemented and enabled.

## Runtime integration

- Enabled trusted mod assets to select variants from another package's active
  feature state.
- Reapply enabled executable mod patches after loading a savestate, preventing
  a stock checkpoint from silently disabling the current mod selection.

Windows x64 and Linux x86_64 AppImage packages are provided. All enhancements
remain opt-in. Existing saves, memory cards, settings, and legally obtained
disc images remain compatible with v1.0.3.
