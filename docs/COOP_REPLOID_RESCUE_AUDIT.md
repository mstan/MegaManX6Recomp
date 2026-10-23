# Original Reploid rescue attribution audit

The [machine audit](COOP_REPLOID_RESCUE_AUDIT.json) maps all **128 native IDs**
losslessly to the immutable [content inventory](COOP_X6_CONTENT.json), including
its seven authored cases per ID. It adds original placement/member identity,
found-state word/nibble and native-save payload offsets, reward assignment,
upgrade ordinal and exactly-once mask. **Every runtime outcome is unverified.**
This is an audit of the fixed X/P1 + Zero/P2 adapter, not a gameplay result,
new ledger, opposite-roster implementation or instruction to write success flags.

## Source and reproduction

| Source | SHA256 |
| --- | --- |
| Original `SLUS_013.95`, 522240 bytes | `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046` |
| Original `ROCK_X6.BIN`, 1665024 bytes | `55b03e4ecc13d6110ff300f80b7000b0f97234e19f1b846aa2b885eece30d80f` |
| Frozen content inventory | `67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad` |
| Original report member20, sector419, 45216 bytes | `353abfee70d0d12cbdc32d620c5482e15ff26a603e4af58b5d341071ca78a956` |

The audit was made against game commit `ec96eb4e57272e0ce8f7305e43a17ebc06ce2e56`.
Its relevant co-op function spans are individually SHA-pinned, so unrelated
diagnostic edits do not silently change the inspected collector contract.
Generated functions/range metadata in the existing local source tree located
the routines; semantics, instruction windows, direct calls, store widths and
tables were verified from the original EXE and selected original report member.
There was no Ghidra open/lock operation, game build/launch or card access.

`tools/audit_mmx6_reploid_rescue.py` reads only the existing bounded ISO root,
EXE and BIN extents. It verifies both original hashes, the exact frozen
inventory hash, every primary placement list/member, and all 128 definitions.
It emits metadata rather than executable/disc bytes. With private non-C:
TEMP/TMP/PYTHONPYCACHEPREFIX, run from the repository:

```text
python tools/audit_mmx6_reploid_rescue.py --exe <original-SLUS_013.95> --disc <original-2352-byte-bin> --check docs/COOP_REPLOID_RESCUE_AUDIT.json
```

An extracted original `ROCK_X6.BIN` can instead be passed with `--bin`.
`--output <fresh.json>` initializes a new audit and refuses an existing file.
`--check` reads/compares and never rewrites it. Source drift fails instead of
reinterpreting another revision. No runtime results are imported or inferred.
The supplied disc EXE must equal the separately supplied EXE. No whole-disc
hash/crawl or new content extraction is required.

## Native actors and found states

The shared live solid/item pool is `800C1220..800C4560`: **80 slots, strideA4h**,
not the enemy pool's 9Ch stride. Allocator `8002C4C4` and Nightmare's target
scan `80042D98` independently establish these bounds. Qualifying a live
Reploid needs allocation `+0`, object type byte `+1==4`, subtype byte
`+2==native_id`, and original placement pointer word `+10`. Original subtype
`80h` is a separate special actor and is excluded from the 128 authored IDs.
Do not attribute a reused pool address without checking that live identity.

The original stage data contains a pointer to native dispatcher `8004F834`.
The JSON retains pointer locations per selected member, but pointer presence
alone does not establish active dispatch or hook interception in a build.
The dispatcher reads signed phase byte `+4`, indexing the nine-word table at
`80078C7C`. Its phase6 action table is at `80078CA0`.

| Phase | Native handler | Meaning established by the inspected path |
| --- | --- | --- |
| 0 | `8004E800` | Initialize, or suppress IDs whose found state is2/3/4 |
| 1 | `8004EA78` | Waiting animation, original rescue test, then pending infection/offscreen handling |
| 2 | `8004F880 -> 8004EC30` | Delayed healing under resident PLAYER |
| 3 | `8004F8C0` | Begin rescued escape animation; remove rescue contact box |
| 4 | `8004F9A0` | Native delay80, then escape setup |
| 5 | `8004FAD0` | Escape/update/camera retirement |
| 6 | `8004FB60` | Infected hostile action, native damage/contact and loss handling |
| 7 | `8004FB40` | Rearm authored placement with `8002CA54`, then clear actor |
| 8 | `8004F8A0` | Clear actor with `8002C9B0` |

