# Zero body audio ownership

The v18 ground-jump fix leaves a concrete nonjump gap: Zero's group1/5 STOP
still executes native volume-zero and KEYOFF on P1's hardware22 before stopping
the private jump voice. Group1/7 uses hardware23. Suppressing STOP alone would
leave a preceding native P2 sound playing on those hardware voices.

The new route therefore covers all eight body-owned group1 records sharing
those two voices. Records1..6 use private22/bank30; records7/8 use
private23/bank30. Their original program0 tones are1,3,4,5,6,7,8,9. Record and
tone are not interchangeable. Header validation checks each complete record;
native SOUND still calculates spatial gains, pitch, ADSR and mode inside the
existing bounded transaction, then restores all native driver state before
private playback. Exact projected PLAYER ownership admits these body sounds;
child actors and other groups remain outside this route.

STOP has no actor argument. The nine [source-pinned callers](COOP_BODY_AUDIO_ROUTES.json)
must retain exact PLAYER in s0 and match the original return address. Seven
sites require phase1. Only the two original death-entry stops admit phase2.
Each accepted STOP performs private volume-zero before private KEYOFF and
returns the original FF000000 without running the hardware stop. Shared
groupFF retains native execution once, followed by title-owned private silence.
The epoch/bank ownership checks now include slot23 and preserve foreign voices.

The actual-plugin fixture covers all eight PLAY records, nine STOP sites,
actor/caller/phase rejection, P1 pending masks and full driver state,
globalFF, foreign slot23 and native transaction failures. The independent
original-source audit checks record-to-tone mappings, original call arguments
and s0 setup, including the helper that loads fixed PLAYER directly. These
checks do not establish native gameplay or audio qualification.

The [frozen v19 receipt](evidence/mmx6-body-audio/manifest-bound-a1dac26-build-and-saber-smoke-reviewed.json)
binds source a1dac26 and both 100/100 suites. A fresh same-machine pair passes
all 11 native menu/resume/movement/Square checks with 20 matched resolved
core/mod samples, matching reviewed composed captures and graceful owned exits.
This gameplay smoke does not observe body-audio event/sample/STOP lifetimes.
Native local and paired SOUND/STOP observations and current-build active23
state coverage remain required.
Prior v18 jump receipts remain bound to their original executable. Other vocal,
hurt, multi-voice death, earned technique, child, music and PCM coverage remain
open under R4/R12.

The owned local audio runner accepts `--private-banks --body-sfx` for an
ordinary standing Zero Square/neutral case. It retains original-source body
records, probes every selected sample byte in reads of at most 4096 bytes,
checks numerical pitch/ADSR, and observes private KEYOFF plus final volume/DSP.
It holds Square until actual saber action and KEYON are observed. Natural
sample end alone cannot pass the STOP check, and reused voices cannot borrow
an older note's final envelope. The finalized native trace must contain actual
P2 Square consumption. Other character vocal events remain visible in the
report and do not acquire a passing disposition from this SFX case.

The first native standing-saber trial reached private47/bank30 and natural
END_STOP, then idle. Its observer incorrectly expected neutral Square release
to issue KEYOFF; that failed setup is retained. A saber-only run now records
partial observations and leaves STOP unverified. It cannot pass the full case.

`--body-death` extends the case through original intro record25 contact: eight
ordinary strength4 HP losses, no HP/death writes, and the surviving primary.
Read-only function tracing records SOUND, STOP, the contact helper and phase2
entry. Both phase2 STOP return addresses must match, and their engine frame
must contain private46/47 KEYOFF with no hardware22/23 KEYOFF. SDK fntrace and
SPU events explicitly read the same external `s_frame_count`; this comparison
does not substitute a native timer, publication counter or independent sample
clock. These native death checks still require an actual retained run.
