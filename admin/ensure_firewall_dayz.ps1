# Inbound UDP firewall rules for DayZ dedicated server + Steam LAN discovery.
# Run once as Administrator.

$ErrorActionPreference = 'Stop'
$ServerExe = "C:\Games\Steam\steamapps\common\DayZServer\DayZServer_x64.exe"
$ClientExe = "C:\Games\Steam\steamapps\common\DayZ\DayZ_x64.exe"

function Add-UdpRule {
    param([string]$Name, [string]$Port, [string]$Program = $null)

    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Exists: $Name"
        return
    }
    $params = @{
        DisplayName = $Name
        Direction   = 'Inbound'
        Action      = 'Allow'
        Protocol    = 'UDP'
        LocalPort   = $Port
        Enabled     = 'True'
        Profile     = 'Domain', 'Private', 'Public'
    }
    if ($Program -and (Test-Path $Program)) {
        $params['Program'] = $Program
    }
    New-NetFirewallRule @params | Out-Null
    Write-Host "Added: $Name (UDP $Port)"
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Re-run this script in an elevated PowerShell (Run as administrator)."
    exit 1
}

# Per-map game + query + steam ports (Chernarus defaults + alts)
foreach ($p in @(2302, 2304, 27016, 27017, 27018, 27019, 2402, 2404, 2502, 2504, 2602, 2604, 8766)) {
    Add-UdpRule -Name "DayZ Server UDP $p" -Port $p -Program $ServerExe
}

if (Test-Path $ClientExe) {
    Add-UdpRule -Name "DayZ Client UDP 27000-27100" -Port "27000-27100" -Program $ClientExe
}

Write-Host "Done. Restart the DayZ server, then use Direct Connect: 192.168.0.3:2302"
