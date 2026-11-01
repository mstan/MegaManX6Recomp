# Complete the remaining 74 Mega Man X6 frozen comparisons

## Objective and authority

Read this file and carry the X6 burndown through to **zero unresolved items**. Start from **159 passed, 0 failed, 74 unverified, 1 inapplicable = 234**. The 74 checks listed below are the remaining work. Implement and qualify applicable behavior; explicitly reject a comparison only with a concrete compatibility/design reason and evidence; use N/A only with positive original-X6 content evidence. Preserve distinctions between passed, rejected, failed, unknown and inapplicable. Difficulty, missing setup, elapsed time or unavailable capacity is not rejection/N/A.

The owner explicitly authorized subagents for this task, routine necessary instrumentation without repeated approval requests, use of measured spare capacity, and continuation until all items have final dispositions. **Do not push, create PRs, publish, or perform remote Beads sync.** Preparing this handoff did not activate another goal.

This is ONLY the **234 frozen X4/X5 comparisons** and their actual X6 counterparts. The separate native3330/1665-case campaign is excluded. Do not repeat an audit of the entire native game or silently expand the frozen acceptance criteria.

Read and apply the current owner/project instructions:

- `F:/Projects/psxrecomp/AGENTS.md` and `F:/Projects/psxrecomp/_wt-mmx6-x4-parity/AGENTS.md`.
- The owner's latest conversation authorizes parallel helpers and measured compatible work, superseding older solo/one-total-job instructions. Older setup/attempt expenditure remains historical evidence; it is not permission to stop the campaign or erase the work.
- Keep support work minimal. Reuse existing validators, source proofs, fixtures, snapshots and raw data. At most ten minutes designing a necessary tool change, then simplify and return to actual implementation/native validation. No new general harness, inventory or receipt pipeline.

## Workspace and authoritative records

- Main worktree: `F:/Projects/psxrecomp/_wt-mmx6-x4-parity`, branch `feature/mmx6-x4-parity-local`.
- Campaign HEAD before this handoff document: **76b5cba2690d1fac0998fab1d6476ab1e1d2d279**. It includes all five closures below and the retained F153 LOCAL component.
- Ledger: `docs/COOP_PARITY_LEDGER.json`; generated view: `docs/COOP_X4_REFERENCE.md`.
- Scratch/evidence root, abbreviated **B** below: `G:/Temp/Codex/psxrecomp/x6-parity`.
- Live pointer/retention record: `B/storage-retention-index.json`. This file becomes its current handoff pointer. Live ledger/job records take precedence over older TXT handoffs.
- Central Bead: `beads-gxrh` remains IN_PROGRESS. Game hierarchy is `beads-eio.1`. Claim/update the owning issue before implementation; do not create a second issue database.
- Existing goal tooling may show an old blocked label. That is not evidence that the 74 are complete or a reason to repeat the previous campaign stop. Honor this new owner instruction and any current goal-system status rules; never mark an unfinished objective complete.

Validation commands (run from main):

```powershell
& 'C:/Users/Matthew/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B tools/build_mmx6_coop_reference.py --render
& 'C:/Users/Matthew/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B tools/build_mmx6_coop_reference.py --check
```

Both passed at 159/0/74/1. When editing the ledger preserve LF bytes; `Path.write_text` under Windows otherwise produced a whole-file CRLF diff. Keep root the sole ledger/index writer. Qualify each required LOCAL/NET mode on the same exact compiled candidate; do not transfer credit between builds. Prepared/built/source-tested is not native qualification. Reuse sufficient completed components rather than replaying them for cleaner reports.

## Clean handoff / owned processes

**All agent-owned native games and compiler jobs are stopped.** The last C125 canonical pair's `B/F179-c125-canonical-net-owned-1.json` is terminal with exits `[0,0]`; parent52708 and game54808/57816 are gone and TCP30228/29 plus UDP35228/29 released. C131 pair73924/68628 exited0; TCP18180/81 and UDP35180/81 released. Never kill a bare historical PID: PID73924 was later reused by an unrelated `conhost`.

No live owner playtest is being handed over. Existing idle subagent sessions may still be listed; reusable names were `approach_death`, `focus_check`, `lift_checks`. `focus_check` twice hit infrastructure `Bad Request`; `lift_checks` successfully took over its existing pair without relaunch. Inspect exact process path/creation identity and current job files before resuming any purported active job. Do not start duplicates or kill unrelated work.

