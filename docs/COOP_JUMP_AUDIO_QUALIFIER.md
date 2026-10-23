# X6 jump voice overlap: source contract and bounded observer

The original hardware-only scope below remains available as `hardware_legacy`.
An explicit `--private-banks` runner mode now uses the additional read-only
bank/voice diagnostics; see [the private diagnostic contract](COOP_JUMP_AUDIO_PRIVATE_DIAGNOSTICS.md).
It does not transfer frozen evidence or grant a new native audio result.

R4/R12 remain unverified. No game, title build or sound output was started for
this work. This adds an observer and original-source metadata, with no audio
adapter or changes to the plugin, SDK, CMake or comparison ledger. The starting
game source is `62037b6`; the owner's earlier frozen `986e1598...` executable is
not asserted to contain these tools. A native run must bind its actual image.

The broader mutation/flush/VAB contract remains in
[COOP_AUDIO_DRIVER_OWNERSHIP.md](COOP_AUDIO_DRIVER_OWNERSHIP.md). This follow-up
selects one executable comparison: an ordinary ground jump by Falcon X/P1,
then Zero/P2 while the first character's jump voice is still sounding. Reverse
order is also supported. It does not qualify general attacks, hurt audio,
private sample banks, paired transport, PCM output or music continuity.

## Original call and bank ownership

The original EXE is SLUS-01395 USA v1.1, SHA-256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
[COOP_JUMP_AUDIO_CONTRACT.json](COOP_JUMP_AUDIO_CONTRACT.json) contains nine
bounded native-window hashes and 18 selected tone records, sample hashes,
sample lengths, offsets, pitch/ADSR inputs and calculated original pitch.
It contains no instruction bytes, VAB data or ADPCM samples. Its canonical
JSON SHA-256 is
`ce11910561b56c85450c0c14d66333b0bddd50156235c76ff12bbeb4c902124a`.

| Native event | Exact source route | Original resource/voice ownership |
| --- | --- | --- |
| Ordinary ground jump | `8003AF1C..8003AFF4`; RNG at `8003AF90`, bit4 test; table `80073CE4` indexed by character and second RNG&3; call `8003AFC4` -> `8003CFE0` | X table `[2,3,6,6]`; Zero `[2,4,7,7]`. Group3, VAB3, program0, selected tone/record, hardware voice20. |
| Character voice wrapper | `8003CFE0..8003D014` | Signed actor+8D>0 suppresses the request; otherwise `80016C48(3,record,actor)`. This is intentional silence, not a missing key-on failure. |
| Animation sound flag | `800356C4..800356F4`, call `800356EC` when actor+45 bit80 is set | Group1/id1; VAB1/program0; Falcon X tone1/sample1, Zero tone5/sample5; hardware voice22. The observer retains these events but does not qualify this separate path. |
| Hurt | `8003963C..80039694`; calls at `8003967C` and `8003968C` | RNG&1 xor1 selects group3 record0/1 (VAB3/program0/tone0/1/voice20), followed by group3 record17. Record17 aliases **VAB1**, voice3: Falcon X program0/tone13, Zero program1/tone7. |
| X charge-threshold sound | `80040084`; another charge path at `8003EFCC` | Group1/id7, actor owner; VAB1/program0/tone8, hardware voice23. These sites do not establish the complete ordinary uncharged-shot sound closure. |
| Zero BIN1 function `801EA004` | `801EA038` requests group1/id7; RNG&4 gates `801EA054` -> voice wrapper record8 | VAB1/program0/tone8/voice23, then VAB3/program0/tone8/voice20 if requested. At `801EA06C` it sets action **3Dh**, not ordinary saber action30h. It must not be mislabeled as the pristine ordinary saber sound. |

Zero BIN1 above is 22,964 bytes, SHA-256
`75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00`.
The complete ordinary uncharged X shot and ordinary Zero saber sound producers
remain to be traced before an attack qualifier is added. A discovered
`80016C48` call alone does not identify the native attack that reaches it.

