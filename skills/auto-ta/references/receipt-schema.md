# Auto TA receipt

Write valid UTF-8 JSON. Paths should be absolute in an execution receipt and may be normalized only when the surrounding project requires portability.

```json
{
  "schema_version": "1.0",
  "status": "validated",
  "asset_contract": {
    "path": "C:/absolute/path/asset-contract.json",
    "sha256": "..."
  },
  "started_at": "2026-01-01T00:00:00Z",
  "finished_at": "2026-01-01T00:03:00Z",
  "assumptions": [],
  "inputs": [
    {"path": "C:/absolute/source.blend", "sha256": "...", "license": "user-owned"}
  ],
  "outputs": [
    {"path": "C:/absolute/asset.glb", "sha256": "...", "role": "engine_delivery"}
  ],
  "runtime": [
    {"name": "Blender", "version": "5.1.2", "mode": "background"}
  ],
  "actions": [
    {"surface": "Blender", "summary": "Generated source asset", "evidence": "C:/absolute/build.log"}
  ],
  "gates": [
    {"id": "geometry.dimensions", "required": true, "verdict": "pass", "evidence_status": "current", "evidence": {"actual_m": [2, 2, 2]}},
    {"id": "visual.silhouette", "required": true, "verdict": "pass", "evidence_status": "current", "evidence": {"images": ["C:/absolute/front.png"]}},
    {"id": "engine.roundtrip", "required": false, "verdict": "not_tested", "evidence_status": "pending", "reason": "No authorized project"}
  ],
  "round_trip": {
    "format": "glb",
    "import_surface": "clean Blender scene",
    "verdict": "pass",
    "evidence": "C:/absolute/roundtrip.json",
    "sha256": "..."
  },
  "limitations": [],
  "next_step": "Import the validated GLB into the authorized Unity project"
}
```

Allowed top-level `status` values are `validated`, `prototype`, `blocked`, and `failed`. Allowed gate `verdict` values are `pass`, `fail`, and `not_tested`. Every gate must also declare `evidence_status` as `current`, `pending`, `stale`, or `rejected`.

A `pass` or `fail` gate must use `evidence_status: current`; a tested failure may retain a `reason`, while a passing gate must express qualification in its evidence rather than carry a contradictory pending reason. A `not_tested` gate must use `pending`, `stale`, or `rejected` and state a non-empty `reason`. Keep known-bad or superseded artifacts outside active passing evidence and label them explicitly as rejected or historical failure evidence.

Any change to code, assets, import/controller configuration, capture implementation, or runtime state that can affect a gate expires its prior evidence. Change its verdict to `not_tested` with `evidence_status: stale` or `pending` until fresh, hash-bound evidence is captured. Likewise, an inspected runtime or visual failure invalidates a conflicting lower-strength pass even when the receipt validator had previously accepted its structure.

The top-level status is `validated` only when every gate with `required: true` is `pass`, all output files exist and match their hashes, and `round_trip.verdict` is `pass` with matching evidence SHA-256. A required or round-trip `fail` makes the result `failed`. A `not_tested` required gate or round trip makes the result `prototype` or `blocked` and must state a reason.

A tested round trip must have exactly one hash-verified `outputs` entry with role `editable_source` and exactly one with role `engine_delivery` or `*_engine_delivery`. The former must match the source audit's `.blend` path/hash; the latter must match the comparison delivery and clean-import input. A tested `artifact.*` gate must include an `evidence.artifacts` list whose path, SHA-256, and role match the corresponding receipt outputs.

Run `<skill-dir>/scripts/validate_receipt.py` before handoff. For a receipt that claims `validated`, pass `--blender-bin <trusted-absolute-Blender-executable>`; omission, either fresh audit replay timing out, or either replay differing from stored evidence fails closed. The command parses the hashed contract and comparator JSON; validates enums, timezone-aware timestamps, absolute artifact paths, output hashes and roles, gate/evidence-status consistency, required gate evidence, minimum validated-domain coverage, source/import roles and run ids, audit schema/verdict/current implementation identity, the exact comparison check set and verdict reduction, the audited-source and delivery-to-import hash chains, and status reduction. It independently recomputes the comparison in memory from the hash-verified source audit, imported audit, and delivery with the current trusted comparator. Its own `validation_verdict: pass` means the receipt is honest and internally evidenced; it does not mean a receipt whose top-level status is `failed`, `prototype`, or `blocked` became a validated asset or that an unrecorded later observation cannot invalidate its evidence.
