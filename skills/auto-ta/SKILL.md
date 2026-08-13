---
name: auto-ta
description: "A novice-friendly 3D Technical Art Skill for game assets: turn a plain-language request into an asset contract, create or adapt 3D geometry, UVs, PBR materials, rigs, animation, lighting, shaders, VFX, exports, and Unity imports, then validate the real artifacts. Use for 3D models, 3D texture and material work, rigging or retargeting, render setup, Blender-to-engine character lookdev, DCC handoff, and 3D technical-art audits. Do not use for standalone 2D art, sprite creation, or sprite-sheet work; 2D imagery is in scope only when it supports a 3D asset."
---

# Auto TA

## Purpose

Act as a 3D technical artist for a user who may know no technical-art vocabulary. Convert intent into a small, reversible 3D production job, execute it on an available DCC or engine surface, and return the asset plus evidence. Do not use this Skill for standalone 2D art, sprite creation, or sprite-sheet production; route that work to `$create-2d-game-art`. 2D imagery belongs here only as a source or component of a 3D asset. A script, README claim, render, or provider response is not by itself a finished game asset.

Match all user-facing explanations, questions, prompts, and handoffs to the user's language unless they request another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.

## Start With an Asset Contract

Read [references/asset-contract.md](references/asset-contract.md). Translate the request into its fields and show the user only the decisions that materially affect the result. Do not ask the user to choose terms such as topology, texel density, skinning method, or color space.

If information is missing, use the `prototype` preset and state the assumptions. Ask before proceeding only when the answer changes authorization, cost, irreplaceable source data, target compatibility, or the basic artistic identity.

Distinguish these jobs:

- `original_asset`: create new geometry and related maps.
- `adapt_asset`: modify an existing asset without destroying its authored source.
- `rig_or_animation`: create, repair, retarget, or validate a skeleton or clip.
- `lookdev`: materials, textures, lighting, shader, or VFX work.
- `audit_or_handoff`: inspect, export, round-trip, or import into an engine.

For a `rig_or_animation` job that aligns a skinned humanoid character with external skeletal clips, invoke `$character-rig-animation-alignment` after establishing this asset contract. Let that Skill own source/license evidence, deform-rig extraction, rest/units/root normalization, Humanoid import, Animator/prefab wiring, and runtime acceptance. Keep `auto-ta` responsible for the broader asset job and final receipt; do not duplicate or weaken the specialized gates.

## Route to the Smallest Working Surface

Read [references/runtime-routing.md](references/runtime-routing.md), then probe rather than assume.

1. Use ImageGen for concept images, texture sources, masks, decals, or reference sheets that support the 3D asset. Treat generated maps as source imagery until channel semantics and tiling are validated.
2. Use Blender Python for deterministic geometry, UV, material, rig, animation, light, render, and export operations. Prefer a healthy live Blender MCP for an already-open authored scene. For a new isolated asset, headless Blender is valid when the live bridge is unavailable.
3. Use `search-game-art` when an existing licensed asset is preferable to original production. Preserve URL, license, author, file hash, and allowed use.
4. Use `character-rig-animation-alignment` when a humanoid character and external animation rig must be normalized, retargeted, wired, and accepted together.
5. Use Unity MCP only when it is healthy and its exact project root is the user-authorized target. Reuse the project's render pipeline and conventions.
6. Use a hosted 3D or texture provider only after the user authorizes that provider, likely cost, upload, and credentials. Never place credentials in prompts, scripts, receipts, repositories, or command output.

Do not install a DCC, package, add-on, MCP gateway, persistent service, or daemon merely to make a route available. Report the missing capability and use another authorized route or stop at a useful intermediate artifact.

## Production Loop

### 1. Protect sources and establish scale

- Work in a new, explicitly named output directory or copy. Never overwrite the only authored `.blend`, `.fbx`, `.gltf`, texture, rig, or engine asset.
- Record source hashes before adapting third-party or user-authored files.
- Establish dimensions, origin/pivot, forward/up axes, unit scale, target engine, triangle budget, texture budget, and required clips.
- For an existing scene, inspect collections, names, linked data, modifiers, armatures, actions, material slots, per-polygon material use, image dependencies, and alpha behavior before editing.

### 2. Build an end-to-end slice

Make the smallest complete representative asset before expanding detail. Keep procedural or destructive stages separate:

