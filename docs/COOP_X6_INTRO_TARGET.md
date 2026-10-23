# Intro type1 action1 targeting (beads-tpy3)

This change addresses one native proximity decision. It does not qualify enemy
AI, damage, collision or stage coverage as passed.

The read-only USA v1.1 disc supplies ROCK_X6.BIN member2, 74,784 bytes,
SHA256 `d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`,
loaded at `800E9860`. Its complete 21-word action1 leaf at `800EB14C..800EB19F`
matches the guard in `mmx6_coop_intro_target.inc`. The leaf reads subtype at
instance+2, signed integer enemy X at instance+0A and signed resident player X
at `800970AA`. It sets action+5 to2 only when the absolute difference is
strictly less than112. It reads no player Y, character, combat body or resource
bank, and invokes no other helper.

Intro placement25 at `800FA2DC` is category0/type1/subtype1 at(416,1080).
With resident X at144, its native distance is272 even when Zero is nearby.
The native chain is `8006DC6C -> 800FA424`, type1 slot `800FA428 -> 800EAFB0`,
phase1 `800FAB4C -> 800EAC8C`, action1 `800FAB5C -> 800EB14C`.
The indirect call at `800EACCC` supplies a0=instance.

The wrapper requires gameplay mode0A, stage0/section0, no pause/scene lock,
the exact chain and all21 native instructions. The actor must be an aligned
member of the48-slot enemy pool `8008EF48..80090C88`, stride9C, active,
type1/subtype1 and phase1/action1. Eligible players must be alive, active,
in native player phase1 with a controllable action, positive nonfatal HP and
no ride/scene lock. Absent, departing, arriving, dying and fallen players
cannot be selected. Scene passengers are excluded.

Signed integer X distance selects the nearer eligible player; equality keeps
P1. When Zero is selected, only the two bytes at `PLAYER+0A` are temporarily
projected. The original leaf runs once, its return is retained, and that
halfword is restored. The actor's native action change remains. Survivor
Zero's already projected world takes the unchanged native path. Neither the
whole enemy update nor a combat/contact callback is wrapped.

`intro_target_call` prevents recursive interception, blocks snapshot readiness,
participates in the canonical state digest guard array, and resets on
full activation, rather than unrelated unit-selection completion. Its
future-restored X value uses `STATE_WORDS` tag46; the nested
guest call uses the existing architectural-register record. No host pointer
or new stable host state is serialized. Rollback and savestates remain disabled
in the netplay profile. Integration advances the compatibility revision to
`mmx6-x-zero-delay-v11` for this simulation change.

## Dispatch and verification

The modern SDK dirty interpreter checks replacements both at surfaced entries
and local transfers (`dirty_ram_interp.c`, including its local indirect-call
path). This reaches the action-table helper during current interpreter-based
overlay runs. The main EXE generated dispatch contains no800EB14C, so no main
EXE regeneration is needed for this overlay-only site.

`game.toml` adds800EB14C to `mod_function_entry_funcs`. The emitter then emits
one replacement check if that function is compiled, after the existing entry
hook and before its original fallback body. The SDK's focused replacement
codegen test passes. `compile_overlays.py` forwards game.toml through
`--ws-config`, but its explicit seed collection reads `[[overlays]]` entries,
not this hook list. Therefore this change does not claim that an unobserved
helper becomes an exported AOT entry automatically. Fresh AOT discovery/export
and runtime interception remain to be qualified; old ABI31 caches are not
evidence for the modern SDK.

The actual-plugin fixture `mmx6_coop_intro_target_test` uses isolated guest RAM
and the real SDK replacement service. Its independent leaf stub implements
the source-proven native proximity contract. The native negative control
leaves the robot in action1 with P1 at144 and Zero at400; the wrapper invokes
that leaf once, enters action2 and restores all guest RAM except that native
action byte. It checks tie-to-P1, the strict112 boundary, ineligible players,
survivor/projection/pause/scene gates, every changed instruction, invalid pool
alignment and wrong handler identity. The fixture proves host projection and
guard behavior; it does not execute the actual native game.

GCC and Clang22 Windows GNU pass this fixture and the actual plugin
snapshot/digest fixture with the new guard. The legacy SDK also passes the
projection fixture, and the plugin compiles as C99 against both legacy
a502-based and modern SDK headers. Clang's existing duplicate
CPUState typedef warning in SDK headers remains unchanged.

Example focused build (run at the game root with TEMP/TMP set under G:):

```powershell
$sdk = 'G:/Temp/Codex/psxrecomp/x6-parity/worktrees/sdk-bridge'
$out = 'G:/Temp/Codex/psxrecomp/x6-parity/build/intro-target/intro-gcc.exe'
& 'C:/msys64/mingw64/bin/gcc.exe' -std=c99 -O2 -ffunction-sections -fdata-sections -Isrc/mods "-I$sdk/runtime/include" tests/test_mmx6_coop_intro_target.c src/mods/mmx6_coop_lifecycle.c "$sdk/runtime/src/mod_function_replacements.c" '-Wl,--gc-sections' -o $out
& $out
```

## Native before/after comparison

The [R13 native receipts](COOP_ENEMY_ADMISSION_BASELINE.md) now observe the
counterexample and fixed response through original input, with X held at144.
On immutable v10 executable `a2f0d2c9...`, Zero admits original placement25
through the camera scanner, approaches within112, and leaves the exact bound
actor waiting in action1 across54 samples. A native jump crosses the observed
terrain step; Square damages that actor without moving X.

On immutable v11 executable
`43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7`,
the same origin-bound actor enters action2 at tick590 while signed integer
positions are enemy416/X144/Zero309. P1 stays fixed in all197 observations.
After native Square, the live actor's HP drops12->4 before its slot is freed.
The original report's failed attack-window reduction is retained; a separate
read-only reanalysis recovers the already-recorded HP transition. It does not
rewrite that report or invent a new runtime pass. Both composed response and
interaction captures were inspected.

Debug and production candidates build, with27/28 checks passing initially;
the missing packaged hook entry was corrected and the one failed configuration
check then passed in both. Target projection, snapshot/digest guard and native
qualification parser tests pass. The build logs and exact receipts remain in
the named G: evidence root. These local results do not transfer to a new SDK
or executable.

Paired targeting, an independent once-world runtime counter, and native
near-P1/tie/absent/fallen/pause/survivor cases remain open. Facing at800EACF8,
action2 range at800EAE24 and every other AI helper remain separate checks.
This bounded action1 fix does not establish sustained nearest-player AI or
pass the aggregate R13 comparison.
