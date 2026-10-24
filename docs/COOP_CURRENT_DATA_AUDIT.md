# Native Current Data prerequisites

The original game exports eligible Current Data during mission-report
processing. A fresh intro profile with headerFF cannot exercise that route.
This is a source finding for R15/F208; no runtime, earned-progress, boss,
native-card or Continue preservation check passes from this audit.

The [reproducible source record](COOP_CURRENT_DATA_AUDIT.json) binds the complete
original USA1.1 EXE and ROCK_X6.BIN, nine exact code/table spans and BIN2/18/20.
It scans aligned direct J/JAL targets in the EXE and all59 archive members.
There are exactly two direct callers of the native export8001BD40: title/card
import at BIN18:800ED15C and mission report at BIN20:800EACB0. This does not
exclude indirect callers.

The ordinary intro route is:

1. The original finale reaches BIN2:800F65A4. It waits for dialogue-active
   byte8008EAFC to clear, then writes positive native exit40h to PLAY+0F and
   removes its actor. Boss/finale activation and accepted dialogue remain
   runtime prerequisites.
2. The stage0 positive exit consumer8001E394 sets PLAY+66=1 and native
   major0Bh. Loader8001E81C enters major0Ch, stage15/section0/checkpoint0.
3. The report dispatcher800EF638 selects table800F3970 by its context+2.
   Entry0 is800EAC28, which finalizes report values and calls8001BD40 before
   later report pages or the native card-save choice.

The exporter ignores incoming argument registers and copies fixed native
PLAY800CCED0 fields into CURRENT80070CC4. It writes eligible header1 before
finishing the payload; a runtime check must wait for the native return and
stable complete data. Exported fields include earned weapons, shared parts,
maximum HP/energy, found Reploid states, soul totals and nightmare matrices.
The existing native reentry helper checks the corresponding imported slices.
Original import8001BA1C takes a0 as the payload pointer; it deliberately does
not import campaign character/armor and reinitializes native lives from its
parts policy. Actual unit selection must be checked separately.

Calling the exporter or authoring Current Data would bypass eligibility and
earned-data provenance. Such a fixture must be disclosed and cannot pass the
boss, exit, acquisition or native-card checks. The offline earned-weapon
mailbox9 only grants prerequisites; it does not export Current Data.

Reproduce with explicit Python312 and the process-local task environment:

```powershell
python tools/audit_mmx6_current_data.py --original-exe <original-EXE> --disc <raw-BIN> --check docs/COOP_CURRENT_DATA_AUDIT.json
python -m unittest discover -s tools -p test_mmx6_current_data_audit.py -v
```

The original-source tests use MMX6_CONTENT_EXE and MMX6_CONTENT_DISC. Eight
focused tests cover the pinned sources, changed identities/spans/caller sets,
J/JAL targets, bounds and exclusive output/read-only checking. No original
binary bytes are emitted by the source record.
