# Dreamweaver Evidence Case: Dream Traveler Retargeting

This is a dated project example, not a fixture or universal preset. Paths are relative to the Dreamweaver repository root. Re-read and re-hash current artifacts before reusing any claim.

## Contract and Provenance

The 2026-08-11 task integrated a reversible PS1/PS2-style full-body candidate into an isolated Unity Animation Lab without replacing the first-person player or declaring a canonical protagonist identity.

The user-provided `asian-girl-ps1ps2-character-mcpato.zip` was recorded as 3,778,700 bytes with SHA-256 `3770933dd89bba1d67d55eb11e85f666911e772547fc721da836f208c60df6ae`. Its seven files contained one FBX and six PNGs, no license file, no unsafe path, and no unexpected executable. Official creator records declared McPato's “Asian Girl PS1/PS2 Character” under CC BY 4.0; the project separately stored the official legal text, attribution, source URLs, redistribution obligations, and modification notice.

The character FBX and PNG bytes remained unchanged. Project-authored changes were the explicit Unity Humanoid mapping, URP materials, prefab, controller, validation scene, and external-animation integration. See:

- `Docs/Art/2026-08-11-dream-traveler-character.md`
- `Assets/ThirdParty/McPato/AsianGirlPS2/THIRD_PARTY_NOTICES.md`
- `Assets/ThirdParty/Quaternius/THIRD_PARTY_NOTICES.md`

## Audited Structures

- McPato FBX: FBX 7.4, 10 mesh objects, one 60-bone armature, six materials, zero actions.
- Character Avatar: explicit 52-slot Unity Humanoid mapping; eight twist bones retained in the skeleton but intentionally unmapped.
- UAL1 Standard: 65 bones and 43 clips at 30 fps; selected `Walk_Loop`, `PickUp_Table`, and `Jump_Loop`.
- Retained UAL2 proof: 17 actions total and `UAL2_Source_Rig` with 382 bones; a continuous 65-deform-bone hierarchy supplied the three selected actions `Walk_Carry_Loop`, `Melee_Combo`, and `OverhandThrow`.
- Original UAL2 source blend: not retained. The proof was saved at 24 fps while its historical generator assigned 30 fps. The delivery preserved the auditable 24 fps and explicitly did not claim official timing.

## Failures That Changed the Process

The obsolete failure artifacts in this section were not retained. Their measurements are recorded session evidence; the current repository retains the corrected derivative and regression gates, not those broken FBX/prefab revisions.

### Valid Avatar with collapsed legs

The first UAL2 derivative produced `Avatar.isValid && Avatar.isHuman`, yet Unity cached `calf_l` and `foot_l` near `0.00493 m` and `0.00505 m`; the correct order was about `0.40031 m` and `0.42948 m`. The old raw FBX combined `UnitScaleFactor=1` with Armature scale 100, and Unity reused a stale `HumanDescription.skeleton`.

The fix used Blender `FBX_SCALE_UNITS`, raw FBX `UnitScaleFactor=100`, and Armature scale `(1,1,1)`, then forced a Generic-to-Human skeleton refresh. A 17-segment UAL2-to-UAL1 ratio gate of `0.5–1.5` made the 1/100 failure observable. This established that Avatar validity must be combined with skeleton geometry checks.

### Animated pose captured as bind/rest

An earlier temporary export rig had three overlapping enabled NLA tracks and gathered the skeleton while animation was evaluated. Rest error reached roughly `0.922 m` even though names, curves, and root checks looked plausible.

The corrected exporter constructed a clean 65-bone rig, removed active action/NLA influence, gathered it in rest, and baked constrained motion hierarchically. It rejected non-root/pelvis translations and all scale curves, then compared source-to-bake and clean-FBX-round-trip poses.

### Root travel and source semantics

The source Walk Carry and Melee actions contained about `1.30 m` and `1.26 m` of horizontal travel; Overhand Throw did not. The project required controller-authoritative in-place playback, so the exporter proved that source travel was sampled before removing XZ motion from the whole evaluated pose. The output root XZ drift was zero and runtime `applyRootMotion` was false.

The Melee clip retained an authored pelvis lunge of about `0.62 m` relative to its source. Acceptance therefore used source-relative pelvis envelopes plus unchanged GameObject/Animator roots instead of a tight target-only hips bound.

### Serialized preview pose and obscured cameras

Edit-mode preview evaluation plus baked-mesh inspection serialized four finger Transform overrides into the prefab. The preview was restricted to Play mode, skeleton TRS was restored before save, and tests rejected nested model-bone TRS overrides. A manual visual iteration also caught backdrop geometry in the camera sight line; camera/backdrop placement was corrected and the retained captures supplied visual evidence. The automated lab validator checks camera count and wiring, not geometric occlusion.

### Black face, blurred features, and the wrong material order

The character looked correct in Blender but initially showed a half-black face and blurred facial detail in Unity. A Blender close-up and normal audit found symmetric left/right face normals, so recalculating normals would have been a destructive false fix. Earlier look-development choices also exposed three contributing risks: strong tints affected several body regions through shared atlases, face details lost readability through ordinary mip/compression settings, and alpha-cut hair or eyelash cards could promote low-alpha black RGB into opaque blockers.