Current found states occupy `PLAY+D8 = 800CCFA8`, **64 bytes / 128 four-bit
fields**. Setter `8004FF00` performs a complete LE32 read/modify/write at
`PLAY+D8+(id>>3)*4`, shifted by `(id&7)*4`. Getter `8004FF4C` returns that
nibble. Physical values0..15 remain representable; inspected native writers
and initialization establish0=unrescued,2=rescued,3=dead,4=missing/infected
loss. Values1 and5..15 remain unknown; the decoder retains them rather than
calling them rescued or inventing an infection state1.
The native setter masks its ID and argument to FFh, not to127/Fh; its callers
and authored domain supply those narrower bounds. The read-only tool rejects
out-of-range IDs and exposes no native-state mutation API.

Native initialization suppresses a previously2/3/4 ID by selecting phase8.
Rescuing, infection loss and death therefore have consequences on re-entry
without a second copy per player. A guarded mission-entry setup at `8001E914`
copies these 16 words to `PLAY+118 = 800CCFE8`. The report compares this
mission-entry snapshot against current rescued state2 to identify new rescues.
Loading a room or observing a found bit does not qualify retry/re-entry.

## Rescue, delayed healing and simultaneous ownership

`8004EECC(a0=Reploid)` chooses the native player/vehicle contact body, requires
masked HP `&7Fh` nonzero and calls the original overlap predicate `8002DCF4`.
That predicate uses each actor's `+68` contact descriptor, signed X/Y offsets,
facing and strict rectangle extents. It has no reward side effects on a miss.
On success the contact routine:

1. Writes found state2 for an ordinary ID before healing completes.
2. Increments shared `PLAY+39` lives, caps it at9 and uses the native sound
   request (`80016C48`, command0/id15h) when below the cap.
3. Draws one shared native RNG value, uses its low two bits to select **2,4,8
   or16 HP units** from `80078BE8`, and calls `8004ED4C` once.
4. Sets phase2 for a player below its character's `PLAY+5B/+5C` maximum, or
   phase3 at full HP. The native tank path also uses the low-two-bit argument;
   it is separate from the delayed HP unit count.

Phase2 initializes a four-call byte timer at actor`+80` and units at `+7F`.
`8004EC30` adds one resident-player HP unit each fourth own call, preserving
the HP pending-hit high bit and stopping at max or the requested amount.
Native heal freeze writes the shared bytes `PLAY+10..17/+19`. Completion
clears that freeze, actor allocation bit08h and phase action, then enters
phase3. The healing HP belongs to the projected collector; lives, tanks,
found states and freeze are shared native state.

The current adapter replaces contact `8004EECC` with `pickup_collect` and
healing `8004EC30` with `pickup_tick`; both are configured native entries in
`game.toml`. It tries **eligible P1, then eligible P2**. A seat must be
lifecycle ALIVE and not a scene passenger. It advances to P2 only if actor
phase remains1, so a successful phase2/3 rescue stops the loop. Native RNG,
life addition and rescue state are thus called once in this source path;
two failed overlap probes do not consume them. Actual runtime interception,
cadence and simultaneous contact still need evidence.

For phase2, the adapter saves `{actor pointer, collector seat}` and projects
that collector through future healing calls until phase changes. Projection
changes the complete PLAYER body plus `PLAY+38` character and `+5E` armor,
then restores the resident body/identity while retaining native shared changes.
When Zero owns the one whole world pass, the same policy can temporarily
project P1 and preserve its mutated body for the outer restoration. This
source reasoning is not a measured local/netplay success.

## Infection, loss, damage and messages

Nightmare target selection at `80042D98` scans that same 80-slot pool for
allocated visible object4 with availability byte `+7==1`. It chooses a
strictly nearer candidate by integer X/Y squared distance; equal distance
keeps the earlier pool slot. `80042E68` revalidates that target. Approach and
contact routines `80040CB0`/`80040E3C` require strict integer
`absX<2` and `abs(NightmareY+28-ReploidY)<2`, then set Reploid`+7=2` and
perform the native Nightmare bookkeeping at `80042D3C`.

That bookkeeping is a **separate Nightmare consumed-bit matrix**, not another
Reploid found table. It uses byte selector `80075FE8[stage*2+section]`, a32-byte
row under `PLAY+178`, and the Nightmare actor's halfword ID`+88` for byte/bit.
The JSON pins the selector and this routine. Native payload packing also copies
the22 rows of32 bytes to relative `CEh`; actual actor-ID/table eligibility and
the resulting respawn/continue behavior still need runtime evidence.

The waiting Reploid tests rescue **before** processing this pending infection.
If contact fails and `+7==2`, `8004EA78` writes found state4 and enters
phase6/action2/subaction0, clearing availability. Its original infected
damage path calls `80031474`: a negative result writes state3, spawns the
native effect/message31h with `8004FF7C`, hides the actor and selects phase8.
Its offscreen-loss branch writes state4 and selects phase8. Ordinary waiting
offscreen cleanup selects phase7 without writing a found-state loss. These
paths must not be conflated in the seven per-ID cases.

