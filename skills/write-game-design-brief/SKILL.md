---
name: write-game-design-brief
description: Turn a raw game idea or production issue into a source-grounded, implementable, and testable design brief for downstream Unity programming and sourced-art work. Use when a planner agent must define player behavior, rules, states, feedback, content needs, and acceptance cases without implementing the feature or level.
---

# Write Game Design Brief

Produce the smallest design contract that lets art and programming work without guessing. Preserve the project's source hierarchy and never present a proposal as an already approved fact.

## Read the design context

Read the full issue and the project's authoritative design documents. Locate the established design-document path and conventions before creating a new file. Separate findings into:

- confirmed facts from the issue or authoritative sources;
- synthesis that follows from multiple confirmed facts;
- proposals that still require producer or user acceptance;
- open questions that materially affect implementation.

When sources conflict, report the conflict and its impact rather than silently choosing one.

## Define the contract

Write a brief containing only relevant sections from this structure:

1. **Player promise** — what the player can perceive, decide, or achieve.
2. **Scope and non-goals** — what this issue changes and deliberately leaves alone.
3. **Player flow** — entry, meaningful actions, feedback, success, failure, recovery, and exit.
4. **Rules and state model** — initial state, triggers, transitions, invalid actions, terminal states, and reset/reload behavior.
5. **Entities and data** — responsibilities, authored data, runtime state, and persistence expectations.
6. **Presentation requirements** — visual roles, theme, readability, animation verbs, audio/VFX cues, camera needs, and technical constraints.
7. **Programming requirements** — system boundaries, external interfaces, events, scene integration, save/load needs, and performance constraints.
8. **Acceptance cases** — happy path, invalid path, recovery path, reset/replay, and regression expectations.
9. **Open decisions** — owner, deadline or blocking point, and safe default when one exists.

Express art needs as functional roles rather than named assets: for example, “humanoid enemy with idle, locomotion, hit, and death actions.” This lets the art worker search appearance, theme, license, and animation coverage together.

## Make acceptance observable

Each acceptance case must state:

- starting conditions;
- player or system action;
- visible or inspectable result;
- failure evidence;
- reset requirements;
- whether the check is automated, Editor-inspected, or independently played.

Avoid criteria such as “feels good” without concrete indicators and an identified human judgment gate.

## Handoff

Return the brief path, confirmed decisions, proposals awaiting approval, art requirement matrix, programming contract, dependencies, and acceptance cases. Do not edit Unity scenes, production code, or imported assets. Send unresolved scope decisions to the producer.

## Language alignment

Match user-facing explanations, prompts, design documents, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.
