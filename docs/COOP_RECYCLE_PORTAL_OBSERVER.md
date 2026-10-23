# R14 Recycle portal observation and setup gap

This lane supplies a **read-only observer**, source plan and conservative native
transition reducer. It deliberately stops before an automated accepted-input
route: safe source feet and a traversable approach have not been proved. It
does not grant an R14, destination, artwork or campaign pass. No game/title
build, launcher, pad injection, guest write, card change or ledger update ran.

## Authored setup

The frozen inventory SHA256 remains
`67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad`.
The helper verifies all 115 checkpoint records against the original USA v1.1
EXE, then verifies the original archive and selected source/destination members.
Its plan retains their actual SHA256 identities and code-window hashes.

| Role | Authored native record | Player spawn | Camera and bounds |
| --- | --- | --- | --- |
| Nearest source, stage4/sec0/CP3 | `80072468` | 1728,1456 | X1568/Y1440; X locked1568, Y locked1440 |
| Other possible approach, CP2 | `80072444` | 480,1456 | X320/Y1424; X320..1264, Y locked1424 |
| Portal, primary record18 | `800F2B0C` | Actor1552,1584 | Category0/type1C/subtype1; not a player foot position |
| Destination, stage20/sec1/CP0 | `80072FCC` | 79,224 | X0/Y224; X0..2576, Y locked224 |

CP3 is nearest by squared distance 47360 among the four authored source-section
checkpoints. Its source spawn is 176px right and 128px above the portal. That is not a
measured grounded position or proof of a safe 128px drop. Fixed camera limits,
the actual landing floor and whether the source portal is admitted from this
checkpoint still need native observations. CP2 is retained as an investigation
alternative, not an approved route. No position or movement sequence is guessed.

If root uses the existing private checkpoint helper for CP3, that remains a
disclosed, tainted prerequisite bypass. It cannot prove original reachability,
retry or campaign progression. Any later private positioning bypass needs the
same treatment. Original contact, action2, fade,41h, loading and arrival must
run through native code. Never write portal state, transition, success flags,
HP, native world clocks or simulation counters to make the check succeed.

The native 41h mapping is `8001E3D4 ->80042F7C`, mapping stage 4 to 20/1.
Major8 entry `8001E914` clears checkpoint at `8001E930` before major9's
initializer `8001E1BC`, giving the CP0 source expectation. Source member6 is
42,944 bytes at archive sector153; destination member28 is40,334 bytes at591.
The source member's controller/dispatch/collision windows and four exact
original/admission-state record variants are checked (byte0=0/1, byte3=00/10h;
all other bytes exact). Original scanner `80029EF8` produces byte3=10h before
allocation; see [the native entry follow-up](COOP_RECYCLE_CP3_NATIVE_ENTRY.md).
Destination code-prefix and native BIN descriptor
presence are only partial loading observations.

## API for the owning launcher adapter

New module: `tools/mmx6_coop_recycle_portal.py`.

```python
plan = portal.source_plan(original_exe, original_raw_bin)
native = portal.observe_native(owned_read_only_request)
publication = portal.observe_publication(owned_read_only_request, actual_diagnostic_address)
partial = portal.reduce_native_transition(native_samples_in_observed_order, plan)

# Optional report-retaining wrapper, one local process or two netplay peers.
case = portal.observe_context({
    "mode": "local",  # or "netplay", with two callbacks/addresses
    "candidate_exe_sha256": explicitly_verified_actual_image_sha,
    "read_only_requests": [owned_read_only_request],
    "diagnostic_addresses": [actual_diagnostic_address],
    "report": parent_owned_report,
}, expected_exe_sha256=explicitly_verified_actual_image_sha)
```

Callbacks must retain the baseline PID/listener ownership checks for the owned
process and expose `(command, **fields) -> response`. This helper only calls
`read_ram`; it never launches, owns, pauses, advances or controls a process.
The wrapper appends its report before reading and retains completed native
samples if a later publication fails. The owning runner persists reports and
artifacts through its normal failure/finally path.

`observe_native` makes **one** 412,344-byte read of `8008EF48..800F3A00`.
The existing SDK supports that bounded read and its hex response fits the
default 1MiB envelope. This uses the owned request callback directly because
`DebugClient.read` intentionally caps its convenience reads at 64KiB. The block
contains the native pool, resident body, primary camera, PLAY flags/namespace,
loader status, original portal record/tables/code windows and BIN descriptors.
Freed slots with stale origins are ignored; duplicate or incompatible live
origin claims are rejected. The resident body is labelled **resident character**,
not P1 or P2. Hashes identify the complete response and selected source windows;
the raw pool/body/record fields needed for analysis are retained.

`observe_publication` reads the complete schema 1 base publication once using
the existing strict parser. P1/P2 body fields, collision/resource pointers,
native ground-contact flags and scene ownership are coherent within that
publication. It contains neither portal actor nor actual stage/section/CP.

These two RPCs **cannot be joined into one same-tick actor/portal sample**.
Equal timers, unchanged publication counters or immediate consecutive reads
do not remove that limitation. In particular, a native sample's PLAYER may be
temporarily projected Zero. The observer never infers "P1 outside/P2 contact"
across those reads. It also leaves both-arrival, independent-control, accepted
input and completed-composed-capture checks false.

The reducer records only ordered partial native observations: source action1,
same origin/slot action2, freeze/saved-pointer,41h plus active fade, majors8/9,
then20/1/CP0 with source-derived camera bounds, matching descriptor/code prefix,
loader status2 and a healthy grounded resident. Missing states stay missing.
Even a complete such sequence remains `unverified_setup_gap`; one resident's
ground flag and descriptor/code presence do not prove completed streaming/GPU,
both actors, safe full-foot terrain, correct pixels or accepted controls.

## Next native check and validation

Root should first retain the actual CP3 initialization, collision-ready landed
bodies, camera, portal record admission/live origin, source code and composed
terrain view. Determine the legal approach using original collision/accepted
input observations. If CP3 cannot reach the portal, investigate the authored
CP2 path. Preserve failures instead of moving an actor to a guessed floor.
Only after that evidence exists should an accepted-input case be added with
neutral release in finally, actual transition/load observation, safe grounded
arrivals/resources and independent post-arrival movement for each seat.

The private-seat/portal joint-observation gap also needs an explicit solution
before contact attribution can qualify. An existing instruction-consumption
capture or a reviewed coherent observation extension may help; this lane adds
neither and does not infer their availability. Actual completed composed
captures and source art review remain the owning runner's separate checks.

Source-only plan (stdout, no output-file overwrite):

```powershell
python tools/mmx6_coop_recycle_portal.py --original <original-SLUS_013.95> --disc <original-raw-bin>
$env:MMX6_CONTENT_EXE='<original-SLUS_013.95>'
$env:MMX6_CONTENT_DISC='<original-raw-bin>'
python -m unittest discover -s tools -p test_mmx6_coop_recycle_portal.py -v
```

Set TEMP/TMP/PYTHONPYCACHEPREFIX to G/F first. Ten tests pass, including actual
original source reproduction and execution of the bounded native admission
leaf's instructions, all256 byte0/byte3 values, malformed/truncated
envelopes, duplicate/stale pool identities, torn publications, candidate binding,
retained partial failures and refusal to turn a synthetic complete native
sequence into a full qualification. The original-input route is unimplemented
because the safe terrain/approach contract is incomplete.
