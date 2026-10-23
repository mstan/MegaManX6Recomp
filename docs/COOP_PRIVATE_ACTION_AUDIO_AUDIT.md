# Remaining private Zero audio ownership

R4 requires native X/Zero **jump, attack, hurt and death** tone identity against
co-op-off character references. R12 requires actual jump/hurt/attack overlap,
correct stop ownership and independent natural lifetimes. The ground-jump-only
candidate at8ad0301 does not close either whole family. This source-only audit
changes no runtime or ledger status and transfers no old candidate's outcome.
The [exact beeae10/a8f20cdc local failure](evidence/mmx6-jump-audio/manifest-bound-beeae10-local-failure-reviewed.json),
SHA `5ca0d23ff531dbdb7fac7a25ab6faefd2b39bb49e7ae6c20019db22c5f477cd1`,
still records Zero using X's sample and replacing P1's vocal. Its raw report
remains unchanged; netplay and all other audio families were unverified there.

The jump-only/current-candidate limitations below describe that audited v18
route. The later [body ownership repair](COOP_BODY_AUDIO_ROUTES.md) covers
body-owned group1 records1..8 and exact STOP5/7 callers on frozen v19. Both
100/100 suites and a paired gameplay smoke pass; native event/sample/STOP and
active private23 state qualification remain pending. The source audit is not
retroactively treated as native audio evidence.

The [reproducible metadata](COOP_PRIVATE_ACTION_AUDIO_AUDIT.json) pins the
original EXE, archive, executable Zero overlay, DAT85 banks,17 source spans,
all direct encoded callers and45 populated Zero records resolved to effective
bank/program/tone/sample/voice ranges. It contains hashes and metadata, not
instructions, VAB/sample bodies or disc assets. Original EXE SHA is
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.

## Executable caller scope and actual banks

Zero executable code is **ROCK_X6.BIN member1**, loaded801EA000,22964bytes,
SHA `75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00`.
ROCK_X6.DAT member85 holds its assets, including sound header/body11/12
(group1) and13/14(group3). DAT85 subasset10/type3 is sprite assembly, not that
executable overlay. These are separate source identities and must be retained
together. Neither a resident-only census nor an asset scan can establish that
Zero has no further action sounds.

| Exact source image | SOUND80016C48 | STOP8001750C | Vocal wrapper8003CFE0 |
|---|---:|---:|---:|
|Resident original EXE|128|20|5|
|Executable Zero BIN1|38|0|19|

These are aligned direct J/JAL calls, with a source-window hash for every site.
They are not a transitive call graph or proof against computed calls. In
particular **zero direct overlay STOPs does not mean no stop**: native Zero
actions call resident helpers which stop records1/5 and1/7. Stage/weapon/other
character overlays beyond the selected Zero bank remain separate scope.

The native group end/record pointer bases are80097738 and80097778, indexed
by group*4. Thus group1 uses8009773C/8009777C and group3 uses
80097744/80097784. P2 needs its retained **Zero** record table, not just its
projected character byte. Effective VAB handle must come from each record.

| Zero record family | Effective bank | Native voices | Native program/tone |
|---|---:|---|---|
|Group1 records1..6|1/effects|22|0/1,3,4,5,6,7 respectively|
|Group1 records7/8|1/effects|23|0/8,9|
|Group1 records9/10|1/effects|21|0/10,11|
|Group1 record11(0B)|1/effects|20,21|0/12,13; two native KEYONs|
|Group1 record13(0D)|1/effects|20,21|0/14,15; two native KEYONs|
|Group1 record12(0C)|1/effects|3|1/7|
|Group1 record14(0E)|1/effects|23|1/0|
|Group1 populated records19..31|1/effects|0,8,9,11 depending record|program2; exact rows in JSON|
|Group3 records0..12,15,16|3/vocals|20|program0;15 aliases tone11 and16 aliases tone12|
|Group3 record14(0E)|3/vocals|23|1/0|
|Group3 record17(11)|**1/effects**|**3**|**1/7**, same sample/tone as group1/12|

Group1 record0 also uses20. Populated records are metadata, not an automatic
runtime allowlist. Records15..18 in group1 and13 in group3 are empty. The
union of populated Zero voice indices is0,3,8,9,11,20,21,22,23. Original
SOUND increments voice and tone for each additional voice, wrapping tone16
into the next program. Record program-high-bit1 skips actor-position gain
adjustment at80016E90; retain native intrinsic stereo gains rather than
applying a generic pan rule. Exact sample offsets/hashes, note/shift/center,
ADSR and end markers are retained per selected tone in the JSON.
SOUND also distinguishes the raw group's80h flag from its group&7F table
index:80016D74 selects a different gain path when it is set. Preserve that
raw request as well as the record's separate program-high-bit. STOP's exact
group1/3 and globalFF contracts must not inherit SOUND's mask accidentally.

