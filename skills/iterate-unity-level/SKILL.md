---
name: iterate-unity-level
description: Deepen an existing playable Unity level through a bounded design-build-play-fix loop with explicit state transitions and independent verification. Use when a level, encounter, tutorial, puzzle, or spatial gameplay scenario already works at a basic level and must become more complex without losing resetability or causal clarity.
---

# Iterate Unity Level

Increase meaningful complexity, not merely object count. Preserve a runnable baseline while adding one coherent decision, dependency, state, or recovery loop tied to the level's core rule.

## Establish the level contract

Read the current design, scene architecture, implementation notes, and latest play evidence. State the iteration thesis in one sentence: what new player reasoning or action this iteration introduces and why it serves the core loop.

Define the required state path before editing:

| State | Entry trigger | Player evidence | Allowed actions | Exit or recovery |
| --- | --- | --- | --- | --- |
| Initial | Level start or reset | What proves a clean start | Intended opening actions | First meaningful transition |
| Intermediate | Valid progress | What changed and why | New choices | Completion or another state |
| Blocked/invalid | Invalid or premature action | Clear rejection feedback | Repair or retreat | Return to a valid path |
| Complete | Win condition | Unambiguous completion | Exit or replay | Reset/reload contract |

Add extra states only when the design requires them. Specify reset, replay, death, scene reload, and repeated-interaction behavior.

## Update the contract before implementation

Update the authoritative design or implementation record with the new state transition and acceptance cases. Keep confirmed behavior separate from proposed polish. If the added complexity requires new sourced art, create a bounded art requirement and route it through `search-game-art`; do not import speculative packs.

## Build the iteration

Use `build-unity-scene` for project-aware scene and prefab changes. Respect established code ownership, generated-scene builders, naming, folders, and asset provenance. Implement the smallest end-to-end slice that demonstrates the new state or decision before adding polish.

Before invoking that builder or the later playtest, pass the canonical authorized
Unity project root in the handoff and require the downstream Skill's
`mcpforunity://project/info` / `data.projectRoot` exact-match gate. A route must
stop on `UNITY_PROJECT_MISMATCH`; it must not choose an Editor by display name or
silently reconnect to another checkout.

Keep the previously working path runnable. Validate compilation, scene wiring, component references, navigation or collision behavior, and Console cleanliness before playtesting.

## Play the complete loop

Use `play-unity-game` as an independent consumer of the design contract. Test:

1. a complete valid path;
2. at least one invalid or premature action and its feedback;
3. the recovery or escape path;
4. reset or reload;
5. a fresh second complete path after reset.

Player-feel claims require player-like input. Label Editor-only or automation-only evidence honestly and do not use it to manufacture a playability pass.

## Fix and close

Route design defects to planning, asset/import defects to art, and code/scene defects to programming. After any fix, clear stale diagnostics and rerun the affected path from a clean start. A green state variable does not override compile errors, exceptions, broken references, or reproducible player-facing failures.

Return the iteration thesis, changed contract, implementation paths, art provenance changes, validation evidence, play evidence, known limitations, and remaining proposals.

## Language alignment

Match user-facing explanations, prompts, documentation, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.
