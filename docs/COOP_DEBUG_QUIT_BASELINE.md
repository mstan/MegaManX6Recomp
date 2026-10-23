# Owned debug quit acknowledgement regression

The [native before/after receipt](evidence/mmx6-shutdown/quit-response-order-summary.json)
qualifies the narrow SDK quit-response correction tracked by `beads-181w`.
All source and evidence remain local.

On frozen executable37cdc487, request `{"id":424242,"cmd":"quit"}` receives
`{"ok":false,"err":"emu busy or frozen"}` without its request ID. The owned
process nevertheless naturally exits0. Two startup probes reproduce this;
the durable regression retains the exact raw reply and independently waits
for natural exit. This establishes an acknowledgement race, not a runtime hang.

`send_ok` buffers while a handler executes. The old handler shuts down and
exits before `debug_server_poll` changes IO_REQ to IO_RESP, so the I/O worker
sends its busy/error fallback. SDK commit `8e7917429` defers shutdown until
the response is published; shutdown joins the worker after it sends that reply.
The isolated original fix is `1a82b081e`.

The fresh developer build from clean game `99ed867` and SDK8e7917429 has image
SHA256 `a9092eee23d44b9cd4f936d0db6ad7f7cc991a83a16797662d8f6e59d468e266`.
Its actual compile manifest/provenance are retained separately. The same probe
now receives the matching successful reply and naturally exits0, with no
termination. The integrated developer suite passes44/44 CTests, including
original content/audio reproduction. Eight owned-cleanup fixtures independently
cover valid/invalid replies, natural exit, timeout, owned termination/kill and
listener-ownership rejection.

The earlier baseline/pair cleanup combined quit RPC and exit wait in one
exception handler. A rejected reply could therefore trigger immediate owned
termination without waiting five seconds. Those historical receipts do not
establish a quit timeout or a shutdown hang. Their raw files and already hashed
review summaries remain unchanged; this note corrects that interpretation.
Current runners retain the protocol error and wait for natural exit before
terminating only their own still-running Popen.

This is a Windowsx64 Clang22.1.8 startup/quit protocol check. Existing `exit(0)`
semantics remain; complete main teardown, future recorder draining, other
platforms and gameplay qualification are separate. R2/R8/R13 evidence stays
bound to executable37cdc487 and is not transferred to the newer build.
