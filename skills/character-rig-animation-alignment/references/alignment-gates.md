# Alignment Gates and Decision Record

Use this reference to define gates before editing and to decide whether a failure requires another bake, an importer rollback, or a different asset. Adapt numeric tolerances to the target scale and animation semantics; record them before looking at the result.

## 1. Source and Rights

| Gate | Pass evidence | Failure action |
| --- | --- | --- |
| Theme and role | Design sources support silhouette, camera distance, identity, and required animation verbs | Replace or keep as an explicitly reversible prototype |
| Original source | Creator page or authoritative marketplace/repository, exact edition, retrieval date | Stop when only re-uploads or snippets remain |
| License | Named license text covers use, modification, commercial context, and intended redistribution | Stop or choose a compatible asset; do not guess |
| Attribution/change notice | Creator, title, source, license link/text, and modification statement are preservable | Change delivery layout or replace asset |
| Archive identity | Filename, byte size, SHA-256, safe-path scan, actual inventory | Quarantine unexpected executables or traversal paths; resolve page/archive conflict |
| Redistribution boundary | Raw files may be committed/shared under the observed terms, or are kept outside a public repository | Do not push restricted raw assets |

Keep declared page data, archive audit, DCC audit, and engine validation as separate evidence classes.

## 2. Rig and Skin Compatibility

| Gate | Pass evidence | Failure action |
| --- | --- | --- |
| Deform hierarchy | One continuous hierarchy owns the required skinned segments | Extract a clean deform rig; replace if no trustworthy hierarchy exists |
| Control separation | IK, mechanism, Rigify, leaf, and helper bones are classified; export uses only required deform bones | Roll back an export of the whole control rig |
| Semantic map | Required human slots map once; bilateral chains and toes are symmetric | Repair mapping or replace source; never auto-fill ambiguous slots |
| Bind/rest state | Skeleton is collected with no active action/NLA contamination; matrices and bone heads survive clean round trip | Rebuild from rest; discard contaminated derivative |
| Weights | Required vertices have normalized deform weights and acceptable influences; no relevant zero-weight vertices | Repair on a copy and repeat all deformation gates |
| Extreme poses | Shoulder, elbow, wrist, hip, knee, ankle, toes, clothing, hair, and accessories remain plausible | Reweight/remodel within scope or replace the model |

An engine's “Humanoid compatible” label or a valid Avatar object does not satisfy these gates.

## 3. Units, Axes, and Rest Geometry

Record scene units, exporter unit mode, raw exchange-file unit metadata, object/armature transforms, engine scale factor, forward/up axes, and representative local segment lengths.

Compare at least torso, upper/lower arms, upper/lower legs, feet, and toes where present. Use a known-good rig with equivalent proportions or the same clean export hierarchy. A broad ratio gate such as `0.5–1.5` is useful for catching a 1/100 collapse, but it is not a universal anatomy rule.

Fail when:

- unit metadata and object scale compensate each other opaquely;
- mapped bones have unexplained non-unit or non-uniform scale;
- only one side loses toes or a chain segment;
- the engine cached skeleton differs from the new FBX;
- rest heads/matrices drift beyond a scale-appropriate threshold;
- the delivery is facing, mirrored, or grounded differently from the contract.

After any FBX unit fix, clean-import the exchange file and force the engine to rebuild its skeleton description before comparing again.

## 4. Animation and Root Policy

For every selected action record source owner, source path/hash, fps, frame range, loop intent, source root travel, expected output root policy, and allowed channel classes.

Require:

- one intended action evaluation at a time; no overlapping enabled NLA tracks during bake;
- hierarchical pose sampling after constraints, with the export skeleton itself in clean rest;
- rotations for semantic bones; translations only where authorized; no unexpected scale curves;
- exact action names, integer ranges, audited fps, and explicit loop settings;
- sampled source-to-bake and bake-to-round-trip pose error within declared tolerances;
- source motion evidence before an in-place conversion and near-zero output XZ drift afterward;
- importer root locks and runtime `applyRootMotion` consistent with the same policy.

Do not “correct” disputed fps or an unusual lunge from memory. Preserve auditable source behavior, disclose provenance conflict, and obtain the canonical source before claiming official timing.

## 5. Unity Import and Derived Assets

