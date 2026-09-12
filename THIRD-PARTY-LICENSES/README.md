# Third-party licenses (MMX6 Tweaks apply path)

This project (MegaManX6Recomp) is licensed **PolyForm Noncommercial 1.0.0**
(see the repository-root `LICENSE`). The **Tweaks apply** feature invokes one
external tool as a **separate process** ("mere aggregation" — the invoked tool
keeps its own license; it does not change the license of this project's code).
Its license and attribution are recorded here.

Nothing of acediez's patcher data is redistributed — see *Attribution* below.

**There is no GPL dependency in this project.** The apply path is one
Apache-2.0 bundled exe (xdelta3) plus pure Python.

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

## EDC/ECC recompute — ours, no third-party code

Recomputing the disc image's EDC/ECC after the hex writes is
[`tools/edc_ecc.py`](../tools/edc_ecc.py): a clean-room, pure-Python
implementation written from the published CD-ROM standard (ECMA-130, 2nd
edition — clause 14 for the sector layout, Annex A for the EDC CRC-32
polynomial and the P/Q Reed–Solomon product code). An algorithm published as a
standard is not copyrightable, so a from-specification implementation carries
no third-party license.

It replaces the external `error_recalc.exe` this project used to invoke, which
was **GPLv3-or-later** (derived from Neill Corlett's cmdpack `ecm.c` EDC/ECC
code). That tool is no longer invoked, shipped, or referenced, so the GPLv3
source-availability obligation no longer applies to any release.

Correctness is established two ways, both in
[`tools/test_edc_ecc.py`](../tools/test_edc_ecc.py):

- **From the definition** — after a recompute, both Reed–Solomon syndromes of
  every P and Q vector are zero, and the EDC table matches a bit-at-a-time CRC
  over the ECMA-130 polynomial. The fast whole-row path is diffed against a
  scalar reference implementation of the same algebra.
- **Against real media** — recomputing a known-good retail PS1 image must
  change nothing. Verified over a full disc (144,972 Mode 2 Form 1 sectors,
  zero differences). Disc images are never committed, so that test reads a
  local image named by `MMX6_EDC_ECC_REF_BIN` and skips when it is unset:

      py -3 tools/edc_ecc.py --verify "path\to\Some Game (USA).bin"

Mode 2 Form 2 sectors, Mode 1 sectors, and CD-DA audio sectors carry no P/Q
parity and are left untouched.

## Attribution (not a bundled tool)

The MMX6 "Tweaks" option research, patch payloads, and patch database are the
work of **acediez** (RomHacking.net utility #1414, "Mega Man X6 Tweaks Patcher").
This project re-implements only the *applicator* so selections integrate with the
recompiler's variant pipeline; **acediez's payload data is never redistributed** —
the tooling reads it in place from the patcher archive the user supplies.

The AutoHotkey engine is used **only as a development-time oracle** (to prove the
Python port byte-identical); it is **not shipped and not run in production**.
