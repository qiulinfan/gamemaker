# 2D Art Production Receipt

Store this UTF-8 YAML or JSON record beside the target project's delivered art
or in its established provenance system. The schema is closed: fields not shown
below are rejected. Paths use `/` and are relative to one declared provenance
root; they are never machine-local absolute paths.

```yaml
schema_version: 1
job:
  id: orb-idle-v1
  status: validated # validated|prototype|blocked|failed
  contract_path: contracts/orb-idle.yaml
sources:
  - path: source/orb-idle-0.png
    role: user_authored # user_authored|generated_source|licensed_source|working_frame
    sha256: 0000000000000000000000000000000000000000000000000000000000000000
    creator: Example Artist
    source_url: ""
    license: user-owned
    generation_provenance: ""
outputs:
  - path: generated/orb-idle.png
    role: engine_delivery # editable_source|engine_delivery|frame_manifest|preview|audit
    sha256: 0000000000000000000000000000000000000000000000000000000000000000
implementation:
  tool: create-2d-game-art.sprite-pipeline
  version: 1.0.0
  command_or_action: uv run sprite_pipeline.py build ...
  processing_contract: {}
evidence:
  artifact:
    - id: structural-audit
      path: generated/orb-idle-audit.json
      sha256: 0000000000000000000000000000000000000000000000000000000000000000
      description: Independent audit of the encoded delivery and manifest
  visual_native_scale: []
  visual_gameplay_scale: []
  animation: []
  tileset_or_ui: []
  engine_import:
    - id: unity-import
      path: evidence/unity-import.json
      sha256: 0000000000000000000000000000000000000000000000000000000000000000
      description: Import and runtime evidence from the authorized project
      engine_delivery_path: generated/orb-idle.png
      engine_delivery_sha256: 0000000000000000000000000000000000000000000000000000000000000000
      project_revision: 0123456789abcdef
gates:
  - id: artifact.structural
    required: true
    result: pass # pass|fail|not_tested|not_applicable
    evidence: [artifact:structural-audit]
    reason: ""
modifications: []
limitations: []
next_owner: gamemaker-programmer
next_action: Integrate the hash-bound delivery
```

## Closed Shapes

Every source, output, evidence item, and gate contains exactly the keys shown.
All six evidence domains are required even when their arrays are empty. A
non-engine evidence item has exactly `id`, `path`, `sha256`, and `description`.
An `engine_import` item additionally has exactly `engine_delivery_path`,
`engine_delivery_sha256`, and `project_revision`.

Gate evidence entries are references in the exact form `<domain>:<id>`, such as
`visual_native_scale:checkerboard`. Referenced evidence must exist. Gate IDs and
evidence IDs are case-insensitively unique in their respective scopes.

## Artifact and Path Rules

- Declare exactly one output for each of `engine_delivery`, `frame_manifest`,
  and `audit`. Optional `editable_source` and `preview` outputs may be added.
- Hash every declared source, output, and evidence file with lowercase SHA-256.
  The validator resolves each path beneath the provenance root, rejects path
  escape including symlink escape, reads the file, and verifies its hash.
- Use normalized, non-empty POSIX relative paths. Absolute POSIX paths, Windows
  drive or UNC paths, backslashes, empty segments, `.` segments, and `..`
  segments are invalid. Paths that differ only by Unicode normalization or case
  cannot identify two sources or two outputs.
- Bind each engine import record to the exact `engine_delivery` path and hash,
  and name an immutable imported project revision rather than only a branch.
- Keep every source distinct from every output by portable path and resolved
  filesystem identity, including case/Unicode aliases, symlinks, and hard
  links. Evidence may intentionally reference an already declared output.
- The required `audit` output is not an opaque attachment. The validator reads
  the closed sprite-pipeline audit JSON, requires its schema, trusted tool,
  `operation: audit`, the complete bound-manifest-specific check inventory,
  unique passing checks, derived `verdict: pass`, and
  binds `artifact.manifest_sha256` and `artifact.png_sha256` to the receipt's
  exact `frame_manifest` and `engine_delivery` outputs. Hashing and semantic
  parsing use the same bounded audit and manifest byte snapshots.
- Keep credentials, private prompts, cookies, purchase receipts, and personal
  paths out of the receipt.

## Gate and Status Reduction

Each gate always declares `required`, `result`, `evidence`, and `reason`.

- `pass` and `fail` require at least one valid evidence reference.
- `not_tested` and `not_applicable` require a non-empty reason.
- A required gate cannot be `not_applicable`. A required `not_tested` gate is
  permitted in a truthful `prototype` or `blocked` receipt.
- Any `fail`, required or optional, reduces the receipt to `failed`.
- A required `not_tested` gate whose ID begins `blocker.` records an unavailable
  required source, authority, tool, license, or target and reduces the receipt
  to `blocked` when no gate failed.
- `validated` requires every required gate to be `pass`, at least one valid
  `engine_import` evidence item, and at least one required passing `engine.*`
  gate that cites that engine evidence.
- Every other non-failed, non-blocked receipt reduces to `prototype`. Thus a
  structurally and visually approved delivery without engine evidence remains
  a prototype ready for engine import.

The declared `job.status` must exactly equal this reduction. The phrase
`prototype_ready_for_engine_import` may appear in prose or `next_action`, but it
is not a legal status.

## Run the Validator

The validator accepts YAML and JSON (JSON is a YAML subset), rejects duplicate
mapping keys, unknown fields, missing fields, invalid types, and multi-document
input, and verifies referenced files:

```sh
uv run <skill-dir>/scripts/validate_receipt.py \
  path/to/receipt.yaml --provenance-root path/to/provenance-root
```

Omit `--provenance-root` when paths are relative to the receipt directory. Exit
`0` means the declared receipt is structurally valid, hash-bound, and honest;
it does not upgrade a truthful `prototype`, `blocked`, or `failed` asset. Exit
`2` reports schema or evidence problems. Exit `3` reports an operational or
invocation error. Any artifact edit invalidates its hash and all downstream
evidence until those records are regenerated.
