# X6 co-op state and netplay audit

This is a source-backed implementation inventory, not runtime qualification.
The baseline is X6 `6cba3f8b4dafe3c4cabd2316593084e87c3f682a` with framework
`a502df3856ae97c2c4860e733fdde3c4f0ad19ec`. The new diagnostic/parser work
below adds observability and prevents unsafe test setup from being counted as
network evidence; it does not establish X4 parity.

## References and actual framework capabilities

- Frozen X4: `50593bca772b600de6911cbfecd40b0f08721147`, framework
  `6f0ccbc6b67fee626de6a7b0945ca3abb26332aa`. `mmx4_coop_plugin.c`
  registers snapshot schema 6 and a canonical `state_digest`; the digest folds
  lifecycle, combat, boss/balance and other host subsystems. Lifecycle snapshot
  readiness explicitly excludes active projection/scene/menu/terrain callbacks.
- X5 is an active worktree, not a frozen passing implementation. At inspection
  its HEAD was `7048d7e5daa0abcf0fd79a22bc63ea293fb6e345` and the plugin and
  snapshot include had uncommitted changes. Observed SHA-256 values:

  | Source | SHA-256 |
  | --- | --- |
  | `src/mods/mmx5_coop_plugin.c` | `7fc0b17af5cd1323223c8bf30e82464ed66aea4c3574d56eb2b910ac98c514a5` |
  | `src/mods/mmx5_coop_snapshot.inc` | `6405735c50d04671a1be6ec98bca730541722d78107229c777ae506e98c01b74` |
  | `tools/test_mmx5_coop_netplay.py` | `1771c5dd59b42ff331fda3acacf48c3207382bfeda5e02e831b0e70fc3ca7538` |

  X5's snapshot schema 9 covers players/effects, lifecycle/input edges,
  scenes/doors, pickups, solids, resource ownership, boss balance, audio and
  texture/menu reconstruction. Validation precedes read, and the readiness
  function excludes live host call stacks. Its netplay harness sends input at
  the host sampler, compares common **simulation** tick core/mod CRCs, and
  requires samples below the peers' resolved-through watermark. These are
  implementation examples; their existence transfers no passing result to X6.
- X6's pinned framework was inspected at
  `F:/Projects/psxrecomp/_wt-mmx6-local-coop/psxrecomp-v4`. It has
  `netplay_status`, `set_input(layer="host")`, `pad_status` acknowledgement,
  `clear_input`, and bounded RAM reads. Its `PSXModNetplayProfile` has loading
  feature fields but **no state-digest callback**, and there is no
  `mod_snapshot.h`. Its core digest log has no `mod=` partition. The X4/X5
  profile initializer and provider cannot be copied into this ABI.

The X6 profile is delay-sync (`rollback_supported=0`,
`savestates_supported=0`), skips the BIOS animation, permits fixed aspect
indices 4:3/16:9/21:9, and forces a widescreen renderer companion for wide
sessions. This is not an adaptive independent-camera implementation. Profile
identity and compilation do not qualify another build, CPU or OS.

## Baseline gaps and persistent-state inventory

All source references in this table are to baseline
`src/mods/mmx6_coop_plugin.c`. Hash fields explicitly in a defined byte order;
do not hash complete native C structs, padding or host pointer values.

