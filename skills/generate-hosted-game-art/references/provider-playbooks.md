# Provider playbooks

Field-tested notes from real runs (2026-08-21, a Godot J-horror art pass).
Costs are observed anchors, not guaranteed prices — re-verify against the
account when they matter.

## Meshy

### Observed credit costs

| Operation | Credits |
| --- | --- |
| text-to-3d preview | 20 |
| text-to-3d refine (PBR texture) | 10 |
| remesh | 5 |
| rigging | 5 |
| animation (per clip) | 3 |

A textured prop ends at 30; a rigged, animated character at ~43 per successful
chain (failed attempts still bill their completed steps).

### Prop chain

`text-to-3d preview → refine(enable_pbr) → download`. Refine outputs are
extremely dense (~2M faces regardless of `target_polycount`); treat the raw
GLB as source material, not a delivery — see "Downstream optimization".

### Character chain (model + rig + animation)

`preview → refine → remesh → rigging → animations`, all task-id-chained:

1. **Preview prompt**: "T-pose"/"A-pose"/"full body" wording is often ignored.
   The reliable fix is `negative_prompt`: exclude
   `pedestal, base, bust, half body, crossed arms, sitting, props`.
   A bust-on-a-pedestal output fails rigging with "Pose estimation failed".
2. **Rigging does not require a T-pose** — its pose estimation handles a
   natural standing full body with legs visible and feet on the ground.
3. **Remesh is mandatory before rigging**: rigging rejects inputs over
   320,000 faces, and refine outputs ~2M. Remesh to ≤60k for game NPCs.
   The rigging error message cites `POST /openapi/v2/remesh`; that route does
   not exist — only `/openapi/v1/remesh` works.
4. **Wait for the remesh task to report SUCCEEDED** before submitting rigging;
   an in-progress input yields 404 "Original task preview file not found".
5. **Animations**: `rig_task_id` + integer `action_id`; 0 = Idle; IDs range
   [0, 696] per the [animation library](https://docs.meshy.ai/en/api/animation-library).
   The delivery (`Animation_*_withSkin.glb`) embeds the clip with a name like
   `Armature|Idle|baselayer` — engines import the clip under exactly that
   name; wire the game's animation lookup to it verbatim.

### Sizing the delivery

Read the character's real size from the **GLB accessor min/max (bind pose,
Y-up)**, not from a DCC scene's world bounding box — an imported animated
scene reports frame-evaluated bounds that can be badly inflated. Meshy
character deliveries arrive normalized to human height (~1.7 m, feet at y=0),
so an engine scale of 1.0 is usually correct.

### Raw downloads and repository hygiene

A finished task download includes redundant formats (`obj` up to ~195 MB,
`stl`/`usdz`/`fbx` 60–95 MB each). GitHub hard-rejects files over 100 MB.
Keep in version control only the generation receipt + preview image; the
engine delivery is the optimized GLB inside the game project. Ignore the rest
(`generated-assets/**/model.*`, `generated-assets/**/texture_*` pattern).

### Downstream optimization (the Blender adjustment layer)

Raw refine GLBs (~75 MB, ~2M tris) shrink to ~2.4 MB with no visible loss at
game scale:

- Decimate modifier to a total triangle budget (60k for hero props/NPCs),
  applied per mesh object with a global ratio;
- scale all images to ≤1024;
- re-export GLB with JPEG textures (quality ~90).

Run headless with the standard isolation flags. This is the concrete form of
"hosted generation first, Blender as the downstream adjustment layer".

### API discovery pattern

Free schema discovery without billing: POST an empty JSON body to a submit
endpoint — the validation error lists required fields (Go-style names map to
snake_case JSON). Malformed or sentinel ids on GET/status routes are also
free. Beware: a GET status call with a malformed task id can fall through to
the list route and return a JSON array instead of an object.

## Tencent Cloud (Hunyuan)

- The credential pair (`SecretId`/`SecretKey`) drives the TC3-signed cloud
  API — a different product surface from TokenHub Bearer keys.
- Settlement order: free resource pack → prepaid pack → pay-as-you-go
  (off by default). Zero cash balance with no claimed pack means every
  generation call fails until the user claims the free pack in the console;
  that console step belongs to the user.
- Service reachability classifies by error code from sentinel-id job queries.
  ai3d wraps the real code inside `FailedOperation.InnerError`'s message
  (e.g. "FailedOperation.JobNotFound 未定义") — unwrap the message before
  classifying, as the bundled client does.
- Observed anchor: one successful Hunyuan 3D task ≈ 20 points.

## Sourcing counterpart

Programmatic CC0 texture/model acquisition from Poly Haven pairs well with
hosted generation for environment surfaces; see
`search-game-art/references/source-apis.md` for the API pattern.
