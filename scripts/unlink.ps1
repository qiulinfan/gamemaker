#requires -Version 7.0

[CmdletBinding()]
param([string]$CodexHome)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'AutoTA unlink.ps1 requires PowerShell 7 or newer (pwsh).'
}
if (-not $IsWindows) {
    throw 'AutoTA unlink.ps1 is the Windows lifecycle entrypoint; use ./scripts/unlink.sh on macOS or Linux.'
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
$receiptPath = Join-Path $resolvedCodexHome 'state\autota\install-receipt.json'
$receipt = Read-AutoTAReceipt `
    -RepositoryRoot $repositoryRoot `
    -CodexHome $resolvedCodexHome `
    -ReceiptPath $receiptPath

if ($null -eq $receipt) {
    Write-Host 'No AutoTA install receipt exists; nothing was removed.'
    exit 0
}

$remaining = [System.Collections.Generic.List[object]]::new()
foreach ($entry in @($receipt.entries)) {
    if (-not (Remove-AutoTAReceiptEntry -Entry $entry)) {
        $remaining.Add($entry)
    }
}

if ($remaining.Count -gt 0) {
    $receiptInventory = [pscustomobject]@{
        receipt_path = $receiptPath
        repository_root = [string]$receipt.repository_root
    }
    Write-AutoTAReceipt -Inventory $receiptInventory -Entries @($remaining)
    throw 'Some receipt entries were preserved because ownership could not be proven.'
}

Remove-Item -LiteralPath $receiptPath
$stateDirectory = Split-Path -Parent $receiptPath
if ((Test-Path -LiteralPath $stateDirectory -PathType Container) -and
    @(Get-ChildItem -Force -LiteralPath $stateDirectory).Count -eq 0) {
    Remove-Item -LiteralPath $stateDirectory
}
Write-Host 'AutoTA receipt-owned links removed. Unrelated Codex files were preserved.'
