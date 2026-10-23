# Optional host-profile gate for the owned paired qualifier

`tools/qualify_mmx6_coop_pair.py` preserves its historical default. Add these
options when testing a candidate with the explicit lab catalog enabled:

```text
--require-host-profile
--expected-host-profile mmx6.win64-clang22.loopback
--expected-host-profile-revision 1
```

The expected identity is explicit; the tool does not guess a rule from a
compiler/version/build string. This gate can accompany `--admission-only` or
the existing native gameplay checks. `--require-state-crc` remains a separate
requirement for resolved core/mod digest evidence. No new runtime arguments
are passed and the optional catalog remains a build-time choice, default OFF.

The verifier accepts only the actual installed stderr syntax from SDK
`792469321`, `runtime/include/netplay_host_startup.hpp`:

```text
psxrecomp: actual-image-sha256=<64 lowercase hex> cpu-arch=2 features=7f backend=2 fp=2 overlays=interpreted offers=1
psxrecomp: host profile settled profile=<expected> revision=<expected> selected_sha256=<64 lowercase hex> cycles=0 sim_tick=0 before-enter-guest=1
```

Each owned peer must log exactly one complete capability line followed by
exactly one complete settlement. Both must agree on installed capabilities,
profile, revision and selected SHA. The actual image SHA must match the staged
candidate, whose file hash is rechecked at startup and shutdown. The current
lab predicate is deliberately exact: x64, feature mask `0x7f`, ENHANCED backend
2, FP contract 2, interpreted overlays, one offer. Broader CPU/catalog coverage
needs separate reviewed evidence. The runtime emits the capability line only
after checking `features_known`, actual CPU probing, canonical FP state,
available backend and immutable overlay sealing; the parser does not invent
an additional `features_known` log field.

Missing or incomplete live records wait within the existing setup deadline.
Complete malformed records, duplicates, a later repeated settlement, wrong
image/profile/revision, nonzero guest cycles/ticks and integer overflow fail.
The complete logs are checked again after both owned writers stop. A failure
then revokes an earlier pass and clears default-launch/default-intro claims.

Before launch, the gate also requires one unambiguous manifest/header pair
under the actual build's `psx_build_manifest/psx-runtime/` directory (normally
`Release/manifest.{json,h}`). It checks schema 1, declared-input coverage,
canonical SHA-256 excluding the `sha256` property, duplicate JSON keys, file
metadata and matching header macros. Each staged executable must contain the
header's exact ASCII digest. Validated manifest/header bytes are retained in
the pair output's `logs/`; their file hashes and declared digest are recorded
in `qualification.json`. Ambiguous configuration records fail instead of
guessing which one produced the executable.

The executable string check proves declared bytes are present. It does not
prove complete source/dependency provenance, whole-binary reproducibility,
cross-build compatibility or native simulation correctness. The selected SHA
is compared between the peers; this parser does not reconstruct its session
nonce/content/qualification preimage. The actual title catalog and existing
network admission checks retain that responsibility. Passing parser fixtures
does not qualify the candidate's fresh native paired route or restart.

Pure tests: `test_coop_host_profile.py` and `test_mmx6_coop_pair_options.py`.
They require no game launches, original assets, sockets or cards. Set process
temp/cache paths to F: or G: before running them.
