# R2 native enemy contact before and after Zero's menu

This is a source audit and candidate route, with **no R2 runtime result**.
It changes no ledger status and has launched no game. The selected compiled
game is `fbba0e3ae5e38174022fa7eb79ac81c3741ef391`, executable SHA-256
`37cdc4876f7e852b97ef5f14210809b0af7d4a8adaa1759c9e096017170e1fa9`.
The coordinator's manifest-bound R13 receipt establishes its original-input
approach, admission and terrain jump; it does not establish incoming contact.
Exact original byte spans and source identities are in
[COOP_R2_NATIVE_CONTACT_AUDIT.json](COOP_R2_NATIVE_CONTACT_AUDIT.json).

The audit used bounded Capstone disassembly against the pinned original EXE
and archive. A read-only Ghidra open met an existing project lock; that lock
was left untouched. No GUI, alternate server, source build or runtime was used.

## Native damage path and observation fields

Record25 `800FA2DC` is the same original intro category0/type1/subtype1 enemy
at (416,1080). Match exactly one live origin-bound slot in the48-slot native
pool; never assume slot0 or accept a stale freed pointer. Its init `800EAFFC`
sets HP12, strength `+60=4`, and contact class `+62=0` remains allocator-cleared.
Its contact rectangle pointer `+50=800FAAE0` resolves to `f4ec1828`: signed
offsets (-12,-20), unsigned width24/height40. Its damageable rectangle `+54`
is separate, at `800FAAE4`, with the same authored bytes.

Alive body `800EAC8C` calls weapon hit `80031474` at `800EAD20`. A fatal weapon
hit changes the enemy's phase to2. Only the continuing live path calls incoming
contact `80030ECC` at `800EADC0`, with return PC `800EADC8`. An enemy HP drop,
native saber action48 or P2 hit counter is outgoing attack evidence, not R2.

| Player field | Native meaning and source |
| --- | --- |
| `+5C` | Low7 bits are remaining HP. Contact sets high bit80 on a surviving hit at `80031200..208`; this is pending reaction, not additional health. Hurt initialization clears it at `80039654..664`. |
| `+61` | Invulnerability timer. Overlap helper `8002D654` rejects any nonzero value. Ordinary reaction1 loads **75** from `80073CD9` at `800397A8..C0`; recovery decrements it and clears `+A4` when it reaches0 at `80039494..4F8`. |
| `+63` | Native reaction class. For this ordinary strength4/contact-class0 case, the unarmored path writes1 at `80031168..180`; armor/parts can select4 instead. Record actual difficulty/equipment rather than assume a damage delta. |
| `+A4` | Additional damage/reaction lock. Ordinary contact rejects nonzero at `80031070..7C`; hurt initialization sets1 at `800396A8`. A zero iframe timer alone does not establish readiness. |
| `+A5`, `+15`, `+20/+24/+28/+2C` | Contact knockback direction, applied facing, velocity/acceleration. Contact chooses direction at `8003127C..2BC`; hurt initialization applies the reaction's native motion table. |
| `+4/+5/+6` | Body state/action/subaction. Native hurt initialization sets action `11h` and subaction0 at `800397D8..E0`. An actual HP drop plus this reaction and a positive timer is stronger evidence than a hook entry. |
| `+54` | Current native damageable-box pointer. Zero's binder selects an entry in `801EEA00` using animation maps `801EE700/EE800/EE900`; zero means no native box. |
| `+CC/+CD` | Player hit-pause fields. The co-op wrapper skips a frozen seat when `+CC!=0`; the native player update consumes `+CD` into a five-tick pause. Keep these distinct from damage invulnerability. |
| `+70/+89`, `+D5`, `+7A/+144` | Terrain/hazard context, alternate-body projection and additional native restrictions. Reject the alternate `+D5` path and terrain-hazard/confounded trials rather than infer all damage came from the selected body. |

The native overlap helper requires actor `+50`, player `+54` and player
`+61==0`; it uses signed rectangle offsets, orientation, strict width/height
comparisons and camera-relative actor flags. Horizontal proximity alone is not
contact. Require the actual box pointers/descriptors and the native outcome.

The ordinary damage calculator `80030DC0..ECC` uses original difficulty
`PLAY+68` and the player's armor/parts. Strength4 normally gives3/4/5 at
difficulty0/1/2, before native half-damage modifiers and minimum1. Preserve that
configuration across both contacts and compare the actual native delta.
No HP or reaction values may be seeded to make the comparison pass.

Zero's `+54` pointer needs special care: it points into the character overlay.
Between projections resident RAM contains X's overlay. Resolve Zero's pointed
bytes against pinned original `ROCK_X6.BIN` member1, SHA-256
`75a142a529ddc70f0d60ee6be32ebcdb0cf5cc90ec88e965c3b15cf0c6d21b00`,
base `801EA000`, size22964. Reading those bytes directly from resident X RAM
can silently describe the wrong character. Reject unresolved pointers.

## Co-op projection and accepted-contact evidence

At the selected game commit, `player_contact` first tries native P1 and retries
P2 only on a miss, with living/nonzero-HP/not-hit-paused Zero. `enter_zero`
projects the full158-byte player body, attack pool, trails/effects, native Zero
overlay and character identity. `leave_zero` captures the modified P2 body and
restores X, including native shared context. This preserves HP, reaction,
invulnerability and native box pointers by source; their runtime behavior
before/after the menu remains the R2 obligation.

