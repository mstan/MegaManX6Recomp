# Native same-build warm/cold snapshot baseline

`tools/qualify_mmx6_coop_state.py` stages two fresh private profiles and reuses
the baseline runner's native boot/input, listener ownership and process cleanup.
It supplies an optional baseline exercise callback rather than another boot
implementation. All controls are original pad input. It performs no guest RAM,
fixture mailbox, success-flag or source-card writes. Ports are 24893/24894;
launches are hidden with dummy output audio and explicit non-C data/cache paths.
No warm cache, native card or shader/overlay cache is copied into the cold profile.
Only the exact completed `.pst` snapshot is copied for cold restore.

The save/load request acknowledgement is insufficient. The qualifier samples
`savestate_status` before each request and requires a forward completion
generation, pending=0, last_ok=1, and matching operation/slot 8. The composed capture
helper separately samples `present_shot_seq` before staging and requires sequence
advance, wrote=1 and an actual artifact. Canonical screenshot output is retained
as a separate baseline probe; at 1x it can show software VRAM without GL banks.

## Measured candidate and result

The corrected local run passed twelve warm and thirteen cold checks, including
the reused intro/input checks. Its executable SHA-256 is
`bd7b9449d9fbc5c9c2137902ba2d8d525d1886211b03fd6756d0f76fbc9c263e`.
Both profiles were frozen from that exact candidate before launch.

Evidence root:
`G:/Temp/Codex/psxrecomp/x6-parity/snapshot-modern-v10-state-menu-ready-frozen`.
`qualification.json` SHA-256 is
`f8cc80175adb4fb0002f32e0884195762a48382274c03ec93b8a0bf4df477980`;
`evidence-summary.json` retains the principal receipts and artifact hashes.
The measured qualifier source SHA-256 is
`a634b17226db0576f3812d34bb571c59d0faef89e6ca12f1ba9bcbc4ea409611`.

Warm execution exercised P2 jump and Square attack (native actions 6 and 50),
expanding its retained sprite cache from 187 to 211 banks. P1 then opened its
native pause menu. The qualifier waited for the actual menu state at 0x800CF814
to reach 1 (observed bytes 1,0), not merely game phase 2. Save completed at
generation 1. After resuming, native P2 movement changed the actor position and
grew the cache to 212. Load completed at generation 2, restoring paused P1
ownership/menu state, all 348 bytes of each native body, and the saved 211-bank
cache. HP, ammo, weapon, position, action, character and active fields matched.

The fresh cold process booted normally and had 170 banks before loading. Its
privately copied 1,805,336-byte snapshot has SHA-256
`52453908781517fb1ad205ed0a85cd661a4b4d9ce74c4c3a52cb566da549bfed`.
Load completed at generation 1 with pending=0/last_ok=1/load/slot 8. Both full bodies
matched the warm saved bodies exactly and the retained cache became 211 banks.
Native menu resume, independent P2 movement and independent P1 jump all worked.

The restored composed warm/cold menu PNGs are byte-identical, SHA-256
`24e3f3de6621aea7c17488b43015065efa17300fa9ca6176db56dfea89510428`.
The cold continued-gameplay composed PNG is
`cold/baseline/cold-native-after-input.png`, SHA-256
`6e7f8b509c2975f316b9b6b7467a20edacb22e7c92f0e048272f5e9de63a44b3`.
Inspection shows clean X/Zero sprites, transparent backgrounds, both HUDs and
the native pause menu. This is composed GL evidence, not a claim from the
canonical software-VRAM capture or a count alone.

## Retained failures and limits

The initial `snapshot-modern-v10-state` attempt saved during the native menu's
opening/fade. Phase2 alone was insufficient: the close edge was ignored and the
capture was black. Its save and cold load did complete, with exact body matches,
but resume qualification failed. The one native retry adds the read-only menu
readiness gate already documented by `test_coop_pause_runtime.py`.

Before that retry, restaging from the live build detected a new executable
`fd4c2ccb...` and failed the expected-SHA guard without launching. That rejection
is retained under `snapshot-modern-v10-state-menu-ready`. The successful retry
uses the previously staged original build's exe/DLL/assets/catalog; it copies
none of its runtime caches, snapshots or cards while preparing the new profiles.
No older snapshot is loaded into the changed build.

Both successful processes responded throughout qualification but did not exit
within the baseline runner's quit deadline. Cleanup terminated only their owned
PIDs; receipts record `owned_process_terminated` and exit 1. Graceful shutdown is
not qualified. No process remains running from this lane.

This covers a healthy intro with HP 32, weapon 0 and the recorded full ammo values.
Spent ammo, damage, delayed healing, death/scene boundaries, moving terrain,
pending DMA, rewind and network state transfer remain unverified. Source-tree
observations are retained but do not establish binary compilation provenance.
No AOT performance or cross-build/OS compatibility claim and no ledger pass is
made. Four composed-capture protocol tests and three save/load receipt tests pass.

For reuse, supply an existing frozen build, the actual source/config root,
original disc, a new G/F output directory and its expected executable SHA:

```text
python tools/qualify_mmx6_coop_state.py --build <frozen-build> --source <source-root> --disc <original-cue> --output <new-private-output> --expected-sha <sha256>
```
