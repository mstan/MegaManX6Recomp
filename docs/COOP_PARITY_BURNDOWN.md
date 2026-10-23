# X6 co-op and netplay parity burndown

Local issue **beads-gxrh**. Integration branch
`feature/mmx6-x4-parity-local`, worktree
`F:/Projects/psxrecomp/_wt-mmx6-x4-parity`. Started October 22, 2026.
All source, commits, evidence and tracker updates remain local. No remote
publication or tracker synchronization is authorized.

## Coverage and evidence contract

| Inventory | Current disposition |
| --- | --- |
| [234 X4 comparisons](COOP_X4_REFERENCE.md), original R1–R26 and F1–F208 | 234 unverified; no inherited X4/X5 passes |
| [79 X6-specific obligations](COOP_X6_CONTENT.md), X6-001–079 | 79 unverified, separately for local co-op and netplay |
| Native content | 115 checkpoint records, 1,964 primary placements, 365 secondary placements |
| Rescuable Reploids | All 128 native IDs; seven independent rescue/infection/reward/persistence checks each, all unverified |

The authoritative comparison ledger is `COOP_PARITY_LEDGER.json`; the native
inventory and X6-only obligations are `COOP_X6_CONTENT.json`. These are coverage
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

## First implementation milestone

The integration retains X6's existing native co-op renderer, hit pause,
stacked meters, lifecycle and loader. It adds:

- A reproducible frozen comparison importer/checker and original-disc content
  extractor. Each comparison has an individual X6 mapping and bounded check;
  64 native analogues still need identification.
- Default rejection of the unilateral P2 input mailbox and fixture commands
  during netplay. Production also rejects both channels. Profile identity is
  `mmx6-x-zero-delay-v8`; rollback and network state transfers remain disabled.
- Diagnostic schema 1 with a completed-publication marker, canonical P1/P2
  bodies, ready/enrolled/failed flags and a **partial** host-context FNV hash.
  This hash is not the framework's whole-machine or mod checksum.
- A bounded diagnostic/parser and paired-session harness, plus isolated local
  candidate preparation and an owned-process intro qualifier. Staging refuses
  existing outputs and excludes CD Speed and Fast Loading packages.
- A local framework correction, `83e8b5e11c005e0868e1aef96335258aad157559`,
  that verifies the actual selected disc before resolving and negotiating the
  default native loading plan. Native-plugin validation remains enforced.

The real-plugin regression fails on baseline 6cba3f8 because a queued network
fixture mutates P2, and passes after the correction. Both debug and production
test variants execute the actual plugin against isolated memory/native-call
fixtures. This is implementation regression evidence, not an actual online
campaign pass.

Full debug and production builds succeed, with **20/20 CTests passing in each**,
including simultaneous runs using the same scratch directory. The original
catalog tests used shared fixed directory names; concurrent runs exposed
deletion/copy races. All three affected test executables now atomically reserve
private directories and preserve previous failures. Original-disc tests were
enabled and reproduce the inventory; changed source identities are rejected.
Framework loader regressions pass in normal and worker-safe configurations;
the original framework fails the exact default-on disc-targeted fixture.
Other-target builds and production gameplay remain separate qualifications.

Final checks: `ctest-isolated-debug.log` and `ctest-isolated-production.log`
under the evidence root. Current debug executable SHA-256 is
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
desynchronization. This is startup admission only. Native gameplay, matched
whole-machine/mod checksums and transport input independence remain unverified.

## Next integration gates

1. Finish native frontend admission and actual loopback delay-sync
   input/partial-state evidence. The loading-off diagnostic timed out in the
   frontend; the corrected default startup check does not resolve that separate
   question. Preserve the distinction between diagnostic publication counts
   and resolved simulation ticks. Do not close the broad netplay comparisons
   without framework core/mod checksums and their actual behavior checks.
2. Bridge X6 onto the modern X4/X5 framework in a separate local framework
   worktree. Their committed base is `6f0ccbc6`, UI `b964eabe`, recomp-net
   `e5305930`, rbengine `2a03e736`. Preserve X6's native replacement service
   from `a6216c6be` and negotiated loading behavior from `50c68be75`; reconcile
   overlay ABI 31/30 and retain modern dependency pins. A blind repin removes
   services used by existing X6 generated code and plugins.
3. Register a canonical host-state digest and a validated snapshot provider,
   with stable callback boundaries and retained resource reconstruction.
   Qualify warm/cold restore, menus, joining/death, scenes, deferred heals and
   moving-solid contact. Keep rollback disabled until resimulation is proven.
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

Full parity remains in progress. No comparison has been closed by this first
implementation milestone.
