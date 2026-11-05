param([Parameter(Position=0, ValueFromRemainingArguments=$true)][string[]]$Roots, [string]$Out, [Alias('max-files')][int]$MaxFiles=200000)
. "$PSScriptRoot/common.ps1"
try {
    if (!$Roots -or !$Out -or $MaxFiles -lt 1) { throw 'roots, --out and positive --max-files are required' }
    $skip = @('node_modules','__pycache__','.venv','venv','AppData','Library','Application Data','$RECYCLE.BIN','System Volume Information','.Trash','99_Private','.obsidian','Pictures','Photos Library.photoslibrary','.cache')
    $keywords = @{invoice='invoices';receipt='receipts';statement='statements';syllabus='syllabi';lecture='lecture notes';transcript='transcripts';contract='contracts';proposal='proposals';resume='resumes';cover_letter='cover letters';tax='tax documents';w2='tax documents';brief='briefs';meeting='meeting notes';notes='notes'}
    $mediaExt = @('.mp4','.mov','.m4v','.avi','.mkv','.wav','.mp3','.aif','.aiff','.m4a','.braw','.r3d','.cr2','.cr3','.nef','.arw','.dng','.psd','.prproj')
    $rootInfo=@{}; $extensions=@{}; $names=@{}; $sizes=@{}; $courses=@{}; $folders=@{}; $media=@{}
    $repos=New-Object 'System.Collections.Generic.List[string]'; $spaces=New-Object 'System.Collections.Generic.List[string]'; $deep=New-Object 'System.Collections.Generic.List[string]'
    $n=0
    foreach ($r in $Roots) {
        if ($n -ge $MaxFiles) { break }
        $root=FullPath $r
        if (!(Test-Path -LiteralPath $root -PathType Container) -or (Linked $root)) { $rootInfo[$root]=@{error='not a folder or not accessible'}; continue }
        $rc=0; [long]$rs=0
        $pending=New-Object 'System.Collections.Generic.Stack[string]'; $pending.Push($root)
        while ($pending.Count -and $n -lt $MaxFiles) {
            $base=$pending.Pop()
            $items=@(Get-ChildItem -LiteralPath $base -Force)
            if (@($items | Where-Object Name -eq '.git').Count) { $repos.Add($base); continue }
            foreach ($item in $items) {
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
                if ($item.PSIsContainer) {
                    if ($item.Name -notin $skip -and !$item.Name.StartsWith('.')) { $pending.Push($item.FullName) }
                    continue
                }
                if ($item.Name.StartsWith('.') -or $item.Name -in @('desktop.ini','thumbs.db')) { continue }
                $n++; $rc++; $rs+=$item.Length
                $ext=$item.Extension.ToLowerInvariant(); if (!$ext) {$ext='(none)'}
                $extensions[$ext]++
                $name=$item.Name.ToLowerInvariant(); if (!$names.ContainsKey($name)) {$names[$name]=@()}; $names[$name]+=$item.FullName
                $size=[string]$item.Length; if (!$sizes.ContainsKey($size)) {$sizes[$size]=@()}; $sizes[$size]+=$item.FullName
                if (!$folders.ContainsKey($base)) {$folders[$base]=@()}; $folders[$base]+=$item.Name
                if ($ext -in $mediaExt) {$media[$base]+=$item.Length}
                if ($item.Name.Contains(' ') -and $spaces.Count -lt 5000) {$spaces.Add($item.FullName)}
                if (@($base.Substring($root.Length).TrimStart('\','/') -split '[/\\]').Count -ge 5) {$deep.Add($item.FullName)}
                foreach ($match in [regex]::Matches(($item.Name+' '+(Split-Path -Leaf $base)), '(?<![A-Z0-9])([A-Z]{2,4})[ _-]?(\d{4})(?!\d)')) {$courses[$match.Groups[1].Value+'_'+$match.Groups[2].Value]++}
                if ($n -ge $MaxFiles) {break}
            }
        }
        $rootInfo[$root]=@{files=$rc; bytes=$rs}
    }
    $dups=@(); foreach ($size in $sizes.Keys) {
        if ($sizes[$size].Count -lt 2) {continue}; $hashes=@{}
        foreach ($p in $sizes[$size]) {$h=Hash $p; if (!$hashes.ContainsKey($h)) {$hashes[$h]=@()}; $hashes[$h]+=$p}
        foreach ($h in $hashes.Keys) {if ($hashes[$h].Count -gt 1) {$dups+=@{size=[long]$size;paths=@($hashes[$h])}}}
    }
    $clashes=@($names.Keys | Where-Object {$names[$_].Count -gt 1} | ForEach-Object {@{name=$_;count=$names[$_].Count;paths=@($names[$_] | Select-Object -First 10)}} | Sort-Object {-$_.count} | Select-Object -First 100)
    $clusters=@(); foreach ($folder in $folders.Keys) {
        $fs=$folders[$folder]; if ($fs.Count -lt 5) {continue}; $kw=@{}; $ex=@{}
        foreach ($f in $fs) {foreach ($key in $keywords.Keys) {if ($f.ToLowerInvariant().Contains($key)) {$kw[$keywords[$key]]++}}; $ex[[IO.Path]::GetExtension($f).ToLowerInvariant()]++}
        $tk=@($kw.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1); $te=@($ex.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1)
        $clusters+=@{folder=$folder;files=$fs.Count;top_keyword=$(if ($tk.Count) {@($tk[0].Key,$tk[0].Value)} else {$null});top_extension=@($te[0].Key,$te[0].Value)}
    }
    $extPairs=@($extensions.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 30 | ForEach-Object {,@($_.Key,$_.Value)})
    $coursePairs=@($courses.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 20 | ForEach-Object {,@($_.Key,$_.Value)})
    $result=@{inspection_errors=@();roots=$rootInfo;total_files=$n;truncated=($n -ge $MaxFiles);extensions=$extPairs;course_codes=$coursePairs;clusters=@($clusters | Sort-Object {-$_.files} | Select-Object -First 60);git_repos=@($repos.ToArray());media_folders=@($media.Keys | Where-Object {$media[$_] -ge 1e9} | ForEach-Object {@{folder=$_;gb=[math]::Round($media[$_]/1e9,2)}});name_clashes=$clashes;likely_duplicates=@($dups | Select-Object -First 200);spaces_in_names=@{count=$spaces.Count;sample=@($spaces | Select-Object -First 15)};deep_paths=@{count=$deep.Count;sample=@($deep | Select-Object -First 15)}}
    WriteNewJson (FullPath $Out) $result
    Write-Output "Scanned $n files across $($Roots.Count) folder(s). $($repos.Count) git repos, $($dups.Count) duplicate groups, $($clashes.Count) repeated names. Summary written to $Out"
    exit 0
} catch {Write-Output "STOPPED: $_"; exit 1}
