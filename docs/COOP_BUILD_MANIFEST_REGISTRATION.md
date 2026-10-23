# X6 declared build manifest registration

X6 explicitly registers `psx-runtime` and, when present,
`psx-runtime-pgxp`, `psx-cosim` and `psx-cosim-pgxp` with the SDK's separate
declared-input build-manifest API. It requires the API; an SDK lacking it fails
configure. No existing title, execution, content or wire identity gate is
removed. The manifest does not qualify a simulation profile or change network
behavior.

The registration captures the final target sources, including generated game
and BIOS units, runtime sources, trusted EXTRAS and UI units directly added to
that target. Source roots include the title, SDK, actual build directory,
selected UI/net/RB trees, compiler/toolchain and relevant prefetched roots.
The exact selected generated-game tree has its own logical root so a junction
onto the scratch drive remains covered after canonical path resolution.
Unmapped or missing direct inputs reject. The Windows resource object is an
explicit prerequisite before its bytes are hashed. SDK generated sources in
the source tree map to `sdk/`; binary-tree generated sources map to `build/`.

Scoped header trees cover game `src/`, game generated headers, SDK
`runtime/include`, UI `src`, and net/RB `src` and `include`. Inputs also include
the title CMakeLists, registration/provenance recipes, SDK runtime/CMake recipes,
dependency CMakeLists and SDK `third_party/deps.manifest`. The SDK generator
captures target flags per C/C++/RC language, global compiler/configuration
flags, source-specific properties, source lengths/hashes and compiler binaries.

A prerequisite refreshes immutable Git HEADs for the exact selected game, SDK,
UI, net and RB repository roots on every build. It hashes current bytes of all
tracked edits relative to HEAD, records deletion/mode/status changes and hashes
the normalized CMake cache. A nested directory cannot silently inherit its
parent repository's pin. Provenance and generated identity headers are written
only when their content changes. This detects tracked dependency edits even
outside the scoped header trees. Clean tracked dependency inputs are represented
by their actual immutable repository pin, not a hard-coded expected version.

`src/mmx6_build_manifest.c` anchors the target's compiled SHA via the portable
plugin constructor macro. It exposes `mmx6_declared_build_manifest_sha256()` and
makes the SHA inspectable in the executable before transport consumes it. It
does not touch guest RAM, card state or settings. SDK consumers compiled as part
of the target can use `psx_compiled_build_manifest_sha256()` directly.

## Local qualification

The isolated production target built successfully using Clang 22.1.8 from the
existing Windows pack, two compile jobs, disconnected FetchContent and the
existing prefetched libchdr/libwebp/libjuice sources. Baseline game source was
`75cdf7e`; SDK source was frozen in a separate local worktree at `f8176ce5b`
plus the mixed-language manifest correction `160e35581`. No game was launched.
Normal target qualification declared 636 files and C/C++/RC option records.

An isolated comment appended only to tracked
`src/mods/mmx6_coop_snapshot.inc` changed the declared identity from
`8bae2ba1bf0b0616a85050cbf34d4e87973f7e66d6e0625234e57ded79cf5d6e` to
`362ebcb0492fff7aa1a704df54c9fc55c31e2124baa5878bda0ec4f493b3a4c1`.
The build compiled exactly the consuming co-op plugin and manifest anchor,
then relinked. The resulting executable SHA changed and its bytes contained
the new compiled manifest SHA. Restoring the include restored the original
declared identity. The executable SHA differed again after restoration: this
is explicitly not a reproducible-binary or whole-binary identity claim.

Private logs and observations remain under
`G:/Temp/Codex/psxrecomp/x6-parity/temp/manifest-registration/`, including
`manifest-real-build-probe.json` and baseline/probe/restoration build logs.
These observations apply to that isolated dirty qualification tree, not a
later committed/staged build. A final commit, dependency update or tracked edit
changes provenance and requires a fresh identity. Optional PGXP/co-sim targets
are registered when present; their full builds were not run in this lane.

The SDK mixed-language fixture also compiles real C/C++ units with different
language options and retains implementation/header/option/generated-source
mutation, relocation and rejection checks. The game provenance fixture uses
real Git repositories to check unchanged HEAD with changed tracked bytes,
deletion, relocation normalization and rejection of an inherited parent pin.

## Coverage limits

Coverage remains `declared-build-inputs-v1`, `whole_binary=false` and
`heterogeneous_qualified=false`. It does not prove complete toolchain/sysroot,
external library binary, driver or dynamically loaded backend provenance.
Prefetched archive trees use the declared archive pins/recipes and actual
configuration; this registration does not independently verify every extracted
archive file against its expected archive. Untracked dependency implementations
outside direct target sources/scoped headers are not represented by Git HEAD
or tracked-edit provenance. Source generation recipes and configuration do not
imply that every generated auxiliary include was separately hashed.

Before this identity becomes a required capability-envelope field, integration
must validate the actual staged candidate's manifest, close any relevant
coverage omissions, retain all existing build/content gates and separately
qualify eligible CPU/backend/profile combinations. No cross-compiler, CPU/OS,
netplay or campaign comparison pass is claimed here.
