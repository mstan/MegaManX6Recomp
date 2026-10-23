# Scoped private Zero jump audio candidate

This page records the earlier scoped implementation and its retained receipts.
The current v18 source candidate is described in
[private character audio](COOP_PRIVATE_CHARACTER_AUDIO.md); its broader route,
voice leases and schema3 supersede the implementation scope below. Older native
receipts do not qualify the new image.

This is a default correctness fix when the fixed X/P1 + ordinary Zero/P2 co-op
package is active. It remains **unqualified in a native candidate**. It does not
resolve the whole R4/R12 families, other attacks/hurt voices, opposite rosters,
campaign audio or netplay. The prior shared-voice implementation locally failed
the bounded X/Zero overlap comparison: P2 used X's resident sample and replaced
P1's hardware vocal. Its scalar pitch/ADSR failure was gated by the wrong sample
identity; it did not demonstrate a separate scalar DSP defect.

[Source metadata](COOP_PRIVATE_JUMP_AUDIO.json) pins the original USA v1.1 EXE,
ten supporting instruction windows, the complete resident direct-stop call
inventory and the exact retained Zero banks. The instruction windows are source
citations, not substitutes for the finite ordinary driver closure established in
[the ownership audit](COOP_AUDIO_DRIVER_OWNERSHIP.md). No instructions, VAB
headers, samples, cards or game binaries are committed.

## Selection and native calculation

The adapter follows the frozen X4 private-bank/native-calculation architecture
at commit `50593bca772b600de6911cbfecd40b0f08721147`, audio blob
`f490a1725aac5775a3e6711305370c279362dceb`. Every address/extent here is X6's.

Only these original requests are redirected, while PLAYER contains the live
private ordinary Zero body (`character=1`, `form=5`, native phase1):

| Native request | Proven caller boundary | Private destination |
| --- | --- | --- |
| SFX group1/record1 | Original action6, SOUND return address `800356F4` | slot22/event46, bank30 |
| Vocal group3/record2,4,7 | SOUND return `8003D004`, wrapper's saved parent `8003AFCC` | slot20/event44, bank31 |

The original `8003AF1C` RNG/voice gate, wrapper's `PLAYER+8D` suppression,
action flags and channel-disabled byte remain native. No extra RNG call,
synthetic voice choice or forced KEYON is introduced. P1, other requests,
unrelated callers and Black Zero remain outside this route. Existing public
roster admission remains X/P1 -> ordinary Zero/P2.

The retained assets are the exact DAT member85 header/body subassets11/12 and
13/14. Bank30 contains **123408 raw body bytes**, bank31 **52096 raw body bytes**,
with logical sample base0 and no prefix. Parsed header copies have private
native handles14/15; the original high routing bits and group3/record17's alias
to effects VAB1 are preserved. The source-derived parser constructs populated
program ranks and cumulative sample-address pairs without opening a native
VAB, starting DMA, changing a transfer gate or faking an asynchronous completion.
Both original header/body SHA-256 pairs are required before publication.

The temporary native VAB-table readiness exists only inside the closed,
uncharged SOUND calculation. The calculation requires unused native slots14/15,
the original max-program bound128, zero callback slots, a clear native gate and
the proven direct routing entry. The helper rejects malformed records, gains,
samples, unexpected KEYON/status arguments, callback activation or an out-of-bank
calculated sample start. It never substitutes a hardware fallback on failure.

X6's transaction saves/restores all bytes `800E4E30..800E572F` (2304 bytes),
including **38h** voice metadata, final `+36h`, all16 end-history words, masks,
dirty bytes, mirrors and VAB calculation/tables. It also restores the24 priority
bytes,128 group-table bytes, native gate and current record pointer. Original
SOUND/KEYON execute under the SDK budget0 uncharged contract, whose ordinary
source closure has no flush/device wait/indirect callback. Every saved region is
restored **before** private DSP play. The resulting native stereo registers,
pitch, ADSR and noise/reverb masks supply the private voice. Initial ENV is0 and
LOOP starts at START; original ADPCM loop/end flags subsequently control lifetime.

