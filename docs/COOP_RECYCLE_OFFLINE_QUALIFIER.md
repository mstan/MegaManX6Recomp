# Owned offline Recycle portal qualifier

`tools/qualify_mmx6_coop_recycle_portal.py` implements one bounded offline
trial. Its first v17 native attempt stopped before placement because a cached
intro publication was mistaken for CP2 enrollment. That retained failure is
covered by `tests/fixtures/mmx6_recycle_cp2_stale_enrollment_v17.json`; the
corrected runner requires original CP2 landing and matching P1 observations.
Pure tests establish runner boundaries only. R14, rendered artwork, campaign reachability and netplay stay
unverified, including after automated observations complete.

The runner reuses the baseline's hidden muted process, listener/PID ownership,
private profile/cards, exception receipts, neutral input cleanup and owned
Quit/exit handling. It requires an unused prepared candidate or creates a new
automated candidate. Existing evidence is refused rather than overwritten.
The actual runtime executable must match the explicit SHA256. The runtime
original EXE and its single-track MODE2/2352 CUE/raw BIN must resolve to the
explicit source paths. Original EXE/archive, selected character banks, Recycle
and destination members, immutable inventory and DAT98 terrain are SHA-pinned
by the existing source helpers. This is bounded original-content verification,
not a whole raw-disc hash or proof of compilation provenance.

## The two disclosed prerequisite bypasses

1. Command8 requests original stage4/section0/CP2 initialization exactly once,
   with a fresh nonce and matched generation/source record/taint receipt. A
   completed initializer is **not** ordinary checkpoint readiness.
2. Command4/seat2 writes both position and previous-position pairs at the
   plugin's existing atomic boundary. No HP, action, ground, locks, clocks,
   source records, success flags, destination or guest-call command is issued.

Before requesting CP2, the runner settles actual intro idle heroes, reads one
coherent X6BX publication and verifies their exact current damage/body box
bytes against the explicit original owners. It derives a conditional common
miss interval using the source calculator. With the published source reference
boxes this is x1489..1523, midpoint1506, airY1593. The code uses the **computed**
result, not a hardcoded1506 or guessed1530.

After the initializer receipt, original X must land at CP2 and native
enrollment must become1 before relocation. Enrollment initializes Zero at
X+24; placing both before enrollment could therefore be overwritten to1530
and accidentally contact the portal. P2's phase1/action0 and null damage
pointer while entering are permitted native states. A null pointer remains a
no-contact gate; unavailable bytes for a nonnull pointer are rejected.
The destination uses the same original incoming-beam lifecycle. The first
source-qualified portal approach reached native action2, fade41h, majors8/9
and stage20/section1/CP0, then exposed a wait that rejected JOINING3. The
retained destination fixture now requires observing that state and waiting
for original living idle completion; it grants no arrival or control pass.
The initializer can finish while diagnostics still contain the intro's
enrolled idle bodies. The helper therefore separately observes actual CP2
namespace/source code, fade/entry-lock clearance and native idle X at the
authored x480, then requires agreeing published P1 position/HP. These remain
separate RPC observations, without a claim of cross-command atomicity.
The fresh CP2 publication initially reports lifecycle `(0,3)`: `enroll`
calls `begin_join`, and `join_animation` completes the native incoming beam
before `mmx6_coop_teleport_done` changes Zero to ALIVE. The next retained v17
attempt exposed that legitimate intermediate state. The wait accepts JOINING
only while observing entry, and returns after both lifecycles are ALIVE and
Zero's original terrain-box pointer is available. No fixture command is sent
to finish the beam; absent, leaving, failed or dying actors still stop the trial.

Before position commit, the runner verifies the exact original528-byte live
layout, scratch pointers80097438/8019A4B0/801AF8B0, complete87,040-byte
metatile and8,000-byte descriptor arrays, source member/record variants and
current terrain boxes. Unknown allocated category0/4 actors in the bounded
nearby rectangle cause an unverified stop; only the portal, origin-bound
capsule and its exact parent-linked child are recognized. This conservative
check is not a complete general dynamic-hazard detector. Before committing
command4 after its payload writes, it obtains a fresh coherent publication
and refuses dying/absent/menu/scene/un-enrolled heroes or an entry body outside
the current1424..1664 vertical view. It never relocates a dying partner based
on a cached pre-asset sample.

