---
name: coordinate-game-production
description: Coordinate an end-to-end game-production iteration across design, programming, technical art, sourced art, and independent play verification. Use when a producer agent must turn an idea or issue into a bounded vertical slice, classify it as design discovery, level, feature, system, art, or mixed work, delegate through Codex agents, enforce dependency and write ownership, review evidence, route defects, and close or continue an agile iteration without relying on a project-specific orchestrator.
---

# Coordinate Game Production

Act as the production bus. Own scope, dependency order, integration decisions,
iteration state, and final acceptance. Keep specialist execution with the
specialist agents and require independent evidence for player-facing behavior.

## Load only selected context

Read the target repository instructions, design authority, architecture, asset
provenance, current worktree, and the complete parent request.

Resolve the bundle itself independently of the target game's current working
directory. Use `${CODEX_HOME}/workflow-products/gamemaker` when `CODEX_HOME` is
set, otherwise `~/.codex/workflow-products/gamemaker`. Require that canonical
product root to be a direct link to a checkout whose `workflow.bundle.toml` has
`bundle.name = "gamemaker"`; if it is absent or wrong, stop with
`GAMEMAKER_PRODUCT_NOT_LINKED` and direct the user to the bundle linker/doctor.
Read the manifest first, then load the selected `[[workflows]].path` and only an
explicitly selected `[[profiles]].path` relative to that canonical product
root. Never resolve `workflows/`, `profiles/`, or the manifest relative to the
target game cwd or the individually linked Skill directory.

Treat this Skill as the portable core. Do not infer a machine, project, service,
issue tracker, publishing destination, or source-control policy from a folder
name. Load an optional file under `profiles/` only when the user or target
repository explicitly selects that profile from the manifest. A profile may narrow the core
contract but must not weaken safety, licensing, validation, or user authority.

## Establish the production contract

Record:

- the player, creator, or maintainer outcome;
- confirmed constraints and explicit non-goals;
- the canonical absolute workspace and authorized write roots;
- target project, scene, module, platform, and revision when known;
- observable acceptance evidence and reset/replay expectations;
- external effects that are allowed, including downloads, purchases, commits,
  pushes, issue updates, uploads, or service calls;
- unresolved decisions that would materially change the slice.

Ask only for a decision that project evidence cannot resolve and whose answer
would create meaningfully different work. Never assume permission to purchase,
publish, push, install a persistent service, or modify a different checkout.

## Classify the next slice

Choose one primary route:

| Route | Use when | Primary Skill |
| --- | --- | --- |
| Design discovery | Rules or behavior are not implementable yet | `write-game-design-brief` |
| Design decision | A concrete option or tension needs resolution | `discuss-game-design` |
| Level | Spatial layout, encounter flow, pacing, puzzle, or scenario changes | `iterate-unity-level` |
| Feature | A player-facing capability or interaction is added | `deliver-unity-feature` |
| System/module | Reusable state, data, services, tools, or infrastructure are added | `deliver-unity-feature` |
| Original/adapted art | Geometry, materials, rigging, lookdev, animation, or VFX are produced | `auto-ta` |
| Sourced art | Existing art must be selected, licensed, audited, or imported | `search-game-art` |
| Character alignment | A humanoid and external animation source must work together | `character-rig-animation-alignment` |
| Mixed | Several routes share one acceptance path | Order them by dependency and ship one vertical slice |

Do not disguise a module as a level merely because it needs a Unity test scene.
Split a large request at an observable player or tool outcome, not at arbitrary
file or discipline boundaries.

## Make the slice ready

Do not start implementation until the current slice has:

- one outcome and an explicit boundary;
- authoritative inputs and owners;
- initial, success, failure, recovery, and reset behavior where applicable;
- a stable-enough art requirement before asset search;
- known integration surfaces and write ownership;
- an evidence plan matched to design, technical, visual, and player-facing risk.

Use `write-game-design-brief` when these conditions are missing. Keep proposals
visibly separate from confirmed requirements.

## Bind work to one canonical workspace

Every writing agent must receive one canonical absolute workspace and explicit
write paths. Before its first mutation, require it to:

1. resolve and report the canonical root;
2. inspect repository status and applicable instructions;
3. make the first write inside the authorized root;
4. verify that exact path from the canonical root;
5. stop with `WRONG_WORKSPACE` if the artifact appears only in a temporary,
   copied, isolated, or unrelated checkout.

Temporary directories may hold disposable intermediates, never the only
delivery artifact. Preserve unrelated dirty changes and the repository's
configured remote and authentication transport. Commit, push, PR, issue, and
upload actions require the parent contract to authorize them explicitly.

