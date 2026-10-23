# R26 accepted-input recording and replay: source audit

X6 has no equivalent of the frozen X4/X5 default playtest recorder in the
audited source. Its diagnostic RAM, input acknowledgments, screenshots and
core/mod CRC logs cannot reconstruct both accepted pad streams and their
starting state. **R26 remains unverified.** The follow-up adds an independent
native-consumption file codec and pure validation tests; it neither installs a
recorder nor qualifies replay. The [native boundary/format contract](COOP_INPUT_CONSUMPTION_CONTRACT.md)
resolves the previously unmapped decoder and lists the remaining activation work.

The accompanying [source manifest](COOP_INPUT_RECORDING_AUDIT.json) pins each
inspected Git blob and SHA-256: X4 `50593bca772b600de6911cbfecd40b0f08721147`,
X5 `9ed460e7b7e60769fa12bcab74e228ae19796214`, X6 `92ba399`, SDK `792469321`.
Objects were read with `git show`, not from the X4/X5 worktrees' current files.
No X4/X5 result, guest address, body size or format compatibility transfers.

## What the frozen implementations actually do

Both `mods/preloaded/packages/mmx{4,5}.diagnostics/1.0.0/manifest.toml`
declare `default_enabled = true`. Their executable's fixed co-op profile also
registers the diagnostic native-input hook under the co-op package ID. This
matters because that profile does not activate an arbitrary offline mod plan.

`mmx4_diagnostics.cpp:341–395` wraps the original native input routine
`80012328`, then samples its decoded pad words and both effective pads. `N`
rows carry a monotonically ordered input number, native frame, decoded input
and selected native/host-player state. Separate `C sequence seat buttons`
events record the actual order of extra co-op pad reads
(`mmx4_diagnostics.cpp:439–450`). This is more precise than one screenshot or
one host poll per displayed frame. X5 keeps this architecture and adds `D`
developer-operation events; its replay launcher rejects those as input-only
reproductions. Their bounded native state FNV is a useful divergence check,
not the full framework core/mod digest.

The writers copy owned POD state into a 4096-entry single-producer queue;
the background thread performs hashing/formatting/file I/O, flushes dirty data
at 100 ms intervals, and drains on normal close. Queue full, I/O failure or
worker-start failure stops capture and reports an error rather than silently
dropping rows or blocking each input. Mode transitions are a separate ordered
stream. Copy this ownership/error design, not X4's addresses or state slices.

At session start, the implementations retain execution ID, portable mod-plan
fingerprint, diagnostic build ID, effective play/camera/campaign mode, settings,
mod choices and raw initial cards or explicit absence markers. Restore/rewind
creates an offline segment with a full `baseline.pst`; online loads are marked
in the stream. Disabled offline Diagnostics must not create a folder through
the snapshot-loaded observer. Replay checks header identity and sequence,
frame and native-state hash, rejects a wrong baseline, and releases its owned
controller sources when stopped. It is explicitly requested, not default.
X5 hooks its own native routine `8001255C`; that is not an X6 hook candidate.

Crucially, both frozen replay launchers **reject network recordings for offline
replay**. They trim an incomplete final native interval rather than asserting
that interrupted output is complete. X5 also rejects `D` fixture records. The
launcher uses private cards/settings/output; its ability to launch is not a
new-build provenance guarantee. X6 should strengthen binding with its actual
image SHA, declared manifest and current host profile, and make the retained
complete prefix versus unfinished tail explicit.

## Current acceptance points and the concrete integration seam

| Layer | Frozen SDK/X6 source | Consequence |
| --- | --- | --- |
| Offline resolution | `main.cpp:7091–7128`, `pad_external_input.c:64–89` | Physical capture, source, title transform, presentation/guard and mouse policy resolve before the pad reaches SIO. Log the result, not SDL keys or a source callback's proposed buttons. |
| Shared normal apply | `main.cpp:6352–6357`, `psx_pad_apply.c:5–22` | `apply_pad_slot_to_sio` and online `apply_pad_slot` both call `psx_pad_apply_to_sio`. This is the narrow shared publication seam for final buttons/sticks and requested pad type. A new read-only observer here can copy the published value without changing the pipeline. It is not an existing recorder callback. |
| Offline resampling | `main.cpp:8526–8556`, `8867–8886` | Offline input can be sampled early and again after pacing. A VBlank-only logger misses publications; recording must not disable low-latency resampling to hide that gap. |
| Online local proposal | `main.cpp:6831–6877`, `psx_netplay.c:3614–3723` | Host input is captured, transformed, normalized and latched by `psx_netplay_stage_local`. Repeated live samples after the latch are not newly accepted input. This is a provenance/local-publish stream, not both peers' consumed input. |
| Online published pair | `psx_netplay.c:2626–2642`, `2656–2669` | `host_publish(tick, by_slot, slots)` decodes and applies the admitted pair. `np_publish_hist_sio` handles history/resimulation. `note_sim_pad` stamps exact per-seat current-simulation-tick rows; `psx_netplay_sim_pad` exposes them read-only while guest code runs. |
| Completed/resolved tick | `psx_netplay.c:5643–5711` | `finish_frame` records the tick that actually ran before advancing it. `resolved_through` is a separate confirmation frontier. A published/admitted row is not thereby a completed, peer-confirmed replay interval. |
| Native extra partner reads | `mmx6_coop_plugin.c:686–698`, `1030–1101`, `1131–1175` | X6 reads slot1 directly in `p2_input`, including pause/lifecycle gates outside a normal world pass. It can also use an offline development mailbox. Record original accepted pad consumption in these paths; never present mailbox overrides as normal recording evidence. |

