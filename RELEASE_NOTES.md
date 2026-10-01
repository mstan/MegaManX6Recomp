# MegaManX6Recomp v1.2.0-rc1

This Windows validation candidate includes the adaptive widescreen integration
and the Weapon Center / Ilumina rendering fixes. The latest stable release
remains v1.1.0. A full playthrough has not been recertified for this candidate.

## Changes

- Optional widescreen now offers Adaptive, 16:9, 21:9, and 32:9, in that order.
  Adaptive follows the window's aspect ratio. Enable it in Mods; it is off by
  default.
- Extended enemy spawning and culling, Ride Armor visibility, moving trash
  blocks, and Recycle Lab background coverage into the widened view.
- Integrated the supporting framework changes, including fixes for crashes
  during mod activation and renderer transitions.
- Kept Ilumina's sprite parts aligned in both phases, including wide views.
  Weapon Center's backdrop stays centered with the boss and reflects its
  original panorama to cover the extra width without exposing an atlas gutter.
- Aligned release overlay compilation hooks with the development configuration
  and rebuilt the original-disc native overlay cache for this exact build.

## Performance revalidation requested

GitHub issues #31 (Ilumina's second phase) and #32 (intro-stage enemies) remain
open. Current tests with Ultimate X in Ilumina's second phase and active intro
encounters ran near 60 FPS on the validation machine using NVIDIA OpenGL.
Those results do not establish performance on the Intel hardware in the reports.

If you reported either slowdown, please retry this candidate and report the
encounter, renderer, supersampling, enabled mods, CPU/GPU, and observed FPS.

## Compatibility and known limitations

Standard PS1 memory-card saves remain supported. Back up your saves before
testing. Old savestates are not guaranteed to load across this framework update;
load from your memory card and create new states in this version.

Rare exposed gaps and local pillarboxing in Amazon Forest are accepted
widescreen limitations. The experimental combined rain/darkness mask also has
remaining limitations. These do not block this candidate.

This is a Windows-only candidate. The package includes OpenBIOS and its MIT
notice, the launcher, bundled mods, a freshly audited overlay cache, and the
overlay toolchain. Your legally obtained game disc is still required. It does
not include a game disc, retail BIOS, or save data.
