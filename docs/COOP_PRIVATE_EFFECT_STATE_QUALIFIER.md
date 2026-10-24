# Current-build private effect snapshot qualification

The explicit `--private-effects` case passes bounded native warm/cold checks
on candidate `22ea525`, image `4b31864f...`, with current internal wire 3.
The [reviewed receipt](evidence/mmx6-private-state/manifest-bound-22ea525-reviewed.json)
retains 36 warm and 37 cold checks, the actual saved state and restored probes,
completed composed captures, source identities and normal owned exits0.
Both private memory cards remain unchanged. **F33 remains unverified**:
actual mapped save/load/rewind controls, active private audio restoration,
rollback and native malformed-state rejection are outside this run.
The body-only command and its historical bd7/37 receipts in
[COOP_SNAPSHOT_BASELINE.md](COOP_SNAPSHOT_BASELINE.md) remain separate.

```text
python tools/qualify_mmx6_coop_state.py --private-effects --build <frozen-build> --source <source-root> --disc <original-cue> --output <new-G-or-F-directory> --expected-sha <exact-executable-sha256> --expected-manifest-sha256 <exact-manifest-sha256> --progress-timeout 12
```

`--private-effects` requires lowercase 64-digit executable and manifest SHA256s.
The actual staged images must carry the expected compiled manifest, and its
declared game and generated source files must match the supplied roots. Other
dependency roots are bound by the retained candidate compilation proof rather
than rehashed by this runner. Both
profiles must contain that exact image, matching DLLs, original assets, BIOS
and bundled catalog files. Preparation reuses the normal default loading
configuration. It copies no warm cache, settings, native cards or earlier
snapshots. The only transfer into the cold profile is the exact newly saved
slot8 `.pst`, whose private relative path, size and SHA256 are retained.
This task retains outputs under `G:/Temp/Codex/psxrecomp/x6-parity`; process-local
TEMP/TMP and cache paths bound temporary output. C: is also permitted for bounded
temporary work under the owner's current storage policy. Preserve referenced
evidence while work continues and remove obsolete disposable output when done.

Both launches reuse `baseline.run(..., exercise=...)`: its hidden, muted native
boot, private profiles, listener/PID checks, accepted controls and owned-process
shutdown remain authoritative. Debug ports are 24893/24894, one process at a
time. A warm failure stops before the cold launch and remains in the report.
The current receipt records two sequential native launches against the same
existing frozen build; the inspector update does not change the executable.

The setup uses the source-backed native Circle mask0x2000 with Left through
`OfflineMenuAdapter`'s persistent original input, not the private mailbox or
direct RAM/SIO writes. A successful input acknowledgement cannot qualify a
dash. The coherent extension must actually show a positive native PLAYER+8C
marker and three allocated, visible, active phase0 native trails. While that
input remains held, original P1 Start opens its own native menu. The case waits
for native phase 2, P1 ownership and CF814 first-byte 1; the second byte is not
assumed. If ordinary menu flow cannot retain the chosen positive effect window,
the case fails setup. This is a native paused live-pool snapshot, not an
unpaused arbitrary-instruction save qualification.

At least three distinct coherent publications must retain the full private
body, shots, all three 0x60-byte trails, all three 0x50-byte attached records,
native held/previous/edge words, personal resources and frozen native clock.
Only the existing read-only1C20 extension is observed. No callback creates a
new simulation counter, changes a guard or forces snapshot readiness.

Save/load requests require the existing completed `savestate_status` contract:
forward generation, pending 0, last_ok 1 and the exact operation/slot. The first
coherent observation after a completed load becomes an anchor; it cannot itself
qualify restored state. A subsequent publication must advance beyond both that
anchor and the saved provider's publication count. Its full private body,
shots, trails, attached pool, native input words and native P1 body must match
the actual saved image, with the same input-ready P1 menu and positive window.
The state must then survive another three-publication frozen observation.
This rejects cached pre-load publications even when they are newer than the
original request.

The qualifier also makes a second **completed native save** to private slot7
after each load. This is a read-only probe of what the current provider now
serializes. It inspects the PST v10 section framing, MSNP v1 records and the
current X6 offline provider `mmx6.local-coop`, provider interface 1 and internal
wire 3. That reader never applies
state, and rejects unsupported schemas, truncation, duplicate sections,
noncanonical provider IDs, unbounded inflate requests and malformed bank
records. It is not a replacement for the SDK's full transactional loader.

The probe compares the complete 9390-byte semantic host core, including private
body/shots/pools, lifecycle, Select history, previous input, edges, Start history,
menu state/backups, pickup/contact/death ownership and all 24 persistent private
audio priorities. The 88-byte resource binding includes the original asset and
allocation identity. Native body+7C/+7E/+80 and serialized host input/edge/Start
values are also recorded explicitly. The only excluded core tail is the
documented 10-byte publication/presentation data: frame_count, hud_fade,
world_packets and hud_seat. No simulation field is normalized. Original and
probe PST build keys and provider IDs must match. Full compressed sprite pixel
and UI bank payloads, not just their counts, must match exactly.

