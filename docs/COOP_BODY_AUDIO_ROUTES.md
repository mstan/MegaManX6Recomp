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

Fresh exact debug and production builds, native local and same-machine paired
SOUND/STOP observations, and current-build state coverage remain required.
Prior v18 jump receipts remain bound to their original executable. Other vocal,
hurt, multi-voice death, earned technique, child, music and PCM coverage remain
open under R4/R12.
