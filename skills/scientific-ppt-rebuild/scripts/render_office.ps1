param(
    [Parameter(Mandatory = $true)][string]$InputPptx,
    [Parameter(Mandatory = $true)][string]$OutputPdf
)
$ErrorActionPreference = 'Stop'
function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $hash.Dispose() }
}
$inputPath = (Resolve-Path -LiteralPath $InputPptx).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputPdf)
if (Test-Path -LiteralPath $outputPath) { throw 'Refusing to overwrite PDF output' }
$before = Get-Sha256 $inputPath
$presentation = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    $presentation = $app.Presentations.Open($inputPath, -1, 0, 0)
    $presentation.SaveAs($outputPath, 32)
} finally {
    if ($null -ne $presentation) { $presentation.Close() }
}
if ((Get-Sha256 $inputPath) -ne $before) {
    throw 'Input file changed while rendering'
}
if (-not (Test-Path -LiteralPath $outputPath)) { throw 'PowerPoint did not create PDF' }
