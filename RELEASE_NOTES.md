# MegaManX6Recomp v1.0.6

v1.0.6 is a patch release. It fixes fast-forwarding that could not be turned
off, and ships a much larger bundled overlay cache.

## Turbo loads is off, and stays off

The game no longer fast-forwards through loads unless you ask it to.

Earlier builds shipped with load acceleration enabled in `game.toml`, and the
launcher had already stopped drawing a control for it — so there was nothing a
player could switch off. It ran the machine at host speed whenever a load was
detected, which also sped through timed screens: the **WARNING** screen at the
start of a new game advanced by itself, and loading icons spun too fast.

Reported by **Arquivista** in [#14](https://github.com/mstan/MegaManX6Recomp/issues/14).

**If you played v1.0.4 or v1.0.5, this affects you even though you never turned
anything on.** Those builds wrote the setting into your `settings.toml`, and the
old runtime restored it on every launch — so it outranked any later change and
could not be undone by updating the game files alone. v1.0.6 ignores that stored
value and drops it the next time settings are saved. No action needed on your
part; you do not have to delete anything.

Want faster loads back? They live in **Mods → Quality of Life**, where you get
real control instead of one hidden switch:

- **Fast Loading (host pacing)** — runs the machine faster while a load is in
  progress. Every guest frame, CD interrupt and callback still happens on
  schedule, so the game cannot desync. It does speed the game up during a load,
  which some speedrun routes rely on *not* happening.
- **CD Speed** — makes the emulated drive deliver data sooner while the game
  itself keeps running at normal speed. Better if you want shorter loads without
  the game moving faster.

Both ship disabled. FMV and CD audio keep authentic timing either way.

## Larger bundled overlay cache

The package now includes **559** precompiled native code shards on Windows and
**558** on Linux, up from 72. More of the game runs as native code the first
time you reach it, instead of being interpreted until your own cache builds up.
This is a startup-smoothness improvement; it does not change behaviour.

## Also in this release

- The Windows packager now takes its version from a single source shared with
  the Linux packager, so the two platforms can no longer disagree about which
  release they are.
- Fixed a packaging bug that placed the bundled overlay cache in a directory the
  loader does not scan. A package built that way looked correct and reported a
  healthy shard count, but every overlay would have run interpreted.
- Refreshed the recompiled BIOS fingerprint. The generated BIOS code itself is
  byte-for-byte identical to v1.0.5 — only the staleness marker was out of date,
  so nothing about how the game runs changes.

## Compatibility

Save files, memory cards and savestates from v1.0.4 and v1.0.5 continue to work.
Your disc image is unchanged and is still not included.