The current 6652-byte private-SPU section is also inspected. Each private voice
contains its own interleaved 64-bit owner tag; these are not a trailing array.
Exactly the nine reserved X6 slots must retain owner `0x4D4D583650320001`.
Warm/cold probes compare every private owner, mode, register and bank binding.
The observed saved snapshot contains **no active private voices**, and its
24 priority bytes are zero. Thus these native results qualify inactive lease
preservation and those actual priority values only. Advancing DSP positions,
envelopes and clock phase are recorded without normalizing them into equality
across later native saves. Active playback and nonzero native-priority restores
remain unverified.

The warm process first resumes and naturally retires the original effect pools
and moves P2 before loading, establishing a changed state. The cold process
must begin with retired effects and fewer retained sprite banks than the saved
image. Its post-load probe must reconstruct the saved full cache payload.
Completed composed captures retain warm/cold restored frames and later native
gameplay for visual review; capture completion or cache equality alone does
not approve texture reconstruction on screen.

After each restore, original P1 Start must resume native gameplay. Observations
retain the original closing interval. `stage_tick` chooses owner at entry, calls
the original menu and publishes afterward; that call can change phase2 to0
before the next entry clears the owner. One distinct phase0/P1-owned closing
publication is retained and excluded from gameplay recovery. A second distinct
one, ownership returning after gameplay, changed resources/roster/P1 position
or a failure to reach owner-free gameplay is refused. This corrects the retained
v12 warm retry's pre-load mutation false failure; it does not qualify save/load.
Observations
retain positive post-release dash continuation separately from the first
negative-marker drain. Native phases 1 and 2 must be observed, followed by
marker 0 **and every trail inactive/invisible**, within 32 native timer ticks of
the first observed negative marker. A positive continuation may last up to
the bounded 120-tick observation window; neutral does not itself start the
retirement bound. These are observed native timer bounds, not an independent
once-world proof. This finite phase1/2 retirement contract belongs to the three
dash trails; attached records are restored byte-for-byte without claiming every
attached-effect lifecycle. Original P2 Right must then move Zero while X stays fixed.
Both heroes' HP/ammo/weapon values and the actual private native card hashes
must remain unchanged.

The automated success string remains
`automated_private_effect_state_checks_passed_artwork_pending`; artwork and
ledger status in the raw report stay pending/unverified. Review is recorded
separately. The current warm/cold restored menu captures are byte-identical;
the menu matches the before-save capture apart from the status toast. Resumed
captures show the intro scene and both meters without observed cache damage.
The overlapping actors and menu-hidden effects do not establish separate
character artwork or active-trail colors. Partial cases preserve `failed_setup`
or `failed_behavior`, operation receipts, input brackets, published bytes,
safe-boundary snapshots, probes, hashes and errors. A failure is not
automatically a game defect. Current-build snapshots are disposable: no older
image is migrated or loaded into a changed image. Network state transfer,
rewind, rollback, opposite roster, other campaign locations, cross-build and
cross-machine behavior remain unqualified.

Validation: 26 pure state tests pass (23 private-state cases plus 3 existing
save/load receipt cases). They cover stale/torn publications, raw/compressed
framing, hidden input/pool changes, wrong bank IDs/content, unsupported
schema/build/asset bindings, source-card rejection, bounded CLI values,
failed-warm retention without a cold launch, positive continuation and
negative-drain evidence, all-slot retirement, stalled clocks and transient
HP/P1-position changes. A read-only inspection of the retained historical bd7
snapshot also identified 211 sprite banks, 6 UI banks and provider tick 369; its
saved native P1/P2 bodies match that historical published receipt. This checks
the reader against an existing artifact, not the new private-effect mechanic.
The current suite also rejects internal wires 1/2/4 and ownerless/truncated
private-SPU layouts, and detects priority, owner, register, mode and bank
differences independently. All 196 selected state/audio/input Python checks pass.

Historical receipt: the exact frozen v12 executable `229ffec7` passed native warm and cold
cases: 31 warm checks, 32 cold checks, unchanged private cards, acknowledged
Quit and natural exit0 for both owned processes. Root independently reviewed
all six completed composed captures: the original menu remains intact and
resumed X/Zero bodies and meters show no observed retained-bank corruption.
The compact [reviewed receipt](evidence/mmx6-private-state/manifest-bound-e2e47e6-reviewed.json)
binds the original report, snapshot, post-load probes, images and compile proof.
It leaves the original artwork-pending report unchanged. This bounded
current-build save/load result does not pass rollback, rewind, network state
transfer, active-trail colors, the campaign or a complete parity comparison.
