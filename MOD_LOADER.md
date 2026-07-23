# PSXRecomp Mod Loader

## Goal

PSXRecomp games must support independently configurable mods while running from
the user's verified stock BIN/CUE.

The user imports a stock disc once, installs one or more `.psxmod` archives,
enables the features they want, configures those features, and plays. Mods are
resolved and applied by the runtime without modifying the stock disc, asking
the user to create or select a patched disc, or compiling a different static
recomp for every permutation.

MMX6 Tweaks is the first large-scale proving ground. Its hundreds of known-good
tweaks must be representable as independent, composable features. The number of
possible configurations must not produce a corresponding number of recomp
builds, package files, or derived disc images.

## Product model

Packages and features are different concepts:

- A **package** is an installation, update, provenance, and trust boundary. A
  `.psxmod` archive may contain one feature or many features.
- A **feature** is a user-facing mod or tweak. It has its own enabled state and
  may expose configuration values.
- An **operation** is the runtime primitive produced by an enabled feature,
  such as a guarded memory write, disc overlay, asset redirect, or function
  hook.

The Mods screen presents features, not package manifests, as its primary list.
For example, an MMX6 Tweaks package may install both of these independent
features:

- `Title Screen`, enabled, with `Rockman X6 (Japan)` selected.
- `Retranslation`, enabled, with `English Retranslation` selected.

Both features can be enabled simultaneously. Disabling `Title Screen` restores
only the stock title screen. Disabling `Retranslation` restores only the stock
script.

Mutually exclusive choices belong inside one feature. The US and Japanese title
screens are values of the `Title Screen` feature; they are not conflicting
packages. Package-level conflicts are reserved for genuinely incompatible
implementations.

## User experience

The ordinary flow is:

1. Select and verify a supported stock BIN/CUE.
2. Open **Mods** from the upper-right navigation, immediately left of
   **Settings**.
3. Install any number of `.psxmod` archives.
4. Search or browse the installed features in the left pane.
5. Enable or disable each feature with its own checkbox.
6. Select a feature to edit its options in the right pane.
7. Press **Play**. The launcher validates and composes the selected features
   before starting the game.

The left pane must remain usable with hundreds of features. It therefore needs:

- an enable checkbox on every row;
- search;
- categories or groups;
- a clear selected state;
- validation markers on the exact features involved in a problem; and
- no requirement to open a feature merely to enable or disable it.

The right pane shows the selected feature's description, author and package
provenance, configuration controls, and any validation details.

Package installation, removal, version selection, and diagnostics belong in a
secondary package-management view. They must not replace the feature list.

## Runtime contract

The stock BIN/CUE is immutable and remains the only game image selected by the
user. An enabled feature resolves into native runtime operations against that
known stock image.

The operation vocabulary should cover:

### Disc and asset overlays

When the game reads a known file, sector, byte range, or asset from the stock
disc, the runtime may serve replacement data from the mod package. Sparse raw
sector overlays must be available for games that bypass ISO9660 filenames or
mix filesystem and direct-LBA access.

Overlay lookup must be prepared before launch and indexed by file identity or
LBA range. It must not scan every installed mod on every CD read.

### Guarded memory and data patches

A feature may write data to a known guest address after verifying the expected
stock value. Expected-value guards prevent a patch from silently applying to an
unsupported revision or on top of an incompatible operation.

Bounded integer options resolve before boot into the same guarded writes. A
format-v2 patch may encode one integer option as `u8`, `u16le`, or `u32le`
inside a fully guarded replacement record. The manifest supplies explicit
minimum, maximum, step, default, field offset, and optional checked addend.
There is no expression evaluator, host-endian encoding, or per-frame integer
dispatcher. A default value that reproduces the expected bytes resolves to no
write, so enabling a numeric feature at its stock value remains a true no-op.

Format 3 additionally supports feature-local ordered-integer constraints and
a typed `mips_lui_ori_u32` transform for a fully guarded, register-linked
instruction pair. `omit_when_default` models source controls whose displayed
default means “leave every destination untouched,” including asymmetric stock
sites. These remain preboot plan operations; they do not add a per-frame mod
dispatcher.

### Code and behavior hooks

A feature may replace or wrap a known recompiled function, call site, or
behavioral hook. Hooks are registered by the game/framework and selected by
stable identifiers; packages do not load arbitrary native code.

Configurable hooks should be installed once and consult resolved feature state
where appropriate. Disabled hooks should have negligible cost, and enabled
hooks should not require a general-purpose per-instruction mod dispatcher.

### Recompiled-code overlays

If the existing dirty-RAM interpreter or native-overlay machinery can safely
execute guarded changes to loaded PSX code, it may be used as one implementation
primitive. The current psxrecomp mod-loader work must be audited before this
contract is finalized so the feature layer builds on current capabilities
instead of duplicating them.

