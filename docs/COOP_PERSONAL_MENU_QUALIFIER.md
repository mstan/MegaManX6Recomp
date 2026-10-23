# Native personal-menu helper contract

The owned paired qualifier exposes this case as `--personal-menu-smoke` and
requires `--require-state-crc`, native gameplay and the default Seamless Loading
path. It runs the P2/Zero case after the existing healthy intro checks, before
optional enemy/lifecycle routes, and then retains a resolved core/mod CRC phase
after the case's paused/resumed composed captures. Host-profile requirements
remain separately optional. Combined routes still enforce their own native
preconditions rather than repositioning or resetting guest state.

The paired adapter uses only the matching peer's ownership-checked published
`host_input` sampler. Holds and neutral release intervals wait on actual
transport/resolved ticks because Start can freeze the world mid-hold.
`native_advance` separately uses the native world timer during gameplay.
It creates the private `personal-menu` capture directory before calling the
shared helper. The helper's automated status and pending artwork review remain
in the retained report; a passing automated runner does not mark R8 passed.

`tools/mmx6_coop_personal_menu.py` provides
`personal_menu_smoke(ctx, owner=1)` for an owning offline or paired runner.
It has no process launcher, CLI, fixture setup or ledger updates. No native
runtime result is claimed by this module or its pure reducer tests. The caller
must retain its complete report on success or exception and perform composed
artwork review separately.

The case begins with two healthy native intro heroes and no menu, scene or
mailbox. The selected owner's original Start opens the native menu. It checks
the diagnostic owner, native pause phase and **first byte1** at `800CF814`.
It retains the second byte without requiring1: the existing native pause
fixture observes `01/00` on initial entry and `01/01` after tank healing.
There are no tank/resource grants in this helper.

The other hero's Start must not resume the owner's menu; its direction input
must not change cursor `800CF824`. The owner must actually change that cursor,
then restore its original value. The default direction pair is Right/Left;
`cursor_buttons=(change,restore)` can supply another native direction pair for
an authored menu layout. An unavailable selection causes a retained failure,
not a fabricated cursor change or pass from pause phase alone.

Every frozen window retains at least four observations. All must preserve
the original menu-entry native world timer, even across intervening Start and
cursor inputs. Diagnostic publications must advance, rejecting an engine that
has stopped entirely. Online, both actual transport ticks and resolved ticks
must advance with active/two-player/non-rollback/no-desync statuses. These
progress checks do not prove exactly-once world cadence or replace core/mod
CRC evidence supplied by a paired runner.

The helper retains both heroes' HP, weapon and all nine ammo fields before,
during and after the menu. Only the owner can resume. Afterwards the actual
world timer must advance, an original Right input must move that hero while
the other stays fixed, and original Square must produce a native attack state.
Zero's default reducer requires a new, forward-publication action48 observation
with the other hero's X unchanged. Acknowledgments, an already active attack,
an idle endpoint or another character's action cannot satisfy it.

## Runner context

| Key | Contract |
| --- | --- |
| `mode` | `local` for one owned process, or `netplay` for two owned peers. |
| `input_path` | `offline_native` locally; **`published_host` online**. Direct online SIO, mailbox and RAM adapters are rejected. |
| `clients` | One or two live debug clients exposing bounded `read(address,length)`. The helper reads only native state and coherent diagnostics. |
| `both(fn)` | Invoke `fn(peer_index)` for every client and return results in peer order; preserve errors. The one-process adapter can use a simple list comprehension. |
| `debug` | Current shared `coop_debug` module, providing `observe(client).json()` and `capture_present(client,path)`. Use its completed GL present capture, not canonical software VRAM screenshots. |
| `report` | Parent report dictionary; the case is appended to `personal_menu` before native controls so partial evidence survives exceptions. |
| `output` | Fresh private evidence directory off C:. Existing per-owner capture files are rejected before controls. |
| `hold(seat,bits,frames,label)` | Original accepted pad input, using pressed-bit masks. Verify listener ownership before control; hold for the requested scheduler/transport interval and release to neutral, including on error. Online route only through the matching peer's published host sampler. |
| `transport_window(frames)` | Bounded scheduler/transport progress while the native world is paused. Never wait for the frozen native world timer here. Offline may wait for diagnostic publications; online uses transport ticks. |
| `native_advance(frames,label)` | Bounded progress measured by the native world timer, used only during gameplay. |
| `network()` | Required online: validate and return the two actual `netplay_status` replies, preserving raw ticks/resolved watermarks. Not called offline. |
| `attack_reducer(before,history,owner)` | Optional native evidence reducer returning an observed row or `None`. Required for a P1-owned case: X's buster action is not guessed from Zero's action48 contract. Retain its source identity with the runner. |

