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

All four replacements are populated, same-size subassets inside
`ROCK_X6.DAT`. The converter identifies them by outer-record ID, subasset
index, and type: palette `26:0`, plus title assets `107:1`, `107:3`, and
`107:8`. It independently resolves those identities in the stock disc, the
title-only oracle, and, when available, the title-plus-retranslation oracle.
This is required because Tweaks' B01-derived image moves record 107 by
`0x40` sectors; B01 raw offsets are conversion evidence, never stock runtime
destinations. The converter emits four guarded overlays at the corresponding
stock locations. No Tweaks `PatchList_Base` writes are included.

Generate and verify the local package with your own extracted Tweaks data and
reference oracle:

```powershell
py -3 tools/tweaks_native_psxmod.py `
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

The converter audits the retranslation's 15 active
`ScriptTextDisplay`/`ScriptMenuAlign` writes. It maps each Tweaks raw-disc
offset to a guarded stock main-EXE address and proves that the retranslation
oracle contains the replacement. Adjacent and byte-identical overlapping
writes are coalesced into 12 canonical runtime ranges.

`ROCK_X6.DAT` begins with a stable outer-record table. Entry `id * 8` contains
the record's sector offset from the start of the DAT and its byte size. Each
outer record has another table describing its typed, sector-aligned subassets.
The converter rebuilds 61 custom outer records from stock plus exactly 82
retranslation-owned s02 subassets:

- 36 custom records remain the same size and are replaced in place;
- 25 grown custom records are packed into the beginning of the stock
  `ZNULL.DAT` padding area; and
- only those 25 outer table entries are redirected to the packed records.

The relocated payload uses `0x1ABE` of the stock padding area's `0x46A8`
sectors. Records 107 and 243–247, including their common b01 scaffolding, are
not emitted. `ROCK_X6.BIN` is byte-identical between stock and s02. The
36-byte s02 SLUS base delta is only rebuilt-image LBA scaffolding and is also
deliberately omitted.

The ISO root record keeps the stock DAT LBA and reports the virtual
`0x03DED000` byte extent in both little- and big-endian fields. This lets the
guest's normal `CdSearchFile` path reach relocated records without changing the
physical stock image.

Record 107 contains three title-screen ranges and no uniquely owned
retranslation subasset, so the retranslation feature does not claim it.
`Title Screen` and `Retranslation` remain independent and can be enabled
together.

## Four-image algebra

`tools/tweaks_diff_algebra.cpp` compares four local reference images:

- `B`: common Tweaks base;
- `T`: title selection;
- `S`: script selection; and
- `TS`: both selections.

It reports byte, sector, overlap, conflict, and composition metrics. User-data
composition must be exact; raw-sector-only mismatch may be regenerated Mode 2
EDC/ECC. This is diagnostic evidence, not a package generator.
