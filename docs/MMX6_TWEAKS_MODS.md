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

Both reviewed localization features are boolean at the launcher boundary.
Disabled means the untouched stock USA title/script; enabled applies the one
available replacement. A one-value dropdown would duplicate enabled state and
is deliberately not emitted. If a future feature offers two or more non-stock
variants, those variants belong in one right-pane choice control under that
single left-pane feature.

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

The upstream GUI catalog contains 332 entries and 329 unique source-control
IDs. The native 1.9.0 package explicitly represents 117 of those IDs, leaving
212 before the modular packages described below. These are source controls,
not necessarily launcher rows: mutually exclusive upstream radio buttons are
one coherent launcher feature, while independently enabled controls remain
independent rows.

Every converter writes its complete upstream IDs to `source_controls` in its
conversion report. Produce an exact, duplicate-aware burndown across installed
package reports with:

```powershell
py -3 tools/mmx6_tweaks_coverage.py `
  --mods-root build-mod-platform/mods `
  --out build-mod-platform/mmx6-tweaks-coverage.json
```

The installed-package scan selects the latest numeric version of every
package. The ledger fails closed when a discovered report lacks
`source_controls`; estimates do not silently enter the represented count.
Converters may separately classify upstream GUI plumbing through
`excluded_source_controls`, with a non-empty reason for every entry. Excluded
widgets reduce the implementation backlog but never inflate the implemented
count, and a control cannot be both represented and excluded.

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

### Core quality-of-life controls

The next six features are accepted as independent, default-disabled
checkboxes, pending their listed live smoke tests. Each isolated engine
selection resolves to exactly its one source option after excluding
`PatchList_Base`; stock, B01, and s02 contain identical guard bytes; and none
overlaps another native feature.

| Feature ID | Tweaks source | SLUS offset / guest address | Stock guard | Replacement |
| --- | --- | --- | --- | --- |
| `alternate_default_controls` | `DefOptions01` | `0x5DE08` / `0x8006D608` | `8000100002004000200008000400` | `8000100008004000040002000100` |
| `faster_cutscene_text` | `CutsceneVoice02` | `0x12ED8` / `0x800226D8` | `04000224` | `02000224` |
| `mute_navigator_alerts` | `DialogueDisable07` | `0x43964` / `0x80053164` | `125B000C` | `00000000` |
| `disable_rescue_extra_lives` | `LivesSwitch02` | `0x3F75C` / `0x8004EF5C` | `01004224` | `00000000` |
| `disable_pickup_extra_lives` | `LivesSwitch03` | `0x3EC94` / `0x8004E494` | `01004224` | `00000000` |
| `disable_rescue_health_refill` | `LivesSwitch04` | `0x3F450` / `0x8004EC50` | `31004014` | `463B0108` |

`qol-core.bin` is the focused six-feature conversion oracle.
`qol-current-combined.bin` enables the same six selections together with the
current title, retranslation, intro, and Nightmare selections. Both are local
development artifacts produced deterministically through the independently
validated Python port of the Tweaks write pipeline; neither ships in the
package. The converter re-resolves every source closure and verifies both
oracles at the stock semantic SLUS offsets.

Required live checks remain intentionally visible in the conversion status:

- alternate defaults on a fresh/no-memory-card configuration and with an
  existing saved controller layout;
- several original and retranslated voiced cutscenes at both text speeds;
- multiple Navigator alert paths, confirming only the voice call is muted;
- item life pickups at ordinary and counter-boundary values;
- rescued-Reploid extra-life rewards separately from health rewards; and
- rescued-Reploid health behavior at low and full health for both characters.

The broader audit deferred `LivesSwitch01` because it silently pulls display
and Exit Button helpers into its source closure. `DialogueDisable01` through
`04` remain deferred behind the `IngameOptions01` conditional-ownership
design. Their patcher order is not permission to implement an arbitrary
last-writer-wins rule.

### Movement controls

