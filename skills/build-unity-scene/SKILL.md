---
name: build-unity-scene
description: Read a Unity project's architecture and level requirements, then import project-ready 2D sprite deliveries or create and modify a Unity scene while respecting documented code boundaries, content structure, asset licenses, and validation workflow. Use when a programming agent needs to configure SpriteImporters and AnimationClips from an audited 2D manifest, lay out a level, wire scene objects and components, create reusable prefabs, bind existing gameplay scripts, add camera and lighting, configure build scenes, or turn a documented prototype into a technically valid Unity scene. This skill builds and validates scenes but leaves exploratory gameplay evaluation to play-unity-game.
---

# Build Unity Scene

Translate architecture and level requirements into a saved, inspectable Unity scene. Keep temporary prototype shortcuts visibly separate from production architecture.

## Read Before Building

1. Locate the Unity project by finding `Assets/`, `Packages/`, and `ProjectSettings/`.
2. Read repository instructions and inspect the worktree.
3. Read the architecture index, normally `Docs/GameFramework/README.md`.
4. Read the technical architecture, data/authoring rules, and the assigned level or prototype specification in full.
5. Read the relevant design source when the scene's gameplay or narrative intent is unclear.
6. Inspect existing scenes, prefabs, materials, input assets, build settings, and third-party notices.

Do not redesign the mechanic while laying out the scene. Report a design gap to the design agent.

## Inspect Unity

Before any Unity tool that can clear the Console, edit an object, save or reload a
scene, change settings, refresh assets, run tests, or enter Play Mode, enforce an
exact project-identity gate:

1. Resolve the authorized Unity project found above to one canonical absolute
   path. It must contain `Assets/` and `ProjectSettings/`.
2. Check `mcpforunity://custom-tools`, then read `mcpforunity://instances` and
   select the intended instance when needed.
3. Read `mcpforunity://project/info` from that selected connection. Require a
   string `data.projectRoot`, resolve it canonically, and compare it for exact
   path equality with the authorized project root. A display name, active scene,
   port, or instance label is not identity evidence.
4. If `project/info` is unavailable, ambiguous, malformed, or mismatched, make
   zero Unity mutations and stop with `UNITY_PROJECT_MISMATCH`, reporting only
   the expected and observed canonical roots.
5. Gate **every individual Unity MCP tool call that can mutate the Editor,
   project, or evidence filesystem**. Immediately before exactly one such call,
   re-read `mcpforunity://project/info`, resolve `data.projectRoot`, and require
   the exact match again; then discard that gate result and repeat for the next
   mutating call. Never reuse a connection-level, phase-level, or earlier-call
   identity check. This covers Console clear, scene/prefab save, scene
   load/reload/reset, GameObject/component/camera changes, build/settings
   changes, asset import/refresh, compilation or test execution, screenshot or
   capture, Play, and Stop. Also repeat after every reconnect, Editor restart,
   domain reload, branch/worktree switch, or MCP instance selection.
6. Read the exact editor-state resource exposed by the server and confirm that
   Unity is ready for tools.
7. Inspect the active scene, Console, project version, render pipeline,
   tags/layers, and relevant assets.
8. Search actual project shaders before assigning materials.
9. Reflect unfamiliar Unity or package APIs before writing C#.

## Import Audited 2D Art

When the input is a sprite or sprite sheet produced by
`$create-2d-game-art`, read and follow
[references/2d-sprite-import.md](references/2d-sprite-import.md) before the
first import mutation. Treat the PNG hash, JSON manifest, passing audit, and
accepted asset contract as one delivery. Configure and then re-read the exact
`TextureImporter`; consume manifest rectangles, top-left-to-bottom-left
coordinate conversion, pivots, state, direction, frame order, and
`duration_ms`; and bind every generated Sprite and AnimationClip back to the
delivery hashes. A copied PNG or plausible-looking slice is not import proof.

## Plan the Scene

Define:

- target scene path and whether it is new or existing;
- scene roots and hierarchy;
- player spawn and camera;
- main light and environment lighting;
- gameplay entities, stable IDs, triggers, colliders, and anchors;
- presentation-only set dressing;
- reusable objects that should become prefabs;
- required scripts and data assets;
- required build-settings changes;
- validation criteria.

For stateful gameplay, define the transition contract before editing the scene: initial state, valid triggers, intermediate evidence, invalid-action feedback, repair or escape path, completion, and reset/reload behavior. Make every transition observable to a later playtest without relying on private fields.

Keep gameplay truth in the documented state or component layer. Do not make animation transforms the only record of gameplay state.

## Build in Safe Order

1. Create or load the target scene.
2. Add a Camera and main Directional Light to a new scene.
3. Establish named hierarchy roots such as `Architecture`, `Gameplay`, `Set Dressing`, `Lighting`, and `UI`.
4. Block out traversal, scale, collision, spawn, and sight lines with simple geometry.
5. Add gameplay objects and semantic anchors.
6. Reuse existing licensed assets. If art is missing, use clear placeholders and hand the requirement to `search-game-art`; do not start an unrelated web search.
7. Create prefabs for objects intended for reuse.
8. Add presentation assets, materials, lighting, and atmosphere after the interaction space works structurally.
9. Save the scene and update build settings only when required by the task or framework.

Preserve unrelated scene and worktree changes. Do not overwrite an existing scene without first resolving its exact target and purpose.

If the project generates scenes or prefabs from an authoritative builder, edit that source and regenerate the artifact instead of making a one-off generated-file change that will be lost.

## Script Workflow

When scripts are required:

1. place prototype code under an explicitly named prototype namespace and directory;
2. place production code in the architecture-defined assembly and layer;
3. edit files with the repository's required patch workflow;
4. validate scripts;
5. refresh Unity and wait for compilation;
6. read the Console before adding new script types to GameObjects;
7. add and configure components only after successful compilation;
8. read the Console again after scene wiring.

Avoid broad singletons, hidden `FindObjectOfType` dependencies, scene-name hardcoding, and static events that survive scene changes unless the architecture explicitly permits them.

## Validate Without Playtesting

Perform the programming-agent checks:

- scene saves successfully;
- no missing scripts or broken prefabs;
- required Camera and light exist;
- component references are assigned;
- colliders and triggers use intended layers;
- key objects are reachable by hierarchy and stable identifier;
- build settings are correct when in scope;
- Unity compilation has no project errors;
- scene validation reports no unresolved issues.

Do not perform exploratory gameplay or claim the scene is fun, readable, or complete. If the user also requests actual play, hand the saved artifact to `play-unity-game` as a separate pass.

When that independent playtest reports a programming defect, apply the requested fix through the same safe build workflow, clear stale Console evidence, and return a newly saved and technically clean artifact for a fresh independent pass. Never reuse the pre-fix play result as acceptance evidence.

## Handoff

Report:

- scene and prefab paths;
- hierarchy and gameplay objects created;
- scripts or data assets added;
- placeholders and external-asset dependencies;
- build-settings changes;
- compile, Console, and scene-validation results;
- known technical limitations;
- exact playtest target, controls, expected state sequence, and acceptance criteria for the playtest agent.

## Language Alignment

Match user-facing explanations, prompts, documentation, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.
