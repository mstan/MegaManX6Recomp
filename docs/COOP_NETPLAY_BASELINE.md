# X6 netplay baseline: 2026-10-23

**Default loopback intro/input and bounded lifecycle smokes pass. Full state
and campaign synchronization remain unverified.** The original attempts preserve the default-loading
failure and a loading-off diagnostic frontend timeout. A subsequent framework
fix was validated with a separate default admission check, documented below.
The offline intro pass recorded elsewhere does not transfer to netplay.

## Exact candidate and isolation

- Executable: `G:/Temp/Codex/psxrecomp/x6-parity/build-debug/mmx6-runtime.exe`.
  SHA-256: `a31a4e7f076a681012c7d8cd879368c0fee5d115ea82042defd26f279c2e094d`.
  Both staged peers verified this same hash.
- Framework: `a502df3856ae97c2c4860e733fdde3c4f0ad19ec`; UI:
  `827f49dda3baa523328ef14acfcf50cbeb078516`; trusted profile:
  `mmx6-x-zero-delay-v7`.
- Source helpers were imported from the integration worktree's explicit
  `--tools-root`, including its corrected single-RPC diagnostic observer.
  Each report records the exact helper hashes, staged config and executable
  hashes, arguments and private output paths. No source commit is inferred
  from an abbreviated candidate label.
- Private profiles on G:, no source cards, fresh keyboard P1 device per peer,
  hidden OpenGL windows and dummy audio. Autocompilation was disabled; no AOT
  cache was copied and no performance claim is made.
- TCP `24901`/`24902`, UDP `29901`/`29902`, loopback only, session `20261023`,
  delay 3, seats 0/1. Both sample local host input player 0; the transport maps
  it to the corresponding simulation seat. Port availability was reserved
  before launch and actual listener ownership checked before debug requests.
- Only the two processes created by each runner were stopped. All four owned
  processes were confirmed absent afterwards. Existing owner processes and
  cards were not touched.

## Results and retained evidence

| Attempt | Setup | Result |
| --- | --- | --- |
| 1 | Prepared catalog's default Seamless Loading enabled | Both peers exited before BIOS with `cannot apply netplay mods: Title loading option must resolve to its native plugin`. |
| 2 | Explicit original-disc-loader diagnostic bypass; offline co-op disabled, trusted co-op supplied by the executable profile | Active two-player delay session, then a 240-second setup timeout. Native modes progressed `0 → 9 → 0`; two live idle heroes were never established. |

Attempt 2's last paired session observations reported `active=1`,
`rollback=0`, `players=2`, correct host/guest identities, `desync=0`, ticks
`12954`/`12955`, and resolved-through `11146`. This establishes a functioning
session observation, not gameplay determinism. Host sampler commands were
acknowledged, but accepted in-game movement/jump was never reached.

The one retained setup screenshot shows the native X6 opening logo. It is a
320×240 game-render-buffer capture, not composed host presentation, and proves
no gameplay behavior. SHA-256:
`abafbe5fd485c12cbe77510fd4a374987cd2d23ac184acb95f3b5481d69dc73d`.

Evidence stays outside the repository:

- `G:/Temp/Codex/psxrecomp/x6-parity/netplay-baseline-attempt1/qualification.json`
  SHA-256 `70ff89a563128d840845976f627f494d6b161284c9ef4d649d34fe21f86a9ca1`.
- `G:/Temp/Codex/psxrecomp/x6-parity/netplay-baseline-attempt2/qualification.json`
  SHA-256 `60363d0df82dd07fc83877325ca6bee5d61a5ad094fd62c88196a2164ee0b2f7`.
- Each attempt retains both peers' `preparation.json`, settings, mod selection,
  game config, stdout/stderr logs and private generated cards. Attempt 2's
  setup image is `peer-0/logs/setup-progress.png`.

Passed observations: isolated staging, matching executable hashes, owned
listeners/processes, hidden muted execution, and (attempt 2 only) an active
two-peer delay session without reported input-contract desynchronization.

Failed setup: default optional-loader plan admission; subsequently, native
intro admission within the bounded loading-off retry.

Unverified: P2 movement/P1 jump independence through transport, paired host-FNV
samples during gameplay, core/mod determinism, campaign behavior, snapshots,
rewind, rollback, real-network play, physical controllers, composed captures
and audible presentation. No gameplay burndown row is closed from this run.

## Concrete default-loader defect

In the pinned framework, `title_loading_selection` already disables every
non-loader feature, including offline co-op. Merely disabling offline co-op
cannot repair the observed loader-only result.

`mod_runtime_commit_netplay` resolves that loader-only plan at
`runtime/src/mod_runtime.cpp:1664` with an **empty disc identity**. The staged
Seamless Loading 0.1.0 manifest defaults the feature on and requires exact disc
SHA-256 `91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318`.
`target_matches` at `runtime/src/mod_packages.cpp:675–686` rejects a nonempty
required disc hash against that empty value. The resulting invalid plan is
reported as the generic native-plugin error. This source evidence explains
why the original-loader bypass admitted the diagnostic session.

