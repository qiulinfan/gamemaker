# Game production workflow

This is the portable end-to-end route. Use one bounded vertical slice at a time
and keep the producer responsible for integration and acceptance.

## Authority and context order

Apply authority in this order:

1. system, developer, and current user instructions;
2. target repository instructions and explicit design-source hierarchy;
3. the accepted parent outcome and current slice contract;
4. this bundle's portable Skills and workflows;
5. an explicitly selected profile for environment adaptation only;
6. historical examples as non-authoritative evidence.

A profile cannot redefine game design, broaden writes, authorize external
effects, or turn an untested gate into a pass.

## Route map

| Stage | Owner | Required output | Exit gate |
| --- | --- | --- | --- |
| Intake | Producer | Parent outcome, canonical workspace, authority ledger | Scope and target are identifiable |
| Triage | Producer | Route and smallest vertical slice | One observable outcome |
| Design | Designer | Brief, state model, art/programming contract | Definition of ready |
| Art discovery | Art scout | Requirement matrix, provenance, audited candidate | License and technical fit |
| Art production | Technical artist | Reversible asset plus receipt | Technical, visual, and round-trip gates |
| Implementation | Programmer | Runnable code/scene/prefab slice plus tests | Compile and focused checks |
| Independent play | Playtester | Read-only result and reproduction evidence | Real/player-like path or disclosed fallback |
| Integration review | Producer/reviewer | Evidence mapped to acceptance | Definition of done |
| Accept or iterate | Producer | Accepted slice or one bounded defect | Clean re-verification or explicit blocker |

Skip stages that do not apply. Do not skip a gate merely because its specialist
stage was skipped; for example, a feature with no new art still needs provenance
confirmation for reused assets.

## Route decisions

- Use design discovery when the player promise, rule, failure, recovery, or
  acceptance behavior is not implementable.
- Use the level route when spatial or scenario structure is the primary change.
- Use the feature/system route when reusable behavior or infrastructure is the
  primary change.
- Use sourced art when an existing licensed asset can close a defined role.
- Use technical art for original/adapted geometry, materials, rigs, animation,
  lookdev, shaders, VFX, or DCC/engine round trips.
- Use character alignment when a skinned humanoid and external skeletal clips
  must be accepted as one chain.
- For mixed work, stabilize the behavior contract, then run independent art and
  programming only where their write surfaces do not overlap.

## Evidence lanes

Keep five lanes separate until final review:

1. design evidence: confirmed decisions, state transitions, and observable
   acceptance cases;
2. implementation evidence: diff, compile state, focused tests, regressions,
   serialized references, and clean diagnostics;
3. asset evidence: source, license, hashes, modifications, technical audits,
   round trip, and engine import;
4. visual/player evidence: inspected captures and independent play through the
   real or closest player-like path;
5. operational evidence: canonical workspace, exact Unity instance/revision,
   performed external effects, and delivery locations.

One lane cannot substitute for another. A screenshot is not a license or test
result; a passing unit test is not a playability verdict; an Avatar validity flag
is not a skeleton-scale or deformation pass.

## Feedback routing

Route one bounded defect to the owner with the failing observation, expected
result, exact artifact/revision, reproduction, and required clean rerun.

- design owner: rule, scope, state, feedback, or acceptance ambiguity;
- art scout: source, license, archive, or acquisition mismatch;
- technical artist: geometry, material, rig, animation, export/import, or visual
  defect;
- programmer: code, scene, prefab, input, Console, test, runtime, or reset
  defect;
- producer: ownership conflict, stale handoff, integration mismatch, or
  unauthorized external effect.

After a fix, invalidate stale downstream evidence and rerun only the affected
dependency chain plus relevant regressions.

## Terminal results

- `accepted`: the exact integrated slice satisfies every required lane.
- `prototype`: useful and runnable, but named game-ready gates remain untested
  or intentionally deferred.
- `blocked`: missing authority, source, target, capability, or consequential
  decision prevents safe progress.
- `failed`: execution reached a required gate and the artifact failed it.

Always return useful safe artifacts and the next smallest ready action. Never
call a prototype accepted.
