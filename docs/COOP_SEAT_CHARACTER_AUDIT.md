# X6 seat and character ownership audit

**Opposite rosters and R9 remain unverified.** This docs-only audit maps the
current fixed X/P1 + Zero/P2 implementation to original X6 character/form
fields and the frozen X4 design. It adds no runtime patch, title build, game
launch, ledger pass, save/card access or SDK change.

Source is game `fbba0e3` and frozen X4 Playtest42
`50593bca772b600de6911cbfecd40b0f08721147`. The
[machine-readable mapping](COOP_SEAT_CHARACTER_AUDIT.json) pins full commits,
Git blobs, SHA-256, eight native EXE windows, three BIN members, five player
DAT bundles and their bounded subassets. It contains 13 field mappings and 12
independent local/netplay obligations, all unverified. Original EXE SHA-256 is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`;
the extracted EXE was compared byte-for-byte with the disc's EXE. Workbook
labels use the previously inventoried Tweaks v2.0 workbook SHA
`6855194c79f0830ee77b86901bc1997a481ce62de17dfaaced79d976d840e552`.
Only metadata is committed. Native instructions/assets remain on the owner's
read-only original disc. Full extraction and whole-disc hashing were not run.

## What is currently fixed

The [co-op plugin](../src/mods/mmx6_coop_plugin.c:171) calls the original native
unit-list builder and removes unit5, Zero. It preserves the permanent unlock
bits, but the ordinary campaign selector cannot choose Zero while this filter
is active. The [package manifest](../mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml)
has only the `prototype` enabled/disabled feature; there is no character, form
or seat roster option. Input/lifecycle/menu ownership already uses seat0/1.
Character/resource ownership still assumes seat1 means Zero.

`load_assets()` reads only BIN1 and DAT85. `enter_zero()` writes campaign
character1/form5, replaces the body/pools and seven graphical/menu pointers,
and installs Zero's overlay. Pickups make the same seat1 -> character1/form5
assumption. The opposite roster therefore requires more than a selector edit.
Removing the filter first would expose Zero/P1 + Zero/P2 with mismatched
resources in X-specific paths; it would not implement X/P2.

## Native character, form and asset mapping

`PLAY=800CCED0`; `PLAYER=800970A0`. Character and form are separate native
values, and neither is a controller seat:

| Native form | Character byte | Form byte | BIN member | DAT member | Native portrait index |
| --- | ---: | ---: | ---: | ---: | ---: |
| X | 0 | 0 | 0 | 86 | 0 |
| Falcon X | 0 | 1 | 0 | 87 | 3 |
| Shadow X | 0 | 2 | 0 | 88 | 4 |
| Blade X | 0 | 3 | 0 | 89 | 5 |
| Ultimate X | 0 | 4 | 0 | 86 | 2 |
| Zero | 1 | 5 | 1 | 85 | 1 |

The original loader `80013BF0..80013D0F` selects these DAT members and loads
BIN0/1 at `801EA000`. **Base X and Ultimate share DAT86**; form0 still has
different native behavior from form4. There is no sixth player DAT bundle to
invent. FilesIndex calls DAT85..89 PL00..PL04; labels describe bundles, not
the native form ordinal. Neighbor DAT84 is a 1,256-byte non-bundle and was
explicitly rejected by the existing subasset parser.

The BIN16 unit menu builds `[0,1,5,2,3,4]` from availability bits at `PLAY+5F`:
Falcon01, Shadow02, Blade04, Ultimate08, Zero10. At `800EB174..800EB19C`
**within BIN16**, confirmation stores the selected ID to `PLAY+5E` and sets
`PLAY+38` to1 exactly for form5. The Black Zero bit20 affects the native
portrait variant: `800228AC..80022924` chooses portrait6 for Zero with this
bit, rather than a seventh ordinary unit ID. Gameplay/palette consequences
of that variant remain a separate trace and test obligation.

BIN16 and stage overlays reuse virtual addresses. In particular BIN16 has
unrelated code at the new intro helper's `800EB14C`. Future hooks must guard
native stage/overlay identity and exact instructions, as the current selector
and intro helper already do.

## Fields that must follow the actor

| Field or region | Original native evidence | Ownership implication |
| --- | --- | --- |
| `PLAY+38 -> PLAYER+02` byte | `8003BDE8` reads selected character; `8003BE10` installs body identity | Resolve character from a seat descriptor; restore the actual campaign owner after projection. |
| `PLAY+5E -> PLAYER+E7` byte | `8003D730/8003D73C` | Preserve chosen X form separately when Zero is the campaign hero. |
| `PLAY+74 + character*4 -> PLAYER+EC` word | `8003D72C..8003D74C` | Native equipped parts are indexed by character, not seat. |
| `PLAY+60 -> PLAYER+C9` byte | `8003D748..8003D798`; form2 clears C9 | Earned weapons and form restrictions must remain native. |
| HP at `PLAYER+5C/+5D/+5E`; ammo `+A8..+C7`; base `+14A` | Fresh init `8003BE64..8003BEB0` uses `PLAY+5B+character` and `PLAY+61+character`; checkpoint branch separately restores resources | Current HP/ammo belongs to the actor. Menu, ordinary door and voluntary rejoin must not refill it. |
| Weapon `+93`, attack `+96`, charge levels `+9B/+9C`, timers `+9D/+9E`, native temporary counters | Native checkpoint weapon store `8003BF28`; charge helpers `8003EEE4/8003FFF4`; native reset helpers `8003CDBC..8003CE2C` | The follow-up source trace supersedes workbook row353's `+D7` charge label for normal glows. Capturing the body alone does not establish runtime closure. |
| Native table `+30`; compression `+38`; assembly `+3C`; page `+40`; CLUT `+42`; frame `+47` | Init `8003BF3C..8003BFB0`; `+30` selects `801F4AD4` for X or `801EF6D0` for Zero | Native overlay/data and resource pointers must agree. The selected table's full consumer contract was not established here; a pointer store alone does not prove it is executable dispatch. |
| Shots `800950A0..800964A0` | `80020160..80020234`: 32 entries, stride A0 | Actor-owned attack pool, with one native allocation/update/retire path. |
| Trails `800972F8..80097418` | `8003BFBC..8003C038`: 3 entries, stride 60 | Each entry inherits the actor's compression, assembly, texture page and a native trail CLUT. |
| Attached effects `800911A8..80091298` | `8003C03C..8003C0A8`: two stride 50 entries; `8003C0AC..8003C124` adds the third for X/Falcon | Fixed charge-glow and Falcon-flare source consumers are mapped in the follow-up; private-seat behavior remains unverified. |

The current `PlayerContext` already captures the full 0x158-byte body, 0x1400
shot bytes, 0x120 trail bytes and 0xF0 attached-effect bytes. This is useful
infrastructure, not a charge/glow qualification. The native `8003CD44` called
by P2 is **pad decoding only**. `8002012C` iterates the shot pool only. The
current explicit retained renderer draws the P2 body and 32 shot actors;
source review has not established a complete private trail/attached-effect
update/render/retirement path. Trace those native consumers before adding a
second update or claiming an R9 fix; a second whole world pass is unsafe.

The [R9 fixed-pool follow-up](COOP_R9_EFFECT_CLOSURE.md) now maps those original
producers, update/render helpers and conditional retirement paths, and
establishes an animation-table consumer for native `+30`. Private-seat
execution, palette/resource correctness and natural retirement still require
the listed runtime proofs. The unit5 filter remains unchanged.

## Resource and deferred ownership gaps

The graphical context includes scratchpad pointers `+14,+1C,+24,+28,+38,+3C,
+A8` and dirty byte `800C4560`. DAT subassets0/3/10 are palette, compressed
graphics and assembly; 6..9 are menu graphics/font/colors/layout; 1/2 provide
common UI/icons. Current Zero portraits are fixed DAT165/166. X/form and
Black Zero portrait assets must follow the native selection, rather than
copying a Zero portrait into the other seat.

`menu_vram()` exchanges eight native regions and a portrait CLUT using a
Boolean `zero_menu_loaded`. HUD generation similarly installs one Zero
assembly/menu and samples `zero_ui_pixels`. Both need seat -> character ->
form resource lookup while pause authority, primary life display and campaign
Quit authority stay seat rules. Both owned menus must preserve native parts,
ammo and attack state after restoration.

`sprite_bank()` assumes one immutable Zero archive, with a separate resident
X-death path. `render_survivor()` explicitly treats the seat0 stored body as
X through `render_x_death`. A generalized cache must distinguish changing
character/form/archive generation as well as source/frame/palette, even when
guest virtual addresses are reused. Stage/section X/Zero COL palettes are
present in FilesIndex; this audit did not establish their full composition
with form palettes, dash CLUTs, fades or Black Zero. That remains an original
X6 trace, not permission to paste X4's palette offsets.

Deferred death allocation already retains position, layer and assembly for
native return sites `8003DB0C/8003DB8C`, then restores them at effect init.
It does not establish complete palette/character/form ownership or natural
expiry under both rosters. Pickups, healing, Nightmare souls, survivor and
scene/passenger paths likewise need the actor's character without changing
the single shared world/campaign pass.

Audio is independently open. [The existing native audit](COOP_AUDIO_NATIVE_AUDIT.md)
and [driver follow-up](COOP_AUDIO_DRIVER_OWNERSHIP.md) pin groups 1/3, explicit
overlapping hardware voice slots, cross-bank record 17 and driver state.
`enter_zero()` does not project sound record pointers or sample residency.
Roster support cannot itself close R4/R12 or justify an unsafe SPU swap.

## What the frozen X4 design contributes

Frozen X4 uses `CharacterAssets[2]`, derives the counterpart from the actual
native campaign body's character, then looks up each owned menu by seat's
character. X's variant is separate from seat identity. Its projected resources
and stage-specific character palette follow that descriptor. The renderer
explicitly includes body, shots, trails and charge glows and retains allocating
character/assembly for deferred effects. Its counterpart identity participates
in digest/snapshot validation. Private audio banks are keyed by character and
group, with SPU boot-epoch rebinding and scoped record/priority state.

These are reusable ownership rules, not reusable addresses, strides or proof.
The JSON pins exact X4 files/lines. X6's body size, overlays, five player
bundles, form IDs, VAB group 3 body type, cross-bank alias and 0x38 driver records
are separately established X6 facts. No active X5 work was used as a proven
implementation reference.

## Feasible first implementation slice

Start with an explicit Zero/P1 + **base X/P2** roster alongside the existing
X/P1 + Zero/P2 path. Native BIN0/DAT86 and BIN1/DAT85 are now source-mapped.
Keep form-specific expansion and audio separate. Define an agreed base-X0
counterpart policy instead of inferring an X armor from Zero's form5, or add
an explicit agreed form option in a later scoped change.

Implement typed seat/character/form descriptors and symmetric resource
projection first. Exercise the actual plugin in isolated fixtures: one native
initializer per actor, exact restoration of campaign identity/body/resources,
character-indexed parts/HP/ammo, owned menu input, deferred effect ownership,
and all callback guards/future-restored locals. Preserve shared progress and
one world pass. Only then adapt the native unit filter. Add bounded enum/asset
identity to current-build snapshot/digest/reset handling; never serialize host
pointers. Old snapshots may be rejected without migration.

Before native X/P2 charge testing, close the attached-effect/trail producer,
update, render and retirement contract. Fresh local and same-artifact netplay
receipts must independently show charge/release, projectile and counter
retirement, dash art/colors, both menus and opposite-character deaths. Bump
the agreed title/options/profile identity for new roster behavior. The current
labv11 catalog should refuse a changed contract until reviewed and requalified.

This mapping supports R9 and related R3/R4/R8/R12/R15, F12/F13/F14/F19/F23,
F49/F54/F71/F179. None of their ledger statuses changed. All 12 concrete proof
obligations in the JSON remain unverified in both modes.

## Reproducing the metadata checks

With process-local temp/cache paths on G:, the existing content/audio audit
tools verify the original EXE, archive descriptors and player sound bundles.
The JSON's EXE windows use PS-X EXE offset `0x800 + address - load_base`,
where `load_base` comes from header offset18h. BIN/DAT descriptors are LE32
sector/length pairs at `member*8`; member payload starts at archive LBA plus
that sector. Read only the listed member sectors and trim to descriptor size.
For each packed DAT bundle, use the existing
`audit_mmx6_coop_audio.subassets()` parser: its type/length table and rounded
2048-byte cursor must consume the complete member. Compare each recorded
SHA-256/length/type. Do not treat unrelated DAT84 as an asset bundle.

All eight EXE-window and eight member hashes, all 80 DAT subasset hashes and
six frozen X4 source hashes were rechecked. Native instruction semantics were
inspected read-only with the installed Capstone MIPS32 little-endian decoder;
hashes do not automate that review. No Ghidra project was opened or unlocked.
