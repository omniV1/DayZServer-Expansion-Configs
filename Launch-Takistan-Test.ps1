# Debug Takistan: minimal mods only (CF + Dabs + map). If this works, add mods back via takistan_mods.txt.
$ErrorActionPreference = 'Stop'
$ServerRoot = $PSScriptRoot
$modsFile = Join-Path $ServerRoot 'admin\takistan_minimal_mods.txt'
$mapCfg = Get-Content (Join-Path $ServerRoot 'admin\map_launch.json') -Raw | ConvertFrom-Json
$t = $mapCfg.maps.takistan
$mods = (Get-Content $modsFile -Raw).Trim()
$exe = Join-Path $ServerRoot 'DayZServer_x64.exe'
$args = @(
    "-config=$($t.config)",
    "-port=$($t.port)",
    "-profiles=$($t.profiles_dir)",
    "-cpuCount=$($t.cpu)",
    '-dologs', '-adminlog', '-netlog', '-freezecheck',
    "-mod=$mods"
)
$parts = foreach ($a in $args) { if ($a -match '[\s;]') { '"' + ($a -replace '"', '""') + '"' } else { $a } }
$argLine = $parts -join ' '
Write-Host 'Takistan MINIMAL test: @CF;@Dabs Framework;@TakistanPlus'
Write-Host 'Wait for RPT storage_* under profiles_takistan, then run admin\check_takistan.ps1'
$p = Start-Process -FilePath $exe -WorkingDirectory $ServerRoot -ArgumentList $argLine -Wait -PassThru
exit $p.ExitCode
