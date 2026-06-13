# DayZ loot toolchain launcher — run from admin/ or via loot.cmd at server root.
# Usage:
#   .\apply-loot.ps1                    # same as: all (active preset)
#   .\apply-loot.ps1 -Action all -Preset high
#   .\apply-loot.ps1 -Action status
#   .\apply-loot.ps1 -Action set-preset -Preset medium

param(
    [ValidateSet('all', 'build', 'globals', 'replicate', 'status', 'set-preset')]
    [string] $Action = 'all',

    [ValidateSet('light', 'medium', 'high', 'arcade', '')]
    [string] $Preset = ''
)

$ErrorActionPreference = 'Stop'
$AdminDir = $PSScriptRoot
$Python = 'python'

function Show-Help {
    Write-Host ''
    Write-Host 'DayZ Loot Scripts' -ForegroundColor Cyan
    Write-Host '  apply-loot.ps1 [-Action all|build|globals|replicate|status|set-preset] [-Preset light|medium|high|arcade]'
    Write-Host ''
    Write-Host 'Examples:'
    Write-Host '  .\admin\apply-loot.ps1 -Action status'
    Write-Host '  .\admin\apply-loot.ps1 -Action all -Preset high'
    Write-Host '  .\admin\apply-loot.ps1 -Action set-preset -Preset medium'
    Write-Host ''
    Write-Host 'Config: admin\loot_config.json'
    Write-Host 'Docs:   admin\SCRIPTS.md'
    Write-Host ''
}

if ($args -contains '-h' -or $args -contains '--help') {
    Show-Help
    exit 0
}

$pyArgs = @("$AdminDir\apply_loot.py", $Action)
if ($Preset) {
    $pyArgs += @('--preset', $Preset)
}

& $Python @pyArgs
exit $LASTEXITCODE
