# Optional coherent private-effects observations

This read-only extension exposes the current fixed X/P1 + Zero/P2 host-owned
native pools. It changes no simulation state, update order, input source,
counter, snapshot provider or roster policy. Native execution, colors and
retirement still require candidate-specific original-input evidence. No R9,
X/P2 charge, opposite-roster or content-ledger pass follows from these tools.

The native source contract is [COOP_R9_EFFECT_CLOSURE.md](COOP_R9_EFFECT_CLOSURE.md)
and its address/hash record. The original EXE SHA256 is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
That audit maps `80020C40`'s `80020D74` attached-pool call followed by
`80020DC8`'s trail updates, native render order, `+50` parent links, and the
accepted dash marker and finite retirement state machine. No native binary
bytes are distributed here.

## Layout and atomic boundary

The existing allocation remains `2000h` bytes. Base schema1, declared size
`1958h`, offsets and the `+88h` odd/even completion marker stay unchanged.
Existing base readers can read exactly `1958h` and ignore the extension.

| Diagnostic offset | Bytes | Meaning |
| --- | ---: | --- |
| `1A00h` | 4 | LE32 magic `58463658h` (bytes `X6FX`) |
| `1A04h` | 4 | Extension schema1 |
| `1A08h` | 4 | Extension size `220h`, from header through end |
| `1A0Ch` | 4 | Same publication count as base `+4h` |
| `1A10h` | `120h` | Three full private native trail records, stride `60h` |
| `1B30h` | `F0h` | Three full private attached records, stride `50h` |
| `1C20h` | — | End of published data |

The plugin writes header and complete `p2.trails`/`p2.effects` **before** the
existing even completion marker. They come from the host-owned P2 context
after projection has unwound, never a separate native singleton read while
another character is projected. The unused `1958h..1A00h` and
`1C20h..2000h` regions remain untouched. No new diagnostic mailbox is added.

`tools/mmx6_coop_private_effects.py` performs one `read_ram` of exactly
`1C20h` bytes. It parses the base prefix with the existing `parse_diagnostic`,
then verifies extension magic/schema/size/tick. An odd base marker, mismatched
base mirrors or unequal extension tick raises `UnstableObservation`. It does
not combine multiple RPCs or retry them into an apparent coherent sample.
The owner may request a later independent sample after an unfinished one.

An entirely zero extension returns `available=False` and
`unavailable_reason="extension_unavailable"`. This supports base-only frozen
executables, including the old37 candidate; the observer does not infer image
provenance. The owning runner must independently bind the actual expected
executable SHA. Partial/unknown headers or nonzero pools without a header are
errors. Reading only the old prefix is insufficient for this reader.

All native bytes are retained as record `raw_hex`, alongside allocation,
subtype, visibility, phase, current/previous position, camera/facing/priority,
animation fields, compression/assembly/page/CLUT, frame and trail counters.
Allocated trails must have native type11h, the correct index and parent chain
(`PLAYER=800970A0`, then `800972F8`, then `80097358`). Visible records must
have source-compatible flags, phases, bounded live counters, valid native or
owned guest resource pointers and native priority/CLUT. Attached records have
implicit resident-PLAYER ownership, **no `+50` field**; their full stride is
only50h. The unallocated third Falcon slot is allowed. Inactive unknown bytes
are retained without treating them as active resource evidence.

## Reader and reducer API

```python
from mmx6_coop_private_effects import observe_effects, reduce_zero_dash

sample = observe_effects(client, address=actual_diagnostic_address)
report_row = sample.json()
# sample.observation is the existing coop_debug.Observation.
# sample.marker is signed PLAYER+8Ch, sampled in the SAME publication.
```

`reduce_zero_dash(before, active, released, *, mode, input_path,
input_receipts, max_retirement_ticks=32)` consumes parsed observations from
one peer. Run it independently on each peer; separate RPCs are not an atomic
cross-peer observation. `mode` is `local` or `netplay`; required paths are
`offline_native` or `published_host`, respectively. The owning runner controls
its process/session and supplies ordered receipts:

```json
[
  {"path":"offline_native","seat":1,"pressed":8192,"accepted":true,
   "bypasses":[],"before_tick":100,"after_tick":104},
  {"path":"offline_native","seat":1,"pressed":0,"accepted":true,
   "bypasses":[],"before_tick":104,"after_tick":106}
]
```

Seat1 is P2; pressed masks are active-high host/native controller inputs.
This example mask is **not** acceptance evidence or a universal binding.
Receipts must bracket actual input using coherent publication ticks, stay
inside the observation range and not overlap/replay stale input windows.
The runner verifies provenance; the pure reducer cannot authenticate a
receipt supplied by its caller. Mailbox/marker/body writes and unreported
bypasses cannot qualify this case.