Seven movement features are independently accepted, pending live behavior
smoke tests. Each resolves to exactly its named source option, inherits no
common-base write, maps to identical stock/B01 guards, and is disjoint from
the current package and the other six features.

| Feature ID | Tweaks source | Semantic operations |
| --- | --- | --- |
| `air_moves_after_dash_jump` | `DashGlobal02` | SLUS `0x8003AF74`: `860022A2 → 860020A2`; `0x8003B490`: `860023A2 → 860020A2` |
| `unlimited_air_moves` | `DashGlobal03` | SLUS `0x80039094`: `60004014 → 00000000` |
| `disable_double_tap_dash` | `DashGlobal04` | SLUS `0x80039FA4`: `8800A2808800A390 → 0000023400000334` |
| `unlimited_dash_duration` | `DashDurationUnlimited01` | SLUS `0x8003A080` and `0x8003A16C`: `FFFF4224 → 00000000`; `ROCK_X6.BIN` member `2+0x2B70`: same |
| `unlock_x_hover` | `HoverUnlock01` | SLUS `0x8003F218`: `18006214 → 00000000` |
| `unlimited_high_jump` | `HighJumpUnlimited01` | SLUS `0x800366A0`: `FFFF8224 → 00000000`; `ROCK_X6.BIN` member `24+0x332C`: `FFFF6224 → 00000000` |
| `always_drop_nightmare_orbs` | `OrbSwitch01` | SLUS `0x80042D94`: `000083A0 → 000080A0` |

`movement-core.bin` and `movement-current-combined.bin` contain all eleven
owned replacements. The focused aggregate is contaminated relative to the old
B01 control by unrelated legacy-patcher bytes, so it is never used as a
whole-diff ownership oracle. The converter admits only source-declared writes,
maps each one independently, and checks the combined image at those semantic
targets. The current combined image is otherwise byte-exact when the eleven
movement writes are applied to the preceding QoL combined control.

Future `HoverUnlock02` repeats the Unlimited Air Moves and hover-duration
writes byte-identically and also requires Unlock X's Hover. Those are shared
capabilities, not mutual exclusions; that feature remains deferred until the
resolver can represent its prerequisite closure without duplicating or hiding
ownership.

Live checks must cover ground and wall dash jumps, landing resets, armor and
character differences, double-tap versus dash-button input, dash cancellation
and stage transitions, both High Jump execution paths, and repeated Nightmare
Virus defeat/reform cycles. The final orb label must be confirmed against
visible behavior because the upstream source describes the behavior as
"always reappear."

### Exit Stage Availability

`ExitButton01`, `ExitButton02`, and `ExitButton03` are represented as one
configurable feature, not three checkboxes:

- disabled is the stock Normal behavior;
- enabled with `Main Stages` NOPs the guard at `0x80033020`
  (`03006010 → 00000000`); and
- enabled with `Everywhere` also NOPs `0x80033004`
  (`0B004010 → 00000000`).

The stock `ExitButton01` selector is payloadless and is recorded only as
source-closure evidence. The common patch has no option condition because both
enabled choices need it; the additional patch is conditioned on
`availability = "everywhere"`. Focused and current-combined oracles verify
both choices, including the negative proof that Main Stages retains the
Everywhere-only stock guard.

`LivesSwitch01` remains deferred. The original GUI forcibly selects
`ExitButton03`, so converting Infinite Lives naively would make the visible
Exit Stage choice lie. It must either be proven safe without that coupling or
declare an explicit, user-visible requirement; persisted Exit Stage state must
never be changed silently.

Live tests must exercise the main eight stages, intro and hidden areas, final
stages, both characters, fresh and loaded saves, actual return destinations,
choice persistence while disabled, and switching from Everywhere back to Main
Stages.

### Narrow combat, audio, and boss data

Five more independent features are accepted as narrow guarded operations,
pending their behavior and audio smoke tests:

