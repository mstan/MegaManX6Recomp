# MMX6 Tweaks portrait and palette package

`tools/tweaks_assets_psxmod.py` converts the reviewed, stock-disc-safe artwork
slice of MMX6 Tweaks v2.6.1 into a separate package:

- package ID: `mmx6.tweaks.assets`;
- twelve independent mugshot feature rows, Alia through Sigma;
- two independent palette rows, Ultimate X and Nightmare Zero;
- twenty-three total non-stock variants; and
- no executable patches, derived disc, VCDIFF fallback, or new DAT records.

The package follows the feature model in
[`PSXMOD_CONVERSION_GUIDE.md`](PSXMOD_CONVERSION_GUIDE.md). Every character and
palette is a separate left-pane feature. A right-pane choice appears only when
that feature has multiple real replacements. Disabling any row restores stock
without changing another row.

## Local generation

The assets and disc images are deliberately not tracked. Generate the package
from a verified Mega Man X6 USA v1.1 BIN, the extracted MMX6 Tweaks data, and
the local B01 conversion oracle:

```powershell
py -3 tools/tweaks_assets_psxmod.py `
  --stock "F:\path\Mega Man X6 (USA) (v1.1).bin" `
  --b01-base "F:\path\test-mod-variants\base.bin" `
  --out "build-mod-platform\test-psxmods\MMX6-Tweaks-Assets.psxmod" `
  --report-out "build-mod-platform\assets-conversion-report.json"
```

Generation fails unless the stock SHA-256 is
`91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318`.
The converter writes the archive twice and requires byte-identical output.
It then parses the ZIP and TOML again, checks every payload hash, and reports
the final archive SHA-256.

For the local MMX6 Tweaks v2.6.1 extraction used during conversion, version
1.0.0 contains 14 features, four choice controls, 1,440 guarded overlay
operations, and 379,813 replacement bytes. Those operation counts are pinned
by the integration test.

## What is actually owned

Replacement art is mapped from B01 source offsets to stock
`ROCK_X6.DAT` record and subasset identities. B01 offsets never become runtime
destinations.

Alia replaces type `0x1060D` portrait tiles and type `0x1A` palettes in 23
stage records. X, Ultimate X, Falcon Armor X, Shadow Armor X, Blade Armor X,
Zero, Black Zero, and Nightmare Zero replace their existing portrait record
pairs. Dynamo, Gate, and Sigma require only their existing tiles/palette record
pairs.

The upstream `MugshotAssembly` helper copies roughly 205 KiB of assembly assets
for every portrait selection. This package never replays it. For characters
whose blink or talk frames need different tiles, the converter compares the
helper output with B01, resolves the owning type `0x18` subasset, and emits only
the changed guarded 16-bit tile-reference fields.

Nightmare Zero exposes an upstream edge case: `assembly_07.bin` is too short
for the Nightmare Zero relative slot, and the patcher appends ten bytes into
alignment padding after the type `0x18` subasset. Padding has no asset identity
or loader-visible meaning. The converter proves the write does not reach the
next subasset, records the ten omitted bytes, and emits only changes inside
typed assets.

Palette conversion follows the same rule. The source patcher emits 2,944 bytes
for every Ultimate X choice and 800 bytes for Nightmare Zero. The native plan
emits maximal changed runs only:

| Palette | Variant | Changed bytes | Runs |
|---|---|---:|---:|
| Ultimate X | X6 Proto / X4 | 475 | 55 |
| Ultimate X | X5 | 531 | 42 |
| Ultimate X | Custom A | 421 | 54 |
| Ultimate X | Custom B | 504 | 40 |
| Ultimate X | Custom C | 556 | 40 |
| Nightmare Zero | Custom A | 300 | 10 |

This prevents stock-identical bytes in one palette from falsely conflicting
with another future palette mod.

## Composition proof

The converter proves all of the following before packaging:

- the disabled/default profile has no Tweaks patch plan;
- every variant has exactly its reviewed source-option closure;
- no selection inherits common B01 writes;
- every source file insert resolves to a stock record or subasset owner;
- every guard matches the supported stock disc;
- no two simultaneously enabled product features overlap;
- first-choice and last-choice all-feature combinations add no hidden source
  dependency or synthesized operation;
- the union of narrow per-feature type `0x18` fields exactly reproduces the
  combined `MugshotAssembly` changes;
- title-screen ownership at record 107 and record 26 is untouched; and
- Retranslation's script records and record 85–89 text subassets are untouched.

Run the focused local test with:

```powershell
$env:MMX6_ASSET_TEST_STOCK = "F:\path\Mega Man X6 (USA) (v1.1).bin"
$env:MMX6_ASSET_TEST_B01 = "F:\path\test-mod-variants\base.bin"
py -3 -m unittest tools.test_tweaks_assets_psxmod
```

Without those local-only paths, the catalog tests run and the disc integration
test is skipped.

## Deliberately deferred domains

This generator fails closed instead of absorbing nearby controls:

- **Hunter and Dr. Light mugshots** need new DAT records 243–246. Their portrait
  references live in script records also rebuilt by Retranslation. They require
  a DAT allocator/virtual asset registry and a script-aware portrait-reference
  transform, not raw overlays.
- **Loading logos** are acknowledged by the upstream patcher as incomplete
  when title demos return to the title screen. The patcher silently forces
  Disable Demos. They remain deferred until the demo-return path is correctly
  implemented, rather than introducing a hidden cross-feature dependency.
- **Recycle Lab's hidden teleport** needs a typed, reviewed stage-object
  identity before its member-153 data can be claimed.
- **Ceiling crush behavior** is one three-choice executable-hook feature.
  Automatic and manual crouch share injected code, while the manual choice
  intentionally overrides part of that foundation. It belongs behind a
  registered hook and code allocator, not in an asset package.

These boundaries are reusable: existing logical assets can ship as guarded
stock overlays now, while new records, translated-script bindings, stage
objects, and executable behavior each wait for their proper composer.
