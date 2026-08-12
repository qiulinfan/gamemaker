---
name: character-rig-animation-alignment
description: Align a sourced or authored humanoid character model with external skeletal animations and deliver a verified engine-ready retargeting integration. Use when Codex must select and license a character for a game, audit FBX/GLB/Blend armatures or Rigify/control rigs, normalize bone mapping, bind/rest pose, axes, scale, root motion, skin weights, Unity Humanoid Avatars, renderer/material mapping, or character transparency, wire Animator/prefab/validation scenes, or diagnose failures such as valid-but-collapsed Avatars, contaminated bind poses, root drift, prefab bone overrides, or Blender-correct characters whose faces render black or blurred in Unity.
---

# Character Rig & Animation Alignment

Treat character selection, offline retargeting, engine import, and runtime acceptance as one evidence chain. Preserve authored sources and perform destructive or lossy work only on named copies.

Match user-facing explanations, questions, prompts, and handoffs to the user's language unless they request another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.

## Establish the Contract

1. Read repository instructions, the worktree, the design-source hierarchy, technical architecture, and existing asset/license conventions.
2. Record the character's gameplay role, camera visibility and distance, thematic identity, required animation verbs, target engine and render pipeline, format, scale, axes, root-motion owner, critical visual regions, alpha surfaces, performance budget, and completion evidence.
3. Separate confirmed requirements, synthesis, assumptions, and open design questions. Do not turn an asset title, marketplace category, or visual resemblance into canonical character identity.
4. Use `$search-game-art` when selection or acquisition is still open. Preserve the original page, creator, exact edition, retrieval date, declared license, redistribution boundary, archive name/size/hash, and locally audited contents. Keep declared web claims separate from inspected-file and engine evidence.
5. Stop before download, import, or redistribution when permission is ambiguous, the page and archive conflict materially, the license cannot satisfy the intended repository or shipping model, or the user has not authorized the required acquisition.

Read [references/alignment-gates.md](references/alignment-gates.md) before mutating an asset. Historical project evidence is not part of the portable core. When an environment profile is explicitly selected, locate its case studies through the bundle manifest; never treat example names, paths, counts, tolerances, or hashes as universal defaults.

## Select the Retargeting Path

Choose the smallest path that preserves source truth:

- Use engine Humanoid retargeting when both rigs can express the required human slots and engine sampling can prove acceptable deformation.
- Build a clean deform/export rig when the animation source is a Rigify, UAL-style, control, constraint, or mixed NLA rig. Export the continuous deform hierarchy, never the whole control rig merely because it contains the motion.
- Use a custom runtime or offline mapping when required semantics are not representable by the engine avatar.
- Replace the model or animation source when license, theme, topology, skinning, missing chains, or adaptation cost makes a reliable bridge disproportionate to the contract.

Do not re-skin a working character merely to make its bone names resemble the source. Do not map twist, leaf, helper, IK, or control bones into semantic human slots unless they actually own that body segment.

## Audit Sources Before Editing

Hash inputs, inspect archive safety, and inventory each model, rig, and animation source independently:

- meshes, populated material slots, per-polygon material use, shared materials or atlases, texture/alpha dependencies, armatures, deform/control bone counts, skin clusters, actions, NLA tracks, constraints, drivers, and shape keys;
- unique bone names, hierarchy, deform flags, required bilateral chains, human-slot candidates, bind/rest matrices, pose state, object transforms, units, forward/up axes, and root structure;
- vertex coverage, normalized weights, maximum influences, zero-weight vertices, non-deform groups, and representative extreme-pose deformation;
- clip names, action ownership, frame ranges, fps, loop intent, active actions, overlapping NLA tracks, translation/rotation/scale channels, and source root travel.

Require a traceable animation source. If the retained file's fps, action provenance, or generator disagrees with the claimed edition, preserve the auditable timing and report the conflict; do not invent the official speed.

## Normalize on Reversible Copies

Perform these operations in order and record each result:

1. **Clean evaluation state.** Disable active actions and NLA influence before gathering the skeleton. Set the armature to its actual rest state and build a clean export hierarchy from required deform bones. Bake evaluated source motion into the clean hierarchy parent-first.
2. **Semantic mapping.** Create an explicit source-to-target human-slot table. Require unique names, complete required chains, symmetric left/right limbs and toes where used, and explain retained unmapped bones.
3. **Bind/rest pose.** Compare source, export, and clean-round-trip rest heads and matrices in the same coordinate space. Fail on animation-frame contamination or any error large enough to change the target's proportions; scale tolerances to the character rather than copying a project-specific epsilon blindly.
4. **Units and axes.** Normalize to the engine's documented unit and axis convention with identity armature/object scale where the format permits. Inspect both exporter settings and raw exchange metadata. Round-trip the file and compare multiple mapped segment lengths; a globally valid avatar can still contain a 1/100 limb collapse.
5. **Channels and timing.** Export only the intended clips. Permit bone rotations and only contract-approved translations, normally root and pelvis; reject unexpected scale curves. Preserve audited fps, integer clip ranges, loop intent, and action names.
6. **Root policy.** Decide whether world displacement belongs to animation or gameplay. For controller-authoritative in-place motion, remove horizontal root travel coherently from the evaluated whole pose, then prove source travel was observed and exported XZ drift is near zero. Configure clip locks and runtime `applyRootMotion` to the same policy.
7. **Skinning.** Preserve working weights. If weights change, re-run coverage, normalization, influence, bind, and extreme-pose tests; visual plausibility at one frame is insufficient.
8. **Clean round trip.** Import the delivery file into a clean DCC scene, then compare hierarchy, rest pose, units, transforms, clips, channels, sampled poses, and root behavior against the recorded source evaluation.

For two Unity `.fbx.meta` files with Humanoid descriptions, run the bundled scale/mapping sentinel after the candidate has imported:

On macOS, run this in `zsh` or `bash` inside iTerm2; use the same POSIX command
on Linux:

```sh
skill_dir="<absolute-skill-directory>"
uv run --python 3.11 python "$skill_dir/scripts/audit_unity_humanoid_meta.py" \
  --reference "<known-good.fbx.meta>" --candidate "<candidate.fbx.meta>" \
  --ratio-min 0.5 --ratio-max 1.5 --min-common 17 \
  --required-human Hips,Spine,Head \
  --required-human LeftUpperLeg,RightUpperLeg,LeftLowerLeg,RightLowerLeg,LeftFoot,RightFoot,LeftToes,RightToes \
  --required-human LeftUpperArm,RightUpperArm,LeftLowerArm,RightLowerArm,LeftHand,RightHand \
  --output "<humanoid-meta-audit.json>" \
  --output-root "<authorized-report-directory>"
```

On Windows, use PowerShell 7:

```powershell
uv run --python 3.11 python <skill-dir>/scripts/audit_unity_humanoid_meta.py `
  --reference <known-good.fbx.meta> --candidate <candidate.fbx.meta> `
  --ratio-min 0.5 --ratio-max 1.5 --min-common 17 `
  --required-human Hips,Spine,Head `
  --required-human LeftUpperLeg,RightUpperLeg,LeftLowerLeg,RightLowerLeg,LeftFoot,RightFoot,LeftToes,RightToes `
  --required-human LeftUpperArm,RightUpperArm,LeftLowerArm,RightLowerArm,LeftHand,RightHand `
  --output <humanoid-meta-audit.json> `
  --output-root <authorized-report-directory>
```

The report must stay inside the explicit output root and must not already exist.
Use `--force` only when the user authorizes replacing that exact report. Treat
this script as a targeted sentinel, not proof of animation quality. Review its
JSON and still run DCC, Unity, and runtime gates.

## Import and Wire Unity

Resolve the user-authorized Unity project to one canonical absolute root that
contains `Assets/` and `ProjectSettings/`. Gate **every individual Unity MCP tool call** that can mutate the Editor, project, or evidence filesystem.
Immediately before exactly one such call, re-read
`mcpforunity://project/info`, require a string `data.projectRoot`, resolve it
canonically, and require exact path equality with the authorized root. Discard
the check after that call and repeat before the next mutation; never reuse a
connection-, importer-, scene-, or phase-level result. If identity is
unavailable, ambiguous, malformed, or mismatched, issue no pending mutation and
stop with `UNITY_PROJECT_MISMATCH`.

Apply this gate to ModelImporter and material edits, Avatar/controller wiring,
prefab or scene creation, Console clear, Play, Stop, screenshot or capture,
scene load/reload/reset, test execution, build or project settings, asset import/refresh or reimport, and save. Repeat after reconnect, Editor restart,
domain reload, branch/worktree switch, or MCP instance selection.

