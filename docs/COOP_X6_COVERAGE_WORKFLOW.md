# X6 live content coverage workflow

[COOP_X6_CONTENT.json](COOP_X6_CONTENT.json) is an **immutable source inventory**.
Its status/check values are the initial extraction result, all unverified.
The extractor's `--check` intentionally compares that byte-derived report,
and its tests intentionally reject gameplay passes in that report. Do not edit
those values to track QA, or regenerate the inventory over QA results.

[COOP_X6_COVERAGE.json](COOP_X6_COVERAGE.json) is the separate **live coverage
ledger**. [COOP_X6_COVERAGE.md](COOP_X6_COVERAGE.md) is its generated view.
The [tool](../tools/mmx6_content_coverage.py) reads the frozen JSON and never
imports or runs the native extractor. It has no title launch, SDK, tracker,
network or native-card operations. The 234-row X4 comparison ledger stays
separate. R8/R13 receipts and source audits do not confer passes here.

## Existing cases and source binding

There are exactly **1,665 cases and 3,330 independent mode results**:

| Existing source definitions | Cases |
| --- | ---: |
| 23 campaign plus 56 mechanics obligations | 79 |
| 115 native locations, each with its six authored check keys | 690 |
| 128 native Reploids, each with its seven authored check keys | 896 |

Obligation case IDs remain `X6-001` through `X6-079`. Other IDs combine the
existing source ID and check key, for example
`s00-a0-c00/terrain_collision_scroll` or `reploid-000/rescue_p2`. Each case
copies the source definition/native IDs without its initial QA labels and
stores the exact inventory pointer. No new gameplay requirements, variants or
route claims are inferred. All initially shipped mode results are unverified
with empty attempt histories.

The tool pins the exact frozen file SHA256:
`67508ae2e19ad07c2c5cad41e12dbeb5e446e4eb50f033efa75ed306f2636fad`.
The ledger also binds the original EXE/BIN identities and a canonical digest
of all 1,665 definitions. Changed bytes, including reserialized inventory
bytes, fail source admission. Missing, duplicate, invented, reordered or
changed definitions/native IDs/check keys fail validation. A future source
revision needs a deliberately reviewed codec/definition update; initialization
is not a migration or a way to discard results.

## Checkpoint entry survey

The [current reviewed entry-survey receipt](evidence/mmx6-content/manifest-bound-50f4a31-entry60751-three-components-failed-parent-reviewed.json)
retains 49 qualified checkpoint-entry setup components and seven blocked
entries on build `50f4a31`; 38 supported checkpoints remain unvisited.
Its previous-receipt chain retains earlier completed components and failed
runs. Each setup uses the guarded original checkpoint loader and records that
reachability bypass. These observations establish entry setup only; all six
gameplay checks and actual stage-end transitions require separate evidence.
Visible background corruption remains unqualified. The receipt changes no
gameplay coverage statuses.

## Native terrain mechanics

The [reviewed stages0?5 terrain batch](evidence/mmx6-content/manifest-bound-e0fdd1e-six-first-checkpoint-terrain-local-reviewed.json) adds six actual local `terrain_collision_scroll` passes, bringing local mode passes to8. Each checkpoint uses the original guarded initializer only as an approach bypass, then independently exercises both heroes' native jumps/landings and accepted walking with horizontal camera scrolling. All24 composed captures, source/image gates, native cards, strict fixture-taint refusals and owned exit0 were reviewed. Full intervening routes, other mechanics, netplay and campaign obligations remain unverified. Raw Recycle Lab vertical-camera excursions are retained separately; no vertical-camera/shake qualification is inferred.

## Initialize, check, render and record

Use redirected non-C: temp/cache paths. The defaults point to the three
coverage files in `docs`; relative evidence paths use the repository root
unless `--artifact-root` names a stable evidence archive.

```powershell
$env:TEMP = 'G:/Temp/Codex/psxrecomp/x6-parity/scratch/content-coverage/temp'
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = 'G:/Temp/Codex/psxrecomp/x6-parity/scratch/content-coverage/pycache'
python tools/mmx6_content_coverage.py check
python tools/mmx6_content_coverage.py render
```

`initialize` creates a new all-unverified JSON ledger exclusively. **It refuses
any existing destination, even an empty file, and has no force/reset option.**
It does not overwrite the Markdown view. Use it only to create a genuinely new
ledger path, then render that ledger explicitly:

```powershell
python tools/mmx6_content_coverage.py --ledger G:/QA/x6/new-coverage.json initialize
python tools/mmx6_content_coverage.py --ledger G:/QA/x6/new-coverage.json render --out G:/QA/x6/new-coverage.md
```

`check` reads and validates definitions, histories, every receipt and every
referenced artifact, including historical failures. It writes nothing.
`render` performs the same validation and updates only the derived Markdown.
It refuses an output equal to the inventory, ledger or evidence, and refuses
to overwrite a file without its generated-view marker. Neither command
changes statuses/evidence or re-extracts source data.

Prepare one complete receipt JSON outside the ledger, then append it:

```powershell
python tools/mmx6_content_coverage.py --artifact-root G:/QA/x6 record --receipt G:/QA/x6/attempt.json
python tools/mmx6_content_coverage.py --artifact-root G:/QA/x6 check
python tools/mmx6_content_coverage.py --artifact-root G:/QA/x6 render
```

Global path options precede the subcommand. `record` validates the old ledger
and the proposed result, appends the new attempt, retains all earlier attempts
and atomically replaces the JSON through a same-directory temporary file.
An exclusive sidecar lock coordinates record commands; a lock already present
causes refusal. Preserve a healthy operation/lock. Invalid evidence, duplicates
or a detected concurrent ledger edit leave the old JSON intact. The tool has
no replace-attempt or delete-history command. Review Git diffs for manual
edits; receipt hashes detect accidental edits but are not signatures or a
trusted external history anchor.

