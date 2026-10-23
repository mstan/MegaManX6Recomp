# Native world execution tracing in the bounded intro case

`tools/qualify_mmx6_world_trace.py` runs the existing original-input R13 case on
the frozen v11 executable, SHA-256
`43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7`.
It adds host observation controls only: no new game binary, guest RAM writes,
fixture/success flags, state loading or source cards. The owned hidden/muted
profile, caches, trace pages and logs stay on G:. It uses port24895 and reuses
the baseline runner's native boot, process/listener ownership and cleanup.
Here the measured world routine is specifically native enemy-pool update
`8002000C`; other object/support subsystems require their own coverage.

## Coverage audit

The source audit used the generated X6 dispatch and compiled functions plus
the modern SDK runtime compiled for the selected candidate. Trace source paths
below name that SDK's `runtime/` and `recompiler/` directories; current source
observations remain distinct from exact executable identity.

| Observation | Source behavior and limitation |
| --- | --- |
| Filtered `fntrace` | `full_function_emitter.cpp` emits `fntrace_record(cpu,addr)` at each `psx_dispatch_impl` iteration. This records entries **and CPS continuation PCs**. It is not a function-body counter by itself. |
| World true entry | Generated `func_8002000C` skips its entry log when `cpu->pc` selects a continuation. Only its initial entry reaches `debug_server_log_call_entry(8002000C)`. An exact virtual `fn_filter` range captures this independent prologue ring. |
| Direct handoff coverage | `dirty_ram_interp.c::interp_enter_compiled` calls the game compiled dispatcher directly, bypassing `fntrace`. It still reaches the generated true-entry logger. Comparing both counters detects such a discrepancy for this static world function. |
| Interpreter local calls | Dirty overlay JAL/JALR/local chaining can bypass `psx_dispatch` entirely. Therefore zero `fntrace` rows at alive body `800EAC8C` cannot prove missing AI. `dirty_flow_log` separately records those local transfers. |
| Wrapper recursion | Co-op replaces stage `8001E9EC` and calls its original through `guest()`. The ordinary live two-player case expects outer and nested stage dispatches. Treating both as full world updates would overcount. |
| Native driver cycle | Clean native driver `80020C40` calls the attack pool with return `80020C70`, then world `8002000C` with return `80020C80`. The trace partitions complete driver-entry-to-next-driver-entry intervals, accounting for exactly one world and its actual return marker. |
| Per-player attacks | The co-op controller separately invokes `8002012C` for P2. Its count belongs to the two player attack pools and must not be added to the shared enemy-world count. |
| Frame tag | Trace `frame` comes from SDK `s_frame_count`, advanced by `debug_server_record_frame` in simulated VBlank handling. Diagnostic publication counts/native timers only pace input and witness actor state; they do not establish the execution count. |

The exact virtual prologue range `8002000C..80020010` excludes the dispatch
shadow logger's physical-address records. Its direct-entry totals are checked
against the dumped row count and `direct_filtered`, with `direct_no_cpu=0`.
The observed world code bytes must equal the original PS-X EXE span before and
after the route. No universal claim about patched/interpreted world code or
other stages follows from this compiled-world case.

## Complete observation windows

The dispatcher is armed for24 exact targets, within the existing32-target
limit: stage entry/continuation, native driver boundaries, world entry and its
known continuations, per-player attack-pool entry, camera driver, type1 handler
`800EAFB0` and alive body `800EAC8C`. The selected ring is cleared only after
arming. Every subsequent unfiltered selected-sequence page must contain exactly
its declared contiguous sequence range. Eviction, missing rows, unexpected
targets and truncated responses reject the window. Raw pages retain sequence,
frame, target, caller RA, stack pointer and arguments.

The independent prologue ring closes explicitly with `fn_disable` before its
last dump. Analysis intersects the two rings' frame ranges and excludes both
boundary frames. Every interior frame is listed, including zero/extra counts;
the tool never selects only frames that happened to match. Complete native
driver cycles are additionally listed by dispatch sequence bounds.

Dirty-flow snapshots retain the full ring watermark/availability plus every
matching alive-body transfer. Snapshots must overlap throughout the live-actor
window, or the body proof is rejected. The first frame after initialized actor
evidence and the last frame before original Square define its interior. Each
must contain exactly one handler and one local alive-body entry with argument
`a0=8008EF48`, the slot already bound to native record25. This measures a real
initialized actor rather than an empty pool. Any pre-actor coverage gaps are
explicitly retained and excluded from this narrower body window.

