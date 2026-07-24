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

## Deliberately deferred

The following IDs are not declared by package version 1.0.0:

- `DashSpeedCont01`, `DashSpeedCont02`: their source implementation has an
  intentional shared rewrite/overwrite and belongs in a later composed
  continuous-dash resolver after hot-path behavior tests.
- `MachDashDuration01`, `MachDashSpeed01`, `MachDashInput01` through
  `MachDashInput03`, `MachDashWait01` through `MachDashWait04`, and
  `MachDashCancel01` through `MachDashCancel04`: these require a coherent Blade
  Mach Dash state model and overlap tests. Radio alternatives should become
  three dropdown features, not mutually conflicting packages.
- `MachDashDuration02`, `MachDashSpeed02`, `MachDashSpeed03`: quarantined.
  The source writes do not provably target code installed by the combinations
  that expose the controls. Byte-for-byte conversion is not accepted as
  behavior proof.
- `MachDashImmunity01`: deferred with the cancellation foundation.
- `CutsceneSouls01`, `CutsceneSouls02`: deferred because the shared source
  foundation writes executable bytes in member 797's padded allocation outside
  its logical payload. No owner is claimed until that lifecycle is explicit.

`MachDashUnlimited01` is not part of this package because it already exists as
the native feature `blade_mach_dash_unlimited_repetitions`.