| Feature ID | Tweaks source | Semantic operations |
| --- | --- | --- |
| `shadow_saber_cancellable` | `SaberCancellable02` | `ROCK_X6.BIN` member 24 at `+0x149/+0x14D/+0x151/+0x155`: `02/01/00/00 → 42/41/40/40` |
| `restore_x_charged_shot_voice` | `VoiceClip03` | SLUS `0x8003FAE8`, sound-ID immediate `06 → 08` |
| `restore_zero_giga_attack_voice` | `VoiceClip04` | member `24+0xF2C`, sound-ID immediate `07 → 0A` |
| `yammark_firefly_resistance` | `BossMod0106` | members `73+0x8ABC` and `662+0x2BDC`, mirrored immediate `08 → 60` |
| `indestructible_yammark_orbs` | `BossMod0102` | members `73+0xAC00` and `662+0x4D20`, mirrored pointer low half `FC4B → 1C4A` |

The Saber edits set bit `0x40` in four consecutive Shadow Armor attack-table
records. The two voice edits change existing sound-call arguments without
injecting code. Yammark's resistance edit changes the byte stored into the
stage/rematch firefly actor, while the orb edit redirects an existing pointer
from `0x80074BFC` to the stock no-contact table at `0x80074A1C`. All mappings
are independently resolved in both mirrored boss members.

`small-data-core.bin` and `small-data-current-combined.bin` provide focused
aggregate and current-package composition evidence. The converter emits only
the ten source-declared narrow ranges, never whole member 24, 73, or 662
overlays. This is important because the Saber and Zero voice features share
member 24 but own disjoint data.

Live tests must cover all four Shadow Saber attacks and cancellation windows;
X charged shots across armor/charge states; Zero's Giga Attack without
duplicate or incorrect playback; Yammark's stage and rematch fights; both
characters and varied weapons; and combinations with Retranslation and the
other restored voice clip. Frame pacing should be checked on the frequently
reached charged-shot function.

`StageMod0404` remains deferred: its eight-byte write crosses two apparent
Recycle Lab object records, and the stage-object schema has not yet proven
that both changed fields belong solely to the teleport.

### Guarded static inclusion spike

Version 1.6 adds twelve more independent feature rows after an adversarial
review of movement, combat, Nightmare, and early-boss candidates:

| Feature ID | Tweaks source | Scope |
| --- | --- | --- |
| `blade_mach_dash_unlimited_repetitions` | `MachDashUnlimited01` | one guarded SLUS instruction |
| `disable_falcon_jump_air_dash` | `FalconDash01=0` | one guarded SLUS instruction; native label describes the inverted action |
| `higher_ceiling_jump` | `HighJumpHeight01=192` | the reviewed Tweaks 192-height preset, not an unconstrained scalar |
| `disable_x_saber_cancelling` | `SaberCancellable01=0` | four bytes in member 24; disjoint from Shadow Saber cancelling |
| `allow_xtreme_item_drops` | `DifficultySwitch01=0` | one guarded SLUS branch |
| `prevent_nightmare_orb_reversion` | `OrbSwitch02=0` | one guarded SLUS instruction; disjoint from Always Drop Orbs |
| `yammark_speed_orbs_easy_normal` | `BossMod0103` | four mirrored member 73/662 values |
| `yammark_speed_orbs_xtreme` | `BossMod0104` | two mirrored member 73/662 instructions |
| `wolfang_debris_all_difficulties` | `BossMod0201` | two mirrored member 103/677 branches |
| `wolfang_ice_spikes_all_levels` | `BossMod0202` | two mirrored member 103/677 instructions |
| `wolfang_indestructible_ice_blocks` | `BossMod0203` | four mirrored member 103/677 halfwords |
| `wolfang_indestructible_ice_spikes` | `BossMod0204` | two mirrored member 103/677 instructions |

Every accepted source selection has exact one-option closure, stock-equal B01
guards, stable SLUS or indexed-member ownership, and no file insertion,
scratch-code injection, archive growth, prerequisite, synthesis, or byte
overlap with the existing native features or another spike feature. The two
default-on source checkboxes are deliberately inverted into positively named
native features: disabled is stock, and enabled applies the reviewed `0`
selection. The height edit is exposed as one boolean preset until bounded
numeric configuration has its own schema and validation.

