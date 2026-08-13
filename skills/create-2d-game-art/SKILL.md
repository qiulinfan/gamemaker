---
name: create-2d-game-art
description: Create, adapt, pixelize, sequence, pack, and validate standalone 2D game art. Use for sprites, sprite animation frames, sprite sheets, tilesets, icons, UI art, portraits, backgrounds, or other raster game assets when Codex must turn a concept, generated image, licensed source, or existing frame set into an engine-ready 2D artifact with stable dimensions, palette, alpha, pivots, frame metadata, previews, hashes, and audit evidence. Use after search-game-art when sourced 2D art needs production adaptation. Do not use for finding third-party assets, 3D technical art, or Unity scene integration.
---

# Create 2D Game Art

Create the smallest complete 2D asset slice that can be inspected, replayed, and handed to an engine workflow. A generated image, source drawing, notebook output, or visually plausible sheet is not by itself an engine-ready sprite asset.

Match user-facing explanations, prompts, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys, action codes, and raw errors unchanged.

## Keep the Boundaries Clear

- Use `$search-game-art` to find, compare, license, acquire, and audit third-party sprites or packs. Return here only for adaptation, repacking, or production.
- Use ImageGen or an authorized drawing surface for source imagery and visual exploration. Treat its output as source imagery until the artifact and visual gates pass.
- Use this Skill for standalone 2D production, including pixel-art conversion and sprite-sheet construction.
- Use `$auto-ta` when the deliverable is a 3D model, material, rig, skeletal animation, shader, VFX system, or a 2D image that exists only to support a 3D asset.
- Hand an audited 2D artifact to `$build-unity-scene` for project-aware import, SpriteImporter settings, slicing, AnimationClips, prefabs, scenes, and runtime validation. This Skill does not mutate Unity.

## Establish the Asset Contract

Read [references/asset-contract.md](references/asset-contract.md). Resolve the target role, camera distance, logical pixel size, frame/state coverage, pivot policy, palette and alpha needs, engine constraints, source authority, and evidence plan before producing a large set.

If details are missing, use the `prototype` preset and state the assumptions. Ask only when the answer changes authorization, cost, irreplaceable source data, the basic artistic identity, or target compatibility.

Protect every input:

- work into a new output root and never overwrite the only authored source;
- hash user-authored and third-party inputs before adaptation;
- keep source art, working frames, packed sheets, previews, manifests, and engine imports distinct;
- preserve creator, source URL, license, attribution, generation provenance, and modification history in the target project;
- do not place credentials, private prompts, purchase receipts, cookies, or personal paths in portable receipts.

## Choose the Smallest Production Route

1. **Original raster art** — establish a visual direction, create one representative asset or state, inspect it at native size and gameplay scale, then expand.
2. **Concept-to-sprite** — generate or draw source imagery, remove only justified background regions, normalize silhouette and anchor, reduce to the target resolution and palette, then hand-correct important pixels when needed.
3. **Existing-frame adaptation** — preserve the original frame order and timing, normalize canvas and pivots, repair alpha/palette inconsistencies, and repack without losing provenance.
4. **Sprite animation** — define semantic states and directions, make one loop or action pass first, inspect timing and contacts, then build the complete sheet and frame manifest.
5. **Tileset or UI art** — apply the same source, color, alpha, scale, and visual gates, plus the tileset seam/autotile or UI stretch/9-slice gates in [references/quality-gates.md](references/quality-gates.md). Do not force these assets through a sprite-animation grid when their native format is more appropriate.

Discard manual stages that do not improve the delivery. Do not create notebooks, per-action glue scripts, duplicated temporary tiles, or character-specific filename logic when one deterministic job can express the same contract.

## Build One Representative Slice

Before batching, finish one state, direction, tile family, icon family, or UI component end to end. Inspect:

- silhouette and semantic readability at the gameplay camera scale;
- consistent canvas, baseline, pivot, proportions, lighting, palette, and outline weight;
- alpha edges against light and dark backgrounds;
- animation pose order, timing, loop seam, anticipation, contact, recovery, and directional identity;
- frame-to-frame jitter and accidental subpixel movement;
- exact engine-facing dimensions and metadata.

Expand only after the representative slice passes. A contact sheet is a review aid, not a replacement for native-scale inspection or animation playback.

## Use the Deterministic Raster Pipeline

The bundled pipeline replaces the old notebook-driven ImageToPixel workflow. It performs no web calls and writes only beneath an explicit existing output root. `uv run` resolves the script's declared Pillow and NumPy dependencies in an isolated managed environment and uses the adjacent lock file for reproducible versions and package hashes.

Resolve the linked Skill independently of the target game's current directory. On macOS or Linux:

```sh
codex_home="${CODEX_HOME:-$HOME/.codex}"
skill_dir="$(realpath "$codex_home/skills/create-2d-game-art")"
pipeline="$skill_dir/scripts/sprite_pipeline.py"
test -f "$pipeline"
```

