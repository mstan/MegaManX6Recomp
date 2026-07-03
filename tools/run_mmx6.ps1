# run_mmx6.ps1 - autonomous launcher for the MMX6 recomp dev build.
# Bakes BIOS + disc paths so no interactive picker is ever needed and the
# space-containing .cue path is quoted as a single argument (PS 5.1 does NOT
# auto-quote -ArgumentList array elements -> the path splits at "Mega").
#
# Usage:  powershell -File tools\run_mmx6.ps1 [-BuildDir build-master]
param(
    [string]$BuildDir = "build-master",
    [switch]$NoLauncher   # boot straight into the game (skip the RmlUi launcher) for scripted/debug runs
)
$ErrorActionPreference = "Stop"
$root = "F:\Projects\psxrecomp\MegaManX6Recomp"
$exe  = Join-Path $root "$BuildDir\mmx6-runtime.exe"
# Older build dirs may predate the per-game exe rename (EXE_NAME "mmx6-runtime").
if (-not (Test-Path $exe)) { $exe = Join-Path $root "$BuildDir\psx-runtime.exe" }
$game = Join-Path $root "game.toml"
$bios = "F:\Projects\psxrecomp\psxrecomp\bios\SCPH1001.BIN"
$disc = Join-Path $root "mmx6\Mega Man X6 (USA) (v1.1).cue"

if (-not (Test-Path $exe))  { throw "exe not found: $exe" }
if (-not (Test-Path $bios)) { throw "bios not found: $bios" }
if (-not (Test-Path $disc)) { throw "disc not found: $disc" }

# Pre-seed the runtime's path cache so even a bare launch resolves correctly.
Set-Content -Path (Join-Path $root "$BuildDir\bios.cfg") -Value $bios -Encoding utf8 -NoNewline
Set-Content -Path (Join-Path $root "$BuildDir\disc.cfg") -Value $disc -Encoding utf8 -NoNewline

# Kill only THIS game's process name — sweeping the shared "psx-runtime" name
# kills every other game's dev instance (the reason for the per-game rename).
Get-Process mmx6-runtime -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 300

# Build a single arg string with explicit quotes around every path.
$argline = "--game `"$game`" --bios `"$bios`" --disc `"$disc`""
if ($NoLauncher) { $argline += " --no-launcher" }
$p = Start-Process -FilePath $exe -ArgumentList $argline -WorkingDirectory $root `
        -RedirectStandardError  (Join-Path $root "_mmx6_stderr.txt") `
        -RedirectStandardOutput (Join-Path $root "_mmx6_stdout.txt") -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited) {
    Write-Output "EXITED code=$($p.ExitCode)"
    Get-Content (Join-Path $root "_mmx6_stderr.txt") -ErrorAction SilentlyContinue
} else {
    Write-Output "RUNNING pid=$($p.Id) ($BuildDir)"
}
