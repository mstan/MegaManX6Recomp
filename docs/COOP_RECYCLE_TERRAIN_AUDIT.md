# R14: Recycle CP3 terrain and approach limit

The initial authored terrain does **not** support a blind Left/fall route from
stage 4/section 0/CP3 to the portal. CP3 supplies player1728/1456 and locked
camera1568/1440. The portal actor is1552/1584, behind an initial solid column.
This source audit grants no safe live position, route or R14 pass. No game,
title build, guest call/write, input, card or ledger operation ran.

## Original input and map closure

`tools/audit_mmx6_recycle_terrain.py` verifies the original USA v1.1 EXE SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and frozen inventory before decoding the selected map. The committed JSON
records exact code/data extents and hashes. Reads are limited to the complete
1,665,024-byte BIN, the first4096 DAT bytes and selected DAT98. It never reads
the entire50,913,280-byte DAT or crawls other files.

| Source | Native identity |
| --- | --- |
| Stage overlay | BIN member6, sector153,42,944 bytes; SHA256 `c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5` |
| Terrain resources | DAT98, relative sector5682,937,984 bytes; SHA256 `f8798efe535ac46ca7ab2a7e4dfd99705c5624ae5c301627543c3d91d3bf6515` |
| Initial layout | EXE `80076300 ->800F286C`;22 by8 screens,3 layers,528 bytes; SHA256 `f68a92a60270db16e4a82a10782d3bfa98643dc82e467122ef8aee31a49b985c` |
| 256px screen metatiles | DAT98 subasset7/type0,87,040 bytes; SHA256 `a8a914262768bcf2b0310a5e4723f545ca4b840387900c1d78d3bd1de6a0b117` |
| 16px tile descriptors | DAT98 subasset8/type1,8000 bytes; SHA256 `613dcf05adfc3810a7b13bf496f9fceae4b156acc00b9c78a9b635326eb6b192` |

Original loader `80014084..800140A4` selects DAT98 through table `8006D9FC`.
The type0/type1 destinations are `1F800008`/`1F80000C`, via `8006E27C` and
pointer publication `800154D0..80015518`. `800268A4` sets `1F800004` to the
live map at `80097438`. `8002798C..80027A4C` copies the initial three-layer
map from root `800762E0`, indexed by stage/section. Dimensions come from
`80076398`, read at `8001429C..800142C8` into `800CD338/339` and
`8008EC10=width*height`.

`80028078..800280F0` bounds-checks unsigned screen column/row, then indexes
`layer*(width*height) + row*width + column`. `80030304..80030408` resolves a
nonzero screen ID to its512-byte metatile, selects a16px cell, masks the tile
ID with3FFFh, and reads the descriptor's low byte. Screen0 and out-of-range
screens return0. Raw collision3Bh is remapped to38h. The pure helper implements
that lookup without native body or collision-scratch writes.

## Exact bounded terrain finding

On **initial layer0**, x1568..1599/y1408..1679 consists of38h/39h tiles.
Both codes select native left collision `8003065C` and downward solid handling
`8002FBA4`. Within x1600..1791/y1440..2047, all456 sampled16px cells resolve0.
This includes the CP3-side corridor and the area below its authored spawn.
The portal side has empty collision at1552/1584 and a solid tile at1552/1616.
These are terrain queries, not proposed player positions: a character's
current body box changes its actual foot/contact coordinates.

The findings establish a straight horizontal obstruction and absence of
initial static support in that sampled corridor. They do **not** establish
that CP3 is impossible, that no actor can support a live body, or that the map
will retain its initial cells. A jump around the column, crossing its roof,
falling below it, or teleporting to the portal side remains unproved. The
fixed camera describes the view and does not prove player clamping or terrain.

All four nearby authored centers in x1408..1920/y1280..1728 are retained:

| Record | Category/type/subtype | Position | Original handler |
| --- | --- | --- | --- |
| `800F2A8C` | 3/6/3 |1600,1584| `80052D30` |
| `800F2B0C` | 0/1C/1 |1552,1584| `800EC678` portal |
| `800F2B14` | 4/8/23h |1872,1584| `80050DFC` |
| `800F2E24` | 4/1A/4 |1424,1592| `800515B4` |

The first is a **checkpoint marker**. Its initializer `80052D6C` and update
`80052DB8` compare native checkpoint/visibility/X threshold; `80052E18` writes
PLAY+1D=3. It does not create support or modify the map in this closure. The
other two handlers' full live behavior/support is not closed by this audit.
There are no authored category1 centers in this rectangle; actors centered
elsewhere and dynamic geometry remain possible. No arbitrary center is
classified as a platform or safe floor.

## Safe next native probe

First finish the existing disclosed CP3 initializer, then remain neutral.
Retain each actual body, its **current** +68 box, native +70/+67 ground fields,
live528-byte map and completed terrain capture. If a body falls or has no
native support, retain that setup failure and stop. Do not begin blind Left
movement, call native terrain functions manually, or write collision scratch.