## Required receipt

Each actual attempt identifies its case and one mode, `local_coop` or `netplay`.
Required fields are:

| Field | Contract |
| --- | --- |
| `case_id`, `mode`, `result` | Exact existing case/mode; result is unverified, blocked, failed, passed or inapplicable. |
| `candidate` | Exact lowercase 40-hex game commit, never an abbreviated/version identity. |
| `recorded_at` | UTC second timestamp, `YYYY-MM-DDTHH:MM:SSZ`. |
| `build_identity` | Object with nonempty `name` and actual nonempty build `image` artifact (`path`, `sha256`). Optional `details` object can retain framework/UI/manifest identities. |
| `settings` | Nonempty object recording effective configuration. Include roster/forms, mods, relevant native prerequisites, transport/state/rollback and other settings needed to reproduce this case. |
| `action`, `outcome` | Concrete accepted native action and observed result; describe the actual destination/damage/reward/retirement that the case requires. |
| `artifacts` | Nonempty list of retained artifact objects with filesystem `path` and lowercase SHA256; optional `role` describes a log, RAM observation, image, audio capture or source audit. |
| `limits`, `bypasses` | Explicit lists of text, possibly empty. State prerequisite cheats, teleports, skipped axes and any reason evidence supports only setup. |

An unattempted mode has status unverified and an empty history, with no
fabricated candidate/evidence. Every recorded attempt, including blocked,
failed or setup-only/unverified attempts, needs all fields above. The stored
mode status must equal its latest attempt. A later pass retains the earlier
failure, its candidate, artifacts, limits and bypasses.

This incomplete template illustrates the shape; replace placeholders with
actual identities and observations before recording it:

```json
{
  "case_id": "s00-a0-c00/terrain_collision_scroll",
  "mode": "local_coop",
  "result": "unverified",
  "candidate": "<exact-40-hex-commit>",
  "recorded_at": "2026-10-23T00:00:00Z",
  "build_identity": {
    "name": "<actual build name>",
    "image": {"path": "candidate/mmx6.exe", "sha256": "<actual-image-sha256>"},
    "details": {"framework_commit": "<exact framework commit>"}
  },
  "settings": {"<effective-setting>": "<actual value>"},
  "action": "<native accepted inputs, positioning and prerequisite steps>",
  "outcome": "<observed native behavior; do not convert setup into success>",
  "artifacts": [{"path": "run/receipt.json", "sha256": "<actual-file-sha256>"}],
  "limits": ["<remaining untested behavior>"],
  "bypasses": ["<disclosed prerequisite bypass, if any>"]
}
```

The checker streams actual files and compares their hashes. It has no
structure-only bypass. Missing files, forged hashes and C: paths are refused;
resolved symlink/junction targets are checked too. C-drive relative/device and
administrative-share spellings are rejected. Keep evidence stable while a
check runs. Hash reuse is invocation-local only; a later check hashes afresh,
so a same-size overwrite with restored mtime is still detected. Prefer stable
relative paths and `--artifact-root` for relocating the same archived bytes
without editing historical receipts. Do not delete failed-run evidence to
make the checker pass.

## Aggregation and inapplicability

Aggregate status is derived, never writable in the ledger. A case passes only
when **both latest independent mode results pass on the same candidate40 and
actual build-image SHA256**. An old common passing candidate cannot conceal a
later failure or a newer unmatched mode. Different candidates/build images
leave aggregate unverified with a visible reason. A current failed/blocked
mode remains failed/blocked. Both inapplicable results also need matching
candidate/build identity; mixed pass/inapplicable is unverified.

Inapplicable requires the additional `native_absence` object:

```json
{
  "kind": "authored_native_content_absent",
  "case_id": "<same existing case ID>",
  "source": {"path": "original/SLUS_013.95", "sha256": "<frozen EXE or BIN sha256>"},
  "audit": {"path": "audit/native-absence.json", "sha256": "<actual audit sha256>"},
  "source_reference": "<exact native table/code window and scoped native IDs>",
  "reason": "<source-backed authored absence for this exact check scope>"
}
```

`source` must be an actual artifact whose SHA matches the frozen original EXE
or BIN, and the hashed audit must also occur in the receipt's evidence list.
The checker does not extract the source or infer absence from a missing handler,
unknown route, unsupported implementation, unavailable test setup or no visible
boss at the current screen. Those remain unverified/blocked. A reviewer must
verify that the cited native source actually proves the claimed absence within
the case scope. Merely typing the structured claim cannot establish it.

Receipt validation establishes identity, file integrity and bookkeeping,
**not gameplay truth or build provenance from a commit string**. A reviewer
still establishes that the actual build corresponds to its candidate, settings
were effective, inputs were accepted and artifacts show the native outcome.
Stage loading, a screenshot alone, synthetic tests, source registration and
teleporting past an obstacle do not qualify behavior. Positioning/protection
cheats may assist QA; setting the success flag being claimed does not.

## Focused tests

```powershell
$env:MMX6_COVERAGE_TEST_TMP = $env:TEMP
python -m unittest discover -s tools -p test_mmx6_content_coverage.py -v
```

Tests use synthetic receipt/image/source files under the supplied non-C:
scratch root. They prove case/mode policy, source/definition drift rejection,
exact candidate/image aggregation, artifact integrity, C-path refusal,
retained failed histories, native-absence admission, malformed input rejection,
exclusive initialization, record locking and non-mutating check/render.
They add no native-content passes. The original inventory/extractor tests and
its all-unverified reproduction contract remain unchanged.
