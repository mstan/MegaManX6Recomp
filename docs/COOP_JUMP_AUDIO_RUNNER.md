# Owned offline jump-audio qualifier

`tools/qualify_mmx6_coop_jump_audio.py` owns one hidden, muted, fresh offline
process around the [source-pinned observer](COOP_JUMP_AUDIO_QUALIFIER.md).
No native run was performed when adding this runner. R4/R12 and audible output
remain unverified. It changes no game or SDK implementation.

The caller supplies an exact executable SHA-256 and compiled declared-manifest
SHA-256, original SLUS01395 v1.1 EXE, raw disc BIN, actual source tree and build.
The tool reproduces the pinned audio contract from the original EXE and DAT85/87
before launch. It validates manifest JSON/header and embedded SHA bytes in both
the build and staged image. It separately rehashes the declared `game/` and
`game-generated/` files through the actual CMake cache mappings. Missing,
escaped or changed inputs are refused. Other dependency roots are bound by
the compiled declared manifest, not independently rehashed or represented as
complete binary provenance. Staging observations do not infer build identity
from current Git HEAD.

The preparation helper creates private settings, cards, cache and logs. Both
native devices are configured as connected digital keyboard/host slots before
frame0. There is no source-card option. The original default OpenBIOS/HLE
loader, authentic1x disc timing, OpenGL/native4:3 and no rewind are required.
The explicit offline `--seal-interpreted-overlays` policy is passed to the
runtime; it does not bypass native game loading. Inherited simulation/debug/
replay environment variables are removed using the existing capture runner's
sanitizer, with owned runtime variables applied afterward. All generated
profile paths stay on F:/G: and SDL uses the dummy audio device.

Before any frontend input, the runner verifies both digital devices through
`pad_status`, verifies observed inactive offline transport through
`netplay_status`, and waits for the complete first native-consumption record. It
uses only `set_input(layer="host",port=1|2)` with persistent buttons, centered
axes128 and triggers0. Each update requires a selected-slot status
acknowledgement, the correct host buttons, both native digital devices, and
absence of SIO/analog/identity overrides. It never uses `press`, the SIO-layer
`set_input`, player writes, mailbox commands, RNG changes or guest calls.
Original frontend Start/Cross input reaches the same offline sampler and
NativePad decoder as ordinary host devices.

After native intro setup, the observer drives the requested jump order.
Every hold retains its selected-slot acknowledgement, coherent start/end
diagnostics and forward native PLAY timer plus diagnostic publication deltas.
`native_advance` uses the actual PLAY timer. Observation and hold receipts are
JSON data; the observer is not duplicated in this runner. A neutral published
host value preserves device topology between holds. Final teardown clears
each selected **host** slot independently, verifies the clear acknowledgement
and uses the baseline's PID/listener-checked quit/exit lifecycle. A bad quit ACK,
unexpected exit, clear failure or changed existing private card fails the run,
even when the process subsequently exits0. Only its own Popen may be stopped.

After a clean quit, the tool validates exactly one complete canonical offline
N/C recording and retained starting cards/settings/content/implementation
artifacts against the expected image and manifest. It requires the actual
recorded two-device topology and sealed ordinary implementation. Requested
seat Cross values must occur in the appropriate N or C stream. These
whole-stream checks do **not** establish a temporal association between a
particular trace event and a particular jump: the observer separately requires
native action6/upward motion inside each held input window. No recording or
diagnostic field is treated as PCM/output equivalence.

Run only after the owner has released the title/game slot. Use a fresh output
for every attempt, preserving every failed attempt. Example, with the exact
SHA values from the selected build substituted explicitly:

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp/audio-owner'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/temp/audio-owner/pycache'
python tools/qualify_mmx6_coop_jump_audio.py --build 'G:/path/to/frozen-build' --source 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity' --original-exe 'G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95' --disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin' --expected-exe-sha256 <exact64hex> --expected-manifest-sha256 <exact64hex> --output 'G:/Temp/Codex/psxrecomp/x6-parity/jump-audio-fresh-01' --first-seat 0 --max-attempts 8
```

`--first-seat` accepts0/1 only. `--max-attempts` is1..8; boot, progress and
audio timeouts are finite and bounded. The source contract can be supplied
explicitly with `--contract`; its content must match the pinned canonical
SHA. The original EXE must be the exact file used by the staged game config,
beside the disc as required by the existing preparer.

Exit0 is `jump_audio_observations_complete_outcomes_unverified`; it still
does not qualify audible output or R4/R12. A `comparison_failed` result exits1
and retains all observations. Intentional RNG silence or no overlapping
two-key-on window returns `inconclusive_native_rng_no_two_voice_window` and
exits2. Private voice/bank paths remain refused. The current shared voice20
path is expected from source to expose replacement/resource ownership gaps;
only an actual run can establish its observed result.

The output keeps `qualification.json`, exact `runner-source.py`, copied source
contract, manifest JSON/header, prepared profile/source patches, raw stdout,
stderr and control JSONL, per-seat ACKs, coherent observation windows,
source-sample hashes, event/lifetime comparison, complete N/C trace, startup
artifacts and before/after private card hashes. Setup and observer errors keep
their prefixes and partial report. Existing output directories are refused.
No screenshot, active-mask-only result or debug fixture is an audio pass.

Pure verification, requiring TEMP/TMP/cache on F:/G: first:

```powershell
python tools/test_qualify_mmx6_coop_jump_audio.py -v
```

The 16 tests cover inactive offline transport, selected-seat publication/clear, neutral axes/device
acknowledgement, native/publication progress and failure cleanup, strict
source mapping, changed source, finalized/truncated capture/startup negatives,
bad quit ACK, private card mutation, foreign listener refusal, preserved setup
failure artifacts and output reuse. Popen/socket access is mocked; these tests
do not launch a native process or qualify any audio mechanic.