The reducer requires a previously clear marker/pool, a newly positive native
`+8Ch` marker during ordinary ground-dash action0Ch or dash-jump action6,
all three native visible phase0 trails, intact source parent/CLUT identity,
and body-owned frame/facing/resources. Button acknowledgment alone fails.
Release history must show a negative marker, active drain phases1 and2,
no positive retrigger, then marker0 with all three visibility/active flags
clear within the bounded observed native-timer window. Missing intermediate
observations leave those checks false; hard-clearing the marker is not a
substitute for a measured drain. Resource leaks cannot be hidden by returning
to idle at the end.

The source's conservative21 bound counts **own native updates** under its
stated no-retrigger/progress assumptions. This reducer's default32 window
counts elapsed observed native timer ticks. It does not equate diagnostic
publications, timer ticks, transport ticks and helper invocations, or claim
once-world cadence. Retain actual rows, input receipts and all failed attempts.

`reduce_effect_menu_freeze(samples, *, resumed=None, minimum_progress=6,
owner=1)` checks a pre-existing visible positive-marker trail window during
the chosen owner's native phase2 menu (owner0=P1, owner1=P2). It requires
at least three ordered publications, diagnostic progress, a frozen native
timer, **exact whole private pools and marker**, and owner resource/CLUT
identity. A resumed phase0 observation must advance both timer and private
effects while retaining resources. A frozen engine or an empty pool cannot
stand in for visible effect retention. Pair this with
`mmx6_coop_personal_menu.reduce_frozen_window` for actual menu state, cursor,
input response and, online, actual network/resolved-tick checks.

`reduce_effect_render_review(row, capture, review)` keeps native visibility,
completed composed capture/hash and explicit artwork review as separate
booleans. `capture` is the existing `capture_present` receipt; a queued ack,
software VRAM capture, empty/C: artifact, unchanged completion sequence or
forged hash fails. Explicit review requires the same capture SHA,
`status="matched_native_reference"`, `owner="Zero/P2"`,
`visible_trail_slots=[0,1,2]`, `cluts=[30733,30734,30735]`, a nonempty native
`reference` description, `retained_colors="matched"`, and `limits=[]`.
This is a reviewer assertion, not automated pixel interpretation. A test
fixture's review record does not qualify artwork. The pool observation and
composed capture are separate RPCs; retain a stable visible window and report
that temporal limit. Packet bytes, actual texture-bank colors and a source
native artwork reference are not embedded in this diagnostic extension.

Dash results always have `status="partial_evidence"`, a check map and limits.
The helpers never assign a gameplay/coverage status. Old37's unavailable
extension cannot satisfy a private-pool check or justify reading live pools
in extra RPCs as a replacement.

## Focused validation

`tests/test_mmx6_coop_diagnostics.c` includes the actual plugin. It verifies
unchanged base layout, full host-pool copying instead of resident pool
borrowing, no P2 mutation, extension tick, both canary gaps, and that every
extension byte is written while the original marker is odd. Deliberately bad
native bytes are copied verbatim; validation belongs to the observer. No
native guest helper is simulated or executed by this publication test.

Run the pure checks from `tools` with a private G: TEMP/TMP and
PYTHONPYCACHEPREFIX:

```text
python -m unittest test_mmx6_coop_private_effects test_coop_debug_protocol
```

The new Python checks cover absent/truncated/partial/torn publications,
invalid native links/fields, stale input, wrong frame resources, missing
drain/retrigger/unretired tails, menu mutation/owner/progress, and independent
capture completion/hash/review. Existing base-reader checks stay applicable.
The current integration's existing CTest for `test_mmx6_coop_diagnostics.c`
continues to cover the actual publisher; register the new Python file as a
separate pure fixture if desired. No CMake, profile, lab contract, SDK or
coverage-ledger edits are part of this lane.

Local focused results:15 new Python tests and23 unchanged base protocol tests
pass. The actual-plugin publisher fixture passes C99/O2 on Windows GCC15.2
and Clang22.1.8, both with and without `PSX_NO_DEBUG_TOOLS`. The updated
fixture built against the unmodified7e74745 publisher fails at the required
extension-byte publication assertion, as expected. Both compilers also compile
the production plugin source against the old a502df3 SDK headers; Clang emits
the existing `CPUState` typedef-redefinition warning from `gpu.h`. These are
publication/codec/reducer checks, not native game or rendered-art evidence.
