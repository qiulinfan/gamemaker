# 2D Asset Contract

Use this record before producing more than one representative asset or animation slice. Store project-specific values in the target game repository, not in this Skill.

```yaml
schema_version: 1
job:
  id: ""
  kind: original_raster|concept_to_sprite|adapt_frames|sprite_animation|tileset|ui_art
  preset: prototype|production
role:
  gameplay_function: ""
  semantic_states: []
  directions: []
  variants: []
visual:
  source_authority: []
  style_traits: []
  must_preserve: []
  must_avoid: []
  camera_distance: ""
  native_scale_readability: ""
raster:
  frame_size_px: [0, 0]
  color_space: srgb
  palette:
    mode: none|median-cut|oklab|authored
    max_visible_colors: null
  alpha: straight
  background: keep|corner-connected|authored-mask
  outline_policy: ""
layout:
  frame_order: []
  frame_duration_ms: 100
  loop: false
  pivot_policy: bottom-center
  padding_px: 0
  columns: 0
engine:
  name: ""
  pixels_per_unit: null
  filter_mode: point
  compression: none
  mipmaps: false
  target_platforms: []
budgets:
  max_sheet_size_px: [8192, 8192]
  max_frames: 4096
source_and_license:
  creator: ""
  source_url: ""
  license: ""
  attribution: ""
  generation_provider: ""
  generation_prompt_record: ""
outputs:
  editable_source: ""
  engine_delivery: ""
  frame_manifest: ""
  preview: ""
  audit: ""
acceptance:
  visual_cases: []
  animation_cases: []
  technical_gates: []
  engine_cases: []
assumptions: []
open_questions: []
```

## Presets

`prototype` defaults to one representative state or loop, an explicit logical frame size, preserved alpha, bottom-center pivot for grounded characters, deterministic frame order, a preview, and a structural audit. Engine import may remain untested.

`production` additionally requires complete state/direction coverage, source and license records, native/gameplay-scale visual acceptance, timing and reset checks for animation, exact target importer settings, runtime evidence, and a receipt bound to the delivered hashes.

## Contract Rules

- Choose logical sprite dimensions from gameplay readability and project pixel density, not from the source image's arbitrary resolution.
- Treat `frame_size_px`, `pixels_per_unit`, and camera reference resolution as separate values that must agree at integration time.
- Define semantic animation verbs and transitions. “Animated” is not a coverage requirement.
- Define the pivot from observable contact or sorting behavior. For a grounded actor, use one stable baseline unless a deliberate displacement is part of the animation.
- Keep state, direction, duration, and order in explicit metadata when filenames alone are ambiguous.
- Record generated imagery, user-authored imagery, and licensed third-party imagery as different source authorities.
- Do not use background removal merely because an image has a visually uniform corner; preserve the background unless transparency is part of the contract.
