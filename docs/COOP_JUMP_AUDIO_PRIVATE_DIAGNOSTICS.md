# Jump audio: explicit private-bank diagnostic scope

The observer/runner now supports `--private-banks` for one offline ordinary
ground-jump overlap between Falcon X/P1 and Zero/P2. No title, build or audio
output ran during this implementation. Pure/source fixtures are not a new
R4/R12 result and do not supersede the retained v17 local failure. No netplay,
other sound families, music or audible-output scope is added.

Without that flag the scope is `hardware_legacy`: original24-row snapshots,
hardware voice20 comparisons and optional historical event fields retain
their meaning. It rejects private voice/nonzero-bank events and cannot gain
private qualification. Old frozen event reports without bank fields remain
readable; no implicit bank0 or Zero identity is inserted into them. The frozen
source contract and canonical SHA `ce11910561b56c85450c0c14d66333b0bddd50156235c76ff12bbeb4c902124a`
are unchanged, including its original SDK6212 source/DSP reference.

The new `private_banks_v1` scope requires the read-only diagnostics introduced
by SDK `bfbfb920bfa509f6a31ec2e6b28411a01797427f` (origin13c5299a9), documented
in the SDK's `docs/SPU_PRIVATE_DIAGNOSTICS.md`:

- Every event carries its **event-time** `sample_bank`; non-voice IRQ uses0.
- `spu_private_voices` supplies schema1 and exactly24 rows numbered24..47,
  including decoder bank, pending bank, mode, addresses and live envelope.
- `spu_sample_bank(bank,addr,len)` supplies explicit residency, total size and
  bounded bytes from that exact named bank; absent/clipped reads never fall
  back to hardware RAM.

These accessors do not catch up audio, bind/register assets, reset events or
change state. Guest execution can occur between RPCs. Their replies are
separate observations, not an atomic cross-command snapshot or an independent
audio/sample clock. The existing actual-image/manifest/source checks still
bind a fresh candidate; API/version presence alone grants no compatibility.

## Native source and actual immutable-bank bytes

`build_private_bank_contract(raw_disc, frozen_contract)` reproduces a separate
metadata descriptor from original Zero DAT85, SHA
`25f558d69e38e5f170b3325e27dc49a8232860f97d97dfeb6a0ce5306364f1c8`:

| Named bank | Original body | Bytes | SHA256 |
| --- | --- | ---: | --- |
|30|VAB1 subasset12, type020101h|123408|425516420dc6ff1d973edae265717a6ca237454631cdb4b7c829c96f6f7057a8|
|31|VAB3 subasset14, type020303h|52096|203c8e0e58ea4e55797445b7af76e7563528c21536ae8fd57e38566a89b38bdd|

Both bodies begin at offset0; there is no header or hardware VAB-base prefix.
The runner stores this companion metadata in `source-private-banks.json`.
Strict metadata validation includes JSON types, original member identity,
body type, extent and SHA. No original ADPCM bytes are committed or retained
in reports.

The observer fingerprints **both complete resident bodies** before and after
the trial, using44 body peeks of at most4096 bytes plus four size/residency
queries per pass. Every response must echo the exact requested bank/offset,
expected full size, exact count and canonical bounded hex. Missing/absent,
short/clipped, wrong-bank, changed-size and malformed responses stop the case.
The two complete body hashes must match their original source and each other.
This also verifies VAB1/bank30 residency; this trial does not qualify its
separate group1 animation sound path.

For each selected group3 KEYON, identity is derived again from its event bank,
sample offset and exact original sample bytes. Hardware bank0 uses the actual
native VAB3 base plus original offset. Bank31 uses original raw-body offsets.
The peek is bounded by the named bank's complete expected extent and4096-byte
limit. The report retains bank/offset/length and observed/expected hashes,
never sample bytes. Merely seeing private voice44 or bank31 cannot identify
Zero, and a current voice snapshot cannot rewrite an older event's bank.

The scope expects P1 hardware voice20/bank0 and P2 private slot20, event voice44,
bank31. The observer still considers an unexpected hardware20 key-on during
P2's accepted window so the old wrong-channel replacement cannot become
inconclusive silence. Private group1 voice46/bank30 events are retained but
are not promoted into group3 jump evidence.

## Independent predicates and stale-channel refusal

New comparisons keep these predicates separate for each seat:

- Original character/group/record/sample byte identity.
- Physical voice and event-time bank route.
- KEYON pitch/ADSR numbers against the complete eligible original tone set
  for that seat, independently of missing/wrong sample identity. The report
  also retains numerical agreement with the identified tone when known. The
  v17 false `p2_pitch_adsr` was character-gated; equal numbers must not hide or
  be mislabeled as the identity failure.
- First subsequent same-voice KEYON/KEYOFF/END_STOP/END_LOOP lifetime. A new
  KEYON is replacement even if it changes bank; an end/keyoff/loop on another
  bank without a recorded key-on is rejected as unproven attribution.
- Later DSP snapshot applicability, final envelope termination, register
  pitch/ADSR and noise-off. A later KEYON, changed current/pending bank or
  changed start address prevents attributing that snapshot to the selected
  note. Its original event lifetime remains separately reported.

`END_STOP` means envelope0/release; it need not clear `active`. Its post-stop
repeat address is not the selected sample identity. Reverb/mode and effective
volume fields are retained without inventing a stereo-gain, reverb or PCM
oracle. Full bank fingerprints, event identity and later snapshots do not
claim cross-RPC atomicity or a bank-generation protocol absent from the API.

## Runner and validation

Use the existing exact-source invocation in
[COOP_JUMP_AUDIO_QUALIFIER.md](COOP_JUMP_AUDIO_QUALIFIER.md), adding
`--private-banks`. The default legacy scope is explicit in reports. An older
runtime missing the new fields/commands refuses the new scope. No legacy
success or failure is converted into private-bank qualification.

The original held-Cross native ascent/short-jump predicate is unchanged.
Numeric virtual host devices, PID/listener ownership, muted output, finalized
native-input capture/image/manifest binding, source cards, private card hashes,
partial errors and neutral/owned Quit cleanup retain the existing guards.
Both new complete bank reads happen while original input is neutral. Their
latency can advance the world; subsequent native observations must remain
healthy and the event ring suffix must remain complete. Final event polling
also brackets the separately observed DSP snapshots.

`observations_complete` still means bounded automated evidence only. The
runner's R4/R12 dispositions remain unverified pending a reviewed actual run.
No pure fixture, source hash or new diagnostic getter grants an audio pass.

Set `TEMP`, `TMP` and `PYTHONPYCACHEPREFIX` to existing F:/G: scratch paths.
Validation commands (no native process or sockets):

```powershell
$env:MMX6_AUDIO_EXE='G:/<original>/SLUS_013.95'
$env:MMX6_AUDIO_DISC='G:/<original>/Mega Man X6 (USA) (v1.1).bin'
python -m unittest discover -s tools -p test_mmx6_coop_jump_audio_private.py -v
python -m unittest discover -s tools -p test_mmx6_coop_jump_audio.py -v
python -m unittest discover -s tools -p test_qualify_mmx6_coop_jump_audio.py -v
```

Fixtures cover exact hardware-X/private-Zero overlap, full source-bank hashes
and selected original sample bytes, wrong/absent/stale banks, short/malformed
peeks, replacement/terminal-bank mismatch, current/pending DSP reuse, explicit
versus legacy schemas, and a complete synthetic private observer control flow.
Owned-runner fixtures retain the real cleanup and private-card failure paths.
Original source bytes are read locally only when the explicit environment
paths are supplied; no source bytes are bundled with tests.
