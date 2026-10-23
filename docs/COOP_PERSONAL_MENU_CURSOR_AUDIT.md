# Pristine Zero personal-menu cursor route

Use **Down, then Up** for the existing pristine intro Zero roster:
published pressed masks `0x0040`, then `0x0010`. The source-backed route is
cursor **0 → 0x0D → 0**, with input substate **0 → 2 → 0**. No confirmation,
inventory grant or relaxed check is needed. The paired adapter supplies this
pair explicitly; the shared helper and its generic defaults remain unchanged.

[COOP_PERSONAL_MENU_CURSOR_AUDIT.json](COOP_PERSONAL_MENU_CURSOR_AUDIT.json)
records the original EXE identity, exact code/table region hashes, native
fields, availability predicates, branch addresses and the retained original
failed Right attempt. Original source is SLUS-01395 USA v1.1 EXE SHA-256
`dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046`.
Reproduce each region hash using file offset
`guest_address - 0x80010000 + 2048`; no original binary is copied here.

Native `80034830` passes menu base `800CF810`. State is base+`0x04`, input
substate base+`0x05`, cursor base+`0x14` (`800CF824`), and eligibility slot `i`
is base+`0x16+i`. Initializer `80032DF0` makes Zero's base-weapon slot0 equal2
(truthy), leaves unearned weapon slots1–8 zero and explicitly clears slot9.
Without earned abilities, Giga field base+`0x2D` is zero. Without tank ownership
bits `PLAY+0x6A & 0x7000`, slots`0x0A`–`0x0C` are zero. This makes Right's
native `0x2000` edge scan fail to find a tank, exactly as the original fresh
offline attempt observed. The old Right fixture granted a tank first and is
not an equivalent pristine-inventory setup.

Crucially, `80032FE8`–`80032FF0` unconditionally sets slots`0x0D`–`0x0F` to1.
The weapon input handler `80033214`, on Down edge `0x4000`, skips empty
weapon slots and absent Giga, finds slot`0x0D` at `800333A4`, selects input
substate2, and stores cursor13 at `800334CC`. Lower-menu handler `800337EC`,
on Up edge `0x1000`, skips absent Giga and slot9, scans weapon slots8 down
to0, finds Zero's truthy slot0, selects substate0 at `80033954`, and stores
cursor0 at `80033A04`. The original native input words are byte-swapped from
the paired runner's published pressed masks.

Node`0x0D` has a proven menu-close/resume confirmation branch at
`800338C0`–`800338D4`; it does not set the exit-route word. The close handler
at `80034714`–`80034734` consequently resumes native gameplay. Its exact
on-screen label is not guessed. Node`0x10` is a distinct stage-exit branch:
confirmation sets menu+`0x38` to1, and `80034738` onward leaves gameplay for
native mode`0x0B` (sometimes`0x13`). Its availability is stage-clear gated by
`PLAY+0x0C` and `PLAY+0x60`; outside the initializer's stage1–8 range this
slot is not rewritten, so no live intro value is inferred. Neither
confirmation path is invoked by the corrective cursor check.

This source audit resolves setup eligibility only. The failed Right receipt
remains unchanged. Fresh local/paired accepted-input evidence, frozen-world
ownership checks, resource retention, resolved CRCs and composed artwork
review remain separate requirements; no R8 result is marked passed here.