## What was closed in this work block ? do not replay

| Comparison | Local commit | Qualified candidate/evidence |
| --- | --- | --- |
| F61 | `641a9fb` | C129 all eight Either/Both-living/actual Select-ABSENT/native-FALLEN door components, LOCAL+NET. |
| F75 | `bd7f9e4` | Exact V56 original P2 boarding animation and actual composed midboarding on LOCAL and both NET peers; final CRC/cards/exits. |
| F123 | `1201a64` | C129 living wait/abort, real absence and primary FALLEN portal admission in LOCAL+NET; original CP2/full48HP boss/feet/controls. Fresh checkpoint legitimately respawns fallen, preserves voluntary absence. |
| F113 | `d69faea` | C130 original five-frame rain before/after actual primary DYING/FALLEN in LOCAL+NET; survivor rain/control/final CRC/cards/exits. |
| F180 | `76b5cba` | C131 independent Sub Tank native16/8 energy retained across original checkpoint, P2 HP11?19/P1 HP13?29 with isolated drains, LOCAL warm SAVE/LOAD, NET final CRC/cards/exits. |

R16 is the one existing content-backed N/A; F175 was already passed separately. F113 does not grant F120/F175/general palette/fade credit. R16 does not make the whole vehicle family N/A. F75 does not grant F60 enrollment or F93 solo timing.

### Current C131, preserve exact source/observer distinction

- Source tree: `B/worktrees/x6-subtank-prerequisite-v131`.
- Runtime: `B/build-subtank-prerequisite-v131/runtime`.
- **Compiled clean game commit:** `1ff585f0bbe6a673bb37f67889ebf590c26cbc70`.
- Later observer-only commits: `f37eafcb298239739e4948fbe3063e2928cc98bd` (parsed preference scope), then `57afe1c` (missing read width). Read current full HEAD rather than relabeling the compiled provenance. Declared game/generated bytes are unchanged and normal source validators passed.
- EXE SHA256: `01bf3bb87fbf22e02699992d5edfe4c4e7f09887d77ab2ff1f912c7736c9fe29`.
- Compiled declared manifest: `4dcd76e0a1e4e40db49b47b0f43c1d7992471b407c13cefbb2fc552f0c523ad1`.
- Title79 / profile62 / snapshot21; semantic contract `90aeb241f26d37cadfa2209dbc6d29f2ca8b3f57fee245422bab37a34267f5ef`.
- SDK `3be00a63ec0ee2b5d412eff8f25ce02a555f765c`; UI `fe667e2b9a992c67f82e421c926258cab0225a0a`; net `e53059306824edf4f0aec4aae5ae65151b18535f`; RB `b29bdde...` (read exact repository identity if needed).
- One real build, one compiler; 10 affected Ctests and 59 Python checks (one source-environment skip), Ruff passed. Actual all298 runtime units have session resources=1. Never copy/forge a CMake cache or pretend a transported source tree was built locally.
- Genuine generated junction remains C126's generation at `B/worktrees/x6-ray-origin-v126/generated`. Preserve it and all SDK/UI/net/RB junction targets.
- C131 alias20 `intro_subtank_cp2` maps the original introCP2 record/index2 with nonce `4C535432`. Declared independent native16/private8/acquisition seed happens before original8?9; existing HP13/11 applies afterward. Existing once/taint/profile/snapshot state reused, no new mutable field/schema. This seeds prerequisites, never the claimed heal/retention result.
- Full passing evidence: `B/F180-c131-native-subtanks-local-2` and `B/F180-c131-native-subtanks-net-1`. Preserve failed LOCAL1 (read width before any fixture), source/observer commits and all raw/card data. Bead133 closed.

### Qualified C130, if a ready case needs it

Source `B/worktrees/x6-native-supported-fatal-v130`, commit `166d38e06c99f8c23d86236e6136ea325ba59b04`; runtime `B/build-native-supported-fatal-v130/runtime`.

EXE `4c18e4c9e3ba4e29d9de75efd31fe6f318cc5ec87d343d28a6cb6f64e798096e`; declared `368e9d3db9f4c7fafa6de82e1ad1a16e3e871443cef3f241596dd98a59539606`; title78/profile61/schema21. Default-off fatal prerequisite accepts terrain70 OR actor-contact71 support8, while retaining other idle/lock/alive guards. Original350F8 clears71; actor paths2E3C4/2E658 accumulate support8, terrain2F2A4 clears70 separately. No weather-renderer change was claimed for this QA guard correction.

