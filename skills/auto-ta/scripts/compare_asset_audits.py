"""Compare Auto TA source and exchange-import audit reports.

This script uses only the Python standard library. It deliberately compares
export-facing semantics rather than raw vertex counts, because glTF and FBX
commonly split vertices at UV, normal, and material seams.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "2.0"


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(f"argument error: {message}")


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Compare two blender_asset_audit.py reports")
    parser.add_argument("--source", required=True)
    parser.add_argument("--imported", required=True)
    parser.add_argument("--delivery", required=True, help="The GLB, glTF, or FBX that was cleanly imported")
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--tolerance-m",
        type=float,
        default=0.001,
        help="Absolute tolerance for meter-valued scene and per-mesh bounds; semantic digests remain strict",
    )
    parser.add_argument("--allow-audit-warnings", action="store_true")
    parser.add_argument(
        "--allow-uv-reparameterization",
        action="store_true",
        help="Allow UV coordinates to change when the asset contract does not require texture-coordinate preservation",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    if value.get("schema_version") != "2.0":
        raise ValueError(f"Expected blender audit schema 2.0: {path}")
    return value


def _authorized_output(args) -> Path:
    root = Path(args.output_root).resolve()
    output = Path(args.output).resolve()
    try:
        common = Path(os.path.commonpath([str(root), str(output)]))
    except ValueError as error:
        raise ValueError("--output and --output-root must be on the same filesystem") from error
    if common != root:
        raise ValueError(f"Report path escapes authorized output root: {output}")
    if output.exists() and not args.force:
        raise FileExistsError(f"Report already exists; pass --force to replace it: {output}")
    if output.exists() and output.is_dir():
        raise IsADirectoryError(output)
    return output


def _atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _mesh_names(report: dict) -> list[str]:
    return sorted(item["name"] for item in report.get("objects", []) if item.get("type") == "MESH")


def _material_names(report: dict) -> list[str]:
    return sorted(item["name"] for item in report.get("materials", []))


def _material_semantic_signature(report: dict) -> list[dict]:
    return sorted(
        [
            {
                "name": item.get("name"),
                "semantics": item.get("semantics"),
                "semantic_digest": item.get("semantic_digest"),
            }
            for item in report.get("materials", [])
        ],
        key=lambda item: item["name"] or "",
    )


def _rounded_numbers(values, digits: int = 6):
    return [round(float(value), digits) for value in values] if values is not None else None


def _scene_bounds_m(report: dict) -> dict | None:
    bounds = report.get("scene", {}).get("evaluated_mesh_bounds") or {}
    meters = bounds.get("meters") or {}
    if not meters:
        return None
    return {
        key: _rounded_numbers(meters.get(key))
        for key in ("min", "max", "dimensions")
    }


def _within_numeric_tolerance(source, imported, tolerance: float) -> bool:
    if isinstance(source, bool) or isinstance(imported, bool):
        return source is imported
    if isinstance(source, (int, float)) and isinstance(imported, (int, float)):
        return abs(float(source) - float(imported)) <= tolerance
    if isinstance(source, dict) and isinstance(imported, dict):
        return source.keys() == imported.keys() and all(
            _within_numeric_tolerance(source[key], imported[key], tolerance)
            for key in source
        )
    if isinstance(source, (list, tuple)) and isinstance(imported, (list, tuple)):
        return len(source) == len(imported) and all(
            _within_numeric_tolerance(left, right, tolerance)
            for left, right in zip(source, imported)
        )
    return source == imported


def _export_objects(report: dict) -> dict[str, dict]:
    return {
        item["name"]: item
        for item in report.get("objects", [])
        if item.get("type") in {"MESH", "ARMATURE"}
    }


def _hierarchy_signature(report: dict) -> list[dict]:
    return sorted(
        [
            {"name": item["name"], "type": item.get("type"), "parent": item.get("parent")}
            for item in _export_objects(report).values()
        ],
        key=lambda item: item["name"],
    )


def _transform_signature(report: dict) -> list[dict]:
    return sorted(
        [
            {
                "name": item["name"],
                "location": _rounded_numbers(item.get("location")),
                "rotation_euler": _rounded_numbers(item.get("rotation_euler")),
                "scale": _rounded_numbers(item.get("scale")),
                "matrix_world": _rounded_numbers(item.get("matrix_world")),
                "world_origin_m": _rounded_numbers(item.get("world_origin_m")),
            }
            for item in _export_objects(report).values()
        ],
        key=lambda item: item["name"],
    )


def _mesh_semantic_signature(report: dict, *, include_uv_digest: bool) -> list[dict]:
    result = []
    for name, item in _export_objects(report).items():
        mesh = item.get("mesh")
        if not mesh:
            continue
        topology = mesh.get("evaluated_position_welded_topology") or {}
        digests = mesh.get("evaluated_semantic_digests") or {}
        weights = mesh.get("weights") or {}
        bounds = (mesh.get("evaluated_world_bounds") or {}).get("meters") or {}
        result.append(
            {
                "name": name,
                "bounds_m": {
                    key: _rounded_numbers(bounds.get(key))
                    for key in ("min", "max", "dimensions")
                },
                "welded_topology": {
                    key: topology.get(key)
                    for key in (
                        "vertices",
                        "triangles",
                        "boundary_edges",
                        "non_manifold_edges_excluding_boundaries",
                        "loose_edges",
                        "loose_vertices",
                        "degenerate_faces",
                        "connected_face_components",
                        "closed_components",
                        "open_components",
                        "outward_closed_components",
                        "inward_closed_components",
                        "indeterminate_closed_components",
                        "winding_conflict_edges",
                    )
                },
                "surface_triangle_digest": digests.get("surface_triangle_digest"),
                "uv_triangle_digest": (
                    digests.get("uv_triangle_digest") if include_uv_digest else "not_compared_by_contract"
                ),
                "material_triangle_digest": digests.get("material_triangle_digest"),
                "weight_digest": weights.get("canonical_position_weight_digest"),
            }
        )
    return sorted(result, key=lambda item: item["name"])


def _split_mesh_bounds(signature: list[dict]) -> tuple[list[dict], list[dict]]:
    bounds = []
    semantics = []
    for item in signature:
        bounds.append({"name": item["name"], "bounds_m": item.get("bounds_m")})
        semantics.append({key: value for key, value in item.items() if key != "bounds_m"})
    return bounds, semantics


def _armature_signature(report: dict) -> list[dict]:
    result = []
    for object_name, item in _export_objects(report).items():
        armature = item.get("armature")
        if not armature:
            continue
        bones = []
        for bone in armature.get("bone_data", []):
            bones.append(
                {
                    "name": bone.get("name"),
                    "parent": bone.get("parent"),
                    "use_deform": bone.get("use_deform"),
                    "head_local": _rounded_numbers(bone.get("head_local")),
                    "matrix_local": _rounded_numbers(bone.get("matrix_local")),
                }
            )
        result.append(
            {
                "object": object_name,
                "root_bones": sorted(armature.get("root_bones", [])),
                "bones": sorted(bones, key=lambda bone: bone["name"] or ""),
            }
        )
    return sorted(result, key=lambda item: item["object"])


def _clip_signature(report: dict) -> list[dict]:
    result = []
    for action in report.get("actions", []):
        if not action.get("valid_bound_clip"):
            continue
        bindings = sorted(
            {
                (binding.get("owner_type"), binding.get("owner"))
                for binding in action.get("bindings", [])
            }
        )
        result.append(
            {
                "name": action.get("name"),
                "frame_range": _rounded_numbers(action.get("frame_range")),
                "bound_owners": bindings,
            }
        )
    return sorted(result, key=lambda item: item["name"] or "")


def _animation_sample_signature(report: dict):
    loop = report.get("animation_loop")
    if loop is None:
        return None
    return {
        "frames": _rounded_numbers(loop.get("frames")),
        "start_end_match": loop.get("start_end_match"),
        "middle_differs": loop.get("middle_differs"),
    }


def _animation_motion_comparison(source: dict, imported: dict) -> tuple[bool, dict, dict]:
    source_loop = source.get("animation_loop")
    imported_loop = imported.get("animation_loop")
    if source_loop is None or imported_loop is None:
        passed = source_loop is None and imported_loop is None
        return passed, {"present": source_loop is not None}, {"present": imported_loop is not None}
    source_vectors = source_loop.get("motion_delta_vectors") or {}
    imported_vectors = imported_loop.get("motion_delta_vectors") or {}
    tolerance = max(
        float(source.get("requirements", {}).get("animation_tolerance") or 0.0),
        float(imported.get("requirements", {}).get("animation_tolerance") or 0.0),
        1e-6,
    )
    summaries = []
    passed = True
    for key in ("start_to_middle", "start_to_end"):
        source_values = source_vectors.get(key)
        imported_values = imported_vectors.get(key)
        comparable = (
            isinstance(source_values, list)
            and isinstance(imported_values, list)
            and len(source_values) == len(imported_values)
        )
        maximum_delta = (
            max((abs(float(a) - float(b)) for a, b in zip(source_values, imported_values)), default=0.0)
            if comparable
            else None
        )
        item_passed = comparable and maximum_delta <= tolerance
        passed = passed and item_passed
        summaries.append(
            {
                "motion": key,
                "source_values": len(source_values) if isinstance(source_values, list) else None,
                "imported_values": len(imported_values) if isinstance(imported_values, list) else None,
                "max_abs_delta": maximum_delta,
                "tolerance": tolerance,
                "verdict": "pass" if item_passed else "fail",
            }
        )
    return passed, {"comparisons": summaries}, {"comparisons": summaries}


def _normalized_path(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return os.path.normcase(str(Path(value).resolve()))


def _isolation_signature(report: dict) -> dict:
    runtime = report.get("runtime") or {}
    return {
        "background": runtime.get("background"),
        "disable_autoexec_flag": runtime.get("disable_autoexec_flag"),
        "offline_mode_flag": runtime.get("offline_mode_flag"),
        "python_exit_code_flag": runtime.get("python_exit_code_flag"),
    }


def _audit_implementation(report: dict):
    implementation = (report.get("runtime") or {}).get("audit_script")
    if not isinstance(implementation, dict):
        return None
    return {
        "path": implementation.get("path"),
        "sha256": implementation.get("sha256"),
    }


def _parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _check(checks: list[dict], identifier: str, passed: bool, source, imported) -> None:
    checks.append(
        {
            "id": identifier,
            "verdict": "pass" if passed else "fail",
            "source": source,
            "imported": imported,
        }
    )


def _valid_audit_verdict(value: str, allow_warnings: bool) -> bool:
    return value == "pass" or (allow_warnings and value == "pass_with_warnings")


def compare(
    source: dict,
    imported: dict,
    tolerance_m: float,
    allow_warnings: bool,
    allow_uv_reparameterization: bool,
    provenance: dict,
) -> dict:
    checks: list[dict] = []
    _check(
        checks,
        "audit.source_verdict",
        _valid_audit_verdict(source.get("audit_verdict"), allow_warnings),
        source.get("audit_verdict"),
        None,
    )
    _check(
        checks,
        "audit.imported_verdict",
        _valid_audit_verdict(imported.get("audit_verdict"), allow_warnings),
        None,
        imported.get("audit_verdict"),
    )
    _check(
        checks,
        "provenance.report_files_distinct",
        provenance["source_report"]["path"] != provenance["imported_report"]["path"]
        and provenance["source_report"]["sha256"] != provenance["imported_report"]["sha256"],
        provenance["source_report"],
        provenance["imported_report"],
    )
    _check(
        checks,
        "provenance.run_ids_distinct",
        isinstance(source.get("run_id"), str)
        and isinstance(imported.get("run_id"), str)
        and source.get("run_id") != imported.get("run_id"),
        source.get("run_id"),
        imported.get("run_id"),
    )
    _check(
        checks,
        "provenance.report_roles",
        source.get("source", {}).get("mode") == "open_blend"
        and imported.get("source", {}).get("mode") == "clean_exchange_import",
        source.get("source", {}).get("mode"),
        imported.get("source", {}).get("mode"),
    )
    _check(
        checks,
        "provenance.source_is_blend",
        str(source.get("source", {}).get("path", "")).lower().endswith(".blend"),
        source.get("source", {}).get("path"),
        None,
    )
    imported_source = imported.get("source", {})
    imported_format = (imported_source.get("import") or {}).get("format")
    delivery_suffix = Path(provenance["delivery"]["path"]).suffix.lower().removeprefix(".")
    _check(
        checks,
        "provenance.delivery_import",
        _normalized_path(imported_source.get("path")) == provenance["delivery"]["normalized_path"]
        and imported_source.get("sha256") == provenance["delivery"]["sha256"]
        and imported_format == delivery_suffix
        and (imported_source.get("import") or {}).get("operator_result") == ["FINISHED"],
        provenance["delivery"],
        {
            "path": imported_source.get("path"),
            "sha256": imported_source.get("sha256"),
            "format": imported_format,
            "operator_result": (imported_source.get("import") or {}).get("operator_result"),
        },
    )
    source_isolation = _isolation_signature(source)
    imported_isolation = _isolation_signature(imported)
    _check(
        checks,
        "provenance.isolated_invocations",
        all(value is True for value in source_isolation.values())
        and all(value is True for value in imported_isolation.values()),
        source_isolation,
        imported_isolation,
    )
    source_implementation = _audit_implementation(source)
    imported_implementation = _audit_implementation(imported)
    _check(
        checks,
        "provenance.audit_implementation",
        source_implementation is not None
        and imported_implementation is not None
        and source_implementation.get("sha256") == imported_implementation.get("sha256")
        and isinstance(source_implementation.get("sha256"), str),
        source_implementation,
        imported_implementation,
    )
    source_generated = _parse_timestamp(source.get("generated_at"))
    imported_started = _parse_timestamp(imported_source.get("started_at"))
    _check(
        checks,
        "provenance.run_order",
        source_generated is not None
        and imported_started is not None
        and source_generated <= imported_started,
        source.get("generated_at"),
        imported_source.get("started_at"),
    )

    comparisons = (
        ("scope.mesh_names", _mesh_names),
        ("materials.names", _material_names),
        ("materials.principled_semantics", _material_semantic_signature),
        ("objects.hierarchy", _hierarchy_signature),
        ("objects.transforms_and_pivots", _transform_signature),
        ("rig.rest_hierarchy", _armature_signature),
        ("animation.clips", _clip_signature),
        ("animation.sample_contract", _animation_sample_signature),
    )
    for identifier, extractor in comparisons:
        source_value = extractor(source)
        imported_value = extractor(imported)
        _check(checks, identifier, source_value == imported_value, source_value, imported_value)
    source_scene_bounds = _scene_bounds_m(source)
    imported_scene_bounds = _scene_bounds_m(imported)
    _check(
        checks,
        "geometry.scene_bounds_m",
        _within_numeric_tolerance(source_scene_bounds, imported_scene_bounds, tolerance_m),
        source_scene_bounds,
        imported_scene_bounds,
    )
    source_mesh_semantics = _mesh_semantic_signature(
        source,
        include_uv_digest=not allow_uv_reparameterization,
    )
    imported_mesh_semantics = _mesh_semantic_signature(
        imported,
        include_uv_digest=not allow_uv_reparameterization,
    )
    source_mesh_bounds, source_mesh_semantics = _split_mesh_bounds(source_mesh_semantics)
    imported_mesh_bounds, imported_mesh_semantics = _split_mesh_bounds(imported_mesh_semantics)
    _check(
        checks,
        "geometry.mesh_bounds_m",
        _within_numeric_tolerance(source_mesh_bounds, imported_mesh_bounds, tolerance_m),
        source_mesh_bounds,
        imported_mesh_bounds,
    )
    _check(
        checks,
        "geometry.mesh_semantics",
        source_mesh_semantics == imported_mesh_semantics,
        source_mesh_semantics,
        imported_mesh_semantics,
    )
    motion_passed, motion_source, motion_imported = _animation_motion_comparison(source, imported)
    _check(
        checks,
        "animation.sampled_motion",
        motion_passed,
        motion_source,
        motion_imported,
    )

    for key, identifier in (
        ("evaluated_triangles", "geometry.triangles"),
        ("total_bones", "rig.total_bones"),
        ("deform_bones", "rig.deform_bones"),
        ("usable_bound_actions", "animation.clip_count"),
    ):
        source_value = source.get("scene", {}).get(key)
        imported_value = imported.get("scene", {}).get(key)
        _check(checks, identifier, source_value == imported_value, source_value, imported_value)

    source_fps = source.get("scene", {}).get("effective_fps")
    imported_fps = imported.get("scene", {}).get("effective_fps")
    _check(
        checks,
        "animation.effective_fps",
        source_fps is not None and imported_fps is not None and abs(float(source_fps) - float(imported_fps)) <= 1e-9,
        source_fps,
        imported_fps,
    )

    source_requirements = source.get("requirements")
    imported_requirements = imported.get("requirements")
    _check(
        checks,
        "audit.requirements_identical",
        source_requirements == imported_requirements,
        source_requirements,
        imported_requirements,
    )

    failures = [item for item in checks if item["verdict"] == "fail"]
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roundtrip_verdict": "fail" if failures else "pass",
        "tolerance_m": tolerance_m,
        "conversion_policy": {
            "allow_audit_warnings": allow_warnings,
            "allow_uv_reparameterization": allow_uv_reparameterization,
        },
        "comparator": {
            "path": str(Path(__file__).resolve()),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "source_report": provenance["source_report"],
        "imported_report": provenance["imported_report"],
        "delivery": {
            "path": provenance["delivery"]["path"],
            "sha256": provenance["delivery"]["sha256"],
        },
        "checks": checks,
        "failure_count": len(failures),
    }


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    output = None
    try:
        args = _parser().parse_args()
        if not math.isfinite(args.tolerance_m) or args.tolerance_m < 0:
            raise ValueError("--tolerance-m must be finite and non-negative")
        source_path = Path(args.source).resolve()
        imported_path = Path(args.imported).resolve()
        delivery_path = Path(args.delivery).resolve()
        if not delivery_path.is_file():
            raise FileNotFoundError(delivery_path)
        if delivery_path.suffix.lower() not in {".glb", ".gltf", ".fbx"}:
            raise ValueError("--delivery must be .glb, .gltf, or .fbx")
        output = _authorized_output(args)
        source = _load(source_path)
        imported = _load(imported_path)
        provenance = {
            "source_report": {
                "path": str(source_path),
                "sha256": _sha256(source_path),
                "run_id": source.get("run_id"),
            },
            "imported_report": {
                "path": str(imported_path),
                "sha256": _sha256(imported_path),
                "run_id": imported.get("run_id"),
            },
            "delivery": {
                "path": str(delivery_path),
                "normalized_path": _normalized_path(str(delivery_path)),
                "sha256": _sha256(delivery_path),
            },
        }
        report = compare(
            source,
            imported,
            args.tolerance_m,
            args.allow_audit_warnings,
            args.allow_uv_reparameterization,
            provenance,
        )
        report["run_id"] = run_id
        report["started_at"] = started_at
        _atomic_write(output, report)
        print(json.dumps({"output": str(output), "roundtrip_verdict": report["roundtrip_verdict"]}))
        return 2 if report["roundtrip_verdict"] == "fail" else 0
    except Exception as error:
        error_report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "started_at": started_at,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "roundtrip_verdict": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        if output is not None:
            try:
                _atomic_write(output, error_report)
            except Exception:
                pass
        print("AUTO_TA_COMPARE_INTERNAL_ERROR=" + json.dumps(error_report, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
