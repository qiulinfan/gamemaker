# Asset contract

Create this contract before tool execution. Store it in `asset-contract.json` for production work; present a short plain-language summary to the user.

```json
{
  "schema_version": "1.0",
  "job": "original_asset",
  "asset_name": "wood_crate",
  "intent": "A readable low-poly supply crate",
  "target": {
    "engine": "Unity",
    "render_pipeline": "URP",
    "platform": "desktop",
    "delivery_formats": ["blend", "glb"]
  },
  "space": {
    "semantic_dimensions_m": {"width": 2.0, "depth": 2.0, "height": 2.0},
    "pivot": "bottom_center",
    "authoring": {
      "application": "Blender",
      "dimensions_m_xyz": [2.0, 2.0, 2.0],
      "right": "+X",
      "forward": "-Y",
      "up": "+Z",
      "meters_per_unit": 1.0
    },
    "target_axes": {"right": "+X", "forward": "+Z", "up": "+Y"}
  },
  "art": {
    "style": "low-poly",
    "references": [],
    "must_read_as": ["wood", "reinforced crate"]
  },
  "geometry": {
    "max_triangles": 2000,
    "lods": [],
    "closed_manifold_required": true,
    "uv_coordinate_preservation_required": true
  },
  "textures": {
    "workflow": "metallic-roughness",
    "max_resolution": 1024,
    "sets": 1,
    "required_maps": ["base_color", "normal", "metallic_roughness"]
  },
  "lookdev": {
    "target_shader": "Universal Render Pipeline/Lit",
    "critical_regions": [],
    "shared_atlases": [],
    "alpha_surfaces": [],
    "target_camera_distances_m": []
  },
  "rig": null,
  "animation": [],
  "integration": {
    "authorized_project_root": null,
    "prefab_required": false
  },
  "acceptance": [
    "silhouette reads as a reinforced crate",
    "semantic and authoring-axis dimensions are within 0.001 m",
    "delivery round-trips without missing resources"
  ],
  "assumptions": [],
  "authorization": {
    "may_modify_existing_source": false,
    "may_mutate_target_project": false,
    "paid_provider": null,
    "upload_allowed": false
  }
}
```

Keep semantic width/depth/height separate from the authoring application's XYZ order. Translate the user's dimensions once, record the mapping, and pass the authoring-axis `dimensions_m_xyz` to Blender audit commands. Record the target axes independently; an exporter or engine conversion may intentionally rotate the representation while preserving semantic size and orientation.

Keep `uv_coordinate_preservation_required` true for bitmap-textured, baked, lightmapped, atlas, decal, or hand-painted assets. It may be false only when the contract has no coordinate-dependent appearance and allows the exporter to reparameterize UVs; UV existence, finite values, and nonzero area on every polygon remain mandatory.

For an image-textured character, fill `lookdev.critical_regions` with areas such as face, eyes, mouth, hairline, hands, or costume marks that must remain readable. Inventory shared atlases and alpha surfaces before changing tints or transparency. Record both diagnostic close-up distance and expected gameplay camera distance; passing only one does not prove the other.

## Prototype defaults

Use these only when the request does not supply a target:

- meters; dimensions inferred from the object category and clearly disclosed;
- bottom-center pivot for placeable props, local origin for articulated pieces;
- one material set, metallic-roughness PBR, 1024 px maximum;
- desktop real-time target, conservative shader features;
- source `.blend` plus `.glb`; do not silently promise `.fbx` when an FBX round-trip cannot be tested;
- no rig, animation, LOD, collider, lightmap UV, or engine project mutation unless requested;
- triangle budget chosen from the target size and viewing distance, recorded as an assumption.

## Questions worth stopping for

Stop for user input when any of these are genuinely ambiguous and consequential:

- character/prop identity or art direction would change substantially;
- the output must fit an existing skeleton, attachment point, material convention, or exact engine project;
- an existing authored asset would be destructively changed;
- a paid provider, external upload, credential, installation, or new persistent service is required;
- trademarked/person-specific likeness or third-party license terms affect intended use.

Do not stop merely to ask the user for implementation choices the technical artist can safely derive.