Passing evidence `B/F113-c130-weather-local-1` and `B/F113-c130-weather-net-2`; all10 LOCAL atlas images and four representative physical NET before/after images were personally reviewed. All old failures retained. Main `9bb458d` passes the existing `transport_window` callback to paired native observers; 26 pair-option and16 intro tests passed using G TEMP.

## First useful next actions

### 1. Finish F179 review / only the genuinely missing canonical endpoint

Same C125 candidate already has LOCAL both rosters/all four menus and **fully complete inverse NET** Zero/P1+X/P2. Reuse it.

C125 source `4fe5075c8a2dddcd39382aec4589ba27fbda419f`, tree `B/worktrees/x6-inverse-roster-v125`; runtime `B/build-inverse-roster-v125/runtime`.

Image `6d4df73bc0ad23f41bff12832820644ba7e8198f9a92cc15215c53e0702e504a`; declared `3d3398cc6297f18b20bcbbddda2f483291e47c4de8407dcc2a4bc7ab4e17cb07`; title73/profile56/snapshot20; SDK/UI same3be/fe667.

Inverse NET complete evidence: `B/R9-F179-c125-net-peer-0-2/control-observations.jsonl`: line422 Zero menu/art,425 otherStart rejected,428 owner resumed,453 Zero action48 both peers; later than case CRC45920/45952 line785. XP2 menu line801, wrongStart804, ownResume807, Xcharge/shot/lifetime/recovery901 onward, final case CRC57984/58016 line1115. Both exit0/cards unchanged. A later optional first-R1/F174 stop does not erase these earlier qualified components. Do not replay inverse.

**New canonical pair was completed and closed during this handoff.** Profiles:

- `B/F179-c125-canonical-net-peer-0-1`
- `B/F179-c125-canonical-net-peer-1-1`
- Existing jobs `B/F179-c125-canonical-native-net-pair-job-1.json` and peer job1 files.
- Owned terminal file `B/F179-c125-canonical-net-owned-1.json` exits0/0.
- Original focus raw: peer0 `control-observations.jsonl`; successful takeover raw: peer0 `logs/takeover-control.jsonl`, SHA `4554d83fd177a8fb992a696cda3709cb420c690bb42bc6bf863a28049a27c750`.
- Actual images in both profiles' `logs/takeover-{P1,P2}-owned-native-menu.png`, `takeover-selected-core-attack.png`, plus initial/after-dialogue images.
- It was still in **original Alia conversation**, not free gameplay, when diagnostic magic was absent. Ordinary Cross advanced the conversation; canonical native roster `[0,1]` then published. Do not label the pre-enrollment dialogue a disabled mod/PC0 failure.
- Both own native menus/art completed, opposite-seat freshStart ignored, ownStart resumed, coreweapon0 retained, HP32/ammo288 preserved. Actual Zero action48/frame61/69 and visible native Saber; X held native20h and charge clock4/7?0 on release.
- Final common profile56 before tick0/cycles0 and final fixed selected `fee00757479c53290da026a82293d376a0455f7c202f9b8b8a53b4d74a30da8e`.
- Later-than-case baseline148086, matching resolved core/mod tick148096=`ee124569/97f0165a`,148128=`e6c6070b/5f97ab9c`; final both ALIVE/HP32/action2/scene0/owner0/ready+enrolled1/desync0. Cards authored4e2c... and blank7706... unchanged, native exits0/0.
- **Honest limit:** the transient X basic projectile was not captured. Samples were while held and24ticks after release, when pool/counter was0. Do not turn this into a projectile observation or R9 pass. Review F179's actual frozen selected-ability requirement against the retained native charging behavior; if actual projectile remains necessary, exercise only that missing X endpoint on the same build and reuse all completed menu/inverse work. No full F179 closure was claimed; the official count stays74.

### 2. F153 LOCAL is qualified; NET needs actual fresh stage1/finisher/follow-up

Main `c2191c6` records LOCAL passed and NET unverified; whole comparison is unverified. Preserve that distinction.

C119 source `ed7aff74194154b5a93818611a0db5651f139440`; image `13f007a1b738cff0443967f9075fffecffd6c60b0a1586ff312a2fc4aa01fdfc`; declared `c97939d2c662832b009c67532a08f79f1647b6f325143aac07637f93f3b5bf9d`; profile50; oldSDK57055/UI34b527. Root `B/server-build-v119-root-v1`.

