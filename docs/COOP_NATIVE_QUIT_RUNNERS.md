# Owned native Quit scenario runners

The offline CLI and the paired option adapt the
[bounded source-backed helper](COOP_NATIVE_QUIT_AUDIT.md). No native run was
performed while implementing these adapters. They never select final Quit on
the second page and do not qualify current-data loading or character reentry.
Native outcomes, artwork and R7/R15 remain unverified.

Run **one scenario per fresh profile/pair**. `guest_authority` attempts original
P2 Start/Select and requires a refusal. If the guest enters native Quit UI,
the original failed behavior and any capture failure remain recorded, no
Cross confirmation is sent, and the CLI exits1. This is an expected diagnostic
failure on a candidate that admits guest Quit; it is never an expected-success
conversion or an R15 pass. `p1_pages_cancel` exercises the source-mapped
primary Continue/cancel path and both confirmation pages with wrong-seat
input rejection, then cancels and resumes native controls.

Use a frozen exact executable and complete build directory. The paired build
must include its compiled `psx_build_manifest/psx-runtime` manifest/header and
bundled catalog, not just a copied executable. Set `quitExpectedSha`, the
expected lab profile and its revision from the selected candidate's retained
receipt/catalog. Do not calculate an expected hash from an actively rebuilding
directory. The placeholders below must be replaced with those selected values;
the rest of each command is complete. Fresh output names retain every attempt.

```powershell
$quitPython = 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe'
$quitTools = 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity/tools'
$quitSource = 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity'
$quitBuild = 'G:/Temp/Codex/psxrecomp/x6-parity/<frozen-complete-build>'
$quitExpectedSha = '<selected-64-lowercase-hex-executable-sha256>'
$quitHostProfile = '<selected-explicit-host-profile>'
$quitHostRevision = <selected-positive-profile-revision>
$quitDisc = 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).cue'
$quitOriginal = 'G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95'
$quitStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:TEMP = 'G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = 'G:/Temp/Codex/psxrecomp/x6-parity/pycache-native-quit'
```

Offline, original native pads through the existing `OfflineMenuAdapter`:

```powershell
& $quitPython "$quitTools/qualify_mmx6_coop_native_quit.py" --build $quitBuild --source $quitSource --disc $quitDisc --output "G:/Temp/Codex/psxrecomp/x6-parity/quit-$quitStamp-local-guest" --original-exe $quitOriginal --expected-exe-sha256 $quitExpectedSha --native-quit-scenario guest_authority --port 24898 --timeout 240 --progress-timeout 12 --window-frames 12
& $quitPython "$quitTools/qualify_mmx6_coop_native_quit.py" --build $quitBuild --source $quitSource --disc $quitDisc --output "G:/Temp/Codex/psxrecomp/x6-parity/quit-$quitStamp-local-primary" --original-exe $quitOriginal --expected-exe-sha256 $quitExpectedSha --native-quit-scenario p1_pages_cancel --port 24898 --timeout 240 --progress-timeout 12 --window-frames 12
```

The alternative `--candidate <new-prepared-profile>` mode requires the same
original EXE, expected executable SHA and explicit scenario; omit `--build`,
`--source`, `--disc` and `--output`. It refuses earlier baseline/runner files,
nonempty private cache/data/saves directories or any source-card preparation.
Both modes require the normal default-on Seamless Loading catalog feature and
the fresh original co-op selection without other persisted feature overrides.
Inherited `PSX_*`/`RNET_*` session, input and backend controls are excluded only
while creating the offline child, then restored in the CLI process. Private
runtime paths, hidden window and dummy output audio come from the existing
baseline; no source cards are read or copied.

Paired, original published host samplers on **this same machine only**:

```powershell
& $quitPython "$quitTools/qualify_mmx6_coop_pair.py" --tools-root $quitTools --build $quitBuild --disc $quitDisc --out "G:/Temp/Codex/psxrecomp/x6-parity/quit-$quitStamp-pair-guest" --original-exe $quitOriginal --expected-exe-sha256 $quitExpectedSha --native-quit-scenario guest_authority --require-host-profile --expected-host-profile $quitHostProfile --expected-host-profile-revision $quitHostRevision --require-state-crc --host-port 24901 --guest-port 24902 --host-udp 29901 --guest-udp 29902 --session 20261023 --timeout 240
& $quitPython "$quitTools/qualify_mmx6_coop_pair.py" --tools-root $quitTools --build $quitBuild --disc $quitDisc --out "G:/Temp/Codex/psxrecomp/x6-parity/quit-$quitStamp-pair-primary" --original-exe $quitOriginal --expected-exe-sha256 $quitExpectedSha --native-quit-scenario p1_pages_cancel --require-host-profile --expected-host-profile $quitHostProfile --expected-host-profile-revision $quitHostRevision --require-state-crc --host-port 24901 --guest-port 24902 --host-udp 29901 --guest-udp 29902 --session 20261023 --timeout 240
```

The pair rejects `--admission-only`, `--native-loader-diagnostic` and every
other optional menu, lifecycle, contact, targeting or private-effects route
when a native Quit scenario is selected. Both actual launch argv plans must
use cross-linked numeric `127.0.0.1` UDP endpoints, delay3, slots0/1 and original
host-pad mapping. Hostnames, LAN/NAS addresses and other machines are rejected.
Each debug request still checks the listener/PID of its owned Popen process.
The source EXE is verified before staging/launch. Staged executables must match
the explicit expected image and declared build evidence. Each actual startup
log must contain the identical pre-guest capability/profile agreement, both
default resident-loader commits must exist, and actual resolved core/mod CRC
samples must already be present before the optional case sends input.

The shared `PublishedHeldInput` exclusively supplies `published_host` controls,
uses resolved transport windows even while native time is frozen, and always
neutralizes in `finally`. Actual post-case resolved comparisons are mandatory
for success. The existing pair's ordinary intro/input checks and complete
owned-process cleanup remain in place. A helper exception remains a failure;
the runner never adds a guest Cross/cancel in an attempt to recover from it.
Debug-server quit is only owned cleanup and is never native Quit evidence.

Both adapters retain source/helper hashes, input/observation/capture receipts
and private native-card hashes. The original offline baseline report is
retained without rewriting its failed status, and helper errors are wrapped
in `DebugError` so its existing cleanup still runs. Successful offline
automation returns `automated_native_quit_bounded_checks_passed_artwork_pending`;
the pair retains its usual aggregate `passed` only if every required guard
and case check succeeds, with the native case/artwork status separately pending.
Neither result passes R7/R15 or extends the source audit's stated scope.

Validation:34 pure checks pass:12 helper tests,9 new runner/adapter tests and
13 paired-option tests (including2 new scenario guards). They cover missing
identity/profile/CRC/source guards, incompatible optional routes, catalog/state
loader overrides, numeric endpoint/cross-link rejection, published input and
neutral cleanup, baseline-compatible error propagation, original failure
retention, inherited offline session isolation and private-card read errors.
No game, title build, plugin/SDK/CMake/ledger edit or remote action occurred.
# Native guest-authority reproduction and fix

Root reproduced guest Select entering native menu1/substate6/phase1/page0 on
exact executable `089bb606`. The probe stopped before Cross, retained its
failed result and acknowledged Quit/exit0. The completed image was black
with fade field1; confirmation artwork remains unverified. The
[reviewed reproduction](evidence/mmx6-native-quit/manifest-bound-6c42c5c-guest-repro.json)
binds the native state and original report. Source now withholds Select only
at P2's owned phase2 menu, while preserving join history, other menu buttons,
P1's native Quit controls and gameplay Select. Actual-plugin debug/production
fixtures pass. Title contract `mmx6-x-zero-delay-v13` requires fresh native
qualification; source tests alone do not pass R7/R15.

