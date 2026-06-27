# backup_config_offsite.ps1 - create a fresh config backup and mirror the zips
# to an off-machine folder (OneDrive). Intended to run on a Windows Scheduled
# Task. Config-only (no PBOs, no player storage); safe to run while servers run.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File admin\backup_config_offsite.ps1
#   ... -Dest "D:\some\folder" -Keep 30
#
# Registered as the daily Windows Scheduled Task "DayZ Config Backup to OneDrive"
# (4:00 AM, runs when next available if the PC was off). To recreate it:
#   $s = "C:\Games\Steam\steamapps\common\DayZServer\admin\backup_config_offsite.ps1"
#   Register-ScheduledTask -TaskName "DayZ Config Backup to OneDrive" -Force `
#     -Action  (New-ScheduledTaskAction  -Execute powershell.exe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$s`"") `
#     -Trigger (New-ScheduledTaskTrigger -Daily -At 4:00AM) `
#     -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)
# To change the time: edit the trigger above. To remove it:
#   Unregister-ScheduledTask -TaskName "DayZ Config Backup to OneDrive" -Confirm:$false
param(
    [string]$Dest = "C:\Users\Owenl\OneDrive\Desktop\games\DayZ\config_backups",
    [int]$Keep = 14
)

$ErrorActionPreference = 'Stop'
$Admin = $PSScriptRoot
$Root = Split-Path $Admin -Parent
$LocalConfig = Join-Path $Root 'local_backups\config'

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = 'python' }

# 1. Fresh rotated local backup.
& $python (Join-Path $Admin 'backup_config.py') --label scheduled --retention $Keep
if ($LASTEXITCODE -ne 0) { throw "backup_config.py exited $LASTEXITCODE" }

# 2. Mirror the local config zips off-machine (copy new/changed only; never deletes).
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
if (Test-Path $LocalConfig) {
    robocopy $LocalConfig $Dest *.zip /XO /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy to $Dest failed (code $LASTEXITCODE)" }
}

# 3. Prune the off-machine copies to the newest $Keep.
Get-ChildItem $Dest -Filter *.zip -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip ([Math]::Max(1, $Keep)) |
    Remove-Item -Force -ErrorAction SilentlyContinue

$count = (Get-ChildItem $Dest -Filter *.zip -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "Offsite config backup OK -> $Dest ($count zip(s) kept)."