LOCAL `f153tl` reached native children24/25/26, finisher HP48?43, then a fresh accepted child24 and HP43?42 **before a Python parser-shadow exception**. Exact `f153tl/candidate/jump-audio/control.jsonl`: RPC5382 P2idle/CB2/nochildren;5387 Sigma61 HP43/recovery0;5396 fresh Square ACK +5397 real P2pad;5398 tick2724 P2action48/CB0/new visible owner2 child24 allocation1;5403 same Sigma HP42/action3/recovery9998;5404 neutral/5418quit later. Root independently decoded the same four pinned parsers and viewed finisher/terminal hit images. Parent remains failed_setup; do not forge parent PASS/replay/final counter claims. Offline finalCRC was not an additional frozen gameplay requirement. Cards unchanged/ownedexit0. **Do not replay qualified LOCAL.**

Fresh source-only variants tracking2 fix parser `f`?`finisher`; tracking3 removes an invented Sigma action4 setup condition. Other native hit/geometry/HP gates unchanged. `f153tl2` missed stance; `f153tn2` got to36.59px but action4 gate blocked it; all raw retained. Latest `f153tn3` actually accepted CB0/type24 on both peers, then stage1 Square offer639 never produced retained CB1/child25. Online observer ACKs were null, so a consumed fresh edge is unproved; no demonstrated cooldown bug. 22 initial CRC matches/profile50 passed, final F153CRC absent. Peer0 exit0; peer1 owned-terminated after exit deadline (exit1), cards unchanged and ports29931/32 released. Reassess that concrete input-window prerequisite rather than another unchanged rerun/geometry tuning or a game-defect inference from input offers.

### 3. F37 prepared pieces, exact C120 only

C120 source `3172b181c0e565030cd2403ff935ae46e8ab50e4`, image `f0076a5c5813390837566c5865aa876a4b632bf4a55f6cc6f3b6ab205d5bda2f`, declared `3da52934f8f56cac9625e29a22d0f30a88b5bcec94b1adfd23405569891722ab`, profile51. C130/C131 do **not** inherit BlackZero support; do not transfer credit.

- Existing wrapper `B/server-build-v120-root-v1/run-existing-F37-pair.py` SHA `99d5ace79ae27d30624e128211498cc98440ec361934d99241e9915ee7d4b6af` reapplies four native form preferences after the final writer/before network selection hash. Old NET writer erased them; old source/forms failures preserved.
- Old wrapper SHA01e8... retained beside it. Both fixed callback invocations are idempotent; parsed TOML regression and Ruff passed.
- Retained C120 `docs/COOP_PERSONAL_MENU_CURSOR_AUDIT.{md,json}` proves pristine Zero **DOWN?UP**, published0040?0010, cursor0?0D?0. Old UP?DOWN assertion was wrong for unearned equipment.
- Corrected MENU-ONLY job `B/server-build-v120-root-v1/f37l-down-up-native-job.json`, fresh profile `f37l-down-up-1`, is prepared and unrun. It is not a full F37 recipe.
- Ultimate producer is concrete: retained F65 source note/helper `B/mmx6_F65_native_camera_v61_root_v3.py`; ordinary R2=0200, native E7=4/action0x22/phase0..2, E0=7A=1, PLAY1C=1, source801EC4C0..678; require real launch/effects/cleanup.
- BlackZero producer is concrete: original PLAY5Fbit20 changes weapon cost. Original8003EB64..EBC0 computes table80073DF4[5]*4=48 Black versus*6=72 ordinary Zero **when bodyEC&20 is clear** (earlier override branch must be handled separately). PL01 SHA75a142...;801EA6A4 requires C9bit80 +fresh80bit40/R2,801EA6CC calls cost(index5),801EA700 selects weapon5,801EA770 sets action3B,801EA764?8003F740 subtracts cost from B2. Real BlackGiga energy288?240 with P1 unchanged is a native form-specific endpoint; palette alone is insufficient.
- C120 supports genuine `recycle_fallen_cp2`/guest fixtures: chosen actor x1312/y1593, safe other x1506, original282F0 fatal beyond y1688. They refuse earned-weapons/starting-HP extras. Do not override that guard. The survivor's second-fatal/native team-retry route remains unqualified. Ability and death/state components may use separate declared fixtures on the same compiled candidate; do not invent a requirement that everything fit one LAB profile. Still actually prove required death/retry/current-build restore, rather than treating a load as a retry.