- source geometry and non-destructive modifiers;
- applied/export geometry;
- high-poly or bake source when needed;
- texture sources and packed/export maps;
- source rig and exported skeleton;
- source clips and engine-ready clips.

Use stable names. Do not join independent parts merely to make the object count smaller. Do not apply modifiers, transforms, or armature changes until the validated export copy requires it.

### 3. Perform a visual checkpoint

Render or capture enough views to expose silhouette, proportions, intersections, shading, UV/material errors, deformation, and lighting. Inspect those images. Use a neutral look-development view to diagnose the asset and the target gameplay camera to accept it. For animation, inspect representative poses plus the full clip timing; a still image cannot validate motion. For a visible direction such as gaze, facing, toe aim, or prop aim, define the observable region and semantic axis from unanimated render geometry, audited landmarks, or a verified skin/bind reference. Do not assume a bone's local axis represents the visible result.

If no visual surface is available, label visual quality `not_tested`; do not infer it from mesh statistics.

### 4. Run technical gates

Read [references/quality-gates.md](references/quality-gates.md). Run only the gates relevant to the contract, but never skip geometry and export/import gates for a deliverable called game-ready.

Resolve the bundled executables from the globally linked Skill, independent of
the target game's current directory. On macOS, run the POSIX examples in `zsh`
or `bash` inside iTerm2; iTerm2 is the terminal emulator, not the shell. Use the
same POSIX syntax on Linux. Do this once before using any example:

```sh
codex_home="${CODEX_HOME:-$HOME/.codex}"
auto_ta_skill_dir="$(realpath "$codex_home/skills/auto-ta")"
audit_script="$auto_ta_skill_dir/scripts/blender_asset_audit.py"
compare_script="$auto_ta_skill_dir/scripts/compare_asset_audits.py"
receipt_validator="$auto_ta_skill_dir/scripts/validate_receipt.py"
test -f "$audit_script" && test -f "$compare_script" && test -f "$receipt_validator"
```

On Windows, resolve the same paths in PowerShell 7:

```powershell
$CodexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
  Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
} else {
  [System.IO.Path]::GetFullPath($env:CODEX_HOME)
}
$AutoTaSkillDir = (Resolve-Path -LiteralPath (Join-Path $CodexHome 'skills\auto-ta')).Path
$AuditScript = (Resolve-Path -LiteralPath (Join-Path $AutoTaSkillDir 'scripts\blender_asset_audit.py')).Path
$CompareScript = (Resolve-Path -LiteralPath (Join-Path $AutoTaSkillDir 'scripts\compare_asset_audits.py')).Path
$ReceiptValidator = (Resolve-Path -LiteralPath (Join-Path $AutoTaSkillDir 'scripts\validate_receipt.py')).Path
```

Treat failure to resolve any of these absolute paths as
`AUTO_TA_SKILL_NOT_LINKED`; do not fall back to `scripts/...` relative to the
game cwd. Set the remaining asset, output, and trusted-Blender variables to
explicit absolute paths for the current job, using the lowercase variable names
below on POSIX or the PowerShell names on Windows.

For `.blend` files, use the bundled audit without external Python packages:

```sh
"$blender_bin" --background --factory-startup --disable-autoexec --offline-mode \
  --python-exit-code 1 "$asset_blend" --python "$audit_script" -- \
  --output "$source_audit" --output-root "$output_dir" --force \
  --root-object "$asset_root" --frame 1 \
  --require-mesh --require-uv --require-material --max-triangles 20000 \
  --expected-dimensions-m 2.0 0.8 1.1 --expected-ground-z-m 0
```

Windows PowerShell equivalent:

```powershell
& $BlenderBin --background --factory-startup --disable-autoexec --offline-mode `
  --python-exit-code 1 $AssetBlend --python $AuditScript -- `
  --output $SourceAudit --output-root $OutputDir --force --root-object $AssetRoot --frame 1 `
  --require-mesh --require-uv --require-material --max-triangles 20000 `
  --expected-dimensions-m 2.0 0.8 1.1 --expected-ground-z-m 0
```

Put isolation flags before the untrusted `.blend` path. `--disable-autoexec` can prevent Python-dependent drivers from evaluating; keep that result `not_tested` until the source is trusted or the user explicitly authorizes an auto-executing run. Require `--output-root` and use `--force` only for the run's own known report path. Exit 0 means the audit gates passed, exit 2 means a gate failed, and exit 3 or Blender's `--python-exit-code` means an internal error. Reject a stale report whose run id, start time, input hash, or process exit code does not match the current invocation.

