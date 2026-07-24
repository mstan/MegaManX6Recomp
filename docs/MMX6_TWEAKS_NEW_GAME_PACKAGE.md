# MMX6 Tweaks New Game composer

`mmx6.tweaks.new-game` is a resolver-backed package for independently
configurable starting-status changes. The first reviewed tranche contains 18
of the 74 controls in MMX6 Tweaks v2.6.1's **New Game Status** tab:

- X and Zero starting Life Up counts;
- X and Zero starting Energy Up counts;
- X and Zero starting Hunter Rank with the matching Soul count;
- eight independent Heart Tank checkboxes; and
- four independent Sub Tank checkboxes.

Every item is its own left-pane feature. Upgrade counts are right-pane integer
choices only while their feature is enabled. Disabled means the upstream
`+0`/stock behavior and emits no write.

## Why this uses a trusted resolver

Every New Game source option injects the same three-write foundation:

| Raw source offset | Guest address | Size | Replacement SHA-256 |
|---|---:|---:|---|
| `0x1D930B9C` | `0x8001E1B4` | 8 | `650ea19428557bf4849f703b30a7daf8c75486655f8c3f7d5ead17b6adc7f159` |
| `0x1D9965F8` | `0x800769E0` | 180 | `951fae5d7f169f3381d16d607f6a0cbb7de2b117573f4dd003c43a11c6b73154` |
| `0x1D99A630` | `0x8007A1C8` | 16 | `a9e8b1c571af2d9cae794992fc97e48e92024a19f3556fea80ebce2e19ed5e4e` |

Copying those writes into every feature would create intentional overlaps and
make resolution depend on feature order. The game-owned
`src/mods/mmx6_new_game_resolver.cpp` instead registers
`builtin:mmx6-new-game`. It reads all enabled rows, composes one final 180-byte
template, and emits the three fully guarded foundation writes exactly once.
Packages cannot supply or replace this native resolver.

The converted fields are:

| Source controls | Template field | Composition |
|---|---:|---|
| `LifeUp01`, `LifeUp02` | `+0x24`, `+0x28` | one byte, `0x20 + 2 × count`, count 1–16 |
| `EnergyUp01`, `EnergyUp02` | `+0x3C`, `+0x40` | one byte, `0x30 + 2 × count`, count 1–8 |
| `CharRank01`, `CharRank02` | `+0x5C/+0x6C`, `+0x60/+0x70` | rank byte plus its upstream-derived `u16le` Soul threshold |
| `HeartTankAdd01..08` | `+0x88` | independent bits `0x01..0x80` |
| `SubTankAdd01..04` | `+0x50` | independent bits `0x10..0x80` |

## Generation and validation

```powershell
py -3 tools/tweaks_new_game_psxmod.py `
  --stock "F:\path\Mega Man X6 (USA) (v1.1).bin" `
  --out "build-local\MMX6-Tweaks-New-Game.psxmod" `
  --report-out "build-local\newgame-report.json"
```

The deterministic archive contains only a manifest, conversion report, and
README. It contains no package-supplied code, declarative patch duplicates,
asset payloads, or derived disc.

The converter reparses the complete 74-control GUI catalog and writes every
control to `source_controls` in the report as `converted` or `deferred`. For
each converted integer it exercises minimum, interior, and maximum values. For
each checkbox it exercises the enabled value. Every isolated result must have
the exact upstream closure and must produce the same final foundation bytes.
All-feature minimum and maximum combinations must also match upstream and
remain identical when feature order is reversed.

Run the local tests with:

```powershell
$env:MMX6_NEW_GAME_TEST_STOCK = "F:\path\Mega Man X6 (USA) (v1.1).bin"
$env:PSXRECOMP_RUNTIME_INCLUDE = "F:\path\psxrecomp\runtime\include"
py -3 -m unittest tools.test_tweaks_new_game_psxmod -v
```

## Deferred ledger

The remaining 56 catalog controls stay visible in the conversion report rather
than disappearing into a broad TODO. Important reasons include:

- rescued-Reploid Life/Energy parts also synthesize `RescRepFoundTable`; their
  foundation bits alone are not full parity;
- character availability derives `ArmorParts`, menu defaults, and starting
  character state;
- rank and Soul fields must remain one feature; independent raw Soul editing is
  intentionally not exposed;
- Parts Set controls pack several related fields;
- rescue marking, randomized parts, debug stage/checkpoint, and Zero debug
  controls have state, determinism, or product-semantics questions.

Those controls can join this package only when their complete isolated and
combined source algebra is proven. The resolver is intentionally structured so
new reviewed fields can be added to the one shared template without changing
the independence of existing rows.