## Other preserved limits / avoid wrong shortcuts

- Preserve old R9/F179 C125 work, all other parked candidates, failed setups, old native3330 evidence and the original paired HUD harness. A stale heartbeat `cpu.pc=0` alone was also seen during normal progressing execution; it does not establish actual PC0/TCB corruption. Original B0/TCB problem remains unproved without causal evidence.
- F104 remains unidentified: retained NorthPole option11/CP3/index10/nonce4C4E4933/record80072270/DAT96 floorY1616/code3C proves ordinary solid classification, not material-dependent slipperiness. `30304?3C`, dispatcher2F9DC routes3C to2FBA4 same ordinary38 resolver. No valid drag producer/character expectations; don't launch an ice test based on the name/art. F189 retained runner is **HeatnixCP7**, not NorthPole. No N/A from missing proof.
- F130 needs same persistent allocation/owner duplicate suppression and natural rearm/later accepted contact. Return126 is an observer proxy, not a frozen mandatory value. F131 one Zero44 cast is not duplicate/rearm proof.
- R10/F115 require actual water-entry/ripple producer; rain is not water. F117 one-versus-four damage without a distinct original reaction doesn't prove reaction differences. F151's one native Zero-return component doesn't cover every story scene.
- F4/F103 C124 LOCAL owner-death/arrival components were preserved; NET matching scene-phase setup still missing. A C129 both-idle fatal setup does not itself test death during beam-in.
- Source discoveries/rejected mappings and prior spent time/attempts must stay in existing records. Resume a parked item from a concrete new fact/implemented fix, not because a new session reset the clock. When no short closeout is ready, choose the least-cost concrete implementation with a native endpoint and continue; don't cycle indefinitely through unknown-producer inventories.

## Capacity, tools and issue tracking

Use measured CPU/GPU/RAM/storage pressure, not declarations/leases as automatic vetoes. Compatible jobs can share a physical host when real headroom fits; retain reproducible matched pairs and serial per-component qualification. Queue patiently when actual pressure is high. Bound native parallelism and I/O, at most2 compiler jobs (recent builds used1). Don't require an otherwise idle PC or kill unrelated work. PC, SERVER and Deck are the pool; verify backend/profile/space before choosing another target. SERVER had two real watchdogs and several passes; retain failures, don't guess their cause or force a host profile.

Installed capacity runner:

```powershell
& 'C:/Users/Matthew/.pyenv/pyenv-win/versions/3.12.5/python.exe' -B 'C:/Users/Matthew/.local/bin/benchmark_hosts.py' probe
```

Use existing `run --host local|server --os windows --owner ... --class timing|build --cpu ... --gpu ... --memory ... --disk ... --job-file JSON --out JSON` jobs and exact Windows argv/env. SERVER Python is `C:/Python311/python.exe`, SSH alias `server` with existing strict identities. Deck has limited scratch; don't start an unrelated Linux setup project merely to create activity.

Engineering Python `C:/Users/Matthew/AppData/Local/Programs/Python/Python312/python.exe -X utf8 -B`; Ruff `C:/Users/Matthew/.pyenv/pyenv-win/versions/3.10.9/Scripts/ruff.exe check --select F821,F822,F823`. Set TEMP/TMP process-locally to an owned G directory (e.g. `B/temp/main-integrated`) for old tests with an F/G-only output guard. Do not make machine-wide environment changes.

Beads CLI `C:/Program Files/nodejs/node_modules/@beads/bd/bin/bd.exe --sandbox -C F:/Software/beads/issues`, env `BEADS_DOLT_SERVER_PORT=30835`, `BD_DOLT_SERVER_PORT=30835`. No remote sync/push during this task. Main campaign IN_PROGRESS; F61 bead119, F123 bead118, F113 bead74 and F180 bead133 closed at qualified evidence; r0kq still covers open vehicle-family work. Find existing F179/F153 owner before edits rather than duplicate issues.

Ghidra: configured headless MCP only; no GUI/new server/lock forcing/process kill. A fresh `registry_list(filter='psx/')` timed out180s during this handoff; earlier read-only MMX6 open had a lock. Preserve others' work and use existing original-source/disassembly artifacts rather than treating that as campaign termination.

## Preservation, QA and completion conditions

