# 2D Sprite Source Coverage

Use this source map for sprites, sprite sheets, frame sequences, atlases, tilesets, icons, UI art, portraits, backgrounds, and flipbook VFX. It is a search order and evidence-cost model, not a license verdict. Availability and terms change; re-open the canonical listing and governing terms during every real search.

## Tier A: Predictable Open Baseline

### Kenney

Search [Kenney 2D assets](https://kenney.nl/assets/category:2D) first when a broadly reusable CC0 prototype can meet the role.

- Require the canonical asset page to declare CC0; do not infer one asset's terms for the whole site.
- After acquisition, verify the included license and actual files, including individual sprites versus sheets, tile size, margins, spacing, metadata, vector sources, and preview-only files.
- Use Kenney's [support/licensing page](https://kenney.nl/support) as governing context and its [tilemap guidance](https://kenney.nl/knowledge-base/game-assets-2d/importing-and-using-tilemaps) only as technical guidance, not proof of a particular archive's contents.

## Tier B: Per-Submission Open Catalogs

### OpenGameArt

Use [advanced search](https://opengameart.org/art-search-advanced) with `2D` and `CC0` as the default low-burden query. Expand to attribution licenses only when the target project accepts their obligations.

- Treat each submission and offered license separately. Explicitly select and record the license relied upon.
- Acquire only files in the submission's `File(s)` section; never treat the preview as the distributable artifact.
- Route CC BY, CC BY-SA, GPL, multiple-license, DRM/storefront, and share-alike interactions to explicit license review before recommendation.
- Use the platform [FAQ](https://opengameart.org/content/faq) and [submission guidelines](https://opengameart.org/content/art-submission-guidelines) to interpret platform structure, then preserve the asset page and included license evidence.

### itch.io

Search the [sprite](https://itch.io/game-assets/tag-sprites) and [spritesheet](https://itch.io/game-assets/tag-spritesheet) catalogs for indie packs and editable sources.

- Require creator-authored terms that map to the exact downloadable file, edition, version, and price tier.
- Do not infer rights from `free`, `name your own price`, a download button, or itch.io's platform [Terms of Service](https://itch.io/docs/legal/terms).
- Record exact filenames, file sizes, free versus paid editions, AI disclosure, PNG/sheet/sequence form, grid and frame size, FPS, animation verbs, and `.aseprite`, PSD, or other editable-source claims.
- Preserve a license snapshot and audit the obtained archive because one page can mix differently licensed or differently priced files over time.

## Tier C: Commercial and Engine-Ready Gap Filling

Use this tier when specialized animation coverage, editable sources, support, or engine-ready packaging materially improves the current slice. Search is not purchase authority.

### GameDev Market

Search the [2D catalog](https://www.gamedevmarket.net/category/2d) and verify the current [Marketplace Terms](https://www.gamedevmarket.net/terms-conditions).

- Record the purchase-era license, non-exclusive/perpetual scope, commercial and multi-project permission, attribution, derivative-work ownership terms, and restrictions on logos/trademarks, standalone redistribution, extraction, NFT use, and AI training.
- Treat listing technical details as declared evidence. Verify exact sheet versus sequence form, frame dimensions, actions, directions, source formats, version, changelog, dependencies, and the acquired package.
- Downloaded filenames may not preserve the listing identity; bind the listing URL, purchase record, original archive, and hash explicitly.

### Unity Asset Store

Search the [2D catalog](https://assetstore.unity.com/2d) and verify the listing against the [Asset Store Terms and EULA](https://unity.com/legal/as-terms).

- Distinguish Standard EULA, Restricted Asset, Provider EULA, and package-internal third-party licenses.
- Distinguish content assets from per-seat tools/extensions and record Single versus Multi Entity scope and contractor implications.
- Do not place raw assets in a public repository or assume a `.unitypackage`, source PSD, sliced sheet, pivot, PPU, AnimationClip, render-pipeline claim, or dependency until the actual package proves it.
- Record the target Unity version and hand audited acquisition to the project integration workflow rather than importing during search.

### Fab

Verify the listing against the [Fab EULA](https://www.fab.com/eula), [license and pricing rules](https://dev.epicgames.com/documentation/en-us/fab/licenses-and-pricing-in-fab), and the actual download dialog.

- Distinguish Fab Standard, CC BY, and legacy UE Marketplace licenses by format and acquisition date.
- Exclude `Reference Only` when raw sprite files are required.
- Distinguish content assets from per-seat plugins/tools; check UE-only, extraction, redistribution, editable-project, and dependency constraints.
- `Source asset` does not prove layered authoring files. Verify exact `.psd`, `.psb`, `.ase`, `.aseprite`, `.spine`, `.png`, or vector files after acquisition.

### Focused Creator Stores

Use [CraftPix sprites](https://craftpix.net/categorys/sprites/) or [GameArt2D sprites](https://www.gameart2d.com/sprites.html) only when their style or formats materially improve coverage.

- Re-open [CraftPix licensing](https://craftpix.net/file-licenses/) for the exact tier. Record commercial/modification scope, standalone redistribution limits, and the platform's AI/ML training, testing, and validation restriction.
- Re-open [GameArt2D licensing](https://www.gameart2d.com/license.html). Treat its Freebies CC0 statement separately from paid-product permission and redistribution limits.
- Verify actual delivered formats and sources per product; a store-wide license does not establish technical contents.

## Required 2D Candidate Evidence

Extend the normal candidate record with:

```yaml
two_d_delivery:
  form: sheet|frame_sequence|atlas|individual_sprites|tileset|layered_source
  sheet_size_px: null
  frame_size_px: null
  rows: null
  columns: null
  margin_px: null
  spacing_px: null
  frame_order: unknown
  fps_or_frame_durations: unknown
  pivot: unknown
  alpha: unknown
  animation_verbs: []
  directions: []
  editable_sources_claimed: []
  editable_sources_verified: []
license_detail:
  exact_download_filename: ""
  edition_or_price_tier: ""
  license_snapshot: ""
  drm_or_share_alike: ""
  ai_restrictions: ""
  seat_entity_contractor_scope: ""
  dependency_licenses: []
acquired_evidence:
  archive_sha256: ""
  package_manifest: ""
  included_license_files: []
  declaration_discrepancies: []
```

Keep `editable_sources_claimed` and `editable_sources_verified` separate. A platform tag, price, listing preview, title containing “spritesheet,” or filename never proves license or file contents.
