# Recycle: conditional setup outside capsule and portal triggers

The source-derived common miss interval is **x1489..1523** for the explicit
reference damage boxes below, with both characters on the checked floor. Its
deterministic midpoint is **x1506**. A common seat2 air probe at **y1593** leaves
X two pixels and Zero one pixel above their predicted native contact planes.
This is a conditional prerequisite-bypass plan, not a safe live placement,
original route, R14 or netplay pass. Actual current boxes and live preflight
must match; otherwise recalculate or refuse. This lane runs no game/build or
setup/input command and changes no production code or frozen reports.

## The capsule that interrupted the first floor probe

Original primary record117 at `800F2E24` is category4/type1A/subtype4,
authored1424/1592. Original stage4 table `8006DF6C ->800F338C`, slot1A at
`800F33F4`, selects handler800515B4. It uses initializer80051158 and updater
80051890; action0 `80078E18[0]` selects **80051924**.

That trigger does not call damage-box collision. It reads signed integer
player/actor centers and admits ordinary local coordinates when:

```text
abs(playerX-capsuleX) <= 64
-104 <= playerY-capsuleY <= 16
```

The native code's differences/negation wrap as signed16, which the calculator
also reproduces. The candidate search remains in the bounded positive source
rectangle; it never exploits wraparound. No button, player iframe or +54/+68
box gate participates in this initial capsule trigger. On acceptance it calls
original script8003D308 with action14h and writes native shared freeze flags.
The co-op interaction wrapper uses the same ordinary rectangle for each seat
and gives simultaneous P1 contact priority.

The capsule's authored Y is not a live grounded assertion. Its native +68 box
is `80078DF8`=(0,0,16,12). Initializer80051394..3BC repeatedly adds16 to its Y
and calls8002F288 until contact. The selected map gives initial foot probes
1604 ->[0,0,0], then1620 ->[38h,38h,38h]; native resolution predicts grounded
capsule Y1604. Its +54 damage box `80078E00`=(-16,-12,32,24) belongs to other
collision paths, not51924. A fresh live origin-bound capsule observation must
confirm the actual position/phase; the source calculator does not infer it.

Root's failed owned CP2 experiment is retained at
`G:/Temp/Codex/psxrecomp/x6-parity/portal-cp2-v15-c5fadea-floor-probe/qualification.json`,
SHA256 `f601a72818474715602ebc7a52201185759c521af73621d01b8fac0a60f1356a`.
It used executable `39c154966f9c12f939a8305551a910de9dbb97878dcf05c5935bed03c7ca7036`.
The exact live layout, scratch pointers and complete metatile/descriptor hashes
matched source. Original X landed at1467/1595, then entered script action14h;
the diagnostic reported scene owner1/phase3 and the partner stayed nearx504
without a ready two-seat roster. Root reviewed the completed composed capture
as Dr.Light dialogue. The report did not retain the capsule pool, so its live
slot/position attribution remains to be captured. Source |1467-1424|=43
explains the capsule trigger; no terrain failure or portal completion follows.

## Portal geometry and the finite constraint solve

Original portal800F2B0C is at1552/1584. Its trigger8002D654 uses actor+50
`800F38BC`=(-18,-28,28,40) and the player's actual current+54 damage box.
Its +68 body box is different and must not substitute for that damage box.
The exact directional, strict-inequality rectangle arithmetic is documented
in [the native-entry follow-up](COOP_RECYCLE_CP3_NATIVE_ENTRY.md) and reproduced
by `contact()` in the new helper.

Portal initializer800EBDD4..EBDE8 selects facing once from resident P1 X:
P1 left of portal gives facing0, otherwise40h. The calculator tests **both**
portal facings and both player facing bits for both actors. Thus it does not
reuse CP3's facing40h assumption after moving to the portal's left.

The explicit source reference boxes are:

| Character owner | Original bank | Native pointer | Damage box |
| --- | --- | --- | --- |
| X | BIN0, sector2,44,588 bytes |801F3F50|(-10,-17,19,38)|
| Zero | BIN1, sector24,22,964 bytes |801EEA04|(-10,-17,21,39)|

These are source identities, **not inferred standing/idle/current poses**.
The actual per-seat +54 pointer, animation/context and resolved bytes must
support the selected inputs. Private Zero's native pointer cannot be read
through the restored resident-X overlay. `source_box()` selects an explicit
original character owner and rejects pointers outside that bank, including
expanded host pointers; such pointers require separately proven owned bank
bytes. It never falls back to resident X bytes.

The current live diagnostic does not yet publish those private-bank bytes.
Although private P2's +54 can name `801EEA04`, ordinary RAM contains the
restored resident-X character overlay at that address. The plugin retains
Zero's private character bank in host `zero_overlay` and projects it only
inside the owning context. A live prerequisite therefore needs a coherent
publication of the actual +50/+54/+68 pointers, the four bytes resolved from
their owning bank, and availability/origin for each record. Root owns that
additive read-only diagnostic extension; this tool neither implements it nor
accepts a resident-RAM substitute. Until then the reference solve remains
conditional and cannot authorize the proposed position setup.

