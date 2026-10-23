# X6 co-op and netplay parity burndown

Local issue **beads-gxrh**. Integration branch
`feature/mmx6-x4-parity-local`, worktree
`F:/Projects/psxrecomp/_wt-mmx6-x4-parity`. Started October 22, 2026.
All source, commits, evidence and tracker updates remain local. No remote
publication or tracker synchronization is authorized.

## Coverage and evidence contract

| Inventory | Current disposition |
| --- | --- |
| [234 X4 comparisons](COOP_X4_REFERENCE.md), original R1–R26 and F1–F208 | R2, R7, R8 and R13 passed on preserved exact candidates; 230 unverified; no inherited X4/X5 passes |
| [79 X6-specific obligations](COOP_X6_CONTENT.md), X6-001–079 | 79 unverified, separately for local co-op and netplay |
| Native content | 115 checkpoint records, 1,964 primary placements, 365 secondary placements |
| Rescuable Reploids | All 128 native IDs; seven independent rescue/infection/reward/persistence checks each, all unverified |
| [Live native coverage](COOP_X6_COVERAGE.md) | 1,665 individual cases / 3,330 independent mode results, all unverified |

The authoritative comparison ledger is `COOP_PARITY_LEDGER.json`. The frozen
native inventory and X6-only definitions are `COOP_X6_CONTENT.json`; live native
attempts belong in `COOP_X6_COVERAGE.json` using its
[append-only workflow](COOP_X6_COVERAGE_WORKFLOW.md). These are coverage
records linked to the central Beads issue, not independent issue databases.
The Markdown reference is generated from the comparison ledger. Preserve the
frozen report, symptom, failure class and source hashes when changing an X6
mapping or status.

X4 is frozen at Playtest42 `50593bca772b600de6911cbfecd40b0f08721147`.
X5 comparison definitions are frozen at
`9ed460e7b7e60769fa12bcab74e228ae19796214`. Later X5 implementation observations
are named separately in the state audit. The X6 baseline is
`6cba3f8b4dafe3c4cabd2316593084e87c3f682a`, framework `a502df385`, UI `827f49dd`.

Passing a build, finding a hook, loading a location or seeing a screenshot
does not pass a mechanic. Keep setup failures, observed gameplay failures,
bounded passes, bypasses and unidentified native analogues distinct. A pass
needs the exact candidate, settings, native trigger/outcome and retained,
hashed evidence for each required mode. Do not set the completion flags under
test. Native cards are preserved separately from disposable build-specific
states; old-state migration is never required.

## Current integrated candidate, October 23

The local integration now uses profile `mmx6-x-zero-delay-v12`, ABI 32,
the modern SDK bridge and UI `b964eabe`. Rollback and online user state jumps
remain disabled. The historical milestones below retain their original
candidate identities; observations do not transfer automatically to a rebuild.

The v12 source adds original native private trail/attached-effect updates,
reverse-order visible trail rendering, owned mode packets and a menu-phase
guard against extra P2 advancement. Source-backed actual-plugin fixtures pass
in optimized GCC/Clang debug/production variants. The development host rule is
now revision2 and remains default-OFF. The frozen v12 image `229ffec7` has a
fresh native pair, same-session-ID nonce restart and reviewed R8 menu checks in
both modes. Its bounded Zero private-pause/dash checks also pass locally and
paired; R9 stays unverified pending X-owned effects, opposite rosters and the
native Zero trail-color comparison. See the exact-image summaries under
`docs/evidence/mmx6-r8` and `docs/evidence/mmx6-private-pause`.

R2 and R13 remain bound to the frozen v11 artifact. New diagnostics/replay and
startup-override source changes require another exact candidate and do not
inherit either image's runtime observations. Stronger native checkpoint
readiness correctly rejects a camera bound of 75 against its authored 944;
the original camera writer is under investigation. No campaign case is passed
by that incomplete setup. Testing uses two peers on this machine; other-machine
qualification remains unverified.

- The native intro enemy action-1 proximity correction has actual before/after
  local evidence and a two-peer original-input route with 37 matching resolved
  core/mod samples. The route admits authored record 25 while X remains fixed,
  observes original initialization, Zero-only proximity response and native
  attack damage on both peers. See [the paired receipt](COOP_PAIRED_ENEMY_BASELINE.md).
  A fresh manifest-bound repeat now passes R13 locally and over development
  loopback: 12 local checks, 16 paired checks, 46 matching resolved core/mod
  samples and verified agreement before guest cycle0/tick0. Other targeting
  routines and stages remain unverified.
