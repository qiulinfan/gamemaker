# AutoTA guidance for Claude Code

Read and follow `AGENTS.md` for repository conventions.

Claude Code integration is skills-only: `scripts/link-claude-skills.sh`
on POSIX/WSL or `scripts/link-claude-skills.ps1` on native Windows links each
`skills/<name>` into the Claude Code user Skill directory (`~/.claude/skills`,
honoring `CLAUDE_CONFIG_DIR`). These scripts are deliberately independent of
`workflow.bundle.toml` and of the receipt-backed Codex link contract
(`scripts/link.sh` / `scripts/link.ps1`); they install no agents, workflows,
profiles, or receipts. Skills resolve their bundled scripts by probing the
Codex home first and the Claude Code home second, so the pipeline runs
natively in both runtimes.