`static-spike-core.bin` proves the twelve-source aggregate. The
current-combined oracle proves all twelve compose with the existing title,
retranslation, intro, Nightmare, quality-of-life, movement, combat, audio, and
Exit Stage selections without causing a hidden synthesized write. Aggregate
oracles are presence/composition evidence only; each emitted range is still
owned by its exact source closure and guarded against stock bytes.

The same review intentionally deferred code-cave injections, options with
hidden prerequisites or exception rewrites, unconstrained numeric fields,
ambiguous stage tables, save-progression rewrites, and hundreds of coupled
animation timings. Yammark's ten-site idle-time rewrite was deferred because
its branch removal needs broader phase testing than this spike's other boss
edits. A superficially clean Zero Yammar-input candidate was also removed when
the full current-package combination synthesized an additional input-hint
rewrite. This is the intended failure mode: shrink a batch when composition
reveals coupling, rather than silently reproduce it.

Live smoke coverage should include Blade and Falcon movement, ceiling
collision, X's four saber actions, Xtreme drops, a Nightmare Virus
kill/orb/reform loop, and both the stage and rematch forms of Yammark and
Wolfang across difficulties. The static guards and composition proof make the
batch safe to ship for testing; they do not replace those behavior checks.

### Standalone Player Mechanics package

`mmx6.tweaks.player-standalone` is the first adversarial Player Mechanics
burndown package. It admits three independent, default-disabled rows:

| Feature row | Source control | Exact source closure |
| --- | --- | --- |
| Unlock X's Air Dash | `DashGlobal01` | `DashGlobal01` |
| Guard Shell Bug Fix | `GuardShellFix01` | `GuardShellFix01` |
| Disable Zero Weapon Auto-select | `ZeroAutoselect01` | `ZeroAutoselect_Common`, `ZeroAutoselect01` |

All 18 writes have complete USA v1.1 stock guards and one semantic owner. The
three closures are byte-disjoint, so enabling all rows is deterministic and
order independent. Disabled rows emit nothing. The archive contains only
declarative guarded writes and uses the stock BIN/CUE at runtime.

`HoverUnlock02` was rejected from this supposedly safe slice. The upstream GUI
silently forces `HoverUnlock01`, so it is not an independent behavior, and the
empty `HoverUnlock02_ASM10` entry terminates the live payload after slot 9.
Importing all later-looking assignments or omitting the forced control would
both be false source closure.

`ShadowSlide01` was also removed after cross-review followed its replacement
JAL to guest `0x8007A5DC`. Stock contains zeroes there; the callee belongs to
`ArmorByPart_Common`, inherited through the old `PatchList_Base` rather than
the apparent `ShadowBase01` prerequisite. Until a resolver owns and composes
that shared armor foundation, installing only the visible Shadow writes would
jump into absent code.

Generate the package from local, user-supplied v2.6.1 source:

```powershell
py -3 tools/tweaks_player_standalone_psxmod.py `
  --stock "F:\path\to\Mega Man X6 (USA) (v1.1).bin" `
  --patcher-source "F:\path\to\Tweaks\_src" `
  --out "build-local\MMX6-Tweaks-Player-Standalone.psxmod"
