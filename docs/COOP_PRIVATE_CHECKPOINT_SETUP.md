# Private offline checkpoint entry setup

This is a development fixture for campaign QA, not a retry, progression,
checkpoint reachability or mechanic pass. The first native v12 attempt reached
the requested initializer but exposed an incomplete completion predicate. The
[reviewed receipt](evidence/mmx6-checkpoint/manifest-bound-e2e47e6-incomplete.json)
rejects its automated completion status: both diagnostic actor positions were
still from the old stage and the composed capture was black. This fixture is
not yet qualified for campaign setup.

The immutable [content inventory](COOP_X6_CONTENT.json) retains all 115 tuples.
Only 94 tuples in its 23 authored placement sections are permitted. The other 21
menu, cutscene and unresolved namespace records are explicitly unsupported setup;
they remain unverified. Neither membership in a stage number range nor a
screen load establishes a playable route.

The runner verifies the complete original USA v1.1 EXE SHA256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`
and frozen inventory SHA256
`67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad`.
The generated guard table retains every original stage/section/checkpoint,
pointer table, record pointer and record hash. At acceptance and again at
mode9 entry the actual plugin checks its selected native pointers/record plus
the original dispatcher, mode8 loader, mode9 initializer and checkpoint-selector
instruction spans. Resident FNV32 guards detect mismatched code/data; they are
not cryptographic identity and do not replace the runner's full EXE check.

## Native ordering and restrictions

At the existing outer `stage_tick(8001E9EC)` boundary, command8 is permitted
only offline in a debug build, with healthy enrolled actors, no menu/scene,
no projected or nested callback, and normal native gameplay. It installs the
inventoried stage/section, selects native mode8 and returns handled immediately.
It does not execute the stale stage's original world pass or grant HP/resources.
The native mode8 loader `8001E914` owns loading and its checkpoint reset.

The new function-entry observer at `8001E1BC` requires mode9, the selected
stage/section, checkpoint0 from mode8, `a0=800CCED0` and return address
`8001E720`, proven by the original dispatcher's `jalr` at `8001E718`. It then
installs only the requested checkpoint before returning to ordinary dispatch.
It never calls the initializer, replaces it, uploads an overlay or writes
native tables. A repeated/out-of-order observer fails the pending operation.
The native receipt reaches completion at the subsequent mode0A stage entry
with the selected tuple. That receipt alone does not establish playable entry.
The original runner's publication check was anchored before the payload RPCs,
which could accept a later old-stage publication. Qualification additionally
needs freshness anchored after the completion receipt, actual new actor
initialization/placement and native control readiness, followed by inspected
composed output. Those checks remain under implementation.

Pending state is cleared by activation/reset and by detected plugin,
source/context/order or offline-policy failure. Queued command8 and both
pending phases reject current-build snapshots. No old-state conversion is
provided. A loader that never reaches the next boundary remains incomplete;
the runner preserves that bounded timeout and stops its owned process.

All online and `PSX_NO_DEBUG_TOOLS` paths reject before authoritative game
mutation. Existing commands1..7 retain their rejection policy. No success,
unlock, rescue, clear or persistent native-save flag is written. The fixture
is an explicit stage/checkpoint prerequisite bypass, and accepted setup sets a
sticky diagnostic taint marker until activation. It cannot qualify strict
ordinary-input capture. When the SDK exposes `session_input_taint.h`, acceptance
also calls `psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX)` before game
mutation. The game never resets those host flags; only the SDK session owner
may reset them. Older SDKs retain the diagnostic marker but lack this capture
API taint integration and remain unsuitable for strict recording qualification.

## Diagnostic transaction

The client writes stage, section and checkpoint bytes at `diagnostic+51/+52/+53`,
a nonzero uint32 request nonce at `+54`, then commits command8 at `+50` last.
Only the outer stage boundary consumes an offline command; the controller's
projected/post-player boundary leaves it queued. Invalid tuples, unsupported
namespaces and zero nonces are rejected before any game state write.

| Offset | Receipt |
| --- | --- |
| `+A0` | `CKP1` capability, little endian `31504B43` |
| `+A4` | Request generation, increments when command8 is consumed |
| `+A8` | 0 idle,1 loading,2 initializing,3 complete,4 failed,5 rejected |
| `+A9` | Reason:0 okay,1 forbidden,2 unknown/invalid,3 unsupported namespace,4 unsafe,5 source,6 order,7 context,8 plugin failure |
| `+AA/+AB/+AC` | Requested stage/section/checkpoint |
| `+B0` | Request nonce |
| `+B4` | Guarded initializer entry count; success requires1 |
| `+B8` | Inventoried native record pointer |
| `+BC` | Sticky prerequisite-bypass taint marker |

An acknowledgement alone cannot pass. The runner requires a new generation,
the exact nonce/tuple/record, count1, taint1, completed state, actual native
mode/tuple and a fresh enrolled publication. Separate native/camera and co-op
reads are retained as separate observations, not one atomic world snapshot.

## Reproduction and current validation

`tools/qualify_mmx6_coop_checkpoint.py` reuses the baseline's process lifecycle,
PID/listener checks, hidden muted profile and cleanup. It uses the existing
offline input adapter to settle the intro before the fixture. It requires a
fresh private candidate or explicit build/source/disc/output arguments, an
expected executable SHA256, original source and inventoried selectors. Output
paths remain arguments; no source cards or old caches are copied.

Example after root builds and freezes a candidate containing the observer:

```powershell
$env:TEMP='G:/Temp/Codex/psxrecomp/x6-parity/temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='G:/Temp/Codex/psxrecomp/x6-parity/pycache-checkpoint'
python tools/qualify_mmx6_coop_checkpoint.py --candidate <fresh-private-profile> `
  --original <original-SLUS_013.95-or-raw-BIN> --stage 0x01 --section 0 --checkpoint 1 `
  --expected-exe-sha256 <exact-runtime-sha256>
```

The original baseline report/status stays hash-linked and unchanged. The
separate result is `prerequisite_bypass_setup_completed_artwork_pending` on
automated setup completion, with `ledger_status=unverified`. Partial errors,
command publication history, native bytes, camera, actors and composed capture
are retained. Artwork still needs inspection and no ledger row is changed.

Focused tests compile the actual plugin against isolated guest RAM, using only
read-only pinned original code/data. They do not emulate the native loader or
prove gameplay. They cover all 115 tuples, the 94/21 policy, guarded mode9 ordering,
pending reset/failure, duplicate entry, source/context mutations, deferred
controller handling, no stale original stage call, unchanged HP/body, and
online/production rejection. The existing snapshot fixture additionally checks
queued command8 and both pending phases reject snapshot creation. Python tests
cover frozen inventory/source identity, selectors, CLI guards and incomplete,
rejected, duplicate, stale or mismatched transaction completions.

Validation passed locally: the checkpoint fixture under Clang with `-O2` in
debug/production and the SDK taint header from `ef638ae184a0d0e3f2c389d26e6e16350bfbe57a`,
plus Clang `-O0` and GCC `-O2` without that optional header; the existing
snapshot fixture under Clang `-O2` debug/production; and all 12 Python cases
with the pinned original EXE supplied. The optional API fixture supplies its
own host taint stub and verifies accepted setup taints, rejection does not,
and fixture reset never clears SDK taint. It does not qualify a linked game.
Header reproduction, Python syntax and whitespace checks also pass.

No CMake, coverage, 234-row parity ledger, title build or native run is included
in this change. Root needs to register `test_mmx6_coop_checkpoint.c` and the
Python test in its owned build work, then qualify an actual entry separately.
