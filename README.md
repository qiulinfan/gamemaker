# AutoTA

AutoTA is a portable, evidence-driven technical-art pipeline. It turns an art
requirement (a design brief's visual/audio needs) into license-verified or
generated assets with receipts, and hands engine integration to the target
project's own workflow. It is the **midstream** of a game production line:
upstream design docs state what is needed; AutoTA sources, generates, adapts,
and audits it; the target project (e.g. a CCGS/Codex game-studio setup)
integrates and verifies it in-engine.

Five portable Agent Skills:

- `search-game-art` — requirement matrix, source-covered search, per-item
  license verification, audited acquisition; programmatic CC0 acquisition for
  uniformly licensed sources (Poly Haven API).
- `create-2d-game-art` — deterministic 2D raster production (pixelize,
  sequence, pack, audit) with closed-schema receipts.
- `auto-ta` — Blender-side 3D technical art: authoring, adaptation, the
  isolated audit chain, round-trip validation, downstream optimization.
- `generate-hosted-game-art` — hosted generation via user-supplied Meshy /
  Tencent Cloud credentials: free capability probe, budget-authorized
  batches, generation receipts.
- `character-rig-animation-alignment` — humanoid × external animation
  alignment and engine-ready retargeting acceptance.

Plus `workflows/handoff-contract.md` (the receipt/gate schema every delivery
shares), two namespaced Codex agents (`autota_technical_artist`,
`autota_art_scout`), and one disabled-by-default project profile.

The initial Skill sources were migrated from
`qiulinfan/qiulinfan.github.io` revision
`0e4cce8a474197170942e9b10984706bb9b95a05`. The deterministic raster core of
`create-2d-game-art` was redesigned from the generalizable parts of
`qiulinfan/ImageToPixel` revision
`152bab66d3def65e6eaa5cd6ba97c00ac754ee31`. The repository was slimmed from
the earlier "gamemaker" full-production bundle in 2026-08: orchestration,
design, and engine-execution Skills were removed (git history keeps them);
only the mature TA pipeline remains.

## Position in a production line

1. **Upstream (design)**: the game project's design docs state visual/audio
   requirements — that text is the design brief AutoTA consumes.
2. **Midstream (AutoTA)**: source or generate the asset, adapt it in Blender,
   audit it, and emit a receipt. Deliveries stay `prototype` until the named
   gates pass; a receipt never converts `not_tested` into a pass.
3. **Downstream (engine)**: the target project imports the delivery, wires it
   into scenes, and verifies in-engine with its own tools. AutoTA never
   mutates the game project's scenes on its own authority.

## Link the working tree into Codex

The linkers point Codex directly at this checkout. Editing a Skill or custom
agent here therefore changes what a newly started Codex task loads; no copied
installation is created.

Runtime requirements are Python 3.11+ and `uv` on every platform. `uv` runs
Skills with their locked inline dependencies; doctor fails closed when it is
missing. On macOS, use iTerm2 as the terminal emulator and run the POSIX
lifecycle in `zsh` or `bash`;
iTerm2 is not itself a shell, and PowerShell is not a macOS requirement. Linux
uses the same POSIX lifecycle. Windows uses PowerShell 7+ (`pwsh`) for the
Windows lifecycle scripts. Windows PowerShell 5.1 is unsupported,
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
links for the five Skills, two namespaced agents, and the complete product
root at `${CODEX_HOME}/workflow-products/autota`. Skills resolve bundled
scripts and the handoff contract only through linked locations, so they work
from an unrelated game cwd.

The linker atomically records every managed destination, canonical source, kind,
and observed link type at
`${CODEX_HOME}/state/autota/install-receipt.json`. The receipt is bound to
this exact checkout and the AutoTA namespaces. Re-linking removes a
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

Claude Code integration is skills-only: `scripts/link-claude-skills.sh`
(POSIX/WSL) or `scripts/link-claude-skills.ps1` (native Windows) links each
Skill into the Claude Code user Skill directory; Skills resolve their bundled
scripts from either runtime home.

## Profiles are explicit

The portable core never auto-selects a profile. A target repository or user
must explicitly choose one:

- `dreamweaver`: project workspace facts and historical retargeting case
  evidence.

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