- Background native runs hidden/muted using TCP input, RAM observations and renderer captures; preserve desktop focus. Owner-facing QA windows, if later requested, must be normal windows with normal audio. No live owner playtest exists now.
- Preserve original/native cards/settings/ROMs and all accepted/failed raw evidence. Current-build snapshots are disposable/build-specific; no legacy save-state migration obligation. Never damage native saves.
- No drive-wide or multi-project recursive searches. Scope exact repository/files, respect ignores, foreground timeout, no `-u/-uu`. F: is slow SMR. Probe free space/I/O before bulk work; do not leave huge agent-created scratch untracked.
- Retained C129/C130/C131 worktrees/builds/profiles are ongoing evidence, as are C125 canonical and C119/C120 partial profiles. Old and new generated/SDK/UI/disc links are controlled junctions. **Never recursively delete through them or nested repositories.** Retain this data while its qualification is needed; clean only audited agent-owned disposable data after evidence retention, non-forced native PowerShell cleanup.
- Report actual comparison decisions and remaining counts, not tool/receipt counts. Update ledger/generated view, check, local commit and owning Bead at meaningful closures. Don't mark unknowns passed, silently weaken frozen acceptance, or aggregate away per-game regressions.
- Normal finish means every one of these74 has an honest final disposition with required evidence; no arbitrary passed-count/time milestone is a stopping point. If the owner stops or asks another handoff, preserve exact live identities/progress and cleanly close owned native processes. Genuine external prerequisites must stay explicit; never falsely claim completion.

## Remaining 74 frozen checks

This table is copied from the current ledger, not a new expanded inventory. Required modes and exact frozen definitions in the ledger remain authoritative. `passed/unverified` means LOCAL already qualifies and NET does not; reuse the passed component.

