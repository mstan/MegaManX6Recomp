# MMX6 Tweaks non-player burndown

This audit starts from the post-package remainder: General 21, Balance 5,
Boss Attacks 1, Stages 5, Damage Tables 12, and Localization + Art 5. Those
numbers are parser catalog entries, not automatically valid launcher rows.

`tools/tweaks_domain_psxmod.py` converts 20 real source controls into 17
feature rows across four independent packages:

| Package | Feature rows | Source controls |
|---|---:|---:|
| `mmx6.tweaks.general` | 13 | 13 |
| `mmx6.tweaks.stage-modes` | 1 | 4 |
| `mmx6.tweaks.boss-attacks` | 1 | 1 |
| `mmx6.tweaks.damage-rules` | 2 | 2 |

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
`BossMod0105`, `DmgTableGate01`, and `DmgTableGateDmg01`.

## Real controls still deferred

- `ArmorByPart01` through `ArmorByPart04` need one incomplete-armor composer.
  The source depends on the common B01 `ArmorByPart_Common` foundation and has
  ordered overlap with shared Mission Report unlock code. The two radio
  controls are one mode selector, and the palette checkbox is conditional.
- `LivesSwitch01` silently adds lives-display and Exit Stage helpers.
- `IngameOptions01` is visible in the source GUI, but its standalone selection
  is normalized away. It needs typed ownership with dependent settings.
- `MissRepUnlocksRank01` and `MissRepUnlocksRank02` independently overwrite
  different bytes inside one Mission Report unlock foundation. Enabling both
  naïve declarative rows produces a real collision; they need a game-owned
  shared-foundation composer.
- `CutsceneSouls01` and `CutsceneSouls02` write executable bytes in member 797's
  padded allocation outside its logical payload.
- `LowerDef01` and `LowerDef02` default checked and emit no isolated source
  writes. Their unchecked A/B corrections assume the unowned common B01
  defense foundation, so applying those corrections directly to stock would
  invert the source contract.
- `StageMod0404` crosses apparent Recycle Lab stage-object records. It remains
  out until a typed teleport/object owner is proven.
- `MugshotCustom01` and `MugshotCustom02` are real Hunter and Dr. Light asset
  choices. Both synthesize a large shared `MugshotAssembly` closure across many
  records. They remain out until that composer proves simultaneous
  retranslation and existing-asset-package use.
- `TitleLoading01` through `TitleLoading03` are one real loading-logo choice,
  but remain deferred while the known demo-return behavior is wrong.

`BossHealth` is a dynamic boss-health table editor template, not one scalar
control. The underlying table needs typed record ownership.

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
