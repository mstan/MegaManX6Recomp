# MMX6 Tweaks trusted hooks

`mmx6.tweaks.hooks` is a stock-disc package resolved by game-owned code. The
package contains feature declarations, not native code or a derived image.
Each feature is a separate left-pane entry and can be enabled independently.

## Implemented in 1.0.0

| Feature ID | Tweaks source ID | Runtime ownership |
|---|---|---|
| `voice_title` | `VoiceClip01` | two guarded SLUS sites plus allocation slice `0x8007647C..0x80076493` |
| `voice_boss_intros` | `VoiceClip02` | guarded `ROCK_X6.BIN` member 398 overlay plus allocation slice `0x80076458..0x8007647B` |
| `voice_low_health` | `VoiceClip05` | one guarded SLUS range plus allocation slice `0x80076440..0x80076457` |
| `voice_boss_warning` | `VoiceClip06` | one guarded SLUS site plus allocation slice `0x80076494..0x800764B3` |

The four fixed slices form one named 116-byte allocation at
`0x80076440..0x800764B3`. If any voice feature is enabled, the resolver emits
one full-range zero guard and one deterministically composed replacement.
Disabled slices remain zero. Callsite and member operations are emitted only
for enabled features. Nothing scans packages or resolves selections per frame.

The boss-intro operation targets canonical `disc_user` offset `0x19D3FE18`.
It therefore participates in the normal CD overlay lifecycle when member 398 is
loaded; it does not depend on a permanently patched or derived disc.

Generate the local package only from the supported stock image, an isolated B01
base oracle, and the user-supplied Tweaks source:

```powershell
python tools/tweaks_hooks_psxmod.py `
  --stock "mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin" `
  --b01-base "path/to/isolated/base.bin"
```

The generator verifies the stock SHA-256, exact source payloads and offsets,
strict indexed-member ownership, complete stock ranges, and deterministic
archive bytes before writing `MMX6-Tweaks-Hooks.psxmod`.

## Continuous dash speed resolver

`mmx6.tweaks.continuous-dash` converts `DashSpeedCont01` and
`DashSpeedCont02` into two independent, default-disabled rows with bounded
integer options. A game-owned resolver emits the 24-byte hook foundation once,
composes the Hyper immediate into that foundation, and emits two guarded sparse
immediate pairs for Normal speed. No option lookup or package scan occurs on
the movement hot path; resolution happens before play.

The converter validates the exact `DashSpeedCont_Base` prerequisite closure,
the original `200000..600000` and `60000..160000` domains, five upstream
composition cases, and three complete USA v1.1 stock guards. The actual runtime
install test covers disabled no-op, each row alone, both rows together,
out-of-range rejection, one-foundation ownership, and deterministic repeated
resolution.

## Blade Mach Dash state-machine resolver

`mmx6.tweaks.mach-dash` represents fourteen source controls as one coherent
left-pane behavior row. The right pane contains the three Input alternatives,
four Stop alternatives, four Cancellation alternatives, and bounded Duration,
Speed, and Immunity values. That shape is intentional: these controls rewrite
the same routines and allocations, so pretending they are independent rows
would make valid-looking combinations overwrite one another.

The resolver reproduces the upstream `GuiControl` rules before emitting bytes.
Hybrid plus No Stop resolves to Normal input and restores the stock
Duration/Speed values; No Cancel restores stock Immunity. Operation order is
resolved once before play. Twenty fixed source operations are composed into
one byte map, stock guards must agree on every overlap, and the final plan owns
each contiguous range once.

The converter mechanically compares those twenty trusted C++ operations with
the v2.6.1 source payloads, exercises five representative upstream closures,
and audits 22 J/JAL edges. Targets must land in package-owned allocations,
nonzero stock main-executable code, or nonzero code in `ROCK_X6.BIN` member 2
at its proven `0x801E9800` load address. The actual runtime archive test covers
disabled and enabled stock no-op, all options together, exact Duration/Speed/
Immunity bytes, normalization order independence, collision-free repeated
resolution, and every numeric boundary.

## Zero-technique independent-row boundary

The remaining 17 Zero-technique controls are deliberately not claimed as
converted. `tools/tweaks_zero_techniques_audit.py` pins six source cases that
show why four attractive left-pane rows would currently be dishonest:

- selecting Sentsuizan Down + Special silently changes the Ensuizan input and
  forces Yammar activation;
- selecting Ensuizan Up + Special also forces Yammar activation;
- Guard Shell Down + Special is silently cleared while normal Ensuizan is
  active;
- Air Ensuizan synthesizes direction/button writes from both Ensuizan and
  Sentsuizan input state;
- Hold/Release Sentsuizan synthesizes two input-dependent AND writes; and
- with Retranslation active, those same choices synthesize different
  `ZeroInputHint_*` data writes.

The current built-in resolver receives its package and its package's selection,
not the resolved selections of another package. It therefore cannot know that
the Retranslation package is active, and separate enabled checkboxes would
silently mutate one another to match the old GUI. The audit publishes
`rejected_source_controls`, not `source_controls`, so the coverage ledger
correctly leaves all 17 open. Conversion needs either cross-package resolved
context or a typed input-hint provider, followed by an explicit UX decision
that replaces silent source-GUI forcing.

## Player Mechanics outcome

This branch converts 19 of the exact 49-control Player Mechanics ledger:
three fixed standalone controls, two continuous-dash controls, and fourteen
Mach Dash controls. Thirty remain, all with explicit reasons:

- 17 Zero-technique controls at the independent-row boundary above;
- `Anim0301` and `Anim0401` through `Anim0407`;
- quarantined `MachDashDuration02`, `MachDashSpeed02`, and
  `MachDashSpeed03`;
- `HoverUnlock02`, whose GUI also forces the already-separate
  `HoverUnlock01`; and
- `ShadowSlide01`, whose callsite targets an unowned
  `ArmorByPart_Common` zero allocation in stock.

## Deliberately deferred

The following IDs are not declared by package version 1.0.0:

- `DashSpeedCont01`, `DashSpeedCont02` are no longer deferred; they are owned by
  the composed continuous-dash resolver above.
- `MachDashDuration01`, `MachDashSpeed01`, `MachDashImmunity01`,
  `MachDashInput01` through `MachDashInput03`, `MachDashWait01` through
  `MachDashWait04`, and `MachDashCancel01` through `MachDashCancel04` are no
  longer deferred. They are one coherent behavior in the resolver above.
- `MachDashDuration02`, `MachDashSpeed02`, `MachDashSpeed03`: quarantined.
  The source writes do not provably target code installed by the combinations
  that expose the controls. Byte-for-byte conversion is not accepted as
  behavior proof.
- `CutsceneSouls01`, `CutsceneSouls02`: deferred because the shared source
  foundation writes executable bytes in member 797's padded allocation outside
  its logical payload. No owner is claimed until that lifecycle is explicit.

`MachDashUnlimited01` is not part of this package because it already exists as
the native feature `blade_mach_dash_unlimited_repetitions`.