The selected original DAT members are Falcon X **87** and Zero **85**.
Group1 headers/bodies are subassets11/12 and group3 are13/14. The original
sample-size table uses eight-byte units; sample lengths sum exactly to the
selected body. The voice calculation uses original integer tables at
`8007B674`/`8007B68C`, not host floating-point math. Every selected group3
voice has pitch **0478h**, ADSRlo **80FFh**, ADSRhi **1FC0h** when native release
adjustment `800E5608` is zero. Group1/id1 is pitch05A8h for Falcon X and05F5h
for Zero; its source samples are6112 and6832 bytes respectively.

The current loader installs the private Zero image/palette/animation resources
but no counterpart VAB/program/tone banks. Both projected actors therefore
still use the resident native group1/group3 tables. Both original jump voice
records also select hardware voice20. These are source-backed ownership gaps;
this audit supplies no native failure or audible-output claim. Frozen X4's
private-bank architecture remains design input in the broader audit, not an
X6 extent/stride substitute. Preserve X6 metadata stride38h and the record17
VAB1 alias in any later adapter.

## SDK observations and their limits

The frozen SDK is `6212e68066a6977dc587e8fca71f27dac9b002fc`:

| Source | Git blob | Read-only contract |
| --- | --- | --- |
| `runtime/include/spu.h` | `3ee4593fe0824d8b0c9437aeef5cd2a722db0302` | Voice/event schema. |
| `runtime/src/spu.c` | `82b179e771ac5bb24e09b180f9e95a66438e91f2` | Event recording198..222, natural end899..929, KEYON1001..1023, SPU peek1812, recent-event get1865. |
| `runtime/src/debug_server.c` | `915e954d9701714c9dd29d3fc5f718e2139021b2` | `spu_voices`7050..7109, `spu_ram`7113..7128, `spu_events`7132..7178. |

`spu_events(count=4096)` returns the newest available rows, oldest first.
`total` is the next sequence number; the first event is seq0. Each row has
engine `s_frame_count`, kind, voice, byte address, pitch, ADSR and volume at
the event. The parser rejects gaps, reset, duplicate/reordered rows, malformed
hex and a lost requested suffix. It never calls `spu_event_reset`.

The event frame is neither PLAY+90 native world time nor SPU sample time nor a
network tick. The helper records frame differences and ordering only; it does
not invent a sample-accurate lifetime or equate frames with decoded length.
At native END_STOP, the SDK has already moved cur_addr to repeat_addr, sets
envelope0/release, and leaves `active=1` while decoding silently. Therefore
active-mask/count and the END_STOP address cannot establish sample identity
or completed audible duration. The helper uses KEYON sample identity and the
first subsequent KEYON/KEYOFF/END_STOP/END_LOOP on that voice. A new KEYON is
replacement, not a natural-end pass.

`spu_voices` exposes hardware voices0..23; `spu_ram` copies at most4096 hardware
RAM bytes without SPU catch-up or MMIO. Sample identification combines native
logical VAB base `800E56F0[id]`, original sample offset and an exact bounded
RAM SHA-256. No sample bytes enter reports. The helper also reads header,
record-pointer/end, VAB-ready and release-adjustment tables before/after and
rejects changes. It accepts only ready VAB1/3 and release adjustment0.

Events can name private voices24..47, but these RPCs do not expose their bank
identity or immutable sample bytes. The helper **refuses** such a case. A
future private-bank implementation needs a read-only bank/voice probe and a
corresponding test before this observer can qualify it. Global volumes and
event volumes are retained, without a fabricated exact stereo-gain oracle.

## Reusable owner context

`tools/mmx6_coop_jump_audio.py::jump_overlap_smoke(ctx, contract,
first_seat=0, max_attempts=8, timeout=90)` does not launch or stop a process.
Its caller owns a fresh private profile, hidden/muted process, PID-bound debug
listener and final report. Required context keys are:

