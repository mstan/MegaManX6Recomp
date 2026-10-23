# X6 Zero/P1 + X/P2 implementation sequence

The current implementation supports a fixed X/P1 + Zero/P2 resource model.
**Zero/P1 + X/P2 remains unimplemented and unverified.** Removing the native
Zero selection filter would enroll a second Zero; it would not create X/P2.
The smallest useful expansion is native Zero/P1 with **base X/form0/P2**,
preserving native availability and campaign ownership. Other X forms and
Black Zero need separate native resource/behavior checks.

This is a read-only follow-up to the [seat/character audit](COOP_SEAT_CHARACTER_AUDIT.md)
at game commit `6c42c5c`. The [source record](COOP_OPPOSITE_ROSTER_PLAN.json)
pins complete Git commits/blobs/SHA-256, bounded original instruction windows
and four portrait records. No plugin, SDK, CMake, comparison ledger or runtime
behavior changed. No title build, game, card or save was opened. Frozen X4
`50593bca` and X5 `9ed460e7` are design references, not inherited passes.

## Exact current restrictions

| Integration point at `6c42c5c` | Current behavior | Required opposite-roster change |
| --- | --- | --- |
| `unit_choices`, plugin184..205; replacement800E9898 | Calls the guarded BIN16 builder once, removes form5 from list800F1CB0/count800F1CEB. Unlock/parts flags remain intact. | Keep the filter until the complete counterpart path exists. Then allow native unlocked Zero; never grant unlocks or change native confirmation. |
| Package manifest; `native_player_init`1156; `controller`1168 | Package has only prototype and HUD-layout settings. There is no roster choice and no independent runtime rejection of a Zero campaign body. Init/controller otherwise use native phase/seat gates. | Derive campaign character/form from the initialized native body and campaign fields. Reject inconsistent/unsupported descriptors before private initialization. No extra character setting is needed for an automatic opposite/base-X policy. |
| `load_assets`235..294 | Loads BIN1/type3D, DAT85, Zero portrait165/166 and a single retained UI plane. | Select a validated immutable resource descriptor for Zero5 or baseX0. X uses BIN0/type3C and DAT86; it cannot pass the current hardcoded type3D check. Check complete aligned allocation bounds, not only a sum of source lengths. |
| `enter_zero`295; `leave_zero_context`321 | Copies full body/pools, swaps the B000-byte overlay and seven scratch pointers, forces PLAY+38=1/+5E=5. Shared-world exit preserves shared mutations but restores campaign identity. | Generalize the projected actor's character/form/resources, retaining exact campaign identity, original overlay and resource restoration. Keep the existing shared-world versus private-call distinction. |
| `enroll`450 | Initializes P2 through original8003BD24, parts8003D718, physics8003D630 and idle8003AD18 under Zero identity. | Run these original helpers once under the validated opposite descriptor. Base-X form0 is explicit; Zero's form5 is not an X armor choice. Verify character-indexed native equipment/HP/ammo rather than copying Zero inventory. |
| `pickup_as_seat`349..369 and callers | For seat1 writes character1/form5; seat0 uses saved campaign identity. | Look up the collector's descriptor while preserving existing delayed-heal and shared soul/progress ownership. Body projection alone does not fix character-indexed PLAY reads. |
| `menu_vram`1004; stage1111/1149 | Boolean `zero_menu_loaded` uploads retained Zero menu/font/portrait pages and restores captured campaign pages. Pause authority already uses seat. | Exchange the selected counterpart's native resources. A Boolean can still mean private versus campaign pages for this two-roster scope; it must cease meaning character Zero. Keep native menu input, shared clock, campaign Quit and native shared lives as seat rules. |
| `draw_coop_hud`1743; `hud_tile_bank`1650 | P1/boss draw once; P2 installs fixed Zero assembly/menu, calls800249D4 and samples `zero_ui_pixels`. | Choose X800246B4 or Zero800249D4 from character; use matching menu/icon palette and retained pixels. Retain primary-only shared-life display, packet ownership and current fades. |
| `sprite_bank`1273; `render_actor`1374 | Ordinary retained pixels come from immutable Zero graphics; the special `render_x_death` path reads resident RAM and saved campaign palette. | Use explicit retained resource identity for private X as well as Zero. Preserve decoded-content validation for mutable resident sources and distinguish form/archive generation when virtual addresses repeat. |
| `render_survivor`1457; scene/lifecycle callers | Seat rules generally work through projections, but stored P1's survivor/death draw uses `render_x_death` and the resident saved palette. | Replace the character assumption with an actual actor/source descriptor. Test Zero/P1 death/passenger art while X/P2 owns the one native world pass. Keep all existing absent/leaving/joining/fallen distinctions. |
| `snapshot_assets_loaded`/`snapshot_ready`/resource codec | One Zero source hash, one graphics/UI allocation, Boolean menu owner; digest already covers actor pools and projected backups. | Bind canonical roster/form/resource generation to digest and current-build serialization, readiness and cold retained-resource reconstruction. No host pointers on wire; old states may be rejected. |
| `activate`, compatibility/profile/catalog | Rematch frees Zero source/UI buffers while immutable banks persist. Profile is `mmx6-x-zero-delay-v12`, lab revision2. | Reset descriptors and stale menu/projection state; preserve cache identity across roster changes. Update title/source/declared-image/profile contracts and requalify the changed artifact; retain rollback0/states0. |