```

The conversion report carries a string-only `source_controls` ledger for the
three admitted controls plus a 49-control Player Mechanics decision ledger.
Mach Dash, continuous dash, and Zero-technique state machines are named as
separate resolver domains; `Anim0301`, `Anim0401` through `Anim0407`, and the
three quarantined Mach Dash scalars remain explicit non-admissions.

### Exhausted low-risk static and bounded-choice tranche

Version 1.7 raises the native package from 44 to 73 feature rows. The review
mechanically exercised every remaining checkbox, radio group, and finite
dropdown in the 329-variable Tweaks catalog. Twenty-nine features passed the
strict easy-conversion gate:

- eight independent Normal Part slot choices, one for each Hunter Rank;
- eight independent Limited Part enable/disable toggles;
- eight independent boss-level choices, one for each Hunter Rank;
- Commander Yammark's isolated always-Xtreme behavior toggle;
- Amazon Area's blind-jump ceiling extension;
- the Secret Lab 2-2 platform;
- Secret Lab 1 spike removal as one two-choice feature; and
- Recycle Lab ceiling extension as one two-choice feature.

The rank and boss-level dropdowns contain only non-stock choices. Disabling a
row therefore always restores stock behavior; enabling it always makes a
material change. A source dropdown with only one non-stock value is represented
as a left-pane checkbox, matching the general launcher UX rule.

All 71 non-stock variants are reassembled independently through the ported
Tweaks engine. Each must retain exact option closure, exact raw write identity,
no synthesis, no file insert, and stock-equal B01 guards. First- and last-choice
aggregate oracles, both alone and composed with the complete v1.6 selection,
exercise the extreme variants. Intermediate values remain protected by exact
source payload checks and the same stock semantic mapping.

Stage edits are never emitted at their Tweaks/B01 raw offsets.
`StageMod01`, `StageMod02`, `StageMod0302/0303`, and
`StageMod0402/0403` map to stock `ROCK_X6.DAT` by record ID, subasset index,
asset type, and subasset-relative range. Their source and stock range hashes
are pinned independently. The two radio pairs become two configurable feature
rows, not four mutually exclusive rows.

The Title Screen feature now exposes all four bundled non-stock variants:
Rockman Japan, Rockman China, Mega Man Custom A, and Mega Man Custom B. They
share one left-pane feature and one artwork dropdown. Every variant is mapped
to the same four logical title subassets; the China variant intentionally owns
only the two background assets and leaves the stock Press Start assets intact.

The nonnumeric easy gate is now exhausted. Exact-looking candidates were still
deferred when they crossed a product boundary:

- dialogue toggles and Nightmare Fire interact with the future in-game options
  hook;
- Shared Stats changes progression/save semantics;
- Zero Yammar input synthesizes an extra hint when combined with the
  retranslation;
- DashGlobal01 changes closure when incomplete-armor support is present;
- Yammark idle time is a ten-site behavior rewrite needing phase coverage;
- the Recycle Lab hidden teleport crosses apparent object records;
- loading-logo choices silently pull Disable Title Demos;
- mugshots and palettes use file insertion plus dynamic assembly; and
- the remaining player/stage radios require scratch-code injection or hidden
  prerequisite closures.

### First bounded-integer tranche

Version 1.8 raises the native package from 73 to 93 feature rows. It adds 20
independent numeric controls:

- seven Commander Yammark and Blizzard Wolfang damage values;
- six Nightmare Soul orb values;
- four normal and Hyper Dash duration values; and
- three starting-lives values.

These features use the format-v2 `replace_from` operation. The resolver encodes
one bounded integer option as `u8` or `u16le` during preboot resolution, then
feeds the result through the ordinary guarded write plan. It adds no in-game
dispatch or CD-read work.

Every feature was exercised at its minimum, an interior value, and its maximum
through the ported Tweaks engine. The converter proves exact one-option closure,
fixed write topology, direct unsigned encoding, no file inserts or synthesis,
and a stock-no-op default. Executable immediates guard the complete four-byte
MIPS instruction even though only the immediate field varies. Indexed
`ROCK_X6.BIN` data is mapped by member identity rather than copied from the
derived B01 layout.

The complete v1.8 plan contains 33 parametric operations guarding 80 stock
bytes. It composes without overlap with all 63 existing executable patches and
231 existing disc overlays. Numeric UI editing uses signed 64-bit bounds and
commits canonical values only when editing completes, avoiding partial text
states and 32-bit truncation.

This tranche deliberately excludes values whose source representation is
split across instructions, whose bounds are not semantically established, or
whose behavior is coupled to injected code. Those belong to later primitives,
not looser use of `replace_from`.

### Parametric completion and Reploid statuses

Version 1.9 raises the package from 93 to 100 feature rows and represents 117
Tweaks source controls. It adds:

- four independent Reploid outcome-status choices;
- one seven-field ordered `Rank Soul Thresholds` feature;
- two independent initial-dash speed features; and
- a full `Ceiling Jump Height` integer control in place of the earlier fixed
  Higher Ceiling Jump checkbox.

The rank thresholds are an exact packed `u16le` data table. The feature is
valid only when C <= B <= A <= SA <= GA <= PA <= UH; equality is allowed.
The loader enforces this while enabled and blocks re-enabling an invalid
disabled draft.

Initial Dash constants use format-v3's guarded
`mips_lui_ori_u32` transform. It validates one linked LUI/ORI pair and writes
the raw high and low 16-bit halves. Normal Initial Dash owns two pairs; Hyper
Dash Initial Speed Bonus owns one. Tweaks declares 425984 as the normal
control's default/no-op even though the second stock site loads 270336.
Therefore the selected default emits no writes and preserves asymmetric stock;
any nondefault selection intentionally writes both pairs.

Changing executable instructions can send the containing functions through
the runtime's dirty-code path. The conversion is exact and guarded, but the
normal and Hyper Dash paths still need live performance and branch coverage
before claiming zero runtime cost.

The complete v1.9 plan contains 44 parametric operations guarding 122 stock
bytes, 74 fixed executable patches, and 231 disc overlays. The converter
re-resolved all accepted values through Tweaks and reported no incompatible
overlaps.

### Standalone timing and status tranche

`tools/tweaks_timing_psxmod.py` deliberately produces a second package,
`mmx6.tweaks.timing`, instead of adding more special cases to the monolithic
native converter. Version 1.1 contains six independent, default-disabled
feature rows:

| Feature row | Right-pane values | Tweaks controls |
|---|---:|---|
| X Saber Timing | seven integers, 1-99 | `Anim0101`-`Anim0107` |
| Shadow Saber Timing | seven integers, 1-99 | `Anim0201`-`Anim0207` |
| Zero Saber Cooldown Timing | seven integers, 1-99 | `Anim0301`-`Anim0307` |
| Zero Z-Buster Timing | seven integers, 1-99 | `Anim0401`-`Anim0407` |
| Maximum Lives | one integer, 0-99 | `LivesValue04` |
| Nightmare Dark Opacity | one integer, 1-64 | `NightmareMod01` |

The left pane therefore has six coherent controls, not 30 rows and not one
package-sized mega-feature. The right pane contains only the actual values.
There is no redundant enabled option; the feature checkbox already supplies
that state.

All operations use package format 4. A patch guards the complete stock
instruction or four-byte animation record, but owns only its declared dynamic
field. This matters for the Saber records: cancellability flags occupy adjacent
bytes and must remain independently composable with timing. The converter
maps every B01 source offset back to stock `SLUS_013.95` or a stable
`ROCK_X6.BIN` member before emitting a runtime destination.

Maximum Lives exactly reproduces both cap sites and both `cap + 1` comparison
sites. For values above 9 it conditionally NOPs `LivesDisplay01`, matching
Tweaks' protection against a one-digit pause-menu graphic. Nightmare Dark
reproduces the four 12-byte source templates as `opacity` and `opacity - 1`
fields. One template crosses a 2048-byte runtime sector and is explicitly
split into guarded 8-byte and 4-byte patches.

The converter re-runs the ported Tweaks pipeline at boundary and interior
samples, rejects source-closure or topology drift, verifies complete B01 and
stock guards, and writes every accepted source field to
`conversion-report.json` under `source_controls`. Its reviewed plan has 56
sparse operations, 252 complete guard bytes, and 66 owned bytes. This proves
exact source-write conversion; gameplay timing and visual behavior remain
marked pending live smoke tests.

One tempting expansion remains explicitly deferred:

- animation value zero is not a direct byte. Tweaks converts it to a `01`
  sentinel plus an `offset + 2` companion zero, and a zero first frame can
  terminate processing of later animation sets.

Generate the package locally:

```powershell
py -3 tools/tweaks_timing_psxmod.py `
  --stock "F:\path\to\Mega Man X6 (USA) (v1.1).bin" `
  --b01-base "build-mod-platform\test-mod-variants\base.bin" `
  --patcher-data "F:\path\to\Tweaks\run_extracted\data" `
  --patcher-source "F:\path\to\Tweaks\_src\data\_dat.ahk" `
  --out "build-mod-platform\test-psxmods\MMX6-Tweaks-Timing.psxmod"
```

