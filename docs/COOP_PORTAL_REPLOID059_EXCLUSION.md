# Reploid059 beside the Recycle portal approach

This is a source-bound exclusion for one private offline setup, pending a fresh
native observation. It does not qualify collecting, rescuing or infecting a
Reploid, campaign progress, or the portal transition. The existing ledger and
the failed v17 native report remain unchanged.

The [source audit](COOP_PORTAL_REPLOID059_EXCLUSION.json) pins the original
SLUS-01395 v1.1 EXE, ROCK_X6.BIN and member6 hashes, plus13 exact EXE windows.
The frozen inventory identifies stage4/section0 placement32 at800F2B7C as
category4/type4/subtype59, authored position1360/1600. Its eight bytes are
`00043b0450054006`. Scanner80029F38 allocates category4 through
8007347C[4] ->8002C4C4, copies the record/type/subtype/position, then sets the
record's allocation bit at8002A254..264. The category<3 admission-state changes
do not apply to this record: the only admitted live record is
`01043b0450054006`.

The category4 update800205A0 traverses80 slots at800C1220 with strideA4 and
dispatches through[1F800094]. Stage4's EXE root[8006DF6C] is800F338C;
member6's type4 entry[800F339C] is8004F834. That function dispatches
phase0/1 through80078C7C to initialize8004E800 / idle8004EA78.

Subtype3B selects variant+84=0. Initialization zeroes velocity/acceleration
words+20/+24/+28/+2C, sets facing+15=0 and body-box+68=80078910,
then sets phase1/action0/eligibility+7=1. The exact box is `00000810`:
offset0/0, horizontal radius8, vertical radius16. Pointer8007891C contains
the same bytes but belongs to a different subtype class; it is rejected here.
Byte+82 selects facing animation and is not an infection flag.

Idle calls the animation/facing helpers, native collection8004EECC, then
offscreen/visibility helpers. These admitted idle callees do not move X.
Idle's explicit position write8004EBB8 only bobs Y when+7E=1; this helper
requires grounded+7E=0 and the exact authored current/previous position.
Eligibility+7=2 enters infection phase6; offscreen dismissal enters phase7.
Those states, healing/collection states, all motion and unknown variants
are rejected.

8004EECC **is** Reploid collection;8004E26C is a different pickup path.
On contact, Reploid collection writes native persistent state via
8004FF00(subtype,2), increments the native life count and may heal/refill
resources through8004ED4C. The actor is therefore not generally harmless.
8004EECC calls8002DCF4, which reads **body boxes at+68** for both objects.
It does not use the portal/damage boxes at+50/+54. The co-op pickup hook
tries native resident X and projected Zero, so both players must miss.

The narrowly admitted actual body boxes are X80073D50=`00020b13` and
Zero80073D54=`00030b13`. Both have horizontal offset0/radius11. With X
fixed at1506 and Zero restricted to1506..1695 during original held Right,
the Reploid's minimum horizontal center distance is146 versus strict contact
radius sum19, giving margin127. Vertical geometry cannot turn that horizontal
miss into contact. These finite coordinates also exclude signed16 wrap.
This proves a conditional contact exclusion for this exact state, not safety
for another actor, route, leftward input, infection, roster or campaign state.

`tools/qualify_mmx6_coop_recycle_portal.py` now retains fullA4 bytes for each
nearby category4 actor and the permitted Reploid's source record8 from its
existing single412,344-byte native read. It never dereferences an arbitrary
actor origin. The raw observer continues to mark this actor unknown.

After landing, the scoped recognizer requires every exact idle/source/box
condition, a separate owned **four-byte** read at fixed80078910, the actual
scratch-slot binding[1F800094]=800F338C, and unchanged critical actor state
across another full native block. Full raw blocks/actor bytes and both private
publications remain in the receipt. Animation bytes may change and stay raw;
critical identity, phase, eligibility, position, motion, facing and box changes
fail. The instance must remain the sole otherwise-unknown nearby actor.

The runner repeats the probe immediately before original P2 Right and rechecks
the critical actor, current owning private box and finite player bounds at
each subsequent source-world observation until actual portal activation.
The accepted box probe is immutable EXE data, retained with its explicit RPC
provenance. Native resident X/actor share one block; private players and box
probes are separate RPCs. The receipt does not imply same-tick private contact
attribution, per-frame tracing or continuous-frame coverage. Any missing,
changing or overlapping state stops and clears the owned input.

The [historical rejection capsule](evidence/mmx6-portal/reploid059-preflight-v17.json)
preserves report SHA
`bda7cb2698ac16324b159d9d6e0627b541982d1f34f2ddd8c36a8335c22ff8ba`
and exact executable SHA
`a8f20cdcc4ac68cdc76bf8fa7f1b3a74b9db67788514468743a355284b2080b8`.
It observed the matching metadata at800C12C4, but lacks the full actor,
live box and dispatch evidence. It still fails the new recognizer; no
retroactive pass or mechanic-failure claim is attached.

Validation:10 new tests and46 existing Recycle tests pass. These include
pure parser/negative fixtures, actual original source guards, execution of the
untouched original horizontal prefix for every1506..1695 coordinate under
three facing bytes plus strict-contact boundaries, and execution of the
original admission leaf proving category4's unchanged byte3. Set non-C
TEMP/TMP/PYTHONPYCACHEPREFIX and explicit read-only original
EXE/raw BIN paths in `MMX6_CONTENT_EXE` / `MMX6_CONTENT_DISC`, then run:

```powershell
python -m unittest discover -s tools -p test_mmx6_coop_reploid059.py -v
python -m unittest discover -s tools -p test_qualify_mmx6_coop_recycle_portal.py -v
```

No title build, game, production change, card operation or ledger pass was
performed in this lane. A fresh owned native trial must supply the new probes;
it may still stop on unsupported actual state or another unqualified actor.
