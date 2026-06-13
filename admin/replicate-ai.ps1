# Sync Chernarus Expansion AI patrol/spatial tuning to other maps.
param([switch] $Status, [switch] $CopyLoadouts)

$pyArgs = @("$PSScriptRoot\replicate_ai_settings.py")
if ($Status) { $pyArgs += "--status" }
if ($CopyLoadouts) { $pyArgs += "--copy-loadouts" }
python @pyArgs
if (-not $Status) {
    python "$PSScriptRoot\apply_ai_ammo.py"
}
exit $LASTEXITCODE