The decisive defect was renderer mapping. Blender displayed the face object's slots as `U4`, `U1`, eyelashes, and hair, but Unity exposed the populated face submeshes in polygon-use order as `U1` skin, `U4` facial detail, then eyelashes; Unity stripped the unused fourth hair slot. Assigning project materials by the assumed Blender slot indices swapped the populated surfaces and produced the black face, a white block, and exaggerated mouth/teeth-like artifacts.

The fix bound materials to the inspected Unity renderer order, retained the original FBX and PNG bytes, and kept look-development changes in derived URP materials and texture importer settings. Soft hair and eyelash cards used double-sided alpha blending rather than cutout. Critical face textures received targeted detail-preserving import settings, not a project-wide uncompressed policy. Opaque materials paired numeric specular/reflection properties with Unity 6 local keywords. Texture-preserving weak emission used `RealtimeEmissive`; non-emissive materials used `EmissiveIsBlack`, because URP material postprocessing can recompute `_EMISSION` from global-illumination flags after save or reimport.

This established a required character gate: verify actual imported submesh/material order, shared texture consumers, alpha behavior, texture sampling, shader keywords, and persisted material state before accepting the rigged prefab. A Blender render, correct normals, a green Avatar, or correct setup code is insufficient.

## Final Derivative and Validation

The deterministic UAL2 derivative was 726,060 bytes with SHA-256 `dfc7c0ff7d73d144d208324aa22a3672bea017ce65dd2f8b957a6696bf99db97`. Its audited proof source hash was `f66c244138b5555f78f3b5fdf9cef8ed6f030df7cb706787e2bb27ceabe2856f`.

Blender gates covered the 65-bone hierarchy, rest matrices, all-frame pose fidelity, semantic channels, loop/root behavior, raw FBX units and scale, and clean round trip. The session recorded two matching export hashes; the repository retains the final hash and deterministic exporter, not two separate derivatives. Maximum sampled source-to-bake and round-trip head-position errors were about `1.38e-6 m` and `3.31e-6 m`. Maximum round-trip rest-head position error was about `1.269e-5 m`, and maximum rest-matrix element delta was about `1.746e-5`. Terminal display-tail differences were recorded but intentionally not gated because FBX does not preserve Blender's arbitrary terminal display length.

Unity gates covered exact 52-slot mappings, bilateral toes, retained unmapped leaf/twist bones, importer diagnostics, clip ranges/loops/root locks, segment ratios, audited face submesh/material order, persisted URP material and texture-import state, prefab/controller wiring, lab isolation, and forbidden bone overrides. All six states were sampled at normalized times `0`, `.25`, `.5`, `.75`, and `.95` for finite transforms, human-space envelopes, pose change, and unchanged GameObject/Animator roots. The three UAL2 states additionally checked a plausible support foot and both Foot–Toes chains; their initial grounding and pelvis envelopes were compared with the UAL2 source where applicable.

The integration did not include an independent post-import per-vertex weight-normalization audit. Skinning acceptance came from importer limits, multi-action deformation, human envelopes, baked-mesh bounds, and visual captures, so a future weight-editing task must add direct vertex-weight gates.

The final receipt recorded:

- focused EditMode: 6 passed, 0 failed;
- full EditMode: 17 passed, 0 failed;
- full PlayMode: 2 passed, 0 failed;
- 12 final front/side captures, one pair for each controller state, retained locally under `Temp/DreamTravelerQA_Final_dfc7/*-1.png`;
- final close-face material capture retained locally at `Temp/DreamTravelerURPFaceQA/final_urp_face_material_fix_1.png`;
- final Console: 0 errors and 0 warnings.

Implementation and evidence entrypoints:

- `ArtSource/Characters/DreamTraveler/Scripts/export_ual2_unity_inplace.py`
- `Assets/_Project/Prototype/Editor/DreamTravelerAssetPipeline.cs`
- `Assets/_Project/Prototype/Editor/DreamTravelerAnimationLabSceneBuilder.cs`
- `Assets/_Project/Prototype/Runtime/DreamTravelerAnimationPreview.cs`
- `Assets/_Project/Prototype/Tests/Editor/DreamTravelerRetargetingTests.cs`
- `Docs/Art/2026-08-11-dream-traveler-retargeting.md`

The `Temp/` captures and overwritten historical test XML are workstation evidence, not versioned checkout guarantees. The project document is the durable receipt for the focused 6/6, full EditMode 17/17, PlayMode 2/2, close-face material result, and Console results.

The result remained a reversible presentation candidate. First-person body visibility, canonical identity, prop-contact IK, secondary motion, and official UAL2 timing remained explicit design or source-acquisition questions.

## 2026-08-12 Animation Evidence Continuation

