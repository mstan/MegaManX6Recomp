# Narrow Recycle hidden-portal admission

This implements only original Recycle stage4/section0 primary record18,
`800F2B0C`, category0/type1C/subtype1. R14 remains **unverified** in local
co-op and netplay until an actual native counterexample and fixed-candidate
regression are retained. Source details are in the independent R14 audit
commit `aed701c155ed4b7d50fbb986c07fa87d8a14a523`.

## Contact and deferred owner

The replacement is `800EC780`, the original action1 helper selected by
`800F3914` and called by the phase1 `JALR800EC704` (return `800EC70C`). It
requires the exact original stage, origin-bound pool slot, type/subtype,
phase/action/subaction and collision pointers. SHA256 guards bind the selected
member6 code/dispatch/collision closure and original EXE contact, controller
order, player transition and stage-init/destination routines. It rejects
different code at the reused overlay address.

The scanner first calls `80029E7C` at `8002A12C`. For this category0 record,
high byte3 state0 becomes10h at `80029EF8` before allocation; PLAY+68=3 bypasses
that state step. The producer's complete188-byte native extent is SHA guarded.
The scanner stores the authored record pointer in instance `+10` at `8002A180`,
then `8002A254..8002A264` ORs1 into byte0. Stage reset `8002A380/384` restores
byte3's low category nibble and byte0's authored70h bits, advancing8 per record.
The guard accepts four complete eight-byte variants: byte0=0 or1 crossed with
byte3=00 or10h; the other six bytes stay exact. Every byte0 and byte3 value is
tested independently, with corruptions of the remaining bytes rejected.
Other scanner state-machine values remain outside this qualified source
closure. No broad high-nibble/flag mask or workbook replacement bytes are used.
See [the CP3/native-record follow-up](COOP_RECYCLE_CP3_NATIVE_ENTRY.md).

Both actors must be allocated, visible, healthy, alive and control-ready in
the current fixed X/P1 and Zero/P2 roster. Scene/passenger, pause, transition,
failed and already-projected worlds are excluded. The survivor/scene native
world already has its owner and is left to its existing path.

The wrapper calls original pure `8002D654` first for resident P1. A P1 contact
retains native P1 priority. Otherwise it uses the existing Zero projection and
probes P2 with the original collision helper. Only a genuine P2 contact calls
the original action1 helper once under Zero. Scene ownership is armed only
after the original helper actually admits action2. A successful probe alone
does not establish admission. No portal action, campaign or transition flag
is synthesized by the adapter.

Existing `scene_owner=2` then places Zero in the one original world pass.
Native `800EBEC0` therefore saves/clears **Zero's** `PLAYER+68` through portal
`+88`, and later `800EC8F8`/`800EBFB4` continue with that same owner. The native
portal controls all shared freeze, fade, timer, coordinate and41h writes.
There is no second portal or whole-world update.

## Old-stage passenger release

This use of the existing scene controller is restricted to both living actors:
its first call starts passenger-out phase2. The earliest phase3 landing check
comes after the next original portal setup, which writes `PLAY+10=2` at
`800EBF08`. That lock persists until native restoration.

At the native41h transition, the controller executes player update `20C60`
before enemy update `20C78`. `8003A628 ->8003B870` writes `PLAY+1C=1` at
`8003B8A4` and body phase3 at `8003B904` before portal restore can clear its
`PLAY+10` lock. The existing scene gate requires both locks clear and owner
phase1, so it cannot begin passenger-in on the old map through this closure.
Native `8001EB48` calls `8001E32C` on fade-idle and returns with next major8;
new-stage initialization is not nested inside that projected world pass.
Major8 entry `8001E914` clears checkpoint `PLAY+1D` at `8001E930` before selecting
major9, so CP0 is the source-derived destination expectation for this path.
The actual next-stage initializer calls `8003BD24` at `8001E264`; its existing
co-op entry hook clears scene ownership/enrollment before normal destination
arrival and enrollment. No synthetic destination-generation token is added.

The wrapper reuses `scene_call`, already in the canonical digest/snapshot guard
and activation reset. Its future-restored scalar context uses `STATE_WORDS`
tag47. Scene ownership/phase already belong to `HostState`; no new persistent
host fields or snapshot ABI are introduced. Rollback/state availability and
semantic profile identifiers are unchanged in this branch; integration owns
any required compatibility/profile changes.

## Fixture and integration

`tests/test_mmx6_coop_recycle_portal.c` includes the actual plugin and the SDK
replacement dispatcher. It reads a complete original EXE and only native
member6 from the raw disc, checking both SHA256 identities. Its guest calls are
bounded external native-contract doubles. They validate projection, native
admission ownership, pointer/pool/resource restoration, snapshot capture and
guard hashing,31 single-world deferred updates, no old-stage passenger-in,
and the existing native-init reset. They do **not** execute the native portal,
load a map or qualify rendered/gameplay behavior. No native payload is bundled.

The fixture also checks native P1-only negative control, P1 tie priority, no
contact, immunity, declined admission, lifecycle and context gates, wrong
origin/subtype/caller/stage/roster, every guarded code-span corruption and exact
record admission variants. Checks remain active under `NDEBUG`.

Build the fixture with C99, function/data sections and linker garbage
collection, using these sources:

- `tests/test_mmx6_coop_recycle_portal.c`
- `src/mods/mmx6_coop_lifecycle.c`, `src/mods/mmx6_coop_assets.c`
- SDK `runtime/src/mod_function_replacements.c`, `runtime/src/psx_sha256.c`

Include `src/mods` and the selected SDK `runtime/include`; invoke the resulting
executable with `<original-SLUS_013.95> <original-raw-disc-bin>`. All output and
process TEMP/TMP must remain on F/G. GCC15.2/O2 and Clang22.1.8/O2 production
fixture runs pass. Both compilers also accept production C99 plugin source
against the old SDK headers; Clang emits its pre-existing CPUState typedef
warning.

Modern interpreted overlay dispatch consults the replacement service in
`dirty_ram_interp.c` (direct entry and indirect call paths). Integration must
add `0x800EC780` to title `mod_function_entry_funcs` so a future fresh overlay
AOT build emits its hook. This branch edits no game configuration, SDK, CMake,
stage tick or input routing. No title build or game has run.

Actual qualification still needs the source-bound live portal slot, ordinary
P1 control and P1-far/P2-only contact, one native setup/fade/41h, actual stage20/
section1 loading and selected checkpoint, safe full-foot arrival/camera bounds,
retained resources and independent control for both actors. Native return/exit
is separate. Local and netplay must be tested independently on one exact
candidate. Other portals, subtypes, alternate routes, refights and opposite
rosters are outside this change.
