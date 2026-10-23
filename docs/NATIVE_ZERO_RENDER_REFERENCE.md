# Native Zero/P1 renderer reference harness

`tools/mmx6_native_zero_reference.py` supplies a bounded **offline** native
Zero/P1 visual reference for comparison with private Zero/P2 dash rendering.
The owning runner launches/stops its own process; this module does neither.
No game/title build or native run was performed while implementing it.

The reference follows the original game's ordinary player sprite/VRAM path
inside an exactly bound recompiled image. It is not original-hardware or
emulator qualification. It does not expose the opposite co-op roster, remove
the co-op unit5 filter, qualify campaign/unlock behavior or mark R9 passed.

## Parent-owned preparation and lifecycle

The parent can prepare a fresh profile with:

```python
import mmx6_native_zero_reference as ref

ref.prepare_reference_profile(build, source, candidate, original_disc,
                              expected_exe_sha256=exact_candidate_sha256)
```

This wraps `prepare_mmx6_coop_playtest.prepare(..., automated=True)` with no
source card. It then writes the **real** `mods/state.toml`: every feature of
every staged package, including `mmx6.local-coop/prototype`, is explicitly
false. Package versions remain explicit. The file SHA and candidate image SHA
are recorded in `native-zero-reference-state.json`. If the parent already
prepared a fresh profile, call `disable_reference_mods(candidate)` before
launch instead. It refuses populated saves/cache/data/appdata/resident folders,
duplicate catalog versions, prior attempts and a source-card preparation.

The runtime may normalize whitespace and table ordering on startup. The helper
records both the prepared raw SHA and a canonical semantic SHA, then checks the
live file against exact package versions and the complete disabled feature set.
Equivalent formatting is accepted; changed settings remain refused. The actual
live raw and semantic hashes are retained in the case receipt.

Use `qualify_mmx6_coop_baseline.candidate_environment` and the same absolute
candidate executable/game/memcard arguments as its owned runner, with that
profile as cwd. All environment/cache/card paths stay private on F:/G:;
background output stays muted. Launch **offline**, with no netplay arguments
or forced online profile. The parent's boot loop should stop at a living idle
native P1 body (`PLAY=0Ah`, phase0, PLAYER phase1/action2). It must not use
`baseline.run`'s two-hero/co-op-readiness predicate for this disabled profile.

Then call:

```python
receipt = {}
ref.run_native_zero_reference(
    owned_popen, port, candidate, original_raw_disc,
    exact_candidate_sha256, receipt,
    allow_private_prerequisite=True,  # explicit setup bypass, described below
    hold_ticks=10, timeout=12)
```

The module checks preparation/config/environment and actual mod-state SHA,
then queries the actual Windows process image path using
`QueryFullProcessImageNameW`, requires the candidate path and hashes that file
against the explicit expected SHA. Every RPC checks the original Popen is
alive and `baseline.owns_listener(port,pid)` is true. Actual `netplay_status`
must explicitly report inactive0 before selection/input. It rejects online
sessions and an unconnected P1 pad. This Windows ownership/image-path path is
the supported execution scope; pure codec tests do not qualify other hosts.

The module does not terminate the process. The parent must retain its normal
`try/finally` and call `baseline.stop_owned_runtime` using PID/listener-checked
clear/quit callbacks. Its private memcard directory is checked to remain
inside the candidate. Existing private `.mcd` hashes are compared after the
case; no source/user card is copied, opened or written by this helper.

## Original native selection and explicit setup taint

The original source bundle is read through the existing bounded raw-disc
reader: only ISO root, original EXE and BIN archive. It verifies:

| Input | SHA256 |
| --- | --- |
| Original EXE | `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046` |
| Original BIN archive | `55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f` |
| BIN16 unit selector | `c9211aee86c5e7377b7716bd698102da1aed8c57a128e90507259cf9f6093ecf` |
| BIN1 Zero overlay | `75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00` |

Existing source analysis is in [COOP_SEAT_CHARACTER_AUDIT.md](COOP_SEAT_CHARACTER_AUDIT.md)
and [COOP_R9_EFFECT_CLOSURE.md](COOP_R9_EFFECT_CLOSURE.md). The helper compares
full live native windows with these original source bytes before setup. This
includes the native major-mode dispatcher, screen loader, player loader/init,
trail updater and original renderer window. `8007112C[2]` must select
`8001E908`, which selects major3; `8001E8CC` then loads the ordinary stage map
and selects major4. This establishes the bounded screen prerequisite path.

