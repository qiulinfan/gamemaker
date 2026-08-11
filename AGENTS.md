# Gamemaker agent guidance

- Treat this repository as the portable authority for the game-production
  workflow bundle. Keep product Skills in `skills/`, orchestration documents
  in `workflows/`, optional deployment or project facts in `profiles/`,
  Codex role definitions in `.codex/agents/`, and bundle operations in
  `scripts/`.
- Keep every Skill portable. Do not add personal paths, project identities,
  hosted orchestrators, cloud destinations, credentials, private URLs, asset
  hashes, or one-off workarounds to `skills/`. Put an explicitly requested
  environment adaptation in a disabled-by-default profile and keep historical
  evidence under that profile's `case-studies/`.
- Never select a profile by guessing from a username, directory name, running
  process, or connected service. Use a profile only when the user or target
  repository explicitly names it.
- Follow `workflow.bundle.toml` as the inventory. A Skill, agent, workflow, or
  profile addition/removal must update the manifest and tests in the same
  change.
- For a production run, use `coordinate-game-production` as the portable
  producer contract and `workflows/agile-iteration.md` as the state machine.
  Prefer the namespaced Codex agents under `.codex/agents/`; keep one
  coordinator, bound each worker to one deliverable, serialize overlapping
  writes, and independently verify handed-off artifacts.
- Read every selected Skill completely and every reference it makes mandatory
  before acting. Preserve source hierarchy, user authority, unrelated changes,
  licenses, and evidence labels. Never replace a failed or untested gate with
  prose implying success.
- Match a Unity MCP instance by its resolved project root before mutation.
  Never use another open Editor or copied checkout as a fallback.
- Do not commit, push, create a PR, purchase an asset, upload evidence, install
  a persistent service, or mutate an issue tracker unless the current user
  request explicitly authorizes that effect.
- Maintain Skills with the active system `skill-creator`. Run its
  `quick_validate.py` against every Skill, then run
  `python -m unittest discover -s tests -v`, Python compilation, PowerShell
  parser checks, and `git diff --check`.
- The repository currently has no selected license. Do not infer redistribution
  permission or create a license text without the owner's explicit choice.
