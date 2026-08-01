# MMX v1.0.0

MMX v1.0.0 is the largest Mega Man X6 Recompiled update yet, adding a
full runtime mod catalog based on Mega Man X6 Tweaks alongside substantial
PSXRecomp framework, launcher, and performance improvements.

## Mega Man X6 Tweaks

- Added 14 mod package families containing 201 individually configurable
  features.
- Tweaks are applied at runtime without modifying your original disc image.
- Features are opt-in and disabled by default, with dependency and conflict
  handling built into the mod loader.
- Mod authors and original sources are linked directly from the launcher.

acediez has explicitly granted permission to adapt and ship his Mega Man X6
Tweaks work as part of Mega Man X6 Recompiled. I am grateful for both his work
and his approval of this adaptation.

## Display enhancements are now mods

Experimental widescreen has moved from the generic Display settings into the
Mods view. Widescreen reconstructs game-specific rendering behavior rather
than merely stretching the output, so presenting it as a mod better reflects
what it changes.

Presentation-only frame interpolation is now handled the same way, with
selectable output rates while preserving the game's original logic, audio,
and VBlank timing.

## OpenBIOS is included and selected by default

OpenBIOS is bundled with this release and is used automatically when no retail
BIOS is selected. A legally obtained retail PlayStation BIOS remains optional.
Selecting **Use OpenBIOS** in first-run setup, or clearing a retail BIOS from
Settings, returns to the default OpenBIOS path.

## Performance and framework updates

This release incorporates numerous PSXRecomp improvements since v0.0.7-alpha,
including:

- optimized MDEC/FMV hot paths and batched cycle accounting;
- faster launcher, game-start, and save-state paths;
- safer overlay caching and on-demand native overlay compilation;
- SDL3 as the default host backend;
- renderer upload and Vulkan batching improvements;
- improved CD, BIOS, and disc-path handling;
- corrected PlayStation load-delay behavior and additional audio/CDDA fixes.

## Not included in this release

The following work is intentionally withheld:

- **Incomplete Armors by Part**, including its Shadow Saber Palette option. Its
  adaptation depends on a shared `ArmorByPart_Common` foundation that could not
  yet be emitted safely; the incomplete conversion caused an unknown dispatch
  during character spawning.
- **English retranslation**, pending direct approval from NeoDynamo.
- **Extra portraits and related palette work**, pending direct approval from
  MetalWario64.
- **In-game Tweaks options**, because that package currently depends on the
  withheld retranslation.

The retranslation and portrait adaptations are staged for a future release and
will be enabled if their respective authors grant approval. None of that
collaborator-owned content is included in this package.

## Setup and compatibility

- Bring your own legally obtained Mega Man X6 USA v1.1 disc image
  (`SLUS-01395`).
- OpenBIOS is included and selected by default; a retail PlayStation BIOS is
  optional.
- Existing memory cards remain compatible.
- End-to-end completion has not yet been recertified on this build, so please
  report any regressions.
