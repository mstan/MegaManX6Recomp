# Disc identity — Mega Man X6 (USA)

Redump-verified clean dump. Format: **bin/cue, single track, MODE2/2352, NTSC-U**.
Do **not** convert to ISO — a 2048-byte "cooked" ISO discards the Mode-2 Form-2
XA sectors PSX uses for streaming FMV/audio.

| Field | Value |
|-------|-------|
| Title | Mega Man X6 (USA) |
| Serial | SLUS-01395 |
| Revision | **v1.1** |
| Track | 01, MODE2/2352, data |
| Size (.bin) | 599,985,792 bytes |
| CRC32 | `8E6D014D` (per Redump, v1.1) |
| MD5 | `237B6FEDDD1A88E86AB1CDDC8822F03F` |
| SHA-1 | `D4F7E08371027A87A3BF13311DB5A4C56733F4EA` |

Verified 2026-05-28: locally computed SHA-1/MD5 match the Redump entry for
Mega Man X6 (USA) **v1.1**.

Redump also tracks a **v1.0** (CRC32 `031BE0E9`, SHA-1
`80F856D4ECF4B7BD25A15173E1228AB73B48AF98`). We build against **v1.1**, the
later/bug-fixed revision — the sensible default. Switch to v1.0 only if a
specific community/RE baseline requires it.

Boot EXE: `SLUS_013.95` — load `0x80010000`, entry `0x80054AD8`, text `0x7F000`.
Disc image and extracted EXE are local-only (gitignored); recreate from the
source dump if missing.
