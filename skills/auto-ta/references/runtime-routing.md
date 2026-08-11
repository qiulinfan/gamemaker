# Runtime routing

Probe capabilities at the start of each job. Tool names and installed products change; this file describes decisions, not assumed inventory.

## Blender

For a known executable, verify a clean background process before depending on it:

```powershell
& $BlenderBin --background --factory-startup --python-expr "import bpy,sys; print(bpy.app.version_string); print(sys.version.split()[0]); print(bpy.app.background)"
```

Use a live Blender MCP when the user wants the currently open scene, the add-on bridge responds to a read-only query, and the exposed tool schema matches the instructions. Use headless Blender when creating or auditing a new isolated asset and the required operations are available through `bpy`.

Do not use headless Blender as a silent fallback for an unsaved open scene; it cannot see that state. Record the Blender version because `bpy` APIs, render engines, animation data, and export behavior differ between releases. Prefer feature detection over version-string branching.

Open an externally sourced `.blend` for first-pass audit only with `--background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1`, with the isolation flags placed before the file argument. Treat Python-dependent drivers as unevaluated in that pass. Enabling auto-execution requires a trusted source or explicit user authorization and a separate receipt. Confine reports to a declared output root and use fresh run ids, input hashes, and atomic writes so an old pass report cannot survive a crashed invocation.

glTF/GLB physical units are meters; the clean-import audit rejects `--meters-per-unit` overrides for those formats. Use an explicit conversion only for a non-metric `.blend` contract or FBX, whose unit and axis behavior must be declared and tested.

## Unity

Before mutation, retrieve the Editor version, ready state, project root, active scene, installed render pipeline, and relevant packages. The connected project is not automatically the authorized project.

Use core asset/material/scene operations first. Treat optional tool groups such as ProBuilder, VFX Graph, Animation Rigging, or provider-backed asset generation as unavailable until both the tool and matching Unity package are verified. Do not add a Unity package just because an MCP tool group exists.

## Image generation

Image generation is appropriate for concept sheets, decals, sprites, masks, texture source imagery, and reference turnarounds. It does not directly prove seamless tiling, physically meaningful material values, consistent orthographic views, mesh topology, rigging, animation, or engine compatibility. Validate and transform the image for its downstream role.

## Existing assets

Invoke `search-game-art` when purchasing, downloading, or adapting a licensed asset is more efficient than creating it. Keep search claims separate from archive inspection and engine validation. Never infer redistribution or commercial permission from “free.”

## Hosted 3D and texture providers

Provider-backed generation is optional. Before use, establish the provider and model/version, expected charge or quota, upload boundary, content and license terms, credential availability without exposing the secret, output formats, and independent audit route.

Provider success means only that output was returned. Run the same geometry, material, rig, visual, export, and engine gates as locally authored assets.

## Incompatible instruction sets

An external Skill is not executable merely because its topic matches. Reject or adapt it when it assumes MCP tool names that are not exposed, a different agent runtime or hard-coded home directory, an absent CLI/gateway/DCC/add-on/package/service, implicit installation or credential use, or a render image as a substitute for an editable 3D deliverable.

Record the mismatch in the receipt. Do not fabricate tool calls named by the external Skill.
