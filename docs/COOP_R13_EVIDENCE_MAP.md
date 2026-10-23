# R13 authored placement and historical evidence map

R13's native X6 analogue is identified: intro stage0/section0/checkpoint0,
primary record25 at `800FA2DC`, category0/type1/subtype1, authored at (416,1080).
The ledger now passes this bounded record locally and over loopback netplay on
compiled candidate `fbba0e3ae5e38174022fa7eb79ac81c3741ef391`, executable
`37cdc4876f7e852b97ef5f14210809b0af7d4a8adaa1759c9e096017170e1fa9`.
The [fresh receipt](evidence/mmx6-r13/manifest-bound-fbba0e3-summary.json) retains
the canonical compiled manifest, clean source provenance, independent native
outcomes, actual zero-cycle host agreement, 46 resolved core/mod samples and a
fresh startup. Its scope remains intro record25 on this exact artifact.

The historical receipts below establish executable hashes without proving which
source commit produced them. They remain supporting history, distinct from the
new formal ledger receipts. No candidate commit is inferred from staging-time
source observations, and the old failed reports remain unchanged.

The machine-readable supporting index is
[historical-ledger-map.json](evidence/mmx6-r13/historical-ledger-map.json).
It preserves original report results, separate reanalysis, artifact hashes and
the remaining qualification gates. It is supporting metadata, not a formal
passed ledger receipt.

## Authored scanner and instance identity

The source audit is
[COOP_PLACEMENT_ADMISSION_AUDIT.md](COOP_PLACEMENT_ADMISSION_AUDIT.md) and its
[JSON metadata](COOP_PLACEMENT_ADMISSION_AUDIT.json), committed at
`42c82d5efec6b2cd32fc243b86e2e7e721c31e14`. It pins the original USA v1.1 EXE
SHA-256 `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and `ROCK_X6.BIN` member2 SHA-256
`d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607`.

| R13 requirement | Concrete X6 mapping |
| --- | --- |
| Actual authored placement | Primary scanner `80029F38`, stage/section root `8007349C`, movement driver `80029D18`, record25 `800FA2DC`. Categories0..2 allocate through `8002BBF4`. |
| Primary stays behind | Native 4:3/margin0; P1 held at x144. The stationary P1-only camera (0,944) scans the strict rectangle `(-48,368) x (896,1232)`, which excludes record X416. The source-derived preflight permits an already shifted camera only while `0<=C && C+368<416`, Y944, with the record inactive and no live matching origin. |
| Progressing P2 admits placement | P2 movement changes the shared midpoint camera. Rightward admission scans strict `(C+336,C+368) x (Y-48,Y+288)`; the selected crossing near C50 contains X416. X6 has one authoritative shared view, rather than X4's separate views. |
| Native initialization | Search all48 slots `[8008EF48,80090C88)`, stride `9C`; require exactly one active slot, type1/subtype1 and origin `+10=800FA2DC`. Init `800EAFFC` writes HP `+5C=12`, strength `+60=4`, phase/action `+4/+5=1/1`. A record bit or stale freed-slot pointer is insufficient. |
| Actual native interaction | Alive body `800EAC8C` calls native hit `80031474` and contact `80030ECC`. Retain the same live slot/type/origin and an HP reduction or native death transition after P2's accepted native attack input. The historical runs exercised attack, not separate contact damage. |

“P1 outside the window” is the admission discriminator: the authored record is
outside the stationary P1-only placement rectangle. It does not mean P1's body
must be outside the shared camera. P1 remains fixed while P2 moves that camera;
there is no supplemental P2 world update in this mapping. The scanner's strict
inequalities, inactive-record preflight and live origin binding keep admission
distinct from an already active enemy or a stale slot.

## Historical results, preserved separately

The full reports remain under `G:/Temp/Codex/psxrecomp/x6-parity`; their exact
paths and SHA-256 values are in the index. Existing compact receipts are
committed under `docs/evidence/mmx6-r13/`.

| Receipt | Original result and supported observation |
| --- | --- |
| Two early bd7 attempts | Setup rejections only: an inactive renderer preference was mistaken for active widescreen, then a literal camera0 check rejected valid camera2. Neither attempted the route. |
| v10 first route | Original `failed`: origin-bound HP12/phase1 initialization succeeded with P1 fixed, but walking stopped before the terrain rise. No attack was attempted. |
| v10 jump correction | Original `passed`: camera50 admitted record25; native initialization HP12/phase1; one native jump crossed the rise; P2 Square produced native action48 and the same actor's HP12/phase1 -> HP0/phase2. P1 stayed x144 in all137 retained observations. |
| v11 local original | Original `failed`, preserved unchanged: its reducer missed the already recorded HP4 window-start sample after Square and examined a later freed slot. |
| v11 local read-only reanalysis | Separate twelve-check `passed` result over that original report: camera51 admission and HP12/phase1 initialization; the same live origin's HP12 -> HP4 after P2 Square, then natural deallocation. P1 stayed x144 in all197 observations. No second v11 local launch was used. |
| v11 paired | Original `passed`: both peers admitted the same record at camera53 and initialized HP12/phase1; published peer1 host inputs traversed the route and caused an origin-bound HP drop and natural deallocation. P1 stayed x144 in all121 paired observations. |

The v10 executable SHA-256 is
`a2f0d2c994db8deece0cb162114e74a225b8151a6c35940d5aa1651132544bc0`.
The v11 local and paired receipts share executable SHA-256
`43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7`.
These are historical executable identities, not claims that an observed source
commit was compiled or that the later manifest-bound candidate was exercised.

The paired v11 profile was `mmx6-x-zero-delay-v11`, delay3, two loopback peers,
with default Seamless Loading. P2 route inputs used the published peer1 host
device through transport; offline inputs used the native port2 pad path. There
were no fixture/mailbox, guest RAM, success-flag or source-card writes. The pair
retained37 equal-simulation-tick resolved core/mod CRC samples, including seven
post-route samples and eight after native pause/resume, with no reported desync.
Those samples qualify the observed windows, not every transition frame. HP4/HP8
peer observations tagged publication1432 were separate advancing RAM reads,
so they are not an atomic matched HP history. The byte-identical composed
capture was a stable paused menu; independently timed gameplay captures were
inspected but had different idle poses and hashes.

## Remaining R13 gates and scope

Repeat this source-mapped case locally and over netplay on one fresh, clean,
manifest-bound candidate. Each formal receipt must bind the actual executable
to its exact candidate commit and retain settings, accepted P2 input, the
pre-admission absence, stationary P1, origin-bound HP12 initialization and
native attack outcome. Retain actual resolved core/mod CRC windows for the
pair and artifacts with their hashes. Only those reviewed receipts can change
R13's per-mode and aggregate statuses.

The bounded native analogue is known; there is no need to invent another
scanner or import X4/X5 addresses. This mapping does not qualify every enemy,
stage, difficulty, camera lock, vertical route, physical controller, cross-host
session or audible output. Natural contact damage remains unexercised here;
the row's attack-or-contact interaction is supported by actual native attacks.
The narrow type1 proximity action1->2 fix has separate before/after evidence;
nearest-player AI across all enemy actions is not an R13 admission prerequisite.

Independent once-world cadence is also a separate contract. The later
[native-world trace](COOP_NATIVE_WORLD_TRACE.md) supports a bounded ordinary
intro enemy-world count, while its stricter route HP-sample check remains
failed. That report is not a replacement passed R13 receipt, and a universal
world counter is not an additional R13 gate. Earlier documents retain their
milestone-era limits; this map defines the current R13 disposition.
