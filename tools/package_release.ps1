param(
    [string]$Version = "v0.0.1-alpha",
    [string]$BuildDir = "build-release",
    # Where your accumulated overlay cache lives (the dir compile_overlays.py
    # writes to, per game.toml overlay_autocompile_cmd --out-dir). Bundled as a
    # head start; optional.
    [string]$CacheBuildDir = "build-modern"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildPath = Join-Path $Root $BuildDir
$StageRoot = Join-Path $Root "release-stage"
$Stage = Join-Path $StageRoot "MegaManX6Recomp-windows-x64"
$ZipPath = Join-Path $Root ("MegaManX6Recomp-{0}-windows-x64.zip" -f $Version)
$MingwBin = "C:\msys64\mingw64\bin"

$env:PATH = "$MingwBin;$env:PATH"

# Regenerate the game's C BEFORE building. The recompiler emits the widescreen
# sites (2D true-FOV + background streamer) at regen time; the runtime build
# below just compiles generated/*.c. A stale generated/ would ship without those.
$RecompDir = Resolve-Path (Join-Path $Root "..\psxrecomp\recompiler\build")
cmake --build $RecompDir --target psxrecomp-game -j $env:NUMBER_OF_PROCESSORS
& (Join-Path $RecompDir "psxrecomp-game.exe") --config (Join-Path $Root "game.toml")
if ($LASTEXITCODE -ne 0) { throw "game regen failed" }

cmake -S $Root -B $BuildPath -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=OFF -DPSX_LAUNCHER=ON
cmake --build $BuildPath -j $env:NUMBER_OF_PROCESSORS

if (Test-Path $StageRoot) {
    Remove-Item -Recurse -Force $StageRoot
}
New-Item -ItemType Directory -Force $Stage | Out-Null
New-Item -ItemType Directory -Force (Join-Path $Stage "saves") | Out-Null

Copy-Item (Join-Path $BuildPath "psx-runtime.exe") (Join-Path $Stage "MegaManX6Recomp.exe")
Copy-Item (Join-Path $Root "README.md") $Stage
Copy-Item (Join-Path $Root "LICENSE") $Stage
if (Test-Path (Join-Path $Root "RELEASE_NOTES.md")) {
    Copy-Item (Join-Path $Root "RELEASE_NOTES.md") $Stage
}

# Launcher assets (RML + fonts + images). The PSX_LAUNCHER build stages these
# next to the exe via a cmake POST_BUILD copy of the framework's launcher assets,
# then this repo's launcher_art/ is copied on top (MMX6 disc art). They live flat
# under $BuildPath (launcher.rml, fonts/, img/). A release without them shows a
# blank/broken launcher. Assert + copy.
$LauncherRml = Join-Path $BuildPath "launcher.rml"
if (-not (Test-Path $LauncherRml)) {
    throw "Launcher assets missing at $BuildPath (no launcher.rml) -- was the build configured with -DPSX_LAUNCHER=ON?"
}
Copy-Item $LauncherRml $Stage
foreach ($dir in @("fonts","img")) {
    $src = Join-Path $BuildPath $dir
    if (-not (Test-Path $src)) { throw "Launcher asset dir missing: $src" }
    Copy-Item -Recurse -Force $src (Join-Path $Stage $dir)
}
$fontCount = (Get-ChildItem (Join-Path $Stage "fonts") -Filter *.ttf -ErrorAction SilentlyContinue).Count
$imgCount  = (Get-ChildItem (Join-Path $Stage "img") -Filter *.png -ErrorAction SilentlyContinue).Count
Write-Host "Bundled launcher assets: launcher.rml + $fontCount font(s) + $imgCount image(s)"

# Player-facing game.toml: same effective runtime settings as the dev config,
# minus dev-only sections ([recompiler] inputs beyond the required block, the
# overlay autocompile command that needs a local python+gcc toolchain, and the
# [audit] block). Players can edit the [runtime]/[video] sections post-install.
@"
[game]
name = "Mega Man X6"
id = "SLUS-01395"
exe = "mmx6/SLUS_013.95"
disc = "mmx6/Mega Man X6 (USA) (v1.1).cue"
load_address = "0x80010000"
entry_pc = "0x80054AD8"
text_size = "0x0007F000"
stack_base = "0x801FFFF0"

# Required block; used only by the developer recompiler tool, not at runtime.
[recompiler]
seeds = "seeds/ghidra_funcs.txt"
out_dir = "generated"

# ---- Player-adjustable options ------------------------------------------
# Edit, save, and restart MegaManX6Recomp.exe to apply.
[runtime]
window_title = "Mega Man X6 Recompiled"
memcard_dir = "saves"

# Disc read speed. "1x" is authentic PlayStation timing and is the safe default:
# speeding up the emulated CD device changes how many frames pass between the
# game's internal steps, which desyncs streamed audio and (for MMX6) wedges the
# boot. Fast loads instead come from turbo_loads below (which fast-forwards the
# whole machine during a load, preserving timing).
disc_speed = "1x"

# Skip the PlayStation BIOS boot logos (true) or watch them (false).
fast_boot  = false

# Turbo loads: while a load is in progress, run the machine at full host speed so
# loading finishes much faster, with all game timing preserved. Audio plays
# through normally. On by default. Toggleable in the launcher (Settings -> Turbo
# loads).
turbo_loads = true

# Overlay cache: keeps converted native code for game areas in the cache folder,
# and records newly visited areas into overlay_captures.json so your own cache
# grows as you play. Keep that file private - it contains game code from your
# disc (see README).
overlay_cache = true

# ---- Visual quality -----------------------------------------------------
[video]
# supersampling: render at this multiple of native resolution and downsample,
# for higher detail and anti-aliased edges. 1 = native PSX look, 2 = recommended,
# 3-4 = sharper (needs a faster CPU to hold full speed).
supersampling = 2
# antialiasing: smooth (linear) scaling to the window. false = sharp pixels.
antialiasing  = true
# texture_filtering: "nearest" = native PSX look; "bilinear" = smooths textures.
texture_filtering = "nearest"
# renderer: "opengl" = hardware GPU renderer (default). "software" = CPU renderer
# (automatic fallback if the GPU renderer can't start). Also set in the launcher.
renderer = "opengl"
# auto_skip_fmv: skip full-motion videos (e.g. the X-vs-Zero opening). When on, a
# video is skipped the instant it starts. On by default for MMX6; toggleable in
# the launcher (Settings -> "Skip FMVs").
auto_skip_fmv = true
# aspect_ratio: "4:3" (native, default) or "16:9" (EXPERIMENTAL widescreen). Also
# toggleable in the launcher (Settings -> Widescreen), which overrides this.
aspect_ratio = "4:3"

# ---- Controller ---------------------------------------------------------
# default_analog: MMX6 will not poll buttons until it detects an analog pad, so
# present a DualShock by default. Per-player toggle in the launcher. deadzone:
# analog stick dead-band (0..32767; ~12000 = 37%), also adjustable in the launcher.
[controller]
default_analog = true
deadzone = 12000
# MMX6 requires a DualShock, so the launcher hides the "Hybrid" pad mode and
# offers only Analog / D-Pad.
allow_hybrid = false

# ---- Widescreen (experimental 16:9, 2D engine) --------------------------
# full_2d treats every in-game frame as gameplay so the wide present path engages
# (MMX6 never emits the 3D sprite-tag the gameplay detector keys on). The bg2d
# hooks widen the per-layer 2D background renderer for a true wider field of view.
# All inert at 4:3. Addresses are specific to MMX6 (USA, v1.1, SLUS-01395) and
# must match the build the cache was made for.
[widescreen]
full_2d = true

[widescreen.bg2d]
count_site        = "0x800271d4"
startcol_site     = "0x80027188"
startx_site       = "0x800271a0"
stream_left_site  = "0x80027424"
stream_right_site = "0x80027444"
bufbase_site      = "0x80026dc4"
cap_site          = "0x80027278"
"@ | Set-Content -Encoding ASCII (Join-Path $Stage "game.toml")

# Prebuilt overlay cache: native code for the game areas contributed so far.
# The cache is namespaced per backend/arch/codegen-version:
#   gcc/<arch-abi>/cg<N>/<entry8>_<crc8>.dll (+ .ranges)
# and the loader scans it by that exact path, so the subtree must be preserved.
# Ship .dll + .ranges only (skip the _patched.c intermediates and the reserved
# sljit/ namespace, which has no on-disk blobs).
$CacheSrc = Join-Path $Root "$CacheBuildDir/cache/SLUS-01395"
if (Test-Path $CacheSrc) {
    $CacheDst = Join-Path $Stage "cache/SLUS-01395"
    $cacheFiles = Get-ChildItem $CacheSrc -Recurse -File -Include *.dll,*.ranges |
        Where-Object { $_.FullName -notmatch '[\\/]sljit[\\/]' }
    foreach ($f in $cacheFiles) {
        $rel  = $f.FullName.Substring($CacheSrc.Length).TrimStart('\','/')
        $dest = Join-Path $CacheDst $rel
        New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
        Copy-Item $f.FullName $dest
    }
    $dllCount = (Get-ChildItem $CacheDst -Recurse -Filter *.dll).Count
    Write-Host "Bundled overlay cache: $dllCount native overlay DLL(s)"
} else {
    Write-Warning "No overlay cache found at $CacheSrc - releasing without bundled cache"
}

# The Release build is statically linked (PSX_STATIC_RUNTIME defaults ON for
# MinGW Release), so the exe imports ONLY Windows system DLLs -- nothing to
# bundle. Assert self-containment rather than trust it (mismatched side-by-side
# DLLs were the cause of the 0xc000007b launch crash on other projects).
$objdump = Join-Path $MingwBin "objdump.exe"
$imports = & $objdump -p (Join-Path $Stage "MegaManX6Recomp.exe") |
    Select-String "DLL Name: (.+)" | ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() }
$systemDlls = @("kernel32.dll","user32.dll","gdi32.dll","shell32.dll","msvcrt.dll",
                "advapi32.dll","ws2_32.dll","comdlg32.dll","dbghelp.dll","ole32.dll",
                "oleaut32.dll","winmm.dll","imm32.dll","version.dll","setupapi.dll",
                "dinput8.dll","rpcrt4.dll","hid.dll","cfgmgr32.dll","opengl32.dll")
$nonSystem = $imports | Where-Object { $systemDlls -notcontains $_.ToLower() }
if ($nonSystem) {
    throw "Release exe is NOT self-contained -- imports non-system DLL(s): $($nonSystem -join ', ')"
}
Write-Host "Verified self-contained: imports only system DLLs ($($imports.Count) total)"

@"
; PSXRecomp input mapping. PSX buttons are active when any listed source is pressed.
; Sources use SDL/Xbox names: a,b,x,y,back,start,leftshoulder,rightshoulder,
; lefttrigger,righttrigger,dpup,dpdown,dpleft,dpright,leftx-/leftx+/lefty-/lefty+.

[controller]
enabled = true
device = 0
deadzone = 12000

[mapping]
up = dpup,lefty-
down = dpdown,lefty+
left = dpleft,leftx-
right = dpright,leftx+
cross = a
circle = b
square = x
triangle = y
l1 = leftshoulder
r1 = rightshoulder
l2 = lefttrigger
r2 = righttrigger
start = start
select = back
"@ | Set-Content -Encoding ASCII (Join-Path $Stage "input.ini")

@"
MegaManX6Recomp $Version

Mega Man X6 boots from the PlayStation BIOS and plays - through the opening, into
stages, with working controller input and memory-card save/load, and no known
crashes. It has not yet been verified all the way to the end, so treat this first
release as a very playable preview rather than a certified full playthrough.

This package does not include the Mega Man X6 disc, the PlayStation BIOS, save
data, or any game assets - you supply those from your own collection, and
MegaManX6Recomp asks for them one at a time (each dialog says which one it
wants). The executable and the cache folder contain statically recompiled
(machine-translated) builds of the game's code, the same distribution model
used by other static recompilation projects such as N64: Recompiled.

First launch:
1. Run MegaManX6Recomp.exe. A launcher window opens.
2. In the launcher, set your PlayStation BIOS: select your legally obtained
   SCPH1001.BIN (a 512 KB file dumped from your own console).
3. Set the game disc: select your legally obtained Mega Man X6 (USA) (v1.1,
   SLUS-01395) disc image.
4. Adjust any options you like (renderer, supersampling, screen look,
   controller), then press Launch. Your choices are remembered next time.

Disc image formats:
- .cue + .bin (preferred - pick the .cue)
- .bin
Do NOT convert to a 2048-byte "cooked" .iso - it discards the XA sectors MMX6
streams its FMV/audio from.

The selected BIOS path is saved in bios.cfg and the selected disc path is saved
in disc.cfg next to the executable. Delete those files to pick different files.

Options such as turbo loads, FMV skip, widescreen, and disc speed can be changed
in the launcher Settings or in game.toml ([runtime]/[video]) with any text editor.

The cache folder contains pre-converted native code for game areas covered so
far; those run at full speed from your first visit. As you play, newly visited
areas are recorded into overlay_captures.json and your local cache grows
automatically. Do NOT post overlay_captures.json publicly - it contains
snapshots of the game's own code read from your disc. See README.md for details.

Keyboard and Xbox-style controller defaults are documented in README.md.
Controller mappings are configurable in input.ini.

Memory cards are stored in the saves directory; save and load work with standard
PS1 .mcd images.
"@ | Set-Content -Encoding ASCII (Join-Path $Stage "START_HERE.txt")

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -Force

Write-Host "Wrote $ZipPath"
