# Native Windows implementation; dot-source common.ps1 first.
$TextExtensions=@('.md','.markdown','.txt','.html','.htm','.json','.yaml','.yml','.toml','.ini','.cfg','.ps1','.py','.sh')
$OpaqueExtensions=@('.xlsx','.xls','.pptx','.ppt','.docx','.doc','.blend','.prproj','.aep','.indd','.lnk','.url')
$ReferenceSkip=@('.git','.obsidian','99_Private','node_modules','.venv','__pycache__','_migration')
function TreeFingerprint([string]$Path) {
    if (@($Path -split '[/\\]' | Where-Object {$_ -in @('99_Private','.obsidian')}).Count) {throw 'private_path_in_bundle'}
    if (Linked $Path) {throw 'linked_path'}
    if (!(Test-Path -LiteralPath $Path)) {throw "missing_source: $Path"}
    if (Test-Path -LiteralPath $Path -PathType Leaf) {return ,@(@{path='.';kind='file';sha256=(Hash $Path).ToLowerInvariant()})}
    $rows=New-Object 'System.Collections.Generic.List[object]';$rows.Add(@{path='.';kind='dir'})
    # Do not enter excluded private material even when a whole folder was selected.
    $stack=New-Object 'System.Collections.Generic.Stack[string]';$stack.Push($Path)
    while ($stack.Count) {
        foreach ($item in (Get-ChildItem -LiteralPath $stack.Pop() -Force)) {
            if ($item.Name -in @('99_Private','.obsidian')) {throw 'private_path_in_bundle'}
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'linked_path'}
            $rel=$item.FullName.Substring($Path.Length).TrimStart('\','/').Replace('\','/')
            if ($item.PSIsContainer) {$rows.Add(@{path=$rel;kind='dir'});$stack.Push($item.FullName)}
            else {$rows.Add(@{path=$rel;kind='file';sha256=(Hash $item.FullName).ToLowerInvariant()})}
        }
    }
    return ,@($rows.ToArray() | Sort-Object -Property { $_.path } -CaseSensitive)
}
function Canonical($Value) {
    if ($null -eq $Value) {return 'null'}
    if ($Value -is [string] -or $Value -is [ValueType]) {return (ConvertTo-Json -InputObject $Value -Compress)}
    if ($Value -is [Collections.IDictionary]) {
        $parts=@(foreach ($key in ($Value.Keys | Sort-Object -CaseSensitive)) {(ConvertTo-Json -InputObject ([string]$key) -Compress)+':'+(Canonical $Value[$key])})
        return '{'+($parts -join ',')+'}'
    }
    if ($Value -is [pscustomobject]) {
        $map=@{};foreach ($p in $Value.PSObject.Properties) {$map[$p.Name]=$p.Value};return Canonical $map
    }
    $parts=@(foreach ($v in $Value) {Canonical $v});return '['+($parts -join ',')+']'
}
function MappedPath([string]$Path,$Moves) {
    foreach ($row in $Moves) {
        if (Within $Path $row._src) {
            $relative=$Path.Substring($row._src.TrimEnd('\','/').Length).TrimStart('\','/')
            if (!$relative) {return $row._dst}
            return Join-Path $row._dst $relative
        }
    }
    return $Path
}
function NormalizeReference([string]$Target,[bool]$Url=$false) {
    $Target=$Target.Trim('<','>')
    if (!$Target) {return $null}
    $fileUri=$Target.StartsWith('file://',[StringComparison]::OrdinalIgnoreCase)
    if ($Target -match '^[A-Za-z][A-Za-z0-9+.-]*:' -and !$fileUri -and $Target -notmatch '^[A-Za-z]:[/\\]') {return $null}
    if ($Url -and $Target.StartsWith('//')) {return $null}
    if ($Url -or $fileUri) {$Target=[Uri]::UnescapeDataString(($Target -split '[?#]',2)[0])}
    if ($fileUri) {
        $Target=$Target.Substring(7)
        if ($Target.StartsWith('localhost/',[StringComparison]::OrdinalIgnoreCase)) {$Target=$Target.Substring(9)}
        if ($Target -match '^/[A-Za-z]:') {$Target=$Target.Substring(1)}
        elseif (!$Target.StartsWith('/')) {$Target='//'+$Target}
    }
    return $Target
}
function LocalReferences([string]$Text) {
    $patterns=@('\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', '(?:src|href)\s*=\s*["'']([^"'']+)["'']', '^\s*@([^\r\n]+\.md)\s*$', '["'']((?:[A-Za-z]:[/\\]|\.\.?[/\\]|/)[^"''\r\n]+)["'']')
    $urlSpans=New-Object 'System.Collections.Generic.List[object]'
    for ($i=0;$i -lt $patterns.Count;$i++) {
        foreach ($m in [regex]::Matches($Text,$patterns[$i],[Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [Text.RegularExpressions.RegexOptions]::Multiline)) {
            if ($i -lt 2) {$urlSpans.Add(@{start=$m.Index;end=($m.Index+$m.Length)})}
            elseif ($i -eq 3 -and @($urlSpans | Where-Object {$m.Index -lt $_.end -and ($m.Index+$m.Length) -gt $_.start}).Count) {continue}
            $target=NormalizeReference $m.Groups[1].Value ($i -lt 2)
            if ($target) {$target}
        }
    }
}
function JsonStrings($Value) {
    if ($Value -is [string]) {$Value;return}
    if ($Value -is [Collections.IDictionary]) {foreach ($v in $Value.Values) {JsonStrings $v};return}
    if ($Value -is [pscustomobject]) {foreach ($p in $Value.PSObject.Properties) {JsonStrings $p.Value};return}
    if ($Value -is [Collections.IEnumerable]) {foreach ($v in $Value) {JsonStrings $v}}
}
function InspectReference($p,$Files,$Coverage,$IgnorePaths) {
    if ($p.FullName -in $IgnorePaths) {return}
    if ($p.Extension.ToLowerInvariant() -notin $TextExtensions) {
        if ($p.Extension.ToLowerInvariant() -in $OpaqueExtensions) {$Coverage.Add(@{path=$p.FullName;reason='application references require owner review'})};return
    }
    if ($p.Length -gt 2097152) {$Coverage.Add(@{path=$p.FullName;reason='text exceeds 2 MiB inspection limit'});return}
    try {$encoding=New-Object Text.UTF8Encoding($false,$true);$text=[IO.File]::ReadAllText($p.FullName,$encoding)}
    catch {$Coverage.Add(@{path=$p.FullName;reason='unreadable text'});return}
    $targets=@(LocalReferences $text)
    if ($p.Extension.ToLowerInvariant() -eq '.json') {
        try {$meta=$text | ConvertFrom-Json -ErrorAction Stop}
        catch {$Coverage.Add(@{path=$p.FullName;reason='unparseable JSON'});return}
        if ($meta.kind -eq 'ai-office-builder-preview' -and $meta.schema -eq 1 -and $meta.manifest -and $null -ne $meta.sources) {return}
        $targets=@(foreach ($value in (JsonStrings $meta)) {
            LocalReferences $value
            if ($value -match '^(?:[A-Za-z]:[/\\]|\.\.?[/\\]|/|file://)') {
                $target=NormalizeReference $value
                if ($target) {$target}
            }
        })
    }
    $Files[$p.FullName]=@{sha256=(Hash $p.FullName).ToLowerInvariant();targets=@($targets | Sort-Object -Unique -CaseSensitive)}
}
function DependencyReport($Manifest,$IgnorePaths=@()) {
    if ($null -ne $Manifest.dependency_review -and $Manifest.dependency_review -isnot [string]) {throw 'dependency_review_required: owner response must be text'}
    $roots=@($Manifest.reference_roots)
    if (!$roots.Count) {throw 'reference_roots must explicitly name authorized absolute scan roots'}
    foreach ($root in $roots) {if (![IO.Path]::IsPathRooted($root)) {throw 'reference_roots must be absolute'}}
    foreach ($row in $Manifest.moves) {
        $covered=$false;foreach ($root in $roots) {if (Within $row._src (FullPath $root)) {$covered=$true}}
        if (!$covered) {throw 'source_outside_reference_roots'}
    }
    $limit=10000
    if ($Manifest.PSObject.Properties.Name -contains 'reference_limit') {
        if (($Manifest.reference_limit -isnot [int] -and $Manifest.reference_limit -isnot [long]) -or $Manifest.reference_limit -lt 1 -or $Manifest.reference_limit -gt 10000) {throw 'reference_limit must be an integer from 1 to 10000'}
        $limit=$Manifest.reference_limit
    }
    $files=@{};$coverage=New-Object 'System.Collections.Generic.List[object]';$visited=0
    foreach ($r in $roots) {
        $root=FullPath $r
        if ((Linked $root) -or !(Test-Path -LiteralPath $root) -or @($root -split '[/\\]' | Where-Object {$_ -in $ReferenceSkip}).Count) {throw 'unsafe_reference_root'}
        if ($root -in $IgnorePaths) {continue}
        $visited++;if ($visited -gt $limit) {throw 'reference_inspection_limit: narrow the authorized roots'}
        $rootItem=Get-Item -LiteralPath $root -Force
        if (!$rootItem.PSIsContainer) {InspectReference $rootItem $files $coverage $IgnorePaths;continue}
        $stack=New-Object 'System.Collections.Generic.Stack[string]';$stack.Push($root)
        while ($stack.Count) {
            foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($stack.Pop())) {
                if ($entry -in $IgnorePaths) {continue}
                $visited++;if ($visited -gt $limit) {throw 'reference_inspection_limit: narrow the authorized roots'}
                if ((Split-Path -Leaf $entry) -in $ReferenceSkip) {continue}
                $item=Get-Item -LiteralPath $entry -Force
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {$coverage.Add(@{path=$item.FullName;reason='linked path not inspected'});continue}
                if ($item.PSIsContainer) {$stack.Push($item.FullName)} else {InspectReference $item $files $coverage $IgnorePaths}
            }
        }
    }
    $broken=New-Object 'System.Collections.Generic.List[object]';$edges=New-Object 'System.Collections.Generic.List[object]'
    foreach ($filename in ($files.Keys | Sort-Object)) {
        foreach ($target in $files[$filename].targets) {
            $q=FullPath $(if ([IO.Path]::IsPathRooted($target)) {$target} else {Join-Path (Split-Path -Parent $filename) $target})
            $newP=MappedPath $filename $Manifest.moves;$newQ=MappedPath $q $Manifest.moves
            if ($newP -eq $filename -and $newQ -eq $q) {continue}
            $actual=FullPath $(if ([IO.Path]::IsPathRooted($target)) {$target} else {Join-Path (Split-Path -Parent $newP) $target})
            $covered=$false;foreach ($r in $roots) {if (Within $q (FullPath $r)) {$covered=$true}}
            if (@($q -split '[/\\]' | Where-Object {$_ -in @('99_Private','.obsidian')}).Count) {$covered=$false}
            $edge=@{source=$filename;target=$q;after_source=$newP;after_target=$newQ;check_target=$covered};$edges.Add($edge)
            if ($actual -ne $newQ -or ($covered -and !(Test-Path -LiteralPath $q))) {$broken.Add($edge)}
        }
    }
    return @{files=$files;edges=@($edges.ToArray());broken=@($broken.ToArray());uninspected=@($coverage.ToArray());owner_review=([string]$Manifest.dependency_review).Trim();scope='Only explicit roots; external consumers and unsupported reference syntax are not certified.'}
}
function BundleSnapshot($Manifest,[string]$Cowork,$IgnorePaths=@()) {
    $report=DependencyReport $Manifest $IgnorePaths
    if ($report.broken.Count) {throw ('dependency_break: '+(ConvertTo-Json -InputObject $report.broken -Compress))}
    if (!$report.owner_review) {throw 'dependency_review_required: record owner review of uninspected and external consumers'}
    $clean=@{};foreach ($p in $Manifest.PSObject.Properties) {if ($p.Name -ne 'moves' -and !$p.Name.StartsWith('_')) {$clean[$p.Name]=$p.Value}}
    $clean.moves=@(foreach ($row in $Manifest.moves) {$r=@{};foreach ($p in $row.PSObject.Properties) {if (!$p.Name.StartsWith('_')) {$r[$p.Name]=$p.Value}};$r})
    $sources=New-Object 'System.Collections.Generic.List[object]'
    foreach ($row in $Manifest.moves) {$sources.Add((TreeFingerprint $row._src))}
    return @{kind='ai-office-builder-preview';schema=1;cowork=$Cowork;manifest=$clean;dependencies=$report;sources=@($sources.ToArray())}
}
function VerifyMoved($Row,$Expected) {
    if ((Test-Path -LiteralPath $Row._src) -or (Canonical (TreeFingerprint $Row._dst)) -cne (Canonical $Expected)) {throw "verification_failed: $($Row._dst)"}
}
function VerifyReferences($Report,$Completed) {
    foreach ($edge in $Report.edges) {
        if (!$edge.check_target) {continue}
        $sourceReady=$edge.source -eq $edge.after_source
        $targetReady=$edge.target -eq $edge.after_target
        foreach ($row in $Completed) {
            if (Within $edge.source $row._src) {$sourceReady=$true}
            if (Within $edge.target $row._src) {$targetReady=$true}
        }
        if ($sourceReady -and $targetReady -and ((Linked $edge.after_target) -or !(Test-Path -LiteralPath $edge.after_target))) {throw "dependency_verification_failed: $($edge.after_target)"}
    }
}
function RecoveryRowAllowed($Row,[string]$Cowork,$State) {
    if ($Row.src -isnot [string] -or $Row.dst -isnot [string]) {return $false}
    if (![IO.Path]::IsPathRooted($Row.src) -or ![IO.Path]::IsPathRooted($Row.dst)) {return $false}
    if (@(($Row.src+'|'+$Row.dst) -split '[/\\|]' | Where-Object {$_ -in @('..','99_Private','.obsidian')}).Count) {return $false}
    $originalAllowed=$false;foreach ($r in @($State.reference_roots)) {
        if ($r -is [string] -and [IO.Path]::IsPathRooted($r) -and (Within $Row.dst (FullPath $r))) {$originalAllowed=$true}
    }
    $destinationAllowed=Within $Row.src $Cowork
    foreach ($r in @($State.destination_roots)) {
        if ($r -is [string] -and [IO.Path]::IsPathRooted($r) -and (Within $Row.src (FullPath $r))) {$destinationAllowed=$true}
    }
    if (!$originalAllowed -or !$destinationAllowed -or !$Row.fingerprint) {return $false}
    foreach ($item in $Row.fingerprint) {
        if ($item.path -isnot [string] -or [IO.Path]::IsPathRooted($item.path) -or @($item.path -split '[/\\]' | Where-Object {$_ -eq '..'}).Count -or $item.kind -notin @('file','dir')) {return $false}
        if ($item.kind -eq 'file' -and $item.sha256 -notmatch '^[0-9a-fA-F]{64}$') {return $false}
    }
    return $true
}
function ReconcileSession([string]$Cowork,$State) {
    $bundles=New-Object 'System.Collections.Generic.List[object]'
    $folder=Join-Path $Cowork '00_Inbox/_migration'
    if (Linked $folder) {throw 'linked_metadata'}
    $logPath=Join-Path $folder 'migration_log.md'
    if (Linked $logPath) {throw 'linked_metadata'}
    $verified=New-Object 'System.Collections.Generic.List[object]'
    if (Test-Path -LiteralPath $logPath) {
        foreach ($line in (Get-Content -Encoding UTF8 -LiteralPath $logPath)) {
            if ($line.StartsWith('VERIFIED ')) {
                try {$event=$line.Substring(9) | ConvertFrom-Json -ErrorAction Stop;if ($event.bundle -and $event.src -and $event.dst) {$verified.Add($event)}} catch {}
            }
        }
    }
    $records=New-Object 'System.Collections.Generic.List[object]'
    if (Test-Path -LiteralPath $folder) {
        foreach ($path in (Get-ChildItem -LiteralPath $folder -Filter 'undo_*.json')) {
            if (Linked $path.FullName) {throw 'linked_metadata'}
            try {
                $u=Get-Content -Encoding UTF8 -LiteralPath $path.FullName -Raw | ConvertFrom-Json -ErrorAction Stop
                if ($u.bundle -isnot [string] -or $u.bundle -notmatch '^[A-Za-z0-9_-]+$' -or $u.moves -isnot [array] -or !$u.moves.Count) {throw 'Malformed recovery record'}
                $records.Add($u)
            } catch {$bundles.Add(@{bundle=$path.BaseName;moved=0;original=0;blocked=1})}
        }
    }
    $proofs=@{}
    foreach ($record in $records) {
        if ($record.cowork -isnot [string] -or (FullPath $record.cowork) -ne $Cowork) {continue}
        foreach ($row in $record.moves) {
            if ((RecoveryRowAllowed $row $Cowork $State) -and @($verified | Where-Object {$_.bundle -ceq $record.bundle -and $_.src -ceq $row.dst -and $_.dst -ceq $row.src}).Count) {
                $key=Canonical @{src=$row.dst;dst=$row.src;fingerprint=$row.fingerprint}
                if (!$proofs.ContainsKey($key)) {$proofs[$key]=@()}
                $proofs[$key]+=$record.bundle
            }
        }
    }
    foreach ($u in $records) {
        $counts=@{bundle=$u.bundle;moved=0;original=0;blocked=0;verified_by=@();issues=@()}
        if ($u.cowork -isnot [string] -or (FullPath $u.cowork) -ne $Cowork) {$counts.blocked=$u.moves.Count;$bundles.Add($counts);continue}
        foreach ($row in $u.moves) {
            $status='blocked'
            try {
                if ((RecoveryRowAllowed $row $Cowork $State) -and !(Linked $row.src) -and !(Linked $row.dst)) {
                    if ((Test-Path -LiteralPath $row.src) -and !(Test-Path -LiteralPath $row.dst) -and (Canonical (TreeFingerprint $row.src)) -ceq (Canonical $row.fingerprint)) {
                        $key=Canonical @{src=$row.dst;dst=$row.src;fingerprint=$row.fingerprint}
                        if ($proofs.ContainsKey($key)) {$status='moved';$counts.verified_by=@($counts.verified_by+$proofs[$key] | Select-Object -Unique)}
                    } elseif ((Test-Path -LiteralPath $row.dst) -and !(Test-Path -LiteralPath $row.src) -and (Canonical (TreeFingerprint $row.dst)) -ceq (Canonical $row.fingerprint)) {$status='original'}
                }
            } catch {$counts.issues+=([string]$_)}
            $counts[$status]++
        }
        $bundles.Add($counts)
    }
    $finished=@($bundles | Where-Object {$_.moved -and !$_.original -and !$_.blocked} | ForEach-Object {$_.bundle})
    $pending=@($State.pending_bundles | Where-Object {$_ -notin $finished})
    foreach ($bundle in $bundles) {if ($bundle.original -and !$bundle.moved -and !$bundle.blocked -and $bundle.bundle -cnotin $pending) {$pending+=$bundle.bundle}}
    return @{choices=$State;bundles=@($bundles.ToArray());pending=$pending;blocked=@($bundles | Where-Object {$_.blocked -or ($_.moved -and $_.original)} | ForEach-Object {$_.bundle})}
}
