#requires -Version 7.0

$script:IsWindowsHost = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows
)

function Resolve-GamemakerPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string]$RelativeTo
    )
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        if ([string]::IsNullOrWhiteSpace($RelativeTo)) {
            throw "Relative path has no base: $Path"
        }
        $Path = Join-Path $RelativeTo $Path
    }
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($pathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathRoot
    }
    return $fullPath.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Get-GamemakerPython {
    $python = Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $python) {
        throw 'Python 3.11+ is required for validated link inventory.'
    }
    return $python.Source
}

function Get-GamemakerInventory {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$CodexHome
    )
    $python = Get-GamemakerPython
    $contractScript = Join-Path $RepositoryRoot 'scripts\link_contract.py'
    $output = @(& $python $contractScript inventory --root $RepositoryRoot --codex-home $CodexHome 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Gamemaker bundle validation/link inventory failed before mutation:`n$($output -join "`n")"
    }
    return (($output -join "`n") | ConvertFrom-Json -Depth 20)
}

function Read-GamemakerReceipt {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$CodexHome,
        [Parameter(Mandatory = $true)][string]$ReceiptPath
    )
    $python = Get-GamemakerPython
    $contractScript = Join-Path $RepositoryRoot 'scripts\link_contract.py'
    $output = @(& $python $contractScript receipt --root $RepositoryRoot --codex-home $CodexHome --receipt $ReceiptPath 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Invalid Gamemaker install receipt; refusing link mutation:`n$($output -join "`n")"
    }
    return (($output -join "`n") | ConvertFrom-Json -Depth 20)
}

function Write-GamemakerReceipt {
    param(
        [Parameter(Mandatory = $true)]$Inventory,
        [Parameter(Mandatory = $true)][object[]]$Entries
    )
    $receiptPath = [string]$Inventory.receipt_path
    $parent = Split-Path -Parent $receiptPath
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    $receipt = [ordered]@{
        schema_version = 1
        product = 'gamemaker'
        repository_root = [string]$Inventory.repository_root
        entries = @($Entries)
    }
    $payload = ($receipt | ConvertTo-Json -Depth 12) + "`n"
    $temporary = Join-Path $parent ".$([System.IO.Path]::GetFileName($receiptPath)).$PID.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [System.IO.File]::WriteAllText(
            $temporary,
            $payload,
            [System.Text.UTF8Encoding]::new($false)
        )
        [System.IO.File]::Move($temporary, $receiptPath, $true)
    }
    finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary
        }
    }
}

function Get-GamemakerLinkTargets {
    param([Parameter(Mandatory = $true)][string]$Destination)
    $item = Get-Item -Force -LiteralPath $Destination -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        return @()
    }
    if ($item.LinkType -in @('SymbolicLink', 'Junction')) {
        $rawTarget = @($item.Target) | Select-Object -First 1
        if (-not [string]::IsNullOrWhiteSpace([string]$rawTarget)) {
            return @(
                Resolve-GamemakerPath -Path ([string]$rawTarget) -RelativeTo (Split-Path -Parent $Destination)
            )
        }
    }
    elseif ($item.LinkType -eq 'HardLink' -and $script:IsWindowsHost) {
        $volumeRoot = [System.IO.Path]::GetPathRoot($Destination).TrimEnd('\')
        $rawTargets = @(& fsutil.exe hardlink list $Destination 2>$null)
        if ($LASTEXITCODE -eq 0) {
            return @(
                $rawTargets |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                    ForEach-Object {
                        Resolve-GamemakerPath -Path ($volumeRoot + ([string]$_).Trim())
                    }
            )
        }
    }
    return @()
}

