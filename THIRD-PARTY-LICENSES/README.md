# Third-party licenses (MMX6 Tweaks apply path)

This project (MegaManX6Recomp) is licensed **PolyForm Noncommercial 1.0.0**
(see the repository-root `LICENSE`). The **Tweaks apply** feature invokes a
small number of external tools as **separate processes** ("mere aggregation" —
the invoked tool keeps its own license; it does not change the license of this
project's code). Their licenses and attributions are recorded here.

Nothing of acediez's patcher data is redistributed — see *Attribution* below.

## Bundled / invoked tools

### xdelta3 3.0.11 — Apache License 2.0
- Applies the base binary (VCDIFF) patch (`b01`/`s02`/`s03`).
- Copyright (C) 2007–2015 Joshua MacDonald.
- The 3.0.11 sources were **relicensed by the original author under Apache 2.0**
  (branch `release3_0_apl` of <https://github.com/jmacd/xdelta>, *"Change to APL
  based on 3.0.11 sources"*). We ship/track the Apache-2.0 build of this exact
  version — **no GPL obligation**. (The original GPL build lives at
  <https://github.com/jmacd/xdelta-gpl>; we do not use it.)
- License text: [`Apache-2.0.txt`](Apache-2.0.txt). NOTICE:
  [`xdelta3.NOTICE.txt`](xdelta3.NOTICE.txt).

### error_recalc — GPL v3-or-later  *(slated for removal — see below)*
- Recomputes the disc image's EDC/ECC after the hex writes.
- Derived from **Neill Corlett's EDC/ECC code** (cmdpack `ecm.c`,
  Copyright (C) 2002–2011 Neill Corlett), which is **GPLv3-or-later**; therefore
  error_recalc is distributed under **GPLv3-or-later**.
- License text: [`GPL-3.0.txt`](GPL-3.0.txt). NOTICE:
  [`error_recalc.NOTICE.txt`](error_recalc.NOTICE.txt).
- Because it is a **separate process**, its GPL terms do **not** extend to this
  project's PolyForm-NC code. If a release ships the error_recalc binary before
  the replacement below lands, that release must also make the error_recalc
  source available per GPLv3 (§6).

## Planned: remove the one GPL dependency

The EDC/ECC recompute is being reimplemented **clean-room in pure Python** from
the published CD-ROM standard (ECMA-130 / "Yellow Book": the EDC CRC-32 and the
P/Q Reed–Solomon ECC parity). The *algorithm* is a standard and is not
copyrightable — only Corlett's specific code is — so a from-spec implementation
carries **no license** and is not a derivative of error_recalc.

Once that lands, `error_recalc.exe`, `GPL-3.0.txt`, and
`error_recalc.NOTICE.txt` are removed, leaving the apply path as:
**one Apache-2.0 bundled exe (xdelta3) + pure-Python everything else** — no GPL,
no AutoHotkey.

## Attribution (not a bundled tool)

The MMX6 "Tweaks" option research, patch payloads, and patch database are the
work of **acediez** (RomHacking.net utility #1414, "Mega Man X6 Tweaks Patcher").
This project re-implements only the *applicator* so selections integrate with the
recompiler's variant pipeline; **acediez's payload data is never redistributed** —
the tooling reads it in place from the patcher archive the user supplies.

The AutoHotkey engine is used **only as a development-time oracle** (to prove the
Python port byte-identical); it is **not shipped and not run in production**.