The co-op adapter does not duplicate Nightmare infection or the Reploid world
actor update. Its existing generic native enemy-hit/player-contact extensions
also cover calls from the infected handler, but this audit does not establish
their gameplay outcomes. Infection/rescue scheduling, actual message/SFX
ownership, partner damage and native following transitions remain unverified.

## Report grants and native persistence

The original 128-word reward table is `8006D674`, indexed by native ID:
**88 no-item,8 Life Up,8 Energy Up and24 part assignments**. JSON rows retain
every exact code and source address. Code1/2 denotes Life/Energy Up. Other
nonzero codes are the distinct part bits2..25. Report member20's predicate
`800F05E8` requires a current rescued2 state and no prior mission-entry state;
newly infected/dead/missing entries cannot become new-rescue rewards.

The report's `800EA1F0` grant path applies separate once guards:

| Grant | Native once guard | Beneficiary/effect |
| --- | --- | --- |
| Life Up | `PLAY+6C`, bit8..15 by native table ordinal | Adds2 to max HP at `PLAY+5B+character` |
| Energy Up | `PLAY+6C`, bit24..31 by native table ordinal | Adds2 at `PLAY+61+character` |
| Part | `PLAY+70`, its exact original part bit | Shared part availability |

Here **character is active `PLAY+38` at the mission report**, not the remembered
rescue collector. The JSON records this distinction. A P2-owned delayed heal
does not establish P2 ownership of a later Life/Energy Up. The current code
does not retain a per-Reploid collector through reports. Changing this requires
a stated co-op grant policy and native evidence; this audit makes no change.
Native report messages use the report's original descriptor/UI routines.
Equipment selection, report paging/termination, actual stage-end destination
and availability to both seats remain independent checks.

Native payload pack `8001BD40` writes `80070CC4`; unpack `8001BA1C` accepts
a payload pointer in native `a0`. The relevant relative fields are:

| Native state | Payload offset | Width |
| --- | --- | ---: |
| Shared parts `PLAY+70` | `04h` | 4 bytes |
| Upgrade once mask `PLAY+6C` | `10h` | 4 bytes |
| Per-character max HP `PLAY+5B/+5C` | `36h` | 2 bytes |
| Per-character max energy `PLAY+61/+62` | `38h` | 2 bytes |
| Found states `PLAY+D8..117` | `44h..83h` | 64 bytes |
| Nightmare consumed matrix `PLAY+178` | `CEh` | 22 rows of32 bytes |

The extra-life increment at `PLAY+39` is run state: native unpack initializes
lives to2 or4 using the native parts flags. Do not expect that increment to
survive a cold continue from this payload. The offsets above are **not card
container offsets**. Checksums, card I/O/completion, actual saving and cold
continue were not inspected or exercised here. Only private native-card copies
may be used by the later owning runner.

## Concrete boundaries before a fix

- Native rescue's `PLAYER+D5` branch uses shared alternate body `800CD340` or
  `800CD3F0`. The current collector projection does not swap those vehicle
  bodies. Qualify or explicitly exclude that path before private vehicle work.
- The delayed `pickup_tick` has no separate collector-lifecycle guard. Native
  heal freeze normally prevents ordinary progression; obtain an actual
  death/absence counterexample before changing that ownership contract.
- Owner entries retain a pointer rather than an origin/generation. Verify
  deallocation, reuse and phase transitions before adding a guard; do not
  fabricate a reuse failure from pointer presence alone.
- Report rewards follow the native active character/shared masks described
  above. A source-backed policy decision is needed before changing grants.

No plugin correctness fix follows unambiguously without those additional
conditions, so this lane edits tools/tests/docs only. New-game/Tweaks options
can alter starting found states and original reward assignments; actual
candidate settings and patched bytes must be reported rather than silently
using this original-table audit as modified-campaign evidence.

Focused checks are `python -m unittest test_mmx6_reploid_rescue_audit` from
`tools`. Set `MMX6_CONTENT_EXE` and `MMX6_CONTENT_DISC` to explicit legitimate
local original paths to run the two original-data tests in addition to the
pure tests. They test all-ID losslessness, nibble boundaries/unknown values,
native store widths, source drift, hook/config binding, original-data hash
rejection, once-mask ordinals and refusal to clobber an existing audit. They
never mark a native rescue, failure or saved continuation passed.

Local validation passed all11 audit tests with explicit original-data inputs,
the standalone `--check`, and all8 existing frozen-inventory tests. The source
report contains40 hashed native/report windows,133 decoded direct-call sites
and23 placement-member bindings. These counts measure source coverage only.
