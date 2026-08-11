# End-to-end acceptance gates

## Contents

1. Safety preconditions
2. Gate A — package and compilation
3. Gate B — server and bridge
4. Gate C — MCP discovery
5. Gate D — Hierarchy
6. Gate E — Inspector
7. Gate F — Play and Game View
8. Gate G — restart persistence
9. Gate H — repository review
10. Evidence template

## Safety preconditions

Before the full test:

- Unity has finished compilation and asset updates.
- The active scene is not dirty.
- Play Mode is stopped.
- The Console is cleared or the timestamp boundary is recorded.
- The screenshot output folder is generated/ignored.
- The intended Unity instance is active, and `mcpforunity://project/info`
  `data.projectRoot` resolves to the explicit canonical project root supplied to
  the full test.
- No unrelated user edit will be overwritten by Stop, reload, or scene load.

If any precondition fails, perform the read-only gates only.

## Gate A — package and compilation

Pass when:

- `Packages/manifest.json` contains the official pinned package source;
- `Packages/packages-lock.json` resolves it;
- Unity shows the package window/menu;
- the latest compilation has no `error CS...`;
- domain reload completes.

Do not count preexisting non-compiler service errors as compiler failures.

## Gate B — server and bridge

Pass when:

- the configured loopback port listens;
- the launch log names the expected endpoint;
- Unity's WebSocket bridge connects;
- the log identifies the intended project;
- Unity-side tools register.

Fail when only the Python server is listening without Unity registration.

## Gate C — MCP discovery

Pass when an MCP client can:

- initialize a streamable HTTP session;
- list tools;
- list resources;
- find required tools:
  - `manage_scene`
  - `manage_gameobject`
  - `manage_components`
  - `manage_editor`
  - `manage_camera`
  - `read_console`
- find editor, instance, project, and scene resources.
- resolve the project root returned by `mcpforunity://project/info` and match it
  exactly to the locally authorized Unity project root before mutation.

Tool counts are evidence, not a stable contract.
Missing or mismatched project identity is a hard failure. Do not clear the
Console, modify a component, reload a scene, enter Play Mode, capture a
screenshot, or stop a different Editor instance.

## Gate D — Hierarchy

Pass when:

- `manage_scene get_active` returns the expected scene;
- `manage_scene get_hierarchy` returns root objects;
- paging fields are respected;
- root names, instance IDs, components, and transforms reflect the live Editor.

For the standard Unity starter scene, common roots are Main Camera, Directional Light, and Global Volume. Do not require these names in custom projects.

## Gate E — Inspector

Read the target GameObject and component using resource templates:

```text
mcpforunity://scene/gameobject/{instance_id}
mcpforunity://scene/gameobject/{instance_id}/components
mcpforunity://scene/gameobject/{instance_id}/component/{component_name}
```

Pass the read-only gate when a known component property matches the Editor.

For a mutation gate:

1. require a clean scene with a saved path;
2. read the original value in Edit Mode;
3. set a harmless value with `manage_components set_property`;
4. read it back;
5. restore the original value;
6. reopen the same scene from disk with a tightly scoped `execute_code` call instead of saving;
7. reacquire the GameObject because instance IDs change on reload;
8. verify the serialized value returned to the original;
9. verify the scene is clean.

Never retain an instance ID across domain reload or Play Mode transition without re-reading the Hierarchy.
A historical 2026-07-31 setup rejected both generic component writes and
specialized camera writes in Play Mode. Treat that as dated evidence, inspect
the connected tool schema and behavior, and never infer present capability from
the old result.

## Gate F — Play and Game View

Pass when:

- `manage_editor play` succeeds;
- editor state reports `is_playing=true`;
- the target Camera exists in the runtime Hierarchy;
- `manage_camera screenshot` requests `capture_source=game_view`;
- the asynchronous output becomes a non-empty image;
- the image dimensions and format are valid;
- Console results are collected;
- `manage_editor stop` succeeds in all paths;
- final editor state reports not playing and not changing.

Suggested output:

```text
Temp/MCPValidation/unity-mcp-gameview.png
```

Use a bounded wait for both Play Mode and screenshot creation.

## Gate G — explicitly authorized restart persistence

Skip this gate for read-only diagnosis and bounded current-session setup. A
missing persistence result is `not_authorized`, not a failure of those modes.
Run this gate only after the user explicitly confirms a persistent background
server and Editor-load Auto-Start. Then enable `Auto-Start Server on Editor
Load` and:

1. confirm the active scene is clean;
2. quit Unity normally;
3. confirm the old server exits or releases the port;
4. reopen the exact project with the exact Unity version;
5. wait for compilation/import;
6. confirm a new server process listens;
7. confirm the Unity plugin registers;
8. repeat MCP discovery and a read-only Hierarchy call.

This gate distinguishes a live one-off setup from a reusable machine configuration.
Never turn a diagnose/repair request into persistent setup to make this gate pass.

Separately restart Codex after configuring MCP and confirm the native Unity tools appear.

## Gate H — repository review

Pass when:

- `git diff --check` succeeds;
- generated caches/screenshots are ignored;
- package and project-setting migrations are understood;
- the active scene is clean;
- Play Mode is stopped;
- no unrequested commit or push occurred.

Expected versioned changes may include:

- `.codex/config.toml`;
- `Packages/manifest.json`;
- `Packages/packages-lock.json`;
- Unity-serialized migrations under `Assets/` and `ProjectSettings/`.

Unexpected changes require inspection, not automatic reversion.

## Evidence template

Use this compact handoff:

```text
Unity:
MCP package:
Endpoint:
Config scope:
Auto-start after Unity restart:

Discovery:
- tools:
- resources:
- Unity-side registered tools:

Hierarchy:
- active scene:
- roots sampled:

Inspector:
- object/component:
- property read:
- runtime mutation and restoration:

Play/Game View:
- entered:
- screenshot:
- stopped:
- final scene dirty:

Compilation:
- C# errors:
- unrelated Console noise:

Repository:
- changed files:
- commit/push status:

Remaining action:
```
