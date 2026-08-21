# 2D Art Quality Gates

Apply the gates relevant to the asset contract. Evidence from one lane cannot substitute for another.

## Artifact and Raster Gates

- The delivered file is actually PNG-encoded RGBA, decodes successfully, and its SHA-256 and decoded RGBA digest match the manifest and audit.
- The PNG-embedded manifest binding matches the source identities, processing contract, frame metadata, and sprite pivot record in the manifest.
- Dimensions, mode, alpha counts, and visible palette count match the contract.
- Transparent pixels do not retain visible matte contamination at the silhouette edge when composited over light and dark backgrounds.
- Background removal preserves disconnected interior colors and intentionally enclosed highlights.
- Logical pixels remain aligned to the intended grid; no accidental smoothing or fractional resampling appears at runtime.
- Source, working, preview, manifest, audit, and delivery files remain distinct and traceable.
- Output sheets remain within the target texture and platform budgets.

## Sprite and Sheet Gates

- Every required state, direction, variant, transition, and frame exists exactly once unless the contract says otherwise.
- Frame order and `duration_ms` express the intended timing; natural filename order is not accepted as semantic proof when several actions are mixed.
- All frame rectangles are within the sheet, non-overlapping, and bound to their decoded crop digests.
- Canvas dimensions, baseline, pivot, subject scale, and contact point remain stable across frames.
- Padding is intentional and importer slicing can reproduce the manifest rectangles exactly.
- Native-size and enlarged checkerboard previews show no clipping, edge bleed, unexpected holes, or palette drift.
- Animation playback shows no unexplained jitter, loop pop, foot/contact sliding, facing reversal, missing anticipation, or missing recovery.

## Pixel-Art Gates

- The target resolution is the authored resolution; enlarged review images use nearest-neighbor scaling only.
- Palette reduction preserves gameplay-significant contrast and semantic colors rather than merely hitting a color count.
- Dithering is intentional and readable at native scale; disable it when it creates noise or motion shimmer.
- Diagonals, curves, outlines, clusters, highlights, and shadows have deliberate pixel rhythms.
- Automated conversion receives a human visual pass on silhouette, face/hands, weapon/prop contacts, and other semantic landmarks.

## Tileset Gates

- Tiles share an exact grid size and origin.
- Orthogonal and, when required, diagonal seams pass for every neighboring family.
- Autotile or terrain-rule coverage includes edges, corners, inner corners, isolated tiles, transitions, and declared variants.
- Collision, navigation, sorting, and decorative overhang assumptions are recorded separately from the raster.
- A representative map proves repetition, readability, and absence of unintended seams.

## UI and Icon Gates

- Icons remain identifiable at every shipped size and in disabled, selected, highlighted, or warning states when required.
- UI art survives every target resolution, aspect ratio, and localization expansion named by the contract.
- 9-slice borders and stretch regions are explicit and do not distort corners, strokes, or motifs.
- Text is not baked into reusable artwork unless localization explicitly permits it.
- Alpha, premultiplication, color space, and shader/blend behavior are verified in the target UI renderer.

## Engine Gates

- The exact intended engine project and imported artifact identity are verified by the target project's own engine workflow before mutation.
- Texture type, sprite mode, filter mode, compression, mipmaps, wrap mode, sRGB, pixels per unit, mesh type, and max size match the contract.
- Slice rectangles, names, pivots, borders, and physics shapes match the manifest or documented engine overrides.
- AnimationClips use the intended frame order, duration, loop behavior, events, and transitions.
- Pixel-perfect camera or equivalent rendering settings preserve integer-scale presentation where required.
- Gameplay-camera captures and independent play show correct readability, sorting, contacts, reset, and replay.

## Verdict Reduction

- Any failed required gate makes the delivery `failed` until a new artifact passes fresh evidence.
- A missing source/license/authority/tool/target makes the delivery `blocked` when it prevents safe progress.
- A useful artifact with named untested visual, animation, tileset, UI, or engine gates is `prototype`.
- Use `validated` only when every gate required by the accepted contract passed against the exact delivery.
