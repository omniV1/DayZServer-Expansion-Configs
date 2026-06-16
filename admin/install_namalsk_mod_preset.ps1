# Namalsk launcher preset: must match server mods + both Namalsk packs (Island + Survival server).
$ErrorActionPreference = 'Stop'
$presetDir = Join-Path $env:LOCALAPPDATA 'DayZ Launcher\Presets'
$dstPreset = Join-Path $presetDir 'Owens-Namalsk.preset2'

# Keep in sync with admin/namalsk_mods.txt + map_launch.json prepend_mods / server_mods.
$required = @(
    'steam:2289456201'  # @Namalsk Island (first in launcher order)
    'steam:2288336145'  # @Namalsk Survival (server) — required on client for LEHS assets
    'steam:1559212036'  # @CF
    'steam:2545327648'  # @Dabs Framework
    'steam:1828439124'  # @VPPAdminTools
    'steam:2291785308'  # @DayZ-Expansion-Core
    'steam:2792982069'  # @DayZ-Expansion-AI
    'steam:2572331007'  # @DayZ-Expansion-Bundle
    'steam:2116157322'  # @DayZ-Expansion-Licensed
    'steam:2572328470'  # @DayZ-Expansion-Market
)

if (-not (Test-Path $presetDir)) {
    Write-Warning "DayZ Launcher Presets folder not found."
    exit 1
}

$xml = New-Object System.Xml.XmlDocument
$xml.AppendChild($xml.CreateXmlDeclaration('1.0', 'utf-8', $null)) | Out-Null
$root = $xml.CreateElement('addons-presets')
$xml.AppendChild($root) | Out-Null
$lu = $xml.CreateElement('last-update')
$lu.InnerText = (Get-Date).ToString('o')
[void]$root.AppendChild($lu)
$idsNode = $xml.CreateElement('published-ids')
[void]$root.AppendChild($idsNode)

foreach ($id in $required) {
    $el = $xml.CreateElement('id')
    $el.InnerText = $id
    [void]$idsNode.AppendChild($el)
}

$xml.Save($dstPreset)
Write-Host "Wrote $dstPreset ($($required.Count) mods, Namalsk first)."
Write-Host "DayZ Launcher -> MODS -> Presets -> Owens-Namalsk -> PLAY (do not use Connect-Namalsk.bat alone)."
