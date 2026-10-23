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
entry. Both phase2 STOP return addresses must match. Active private voices
require same-frame private KEYOFF with no hardware22/23 KEYOFF. An already
ended voice is a separate contract: its private volume must change to zero,
with its sample attribution and P1 hardware registers preserved. That never
passes active STOP7 lifetime coverage. SDK fntrace and
SPU events explicitly read the same external `s_frame_count`; this comparison
does not substitute a native timer, publication counter or independent sample
clock. Active and inactive STOP dispositions require their own retained
observations.

The [reviewed first contact-death receipt](evidence/mmx6-body-audio/manifest-bound-a1dac26-local-contact-and-vocal-reviewed.json)
verifies the saber SFX source sample and numerical fields, nine live STOP5
private46 events with zero volume and no hardware22 stop, and native HP32->0
through eight ordinary contacts. All 1342 contact trace rows name the original
record25 actor and caller. Both original phase2 STOP calls ran, but the earlier
saber had naturally ended; the SDK deactivates Release/env0 and skips KEYOFF
on inactive voices. Active STOP7 remains unverified. The receipt also records
a current v19 failure: Zero's saber vocal used actual X DAT87 sample bytes on
hardware20/bank0 instead of the retained Zero sample. Correct SFX do not close
the remaining vocal, hurt or death families.

The [fresh inactive-STOP receipt](evidence/mmx6-body-audio/manifest-bound-a1dac26-local-inactive-stops-reviewed.json)
passes all 18 bounded SFX/inactive-death-STOP checks. Private23 was already
inactive with envelope0 and volume13433/13433; its volume becomes0/0 after the
original phase2 STOP7, with the sample binding intact. P1 hardware22 volume,
start, pitch and ADSR remain unchanged. Both immutable banks, eight ordinary
native contacts, source caller traces, clean input recording, owned exit0 and
unchanged private cards are retained. No saber vocal was selected on this run;
the prior same-image X-sample counterexample remains failed. Active STOP7,
paired body audio, active23 state and the other sound families remain open.
