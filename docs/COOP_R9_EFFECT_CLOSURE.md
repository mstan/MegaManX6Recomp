# X6 R9 native trail and attached-effect closure

**Source mapped; private X/P2 behavior remains unverified.** The original X6
fixed pools now have producer, update, draw and retirement paths identified.
This docs-only follow-up to the [seat/character audit](COOP_SEAT_CHARACTER_AUDIT.md)
does not implement the opposite roster or remove the unit5 filter. There was
no game launch, title build, SDK change, native save access or ledger pass.

The [JSON record](COOP_R9_EFFECT_CLOSURE.json) pins 38 native code windows,
seven dispatch tables and 26 checked direct JAL edges. Input is the original
USA v1.1 EXE SHA-256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and BIN0, the 44,588-byte X overlay loaded at `801EA000`, SHA-256
`180175846cf8b1b650c405be8085b19417be033b4644a4034d70703124bf7871`.
Only these original inputs were read for this follow-up; the prior audit's
selected DAT86..89/form metadata is reused. No full-disc extraction or hashing
was run. Native instructions and assets are not bundled here.

## Native call order and ownership

The stage dispatcher `8001E9EC` uses `PLAY+1` and table `80071184`.
The ordinary phase calls controller `80020C40` at `8001EB0C`; the next phase
can call it at `8001EB64` when `80097424` is nonzero. A native menu/controller
context also calls it at `80034D90`. The recorded-input path calls a separate
controller `80021500` at `8001D698`; it consumes its native replay input table,
so it is a call-site reference, not a replacement private-input path.

In the ordinary controller, player advancement `80034DCC` and shot-pool
update `8002012C` precede contact `8002F288`. After the remaining native
contact helpers, **`80020CE8` calls attached effects `80020D74`, then
`80020CF0` calls trails `80020DC8`**, followed by body graphics preparation
`80017B04`. The recorded-input controller calls the same two pools at
`8002160C/80021614`. A private actor needs this order once when eligible.
Calling the entire controller or stage a second time would repeat shared
work. A survivor already owning the native world pass must not be advanced
again. Pause, absent, fallen, scene and passenger gates still need actual
plugin tests.

| Pool | Native storage | Ownership and native update |
| --- | --- | --- |
| Trails | `800972F8..80097418`, three slots of `60h` | `80020DC8 -> 80020E1C`; hardcoded resident `PLAYER=800970A0`. Slot0 `+50` links to PLAYER; slots1/2 link to the previous trail. |
| Charge glows | `800911A8..80091248`, two slots of `50h` | `80020D74 -> 80020AA8`; hardcoded resident PLAYER, with no separate owner pointer. |
| Falcon flare | `80091248..80091298`, one slot of `50h` | The same helper, subtype3. Native initializer creates it only for character0 and form1. The pool updater checks allocation byte `+0`, not the current form. |

Initializer `8003BFBC..8003C038` gives each trail the player's camera layer,
compression/assembly pointers and texture page, a CLUT from `80073CEC`, and
priority4. It installs the three native guest parent links. Each trail update
copies the resident player's frame `+47`, facing `+15`, compression `+38` and
assembly `+3C`; it saves its own previous position at `+18/+1C` first.
Changing a body or overlay without its pool/parent/resource context can
therefore borrow another actor's history or art.

Initializer `8003C03C..8003C0A8` creates ordinary attached subtypes0/1 with
animation table `8007789C`, priority2, page0, CLUT `7802`, compression pointer0
and assembly `SCRATCH[1C] + word(assembly+70h)`. The Falcon third instead uses
the assembly's `+20h` offset. These common textures differ from body/trail
compressed-frame textures. A roster/form transition must account for the
whole third slot; its updater does not independently remove an allocation
merely because the current form changed.

## Charge acceptance and glow retirement

The living player phase `80034FBC` calls `8003EC78` at `80035118`. This parent
allows character0 only, excludes actions0/1/18h/19h and nonzero `+D5`, and
excludes form4 when `+E0` is nonzero. The original fire/release predicate
`8003ED98` must return0 and equipped-parts bit `00080000` must be clear before
it calls the two charge helpers. The predicate reads held/previous/edge input
at `+7C/+7E/+80`, attack state, charge timers and shared `PLAY+C9` options;
new presses and releases can take the native clear/fire path. A host-held
button approximation would skip those conditions.