`foot_probes(actual_body, actual_box_bytes, terrain)` computes the three
initial downward sample points from `800304D8` and `8002F840`: signed body X/Y,
signed box offsets, unsigned box radii; facing byte nonzero reflects the X
offset. The samples are center-radius, center+radius-1 and center, at
Y+offsetY+radiusY. Arithmetic wraps as native signed16 values. The current
source box defaults are X `80073D50`=(0,2,11,19) and Zero
`80073D54`=(0,3,11,19), selected by `8003CCBC` only when body+D5 is nonnegative.
Never substitute those defaults for a different live +68 box. Neither three
sample points nor a source tile response grants full-foot safety.

For concrete native confirmation, observe **naturally executed** `80030304`
calls during the original neutral collision pass, including a0(body), a1/a2
(sample X/Y), return values at original callers `8002F8A8`, `8002F8D0` and
`8002F8E4`, and the later `8002F418` contact result. `80030888` writes ground
bit8 during resolution; `8002F590` also sets it during final contact probing.
Those functions mutate the body and shared scratch, so invoking them from a
read-only observer would violate its contract. The original controller calls
`8002F288` at `80020CC0`; private Zero already receives its original pass.
Seat attribution still requires an actually coherent private-seat/native-call
observation; separate RPCs must not be fused into one contact sample.

For the owning runner, `load_original(original_exe, original_disc)` returns
`(exe, member6, terrain, resource_metadata)`.
`observe_source_preflight(owned_read_only_request, terrain)` reuses the portal
observer's single412,344-byte native read and retains its parsed native state
plus the live528-byte layout comparison and changed indices. The source floor
envelope appears only when the original portal closure and initial map match.
This is not position approval: live scratch pointers, metatile/descriptor bytes,
actual private boxes and dynamic support/hazards remain explicit gaps. No pad or
guest mutation command is available through this helper.

If live support or map mutations make CP3 viable, identify their producer and
retain the resulting actual collision-ready position before defining bounded
accepted movement. Otherwise investigate the authored CP2 route separately.
There is currently no approved movement sequence or guessed grounded position.

## Conditional portal-side probe envelope

A tightly scoped static probe can be derived without using the portal center as
a guessed foot position. Within x1456..1567, the original map is clear over the
standing Zero body rectangle and has38h floor at y1616. With the actual source
standing box (0,3,11,19), native bottom is centerY+22. Thus the predicted contact
plane is centerY1594, and a one-pixel-air probe is1593. Keeping the entire body
inside that checked horizontal rectangle gives centerX1467..1557. The helper
checks all covered tiles and reports this **source envelope**, not an approved
live teleport or grounded position. It selects no exact X or movement sequence.

A future private positioning bypass could use that envelope only after live
map/resource identity, the actual current+68 box, dynamic hazards/solids and
script locks are checked. Its initial actual damage-box/portal contact must be
a miss, with P1 outside; the standing terrain box alone cannot prove that miss.
Record the bypass and taint. Then allow original gravity/contact to establish
the actual landing before using original accepted movement to enter the portal.
Never force ground bits, body phase, HP, portal action, fade, success or clocks.
Static support alone cannot qualify the destination or make CP3 reachable.

The existing `diagnostic_setup` command4 already supplies an atomic offline
positioning mechanism, so no title implementation is needed for a later
reviewed bypass. In frozen game `b766ed1d7a698ec10bcdf9b793a82c4ca84aff10`,
the payload is diagnostic+52 seat, +54 fixed32 X and +58 fixed32 Y; writing
command4 to +50 requests the original outer diagnostic boundary. Seat0 changes
resident P1, seat1 private P2, seat2 both. The handler updates body+8/+C and
previous+18/+1C together, leaving other native body fields unchanged.
`diagnostic_mutation_allowed` rejects active netplay and builds with
`PSX_NO_DEBUG_TOOLS`; the input-taint API marks game-mailbox use. Keep this
bypass explicitly disclosed even when that API is unavailable. Do not use this
mailbox for a paired portal test or call its acknowledgement a successful
landing/contact. This read-only lane does not issue the command.

## Reproduction

Set TEMP/TMP/PYTHONPYCACHEPREFIX to G/F first. The CLI refuses to overwrite an
existing audit; checking never changes it:

```powershell
python tools/audit_mmx6_recycle_terrain.py --original <original-EXE> --disc <original-raw-bin> --out docs/COOP_RECYCLE_TERRAIN_AUDIT.json --check
$env:MMX6_CONTENT_EXE='<original-EXE>'
$env:MMX6_CONTENT_DISC='<original-raw-bin>'
python -m unittest discover -s tools -p test_mmx6_recycle_terrain_audit.py -v
```

Tests cover actual selected source reproduction and bounded reads, descriptor
masking and3Bh remap, empty/out-of-bounds screens, all three layers, malformed
references, native facing/offset/wrap semantics, current-box prerequisites and
source identity drift. They do not emulate original movement or qualify a route.