The fix must resolve and negotiate the loader plan against the verified selected
disc identity while retaining native-plugin-only validation and identical
host/guest loading settings. Then retest the normal default. Turning off
Seamless Loading is a disclosed bypass, not the correctness fix. The separate
native frontend timeout remains a setup failure requiring its own evidence;
no cause is assigned from the loading-plan defect.

## Corrected default admission

Local framework branch `fix/mmx6-netplay-loader-disc-identity`, commit
`83e8b5e11c005e0868e1aef96335258aad157559`, fixes the empty identity in both
the direct commit and launcher fingerprint paths. It freshly measures the
selected CUE/CHD-aware disc, clears stale cached identity and resolves the
native-only loader selection using the verified hash. Absent, wrong,
unreadable and same-path-replaced discs are rejected; valid recovery succeeds.
Other fingerprint behavior is preserved. Regression checks pass in both normal
and worker-safe framework configurations. Local framework issue: `beads-skok`.

The game now pins that local commit and uses profile `mmx6-x-zero-delay-v8`.
UI and network dependency pins are unchanged. With default Seamless Loading
enabled, `--admission-only` passed for both peers:

- Both logs contain `title netplay loading = resident assets`.
- Active delay session, two players, expected host/guest identities, rollback
  disabled, tick 93 and resolved-through 92 on both peers, `desync=0`.
- Executable SHA-256:
  `7a600daf6dc29b26d602b729984b004f513092e0c11678254f268ce4824394ed`.
- Evidence:
  `G:/Temp/Codex/psxrecomp/x6-parity/netplay-default-loader-fixed/qualification.json`,
  SHA-256 `6ca1e6ee5585cfd1ad0aafaf939d024562fe77b877e1e96e40caa1bb53689016`.
- Both owned processes were stopped by the runner. Graceful quit remains
  unverified. Original cards and owner processes were not used.

This proves default loader admission and session progress only. It performs
no native gameplay, movement or host-FNV qualification. The earlier frontend
timeout was investigated separately below. Every full gameplay/state comparison
remains open. Later build hashes
are listed separately in the burndown; this native pass belongs to the exact
binary above.

## Native transport input smoke after the sampler correction

The old framework's `capture_pad_slot_exclusive` omitted the virtual host
device that the offline sampler already accepts. Thus `pad_status` correctly
acknowledged a host-layer command while the netplay sampler still captured a
neutral keyboard. Frozen modern X4 already contains the correction
`1e33761d2a4060a1d6092ecf18c243fb9604d43c`. Its exact change was cherry-picked
locally as `a72527f13a378688d7974afde86c3c8c140b79fd`, retaining the disc-identity
fix. It samples the explicit virtual device before transport staging and uses
the destination seat's pad mode; no simulation-layer SIO override is involved.

A fresh default-Seamless pair then passed the bounded intro/input checks:

- Native frontend reaches two living idle heroes using original inputs only.
- P2 Right moves P2 on both peers while preserving P1's X; P1 Jump reaches
  both peers while preserving P2's Y. Both remain healthy; mailbox unused.
- The three partial host-observation windows contain 104, 106 and 109 matching
  diagnostic publications. These are not framework simulation CRC samples.
- Final session ticks are 3690/3691, resolved-through 3689/3690, two players,
  rollback disabled, no reported input-contract desynchronization.
- Both 320x240 game-render-buffer captures were inspected and show X/Zero and
  their meters. Both SHA-256 values are
  `088fa57c185d86dea69344dc612814eb77ab3389f21bc82cadbde94c8a9c4a95`.

Exact executable:
`cff00c09fde9f6f786883a869bb276bbd20aedfd6b50224c183ee2b39e0f4384`.
Report:
`G:/Temp/Codex/psxrecomp/x6-parity/netplay-host-input-fixed/qualification.json`,
SHA-256 `d7a8fbd69bdb5ff5e995e8b5805ad2173d33463b060b21fce7cb828dcfda5ea6`.
Only the runner's two processes were terminated and verified absent. Graceful
exit remains unverified. This is a bounded loopback input smoke, with no core/mod
determinism, physical controller, audible, campaign or internet qualification.

## Lifecycle smoke on profile v9

The source/helper correction in game `fb95f99` preserves queued rejoin intent
and consumes blocked Select edges, with compatibility profile bumped to
`mmx6-x-zero-delay-v9`. Full debug and production builds plus 20/20 checks each
pass (`build-lifecycle-*.log`, `ctest-lifecycle-*.log`). Debug executable:
`407f13b2b44a795dfc2316a6884c64b6e453ae554569fb64ca528e4b36d0233b`;
production: `112990647ce3c8c2781a5238c272790a0894223c2be6c54f299a68b29ade3464`.

