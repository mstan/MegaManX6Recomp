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

## Actual result: setup rejected, no admission qualification

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
assertion, not a failed mechanic. The owner confirmed stopping further launches
in this lane and reviewing that source-derived guard centrally.

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
Before a future native case, review the preflight against the source scanner
predicate rather than requiring literal checkpoint camera0 after the baseline
movement smoke. Keep the existing setup rejection evidence. Enemy admission,
actual enemy interaction, composed art for
this case, paired equivalence and independent once-world runtime proof remain
unverified. R13 is not passed by this lane.
