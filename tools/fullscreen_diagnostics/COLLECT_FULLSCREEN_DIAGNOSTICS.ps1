param(
    [int]$Port = 4490
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-SafeVideoSettings {
    $settingsPath = Join-Path $scriptDir "settings.toml"
    $result = [ordered]@{
        file_present = Test-Path $settingsPath
    }
    if (-not $result.file_present) {
        return [pscustomobject]$result
    }

    # Deliberately collect display settings only. Do not include the BIOS,
    # disc, save, or controller sections because those can contain user paths.
    $allowed = @(
        "renderer", "supersampling", "window_width", "antialiasing",
        "texture_filtering", "crt_filter", "fullscreen",
        "frame_interpolation", "frame_interpolation_fps", "aspect_ratio"
    )
    $section = ""
    foreach ($line in Get-Content -LiteralPath $settingsPath) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') {
            $section = $Matches[1]
            continue
        }
        if ($section -ne "video") { continue }
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*(?:#.*)?$') {
            $key = $Matches[1]
            if ($allowed -contains $key) {
                $result[$key] = $Matches[2].Trim()
            }
        }
    }
    return [pscustomobject]$result
}

function Convert-CimObject {
    param($Object, [string[]]$Properties)
    if ($null -eq $Object) { return $null }
    $result = [ordered]@{}
    foreach ($property in $Properties) {
        $result[$property] = $Object.$property
    }
    return [pscustomobject]$result
}

function Invoke-FullscreenDiagnostic {
    param([int]$TcpPort)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        try {
            $connect = $client.ConnectAsync("127.0.0.1", $TcpPort)
            if (-not $connect.Wait(5000)) {
                throw "Timed out connecting to the game on localhost port $TcpPort."
            }
        }
        catch {
            $cause = $_.Exception.GetBaseException().Message
            throw "Could not connect to the game on localhost port ${TcpPort}: $cause"
        }
        if ($connect.IsFaulted) {
            throw $connect.Exception.GetBaseException()
        }

        $stream = $client.GetStream()
        $stream.ReadTimeout = 5000
        $stream.WriteTimeout = 5000
        $writer = New-Object System.IO.StreamWriter(
            $stream, (New-Object System.Text.UTF8Encoding($false)), 1024, $true)
        $writer.NewLine = "`n"
        $writer.WriteLine('{"cmd":"fullscreen_diag","id":1}')
        $writer.Flush()

        $reader = New-Object System.IO.StreamReader(
            $stream, (New-Object System.Text.UTF8Encoding($false)), $false, 4096, $true)
        $read = $reader.ReadLineAsync()
        if (-not $read.Wait(5000)) {
            throw "The game accepted the connection but did not return a diagnostic report."
        }
        $line = $read.Result
        if ([string]::IsNullOrWhiteSpace($line)) {
            throw "The game returned an empty diagnostic report."
        }
        return $line | ConvertFrom-Json
    }
    finally {
        $client.Dispose()
    }
}

try {
    Write-Host "Collecting MegaManX6Recomp fullscreen diagnostics..."
    $runtime = Invoke-FullscreenDiagnostic -TcpPort $Port
    if (-not $runtime.ok) {
        throw "The runtime reported an error: $($runtime.error)"
    }

    $os = Get-CimInstance Win32_OperatingSystem
    $computer = Get-CimInstance Win32_ComputerSystem
    $gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
        Convert-CimObject $_ @(
            "Name", "DriverVersion", "VideoModeDescription",
            "CurrentHorizontalResolution", "CurrentVerticalResolution",
            "CurrentRefreshRate", "CurrentBitsPerPixel", "AdapterRAM",
            "PNPDeviceID"
        )
    })
    $monitors = @()
    try {
        $monitors = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    instance_name = $_.InstanceName
                    manufacturer  = (($_.ManufacturerName | Where-Object { $_ }) |
                        ForEach-Object { [char]$_ }) -join ""
                    product_code  = (($_.ProductCodeID | Where-Object { $_ }) |
                        ForEach-Object { [char]$_ }) -join ""
                    serial_number = (($_.SerialNumberID | Where-Object { $_ }) |
                        ForEach-Object { [char]$_ }) -join ""
                    active        = $_.Active
                }
            })
    }
    catch {
        $monitors = @([pscustomobject]@{ collection_error = $_.Exception.Message })
    }

    $report = [ordered]@{
        schema             = 1
        collected_utc      = [DateTime]::UtcNow.ToString("o")
        collector_version  = "1.0"
        runtime            = $runtime
        operating_system   = Convert-CimObject $os @(
            "Caption", "Version", "BuildNumber", "OSArchitecture"
        )
        computer           = Convert-CimObject $computer @(
            "Manufacturer", "Model", "TotalPhysicalMemory"
        )
        video_controllers  = $gpus
        monitors           = $monitors
        video_settings     = Get-SafeVideoSettings
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $outputPath = Join-Path $scriptDir "fullscreen-diagnostic-$timestamp.json"
    $report | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host ""
    Write-Host "Diagnostic report written to:"
    Write-Host $outputPath
    Write-Host ""
    Write-Host "Please attach that JSON file to the GitHub issue."
}
catch {
    Write-Host ""
    Write-Host "Could not collect the report:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Keep MegaManX6Recomp running on the game screen, then try again."
    Write-Host "If the game is running, allow its localhost connection in security software."
    exit 1
}