`tools/test_tweaks_timing_psxmod.py` covers the admitted control surface,
zero-byte literals, boundary templates, manifest shape, report contents, and
byte-deterministic archive construction. The C++ integration test in
`tools/test_tweaks_timing_runtime.cpp` installs the generated archive through
the real package manager, rejects deferred/out-of-range values, resolves all
30 controls together, verifies the 56-write/59-field plan, and exercises the
Maximum Lives 9/10 predicate boundary.

### New Game status modular package

`tools/tweaks_new_game_psxmod.py` produces the resolver-backed
`mmx6.tweaks.new-game` package. Version 1.2 represents 65 Tweaks source
controls as 65 independent left-pane rows. Integer and rank rows use right-pane
options; bit rows use only the feature checkbox. `CharStart01` is represented
as one `Intro Stage Starting Armor` row with a local armor dropdown, because
its choices are mutually exclusive within that one feature rather than across
packages.

The resolver composes all enabled New Game rows into the shared New Game
foundation and the optional found-Reploid table. `CharStart01` also emits a
separate guarded intro-stage call-site write; the selected intro armor and the
Blade/Shadow `ArmorParts` byte are composed to match the original Tweaks
source closure. Falcon Armor remains the stock disabled state; enabling the
row offers the non-stock choices None, Blade, Shadow, and Ultimate.

