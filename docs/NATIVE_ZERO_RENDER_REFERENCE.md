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

## Dash, resources, captures and retirement

The P1 body, intervening camera block and three complete trail records are
read in **one `378h`-byte RPC** from `800970A0`. Native links, fields, CLUTs,
phases and counters are parsed with the existing strict `NativeEffect` codec.
The signed native producer is body`+8C`, not an input acknowledgment. PLAY
clock/mode reads bracket that RPC and mismatches reject the observation;
they remain separate operations, with the temporal limit recorded explicitly.

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
the original-source guard test. Fifteen fixtures cover real-state setup and
drift, source cards/non-pristine profiles, listener/image/online rejection,
source guards, exact record reads/links, original unit navigation and bypass
boundaries, held input cleanup, source palette framing, positive capture
brackets, negative drain/resource failures and retained partial results.
The modeled native responses are test contracts, not original-game execution
or artwork evidence. No SDK/plugin/profile/ledger/CMake files are changed.
