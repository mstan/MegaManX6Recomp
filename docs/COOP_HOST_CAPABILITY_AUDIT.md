# X6 host optimization capability audit

This source audit finds working fixed execution identity and a pre-admission
agreement gate, but the inspected PSX setup does not implement the owner's
required exchange of actual CPU features, available backends and qualified
simulation profiles, or selection of a common portable fallback. X6 v10 is a
title simulation policy, not a negotiated hardware capability profile. No
cross-CPU, cross-OS or cross-build qualification is established here.

The scope is the local SDK at `9cb68408232f926a9c62a57bfcf9e4f829922261`,
recomp-net at `e53059306824edf4f0aec4aae5ae65151b18535f`, and committed X6 at
`5f9ba57c6cd3665182b3093bcadd7889f36f574e`. Reads of game source use that
commit, not changing integration work. The companion
[JSON manifest](COOP_HOST_CAPABILITY_AUDIT.json) records Git blob identities,
SHA-256 and lengths for 26 source files and full-file hashes for the two local
owner policy documents. No binaries, game assets or native saves are copied.

## Required contract

The source policies are
`F:/Projects/recomp-template/NETPLAY.md#host-optimization-capabilities` and
`F:/Projects/recomp-template/OPTIMIZATION.md#host-assembly-portability`.
They require actual architecture/optional instruction features, available
backends, qualified profile revisions and build identities during setup;
selection and confirmation of a common validated profile before frame 0;
an agreed functioning portable fallback where required; and a fixed selection
for the match. Existing game/core/config identity checks must remain. Different
implementations are acceptable only with qualified identical guest results.
Compilation, a shared version string and same-host replay do not qualify a
heterogeneous match.

## Implemented path and limits

| Area | Source evidence | Finding |
| --- | --- | --- |
| Fixed implementation selection | SDK `cmake/psx_execution_profile.cmake:1`, `:9`, `:133` | Developer build choice `ENHANCED` or `REFERENCE`, default `ENHANCED`. Only one implementation source list links. The selection cannot switch during a match. |
| Source-contract identity | Same CMake file, SDK `runtime/runtime.cmake:1616`, `runtime/include/execution_identity.h:10` | SHA-256 includes fixed profile, sorted registered implementation families, contract revisions, selected source hashes and declared shared contract hashes. The session then binds it to optional content identity. Bytes identify sources independently of workstation paths. |
| Mutual agreement | SDK `runtime/include/netplay_content_gate.h:10`, `runtime/src/psx_netplay.c:4154`, `:5131`, `:5319` | The full 256-bit identity travels as four fragments. Every occupied peer must match and acknowledge the occupied set. Mismatch blocks `psx_netplay_poll_admit` before admitting simulation. The exchange can occur after transport reaches RUNNING; transport RUNNING does not itself mean a guest frame was admitted. |
| Transport bootstrap | Net `src/protocol/rnet_protocol.c:77`, `src/session/rnet_session.c:608`, `include/recomp_net/config.h:16` | HELLO carries magic, session, seat, slot count, delay and wire version. It checks wire version and settles delay. It does not carry CPU features, backend availability or qualified simulation profile offers. |
| PSX lobby settings | SDK `runtime/include/psx_lobby_client.h:210`, `runtime/src/psx_lobby_client.c:2063`, `:2130` | Concrete settings cover aspect, loader/BIOS/boot, input, transport, cards, language and mod plan. No CPU architecture/optional-feature set, backend offer set or qualified simulation profile set is serialized. |
| Generic extension points | Net `include/recomp_net/lobby_client.h:240`, `:348`, `docs/lobby.md` | Generic lobby `ext`/codec and opaque `session_variant` can carry engine data. They do not implement PSX capability selection. PSX retains a separate concrete lobby client/serializer. |
| Module feature bits | Net `include/recomp_net/module.h` | ABI/wire/module feature and source-build metadata describe a locally loaded transport module. ICE/RB-engine feature flags do not advertise remote CPU instructions or qualified guest simulation. |
| Rollback fingerprint | Net `src/rollback/rnet_rb_driver.c:1503`, `:1780`, `include/recomp_net/rb_driver.h:234` | Opaque optional build/content fingerprints support equality diagnostics. They are not hardware offers or a fallback selection protocol. X6 v10 disables rollback, so this path cannot alone establish X6 delay-sync setup coverage. |

The content gate is conditional when invoked with an empty legacy identity;
the normal CMake-generated execution identity enables it even without mods.
Its existence must not be interpreted as evidence that a particular candidate
binary contains a nonempty generated identity. Inspect that candidate's
`.execution.json` and compiled configuration when qualifying a build.