function Get-GamemakerLinkState {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedSource,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string]$ExpectedLinkType
    )
    $item = Get-Item -Force -LiteralPath $Destination -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        return [pscustomobject]@{ Status = 'Absent'; LinkType = $null; Targets = @() }
    }
    $targets = @(Get-GamemakerLinkTargets -Destination $Destination)
    if ($targets.Count -eq 0) {
        return [pscustomobject]@{ Status = 'RealItem'; LinkType = [string]$item.LinkType; Targets = @() }
    }
    $expected = Resolve-GamemakerPath -Path $ExpectedSource
    $targetMatches = @($targets | Where-Object {
        $_.Equals($expected, [System.StringComparison]::OrdinalIgnoreCase)
    }).Count -gt 0
    $typeMatches = [string]::IsNullOrWhiteSpace($ExpectedLinkType) -or
        ([string]$item.LinkType -eq $ExpectedLinkType)
    $status = if ($targetMatches -and $typeMatches) { 'Owned' } else { 'WrongOwner' }
    return [pscustomobject]@{
        Status = $status
        LinkType = [string]$item.LinkType
        Targets = $targets
    }
}

function Remove-GamemakerReceiptEntry {
    param([Parameter(Mandatory = $true)]$Entry)
    $state = Get-GamemakerLinkState `
        -ExpectedSource ([string]$Entry.source) `
        -Destination ([string]$Entry.destination) `
        -ExpectedLinkType ([string]$Entry.link_type)
    if ($state.Status -eq 'Absent') {
        Write-Host "ABSENT  $($Entry.destination)"
        return $true
    }
    if ($state.Status -ne 'Owned') {
        Write-Warning (
            "Refusing to remove unproven managed entry: $($Entry.destination); " +
            "status=$($state.Status), type=$($state.LinkType), targets=$($state.Targets -join ', ')"
        )
        return $false
    }
    Remove-Item -LiteralPath ([string]$Entry.destination)
    Write-Host "UNLINKED $($Entry.destination)"
    return $true
}

function New-GamemakerManagedLink {
    param(
        [Parameter(Mandatory = $true)]$Entry,
        [switch]$Force
    )
    $source = Resolve-GamemakerPath -Path ([string]$Entry.source)
    $destination = Resolve-GamemakerPath -Path ([string]$Entry.destination)
    $state = Get-GamemakerLinkState -ExpectedSource $source -Destination $destination
    if ($state.Status -eq 'Owned') {
        Write-Host "OK      $destination -> $source"
        return [pscustomobject]@{ LinkType = [string]$state.LinkType; Created = $false }
    }
    if ($state.Status -eq 'RealItem') {
        throw "Refusing to replace a real file or directory: $destination"
    }
    if ($state.Status -eq 'WrongOwner') {
        if ($state.LinkType -eq 'HardLink') {
            throw (
                "Refusing to replace an unproven hard link even with -Force: " +
                "$destination -> $($state.Targets -join ', ')"
            )
        }
        if (-not $Force) {
            throw "Conflicting link exists: $destination -> $($state.Targets -join ', ') (use -Force to replace only this link)"
        }
        Remove-Item -LiteralPath $destination
    }

    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
    if ([string]$Entry.kind -eq 'directory' -and $script:IsWindowsHost) {
        New-Item -ItemType Junction -Path $destination -Target $source | Out-Null
    }
    elseif ([string]$Entry.kind -eq 'file' -and $script:IsWindowsHost) {
        try {
            New-Item -ItemType SymbolicLink -Path $destination -Target $source -ErrorAction Stop | Out-Null
        }
        catch {
            try {
                New-Item -ItemType HardLink -Path $destination -Target $source -ErrorAction Stop | Out-Null
            }
            catch {
                throw "Could not directly link '$destination'. Enable Windows Developer Mode for symlinks or keep CODEX_HOME on the same volume for the hard-link fallback. $($_.Exception.Message)"
            }
        }
    }
    else {
        New-Item -ItemType SymbolicLink -Path $destination -Target $source | Out-Null
    }
    $created = Get-Item -Force -LiteralPath $destination
    Write-Host "LINKED  $destination -> $source"
    return [pscustomobject]@{ LinkType = [string]$created.LinkType; Created = $true }
}