If stage-map/Zero availability is absent, `allow_private_prerequisite=False`
fails without any guest write. With explicit `True`, an idle living gameplay
body and the live source guards are required first. The only permitted setup
bytes are:

- `PLAY+5F`: OR bit10h to make native Zero available, retaining existing bits.
- `PLAY+1/+2`: initialize the native screen phase/subphase to0.
- `PLAY+0`: request native screen2.

The helper records each old/new byte and reason before attempting it. Both
`prerequisite_bypass` and `ordinary_input_evidence_tainted` remain true in the
partial or completed receipt. It never writes PLAYER, form/character, native
unit list/cursor, HP, stage-clear/rescue/success flags, overlays or cards.
Base Zero only is supported: a Black Zero/unknown high availability bit is
refused rather than cleared. The bypass does not establish an unlock or
ordinary campaign route.

After the native map reaches `PLAY=04/04/00`, the helper compares original
BIN16 list-builder and confirmation code windows. It reads the native list
and verifies the original order `[X,Falcon,Zero,Shadow,Blade,Ultimate]` with
availability masks. A filtered/missing unit5 fails. It uses native Cross to
open the selector, Right to move its real cursor, then Cross to confirm Zero.
Only native input changes that cursor and writes form5/character1. The helper
waits for the actual selected stage's living idle Zero/P1, native animation
table `801EF6D0`, body form5 and native RAM compression/assembly resources.
It records the stage/section reached, without assuming intro or claiming a
campaign transition pass. Briefing dismissals are bounded original input too.

### Briefing readiness and consumed neutral between menu pulses

The preserved native attempt
`G:/Temp/Codex/psxrecomp/x6-parity/native-zero-reference-v12-e2e47e6-normalized/qualification.json`
has SHA256 `37f100b990f9f6327330bf5d833f30e9756e72b94d54cc3e0fa446964cd27198`.
It remains `failed_setup` on image
`229ffec7a7dabda9742653264e1d023adde408602003df7f48b4c4d3f758d8e6`.
Source/profile guards and the explicit prerequisite bypass completed. One
briefing input was recorded, then the next pulse timed out before the unit
list. The old report lacks the failed pulse's decoded observations; it cannot
establish the exact runtime cause. It is retained unchanged.

The original source identifies two defects in that pulse predicate:

| Original source | Native behavior and helper requirement |
| --- | --- |
| EXE `80012A34..80012B43` | Pad bytes are decoded to `800C456C` held, `800C456E` previous and `800C4570` rising edge. `80012B20..40` writes `previous=old held` and `edge=new held & ~old held`. A clear-input ACK does not establish consumption. |
| BIN16 `800F1068[11] -> 800ED6E0`; subtable `800F1060` | Stage-map phase11 dispatches subphase0 to `800ED648`, subphase1 to `800ED6B4`. |
| BIN16 `800ED690..800ED6A4` | Subphase0 calls the native dialogue initializer `80021760`, then increments subphase automatically. A change from `04/0B/00` to `04/0B/01` is insufficient evidence of a Cross dismissal. |
| BIN16 `800ED6B4..800ED6D4` | Subphase1 waits for the dialogue active byte `8008EAFC` to clear, then returns to map phase3/subphase0. |
| EXE `800100B4[3] -> 80022000`; dispatch `80021C20..4C` | Dialogue phase is `8008EAFD`. Phase3 reads the decoded edge low byte at `80022004`; Cross is native `0040h`. Phase2 at `80021FC4` may change text timing without dismissing the page. |
| BIN16 `800EB080..800EB1E7` | The original selector reads rising edges. Published Right `0020h` decodes to native `2000h`; published Cross `4000h` decodes to native `0040h`. |
| BIN16 `800F0F40[5/6] -> 800EB080/800ECD80` | Selector input runs in `04/04/05`. Right changes the cursor and enters subphase6 at `800EB148..158`; `800ECD80..800ECDE0` returns to5 after eight native animation updates. Neutral input during6 does not make the selector ready for another edge. |

