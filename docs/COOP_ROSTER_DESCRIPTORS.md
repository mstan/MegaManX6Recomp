# Canonical native roster descriptors

`mmx6_coop_roster.h/.c` implements the logical first step of the
[opposite-roster plan](COOP_OPPOSITE_ROSTER_PLAN.md). It is intentionally
detached from the plugin: no selector, native input, character initialization,
asset load, profile, snapshot, SDK or runtime behavior changes yet. Opposite
rosters and R8/R9 remain unverified.

The caller passes the actual initialized P1 body character/form
(`PLAYER+02/+E7`), native campaign character/form (`PLAY+38/+5E`) and unchanged
native flags (`PLAY+5F`). `mmx6_coop_roster_resolve()` requires two valid and
identical native identities, then resolves these policies:

| Native P1 | Private P2 |
| --- | --- |
| X, native form0..4 | Ordinary Zero, form5 |
| Ordinary Zero, form5 | Base X, form0 |

Every accepted roster includes Zero. Shared flag bit20 selects Black Zero's
native portrait6 when the Zero actor is projected, including Zero/P2 with
X/P1. Resolution therefore explicitly returns `black_zero_unsupported` in
both directions. It neither clears that bit nor substitutes ordinary Zero
assets. Other flag bits are left intact and do not become new availability
gates. Original campaign selection owns those gates; current early-game
private Zero does not require its native unlock. The helper grants no unlock
and cannot enable Zero in the existing filtered selector.

The result has a `resolved` marker and two `Mmx6CoopRosterActor` descriptors
with character, form, BIN member/type, DAT member, native portrait index and
portrait graphics/palette record. `mmx6_coop_roster_validate()` verifies every
resource field against the source-owned native form mapping and verifies the
fixed counterpart policy. A valid Falcon descriptor in P2 is still refused
when Zero/P1 requires base X. These are archive identities, not loaded asset
handles, pointers, hashes or assertions of runtime readiness.

Both functions return an explicit `Mmx6CoopRosterReason`; the reason string
helper performs no allocation or I/O. Any resolution refusal clears a
non-null output, including a prior successful roster. Validation does not
trust the marker alone. It checks internal canonical resources/policy; callers
must resolve current native reads again to compare with changed guest state.
Serialize/hash named fields explicitly in any later state integration.

## Native source and integration boundary

The pinned source and original metadata are in
[COOP_SEAT_CHARACTER_AUDIT.json](COOP_SEAT_CHARACTER_AUDIT.json) and
[COOP_OPPOSITE_ROSTER_PLAN.json](COOP_OPPOSITE_ROSTER_PLAN.json). Native EXE
SHA256 is `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
The module contains no original binary or asset bytes.

Original loader80013BF0 maps X forms0/4 to DAT86, Falcon1 to87, Shadow2 to88,
Blade3 to89, Zero5 to85. X uses BIN0/type3C; Zero uses BIN1/type3D.
Portrait selector800228AC maps X0/Zero1/Ultimate2/Falcon3/Shadow4/Blade5;
80014314..80014398 loads records163+2*index and164+2*index. Thus the two
counterparts use X163/164 or Zero165/166. Ultimate's shared DAT86 does not
erase its distinct form or portrait.

Original8003BDE8/8003BE10 installs the character in body+2, while native parts
helper8003D730/8003D73C installs body+E7. The existing plugin's hook at
8003BD24 is an **entry** hook that invalidates enrollment, not proof that
either initializer has finished. A future plugin integration should read and
resolve P1 at the initialized idle enrollment boundary, after native parts
and before P2 projection/initialization. Re-resolve after native respawn or
new stage initialization. Never derive the campaign from a projected P2 body.

The next plugin step still needs symmetric asset validation, projection,
native enrollment, menu/HUD/retained resources, actor/deferred-effect/audio
ownership and current-build state integration. The first-step helper does not
install private base-X resources or justify removing the selector filter.
No profile or compatibility identity was changed by this detached addition.

## Focused fixture

`tests/test_mmx6_coop_roster.c` exercises all six primary native forms and all
256 native flag bytes; body/campaign mismatch; every out-of-range byte for
character/form; invalid character/form pairings; stale output after refusal;
null arguments; all six resource fields independently damaged in both seats;
invalid resolved markers; and canonical resources that violate the fixed
counterpart policy. Explicit checks remain active with `NDEBUG`.

GCC15.2.0 and Clang22.1.8 Windows x64 each passed debug (`-O0 -g -UNDEBUG`)
and production (`-O3 -DNDEBUG`) C99 cells with
`-Wall -Wextra -Werror -pedantic -ffp-contract=off -static`. The common command
is:

```text
<cc> -std=c99 -Wall -Wextra -Werror -pedantic -ffp-contract=off -static
     -Isrc/mods <configuration flags> tests/test_mmx6_coop_roster.c
     src/mods/mmx6_coop_roster.c -o <owned G: output>
```

The exact commands, source/binary hashes and logs are retained under
`G:/Temp/Codex/psxrecomp/x6-parity/helper-qualification/roster-descriptors-4ac582b/`.
Process-local temp/cache paths were on G: and concurrency was limited to two.
This is portable C logical-helper evidence on the observed compilers/host;
it is not original native execution, a title build, other-platform evidence,
an opposite-roster gameplay result or a comparison-ledger pass.
