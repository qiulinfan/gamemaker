# Blender-to-Unity Character Lookdev and Round Trip

Use this reference for image-textured characters, especially when Blender looks correct but Unity shows dark faces, blurred features, white blocks, opaque hair cards, missing details, or shader behavior that changes after reimport. It is a diagnosis and acceptance workflow, not a preset material recipe.

## Establish the visual contract

Record before editing:

- Blender and Unity versions, render pipeline, shader, color space, lighting, exposure, and target camera distances;
- critical regions such as face, eyes, mouth, teeth, hairline, hands, and costume markings;
- mesh objects, populated submeshes, source material slots, per-polygon material use, shared atlases, and alpha surfaces;
- source texture identity, dimensions, alpha statistics, color-space intent, roughness/smoothness semantics, and normal convention;
- which bytes are immutable source and which materials, textures, prefabs, or import settings are project-authored derivatives.

Do not overwrite the only FBX, Blend, or texture source while diagnosing. Hash source files and change derived materials/import settings first.

## Diagnose in evidence order

Use an isolated character lab with neutral light, a plain backdrop, a close face camera, a full-body camera, and at least one representative animation pose. Change one variable family at a time.

1. **Renderer mapping.** Inspect Unity's actual mesh `subMeshCount`, renderer `sharedMaterials`, and each populated submesh's material. Temporarily isolate or assign diagnostic colors if needed. Do not infer this mapping from Blender's material panel.
2. **Texture identity and shared use.** Confirm that each Unity material points to the intended image and enumerate every mesh/submesh that consumes the same material or atlas. A tint that fixes one body region can damage another.
3. **Geometry and normals.** Compare face orientation and normals in Blender only after the failure has been localized to geometry. Check symmetry, negative scale, mirrored UVs, tangents, and double-sided intent. Do not recalculate normals merely because one screen region is black.
4. **Alpha cards.** Inspect alpha coverage and RGB below low alpha. If transparent pixels contain black color, an alpha cutoff can turn soft hair or eyelash cards into opaque blockers. Compare blend, cutout, or authored dither in the target pipeline and camera; verify culling, shadows, ZWrite, sorting, and render queue.
5. **Texture sampling.** Verify sRGB for color images and non-color import for masks/normals. Inspect mip levels, compression, maximum size, filtering, bias, alpha preservation, and streaming or mip-limit behavior at close and gameplay distances. Adjust only the critical textures that show loss.
6. **Shader response.** Translate semantics, not UI labels. Metallic stays metallic; Blender roughness normally becomes Unity smoothness `1 - roughness` for a Lit workflow. Reproduce tint, emission, specular/reflection policy, transparency, and culling deliberately rather than relying on automatic FBX material conversion.
7. **Serialization and reimport.** Save assets, reimport textures/models/materials, rebuild the validation prefab or scene, reload it, and inspect the saved state. Setup code that looked correct before Unity postprocessing is not evidence of the final material.

## Material-slot and submesh gate

DCC material slots and engine submeshes are related but not guaranteed to preserve visible indices:

- zero-polygon material slots may be stripped;
- exporters or importers may order populated submeshes by polygon/material use;
- multiple objects can reuse a material name while having different slot layouts;
- a renderer may expose fewer materials than the DCC object panel;
- assigning a plausible material to the wrong populated submesh can resemble broken normals, missing teeth, a white face block, or corrupt UVs.

Acceptance requires a table keyed by mesh/renderer name with source populated material use, imported submesh count, saved `sharedMaterials` order, and intended identity. Add a focused regression test for critical meshes instead of relying on visual memory.

## URP state gate

For URP Lit materials, inspect both numeric properties and shader state. Relevant fields may include:

- `_BaseMap`, `_BaseColor`, `_Metallic`, `_Smoothness`, `_EmissionMap`, and `_EmissionColor`;
- `_Surface`, `_Blend`, `_AlphaClip`, `_Cutoff`, `_Cull`, `_ZWrite`, render queue, and `RenderType` tag;
- `_SpecularHighlights` and `_EnvironmentReflections` together with the corresponding Unity 6 local keywords;
- `_EMISSION` together with `MaterialGlobalIlluminationFlags`.

Use the current Unity shader's `LocalKeyword` API when programmatically changing local keywords. Do not validate only the serialized keyword text. Unity material postprocessing can recompute `_EMISSION`; an emissive material needs an emissive global-illumination flag, while a non-emissive material should be marked black. Re-check after save and reimport.

Weak texture-preserving emission can be an intentional stylized face treatment, but it must be contract-specific, tested under the target lighting, and kept low enough to retain form. It is not a generic fix for bad normals, wrong material mapping, or missing light.

## Acceptance evidence

Retain:

- Blender neutral close-up and full-body captures;
- Unity close-up and target-camera captures from the rebuilt validation scene;
- renderer/submesh/material tables and focused automated tests;
- texture importer and saved material state after reimport;
- representative animation poses, because deformation can expose sorting and card intersections;
- focused tests, relevant full Editor/PlayMode regressions, and clean Console output;
- source and derivative hashes plus the rebuild entrypoint.

If the Unity visual result is untested, record the lookdev round trip as `not_tested` and keep the asset `prototype`. A correct Blender render cannot promote a Unity delivery to `validated`.

## Historical lesson generalized

One validated project run produced a half-black face and blurred detail in Unity even though Blender showed symmetric face normals. The decisive defect was imported populated-submesh order, compounded by shared-atlas grading, transparent cards, and texture sampling. Recalculating normals would have damaged valid source geometry without fixing the mapping.

The correction bound materials to inspected engine submeshes, kept engine materials as project-authored derivatives, selected target-pipeline alpha behavior, adjusted only critical texture sampling, and verified keywords plus emission flags after reimport. Preserve project names, colors, numeric settings, paths, and hashes only in an explicitly selected profile or target-project receipt.
