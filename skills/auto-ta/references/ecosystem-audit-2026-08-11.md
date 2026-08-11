# AI art and technical-art Agent Skills audit

Audit date: 2026-08-11. This is a dated selection and test record, not a lockfile.

## Search scope

The search covered skills.sh plus GitHub projects that contain a real `SKILL.md`. About 49 query families included Blender, Maya, Houdini, ZBrush, Substance, mesh, modeling, sculpt, retopology, UV, PBR, texture, bake, rig, skin weights, animation, retargeting, motion capture, lighting, HDRI, render, shader, VFX, Unity, Unreal, Godot, ComfyUI, concept art, sprite, and image-to-3D.

The skills.sh search union contained about 2,332 unique hits. Search endpoints cap individual result sets, the index changes, and many hits are reposts, personas, web-design prompts, or unrelated uses of “image” and “model.” The catalog below groups the directly useful families after repository/path inspection. It is intended to be reproducible and operationally useful, not to imply that a dynamic public index can be mathematically exhausted.

Evidence levels are kept separate:

1. `local_e2e`: a real artifact or preview was produced and independently inspected on this machine.
2. `local_probe`: dependency, connection, or failure behavior was observed locally.
3. `static_audit`: `SKILL.md`, source, license, and execution contract were inspected.
4. `upstream_claim`: only the publisher reports validation.

## Main conclusion

No single third-party Skill safely implements a complete automatic technical artist. The useful ecosystem has four layers:

```text
plain-language brief and asset contract
  -> deterministic or provider-backed asset execution
  -> DCC and engine interchange
  -> visual, structural, animation, license, and performance gates
```

The local first-party route should be ImageGen for image sources, Blender `bpy` for deterministic asset work, `search-game-art` for licensed existing assets, and the already configured Unity MCP for an explicitly authorized project. Provider-backed 3D generation remains optional and cost/upload gated.

## Local capability baseline

| Surface | Observed state | Decision |
| --- | --- | --- |
| Blender 5.1.2 / Python 3.13.9 | Background `bpy` succeeds | Primary isolated modeling, material, rig, animation, lighting, render, export, and audit surface |
| Current Blender MCP | 22 tools exposed; read-only scene query cannot reach the add-on bridge | Do not claim live-scene control until Blender GUI/add-on responds |
| Unity 6000.5.6f1 MCP | Connected and ready; URP and Shader Graph present | Valid engine surface only for the exact user-authorized project |
| Unity optional packages | ProBuilder, VFX Graph, and Animation Rigging absent in the observed project | Do not call corresponding features installed or add packages implicitly |
| ImageGen | Built-in generation works without a user API key | Concept and texture-source route; still run tiling/channel/color-space gates |
| ComfyUI | CLI absent and `127.0.0.1:8188` unavailable | Blocked locally |
| DCC-MCP / Flue | `dcc-mcp-cli` and `flue` absent | Static candidate only; do not fabricate its tools |
| Cloud 3D providers | Meshy, Tripo, Gemini, and Tencent credential-presence probes were false | Not tested; do not spend or upload without authorization |
| Other DCCs | Maya, Houdini, Godot, OIIO/OCIO, RenderDoc, and Tracy CLIs absent | Static candidate only |

## Blender and direct DCC execution

### Strong current candidates

