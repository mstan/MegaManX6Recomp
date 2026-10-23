# X6 host-state codec and modern candidate registration

This lane starts at game `fb95f99`. It targets the frozen modern
`6f0ccbc6b67fee626de6a7b0945ca3abb26332aa` snapshot/digest interfaces plus the
separately owned loader bridge. It does not establish that SDK's scheduler or
X6 gameplay is qualified. The profile retains disabled rollback and network
state transfer. No comparison ledger passes are added.

## State and resources

`mmx6_coop_snapshot.inc` supplies `state_digest`, `snapshot_provider` schema 1,
and `snapshot_resources_restored`. The integrated modern candidate attaches
them under profile `mmx6-x-zero-delay-v10`; legacy SDK builds without
`mod_snapshot.h` remain buildable and omit those callbacks. Rollback and user
state transfers in netplay remain disabled. Registration alone does not qualify
native restore or rewind.

The explicit little-endian wire includes P2's complete actor/attack/trail/effect
pools; lifecycle, Select history and queued rejoin; retained departure body;
join phase/Y; menu owner, Start history, private menu state and palette backup;
scene owner/phase/body/Y; pickup collectors; per-solid contacts; pending death
effect origins; diagnostic publication count and HUD/packet presentation state.
Enums, booleans, ownership, actor/assembly ranges, duplicate collector records,
counts, guest-allocation identities, immutable asset SHA-256 and exact lengths
are checked before any live host or guest mutation.

Validation stages all fallible pixel allocation/decoding offside. Read only
copies validated state and transfers prepared buffers; it allocates and decodes
nothing. Another provider's failed validation leaves live X6 state intact.
Guest RAM, VRAM, SPU/device state and the mod CPU/DMA allocation backing remain
the framework's separate responsibility: modern `boot_state.c` captures its
`BS_SEC_MODMEM` section and validates that allocation layout. This provider
never represents a RAM-only image as a complete co-op snapshot.

Retained sprite banks now keep canonical compressed decoded pixels, including
X death images whose original compression address can be overwritten by a later
stage/form. Actual decoded content distinguishes those cache entries; unrelated
trailing guest RAM does not. The immutable Zero archive retains its fast source
lookup. Raw/RLE pixels use explicit LE16 values and bounded nonzero run lengths.
UI banks rebuild from the immutable loaded Zero atlas and saved per-bank colors.
The restore callback forgets only IDs `6000..7fff` and installs the resolver before
restored guest execution resumes.

Cold restore requires the same build's guest allocations and original assets to
be loaded first. It accepts an empty retained cache and reconstructs saved IDs
without relying on historical guest compression bytes or a warm GL cache. It
does not promise loading from an uninitialized title screen. The 16 MiB SDK
payload limit is enforced; an oversized incompressible cache is rejected rather
than truncated. Native memory cards are outside this codec and are never edited.

## Canonical digest and safe boundaries

The digest hashes authoritative host state and deterministic guest handles,
including queued rejoin, pickup/solid/death ownership and private menu backups.
It excludes publication count, HUD fade, immutable texture-cache growth, heap
addresses and structure padding. Active projection backups and future-restored
CPU/body/pad/camera/contact/packet locals are exposed as typed owned callback
frames; words hash in LE order. Thus a VBlank digest inside a nested guest call
does not merely hash the stale unprojected P2 body.
The saved guest frame includes its dispatch target and arguments as well as
architectural registers. Explicit caller contexts preserve collector indices,
soul-box restoration, enrollment origins, scene/door decisions, stage return
values, controller samples, render arenas, solid owner indices and HUD return
values across later nested calls. These are owned values, not borrowed local
addresses or an attempt to resume native C execution from serialized bytes.

Snapshot readiness rejects all existing callback/projection guards and every
live callback frame. A stable paused menu is allowed. Callback frames are
bounded to 64 records of at most 8 KiB each; overflow or unbalanced completion
fails closed with an explicit error. Digest reads copied bytes, never borrowed
stack pointers, including after a nonlocal escape.

