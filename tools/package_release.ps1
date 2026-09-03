param(
    # Empty => read packaging/release/VERSION, the single source of truth that
    # tools/package_appimage.sh already uses. Do NOT reintroduce a hardcoded
    # default: this used to say "v1.0.5", so bumping VERSION for a release
    # silently produced a Windows zip named after the PREVIOUS version while the
    # AppImage picked up the new one. Per-platform version drift is exactly the
    # release-packager defect class this repo has been bitten by before.
    [string]$Version = "",
    [string]$BuildDir = "build-release",
    # Where your accumulated overlay cache lives (the dir compile_overlays.py
    # writes to, per game.toml overlay_autocompile_cmd --out-dir). Bundled as a
    # head start.
    [string]$CacheBuildDir = "build-release",
    [switch]$SkipRegen
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

if ([string]::IsNullOrWhiteSpace($Version)) {
    $VersionFile = Join-Path $Root "packaging/release/VERSION"
    if (-not (Test-Path $VersionFile)) {
        throw "no -Version given and $VersionFile is missing"
    }
    $Version = (Get-Content -Raw $VersionFile).Trim()
    if ([string]::IsNullOrWhiteSpace($Version)) {
        throw "$VersionFile is empty"
    }
    Write-Host "Release version from packaging/release/VERSION: $Version"
}
$BuildPath = Join-Path $Root $BuildDir
$StageRoot = Join-Path $Root "release-stage"
$Stage = Join-Path $StageRoot "MegaManX6Recomp-windows-x64"
$ZipPath = Join-Path $Root ("MegaManX6Recomp-{0}-windows-x64.zip" -f $Version)
$MingwBin = "C:\msys64\mingw64\bin"

$env:PATH = "$MingwBin;$env:PATH"

# Regenerate the game's C BEFORE building. The recompiler emits the widescreen
# sites (2D true-FOV + background streamer) at regen time; the runtime build
# below just compiles generated/*.c. A stale generated/ would ship without those.
# cmake writes benign warnings (e.g. freetype's cmake_minimum_required
# deprecation) to STDERR. Under $ErrorActionPreference='Stop', PowerShell 5.1
# promotes a native command's stderr write to a TERMINATING error, aborting the
# release for a non-error. Run the native cmake invocations with the preference
# relaxed and gate on the real signal -- $LASTEXITCODE -- instead.
function Invoke-Native {
    param([scriptblock]$Cmd, [string]$What)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Cmd 2>&1 | Out-Host
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw "$What failed (exit $code)" }
}

function Get-TomlScalar {
    param(
        [Parameter(Mandatory)][string]$GameToml,
        [Parameter(Mandatory)][string]$Table,
        [Parameter(Mandatory)][string]$Key
    )
    $section = ""
    foreach ($raw in (Get-Content -LiteralPath $GameToml)) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        if ($line -match '^\[\[?([^\]]+)\]\]?$') { $section = $Matches[1].Trim(); continue }
        if ($section -ne $Table) { continue }
        if ($line -match ('^' + [regex]::Escape($Key) + '\s*=\s*(.+?)\s*(?:#.*)?$')) {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Ensure-BiosBackends {
    param([Parameter(Mandatory)][string]$FrameworkRoot)
    $stems = @()
    if (Test-Path -LiteralPath (Join-Path $FrameworkRoot "bios\OpenBIOS.toml")) {
        $stems += ,@("OpenBIOS", "bios/OpenBIOS.toml")
    }
    if (Test-Path -LiteralPath (Join-Path $FrameworkRoot "bios\SCPH1001.BIN")) {
        $stems += ,@("SCPH1001", "bios/SCPH1001.toml")
    }
    if (-not $stems) { throw "No BIOS profile available under $FrameworkRoot\bios" }

    $missing = @($stems | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $FrameworkRoot ("generated\{0}_dispatch.c" -f $_[0])))
    })
    if (-not $missing) { return }

    $bash = $null
    foreach ($cand in @("C:\msys64\usr\bin\bash.exe", "C:\msys64\mingw64\bin\bash.exe")) {
        if (Test-Path -LiteralPath $cand) { $bash = $cand; break }
    }
    if (-not $bash) {
        throw ("Missing recompiled BIOS backend(s): {0}. Install MSYS2 or run " +
               "psxrecomp-v4/tools/regen_bios.sh manually." -f (($missing | ForEach-Object { $_[0] }) -join ', '))
    }

    $cygpath = Join-Path (Split-Path -Parent $bash) "cygpath.exe"
    $posixRoot = (& $cygpath -u $FrameworkRoot).Trim()
    $posixMingw = (& $cygpath -u $MingwBin).Trim()
    foreach ($stem in $missing) {
        Write-Host "Generating recompiled BIOS backend: $($stem[0])"
        $biosShellCmd = "export PATH='$posixMingw':`$PATH; cd '$posixRoot' && " +
                        "PSXRECOMP_BIOS_BUILD=recompiler/build tools/regen_bios.sh --config $($stem[1])"
        Invoke-Native { & $bash -c $biosShellCmd } "regen_bios ($($stem[0]))"
    }
}
# The executable is generated from the developer config but runs against the
# player config. Keep widescreen codegen and runtime gates identical.
Invoke-Native {
    py -3 (Join-Path $Root "tools\check_release_config.py")
} "release config parity check"

