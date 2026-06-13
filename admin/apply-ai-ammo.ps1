# Expansion AI ammo — unlimited reload on patrols/spatial + extra mags in loadouts.
# Usage:
#   .\apply-ai-ammo.ps1
#   .\apply-ai-ammo.ps1 -Status

param([switch] $Status)

$ErrorActionPreference = 'Stop'
$pyArgs = @("$PSScriptRoot\apply_ai_ammo.py")
if ($Status) { $pyArgs += '--status' }
python @pyArgs
exit $LASTEXITCODE
