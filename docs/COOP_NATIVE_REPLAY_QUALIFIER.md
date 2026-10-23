# Owned offline capture and replay runner

`tools/qualify_mmx6_input_replay.py` prepares and owns one hidden/muted native
recording followed by one private same-image replay. This implementation lane
ran only pure Python tests: no title build, native launch or R26 pass. The
successful runner status is `native_stream_consumed_outcomes_unverified`, not a
gameplay/outcome or complete machine replay qualification.

The caller supplies explicit frozen executable and compiled-manifest SHA256
values. The runner stages a fresh candidate using the existing playtest
preparer, validates the actual manifest JSON/header and its compiled SHA bytes
in the build/staged executables, and keeps that evidence. The staged executable
must independently match the explicit expected full-image SHA after preparation.
`run_capture(..., expected_exe_sha256=...)` rechecks those actual bytes immediately
before its Popen call; a preparation receipt or embedded manifest string cannot
substitute for this check. A changed image fails before launch and retains the
partial receipt. It copies no source
cards. Generated settings configure both slots as keyboard devices in digital
mode **before guest0** (`config_loader.cpp` controller settings keys). The exact
resolved startup bundle and exported initial cards are later required by the
strict replay module. Existing profiles and previous outputs are never reused
or overwritten.

Both launches explicitly use the SDK `--seal-interpreted-overlays` caller
policy. Ordinary offline preferences are not changed by the diagnostics
observer. All supported-scope/image/manifest/settings/content/implementation/
card validation remains active. An unavailable recorder, unsupported setup,
tainted/partial/failed recording or mismatch causes failure, never a fake trace
or ordinary-input replay fallback.

Recording uses the per-port published virtual host device added in SDK local
`a78ee4328` / integrated `4386d6740`. The preflight requires host_input_slots and
the selected host_port acknowledgement; older P1-only SDKs fail. Both native
slots must already report connected and digital. The route advances original
frontend Start/Cross inputs, reaches two idle living heroes, then holds P2 Right
and P1 Jump through native world-clock windows. Releases use a neutral host set
and preserve device topology. The trace must contain actual native P1 Cross
words and extra P2 Right reads. The receipt field
`actual_p1_cross_word_anywhere` means Cross occurred somewhere in the complete
stream, which includes frontend input. It does not associate that N with the
later gameplay jump window or establish a jump outcome. Native route observations
and their limits remain separate evidence; R26/outcomes remain unverified.
It never sends debug press/direct SIO, pad-type
overrides, a scripted input route, guest RAM writes or a title mailbox. This
does not qualify physical controllers or reproduce raw serial publication.
Non-neutral frontend pulses wait until the actual recording worker has emitted
its first complete canonical N. Until then the agent keeps the configured
devices neutral, so its controls cannot alter BIOS serial branches before the
recorded decoder seam. This live-prefix gate is not complete trace admission;
the finalized file is still strictly validated after quit.

The historical baseline.run still uses direct SIO controls and is unchanged.
This runner reuses baseline candidate validation, Windows listener/PID ownership
checks and the existing owned-Popen shutdown helper, with an independent host
route so historical behavior cannot contaminate an ordinary trace. Every RPC
is checked against the actual listener PID. Only the Popen it created may be
terminated/killed after the existing bounded quit/wait fallback.

After a clean acknowledged quit and process exit0, the runner requires one
complete canonical offline trace under the private save root. The codec checks
ordered repeated N/C events, counts, footer/hash, mode and exact required build
identities. The actual resolved startup topology and sealed implementation are
checked. The private replay preparer verifies finalized canonical capture status,
all settings/content/implementation artifact hashes and initial card presence/
bytes, then stages fresh private starting cards and the exact executable.

Replay uses the preparation receipt's fixed actual runtime arguments, rejecting
extra flags, escaped paths or changed environment/image. It rejects a preexisting
replay result before launch. The child environment clears inherited
PSX_/MMX6_INPUT_/RNET_/LNG_ values and applies only validated private paths and
muted audio. TEMP/TMP, AppData, data/config/cache, overlays, resident cache and
recordings stay in the F:/G: profile. The parent's environment is untouched and
credentials are not copied into receipts.

The native replay must exit0 within its explicit process deadline and commit an
exact consumed result with matching full trace SHA, event/consumed counts and
empty failure. Missing, duplicate/malformed, failed, partial, stale or nonzero
exit evidence fails. A fatal replay's debug listener can remain alive; the
runner retains its failed result/logs and stops only its owned process.

The replay implementation's EOF behavior is unchanged: the last recorded C can
return, then the next consumption fence disarms/drains and exits0 without an
unrecorded return or live-input fallback. There is no proven native/wall bound
for reaching that fence; this runner imposes a process timeout. At a next-N
fence the original serial decoder has already run, so its RAM is not a qualified
capture-end comparison. No live EOF RAM, core/mod/output hashes or native outcome
comparison are asserted. See [COOP_NATIVE_REPLAY.md](COOP_NATIVE_REPLAY.md).

Every attempt retains `qualification.json`, current runner source and dependency
hashes, manifest evidence, both process stdout/stderr, each recording RPC/reply,
route observations/windows, capture artifacts, replay preparation and runtime
result. Cleanup/protocol errors remain explicit; neither a timeout nor a failed
route is silently retried. No tracker/ledger result follows automatically.

After freezing a healthy candidate, fill the two owner-selected hashes and the
actual original disc path, then invoke this exact CLI shape from the game tree:

```powershell
$env:TEMP = 'G:\Temp\Codex\psxrecomp\x6-parity\temp\native-replay'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pycache'
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' tools/qualify_mmx6_input_replay.py `
  --build '<frozen native build directory>' `
  --source 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity' `
  --disc '<actual original disc used by that build>' `
  --output 'G:/Temp/Codex/psxrecomp/x6-parity/native-capture-replay-fresh' `
  --expected-exe-sha256 '<owner-frozen 64 lowercase hex>' `
  --expected-manifest-sha256 '<owner-frozen 64 lowercase hex>' `
  --record-port 24920 --replay-port 24921 `
  --boot-timeout 240 --progress-timeout 12 --replay-timeout 240
```

The placeholders intentionally refuse until replaced; the runner does not infer
an expected identity from whichever binary happens to exist. Timeout arguments
must be finite, positive and bounded (boot/replay<=600, progress<=60); ports must
be distinct. Output must not already exist. This lane did not execute that CLI.

Pure protocol/cleanup tests:

```powershell
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' -m unittest discover -s tools -p test_qualify_mmx6_input_replay.py
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' -m unittest discover -s tools -p test_prepare_mmx6_input_replay.py
```

All twenty runner tests and eight existing preparation tests passed. Tests mock
Popen/sockets; their synthetic executable bytes are never executed. They cover
capability/topology/override rejection, per-seat held/neutral routing, original
failure preservation during release, listener ownership, exact capture inputs,
stale/malformed/changed result/command/environment refusal, missing result,
native failure/deadline cleanup and failure-report preservation. The exact-image
regressions refuse changed staged bytes before capture, refuse a change after
candidate-environment validation immediately before Popen, and retain the
positive exact-image guard/forwarding path. A trace containing only an unbound
Cross word cannot be mislabeled as a proven jump. The initial
success-fixture error exhausted its finite mock poll list; using the real
process contract of repeated stable exit-code reads corrected that fixture
without changing runtime behavior or weakening assertions.