$FrameworkRoot = Join-Path $Root "psxrecomp-v4"
if (-not (Test-Path $FrameworkRoot)) {
    $FrameworkRoot = Join-Path $Root "..\psxrecomp"
}
$RecompDir = Resolve-Path (Join-Path $FrameworkRoot "recompiler\build")
if (-not $SkipRegen) {
    Invoke-Native { cmake --build $RecompDir --target psxrecomp-game -j $env:NUMBER_OF_PROCESSORS } "recompiler build"
    Ensure-BiosBackends -FrameworkRoot $FrameworkRoot
    & (Join-Path $RecompDir "psxrecomp-game.exe") --config (Join-Path $Root "game.toml")
    if ($LASTEXITCODE -ne 0) { throw "game regen failed" }
} else {
    Ensure-BiosBackends -FrameworkRoot $FrameworkRoot
    Write-Host "Skipping game C regeneration; packaging the existing generated sources"
}

Invoke-Native { cmake -S $Root -B $BuildPath -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=OFF } "cmake configure"
Invoke-Native { cmake --build $BuildPath -j $env:NUMBER_OF_PROCESSORS } "cmake build"

if (Test-Path $StageRoot) {
    Remove-Item -Recurse -Force $StageRoot
}
New-Item -ItemType Directory -Force $Stage | Out-Null
New-Item -ItemType Directory -Force (Join-Path $Stage "saves") | Out-Null

# Dev exe is mmx6-runtime.exe (per-game EXE_NAME); accept the pre-rename name too.
$DevExe = Join-Path $BuildPath "mmx6-runtime.exe"
if (-not (Test-Path $DevExe)) { $DevExe = Join-Path $BuildPath "psx-runtime.exe" }
Copy-Item $DevExe (Join-Path $Stage "MegaManX6Recomp.exe")
Copy-Item (Join-Path $Root "README.md") $Stage
Copy-Item (Join-Path $Root "LICENSE") $Stage
# Stage the mod catalog from the BUILD OUTPUT, not from mods/preloaded. The
# build output is the authoritative catalog: it is this repo's own packages
# PLUS the ones the framework stages for every game (loading speed). Copying
# the source tree instead silently drops the framework's mods from the
# release, so players get a Mods page missing entries the dev build shows.
#
# Routed through the framework's shared Add-ModCatalog. The hand-written block
# that used to live here was wrong twice over:
#
#   * it globbed mods/packages, the PRE-SPLIT layout. Framework 4cc04be3 moved
#     staged build output to mods/bundled and nothing in this repo followed, so
#     at framework master this threw "No mod catalog staged ... build the
#     runtime first" -- a message that blames the build for a layout rename
#     (bead beads-eio.3.101);
#   * it asserted "at least 16 package families". A count describes only one
#     side of a catalog two repositories contribute to, so it goes stale the
#     moment either side gains a mod. The identical assertion made Tomba 2
#     unreleasable on 2026-09-01 when the framework gained a fifth builtin.
#
# Add-ModCatalog asserts the invariant instead: every package the SOURCES
# define -- this repo's mods/preloaded/packages and the framework's
# mods/builtin/packages -- must survive into the staged catalog. It also strips
# the two things under mods/ that belong to this machine (installed/ and
# state.toml) rather than leaving them to be noticed later.
. (Join-Path $FrameworkRoot "tools\release_overlay_stage.ps1")
Add-ModCatalog -BuildPath $BuildPath -Stage $Stage `
               -GameModSource (Join-Path $Root "mods\preloaded") `
               -FrameworkModSource (Join-Path $FrameworkRoot "mods\builtin") | Out-Null