The local integration test replays every admitted source control through the
ported Tweaks engine, checks isolated parity, checks minimum/maximum combined
composition, verifies the embedded C++ stock guards, and builds a deterministic
archive. Remaining New Game controls are deferred only where semantics are not
yet product-ready: random starting parts and found-Reploid mark algebra. The
hidden debug-start controls are explicitly excluded because the normal
submitted profile path emits no writes for them.

### General shared-foundation package

`tools/tweaks_general_foundations_psxmod.py` produces the resolver-backed
`mmx6.tweaks.general-foundations` package. Version 1.2 represents six
General/Balance controls as independent left-pane rows:

| Feature row | Tweaks control | Runtime composition |
|---|---|---|
| Rank UH Unlocks Ultimate Armor | `MissRepUnlocksRank01` | shared Mission Report foundation plus the Ultimate Armor unlock hook |
| Rank UH Unlocks Black Zero | `MissRepUnlocksRank02` | shared Mission Report foundation plus the Black Zero unlock hook |
| Normalize Unarmored X Defense | `LowerDef01` | shared Lower Defense span, X-normalized variant |
| Normalize Zero Defense | `LowerDef02` | shared Lower Defense span, Zero-normalized variant |
| Gate Revealed Souls | `CutsceneSouls01` | shared Cutscene Souls foundation plus five threshold halfword writes |
| Gate Revealed Refight Souls | `CutsceneSouls02` | shared Cutscene Souls foundation plus two threshold halfword writes |

The source patcher writes both features through `MissRepUnlocksBase01`, so
declarative rows would collide on the same 324-byte executable allocation.
The resolver emits that foundation exactly once and composes the two
rank-specific eight-byte hooks into their owned offsets. This preserves the
left-pane UX: either unlock can be enabled independently, and enabling both is
one valid composed plan rather than two conflicting patches.

Version 1.1 also represents the two default-checked Lower Defense controls as
positive modular rows. Disabled is the stock/Tweaks default where unarmored X
and red Zero take extra damage; enabling a row normalizes that character's
defense. Enabling both composes to the source `LowerDef_All_A` variant over
the same guarded 12-byte span.

