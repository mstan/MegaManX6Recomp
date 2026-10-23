# Paired native intro enemy targeting and attack

The first bounded paired v11 run passed eleven checks: six existing intro/input
checks and five native record25 checks. It used two fresh private hidden/muted
profiles with default Seamless Loading, delay3, loopback UDP29901/29902 and
debug ports24901/24902. The negotiated title profile was
`mmx6-x-zero-delay-v11`; both peers used executable SHA-256
`43796887fda9e8b6bf547acdd1fa1149e1a944717e824e0dee5bf4a5b6010db7`.
The source build for staging was the frozen offline v11 candidate. Preparation
copied only executable/assets/catalog/bios dependencies, with no saves, shader
or overlay caches or source cards. All private data/cache/temp paths were on G:.

The existing owned-process runner now supports `--enemy-targeting-smoke`. It
requires `--require-state-crc`, native gameplay and the default loader. The
existing lifecycle option remains independent and can be combined with it.
The new case uses original published **peer1 host input** for P2 movement,
jump-right and Square through the transport. P1's native Start opens/resumes
the menu for a stable composed capture. It issues no guest RAM writes, fixture
commands, mailbox inputs, direct online SIO presses or state loads. The inherited
cleanup helper dearmed debug input after qualification before quitting; it did
not supply any route controls. Only the two Popen-owned processes were stopped.

## Native observations

The source/instance contract is documented in
[COOP_ENEMY_ADMISSION_BASELINE.md](COOP_ENEMY_ADMISSION_BASELINE.md) and
`COOP_PLACEMENT_ADMISSION_AUDIT.md`. Both peers initially had an inactive
record25, no live matching origin, P1x144, native 4:3/margin0 and camera X below
the source admission threshold. Shared-camera movement from P2 admitted record
`800FA2DC` into native pool slot `8008EF48` on both peers at camera(53,944),
publication1182/native timer1181. The actor had type1/subtype1, phase1/action1,
HP12 and strength4. Record flags alone were not used as spawn evidence.

Each peer subsequently observed the same origin-bound actor enter action +5=2
with only P2 near. The first observed publication counts were1253/1256. The
native signed integer X values were enemy416/P1=144/P2=309, distances272/107;
P2's raw position was309.5. P1 stayed at x144 in all121 retained paired case
observations. One native jump-right crossed the same terrain rise as offline.

After published peer1 Square, both peers observed a real HP drop on the same
live slot/type/origin while P2 entered native action48 at x384.5. The retained
short transition samples show HP4 and HP8, each tagged publication1432; these
are **separate advancing guest reads**, not an atomic same-frame HP comparison.
The preceding published diagnostic read does not freeze subsequent pool reads.
Both later observed the native slot freed and record allocation clear, with
P2 hit counter3 and both heroes alive at HP32. The HP transitions establish
native interaction; the counter is corroborating telemetry. Native contact was
not separately exercised. Per-frame identity during the short hit transition
is not established by these samples.

## Resolved checksums and composed output

The runtime's authoritative host digest capability was registered on both
peers. The tool compared37 actual core/mod CRC pairs at equal simulation ticks,
strictly below both resolved watermarks. Publication counts and diagnostic FNV
are separate observations and were not substituted for those CRCs.

| Window | Equal core/mod samples | Simulation ticks | Both resolved through |
| --- | ---: | --- | --- |
| Initial idle | 7 | 2944..3136 | at least3164 |
| P2 movement/release | 8 | 3200..3424 | 3434 |
| P1 jump/settle | 7 | 3520..3712 | at least3737 |
| Native target response/attack, after route | 7 | 4288..4480 | 4499 |
| Native post-capture resume | 8 | 4608..4832 | 4842 |

The compact receipt retains every core/mod value and both watermarks, not just
these ranges. Final network status was active/two players/rollback0, ticks4852
and resolved-through4851 on both peers, with no reported desync.

Both actual composed paused-menu PNGs were byte-identical, SHA-256
`34a3b672a3fd5fdf06710fa53c65fdd2560a3a622bb688039bf11737fdaa7b7c`.
Each completed at present sequence1/wrote1 after the native menu finished
opening. Inspection confirms clean native menu output. Final composed gameplay
images were also inspected: both show clean X/Zero sprites and HUDs at the
post-route positions. Their hashes differ (`0135e09c...` / `d2b4e095...`) and X's
idle pose differs; those independently timed captures do not establish a
pixel-identical gameplay frame. The required composed byte match is for the
stable native paused menu. Canonical software screenshots are retained
separately and are not used to qualify retained GL sprite art.

## Durable receipts and limits

Evidence root:
`G:/Temp/Codex/psxrecomp/x6-parity/netplay-native-r13-v11`.
The full report SHA-256 is
`a62da3b15fca9ec5708726c71cd170427fb3212d2ccff7972fa275da70361b45`.
The exact executed runner is retained as `runner-source.py`, SHA-256
`265a041fb1218f3307a68be605a5441756d451657adb838ad04b11346751b8a2`.
The committed compact receipt is
`docs/evidence/mmx6-r13/paired-v11-native-summary.json`, SHA-256
`53df53deaf45e01466f3eff30e0bed4b672b4f8174e1de22b868a557ae1b8d5d`.
It retains source/tool hashes, native checkpoints, all CRC sample windows,
network status, complete capture hashes and owned-process cleanup receipts.

Four public-option tests pass, including existing lifecycle defaults and
combined lifecycle/enemy selection. Eight existing offline evidence-parser
tests also pass. The lifecycle departure/rejoin option was not selected for
this run; it has no new runtime claim here. Both owned processes required
termination after bounded quit handling and were verified absent afterwards.
There was one pair attempt and no setup correction or replay.

The scope is this native intro type1 record, one attack route and same-machine
loopback peers. Cross-host/physical-controller/audible behavior, other native AI,
full campaign coverage and the complete R13 row remain separate gates. Static
source evidence shows the world update loop, but an independent runtime count
of exactly one full native world update per frame remains unverified. No issue
or full-row pass is implied by this bounded receipt.