`netplay-lifecycle-v9-owner-fixed/qualification.json` passes the six intro/input
checks plus three native lifecycle checks: held departure remains absent,
Select pressed during primary pause and held through resume creates no rejoin,
and a fresh released/pressed Select rejoins with observed HP/ammo/weapon
preserved. Both peers finish tick 4418, resolved-through 4417, `desync=0`.
Report SHA-256:
`d5dd9796f3751fde9971c474741e655255eb5320176342f90f9e37cdd22d09a0`.
Both final game-buffer captures were inspected; SHA-256:
`3a2d09561d3a91261178ca645ba9304667f1a953b24e1b4ecd9559fb15e70f6a`.

The prior `netplay-lifecycle-v9/qualification.json` is retained as a harness
failure (SHA-256
`a4ba79cf665f9e2a90846e81607a424abfa3b8d8bb983ab995545c3bf2f0d813`).
Its screenshot and published phase show the primary menu opened correctly;
the new assertion incorrectly expected zero-based ownership, while the wire
uses 0=none/1=P1/2=P2. Only that assertion was corrected before the successful
retry. No game fix or native pause defect is inferred from this failed tool run.

All four owned processes were verified absent after their runners stopped them.
Healthy intro resources only were exercised; this does not qualify spent ammo,
airborne unsafe landing, death/retry, audio, full state restoration or campaign
scenes. Matching diagnostic publications remain partial evidence.

## Modern SDK candidate admission

The isolated Clang candidate bridges X6's native services onto framework base
`6f0ccbc6`, with modern UI `b964eabe`, net `e5305930` and rbengine `2a03e736`.
Framework bridge commit `2a0754436` uses overlay ABI 32. This candidate is not
the game repository's selected SDK pin yet.

`netplay-modern-bridge-admission/qualification.json` passes default resident
loader admission and an advancing two-peer delay session, with both resolved
through tick 62 and no reported input desynchronization. Report SHA-256:
`d38cc60b8c10870ff68be479b558adca6d9f2521a538520e2db27b4eb90f23e0`.
Executable SHA-256:
`81cae43aec8ccde5417373a4fe25f48d383b3d75799349bd01ff02e69010aaa3`.
The 21 game checks also pass (`ctest-modern-debug.log`). The original-disc
resident-store check passes cold/warm preparation, 302 member hashes, loader
guard, mod-plan separation, corruption repair and fail-closed fallback. Its log
is `F:/Temp/Codex/psxrecomp/x6-parity/resident-validation/resident-check.log`,
SHA-256 `914adc9c36034743694f4df3fcd6dc820ded107ab6c5173a6ae2f0cb50e21ef4`.

These receipts precede the integrated host-escape and Windows file-identity
fixes. They establish neither gameplay nor registered core/mod synchronization
on the combined SDK. Both owned admission processes were verified absent;
graceful exit remains unverified.

## Reusable runner

`tools/qualify_mmx6_coop_pair.py` stages, launches, boots and observes two owned
processes. It imports the existing preparation, listener-ownership, diagnostic
and pair-comparison helpers rather than copying them. It records failures and
cleans up only owned processes. RAM writes, diagnostic fixtures, input
mailboxes and state loading are absent.

The final runner preserves default Seamless Loading. An explicit
`--native-loader-diagnostic` option reproduces the disclosed original-loader
bypass used by attempt 2. The runner gained that explicit flag after the
bounded attempts; neither original attempt was rerun. `--admission-only` checks
the corrected default loader and advancing delay session without claiming
intro gameplay; it cannot be combined with the diagnostic loading bypass.
`--lifecycle-smoke` extends a gameplay run with native departure, a Select
press held through primary pause/resume and a fresh rejoin, retaining resource
observations. This mode does not inject death, spent ammo or success flags.
`--require-state-crc` additionally requires modern core/mod breadcrumb pairs at
the same simulation tick, strictly below both resolved-through watermarks and
after each input window. Legacy/missing partitions and too few samples cannot
pass. The candidate must separately register its complete authoritative host
digest: a logged `mod=00000000` alone proves no such registration. This mode
also requires the explicit framework-registration capability at diagnostic
`+0x9C` on both peers; existing unregistered candidates publish zero there.
The standalone diagnostic FNV cannot satisfy that capability. The mode
has parser regressions but no native X6 qualification yet.
Python 3.11+ is required by the
shared tools; the actual attempts used Python 3.12.5.

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/pycache-state'
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' `
  tools/qualify_mmx6_coop_pair.py `
  --tools-root F:/Projects/psxrecomp/_wt-mmx6-x4-parity/tools `
  --build G:/Temp/Codex/psxrecomp/x6-parity/build-debug `
  --disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).cue' `
  --out G:/Temp/Codex/psxrecomp/x6-parity/netplay-next-default
```

Choose a fresh evidence directory. A passing bounded runner would still be
only an intro/input smoke. The pinned framework has no host-state `mod`
checksum partition; standalone diagnostic FNV matching must never be described
as full core/mod synchronization.
