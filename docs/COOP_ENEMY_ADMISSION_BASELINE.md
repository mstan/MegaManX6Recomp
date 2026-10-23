# Bounded native enemy-admission qualifier

`tools/qualify_mmx6_coop_enemy_admission.py` stages a private, hidden, muted
offline profile from the frozen executable below. It reuses the baseline
runner's listener ownership, native boot, input and cleanup. Its planned case
keeps P1 at x144 while P2 moves the shared camera far enough to admit intro
category0 record25, then approaches and attacks its native enemy instance.
It uses original port2 SIO pad input. This SDK's explicit host virtual input
layer supports P1 only; this does not qualify physical controllers or transport.
There are no guest RAM, fixture mailbox, success-flag or source-card writes.
Data/cache/temp paths are on G: and the debug port is 24895.

## Source contract

The source audit is `COOP_PLACEMENT_ADMISSION_AUDIT.md` and its JSON companion.
The pinned intro overlay SHA-256 is
`d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`.
Record25 at `800FA2DC` is category0/type1/subtype1 at authored (416,1080).
With the native 320x240 viewport and zero margin, camera x0 leaves it beyond
the horizontal scanner bound; camera x48..80 is the selected admission window.
The scanner is `80029F38`, driven by `80029D18`, and allocates through `8002BBF4`.

The parser examines all 48 native pool slots at `8008EF48`, stride `9C`.
It requires active byte +0, type1 at +1 and the exact origin pointer at +10.
It ignores stale freed slots and rejects duplicate live origins. Native phase0
initialization at `800EAFFC` writes HP12, strength4 and phase/action 1/1; render
byte +3 may still be zero. The planned interaction must retain that slot address
and change its HP or native phase after P2 input. Counters or a record bit alone
cannot pass it. Type1 phase1 at `800EAC8C` calls the native hit/contact helpers.

The native enemy loop at `8002000C` visits the pool once in source. No independent
runtime counter proving exactly one world update has been qualified. Native
timer progress is telemetry only. Diagnostic publication is atomic, but camera,
record and pool reads are separate bounded observations. They do not prove a
single atomic world state.

The native proximity helper `800EB14C` compares against resident P1. With P1x144
and this enemy x416 its distance is 272, regardless of P2 leading. P2 proximity
alone must not be required to trigger native action2. That targeting behavior
is a separate source finding; this lane obtained no runtime targeting result.

## Prior bd7 setup rejections

Both retained attempts used executable SHA-256
`bd7b9449d9fbc5c9c2137902ba2d8d525d1886211b03fd6756d0f76fbc9c263e`.
They staged from `snapshot-modern-v10-state/warm`, not the changing central
build directory. Staging records current source observations without claiming
that those observations establish compilation provenance.

| Attempt | Result | Retained report SHA-256 |
| --- | --- | --- |
| `enemy-admission-r13-bd7` | Harness rejected stored `ws_nw.native_wide=1`; actual mode0/extra0/margin0 was already native 4:3. | `dc23b225fd1dd10930d50192d4d0c2ae1b9161b1c2907b24e947cdc6ad6665a4` |
| `enemy-admission-r13-bd7-native43` | Corrected viewport check passed; strict initial-camera gate rejected x2 instead of x0. No route traversal followed. | `1af75072fbf5c02224c1fc95a8214c44a8d7e7fe1c62e2546f70cc003089a95e` |

Both directories are under `G:/Temp/Codex/psxrecomp/x6-parity`; each contains
`qualification.json`, profile/configuration and baseline logs/canonical images.
The sole correction uses active `GpuWsDebug.mode`, configured state, margin and
extra width. The `ws_nw.native_wide` field is a stored preference even while
widescreen is off; SDK `gpu.h` defines mode0=off and `gpu.c` requires mode2 for
active native-wide rendering. A focused regression protects that distinction.

The corrected attempt's initial observation was diagnostic tick248/native
timer247, both heroes alive with HP32, P1x144, P2x181.5, mailbox0 and no scene or
pause owner. Current and previous cameras were both (2,944). Record bytes were
`00010100a001380400010100`, its allocation bit was clear, and the entire live
enemy pool was empty. The reused baseline's earlier twelve-frame P2 movement
smoke had already shifted the camera. The strict setup gate stopped before the
case moved P2 or attacked. Camera2 still satisfies the actual source
discriminator `cameraX+368<416`: this was an unnecessary literal checkpoint
assertion, not a failed mechanic. The coordinator ended that bounded lane and
reviewed the source-derived guard. This was not a new owner instruction.