There is no inspected startup operation that intersects each peer's available
qualified profiles, selects a common validated profile, selects a portable
fallback if necessary, and confirms the selection. `REFERENCE` is a build
selection, not a negotiated fallback. Rejection of different fixed source
identities is useful admission protection, but does not fulfill the complete
capability policy.

## X6 v10 interaction and build identity

The committed X6 constructor registers `mmx6.local-coop.prototype` with
compatibility ID `mmx6-x-zero-delay-v10`, rollback and user savestates disabled,
three fixed aspects and the X6 widescreen plugin. Under
`MMX6_COOP_MODERN_STATE`, it adds the state digest callback and requires
retained texture banks. Its loading package/feature/plugin are explicit.

SDK `runtime/src/mod_netplay.c:86` hashes the execution/content identity plus
the title plugin ID, compatibility ID, aspect policy/selection, rollback,
savestate, skip-BIOS and retained-texture flags. It also binds relevant
renderer, options and loading policy. The related session namespace includes
the title compatibility ID, aspect and loading selection. These preserve
important title/config distinctions when a capability protocol is added.

The retained-bank requirement is checked locally. SDK
`runtime/src/main.cpp:18627` rejects a non-OpenGL choice for this title;
`:19543` rejects missing working retained-bank support before starting
transport and the guest fiber. This is a concrete fail-closed backend admission
path, not a peer exchange of available backend sets. No software retained-bank
fallback is negotiated. Refusing an unavailable required renderer is
appropriate until a conforming alternative exists.

There is an additional identity limit to preserve in follow-up work. SDK
`runtime/src/psx_lobby_client.c:1070` returns the forced profile compatibility
ID before considering the ordinary release/game version. Thus X6 v10 replaces
the normal lobby version label. SDK `runtime/src/mod_runtime.cpp:1775` builds
the forced profile plan from that compatibility ID and selected options; it
does not automatically hash every executable-owned plugin body. The execution
stamp hashes explicitly registered source/contract inputs, not the whole
executable, compiler version/options, CPU features or every runtime source.
The default shared contract list is GTE/PGXP bodies and adapter headers.

Consequently two builds sharing v10 and the declared execution contract may
still differ outside those declared inputs. This audit does not establish
that all such differences are safe or unsafe. Do not claim exact-binary or
cross-build compatibility from these fields. Capability selection must retain
the existing identity gates and bind a truthful game/core/build identity; a
feature bit or common profile name must not bypass them.

## Portable implementation example

SDK `runtime/src/mdec.c:10` conditionally includes SSE2 intrinsics and keeps a
scalar IDCT fallback (`:273`, `:405`). x86-64 SSE2 is a baseline; the 32-bit
condition represents the compiler's SSE2 target contract, not runtime CPUID
discovery. Initialization compares SSE2 against scalar for deterministic IDCT
patterns and RGB rows (`:381`, `:806`) and aborts on disagreement. These are
useful local equivalence checks. They do not exchange capability offers,
qualify every instruction/path or establish an OS/architecture matrix. The
NEON include condition alone is not evidence of a qualified NEON IDCT backend.

This bounded audit did not inventory every assembly/SIMD path, compiler flag,
generated code family, device backend or renderer readback path. The example
must not be generalized into a universal portability or determinism pass.

## Necessary next work

1. Inventory simulation-affecting optimized implementations and supported
   portable contracts. Define explicit profile/revision, architecture/features
   and compiled/actually available backend descriptors, with qualification
   evidence for each permitted implementation pair. Separate presentation
   only after checking readback, ordering, digest and snapshot effects.
2. Add one startup offer/selection/confirmation protocol for every supported
   PSX entry path, including direct/LAN sessions. A generic lobby extension
   alone does not cover direct sessions or advertise each peer's capabilities.
   Choose the common validated semantic profile, otherwise the agreed portable
   contract, otherwise reject. Missing or malformed required offers must not
   silently mean qualified support.
3. Bind the selected profile/revision and required build/config identity to
   the existing full identity gate. Keep the result fixed for the match.
   Do not introduce continuous feature polling or live switching.
4. Add focused protocol/admission tests for asymmetric features/backends,
   no common qualified profile, unsupported fallback, malformed/truncated
   offers, dropped confirmation and profile/build identity mismatch. Verify
   zero guest frames before mutual confirmation on every entry path.
5. Qualify actual optimized/fallback builds across the relevant CPU/OS pairs
   using guest results, memory/devices/completion and deterministic replay.
   Include rollback for profiles that permit it; X6 v10 remains delay-only.
   Build representative targets with specialized assembly excluded, then
   measure the real workload before promoting a faster implementation.

No tests or runtime sessions were executed by this source-only audit. The
parent's existing evidence is same-host Windows loopback; it supplies no
cross-CPU/OS qualification. All heterogeneous qualification remains
**UNVERIFIED**, and no comparison ledger row is passed by this document.
