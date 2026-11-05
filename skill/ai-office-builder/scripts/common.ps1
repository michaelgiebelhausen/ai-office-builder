$ErrorActionPreference = 'Stop'
function FullPath([string]$Path) {
    if ($Path -eq '~') { return $env:USERPROFILE }
    if ($Path.StartsWith('~/') -or $Path.StartsWith('~\')) { $Path = Join-Path $env:USERPROFILE $Path.Substring(2) }
    return [IO.Path]::GetFullPath($Path)
}
function Within([string]$Path, [string]$Parent) {
    return $Path.Equals($Parent, [StringComparison]::OrdinalIgnoreCase) -or $Path.StartsWith($Parent.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}
function Linked([string]$Path) {
    while ($Path) {
        if (Test-Path -LiteralPath $Path) {
            if ((Get-Item -Force -LiteralPath $Path).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $true }
        }
        $Path = Split-Path -Parent $Path
    }
    return $false
}
function Hash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
    finally { $stream.Dispose(); $sha.Dispose() }
}
function Same([string]$A, [string]$B) {
    return (Test-Path -LiteralPath $A -PathType Leaf) -and (Test-Path -LiteralPath $B -PathType Leaf) -and ((Get-Item -LiteralPath $A).Length -eq (Get-Item -LiteralPath $B).Length) -and ((Hash $A) -eq (Hash $B))
}
function WriteNewJson([string]$Path, $Data) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Data -Depth 100))
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}
function LogLine([string]$Path, [string]$Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}
function MoveSafe([string]$Source, [string]$Destination) {
    # .NET Move never replaces or merges. No cross-volume copy/delete fallback.
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $Destination))
    if (Test-Path -LiteralPath $Source -PathType Container) { [IO.Directory]::Move($Source, $Destination) }
    else { [IO.File]::Move($Source, $Destination) }
}
function Walk([string]$Root, [switch]$SkipGit) {
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($Root)
    while ($pending.Count) {
        $base = $pending.Pop()
        $items = @(Get-ChildItem -LiteralPath $base -Force)
        if ($SkipGit -and @($items | Where-Object Name -eq '.git').Count) {
            [pscustomobject]@{ Kind='git'; Path=$base; Item=$null }; continue
        }
        foreach ($item in $items) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                [pscustomobject]@{ Kind='link'; Path=$item.FullName; Item=$item }; continue
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
            [pscustomobject]@{ Kind=$(if ($item.PSIsContainer) {'dir'} else {'file'}); Path=$item.FullName; Item=$item }
        }
    }
}