On Windows PowerShell 7:

```powershell
$CodexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
  Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
} else {
  [System.IO.Path]::GetFullPath($env:CODEX_HOME)
}
$SkillDir = (Resolve-Path -LiteralPath (Join-Path $CodexHome 'skills\create-2d-game-art')).Path
$Pipeline = (Resolve-Path -LiteralPath (Join-Path $SkillDir 'scripts\sprite_pipeline.py')).Path
```

Treat failure to resolve the script as `CREATE_2D_GAME_ART_NOT_LINKED`; do not fall back to a `scripts/...` path relative to the game repository.

### Build a sheet from a frame directory

Use natural filename order for a quick homogeneous sequence:

```sh
uv run "$pipeline" build \
  --input-dir "$source_frames" --pattern '*.png' \
  --frame-width 48 --frame-height 48 \
  --fit contain --anchor bottom-center --resample lanczos \
  --background keep --alpha-threshold 1 \
  --palette oklab --colors 16 --seed 123 \
  --columns 6 --padding 1 --pivot bottom-center --duration-ms 100 \
  --output-root "$output_root" \
  --output hero-walk.png --manifest hero-walk.json \
  --preview hero-walk-preview.png --preview-scale 6
```

Use `--background corner-connected` only when the corners genuinely identify a flat removable background. It flood-fills connected background regions; it does not globally erase every matching interior color. The safe default is `keep`.

### Preserve explicit state and timing

For multiple states, directions, or nonuniform timings, provide a strict frame-data JSON file instead of encoding production semantics in incidental directory order. See [references/examples.md](references/examples.md) for the schema and a complete bundled example.

### Pixelize one source image

Use `pixelize` for a single logical frame. Choose `lanczos` for reducing smooth source imagery and `nearest` when the source is already pixel art. `median-cut` supports optional Floyd-Steinberg dithering; deterministic `oklab` palette reduction does not.

### Audit the delivery

Always re-read the generated PNG and manifest:

```sh
uv run "$pipeline" audit \
  --image "$sheet" --manifest "$manifest" \
  --output-root "$output_root" --output sprite-audit.json
```

The audit verifies actual PNG/RGBA encoding, binds the source and processing manifest fields into PNG metadata, and checks the encoded hash, decoded RGBA digest, dimensions, alpha counts, visible palette count, preview identity and scale, grid geometry, frame rectangles, pivots, and cropped frame digests. It reads each encoded input into one bounded byte snapshot so the reported hashes and decoded facts cover the same bytes. Exit `0` means every implemented check passed, exit `1` means the artifact failed an audit check, and exit `2` means the request or input was invalid. A passing structural audit is not an artistic or runtime verdict.

The tool refuses path escape and existing outputs by default. Use `--force` only for the current run's explicitly named files after confirming they are disposable; it never authorizes source overwrite or directory deletion.

## Validate the Real Artifact

Read [references/quality-gates.md](references/quality-gates.md). Apply every relevant gate and mark irrelevant gates `not_applicable`, not silently absent. At minimum, inspect the final encoded artifact, the native-resolution frames, the preview, and any animation playback.

For a sheet, verify that the manifest's semantic state, direction, duration, rect, and pivot data match the actual sequence. For pixel art, verify integer-scale presentation, intentional palette and alpha, and no smoothing. For a tileset, test seams and rule coverage in a representative map. For UI, test target resolutions and every intended stretch region.

Do not claim engine readiness until the authorized engine workflow imports the exact hashed artifact and verifies filter mode, compression, mipmaps, color space, pixels per unit, slicing, pivots, animation timing, material/shader behavior, and gameplay-camera readability.

## Record Evidence and Hand Off

Write a production receipt using [references/receipt-schema.md](references/receipt-schema.md) in the target project's normal provenance location. Bind it to the generated manifest and audit report hashes. Use these status labels exactly:

- `validated`: every required artifact, visual, technical, and requested engine gate passed;
- `prototype`: useful for iteration, with named game-ready gates intentionally untested;
- `blocked`: a required source, authority, tool, license, or target is unavailable;
- `failed`: execution completed but a required gate failed.

Without engine import evidence, a structurally and visually approved sprite delivery still has status `prototype`; record `prototype_ready_for_engine_import` only as a readiness note or `next_action`, never as a fifth status value. Do not relabel it `validated`.

Validate the completed YAML or JSON receipt against the real referenced files:

```sh
uv run "$skill_dir/scripts/validate_receipt.py" \
  "$receipt" --provenance-root "$provenance_root"
```

Exit `0` means the declared status honestly matches the strict gate reduction
and every referenced portable path and hash. Exit `2` means schema, evidence,
hash, or status reduction failed; exit `3` means invocation or I/O failed.

Return the contract, exact source and output identities, generated manifest, audit, visual evidence, licenses/provenance, passed/failed/not-tested gates, status, limitations, and the next owner. Never turn an untested aesthetic, animation, or engine behavior into prose implying success.