## Concrete action families outside the current jump route

| Source boundary | Original request/side effects | Remaining bounded route/evidence |
|---|---|---|
|80035898 /800372B0|Animation flag gates group1/5, voice22, sample7;80035AF8 requests1/6.|Observe the actual body action/frame/flag and accepted native input before assigning an animation name. Prove identity and later native stop; no inference from ground jump.|
|Zero801EC298; SOUND801EC2D0; wrapper801EC2DC|Native PLAYER+80 bit80 starts animation5F, group1/1 and vocal3/7, then action6; different caller from resident ground jump.|Original Cross during an eligible Zero airborne state; retain actual entry/action and event-time sample. The current ground-jump RA/parent checks exclude it.|
|Zero801EA038/801EA168; table801EE3BC via801EB1BC/801EB2B4|Saber/chain requests1/7 or1/8 on23; table pairs(7,3),(8,4),(7,5) select SFX and vocal. Wrapper retains PLAYER+8D suppression; some vocal paths retain native RNG gates.|Use original standing/air Square and consumed neutral, then a native chain only when its action/counter allows it. Capture every selected record and sample, never force a chain counter or voice choice.|
|8003963C; SOUND8003967C /8003968C|Native hurt clears HP's high bit, calls original RNG once, requests vocal3/(0 or1), then3/17 on effects voice3.|Reuse the source-bound record25 contact route: actual native strength4 HP loss/reaction/iframe, with event-time voice/sample and P1 overlap. Source entry alone is not accepted contact.|
|8003D850 ->8003D870; phase2 dispatcher8003CC78, table80073D20 ->8003D8A8 /8003D954|Fatal launch requests1/0D, voices20/21. Phase2 entry stops1/5 and1/7; after original countdown,3/16 and3/14 execute at8003D9B4 /8003D9C4.|A fresh owned native damage/death route, with original inputs and natural HP loss; retain pre-fatal/fatal/death phases and partner survival. No HP grants, success writes, forced death state or inherited hurt-only pass.|
|Zero801EDA90|Group1/21 uses a2=s1 while the surrounding actor is s0; other overlay calls also pass attack children.|Prove the actual parent/seat/pool binding before routing a child. Projected/world flags alone do not establish ownership of every shared actor callback.|

Other overlay records include1/14,1/20..28 and further wrapper records3/3,
3/5,3/8,3/9. Their exact callers are inventoried; their original ability,
action and earned-progress prerequisites have not all been closed here.
Retain these as specific remaining work, not absent or inapplicable. Broad
interception of every sound made while Zero is projected would also risk
shared-world callbacks and non-character groups.

## Stop ownership: the immediate nonjump22 gap

Original STOP does not perform SOUND's disabled-channel or record-end guards.
For a character record it directly decodes first=(byte3&31),
count=1+((byte3>>5)&3), then for each contiguous voice performs
**volume-zero8005BC14(voice,0,0) followed by KEYOFF8005AD40(voice)**. Its valid
record result isFF000000 even for multiple voices. GroupFF executes the pair
for every hardware voice0..23 and returns0. Empty/malformed records cannot
authorize a private route merely because this decoder would select a slot.

The exact Zero1/5 record selects22, which P1 also uses for native jump SFX.
Its six resident STOP sites are800385FC,800386EC,800387E4,800388F8,
8003B234 and8003D8BC. Source800359AC ->80039FFC, if nonzero,
800359BC ->8003B218 ->8003B234 is one concrete stop path; the direction/countdown
branch at800385F4 and phase2 entry8003D8A8 are others. Record1/7 selects23;
its STOP sites are8003D8C8,8003F494 and8003F60C.

The current candidate mirrors a nonjump stop **after** executing native STOP.
That can retire a prior private jump but leaves the hardware22/23 stop intact.
Thus it is not a fix for P2's nonjump stop ownership. A narrow next repair
should prove a P2-owned call/context and exact retained record, redirect both
volume and KEYOFF into its private range, and preserve native results without
touching P1 hardware. Phase2 death must be admitted deliberately; the current
phase1-only jump predicate excludes it. Do not use a broad phase relaxation
or swallow another actor's/shared stop.

Shared groupFF is a different contract: native once plus all **title-owned**
private voices. Resident800349EC is original **personal-menu setup** through
80034830/80073998 ->80034874/800739A4; it is not the player's phase2 death
handler. Keep menu/title/retry/reset global semantics separate from the six
character1/5 sites. Preserve foreign private voices on teardown/global stop;
an active-mask bit or bank number alone is not a lease.