| Producer | Accepted conditions after the parent gate | Mutations |
| --- | --- | --- |
| Buster `8003FFF4` | Held input `+7C & 20h`, or `PLAY+C9 & 01h` with weapon `+93==0`; charge level `+9C!=2` | Increment `+9E`; set `+9C=1` at25 and2 at90 eligible helper calls. Parts `+EC & 00100000` changes thresholds to12/45. |
| Special weapon `8003EEE4` | Weapon `+93!=0`, held input `10h`, level `+9B!=2`, form1/3/4, enough native ammo for `8003EB0C(actor,weapon+9)` | Increment `+9D`; set `+9B=1` at25 and2 at90, or12/45 with the same parts bit. |

Both first thresholds call native sound group1/id7. These are counts of
eligible helper invocations, not a measured frame count since first keypress.
The workbook-derived `+D7` charge label in the earlier mapping is superseded:
**this glow producer uses levels `+9B/+9C` and timers `+9D/+9E`**. `+D7`
appears in other arrival/death countdown contexts; its complete semantics
remain outside this closure.

Attached updater `80020AA8` always copies PLAYER position. While an ordinary
slot is inactive, subtype0 requires either charge level to equal2, subtype1
requires1. It makes the actor visible, selects animation8/9 and activates
`+4`. Once active, it advances animation while either charge level is nonzero.
**Both levels zero hide it and clear `+4` on the next update.** The level1
slot is not automatically removed just because level2 is reached. A held
charge can remain visible indefinitely; there is no independent expiry timer.

`8003F480` stops group1/id7, calls native `8003CE30`, then clears all four
level/timer bytes. `8003F58C` clears the corresponding pair when its held bit
is absent, except native autocharge with weapon0; when the timers clear it
stops the sound and refreshes animation. The native menu context uses these
paths before its controller and when the selected weapon changes. This maps
the source path; private menu state, charged projectiles and audio ownership
are still separate runtime obligations.

## Accepted dash markers and finite trail drain

`80039F78` implements a native direction double-tap window: it clears latch
`+87` each call; for eligible actions it retains a first direction edge in
`+82`, counts down `+88` from12 and sets `+87` for a matching second edge.
`80039EB0` accepts a dash only with `+D3==0`, that latch or edge input `100h`,
and a clear facing side in native collision byte `+89`. It sets horizontal
velocity `+20` from native speed `+104`, with facing updated from held
direction bits1/2. Native callers `80039BC4/80039C40` then invoke `8003A9C4`.

That initializer sets dash state `+84/+86`. A simultaneous jump edge `80h`
takes action6 and writes `+8C=1` immediately. The ordinary branch takes
action0Ch, subphase0, selects animation10h and a `+85` timer of15 with parts
bit10h or30 otherwise. Action0Ch dispatches through `80073C04`; its initial
helper `800357A8` waits for native animation flag `+45 & 80h` before writing
`+8C=1`, playing group1/id5 and advancing subphase. Earlier native action
cancellation can prevent that accepted marker. Other dash actions also
produce it; a raw held dash button is not proof of acceptance.

Trail updater `80020E1C` treats **signed PLAYER `+8C`** as its producer state.
Positive activates an inactive trail with delay3, counter8, tail counter
`(5-index)*2`, visibility1 and current PLAYER position. Zero hides/reset an
active trail immediately. A negative marker starts the drain phases through
the exact three-entry table `80071388`:

| Phase | Routine | Retirement behavior |
| --- | --- | --- |
| Follow0 | `80020F24` | Periodically copy the linked parent's old position. Negative owner marker advances to1. |
| Drain1 | `80020F8C` | Consume counter8, copying parent history on alternating calls, then advance to2. Positive owner marker reinitializes phase0. |
| Drain2 | `8002103C` | Consume tail10/8/6, then clear visibility/active bytes. Retiring index2 also clears owner `+8C`. Positive owner marker reinitializes phase0. |

Common transition `8003CD9C` changes a positive marker to-1 and clears dash
state; hard reset `8003CDF0` clears the marker and related body state. An
inactive slot seeing a negative marker can also clear it, hiding other slots
sooner. With valid native counters, a retained negative marker, continuing
updates and no retrigger, the phase arithmetic gives a conservative bound of
21 own updates from phase0 to retirement. The last slot's marker clear can
shorten the other slots. **This is conditional source arithmetic, not a
measured native-frame result.** Pauses, skipped updates and new accepted
dashes change the wall-clock duration.