The earlier exact static terrain envelope is1467..1557, floor1616. The capsule
excludes1467..1488. With these reference boxes, portal contact excludes at least
one tested character/facing combination at1524..1557. The remaining35 integer
centers form1489..1523; midpoint1506 is calculated from that interval, not
guessed. X1530 can already contact the portal, for example when portal facing0.
The solver recomputes for different supplied current boxes and can return no
common interval. Missing bytes for a nonnull pointer are an error, not a miss.

Source terrain boxes80073D50=(0,2,11,19) and80073D54=(0,3,11,19) predict X1595
and Zero1594 contact Y. Seat2's common airY1593 gives initial feet1614/1615.
Only original gravity/contact can establish actual landing. Moving only P1
after P2 has joined leaves an uncontrolled remote partner on the previous map
location; the conditional plan places both eligible actors atomically or
establishes an independently proven safe join before continuing.

## Original camera, admission and readiness remain mandatory

Use a fresh scene-free offline CP2 setup. An existing capsule dialogue or
portal freeze is not cancelled by moving actors; never clear its owner,
action, locks or flags. Preserve private checkpoint and position bypasses and
their input taint; neither action is available for a paired mailbox test.

CP2 camera bounds are X320..1264, Y1424 locked. Once the **original** camera
follows to1264/1424, native320x240 view1264..1584/1424..1664 covers both source
players and both authored actors. Original initial admission8002A3E8 calls
scanner80029F38 with expanded rectangle1216..1632/1376..1712. Both original
actor origins lie strictly inside. That supplies admission prerequisites,
not proof of live initialization or visible rendering.

Before accepted movement, retain both living visible native-idle grounded
actors, current boxes/resources, independent controls, no scene/freeze/entry
locks, settled camera and actual admitted actors. The capsule must be origin
800F2E24/type1A/sub4/phase1/action0 at its actual position. The portal must be
origin800F2B0C/type1C/sub1/phase1/action1 with original geometry pointers and
native record variants. A phase0 allocated portal is still uninitialized.
Do not write admission flags, actor fields, HP, ground bits, phase, locks,
success, timers or destination state. Original movement/contact/fade/loader
must establish the actual route. Keep the authored checkpoint-X mismatch as
a disclosed bypass instead of weakening that original readiness predicate.

## Helper interface and source validation

New module `tools/mmx6_coop_recycle_setup.py`:

```python
sources = setup.load_sources(original_exe, original_raw_bin)
x_box = setup.source_box(sources, 0, actual_current_x_native_pointer)
z_box = setup.source_box(sources, 1, actual_current_zero_native_pointer)
plan = setup.derive_setup(sources["terrain"], x_box, z_box, capsule=(actual_cx, actual_cy))

# Pure predictions, using the actual supplied current fields and exact boxes:
result = setup.contact(actor_fields, player_fields, attack_box, damage_box, camera=None)
capsule_hit = setup.capsule_region(cx, cy, px, py)

# One read-only native block; no launcher or pad/write command:
observed = setup.observe_setup(owned_read_only_request)
```

`contact` fields: actor x/y/facing/layer/attack_pointer; player
x/y/facing/iframe/damage_pointer. Negative actor layers require actual camera
coordinates. `observe_setup` adds the origin-bound category4 capsule to the
existing single412,344-byte native block parse. It does not join private-player
RPCs into a coherent contact claim or grant readiness. Caller retains actual
image SHA/PID/listener ownership and partial reports through failure cleanup.

The new JSON is source-only metadata with original EXE/BIN/member hashes,
native extents, capsule dispatch and explicit reference-box conditions. Existing
frozen inventory and prior source reports are unchanged. Set G/F TEMP, TMP and
PYTHONPYCACHEPREFIX, then run:

```powershell
python tools/mmx6_coop_recycle_setup.py --original <original-EXE> --disc <original-raw-bin> --out docs/COOP_RECYCLE_TRIGGER_FREE_SETUP.json --check
$env:MMX6_CONTENT_EXE='<original-EXE>'
$env:MMX6_CONTENT_DISC='<original-raw-bin>'
python -m unittest discover -s tools -p test_mmx6_coop_recycle_setup.py -v
```

Six tests pass. They compare600 contact calculations and capsule boundaries
against bounded execution of the **original native instructions**, cover strict
edges/facings/null/unknown boxes/camera layers, signed16 edges, original-source
reproduction, changed-box recomputation and stale/duplicate/wrong capsule slots.
This is source/parser validation. No build, game, positioning or route test ran.
