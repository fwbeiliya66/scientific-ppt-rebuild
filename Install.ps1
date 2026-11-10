<#
.SYNOPSIS
Installs Scientific PPT Rebuild using an existing Python 3.11 or newer.
.DESCRIPTION
Finds Python through py or python, copies the core skill, and installs dependencies
in the target's own .venv. No Python executable or machine-wide package is installed.
.PARAMETER Target
Exact final skill directory. Defaults to CODEX_HOME/skills/scientific-ppt-rebuild,
or ~/.codex/skills/scientific-ppt-rebuild when CODEX_HOME is unset.
.PARAMETER Replace
Preserves an existing target as a timestamped sibling backup before replacement.
.PARAMETER SkipDependencies
Copies source only for offline setup. Does not create a venv or install packages.
.EXAMPLE
.\Install.ps1 -Target 'D:\Skills\scientific-ppt-rebuild' -SkipDependencies
#>
[CmdletBinding()]
param(
    [string]$Target,
    [switch]$Replace,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$candidates = @()
$launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
if ($launcher) { $candidates += [pscustomobject]@{ command = $launcher.Source; prefix = @('-3') } }
$pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
if ($pythonCommand) { $candidates += [pscustomobject]@{ command = $pythonCommand.Source; prefix = @() } }
$python = $null
foreach ($candidate in $candidates) {
    try {
        $probeArgs = @($candidate.prefix) + @('-B', '-X', 'utf8', '-c',
            'import sys; sys.exit(1) if sys.version_info < (3, 11) else print(sys.executable)')
        $detected = & $candidate.command @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and ![string]::IsNullOrWhiteSpace([string]$detected)) {
            $python = ([string]$detected).Trim()
            break
        }
    } catch { continue }
}
if (!$python) { throw 'Python 3.11 or newer was not found. Install it or put an existing interpreter on PATH, then retry.' }

$installerArgs = @('-B', '-X', 'utf8', (Join-Path $PSScriptRoot 'install.py'))
if ($Target) { $installerArgs += @('--target', $Target) }
if ($Replace) { $installerArgs += '--replace' }
if (!$SkipDependencies) { $installerArgs += '--install-deps' }
& $python @installerArgs
exit $LASTEXITCODE