$BundledBiosSrc = Join-Path $BuildPath "bios"
if (!(Test-Path (Join-Path $BundledBiosSrc "openbios.bin")) -or
    (Get-Item (Join-Path $BundledBiosSrc "openbios.bin")).Length -ne 524288 -or
    !(Test-Path (Join-Path $BundledBiosSrc "OpenBIOS.LICENSE"))) {
    throw "Runtime build did not stage OpenBIOS and its MIT notice"
}
$BundledBiosDst = Join-Path $Stage "bios"
New-Item -ItemType Directory -Force $BundledBiosDst | Out-Null
Copy-Item (Join-Path $BundledBiosSrc "openbios.bin") $BundledBiosDst
Copy-Item (Join-Path $BundledBiosSrc "OpenBIOS.LICENSE") $BundledBiosDst
if (Test-Path (Join-Path $Root "RELEASE_NOTES.md")) {
    Copy-Item (Join-Path $Root "RELEASE_NOTES.md") $Stage
}

# Launcher assets: this build ships the shared recomp-ui Dear ImGui launcher
# (RECOMP_LAUNCHER; see main.cpp + recomp-ui/recomp_ui.cmake), which loads from
# <exe>/assets/ (fonts + img TGAs, including this repo's boxart baked in by
# recomp_target_launcher_ui's POST_BUILD).
$AssetsSrc = Join-Path $BuildPath "assets"
if (-not (Test-Path (Join-Path $AssetsSrc "img"))) {
    throw "recomp-ui launcher assets missing at $AssetsSrc -- was the recomp-ui launcher built (recomp-ui junction present)?"
}
Copy-Item -Recurse -Force $AssetsSrc (Join-Path $Stage "assets")
$fontCount = (Get-ChildItem (Join-Path $Stage "assets/fonts") -Filter *.ttf -ErrorAction SilentlyContinue).Count
$imgCount  = (Get-ChildItem (Join-Path $Stage "assets/img")   -Filter *.tga -ErrorAction SilentlyContinue).Count
Write-Host "Bundled recomp-ui launcher assets: $fontCount font(s) + $imgCount image(s)"

# Player-facing game.toml: same effective runtime settings as the dev config,
# minus dev-only sections ([recompiler] inputs beyond the required block, the
# gcc overlay-autocompile command, and the [audit] block). overlay_backend is
# left at the default "auto": with no gcc toolchain on a player box it resolves
# to tcc, which fills overlay gaps via the bundled overlay_toolchain/ (no system
# python or gcc needed). Players can edit [runtime]/[video] post-install.
# Player-facing game.toml comes from packaging/release/game.toml, the same
# file tools/package_appimage.sh ships. Generating it here instead let the
# two platforms drift: they produced different configs, hence different
# overlay codegen tags, so a cache built for one did not load on the other.
Copy-Item -Force (Join-Path $Root "packaging/release/game.toml") (Join-Path $Stage "game.toml")