| State group | Baseline evidence | Required treatment |
| --- | --- | --- |
| P2 actor and personal pools | `PlayerContext p2` at lines 26–34; capture/project at 103–114; body/shots/trails/effects survive each native pass | Serialize every authoritative pool; include gameplay-relevant bytes in the shared digest. Distinguish native guest pointers from process pointers. P1 normally resides in guest RAM. |
| Live projection backups | `p1`, `saved_overlay`, `saved_play`, `saved_camera`, `saved_resources`, `saved_palette_dirty`; `enter_zero`/`leave_zero_context` at 246–294 | Snapshot only after all projected calls return. Hash authoritative projected state if the core can take a digest during a callback; do not pretend a resumable host C stack was captured. |
| Lifecycle and input | `life`, `previous_input`, `p2_edges`, `returning_body`, `join_phase`, `join_y`; leave/join at 467–538 | Capture each enum/counter/flag explicitly, including Select arming and previous edges, retained health and join history. Test hold/release across restore. |
| Menu ownership | `pause_owner`, `p2_start_previous`, `zero_menu_loaded`, `saved_portrait_colors`; stage/menu code at 817–947 | Preserve native menu owner and edge history plus the original palette backup needed to leave a P2 menu. Restore GPU resources before resuming guest execution. |
| Scene ownership and passenger | `scene_owner`, `scene_phase`, `scene_body`, `scene_y`; scene code at 570–756 | Preserve admission/transport and exactly-once world ownership across script starts, fades, owner death and release. Snapshots must exclude live scene projection. |
| Pickup collector | `pickup_owners[128]`, pickup dispatch at 300–381 | Serialize valid guest actor address/seat associations; retain collector during delayed healing and reject stale/recycled associations safely. |
| Terrain contact history | `zero_solid_contacts[80]`; contact code at 1284–1347 | Capture P2's previous sides/carried state. Restoring only positions does not restore moving-solid admission/history. |
| Death effect origins | `death_effect[96]`; allocation/init at 1204–1241 | Preserve or deterministically rebuild owner origins and art references; distinguish visual-only data from collision/actor state before excluding it from the digest. |
| Renderer caches | `banks`, `ui_banks`, counters, packet arenas, HUD fade and GPU/menu guest allocation handles | Audit which are process-lived immutable resources and which require reconstruction. A cold restore must recover used retained texture banks and their pixels; an existing cache in a warm process is insufficient evidence. |
| Disc-derived resources | `zero_overlay`, `zero_compressed`, `zero_ui_pixels`, asset/assembly/palette/menu addresses; `load_assets` at 191–243 | Rebuild from the exact verified disc/build as needed. Never serialize heap addresses. Asset readiness must precede restore validation/read; size and guest-range validation remain mandatory. |
| Callback guards | `inside`, player/stage/world/render/effect/pickup/solid/scene/unit-choice guards | Define a single safe-boundary predicate covering every nested host/guest callback. A paused menu may still be a valid stable save boundary once the stack has returned. |

At baseline there is no host-state snapshot provider or shared-state digest.
Guest RAM can match while `p2`, lifecycle, scene or contact state differs.
The netplay profile disables network snapshots/rollback; it does not serialize
the host state or establish correctness of offline save/load and rewind.
Those paths remain unverified until a provider or explicit safe restriction
exists. Native memory cards are separate and must be preserved.

Two immediate test-boundary defects were found: `p2_input` at 565–568 accepts
a raw guest mailbox during netplay, and `diagnostic_setup` at 758–809 accepts
health/ammo/actor/position/scene/weapon fixture writes without a network guard.
These paths can bypass the transport and produce convincing but invalid
network tests. The integrated parity work must reject them during netplay and
exclude fixture mutation from production builds.

## New diagnostic and harness contract

The integrated plugin publishes diagnostic schema 1 without reusing the old
pickup and scene-stat slots. All integers are little endian. The legacy block
length read by tools is `0x1958` bytes; P2's native body is at `+0x100` and
P1's stable native body at `+0x1800`, each `0x158` bytes.

| Offset | Field |
| --- | --- |
| `+0x00`, `+0x04` | Magic `0x434f4f50`, plugin publication count |
| `+0x38..39`, `+0x3c`, `+0x3e..3f` | Two lifecycle states, menu owner, scene owner/phase |
| `+0x80`, `+0x84` | Schema version `1`, block size `0x1958` |
| `+0x88` | Publication sequence: odd while writing, even after commit |
| `+0x8c..8e` | Ready, enrolled, failed (one byte each) |
| `+0x90..91` | Native major mode and phase |
| `+0x94`, `+0x98` | Bounded host diagnostic digest; algorithm ID `1` (FNV-1a) |

`tools/coop_debug.py` reads the sequence before the block and afterwards,
accepting only identical even values and coherent mirrored P2 position/health.
It retries torn publications a bounded number of times. It validates magic,
size, schema, ownership, booleans and digest algorithm. Frozen legacy schema 0
is accepted only through an explicit offline inspection option; it cannot
qualify the new pair harness.