| Family | Coverage | License / dependency | Audit result |
| --- | --- | --- | --- |
| [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) | Modeling, material, UV, cameras, lighting, rendering, export, reference fitting, and quality loops | MIT; Blender MCP plus scientific/image Python packages | Best skills.sh Blender execution family; local `blender-modeling` artifact test passed with findings |
| [dcc-mcp/dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender) | Typed tools for mesh, UV, bake, materials, Geometry Nodes, rigging, pose, animation, lighting, render, and validation | MIT; Blender extension, sidecar, gateway | Broadest promising typed backend; not installed locally and therefore not locally E2E-tested |
| [ra100/blender-claude-plugin](https://github.com/ra100/blender-claude-plugin) | Blender 5.x knowledge for nodes, scripting, modeling, rigging, physics, and rendering | MIT; assumes the Blender Lab MCP but permits scripts | `blender-animation-rigging` passed a real local rig/IK/animation test |
| [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) `cli-anything-blender` | Stateful JSON scene, primitives, materials, modifiers, camera, lights, keyframes, render, and preview | Root Apache-2.0; Python Click/prompt-toolkit and Blender | Core preview passed, but Windows default encoding and upstream tests failed; not production-clean |
| [SFKislev/Flue](https://github.com/SFKislev/Flue) | Cross-DCC transport for Blender, Houdini, 3ds Max, Adobe, and Office apps | MIT; Python/pywin32 plus installed host | Not locally runnable; Blender Skill contains a hard-coded author path, so adapt before use |
| [jasonjgardner/blockbench-mcp-project](https://github.com/jasonjgardner/blockbench-mcp-project) | Low-poly/voxel modeling, painting, PBR, bone animation | Apache-2.0; Blockbench, plugin, Node MCP bridge | Strong for Minecraft/Hytale-like assets; Node and Blockbench route not locally tested |

RobLe3 direct slugs found in the indexed suite:

```text
blender-modeling, blender-materials, blender-pro-workflow, blender-animation,
blender-rendering, reference-to-3d, blender-export, blender-lighting,
blender-uv-texturing, blender-cameras, text-to-blender,
animation-quality-gate, wireframe-to-3d, blender-skill-harmonizer,
reference-analysis-validator, quality-refinement-autoloop, contour-to-mesh,
orthographic-registration, multiview-fit-loop, atlas-uv-fitting,
texture-driven-mesh-fitting, landmark-fit-repair, reference-look-calibration,
fit-repair-optimizer, texture-state-animation, mascot-logo-reconstruction,
closed-surface-uv-coverage, source-part-segmentation,
multiview-constraint-solver, orbital-hud-motion
```

dcc-mcp Blender slugs found in the source suite:

```text
blender-animation, blender-asset-source, blender-attributes, blender-camera,
blender-collection, blender-dev, blender-export-preset, blender-expressions,
blender-extensions, blender-geometry-nodes, blender-geometry,
blender-import-to-scene, blender-interchange, blender-light-rig,
blender-lighting, blender-material-library, blender-materials,
blender-mesh-ops, blender-mesh, blender-node-graph, blender-objects,
blender-physics, blender-pipeline, blender-pose-library,
blender-render-farm, blender-render, blender-rigging,
blender-scene-assembly, blender-scene, blender-scripting,
blender-shader-nodes, blender-shot-export, blender-texture-bake,
blender-uv-ops, blender-validation
```

### Useful knowledge or validation layers

- [affaan-m/ECC blender-motion-state-inspection](https://skills.sh/affaan-m/everything-claude-code/blender-motion-state-inspection): animation sampling and QA for foot slide, ground penetration, twist, and scale drift. It needs a locally implemented state exporter.
- [arjun988/blender-skills](https://github.com/arjun988/blender-skills): a large MIT knowledge suite. Direct TA slugs include `animation`, `asset-optimization`, `blender-modeler`, `camera-cinematography`, `character-artist`, `cloth-sim`, `collision-proxy`, `compositing`, `creature-artist`, `environment-artist`, `export-pipeline`, `geometry-nodes`, `hair-groom`, `hard-surface`, `lighting`, `lod-pipeline`, `lookdev`, `materials`, `physics-sim`, `procedural-modeling`, `prop-artist`, `qa-review`, `rendering`, `retopology`, `rigging`, `scene-assembly`, `sculpting`, `texture-workflow`, `uv-workflow`, `vehicle-artist`, and `vfx-fx`. Many are checklists rather than executable operations.
- [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills): Apache-2.0 knowledge for `create-game-assets`, shader programming, engine animation, Godot 3D/shaders, Unreal Niagara, and Three.js materials/lighting.
- [MengTo/Skills build-rigged-game-assets](https://skills.sh/mengto/skills/build-rigged-game-assets): MIT delivery/manifest contract for skeletons, clips, sockets, equipment, collisions, LOD, weights, and runtime evidence; it does not build the rig.
- [calesthio/generative-media-skills 3d-asset-production](https://skills.sh/calesthio/generative-media-skills/3d-asset-production): MIT asset contract and glTF inspection layer for topology, axes, pivots, UV/PBR, LOD, skin/rig handoff, formats, provenance, and engine acceptance.

### Deprioritize or exclude

- Dev-GOM `blender-toolkit` describes useful Mixamo/Rigify retargeting, but its advertised `blender-retargeting/SKILL.md` path was missing during the audit. Do not depend on it until source integrity is restored.
- TMHSDigital Blender Developer Tools has strong Blender 4.5/5.1 CI examples, but CC-BY-NC-ND-4.0 prohibits commercial reuse and derivatives. It may be studied only within those terms; do not copy it into this Skill.
- `3djianmo` produces reference renders rather than an editable OBJ/FBX/STL deliverable.
- Several OpenClaw Blender Skills name MCP tools that do not match the tools actually exposed here. Topic similarity is not compatibility.

## Other DCC hosts and interchange infrastructure

The young [dcc-mcp organization](https://github.com/dcc-mcp) is the broadest source of real DCC-focused Skills outside the main skills.sh results. Most adapters are MIT and expose typed tools, but the projects are new and each still needs an isolated host smoke test.

| Host / layer | Relevant Skills | Requirements and boundary |
| --- | --- | --- |
| Maya | animation, geometry, rigging, mesh ops, materials, UV, bake, render, pipeline | Paid Maya/mayapy and sidecar; arbitrary MEL/Python should remain disabled by default |
| Houdini | geometry, HDA, KineFX, VEX, USD LOPs, Karma, materials, bake, render | Houdini license/hython; VEX/Python is code execution |
| 3ds Max | modeling, mesh ops, rigging, UV atlas, lookdev, materials, render, validation | Windows and paid 3ds Max/pymxs |
| ZBrush | subtools, brushes, interchange, scripting | ZBrush 2026 Python SDK; high-poly operations need bounded timeouts |
| Marmoset Toolbag | scene, lookdev, diagnostics | Paid Toolbag; new and low-adoption adapter |
| Substance Painter / Designer | project/texture sets/fills/export and procedural material graphs | Paid Adobe hosts; promising typed operations but very new |
| Maya rig extensions | mGear and AdvancedSkeleton adapters | mGear is open-source; AdvancedSkeleton carries its own license |
| OpenUSD | stage, composition, material, animation, light/camera, validation | Python OpenUSD/`pxr` required |
| MaterialX | Standard Surface and lookdev exchange | Python MaterialX required |
| OIIO / OCIO | resize, mip, tile, channel, and color-space operations | OpenImageIO/OpenColorIO CLI required |
| Lookdev turntable | ColorChecker, gray/white/chrome balls, CC0 HDRI, turntable contract | Needs a real DCC adapter and visual inspection |
| RenderDoc / Tracy | GPU capture, draw/shader/texture inspection, CPU/GPU timing | Matching tools and an instrumented/runtime application required |

## AI generation, image, texture, and asset sources

| Skill family | Capability | Authorization / risk | Decision |
| --- | --- | --- | --- |
| Built-in `imagegen` | Concepts, source images, masks, sprites, texture source | Managed built-in route | Use, then validate dimensions, seams, map semantics, and color space |
| [meshy-dev/meshy-3d-agent](https://github.com/meshy-dev/meshy-3d-agent) | Text/image-to-3D, texture, remesh, UV, humanoid rig, animation, conversion | Meshy Pro key, credits, upload, provider terms | Optional provider behind explicit cost/upload gate |
| calesthio `tripo-3d` / `meshy-3d` | Executable REST recipes plus cost, licensing, rig, retarget, conversion, and QA guidance | Provider key and credits | Strong provider knowledge; test only with authorization |
| dcc-ai Hunyuan3D / Tripo3D | Submit/poll/download provider adapters | Tencent or Tripo credentials and cloud cost | Optional; returned output still needs full QA |
| [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills) | Tripo/Gemini-driven web 3D production | Tripo/Gemini keys; Web/Three.js target | Useful for web games, not a Blender/Unity substitute |
| [EachLabs/skills](https://github.com/EachLabs/skills) | Wrapped media/image/3D/game-asset generation | EachLabs key; opaque provider routing | Lower transparency than direct provider Skills |
| [MCKRUZ/ComfyUI-Expert](https://github.com/MCKRUZ/ComfyUI-Expert) | Workflow/API/prompt/video/LoRA knowledge | Local ComfyUI/GPU/models; repository archived | Not a core dependency; local service absent |
| CLI-Anything ComfyUI | Small localhost REST wrapper | Running local ComfyUI | Prefer over archived expert suite when ComfyUI exists |
| [SpriteCook/skills](https://github.com/SpriteCook/skills) | 2D assets, animation, tilesets, UI kits, Godot import | Account/credits | Strong optional 2D provider |
| inference-sh / Godot asset generator | Image generation, character sheets, upscaling, sprites | Cloud CLI/token and credits | Optional 2D source, not mesh/rig execution |
| Poly Haven / ambientCG adapters | CC0 HDRI, materials, and models | Public source; preserve provenance | Preferred free lookdev/source route |
| Sketchfab / Objaverse adapters | Broad downloadable assets | Per-item mixed licenses/token | Never generalize license from availability |

The local ImageGen texture test produced a visually usable wood source twice, but neither output passed a seamless texture gate. Attempt 1 was 1254×1254, with left/right edge difference 8.85 times ordinary horizontal adjacency. A focused second attempt improved that ratio to 6.04 but still had a visible internal and tile boundary seam. Both remain `prototype`, not PBR texture deliveries.

## Engines

### Unity

- [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp): MIT execution layer already represented by the local `unity-mcp-orchestrator`; scene, asset, material, animation, texture, shader, VFX, ProBuilder, profiling, tests, and build operations depend on installed tool groups/packages.
- [Unity-Technologies/skills](https://github.com/Unity-Technologies/skills): Unity Companion License; Unity 6+ CLI and live Editor command execution. Strong execution layer, not a TA oracle.
- [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills): MIT and extensive modules for importer, material, shader/Shader Graph, light, animation, ProBuilder, URP, volume, validation, optimization, and profiler. Requires installing its Unity package/local REST surface before testing.
- [meta-quest/agentic-tools](https://github.com/meta-quest/agentic-tools): Apache-2.0 and genuinely executable Movement SDK retarget configuration, but specific to Meta/Quest packages.
- Nice-Wolf-Studio Unity Skills: MIT knowledge for lighting/VFX, animation, graphics, performance, and editor tools; pair with an execution surface.

### Unreal

- [db-lyon/ue-mcp](https://github.com/db-lyon/ue-mcp): mature MIT candidate for assets, materials, animation, Niagara, PCG, import, profiling, and C++/Blueprint workflows.
- [kevinpbuckley/VibeUE](https://github.com/kevinpbuckley/VibeUE): MIT UE 5.8 tool/Skill suite with materials, animation, skeleton, UV, landscape, Niagara, and profiling.
- [EpicGames/unreal-engine-skills-for-claude-code-plugin](https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin): MIT official experimental UE 5.8 MCP Skill layer; raw tool script remains full project Python authority.
- [quodsoler/unreal-engine-skills](https://github.com/quodsoler/unreal-engine-skills): MIT knowledge for editor tools, Niagara, materials/rendering, animation, procedural generation, world/streaming, and Sequencer. It is not an Editor controller.

### Godot

- [regiellis/godot-mcp-go](https://github.com/regiellis/godot-mcp-go): MIT, broad typed editor/runtime candidate for animation, import, lighting, materials, mesh, particle, profiling, shader, skeleton, and 3D scene work. Requires Godot 4.7+.
- [TheDivergentAI/GD-Agentic-Skills](https://github.com/TheDivergentAI/GD-Agentic-Skills): LGPL-3.0 knowledge/CLI suite for shaders, animation, particles, procedural 3D, lighting, materials, and performance. Load targeted modules rather than all Skills.
- dcc-mcp Godot: MIT adapter family for assets, 3D scenes, animation trees, particles, profiling, shaders, and runtime; newer and less proven than `godot-mcp-go`.

## Local test record

| Target | Evidence | Verdict |
| --- | --- | --- |
| RobLe3 `blender-modeling` | Built and reopened a 2 m crate: 5 independent mesh objects, Bevel→Triangulate stacks, 60 source / 284 evaluated triangles, closed topology, exact saved hash; neutral render inspected | `pass_with_findings`: behavior/artifact passed, but the worker wrote two unrequested validation files |
| ra100 `blender-animation-rigging` | Built and reopened a 3-bone, weighted two-segment arm with IK/pole and `ReachLoop`; 19/19 producer assertions plus independent Blender audit and 3-pose visual check | `pass` |
| CLI-Anything `cli-anything-blender` | 25/25 JSON commands; state/undo/redo; real 160×160 hero/workbench previews from Blender 5.1 | `fail` overall: core flow passes only with UTF-8 workaround; 229 upstream tests passed and 10 failed |
| Built-in `imagegen` texture source | Two generated images, decoded and 2×2 tiled; seam metrics and visual inspection | `prototype`: appearance useful, seamless/PBR contract failed |
| Bundled `blender_asset_audit.py` schema 2.0 | Positive static/rig/animation and clean-GLB paths; meter/unit-scale, empty-scene, fake-weight, empty/mismatched-slot Action, partial UV collapse, missing required images, GLB unit override, NaN, output confinement, usage/internal-error, triangle-budget, seam-split, inward-shell, and far-translated-small-shell regressions | `pass`: gates exit 2, configuration/internal errors exit 3; raw seam splits remain visible while 1e-6 m position-welded geometry prevents false hole reports; per-component signed volume rejects the retained inward-shade GLB and remains translation-invariant |
| Bundled round-trip comparator schema 2.0 and receipt validator | Compared the 884-triangle lamp source against a distinct clean Blender GLB import and actual delivery hash; checked hierarchy, transforms/pivots, canonical triangles, the explicit image-free constant-Principled material profile, shell orientation, weights, joint rest matrices, clip identity and sampled motion; independently recomputed the full hashed evidence chain | `pass`: same-report substitution, transformed imports, strict UV mismatch, failed-evidence relabeling, stale/underspecified receipts, invalid contract evidence, empty check sets, hidden failed checks, fake comparator identity, audits missing schema/verdict, complex material profiles, unaudited editable-source substitution, and a different file relabeled as the main engine delivery all fail; 0.5 mm bounds drift passes a 1 mm tolerance while 2 mm fails |
| `$auto-ta` blind run 2 | Built a 0.60 × 0.40 × 1.00 m mechanical inspection lamp with 15 meshes, 3 materials, 884 triangles, 3 deform bones, normalized one-influence weights, and a named 24 fps loop; inspected front/rear/side renders and a pose sheet; an independent review found the first lamp-shade shell globally inverted, so the new winding gate rejected it and the asset was rebuilt | `validated` for corrected Blender→GLB→clean-Blender after preserving the clip name, requiring outward winding per closed shell, and explicitly allowing UV reparameterization for a no-bitmap material contract; Unity import remains `not_tested` and no Unity project was mutated |
| Live Blender MCP | `get_scene_info` read-only probe | `blocked`: add-on bridge not running |
| Unity MCP | Connection and package inventory only; no project mutation | `local_probe`, not a TA feature E2E test |
| Meshy / Tripo / Hunyuan / ComfyUI / DCC-MCP | Dependency/credential/service probes | `not_tested` or `blocked`; no spend, upload, installation, or fabricated call |

## Security and licensing decisions

- Exclude the indexed `material-generator`: its instructions contained what appeared to be a live MiniMax credential, and its security scan was suspicious. Do not install, execute, or reproduce the secret.
- Do not copy or adapt repositories without an explicit license. A README saying “MIT” is insufficient when the repository has no license file and GitHub does not identify one.
- Treat CC-BY-NC-ND and PolyForm Noncommercial projects as noncommercial references under their exact terms, not as source for this distributed Skill.
- Keep DCC gateways on loopback. Disable arbitrary Python, MEL, VEX, and runtime eval when typed operations suffice.
- Never equate an MCP/CLI installation, a webpage badge, provider completion, render, or successful export command with a validated game asset.
- Deduplicate exact mirrors before evaluating. Examples observed in the SkillHub set include `gpu-shader-toolkit`/`yjkj-gpu-shader-toolkit` and `yq-vfx-pipeline-automation`/`yjkj-yq-vfx-pipeline-automation`.

## Adoption tiers

1. **Use now:** local ImageGen as source imagery, headless Blender `bpy`, the bundled audit, `search-game-art`, and exact-project Unity MCP.
2. **Isolated next tests:** dcc-mcp Blender typed adapter, OIIO/OCIO texture validation, MaterialX/OpenUSD interchange, and a clean-project Unity import round trip.
3. **Only with explicit authorization:** Meshy/Tripo/Hunyuan, external uploads, paid DCCs, new Unity packages, gateways, and provider keys.
4. **Reject until fixed:** secret-bearing Skills, missing-license adaptations, missing advertised source paths, hard-coded author paths, incompatible MCP schemas, and image-only “3D model” substitutes.

## Ongoing experience feedback loop

For each real Blender production run, classify the needed capability first, then select at most the smallest relevant external Skill family from this audit or a newly verified upstream source. Re-check its exact repository path, license, dependencies, tool names, and current release; run it on an isolated representative slice before letting it touch the authored scene.

After the run, separate three outputs: project-specific asset decisions stay in the game repository, external-skill compatibility evidence stays in this dated audit or a successor audit, and only generalizable production or acceptance rules enter `auto-ta` or a specialized local Skill. A failure should become a reusable diagnostic order or gate only when the evidence identifies the cause; do not promote a one-off color, shader value, asset name, or workaround into a universal preset.
