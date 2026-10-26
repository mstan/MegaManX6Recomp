# Co-op resources at session activation

The runtime ends renderer/guest work, retires texture IDs and packet ranges,
and resets both enhancement memory arenas before invoking activation for a
new session. A cached numerical guest address or texture ID has no ownership
after that boundary.

X6 therefore reacquires its asset/diagnostic, world/HUD packet, menu and two
private audio-header allocations on every activation. It clears all derived
addresses and callback backups, discards prepared snapshots, frees encoded
sprite caches and resets sprite/UI bank metadata before new resources load.
The previous audio headers and sample copies are freed, the private audio
calculation/epoch state is cleared, and only this title's owned voices may be
stopped. The SDK owns reclamation of guest/GPU storage and framework banks;
the plugin does not reset shared arenas or poll them during gameplay.

No serializer or restore callback changes are required. Current-build state
restoration retains its existing exact handle/layout and asset identity gates,
prepared cache import, immutable pixel reconstruction and audio header restore.
States remain build-specific; no old-state migration is provided. Native cards
are outside this resource lifecycle and are not modified by activation.

`mmx6_coop_session_resources_{debug,production}_test` embeds the actual plugin
and real SDK `memory.c` and `mod_texture_banks.c`, following the SDK's own
memory snapshot fixture pattern. Its strict bridge refuses access outside
actual allocated extents. Twenty-four reset/activation boundaries exercise
stable allocation layouts, both actual packet registrations, retired bank IDs,
sprite/menu-atlas pixels, balanced plugin host buffers, failed-allocation
recovery and a current state/arena/cache roundtrip. Its host pixels/audio
metadata are authored unit fixtures, not original-game or native QA evidence.

The fixture provides typed fail-fast peripheral/debug/scheduler callbacks for
unrelated hardware routing retained by COFF links. It does not depend on LTO
or section discard to remove those references. Every such callback prints
its name and exits with code 86 if reached; none models an allocator, arena,
bank, replacement table or reset. The pure kernel-range helper is the real
SDK implementation. Existing strict menu-upload callbacks remain separate.
The production fixture defines `PSX_NO_DEBUG_TOOLS`; correctness is not hidden
behind that macro. A source-only companion checks actual SDK reset order and
fixture providers without executing a compiler or game.

`mmx6_coop_session_peripheral_rejection_test` runs three authored rejection
probes against both compiled fixture variants: actual `memory.c` MMIO routing,
actual render-store policy routing and a direct device callback. Each must
produce exactly its named marker and exit 86. A successful return, unrelated
failure or extra output fails the test. The ordinary 24-activation tests run
independently, so a boundary double accidentally reached there fails them.
The probes perform no guest gameplay, use no original assets and touch no
native cards. Their compilation/execution remains a required separate check.

Actual same-process qualification remains separate: keep both OS PIDs through
a real lobby match, owned Escape/BYE soft return and actual rematch Play,
then observe healthy enrollment, independent controls, art, selected profile,
resolved CRC and preserved active/personal cards. An ordinary fresh offline
process cannot establish this contract. The supported lobby-to-offline path
can exercise a local activation in the same process if retained by the runner.

For that runtime audit, a small host-only lifecycle receipt is still useful:
epoch plus pre-reset/post-reset/post-activation guest/GPU used extents, packet
range count, bank count/bytes and title-owned handles/cache counts. Existing
working-set size and screenshots cannot establish resource ownership. This fix
does not add a generic polling API, alter lobby serialization or claim F39
passed from its source/fixture checks.