The corrected failure's canonical PNG SHA-256 is
`80d5ef0574f7377c7a412493bad12c3d5ae5fde34c61ba71d37fedf639b0dfac`.
No composed admission or interaction capture was produced because those gates
were never reached. Both owned processes required termination after bounded
quit handling; there is no graceful-exit claim. Source cards were unused and
the runner reported existing private card contents unchanged. Other agents'
live peer processes were left alone.

Five parser/viewport unit checks pass: nonzero-slot origin binding with render0,
stale/dead and wrong-type rejection, duplicate origin rejection, truncated-pool
rejection, and active viewport versus stored renderer preference. They do not
qualify the unexecuted gameplay portions of the tool. Later tool-only additions
of source metadata, explicit limits and slot-identity guarding were not rerun.

The two reports are also committed under `docs/evidence/mmx6-r13/` with only
CRLF line endings normalized to LF; the hashes above identify retained originals.
The following route attempt replaces the literal camera check with the actual
scanner predicate. Both original setup rejections remain preserved.

## Native v10 route result

The selected SDK9cb/profile-v10 candidate is a separately frozen executable:
`a2f0d2c994db8deece0cb162114e74a225b8151a6c35940d5aa1651132544bc0`.
Its executable/assets/catalog were staged from
`netplay-modern-sdk-final-v10/peer-0`; caches, saves and cards were not copied.
The preflight now requires `0<=cameraX` and `cameraX+368<416`, cameraY944,
P1x144, an inactive record and no live matching origin. Unit cases accept
camera0/2/47 and reject -1/48/80, wrong Y, moved P1, allocation and live origin.

The first actual route, `enemy-admission-r13-sdk9cb-v10-before`, admitted the
exact origin into slot0 at `8008EF48` at camera(49,944), diagnostic tick461.
Native initialization was observed at tick476 with phase1/action1/subaction0,
HP12 and strength4. P1 stayed x144. P2 walking stopped at x309/y1114 before the
nearby terrain rise; its bounded approach could not reach attack distance.
The report retains 56 samples from ticks642..841 with P2 distance111..107,
P1 distance272 and native enemy action +5 still1. This observes the resident
P1 proximity gap without using a hook counter as proof. No attack was attempted
in that first route. Its report SHA-256 is
`1e49a755856feb288a9420485665ed19281b52fd70c647cbf98d7ac37b19763c`.
The executed qualifier source was saved alongside it, SHA-256
`cfda96fafb71519c81867eff2cc8882a5ab5515a8eed9f079da31edd3c54710c`.

One evidence-based route correction supplies one original jump-right input
after walking stops. `enemy-admission-r13-sdk9cb-v10-before-jump` passes all
eleven bounded offline checks, including the six reused intro/input checks.
At tick383/camera(50,944), record25 was admitted into the same native pool slot;
tick398 observed HP12/phase1 initialization. The single terrain jump began at
tick572/x309. P2 subsequently reached x376/y1082, forty pixels from the enemy,
while P1 stayed x144. Native Square input changed the exact origin-bound
instance from HP12/phase1 to HP0/phase2 by tick725. P2 was in native action48;
the native P2 hit counter changed 0->1 as corroborating telemetry. The native
body transition, rather than that counter alone, establishes the interaction.
There were 137 retained case observations; P1's X remained fixed in all of them.

The corrected route report SHA-256 is
`b83de4a8bc433c010ba13cc64c874323a3885947bfc75d579ee42dbbdd015948`.
Its saved executed qualifier source SHA-256 is
`ab8c3a56356872bf6eb5eabe2829b587e4e80ea458391dd6107357a5abd60ff2`.
The composed `baseline/native-enemy-interaction.png` SHA-256 is
`f03cf598b1ab2f2f27056c7a7427fdbecbd6b8a2d7094b067b53b6a1e78866d5`.
Inspection shows X held at the left, Zero performing the saber attack and a
hit/death burst at the right edge. The capture has actual present completion
sequence3/wrote1. It is a single interaction image, not a full art qualification.