These additional EXE/BIN16 windows are compared with live original bytes
before their associated inputs. Briefing input now waits for coherent sampled
mode `04/0B/01`, nonzero dialogue activity and dialogue phase3. It rechecks
that readiness while waiting for neutral before pressing. The response must
leave the native input-wait phase/page or leave phase11; initialization alone
is never labeled a dismissal. The outer wait retains mode, dialogue and
decoded observations even while native text/loading work progresses.
The map-opening pulse requires sampled `04/04/00`. Every cursor/confirmation
pulse requires sampled `04/04/05` before pressing. The helper waits for the
original cursor animation to return from6 to5; leaving5 due to a previous
cursor animation can no longer masquerade as confirmation. It does not force
the native animation counter, cursor or form.

Every menu pulse uses the existing persistent `frames=0` input, waits for an
observed native held mask plus the expected native response, clears input in
`finally`, then waits until **all three decoded halfwords are zero**. Following
an observed hold, held0/previous-held is still a pending release and cannot
permit the next pulse. A separate pre-pulse neutral check also rejects stale
previous/edge values. Poll sleeps only pace reads; native values determine
readiness and release completion. The frozen gameplay clock is not used as a
menu progress clock. A one-frame edge can be missed by polling, so the receipt
records whether an edge was sampled without treating that absence alone as a
failure after a neutral-to-held input and actual native response.

`selection.inputs` appends each attempt **before** issuing it. It retains the
purpose, published/native masks, timeout, mode brackets, decoded triples,
dialogue state, held/response/release observations, timeout stage(s), elapsed
time and any independent release error. A response or release timeout remains
`failed_setup`; a successful attempt is only
`native_transition_and_neutral_observed`. The decoded triple is one six-byte
RPC; PLAY mode and dialogue are separate reads, with mode brackets checked.
This is not an atomic cross-RPC state or a complete input trace.

The menu correction was source-audited and tested without launching a game in
its implementation lane. A subsequent owning-runner receipt reached native
Zero selection, as described below. The old failed report is not reclassified.

## Dash, resources, captures and retirement

The original three-RPC clock/pool/clock reader correctly rejected changing
clocks, but ordinary progress between independently owned requests could make
a coherent sample unavailable. The preserved owning-runner attempt
`G:/Temp/Codex/psxrecomp/x6-parity/native-zero-reference-v12-e2e47e6-ready-neutral/qualification.json`
has SHA256 `ec16a1587755696e06e6b44ba0e29785fb80de81a86e9cecca31fee2030f180d`.
On the same exact `229ffec7...758d8e6` image it reached
`selection.status=native_zero_selected`, passed its source/profile guards and
completed an idle composed capture. It then remained `failed_setup` on an
unstable three-RPC sample **before any dash input**. The owned process quit
with ACK and exit0. That raw result remains unchanged; it is not an art/dash pass.

The replacement uses the existing SDK's **one fixed contiguous ordinary-RAM
request** from `800970A0` through exclusive `800CCF64`: `35EC4h`/220,868 bytes.
The first `378h` bytes contain the P1 body, camera block and three complete
trails. PLAY's exact `94h` bytes, including native clock/mode, start at offset
`35E30h`. There is no pairing with an earlier/later clock and no retry which
admits mismatched data.

This path is supported in frozen SDK
`199839335e32448c10a52f4c98967903a807e040`,
`runtime/src/debug_server.c` blob `c35a59284c6148def1ee12fc94b20413f459026f`:
`handle_read_ram` at line5283 permits up to full live RAM, allocates a bounded
heap reply and reads it in one handler. `process_command` at line16289 runs
that handler at an emulation-thread `debug_server_poll` safe point.
The same file's `debug_server_send_line` grows its response buffer up to64MiB,
so there is no intervening64KiB transport truncation. All bytes
in this mapping are ordinary 2MiB RAM; no MMIO, guest call, guest pause command
or fixture write is involved. Thus guest execution cannot advance between
the native fields within this handler. This is a native RAM observation at
that safe point, not a full core/peripheral or savestate snapshot.

The exact 441,736 hex characters plus the server's small envelope fit the
existing 1MiB client response cap. Generic `DebugClient.read` retains its64KiB
limit. Only `read_native` issues this fixed larger mapping, through the same
PID/listener-checked `OwnedNativeSession.request`. It strictly verifies reply
address, integer length, exact hex size/decoding and native record links. A
clamped, truncated, malformed, incorrectly mapped or unavailable reply fails
closed; it does not fall back to split reads, pause execution or weaken native
clock equality. Each observation still requires native Zero/living-body,
resource, phase, held-clock/capture and finite-retirement checks.

