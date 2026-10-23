# R26: bounded native-consumption capture activation

The trusted `mmx6_diagnostics.cpp` observer now connects the frozen-source
contract in [COOP_INPUT_CONSUMPTION_CONTRACT.md](COOP_INPUT_CONSUMPTION_CONTRACT.md)
to a bounded native writer. **No native executable has been built or run for
this change. Replay remains unimplemented and R26 remains unverified.**

The default-enabled `mmx6.diagnostics` catalog feature owns the offline
instruction callback. The actual forced online profile
`mmx6.local-coop.prototype` owns the same callback online. Startup checks the
actual committed plugin ID through the SDK read-only getter; a disabled offline
feature does not start a restore-only or empty capture. `MMX6_INPUT_RECORDING=0`
explicitly disables capture. No setting, pad, backend or capability agreement is
changed to make a configuration eligible.

The SDK final-startup service supplies the actual image/declared-manifest/
execution/selected-profile identities and owned resolved settings/content/
implementation bundles. The observer copies both present 128 KiB memory cards on
the owner thread through `memcard_export_raw`, after initialization/sync and
before guest dispatch. Absent cards stay absent. It never imports, flushes,
rebinds or reopens a live card. The three exact bundle files and initial card
copies accompany the trace. Their hashes occupy the existing codec identity
fields, including `simulation_contract_sha256` for `simulation-contract.json`.
The SDK's admitted `coldboot-native-consumption-v1` scope is required; unsupported
startup prints its actual reason and starts no worker. In particular ordinary
unsealed offline overlays remain unavailable. The default-on diagnostic feature
does not claim default offline capture is already qualified.

The native callback is configured at `80012C44`/`8FBF0010`, after both original
decoded pad triples. It validates an aligned in-RAM guest stack and reads the
saved original return PC at `sp+16`, never the inner-call live `$ra`. Both native
triples and native frame are read without reentering guest code. Exactly six
existing co-op reads pass explicit consumer tags; the existing SIO read still
happens once and returns its same final active-high unswapped buttons. A title
mailbox result and each accepted setup command 1–7 mark the session-sticky fixture
taint. Rejected/unknown operations do not invent acceptance. Every actual event checks
the non-consuming sticky unilateral-input flags. Published-host provenance is
retained in startup settings and is not a unilateral SIO bypass.

`game.toml` now lists the native instruction site. **Generated C is deliberately
not edited:** integration must regenerate with that config and verify the actual
generated function emits `psx_mod_instruction` immediately before the original
`80012C44` instruction. Merely finding the config/registration is not emission
or runtime evidence. The fixture verifies both offline/online registrations and
their exact expected word, and actual C callbacks retain CPU/RAM behavior.
`tools/check_mmx6_input_capture_hook.py --unit generated/SLUS_013.95_full_00.c`
requires the exact callback in the actual decoder block before its original
saved-RA load, emits source hashes, and fails on missing/malformed/duplicated or
late hooks. Its synthetic malformed-emission suite passes; the existing old
generated unit was actually rejected for the missing hook. A regenerated
positive remains an integration check.

On the simulation owner, events are fixed owned POD copies into an 8192-event
SPSC queue. There is no file I/O, dynamic event allocation, guest call, extra
input sample or capability poll on that path. A separate worker encodes explicit
fields as the same canonical ASCII JSONL consumed by
`tools/mmx6_input_recording.py`. Equal world/native frame numbers and identical
P2 reads remain separate ordered events. A session is limited to 1 million events;
queue or event-limit exhaustion atomically stops publication, drains the accepted
prefix and writes an explicit failed terminal. Invalid/order/cycle/write errors
poison the encoder, preserving a rejected partial stream and failed status when
possible. No failed trace can later finalize successfully. Worker failures do
not stop gameplay. Normal end and the SDK `std::exit` fallback disarm producers,
account for bounded in-flight publication, drain and join. Crash/forced kill or
permanent OS I/O stalls cannot promise a completed footer/drain.
Successful state replacement ends this stream with explicit failure, including
loads to future cycles; ordinary recording never silently continues or restarts
without a new complete before-guest startup/baseline envelope.

Output defaults to `<actual configured savestate root>/input-recordings/`.
`MMX6_INPUT_RECORDING_DIR` selects a different absolute owned diagnostics root.
Every session reserves a fresh child directory; existing files are never reused
or overwritten. Windows C: bulk output is refused explicitly; automated work
must set the existing profile/save/cache/temp overrides and choose its private
F:/G: recording root. Unix children use owner-only permissions; Windows inherits
the supplied owned root's ACL. The worker writes `inputs.jsonl`, the three bundle
JSON files, present initial-card copies and `status.json`. These are sensitive
local diagnostics, never source assets or release artifacts.

Changing these trusted source files/package defaults changes the actual image
and declared manifest. Existing execution/title/content/profile checks remain;
no compatibility ID weakening or rollback enablement is introduced. The current
lab contract's explicit source hashes and selected identity must be regenerated
centrally after review, followed by fresh native capture evidence. This observer
adds no deterministic state, snapshot fields or gameplay digest partition.

Helper validation, with TEMP/TMP/cache/output under G: and no title/game launch:

- Clang22.1.8 and GCC15.2.0 at `-O3 -UNDEBUG -ffp-contract=off` execute the actual
  capture TU with read-only engine doubles, real worker/files/cards and six tags.
  Python independently accepts canonical complete outputs, exact startup/card
  artifacts and repeated same-frame events, and rejects failed/empty prefixes and
  online offline-replay attempts.
- Negative fixtures cover queue full/FIFO/wrap and concurrent SPSC ownership,
  malformed order/native ordinal/caller/edge/event kind, C before N, regressed
  cycles, poisoned short writes, disabled/unsupported starts, stale end epoch,
  rematch counters, unilateral mailbox input, invalid stack, real non-directory
  output failure without changing its sentinel, and end racing owner publication.
  A separate child calls real `std::exit` and drains through the registered end
  callback. These are helper observations, not native quit or game qualification.

The standalone fixture is `tests/test_mmx6_input_capture.cpp`, linked with actual
SDK `psx_sha256.c`, runtime includes and threads. Run
`python tools/test_mmx6_input_capture.py --fixture <helper-executable> --output <owned-G-scratch>`.
CTest registration is an integration edit; this lane changes no CMake, paired
runner, comparison ledger, generated output or native coverage result. Future
work still includes ordinary supported offline implementation closure, native
hook/capture confirmation, source-owned offline replay, complete SIO/publication/
resolution provenance and actual replay/core/mod/output comparison.