Add `--require-closed`, `--require-outward-winding`, `--require-armature`, `--require-actions`, `--require-all-weighted`, `--require-normalized-weights`, `--max-influences N`, `--min-deform-bones N`, or bone budgets only when the contract requires them. Boundary edges are valid for some assets, so closed-manifold geometry is opt-in. `--require-outward-winding` also requires `--require-closed`; it evaluates every disconnected welded shell independently, rejects shared-edge winding conflicts, and uses signed volume to catch a consistently inverted shell. Keep this explicit because a deliberately hollow solid may contain an inward inner shell. Weight gates count only vertex groups that match deform bones on the armature actually associated with the mesh; an unrelated group cannot satisfy them. An Action counts only when it is non-empty and bound to an in-scope owner or NLA strip.

Pass `--expected-dimensions-m X Y Z` in Blender world-axis order and `--expected-ground-z-m Z` whenever the contract defines them. The default `--tolerance-m` is 0.001 m. A metric scene uses `scene.unit_settings.scale_length`; a non-metric scene needs an explicit `--meters-per-unit`. These gates compare unrounded dependency-graph-evaluated mesh vertices, not pre-modifier object bounds.

The report records both raw topology and a position-welded geometric probe. glTF commonly splits a geometrically closed surface at UV, hard-normal, or material seams, so raw boundary edges are evidence, not by themselves proof of a hole. `--require-closed` uses the position-welded result at the declared `--position-weld-tolerance-m` (default 1e-6 m). Keep the tolerance tiny, report merged-vertex counts, and inspect suspicious merges; the probe must not become a repair operation.

The audit is an evidence producer, not an automatic artistic verdict. Independently inspect its JSON and the asset.

### 5. Round-trip the delivery format

Export the requested `.glb`/`.gltf` or `.fbx` from an export copy. Import it into a clean temporary scene or the authorized target engine and compare at least:

- object, mesh, material, skeleton, and clip counts;
- dimensions, axes, pivot, transforms, and hierarchy;
- normals/tangents, UV sets, material channel assignment, and transparency;
- bind pose, weights, clip ranges, loop/root-motion behavior, and scale;
- missing external files and importer warnings.

An export command returning success is not a round-trip pass.

Compute source and imported dimensions from the actual evaluated/imported mesh vertices in world space. Do not compare a pre-modifier `Object.dimensions` or raw `bound_box` against another pre-modifier value and call that a round-trip pass.

For a clean Blender GLB audit, repeat the source gates through the same schema:

```sh
"$blender_bin" --background --factory-startup --disable-autoexec --offline-mode \
  --python-exit-code 1 --python "$audit_script" -- \
  --input-file "$delivery_glb" --output "$imported_audit" \
  --output-root "$output_dir" --force --frame 1 \
  --require-mesh --require-uv --require-material --max-triangles 20000 \
  --expected-dimensions-m 2.0 0.8 1.1 --expected-ground-z-m 0

uv run --python 3.11 python "$compare_script" \
  --source "$source_audit" --imported "$imported_audit" \
  --delivery "$delivery_glb" --output "$round_trip_report" \
  --output-root "$output_dir" --force
```

Windows PowerShell equivalent:

```powershell
& $BlenderBin --background --factory-startup --disable-autoexec --offline-mode `
  --python-exit-code 1 --python $AuditScript -- `
  --input-file $DeliveryGlb --output $ImportedAudit --output-root $OutputDir --force `
  --frame 1 --require-mesh --require-uv --require-material --max-triangles 20000 `
  --expected-dimensions-m 2.0 0.8 1.1 --expected-ground-z-m 0

uv run --python 3.11 python $CompareScript `
  --source $SourceAudit --imported $ImportedAudit --delivery $DeliveryGlb `
  --output $RoundTripReport --output-root $OutputDir --force
```

The comparator requires two distinct audit files and run ids, an `open_blend` source role, a `clean_exchange_import` role, matching isolation flags, and a delivery path/hash identical to the imported input. It checks hierarchy, transforms/pivots, full meter bounds, canonical surface triangles, shell orientation summaries, per-triangle material assignment, tracked Principled material semantics, position/deform-weight signatures, runtime joint origins/orientations, clip names/ranges, sampled motion, and identical gate requirements while deliberately not requiring raw vertex counts, triangulated polygon counts, exact floating-point corner-normal digests, or Blender bone-display tails to match. The audit records a quantized corner-normal digest as diagnostic evidence only; the strict outward-winding gate is the reliable closed-shell orientation check.