## Resolution and conflicts

Resolution occurs before boot:

1. Verify the selected stock game and revision.
2. Load installed packages and persisted feature state.
3. Expand every enabled feature and its selected options into operations.
4. Validate dependencies, expected stock values, targets, hook identifiers, and
   operation bounds.
5. Detect collisions across the complete operation plan.
6. Produce a deterministic plan and diagnostic fingerprint.
7. Install the resolved overlays, writes, and hooks for the upcoming run.

Enabling one feature must never silently disable another.

A collision exists when two enabled features claim the same byte range, asset,
hook, or exclusive resource incompatibly. Identical writes may be coalesced.
Intentional composition must use an explicit dependency or supported hook chain,
not package ordering as an accidental override mechanism.

When resolution fails, the launcher identifies both features, the contested
resource, and the owning packages. The user decides which feature to disable.
The launcher does not guess.

## Performance expectations

Performance must scale with the operations selected for the current run, not
with the theoretical number of mod permutations.

- Feature conditions are resolved once before launch.
- Disc overlays use indexed range lookup.
- Guarded startup writes are applied once at the correct lifecycle point.
- Behavioral hooks dispatch directly through registered hook points.
- Untouched assets and functions remain on the normal static-recomp path.
- Hundreds of installed but disabled features add no meaningful in-game cost.

No permutation-specific static recomp is required.

## MMX6 Tweaks conversion

The existing MMX6 Tweaks patcher and its generated patched discs are development
oracles. They are not a product runtime, a compatibility fallback, or a format
the player must understand.

Conversion proceeds feature by feature:

1. Start from the verified stock MMX6 image.
2. Apply exactly one Tweaks feature or option with the reference patcher.
3. Diff the result against stock.
4. Classify each change as an asset/disc overlay, data patch, or behavior hook.
5. Emit the equivalent native `.psxmod` feature operations.
6. Run the stock game with only those native operations enabled.
7. Compare the runtime result and relevant bytes/behavior with the reference
   patched result.
8. Record parity and repeat for combinations that exercise shared resources.

The diff tooling should automate discovery and verification, but its output is
reviewed and converted into stable, understandable operations. A whole-disc
VCDIFF may be useful as temporary test evidence while developing the converter;
it must not become a shipped runtime path or user-facing fallback.

## First vertical slice

The first implementation slice contains:

- a feature schema inside `.psxmod`;
- persisted per-feature enabled state and option values;
- a feature-oriented ImGui Mods screen;
- native disc/asset overlay support sufficient for the selected MMX6 changes;
- guarded collision detection and actionable diagnostics;
- an MMX6 `Title Screen` feature;
- an MMX6 `Retranslation` feature; and
- a test demonstrating both features enabled together against an untouched
  stock BIN/CUE.

The slice is complete only when this flow works:

> Import verified stock MMX6, install the package or packages, independently
> enable the Japanese title screen and retranslation, launch, observe both
> changes, disable either one, and observe only that feature return to stock.

## Implementation sequence

1. Audit the current psxrecomp mod-loader branch and current ImGui launcher.
   Discard assumptions inherited from the obsolete RmlUi integration.
2. Specify the package/feature/operation schema and migration from the prototype
   package-only state.
3. Implement feature enumeration, persistence, resolution, and diagnostics in
   the framework API.
4. Implement the feature-oriented ImGui screen and separate package-management
   surface.
5. Implement the smallest required runtime overlay/hook primitives.
6. Convert and validate the two-feature MMX6 vertical slice.
7. Build reusable Tweaks diff, classification, and parity tooling.
8. Convert additional Tweaks categories incrementally, with combination and
   collision tests.
9. Remove the derived-disc prototype from the product path once the native
   vertical slice is proven.

## Non-goals

- Generating or shipping every possible Tweaks permutation.
- Asking users to patch, rebuild, or select a non-stock disc.
- Treating one entire configured Tweaks image as one user-facing mod.
- Automatically disabling supposedly conflicting features.
- Allowing packages to execute arbitrary native code.
- Preserving the prototype's derived-disc architecture as a fallback.

## Architectural acceptance criteria

The architecture is acceptable when:

- the user supplies only a supported stock BIN/CUE;
- multiple independently installed packages can contribute independent
  features;
- hundreds of features remain searchable and independently toggleable;
- feature options do not require new recomp builds;
- compatible title, script, gameplay, and asset changes compose;
- actual byte, asset, and hook collisions fail clearly before launch;
- disabling a feature removes only its operations;
- the stock disc is never modified;
- runtime overhead is proportional to enabled operations; and
- MMX6 Tweaks reference output is needed only by conversion and parity tooling,
  not by players.