Version 1.2 adds the two Cutscene Souls threshold controls. The resolver owns
the shared `CutsceneSouls_Base` executable foundation and emits it once when
either threshold is non-stock. Each enabled row exposes a bounded integer
`Souls` option matching the Tweaks UI range; disabled remains stock.

### Current modular coverage checkpoint

After the modular New Game, domain, timing, player, title/retranslation, and
hook packages installed in this worktree, the coverage ledger classifies 290
of 329 unique Tweaks source controls: 276 represented and 14 explicitly
excluded as GUI/patcher artifacts or source no-ops. Thirty-nine controls
remain:

| Tweaks area | Remaining controls |
|---|---:|
| Player Mechanics | 22 |
| General Tweaks | 6 |
| New Game Status | 5 |
| Balance | 1 |
| Localization + Custom Art | 5 |

## Burndown after version 1.9

The v2.6.1 source parser finds 329 unique user controls across 332 catalog
entries. Version 1.9 represents 117 of those source controls as 100 feature
rows; combined and configurable rows account for the difference. Exactly 212
unique controls remain:

| Tweaks area | Remaining controls |
|---|---:|
| New Game | 74 |
| Player Mechanics | 69 |
| General | 23 |
| Localization and Art | 23 |
| Balance | 5 |
| Damage Tables | 12 |
| Stages | 5 |
| Boss Attacks | 1 |

This table is the version-1.9 monolithic-package snapshot. The standalone
timing/status package above subsequently represents 22 of those controls
without changing the historical v1.9 counts.

The next work is grouped by the runtime or conversion primitive it retires,
not by arbitrary source-file order:

1. **Conditional multi-write templates:** the seven deferred `Anim04` cells,
   zero-value support for the 20 admitted animation cells, and remaining
   derived scalars. Zero has compound meaning for several timings and remains
   outside the direct positive-integer contract.
2. **Registered hook and code-foundation allocation:** an exact known core of
   25 remaining controls: 17 not-yet-native Mach Dash controls, two
   cutscene-soul controls, and four remaining voice controls. Another 20–40
   controls may reuse this foundation, but that reuse count remains an estimate
   until each closure is classified.
3. **Typed asset slots:** 14 mugshots, three loading logos, and two sprite
   palettes. These need asset identity, palette/VRAM metadata, and dependency
   composition rather than blind file insertion.
4. **Declarative new-game and progression state:** all 74 New Game
   controls. A related General set covers unlockables, incomplete armor, and
   shared stats. This requires typed bitfields, dependency validation, save
   semantics, and deterministic randomization.
5. **Typed tables:** 61 active boss-health cells followed by 33 damage tables.
   Each damage table exposes 63 attack records, or 2,079 underlying records.
   That record count measures data scale; it is not 2,079 ordinary feature
   rows. The editor needs table schemas, derived-field validation, and
   row-level ownership.
6. **Typed stage objects:** five remaining stage controls whose current source
   closures cross object or apparent record boundaries.

There is also a small existing-operation cleanup queue: Commander Yammark's
ten-site idle-time rewrite. It is byte-isolated, but remains deferred until its
stage and rematch phase transitions receive live behavior coverage.

The size ranking differs from the implementation order. New-game state and
damage tables cover the most controls and records, but building them before
the smaller typed primitives would force their semantics into generic byte
patches. The sequence above deliberately establishes reusable invariants,
templates, hooks, assets, state, and table ownership first.

## Four-image algebra

`tools/tweaks_diff_algebra.cpp` compares four local reference images:

- `B`: common Tweaks base;
- `T`: title selection;
- `S`: script selection; and
- `TS`: both selections.

It reports byte, sector, overlap, conflict, and composition metrics. User-data
composition must be exact; raw-sector-only mismatch may be regenerated Mode 2
EDC/ECC. This is diagnostic evidence, not a package generator.
