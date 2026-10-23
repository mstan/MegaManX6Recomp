# Owned same-machine New Game reentry probe

`qualify_mmx6_coop_pair.py --native-reentry new_game` adapts the existing
source-bound `mmx6_coop_native_reentry.native_reentry_smoke` to two owned peers.
The option is a qualification route; the gameplay correction stays default.
No native result or ledger pass is established by this implementation/tests.

The separate [exact348a52c native receipt](evidence/mmx6-native-reentry/manifest-bound-348a52c-new-game-reviewed.json)
now completes this New Game route on two owned same-machine peers, including
all11 guest-menu checks,29 matching resolved core/mod samples, matching reviewed
paused/resumed images and natural owned exit0/private-card preservation.
Earlier incomplete setup and180-second wall-deadline attempts remain retained.
The latter was still changing story state at its deadline; it is not evidence
of a stationary native story deadlock. Full Continue/current-data/acquired
progression and R15/F208 scope remain incomplete.

Use a new output directory, an exact expected executable SHA, the default
resident loader, required resolved core/mod CRC and the actual expected host
profile/revision. The runner stages both private profiles from the supplied
build/source. It validates the compiled canonical manifest and its embedded
SHA using the existing gate, then rehashes the declared game/generated source
inputs against that manifest using the existing source validator. That check
does not rehash every SDK/dependency root or assert whole-build provenance.

The runtime CUE must contain one quoted BINARY file, track01 MODE2/2352 and
index01 `00:00:00` (REM lines allowed). Its resolved file must be the exact
explicit `--original-disc` raw BIN. Multi-file, shifted-index and other track
layouts refuse before launch. The helper also pins the original USA1.1 EXE,
ROCK_X6.BIN and native menu/title members and checks the relevant loaded native
code windows on both peers before controls. Prepared boot EXE/CUE/private-card
paths and default loader settings are checked before Popen. This is bounded
content/source identity, not a whole raw-disc hash claim.

Both fresh profiles receive connected digital keyboard devices before either
process starts. Each logical seat uses **its own peer's local host port1**,
matching actual `--net-input-player 0`; the peer's native/transport path resolves
that input into the corresponding session seat. `HostRoute` and `control_for`
retain per-command PID/listener ownership, exact host-layer acknowledgements,
neutral axes, digital topology and absence of direct SIO overrides. No `press`,
RAM/mailbox input or physical port2 shortcut is used. Per-peer command transcripts
and host-status receipts are saved. Neutral releases keep the topology stable;
final teardown clears only each peer's host port1.

The actual launch plan must cross-link two different numeric127.0.0.1 UDP
endpoints, roles0/1 and delay3. Existing host-profile gates require one identical
pre-guest agreement per peer and recheck the complete logs after teardown.
The selection remains fixed through final Quit and New Game; the runner does
not renegotiate capabilities or change the simulation profile.

The shared native helper, unchanged by this adapter, requires every frontend
press to reach the actual post-decoder held bits, the expected native transition
on **both** peers and consumed neutral. Story/in-game dialogue Cross is supplied
only at its original ready phase, with actual cursor/page/retirement response.
Native arrival requires original idle action2, inactive dialogue and clear
script locks. A later per-peer diagnostic publication must then establish fresh
living X/P1 + Zero/P2 ownership. A stale publication from before Quit cannot
satisfy that gate. New Game defaults are checked in an observed native primary
scope; they are never normalized from a projected Zero read.

After fresh reentry, the full existing Zero/P2 personal-menu check runs again:
owner pause/frozen native clock, wrong-seat Start/cursor rejection, real Down/Up
cursor change/restore, resources, resume, independent Right and native Square.
Paused holds use resolved network ticks; gameplay waits use the native world
timer. Both composed captures are retained, then matching resolved core/mod CRC
evidence is required. Artwork review remains pending independently of automatic
checks.

Card hashes are retained before/after the native case and again after both owned
processes stop. A changed/unreadable card, failed host neutral/clear, nonzero exit,
unexpected exit or forced termination revokes success. Partial native cases and
the original failure survive cleanup errors. Each process uses the existing
owned shutdown helper; no external process is terminated.

Example (substitute the actual frozen build/source/image identity):

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp/reentry-pair'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX=$env:TEMP+'/pycache'
& $python tools/qualify_mmx6_coop_pair.py `
  --tools-root $executingTools --source $compiledGameSource --build $frozenBuild `
  --disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).cue' `
  --original-disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin' `
  --out 'G:/Temp/Codex/psxrecomp/x6-parity/native-reentry-pair-FRESH' `
  --expected-exe-sha256 $actualImageSHA --native-reentry new_game `
  --require-state-crc --require-host-profile `
  --expected-host-profile mmx6.win64-clang22.loopback --expected-host-profile-revision 2
```

Do not combine this route with the other optional scenarios. The helper uses
bounded12-second input/readiness deadlines and180-second source-gated reentry
deadline; the existing boot timeout remains separate. The CLI deliberately
admits only `new_game`. The offline current-data route remains separate and
refuses an empty current buffer before any Quit input. No acquired progress,
source cards, Load/Continue, primary Zero/opposite roster, frame0 roster choice,
different physical host or heterogeneous CPU/OS qualification is claimed.

Pure validation, with TEMP/TMP/pycache pointing to owned non-C scratch:

```powershell
& $python -m unittest discover -s tools -p test_mmx6_coop_native_reentry_pair.py
& $python -m unittest discover -s tools -p test_mmx6_coop_pair_options.py
& $python -m unittest discover -s tools -p 'test_mmx6_coop_native_reentry*.py'
```

The new protocol suite covers mismatched/shifted/multi-file CUEs, prepared
topology/default-loader rejection, local port ownership, malformed acknowledgments,
lost listeners, missing manifest/source proof before Popen, unchanged existing
pair evidence, partial helper failure, neutral/card failures and final owned
teardown gates. These tests launch no native process and do not qualify gameplay.
