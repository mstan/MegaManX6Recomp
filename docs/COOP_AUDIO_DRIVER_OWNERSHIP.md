# X6 native driver ownership follow-up

This extends [the bank audit](COOP_AUDIO_NATIVE_AUDIT.md). It remains audit-only:
R4/R12, local co-op and netplay audio outcomes are unverified. No adapter is
enabled and no game or card was opened. The original SLUS-01395 USA v1.1 EXE
SHA-256 is `dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.

[The reproducible metadata](COOP_AUDIO_DRIVER_OWNERSHIP.json) pins 18 inspected
routine extents, direct calls, unresolved indirect call sites, eight native
state regions and ten original character tone tables. These bounds were traced
from original MIPS instructions with Capstone 5.0.7. The reproducer needs only
Python's standard library and existing disc reader; it commits no instructions,
ADPCM, VAB headers or disc assets. Hashes establish source identity; they do not
prove gameplay or audible output. Ghidra registry `psx/MMX6` returned a project
`LockException`; the lock and database were left alone.

## Ordinary sample KEYON, STOP and volume

The explicit KEYON routine is `8005A9D4..8005AD3F`. Its `800E459C` word gate
protects shared selection/calculation state. `8005FC94` requires VAB status
`800E5690[id] == 1`, then changes selected program/header/tone pointers at
`800E5654`, `800E565C`, `800E5660` and temporary selectors at `800E5671`,
`800E5676`, `800E5677`. KEYON writes additional selected tone/volume/pan fields
through `800E5689`. Those shared fields must be scoped too; saving only a
voice's registers is incomplete.

For voice `v`, define `M=800E4E40+v*38h` and `R=800E53A0+v*10h`.
The X6 metadata stride is **38h**, including its final halfword at `M+36h`.

| Native path | Exact observed mutations and evidence |
| --- | --- |
| KEYON outer setup | `8005AC18..8005ACC8` writes `M+00,02,0a,0e,10,12,14,16,18,1d,36` with original VAB/program/tone/sample and voice state. |
| `8005BCA4..8005BE6B` | Writes `M+06=7fff`; clears bit `v` from **all 16 words** at `800E5528..800E5567`; writes sample address at `R+06`, ADSR at `R+08/0a`; ORs dirty byte `800E5380[v]` with `08h` and `30h`. Sample-address lookup uses the selected original program table. |
| `8005E794..8005EC5B` | Computes stereo gains/pitch; writes `R+00/02/04`, dirty `|=07h`, `M+04=pitch`; updates KEYON, KEYOFF, noise and reverb masks. This is queued state: ordinary sample KEYON does not directly submit SPU KEYON here. |
| Explicit volume `8005BC14..8005BC97` | Requires `v<24`, writes `(int16)left*129` and `(int16)right*129` to `R+00/02`, dirty `|=03h`. No metadata or mask writes occur in this routine. |
| Explicit stop `8005AD40..8005ADB3` | Sets the shared gate, selects voice at `800E5688`, calls `8005E6D4`, releases gate. |
| Stop queue `8005E6D4..8005E793` | Writes `M+1d=0`, `M+04=0`, `M+00=0`; ORs the voice bit into KEYOFF and removes the resulting KEYOFF bits from pending KEYON. It does not itself zero volume. |

Native character stop `8001750C..800175EF` supplies the missing pairing:
group `ffh` loops every voice `0..23`; otherwise it reads the selected group's
sound record, obtains its first voice and additional-voice count, and visits
exactly that contiguous range. Each voice calls volume-zero at `8001753C` /
`800175B4`, then stop at `80017544` / `800175BC`. A private stop handler must
scope the original record pointer and redirect both operations. Blanket private
interception would also alter shared music/other hardware voices.

The group-3 record-17 alias to effects VAB1 remains mandatory. The individual
record's original handle must select the corresponding character effects or
voice bank. Replacing every group-3 handle with a voice-bank ID is incorrect.

## Next flush and hardware queue boundary

The next native flush is `8005BE94..8005C357`. Its callers include the guarded
driver/tick entry at `80058ED4` (`JAL` at `80058F18`) and driver initialization
(`JAL` at `8005D418`). The tick entry checks/sets `800E459C` before flushing;
this is source evidence for the gate, not proof that every scheduler path has
been excluded during a projected call.

| Region | Exact extent | Flush consumption |
| --- | --- | --- |
| Per-voice metadata | `800E4E40..800E537F`, 24 * `38h` | Polls hardware envelope via `8005D0D4`; traverses metadata in `38h` steps. |
| Dirty bytes | `800E5380..800E5397`, 24 bytes | `8005C128..8005C238` builds attributes, submits `8005C8D4`, then clears each byte. |
| Register mirrors | `800E53A0..800E551F`, 24 * `10h` | Dirty bits select volume, pitch, sample start and ADSR fields. Init independently clears `c0h` halfwords at `8005D13C..8005D164`. |
| End-history masks | `800E5528..800E5567`, 16 words | Index word `800E5524` advances modulo 16, one entry clears, voice-end bits accumulate. `8005BF94..8005BFA8` intersects 15 entries; KEYON setup clears its bit from all 16. This is history, not an arbitrary scratch buffer. |
| KEYON | `800E4E30..800E4E33` | `8005C274 -> 8005C714(1,mask)`. |
| KEYOFF | `800E5568..800E556B` | `8005C254 -> 8005C714(0,mask)` before KEYON. |
| Reverb | `800E4E34..800E4E37` | `8005C2C4 -> 8005C6B4`; preserves hardware bits outside the managed voice mask. |
| Noise | `800E4E38..800E4E3B` | `8005C2F4 -> 8005C364`; preserves hardware bits outside the managed mask. |

Two indirect callbacks execute during flush when per-voice fields `M+1e` or
`M+2a` are nonzero: `8005C0A8` uses pointer `800E5520`; `8005C0D4` uses pointer
`800E5398`. Their active targets and complete ramp mutations remain unresolved.
This prevents declaring the entire stop/volume/flush ownership contract complete.

`8005C714` also has two submission modes, controlled by bit 0 of `8007AE00`.
Direct mode writes SPU KEYON at register offsets `188h/18ah`, KEYOFF at
`18ch/18eh`, and updates `8007ADA0`. Buffered mode writes `800E44F0..800E44F7`
and queue globals `8007ADCC` / `8007ADC8`. Mask helper `8005C394` similarly
selects hardware versus the `800E4368` mirror. Preserving a high-level mask
after a flush already consumed it cannot undo a hardware voice replacement.
The isolated calculation must prove that no flush/escape occurs before restore.

There is also a distinct tone sample-number `ffh` path: KEYON calls
`8005E0D4`, which calls `8005E644` and writes shared SPU control register
`+1aah` (noise clock) at `8005E688`. It can update other managed voices' state
bytes too. The ten frozen player VABs have **no allocated tone slot with sample
number 255**; that result is reproduced from all slots, including unused ones.
It bounds this branch for those exact banks. It does not authorize intercepting
shared music/noise or accepting arbitrary later banks as equivalent.

## VAB header residency and asynchronous completion

The logical-base opening contract is now source-backed. Wrapper `800601A4`
passes callback `8006020C` into parser `80060214`; that callback simply returns
its second argument, the caller's explicit logical sample base. The parser
rounds body size to 64 bytes, checks base+size <= `80000h`, installs per-ID
header/program/tone tables, writes relative sample addresses into the private
header's program table, and publishes VAB **status 2**, not ready status 1.

| State | Native owner |
| --- | --- |
| Transfer gate `8007AD68` | `8005D4A4(1)` writes 0 (busy); `(0)` writes 1 (released). `8005D4CC` tests busy. Header-open acquires it before changing tables. |
| Tables | `800E55C8[id]` header pointer; `800E5588[id]` program pointer; `800E5610[id]` tone pointer; `800E56F0[id]` sample base; `800E56A8[id]` aligned body bytes; status bytes `800E5690[id]`; allocation count halfword `800E56E8`. |
| Body upload `80060604` | Requires status 2; owns active-bank halfword `8007B794` and remaining-byte word `800E5668`, submits a chunk through `800607F4`. |
| Final submission | At `80060740..80060764`, clears active bank/remaining bytes and publishes status **1** after the final chunk is submitted. This alone does not prove DMA completion or gate release. |
| Completion wait/poll `80060884 -> 800608B4` | Checks transfer/event state; calls BIOS event test `80069E44` using handle `8007AD9C`; blocking mode loops until completion, then writes gate=1 at `80060940`. The game calls it at `80015E00`, `80015E8C`, `800172C0`. |

A private immutable body can bypass DMA only after proving the acquired gate
belongs to that private header open and no prior transfer is outstanding.
Publishing status 1 and releasing that gate would emulate two distinct native
events. Calling completion wait for a DMA never submitted could hang. Releasing
another bank's pending gate could expose incomplete shared samples. An adapter
must preserve these ownership distinctions and rebind immutable banks by SPU
epoch; the current audit does not implement either shortcut.

## Implementation boundary and reproduction

Frozen X4 `50593bca` audio blob `f490a1725aac5775a3e6711305370c279362dceb`
supplies the architecture: retained original banks, independent voices, scoped
priorities, an uncharged native calculation, status/stop/volume routing and
epoch rebinding. Its `34h` records and `48h` queue backup are not X6 extents.
X6's ordinary setup touches the 16-word history plus separate KEYOFF masks and
shared selectors. Any transaction must derive its own exact capture/restore
set from these paths, preserve pending P1 hardware work, and retain cross-bank
record routing. New host-owned audio state must join the canonical codec/digest.

No narrow runtime fix is enabled: unresolved flush callbacks, scheduler
admission and native lifetime/transition observations make a passing adapter
claim premature. The remaining work is specific: resolve the two callback
targets and ramp state; prove the uncharged transaction cannot flush midway;
implement character-scoped routing and transfer/epoch ownership; then compare
muted native captures, shared music, both overlap orders and current-build
restore on local and accepted-input netplay sessions. No ledger row closes here.

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp/audio'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX="$env:TEMP/pycache"
$env:MMX6_AUDIO_EXE='G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95'
$env:MMX6_AUDIO_DISC='G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin'
python tools/audit_mmx6_audio_driver.py --exe $env:MMX6_AUDIO_EXE --disc $env:MMX6_AUDIO_DISC --out docs/COOP_AUDIO_DRIVER_OWNERSHIP.json --check
python -m unittest discover -s tools -p test_mmx6_audio_driver_audit.py -v
```

Five tests pass with original-source reproduction enabled. They check bounded
routine extraction, return delay-slot inclusion, direct/indirect call identity,
unknown-source rejection and exact source reproduction. They establish audit
integrity, not simulated execution of native audio or audible correctness.
