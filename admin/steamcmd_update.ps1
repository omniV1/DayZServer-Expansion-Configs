# steamcmd_update.ps1 - install SteamCMD and update the DayZ server / Workshop mods.
#
# SteamCMD needs an interactive Steam login (password + Steam Guard) the first time.
# So 'login', 'update-server', and 'update-mods' open a VISIBLE console window and
# return immediately; the long download and any prompts happen in that window, and
# SteamCMD caches the session for later runs. Only 'install' (which needs no login)
# runs inline so its output is captured.
#
# No Steam password is ever stored or passed by this tool.
#
# Usage:
#   steamcmd_update.ps1 -Action install
#   steamcmd_update.ps1 -Action status
#   steamcmd_update.ps1 -Action login         -Username you
#   steamcmd_update.ps1 -Action update-server  -Username you
#   steamcmd_update.ps1 -Action update-mods    -Username you -ModIds 123,456

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'status', 'login', 'update-server', 'update-mods')]
    [string]$Action,

    [string]$SteamCmd,
    [string]$Username,
    [string]$ModIds,
    [string]$ServerDir
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$DefaultDir = Join-Path $Root 'local_runtime\steamcmd'
if (-not $SteamCmd) { $SteamCmd = Join-Path $DefaultDir 'steamcmd.exe' }
$SteamWorkDir = Split-Path $SteamCmd

$DAYZ_SERVER_APPID = '223350'
$DAYZ_WORKSHOP_APPID = '221100'

function Assert-SteamCmd {
    if (-not (Test-Path $SteamCmd)) { throw "SteamCMD not found at $SteamCmd. Run Install SteamCMD first." }
}

function Assert-Username {
    if (-not $Username) { throw 'Set your Steam username first (Updates tab). No password is stored.' }
}

switch ($Action) {
    'install' {
        New-Item -ItemType Directory -Force -Path $DefaultDir | Out-Null
        $zip = Join-Path $DefaultDir 'steamcmd.zip'
        Write-Host 'Downloading SteamCMD from Valve...'
        Invoke-WebRequest -Uri 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip' -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $DefaultDir -Force
        Remove-Item $zip -Force
        Write-Host 'Running first-time SteamCMD self-update (no login needed)...'
        & $SteamCmd +quit | Out-Null
        Write-Host "SteamCMD installed at $SteamCmd"
    }
    'status' {
        if (Test-Path $SteamCmd) { Write-Host "SteamCMD found: $SteamCmd" }
        else { Write-Host "SteamCMD not found at $SteamCmd" }
    }
    'login' {
        Assert-SteamCmd
        Assert-Username
        Write-Host 'Opening a console for interactive Steam login.'
        Write-Host 'Enter your password and Steam Guard code in that window. SteamCMD caches the session afterward.'
        Start-Process -FilePath $SteamCmd -ArgumentList "+login $Username +quit" -WorkingDirectory $SteamWorkDir
    }
    'update-server' {
        Assert-SteamCmd
        Assert-Username
        if (-not $ServerDir) { $ServerDir = $Root }
        Write-Host "Starting DayZ server update (app $DAYZ_SERVER_APPID) in a new window..."
        $argLine = "+force_install_dir `"$ServerDir`" +login $Username +app_update $DAYZ_SERVER_APPID validate +quit"
        Start-Process -FilePath $SteamCmd -ArgumentList $argLine -WorkingDirectory $SteamWorkDir
        Write-Host 'Update running in the new window. Stop the server before updating, and wait for it to finish.'
    }
    'update-mods' {
        Assert-SteamCmd
        Assert-Username
        $ids = @($ModIds -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if ($ids.Count -eq 0) { throw 'No Workshop mod IDs provided.' }
        $parts = @('+login', $Username)
        foreach ($id in $ids) {
            if ($id -notmatch '^\d+$') { throw "Invalid Workshop mod ID: $id" }
            $parts += '+workshop_download_item'
            $parts += $DAYZ_WORKSHOP_APPID
            $parts += $id
        }
        $parts += '+quit'
        Write-Host "Starting Workshop update for $($ids.Count) mod(s) in a new window..."
        Start-Process -FilePath $SteamCmd -ArgumentList ($parts -join ' ') -WorkingDirectory $SteamWorkDir
        Write-Host 'Downloads run in the new window. Then use Sync Workshop mods to copy them into the server root.'
    }
}

exit 0
