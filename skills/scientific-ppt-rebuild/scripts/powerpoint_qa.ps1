param(
    [Parameter(Mandatory = $true)][string]$InputPptx,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [switch]$TestEdits
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# Bundled runtimes can inherit a PSModulePath without the Windows PowerShell modules.
foreach ($moduleName in @('Microsoft.PowerShell.Management', 'Microsoft.PowerShell.Utility')) {
    Import-Module ([IO.Path]::Combine($PSHOME, 'Modules', $moduleName, ($moduleName + '.psd1'))) -ErrorAction Stop
}

function Get-QaHash([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($Path)
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}

function Resolve-QaPaths([string]$InputPath, [string]$DirectoryPath) {
    $inputFile = Get-Item -LiteralPath $InputPath
    if ($inputFile.PSIsContainer -or $inputFile.Extension -ine '.pptx') {
        throw 'InputPptx must be an existing .pptx file.'
    }
    if ([string]::IsNullOrWhiteSpace($DirectoryPath)) { throw 'OutputDir cannot be empty.' }
    $outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DirectoryPath)
    $outputPath = [IO.Path]::GetFullPath($outputPath)
    $separator = [IO.Path]::DirectorySeparatorChar
    $outputPrefix = $outputPath.TrimEnd($separator) + $separator
    if ($inputFile.FullName.Equals($outputPath, [StringComparison]::OrdinalIgnoreCase) -or
        $inputFile.FullName.StartsWith($outputPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Input/output collision: OutputDir must not contain InputPptx.'
    }
    # Reject aliases through junctions/symlinks rather than guessing their physical targets.
    foreach ($path in @($inputFile.FullName, $outputPath)) {
        $ancestor = $path
        while ($ancestor) {
            if (Test-Path -LiteralPath $ancestor) {
                $item = Get-Item -LiteralPath $ancestor -Force
                if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw "Reparse-point path is not supported: $ancestor"
                }
            }
            $ancestor = Split-Path -Parent $ancestor
        }
    }
    if (Test-Path -LiteralPath $outputPath) {
        if (!(Test-Path -LiteralPath $outputPath -PathType Container)) { throw 'OutputDir is an existing file.' }
        if (@(Get-ChildItem -LiteralPath $outputPath -Force).Count -ne 0) {
            throw 'OutputDir must be empty; existing files will never be overwritten.'
        }
    }
    return @{ input = $inputFile.FullName; output = $outputPath }
}

function Get-RenderSize([double]$Width, [double]$Height) {
    if ($Width -le 0 -or $Height -le 0 -or [double]::IsNaN($Width) -or
        [double]::IsNaN($Height) -or [double]::IsInfinity($Width) -or [double]::IsInfinity($Height)) {
        throw 'Slide dimensions must be positive and finite.'
    }
    return @{ width = 1600; height = [int][Math]::Max(1, [Math]::Round(1600 * $Height / $Width)) }
}

function New-TestResult([string]$Status, [string]$Reason) {
    return [ordered]@{
        status = $Status; attempted = $false; changed = $false; reverted = $null; passed = $false
        reason = $Reason; target_count = $null; unavailable = $null; error = $null; detail = [ordered]@{}
    }
}

function Get-ComIdentity($Object) {
    $pointer = [Runtime.InteropServices.Marshal]::GetIUnknownForObject($Object)
    try { return $pointer.ToInt64() } finally { [void][Runtime.InteropServices.Marshal]::Release($pointer) }
}

function Open-OwnedPresentation([string]$Path, [bool]$ReadOnly) {
    $existing = @()
    for ($index = 1; $index -le $app.Presentations.Count; $index++) {
        $existing += Get-ComIdentity ($app.Presentations.Item($index))
    }
    $readOnlyFlag = 0
    if ($ReadOnly) { $readOnlyFlag = -1 }
    $opened = $app.Presentations.Open($Path, $readOnlyFlag, 0, 0)
    if ((Get-ComIdentity $opened) -in $existing) {
        throw 'PowerPoint reused a pre-existing presentation; it will not be modified or closed.'
    }
    [void]$owned.Add($opened)
    return $opened
}

function Close-OwnedPresentation($Presentation) {
    $identity = Get-ComIdentity $Presentation
    $ownedIndex = -1
    for ($index = 0; $index -lt $owned.Count; $index++) {
        if ((Get-ComIdentity $owned[$index]) -eq $identity) { $ownedIndex = $index; break }
    }
    if ($ownedIndex -lt 0) { throw 'Refusing to close an unowned presentation.' }
    # Scratch tests intentionally discard unsaved changes; this prevents a save prompt.
    $Presentation.Saved = -1
    $Presentation.Close()
    $owned.RemoveAt($ownedIndex)
}

function Get-ShapeTargets($Shapes, [int]$SlideNumber, [string]$Prefix = '') {
    for ($index = 1; $index -le $Shapes.Count; $index++) {
        $shape = $Shapes.Item($index)
        $path = $Prefix + $shape.Name
        [pscustomobject]@{ shape = $shape; slide = $SlideNumber; path = $path; top_level = ($Prefix -eq '') }
        if ($shape.Type -eq 6) { Get-ShapeTargets $shape.GroupItems $SlideNumber ($path + '/') }
    }
}

function Get-PngInfo([string]$Path) {
    Add-Type -AssemblyName System.Drawing
    $image = [Drawing.Image]::FromFile($Path)
    try {
        return @{ width = $image.Width; height = $image.Height; bytes = (Get-Item -LiteralPath $Path).Length }
    } finally { $image.Dispose() }
}

function Set-TestOutcome($Result) {
    $Result.passed = $Result.changed -and ($Result.reverted -eq $true) -and ($null -eq $Result.error)
    if ($Result.passed) { $Result.status = 'passed' }
    elseif ($null -ne $Result.error) { $Result.status = 'error' }
    else { $Result.status = 'failed' }
}

function Get-QaPassed($Report, [bool]$EditsRequested) {
    if ($Report.status -ne 'completed' -or !$Report.opened_read_only -or !$Report.render_complete -or
        !$Report.source_unchanged -or $Report.errors.Count -gt 0 -or $Report.slide_count -le 0 -or
        @($Report.rendered_files).Count -ne $Report.slide_count) { return $false }
    if ($EditsRequested) {
        foreach ($name in @('text', 'fill', 'picture_move', 'picture_replace', 'group_ungroup', 'save_reopen')) {
            $result = $Report.edit_tests[$name]
            if ($null -eq $result) { return $false }
            if ($name -eq 'group_ungroup' -and $result.status -eq 'not_applicable') {
                if (!$Report.object_scan_complete -or $Report.object_counts.groups -ne 0 -or $result.target_count -ne 0 -or
                    $result.passed -or $result.attempted -or [string]::IsNullOrWhiteSpace($result.reason) -or
                    $null -ne $result.error -or $null -ne $result.unavailable) { return $false }
                continue
            }
            if ($result.status -ne 'passed' -or !$result.passed -or $null -ne $result.error) { return $false }
        }
    }
    return $true
}

# All validation precedes directory creation and COM activation.
$paths = Resolve-QaPaths $InputPptx $OutputDir
$sourceHash = Get-QaHash $paths.input
[void][IO.Directory]::CreateDirectory($paths.output)
$workDir = Join-Path $paths.output ('.qa-' + [Guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $workDir) { throw 'Work directory collision.' }
[void][IO.Directory]::CreateDirectory($workDir)
$reportPath = Join-Path $paths.output 'report.json'
$owned = New-Object 'System.Collections.Generic.List[object]'
$app = $null
$report = [ordered]@{
    schema_version = 1; status = 'running'; input = $paths.input; output_dir = $paths.output
    input_sha256 = $sourceHash.ToLowerInvariant(); passed = $false; test_edits_requested = [bool]$TestEdits
    report_path = $reportPath; work_dir = $workDir; started_utc = [DateTime]::UtcNow.ToString('o'); finished_utc = $null
    source_sha256_before = $sourceHash; source_sha256_after = $null; source_unchanged = $false
    opened_read_only = $false; slide_count = 0; width_pt = 0; height_pt = 0
    render_width_px = 0; render_height_px = 0; render_complete = $false; rendered_files = @(); slides = @()
    edit_test_path = $null; object_scan_complete = $false; object_counts = $null; edit_tests = [ordered]@{}; errors = @()
}
foreach ($name in @('text', 'fill', 'picture_move', 'picture_replace', 'group_ungroup', 'save_reopen')) {
    $report.edit_tests[$name] = New-TestResult 'not_requested' 'TestEdits was not supplied.'
    if ($TestEdits) { $report.edit_tests[$name] = New-TestResult 'not_run' 'Execution did not reach this test.' }
}

try {
    $app = New-Object -ComObject PowerPoint.Application
    # Untitled copies are writable on some PowerPoint versions even with ReadOnly requested.
    $final = Open-OwnedPresentation $paths.input $true
    $report.opened_read_only = ($final.ReadOnly -eq -1)
    if (!$report.opened_read_only) { throw 'PowerPoint did not open the final deck read-only.' }
    $report.slide_count = $final.Slides.Count
    $report.width_pt = $final.PageSetup.SlideWidth
    $report.height_pt = $final.PageSetup.SlideHeight
    $size = Get-RenderSize $report.width_pt $report.height_pt
    $report.render_width_px = $size.width; $report.render_height_px = $size.height
    for ($index = 1; $index -le $final.Slides.Count; $index++) {
        $fileName = 'slide_{0:D3}.png' -f $index
        $renderPath = Join-Path $paths.output $fileName
        $temporaryPath = Join-Path $workDir $fileName
        $slideResult = [ordered]@{ page = $index; render_path = $renderPath; temporary_render_path = $temporaryPath; rendered = $false; bytes = 0; width_px = 0; height_px = 0; error = $null }
        $report.slides += $slideResult
        try {
            $final.Slides.Item($index).Export($temporaryPath, 'PNG', $size.width, $size.height)
            $png = Get-PngInfo $temporaryPath
            $slideResult.bytes = $png.bytes; $slideResult.width_px = $png.width; $slideResult.height_px = $png.height
            if ($png.width -ne $size.width -or $png.height -ne $size.height) { throw 'PowerPoint returned unexpected PNG dimensions.' }
            [IO.File]::Move($temporaryPath, $renderPath)
            $slideResult.rendered = $true
        } catch {
            $slideResult.error = $_.Exception.Message
            $report.errors += "Render slide ${index}: $($_.Exception.Message)"
        }
    }
    $report.render_complete = $report.slide_count -gt 0 -and @($report.slides | Where-Object { !$_.rendered }).Count -eq 0
    if ($report.slide_count -eq 0) { $report.errors += 'The presentation has no slides.' }
    Close-OwnedPresentation $final

    if ($TestEdits) {
        $scratchPath = Join-Path $paths.output 'edit_test.pptx'
        [IO.File]::Copy($paths.input, $scratchPath, $false)
        (Get-Item -LiteralPath $scratchPath).IsReadOnly = $false
        $report.edit_test_path = $scratchPath
        $scratch = Open-OwnedPresentation $scratchPath $false
        $targets = @()
        for ($index = 1; $index -le $scratch.Slides.Count; $index++) {
            $targets += @(Get-ShapeTargets $scratch.Slides.Item($index).Shapes $index)
        }
        $textTarget = $null; $fillTarget = $null; $pictureTarget = $null; $replaceTarget = $null
        $counts = [ordered]@{ text_frames = 0; fillable_shapes = 0; pictures = 0; groups = 0; top_level_groups = 0; nested_groups = 0 }
        foreach ($target in $targets) {
            $shape = $target.shape
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
                $counts.text_frames++
                if (!$textTarget) { $textTarget = $target }
            }
            if ($shape.Type -in @(1, 17)) {
                $counts.fillable_shapes++
                if (!$fillTarget) { $fillTarget = $target }
            }
            if ($shape.Type -in @(11, 13)) {
                $counts.pictures++
                if (!$pictureTarget) { $pictureTarget = $target }
                if (!$replaceTarget -and $target.top_level) { $replaceTarget = $target }
            }
            if ($shape.Type -eq 6) {
                $counts.groups++
                if ($target.top_level) { $counts.top_level_groups++ } else { $counts.nested_groups++ }
            }
        }
        $report.object_counts = $counts
        $report.object_scan_complete = $true
        $testTargetCounts = @{ text = $counts.text_frames; fill = $counts.fillable_shapes; picture_move = $counts.pictures }
        if (!$replaceTarget) { $replaceTarget = $pictureTarget }

        foreach ($name in @('text', 'fill', 'picture_move')) {
            $target = switch ($name) { 'text' { $textTarget } 'fill' { $fillTarget } 'picture_move' { $pictureTarget } }
            if (!$target) {
                $reason = switch ($name) {
                    'text' { 'No nonempty native text frame exists.' }
                    'fill' { 'No native AutoShape or text box exists.' }
                    'picture_move' { 'No native or linked picture exists.' }
                }
                $report.edit_tests[$name] = New-TestResult 'not_applicable' $reason
                $report.edit_tests[$name].target_count = $testTargetCounts[$name]
                continue
            }
            $result = New-TestResult 'running' $null
            $report.edit_tests[$name] = $result
            $result.target_count = $testTargetCounts[$name]
            $result.attempted = $true; $result.reverted = $false
            $result.detail = [ordered]@{ slide = $target.slide; shape_path = $target.path }
            $shape = $target.shape
            $restore = $null
            try {
                switch ($name) {
                    'text' {
                        $range = $shape.TextFrame.TextRange
                        $original = [string]$range.Text
                        $first = $original.Substring(0, 1)
                        $letter = 'Q'; if ($first -ceq 'Q') { $letter = 'R' }
                        $restore = { $range.Characters(1, 1).Text = $first }.GetNewClosure()
                        $range.Characters(1, 1).Text = $letter
                        $result.changed = ([string]$range.Text -ceq ($letter + $original.Substring(1)))
                        & $restore
                        $result.reverted = ([string]$range.Text -ceq $original)
                        $result.detail.character_count = $original.Length
                    }
                    'fill' {
                        $original = $shape.Fill.ForeColor.RGB
                        $originalFillType = $shape.Fill.Type
                        $originalVisible = $shape.Fill.Visible
                        $originalColorType = $shape.Fill.ForeColor.Type
                        $shape.PickUp()
                        $restore = { $shape.Apply() }.GetNewClosure()
                        $color = $original -bxor 0xFFFFFF
                        $shape.Fill.Solid()
                        $shape.Fill.Visible = -1
                        $shape.Fill.ForeColor.RGB = $color
                        $result.changed = ($shape.Fill.ForeColor.RGB -eq $color -and $shape.Fill.Type -eq 1 -and $shape.Fill.Visible -eq -1)
                        & $restore
                        $result.reverted = ($shape.Fill.ForeColor.RGB -eq $original -and $shape.Fill.Type -eq $originalFillType -and
                            $shape.Fill.Visible -eq $originalVisible -and $shape.Fill.ForeColor.Type -eq $originalColorType)
                        $result.detail.original_rgb = $original; $result.detail.test_rgb = $color
                        $result.detail.original_fill_type = $originalFillType; $result.detail.original_visible = $originalVisible
                        $result.detail.restore_method = 'PickUp_Apply'
                    }
                    'picture_move' {
                        $original = [double]$shape.Left
                        $restore = { $shape.Left = $original }.GetNewClosure()
                        $shape.Left = $original + 3
                        $result.changed = ([Math]::Abs($shape.Left - ($original + 3)) -lt 0.05)
                        & $restore
                        $result.reverted = ([Math]::Abs($shape.Left - $original) -lt 0.05)
                        $result.detail.original_left_pt = $original; $result.detail.delta_pt = 3
                    }
                }
            } catch { $result.error = $_.Exception.Message }
            finally {
                if ($restore -and !$result.reverted) {
                    try { & $restore } catch { $result.error = "$($result.error); restore: $($_.Exception.Message)" }
                }
            }
            Set-TestOutcome $result
        }

        $replacement = New-TestResult 'not_applicable' 'No native or linked picture exists.'
        $replacement.target_count = $counts.pictures
        $report.edit_tests.picture_replace = $replacement
        if ($replaceTarget) {
            $replacement.status = 'running'; $replacement.reason = $null; $replacement.attempted = $true; $replacement.reverted = $false
            $shape = $replaceTarget.shape
            $slideNumber = $replaceTarget.slide
            $slide = $scratch.Slides.Item($slideNumber)
            $originalId = $shape.Id
            $originalCount = $slide.Shapes.Count
            $originalPictureCount = @(Get-ShapeTargets $slide.Shapes $slideNumber | Where-Object { $_.shape.Type -in @(11, 13) }).Count
            $originalGeometry = @($shape.Left, $shape.Top, $shape.Width, $shape.Height, $shape.Rotation)
            $exportPath = Join-Path $workDir 'picture_original.png'
            $replacement.detail = [ordered]@{ slide = $slideNumber; shape_path = $replaceTarget.path; exported_image_path = $exportPath; method = $null; com_replace_supported = $null; com_replace_error = $null; restore_method = 'discard_unsaved_scratch_and_reopen' }
            $exportHash = $null
            try {
                $shape.Export($exportPath, 2)
                $exportHash = Get-QaHash $exportPath
                try {
                    $shape.PictureFormat.Replace($exportPath)
                    $replacement.detail.com_replace_supported = $true
                    $replacement.detail.method = 'PictureFormat.Replace'
                    $replacement.changed = ($shape.Type -in @(11, 13))
                } catch {
                    if ($_.Exception -is [Management.Automation.RuntimeException] -and $_.FullyQualifiedErrorId -like '*MethodNotFound*') {
                        $replacement.detail.com_replace_supported = $false
                    }
                    $replacement.detail.com_replace_error = $_.Exception.Message
                    $replacement.unavailable = 'PictureFormat.Replace could not be used; scratch delete/reinsert fallback was used.'
                    $replacement.detail.method = 'delete_reinsert'
                    $shape.Delete()
                    $inserted = $slide.Shapes.AddPicture($exportPath, 0, -1, $originalGeometry[0], $originalGeometry[1], $originalGeometry[2], $originalGeometry[3])
                    $replacement.changed = ($inserted.Type -eq 13 -and $inserted.Id -ne $originalId)
                }
                $replacement.detail.picture_count_after = @(Get-ShapeTargets $slide.Shapes $slideNumber | Where-Object { $_.shape.Type -in @(11, 13) }).Count
                $replacement.detail.picture_count_before = $originalPictureCount
                $replacement.changed = $replacement.changed -and $replacement.detail.picture_count_after -eq $originalPictureCount
            } catch { $replacement.error = $_.Exception.Message }
            finally {
                # Restore the actual original picture, including crop/effects, from the untouched scratch file.
                Close-OwnedPresentation $scratch
                $scratch = Open-OwnedPresentation $scratchPath $false
            }
            try {
                if ($exportHash) {
                    $restoredSlide = $scratch.Slides.Item($slideNumber)
                    $restored = $null
                    foreach ($target in @(Get-ShapeTargets $restoredSlide.Shapes $slideNumber)) {
                        if ($target.shape.Id -eq $originalId) { $restored = $target.shape; break }
                    }
                    if (!$restored) { throw 'Original picture ID not found after restoration.' }
                    $restoredPath = Join-Path $workDir 'picture_restored.png'
                    $restored.Export($restoredPath, 2)
                    $geometry = @($restored.Left, $restored.Top, $restored.Width, $restored.Height, $restored.Rotation)
                    $geometryEqual = $true
                    for ($index = 0; $index -lt 5; $index++) {
                        if ([Math]::Abs($geometry[$index] - $originalGeometry[$index]) -ge 0.05) { $geometryEqual = $false }
                    }
                    $replacement.detail.restored_image_path = $restoredPath
                    $replacement.detail.original_image_sha256 = $exportHash
                    $replacement.detail.restored_image_sha256 = Get-QaHash $restoredPath
                    $replacement.reverted = $geometryEqual -and $restoredSlide.Shapes.Count -eq $originalCount -and $replacement.detail.restored_image_sha256 -eq $exportHash
                }
            } catch { $replacement.error = "$($replacement.error); restoration verification: $($_.Exception.Message)" }
            Set-TestOutcome $replacement
        }

        # Find groups afresh because replacement restoration invalidates earlier COM references.
        $groupTarget = $null
        $groupsFound = 0
        for ($index = 1; $index -le $scratch.Slides.Count; $index++) {
            foreach ($target in @(Get-ShapeTargets $scratch.Slides.Item($index).Shapes $index)) {
                if ($target.shape.Type -eq 6) {
                    $groupsFound++
                    if (!$groupTarget -and $target.top_level -and $target.shape.GroupItems.Count -ge 2) { $groupTarget = $target }
                }
            }
        }
        $group = New-TestResult 'not_applicable' 'Recursive slide-shape scan found no groups, including nested groups.'
        $group.target_count = $counts.groups
        $group.detail = [ordered]@{ groups_found_before_test = $groupsFound; scan_scope = 'slide_shapes_recursive' }
        $report.edit_tests.group_ungroup = $group
        if (!$groupTarget -and ($counts.groups -gt 0 -or $groupsFound -gt 0)) {
            $group.status = 'unavailable'
            $group.reason = 'Groups exist, but no safe top-level ungroup target was found.'
            $group.unavailable = 'Nested or missing scratch groups cannot be certified by the top-level ungroup test.'
        }
        if ($groupTarget) {
            $group.status = 'running'; $group.reason = $null; $group.attempted = $true
            $group.detail = [ordered]@{ slide = $groupTarget.slide; shape_path = $groupTarget.path; member_ids = @(); persisted = $false; groups_found_before_test = $groupsFound; scan_scope = 'slide_shapes_recursive' }
            try {
                $groupSlide = $scratch.Slides.Item($groupTarget.slide)
                $countBefore = $groupSlide.Shapes.Count
                $memberCount = $groupTarget.shape.GroupItems.Count
                $ungrouped = $groupTarget.shape.Ungroup()
                for ($index = 1; $index -le $ungrouped.Count; $index++) { $group.detail.member_ids += $ungrouped.Item($index).Id }
                $group.detail.expected_shape_count = $countBefore + $memberCount - 1
                $group.changed = $ungrouped.Count -eq $memberCount -and $memberCount -ge 2 -and $groupSlide.Shapes.Count -eq $group.detail.expected_shape_count
                $group.status = 'failed'; if ($group.changed) { $group.status = 'pending_reopen' }
            } catch { $group.status = 'error'; $group.error = $_.Exception.Message }
        }

        $save = New-TestResult 'running' $null
        $save.target_count = $scratch.Slides.Count
        $save.attempted = $true; $save.reverted = $false
        $save.detail = [ordered]@{ persisted_edit = $false; reverted_edit = $false }
        $report.edit_tests.save_reopen = $save
        try {
            $probeName = 'QA_SAVE_' + [Guid]::NewGuid().ToString('N').ToUpperInvariant()
            $probeValue = 'PERSISTED'
            $tagCount = $scratch.Slides.Item(1).Tags.Count
            $scratchHashBefore = Get-QaHash $scratchPath
            $scratch.Slides.Item(1).Tags.Add($probeName, $probeValue)
            $scratch.Save()
            $save.detail.probe_tag = $probeName
            $save.detail.edited_copy_sha256 = Get-QaHash $scratchPath
            $save.changed = $scratch.Saved -eq -1 -and $scratchHashBefore -ne $save.detail.edited_copy_sha256
            Close-OwnedPresentation $scratch
            $scratch = Open-OwnedPresentation $scratchPath $false
            $save.detail.persisted_edit = $scratch.Slides.Item(1).Tags.Item($probeName) -ceq $probeValue
            if ($scratch.Slides.Item(1).Tags.Item($probeName)) { $scratch.Slides.Item(1).Tags.Delete($probeName) }
            $scratch.Save()
            Close-OwnedPresentation $scratch
            $scratch = Open-OwnedPresentation $scratchPath $true
            $save.detail.reverted_edit = $scratch.Slides.Item(1).Tags.Item($probeName) -eq '' -and $scratch.Slides.Item(1).Tags.Count -eq $tagCount
            $save.reverted = $save.detail.reverted_edit
            $save.passed = $save.changed -and $save.detail.persisted_edit -and $save.reverted -and $scratch.ReadOnly -eq -1 -and $scratch.Slides.Count -eq $report.slide_count -and
                [Math]::Abs($scratch.PageSetup.SlideWidth - $report.width_pt) -lt 0.05 -and
                [Math]::Abs($scratch.PageSetup.SlideHeight - $report.height_pt) -lt 0.05
            $save.detail.reopened_slide_count = $scratch.Slides.Count
            $save.detail.bytes = (Get-Item -LiteralPath $scratchPath).Length
            $save.status = 'failed'; if ($save.passed) { $save.status = 'passed' }
            if ($group.changed -and $null -eq $group.error) {
                $groupSlide = $scratch.Slides.Item($group.detail.slide)
                $ids = @(); for ($index = 1; $index -le $groupSlide.Shapes.Count; $index++) { $ids += $groupSlide.Shapes.Item($index).Id }
                $group.detail.persisted = $groupSlide.Shapes.Count -eq $group.detail.expected_shape_count -and
                    @($group.detail.member_ids | Where-Object { $_ -notin $ids }).Count -eq 0
                $group.passed = $save.passed -and $group.detail.persisted
                $group.status = 'failed'; if ($group.passed) { $group.status = 'passed' }
            }
        } catch {
            $save.status = 'error'; $save.error = $_.Exception.Message
            if ($group.status -eq 'pending_reopen') { $group.status = 'error'; $group.error = 'Could not verify ungroup persistence because save/reopen failed.' }
        }
        Close-OwnedPresentation $scratch
    }
} catch {
    $report.errors += $_.Exception.Message
} finally {
    foreach ($presentation in @($owned.ToArray())) {
        try { Close-OwnedPresentation $presentation } catch { $report.errors += "Close script-owned presentation: $($_.Exception.Message)" }
    }
    # Release our automation handle; never call Application.Quit or close other presentations.
    if ($null -ne $app) {
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
        catch { $report.errors += "Release application handle: $($_.Exception.Message)" }
    }
    try {
        $report.source_sha256_after = Get-QaHash $paths.input
        $report.source_unchanged = $sourceHash -eq $report.source_sha256_after
        if (!$report.source_unchanged) { throw 'Source SHA256 changed during verification.' }
    } catch { $report.errors += "Source invariant: $($_.Exception.Message)" }
    foreach ($result in $report.edit_tests.Values) {
        if ($result.status -in @('running', 'pending_reopen')) {
            $result.status = 'error'; $result.passed = $false
            if ($null -eq $result.error) { $result.error = 'Execution was interrupted before this test could finish; see report.errors.' }
        }
    }
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    $report.status = 'completed'
    if ($report.errors.Count -gt 0 -or !$report.render_complete) { $report.status = 'failed' }
    elseif (@($report.edit_tests.Values | Where-Object { $_.status -in @('failed', 'error', 'unavailable', 'not_run', 'pending_reopen') }).Count -gt 0) {
        $report.status = 'completed_with_test_errors'
    }
    $report.rendered_files = @($report.slides | Where-Object { $_.rendered } | ForEach-Object { $_.render_path })
    # A verified absence of groups is acceptable without marking the individual ungroup test passed.
    $report.passed = Get-QaPassed $report ([bool]$TestEdits)
    # Write a complete JSON file, then publish without replacing an existing report.
    $temporaryReport = Join-Path $workDir 'report.json.tmp'
    $json = $report | ConvertTo-Json -Depth 15
    $stream = [IO.File]::Open($temporaryReport, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($json)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    [IO.File]::Move($temporaryReport, $reportPath)
}
Write-Output $reportPath
if ($report.status -ne 'completed') { throw "PowerPoint verification status: $($report.status). See $reportPath" }
