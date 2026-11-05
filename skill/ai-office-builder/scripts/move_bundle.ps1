# Usage mirrors Python: manifest.json --cowork PATH --dry-run; --undo FILE.
# PowerShell accepts -Cowork, -DryRun, -Undo too. Windows PowerShell 5.1+.
param([Parameter(Position=0)][string]$Manifest, [string]$Cowork, [Alias('dry-run')][switch]$DryRun, [string]$Undo)
. "$PSScriptRoot/common.ps1"
try {
    if ($Undo) {
        $u = Get-Content -Raw -LiteralPath $Undo | ConvertFrom-Json
        $log = Join-Path $u.cowork '00_Inbox/_migration/migration_log.md'
        $skipped = 0; $back = 0
        foreach ($row in $u.moves) {
            if (!(Test-Path -LiteralPath $row.src) -and (Test-Path -LiteralPath $row.dst)) { continue }
            if (!(Test-Path -LiteralPath $row.src) -or (Test-Path -LiteralPath $row.dst) -or (Linked $row.src) -or (Linked $row.dst)) {
                Write-Output "skip (missing, linked or occupied): $($row.src) -> $($row.dst)"; $skipped++; continue
            }
            if ($row.hash -and (Hash $row.src) -ne $row.hash) { Write-Output 'skip (changed contents)'; $skipped++; continue }
            Write-Output "UNDO $($row.src) -> $($row.dst)"
            if (!$DryRun) {
                if (Linked $log) { throw 'linked_metadata' }
                LogLine $log "UNDO INTENT $($row.src) -> $($row.dst)"
                MoveSafe $row.src $row.dst
                LogLine $log "UNDO MOVED $($row.src) -> $($row.dst)"
            }
            $back++
        }
        Write-Output "Restored $back item(s); skipped $skipped."
        if ($skipped) { exit 1 }; exit 0
    }
    if (!$Manifest -or !$Cowork) { throw 'manifest and --cowork are required' }
    $Cowork = FullPath $Cowork
    $m = Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json
    if ($m.bundle -notmatch '^[A-Za-z0-9_-]+$' -or !$m.moves -or @($m.moves).Count -eq 0) { throw 'Invalid bundle or empty moves' }
    $problems = New-Object 'System.Collections.Generic.List[string]'
    $pairs = New-Object 'System.Collections.Generic.List[object]'
    foreach ($row in $m.moves) {
        if (![IO.Path]::IsPathRooted($row.src)) { throw 'source paths must be absolute' }
        $s = FullPath $row.src
        $absolute = [IO.Path]::IsPathRooted($row.dst)
        $d = FullPath $(if ($absolute) { $row.dst } else { Join-Path $Cowork $row.dst })
        if (!$absolute -and !(Within $d $Cowork)) { $problems.Add('destination_escape') }
        $row | Add-Member -NotePropertyName _src -NotePropertyValue $s
        $row | Add-Member -NotePropertyName _dst -NotePropertyValue $d
        if (!(Test-Path -LiteralPath $s)) { $problems.Add('missing_source') }
        if ((Linked $s) -or (Linked $d)) { $problems.Add('linked_path') }
        if (Test-Path -LiteralPath $d) { $problems.Add($(if (Same $s $d) { 'duplicate' } else { 'clash' })) }
        if ((Within $d $s) -or (Within $s $d)) { $problems.Add('overlapping_paths') }
        if ([IO.Path]::GetPathRoot($s) -ne [IO.Path]::GetPathRoot($d)) { $problems.Add('cross_filesystem') }
        $parent = Split-Path -Parent $d
        while (!(Test-Path -LiteralPath $parent)) { $parent = Split-Path -Parent $parent }
        if (!(Test-Path -LiteralPath $parent -PathType Container)) { $problems.Add('parent_is_file') }
        if (Within $d $Cowork) {
            $depth = @($d.Substring($Cowork.Length).TrimStart('\','/') -split '[/\\]').Count
            $isDir = Test-Path -LiteralPath $s -PathType Container
            if ($depth -gt $(if ($isDir) {5} else {6})) { $problems.Add('too_deep') }
            if ($isDir) {
                if (Test-Path -LiteralPath (Join-Path $s '.git')) { $problems.Add('git_in_cowork') }
                foreach ($entry in (Walk $s)) {
                    $extra = @($entry.Path.Substring($s.Length).TrimStart('\','/') -split '[/\\]').Count
                    if ($entry.Kind -eq 'link') { $problems.Add('linked_path') }
                    if ($entry.Item.Name -eq '.git') { $problems.Add('git_in_cowork') }
                    if (($depth + $extra) -gt $(if ($entry.Kind -eq 'dir') {5} else {6})) { $problems.Add('too_deep') }
                }
            }
        }
        $metadata = Join-Path $Cowork '00_Inbox/_migration'
        if ((Within $d $metadata) -or (Within $s $metadata) -or (Within $metadata $s)) { $problems.Add('reserved_metadata') }
        foreach ($prior in $pairs) {
            if ($d -eq $prior.dst) { $problems.Add($(if (Same $s $prior.src) {'duplicate_in_bundle'} else {'clash_in_bundle'})) }
            elseif ((Within $d $prior.dst) -or (Within $prior.dst $d) -or (Within $s $prior.src) -or (Within $prior.src $s) -or (Within $d $prior.src) -or (Within $prior.src $d) -or (Within $s $prior.dst) -or (Within $prior.dst $s)) { $problems.Add('overlapping_bundle') }
        }
        $pairs.Add(@{src=$s; dst=$d})
    }
    $meta = Join-Path $Cowork '00_Inbox/_migration'
    $undoPath = Join-Path $meta "undo_$($m.bundle).json"
    $log = Join-Path $meta 'migration_log.md'
    if (Test-Path -LiteralPath $undoPath) { $problems.Add('bundle_already_used') }
    if ((Linked $undoPath) -or (Linked $log)) { $problems.Add('linked_metadata') }
    foreach ($problem in $problems) { Write-Output "[$problem]" }
    if ($DryRun) {
        Write-Output "Dry run: $(@($m.moves).Count) move(s) planned for bundle $($m.bundle)."
        $m.moves | Select-Object -First 50 | ForEach-Object { Write-Output "$($_._src) -> $($_._dst)" }
        if ($problems.Count) { exit 1 }; exit 0
    }
    if ($problems.Count) { Write-Output 'Refusing to run. Resolve all problems; route duplicates to 00_Inbox/_duplicates/.'; exit 1 }
    [void][IO.Directory]::CreateDirectory($meta)
    $undoMoves = @($m.moves | ForEach-Object { @{src=$_._dst; dst=$_._src; hash=$(if (Test-Path -LiteralPath $_._src -PathType Leaf) {Hash $_._src} else {$null})} })
    [array]::Reverse($undoMoves)
    WriteNewJson $undoPath @{bundle=$m.bundle; cowork=$Cowork; moves=$undoMoves}
    LogLine $log "`n## $(Get-Date -Format o) bundle $($m.bundle)`n$($m.description)`nUndo: $undoPath"
    $done = 0
    foreach ($row in $m.moves) {
        LogLine $log "INTENT $($row._src) -> $($row._dst)"
        MoveSafe $row._src $row._dst
        $done++
        LogLine $log "MOVED $($row._src) -> $($row._dst) $($row.note)"
    }
    Write-Output "Moved $done item(s). Logged. Undo file: $undoPath"
    exit 0
} catch { Write-Output "STOPPED: $_. Existing undo plans and log entries are preserved."; exit 1 }
