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

The 17 runner tests cover inactive offline transport, selected-seat publication/clear, neutral axes/device
acknowledgement, native/publication progress and failure cleanup, strict
source mapping, changed source, finalized/truncated capture/startup negatives,
bad quit ACK, private card mutation, foreign listener refusal, preserved setup
failure artifacts and output reuse. Popen/socket access is mocked; these tests
do not launch a native process or qualify any audio mechanic.

## Native endpoint correction

The first owned v16 attempt at
`G:/Temp/Codex/psxrecomp/x6-parity/jump-audio-v16-4cdfe4d-local-x-first-source-bound/qualification.json`
reached a valid native jump, then the observer falsely refused its later
action7 endpoint. That original report is preserved unchanged, SHA-256
`2be42456f2b78ca830580a74b70c98fee4bd684875eb0e7bdb5cf95f922d33af`.
The earlier source-cache mismatch was refused before launch; it supplies no
runtime/audio result. Neither attempt establishes an R4/R12 audio failure.

The original action table `80073ACC` selects action6=`80035620` and
action7=`800368FC`. Ground jump initialization `8003AF30..4C` copies actor+F8
to actor+24 and sets airborne1; `8003AFD8..E0` selects action6. Actor+24 is
vertical speed with **positive up**: `8002D070..80` subtracts it from Y;
`8002D0A0..B4` subtracts gravity actor+2C from that speed. Actor+1C is previous
Y, copied at `80034E30`, not a velocity. A grounded body can retain stale
speed, so it is not an airborne/idle discriminator.

The action6 handler tests held native Cross (`actor+7C & 80h`) at
`8003565C..70`. Releasing it zeros actor+24. At `80035760..8C`, nonpositive
speed selects animation11, airborne-1 and action7. Action7 handles landing
through `8003690C..34` and otherwise continues the ordinary air path. Thus
sampling after the owner's finally-neutral release can legitimately observe
action7 while the actor remains above its initial Y.

| Original observed point | Publication / native timer | Action / airborne | Y raw | Actor+24 |
| --- | --- | --- | --- | --- |
| Ground before hold | 148 /147 | 2 /0 | 73072640 | -354816 (stale) |
| End while Cross held | 152 /151 | 6 /1 | 72691712 | +364032 |
| Observer after neutral release | 156 /155 | 7 /-1 | 71997440 | -33792 |

The narrow corrected predicate requires the held receipt to prove living
native action6 and upward displacement from the grounded start. It then
accepts only action6/airborne1 or action7/airborne-1, still airborne and above
that starting Y. It refuses a generic falling actor, absent held evidence,
other actions, wrong seat, changed HP/character, no displacement and invalid
progress. It no longer treats the post-release velocity as a rising-speed
requirement. No input duration, game state or sound routing was changed.

Sampler acceptance is independently retained: 94 host receipts exist, and the
specific jump ACK id1360 has host port1, layer enabled, buttonsBFFFh, centered
axes and native slot0 buttonsBFFFh with both connected digital devices and no
SIO overrides. Its held window advanced3 native ticks and3 publications.
The source-bound image SHA-256 is
`eeb5754a53a6d10aeac13b294ce3325a7e2b8a6180b20ce001a3800401fcec6d`;
compiled manifest is
`3d462d7f1bdcdbcd5f17211eaf597a7b3be4e199484c1f08fb90444f6cae89c8`.
New SPU events202/203 were KEYON voice20/22 at engine frames2543/2545.
No audio sample/lifetime comparison had run when the false refusal occurred.

Owned PID50516 quit with a valid ACK, exit0 and unchanged existing private
cards. A separate read-only postmortem validated its canonical finalized
offline recording and all initial card/settings/content/implementation
artifacts: **5844 events,4096 N,1748 C**, trace SHA-256
`cbab538f52e1511628afaa43c33b6eb936b797fbd34fd5e8d83af9ba1f398e88`.
The stream contains P1 Cross, without claiming RPC-to-event temporal mapping.
The prior runner had skipped this postcheck when the observer threw; it now
performs post-quit recording validation after such exceptions too, preserving
the original error and any separate postrun error. Valid input artifacts
cannot convert an observer error into success.

[The compact regression fixture](../tests/fixtures/mmx6_jump_audio_native_endpoint_v16.json)
retains scalar observations, ACK/hold evidence, source-window/table identities,
raw-report/control hashes and finalized artifact hashes, with no game assets
or card bytes. Four new observer tests cover this actual trace, positive-up
speed, rejected alternative states and original EXE window reproduction.
Together with the post-error runner regression, the suites pass48/48 when
original-source paths are supplied. The correction needs a fresh owned native
rerun; R4/R12 remain unverified.
