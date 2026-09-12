# Original-disc AOT overlays

Mega Man X6 USA v1.1 (SLUS-01395) packages native code for 56 original-disc
archive images. Every Windows and Linux release freshly extracts, compiles,
audits and stages the full configured inventory, including with `-SkipRegen`
or `--skip-build`. No historical runtime capture or cache is a build input.

The declarative [profile](../aot/overlays.json) consumes psxrecomp's shared
`sector_extent_members` method: little-endian `{sector offset, byte size}`
descriptors, archive-relative sector offsets, consecutive aligned payloads.
The shared implementation has no title-ID branches.

## Evidence from the original executable

The archive initializer at `0x80016780` reads two header sectors from
`ROCK_X6.BIN`. At `0x8001681C` it adds each descriptor's first word to the
file LBA; its second word is the byte size. The loop copies 59 descriptors.
`0x80016858` selects by table index and passes the destination through to
`0x80014D50`, which copies sectors verbatim, including the member's leading
logical ID. The final transfer rounds the byte count to four bytes.

Load destinations are established by call sites and selector tables:

| Table indices (decimal) | Destination | Original evidence |
| --- | --- | --- |
| 0, 1 | `0x801EA000` | Calls at `0x80013CDC`, `0x80013CF0` |
| 2-32 | `0x800E9860` | Selector table `0x8006DB78`, destination word `0x80010000`, call `0x80013E7C` |
| 33-40 | `0x800FA000` | Selector table `0x8006D9EC`, call `0x80013D54` |
| 43-45 | `0x800FA000` | Immediate selections, call `0x80052E94` |
| 46-58 | `0x800FA000` | Selector table `0x8006DC50`, call `0x80013E40` |

Index 13 is a pointer table with no established callable roots. Indices 41
and 42 contain only four-byte IDs. All three are explicitly excluded from
native code generation; their descriptors still participate in full archive
extent validation. All other 56 members have static callable roots. A BIOS
resident helper makes 57 independently compiled recipes.

The profile pins the original disc SHA-1 and checks loader instructions and
selector-table words. The archive parser verifies table termination, count,
bounds and exact coverage after sector alignment. The previous heuristic
treated sector offsets as opaque IDs and assumed a one-sector header, moving
each member 2048 bytes early and omitting its final bytes. The shared reader
now prioritizes explicit extents; synthetic regression tests cover this case.

## Validation and limits

`AOT_CACHE_AUDIT.json` in each package records every native pair and its
hashes. The audit requires nonempty guarded native coverage for every recipe,
the current code-generation ABI, and matching original bytes. It does not
prove every indirect entry or execution path has been found. Interpreter and
runtime compilation fallback remain enabled. Code-changing mods can invalidate
stock code guards and need fallback; this release does not claim AOT coverage
for every mod combination.

Gameplay spot checks should include the opening stage, several selectable
stages and boss transitions, X/Zero where available, and menu/save transitions.
Movement, graphics, audio and performance remain the user's final validation.
