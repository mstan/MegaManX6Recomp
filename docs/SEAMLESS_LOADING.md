# Mega Man X6 Seamless Loading

Branch: `spike/mmx6-seamless-20261004`. Tracking: `beads-eio.1.36` (stock game),
`beads-eio.1.37` (asset mods). Reference design: Tomba 2 `075335f`/`5a4e3e0`.

Seamless Loading removes the "Now Loading" screen without fast-forward, faster
guest CD timing, audio discard or gameplay snapshots. It is enabled by default
in Mods; disabling it restores the original loader. The catalog no longer
offers the generic CD Speed or host-paced Fast Loading mods. Target: SLUS-01395
v1.1 (`disc_sha256 91ef53c1...`).

## Player setup

On first activation, native code reads `ROCK_X6.DAT` (50,913,280 bytes) and
`ROCK_X6.BIN` (1,665,024 bytes) from the mounted disc and writes a verified pack
(52,578,304 resident bytes). No Python, compiler or extraction step is
involved. Packs live in `%LOCALAPPDATA%/MegaManX6Recomp/seamless` on Windows,
`$XDG_CACHE_HOME/MegaManX6Recomp/seamless` (or `~/.cache/...`) elsewhere. The
name includes a hash of the mod-plan fingerprint (package order, selections,
disc writes/overlays, derived discs, source disc hash). Every launch verifies
the pack's per-archive SHA-256; a corrupt or truncated pack is rebuilt, and a
failed rebuild leaves the original loader active. The four most recently used
packs are kept. Packs contain licensed game data and must not be distributed.

Music, voices and movies (`XA/*.XA`, `STR/*.STR`) stay on their streaming paths.

Developer-only environment variables: `MMX6_SEAMLESS_CACHE` (cache directory),
`MMX6_SEAMLESS_TRACE=1` (per-load diagnostics with guest-cycle cost),
`MMX6_SEAMLESS_RETAIL=1` (prepare, then bypass, for A/B). Always-on counters:
TCP `{"cmd":"mod_counters"}` (`mmx6.seamless.*`).

## Original loader (from the original executable)

| Address | Role |
| --- | --- |
| `800147D0` / `80016780` | Boot: read the DAT (243 entries) / BIN (59 entries) descriptor headers into `800E0398` / `800E0B58` (`{absolute LBA, bytes}`). |
| `80014F70` → `80015230` | Start a packed DAT resource: header sector lists `{type<<16, bytes}` sub-resources; Setmode 0xA0 (2x, 2340-byte sectors), Setloc, ReadN. |
| `8001642C`, `80016858` → `80014E60` | Start a whole-file DAT/BIN read to a RAM destination. |
| `8001531C`, `800165A4` | Data-ready callbacks: packed / whole-file. Read the 12-byte header with `CdGetSector` (`80064CB4`), check the LBA, dispatch. |
| `8001668C`, `8001574C`, `80015A0C`, `80015630` | Packed handlers: RAM copy, VRAM (32-slot ring at `800CF998`, deferred LoadImage), SPU bank (deferred `SsVabTransBodyPartly`), SEQ. |
| `80015C5C` | Deferred queue drain, run once per frame by the main loop (`8001651C`). |
| `80015EC0`, `80016178`, `8001494C` | Blocking waits: yield a frame and draw "Now Loading" until status `8009509C` = 2 and the queue is empty. |
| `800528F4`, `80052E44` (`80014B78`) | Gameplay actors that stream a packed resource / an overlay in the background and poll. |

X6 resources are **not compressed**. Load time is CD transfer at 2x plus the
queue's per-sector LoadImage/SPU work. Measured retail stage entry: ~470
frames of "Now Loading" and logo.

## Adapter contract (`src/mods/mmx6_seamless.c`)

Function filters (`game.toml` `mod_function_entry_funcs`, regenerated) on
`80015230`, `80014E60`, `80064894` (CdReady) and `80064CB4` (CdGetSector):

1. A load start is served only when its original call site is one of the 22
   blocking sites (positive list; the caller is read from the original stack
   frame). Background actor loads and unknown callers keep the original CD path
   and timing; overlapping them with play is their design, and serving them at
   once would move their queue work into a gameplay hitch and change spawn
   timing (counter `background_original`).
2. The live loader code/data (5 ranges, 6.6 KB) must match the original
   executable (SHA-256 guard), and the game's in-RAM descriptor tables must
   agree with the resident archive headers entry by entry.
3. The start routine's guest-visible state changes are applied without driving
   the drive. Then, per sector, the original callback runs with a synthesized
   header (BCD MSF, Form 1 subheader, EOR|EOF on the archive's last sector);
   `CdReady` returns DataReady and `CdGetSector` copies resident bytes with the
   CD-DMA path's RAM effects (overlay capture, executable invalidation). After
   each sector with queued work, the original drain (`80015C5C`) and
   `DrawSync(0)` run. The callbacks issue their own Pause and set status 2.
4. Any inconsistency leaves the game's own 600-frame timeout/retry to recover
   with the real drive and disables the adapter for the session.

The adapter never changes guest clocks, CD timing, XA streaming or audio. Guest
cycles spent in the pump are the game's own install work (mostly SPU/VRAM queue
jobs, ~21k cycles per sector) and land in frames that are already black.

## Validation (2026-10-04)

- Stage entry from stage select, savestate A/B, confirm → stage loop
  (`800CCED0` = 0x0A): retail 527–559 frames, seamless 112–118, across four
  entries (X and Zero, three stages). No "Now Loading" or logo screen; fade-out
  and stage fade-in unchanged; gameplay screens identical to retail; player live.
- Title, menu, memory-card continue and stage select load normally.
- `mmx6_seamless_store_test` (owner disc): cold/warm preparation, all 302
  member hashes, loader guard against the disc's executable and rejection of a
  modified one, asset-mod plan isolation and served modified bytes, corruption
  repair, fail-closed fallback. `mmx6_preloaded_mods_test`: 16 packages,
  Seamless Loading the only default-on feature, opt-out plan is empty.
- `tools/mmx6_seamless_catalog.py --check` regenerates the catalog from the disc.

Not covered by automation (owner manual testing): boss doors/WARNING, boss
defeat → weapon get → stage select, checkpoint/death retry, ending. No
exhaustive playthrough is claimed.

## Asset mods (phase 2)

Preparation reads the effective mounted disc (sector patches and derived
discs), so a modified member is served as modified and counted (`N/302 members
differ` in the log); a changed plan never reuses another plan's pack. Code mods
that change the loader fail the guard and use the original loader.
Compatibility of specific asset-mod combinations is tracked in `beads-eio.1.37`.

## Reproduce checks

```text
cmake -B build -DMMX6_TEST_DISC="<path>/Mega Man X6 (USA) (v1.1).bin" ...
ctest --test-dir build -R "seamless|preloaded|release_config" --output-on-failure
py -3 tools/mmx6_seamless_catalog.py "<path>/Mega Man X6 (USA) (v1.1).bin" --check
```
