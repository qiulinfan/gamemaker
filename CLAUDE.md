# Gamemaker guidance for Claude Code

Read and follow `AGENTS.md` for repository conventions.

Claude Code integration is currently skills-only: `scripts/link-claude-skills.sh`
on POSIX/WSL or `scripts/link-claude-skills.ps1` on native Windows links each
`skills/<name>` into the Claude Code user Skill directory (`~/.claude/skills`,
honoring `CLAUDE_CONFIG_DIR`). These scripts are deliberately independent of
`workflow.bundle.toml` and of the receipt-backed Codex link contract
(`scripts/link.sh` / `scripts/link.ps1`); they install no agents, workflows,
profiles, or receipts. Porting the full bundle (agents, workflows, profiles) to
Claude Code is a separate project that needs an explicit request.