## Frozen X4 comparison and implementation order

The actual local Git object at frozen50593bca was read, not current X4 WIP:
`src/mods/mmx4_coop_audio.c`, blob
`f490a1725aac5775a3e6711305370c279362dceb`. It projects whole character
group1/3 tables, saves24 P2 priority bytes, uses private activity for original
voice selection, computes native pitch/gain/ADSR uncharged, restores hardware
records/queues/masks, and routes **both** volume and stop through private slots.
Global silence calls native once and stops private voices too.

Carry those ownership contracts into X6, not X4's addresses or34h metadata /
48h queue backup. X6's already-audited2304-byte driver transaction,16-word
end history,38h voice records, temporary VAB tables and callback/null guards
remain required. The current jump transaction is a useful bounded foundation.
It should not be replaced with X4's asynchronous VAB-open status/gate shortcut.

Prioritize these concrete steps:

1. Close the exact P2 nonjump1/5 and1/7 STOP boundary and native-global
   distinction; test pending P1 KEYON/voice state survives P2 stops.
2. Add primary Zero saber/chain and hurt requests, selecting original effective
   bank/program/tone from the retained record. Preserve native RNG, PLAYER+8D,
   status, priorities, actor spatial gains and suppressed/no-KEYON outcomes.
3. Support multi-KEYON records and a per-title owned voice/bank set. The same
   P2 slot20 legitimately uses either effects bank30 or vocal bank31; treating
   its own other bank as foreign is not a general model. Keep true foreign-bank
   conflicts refused. Include program1/2 and cross-bank3/17.
4. Qualify original phase2/fatal/death, acquired techniques and source-bound
   child actors separately. Shared groups0/2/6, music and world SFX keep native
   routing unless their own ownership contract is proven.
5. Extend current-build digest/snapshot and epoch readiness for every added
   priority/owner/pending field and private DSP binding. Preserve rejection of
   active calculations, malformed input and abandoned transactions; do not
   migrate old snapshots or restore another native bank's pending work.

Meaningful helper tests should execute native STOP's ordered call ABI/return,
exercise1/5 /1/7 /stereo ranges and globalFF, reject empty/foreign/out-of-range
records, verify source aliases and tone rollover, and assert full native-state
restoration before private play with zero/one/two KEYON outcomes. Real-plugin
tests still need P1/nonowner/caller rejection, private priority/status selection,
foreign slot preservation, natural own-bank reuse, epoch reset, setup failure,
current-build warm/cold DSP restoration and nonjump stops. Source/mocks alone
do not prove native lifetime, sound identity, PCM equivalence or audible output.

## Native qualification plan and retained limits

Run fresh local and two-peer **same-machine** cases on one exact new image and
manifest, retaining the existing failed attempts. Start with ordinary Zero
saber, source-bound hurt and P2 nonjump stop while P1's real hardware sound is
active. Use accepted original inputs and complete event-time SPU records;
identify exact bank/sample bytes, note/pitch/ADSR/mode/gains and natural
END_STOP/KEYOFF/volume ordering. Reverse overlap order so a P2 first sound also
survives P1's next native request. Require visible native action/contact and
continued independent controls. Function-entry counts, ACKs, active bits or
shared slots alone cannot pass any of those checks.

Then perform fatal/death's stereo and later vocal/effect sequence, preserve the
living partner and its sounds, and compare a co-op-off native Zero reference
on the same image/source. Any private Zero-availability prerequisite remains
an explicit bypass, never earned-progress evidence. Default fresh runs cannot
qualify acquired techniques, other forms/rosters or a campaign's whole sound
closure. Per-peer resolved core/mod samples and both mode-specific receipts
remain necessary; no cross-image/roster transfer follows from this audit.

Five new source tests pass, including bounded execution of original STOP with
modeled leaf call recording, exact source/X4-object reproduction and malformed
bank/alias/range negatives. This execution never invokes a native game or SPU
device. Reproduce with non-C TEMP/TMP/PYTHONPYCACHEPREFIX and explicit original
`MMX6_AUDIO_EXE`, `MMX6_AUDIO_DISC`, `MMX6_AUDIO_X4_REPO`:

```powershell
python tools/audit_mmx6_private_action_audio.py --original-exe <original-EXE> --original-disc <raw-BIN> --x4-repo <local-X4-repo> --out docs/COOP_PRIVATE_ACTION_AUDIO_AUDIT.json --check
python -m unittest discover -s tools -p test_mmx6_private_action_audio_audit.py -v
```

No games, title builds, SDK/plugin/CMake/ledger changes, remotes, source cards
or speaker output were used in this lane. R4/R12 stay open beyond ground jump.
