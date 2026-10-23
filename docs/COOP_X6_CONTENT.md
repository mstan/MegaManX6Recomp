# X6 native content inventory for co-op and netplay

The machine-readable [inventory](COOP_X6_CONTENT.json) contains **115 checkpoint
records**, **1,964 primary placements**, **365 secondary placements**, and all
**128 rescuable Reploid IDs**. It also defines **79 X6-specific obligations**
(`X6-001` through `X6-079`) for the parity burndown. Every gameplay check is
**unverified**, independently for local co-op and netplay. Extraction establishes
what to audit; it does not establish that any mechanic works.

## Original-source evidence

Only original **SLUS-01395 USA v1.1** is supported. The extractor rejects other
EXE/archive identities instead of interpreting their offsets as this revision.
No game bytes, save states, cards or disc copies are included in this inventory.

| Input | Verified SHA-256 |
| --- | --- |
| `SLUS_013.95` (522,240 bytes) | `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046` |
| `ROCK_X6.BIN` (1,665,024 bytes) | `55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f` |

The local raw disc was opened read-only and only the ISO root, EXE and BIN
archive were read. Both input files match the identities above; a whole-disc
hash was not recomputed. [DISC.md](../DISC.md) records the established disc
identity. Each placement section also records its member index, sector extent,
size and member hash.

Native executable instructions were inspected directly, with generated code
used only to locate routines:

| Data | Native evidence and interpretation |
| --- | --- |
| Checkpoint selector | `80029B8C..80029D14`: index root `80073300` by `(stage*2+section)*4`, then checkpoint by `*4`. |
| Checkpoint extents | 46 root slots in `80073300..800733B8`; nonzero roots bound arrays in `80073134..80073300`. Adjacent non-pointer data starts at `800733B8`. |
| Checkpoint records | `80072108..80073134`, stride `0x24`; native reads player coordinates, camera coordinates/bounds, arrival byte and other layer parameters. |
| Primary placements | `80029F38..8002A338`: root `8007349C`, same stage/section index, eight-byte records, exact byte3 value `15` terminates. Native viewport and state eligibility remain runtime obligations. |
| Secondary placements | `8002A438..8002A468`: root `80073554`, passed to producer `8002A4E4`. Its separate terminator is honored; lists are not concatenated. |
| Stage source | `80013E54..80013E80`: selector halfwords at `8006DB78`, destination word at `80010000` = `800E9860`. Placement sections select BIN members 2–32. |
| Archive layout | `80016780..80016858`: 59 `{sector offset, byte size}` descriptors, with a two-sector header and aligned consecutive payloads. See [original-disc overlay evidence](AOT_OVERLAYS.md). |

Names and broad stage roles follow acediez's local **Mega Man X6 Tweaks Workbook
v2.0**, SHA-256
`6855194c79f0830ee77b86901bc1997a481ce62de17dfaaced79d976d840e552`, particularly
`PlaythroughTable`, `ObjectOriginTable`, `RescReploids`, `Rank` and
`NightEftTable`. Counts, pointers, coordinates and subtype IDs come from original
game tables. Semantic names remain research labels until native runtime behavior
is observed. Category `4`, object ID `4` identifies the Reploid placements in
that research; the extracted subtypes cover `0..127` exactly once across normal
and alternate sections.

## Authored coverage

Stage and section values below are hexadecimal. Checkpoints are **table record
counts**, including entries beyond those documented by older warp notes; they
are not claims that every entry is reachable during a normal campaign.

| Stage/section | Authored area | Checkpoints | Primary | Secondary |
| --- | --- | ---: | ---: | ---: |
| `00/0` | Intro / Eurasia ruins | 3 | 57 | 7 |
| `01/0` | Amazon / Commander Yammark | 4 | 108 | 21 |
| `02/0` | North Pole / Blizzard Wolfang | 6 | 67 | 23 |
| `03/0` | Magma / Blaze Heatnix | 8 | 138 | 3 |
| `04/0` | Recycle Lab, first section | 4 | 118 | 60 |
| `04/1` | Recycle Lab, second section | 3 | 79 | 48 |
| `05/0` | Museum / Ground Scaravich | 3 | 516 | 36 |
| `06/0` | Inami Temple / Rainy Turtloid | 6 | 137 | 12 |
| `07/0` | Laser Institute / Shield Sheldon | 4 | 114 | 26 |
| `08/0` | Weapon Center / Infinity Mijinion | 3 | 55 | 8 |
| `0C/0` | Secret Lab 3 / Investigator refights | 18 | 18 | 14 |
| `0C/1` | Secret Lab 3 / Sigma | 2 | 43 | 5 |
| `10/0` | Secret Lab 1 | 5 | 110 | 6 |
| `11/0` | Secret Lab 2 A, common | 4 | 113 | 3 |
| `12/0` | Secret Lab 2 B, character-specific | 5 | 65 | 29 |
| `13/0` | Alternate Amazon | 2 | 9 | 6 |
| `13/1` | Alternate North Pole | 2 | 15 | 12 |
| `14/0` | Alternate Magma | 2 | 28 | 0 |
| `14/1` | Alternate Recycle | 2 | 31 | 27 |
| `15/0` | Alternate Museum | 2 | 28 | 2 |
| `15/1` | Alternate Inami | 2 | 41 | 5 |
| `16/0` | Alternate Laser | 2 | 42 | 7 |
| `16/1` | Alternate Weapon Center | 2 | 32 | 5 |