The proposed implementation is a **default-enabled title recorder backed by
small read-only SDK observer seams**, with two related streams:

1. Copy normal final pad publications at the shared apply seam, tagged with
   session/restore epoch, event order, guest cycle, offline boundary or online
   simulation/wire tick, seat-to-port mapping and provenance. Preserve full pad
   state, connection/config capability and effective versus requested type.
   Type changes are deferred to an idle SIO bus; the requested type alone does
   not describe what a serial poll consumed. Dynamic connection changes need
   explicit events too.
2. Copy native accepted reads: original serial-pad poll latch state for P1 and
   X6's extra `p2_input` reads for P2, with ordered consumer identity. Add a
   title boundary/native-state check without projecting a new actor or calling
   guest code. This is the X6 analogue of X4/X5 `N` plus `C`, not a port of
   their hook address. The follow-up maps native decoder `80012A34` and a
   read-only post-decode instruction boundary at `80012C44`. It does not install
   them or map a complete public serial transaction observer. No suitable
   public observer callback currently supplies this complete event contract.

The shared apply function is concrete, but not sufficient alone: legacy
`apply_input_override_to_sio`, port2 overrides and `env_pad_hold_apply` can
write SIO outside it. An authoritative recording must either observe these
through explicit provenance events or mark that capture unsupported/fixture
contaminated; it must not silently call it original-input replay. The normal
published host layer used by the paired tools is different: it enters capture
before the normal netplay latch/publish/transport path. Acknowledging that
request alone still proves no accepted simulation input.

For current X6 delay mode, combine the complete published pair with the
completion event, then finalize a replayable prefix only below the resolved
frontier. Re-admits, same-tick republishes and state loads require epoch/order
tracking; deduplicating merely by unchanged button values loses held duration.
Paused menus still accept input while the native world timer is frozen, so
that timer cannot be the recorder clock. Future rollback would need explicit
authoritative replacement/commit handling. X6 rollback remains disabled;
do not enable it for this feature or label predicted history resolved.

No observer changes a pad, filters buttons, advances a clock, performs a guest
call, writes a mailbox/RAM success field or invokes debug controls. All guest
and host-owned state copies occur on the emulation thread. Only owned immutable
event copies cross to the file worker. Skip presentation-only render replay;
do not retain process pointers or native callback stacks. Hook activation must
cover both the default offline diagnostic package and the fixed online co-op
profile; an inactive offline diagnostics observer must remain inactive after
state load, matching the frozen F70 fix.

## Exact starting state and files

Capture the starting envelope **after configuration/cards/profile resolution,
before guest cycle0 or the first recorded accepted input**, not when healthy
co-op enrollment finally occurs. Retain actual executable SHA-256, canonical
declared manifest/header identity, execution/implementation IDs, effective mod
plan and options, actual BIOS/disc identities, boot/loader policies, controller
mode/mapping, initial effective game/roster/camera mode, relevant environment
overrides, renderer/retained-bank policy and chosen FP/overlay/backend contract.
Store settings files plus resolved values: a saved preference may not be the
effective runtime setting. A version string or source-tree HEAD is insufficient.

Export each present card's exact initial bytes through the memory-card API,
hash them, and retain explicit absent-slot markers. Read/export only: never
flush, rename or overwrite the owner's original cards to create a recording.
Include each online peer's actual initial-card/baseline identity and preserve
the authoritative startup-state transfer relationship rather than guessing
that both peers independently loaded the same files. Do not distribute BIOS,
disc images, original executables or private credentials with the trace.

Normal cold boot can use its exact configuration/cards/accepted boot inputs.
A segment that starts after a state load/rewind needs the complete current-build
machine **and** X6 host provider snapshot at a ready boundary, including retained
resource reconstruction. Guest RAM alone is inadequate. If readiness/capture
cannot be obtained, report that segment unreplayable; do not fabricate a baseline.
Older snapshots/recording schemas may be rejected without migration. The SDK's
`mod_session_baseline.h` contains only selected host presentation scalars; it is
not a complete replay baseline.