- [Zero's personal menu](COOP_PERSONAL_MENU_BASELINE.md) now passes R8 in both
  modes on the same frozen candidate. Eleven native case checks cover owning
  input, wrong-seat rejection, frozen world time, retained resources and
  resumed movement/action48. The pair adds 30 matching resolved core/mod
  samples; both paused and resumed composed images match and were inspected.
  The initial unavailable Right cursor setup remains failed; the correction
  uses the source-proven Down/Up path without granting inventory.
- [Native damage before/after Zero's menu](COOP_CONTACT_BASELINE.md) passes R2
  on that same candidate. Local135 and paired118 contact observations retain
  ZeroHP32->28->24, native reactions/recoveries, the same enemyHP12 and unchanged
  X resources. The pair adds30 matching resolved core/mod samples; completed
  composed images were reviewed. Three incomplete route attempts remain explicit.
- [Independent native trace counters](COOP_NATIVE_WORLD_TRACE.md) show one
  enemy-world entry per complete frame in the observed intro sequence: 361
  frames, 364 complete driver cycles and 83 bound live-enemy frames. Both
  broader route reports retain their failed status; the corrected trace run
  missed the intermediate HP-loss sample. This counter result does not qualify
  moving platforms or every world subsystem.
- The SDK now requires actual CPU/backend offers and a trusted title catalog,
  canonical startup floating-point state, verified linked BIOS selection,
  immutable interpreted overlays, actual executable SHA and mutual profile
  agreement before guest execution. Fresh OS nonces bind each startup;
  existing title/content/build gates remain. Eight integrated startup/core/
  wire/CPU/FP/image/nonce fixtures pass. Narrow loopback transport evidence is
  recorded below; broad host catalogs remain unavailable.
- X6 explicitly registers its declared build inputs, including the resolved
  generated-game tree, actual dependency pins and tracked edits. The integrated
  frozen Clang developer lab build passed36/36 game CTests; the later production
  default-OFF integration passes41/41. A separate developer
  [quit-acknowledgement fix](COOP_DEBUG_QUIT_BASELINE.md) passes44/44, with original content/audio reproduction
  enabled. The manifest covers declared inputs, not an exhaustive
  external binary or driver closure. See [manifest limits](COOP_BUILD_MANIFEST_REGISTRATION.md).
- The same frozen executable passes a fresh [current-build warm/cold snapshot
  repeat](COOP_SNAPSHOT_BASELINE.md): 12 warm and 13 cold checks, exact restoration
  of both complete native bodies, reconstructed retained banks and independent
  resumed input. Only the private snapshot was transferred to the cold profile.
  This does not qualify rewind, online state transfer or campaign restoration.
- The [native input consumption contract](COOP_INPUT_CONSUMPTION_CONTRACT.md)
  now maps the original decoder completion and all six extra P2 read sites.
  Its strict file codec rejects truncation, event-order gaps and mismatched
  startup artifacts. Runtime recording and replay remain separate work; R26
  is still unverified.
- The [optimized helper matrix](../psxrecomp-v4/docs/qa/x6-helper-qualification-20261023/README.md)
  retains 48 passes, two fixture linkage blocks and one disabled SPU test.
  Running that disabled executable directly reproduces four existing ADSR
  failures. Compressed-stream MDEC, forced-scalar and exhaustive load-delay
  coverage remain open; this matrix does not qualify another CPU or OS.

The explicit development-only numeric `127.0.0.1` catalog now has actual
transport and same-session-ID restart evidence on frozen executable37cdc487.
Both starts settle before cycle0/tick0, with different nonce-bound selected
identities. The enabled developer build passes36/36 game checks. The option
remains off by default; no cross-machine or broad production profile is inferred.
See [the exact candidate and limits](COOP_HOST_LAB_BASELINE.md).

## First implementation milestone

The integration retains X6's existing native co-op renderer, hit pause,
stacked meters, lifecycle and loader. It adds:

- A reproducible frozen comparison importer/checker and original-disc content
  extractor. Each comparison has an individual X6 mapping and bounded check;
  64 native analogues still need identification.
- Default rejection of the unilateral P2 input mailbox and fixture commands
  during netplay. Production also rejects both channels. Profile identity is
  `mmx6-x-zero-delay-v9`; rollback and network state transfers remain disabled.
- Diagnostic schema 1 with a completed-publication marker, canonical P1/P2
  bodies, ready/enrolled/failed flags and a **partial** host-context FNV hash.
  This hash is not the framework's whole-machine or mod checksum.
- A bounded diagnostic/parser and paired-session harness, plus isolated local
  candidate preparation and an owned-process intro qualifier. Staging refuses
  existing outputs and excludes CD Speed and Fast Loading packages.
  New receipts retain scoped tracked-source observations and exact local Git
  heads/patch hashes for game, framework and UI. These observations describe
  staging-time sources; they do not establish compilation provenance or capture
  untracked inputs. Runners reject changed source-observation artifacts.
- A local framework correction, `83e8b5e11c005e0868e1aef96335258aad157559`,
  that verifies the actual selected disc before resolving and negotiating the
  default native loading plan. Native-plugin validation remains enforced.
- X4's virtual-host netplay sampler correction, locally `a72527f13`, plus
  source-backed Select edge/queued-rejoin corrections described in
  [the lifecycle audit](COOP_LIFECYCLE_AUDIT.md).

The real-plugin regression fails on baseline 6cba3f8 because a queued network
fixture mutates P2, and passes after the correction. Both debug and production
test variants execute the actual plugin against isolated memory/native-call
fixtures. This is implementation regression evidence, not an actual online
campaign pass.

Full debug and production builds succeed, with **21/21 CTests passing in each**,
including simultaneous runs using the same scratch directory. The original
catalog tests used shared fixed directory names; concurrent runs exposed
deletion/copy races. All four catalog test executables now atomically reserve
private directories and preserve previous failures. Original-disc tests were
enabled and reproduce the inventory; changed source identities are rejected.
Framework loader regressions pass in normal and worker-safe configurations;
the original framework fails the exact default-on disc-targeted fixture.
Other-target builds and production gameplay remain separate qualifications.
The later timing-package test hang and unsuccessful debugger startup are retained
in `timing-test-hang.json`; only that verified owned test was stopped. Its fixed
scratch root was another collision risk. After private-directory reservation,
both simultaneous suites pass 21/21 (`ctest-timing-isolated-*.log`). This does
not infer a gameplay defect or a proven fault stack from the hung test.
Catalog checks now have a 120-second deadline. The resident-store test also
uses atomic directory reservation, avoiding a libc++ extended-clock `to_string`
compile error found during the separate modern Clang candidate build.
Latest logs: `build-audio-audit-debug.log`, `build-audio-audit-production.log`,
`ctest-audio-audit-debug.log`, `ctest-audio-audit-production.log`. Both native
content and audio reproduction tests were enabled against the private G: disc
copy. The protocol suite includes 23 checks, including rejection of unresolved,
legacy, conflicting or mismatched core/mod checksum evidence and missing
framework digest registration on either peer.

Checks for framework 83e: `ctest-isolated-debug.log` and
`ctest-isolated-production.log` under the evidence root. That debug executable
SHA-256 is
`044731e5e78346b5f49d6ec810584e02dfbf14ce37c6271a6553a5525a8ba7e3`;
production is
`87c39513288921e12594e0bf330d657b49875e97701d2de9da843d4e90555c69`.
Native observations below name their own executable hashes; build checks do
not transfer those observations to a different binary.

## Native baseline evidence and limits

Evidence root: `G:/Temp/Codex/psxrecomp/x6-parity`.
Candidate executable SHA-256:
`c494c3624284560b1287e5494e550e91b781f6b4389201d793ac4b850ca9960e`.
It uses the unchanged framework/UI pins, default OpenBIOS and a private card,
settings, cache and data profile. Automated output is hidden and muted;
OpenGL and SPU emulation remain active. Overlay autocompilation is disabled in
the isolated profile, so no AOT performance claim follows.

| Evidence directory | Result and limits |
| --- | --- |
| `baseline-6cba3f8/baseline` and `candidate-delay-v7/baseline` | Retained failed setups; neither reached the requested playable state before its deadline. The preparer's disconnected P1 setup was subsequently identified. No gameplay defect or boot regression is inferred. |
| `candidate-delay-v7-connected/baseline` | Corrected virtual P1 reaches two living native actors. The first observer then fails because three RPCs can span consecutive frames. Preserve this observer failure; it is not an actor-state mismatch. |
| `candidate-delay-v7-observer-fixed/baseline` | Bounded intro pass: P2 moves through direct debug SIO injection while P1 stays put; P1 jumps while P2 stays independent; both have 32 HP and mailbox remains unused. The composed capture was inspected and shows both native bodies/meters. This does not qualify physical controllers, full movement/combat, campaign or network behavior. |
| `diagnostic-regression/qualification.json` | Before/after actual-plugin rejection regression, exact source hashes and output. Isolated fixture only. |

The diagnostic reader now uses one `read_ram` request. The pinned runtime
copies that block on the emulation thread in `debug_server_poll`; gameplay
does not run during the copy. The reader rejects an unfinished sequence,
tick/sequence disagreement and mismatched mirrored bodies. Requiring identical
sequences across three separate RPCs caused false failures in a running game.

The intro runner requested normal quit, then terminated only its owned process
after quit failed to finish within the deadline. **Graceful exit remains
unverified.** Existing private cards were unchanged; source cards/settings were
never used as writable test state. No owner-facing window was launched.

The original paired attempts and corrected default admission are recorded in
[COOP_NETPLAY_BASELINE.md](COOP_NETPLAY_BASELINE.md). After the framework fix,
both peers commit the default resident loader and advance an active two-player
delay session: tick 93, resolved-through 92, rollback off, no reported input
desynchronization. This is startup admission only. A subsequent sampler fix
also passes the bounded native intro/input smoke on both peers with original
host inputs, healthy heroes and unused mailbox. Its exact candidate, matching
captures and limitations are recorded separately in the baseline document.
Whole-machine/mod checksums and full campaign behavior remain unverified.

Profile v9 also passes a bounded native two-peer leave/pause/rejoin smoke:
held departure stays absent; a Select press held from primary pause through
resume creates no join; a fresh edge rejoins with the observed healthy intro
resources retained. The initial one-based-owner assertion error is preserved
as a harness failure, followed by the successful corrected run. Full debug
and production builds and 20/20 tests pass for this lifecycle candidate.

[The native audio audit](COOP_AUDIO_NATIVE_AUDIT.md) reproduces ten banks across
five forms with five passing source/metadata checks. X6 voice records use
stride 0x38 and voice body type 0x20303; every voice group's record 17 references
the effects VAB. Proven X4 design is a reference, but its memory extents and
blanket bank mapping cannot be copied. R4/R12 remain unverified pending complete
X6 driver/flush ownership and native muted captures.

## Modern host-state milestone

The modern candidate uses ABI 32 and profile `mmx6-x-zero-delay-v10`, with a
canonical host digest, explicit callback-local tracking, validated snapshots
and cold retained-texture reconstruction. Rollback and online user state jumps
remain disabled. [The codec document](COOP_HOST_STATE_CODEC.md) records the
state contract and refusal after an abandoned callback.

The exact `bd7b9449...` candidate passes nine native two-peer intro/input/lifecycle
checks and 30 common resolved core/mod samples across four phases. Matching
composed GL captures show the original actors and HUD; canonical VRAM alone
omits retained GL textures. The report, complete hashes and prior capture
ambiguity are retained in [the netplay baseline](COOP_NETPLAY_BASELINE.md).

[Warm/cold native snapshot qualification](COOP_SNAPSHOT_BASELINE.md) passes
on that same executable: actual save/load completion generations, both complete
348-byte bodies and healthy resources restored, cold cache reconstruction from
170 to 211 banks, native menu resume and independent controls after load.
Composed restored menu captures match. The initial menu-fade failure and a
changed-executable staging rejection remain recorded. This covers the healthy
intro and P1 menu; other restoration contexts and rewind remain unverified.

The combined SDK GCC matrix passes 24/24 after isolation of shared test
directories. Modern Clang developer and production builds pass 26/26 game
checks, including original-source content/audio reproduction. The selected
local SDK pin is `9cb684082`, UI `b964eabe`; Windows files over 64 KiB and live
writable mappings use fresh preparation instead of an unqualified identity
cache shortcut. Subsequent exact-candidate native checks remain separate from
the frozen `bd7b9449...` observations. No full comparison status changes follow
from these bounded milestones.

## Next integration gates

1. Extend the now-passing native intro cases with both personal menus and
   authored scene checks. Keep framework fixture gaps and existing SPU
   fidelity failures explicit. Use real peer hardware before enabling any
   cross-machine, cross-CPU or cross-OS qualification.
2. Validate subsequent implementation changes on a newly frozen candidate;
   retain the current R13 receipt against its actual compiled source commit.
   Repeat relevant cases when a changed binary or execution contract is used.
3. Extend the registered host-state provider beyond the healthy intro/P1 menu:
   qualify rewind, both menus, joining/death, scenes, deferred heals and moving
   solids, including cold resource restoration. Keep rollback disabled until
   resimulation is proven.
4. Implement the missing seat/character ownership and diagnostic recorder;
   qualify voices, effects, personal menus, resources and lifecycle before
   expanding cameras, Both-door policy and elective options. Correctness works
   by default when co-op is active; elective additions default off.
5. Use the actual content inventory for cheats/teleports through every authored
   route and interaction. Resolve Museum room-selection topology, dynamic
   boss substitutions and unresolved native namespaces before claiming route
   coverage. Batch compatible mechanic checks on one integrated candidate,
   with a bounded attempt and one evidence-based setup correction before
   deferring a difficult starting situation to human assistance.
6. Complete other-target builds, production gameplay, default settings, stability,
   physical controls, real-network and owner QA. A normal-audio, windowed
   launcher is staged separately; launching it requires an actual handoff.

Full parity remains in progress. Bounded native checks and framework fixes do
not close the unexecuted campaign inventory.
