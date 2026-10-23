# R26: X6 native consumption boundary and file codec

The native P1 decoder and all six current P2 read sites are source-mapped.
`tools/mmx6_input_recording.py` implements only the strict native-consumption
file codec and startup-artifact validator. A later bounded
[activation slice](COOP_INPUT_CAPTURE_ACTIVATION.md) now connects a native worker
to those boundaries; generated-hook and native capture verification remain
pending. A bounded explicit [offline replay implementation](COOP_NATIVE_REPLAY.md)
now supplies those native consumption boundaries; **native replay and R26 remain
unverified.** A syntactically valid file is not evidence
that these hooks ran, that exported settings were complete, or that replay works.

The [source manifest](COOP_INPUT_RECORDING_AUDIT.json) retains 33 frozen Git
blobs, original EXE identity, six independently hashed native spans and the
direct-call scan scope. No game binary, card or snapshot is committed. The
audited X6 co-op blob `dcf35129764cf75f8cceb653d9e59e79c4595154` was unchanged
between frozen `92ba399` and observed main `fd567309`.

## Original P1 acceptance

For USA v1.1 EXE SHA-256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`,
the complete native function is `80012A34..80012C50` inclusive. Its 544 bytes
hash to `8ca7b0e60a42934a40186be927ca9ec2683f2ace00b37edd0b2f9a293ef379fa`.
To reproduce any span hash, read the original EXE at
`2048 + (guest_address - 0x80010000)` for the manifest's exact byte count.

Native setup at `800126DC..800126F4` passes `800CF920`/`800CF870` as a0/a1
to `8006AC64`, then calls `8006AB54`. The decoder reads first PadData at
`800CF920`: absent status `FF` yields
neutral; controller-ID high nibbles `40`, `70`, `50` enter decoding. Bytes2/3
are inverted and byte-swapped into native active-high buttons. The `50` path
has additional native remapping; do not replace it with a generic host bitset.
Opposing native direction pairs `A000`/`5000` select the previously stored
previous value. It then writes:

| Native stores | Meaning |
| --- | --- |
| `80012B24 -> 800C456C` | current first-port native buttons |
| `80012B34 -> 800C456E` | old current, now previous |
| `80012B40 -> 800C4570` | `(current XOR previous) AND current`, pressed edges |
| `80012C2C/30/40 -> 800C4758/5A/5C` | corresponding triple for second-port PadData at `800CF870` |

The second decoded port is not X6 co-op's extra P2 input source. Keep both
native triples because the original routine owns both. Do not synthesize P1
from a fresh `sio_get_pad_buttons_slot(0)` call: that may read a newer host
publication than the native serial transaction consumed.

The aligned loaded-EXE direct J/JAL scan finds three `0C004A8D` calls:

| Call instruction | Return PC | Context |
| --- | --- | --- |
| `80012218` | `80012220` | main driver `800120A0`; loop begins at `800120FC` |
| `8001A82C` | `8001A834` | native wait loop; immediately tests decoded pressed edges |
| `8001AB10` | `8001AB18` | another native wait loop; immediately tests decoded pressed edges |

There are no aligned literal `80012A34` pointer words in that EXE payload.
This is not a claim that overlays/indirect calls have all been exercised.
Schema1 rejects an unknown caller so a newly discovered path cannot silently
enter a supposedly complete trace. The main driver increments `80097420` at
`80012228..80012238`, after decoding. Wait-loop calls need not increment it.
Neither that counter nor gameplay timer `PLAY+90` is a unique input clock.

The preferred future observer is an instruction callback at **`80012C44`**,
with exact expected word **`8FBF0010`** (`lw ra,16(sp)`). Both triples and
the `80013064..80013124` pad-configuration tail have completed. The remaining
epilogue restores RA/stack and returns without further pad writes. The original
caller is the saved guest word at **`sp+16`**, not live `$ra` (the inner JAL
has made that `80012C44`). Validate stack access and the caller before enqueue.

SDK792 `PSXModInstruction` callbacks already observe exact configured
instructions without guest reentry, redirecting PC or adding guest cycles.
Activation would add this address to `game.toml`'s `mod_instruction_sites` and
register the exact instruction under the offline diagnostics ID and actual
fixed-profile plugin ID `mmx6.local-coop.prototype`. No such edit is made here.
This avoids a new nested guest call simply to observe an existing original
call. Any alternate function wrapper must execute the original exactly once,
preserve its return effects, and handle abandoned callbacks explicitly.

## Extra P2 reads and low-latency ordering

Frozen X4 `50593bca` installs a function filter at **its** `80012328` under
both `mmx4.diagnostics` and fixed-profile `mmx4.coop`. `inputs` calls the
original once, then writes `N`; `mmx4_coop_input` passes active-low standard
buttons to `mmx4_diagnostics_resolve_input` before its native byte swap. That
resolver writes/reads `C sequence seat buttons` for every extra actual read.
`inside` there is the recorder's guard: diagnostic sampling itself must not
manufacture additional `C` events. Replay checks exact C sequence and seat;
N checks sequence/frame/native state before replacing decoded input. Its
offline launcher explicitly refuses network recordings and incomplete final
native intervals. X5 follows this design with its own `8001255C` and adds
developer-operation records; none of those addresses or passes transfer.

X6 `p2_input` returns **active-high standard PSX bits**, before callers byte-swap
for native input. Record its actual final normal read once, with these tags:

| Tag | Frozen X6 source line | Why the read matters |
| --- | --- | --- |
| `stage` | 1033 | Start ownership and held Select history, including paused UI |
| `controller-scene` | 1137 | keep Select latch current during owned scenes |
| `controller-inactive` | 1141 | inactive/non-gameplay held-button history |
| `controller-blocked` | 1147 | native transition/menu gate held-button history |
| `controller-player` | 1161 | actual joining/leaving/player update input |
| `interaction` | 771 | P2-owned native interaction projection |

A narrow activation can pass one explicit tag into each existing call; it
must not invoke `p2_input` to fill an N row. Co-op's `inside` is frequently set
at real P2 reads, so copying it as the recorder's global skip guard would lose
events. Presentation-only replay must remain excluded by its actual scope,
not by suppressing legitimate gameplay projection. A mailbox override or
unilateral SIO/environment override must mark the original-input capture
unsupported/failed; it must not be relabelled normal input.

SDK792 `sio.c:1409..1432` copies live `pad_buttons` into the persistent normal
`42` response. `1663..1671` subsequently shifts those latched response bytes.
By contrast, `sio_get_pad_buttons_slot` at1203 returns the current live value.
The main loop may sample early and again after pacing. Therefore retain every
N boundary and ordered C read, including identical buttons and equal frame
numbers. Do not record every host poll as consumed, deduplicate by world time,
disable low-latency sampling, or substitute a sampled proposal for N's native
decoded result.

Copying serial-buffer bytes at decoder entry is not proven to equal the bytes
later read across guest IRQ/event boundaries. The codec deliberately contains
no supposedly consumed raw-serial-header field. A complete serial transaction
observer/publication history remains separate SDK work; there is no existing
public callback for it. The native trace does not by itself reconstruct SIO's
full protocol state or authorize a whole-machine replay claim.

## Concrete independent codec slice

Contract `mmx6.native-consumption.v1` uses canonical ASCII JSONL, one bounded
record per line, with duplicate/unknown fields rejected. There is no runtime
path discovery, thread, environment switch, controller source or replay engine.
The Python encoder writes an already-owned binary output. Its eventual native
counterpart must use the bounded POD queue/background writer described in the
parent audit; doing Python/file I/O on the simulation thread is not proposed.

1. One `header` identifies schema1/contract and exact startup envelope.
2. Every `N` or `C` has contiguous global `order`, nondecreasing uint64 guest
   `cycles`, and offline `sim_tick:null` or an online uint32 tick annotation.
   An N has contiguous `native`, native frame, saved original return PC and
   both decoded `[current,previous,pressed]` triples. C has the most recent N
   interval, seat1, one exact consumer tag and uint16 unswapped active-high
   buttons. Repeated reads are retained. No C is valid before the first N.
3. Exactly one `end` declares N/C/global counts, SHA-256 of all exact header and
   event bytes, and `failure:null` or the first bounded failure reason. Extra
   bytes, missing newline/terminal, wrong digest/counts or an empty capture
   fail validation. A writer validation/short-write error poisons that encoder;
   it cannot resume or later emit a successful footer.

`end` means the stream finalized, not that an online tick completed/resolved,
that input provenance is authentic, or that replay succeeded. File hashes
detect byte changes; they are not signatures. The streaming validator bounds
each line to16KiB and defaults to10 million events without retaining the whole
trace. A finalized failed trace can be inspected explicitly, but cannot pass
the offline-replay preflight. A truncated tail always fails strict validation;
future recovery must expose an explicit bounded prefix rather than silently
calling it complete.

The startup envelope binds actual image SHA, compiled declared-manifest SHA,
execution ID, exact resolved-settings bundle SHA, original content-identity
bundle SHA, simulation-contract bundle SHA, offline/netplay mode, selected
profile ID/revision/session SHA where applicable, both initial card slots, and
an optional full restored-state baseline. `null` card means absent; a present
card is exactly128KiB plus SHA. `null` baseline means cold boot. A post-restore
segment requires a complete ready current-build machine plus X6 host snapshot,
never guest RAM alone.

`validate_startup_artifacts` independently checks supplied exported settings,
raw cards/absence and baseline bytes. It opens no live card and never imports,
rebinds or flushes one. The activation exporter still needs to gather those
bytes **after actual settings/cards/profile resolution and before guest0**,
under the existing validated private F:/G: root. The settings/content/contract
bundle exporters must cover all fields listed in the parent audit; hashing an
incomplete bundle cannot make it complete. No new environment/CLI setting or
default directory is introduced by this slice.

Offline-replay preflight requires an independently observed expected envelope
and rejects any mismatch, every network trace and declared capture failure.
It only validates data: actual playback, native consumer-by-consumer comparison,
native-state and full core/mod checks, output comparison, source ownership and
release, publication/completion/resolution records, default activation and
disk/queue/restore behavior remain unimplemented. Backward file/snapshot
compatibility is not promised.

Run the pure suite with Python `tools/test_mmx6_input_recording.py -v`, with
TEMP/TMP/PYTHONPYCACHEPREFIX redirected to the task's G: scratch. Twenty tests
cover the repeated same-frame scenario, every byte truncation, missing/duplicate/
swapped events, counter/caller/consumer/cycle errors, changed build/settings/
content/profile/cards/baseline identity, actual exported-byte mismatches, network
refusal, terminal/hash failures, bounds and poisoned short-write handling.
There are no game launches or inherited replay results.