Active foreign-bank private slots20/22 are refused using the SDK's read-only
`spu_get_private_voice_state`, including conflicts after initial binding. Fault
and teardown do not volume-zero or KEYOFF a foreign voice. Immutable bank
registration rejects different bytes already resident at30/31. An inactive slot
may be reused; this is not a general SDK resource-allocation/lease system.

## Stop, lifetime and the remaining shared-slot gap

Exact jump-record stops perform private volume0 followed by private KEYOFF and
preserve native's single-voice result `FF000000`, without native hardware writes.
Global groupFF calls the original once, then stops the two owned private slots.
Other character stops retain their original call/result; if their actual native
record's contiguous voice range overlaps20/22, the matching private stop is
mirrored afterward. Foreign private voices are preserved and the conflict
refuses the co-op audio path.

The resident EXE has20 direct calls to `8001750C`, inventoried in the metadata.
They use globalFF or character records1/5 and1/7. Original Zero1/5 selects
hardware22, whereas1/7 selects23. Concrete1/5 callers are `800385FC`, `800386EC`,
`800387E4`, `800388F8`, `8003B234` and `8003D8BC`.
For example, `800359AC` calls `80039FFC(PLAYER)` and a nonzero result takes
`800359BC -> 8003B218 -> 8003B234`, stopping1/5. `800385F4` similarly gates the
1/5 stop after the native `PLAYER+85` countdown / `PLAYER+7C` held-direction
predicate. These are exact native branch triggers; no new normal-input gameplay
receipt is claimed for them. `8003D8A8` also stops1/5 and1/7 before its transition.

**Known gap:** the unchanged nonjump1/5 hardware stop can still cut P1's
hardware22 when that native path executes. The mirror closes a preceding private
jump SFX lifetime; it does not fix ownership of other P2 hardware sounds/stops.
This must remain separate from a bounded overlap result. Neither active masks
nor slot numbers alone establish correct sample identity or natural completion.

## Current-build state and integration

The two retained immutable headers/bodies participate in the asset SHA; their
guest allocations are fixed snapshot resources. Host schema2 intentionally
rejects older snapshots. Readiness rejects every live audio callback/transaction,
pending register set, foreign active slot and unbound/reset SPU epoch. The canonical digest names
audio fields explicitly and hashes no pointers, padding or process epoch.
Private DSP decoder/envelope/sweep/bank bindings remain in the existing SDK SPU
codec. The immutable registry must already be bound before state validation;
an epoch reset is rejected until the owner reloads/rebinds retained assets.
Successful apply reprojects retained parsed headers without allocation, DMA,
guest calls or replaying a sound. Cold-cache tests retain the immutable loaded
assets; they do not establish arbitrary pre-assets process-cold loading.

Central integration must link `mmx6_coop_jump_audio.c` into every title EXTRAS
variant, require SDK `bfbfb920bfa509f6a31ec2e6b28411a01797427f` or later for the
read-only private-voice accessor, add/regenerate the four native hook entries
`80016C48`, `8005A9D4`, `80055B14`, `8001750C`, and update the build/profile
identity. No generated source, CMake, catalog, compatibility string or parity
ledger was edited in this worker branch. Source/manifest/image identity changes
are expected; no cross-build or backward-state compatibility is asserted.

## Focused helper evidence

The header, actual-plugin transaction and checked snapshot fixtures pass on
GCC15.2 and Clang22.1.8 in debug and production modes (12 fixture configurations).
The transaction fixture also runs with an optional original-member source
capsule stored only in G scratch. It verifies exact retained body bytes,
all four allocation-failure points, corrupt-body refusal and epoch rebinding.
The actual-plugin guest double models the audited driver contract; it is not
original MIPS execution. It mutates every byte of the native transaction and
asserts complete restoration before private play, including pending P1 masks.
It covers all four jump records, P1/nonjump caller rejection, active own and
foreign slots, foreign stop/teardown preservation, bank/native-slot conflicts,
malformed calculated output, missing KEYON, charged calls, capacity failure,
private-play failure, and exact jump/nonjump/global stop distinctions.

Example portable helper build (set TEMP/TMP/cache to an owned non-C directory):

