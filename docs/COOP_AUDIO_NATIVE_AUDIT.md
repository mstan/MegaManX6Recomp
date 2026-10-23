# X6 character audio ownership: native evidence and implementation boundary

**R4 and R12 remain unverified for local co-op and netplay. No audio runtime fix
is included in this audit.** The [metadata report](COOP_AUDIO_NATIVE_AUDIT.json)
and [extractor](../tools/audit_mmx6_coop_audio.py) establish original banks,
explicit voice reuse and native call boundaries. No game was launched and no
speaker output or reference recording was produced.

The X6 candidate is `1d6f67c`. Original SLUS-01395 USA v1.1 EXE SHA-256:
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
The disc's EXE is compared byte-for-byte, and each selected player DAT member
has an exact pinned hash. Only metadata is committed; game samples remain in
the owner's original disc. No save/card data is read or changed.

## What the current projection omits

`load_assets()` loads Zero's code, graphics, sprite assembly, palettes and menu
resources. It omits the original sound header/sample pairs. `enter_zero()`
changes the player body, executable overlay, seven graphical scratch pointers
and campaign character/armor fields; `leave_zero_context()` restores them.
Neither function projects the native sound-record pointers or VAB residency.
Changing character identity alone therefore cannot select Zero's original
samples from an X-resident bank.

Both characters' original voice-group records also request the same explicit
hardware slots. Group-3 record 0 selects **voice 20** in every audited player
form. Zero's record12 also selects20, while the X-form record12 is empty; sound
IDs cannot be assumed identical between characters. These selections establish a native collision
mechanism: a second KEYON on that slot can replace the first voice. Actual
overlap, tone identity and natural end timing still need runtime evidence.

## Original bank inventory

All rows are in `ROCK_X6.DAT`. Header/body subassets **11/12** are sound group 1
(effects), and **13/14** are group 3 (character voices). Headers have type `6`;
bodies have types `00020101` and **`00020303`** respectively. The low 24 bits of
the preheader locate `pBAV`; the upper byte identifies the sound group.

| Member | Character/form | Effects header/body bytes | Voice header/body bytes | Effect/voice record counts |
| --- | --- | ---: | ---: | ---: |
| 85 | Zero | 4,264 / 123,408 | 3,696 / 52,096 | 32 / 18 |
| 86 | Ultimate X | 5,312 / 172,768 | 3,696 / 52,608 | 38 / 18 |
| 87 | Falcon X | 5,312 / 182,064 | 3,696 / 52,608 | 38 / 18 |
| 88 | Shadow X | 4,212 / 91,872 | 3,696 / 52,608 | 19 / 18 |
| 89 | Blade X | 5,824 / 171,712 | 3,696 / 52,608 | 38 / 18 |

Record 17 of **every voice group references VAB handle 1**, the effects bank,
while most other voice records reference handle 3. A private adapter must map
each original handle to the matching character bank. Rewriting all records in
group 3 to its private voice bank would silently select the wrong sample for
this cross-bank record. The report preserves empty records, routing bits,
program/tone selection, priority and explicit voice ranges separately.

## Native call and mutable-state evidence

These addresses are from original EXE instructions, not guessed from X4/X5:

| Native boundary | Evidence / responsibility |
| --- | --- |
| `80015AA0..80015B10` | Installs record/end pointers and calls header-open wrapper `800601A4` at `80015AFC`; records start at preheader+8. |
| `80016C48` | Checks group status at `80090D50`, indexes end/record arrays `80097738` / `80097778`, bounds the requested sound ID and routes its record. |
| `80016CD4` | Publishes current sound-record pointer at `800E155C`. |
| `80016D0C` / `80016D1C` | Calls alternate route `80017008` or direct routine `80016D34`, preserving record routing bits. |
| `80016E7C` | Calls `8005A794` to derive original VAB/program/tone parameters. VAB readiness is read at `800E5690`; selected metadata tables include `800E5654` / `800E5660`. |
| `80016EF4` | Calls `80055B14` with the explicit voice mask; its status path reads the SPU register pointer held at `8007AD34` (initially `1F801C00`). |
| `80016F20`, `80016F78` | Both call key-on entry `8005A9D4`, for an idle voice or allowed priority replacement. Native priority bytes are at `800E25E0`. |
| `8005A9D4` | Receives explicit voice/VAB/program/tone plus four stack arguments. Reentrancy gate `800E459C` and temporary selected tone fields are shared globals. |
| `8005ABF8..8005AC00` | Computes `(voice*8-voice)*8`: native per-voice record stride **`0x38`**, base `800E4E40`. |
| `8005ACC4` | Calls `8005BCA4`, which mutates additional state. `8005BCEC..8005BD10` walks 16 words beginning at `800E5528`; full ownership/extents remain unresolved. |
| `8005ACEC`, `8005ACF8` | Further calls to `8005DF40` and `8005E794` need complete native mutation/flush qualification before private KEYON publication. |