The separate command and publication RPCs cannot make a debugger transaction
atomic with the next native frame. Position application itself is atomic
inside the plugin. Its completion, original landing and subsequent enrollment
are observed rather than inferred from the write ACK.

## Landing, actual boxes and original portal route

Neutral observations must establish both living, visible, grounded idle
heroes; clear shared entry/menu/scene/freeze gates; stable current/previous
positions; settled original camera1264/1424; and actual initialized capsule
origin800F2E24 phase1/action0 plus portal800F2B0C phase1/action1. Both X
positions must equal the disclosed solver center. The ordinary authored CP2
X480 predicate remains false and is retained as a bypass, never relaxed into
a checkpoint pass.

The helper then revalidates actual **current** idle boxes and recomputes the
miss interval using the live capsule position. X6BX resolves private Zero's
box bytes from its real owning bank. The runner never dereferences a Zero
overlay pointer through resident-X RAM. It requires the original native X and
Zero terrain boxes and source-backed byte equality for every nonnull current
damage pointer. If an expanded/unknown pointer or changed shape cannot be
proven against the bounded sources, it stops.

P1/portal/capsule coordinates from one native block feed the original51924
and2D654 arithmetic to require resident P1 outside both triggers. Original
portal geometry pointers, source bytes and native actor initialization are
checked. The same P1 miss guard runs again immediately before holding P2
Right. Initial composed capture completion requires actual renderer output;
its ACK is insufficient.

P2 Right uses the original host-pad `press` route with frames0, held only
until portal action2/owner2 evidence or the24-world-tick/179-publication and
wall-clock bound. It always clears input in `finally`. The source reducer
retains requested and observed counter deltas; RPC polling can overshoot a
requested window and is not an exact native-frame input trace. The reducer
requires retained original portal action2, freeze/saved native box,41h plus
fade, major8 then major9 and actual stage20/section1/CP0 resident loader/
camera/ground/resource conditions. Missing short-lived states stay missing;
there is no inferred successful transition or retry. Unexpected P1 scene
ownership stops the trial.

At the destination, both published bodies must be living, visible, stable
native idle/grounded heroes with actual box and render resource pointers.
Three-world-tick Right windows separately exercise each seat: the selected
hero must move and the other position must stay fixed. Completed composed
captures are retained at source readiness, destination readiness and after
independent controls. Visual review still decides terrain, actor, palette and
resource appearance; memory/pointer/ACK checks do not approve rendered art.

Native actor/camera blocks and X6BX player publications are separate RPCs.
The report preserves their individual hashes, bodies, labels and order; it
does not manufacture exact native-tick fusion or prove an exact instantaneous
P1-outside/P2-contact collision from them. Owner2 plus the ordered native
route are retained evidence with that attribution limit. Even the success
status is `offline_portal_observations_complete_artwork_and_contact_attribution_pending`,
with `ledger_status=unverified` and `artwork_review=pending`.

## Invocation and pure validation

Root owns all native execution. A future reviewed invocation for an unused
automated private candidate is:

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/<task>/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/<task>/pycache'
python tools/qualify_mmx6_coop_recycle_portal.py --candidate G:/<fresh-private-candidate> --original-exe G:/<original>/SLUS_013.95 --original-disc 'G:/<original>/Mega Man X6 (USA) (v1.1).bin' --expected-exe-sha256 <actual64hexSHA> --port 24908
```

Alternatively supply `--build`, `--source`, runtime `--disc` and fresh
`--output` instead of `--candidate`. Entry/transition and progress deadlines
are bounded CLI values. The new runner never changes an existing report or
frozen inventory. Baseline output stays under `baseline/`; the additional
top-level qualification report binds that original receipt's SHA and status.
Partial cases, asset mismatches, native samples, private publications, input
release errors and owned shutdown remain available after failure.

Pure runner tests require no source disc, runtime process, build, sockets or
cards:

```powershell
python -m unittest discover -s tools -p test_qualify_mmx6_coop_recycle_portal.py -v
```

They cover exact position payload/command ordering; online/pending/invalid
command rejection; last-moment death refusal before commit; initializer
nonce/generation versus readiness; native null damage and wrong private-bank
provenance; capsule/portal misses; full asset mismatch and unknown actors;
original enrollment; held-input release/counter/scene/error behavior; missing
transition evidence; strict options/CUE binding; and preservation of prior
candidate evidence. No native success follows from these tests.