## Falcon action and flare

`8003906C` requires `+D3==0` and `+86==0`; character0/form1 selects
`8003F28C`. It accepts a jump edge `80h` or native dash acceptance from
`80039EB0`, initializes native timing through `8003B298`, takes action23h and
animationA9, and calls shared effect producers `8003D3F8/8003D510` as well as
sound1/id5. Those shared allocations are outside these fixed pools and still
need deferred owner/resource tracing.

The original X action23h entry is BIN0 `801EB8B8`, with phases at
`801EC878/801EC908` from table `801F3730`. Initial phase waits for animation
`+46==0`, selects animationAC/AD/AB by vertical velocity `+24`, sets trail
marker1 and advances player `+6`. The fixed Falcon actor is visible only
while **PLAYER action23h and signed subphase `+6>0`**. On a subphase change
it chooses its own animation2B/2C/2A by velocity sign and copies facing. An
invalid action/subphase resets animation2A and hides it on that update.
Its retirement therefore depends on native action exit, not a new host TTL.
Phase1 uses native `8003A0E8` and native fall/landing exit paths. No armor
expansion or unmeasured Falcon runtime claim follows from this mapping.

## Animation, drawing and required context

`800179A4` indexes actor `+30` by animation ID and writes actor `+17/+34`,
the command word `+44..47` and `+48`. `80017A04` decrements `+44`, then uses
signed command byte `+46` to step pointer `+34` and load the next command.
Both are leaf routines using the passed actor and its animation pointers;
they do not access a global owner or clear visibility. This establishes an
animation-table consumer for native `+30`, whose purpose was previously open.

World-render entry `80022960` draws the body, then, for character0, visible
attached actors at `80022B3C/80022B58/80022B74`. It then draws visible trails
in reverse order2/1/0 at `80022BA8`. Every one uses generic actor renderer
`800232D4`. Whole-world rendering also draws terrain, HUD and shared actors;
it must not be invoked a second time to get these effects.

The generic actor renderer reads actor layer `+14`, assembly/frame
`+3C/+47`, facing `+15`, page/CLUT `+40/+42` and priority `+16`. Its mutable
draw context includes the layer camera at `800971F8` with stride54h,
scratch frame bank0, packet cursors `+100/+104`, budget `+124` and OT tails
at `8008EB08`. PriorityFF additionally follows `8009B7A0+78`; these initialized
fixed actors use ordinary priorities2/4. Future private rendering needs
valid owned DMA arenas and correct native tail continuation, preserving
already linked packets. Restoring every draw global after each actor would
discard valid output; sharing packet storage would overwrite it.

An X/P2 projection therefore needs the whole native body, both fixed pools
and their guest parent links, correct X/form overlay and resource pointers,
shared option/identity handling, native camera/draw context and immutable
owner-specific retained art/CLUT identity. Merely passing a different `a0`
cannot change the hardcoded resident owner. The current retained renderer
explicitly draws body/shot actors and has Zero-specific resource assumptions;
capture of trails/effects alone does not make them advance or render privately.
Full stage palette/fade composition, armor auxiliary rendering, SPU ownership
and shared deferred dash effects remain outside the completed fixed-pool
source trace.

Any later runtime slice must preserve one world pass, track guards and
future-restored locals through the existing typed state mechanism, and extend
current-build ready/digest/reset/snapshot handling without serializing host
pointers. Both roster directions, accepted/rejected inputs, charge release,
trail drain/retrigger, menu/scene/death transitions, draw colors/OT bounds and
fresh two-peer evidence remain unverified. The JSON lists eight independent
proofs; none changes R9 or related audio statuses.

## Rechecking metadata

Use the existing content parser for the original EXE and disc directory.
Read BIN0 only: the archive descriptor is a LE32 sector/size pair at offset0;
read the recorded member sectors and trim to size. EXE code-window file
offset is `800h + start - header_load_base`; BIN0 payload offset is
`start - 801EA000`. Check every recorded length and SHA-256. For each direct
edge, decode its LE32 word as MIPS JAL and compare the target; compare table
entries and bounds exactly. The trail CLUT table is three LE16 values.
Recheck the pinned game Git blobs separately. These checks validate the
metadata and source identity; instruction semantics required read-only
inspection with Capstone and are not a gameplay test. Temp/cache output stays
under the task's G: scratch root.