The host digest is a diagnostic aid. It is not the framework core checksum,
does not cover CPU/devices/guest RAM, and is not negotiated into the pinned
transport identity. Matching publication counts are not matching simulation
ticks. Neither this hash nor matching screenshots establish determinism.

`tools/test_mmx6_coop_netplay.py` attaches to two already-running private
processes. It never launches/stops processes, writes RAM, loads states or uses
fixtures. Default mode gathers bounded paired observations; optional
`--exercise-pads` requires an active host/guest two-player delay session and
live idle heroes in a safe unlocked intro area. It acknowledges each host
sampler input, moves one seat at a time, checks both peers observed its motion
and an idle partner, then releases input even on failure.

Example, after a separately controlled muted private pair reaches that setup:

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/pycache'
python tools/test_mmx6_coop_netplay.py --host-port 12345 --guest-port 12346 `
  --candidate 'game=<sha>;framework=a502df3856ae97c2c4860e733fdde3c4f0ad19ec;ui=<sha>;exe=<sha>' `
  --output G:/Temp/Codex/psxrecomp/x6-parity/qa/pair-observe
```

Add `--exercise-pads` only for the established safe input scenario. Supply
`--host-diagnostic`/`--guest-diagnostic` when runtime logs report a different
address. A default address is an explicit legacy fallback, not discovery.
Do not attach to owner playtest processes or overwrite an existing evidence
directory. The tool refuses output on C:.

Each run writes `result.json`, including candidate identity, all observations,
partial comparisons, unverified contracts and failures. Exit codes are `0`
for this bounded smoke, `1` for a failed established check and `2` for
`failed_setup`. Missing/old diagnostics, unavailable required commands,
inactive sessions and insufficient common publications are setup failures,
not gameplay regressions or passes. No core/mod simulation CRC, snapshot,
rewind, rollback, campaign, audio or visual row is closed by this tool.

## Prioritized next changes and acceptance evidence

1. **Test boundary and publication coherence:** reject raw mailbox/fixtures
   during netplay; production must exclude mutation. Make every coherent
   field part of one publication commit, including lifecycle/menu ownership
   bytes previously written early by player/stage callbacks. Test debug and
   production guards and malformed/unknown fixture requests. The new parser's
   unit tests cover framing, timeout, truncation, schema and torn publications.
2. **Real shared-state digest:** select/backport the newer trusted profile
   callback ABI, encode the authoritative state inventory above, and bump X6's
   compatibility identity. Confirm the callback is folded into the core
   checksum and exported in a `mod` partition. Test a controlled host-state
   perturbation is detected even when guest RAM initially matches. Compare
   same-simulation-tick core/mod partitions below the resolved watermark for
   input, menu, lifecycle and scene transitions. Do not replace build checks.
3. **Current-build snapshots:** add the provider API/backport and a versioned
   checked codec; all providers validate before any mutation. Reject invalid
   lengths/enums/ranges and resource mismatches safely. Capture/restore only
   after nested contexts return, then reconstruct derived GPU/audio resources.
   Qualify offline warm and cold restore, paused menus, join/death, scene
   transport, pickup healing and moving-solid history; compare replayed outputs
   and host/core state. Preserve cards and include no old-state migration work.
4. **Input replay and simulation profiles:** retain exact build/settings/card
   seed provenance and accepted inputs; qualify replay without raw RAM writes.
   Exchange actual CPU/backend/profile capability once before frame 0 and
   retain the settled profile for the match. Delay-sync remains the only
   advertised mode until resimulation and full capture are proven.
5. **Integrated gameplay/network qualification:** owner/lifecycle/menu/scene
   checks across both seat/character arrangements, native rewards and exits,
   fixed/adaptive view contracts when implemented, latency/jitter and sustained
   sessions. Keep real-network/front-end/controller/audio checks explicitly
   separate from this local diagnostic smoke.

Pure Python verification for the new observation code:

```powershell
python -m unittest discover -s tools -p test_coop_debug_protocol.py -v
```

At this audit milestone all 16 synthetic parser/protocol tests passed. No game
was launched by this audit lane and no runtime gameplay/network pass is claimed.
