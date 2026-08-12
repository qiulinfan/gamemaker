# Gamemaker

Gamemaker is a portable Codex workflow bundle for taking a game idea or
production issue through a small, evidence-backed agile iteration. It combines
design, Unity implementation, sourced and original art, character/animation
alignment, independent play verification, and producer acceptance without
making one project, machine, orchestrator, or cloud provider the default.

The initial Skill sources were migrated from
`qiulinfan/qiulinfan.github.io` revision
`0e4cce8a474197170942e9b10984706bb9b95a05`. Generated Python cache files were
not migrated. Project-specific facts were separated into opt-in profiles.

## What is included

- `skills/`: twelve portable Agent Skills covering production coordination,
  design, Unity scenes/features/levels, Unity MCP, playtesting, game-art search,
  technical art, rig alignment, and bounded Windows capture.
- `workflows/`: the end-to-end production map, agile iteration state machine,
  and handoff contract.
- `.codex/agents/`: namespaced producer, designer, programmer, technical-art,
  art-scout, playtester, and reviewer roles using Codex's standard custom-agent
  TOML format.
- `profiles/`: disabled-by-default Dreamweaver, Multica, and Google Drive
  adaptations and historical evidence.
- `workflow.bundle.toml`: the machine-readable bundle inventory.
- `scripts/`: POSIX lifecycle commands for macOS/Linux and PowerShell lifecycle
  commands for Windows.
- `tests/`: manifest, portability, agent, installer, and syntax checks.

## Production loop

Use `$coordinate-game-production` for the umbrella workflow:

1. establish the parent outcome and canonical workspace;
2. classify the next smallest vertical slice;
3. make design, ownership, dependencies, and evidence ready;
4. dispatch only ready specialist work;
5. integrate exact handed-off artifacts;
6. run focused checks, relevant regressions, and independent play when the
   result is player-facing;
7. accept, route one bounded defect, or re-plan;
8. record the next smallest ready slice.

See `workflows/game-production.md` and `workflows/agile-iteration.md` for the
full contracts.

## Link the working tree into Codex

The linkers point Codex directly at this checkout. Editing a Skill or custom
agent here therefore changes what a newly started Codex task loads; no copied
installation is created.

Runtime requirements are Python 3.11+ on every platform. On macOS, use iTerm2
as the terminal emulator and run the POSIX lifecycle in `zsh` or `bash`;
iTerm2 is not itself a shell, and PowerShell is not a macOS requirement. Linux
uses the same POSIX lifecycle. Windows uses PowerShell 7+ (`pwsh`) for the
Windows lifecycle and capture scripts. Windows PowerShell 5.1 is unsupported,
and the PowerShell entrypoints fail before mutation when invoked by an older
host.

macOS — open the checkout in iTerm2, then run these commands in `zsh` or
`bash`:

~~~sh
./scripts/link.sh
./scripts/doctor.sh
~~~

Linux — run the same POSIX entrypoints in a POSIX shell:

~~~sh
./scripts/link.sh
./scripts/doctor.sh
~~~

Windows — run the Windows entrypoints in PowerShell 7:

~~~powershell
pwsh -NoProfile -File .\scripts\link.ps1
pwsh -NoProfile -File .\scripts\doctor.ps1
~~~

Set `CODEX_HOME` or pass an explicit home path as the first argument. Existing
real files or directories are never overwritten. Use `-Force` (PowerShell) or
`--force` (POSIX) only to replace a conflicting symbolic link; the scripts
still refuse to replace non-links.

Before the first `CODEX_HOME` write, the linker validates the manifest and its
exact Skill, agent, workflow, and profile inventories. It then creates direct
links for the twelve Skills, seven namespaced agents, and the complete product
root at `${CODEX_HOME}/workflow-products/gamemaker`. Producer workflows resolve
`workflow.bundle.toml`, workflow files, and explicitly selected profiles only
through that canonical product root, so they work from an unrelated game cwd.

The linker atomically records every managed destination, canonical source, kind,
and observed link type at
`${CODEX_HOME}/state/gamemaker/install-receipt.json`. The receipt is bound to
this exact checkout and the Gamemaker namespaces. Re-linking removes a
receipt-owned stale symlink/junction after a manifest rename or deletion;
unlinking uses the receipt rather than only the current disk inventory.
Corrupt, wrong-checkout, wrong-owner, or real destinations are preserved and
reported instead of guessed. `CODEX_HOME` must not equal, contain, or be
contained by this repository, because that would make the product-root link
recursive.

Unlink only receipt-owned entries that can still be proven to target this
checkout. On macOS, run the POSIX command in `zsh` or `bash` inside iTerm2; use
the same command on Linux:

~~~sh
./scripts/unlink.sh
~~~

On Windows, use PowerShell 7:

~~~powershell
pwsh -NoProfile -File .\scripts\unlink.ps1
~~~

Restart Codex after changing linked Skills or custom-agent configuration.
On Windows, Skill directories use junctions. Agent files use symbolic links when
available and same-volume hard links as the non-admin fallback. Because a Git
operation can replace a hard-linked file inode, run doctor after switching or
updating this bundle. A detached hardlink whose original source identity no
longer exists cannot be proven owned from its path; doctor/link/unlink fail
safely and preserve it for manual inspection. The lifecycle does not promise
automatic stale cleanup for that fallback. Enable Windows Developer Mode so
agent symlinks can be used when rename/delete cleanup must remain automatic.

## Profiles are explicit

The portable core never auto-selects a profile. A target repository or user
must explicitly choose one:

- `dreamweaver`: historical project paths, exact-Editor policy, and case
  evidence;
- `multica`: event-driven issue/run dispatch as an optional orchestrator
  adapter;
- `google-drive`: mounted-folder publication for verified playtest evidence.

Profiles can narrow paths and delivery adapters. They cannot expand user
authority or weaken validation, licensing, or workspace boundaries.

## Validate

On macOS, open iTerm2 and run the complete POSIX validation path in `zsh` or
`bash`. Linux uses the same commands:

~~~sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q skills scripts tests
sh -n scripts/link.sh scripts/unlink.sh scripts/doctor.sh
./scripts/doctor.sh --skip-link-check

codex_home="${CODEX_HOME:-$HOME/.codex}"
validator="$codex_home/skills/.system/skill-creator/scripts/quick_validate.py"
for skill_dir in skills/*; do
    [ -d "$skill_dir" ] || continue
    uv run --with pyyaml python "$validator" "$skill_dir"
done

git diff --check
~~~

This macOS path neither invokes nor requires `pwsh`. On Windows, run the
equivalent validation in PowerShell 7:

~~~powershell
python -m unittest discover -s tests -v
python -m compileall -q skills scripts tests
pwsh -NoProfile -File .\scripts\doctor.ps1 -SkipLinkCheck
$env:PYTHONUTF8 = '1'
$codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    Join-Path $env:USERPROFILE '.codex'
} else {
    [System.IO.Path]::GetFullPath($env:CODEX_HOME)
}
$validator = Join-Path $codexHome 'skills\.system\skill-creator\scripts\quick_validate.py'
Get-ChildItem .\skills -Directory | ForEach-Object {
    uv run --with pyyaml python $validator $_.FullName
}
git diff --check
~~~

The tests use temporary Codex homes and do not modify the user's live Codex
installation.

## License status

No license could be established from the source checkout, public repository
metadata, or the new empty remote. This repository intentionally has no `LICENSE` file
until the owner selects terms. Do not infer permission to copy, redistribute,
or publish this work from repository visibility alone.