The bundled automatic `validated` material profile is intentionally narrow: one direct active Material Output, one Principled BSDF, tracked core values unlinked, no image-texture nodes, and matching render/backface settings. It covers the self-contained constant-material path exercised locally. Bitmap identity and channel mapping, arbitrary upstream node graphs, open-surface normal direction, exported tangents, tangent-space normal maps, and target-engine double-sided/shader behavior need additional task-specific evidence; without it, mark those gates `not_tested` and keep the delivery `prototype`. The receipt validator rejects a passing round trip whose audit reports `complex_material_unvalidated`.

UV coordinates are strict by default. Add `--allow-uv-reparameterization` only when the asset contract explicitly says exact coordinates need not survive, such as a self-contained constant-value material with no bitmap maps. The audits must still prove every polygon has finite, non-collapsed UVs. Record this flag in the comparison evidence. `--tolerance-m` applies only to reported scene and per-mesh meter bounds; canonical surface, material, rig, hierarchy, and clip digests remain strict. The GLB path is locally exercised. FBX import support is conditional on the Blender build and requires explicit `--meters-per-unit`; target-specific FBX axis and root conversions still belong in the asset contract and must be tested rather than assumed.

### 6. Integrate only after artifact validation

For Unity integration, resolve the user-authorized project to one canonical
absolute root containing `Assets/` and `ProjectSettings/`. Gate **every individual Unity MCP tool call** that can mutate the Editor, project, or
evidence filesystem. Immediately before exactly one such call, re-read
`mcpforunity://project/info`, require a string `data.projectRoot`, resolve it
canonically, and require exact path equality with the authorized root. Discard
that result after the call and repeat before the next mutation; never reuse a
connection-, import-, or phase-level check. If the resource is unavailable,
ambiguous, malformed, or mismatched, issue no pending mutation and stop with
`UNITY_PROJECT_MISMATCH`.

This per-call gate covers ModelImporter or material changes, prefab or scene
creation, Console clear, Play, Stop, screenshot or capture, scene
load/reload/reset, test execution, build or project settings, asset import/refresh or reimport, and save. Repeat it after reconnect, Editor restart,
domain reload, branch/worktree switch, or MCP instance selection.

For Unity, keep raw source assets separate from prefabs and project-authored materials. Configure importer settings explicitly, instantiate a minimal validation prefab or scene, and verify the target render pipeline. Do not mutate an unrelated open project because its MCP happens to be connected.

For an image-textured character or any Blender-to-Unity look-development job, read [references/blender-unity-character-lookdev.md](references/blender-unity-character-lookdev.md). Treat renderer submesh/material mapping, shared-atlas use, alpha surfaces, texture import, shader properties, local keywords, and serialized reimport state as separate gates. Blender material-slot order is not proof of Unity renderer order.

## Task-Specific Rules

### Modeling and UV

- Model to observable dimensions and silhouette, not a vague object label.
- Check duplicate/loose geometry, degenerate faces, normals, unintended boundary or non-manifold edges, negative scale, intersections, pivot, and triangle count.
- Validate UV existence, intended unique versus tiled regions, padding, orientation where meaningful, texel density, and required lightmap UV. An automatic overlap number alone is not sufficient.

### PBR materials and texture painting

- Define the target shader and exact channel packing before generating maps.
- Treat base color/emission as color data and masks, metallic, roughness, normal, height, and ambient occlusion as non-color data unless the target pipeline specifies otherwise.
- Validate normal-map handedness, bit depth where displacement matters, alpha mode, seams, tiling, and mip behavior. Never relabel a color image as a normal/roughness map just to satisfy a filename contract.
- Inventory every mesh that shares a material or atlas before applying a tint or shader change; a face-detail texture may also serve teeth, eyes, boots, or another mesh.
- In the target engine, bind materials to inspected submeshes rather than inferred DCC slot indices. Validate the saved and reimported renderer state, not only the setup code.

### Rigging and animation

