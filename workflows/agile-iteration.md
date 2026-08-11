# Agile iteration state machine

Run one inspectable slice through these states. A production run may end between
states and resume from a recorded handoff; it must not rely on an in-memory
polling loop.

| State | Required record | Allowed transition |
| --- | --- | --- |
| `intake` | outcome, authority, canonical workspace, baseline | `ready`, `blocked` |
| `ready` | route, slice, owners, dependencies, evidence plan | `executing`, `blocked` |
| `executing` | owned artifacts and current revisions | `integrating`, `failed`, `blocked` |
| `integrating` | exact handed-off artifact versions | `verifying`, `executing`, `failed` |
| `verifying` | focused, regression, art, and play evidence | `reviewing`, `executing`, `failed`, `blocked` |
| `reviewing` | evidence-to-acceptance map | `accepted`, `executing`, `ready` |
| `accepted` | completion receipt and remaining backlog | next `intake` only |
| `blocked` | exact missing authority/capability/input | prior state after resolution |
| `failed` | failed gate and retained evidence | `ready` or `executing` after triage |

## Definition of ready

A slice is ready when:

- the outcome is observable and smaller than the parent epic;
- scope and non-goals are explicit;
- confirmed facts, proposals, and open decisions are separated;
- starting, success, invalid/failure, recovery, and reset behavior are defined
  where applicable;
- canonical workspace, target artifact, and write ownership are unambiguous;
- dependencies and integration order are known;
- asset roles are stable enough to search or build;
- each required evidence lane has an owner and check;
- external effects and source-control actions are explicitly allowed or denied.

## Work-in-progress policy

- Keep one integrated vertical slice in progress.
- Retain one coordinator and enough capacity for independent verification.
- Parallelize read-only discovery and disjoint writes only.
- Do not create a future-stage task before its inputs are ready.
- Stop spawning when integration or verification is the bottleneck.
- Never use nested delegation unless the parent contract explicitly requires and
  bounds it.

## Definition of done

A slice is done only when:

- the accepted design contract matches the implemented behavior;
- the exact integrated revision compiles and focused checks pass;
- relevant regression suites pass and diagnostics are clean;
- every used asset has sufficient source/license/modification evidence;
- technical-art and engine round trips pass when required;
- player-facing behavior has independent play evidence through a disclosed
  input path;
- stateful behavior completes again after reset/reload;
- known limitations are compatible with the accepted scope;
- external effects are listed and no unauthorized effect occurred;
- the next backlog item remains separate from accepted scope.

## Defect iteration

Return one defect with:

1. owner and affected state;
2. exact artifact/revision;
3. reproduction and evidence;
4. expected versus observed result;
5. permitted write boundary;
6. checks invalidated by the change;
7. clean rerun required for acceptance.

Do not patch around a design contradiction or lower a gate to make an iteration
green.

## Learning

Promote only generalizable process improvements into core Skills. Keep project
names, paths, asset choices, hashes, endpoints, and one-off workarounds in the
target repository or an explicit profile. Re-run bundle validation after any
workflow or Skill change.
