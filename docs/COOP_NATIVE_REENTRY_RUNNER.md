# Owned offline native final-Quit/reentry runner

`tools/qualify_mmx6_coop_native_reentry.py` adapts the
[source-bound helper](COOP_NATIVE_REENTRY_AUDIT.md) to the existing baseline
and `OfflineMenuAdapter`. No game or title build was launched while adding
this runner. It creates one hidden, muted, private offline process through
the baseline; both route results, artwork and R15 remain unverified.

Use a separate fresh profile for each route. `current_data` requires an
actually eligible native RAM buffer. HeaderFFh remains `failed_setup` before
any native Quit input; the wrapper retains that partial report and exits1.
It does not fabricate current data, load a source card or convert the missing
prerequisite into success. `new_game` is a different native path and does not
qualify acquired-progress preservation or the current-data unit selector.

Choose an immutable complete build, exact executable SHA and frozen game
configuration source from the candidate receipt. The original raw BIN is a
separate source input from the runtime CUE. Replace these placeholders with
the selected values; do not hash an actively rebuilding directory and call
that an expected identity.

```powershell
$reentryPython = 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe'
$reentryTools = 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity/tools'
$reentryBuild = 'G:/Temp/Codex/psxrecomp/x6-parity/<immutable-complete-build>'
$reentrySource = 'G:/Temp/Codex/psxrecomp/x6-parity/<frozen-game-source-worktree>'
$reentryExpectedSha = '<selected-64-lowercase-hex-executable-sha256>'
$reentryRuntimeDisc = 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).cue'
$reentryOriginalDisc = 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin'
$reentryStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:TEMP = 'G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = 'G:/Temp/Codex/psxrecomp/x6-parity/pycache-native-reentry-runner'

& $reentryPython "$reentryTools/qualify_mmx6_coop_native_reentry.py" --build $reentryBuild --source $reentrySource --disc $reentryRuntimeDisc --output "G:/Temp/Codex/psxrecomp/x6-parity/reentry-$reentryStamp-current-data" --original-disc $reentryOriginalDisc --expected-exe-sha256 $reentryExpectedSha --route current_data --port 24899 --timeout 240 --progress-timeout 12 --reentry-timeout 180
& $reentryPython "$reentryTools/qualify_mmx6_coop_native_reentry.py" --build $reentryBuild --source $reentrySource --disc $reentryRuntimeDisc --output "G:/Temp/Codex/psxrecomp/x6-parity/reentry-$reentryStamp-new-game" --original-disc $reentryOriginalDisc --expected-exe-sha256 $reentryExpectedSha --route new_game --port 24899 --timeout 240 --progress-timeout 12 --reentry-timeout 180
```

These are sequential separate-process cases; do not run them together. The
alternative `--candidate <pristine-prepared-profile>` requires the same explicit
`--original-disc`, `--expected-exe-sha256` and `--route`; omit `--build`,
`--source`, `--disc` and `--output`. Existing shared pristine-profile validation
rejects prior runner/baseline evidence, populated private saves/cache/data and
any source-card preparation. The original EXE/archive/member source guards
run before staging/launch and again inside the helper before controls. Build
mode checks the selected executable hash before preparation; the shared
pristine/baseline checks validate the staged image and configuration before
Popen. Default Seamless Loading and the unmodified fresh co-op selection are
required through the same catalog/state guard as the native Quit runner.

`PersistentNativeInput` supplies only baseline-owned controls: nonzero mask
uses `press(port=seat+1, buttons=FFFFh XOR mask, frames=0)`, and zero uses
`clear_input` for that seat. Every request retains baseline's listener/PID
check. There is no input through the observer's read-only client, mailbox or
guest RAM. The frontend source never waits on diagnostic publication progress
after the old game thread ends. The helper observes the original decoded pad
and consumed neutral. Wrapper input receipts say `rpc_completed`, which is
only a protocol result; they do not label an acknowledgement as accepted input.

The baseline jump settles through the existing menu adapter before entry.
After the helper verifies native arrival and a strictly subsequent coherent
diagnostic publication, that same adapter runs the existing guest-menu,
resources, independent movement and native Square case. Native projection
scope/default-form checks remain in the helper. The runner does not relax or
replace them. It does not provide online or arbitrary runtime arguments.

The wrapper clears both owned native ports in `finally`, including helper
failure or unexpected input errors, without a diagnostic-clock wait. It
records clear-request errors separately from actual neutral-consumption
proof. Private card hashes are retained before/after the native case. Changed
cards or unavailable hashes revoke aggregate success; secondary clear/card
errors do not replace the original native failure. `ReentryError` is wrapped
in `DebugError` for the unchanged baseline's catch/finally, which owns actual
debug Quit, ACK/protocol-error details, natural-exit wait and any necessary
owned-process termination. Debug-server quit is never native Quit evidence.

Artifacts include the wrapper, native helper and shared guest-menu source
snapshots, module hashes, exact expected/candidate image, source identities,
default-loader evidence, persistent-input requests and complete partial
helper observations. The original `baseline/qualification.json` is retained
unchanged and linked by status/hash in the aggregate `qualification.json`.
Inherited `PSX_*`/`RNET_*` controls are excluded while constructing the offline
child, then restored in the CLI process. Runtime paths, caches, cards and
reports stay in the candidate's private non-C directories.

Exit0 returns `automated_native_reentry_checks_passed_artwork_pending` only
when the baseline, helper and all wrapper/card/cleanup checks complete. It is
not an R15 or artwork pass. Earned native-card preservation, paired same-machine
execution and the separate post-reentry guest-Select probe remain root-owned
qualification work.

Validation:12 new pure runner tests pass. They cover explicit route/raw source
and immutable-image options, staging/deadline exclusions, persistent original
ports/masks, ownership rejection, absence of frontend clock reads, retained
empty-header failure before any Quit press, finally release without extra
confirmation, secondary cleanup errors, card mutation, source/pristine/loader
guards and preservation of baseline cleanup/failure/environment receipts.
No native run, title build, existing runner/helper, plugin/SDK/CMake/ledger or
remote mutation was performed.