- Preserve the source skeleton and clips; retarget on copies.
- Check bone hierarchy, unique names, bind pose, deform versus control bones, weights, zero-weight vertices, influences per vertex, normalized weights, constraints, frame rate, clip ranges, loop seam, root motion, and representative extreme poses.
- Validate retargeting on the actual source and target skeletons. A marketplace compatibility label or Humanoid mapping claim is not proof.
- Establish semantic direction references before animation and correction can contaminate them. Treat root, Humanoid, and bone-local axes as diagnostic proxies until they are independently shown to match the visible surface.
- Keep the acceptance oracle independent from the correction under test. Re-derive expected observables from source geometry, audited landmarks, or binding data, or cross-check them against final rendered evidence; a correction's own calibrated measurement cannot prove itself.

### Lighting, shaders, and VFX

- Match the target render pipeline before authoring nodes or code.
- Establish a neutral look-development view before stylized lighting.
- Check color space, exposure, shadow bias, transparency/depth behavior, platform shader compilation, keyword/variant use, overdraw, particle bounds, and performance budgets.
- A rendered beauty image validates appearance only for that camera and configuration; keep a reproducible scene and settings receipt.

## Evidence and Completion

Write `auto-ta-receipt.json` beside the delivery using [references/receipt-schema.md](references/receipt-schema.md). Include assumptions, input/output hashes, tools and versions, executed commands or tool actions, gates with `pass`/`fail`/`not_tested`, explicit evidence status, visual evidence paths, round-trip evidence, licenses, known limitations, and recommended next step. Any code, asset, configuration, capture implementation, or runtime-state change that can affect a gate expires its prior current-state evidence; downgrade that gate until fresh evidence is bound. A higher-strength observed failure likewise invalidates a conflicting lower-strength pass.

Validate the receipt before reporting completion:

```sh
uv run --python 3.11 python "$receipt_validator" "$receipt" \
  --blender-bin "$blender_bin" \
  --output "$receipt_validation" --output-root "$output_dir" --force
```

Windows PowerShell equivalent:

```powershell
uv run --python 3.11 python $ReceiptValidator $Receipt `
  --blender-bin $BlenderBin `
  --output $ReceiptValidation --output-root $OutputDir --force
```

A structurally valid `failed`, `prototype`, or `blocked` receipt may pass receipt validation: the validator is checking honesty and evidence, not converting failure into success. A tested round trip needs an evidence hash; an untested round trip needs a reason. For a tested round trip, declare exactly one output with role `editable_source` and exactly one with role `engine_delivery` or a more specific `*_engine_delivery`; these must be the files named and hashed by the source audit and clean-import comparison. A tested `artifact.*` gate must cite its output paths, hashes, and roles rather than only sizes or prose. For `validated`, run `<skill-dir>/scripts/validate_receipt.py` with `--blender-bin <trusted-absolute-Blender-executable>`. The validator parses the hashed contract, requires schema/verdict/implementation identity from both audits, replays both source and clean-import audits in fresh isolated Blender processes with a bounded timeout, rejects replay mismatch or timeout, verifies the complete comparison check set and verdict reduction, binds the source and delivery roles to the audit chain, then independently recomputes the comparison in memory with the current trusted comparator. Without an explicitly selected trusted Blender executable, a `validated` claim fails closed. It also requires minimum contract/artifact/visual/source/round-trip gate coverage. Deleting checks or schema fields, substituting unaudited deliverables, hiding a failed check behind a top-level `pass`, or relabeling failed evidence must fail validation.

Use these completion labels exactly:

- `validated`: every required artifact, visual, technical, and round-trip gate passed.
- `prototype`: usable for iteration but one or more game-ready gates intentionally remain.
- `blocked`: a required capability, authorization, credential, source file, or engine target is unavailable.
- `failed`: execution completed but a required gate failed.

Never replace a failed or untested gate with prose such as “should work.” Return the useful artifacts even when the overall result is `prototype`, `blocked`, or `failed`, as long as doing so is safe.

## Maintain Adapter Coverage

When adding, replacing, or recommending third-party Skills, providers, DCC adapters, or engine backends, read [references/ecosystem-audit-2026-08-11.md](references/ecosystem-audit-2026-08-11.md) as a dated research baseline. Re-check the upstream repository, license, tool schema, release, dependencies, and security posture before use; popularity and a skills directory listing are not runtime evidence.

Treat skills.sh Blender entries as bounded execution recipes, knowledge checklists, or validation layers, not as proof that their named tools exist locally. Adopt a useful method only after static audit and an isolated probe, then keep local artifact, round-trip, engine, and visual gates authoritative. Feed back generalizable failures and acceptance gates; keep project-specific colors, slot names, hashes, and asset choices in the project receipt or case study.
