# Import a Hashed 2D Sprite Delivery

Use this contract only when the input came from `$create-2d-game-art` with a
sprite PNG, its JSON manifest, and a passing structural audit. The target Unity
project and its installed editor version remain authoritative.

## Preflight the Exact Delivery

1. Recompute the PNG and manifest SHA-256 values. Require the PNG hash to equal
   `artifact.sha256`, then rerun the bundled `sprite_pipeline.py audit` against
   those exact files. Stop on any mismatch or nonzero audit result.
2. Require `artifact.format == "PNG"`, `artifact.mode == "RGBA"`, and the
   manifest path to identify the exact PNG being imported.
3. Read the accepted 2D asset contract for pixels per unit, sRGB, filter mode,
   compression, mipmaps, mesh type, wrap mode, max size, loop policy, and the
   requested states and directions. Do not invent missing production settings.
4. Copy or generate only into the authorized Unity project's intended `Assets/`
   path. Preserve the source delivery and provenance receipt separately.
5. If the target Unity version or project architecture has no supported way to
   apply and re-read exact sprite metadata, stop as `blocked`; never replace an
   importer gate with a `.meta` guess or prose.

## Configure the Texture Importer

After the per-call project-identity gate in `SKILL.md`, use a project-compatible
Unity Editor API to set and then re-read at least:

- `TextureImporterType.Sprite` and `SpriteImportMode.Multiple` for a sheet, or
  `SpriteImportMode.Single` for a `pixelize` delivery;
- accepted pixels per unit, pivot/alignment, sRGB, alpha transparency, wrap
  mode, mesh type, max texture size, and platform overrides;
- Point filtering, disabled mipmaps, and uncompressed texture data for pixel
  art unless the accepted contract explicitly specifies otherwise.

Prefer Unity's Sprite Editor Data Provider API for multi-sprite metadata in
versions that expose it. Reflect the installed Unity and package APIs before
writing C#; do not assume an obsolete `TextureImporter.spritesheet` surface.
Save, reimport, and re-read the importer. Serialized intent alone is not import
evidence.

## Convert Manifest Geometry Exactly

The manifest declares sheet and frame rectangles from the image's top-left,
while Unity sprite rectangles use a bottom-left texture origin. For every frame:

```text
unity_x = rect_px_top_left.x
unity_y = sheet_height - rect_px_top_left.y - rect_px_top_left.height
unity_width = rect_px_top_left.width
unity_height = rect_px_top_left.height

pivot_normalized_x = pivot_px_from_bottom_left.x / unity_width
pivot_normalized_y = pivot_px_from_bottom_left.y / unity_height
```

Use the manifest `id` as the stable sprite name. Reject duplicate IDs, missing
sprites, out-of-bounds rectangles, changed frame counts, or imported rect/pivot
values that differ from the converted values. A single-sprite delivery consumes
the top-level `sprite.pivot_px_from_bottom_left` using the same normalization.

## Build Animation Clips From Semantics

Group frames only by explicit `state` and `direction`; array order within each
group is playback order. Convert each `duration_ms` into cumulative key times
for the `SpriteRenderer.sprite` object-reference curve. Do not replace
nonuniform durations with a guessed FPS. Take loop behavior and transitions
from the accepted asset/design contract because the sheet manifest does not
invent them.

After saving each clip, re-read its sprite keys and verify names, order, key
times, loop setting, and final duration. Then bind the clip through the
project's documented Animator or animation architecture instead of creating an
unowned parallel controller.

## Engine Evidence and Handoff

The engine-import evidence must record:

- source PNG and manifest hashes plus the passing audit hash;
- canonical Unity project root and revision;
- imported texture, sprite, clip, controller, prefab, and scene paths;
- observed importer settings;
- observed sprite names, converted rectangles, pivots, and clip key times;
- compile and Console status.

Run `$play-unity-game` when runtime presentation is required. Its evidence must
bind the same delivery hash and cover gameplay-camera scale, animation timing,
loop seams, contacts, sorting, reset, and replay before the 2D production
receipt may be marked `validated`.
