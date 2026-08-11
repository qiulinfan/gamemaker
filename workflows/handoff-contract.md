# Handoff contract

Use this record at every specialist-to-producer boundary. Store it in the target
project's normal issue, receipt, or design system; this repository defines the
shape but is not the production database.

~~~yaml
schema_version: 1
parent:
  id: ""
  outcome: ""
slice:
  id: ""
  route: design|level|feature|system|sourced_art|technical_art|mixed
  status: prototype|validated|blocked|failed
workspace:
  canonical_root: ""
  revision: ""
  dirty_paths_before: []
ownership:
  role: ""
  write_roots: []
  forbidden_roots: []
inputs:
  authoritative: []
  hashes: {}
outputs:
  - path: ""
    role: ""
    sha256: ""
evidence:
  design: []
  tests: []
  diagnostics: []
  assets_and_licenses: []
  visual: []
  play: []
  reset_or_replay: []
gates:
  - id: ""
    result: pass|fail|not_tested
    evidence: []
external_effects:
  authorized: []
  performed: []
limitations: []
next_owner: ""
next_action: ""
~~~

## Rules

- Name the canonical workspace and exact revision; a branch name alone is not
  an artifact identity.
- Hash immutable sources and durable deliveries when the selected Skill
  requires it.
- Use `not_tested` with a reason. Never omit an expected gate to manufacture a
  pass.
- Separate local validation, mounted-folder submission, and independently
  confirmed remote visibility.
- Include source and license evidence before an acquired asset becomes accepted
  project content.
- After a fix, issue a new handoff for the new artifact. Do not edit the old
  receipt to imply its evidence covered a later revision.
- The producer independently inspects the actual outputs before acceptance.
