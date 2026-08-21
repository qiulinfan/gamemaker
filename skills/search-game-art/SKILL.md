---
name: search-game-art
description: Read a game design brief, turn visual, thematic, gameplay, animation, and technical needs into an asset requirement matrix, then run a source-covered search for license-verified game art. Use for 2D or 3D models, textures, materials, icons, UI, animation, VFX, fonts, or environment kits when appearance and functional coverage must both fit. In selection mode, return a ranked shortlist and a search-coverage record without downloading. When the user explicitly asks to acquire or import assets, audit the actual files, stage only the needed subset, preserve provenance, and hand engine integration to the target project's own engine workflow.
---

# Search Game Art

Find assets that support the game design, not merely assets that resemble a reference image. Treat visual fit, thematic role, gameplay function, animation coverage, technical compatibility, and license as separate requirements.

## Choose the Mode

Use the least invasive mode authorized by the user:

- **Selection mode**: search, verify, compare, and recommend. Do not download or import.
- **Acquisition mode**: when the user explicitly asks to download, acquire, or import, also audit the selected files and stage the smallest useful subset.
- **Engine integration handoff**: when the user explicitly asks to put the asset into an engine project or scene, complete source, license, and file auditing here, then hand the audited candidate and import record to the target project's own engine workflow. This Skill performs no engine import itself.

Do not convert a search request into an import. Do not treat permission to download one candidate as permission to purchase paid content or accept a custom license.

## Read the Design Source Hierarchy

Read the project's authoritative design, art, level, interaction, and technical documents before searching. Resolve conflicts according to the project's documented source hierarchy. Separate:

- confirmed requirements from source documents;
- synthesis that combines multiple confirmed facts;
- assumptions needed to proceed;
- open questions that materially affect selection.

Do not turn an example, mood reference, or brainstorm into a mandatory requirement.

## Build an Asset Requirement Matrix

Create one row per asset role or animation family. Use the demand-record schema in [references/asset-records.md](references/asset-records.md).

For each row, capture:

- gameplay function and player-visible feedback;
- narrative or thematic role;
- visual style, mood, palette, silhouette, and camera distance;
- required pieces, variants, states, and estimated quantity;
- required animation verbs and transitions;
- engine, render pipeline, format, scale, rig, shader, and texture constraints;
- performance budget and target platform;
- acceptable license, attribution burden, and budget;
- required editable source, such as `.blend`, layered textures, source rig, or source animation, when local adaptation matters;
- priority: current vertical slice, near-term reusable, or speculative.

Animation verbs must be semantic and testable, such as `sit_down`, `seated_idle`, `stand_up`, `point`, `push`, `open_door`, or `carry`. Do not accept the label “animated” as coverage.

## Decompose References Before Searching

Translate every named visual reference into explicit traits. Record:

- `must_preserve`: the parts of the current direction the user already likes;
- `desired_traits`: silhouette, emotional valence, texture treatment, proportion, motion quality, or camera readability to borrow;
- `must_avoid`: motifs, costumes, expressions, genre signals, or cultural markers that would over-literalize the reference;
- `allowed_to_change`: elements that can be remodeled, retextured, hidden, or replaced.

Do not turn “like” into “copy every recognizable motif.” If a reference could imply several identities, search the trait vocabulary and keep the current concept intact until the user approves a larger identity change.

## Search by Coverage

Use internet search because availability, versions, prices, and licenses can change. Prefer original asset pages and official creator repositories.

Search each high-priority row across multiple query families, not one literal phrase:

```text
<gameplay function> + <visual style> + <dimension> + <engine/format>
<animation verb family> + humanoid + FBX/GLB + Unity
<thematic object> + low poly + CC0
<reference style> + modular kit
<role or age> + <silhouette or proportion> + <emotional valence>
<creator tag or collection> + rigged/downloadable + <license>
```

For sprites, sprite sheets, frame sequences, atlases, tilesets, icons, UI art,
portraits, backgrounds, or flipbook VFX, read
[references/2d-sprite-sources.md](references/2d-sprite-sources.md). Search its
source tiers in order, adapting coverage to the role. Record sheet-versus-frame
form, dimensions, layout, timing, directions, alpha, pivots, exact downloadable
edition, editable-source claims, and governing license as separate evidence.

For uniformly licensed sources with a public API (currently Poly Haven, CC0),
acquisition may be scripted; follow the access pattern and provenance
requirements in [references/source-apis.md](references/source-apis.md).

Record the query families and source classes tried. For authored 3D characters and unusual stylized models, the default coverage should include:

- **Sketchfab** for creator-published, downloadable, scanned, hand-painted, and niche stylized models; inspect the original model page, creator profile, tags, collections, downloadable state, per-item license, geometry/animation declarations, and any linked creator download page;
- **itch.io and creator-owned stores** for indie packs, source `.blend` files, source textures, and name-your-own-price editions;
- **Unity Asset Store and Fab** for engine-ready packages whose pipeline/version claims matter;
- **CGTrader, TurboSquid, and creator storefronts** when paid editable sources may close a high-priority gap;
- **Poly Haven, ambientCG, Kenney, Quaternius, official repositories, and comparable primary CC0/open sources** for reusable public-domain or openly licensed materials, props, models, and animation libraries.