| Gate | Evidence |
| --- | --- |
| Avatar | `isValid`, `isHuman`, intended explicit mapping, required symmetric slots, plausible segment ratios |
| Diagnostics | No relevant import errors, “inbetween humanoid transforms,” discarded toe curves, or mapping warnings |
| Clips | Exact state-to-clip binding, frame ranges, loops, root locks, human motion, audited fps provenance |
| Controller | All required states reachable; no missing motions; transitions and defaults match the validation contract |
| Renderer layout | Imported populated submesh count and saved `sharedMaterials` order match an inspected renderer/material map; stripped empty source slots are recorded |
| Materials | Intended target-pipeline shader, textures, color space, alpha/culling/depth state, and shared-atlas consumers are explicit |
| Prefab | Intended Avatar/controller/materials; unit scale; no nested model-bone TRS overrides |
| Preview code | Does not animate in Edit mode or persist a sampled pose; restores any temporary transforms |
| Validation scene | Character, neutral ground, landmarks/props, visible front/side cameras, light; excluded from shipping build unless requested |
| Authority | Generated prefabs/scenes match their builder; gameplay state and world movement remain owned by the documented system |

If Unity appears to retain stale `HumanDescription.skeleton` data after replacing an FBX, transition the importer through a non-Humanoid state, reimport, then apply the intended Humanoid mapping and reimport again. Accept this only after the rebuilt skeleton passes the same gates.

## 6. Renderer and Material Round Trip

Require an engine-side table for every critical skinned renderer:

| Field | Evidence |
| --- | --- |
| Source use | DCC object, populated material slots, and per-polygon material assignment |
| Imported use | Mesh `subMeshCount`, renderer `sharedMaterials` count/order, and intended material identity |
| Shared surfaces | Every mesh or body region using the same material or texture atlas |
| Transparency | Source alpha distribution and RGB below low alpha; chosen blend/cutout/dither, culling, ZWrite, shadows, and render queue |
| Texture import | Color space, alpha preservation, mip/filter/bias, compression, maximum size, and representative near/far result |
| Shader state | Numeric properties plus valid local keywords, tags, queue, and global-illumination flags after save/reimport |

Do not diagnose a dark face as inverted normals until submesh mapping, shared tints, alpha cards, light/shadow, and texture sampling have been isolated. Do not use alpha cutout merely because a texture has alpha; low-alpha black RGB can become an opaque blocker. Do not globally disable mips or compression to repair one face texture. Tune only the critical images and prove both close-up and gameplay-camera readability.

For URP, translate material semantics deliberately: roughness and smoothness are inverse conventions, transparency requires coherent surface/blend/depth/queue state, and Unity 6 shader features may use local keywords. Emission must have both the intended keyword and compatible `MaterialGlobalIlluminationFlags`, then survive material save, asset reimport, prefab rebuild, and scene reload.

## 7. Runtime and Visual Acceptance

For each required state, sample several normalized times across the clip and test:

- finite positions/rotations/scales and plausible human landmarks;
- no segment collapse, both foot-to-toe chains, and at least one plausible support foot;
- loop seam where required;
- unchanged character and Animator child roots for controller-authoritative in-place playback;
- source-relative pelvis and limb envelopes for large authored motions;
- material, alpha, silhouette, intersections, prop contact, and camera readability from front and side.

Then enter Play mode, exercise the real state path, reset, and repeat. Retain focused and full-suite results, Console errors/warnings, screenshots, logs, versions, hashes, and rebuild commands. Treat screenshots as visual evidence, never as a substitute for structural or runtime checks.

## 8. Outcome Decision

| Outcome | Meaning |
| --- | --- |
| `validated` | Required source, DCC round-trip, importer, Editor sampling, runtime, visual, and reproducibility gates passed |
| `prototype` | Useful reversible integration, but explicitly listed game-ready gates remain untested or design-dependent |
| `blocked` | Required authority, source, license, DCC/engine capability, or project target is unavailable |
| `failed` | Execution ran and a required gate failed; retain the evidence and roll back the derivative/import |
| replace recommendation | Rights, theme, required topology/skinning, or source trust cannot be repaired proportionately |

## Minimal Evidence Receipt

Record at least:

```yaml
contract:
  role: <gameplay and presentation role>
  required_actions: []
  engine: <version and render pipeline>
  root_policy: <in_place | animation_root_motion>
sources:
  - path_or_url: <source>
    creator: <creator>
    license: <license and redistribution boundary>
    sha256: <hash>
rigs:
  model: {bones: 0, deform_bones: 0, human_slots: 0}
  animation_sources: []
normalization:
  units_axes: <record>
  rest_pose: <record>
  weights: <record>
  root_motion: <record>
delivery:
  outputs: []
  rebuild_entrypoint: <script, menu, or command>
validation:
  dcc_round_trip: <pass | fail | not_tested>
  unity_importer: <pass | fail | not_tested>
  renderer_material_round_trip: <pass | fail | not_tested>
  editor_sampling: <pass | fail | not_tested>
  runtime: <pass | fail | not_tested>
  visual: <pass | fail | not_tested>
verdict: <validated | prototype | blocked | failed>
limitations: []
```
