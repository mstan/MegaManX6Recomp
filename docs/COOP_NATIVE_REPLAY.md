# R26 bounded offline native-consumption replay

This implements explicit offline replay of the existing `mmx6.native-consumption.v1`
N/C contract. R26 remains **unverified**. Helper fixtures do not establish native
replay, outcome equality, raw SIO/publication reproduction or paired replay. No
game executable was built or launched in this lane.

The frozen source references are X4 `50593bca772b600de6911cbfecd40b0f08721147`
(`mmx4_diagnostics.cpp` blob `139473f5bf1548bdbe1e139969d07a1ca078e9b2`)
and X5 `9ed460e7b7e60769fa12bcab74e228ae19796214`. Their exact recorder,
replayer and launcher hashes are retained in
[COOP_INPUT_RECORDING_AUDIT.json](COOP_INPUT_RECORDING_AUDIT.json).
Their ordered native/extra-pad supply informs this implementation. Their failure
fallback to ordinary controller sources and launcher truncation of a final
interval are deliberately not used: an explicit X6 replay requires the complete
terminal and never falls back to live input.

For original SLUS01395 v1.1 EXE SHA-256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`,
the native decoder span `80012A34..80012C50` has SHA-256
`8ca7b0e60a42934a40186be927ca9ec2683f2ace00b37edd0b2f9a293ef379fa`.
N is the existing instruction hook `80012C44`/`8FBF0010` after both native
triples, with caller from guest `sp+16`, frame `80097420`, and triples
`800C456C/6E/70` and `800C4758/5A/5C`. The six existing P2 C tags remain
stage, controller-scene, controller-inactive, controller-blocked,
controller-player and interaction. No world-frame deduplication is allowed.
[COOP_INPUT_CONSUMPTION_CONTRACT.md](COOP_INPUT_CONSUMPTION_CONTRACT.md)
records the exact native call sites, serial-latch distinction and limitations.

## Admission and private setup

An explicit `MMX6_INPUT_REPLAY` request selects the SDK guarded startup observer
during trusted title construction, including an empty request which refuses.
Capture and replay are exclusive. The ordinary capture path retains its default
and its non-refusing error behavior. Replay requires the exact active offline
diagnostics plugin, complete actual startup export at cycles/tick zero, offline
mode, and a prepared absolute private profile via `MMX6_INPUT_REPLAY_PROFILE`.
No observer changes controller sources, backend, floating-point environment,
settings, negotiated profile or capabilities.

The complete trace is read and validated by a joined startup worker before
activation: maximum 262144 events, 128 MiB file, 16384-byte line. No partially
validated vector becomes available to a consumer. The actual writer encoder
independently reconstructs every canonical header/event/footer, checks stream
hash, caller/edge/order/cycle/count invariants, and rejects a failed terminal,
truncation, extra data, unknown/duplicate keys, overflow or unsupported online/
restored-state baseline. Identity comes from actual startup, not the trace:
image SHA, compiled manifest SHA, execution ID, settings/content/implementation
bundle hashes, both card byte hashes/presence, and null cold-boot baseline must
all match. The retained bundle/card files must also equal those actual owned
bytes. A finalized canonical source status is required. Its historical scope
string is a capture format label, not a replay qualification claim.

`tools/prepare_mmx6_input_replay.py --recording <finalized-directory>
--candidate <exact-staged-candidate> --output <new-private-directory>` only
prepares files. It verifies the candidate executable's exact SHA and presence of
the compiled manifest SHA, copies its runtime/configuration sources, and copies
the trace's initial card bytes to private `saves/cardN.mcd`. Absent slots stay
absent. It never imports a card, overwrites an existing destination or launches
a game. On Windows output is restricted to F:/G:. Manifest SHA string presence
is an additional declared-byte check, not exhaustive binary provenance.

The receipt emits real runtime arguments `--game`, `--memcard-dir`,
`--seal-interpreted-overlays`, `--no-launcher`. `--memcard-dir` clears explicit
slot paths at both actual ordinary startup override boundaries. The replay
observer additionally checks every bound live card path resolves under the
private profile's `saves` directory. It only exports already initialized bytes;
it never rebinds/imports/flushes cards. A preparation marker binds exact image and
full trace SHA. Runtime output must stay under that private profile. All replay
file reading/writing uses the startup/status workers.

The receipt isolates TEMP/TMP, AppData/data/cache, resident/overlay caches and
recording output and supplies dummy automated audio. It lists inherited
PSX_/MMX6_INPUT_/RNET_/LNG_ environment prefixes that the caller must clear
before applying its explicit environment. Configuration JSON is not an
importable preference file: the supplied candidate must retain the original
settings.toml, keybinds.ini and other configuration sources. Actual startup
compares their resolved result and refuses discrepancies. Existing relative
resource paths may require the original staged candidate's absolute resources;
preparation does not reconstruct missing original content.

The caller-owned `--seal-interpreted-overlays` SDK path (local SDK commit
`fd52f9413`) is a separate integration dependency. It must join cache
initialization, stop autocompilation, successfully
call `code_provider_session_seal_interpreted()` before guest zero, and end that
policy only after guest execution stops. The observer checks the resulting
envelope, not the CLI's presence. Ordinary unsealed offline remains refused.
Other scope exclusions remain: external BIOS, nondefault FP, known simulation
testing overrides, opaque input callbacks, mouse, PGXP, dynamic/wide projection,
rewind, non-unit cycle scaling and unexported persisted native option restore.
The seal supplies implementation lifetime closure; it does not qualify a CPU
profile or another machine.

## Supply and terminal behavior

At each N, the actual observed kind/order/native ordinal/cycles/tick/caller/frame
and both previous decoded words must match. Only then are the six recorded
native halfwords written. CPU state and all other RAM are untouched. At each C,
the exact ordered consumer and cycles must match before its recorded active-high
standard buttons are returned. The ordinary `p2_input` path still samples SIO
once, and its observer returns the same value unless explicit replay is active.
No observer samples another pad, enters guest execution or polls capabilities.

Validated events are immutable and fully prefetched; successful N/C supply does
no filesystem I/O, parsing, allocation or worker waiting. Sticky unilateral/
fixture taint, a title mailbox, unexpected consumer/caller/frame/previous/cycle
or early/state-replaced end records failure. A mismatch never writes that N's
triples or returns that C's ordinary buttons. After the outer observer guard is
released, replay is atomically disarmed and the SDK end callback joins its
status worker. Only then does the existing `psx_fatal_halt` boundary run. No
longjmp, lock reentry or new scheduler escape is used. The SDK's callback
adapter uses trivially destructible context; no replay Callback guard survives
the terminal call.

After all recorded events have been supplied, the next valid consumption
boundary terminates successfully through the existing tagged process exit.
This permits the final returned C value to reach its caller. The result says
`consumed`, not gameplay passed: work between the final event and that next
boundary and native outcome equality are not asserted. An early normal/process
exit with events remaining is failed. A failed status write also prevents
successful completion. Forced termination/crash or permanent OS I/O stalls
cannot promise a drained result.
There is no proven hard wall/native time bound to reach that next read, and
process exit supplies no live end-state inspection window. An N fence is after
the original decoder: the next serial/decode work and its native pad RAM writes
have already occurred before that hook exits. No further replay input is
supplied or C value returned, but this terminal RAM is not a qualified
capture-end state comparison.

## Evidence and remaining qualification

The actual-module fixture uses real worker threads/files, SDK boundary doubles
and isolated RAM/cards. It checks two native ports, all six C tags, repeated
native frame, unchanged CPU on N, exactly six permitted RAM writes, private card
preservation, terminal ownership after guard release, startup identity/artifact
refusals, runtime order/cycle/caller/frame/previous/tag/taint/mailbox failures,
early end and state replacement. The independent reader test rejects every byte
truncation, malformed/order/hash/identity/count/overflow/cap failures. The normal
capture fixture checks unchanged CPU/RAM and all six observations; actual co-op
helper checks one SIO read per call and use of an explicitly supplied return.
Preparation tests never execute their synthetic executable bytes.

The checked helper matrix passed Clang 22.1.8 and GCC 15.2 at those optimized
flags, assertions active, with/without debug tools: eight reader/replay cells
and twelve normal capture/co-op diagnostics/private-effects cells. The two
legacy-service absence cells also passed. Python checks passed twenty codec,
eight preparation and three hook-emission negatives. The original debug fixture
failure logs are retained in G: scratch: its persistent mailbox flag had to be
cleared before the separate ordinary-input return-supply assertion. No runtime
behavior or assertion was relaxed to correct that fixture setup.

Compile helper fixtures with assertions active, e.g. C++17, `-O3 -UNDEBUG
-ffp-contract=off -pthread`, SDK runtime includes and the actual `psx_sha256.c`
object. Run `tools/test_mmx6_native_replay.py --fixture <compiled-exe>
--output <owned-G-scratch>`; run reader fixture directly and Python unittest
discovery for `test_prepare_mmx6_input_replay.py`. These are helper results only.

The guarded diagnostics startup service must be present (SDK commits
`345637ba6` and `5e900ebc5` or their integrated equivalents). On older SDKs
without any session diagnostics header, an explicit replay exits with failure
during trusted construction instead of registering a live-input fallback.

Integration still needs a fresh executable (image/manifest change is expected),
regenerated/emitted native hook, actual supported offline capture, strict replay
of that same executable/settings/starting cards and comparison of native
menu/lifecycle/low-latency outcomes. No runtime/R26/ledger pass follows from
these fixtures. Raw SIO bytes, serial transaction state and publication timing
are not replayed; an N/C trace is not a complete machine event stream. The
current startup implementation export also does not independently hash loaded
non-system DLLs; copying candidate DLLs does not prove which files were loaded
during capture. No cross-build, cross-compiler, other-CPU, other-OS or second
physical-host claim is made.