Adapt this list to the asset class; do not mechanically search every platform for every icon or font. However, do not end a character search after only general web results, one engine marketplace, or one low-poly pack site. If the shortlist is merely “acceptable,” broaden synonyms, emotional tone, creator tags, adjacent categories, and platform coverage before lowering the visual bar.

Sketchfab availability is not a license verdict. Free downloadable items use per-item Creative Commons terms, source and converted formats can differ, and automated downloads may require the user's authenticated account. Never handle credentials or infer permission from the download icon. If the user downloads through their own session, audit the delivered archive normally.

Do not use image thumbnails, re-upload sites, compilation blogs, search snippets, or AI summaries as proof of permission or file contents.

## Verify Declared Evidence

Open the original page for every serious candidate and record:

- asset name, creator, source page, version, and publication/update date;
- license name, license URL, attribution, commercial use, modification, redistribution, share-alike, non-commercial, and AI-use restrictions;
- price and whether the free download is genuinely available;
- the exact edition, tier, or sub-package covered by each headline claim;
- declared formats, engine support, render pipeline, polygon count, texture size, rig, animation list, root-motion behavior, and modular contents;
- visual fit, functional coverage, and likely adaptation work.

Also record a compact search-coverage receipt using [references/asset-records.md](references/asset-records.md). A strong candidate discovered late is evidence that earlier platform or vocabulary coverage was incomplete; add the missing source class or query family rather than treating the result as luck.

If the source and license disagree, permission is unclear, or the only evidence is a re-upload, exclude the candidate from the recommended shortlist. Prefer CC0 for prototypes. Treat CC BY, share-alike, and marketplace licenses as explicit tradeoffs. Do not recommend non-commercial assets for a potentially commercial project.

For 2D listings, keep `editable_sources_claimed` separate from
`editable_sources_verified`. A store tag, title containing “spritesheet,” PNG
preview, price, or download button does not establish the delivered grid,
frames, layered sources, or permission. Use the 2D candidate extension in
[references/2d-sprite-sources.md](references/2d-sprite-sources.md).

## Compare Candidates

Return three to eight strong candidates when the user asks for a broad shortlist. A focused acquisition pass may use one primary candidate and one fallback.

Score each candidate independently on:

| Dimension | Question |
| --- | --- |
| Visual fit | Does the silhouette, mood, palette, and camera-distance readability fit? |
| Theme fit | Does the asset reinforce the narrative or rule language of the scene? |
| Functional coverage | Does it contain the exact pieces, states, and animation verbs required? |
| Technical fit | Will format, scale, rig, shaders, textures, and performance work? |
| License fit | Can the project use, modify, and ship it with an acceptable burden? |
| Adaptation cost | How much remodeling, retexturing, retargeting, or setup remains? |
| Source editability | Are the authored source, textures, rig, and legal modification rights available for the expected Blender work? |

Recommend one primary candidate and one fallback. Do not select from aesthetics alone. Prefer an asset that closes a current gameplay gap over a large pack whose useful contents are speculative.

Score character appearance, skeleton suitability, editable-source quality, and animation coverage separately. A character model does not need bundled clips when it has a usable rig and a verified external animation library covers the required verbs. Conversely, owning an animation library does not rescue an unsuitable silhouette, broken skinning, ambiguous license, or uneditable source. Keep `bundled_animation` and `external_retarget_path` as separate evidence until the actual character/clip pair passes retargeting.

## Audit Acquired Files

In acquisition mode, download to a temporary directory first. Do not import an archive directly into the project.

1. Record the source URL, retrieval date, filename, size, and SHA-256.
2. Run the audit with a fresh report path under an existing temporary root:

   ```text
   python <skill-dir>/scripts/audit_artifact.py <archive-or-directory> \
     --output <absolute-temporary-root>/artifact-audit.json \
     --output-root <absolute-temporary-root> \
     --max-files 10000 \
     --max-uncompressed-bytes 1073741824 \
     --max-ratio 200
   ```

   The script refuses an output outside that root or an existing report. The
   bundled non-extracting archive audit supports ZIP only.
   Keep or lower these explicit acquisition budgets; raising them requires a
   target-specific storage/memory review. A ZIP is blocked when it lacks a
   license candidate, exceeds entry/expanded-size/single-file/compression-ratio
   limits, contains unsafe/duplicate paths, symlinks, special or encrypted
   entries, executables/scripts, or Unity auto-compiled code such as `.cs`.
3. Require `kind: zip`, `verdict: pass`, `path_scan_passed: true`, and
   `safe_to_extract: true` before extracting an archive. Treat RAR, 7z, tar, tar.gz/tgz, gzip, bzip2, xz,
   invalid ZIP, and any renamed file whose magic resembles an unsupported
   archive as `BLOCKED`; do not pass it to a generic extractor. A plain single
   asset file or an already extracted directory is never an extraction grant.
