# AutoTA repository conventions

AutoTA is a portable technical-art pipeline: five Skills (search, 2D, 3D,
hosted generation, rig alignment), one shared handoff/receipt contract, two
Codex agents, and one opt-in profile. It is the midstream between a game
project's design brief (upstream) and that project's engine integration
(downstream).

Rules for working in this repository:

- Skills must stay portable. Never write personal paths, project identities,
  cloud endpoints, or artifact hashes into `skills/`; `scripts/validate_bundle.py`
  enforces the forbidden-token list. Project facts belong in `profiles/`.
- Profiles are opt-in only: load one only when the user or target repository
  explicitly selects it. A profile can narrow paths; it cannot expand
  authority or weaken validation, licensing, or workspace boundaries.
- Evidence discipline: deliveries stay `prototype` until named gates pass;
  never convert `not_tested` into a pass; receipts follow
  `workflows/handoff-contract.md`.
- Engine boundary: AutoTA does not mutate a game project's scenes or code on
  its own authority. For Unity-MCP-mutating steps that remain inside kept
  Skills, match the instance by resolved project root before every mutation.
- Claude Code boundary: integration is skills-only via
  `scripts/link-claude-skills.sh` / `.ps1`, deliberately independent of
  `workflow.bundle.toml` and the receipt-backed Codex link contract; those
  scripts install no agents, workflows, profiles, or receipts. Skills resolve
  bundled scripts by probing the Codex home then the Claude Code home.
- After changing the Skill/agent/workflow/profile inventory, update
  `workflow.bundle.toml` in the same change and run the full validation path
  in `README.md` before reporting success.