X4/X5 use executable-relative `saves/diagnostics/session-<stamp>` (AppImage
uses the outer image location), make the real location visible in the OSD/log,
and capture starting saves there. X6 should use one fresh session directory
beneath the already validated private F:/G: data/saves root, with collision-safe
creation, explicit readable location and success/failure/finalization metadata.
Do not silently fall back to AppData or C: if that root is missing/unwritable.
The current X6 staging environment already isolates `TEMP`, `TMP`,
`LOCALAPPDATA`, `APPDATA`, `XDG_CACHE_HOME`, resident and overlay/capture paths
(`prepare_mmx6_coop_playtest.py:151–162`). A future recorder must bind its own
output root to that same contract; no new environment variable or CLI is
implemented by this audit. Replays need fresh private cards/settings/output,
all applicable caches/logs/temp redirected off C:, and muted automated output.

## Failure, replay and validation requirements

Keep a bounded single-producer/background-writer design. Startup path/card
export failure creates an explicit failed capture; queue saturation or disk
failure stops recording without blocking or mutating the game. Flush periodically
even while gameplay is paused, drain normal shutdown, and retain declared row
counts, rolling stream/hash checks and a terminal completeness marker. Crashes,
unresolved tails and missing controller-read events remain incomplete; validating
an explicitly bounded complete prefix is not a full-session replay pass. Surface
failure visibly and once in logs, preserve the first reason and do not silently
resume into the same stream after a gap.

Replay is an explicit startup operation. Existing offline controller-source APIs
are reusable only within their actual resolution/gating contract: source
buttons merge with physical input, other transforms/policies may still act,
and current SDK excludes ordinary sources in netplay/resimulation. Its normal
headless sampler neutralizes both pads; the explicit host-layer exception
resolves P1 and still neutralizes P2 (`main.cpp:7154–7187`). That exception does
not establish two-pad headless replay support.
Use isolated neutral physical sources and a verified compatible replay path;
do not inherit X4's older headless comments as proof for SDK792. A read-only
recorder never claims input ownership. Replay ownership must be installed before
the session and released/reset deterministically on completion/error/rematch.

An online recording cannot be replayed by putting both pads into one peer's
debug/SIO/mailbox overrides. A future paired replayer needs a trusted
tick-indexed input-source seam at each peer's real local publication callback
(`host_sample_local`), followed by the unchanged transport/latch/admission path,
with local wire rows and resolved accepted pair rows both retained. Both peers
must agree on replay mode/start identity before guest execution. Use a fresh
session nonce: record old/new selected host identities, rather than expecting
the nonce-bound selected SHA to stay equal across sessions. Until that exists,
online capture is inspectable data and paired replay remains unsupported,
as it is in the frozen X4/X5 launchers. Matching their bounded scope means
default local/online capture plus strict offline replay and an explicit refusal
to replay network traces offline; it does not require inventing a paired
replayer solely to claim reference parity. Any broader replay claim needs its
own implementation and evidence.

Required evidence before R26 can pass:

- Actual default-enabled offline **and** paired sessions produce discoverable,
  finalized files with both accepted pads, initial settings/cards and correct
  effective mode. Include boot menus, P2 personal pause, held/released inputs,
  voluntary absence/rejoin and multiple sessions; disabled mode must not spawn
  restore-only folders.
- Replay a complete original-input offline interval on the exact candidate in a
  fresh private process, checking consumer order, input sequence, native state,
  full core/mod digests at defined completed boundaries and composed outputs.
  Physical-device and published-host routes need separate retained evidence.
- Demonstrate rejection of changed image/manifest/profile/settings/cards or
  baseline, malformed/duplicate/missing/truncated rows, wrong consumer order,
  fixture contamination and divergence. Exercise queue-full, disk/open/flush
  failure and interrupted shutdown without hidden drops or simulation changes.
- Verify that network traces are clearly labelled and rejected by the offline
  replayer, matching the frozen reference scope. Keep optional future paired
  replay unclaimed until its real per-peer publication-source path is qualified.
  A recorder file, engine JSONL, matching diagnostic FNV or matching CRC
  breadcrumbs alone establishes none of the required capture/replay behavior.

The existing `PSX_RB_SELFCHECK` is a separate opt-in, offline in-memory
snapshot/resimulation comparator. Its applied-pad note/replay and digest code
are useful implementation references, but it deliberately locks boundary input
and can synthesize mash inputs. It is neither the default persistent user
recorder nor a justification for changing live timing to make R26 pass.