4. Route a ZIP containing code or link-like entries to explicit manual security
   review; never auto-extract or auto-import it. Even a passing ZIP audit is a
   bounded structural gate, not a malware sandbox. Extract with a low-privilege
   process into a fresh temporary directory, keep auto-execution disabled, and
   reject contents that materially contradict the source page.
5. Extract an accepted ZIP into a dedicated temporary directory and inventory
   the actual formats and candidate license files.
6. For `.blend`, `.fbx`, `.glb`, or `.gltf` files, use the safe launcher when
   rig, mesh, material, image, or animation facts matter:

   ```text
   python <skill-dir>/scripts/run_blender_inventory.py \
     --blender <absolute-trusted-blender-executable> \
     --asset <absolute-acquired-asset> \
     --output <absolute-temporary-root>/blender-inventory.json \
     --output-root <absolute-temporary-root>
   ```

   `--blender` has no PATH-based default: it must name an existing absolute
   executable that the user or trusted machine policy selected. The launcher
   always places `--background --factory-startup
   --disable-autoexec --offline-mode --python-exit-code 1` before the inventory
   script and keeps the acquired file after Blender's `--` boundary. The
   inventory script independently rejects an untrusted `.blend` if those flags
   are missing, late, or a Blend file was already opened. Never invoke
   `blender_asset_inventory.py` directly for an acquired `.blend`. Both layers
   refuse to overwrite an existing report or escape the declared temporary root.
   These Blender flags reduce startup, script, and network exposure; they do not
   sandbox native parsers or prove a file benign. Run untrusted assets with low
   OS privileges, bounded time, and no access to valuable writable directories.
7. Import only the files needed for the selected requirement rows. Avoid copying redundant source formats, previews, unrelated variants, or an entire large pack by default.

The source page is declared evidence; the downloaded archive and imported files are audited evidence. Keep both and report discrepancies.

Marketing totals may combine free, paid, source, or add-on tiers. Count the actions, models, and variants in the exact acquired package before claiming coverage.

## Apply the Animation Gate

For animated 3D assets, verify the following before claiming production readiness:

- an actual armature exists and has a plausible bone hierarchy;
- actions contain pose-bone curves rather than only object transforms;
- the exact required animation verbs exist, including transitions where needed;
- clips are looping or one-shot as intended;
- frame rate and clip ranges are sane;
- root-motion and in-place variants are identified;
- humanoid or generic rig type is known;
- retarget compatibility is tested against the intended character, not inferred from marketing copy;
- scale, forward axis, foot sliding, hand contact, and prop alignment are checked in engine.

An animation library may be imported as `pending retarget validation`, but do not describe it as integrated with a character until a retarget test passes.

## Preserve Provenance

Use the acquisition and import record schemas in [references/asset-records.md](references/asset-records.md). Keep the original license text or a source snapshot when redistribution permits it. Record:

- original source and creator;
- license and attribution obligations;
- downloaded archive hash;
- files actually imported;
- local renames, conversions, material changes, or other modifications;
- unresolved compatibility risks.

Do not place credentials, purchase receipts, cookies, or personal account data in the project.

## Hand Off Engine Integration

When engine integration is requested, hand the audited candidate and import record to the target project's own engine workflow. That workflow must inspect the project architecture, place third-party files under the project's established asset structure, configure importer settings, create only useful derived objects, and validate inside the engine editor.

When an acquired 2D asset needs palette, alpha, size, pivot, frame-order,
timing, sheet, tileset, icon, UI, portrait, or background production work before
engine import, hand the audited source and provenance record to
`$create-2d-game-art`. Keep this Skill responsible for source and license
evidence and let the 2D production Skill own derivative artifacts and their
visual/technical receipt.

Do not destabilize a working character or scene merely to test a new rig. Prefer a duplicate prefab, isolated validation scene, or staged asset marked pending compatibility when a reversible test is available.

## Improve This Skill from Real Runs

After a real search or import pass, update this Skill only with generalizable findings: new evidence gates, reusable record fields, or repeatable audit steps. Keep project-specific asset choices and one-off URLs in the target project's provenance records, not in this Skill.

For a material Skill change, follow the repository's Skill maintenance rules, update discovery/catalog/workflow documentation when behavior changed, validate with the active `skill-creator` validator, run `git diff --check`, and inspect the diff.

## Handoff

Match user-facing explanations, prompts, and handoffs to the user's language unless the user requests another language. Keep commands, identifiers, structured keys/action codes, and raw errors unchanged.

In selection mode, provide the requirement matrix, search-coverage record, ranked comparison, recommendation, fallback, license obligations, and post-download checks. End with `Search only: no files downloaded or imported.`

In acquisition mode or an engine integration handoff, provide the selected requirements, downloaded archive hashes, audited contents, imported files, provenance locations, validation evidence, and remaining compatibility risks. Never claim that an asset was imported, animated, or retargeted without corresponding evidence.
