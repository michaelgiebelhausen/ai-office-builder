param([Parameter(Position=0)][string]$Cowork, [ValidateSet('professional','student')][string]$Mode, [string]$Code, [string]$Json)
. "$PSScriptRoot/common.ps1"
try {
    if (!$Cowork -or !$Mode) {throw 'Cowork path and --mode are required'}
    $root=FullPath $Cowork
    $fail=New-Object 'System.Collections.Generic.List[string]'; $warn=New-Object 'System.Collections.Generic.List[string]'
    function Need([string]$Base,[string]$Name,[bool]$Directory=$false) {
        $p=Join-Path $Base $Name
        if (!(Test-Path -LiteralPath $p -PathType $(if ($Directory) {'Container'} else {'Leaf'}))) {$fail.Add("Missing $p")}
    }
    if (!(Test-Path -LiteralPath $root -PathType Container)) {$fail.Add("Not a folder: $root")}
    else {
        Need $root 'start_here.md'; Need $root '.claude/CLAUDE.md'
        $route=''; if (Test-Path -LiteralPath (Join-Path $root '.claude/CLAUDE.md') -PathType Leaf) {$route=Get-Content -Raw -LiteralPath (Join-Path $root '.claude/CLAUDE.md')}
        foreach ($sub in @('00_Inbox','00_Inbox/to_sort','00_Inbox/_duplicates','00_Inbox/_migration','01_Library','01_Library/raw_human','01_Library/raw_AI')) {Need $root $sub $true}
        Need $root '01_Library/CLAUDE.md'
        foreach ($top in (Get-ChildItem -LiteralPath $root -Directory -Force)) {
            $d=$top.Name; $p=$top.FullName; if ($d -eq '.claude') {continue}
            if ($d -notmatch '^(\d{2})_(.+)$') {$fail.Add("Invalid top-level folder: $d");continue}
            $n=[int]$Matches[1]
            if ($n -gt 39 -or ($Mode -eq 'student' -and $n -ge 30)) {$fail.Add("Invalid range: $d");continue}
            if ($n -ge 10 -and $n -le 19) {
                Need $p '.claude/CLAUDE.md'; foreach ($drawer in @('Projects','Resources','Archive')) {Need $p $drawer $true}; Need $p 'Resources/context.md'
                if (!$route.Contains($d)) {$fail.Add("Root routing missing $d")}
                Need $root "01_Library/$($d)_Wiki" $true; Need $root "01_Library/$($d)_Wiki/index.md"
                if ($Mode -eq 'student' -and $d -match 'class') {
                    foreach ($sub in @('major_classes','gened_classes','job_search')) {Need $p "Archive/$sub" $true}
                    foreach ($course in (Get-ChildItem -LiteralPath $p -Directory -Force | Where-Object Name -notin @('.claude','Projects','Resources','Archive'))) {Need $course.FullName 'Projects' $true;Need $course.FullName 'Resources' $true;Need $course.FullName 'Resources/context.md'}
                }
            } elseif ($n -ge 20) {
                Need $p 'Projects' $true; Need $p 'Resources' $true
                if ($n -lt 30) {
                    Need $p '.claude/CLAUDE.md'
                    if (Test-Path -LiteralPath (Join-Path $p 'Projects') -PathType Container) {
                        foreach ($project in (Get-ChildItem -LiteralPath (Join-Path $p 'Projects') -Directory)) {foreach ($stage in @('01_brief','02_spec','03_build','04_output')) {Need $project.FullName $stage $true}}
                    }
                }
            }
        }
        foreach ($entry in (Walk $root -SkipGit)) {
            $rel=$entry.Path.Substring($root.Length).TrimStart('\','/')
            if ($entry.Kind -eq 'git') {$fail.Add("Git repo inside Cowork: $rel");continue}
            if ($entry.Kind -eq 'link') {$fail.Add("Linked path requires review: $rel");continue}
            if ($entry.Kind -eq 'dir' -and @($rel -split '[/\\]').Count -gt 5) {$fail.Add("Folder deeper than 5 levels: $rel")}
            if ($entry.Kind -eq 'file' -and $entry.Item.Name -eq 'CLAUDE.md' -and @(Get-Content -LiteralPath $entry.Path).Count -ge 200) {$fail.Add("CLAUDE.md must be under 200 lines: $rel")}
            if ($entry.Item.Name.Contains(' ') -or $entry.Item.Name -match 'final|\bcopy\b|\(\d+\)') {$warn.Add("Optional rename: $rel")}
            if ($entry.Kind -eq 'dir' -and (Split-Path -Leaf (Split-Path -Parent $entry.Path)) -eq 'Projects' -and $entry.Item.Name -notmatch '^\d{4}_Q[1-4]_') {$warn.Add("Optional project naming: $rel")}
        }
    }
    if ($Code) {
        $c=FullPath $Code
        if (!(Test-Path -LiteralPath $c -PathType Container)) {$fail.Add("Code folder not found: $c")}
        elseif ((Within $c $root) -or $c -match '(^|[/\\])OneDrive[^/\\]*([/\\]|$)') {$fail.Add('Code must be outside Cowork and OneDrive')}
    }
    $result=@{pass=($fail.Count -eq 0);problems=@($fail.ToArray());suggestions=@($warn.ToArray())}
    Write-Output "STRUCTURE: $(if ($result.pass) {'PASS'} else {"$($fail.Count) problem(s)"})"
    foreach ($message in $fail) {Write-Output "  FAIL $message"}
    Write-Output "SUGGESTIONS: $($warn.Count)"; foreach ($message in $warn) {Write-Output "  $message"}
    if ($Json) {WriteNewJson (FullPath $Json) $result}
    if ($result.pass) {exit 0}; exit 1
} catch {Write-Output "STOPPED: $_";exit 1}
