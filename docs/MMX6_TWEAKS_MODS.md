# MMX6 Tweaks as PSXRecomp mods

MMX6 Tweaks profiles are stock-targeted `.psxmod` packages. They do not create
a new recomp variant, rebuild generated C, alter the original BIN, or require
the user to select an intermediate Tweaks image.

The converter intentionally does not redistribute the Tweaks payload database
or artwork. Supply your own extracted copy of acediez's patcher to the existing
`tools/tweaks_engine.py` flow, or have the reference patcher produce a BIN.

```powershell
python tools/tweaks_psxmod.py `
  --vanilla "mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin" `
  --patched-bin "mmx6-tweaks/My Tweaks Profile.bin" `
  --name "My X6 Tweaks" `
  --out "My-X6-Tweaks.psxmod"
```

For selections covered by the pure-Python parity engine:

```powershell
Set-Content my-tweaks.json '{"DashGlobal01":1,"BossGuardShell01":1}'
python tools/tweaks_psxmod.py `
  --vanilla "mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin" `
  --selection-file "my-tweaks.json" `
  --out "My-X6-Tweaks.psxmod"
```

Install the archive from the launcher's **Mods** view, enable it, keep the stock
USA v1.1 BIN/CUE selected, and press **Play**. The package is tied to the stock
image's SHA-256. The runtime verifies the VCDIFF payload, builds a private cache
under `mods/cache/<plan fingerprint>.bin`, verifies the result, and mounts it
internally. Changing an option produces a different fingerprint/cache.

This profile-package bridge supports every permutation without requiring every
permutation to be compiled into the executable. VCDIFF is used because Tweaks
can change disc geometry; representing that structural transform as hundreds
of thousands of sparse sector replacements would be wasteful.

For user-facing distribution, Tweaks should be represented as one structural
owner package with many options, not as one package per option. Mutually
exclusive choices such as US vs. Japanese title screen live inside that package
as dropdown values. Independent non-structural mods can still be separate
packages; the runtime rejects overlapping guarded writes and rejects more than
one active full-disc recipe after option resolution.
