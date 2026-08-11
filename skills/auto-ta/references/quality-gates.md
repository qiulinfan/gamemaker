# Quality gates

Select gates from the asset contract. Every required gate needs raw evidence and a verdict.

## Geometry and scene

- Intended object and hierarchy counts; stable, unique names.
- Dimensions, unit scale, orientation, origin/pivot, transforms, and negative scale. Contract dimensions and ground contact are measured from dependency-graph-evaluated world-space mesh vertices; raw pre-modifier bounds are recorded only as source-editability evidence.
- Vertex/edge/polygon/triangle counts within the declared budget.
- Loose, duplicate, degenerate, boundary, and non-manifold geometry as appropriate to the asset. Record raw topology separately from a tiny-tolerance position-welded geometric probe: exchange formats may split vertices at UV, normal, or material seams, while the welded result can also hide unintended coincident shells if its tolerance is too large.
- Face orientation, normals, smoothing, hard edges, and tangent readiness. For assets contracted as closed solids, use `--require-closed --require-outward-winding`; the latter checks disconnected welded shells independently and rejects inconsistent or globally inverted winding.
- Modifier order and whether the source remains editable.
- Intersections and z-fighting assessed visually or by an appropriate geometric test.
- LOD naming, bounds, silhouette retention, and monotonic complexity when LODs are required.

## UV and textures

- Required UV sets exist and use the intended channel indices.
- Unique/tiled/mirrored policy, overlap, out-of-range coordinates, orientation, padding, and texel density are checked against intent. Every required polygon must have finite, nonzero UV area; one valid face cannot hide collapsed UVs elsewhere.
- Lightmap UV has unique charts and pipeline-appropriate padding when required.
- Every material slot is intentional and every referenced image resolves or is packed as contracted.
- Per-polygon material use and the target engine's actual renderer submesh/material order are inventoried; zero-polygon source slots and stripped engine slots are recorded instead of assumed to retain their indices.
- Exact map semantics, dimensions, bit depth, alpha mode, color space, channel packing, and normal convention are recorded.
- Seams, mip behavior, compression artifacts, and representative near/far appearance are visually checked.

## Rig and animation

- Skeleton name, root count, hierarchy, bind pose, joint origins/orientations, scale, deform/control distinction, and required bone names. For glTF, Blender bone tail length and `use_connect` are display/editor reconstructions rather than runtime joint semantics; compare rest joint matrices, weights, and sampled deformation instead.
- Armature association, zero-weight vertices, normalized weights, maximum influences, and deformation at neutral and extreme poses. Count only groups matching `use_deform` bones on the armature that actually drives the mesh; report unrelated/control groups separately.
- Constraints/drivers needed at runtime are baked or supported by the target.
- Clip names, frame ranges, sample rate, duration, loop seam, root motion, events, and additive/reference pose policy. A global, empty, or unbound Action is not an exportable clip; include bound Action slots and NLA strips.
- Source-to-target retarget is run on the actual pair and inspected during motion.

## Materials, lighting, shaders, and VFX

- Target render pipeline and shader identity are explicit.
- PBR channel mapping, color/non-color sampling, normal convention, transparency, double-sided state, and emission units are verified.
- Shared-material and shared-atlas consumers are enumerated before tint, roughness, emission, alpha, or keyword changes; critical face/detail surfaces are isolated when diagnosing.
- Transparent cards are checked against source alpha and the RGB stored under low alpha. Cutout, blend, dither, shadow, culling, depth-write, and render-queue choices are validated from the target camera instead of inferred from the DCC blend mode.
- Texture import color space, mip generation/filter/bias, compression, maximum size, alpha preservation, and streaming/limit policy are tested at the diagnostic and gameplay distances. Asset-specific detail preservation is not promoted to a global uncompressed-texture policy.
- Shader compilation has no target-platform errors; variants/keywords are bounded.
- Engine shader properties, local keywords, render queue, tags, and global-illumination flags survive material save, asset reimport, and scene/prefab reload.
- Neutral look-development lighting separates material errors from artistic lighting.
- Exposure, tone mapping, shadow settings, reflection/probe behavior, and light baking mode are reproducible.
- VFX lifetime bounds, sorting/depth, collision, spawn rate, maximum live particles, overdraw, and off-screen behavior are checked.

## Export and engine round-trip

- Export log and importer log contain no unexplained errors or missing dependencies.
- Object/mesh/material/skeleton/usable-clip counts match the intentional conversion. Raw vertex and polygon counts may legitimately differ at attribute seams and mandatory triangulation; compare canonical world-space surface triangles, welded closure, bounds, per-triangle material assignment, weights, and component correspondence instead.
- Source and imported audits must be distinct isolated runs. The comparison report must bind the actual delivery file hash to the imported audit input hash, preserve object hierarchy/transforms/pivots, and record every explicitly allowed conversion such as UV reparameterization.
- Dimensions, transforms, axes, hierarchy, pivots, normals, tangents, UVs, material maps, skeleton, and clips survive. Recompute imported world-space bounds from imported mesh vertices and compare them with both the contract and evaluated source bounds. The bundled comparator alone proves only its declared fields; open-surface normal direction, exported tangents, bitmap/channel identity, tangent-space normal maps, complex node graphs, and target-engine double-sided behavior require dedicated evidence or remain `not_tested`.
- For skinned or multipart characters, compare saved renderer `subMeshCount`, `sharedMaterials` count/order, and the intended material identity for every populated submesh. DCC material-panel order is diagnostic evidence only.
- Engine-side shader and render-pipeline conversion is explicit.
- A minimal prefab or validation scene renders and animates the asset when engine integration is required.
- Static batching, instancing, collider, lightmap, compression, memory, draw-call, triangle, bone, skin-influence, and shader-variant budgets are checked when applicable.

## Evidence strength

Use evidence in this order:

1. inspected engine/runtime behavior and round-tripped artifacts;
2. DCC data queried from the saved deliverable;
3. rendered or captured visual evidence;
4. command logs and structured reports;
5. source code or instructions;
6. web page or provider claims.

Lower-ranked evidence cannot override a failure found by higher-ranked evidence.