| ID | Workstream | LOCAL / NET | Existing bounded acceptance |
| --- | --- | --- | --- |
| R1 | netplay | unverified / unverified | Select two distinct pads; launch native X6 through Host/Join and verify independent accepted inputs on both peers, then repeat Windows/Linux. |
| R9 | assets | passed / unverified | First enable X in either seat; charge/release and dash after each owned menu, retaining allocation owner, native lifetime and composed art. |
| R10 | scene | unverified / unverified | Locate a native surface-crossing callback before testing a leading partner splash/ripple; another particle or underwater room does not satisfy the trigger. |
| R14 | camera | unverified / unverified | Enter a genuine alternate-route trigger with the partner first while the primary remains outside; verify room limits, collision, controls and native return. |
| R18 | lifecycle | unverified / unverified | Establish an authored vehicle/foot boundary first; then compare survivor, retry budget and roster after native continuation. |
| R23 | combat | unverified / unverified | Map an original homing producer and eligible-target predicate; make only the guest eligible and retain trajectory plus native contact. |
| R24 | combat | unverified / unverified | Identify an original restraining attack, let it hit the guest and observe native release without Select or lifecycle-result writes. |
| F4 | render | passed / unverified | Kill the actual scene owner once before release; count native effect creation/expiry and world cadence while the passenger recovers. |
| F11 | lifecycle | unverified / unverified | Find a native X6 mounted entrance/death sequence first; require finite beam retirement and surviving or retried rider control. |
| F16 | render | unverified / unverified | Find an authored compatible vehicle counterpart; overlap riders and inspect body/vehicle/exhaust priority in the final image. |
| F29 | solid | unverified / unverified | Ride an authored lift with both actors, wipe and retry natively; compare per-seat carry/side contact and genuine ceiling clearance. |
| F30 | netplay | unverified / unverified | During an actual service failure, retain startup log and exact sign-in error; local delay-peer success cannot qualify external service availability. |
| F35 | solid | unverified / unverified | Map native X6 gate geometry; place one living partner below/inside and verify no closure until their actual collision box clears. |
| F36 | solid | unverified / unverified | Place each actor and a native pickup on the same authored support; compare surface position, per-seat contact and pickup carry during motion. |
| F37 | enhancements | unverified / unverified | Qualify simultaneous elective X and Zero forms using X6's native art/abilities, unlocks, menu resources and death/retry/current-state restoration. |
| F41 | scene | unverified / unverified | Die during genuine pre-boss warning/admission, retry and require one native boss introduction rather than repeated WARNING or missing allocation. |
| F46 | solid | unverified / unverified | Find an authored X6 lift and use guest-only approach; observe its actual activation, carry motion and appropriate camera follow. |
| F49 | assets | unverified / unverified | Charge/release on an authored moving solid; retain actual shot travel, hit and retirement without moving the projectile directly. |
| F54 | scene | unverified / unverified | With each supported roster, let the counterpart deliver the actual D-1000 final hit; require original cleanup and campaign continuation. |
| F55 | enhancements | unverified / unverified | Acquire a native Blade/Shadow capsule with X in the counterpart seat; verify granted part, body art and actual ability after native reload. |
| F57 | solid | unverified / unverified | Identify a real closing gate, kill primary before guest passes and verify the corpse does not keep the native closure permanently open. |
| F60 | lifecycle | unverified / unverified | Identify a genuine X6 mounted entrance, then require the partner to execute its original arrival sequence rather than enrolling after it. |
| F62 | scene | unverified / unverified | Inventory Nightmare Zero, High Max and Dynamo story/route prerequisites; define the X6-native elective contract before implementing any replacement encounter sequence. |
| F71 | assets | unverified / unverified | Equip genuine X armor with X in the guest seat; compare body and effect colors with original character references across stage changes. |
| F72 | combat | unverified / unverified | Locate an original X6 hold/capture attack; capture one hero, change the boss's eligible target and verify damage/release stays on the captured actor. |
| F77 | scene | unverified / unverified | Find an authored destructible admission gate; break it with guest leading and require original controller/camera commitment before traversal. |
| F81 | assets | unverified / unverified | Locate a shared boss palette-flash initializer; admit it after primary death and compare intended native colors without screen-wide corruption. |
| F86 | lifecycle | unverified / unverified | Enter a genuine next fortress level after one actor previously fell; verify native fresh-stage roster policy rather than carrying a stale corpse. |
| F87 | assets | unverified / unverified | Reverse X/Zero seats, then initialize an original route-specific boss; compare resource identity and visible art against its native solo reference. |
| F88 | solid | unverified / unverified | Locate an authored shaft trigger with hazards/solids; traverse as guest survivor and verify no singleton carry lock or false immobilization. |
| F93 | lifecycle | unverified / unverified | Identify a native X6 vehicle entrance and measure authored travel/world ticks against a co-op-off reference; retain independent animation identity. |
| F100 | solid | unverified / unverified | Trigger original forced ejection with partner returning nearby; verify full collision boxes and native landing avoid walls/ceilings without relocating the result. |
| F103 | scene | passed / unverified | Kill actual scene owner during partner beam-in; require native passenger completion, released controls and survivor ownership without resetting the checkpoint. |
| F104 | solid | unverified / unverified | Locate an original X6 slippery surface and compare acceleration/friction for both heroes under identical native contact conditions. |
| F105 | camera | unverified / unverified | After private views exist, ride a genuine lift with guest progressing; inspect authored vertical current/target limits and follow through native lift motion. |
| F108 | camera | unverified / unverified | Locate an actual breakable forward exit, traverse with guest and compare destination scenery/camera state after original cleanup. |
| F112 | solid | unverified / unverified | Find the same native support's real lifetime driver; kill primary after spawn and require native expiry while guest remains active. |
| F115 | scene | unverified / unverified | Identify native X6 water-entry/ripple producer and make primary distant; require guest's genuine surface crossing to emit visible correctly owned effects. |
| F117 | combat | unverified / unverified | Map an original route boss reaction that differs by valid attack family; confirm X attacks cause native knockback/reaction when X6 rules allow. |
| F120 | assets | unverified / unverified | After primary death, continue through an original palette-animated background; compare advancing native controller and actual upload to the displayed view. |
| F126 | combat | unverified / unverified | Locate an original X6 grabbing attack; capture primary, make guest the next eligible target and require original release without guest death. |
| F130 | combat | unverified / unverified | Hit a real Investigator using a persistent native weapon; verify duplicate suppression per projectile/seat and fresh later contact without stale vetoes. |
| F135 | combat | unverified / unverified | Map an original X6 boss's valid attached/wall phase and weakness overlap; observe that exact native reaction before using general weakness evidence. |
| F140 | combat | unverified / unverified | Trace a native final-boss special targeting path separately from ordinary AI; make guest the sole eligible target and inspect its real trajectory/contact. |
| F145 | solid | unverified / unverified | Find a closing gate and cross with one living actor temporarily lacking a contact box; keep the gate safe until actual partner clearance. |
| F146 | solid | unverified / unverified | Kill primary before an authored lift activates; guest must trigger and ride its native controller with valid contact/camera behavior. |
| F148 | scene | unverified / unverified | Enter an eligible native boss scene mounted; preserve vehicle/rider ownership and visible partner after original scene release without destroying armor as a workaround. |
| F149 | enhancements | unverified / unverified | Use genuine Falcon/Blade/Shadow movement effects with X in each seat; compare native flame/trail art, palette, allocation and expiry. |
| F151 | scene | unverified / unverified | Inventory original Alia/Gate/Zero scene identities and eligibility; define per-scene paired staging without changing native story prerequisites or claiming generic dialogue coverage. |
| F153 | combat | passed / unverified | Use an original grounded combo finisher then a genuine fresh slash under per-seat cooldowns; retain native owner/timing and accepted boss damage. |
| F154 | scene | unverified / unverified | Enter a native Blade/Shadow capsule under each X seat; require original Dr Light text/resources and native part grant rather than unrelated route/story dialogue. |
| F155 | combat | unverified / unverified | Have both eligible heroes attack during a source-qualified weakness window; retain child ownership, accepted hits and stable native control flow through recovery. |
| F159 | solid | unverified / unverified | Inventory a distinct later native temporary-support subtype and make only guest eligible; require its own original admission rather than reusing the first subtype. |
| F161 | assets | unverified / unverified | Map a genuine later-area X6 spawn with guest progressing; compare native sprite/texture identity after section load and actual enemy interaction. |
| F162 | camera | unverified / unverified | Find an original global field effect with finite freeze; while views are separated retain each camera and proper original shared timing. |
| F167 | scene | unverified / unverified | During a genuine capsule sequence, kill the owning hero at an admissible point; require surviving partner release onto real safe terrain. |
| F169 | camera | unverified / unverified | Continue a native vertical lift route as guest after primary death; inspect authored camera landing/current/target bounds through native motion. |
| F171 | combat | unverified / unverified | Locate an original X6 freeze-field controller and observe its real end; prove guest targeting does not retain timer/work after the effect retires. |
| F172 | render | unverified / unverified | Find a native X6 targeting/assessment visual if present; derive whether one or both eligible heroes should be represented before testing art/ownership. |
| F179 | menu | passed / unverified | Support X/Zero in either seat; open each own menu, inspect native equipment/art, reject other-seat resume and exercise the selected native ability. |
| F182 | render | unverified / unverified | Locate an authored X6 beam/laser encounter and separate views; inspect correct world-space geometry/collision without projection into the distant partner's pane. |
| F183 | solid | unverified / unverified | Identify an original closing hatch, hold one living actor inside and move the other beyond; require clearance before native closure. |
| F185 | camera | unverified / unverified | On an authored lift, jump one hero while the other rides; retain each view's native vertical bounds and valid feet through actual lift motion. |
| F186 | solid | unverified / unverified | Find an original destructible moving-support mechanism, kill primary first and require guest's native attack/trigger to change world collision and permit traversal. |
| F189 | camera | unverified / unverified | Observe actual X6 native panorama wrap with both actors healthy and separated; compare phase/origins and composed motion without rolling back shared writes. |
| F190 | scene | unverified / unverified | Find an authored X6 bomb/script controller and its real threshold; guest admits it with primary behind and one original event ending must occur. |
| F192 | solid | unverified / unverified | Map an original X6 moving controller with a native stop phase; guest triggers it and both observe one world stop with correct cameras/carry. |
| F193 | solid | unverified / unverified | Find a separate native stationary support/start trigger; guest admits original motion with primary behind, retaining owner and actual carry. |
| F195 | scene | unverified / unverified | Map a different authored X6 platform hazard, then observe guest-triggered original spawn, actual collision and native retirement independently of F194. |
| F196 | camera | unverified / unverified | Let guest trigger a native intro geometry event while primary remains on another safe slope/floor; inspect each appropriate camera Y after completion. |
| F200 | scene | unverified / unverified | Trace a genuine X6 environmental event that emits an enemy group; guest-first progression must preserve original group timing and interaction, distinct from static placements. |
| F201 | solid | unverified / unverified | Find an actual X6 support release producer before asserting it; preserve signed per-seat carry commands and observe original airborne/landing state without teleporting free. |
| F202 | solid | unverified / unverified | Map an authored X6 Y/camera predicate and resulting real wall collision; guest descends while primary stays above and both retain native control. |
| F203 | assets | unverified / unverified | Kill primary before a source-qualified boss color/effect initializer; admit with guest and compare original source colors, working palettes and actual upload. |