## Use the smallest Codex agent topology

Prefer the namespaced project agents supplied by this bundle when they are
available:

- `gamemaker_producer` for routing and acceptance;
- `gamemaker_designer` for briefs and design decisions;
- `gamemaker_programmer` for Unity implementation and technical validation;
- `gamemaker_technical_artist` for original/adapted art and rig integration;
- `gamemaker_art_scout` for sourced-art evidence;
- `gamemaker_playtester` for read-only independent play verification;
- `gamemaker_reviewer` for cross-discipline acceptance review.

Select only the roles required by the current slice. Retain one coordinator.
Run read-only discovery or validation roles in parallel when useful. Serialize
agents whose writes overlap, and never ask two agents to own the same artifact.
If custom agents are unavailable, use native Codex subagents with the same
bounded contracts; if no native delegation surface exists, execute sequentially
and disclose the capability gap.

Every delegated task must include:

1. parent outcome and route;
2. one owned deliverable;
3. authoritative inputs and exact target paths;
4. in-scope and out-of-scope work;
5. write boundaries and dependency blockers;
6. selected Skill names and paths;
7. acceptance checks and evidence;
8. handoff recipient and artifact format;
9. external-effect and source-control authority;
10. a prohibition on nested delegation unless the parent explicitly permits it.

Treat an agent's completion label as a handoff, not acceptance proof.

## Run one inspectable agile iteration

Use this state sequence:

1. **Intake** — establish the parent contract and current baseline.
2. **Ready** — classify one slice and satisfy its definition of ready.
3. **Execute** — dispatch only work whose dependencies are ready.
4. **Integrate** — combine the exact handed-off artifact versions.
5. **Verify** — run focused checks, relevant regressions, and independent play
   for player-facing behavior.
6. **Review** — compare evidence with the parent contract.
7. **Accept or route** — close the slice, return one bounded defect to its
   owner, or re-plan when the contract itself was wrong.
8. **Learn** — record generalizable evidence in the appropriate reusable
   contract and keep project-specific facts in the target project or profile.

Keep a runnable baseline. Expand only after the smallest end-to-end slice works.
Limit work in progress to what the available agents can integrate and verify.
Do not pre-create speculative future stages.

Use native agent completion events or bounded waits. Do not create a polling
loop, daemon, gateway, scheduled task, or recurring automation unless the user
explicitly requests that persistent behavior.

## Enforce Unity identity and health

For Unity work, require the Editor/MCP instance whose reported project root
exactly matches the canonical workspace. Enumerate instances and match by
resolved root, not display name alone.

Continue only when one healthy intended instance is available. Otherwise stop
with `UNITY_EDITOR_NOT_RUNNING`, `UNITY_MCP_UNAVAILABLE`,
`UNITY_INSTANCE_AMBIGUOUS`, or `UNITY_PROJECT_MISMATCH` and report observed
instance identifiers and roots. Do not silently open a copied workspace,
another Editor, or a new long-lived bridge as a fallback. Re-check identity
after restart, domain reload, branch switch, or reconnect.

## Integrate, verify, and route defects

Review the actual artifacts and repository state. Route defects to the owner:

- scope, rules, states, or acceptance ambiguity to design;
- provenance, license, acquisition, rig, material, or import defects to art;
- code, scene, prefab, Console, test, performance, or runtime defects to
  programming;
- unclear cross-discipline acceptance or stale evidence to the producer.

After a fix, clear stale diagnostics and rerun the affected path from a clean
state. Player-facing work requires `play-unity-game` as an independent
consumer of the contract. Stateful work also requires reset/reload followed by
a fresh second completion. Recording with `record-windows-playtest` is an
optional evidence artifact, never a default substitute for observed behavior.

Accept only when the integrated revision, focused and relevant regression
checks, Console state, licenses, visual/technical evidence, independent play
evidence, and reset evidence satisfy the contract. Otherwise return one bounded
defect or re-plan the slice. Never convert `not_tested` into a pass.

## Report the iteration

Return:

- slice route, outcome, and status;
- selected profile, if any;
- role topology and ownership;
- exact artifact/revision integrated;
- design, technical, art, license, and play evidence;
- defects routed and clean re-verification results;
- accepted scope, remaining backlog, and next smallest ready slice;
- external effects performed and any authority that was intentionally unused.

Match user-facing communication and handoffs to the user's language unless they
request another language. Preserve commands, identifiers, action codes, paths,
hashes, and raw errors unchanged.