Every attempted read is appended to `native_snapshot_reads` before its RPC,
with a context label and exact mapping. Accepted records retain the PLAY and
full `378h` body/camera/trails slices plus a full response-payload SHA256;
unparsed gap bytes are discarded. Rejected requests retain their status/error,
available address/length/hex-size and encoded-response hash/prefix/suffix.
Transport and invalid-link failures are retained too. The payload hash is
diagnostic evidence, not a framework CRC or simulation digest. Native links,
fields, CLUTs, phases and counters still use the strict `NativeEffect` codec;
the signed native producer is body`+8C`, not an input acknowledgment.

The single-RPC fix was tested without a native launch or title build. A fresh
owned run must still qualify dash/artwork behavior; no old result is promoted.

The case captures a completed composed idle image, then holds original P1
Right+Circle+Cross (`6020h` active-high; NativePad active-low`9FDFh`) with
`frames=0`. Short `press` counters expire per sampler read on this SDK, so
they cannot substitute for a bounded native-frame hold. The gameplay window
uses actual `PLAY+90` progress, a hard deadline, a maximum native-tick budget
and neutral input in `finally`. Menu input uses bounded actual cursor/phase
response because the gameplay clock is frozen there.

Acceptance requires a newly positive `+8C`, ordinary dash/jump-dash action0Ch
or6, all three native visible phase0 trails, intact parent chain and owner
frame/facing/compression/assembly. The original Zero renderer skips X charge
attachments and orders the body then trails2,1,0; the receipt records that
source order. Co-op is disabled through real state, so no private P2 render
pass/bank is installed by this case.

The positive composed capture uses the existing `capture_present` completion
protocol, not its acknowledgment alone. A visible accepted snapshot is
retained immediately before and after completion. Capture polling also checks
the held native-clock budget. If the pose/marker expires before completion,
the reference check fails and keeps the partial image and observations.
CPU `vram_peek` and GL `gl_fbo_peek` each retain48 actual RGB555 palette words
for native CLUTs780Dh/780Eh/780Fh at VRAM208,480. Empty/truncated/malformed
palette responses fail. Those palette reads and the image are separate RPCs;
the receipt does not pretend they are same-cycle pixel evidence.

After neutral release, the case retains original native negative marker
phases1 and2 and waits for marker0 with all three visibility/active flags
clear. No native body/marker is assigned to force that result. The reducer
requires ordered native clocks, unchanged parent/resource/CLUT identity and
retirement within32 observed timer ticks of the first negative sample.
The overall release window is bounded at64 ticks. These are observed clock
windows, not proof that one clock tick equals one own helper invocation.

Fresh output is `candidate/native-zero-reference/` with idle/positive composed
images and `reference.json`. Errors retain setup writes, inputs, native rows,
captures, binding and cleanup failures already observed. Reusing the folder
is refused. A completed automated case is only
`reference_observations_completed_artwork_pending`: artwork stays `pending`,
ledger status stays `unverified`. The parent must visually compare the
native P1 reference and private P2 capture, including colors, pose, CLUT/frame
identity and temporal limits. No native acceptance, rendered-art or retirement
pass is inferred from fixture tests, ACKs or source metadata alone.

## Focused checks

From `tools`, with private non-C: TEMP/TMP/PYTHONPYCACHEPREFIX:

```text
python -m unittest test_mmx6_native_zero_reference
```

Set `MMX6_CONTENT_DISC` to the explicit legitimate raw disc path to include
the original-source guard test. Twenty-seven fixtures cover real-state setup and
drift, source cards/non-pristine profiles, listener/image/online rejection,
source guards, exact record reads/links, original unit navigation and bypass
boundaries, held input cleanup, source palette framing, positive capture
brackets, negative drain/resource failures and retained partial results.
Menu regressions cover delayed native release consumption, stale previous
input after a clear ACK, mode transitions without consumed input, phase11
initialization/text states, pending selector animation, truncated/incoherent samples and independent
response/cleanup failures. The optional source check includes every added
live guard extent from the unchanged full-identity original bundle.
Snapshot fixtures require clock/body/pools from one exact RPC, reject wrong
addresses/counts/lengths/encoding and invalid links, retain failed requests,
and refuse unsupported atomic mapping before any dash input. Split-read
fallback is forbidden. Synthetic responses establish protocol behavior only.
The modeled native responses are test contracts, not original-game execution
or artwork evidence. No SDK/plugin/profile/ledger/CMake files are changed.