Names such as `zero_world`, `zero_projected` and `zero_solid_contacts` currently
mean private seat1 in many branches. Renaming them without changing their
contracts is useful cleanup but does not prove opposite-character behavior.
The full context already owns body158h, shots1400h, trails120h and effectsF0h.
No second enemy, world, camera or shared clock pass is needed.

## Original X6 resources and character semantics

The original character loader80013BF0..80013D10 selects BIN0 for character0,
BIN1 for character1, both at801EA000. Character0 forms0/4 use DAT86; forms1/2/3
use DAT87/88/89. Zero is character1/form5, DAT85. The existing native audit
pins all five player bundles and their subassets; the addresses and form IDs
are X6 facts, independent of X4/X5.

Original8003BDE8/8003BE10 transfers PLAY+38 to PLAYER+2.
8003D730/8003D73C transfers PLAY+5E to PLAYER+E7. Parts come from
PLAY+74+character*4; earned weapons from PLAY+60 (with native Shadow
restrictions). Fresh HP and energy use PLAY+5B+character and PLAY+61+character.
Current HP, weapon, ammo and charge state stay with each actor; an ordinary
menu, door or voluntary rejoin must not refill them. Enrollment and native
checkpoint/retry are separate initialization contracts.

For portraits, the original selector800228AC..80022928 returns baseX0,
Zero1, Ultimate2, Falcon3, Shadow4, Blade5, or BlackZero6 from PLAY identity,
form and bit20 of PLAY+5F. Loader80014314 calls that selector;
80014324..80014334 requests **DAT163+2*index**;80014384..80014394 requests
**DAT164+2*index**. Thus base X uses163/164 and ordinary Zero uses165/166.
The actual record-loader8001642C..8001651C indexes the DAT table800E0398
by record*8. Four bounded original records were re-read: graphics8192 bytes,
palette512 bytes for each character. Only metadata/hashes are committed.
The native Black Zero variant remains an explicit gap: fixed Zero165/166 is
not a valid blanket portrait policy when the native selector returns6.

Stage-specific character COL palettes, working palette composition, fades,
dash CLUTs and menu writeback must be checked against original X6 loaders
before an opposite-roster release. DAT0's base palette alone does not establish
that closure. Preserve shared stage colors when the private actor owns a
scene/world pass; X4's exact COL bytes and offsets do not apply.

## X-only attached effects and deferred work

The [R9 native closure](COOP_R9_EFFECT_CLOSURE.md) maps the original fixed
pools and accepted action predicates. Current source has since implemented
private updates in original order: body80034DCC, shots8002012C,
contact8002F288, attached80020D74, trails80020DC8, within one projection.
The retained draw includes body, **character0-only** attached slots,
trails2/1/0 and32 shots. Its character test already matches native80022960;
it must remain a character predicate, not become `seat==1`.

Three trails at800972F8 have stride60 and projected native parent links.
Two ordinary attached slots at800911A8 have stride50; a third slot80091248
is initialized only for Falcon form1. Original charge levels are body9B/9C
and timers9D/9E; the native producer, release and action-interruption paths
must remain intact. Attached common art uses compression0 and native assembly
relative offsets; immutable retained body graphics are not their whole source.
Existing actual-plugin fixtures check call/projection/render wiring with
bounded native-helper models. They do not execute original X charge routines
or qualify X/P2, either roster, art, audio or retirement in gameplay.

Shared deferred effects need a separate allocating-owner audit. Current
`DeathEffectOrigin` retains x/y/layer/assembly at two death return sites;
it does not retain a general character/form/palette descriptor. Frozen X4's
X/P2 deferred effects demonstrate why reading restored Zero/P1 can delete a
beam or bind a Zero shot to an X-only decoder. Those exact X4 types are not
proof of corresponding X6 effects. Audit original base-X charge/projectile,
dash, hurt/death and shared secondary producers before broad opposite-roster
claims; add only source-backed owner projection at their actual late reads.

