# X6 netplay baseline: 2026-10-23

**Default netplay failed setup. Gameplay synchronization remains unverified.**
One original/default-loading launch and one evidence-based loading-off
diagnostic retry were performed. No further configurations or launches were
tried. The offline intro pass recorded elsewhere does not transfer to netplay.

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

Fix target: resolve and negotiate the loader plan against the verified selected
disc identity while retaining native-plugin-only validation and identical
host/guest loading settings. Then retest the normal default. Turning off
Seamless Loading is a disclosed bypass, not the correctness fix. The separate
native frontend timeout remains a setup failure requiring its own evidence;
no cause is assigned from the loading-plan defect.

## Reusable runner

`tools/qualify_mmx6_coop_pair.py` stages, launches, boots and observes two owned
processes. It imports the existing preparation, listener-ownership, diagnostic
and pair-comparison helpers rather than copying them. It records failures and
cleans up only owned processes. RAM writes, diagnostic fixtures, input
mailboxes and state loading are absent.

The final runner preserves default Seamless Loading. An explicit
`--native-loader-diagnostic` option reproduces the disclosed original-loader
bypass used by attempt 2. The runner gained that explicit flag after the
bounded attempts; neither attempt was rerun. Python 3.11+ is required by the
shared tools; the actual attempts used Python 3.12.5.

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/pycache-state'
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' `
  tools/qualify_mmx6_coop_pair.py `
  --tools-root F:/Projects/psxrecomp/_wt-mmx6-x4-parity/tools `
  --build G:/Temp/Codex/psxrecomp/x6-parity/build-debug `
  --disc 'F:/Projects/psxrecomp/MegaManX6Recomp/mmx6/Mega Man X6 (USA) (v1.1).cue' `
  --out G:/Temp/Codex/psxrecomp/x6-parity/netplay-next-default
```

Choose a fresh evidence directory. A passing bounded runner would still be
only an intro/input smoke. The pinned framework has no host-state `mod`
checksum partition; standalone diagnostic FNV matching must never be described
as full core/mod synchronization.
