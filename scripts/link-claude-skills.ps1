#Requires -Version 7.0
# Skills-only Claude Code linker for the gamemaker product checkout.
#
# Links each skills\<name> of this checkout into the Claude Code user Skill
# directory as an individually owned junction, so local edits are visible
# immediately. It installs no agents, workflow manifests, or receipts: the
# full product integration stays Codex-only (the receipt-backed `scripts/link.sh` / `scripts/link.ps1` contract),
# and porting it to Claude Code is a separate project.
[CmdletBinding()]
param([string]$ClaudeHome)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$repositorySkills = Join-Path $repoRoot 'skills'
if (-not (Test-Path -LiteralPath $repositorySkills -PathType Container)) {
    throw "Missing product skills directory: $repositorySkills"
}
if (-not $ClaudeHome) {
    $ClaudeHome = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
}
$claudeSkills = Join-Path $ClaudeHome 'skills'
$existingRoot = Get-Item -Force -LiteralPath $claudeSkills -ErrorAction SilentlyContinue
if ($null -ne $existingRoot -and ($existingRoot.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
    throw "Claude Code skills path must be a Claude Code-owned real directory, not a link: $claudeSkills"
}
if ($null -ne $existingRoot -and -not $existingRoot.PSIsContainer) {
    throw "Claude Code skills path is not a directory: $claudeSkills"
}
[System.IO.Directory]::CreateDirectory($claudeSkills) | Out-Null

$repositoryPrefix = [System.IO.Path]::GetFullPath($repositorySkills).TrimEnd('\') + '\'

# Remove links this checkout owns that are stale or renamed. Links owned by
# qlblog or other product checkouts are never touched.
Get-ChildItem -Force -LiteralPath $claudeSkills | ForEach-Object {
    if (-not ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { return }
    if ([string]::IsNullOrEmpty($_.LinkTarget)) { return }
    $target = [System.IO.Path]::GetFullPath($_.LinkTarget)
    if (-not $target.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { return }
    if ((Test-Path -LiteralPath (Join-Path $target 'SKILL.md') -PathType Leaf) -and
        ([System.IO.Path]::GetFileName($target) -eq $_.Name)) { return }
    Remove-Item -LiteralPath $_.FullName
    Write-Host "REMOVED stale gamemaker Skill link: $($_.FullName)"
}

$linked = 0
foreach ($skillDirectory in (Get-ChildItem -LiteralPath $repositorySkills -Directory | Sort-Object Name)) {
    if (-not (Test-Path -LiteralPath (Join-Path $skillDirectory.FullName 'SKILL.md') -PathType Leaf)) { continue }
    $destination = Join-Path $claudeSkills $skillDirectory.Name
    $existing = Get-Item -Force -LiteralPath $destination -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        if (-not ($existing.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing to replace a real file or directory: $destination"
        }
        if ([string]::IsNullOrEmpty($existing.LinkTarget) -or
            [System.IO.Path]::GetFullPath($existing.LinkTarget) -ne [System.IO.Path]::GetFullPath($skillDirectory.FullName)) {
            throw "Conflicting link exists: $destination"
        }
    } else {
        New-Item -ItemType Junction -Path $destination -Target $skillDirectory.FullName | Out-Null
    }
    $linked++
}

Write-Host "CLAUDE_SKILLS_OK ($linked gamemaker Skills; skills-only, agents and workflows stay Codex-only)"
