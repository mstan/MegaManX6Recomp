# MMX6 Tweaks non-player burndown

This audit starts from the post-package remainder: General 21, Balance 5,
Boss Attacks 1, Stages 5, Damage Tables 12, and Localization + Art 5. Those
numbers are parser catalog entries, not automatically valid launcher rows.

`tools/tweaks_domain_psxmod.py` converts 22 real source controls into 19
feature rows across four independent packages:

| Package | Feature rows | Source controls |
|---|---:|---:|
| `mmx6.tweaks.general` | 13 | 13 |
| `mmx6.tweaks.stage-modes` | 2 | 5 |
| `mmx6.tweaks.boss-attacks` | 1 | 1 |
| `mmx6.tweaks.damage-rules` | 3 | 3 |

The stage package deliberately represents `AutoCrouching01`,
`AutoCrouching02`, `AutoCrouching03`, and `RecycleCeiling01` as one enabled
feature with a right-pane mode choice. They are real mutually exclusive
alternatives in one source radio group, not four conflicting mods. The manual
mode's ordered write inside the automatic-mode code block is composed into a
single guarded final plan before the manifest is emitted. Disabling the
feature is the stock/no-changes state; the right pane contains only Automatic,
Hold Manual Crouch, and Disable Ceiling Movement.

Every report contains explicit `source_controls` strings, structured
`deferred_source_controls` objects for real unfinished work, and structured
`excluded_source_controls` objects only for non-game GUI/patcher plumbing.
Every ledger entry has a nonempty reason. Provenance stays in the conversion
report; no unknown keys are added to the runtime manifest schema.
Generation reads the supported stock disc and user-supplied Tweaks source
directly. It rejects changed closures, synthesized payloads, file insertion,
unsupported ISO files, and ranges without strict indexed-member ownership. No
patched disc, B01 image, or behavior oracle is used.

## Accepted real controls

General accepts:

- `LivesSwitch05`;
- `DialogueDisable01`, `DialogueDisable02`, `DialogueDisable03`,
  `DialogueDisable04`;
- `SharedStats01`, `SharedStats02`;
- `UnlockCode01`, `UnlockCode02`, `UnlockCode03`;
- `UnlockEffect01`;
- `CutsceneVoice01`; and
- `MenuDefaultSel01`.

The other accepted domains are the four ceiling-mode controls above,
`StageMod0404`, `BossMod0105`, `DmgTableGate01`, and
`DmgTableGateDmg01`.

Version 1.2 of `mmx6.tweaks.damage-rules` also accepts `BossHealth` as one
`Boss Health by Level` feature row with 61 bounded integer fields. Disabled is
stock. Enabled applies the reviewed v2.6.1 table algebra for single-value
bosses, fixed-level bosses, Nightmare Snake's derived halfwords, Dynamo's
halfword delta table, Nightmare Mother's relocated base/bonus values, and the
common base-plus-delta byte tables.

## Real controls still deferred

- `ArmorByPart01` through `ArmorByPart04` need one incomplete-armor composer.
  The source depends on the common B01 `ArmorByPart_Common` foundation and has
  ordered overlap with shared Mission Report unlock code. The two radio
  controls are one mode selector, and the palette checkbox is conditional.
- `LivesSwitch01` silently adds lives-display and Exit Stage helpers.
- `IngameOptions01` is visible in the source GUI, but its standalone selection
  is normalized away. It needs typed ownership with dependent settings.
- `MugshotCustom01` and `MugshotCustom02` are real Hunter and Dr. Light asset
  choices. Both synthesize a large shared `MugshotAssembly` closure across many
  records. They remain out until that composer proves simultaneous
  retranslation and existing-asset-package use.
- `TitleLoading01` through `TitleLoading03` are one real loading-logo choice,
  but remain deferred while the known demo-return behavior is wrong.

## GUI and patcher artifacts

The following Damage Tables catalog entries must never become launcher rows:

- `DmgTableCurrent1` through `DmgTableCurrent5` are category navigation;
- `DmgTableInput_S` is selection plumbing;
- `DmgTableInput_V` is the dynamic 33-by-63 cell editor template;
- `ErrorRecalc` is a patcher action;
- `PatchList_BaseHacks` is an internal sentinel; and
- `HelpButton` is a GUI action.

The actual damage-table surface is thousands of typed records, not twelve
ordinary toggles.

## Source no-ops

`DebugStageStart`, `DebugCheckpointStart`, and `ZeroDebug` are excluded from
the modular launcher surface. Under the normal submitted profile path, each
emits no patchfile, owned writes, or synthesized payload, so exposing them as
mods would create dead UI rows rather than real game changes.