Existing paired callbacks already have this general shape, but this module
does not edit that runner or import a worker's stale copy. The offline runner
may adapt its owned `control`/client callbacks to the same interface. The
adapter is responsible for accepted input, endpoint/process ownership,
same-build identity, safe cleanup, private paths and preserving source cards.
All background execution must remain hidden and muted.

## Results and review

The helper records native reads, original input events, frozen intervals,
resources, attack evidence and completed composed captures before and after
resume. A completed automated case returns
`automated_checks_passed_artwork_review_pending`; artwork stays `pending`.
It never marks R8 or another ledger row passed. Review the owner-specific menu
portrait/palette/layout, personal resources, restored gameplay heroes/HUD and
the exact candidate/build/settings before using a receipt for qualification.

The pure tests cover transient wrong ownership/resume, cursor leakage,
world-clock advancement between otherwise frozen intervals, stopped engines,
stalled resolution, desync, resource leakage, publication wrap, stale/preexisting
attack observations and forbidden online input adapters. They establish parser
and reducer behavior only. Actual accepted input and composed artwork require
fresh local and paired runtime evidence from the owning runner.

## Standalone owned offline runner

`tools/qualify_mmx6_coop_personal_menu.py` adapts this case through
`qualify_mmx6_coop_baseline.run(..., exercise=...)`. This implementation has
only CLI/input-adapter unit evidence; it has not launched a native case.

Stage a new private candidate from a selected immutable build:

```powershell
python tools/qualify_mmx6_coop_personal_menu.py --build G:/path/to/frozen-build `
  --source F:/path/to/game-source --disc G:/path/to/original-disc.cue `
  --output G:/path/to/new-private-menu-case --expected-exe-sha256 <64-lowercase-hex>
```

Or use an already prepared, unused automated profile:

```powershell
python tools/qualify_mmx6_coop_personal_menu.py --candidate G:/path/to/fresh-prepared-profile `
  --expected-exe-sha256 <64-lowercase-hex> --port 24896
```

The modes are mutually exclusive. Build staging requires source/disc/output;
candidate mode forbids those staging arguments. The executable must match the
explicit hash and preparation receipt. The runner rejects prior qualification
files, a reused baseline directory, cards and populated private saves/temp/
cache/data/appdata/resident directories. Shared preparation validates the
private F:/G: profile paths, hidden/muted runtime environment and source
observation artifacts. Preparation does not establish compilation provenance.
There is no source-card option and no cache/save copy.

The adapter first clears both native ports and waits for two healthy action2
heroes with stable coordinates across advancing publications. It does not
assume the baseline's preceding jump has finished. Each accepted hold uses
`press(port=seat+1, buttons=0xFFFF^pressed_bits, frames=N)`, paces by coherent
diagnostic publication progress, attempts port-specific neutral clear even
on failure, then leaves a neutral publication interval. Gameplay-only advance
uses the native world timer. Reads and composed capture RPCs also pass through
the baseline's listener-PID check; the helper receives a read/capture-only
client view. No online input route is provided by this offline adapter.

Each candidate retains runner/helper source snapshots and hashes, shared-tool
hashes, adapter publications/native windows, original input events, partial
case errors, personal resources and completed composed captures. The original
`baseline/qualification.json` remains untouched, with its original status and
hash linked from the top-level `qualification.json`. A failed helper is
converted to the baseline's handled error type so cleanup and the original
failed report survive; it is never relabeled as a passed run. An automated
success is recorded separately as
`automated_checks_passed_artwork_review_pending`; exit0 only indicates those
automated checks completed. Artwork remains pending and the ledger remains
unverified. The owning reviewer must inspect the composed menu/gameplay
captures before treating the receipt as qualification.

The [frozen native baseline](COOP_PERSONAL_MENU_BASELINE.md) now supplies that
review for R8 on executable37cdc487, independently local and paired. The raw
automated/artwork-pending receipts remain unchanged. This does not transfer
qualification to another artifact, roster, equipment set or restoration flow.