**Readiness restriction:** a watchdog/scheduler escape can abandon plugin C
frames and half-restored native projections. This lane rejects snapshots in that
condition; full plugin reactivation is required. It does not blindly clear guards
and continue half-applied native state. Such a session cannot save, load or
rewind through the provider. A proven unwind/abort contract is still required
to recover that session without reactivation. The synthetic longjmp fixture
confirms safe digest access and snapshot refusal, not native recovery. Normal
completed callback paths pop their records. Owner save/load/rewind qualification
remains a separate integration gate.

The local package ID `mmx6.local-coop` and forced profile ID
`mmx6.local-coop.prototype` need the same provider and restore callback.
Modern `mod_runtime_snapshot_package_active` in `runtime/src/mod_runtime.cpp`
selects only `profile->plugin_id` while netplay is active; only its offline
branch scans `plan.ordered`. Those provider identities are therefore mutually
exclusive. A forced profile belongs in the internal initial complete-machine
transfer even with `savestates_supported=0`; leaving it without a provider would
omit mutable host state. This conclusion comes from the actual bridge selection
function, rather than an assumed relationship between package and profile IDs.

Central registration sets the profile's `state_digest` and retained-texture
requirement and registers providers for both mutually exclusive IDs. The
resource restore callback belongs to the common implementation plugin
`mmx6.local-coop.prototype`, used by the offline package and forced profile.
Compatibility identity is bumped and online user state jumps/rewind stay blocked.
Nothing here weakens executable,
content or agreed simulation-profile checks.
The diagnostic now publishes the actual
`psx_mod_netplay_has_state_digest()` capability at `+0x9c`. A zero digest value itself cannot
distinguish an unavailable callback from a valid hash.

## Focused evidence and remaining qualification

Actual-plugin fixtures cover source-address reuse with changed X pixels; ignored
trailing bytes; raw/RLE and maximum-run boundaries; malformed/truncated/extra
payloads; invalid enums, resources and cache encodings; allocation failure;
200 validation perturbations without live mutation; allocation-free read; warm
host restoration; empty-cache sprite/UI reconstruction; every named guard;
stable paused UI; canonical state perturbation and pointer-independent callback
frames; actual pickup/body and solid-contact backup restoration; overflow and
abandoned-call rejection using the SDK's `psx_host_escape.h` supported landing
and a live 32 KiB target frame. They run in developer and production variants against
the modern headers. Old and modern SDK source compilation is checked separately.

The focused fixture passed with GCC 15.2 and Clang 22.1 in both developer and
production configurations against bridge
`948b99eba5f98edcc37c475535f84c1cb333b713`. The existing actual-plugin diagnostic
fixture also passed in both configurations. GCC C99 source checks passed against
both the legacy and modern headers. CTest registers
`mmx6_coop_snapshot_debug_test` and `mmx6_coop_snapshot_production_test` when the
modern SDK is selected. No engine build or game execution is claimed by these
standalone fixture results.

The first integrated native delay pair passes nine bounded intro/input/lifecycle
checks and 29 common core/mod samples across four input windows, all strictly
below both peers' resolved-through watermarks. Both peers explicitly report
digest registration. Exact executable/report identities and limitations are in
[COOP_NETPLAY_BASELINE.md](COOP_NETPLAY_BASELINE.md). This does not establish
snapshot round trips or resimulation.

These fixtures contain synthetic memory/resources and do not execute original
game logic. Native warm/cold save/load, mapped rewind, menus, beam/death/scene
transitions, delayed healing, moving terrain, pending DMA, composed art and
same-simulation-tick core/mod peer CRCs remain required. Audio audit added no new
host state; native audio correctness remains a separate unverified obligation.
No game runner, source card or remote service was used by this lane.