1. Keep immutable third-party bytes, project-authored derivatives, and generated validation assets in separate project locations. Preserve notices and record modifications.
2. Configure `ModelImporter` deterministically: scale, axis conversion, animation import, explicit Humanoid mapping, Avatar source/setup, clip ranges, loop flags, root locks, materials, and optimization policy.
3. When an FBX skeleton changes under the same path, force a fresh skeleton description before accepting Humanoid state; a Generic-to-Human reimport is a valid cache refresh when verified. Never use `Avatar.isValid && Avatar.isHuman` as the only gate.
4. Require the intended human mapping, bilateral toes, expected unmapped helpers, plausible mapped segment ratios, and no relevant importer errors or discarded-curve warnings.
5. Inventory each imported mesh's populated `subMeshCount` and each renderer's saved `sharedMaterials` order. Bind project-authored engine materials to the inspected engine submeshes; never assume Blender material-panel indices survive zero-polygon slot stripping or importer reordering.
6. Reconstruct the target-pipeline material response explicitly. Verify texture identity and shared-atlas consumers, color space, roughness-to-smoothness translation, alpha/culling/depth/render-queue behavior, mip/compression policy, numeric shader properties, local keywords, and global-illumination flags after save and reimport.
7. Bind real clips to named Animator states, assign the intended Avatar and controller, and make `applyRootMotion` match the root policy. Test state identity and clip semantics rather than relying on Inspector appearance.
8. Create a reusable prefab without nested model-bone position/rotation/scale overrides. Runtime preview code must not sample and serialize pose changes in Edit mode; restore modified transforms before saving.
9. Use an isolated validation scene with close-face, front, and side cameras, neutral light, ground, scale landmarks, and contact props. Keep it out of shipping build settings unless explicitly required. If a builder is authoritative, edit the builder and regenerate instead of hand-editing only its outputs.
10. Do not replace the canonical player, main scene, character identity, or gameplay state authority unless the contract explicitly requires it.

## Accept With Reproducible Evidence

Validate from a clean state at five layers:

- **Static importer:** exact mapping, clips, avatar, populated submesh/material order, texture import state, serialized shader properties/keywords, prefab references, no forbidden overrides, build-setting isolation, and clean relevant Console output.
- **Editor sampling:** sample every state at several normalized times such as `0`, `.25`, `.5`, `.75`, and `.95`; assert finite transforms, plausible scale/landmarks, bilateral foot-toe length, a support foot, and unchanged GameObject/Animator roots for in-place motion.
- **Source-relative motion:** compare unusual pelvis or limb excursions with the source animation. Do not hide a real retargeting failure behind a wide bound, but do not reject an authored lunge with an arbitrary target-only envelope.
- **Runtime:** enter Play mode through the player-like path, transition every required state, verify looping and root authority, reset, and repeat enough to expose state leakage.
- **Visual and reproducible evidence:** inspect close-face, front, and side captures under neutral and target presentation conditions for representative states. Accept an engine-generated animation capture only when the actual state and clip, evaluated time, CPU semantic pose, skinned-renderer evaluation, and final pixels are proven to belong to the same synchronized evaluation. Retain capture identity, presentation offsets, image hashes, tool/engine versions, commands or menu actions, test XML or logs, screenshot paths, and the final worktree diff; distinct image hashes alone do not prove pose correctness.

Run focused tests, then the relevant full Editor and PlayMode suites. Rebuild from the authoritative source and repeat critical checks when generated assets are part of the delivery. A screenshot, successful export command, green Avatar icon, or one passing pose is not a completed retarget.

## Stop, Roll Back, or Replace

- **Stop** on missing authority, unresolved license/provenance, wrong project or Editor instance, missing only source needed to prove timing/bind state, or an operation that would overwrite the sole authored source.
- **Roll back the current derivative/import** on bind-pose contamination, unexplained unit or axis conversion, collapsed segment ratios, scale curves, unexpected root drift, asymmetric/missing semantic chains, relevant importer warnings, prefab bone overrides, serialized preview poses, renderer/material order mismatch, opaque alpha cards obscuring critical regions, shader state that changes after reimport, obscured validation cameras, or failed regression. Keep the failing artifact only when useful as labeled evidence.
- **Replace the asset** when its theme or camera readability fails the contract, redistribution terms conflict with delivery, the necessary human chains or skinning cannot be repaired within scope, or source ambiguity makes a trustworthy result impossible.

Report `validated`, `prototype`, `blocked`, or `failed` honestly. Deliver the source/derivative inventory, skeleton and renderer/material maps, clip tables, provenance and modification notices, hashes, executed gates, screenshots/logs, remaining risks, and exact rebuild entrypoint. Never turn an untested or failed gate into “should work.”