# Prebuilt overlay cache + self-contained overlay toolchain, both staged by the
# shared framework implementation. The cache-required decision is read from the
# STAGED game.toml, since that file is folded into the tag and is the contract
# the released executable actually loads.
$RecompTools = (Resolve-Path (Join-Path $FrameworkRoot "tools")).Path
$RecompInc   = (Resolve-Path (Join-Path $FrameworkRoot "runtime\include")).Path
$StagedGameToml = Join-Path $Stage "game.toml"
$CacheGameId = Get-TomlScalar -GameToml $StagedGameToml -Table "game" -Key "id"
if (-not $CacheGameId) { throw "Could not read [game] id from $StagedGameToml" }

$CacheSrcRoot = if ([System.IO.Path]::IsPathRooted($CacheBuildDir)) {
    $CacheBuildDir
} else {
    Join-Path $Root $CacheBuildDir
}
foreach ($p in @($CacheSrcRoot, (Resolve-Path -LiteralPath $CacheSrcRoot -ErrorAction SilentlyContinue).Path)) {
    if ($p -and $p -match 'QUARANTINE') { throw "Refusing quarantined overlay cache source: $p" }
}
$CacheSrcRoot = Join-Path $CacheSrcRoot "cache"

$CgTag = Get-OverlayCgTag -RecompTools $RecompTools -RecompInc $RecompInc `
                          -GameExe (Join-Path $RecompDir "psxrecomp-game.exe") `
                          -GameToml $StagedGameToml `
                          -BuildPath $BuildPath -RuntimeTarget "psx-runtime"
Write-Host "Release codegen tag: $CgTag (only this cache namespace is shipped)"

$OverlayCacheDeclared =
    ((Get-TomlScalar -GameToml $StagedGameToml -Table "runtime" -Key "overlay_cache") -eq "true")
if ($OverlayCacheDeclared) {
    Write-Host "Staged game.toml declares overlay_cache = true; a shard cache is required"
    Add-OverlayCache -GameId $CacheGameId -CacheSrcRoot $CacheSrcRoot `
                     -Stage $Stage -CgTag $CgTag | Out-Null
} else {
    Write-Host "Staged game.toml does not declare overlay_cache; staging no shard cache"
}
Add-OverlayToolchain -Stage $Stage -RecompDir $RecompDir -RecompTools $RecompTools `
                     -RecompInc $RecompInc -MingwBin $MingwBin `
                     -DlCache (Join-Path $Root "tools\_toolchain_cache") | Out-Null
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

Mega Man X6 boots from the PlayStation BIOS and plays through the opening and
stages with working controller input and memory-card save/load. End-to-end
completion has not yet been recertified for this build, so please report any
regressions you encounter.

This package includes the MIT-licensed OpenBIOS from PCSX-Redux and its notice
in bios/OpenBIOS.LICENSE. It does not include the Mega Man X6 disc, a retail
PlayStation BIOS, save data, or game assets.

First launch:
1. Run MegaManX6Recomp.exe. A launcher window opens.
2. OpenBIOS is selected automatically. You may optionally select your legally
   obtained SCPH1001.BIN in the BIOS row.
3. Set the game disc: select your legally obtained Mega Man X6 (USA) (v1.1,
   SLUS-01395) disc image.
4. Adjust any options you like (renderer, supersampling, screen look,
   controller), then press Launch. Your choices are remembered next time.

Disc image formats:
- .cue + .bin (preferred - pick the .cue)
- .bin
Do NOT convert to a 2048-byte "cooked" .iso - it discards the XA sectors MMX6
streams its FMV/audio from.

An optional retail BIOS choice and the selected disc path are saved next to the
executable. Clear the BIOS row to return to OpenBIOS.

Turbo loads, FMV skip, and disc speed can be changed in launcher Settings or in
game.toml. Widescreen, frame interpolation, and Mega Man X6 Tweaks options live
in the launcher's Mods view.

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