The corrected route also retains 54 proximity-gap samples from ticks528..722,
with P2 distance111 down to40 while P1 remains272 away and the enemy stays in
action +5=1 before the hit. This is the v10 before case for the narrow targeting
fix. The native timer advances, but independent once-world runtime proof,
paired equivalence, audible behavior and the complete R13 row remain unverified.
The runner again terminated only its owned process after bounded quit handling;
no source card was used and existing private card bytes were unchanged.

The tool supports an explicit `--expected-exe-sha256` for the selected after
candidate and `--expect-targeting-action2` to require an actual origin-bound
native action2 observation while P2 is within112 and fixed P1 remains outside.
The comparison uses the native signed integer X halves, including the strict
112-pixel boundary, and captures the first observed action2 composed response.
Seven focused parser/preflight/comparison tests pass. The after-comparison
option was added after the v10 run and is not a v11 qualification by itself.

All run directories above are under `G:/Temp/Codex/psxrecomp/x6-parity`.
`docs/evidence/mmx6-r13/native-v10-route-summary.json` preserves compact receipts
for both actual route attempts; the full observations/logs/captures remain in
their identified output directories. No v11 result is implied by this evidence.

## Native v11 after comparison

The coordinator prepared a new immutable candidate at
`enemy-admission-r13-sdk9cb-v11-after`, executable SHA-256
`43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7`.
The tool's `--candidate` mode validates and uses a fresh existing preparation
without restaging it, and rejects existing qualification evidence. This run
used `--expect-targeting-action2` and the exact expected executable hash.
Its executed qualifier source is retained alongside it, SHA-256
`8f2238226dae172d3f6aef39b712349a217b615bb8e66e78972c6456ea7d5c83`.

Record25 was admitted at camera(51,944), tick454, and native initialization was
observed at tick473. P1 stayed x144 in all 197 case observations. At tick590 the
same origin-bound actor entered native action +5=2 with HP12 while Zero's raw
X was309.5: the native signed integer X values were enemy416/P1=144/P2=309,
distances272/107. This directly discriminates the fixed behavior from v10's
waiting action1 under the same near/far condition. The first response composed
capture has completion sequence3/wrote1, SHA-256
`33862cf795400063200ea0d3338543cf75bcbd784126a58a0a99a8557238b685`.
Inspection shows both heroes and a native attack/projectile response; the bound
enemy is beyond the right viewport edge at this camera position. This does not
qualify its complete animation/art or other native AI types.

At tick796, before original Square input, the exact actor was alive with HP12
and phase1. The recorded `native P2 attack interaction 0 start` at tick799
already had HP4/phase1, the same live slot/type/origin and P2 native action48 at
x376/y1082. By tick805 the slot was freed and the P2 hit counter was3. Both
heroes ended alive with HP32; P1 remained fixed. The final composed image
SHA-256 is `d28230cc86a84814ee3a8a742b19aca7620f28df5b549d5a5ef6c2c89b1e4ac5`.

The original report is preserved with status `failed`, SHA-256
`46d18e38fc8f8fba0782be0223d6525d449a116e4402024dad74aed2c280f944`.
Its attack reducer checked only the wait window's returned sample, overlooking
the already-recorded HP4 start sample before the enemy was freed. The corrected
reducer examines every post-input observation, requires a forward tick, the
same live native slot/type/origin and an actual HP drop. A regression covers
the observed HP12 -> HP4 -> freed sequence plus stale, dead, wrong-origin,
wrong-slot, wrong-type and unchanged-HP negatives.

No second v11 launch was needed. Separate read-only
`qualification-reanalysis.json` retains the original report hash and recovered
sample; SHA-256 `19f2c19181d0ff2cf6640ceb4a2631c1b7c74b03381eb49442762625502e8ac0`.
It is committed as `docs/evidence/mmx6-r13/native-v11-after-reanalysis.json`.
All twelve bounded local checks are supported by the retained observations,
including native action2 and the HP drop. The original runtime status was not
rewritten. Eight focused tool tests pass. The corrected reducer has been
exercised against the retained real report and unit fixtures, not a fresh game
run. Graceful shutdown remains unqualified: only the owned process was
terminated after bounded quit handling. Paired behavior and an independent
once-world runtime counter remain open; this does not pass the complete R13 row.