The extractor guards these call targets against the supported original EXE and
records addresses separately from sample content. The record bitfield decode
is supported by `80016E24..80016E60`: VAB handle/routing, program, initial tone,
priority, initial voice and additional-voice count.

## What transfers from frozen X4, and what does not

The proven reference is X4 commit
`50593bca772b600de6911cbfecd40b0f08721147`,
`src/mods/mmx4_coop_audio.c`, Git blob
`f490a1725aac5775a3e6711305370c279362dceb`, plus its
`docs/COOP_AUDIO_EVIDENCE.md`. Active X5 work is not treated as proven evidence.

X4 retains original VAB parsing and tone calculations, binds immutable sample
banks, and runs P2 audio on independent private voice slots. Before returning
from native calculations it restores P1's pending register mirror, per-voice
metadata, dirty flags and KEYON/KEYOFF/reverb/noise state. Separate priority,
status, stop and volume handling prevents one player's sound from stealing the
other's lifetime. Immutable banks are rebound after SPU initialization epochs.

Those design obligations apply to X6. X4's addresses, `0x34` voice-record size
and body-type assumptions do not: X6 demonstrably uses `0x38` records and
`00020303` voice bodies. X6 also requires explicit cross-bank record mapping.
The modern framework bridge at `sdk-bridge/runtime/include/mod_plugins.h`
provides sample-bank, bank-binding, private-voice and epoch APIs, so SDK
availability is no longer the implementation blocker. The unresolved X6
driver mutation/flush contract is the remaining safety boundary.

Read-only Ghidra registry `psx/MMX6` was opened. The batched decompiler request
did not return during the bounded audit; no decompiler interpretation is used
as evidence here. Native EXE instructions remain the authority. No Ghidra
database or annotation was changed.

## Next implementation and native qualification

1. Trace `8005A9D4` through every downstream register/record update and the next
   native flush. Establish exact mirror, dirty, queue, KEYON/KEYOFF and
   reverb/noise ownership; do not copy X4's extents. Verify native header-open at
   a logical sample base and completion/transfer-gate release independently.
2. Add an isolated audio helper with per-character/group retained headers and
   immutable ADPCM. Preserve original record routing and map VAB1/VAB3
   references individually. Scope record pointers and priorities only around
   actual projected-owner sound calls. Keep P1's pending hardware voice state.
3. Route actual private key-on/status/stop/volume paths, including global stop,
   menu/stage transitions and epoch rebind. Suppress audio from private visual
   replay. Snapshot/digest participation must include host-owned mutable state;
   no old-snapshot migration is required.
4. Capture muted native X/Zero action, hurt and death from each seat, then
   overlap both orders. Compare original sample identity, pitch, gain, ADSR and
   natural end/stop timing. Include voice-group record17, charge loops, pause,
   character/menu changes, stage loads, retry, rematch and current-build restore.
   Repeat on two peers with accepted-input and checksum evidence. These checks
   close R4/R12 only after actual audio evidence exists.

Reproduce metadata without a game process:

```powershell
$env:TEMP = 'G:\Temp\Codex\psxrecomp\x6-parity\scratch\voice'
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = $env:TEMP
$env:MMX6_AUDIO_EXE = 'G:\Temp\Codex\psxrecomp\x6-parity\disc\SLUS_013.95'
$env:MMX6_AUDIO_DISC = 'G:\Temp\Codex\psxrecomp\x6-parity\disc\Mega Man X6 (USA) (v1.1).bin'
python tools/audit_mmx6_coop_audio.py --exe $env:MMX6_AUDIO_EXE --disc $env:MMX6_AUDIO_DISC --out docs/COOP_AUDIO_NATIVE_AUDIT.json --check
python -m unittest discover -s tools -p test_mmx6_coop_audio_audit.py -v
```

Parser tests cover cross-bank preservation, explicit voice/tone metadata,
truncated headers, sample-size/alignment mismatches and escaping DAT extents.
Original-source reproduction is optional and explicitly skipped when its two
environment variables are absent. These are extraction checks, not gameplay
or audible-output qualification.
