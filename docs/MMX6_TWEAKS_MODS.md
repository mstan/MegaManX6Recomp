# MMX6 Tweaks as PSXRecomp mods

MMX6 Tweaks profiles are now boot-time `.psxmod` overlays. They do not create a
new recomp variant, rebuild generated C, or alter the original BIN.

The converter intentionally does not redistribute the Tweaks payload database
or artwork. Supply your own extracted copy of acediez's patcher to the existing
`tools/tweaks_engine.py` flow, or have the reference patcher produce a BIN.

```powershell
python tools/tweaks_psxmod.py `
  --vanilla "mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin" `
  --base-bin "mmx6-tweaks/MMX6 Tweaks Base.bin" `
  --patched-bin "mmx6-tweaks/My Tweaks Profile.bin" `
  --name "My X6 Tweaks" `
  --out "My-X6-Tweaks.psxmod"
```

For a BIN produced by the reference patcher, pass `--base-bin` pointing at the
matching unconfigured Tweaks xdelta base. The base and final image must have the
same geometry.

For selections covered by the pure-Python parity engine:

```powershell
Set-Content my-tweaks.json '{"DashGlobal01":1,"BossGuardShell01":1}'
python tools/tweaks_psxmod.py `
  --vanilla "mmx6-tweaks/Mega Man X6 (USA) (v1.1).bin" `
  --selection-file "my-tweaks.json" `
  --base-out "mmx6-tweaks/MMX6 Tweaks Base.bin" `
  --out "My-X6-Tweaks.psxmod"
```

The selection form produces two outputs:

- the common Tweaks xdelta base BIN, selected once as the runtime disc;
- a small `.psxmod` containing only this profile's sector changes relative to
  that base.

Install the archive from the launcher's **Mods** view, enable it, select the
generated base BIN as the disc, and press **Play**. The package is tied to that
base's SHA-256 and all changed sectors carry expected-byte guards. Two packages
that touch the same bytes are rejected instead of being applied in an undefined
order.

This profile-package bridge supports every permutation without requiring every
permutation to be compiled into the executable. The common xdelta base is
necessary because Tweaks expands the raw disc by 220 sectors; representing that
structural transform as hundreds of thousands of sparse sector replacements
would be wasteful. A later trusted X6 resolver can put the full option catalog
directly in the launcher; the package and runtime format do not need to change.
