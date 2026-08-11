---
name: deliver-unity-feature
description: Deliver a Unity module, feature, or system as a bounded architecture-implementation-validation loop, including scene integration and independent play evidence only when player-facing behavior requires them. Use when the requested work is reusable functionality, data or state infrastructure, tools, services, or a gameplay capability rather than primarily a level-layout change.
---

# Deliver Unity Feature

Build the smallest coherent end-to-end slice that proves the requested capability. Do not force a headless module into a level workflow merely to make it visible.

## Define the feature contract

Read the issue, design brief, architecture documents, code boundaries, tests, and existing patterns. Define:

- observable outcome and explicit non-goals;
- callers, entry points, outputs, events, and error behavior;
- data ownership, runtime state, lifecycle, and persistence;
- public interfaces and compatibility requirements;
- scene, prefab, inspector, tool, or user-facing integration points;
- performance, platform, and determinism constraints;
- acceptance and regression cases.

Resolve consequential architecture questions before implementation. Prefer the project's established patterns and dependencies; do not add abstraction for hypothetical future use.

## Choose the verification surface

Match evidence to the work:

- pure logic or data module: focused unit or Edit Mode tests;
- Unity lifecycle or integration: integration or Play Mode tests and Inspector evidence;
- scene-wired capability: compile, reference, and runtime scene validation;
- player-facing behavior: independent `play-unity-game` evidence;
- persistent or resettable state: save/load, reset/reload, and a fresh second run.

A test scene is a verification fixture, not proof that the request was a level.

## Implement a runnable slice

Keep concerns cohesive and write within documented ownership boundaries. Implement in this order when applicable:

1. contract and data model;
2. core behavior;
3. Unity lifecycle or service integration;
4. scene, prefab, Inspector, or tool wiring;
5. feedback and failure handling;
6. focused tests and documentation.

Use `build-unity-scene` for scene and prefab integration. Route required external art through `search-game-art`; the feature worker must not silently substitute unlicensed or untracked assets.

Every `build-unity-scene` or `play-unity-game` handoff must name the canonical
authorized Unity project root and require the downstream Skill to compare it
exactly with `mcpforunity://project/info` `data.projectRoot` before Unity
mutation or Play. Stop on `UNITY_PROJECT_MISMATCH`; an instance label, scene
name, or port is not sufficient identity evidence.

## Validate and regress

Run the narrowest useful tests first, then the integrated checks. Verify compilation, Console cleanliness, serialized references, domain reload behavior, enable/disable or teardown behavior, and the documented failure path. For player-facing work, play the capability from its real entry point rather than mutating private state to force success.

After any fix, clear stale diagnostics and rerun from a clean state. Stateful features require reset or reload followed by a second successful run. Do not accept a feature while relevant compile errors, exceptions, broken references, failed tests, or reproducible regressions remain.

## Handoff

Return the feature contract, changed files, public interfaces, integration instructions, tests and results, play evidence when applicable, asset provenance changes, known limitations, and follow-up proposals. Clearly separate completed scope from optional extensions.

## Language alignment

Match user-facing explanations, prompts, documentation, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.