Four focused accounting fixtures distinguish continuations from true world
entries, preserve separate two-player attack counts, and reject duplicated
world execution, missing prologue/body coverage, wrong actor pointers,
sequence gaps, eviction and truncation. These are evidence-parser tests, not
new game mutations or a substitute for runtime measurements.

## Measured result and retained route failure

Five independent counter checks passed on the corrected bounded trace run:

| Window | Complete observations | Count |
| --- | ---: | --- |
| Simulated VBlank frames2807..3167 | 361 frames | World dispatch1, independent world prologue1, driver1, world return1 in every frame; stage wrapper2 and player attack pool2 were separate. |
| Complete native driver cycles | 364 cycles | World1/return1, stage wrapper2 and attack pool2 in every cycle. Every sequence boundary is retained. |
| Bound phase1 actor frames2924..3006 | 83 frames | Exactly one type1 handler entry and one local alive-body entry for slot `8008EF48` in every interior frame. |

The selected trace retains4599 dispatcher rows,363 independent world prologue
rows and108 matching local alive-body rows across24 raw pages. No dirty-flow
coverage eviction occurred. The prologue total, `direct_filtered` and dumped
row count all equal363, with `direct_no_cpu=0`. Original world bytes matched
before and after. The complete per-frame records/cycles remain in the raw
report; the compact receipt losslessly compresses identical frame counts and
retains all cycle sequence bounds. Counts come from actual execution records,
not diagnostic publication or native timer deltas.

The first attempt, `native-world-trace-v11`, stopped before attack range. Under
the additional observation RPCs, each short four-frame right pulse moved P2
only two pixels once neutralized; the bounded24-burst approach ended at x359.
Its terrain jump had crossed the observed x309 rise. The one evidence-based
correction changed the same route's right pulses to ten frames in the new
trace wrapper only. No shared helper or game source changed and there was no
third run. The first report is retained, SHA-256
`6e280461ca04a8b88992d38cd242d7df10d4360f69528e9ba03be3b7ad308e16`.

The corrected run, `native-world-trace-v11-right10`, did execute original Square:
P2 entered native action48 at approximately x377.94/y1082. The exact bound
enemy was HP12/phase1 immediately before; one early attack sample still saw
HP12, then the native slot was freed and the P2 hit counter reached3. Added
trace RPCs did not sample its intermediate HP loss. The reused strict route
check therefore remains **false**, and the original overall status remains
**failed**. It was not rewritten to success. Native attack execution and later
deallocation are context observations here, not a new intermediate-HP pass.
The prior offline/paired interaction receipts are separate evidence.

This measures one shared world invocation per complete observed VBlank/native
driver cycle through this ordinary intro movement/jump/Square context. It does
not establish every enemy, route, lifecycle, stage, backend or host, nor the
moving-support cadence cases. R13's placement/initialization/interaction
contract is separate from this world counter; the coordinator is retaining
R13 as unverified until a final manifest-bound candidate repeats both modes.
No additional once-world requirement is being added to R13.

Evidence directories are under `G:/Temp/Codex/psxrecomp/x6-parity`.
The corrected `world-qualification.json` SHA-256 is
`3691196c9d0ccabc9d89caee298350115be1af2e1c000ae02e01adde62ab8d58`.
`baseline/native-trace.json` SHA-256 is
`8eb015ea1d8d511befa8c3b80f74d71fa3acea297d85c4c00feeec168f2de88a`.
The executed new tool is saved in the profile, SHA-256
`93184fffd464dd5d6c0014d940654c91b90c84c1957be2090fba0ffaea95cdc7`.
The committed compact receipt is
`docs/evidence/mmx6-r13/native-world-v11-counter-summary.json`, SHA-256
`5812d020b166b951562beae292a52f7ab3aeccb2ed44f279cec729a75f89b2ce`.
It preserves both failed route statuses, native witnesses and independent
counter results. Both owned processes were verified absent after bounded
cleanup; graceful shutdown is unqualified. Source cards were unused and
existing private card contents were unchanged. No new binary was built.
