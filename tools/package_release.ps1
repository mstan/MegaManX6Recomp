param(
    # Empty => read packaging/release/VERSION, the single source of truth that
    # tools/package_appimage.sh already uses. Do NOT reintroduce a hardcoded
    # default: this used to say "v1.0.5", so bumping VERSION for a release
    # silently produced a Windows zip named after the PREVIOUS version while the
    # AppImage picked up the new one. Per-platform version drift is exactly the
    # release-packager defect class this repo has been bitten by before.
    [string]$Version = "",
    [string]$BuildDir = "build-release",
    # Ship without a bundled overlay cache; off by default.
    [switch]$AllowNoCache,
    # Where your accumulated overlay cache lives (the dir compile_overlays.py
    # writes to, per game.toml overlay_autocompile_cmd --out-dir). Bundled as a
    # head start.
    [string]$CacheBuildDir = "build-stable",
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
    & (Join-Path $RecompDir "psxrecomp-game.exe") --config (Join-Path $Root "game.toml")
    if ($LASTEXITCODE -ne 0) { throw "game regen failed" }
} else {
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
$ModsSrc = Join-Path $BuildPath "mods"
if (Test-Path (Join-Path $ModsSrc "packages")) {
    Copy-Item -Recurse -Force $ModsSrc (Join-Path $Stage "mods")
    $preloadedCount = (Get-ChildItem (Join-Path $Stage "mods/packages") -Directory).Count
    Write-Host "Bundled mod catalog: $preloadedCount package family/families"
    if ($preloadedCount -lt 16) {
        throw ("Expected the game's 15 packages plus the framework's " +
               "loading-speed mods, found $preloadedCount. The framework " +
               "catalog is missing from $ModsSrc.")
    }
} else {
    throw "No mod catalog staged at $ModsSrc - build the runtime first"
}
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

# Prebuilt overlay cache: native code for the game areas contributed so far.
# The cache is namespaced per backend/arch/codegen-version:
#   gcc/<arch-abi>/cg<N>/<entry8>_<crc8>.dll (+ .ranges)
# and the loader scans it by that exact path, so the subtree must be preserved.
# Ship .dll + .ranges only (skip the _patched.c intermediates and the reserved
# sljit/ namespace, which has no on-disk blobs), and ONLY the dir matching THIS
# build's codegen tag -- a stale-hash dir is dead weight the runtime never loads.
$RecompTools = Resolve-Path (Join-Path $FrameworkRoot "tools")
$RecompInc   = Resolve-Path (Join-Path $FrameworkRoot "runtime\include")
$tagScript = Join-Path $env:TEMP ("psx_cgtag_{0}.py" -f $PID)
@"
import importlib.util
s = importlib.util.spec_from_file_location('co', r'$RecompTools\compile_overlays.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
inc = r'$RecompInc'
print('cg%d_%08x_gc%08x' % (
    m.codegen_ver(inc),
    m.codegen_hash(inc),
    m.overlay_config_hash(
        r'$(Join-Path $RecompDir "psxrecomp-game.exe")',
        r'$(Join-Path $Stage "game.toml")')))
"@ | Set-Content -Encoding ASCII $tagScript
$CgTag = (& python $tagScript).Trim()
Remove-Item -Force $tagScript
Write-Host "Release codegen tag: $CgTag (only this cache namespace is shipped)"
$CacheSrc = Join-Path $Root "$CacheBuildDir/cache/SLUS-01395"
if (Test-Path $CacheSrc) {
    # NORMALISE before any Substring(): $CacheBuildDir may legitimately contain
    # '..' (a cache built outside the repo), and Join-Path does NOT collapse it.
    # The unresolved string is then LONGER than the real prefix of $f.FullName,
    # so Substring($CacheSrc.Length) ate part of the subtree and produced
    # cache/SLUS-01395/9a4721_gc4f033776/... instead of
    # cache/SLUS-01395/gcc/win-x64/cg9_0e9a4721_gc4f033776/... . The loader
    # scans by that exact path, so every shard silently failed to load while
    # the packager still reported a healthy shard count.
    $CacheSrc = (Resolve-Path $CacheSrc).Path
    $CacheDst = Join-Path $Stage "cache/SLUS-01395"
    $cacheFiles = Get-ChildItem $CacheSrc -Recurse -File -Include *.dll,*.ranges |
        Where-Object { $_.FullName -notmatch '[\\/]sljit[\\/]' -and $_.FullName -match "[\\/]$CgTag[\\/]" }
    foreach ($f in $cacheFiles) {
        $rel  = $f.FullName.Substring($CacheSrc.Length).TrimStart('\','/')
        $dest = Join-Path $CacheDst $rel
        New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
        Copy-Item $f.FullName $dest
    }
    $dllCount = @($cacheFiles | Where-Object { $_.Extension -eq ".dll" }).Count
    Write-Host "Bundled overlay cache: $dllCount native overlay DLL(s)"

    # Assert the STAGED LAYOUT, not just the copied count. A shard the loader
    # cannot find is worth exactly as much as no shard at all, and the count
    # above cannot tell the difference.
    if ($dllCount -gt 0) {
        $staged = @(Get-ChildItem (Join-Path $CacheDst "gcc") -Recurse -File -Filter *.dll -ErrorAction SilentlyContinue |
                    Where-Object { $_.FullName -match "[\\/]$CgTag[\\/]" })
        if ($staged.Count -ne $dllCount) {
            throw ("Staged overlay cache layout is wrong: expected $dllCount shard(s) under " +
                   "cache/SLUS-01395/gcc/<arch-abi>/$CgTag/ but found $($staged.Count). " +
                   "The loader scans that exact path, so the bundled cache would never load.")
        }
    }
    if ($dllCount -eq 0 -and -not $AllowNoCache) {
        # The directory existing is not enough: the tag folds in a hash of the
        # PACKAGED game.toml, so a cache built against any other config lands
        # under a different tag and matches nothing. Fail instead of quietly
        # shipping a package whose first session runs entirely interpreted.
        throw ("Overlay cache at $CacheSrc has no shards for tag $CgTag. " +
               "Rebuild it with compile_overlays.py using the PACKAGED " +
               "game.toml (release-stage/*/game.toml), or pass -AllowNoCache.")
    }
} else {
    if ($AllowNoCache) {
        Write-Warning "No overlay cache at $CacheSrc - shipping without one because -AllowNoCache was given"
    } else {
        # A cache-less package makes every player's first session run overlays
        # interpreted. This used to be a warning that scrolled past, while the
        # tag computed above had drifted from the one the runtime actually uses
        # (it was missing the overlay-config hash), so the match never hit.
        throw ("No overlay cache found at $CacheSrc for tag $CgTag. Build one " +
               "with compile_overlays.py against the PACKAGED game.toml, or " +
               "pass -AllowNoCache to ship without one.")
    }
}

# ---- Self-contained overlay toolchain (tcc tier) -------------------------
# A player box has no gcc AND no Python, so overlay_backend=auto resolves to tcc:
# the runtime fills overlay gaps the shipped gcc cache misses by spawning this
# bundled, fully self-contained toolchain. The runtime constructs the command
# from <exe>/overlay_toolchain/ (see main.cpp): embedded Python + TinyCC + the
# recompiler + compile_overlays.py + the runtime headers. Every exe here must be
# self-contained (embedded python + prebuilt tcc are; the recompiler needs its
# mingw runtime DLLs bundled beside it).
$Toolchain = Join-Path $Stage "overlay_toolchain"
New-Item -ItemType Directory -Force $Toolchain | Out-Null
$DlCache = Join-Path $Root "tools/_toolchain_cache"
New-Item -ItemType Directory -Force $DlCache | Out-Null

# Pin every fetched archive by SHA256 and verify on EVERY use, including cache
# hits. Without this a release trusts whatever the mirror served that day, and a
# corrupted/tampered file already in tools/_toolchain_cache is reused forever
# because the old code only checked Test-Path. Mirrors (python.org, savannah)
# both 502 periodically, so transient failures retry instead of losing a build.
function Get-PinnedArchive {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$Sha256,
        [Parameter(Mandatory)][string]$Destination,
        [int]$Retries = 4
    )
    $name = Split-Path -Leaf $Destination
    if (Test-Path -LiteralPath $Destination) {
        $have = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLower()
        if ($have -eq $Sha256.ToLower()) { return $Destination }
        Write-Warning "$name in the download cache has SHA256 $have (expected $Sha256); refetching"
        Remove-Item -LiteralPath $Destination -Force
    }
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            $tmp = "$Destination.tmp"
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
            Invoke-WebRequest -Uri $Uri -OutFile $tmp -UseBasicParsing
            $got = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLower()
            if ($got -ne $Sha256.ToLower()) {
                Remove-Item -LiteralPath $tmp -Force
                throw "SHA256 mismatch for $name : got $got, expected $Sha256"
            }
            Move-Item -LiteralPath $tmp -Destination $Destination -Force
            return $Destination
        } catch {
            if ($attempt -eq $Retries) {
                throw ("Failed to fetch $name after $Retries attempts: $($_.Exception.Message). " +
                       "Place a verified copy at $Destination and re-run.")
            }
            $delay = [Math]::Min(30, [Math]::Pow(2, $attempt))
            Write-Warning "$name fetch attempt $attempt failed ($($_.Exception.Message)); retrying in ${delay}s"
            Start-Sleep -Seconds $delay
        }
    }
}

