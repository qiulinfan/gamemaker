# Asset Records

Use these compact records to keep design intent, web claims, downloaded evidence, and engine results separate. Store project-specific records in the target game repository when acquisition or import occurs.

## Demand Record

```yaml
asset_role: quest_giver_semantic_animation
source_refs: []
priority: vertical_slice
gameplay_function: communicate or execute a rule-authorized action
theme_role: friendly authority expressed through controlled gestures
visual_requirements: low-poly humanoid motion readable at conversational distance
functional_requirements:
  animation_verbs: [sit_down, seated_idle, stand_up, point, push]
technical_requirements:
  engine: Unity
  rig: humanoid_or_verified_retargetable
  preferred_formats: [fbx, glb]
license_requirements: commercial_use_and_modification_allowed
assumptions: []
open_questions: []
```

## Search Coverage Record

```yaml
asset_role: stylized_humanoid_character_candidate
searched_at: ""
query_families:
  - role_plus_silhouette_plus_emotional_valence
  - reference_traits_without_literal_costume_motifs
  - rigged_downloadable_plus_license
source_classes:
  sketchfab:
    status: searched
    queries: []
    notable_creators_or_collections: []
  itch_and_creator_stores:
    status: searched
    queries: []
  engine_marketplaces:
    status: searched
    queries: []
  paid_editable_sources:
    status: not_needed
    reason: ""
coverage_gaps: []
plateau_action: broadened_traits_and_creator_tags
```

Use `searched`, `not_relevant`, `blocked`, or `not_needed` for source-class status and explain every value other than `searched`. This is a coverage receipt, not a claim that a dynamic catalog was exhausted.

## Candidate Record

```yaml
asset_name: ""
creator: ""
source_url: ""
source_kind: official_creator_page
version_or_date: ""
price: free
license:
  name: ""
  url: ""
  attribution: ""
  commercial_use: unknown
  modification: unknown
  redistribution: unknown
declared_contents:
  formats: []
  editable_sources: []
  rig: unknown
  animation_verbs: []
  bundled_animation_count: unknown
  root_motion: unknown
  engine_support: []
fit:
  visual: ""
  theme: ""
  functional: ""
  technical: ""
  license: ""
  source_editability: ""
  adaptation_cost: ""
external_retarget_path:
  animation_source: ""
  required_verbs_covered: []
  actual_pair_test: not_tested
unverified_after_download: []
```

## Acquisition Record

```yaml
retrieved_at: ""
source_url: ""
archive_filename: ""
archive_size_bytes: 0
sha256: ""
audit_report: ""
license_files: []
actual_formats: []
unexpected_contents: []
selected_subset: []
rejected_files: []
```

## Unity Import Record

```yaml
project: ""
unity_version: ""
destination: ""
imported_files: []
created_assets: []
import_settings:
  scale: ""
  rig: ""
  materials: ""
  textures: ""
modifications: []
validation:
  editor_import: pending
  console_errors: unknown
  prefab_or_scene: pending
  animation_retarget: not_applicable
  visual_evidence: ""
remaining_risks: []
```

For animation libraries, set `animation_retarget` to `passed`, `failed`, or `pending`; never infer it from compatible-format claims.