```powershell
& $compiler -std=c99 -O3 -DNDEBUG -DPSX_NO_DEBUG_TOOLS `
  -ffunction-sections -fdata-sections -I src/mods -I "$sdk/runtime/include" `
  tests/test_mmx6_coop_jump_audio.c src/mods/mmx6_coop_jump_audio.c `
  src/mods/mmx6_coop_assets.c src/mods/mmx6_coop_lifecycle.c `
  "$sdk/runtime/src/psx_sha256.c" '-Wl,--gc-sections' -o "$scratch/jump-audio.exe"
& "$scratch/jump-audio.exe"
```

Use `-O0 -g` for the debug matrix and omit the two production definitions.
For GCC's unoptimized isolated fixture, `-fno-asynchronous-unwind-tables
-fno-unwind-tables` permits PE section collection. Preserve Clang's normal
unwind metadata in the snapshot fixture: its real longjmp test needs it. An
initial Clang snapshot attempt with unwind tables disabled exited `C00000FF`;
the corrected normal-metadata builds pass without changing assertions or the
32768-byte live landing frame. All compiler/test output stays in
`G:/Temp/Codex/psxrecomp/x6-parity/temp/zero-jump-audio`, including the failed
configuration receipt. No title build, game launch or sound output occurred.

Fresh native qualification must bind the new image/manifest and event-time bank,
read actual private state and immutable bank bytes, match selected Zero sample
offset/hash, pitch/ADSR/mode, verify P1 continues through P2 KEYON, and observe
both original end markers/lifetimes with no unintended replacement. It must also
retain known nonjump stop behavior as a separate open obligation. Local and
netplay evidence remain separate; no R4/R12 pass follows from these fixtures.

Central integration now selects title compatibility v16, links the helper
through the title's existing mod-source glob and the actual-plugin fixtures,
registers header/transaction tests in debug and production variants, and seeds
all four driver functions in development and release configurations. Ignored
native regeneration changed only full_01, full_23 and full_24; each required
function contains the actual replacement entry, and the original input-capture
hook remains verified. Ten combined audio/snapshot/effects/retirement CTests
pass. The frozen348a52c debug and production suites now both pass96/96.
Its [local X-first native receipt](evidence/mmx6-jump-audio/manifest-bound-348a52c-local-private-overlap-reviewed.json)
passes all19 sample/route/DSP/lifetime checks: hardware P1 continues after
private P2 voice44/bank31, both reach original end markers and zero final
envelopes, and immutable source banks remain unchanged. At that point opposite
order, paired audio and other action families were unverified; prior exact-image
failures are retained and R4/R12 are not closed by this bounded ground jump.

The first reverse-order trial retained an input setup failure: its first
post-input world publication still showed idle Zero, then Zero was airborne
in action7 during cleanup after release. One world tick did not prove host
sample consumption. The local audio adapter now holds Cross through observed
native action6 ascent, with the existing wall deadline and120-native-update
bound, before releasing. It still requires the independent original body and
source acceptance checks afterward. The21 runner/protocol tests include that
one-publication delay, a missing-ascent bound and neutral cleanup; the failed
native attempt is retained. The [fresh reverse-order receipt](evidence/mmx6-jump-audio/manifest-bound-348a52c-local-private-reverse-reviewed.json)
now passes all19 checks on the same frozen348a52c image. Zero's private voice
continues through X's native KEYON; both reach natural end with correct source,
DSP and immutable banks. The source correction makes input acceptance observed
instead of assuming it from a requested one-tick window. Both local orders are
now covered.

The [paired receipt](evidence/mmx6-jump-audio/manifest-bound-348a52c-paired-orders-reviewed.json)
also covers both orders on fresh same-machine pairs using the same frozen image.
Each peer independently passes all 19 source, route, lifetime and final DSP
checks. The X-first run took six ordinary jump trials and retained 29 matched
resolved core/mod samples; Zero first took four trials and retained 30 samples.
Both pairs used the fixed startup profile, published neutral inputs afterward,
preserved their private memory cards and exited through owned Quit. Composed
captures were reviewed and match between peers. The earlier eight-trial
inconclusive run is retained. Other action families, PCM/listening, music
continuity and cross-machine qualification remain open; R4/R12 remain incomplete.