# Embedded Python (fixed version; downloaded once + cached)
$PyVer = "3.13.1"
$PyZip = Get-PinnedArchive `
    -Uri "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" `
    -Sha256 "7b7923ff0183a8b8fca90f6047184b419b108cb437f75fc1c002f9d2f8bcec16" `
    -Destination (Join-Path $DlCache "python-$PyVer-embed-amd64.zip")
Expand-Archive -Path $PyZip -DestinationPath (Join-Path $Toolchain "python") -Force

# TinyCC prebuilt win64 (fixed version; downloaded once + cached). The zip has a
# top-level tcc/ dir (tcc.exe + libtcc.dll + include/ + lib/) — ship it whole.
$TccZip = Get-PinnedArchive `
    -Uri "https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip" `
    -Sha256 "34a721949a2583fdff725312da092fa0f5f1f284b702e6f811c6954714faabb2" `
    -Destination (Join-Path $DlCache "tcc-0.9.27-win64-bin.zip")
$TccTmp = Join-Path $DlCache "tcc_extract"
if (Test-Path $TccTmp) { Remove-Item -Recurse -Force $TccTmp }
Expand-Archive -Path $TccZip -DestinationPath $TccTmp -Force
Copy-Item -Recurse -Force (Join-Path $TccTmp "tcc") (Join-Path $Toolchain "tcc")

# Recompiler (built above) + its mingw runtime DLLs (NOT statically linked) +
# compile_overlays.py + the runtime headers.
Copy-Item (Join-Path $RecompDir "psxrecomp-game.exe") $Toolchain
foreach ($d in @("libgcc_s_seh-1.dll","libstdc++-6.dll","libwinpthread-1.dll")) {
    Copy-Item (Join-Path $MingwBin $d) $Toolchain
}
Copy-Item (Resolve-Path (Join-Path $FrameworkRoot "tools\compile_overlays.py")) $Toolchain
$ToolInc = Join-Path $Toolchain "include"
New-Item -ItemType Directory -Force $ToolInc | Out-Null
Copy-Item (Join-Path (Resolve-Path (Join-Path $FrameworkRoot "runtime\include")) "*.h") $ToolInc
$tcMB = "{0:N0}" -f ((Get-ChildItem $Toolchain -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Bundled overlay toolchain (embedded python + tcc + recompiler): ~$tcMB MB"

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