- `mode="local"`, `input_path="published_host"`, `clients=[owned_client]`;
  `client.read(address,count)` must be the existing ownership-checked reader.
- `request(command, **fields)` must route through that same owned listener.
  The helper uses only `spu_events`, `spu_voices`, `spu_ram` and RAM reads.
- `hold(seat,bits,frames,label)` publishes actual host input for seat0/1,
  waits through the requested bounded native window, and always neutralizes
  in its own finally. It returns its JSON receipt with seat/pressed mask,
  actual native/publication deltas and coherent `start`/`end` player snapshots.
  CROSS is4000h. `native_advance(frames,label)` waits on
  the native PLAY timer. Neither callback may write SIO, player RAM, RNG,
  diagnostic mailboxes, audio tables or directly invoke guest code.
- `report` is a dictionary; `candidate` is the prepared directory;
  `expected_sha256` is the explicitly expected staged executable SHA-256.

The caller must prove the live PID uses that staged image and compiled
manifest, preserve exact starting settings/cards, configure both connected
digital host slots before guest0, and retain the accepted-input trace and
native timer receipts. A matching staged file alone does not prove the
running process's identity. Do not adapt the older offline `press`/SIO menu
adapter: it uses a different input provenance. Physical controllers,
netplay, arbitrary forms, fixture inventory and sound output are outside
this bounded helper.

The helper checks healthy initialized Falcon X/P1+Zero/P2, live ordinary
mode0Ah, no pause/scene owner/absence/mailbox, HP32, native speech gate0,
ground/idle before an attempt, and action6/upward displacement in each held
input receipt. The later post-release snapshot must remain above the starting
Y in native action6/airborne1 or action7/airborne-1. Actor+24 is positive-up
speed, subtracted from Y; releasing Cross can zero it and enter action7 before
the RPC endpoint. A generic fall without the held native action6 witness is
refused. See the [retained native regression](COOP_JUMP_AUDIO_RUNNER.md#native-endpoint-correction).
Intentional RNG silence retries without forcing RNG. At most8 attempts,
120 seconds,16384 retained events and4096 bytes per sample probe are allowed.
If the first voice ends before the second key-on it is not an overlap.
If no two-voice window occurs, the result is explicitly inconclusive.

Every comparison keeps source-sample, pitch/ADSR and natural-end checks per
seat. A same-voice replacement cannot satisfy independent natural endings.
The final hardware voice must have zero envelope/release; active0 is not
required. Exceptions preserve the observation prefix and neutralize both
ordinary host slots. Cleanup errors mark `failed_cleanup`. The owning runner
must refuse `comparison_failed`, `failed_setup`, `failed_cleanup` or
inconclusive outcomes; `observations_complete` still establishes neither
audible output nor an R4/R12 disposition.

## Reproduction and validation

Set process-local TEMP/TMP/cache to an existing private F:/G: directory first.
This source-only command prepares a **fresh** metadata file without connecting
to a game:

```powershell
python tools/mmx6_coop_jump_audio.py --exe 'G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95' --disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin' --out 'G:/Temp/Codex/psxrecomp/x6-parity/temp/audio-overlap/reproduced.json'
$env:MMX6_AUDIO_EXE='G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95'
$env:MMX6_AUDIO_DISC='G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin'
python tools/test_mmx6_coop_jump_audio.py -v
```

Pure tests cover event order/truncation/frame wrap, real SDK END_STOP semantics,
voice bounds, native table extents, exact sample-probe failure, source metadata
drift/fabricated pass, wrong character/pitch/ADSR, replacement versus natural
end and rejection of online/unilateral-input/candidate mismatch before
controls. With both original paths supplied, an additional bounded test
rebuilds the entire metadata contract. These fixtures are not native audio
qualification. The first native run reached a valid short jump but exposed
the original observer's endpoint predicate error; its audio comparison was
not reached. No successful native audio comparison is claimed.
