# X6 lifecycle source and helper audit

Baseline: `1d6f67c`; frozen X4 reference:
`50593bca772b600de6911cbfecd40b0f08721147`,
`src/mods/mmx4_coop_lifecycle.c`, native stage gameplay's `departed` branch.
This is source/helper evidence, not a local or netplay gameplay pass.

The X4 branch retains a deliberate rejoin request during the outgoing beam or
unsafe landing, then waits for a genuine living, grounded native leader. It
keeps voluntary departure separate from native death and scene passengers.
X6 retains its own native addresses, beam routines and safe-ground predicate.

The inspected X6 callers exposed three gaps:

- An absent partner's Select edge was discarded whenever the leader was not
  safe on that exact update. `rejoin_pending` now retains a real gameplay edge
  through release, outgoing-beam completion and temporary native locks; the
  existing native ground predicate still controls the one actual join.
- Menus bypass the ordinary controller callback; scene and native-lock returns
  also skipped its edge sampler. Those intervals now call the existing helper
  with `gameplay=0`, consuming history and breaking the departure hold without
  creating a request. A new Select press during a menu/scene cannot become a
  fabricated gameplay edge on resume. An already accepted request remains pending.
- A stale fatal callback could convert voluntary absence into DYING. Fatal entry
  now requires a living actor. Repeated native fatal/completion notifications
  preserve the original wipe owner and cannot cancel a newer queued request.

Leader death or genuine stage/team respawn cancels pending rejoin. JOINING and
LEAVING continue to count as living until native completion, so the existing
survivor recovery can retain that actor if the other hero dies during a beam.
There is no extra life charge or change to native card state. The explicit
pending flag participates in the bounded host digest and must also participate
in any future canonical snapshot serializer and simulation checksum.

Validation uses the actual lifecycle C helper with a source-backed event stream:
90 consecutive gameplay frames; held Select at boot/retry; interrupted holds;
unsafe press/release then safe landing; fresh press during outgoing animation;
duplicate completion; blocked menu/scene edges; both death orders; repeat death
notifications; absent/fallen distinctions and exactly one wipe owner. The new
unsafe-request regression fails on the baseline helper at its safe-landing JOIN
assertion. Debug and optimized builds pass with `-Wall -Wextra -Werror`.
Actual-plugin diagnostic fixtures also pass in debug and production variants,
including pending-flag digest sensitivity.

Native checks still required: both peers' accepted Select streams; actual beam
art/lifetime; airborne leader landing and portal waits; menu transitions;
owner death during each beam direction; survivor play; original death/retry and
forward-section policies; HP/ammo/weapon retention; copied native-card integrity;
and exact core/mod checksum agreement. A subsequent bounded profile-v9 native
loopback smoke passes departure, held Select across primary pause/resume and
fresh rejoin with healthy intro resource retention; exact hashes and the
retained initial harness ownership-encoding error are in
[COOP_NETPLAY_BASELINE.md](COOP_NETPLAY_BASELINE.md). Other checks above remain
open. No full comparison ledger status changes here.
