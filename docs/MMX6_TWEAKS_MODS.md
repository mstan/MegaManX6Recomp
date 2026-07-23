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

## Adversarial ingestion ledger

An entry is accepted only when the patcher source identifies its owned writes,
the B01 address can be mapped back to a stable stock member, the stock guard
matches the common base at that member, and both a focused oracle and an
available combined-feature oracle contain the replacement. Whole-image
differences are never accepted as ownership evidence.

### Nightmare-effect toggles

`NightmareDisable01` through `NightmareDisable08` are accepted as eight
independent, default-disabled checkbox features. Their members are all inside
the stock `ROCK_X6.BIN` ISO member at LBA `0x338F1`, disc-user offset
`0x19C78800`, size `0x196800`. The file's location and size are the same in
stock and B01. `ROCK_X6.BIN` is a strict indexed archive; the member ID plus
member-relative offset is the runtime identity. The whole-file offset is shown
only as a diagnostic.

| Feature | Indexed member + relative offset | Whole-file offset | Stock guard | Replacement |
| --- | --- | ---: | --- | --- |
| `NightmareDisable01` / Nightmare Bug | `381 + 0x7EB4` | `0x0C5EB4` | `030707` | `000000` |
| `NightmareDisable02` / Nightmare Ice | `381 + 0x7EB7` | `0x0C5EB7` | `040404` | `000000` |
| `NightmareDisable03` / Nightmare Fire | `381 + 0x7EBA` | `0x0C5EBA` | `020808` | `000000` |
| `NightmareDisable03` / North Pole wall check A | `103 + 0x5E60` | `0x038E60` | `3A04638203000224` | `2FBC030800000000` |
| `NightmareDisable03` / North Pole wall check B | `574 + 0x43DC` | `0x122BDC` | `3A046382` | `A1B50308` |
| `NightmareDisable04` / Nightmare Iron | `381 + 0x7EBD` | `0x0C5EBD` | `030508` | `000000` |
| `NightmareDisable05` / Nightmare Cube | `381 + 0x7EC0` | `0x0C5EC0` | `040707` | `000000` |
| `NightmareDisable06` / Nightmare Rain | `381 + 0x7EC3` | `0x0C5EC3` | `010505` | `000000` |
| `NightmareDisable07` / Nightmare Mirror | `381 + 0x7EC6` | `0x0C5EC6` | `020606` | `000000` |
| `NightmareDisable08` / Nightmare Dark | `381 + 0x7EC9` | `0x0C5EC9` | `010606` | `000000` |

For all ten ranges:

- stock USA v1.1 and the B01 common base contain the same guard bytes;
- `no-nightmare-effects.bin` contains the exact replacement; and
- the Rockman-title plus retranslation plus no-Nightmare matrix image contains
  the exact replacement at the same semantic member.

The eight table entries are adjacent three-byte members, not overlapping
writes. The two additional Fire members are disjoint. None overlaps any
current Title Screen or Retranslation disc overlay, and Retranslation's
`main_exe` patches use a different target.

The no-Nightmare image is a contaminated whole-image oracle. Its generating
profile also selects `IngameOptions01`, `DefOptions01`, and base hacks.
Compared with the common base it has 43 changed `ROCK_X6.BIN` runs totaling
171 bytes, plus SLUS changes. Only the ten source-declared ranges above are
owned by these toggles. No `PatchList_Base` write, exception transform, or
prerequisite is included in their native conversion.

There is one known future collision. `IngameOptions01_ASM16` and
`IngameOptions01_ASM18` write different hooks over the two
`NightmareDisable03` North Pole wall members. Tweaks resolves this by applying
the hard-disable after the in-game-options hooks. Native ingestion of
`IngameOptions01` is therefore deferred until its Fire hooks can be expressed
conditionally: with both features enabled, hard-disable must take precedence;
with hard-disable disabled, the in-game toggle may own the hooks. These
features are not semantically mutually exclusive, and their overlapping byte
sequences must never be silently composed.

### Intro controls

These are accepted as three separate, default-disabled checkbox features, not
one preset. All four writes map to stable instructions in stock
`SLUS_013.95`:

| Feature | Semantic member ID | SLUS relative offset / guest PC | Stock guard | Replacement |
| --- | --- | --- | --- | --- |
| `IntroSkip01` / Skip Capcom video | `intro.capcom-call-a` | `0x0D360` / `0x8001CB60` | `F872000C` | `00000000` |
| `IntroSkip01` / Skip Capcom video | `intro.capcom-call-b` | `0x0D3A8` / `0x8001CBA8` | `7A4F000C` | `00000000` |
| `IntroSkip02` / Skip opening video | `intro.opening-call` | `0x0DBF0` / `0x8001D3F0` | `B369000C` | `00000000` |
| `IntroSkip03` / Disable title-screen demos | `title.demo-timer-init` | `0x0E774` / `0x8001DF74` | `FFFF4224` | `00000000` |

Stock, B01, s02, title-only, and retranslation-only inputs contain identical
guard bytes at all four members. All four relevant combined-factorial
`skip_intros` outputs contain the zero replacements, while their corresponding
control outputs retain the guards. The members do not overlap one another or
any current Title Screen, Retranslation, or Nightmare operation.

The top-level `skip-intros.bin` is stale and omits `IntroSkip03`; it is not a
valid ownership oracle. Only the source declarations plus the factorial
controls and combined outputs justify these four guarded operations.

## Four-image algebra

`tools/tweaks_diff_algebra.cpp` compares four local reference images:

- `B`: common Tweaks base;
- `T`: title selection;
- `S`: script selection; and
- `TS`: both selections.

It reports byte, sector, overlap, conflict, and composition metrics. User-data
composition must be exact; raw-sector-only mismatch may be regenerated Mode 2
EDC/ECC. This is diagnostic evidence, not a package generator.
