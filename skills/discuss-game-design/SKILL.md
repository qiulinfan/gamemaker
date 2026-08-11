---
name: discuss-game-design
description: Read a game's design documents and discuss a concrete game-design decision while preserving source hierarchy and separating confirmed facts, synthesis, proposals, and open questions. Use when a design agent needs to understand the current vision, analyze a mechanic or loop, compare design options, resolve a design tension, define a prototype, write acceptance criteria, or prepare a clear handoff to art and programming. Discussion is read-only unless the user explicitly asks to update design documents.
---

# Discuss Game Design

Ground the conversation in the project's actual design baseline. Produce decisions that can be tested, not feature lists detached from player experience.

## Read the Baseline

1. Locate the project design index, normally `Docs/Design/README.md`.
2. Read the index and every document directly relevant to the question in full.
3. When implementation constraints matter, read the relevant `Docs/GameFramework/` documents without treating them as higher-level design facts.
4. Follow the source hierarchy declared by the project. In this project, the original proposal is the factual source when a topic document conflicts with it.
5. Search the repository for existing decisions, prototypes, tests, and unresolved questions before proposing new systems.

Do not browse the web unless the user requests research or a current external fact is necessary.

## Build a Fact Ledger

Classify important statements using the project's own labels. When none exist, use:

- **Confirmed:** explicitly established by the source or a recorded decision;
- **Synthesis:** connects existing confirmed material without adding a new promise;
- **Proposal:** a candidate solution requiring approval or a prototype;
- **Open:** ambiguous, conflicting, or missing.

Never silently upgrade a proposal to confirmed design.

## Frame the Decision

State:

- the player and situation;
- the current loop or behavior;
- the decision being made;
- the intended player experience;
- constraints from narrative, content, technology, scope, and safety;
- what evidence would distinguish a good solution from a bad one.

If the request is broad, choose the smallest decision that unlocks useful work and explain the boundary.

## Develop Options

Generate two to four materially different options.

For each option, analyze:

- what the player observes and does;
- how the mechanic produces the intended realization or emotion;
- how it connects to the core loop;
- failure and recovery behavior;
- content and authoring cost;
- technical dependencies;
- art and UI implications;
- narrative or safety risks;
- the smallest prototype that can falsify the idea.

Reject options that add activity without strengthening the project's design pillars.

## Recommend

Recommend one option when evidence supports it. Include:

- why it fits better than the alternatives;
- the assumption most likely to be wrong;
- a minimal prototype;
- measurable success and failure criteria;
- what not to build yet.

For a dream-rule puzzle, explicitly separate:

- the character premise;
- the computable rule;
- observable evidence;
- safe experiments;
- rule utilization;
- exit condition;
- repair condition;
- narrative reward.

## Discuss Before Editing

Do not change documents, code, scenes, tasks, or external systems when the user only asks to read, review, or discuss.

When the user asks to record the decision:

1. update the relevant design topic;
2. preserve the fact labels;
3. add or update a decision record;
4. identify affected framework, art, and programming documents;
5. keep unresolved questions visible.

## Handoff

Lead with the recommended decision or the exact unresolved choice.

Then provide:

- current baseline and source confidence;
- options and tradeoffs;
- recommended prototype;
- success criteria;
- risks and open questions;
- **art handoff:** mood, readable states, required assets, and visual evidence;
- **programming handoff:** required state, inputs, outputs, failure behavior, and technical unknowns;
- **playtest handoff:** scenarios that must be played and what observations matter.
