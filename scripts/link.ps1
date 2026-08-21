#requires -Version 7.0

[CmdletBinding()]
param(
    [string]$CodexHome,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'AutoTA link.ps1 requires PowerShell 7 or newer (pwsh).'
}
if (-not $IsWindows) {
    throw 'AutoTA link.ps1 is the Windows lifecycle entrypoint; use ./scripts/link.sh on macOS or Linux.'
}
. (Join-Path $PSScriptRoot 'LinkContract.ps1')

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = $env:CODEX_HOME
}
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
}
$resolvedCodexHome = Resolve-AutoTAPath -Path $CodexHome

# Inventory construction runs the complete validator before any CODEX_HOME write.
$inventory = Get-AutoTAInventory -RepositoryRoot $repositoryRoot -CodexHome $resolvedCodexHome
$receipt = Read-AutoTAReceipt `
    -RepositoryRoot $repositoryRoot `
    -CodexHome $resolvedCodexHome `
    -ReceiptPath ([string]$inventory.receipt_path)

$desiredByDestination = @{}
foreach ($entry in @($inventory.entries)) {
    $desiredByDestination[([string]$entry.destination).ToLowerInvariant()] = $entry
}

$keptReceiptEntries = [System.Collections.Generic.List[object]]::new()
$staleFailures = $false
$oldEntries = if ($null -eq $receipt) { @() } else { @($receipt.entries) }
foreach ($old in $oldEntries) {
    $key = ([string]$old.destination).ToLowerInvariant()
    $desired = $desiredByDestination[$key]
    $stillDesired = $null -ne $desired -and
        ([string]$old.source).Equals([string]$desired.source, [System.StringComparison]::OrdinalIgnoreCase) -and
        ([string]$old.kind -eq [string]$desired.kind)
    if ($stillDesired) {
        $keptReceiptEntries.Add($old)
        continue
    }
    if (-not (Remove-AutoTAReceiptEntry -Entry $old)) {
        $keptReceiptEntries.Add($old)
        $staleFailures = $true
    }
}

if ($staleFailures) {
    Write-AutoTAReceipt -Inventory $inventory -Entries @($keptReceiptEntries)
    throw 'One or more stale AutoTA entries could not be proven owned; current links were not changed.'
}

$installed = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($entry in @($inventory.entries)) {
        $result = New-AutoTAManagedLink -Entry $entry -Force:$Force
        $installed.Add([ordered]@{
            inventory_id = [string]$entry.inventory_id
            source = [string]$entry.source
            destination = [string]$entry.destination
            kind = [string]$entry.kind
            link_type = [string]$result.LinkType
        })
    }
    Write-AutoTAReceipt -Inventory $inventory -Entries @($installed)
}
catch {
    # Keep an atomic receipt for every successfully observed/created managed entry
    # so a later unlink never has to infer ownership from current disk inventory.
    $partial = @($installed)
    $installedDestinations = @($partial | ForEach-Object { ([string]$_.destination).ToLowerInvariant() })
    foreach ($old in @($keptReceiptEntries)) {
        if (([string]$old.destination).ToLowerInvariant() -notin $installedDestinations) {
            $partial += $old
        }
    }
    if ($partial.Count -gt 0) {
        Write-AutoTAReceipt -Inventory $inventory -Entries $partial
    }
    throw
}

Write-Host "AutoTA links installed from $repositoryRoot"
Write-Host "Canonical product root: $($inventory.entries[-1].destination)"
Write-Host "Install receipt: $($inventory.receipt_path)"
Write-Host 'Restart Codex so Skill, workflow, profile, and custom-agent metadata reload.'
