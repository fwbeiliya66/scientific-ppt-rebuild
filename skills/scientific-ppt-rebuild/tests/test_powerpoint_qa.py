import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('pwsh') or shutil.which('powershell')

PARSE_SCRIPT = r'''
param([string]$QaPath, [string]$Directory)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($QaPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
'''


@unittest.skipUnless(POWERSHELL, 'PowerShell is required for QA script regression checks')
class PowerPointQaTests(unittest.TestCase):
    def run_probe(self, body):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / 'probe.ps1'
            probe.write_text(PARSE_SCRIPT + body, encoding='utf-8')
            result = subprocess.run(
                [POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                 '-File', str(probe), str(SKILL / 'scripts/powerpoint_qa.ps1'), str(root)],
                capture_output=True, text=True, encoding='utf-8',
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

    def test_ungroup_scan_skips_single_member_and_nested_groups(self):
        result = self.run_probe(r'''
$shapeFunction = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-ShapeTargets'
}, $true)
. ([scriptblock]::Create($shapeFunction.Extent.Text))
$groupLoop = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.ForStatementAst] -and $null -ne $node.Body.Find({ param($child)
        $child -is [Management.Automation.Language.VariableExpressionAst] -and $child.VariablePath.UserPath -eq 'groupTarget'
    }, $true)
}, $true)
if ($null -eq $groupLoop) { throw 'Group scan was not found.' }
function New-Collection([object[]]$Items) {
    $collection = [pscustomobject]@{ Count = $Items.Count; Items = $Items }
    $collection | Add-Member ScriptMethod Item { param([int]$Index) $this.Items[$Index - 1] }
    return $collection
}
function New-Leaf([string]$Name) { return [pscustomobject]@{ Type = 1; Name = $Name } }
function New-Group([string]$Name, [object[]]$Members) {
    return [pscustomobject]@{ Type = 6; Name = $Name; GroupItems = (New-Collection $Members) }
}
$single = New-Group 'Single' @((New-Leaf 'a'))
$nested = New-Group 'Nested' @((New-Leaf 'b'), (New-Leaf 'c'))
$wrapper = New-Group 'Wrapper' @($nested)
$eligible = New-Group 'Eligible' @((New-Leaf 'd'), (New-Leaf 'e'))
$scratch = [pscustomobject]@{ Slides = (New-Collection @(
    [pscustomobject]@{ Shapes = (New-Collection @($single, $wrapper, $eligible)) }
)) }
$groupTarget = $null; $groupsFound = 0
. ([scriptblock]::Create($groupLoop.Extent.Text))
$chosen = $groupTarget.path
$found = $groupsFound
$scratch.Slides = New-Collection @([pscustomobject]@{ Shapes = (New-Collection @($single, $wrapper)) })
$groupTarget = $null; $groupsFound = 0
. ([scriptblock]::Create($groupLoop.Extent.Text))
@{ selected = $chosen; groups_found = $found; no_eligible_target = ($null -eq $groupTarget) } | ConvertTo-Json
''')
        self.assertEqual(result['selected'], 'Eligible')
        self.assertEqual(result['groups_found'], 4)
        self.assertTrue(result['no_eligible_target'])

    def test_edit_scratch_copy_is_writable_without_changing_readonly_source(self):
        result = self.run_probe(r'''
$editBlock = $ast.Find({ param($node)
    if ($node -isnot [Management.Automation.Language.IfStatementAst]) { return $false }
    $statements = $node.Clauses[0].Item2.Statements
    return $statements.Count -gt 0 -and $statements[0] -is [Management.Automation.Language.AssignmentStatementAst] -and
        $statements[0].Left.Extent.Text -eq '$scratchPath'
}, $true).Clauses[0].Item2
$source = Join-Path $Directory 'source.pptx'
[IO.File]::WriteAllText($source, 'Synthetic source bytes')
[IO.File]::SetAttributes($source, ([IO.File]::GetAttributes($source) -bor [IO.FileAttributes]::ReadOnly))
$originalAttributes = [IO.File]::GetAttributes($source)
$output = Join-Path $Directory 'qa'
[void][IO.Directory]::CreateDirectory($output)
$paths = @{ input = $source; output = $output }
$report = @{}
try {
    # Run the real scratch setup, stopping before any PowerPoint call.
    foreach ($statement in $editBlock.Statements) {
        if ($statement -is [Management.Automation.Language.AssignmentStatementAst] -and
            $statement.Left.Extent.Text -eq '$scratch') { break }
        . ([scriptblock]::Create($statement.Extent.Text))
    }
    @{
        scratch_readonly = (Get-Item -LiteralPath $scratchPath).IsReadOnly
        source_readonly = (Get-Item -LiteralPath $source).IsReadOnly
        source_attributes_unchanged = ([IO.File]::GetAttributes($source) -eq $originalAttributes)
        source_text = [IO.File]::ReadAllText($source)
    } | ConvertTo-Json
} finally {
    (Get-Item -LiteralPath $source).IsReadOnly = $false
    if (Test-Path -LiteralPath (Join-Path $output 'edit_test.pptx')) {
        (Get-Item -LiteralPath (Join-Path $output 'edit_test.pptx')).IsReadOnly = $false
    }
}
''')
        self.assertFalse(result['scratch_readonly'])
        self.assertTrue(result['source_readonly'])
        self.assertTrue(result['source_attributes_unchanged'])
        self.assertEqual(result['source_text'], 'Synthetic source bytes')


if __name__ == '__main__':
    unittest.main()