The next review exposed a different failure class: correct Animator and CPU
bone data did not guarantee that an Edit-mode off-screen render contained the
same pose. The first `v002` jump manifest recorded the intended `Jump_Start`,
`Jump_Loop`, and `Jump_Land` clips and matching semantic-bone samples, while
the PNGs still showed poses cached from the previously rendered action.
Independent direct-controller and override-controller sampling produced
identical bones, which excluded controller wiring as the cause.

Unity had not refreshed every `SkinnedMeshRenderer` skin matrix between
consecutive synchronous `Camera.Render()` calls after `Animator.Play` and
`Animator.Update(0)`. The capture-only fix set
`forceMatrixRecalculationPerRender = true` on all ten temporary skinned
renderers. It also used an exclusive capture layer in a temporary additive
scene, rejected any unrelated renderer on that layer, asserted the actual
active clip before every render, and recorded one capture ID, sample time,
semantic bones, root presentation, and PNG SHA-256. Cleanup restored the prior
active scene and left one clean Animation Lab scene loaded. The `v002` output
was explicitly marked rejected rather than silently replaced.

This established that Animator state, active clip, CPU pose, renderer skinning
cache, and final pixels require one synchronized evidence chain. Distinct image
hashes are useful for detecting repeated output but cannot establish that the
pixels depict the claimed pose. The Unity API above is a temporary capture
safeguard, not a production-renderer setting.

### Jump sequence and presentation root

The old six-state audition exposed only `Jump_Loop`, which is an airborne hold
rather than a complete jump. The corrected review sampled
`Jump_Start -> Jump_Loop -> Jump_Land` and treated their ordered seams as one
verb. The pose sheet accumulated a temporary vertical root presentation so
takeoff, airborne hold, descent, contact, and recovery remained visually
continuous. The production prefab still used `applyRootMotion = false`.

Consequently the pose sheet passed animation-review gates but did not validate
CharacterController gravity, collision, gameplay transition timing, or the
final jump trajectory. Those gates remained `not_tested`, and the overarching
receipt remained `prototype`.

### Faithful retargeting versus unsuitable performance

The original `OverhandThrow` looked wrong for the character, but direct
inspection of the locally provided official `UAL2.blend` proved the deep fold
was authored in the source. Its root stayed at zero while pelvis-to-head lean
reached about `59.78 degrees`; more than 40 degrees persisted for 20 frames.
The retained earlier proof and Unity import had also stretched the official
30 fps, frames 0-40 action to 24 fps, making the follow-through linger without
creating the pose.

The repair therefore became a named performance derivative rather than a
retargeting correction. `OverhandThrow_Soft` preserved the throw phases and
right-hand path while reducing pelvis translation, drop, and torso fold on a
reversible Blender copy. The 30 fps, 41-frame, 65-bone animation-only FBX had
zero root XZ drift. Blender measured peak pelvis-to-head lean at about
`23.83 degrees`, upper-torso lean at `16.74 degrees`, pelvis drop at `0.104 m`,
contact-foot slide at `0.041 m` left and `0.014 m` right, and a right-hand path
span of `1.339 m`.

The official source remained unchanged with SHA-256
`7412ee86c8b322f9aa94ea99eb7f91f150f91638f08035b2374ee1452ae09ba7`.
The editable derivative hash was
`1977ae4e62be94c02a36f0d46974166db4a9f1b7984b3919ba077f01361ebbc1`;
the FBX hash was
`f6d59a546e4a96a449e0062559bd49c299192ad8676ef163659f6c631741003c`.
Clean FBX round-trip comparison covered all 41 frames.

Unity imported the derivative as a valid Human Avatar with the same explicit
52-slot mapping and measured peak target torso lean at `18.948 degrees`, right
hand `0.256 m` above the head at the apex, `0.519 m` forward reach at release,
`0.005 m` closing hand error, and zero Animator-root drift. The focused
EditMode suite passed 8/8. The final capture manifest bound 36 PNG samples to
the expected active clips and current hashes without leaking or dirtying a
temporary scene. It did not bind the capture script revision or exact menu
invocation, so the set remained a prototype review candidate rather than
independently reproducible validation.

Durable continuation evidence:

- `ArtSource/Characters/DreamTraveler/Animations/OverhandThrowSoft_v001/`
- `Assets/_Project/Art/Characters/DreamTraveler/Animations/UAL2_OverhandThrowSoft.fbx`
- `ArtSource/Characters/DreamTraveler/Renders/SkeletalAnimationFrames_v002/REJECTED.md`
- `ArtSource/Characters/DreamTraveler/Renders/SkeletalAnimationFrames_v003/capture-manifest.json`
- `ArtSource/Characters/DreamTraveler/Receipts/SkeletalAnimationFrames_v003/auto-ta-receipt.json`
- `Assets/_Project/Prototype/Editor/DreamTravelerAnimationFrameCapture.cs`
- `Assets/_Project/Prototype/Tests/Editor/DreamTravelerRetargetingTests.cs`

The remaining limitations were deliberate: the images were pose/contact
sheets rather than full-speed playback evidence, and no held prop, release
event, projectile trajectory, hand IK, or gameplay jump controller was
implemented in this correction pass.
