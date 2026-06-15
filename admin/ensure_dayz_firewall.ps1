# Add Windows Firewall rules for the configured DayZ game and Steam query UDP ports.
param(
    [string]$Map = 'all',

    [switch]$SkipClientRules
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Windows Firewall changes require an Administrator PowerShell."
}

$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$maps = if ($Map -eq 'all') {
    $Launch.maps.PSObject.Properties
} else {
    $cfg = $Launch.maps.$Map
    if (-not $cfg) {
        $known = ($Launch.maps.PSObject.Properties.Name -join ', ')
        throw "Unknown map: $Map. Known maps: $known"
    }
    @([pscustomobject]@{ Name = $Map; Value = $cfg })
}

$ports = [System.Collections.Generic.SortedSet[int]]::new()
foreach ($entry in $maps) {
    $cfg = $entry.Value
    [void]$ports.Add([int]$cfg.port)
    [void]$ports.Add([int]$cfg.steam_query_port)
    [void]$ports.Add(([int]$cfg.port + 2))
}

function Enable-PortRule {
    param(
        [string]$Name,
        [string]$Direction,
        [int]$Port
    )

    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $Name -Enabled True -Direction $Direction -Action Allow
        Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing -Protocol UDP -LocalPort $Port
        Write-Host "Updated firewall rule: $Name"
    } else {
        New-NetFirewallRule -DisplayName $Name -Direction $Direction -Action Allow -Protocol UDP -LocalPort $Port | Out-Null
        Write-Host "Created firewall rule: $Name"
    }
}

function Enable-ProgramRule {
    param(
        [string]$Name,
        [string]$Direction,
        [string]$Program
    )

    if (-not (Test-Path -LiteralPath $Program)) { return }
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $Name -Enabled True -Direction $Direction -Action Allow
        Set-NetFirewallApplicationFilter -AssociatedNetFirewallRule $existing -Program $Program
        Write-Host "Updated firewall rule: $Name"
    } else {
        New-NetFirewallRule -DisplayName $Name -Direction $Direction -Action Allow -Program $Program | Out-Null
        Write-Host "Created firewall rule: $Name"
    }
}

foreach ($port in @($ports)) {
    $ruleName = "DayZ Server UDP $port"
    Enable-PortRule -Name $ruleName -Direction Inbound -Port $port
}

if (-not $SkipClientRules) {
    $commonRoot = Split-Path $Root -Parent
    $steamRoot = Split-Path (Split-Path $commonRoot -Parent) -Parent
    $programs = @(
        @{ Name = 'DayZ Server'; Path = (Join-Path $Root 'DayZServer_x64.exe') },
        @{ Name = 'Steam'; Path = (Join-Path $steamRoot 'steam.exe') },
        @{ Name = 'Steam WebHelper'; Path = (Join-Path $steamRoot 'bin\cef\cef.win64\steamwebhelper.exe') },
        @{ Name = 'DayZ Launcher'; Path = (Join-Path $commonRoot 'DayZ\DayZLauncher.exe') },
        @{ Name = 'DayZ Client'; Path = (Join-Path $commonRoot 'DayZ\DayZ_x64.exe') }
    )
    foreach ($program in $programs) {
        Enable-ProgramRule -Name "DayZ LAN $($program.Name) UDP In" -Direction Inbound -Program $program.Path
        Enable-ProgramRule -Name "DayZ LAN $($program.Name) UDP Out" -Direction Outbound -Program $program.Path
    }
}

Write-Host "Launcher visibility still requires Steam online, the server running, and the RPT to reach 'Player connect enabled'."
