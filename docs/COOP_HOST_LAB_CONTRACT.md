# Same-machine host-profile lab candidate

The catalog is **disabled by default**. Explicit development builds may set
`-DMMX6_ENABLE_LOOPBACK_HOST_LAB=ON` to exercise the candidate
`mmx6.win64-clang22.loopback`, revision1. This is a route to collecting fresh
evidence, not a production qualification or a correctness-fix rollout switch.
GCC and unsupported builds remain valid offline builds and return an empty
catalog even when the lab option is requested. SDKs before host-catalog API2
keep their original plugin initializer layout and do not install the callback.

The callback checks the actual runtime startup context and the registered
trusted X6 title profile. It requires two occupied seats, delay mode, disabled
network user states, default resident loading, retained OpenGL at 4:3, linked
OpenBIOS with the observed immutable ID/word sum, canonical FP contract2 and
the immutable interpreted-overlay seal. It accepts only Windows x64 GNU ABI
Clang22.1.8, the fixed prior ENHANCED execution identity, and the observed
x64 optional-feature mask0x7f. Requiring exactly that current known mask is
conservative: no CPU missing any observed bit is admitted. PGXP variants and
REFERENCE builds are refused. There is no runtime backend switch, portable
flag, invented fallback or qualified remote/heterogeneous cell.

Both a valid nonzero schema1 declared manifest and the OS-resolved running
image SHA are required. They are separate identities. The profile module's
existing match gate requires identical actual artifacts and binds the selected
profile/revision/semantic digest into its confirmed identity; this catalog
does not replace the existing execution, content, title or settings gates.
The startup API's direct-loopback scope is computed centrally from the actual
resolved route and checked again before transport. It excludes names,
wildcard/remote addresses, ICE, relay, lobby routing and spectators.

[The JSON record](COOP_HOST_LAB_CONTRACT.json) fixes the semantic contract,
prior receipt hashes, exact proof limits and required fresh evidence. Its
canonical UTF-8/ASCII JSON encoding uses sorted keys and compact separators;
SHA-256 becomes the rule's qualification identifier. Run
`python tools/mmx6_host_lab_contract.py` to verify the committed generated
header, or `--write` after an explicitly reviewed record change. This hash is
a contract identifier; it does not turn earlier receipts into evidence for a
new executable. The record deliberately includes the old v10 staging patch
and the incomplete helper matrix, including its link failures and existing
SPU ADSR failures.
An enabled lab build also checks record/header agreement before compiling the
title; it fails rather than silently using a stale semantic identifier.

The actual-source C99 fixture checks a positive callback offer under the real
Clang22.1.8 compiler, a valid descriptor accepted by the SDK codec, unavailable
REFERENCE refusal, and negative CPU/features/backend/FP/seal/scope/seat/loader/
renderer/aspect/BIOS/manifest/image/execution/title-state cases. The test's
expected positive is supplied explicitly rather than inferred from the
implementation's platform guard. Separate disabled and wrong-contract builds
and the PGXP variant must produce no offers. GCC performs the same context predicate checks while
its actual catalog remains empty. Old-SDK source compilation is also checked.

CTest registers `mmx6_host_lab_enabled_test`, `mmx6_host_lab_disabled_test`,
`mmx6_host_lab_wrong-contract_test`, `mmx6_host_lab_pgxp_test` and
`mmx6_host_lab_contract_test`. The standalone checks passed with actual Clang
22.1.8 and GCC15.2 using C99 `-O2 -Wall -Wextra -Werror`; the prior SDK compiles
the empty-catalog fixture and actual plugin. The GCC diagnostic and Clang
canonical snapshot/resource fixtures also pass. No full title was built here.

These tests run no game and supply no native timing evidence. Before enabling
or describing this candidate as eligible, the parent lane must retain a fresh
same-artifact pair and restart/rematch receipt, identical selected SHA on both
peers, actual cycle0/tick0 settlement before guest dispatch, default native
loader/intro/input checks, and resolved core/mod matching. Broader gameplay,
audio, rollback, other hosts and production release remain unverified.