Diagnostic `+44` increments only when P2's retried native contact returns a
nonzero result. It is useful acceptance evidence, but does not identify the
actor. A bounded trial must combine a delta of exactly1 with an actual P2 HP
loss/reaction, unchanged X resources and a complete selected `80030ECC` trace
whose actor arguments all identify the live record25 body. Trace entries alone
do not show a successful hit; current dispatch traces retain arguments/RA/frame,
not return `v0`. Keep raw sequences and reject eviction/truncation or foreign
contact sources. Body/counter fields can share one coherent diagnostic RPC;
subsequent pool/box reads do not become an atomic world snapshot.

Native action2 can allocate an enemy projectile through `8002C458`, pool
`[80093C98,80095098)`,32 slots of `A0h`. Its range test still uses resident P1,
even after the narrow near-target fix. Do not assume that makes a trial safe:
retain the projectile pool and reject foreign-contact or terrain-hazard windows.
The trial must not use Square to obtain its incoming-contact result.

## Source-derived candidate contact/menu/contact route

1. Enter the same healthy native intro normally at4:3/margin0. Keep Xx144.
   Admit and initialize record25 using accepted P2 Right and R13's single
   terrain jump. Require origin-bound HP12/phase1, native strength4/class0,
   and actual P2 box eligibility. Preserve authored flags and all other actors.
2. Continue original P2 Right toward body contact without Square. Arm the
   selected contact trace before this controlled window. Stop on the first
   accepted P2 contact: counter+1, native HP loss and hurt action/reaction/
   iframe evidence on the same live authored enemy. Reject ambiguous sources.
3. Retreat with original Left to a safe position around x280; retain the
   actual camera and verify the same enemy remains alive HP12/phase1. The
   native extended retention margin makes this a plausible bounded retreat,
   not a proven runtime position. If it unloads or another contact occurs,
   retain failed setup and stop rather than reallocate or reset it.
4. Wait at least75 advancing native timer ticks and actual recovery:
   HP80 clear, `+61=0`, `+A4=0`, `+CC=0`, live idle state and stable native
   boxes. Longer native recovery is allowed; publication counts alone cannot
   stand in for the native timer or those fields.
5. Open/resume Zero's own native menu using accepted inputs. The shared menu
   helper now supports explicit `expected_hp=(32,remaining_zero_hp)`, default
   unchanged. It still checks both heroes' exact HP/ammo/weapon before/during/
   after the menu, wrong-seat rejection, actual cursor response and frozen
   world time. Use the source-backed pristine Down/Up route. Its post-menu
   Right/Square controls must run safely away from record25; require that
   target still alive HP12 afterwards. No healing or resource grant is used.
6. Let Zero's native attack finish and hit-pause clear before a second trial.
   Reapproach with Right and the same bounded terrain jump if needed. Require
   the second accepted body contact, with the same difficulty/equipment,
   native damage/reaction/recovery contract and unchanged X resources.
7. Retain both trials, the owned menu, composed captures and exact build/tool
   identities. For netplay use only published host input and actual resolved
   core/mod CRC evidence. Review local and paired results independently;
   source audit or a menu pass cannot close R2.

`tools/mmx6_coop_contact.py` now supplies the collector and reusable
`contact_pause_contact(ctx, expected_exe_sha256=...)` candidate. It has no
launcher or automatic ledger result. The selected route remains unexecuted
until the owning native run verifies physical contact, safe retreat and
retention of the same enemy. No universal damage-class, AI, campaign, audio,
cross-host or exactly-once-world claim follows from this audit.

## Candidate helper integration

Supply the existing personal-menu runner context (`mode`, `input_path`,
`clients`, `both`, `debug`, `report`, private `output`, `hold`,
`native_advance`, `transport_window`, plus `network` online). Additional keys:

| Key | Required evidence/ownership contract |
| --- | --- |
| `candidate_exe_sha256` | The exact selected `37cdc487...` executable identity, checked against the explicit function argument. A staging source observation is not compilation proof. |
| `zero_overlay` | Immutable original member1 bytes. `load_zero_overlay(raw_disc_bin_path)` reads only the bounded inventory extents, verifies original EXE/archive/member identities and returns those22964 bytes without exporting a binary copy. |
| `rpc(peer,command,**fields)` | Owning runner's listener-checked RPC callback for read-only GPU queries and host trace filter/clear/dump commands. No guest mutation or additional guest call is used. The one-process adapter can ignore the peer index after validating0. |
| `matched(label)` | Required online and backed by real equal-simulation-tick resolved core/mod CRC samples, retained by the owning paired runner. Diagnostic counters are not substituted. |

The helper keeps Xx144/resources unchanged, uses original P2 holds only, and
requires native4:3/margin0. Each trial retains its pre-state, raw complete
contact trace, all sampled body/counter/config/box observations and recovered
native hit. An incomplete trace, foreign actor/caller, multiple acceptance
increments, outgoing enemy damage, changed native configuration, terrain
hazard, lost actor or missed native hurt window fails the case. The same
sampled native slot/origin must stay alive HP12 throughout; no latch, HP,
iframes, actor position or result flag is written.

After each accepted hit it retreats before requesting a composed capture,
then waits at least75 actual native timer ticks and observed eligibility.
The full Zero menu helper runs at the safe retreat with Down/Up and exact
reduced living HP. Its native post-menu Square expires away from the enemy
before reapproach. These geometric choices are source-derived candidates,
not runtime-confirmed safe positions. Their failures must be retained as
setup/route failures rather than converted into a damage-mechanic verdict.

Successful automated return remains
`automated_contact_checks_passed_artwork_review_pending`, with ledger status
unverified. The owning baseline adapter must preserve partial cases and wrap
the menu helper's `RuntimeError` as its handled `DebugError`, as the standalone
menu adapter already does. The helper's tests exercise evidence rejection,
field decoding, original-difficulty arithmetic and trace completeness only;
they do not qualify accepted controls, the route or native contact.