Audio is another concrete dependency. Current `load_assets` does not install
the counterpart's VAB or project sound-record pointers. Under Zero/P1 the
ordinary loader's resident character audio changes, while base X/P2 makes
group1 calls (including charge id7). The existing
[driver audit](COOP_AUDIO_DRIVER_OWNERSHIP.md) remains adapter-disabled:
record17's group3 alias, stride38, queued key-on/key-off/volume state,
asynchronous VAB completion and conditional flush callbacks cannot be omitted.
Symmetric graphics alone must not be described as complete roster support.

## Frozen designs that transfer

X4 `mmx4_coop_plugin.c`257..281 uses `CharacterAssets[2]`;466..476 derives
`counterpart=PLAYER[2]^1`, validates both resources and loads the counterpart's
stage palette. X's variant/code flag is separate from native campaign/seat.
`mmx4_coop_combat.c`413..454 projects the allocating owner for late native
effect reads, explicitly handling X/P2 while Zero/P1 has been restored.
`mmx4_coop_lifecycle.c`1459..1488 also preserves shared stage palette work
while projecting an actor for story behavior. Use these ownership rules,
not X4 pool strides, addresses, stage IDs or passed checks.

Committed X5 `mmx5_coop_plugin.c`49..78 distinguishes character resources,
immutable DAT source records and generation-tagged sprite banks.
525..560 projects counterpart identity separately from form, and preserves
campaign identity on shared-world exit.1065..1111 validates actual native
character, derives its opposite and invokes the native initializer/parts
helpers.3881..3938 chooses the HUD entry by counterpart character and uploads
that descriptor's native UI pixels for the owned menu. This is committed
implementation evidence only; no X5 WIP or gameplay pass was imported.

## Smallest correct sequence

1. Add a validated canonical roster descriptor resolved after native P1 init:
   native X/form0..4 -> private Zero5; native Zero5 -> private baseX0.
   Preserve actual P1 selection and shared unlocks. Separate seat, character,
   form, immutable archive identity and campaign authority. Reject inconsistent
   identity; do not enable the Zero selector yet. Explicitly refuse an active
   unsupported Black Zero variant until its original resource/behavior closure
   is covered; never clear the player's persistent bit to fit the first slice.
2. Generalize resource loading/projection and native enrollment for the two
   counterpart descriptors (Zero5/baseX0). Cover complete aligned guest/host
   allocation bounds, correct BIN type, native character-indexed resources,
   exact overlay/pointer restoration, both shared/private exits and abandoned
   callback guards. Keep one shared world and existing input boundaries.
3. Generalize pickup identity, HUD, menu/portrait pages, immutable pixels,
   resident death/survivor rendering and cache/rematch identity. Trace native
   stage palette composition and base-X shared deferred effects; close the
   required audio residency/queue ownership before calling the roster complete.
   Keep fixed-pool update/draw gates native and prove X/P2 charge/release,
   dash, owner retirement and no cross-seat contamination.
4. Extend actual-plugin fixtures and current-build digest/snapshot validation
   alongside each change: both directions; invalid descriptors; distinct
   spent HP/ammo/weapons; both menu owners; native init once; world once;
   pool/overlay/resource restoration; death/survivor/scene; rematch direction
   changes; cold retained sprite/UI reconstruction. Reject old schema freely.
   Fixtures remain helper evidence, not native behavior qualification.
5. After these dependencies, retain original native unit availability while
   removing only the co-op Zero exclusion. Record the roster policy in title
   compatibility and actual build/profile identity. Fresh offline and same
   physical-machine pair receipts must cover native unlocked Zero selection,
   first X/P2 enrollment, independent controls, attacks/contact, both owned
   menus, resource retention, both deaths/retry and normal stage transitions.
   Capture original art and muted audio evidence. Keep every unsupported form,
   audio condition and mechanic explicitly unverified; no rollback/state-save
   enablement follows from this work.

No new selectable roster option is necessary for that first policy. A later
agreed X/P2 armor choice would expand resources, action/deferred effect closure,
menus, identity and native qualification for every chosen form. It should not
be inferred from a previous X campaign body after native Zero selection.

Verification here consisted of frozen Git source/metadata checks, SHA-256 and
direct bounded original instruction review, plus selected portrait record
hashes. No runtime tests ran and no R8/R9 or other comparison changed status.