Those 23 placement sections account for 94 checkpoints. The remaining **21**
checkpoint records are retained: unresolved slots `09/0` and `0A/0` (one each),
cutscene namespace `0B/0` (13), and stage-select/title/report namespaces
`0D..0F`, both sections (one each). They must not silently become alleged
playable routes or disappear from the inventory.

`X6-001..023` cover these authored sections. `X6-024..035` cover native boss
admission and outcomes, including Nightmare Zero, alternate High Max, Dynamo,
Nightmare Mother, fortress High Max, Gate, all refights and Sigma/ending phases.
`X6-036..079` separate rescue/infection/rewards, souls/ranks, each Nightmare
effect, forms/techniques, collection/equipment, unique terrain/vehicles,
progression and native-card continuation. Each row supplies a concrete procedure
and independent local/netplay results. All 128 Reploid records additionally
track P1/P2 rescue, simultaneous contact, infection/loss, exactly-once rewards,
retry/re-entry and cold native-card continuation.

## Qualification procedure and remaining gaps

Use native checkpoints and authored coordinates to position/protect players
quickly. Traverse between checkpoints and exercise native triggers; do not set
success, boss-clear, unlock or rescue flags for the check being claimed. Record
any prerequisite bypass. A screen load or teleport past an obstacle is only
setup evidence.

For each relevant location retain candidate game/framework/UI identities,
effective mods, character/armor/seat, prerequisite state, accepted inputs,
actor/RAM observations and the actual subsequent destination. Check terrain,
spawning/interactions, music/SFX, retry, bosses and exits independently. Capture
visual/audio evidence for those claims; background output stays muted. Use
private native-card copies for destructive campaign scenarios.

The native pointers do **not** resolve these remaining obligations:

- Central Museum's 516 primary records include room variants; its room-choice
  graph, randomized chains and reachable combinations still need extraction and
  runtime coverage. One realized route cannot qualify the whole table.
- Alternate arenas substitute Nightmare Zero, High Max and Dynamo according to
  story state. Static layout membership cannot prove admission, prerequisites,
  damage rules, rewards or progression.
- Refight slot `0C/0` has 18 checkpoints. Its full teleporter ordering, dynamic
  boss creation and final gate conditions remain unverified.
- Recycle Lab section `04/0` has four native records missing from the workbook's
  checkpoint note. Their reachability and purpose must be observed.
- Dynamic actor producers, actor identities, route topology and all exits are
  not exhaustively derived by these two static placement lists. The ledger must
  retain explicit gaps until those sources are audited.

Current-build save/load, rewind and rollback must preserve any newly identified
simulation state. Old snapshot migration is excluded. Native card progress is
a separate persistence contract and must remain intact.

## Reproduction and tests

Run from this worktree using verified non-C: temporary/cache locations. The raw
disc option performs no extraction or whole-disc scan:

```powershell
$env:TEMP = 'G:\Temp\Codex\psxrecomp\x6-parity\scratch\content'
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = $env:TEMP
$env:MMX6_CONTENT_EXE = 'F:\Projects\psxrecomp\_wt-mmx6-local-coop\mmx6\SLUS_013.95'
$env:MMX6_CONTENT_DISC = 'F:\Projects\psxrecomp\_wt-mmx6-local-coop\mmx6\Mega Man X6 (USA) (v1.1).bin'
python tools/inventory_mmx6_coop_content.py --exe $env:MMX6_CONTENT_EXE --disc $env:MMX6_CONTENT_DISC --out docs/COOP_X6_CONTENT.json --check
python -m unittest discover -s tools -p test_mmx6_coop_content.py -v
```

Use `--bin` for an already extracted original `ROCK_X6.BIN`. EXE-only mode
retains checkpoint and mechanic obligations, marks placement inputs absent and
does not imply complete authored placement coverage. The CLI creates new output
files exclusively; `--check` compares an existing report without writing it, so
rerunning extraction cannot silently reset qualification results.

Tests cover truncated headers/payloads, address bounds, checkpoint pointer
escapes, exact placement terminators, missing terminators, archive gaps/counts,
frozen metadata invariants, original-source reproduction and altered-revision
rejection. Original-source checks skip explicitly when the two input environment
variables are absent.
