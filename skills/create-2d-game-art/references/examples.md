# Examples

## Run the Bundled End-to-End Example

The example uses two tiny authored PPM frames. It demonstrates explicit state, direction, timing, connected-corner background removal, deterministic OKLab palette reduction, sheet packing, a checkerboard preview, and an independent audit.

From the linked Skill directory on macOS or Linux:

```sh
pipeline="$skill_dir/scripts/sprite_pipeline.py"
example_root="$skill_dir/assets/examples"

uv run "$pipeline" build \
  --frame-data "$example_root/orb-frames.json" \
  --frame-width 16 --frame-height 16 \
  --fit contain --anchor bottom-center --resample nearest \
  --background corner-connected --background-tolerance 8 \
  --alpha-threshold 1 --palette oklab --colors 5 --seed 123 \
  --columns 2 --padding 1 --pivot bottom-center \
  --output-root "$example_root" \
  --output generated/orb-idle-sheet.png \
  --manifest generated/orb-idle-sheet.json \
  --preview generated/orb-idle-preview.png --preview-scale 6 \
  --force

uv run "$pipeline" audit \
  --image "$example_root/generated/orb-idle-sheet.png" \
  --manifest "$example_root/generated/orb-idle-sheet.json" \
  --output-root "$example_root" \
  --output generated/orb-idle-audit.json --force

uv run "$skill_dir/scripts/validate_receipt.py" \
  "$example_root/generated/orb-production-receipt.yaml" \
  --provenance-root "$example_root"
```

The committed generated artifacts are a review fixture, not a style template. The interior white highlight remains because background removal clears only connected background pixels.

## Frame-Data Schema

Use paths relative to the JSON file. Order in the array is sheet and playback order.

```json
{
  "schema_version": 1,
  "frames": [
    {
      "path": "walk/walk-south-0.png",
      "id": "walk_south_0",
      "state": "walk",
      "direction": "south",
      "duration_ms": 90
    },
    {
      "path": "walk/walk-south-1.png",
      "id": "walk_south_1",
      "state": "walk",
      "direction": "south",
      "duration_ms": 110
    }
  ]
}
```

The file accepts exactly `schema_version` and `frames`. Each frame accepts exactly `path`, `id`, and optional `state`, `direction`, and `duration_ms`. Paths must remain beneath the JSON file's directory and frame IDs must be unique case-insensitively.

## Convert a Smooth Concept Into One Prototype Sprite

```sh
uv run "$pipeline" pixelize \
  --input "$concept_png" \
  --frame-width 48 --frame-height 48 \
  --fit contain --anchor bottom-center --resample lanczos \
  --background keep --alpha-threshold 8 \
  --palette oklab --colors 16 --seed 123 \
  --output-root "$output_root" \
  --output concept-sprite.png --manifest concept-sprite.json \
  --preview concept-sprite-preview.png --preview-scale 6 \
  --pivot bottom-center
```

Inspect the result at 48×48 before enlarging it. Automated palette reduction is a starting point; hand-correct semantic landmarks and rerun the audit after every edit.

## Repack Existing Pixel Frames Without Resampling

```sh
uv run "$pipeline" build \
  --input-dir "$frames" --pattern '*.png' \
  --frame-width 32 --frame-height 32 \
  --fit contain --anchor bottom-center --resample nearest \
  --background keep --alpha-threshold 1 --palette none \
  --columns 8 --padding 0 --pivot bottom-center --duration-ms 80 \
  --output-root "$output_root" \
  --output run-sheet.png --manifest run-sheet.json \
  --preview run-preview.png --preview-scale 8
```

Use explicit frame data instead when the directory contains several states or directions, or when timing is not uniform.
