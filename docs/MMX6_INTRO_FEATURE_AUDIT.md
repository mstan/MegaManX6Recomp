# MMX6 intro feature audit

Status: accepted for native mod-loader ingestion, pending the live smoke tests
below. These are three independent, default-disabled features in the `Game
Intro` group:

| Feature ID | Tweaks selection | User-facing name |
|---|---|---|
| `skip_capcom_video` | `IntroSkip01=1` | Skip Capcom video |
| `skip_opening_video` | `IntroSkip02=1` | Skip opening video |
| `disable_title_demos` | `IntroSkip03=1` | Disable title-screen demos |

They are separate feature checkboxes, not choices in one feature. Enabling or
disabling one must not change either of the others.

## Reviewed operations

All four operations are guarded `main_exe` writes against the verified USA
v1.1 `SLUS_013.95`. The SLUS ISO entry begins at LBA 210930, its PS-X EXE load
address is `0x80010000`, and the normal 2048-byte PS-X EXE header is excluded
when mapping file offsets to guest PCs.

| Feature | Tweaks raw BIN offset | SLUS file offset | Guest PC | Expected stock bytes | Replacement |
|---|---:|---:|---:|---|---|
| `skip_capcom_video` | `0x1D92F1B8` | `0xD360` | `0x8001CB60` | `F872000C` (`0x0C0072F8`, `jal 0x8001CBE0`) | `00000000` (NOP) |
| `skip_capcom_video` | `0x1D92F200` | `0xD3A8` | `0x8001CBA8` | `7A4F000C` (`0x0C004F7A`, `jal 0x80013DE8`) | `00000000` (NOP) |
| `skip_opening_video` | `0x1D92FB78` | `0xDBF0` | `0x8001D3F0` | `B369000C` (`0x0C0069B3`, `jal 0x8001A6CC`) | `00000000` (NOP) |
| `disable_title_demos` | `0x1D93082C` | `0xE774` | `0x8001DF74` | `FFFF4224` (`0x2442FFFF`, `addiu v0,v0,-1`) | `00000000` (NOP) |

`skip_capcom_video` owns both of its writes atomically. A failed expected-byte
guard at either PC must reject the whole feature rather than apply half of it.

The AHK source declares these exact writes in `_src/data/_dat.ahk`. The
independent Python applicator resolves the same two/one/one feature-owned
writes. The reference pipeline normally also applies the B01 xdelta and
prepends 15 `PatchList_Base` variables (41 common writes), producing 43 total
writes for `IntroSkip01` and 42 for `IntroSkip02` or `IntroSkip03`. None of that
common scaffolding belongs to these native features.

The four expected instructions are byte-identical in:

- the verified stock USA v1.1 image;
- `base.bin` (the B01 base);
- `s02-base.bin`;
- `rockman-jp-title.bin`; and
- `retranslation.bin`.

The NOPs locally skip a call or stop the title/demo countdown decrement.
Therefore the operations map directly to stock SLUS code and do not depend on
`PatchList_Base`, a derived disc, relocated DAT records, or a replacement EXE.

## Oracle and composition evidence

The factorial images under `build-mod-platform/test-mod-variants/tweaks-matrix`
contain all four NOPs in every available `__skip_intros.bin` context:

- Mega Man title + original script;
- Mega Man title + retranslation;
- Rockman title + original script; and
- Rockman title + retranslation.

The corresponding `__none.bin` or `__no_nightmare_effects.bin` controls retain
all four stock instructions. This proves the reference patcher composes the
three intro selections with both currently converted localization features.

Warning: the older top-level
`build-mod-platform/test-mod-variants/skip-intros.bin` contains the
`IntroSkip01` and `IntroSkip02` NOPs but not the `IntroSkip03` NOP. It is stale
or incomplete evidence for the third selection and must not be used as its
parity oracle. The factorial matrix is the reviewed `IntroSkip03` evidence.

## Collision and runtime audit

The current Title Screen feature owns only `disc_user` overlays, so it cannot
collide with these `main_exe` writes. The current Retranslation executable
ranges do not intersect `0x8001CB60`, `0x8001CBA8`, `0x8001D3F0`, or
`0x8001DF74`; its disc overlays are also separate targets.

Future `TitleLoading02` and `TitleLoading03` conversions may also request the
NOP at `0x8001DF74`: the original Tweaks GUI forces demos off for alternate
loading logos. That is an identical write and should coalesce or use an
explicit shared internal effect. It is not a reason to make either
user-facing feature mutually exclusive.

The runtime applies each guarded main-EXE write once before the game entry
point and marks the affected executable range dirty. `skip_capcom_video` dirties
one code page; the other features dirty one page each. The first two paths are
boot-only. `disable_title_demos` may run its small dirty-interpreted countdown
function while the title screen is idle, so title-idle performance must be
measured. No per-frame mod-list scan or permutation-specific recomp is needed.

## Required live smoke tests

- With all three features disabled, observe the stock Capcom video, opening
  video, and automatic title-screen demo.
- Enable only `skip_capcom_video`: the Capcom video is skipped, while the
  opening and title demos remain stock.
- Enable only `skip_opening_video`: the Capcom video remains, the opening is
  skipped, and title demos remain stock.
- Enable only `disable_title_demos`: both videos remain, then leave the title
  screen idle past its normal timeout and confirm that no demo starts.
- Enable all three together and confirm that boot reaches the title screen
  without either video and remains there while idle.
- Repeat the all-enabled test with Japanese Title Screen and Retranslation both
  enabled; verify the Rockman title artwork and translated text still appear.
- Disable each intro feature one at a time from the combined configuration and
  confirm only that behavior returns to stock.
- Confirm resolution reports no collision among the three intro features,
  Title Screen, and Retranslation.
- Corrupt or substitute one expected instruction in a test fixture and confirm
  the affected feature fails closed; specifically verify the two-write Capcom
  feature is not partially applied.
- Compare title-idle and gameplay frame pacing with
  `disable_title_demos` off and on. Reject or replace the raw instruction patch
  with a registered behavior hook if dirty interpretation causes a material
  regression.
