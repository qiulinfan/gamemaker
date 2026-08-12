#requires -Version 7.0

[CmdletBinding()]
param(
    [string]$CodexHome,
    [switch]$SkipLinkCheck
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'Gamemaker doctor.ps1 requires PowerShell 7 or newer (pwsh).'
}
if (-not $IsWindows) {
    throw 'Gamemaker doctor.ps1 is the Windows lifecycle entrypoint; use ./scripts/doctor.sh on macOS or Linux.'
}
. (Join-Path $PSScriptRoot 'LinkContract.ps1')

$failures = [System.Collections.Generic.List[string]]::new()
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = $env:CODEX_HOME
}
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
}
$resolvedCodexHome = Resolve-GamemakerPath -Path $CodexHome

try {
    $inventory = Get-GamemakerInventory -RepositoryRoot $repositoryRoot -CodexHome $resolvedCodexHome
}
catch {
    $failures.Add($_.Exception.Message)
    $inventory = $null
}

Get-ChildItem -Recurse -File -Filter '*.ps1' -LiteralPath $repositoryRoot | ForEach-Object {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $_.FullName,
        [ref]$tokens,
        [ref]$parseErrors
    )
    if ($parseErrors.Count -gt 0) {
        $failures.Add("PowerShell parse failure: $($_.FullName): $($parseErrors[0].Message)")
    }
}

if (-not $SkipLinkCheck -and $null -ne $inventory) {
    try {
        $receipt = Read-GamemakerReceipt `
            -RepositoryRoot $repositoryRoot `
            -CodexHome $resolvedCodexHome `
            -ReceiptPath ([string]$inventory.receipt_path)
    }
    catch {
        $failures.Add($_.Exception.Message)
        $receipt = $null
    }
    if ($null -eq $receipt) {
        $failures.Add("Missing managed install receipt: $($inventory.receipt_path)")
    }
    else {
        if (-not ([string]$receipt.repository_root).Equals(
            [string]$inventory.repository_root,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            $failures.Add(
                "Receipt repository root mismatch: $($receipt.repository_root) " +
                "(expected $($inventory.repository_root))"
            )
        }
        $receiptByDestination = @{}
        foreach ($entry in @($receipt.entries)) {
            $receiptByDestination[([string]$entry.destination).ToLowerInvariant()] = $entry
        }
        $desiredDestinations = @{}
        foreach ($desired in @($inventory.entries)) {
            $key = ([string]$desired.destination).ToLowerInvariant()
            $desiredDestinations[$key] = $true
            $entry = $receiptByDestination[$key]
            if ($null -eq $entry) {
                $failures.Add("Receipt missing inventory entry: $($desired.inventory_id)")
                continue
            }
            if (-not ([string]$entry.source).Equals(
                [string]$desired.source,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -or [string]$entry.kind -ne [string]$desired.kind) {
                $failures.Add("Receipt contract mismatch: $($desired.inventory_id)")
                continue
            }
            $state = Get-GamemakerLinkState `
                -ExpectedSource ([string]$entry.source) `
                -Destination ([string]$entry.destination) `
                -ExpectedLinkType ([string]$entry.link_type)
            if ($state.Status -ne 'Owned') {
                $failures.Add(
                    "Managed link is not owned: $($entry.destination); " +
                    "status=$($state.Status), type=$($state.LinkType), " +
                    "targets=$($state.Targets -join ', ')"
                )
            }
            else {
                Write-Host "LINK OK $($entry.destination)"
            }
        }
        foreach ($entry in @($receipt.entries)) {
            if (-not $desiredDestinations.ContainsKey(
                ([string]$entry.destination).ToLowerInvariant()
            )) {
                $failures.Add("Stale receipt entry: $($entry.destination)")
            }
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ -ErrorAction Continue }
    exit 1
}
Write-Host 'GAMEMAKER_BUNDLE_OK'
Write-Host 'GAMEMAKER_DOCTOR_OK'
