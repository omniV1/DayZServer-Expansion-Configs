# Launcher preset: Chernarus mod set + TakistanPlus (map loads last on server via takistan_mods.txt).
$ErrorActionPreference = 'Stop'
$presetDir = Join-Path $env:LOCALAPPDATA 'DayZ Launcher\Presets'
$dstPreset = Join-Path $presetDir 'Owens-Takistan.preset2'

# TakistanPlus last; Dabs before it (sandstorm). Other IDs match common Owens Chernarus stack.
$required = @(
    'steam:1559212036'   # @CF
    'steam:1828439124'   # @VPPAdminTools
    'steam:2291785308'   # @DayZ-Expansion-Core
    'steam:2792982069'   # @DayZ-Expansion-AI
    'steam:2572331007'   # @DayZ-Expansion-Bundle
    'steam:2116157322'   # @DayZ-Expansion-Licensed
    'steam:2572328470'   # @DayZ-Expansion-Market
    'steam:2545327648'   # @Dabs Framework (before map)
    'steam:2563233742'   # @TakistanPlus (map — enable on client)
)

if (-not (Test-Path $presetDir)) {
    Write-Warning 'DayZ Launcher Presets folder not found.'
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
Write-Host "Wrote $dstPreset"
Write-Host 'For full Chernarus parity, also enable your other Chernarus mods, then ensure @Dabs Framework and @TakistanPlus stay at the end.'
Write-Host 'Launcher -> MODS -> Presets -> Owens-Takistan -> PLAY'
