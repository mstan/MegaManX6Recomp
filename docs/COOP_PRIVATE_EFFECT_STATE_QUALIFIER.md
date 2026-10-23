# Current-build private effect snapshot qualification

The state runner has an explicit `--private-effects` case. Its implementation
and pure protocol tests are complete; native warm/cold execution and composed
artwork review are **unverified**. The existing body-only command and its
historical bd7/37 receipts in [COOP_SNAPSHOT_BASELINE.md](COOP_SNAPSHOT_BASELINE.md)
remain separate and unchanged. No ledger row is passed by this addition.

```text
python tools/qualify_mmx6_coop_state.py --private-effects --build <frozen-build> --source <source-root> --disc <original-cue> --output <new-G-or-F-directory> --expected-sha <exact-executable-sha256> --progress-timeout 12
```

`--private-effects` requires a lowercase 64-digit executable SHA256. Both
profiles must contain that exact image, matching DLLs, original assets, BIOS
and bundled catalog files. Preparation reuses the normal default loading
configuration. It copies no warm cache, settings, native cards or earlier
snapshots. The only transfer into the cold profile is the exact newly saved
slot8 `.pst`, whose private relative path, size and SHA256 are retained.
All generated files must stay on F:/G:. The caller must also set its Python
cache and process TEMP/TMP off C: before invoking the runner.

Both launches reuse `baseline.run(..., exercise=...)`: its hidden, muted native
boot, private profiles, listener/PID checks, accepted controls and owned-process
shutdown remain authoritative. Debug ports are 24893/24894, one process at a
time. A warm failure stops before the cold launch and remains in the report.
No game or title build was launched while implementing this case.

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
current X6 offline provider `mmx6.local-coop`, schema 1. That reader never applies
state, and rejects unsupported schemas, truncation, duplicate sections,
noncanonical provider IDs, unbounded inflate requests and malformed bank
records. It is not a replacement for the SDK's full transactional loader.

The probe compares the complete 9366-byte semantic host core, including private
body/shots/pools, lifecycle, Select history, previous input, edges, Start history,
menu state/backups, pickup/contact/death ownership, and the original asset and
allocation binding. Native body+7C/+7E/+80 and serialized host input/edge/Start
values are also recorded explicitly. The only excluded core tail is the
documented 10-byte publication/presentation data: frame_count, hud_fade,
world_packets and hud_seat. No simulation field is normalized. Original and
probe PST build keys and provider IDs must match. Full compressed sprite pixel
and UI bank payloads, not just their counts, must match exactly.

The warm process first resumes and naturally retires the original effect pools
and moves P2 before loading, establishing a changed state. The cold process
must begin with retired effects and fewer retained sprite banks than the saved
image. Its post-load probe must reconstruct the saved full cache payload.
Completed composed captures retain warm/cold restored frames and later native
gameplay for visual review; capture completion or cache equality alone does
not approve texture reconstruction on screen.

After each restore, original P1 Start must resume native gameplay. Observations
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

The automated success string is
`automated_private_effect_state_checks_passed_artwork_pending`; artwork and
ledger status stay pending/unverified. Partial cases preserve `failed_setup`
or `failed_behavior`, operation receipts, input brackets, published bytes,
safe-boundary snapshots, probes, hashes and errors. A failure is not
automatically a game defect. Current-build snapshots are disposable: no older
image is migrated or loaded into a changed image. Network state transfer,
rewind, rollback, opposite roster, other campaign locations, cross-build and
cross-machine behavior remain unqualified.

Validation: 22 pure tests pass (19 new private-state cases plus 3 existing
save/load receipt cases). They cover stale/torn publications, raw/compressed
framing, hidden input/pool changes, wrong bank IDs/content, unsupported
schema/build/asset bindings, source-card rejection, bounded CLI values,
failed-warm retention without a cold launch, positive continuation and
negative-drain evidence, all-slot retirement, stalled clocks and transient
HP/P1-position changes. A read-only inspection of the retained historical bd7
snapshot also identified 211 sprite banks, 6 UI banks and provider tick 369; its
saved native P1/P2 bodies match that historical published receipt. This checks
the reader against an existing artifact, not the new private-effect mechanic.
