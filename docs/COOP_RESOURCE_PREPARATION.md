# Bounded resource preparation and fixed runtime admission

This implements the resource-planning preparation step after
[canonical descriptors](COOP_ROSTER_DESCRIPTORS.md). **The public runtime
still admits only native X/P1 with ordinary Zero/P2.** The native Zero
selector filter, projection/restoration paths, menu/HUD behavior, compatibility
profile, diagnostic schema and state codec are unchanged. There is no X/P2,
R8/R9, audio, campaign or netplay qualification claim.

`mmx6_coop_resources.h/.c` prepares typed views from a validated canonical
roster and one selected seat using the existing BIN/DAT parsers. It does no
I/O, allocation, guest call, input sampling or guest write. Its views refer to
caller-owned archive buffers and must be consumed before those buffers are
freed. It validates logical descriptors, member types, extents, source/UI sizes
and the complete bounded actor allocation; mounted-disc/content identity
remains the caller's contract. It does not hash original assets or assert
that a VAB, texture or native actor is resident/ready.

`mmx6_coop_resources_fixed_runtime_admit()` is a separate, explicit temporary
boundary. A canonical Zero/P1 + base-X/P2 descriptor can prepare resource
views in helper tests, but is rejected by public runtime admission. Invalid
descriptors are rejected too. Native body/campaign inconsistency and active
Black Zero are refused by the roster resolver before resource preparation.
Native flags are read-only and remain unchanged.

## Full allocation before copies

The plan starts compressed graphics at offset0, then appends each rounded
16-byte source span in order: graphics, native assembly, source palette.
It reserves a full `4000h` working-palette window, then appends the actual
menu-layout span. The source palette must be nonempty and at most `4000h`;
all source/menu spans must be nonempty. Every alignment, addition and
32-bit guest-offset conversion is bounded before any copy.

| Measured native source | Assembly | Source palette | Working palette | Menu | End |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero/DAT85 | 229680 | 263776 | 266432 | 282816 | 291852 |
| Base X/DAT86 | 245296 | 286704 | 289392 | 305776 | 315028 |

These offsets come from the source sizes pinned in
[COOP_SEAT_CHARACTER_AUDIT.json](COOP_SEAT_CHARACTER_AUDIT.json). They preserve
the existing valid Zero layout. The old approximate `sum+4040h` and menu-end
checks were insufficient for a malformed oversized palette: with source sizes
`16,16,30000h`, menu16 and capacity40000h, both old checks fit, while copying
that source again at the working-palette address would extend past the arena.
The new planner rejects it before copies. It also rejects `SIZE_MAX`, 32-bit
alignment overflow, short capacity and truncated/incorrect typed archive views.

The preparer maps graphics/assembly/palette subassets3/10/0; menu graphics,
font, colors and layout6/7/8/9; common UI/icons1/2; and the actor descriptor's
native portrait records. Exact types and fixed UI/portrait lengths are from
the pinned original metadata, not X4/X5 offsets. For the first two resource
sets, these are BIN1/type3D/DAT85/portraits165-166 and
BIN0/type3C/DAT86/portraits163-164. The selected overlay also fits the native
B000h aperture and the plugin's actual destination array.

## Current plugin wiring

Only the resources header include, loader/admission region, enrollment guard
and existing idle-enrollment block changed. The controller resolves a local
canonical roster after the original initialized idle handoff and before
private initialization. It repeats that check when `ready==1` but native
respawn/new-stage initialization invalidated enrollment, so cached Zero assets
cannot silently admit a different roster. A refusal sets the existing failed
state and unwinds `inside`; it neither projects nor initializes P2.

Both `load_assets(roster)` and `enroll(cpu,roster)` independently enforce the
fixed runtime boundary. The loader obtains both archive buffers, validates
the complete selected resource plan, allocates retained host buffers and only
then copies to existing guest destinations. It preserves the existing source
order used by the snapshot asset hash, Zero immutable bank/cache identity,
activation teardown, menu memory and retained UI path. Overlay padding is
deterministically zeroed. No persistent roster or resource-plan state was
added; the current fixed resource set still uses the existing state codec.

Native P2 initialization remains original8003BD24, character-indexed native
parts8003D718, physics8003D630 and idle8003AD18, once under existing Zero
projection. `enter_zero()` and both leave paths are untouched: original P1
body/overlay/seven resource pointers are restored exactly; private calls
restore full PLAY/camera while the shared-world exit retains shared mutations
and restores native campaign character/form. Actual opposite-resource
projection will require explicit canonical roster/generation state in
digest/snapshot/reset plus symmetric menu/HUD/retained/deferred/audio closure
before public admission or selector expansion.

## Focused evidence and integration

The synthetic archive fixture `test_mmx6_coop_resources.c` uses real parser
boundaries and measured sizes, with generated fill bytes, not original assets.
It checks exact Zero/base-X views and offsets; all five supported X-primary
admissions; the rejected X/P2 public boundary; stale output clearing; malformed
rosters/seats, archive truncation/types/UI/portrait lengths; palette windows;
exact capacity limits; and overflow. Archive bytes remain unchanged.

`test_mmx6_coop_resource_admission.c` includes the existing private-effects
fixture under a renamed main without editing it. All its original projection,
native-helper-model, menu and retained-packet checks still run. Added checks
invoke the actual controller with fresh and cached resources and assert that
unsupported, inconsistent, impossible and Black Zero identities fail before
disc reads, any native dispatch, CPU/RAM or private-pool mutation. Direct
loader/enrollment calls cannot bypass the admission boundary.

Both fixtures pass GCC15.2 and Clang22.1.8 debug/production cells (8/8), with
explicit checks active in production and at most two compiler processes.
Exact commands, source/binary hashes and original logs are retained under
`G:/Temp/Codex/psxrecomp/x6-parity/helper-qualification/roster-resources-754f8ca/`.
The actual-plugin fixture uses SDK6212e68066a6977dc587e8fca71f27dac9b002fc.
No title/game build, original native execution, card access or ledger change
was performed. A newly built candidate still needs native loader/enrollment
regression and fresh applicable qualification; source/helper results do not
transfer earlier artifact passes.

The normal title's existing `src/mods/*.c` CMake glob discovers the new module.
Central fixture registration must link `mmx6_coop_resources.c` and
`mmx6_coop_roster.c` for actual-plugin fixtures that retain the controller;
no new sampler or SDK stubs are needed. The pure resource fixture also links
`mmx6_coop_assets.c`. The admission fixture uses lifecycle/assets/resources/
roster plus the existing SDK SHA256 helper and section garbage collection,
as the unchanged private-effects fixture does. This lane made no CMake,
SDK, game.toml, selector, stage/input routing or profile edits.
