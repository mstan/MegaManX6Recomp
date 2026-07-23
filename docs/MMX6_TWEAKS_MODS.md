# Converting MMX6 Tweaks to native PSXRecomp mods

MMX6 Tweaks patched discs are conversion and parity oracles. They are not
runtime inputs, compatibility fallbacks, or packages a player must select.
Every converted feature targets the verified USA v1.1 stock BIN and resolves
to independently owned runtime operations.

The converter is intentionally fail-closed. It emits a feature only after its
changes have been reviewed and mapped to stable stock-disc ranges, guarded
main-EXE addresses, or registered hooks. It does not turn an arbitrary Tweaks
profile into a whole-disc VCDIFF.

## Reviewed vertical slice

`Title Screen` and `Retranslation` are currently reviewed. `TitleScreen02`
owns four artwork inserts and no WriteList entries:

- background tileset;
- background palette;
- `PRESS START` tileset; and
- `PRESS START` assembly.

All four destinations are populated, same-size ranges inside the stock
`ROCK_X6.DAT`. The converter verifies that the source payload is read at the
same destination in both the title-only oracle and, when available, the
title-plus-retranslation oracle. It emits four guarded `disc_user` overlays.
No Tweaks `PatchList_Base` writes are included.

Generate and verify the local package with your own extracted Tweaks data and
reference oracle:

```powershell
python tools/tweaks_native_psxmod.py `
  --stock "F:\path\to\Mega Man X6 (USA) (v1.1).bin" `
  --title-oracle "build-mod-platform\test-mod-variants\rockman-jp-title.bin" `
  --combined-oracle "build-mod-platform\test-mod-variants\rockman-jp-title-retranslation.bin" `
  --patcher-data "F:\path\to\Tweaks\run_extracted\data" `
  --s02-base "build-mod-platform\test-mod-variants\s02-base.bin" `
  --script-oracle "build-mod-platform\test-mod-variants\retranslation.bin" `
  --out "build-mod-platform\test-psxmods\MMX6-Tweaks-Native.psxmod"
```

The generated archive and source assets stay local. The repository does not
redistribute Tweaks artwork or patched game data.

## Retranslation record repacking

The converter audits and emits the retranslation's 15 active
`ScriptTextDisplay`/`ScriptMenuAlign` writes. It maps each Tweaks raw-disc
offset to a guarded stock main-EXE address and proves that the retranslation
oracle contains the replacement.

`ROCK_X6.DAT` begins with a stable logical-record table. Entry `id * 8` contains
the record's sector offset from the start of the DAT and its byte size. The s02
base changes exactly 67 reviewed records:

- 32 existing equal-size records are replaced in place;
- 30 grown records and five new records are packed into the beginning of the
  stock `ZNULL.DAT` padding area; and
- only the corresponding 8-byte table entries are redirected to the packed
  records.

The relocated payload uses `0x236A` of the stock padding area's `0x46A8`
sectors. `ROCK_X6.BIN` is byte-identical between stock and s02. The 36-byte
s02 SLUS base delta is only rebuilt-image LBA scaffolding and is deliberately
omitted.

Record 107 also contains three title-screen ranges. Retranslation emits only
its 21 changed bytes outside those ranges, so `Title Screen` and
`Retranslation` remain independent features and can be enabled together.

## Four-image algebra

`tools/tweaks_diff_algebra.cpp` compares four local reference images:

- `B`: common Tweaks base;
- `T`: title selection;
- `S`: script selection; and
- `TS`: both selections.

It reports byte, sector, overlap, conflict, and composition metrics. User-data
composition must be exact; raw-sector-only mismatch may be regenerated Mode 2
EDC/ECC. This is diagnostic evidence, not a package generator.
