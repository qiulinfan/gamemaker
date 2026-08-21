"""Validate an Auto TA receipt and its referenced artifacts.

The validator is intentionally strict: it verifies enums, gate reduction,
absolute paths, file existence, SHA-256 values, and round-trip evidence before
allowing a receipt to claim ``validated``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_STATUSES = {"validated", "prototype", "blocked", "failed"}
ALLOWED_VERDICTS = {"pass", "fail", "not_tested"}
ALLOWED_EVIDENCE_STATUSES = {"current", "pending", "stale", "rejected"}
EXPECTED_COMPARISON_CHECK_IDS = {
    "audit.source_verdict",
    "audit.imported_verdict",
    "provenance.report_files_distinct",
    "provenance.run_ids_distinct",
    "provenance.report_roles",
    "provenance.source_is_blend",
    "provenance.delivery_import",
    "provenance.isolated_invocations",
    "provenance.audit_implementation",
    "provenance.run_order",
    "scope.mesh_names",
    "materials.names",
    "materials.principled_semantics",
    "objects.hierarchy",
    "objects.transforms_and_pivots",
    "geometry.scene_bounds_m",
    "rig.rest_hierarchy",
    "animation.clips",
    "animation.sample_contract",
    "geometry.mesh_semantics",
    "geometry.mesh_bounds_m",
    "animation.sampled_motion",
    "geometry.triangles",
    "rig.total_bones",
    "rig.deform_bones",
    "animation.clip_count",
    "animation.effective_fps",
    "audit.requirements_identical",
}


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(f"argument error: {message}")


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Validate auto-ta-receipt.json")
    parser.add_argument("receipt")
    parser.add_argument("--output")
    parser.add_argument("--output-root")
    parser.add_argument(
        "--blender-bin",
        help="Trusted Blender executable used to replay both audits before accepting validated status",
    )
    parser.add_argument("--force", action="store_true")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _problem(problems: list[dict], code: str, message: str, **context) -> None:
    item = {"code": code, "message": message}
    if context:
        item["context"] = context
    problems.append(item)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Receipt must be a JSON object")
    return value


def _check_artifact(entry: dict, section: str, index: int, problems: list[dict]) -> Path | None:
    path_value = entry.get("path")
    expected_hash = entry.get("sha256")
    if not isinstance(path_value, str) or not path_value:
        _problem(problems, "ARTIFACT_PATH_MISSING", "Artifact path is required", section=section, index=index)
        return None
    path = Path(path_value)
    if not path.is_absolute():
        _problem(problems, "ARTIFACT_PATH_NOT_ABSOLUTE", "Execution receipt artifact paths must be absolute", section=section, index=index, path=path_value)
        return None
    if not path.is_file():
        _problem(problems, "ARTIFACT_MISSING", "Referenced artifact does not exist", section=section, index=index, path=str(path))
        return None
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        _problem(problems, "ARTIFACT_HASH_MISSING", "Artifact must declare a SHA-256", section=section, index=index, path=str(path))
        return None
    actual = _sha256(path)
    if actual.lower() != expected_hash.lower():
        _problem(problems, "ARTIFACT_HASH_MISMATCH", "Artifact SHA-256 does not match", section=section, index=index, path=str(path), expected=expected_hash, actual=actual)
        return None
    return path.resolve()


def _check_timestamp(value, name: str, problems: list[dict]):
    if not isinstance(value, str):
        _problem(problems, "TIMESTAMP_MISSING", "Timestamp is required", field=name)
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _problem(problems, "TIMESTAMP_INVALID", "Timestamp must be ISO 8601", field=name, value=value)
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _problem(problems, "TIMESTAMP_TIMEZONE_MISSING", "Timestamp must include a UTC offset", field=name, value=value)
        return None
    return parsed


def _normalized_path(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return os.path.normcase(str(Path(value).resolve()))


def _load_evidence_json(path: Path, problems: list[dict], code: str) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _problem(problems, code, "Evidence is not a readable JSON object", path=str(path), error=str(error))
        return None
    if not isinstance(value, dict):
        _problem(problems, code, "Evidence JSON must be an object", path=str(path))
        return None
    return value


def _trusted_script(name: str) -> Path:
    path = Path(__file__).resolve().with_name(name)
    if not path.is_file():
        raise FileNotFoundError(f"Trusted Auto TA implementation is missing: {path}")
    return path


def _validate_audit_report(
    report: dict,
    expected_role: str,
    problems: list[dict],
    *,
    context: str,
) -> None:
    if report.get("schema_version") != "2.0":
        _problem(
            problems,
            "AUDIT_SCHEMA_INVALID",
            "Audit evidence must use schema 2.0",
            context=context,
            actual=report.get("schema_version"),
        )
    if report.get("audit_verdict") not in {"pass", "pass_with_warnings", "fail"}:
        _problem(
            problems,
            "AUDIT_VERDICT_INVALID",
            "Audit evidence must contain a valid audit_verdict",
            context=context,
            actual=report.get("audit_verdict"),
        )
    if not isinstance(report.get("run_id"), str) or not report.get("run_id"):
        _problem(problems, "AUDIT_RUN_ID_INVALID", "Audit evidence must contain a run id", context=context)
    actual_role = report.get("source", {}).get("mode")
    if actual_role != expected_role:
        _problem(
            problems,
            "AUDIT_ROLE_INVALID",
            "Audit evidence has the wrong source role",
            context=context,
            expected=expected_role,
            actual=actual_role,
        )

    trusted = _trusted_script("blender_asset_audit.py")
    implementation = report.get("runtime", {}).get("audit_script")
    if not isinstance(implementation, dict) or (
        _normalized_path(implementation.get("path")) != _normalized_path(str(trusted))
        or str(implementation.get("sha256", "")).lower() != _sha256(trusted).lower()
    ):
        _problem(
            problems,
            "AUDIT_IMPLEMENTATION_UNTRUSTED",
            "Audit evidence is not bound to the current trusted auditor implementation",
            context=context,
            actual=implementation,
            trusted_path=str(trusted),
            trusted_sha256=_sha256(trusted),
        )


def _numbers_match(left, right, tolerance: float = 1e-9) -> bool:
    if not isinstance(left, (int, float)) or isinstance(left, bool):
        return False
    if not isinstance(right, (int, float)) or isinstance(right, bool):
        return False
    return math.isfinite(float(left)) and math.isfinite(float(right)) and abs(float(left) - float(right)) <= tolerance


def _number_lists_match(left, right, tolerance: float = 1e-9) -> bool:
    return (
        isinstance(left, (list, tuple))
        and isinstance(right, (list, tuple))
        and len(left) == len(right)
        and all(_numbers_match(a, b, tolerance) for a, b in zip(left, right))
    )


def _validate_contract_binding(
    contract: dict,
    source: dict,
    imported: dict,
    comparison: dict,
    output_index: dict[str, dict],
    problems: list[dict],
) -> None:
    """Bind supported structured contract fields to the real audit chain."""

    source_requirements = source.get("requirements")
    imported_requirements = imported.get("requirements")
    if not isinstance(source_requirements, dict) or not isinstance(imported_requirements, dict):
        _problem(problems, "CONTRACT_AUDIT_REQUIREMENTS_MISSING", "Both audits must declare their gate requirements")
        return
    if source_requirements != imported_requirements:
        _problem(problems, "CONTRACT_AUDIT_REQUIREMENTS_DIFFER", "Source and imported audit requirements differ")
        return
    requirements = source_requirements

    geometry = contract.get("geometry")
    space = contract.get("space")
    target = contract.get("target")
    textures = contract.get("textures")
    if not all(isinstance(value, dict) for value in (geometry, space, target, textures)):
        _problem(problems, "CONTRACT_STRUCTURED_SECTION_INVALID", "Contract geometry, space, target, and textures must be objects")
        return

    boolean_requirements = (
        ("closed_manifold_required", "require_closed"),
        ("outward_winding_required", "require_outward_winding"),
        ("all_meshes_require_uv", "require_uv"),
        ("all_meshes_require_material", "require_material"),
    )
    for contract_field, requirement_field in boolean_requirements:
        value = geometry.get(contract_field)
        if value is True and requirements.get(requirement_field) is not True:
            _problem(
                problems,
                "CONTRACT_GATE_NOT_ENFORCED",
                "A required geometry contract gate was not enabled in the audits",
                contract_field=contract_field,
                requirement_field=requirement_field,
            )

    max_triangles = geometry.get("max_evaluated_triangles")
    audited_max_triangles = requirements.get("max_triangles")
    if isinstance(max_triangles, int) and not isinstance(max_triangles, bool):
        if not isinstance(audited_max_triangles, int) or audited_max_triangles > max_triangles:
            _problem(
                problems,
                "CONTRACT_TRIANGLE_BUDGET_NOT_ENFORCED",
                "Audit triangle budget is absent or looser than the contract",
                contract=max_triangles,
                audit=audited_max_triangles,
            )
    else:
        _problem(problems, "CONTRACT_TRIANGLE_BUDGET_INVALID", "geometry.max_evaluated_triangles must be an integer")

    contract_tolerance = space.get("dimension_tolerance_m")
    audit_tolerance = requirements.get("tolerance_m")
    comparison_tolerance = comparison.get("tolerance_m")
    if not _numbers_match(contract_tolerance, contract_tolerance, 0.0) or float(contract_tolerance) < 0:
        _problem(problems, "CONTRACT_DIMENSION_TOLERANCE_INVALID", "space.dimension_tolerance_m must be finite and non-negative")
        contract_tolerance = None
    elif (
        not _numbers_match(audit_tolerance, audit_tolerance, 0.0)
        or float(audit_tolerance) > float(contract_tolerance)
        or not _numbers_match(comparison_tolerance, comparison_tolerance, 0.0)
        or float(comparison_tolerance) > float(contract_tolerance)
    ):
        _problem(
            problems,
            "CONTRACT_TOLERANCE_NOT_ENFORCED",
            "Audit or comparison tolerance is absent or looser than the contract",
            contract=contract_tolerance,
            audit=audit_tolerance,
            comparison=comparison_tolerance,
        )

    authoring = space.get("authoring")
    expected_dimensions = authoring.get("dimensions_m_xyz") if isinstance(authoring, dict) else None
    if not _number_lists_match(requirements.get("expected_dimensions_m"), expected_dimensions):
        _problem(
            problems,
            "CONTRACT_DIMENSIONS_NOT_ENFORCED",
            "Audit expected dimensions do not match space.authoring.dimensions_m_xyz",
            contract=expected_dimensions,
            audit=requirements.get("expected_dimensions_m"),
        )
    expected_ground = space.get("ground_z_m")
    if not _numbers_match(requirements.get("expected_ground_z_m"), expected_ground):
        _problem(
            problems,
            "CONTRACT_GROUND_NOT_ENFORCED",
            "Audit expected ground height does not match the contract",
            contract=expected_ground,
            audit=requirements.get("expected_ground_z_m"),
        )
    meters_per_unit = authoring.get("meters_per_unit") if isinstance(authoring, dict) else None
    if meters_per_unit is not None:
        for label, report in (("source", source), ("imported", imported)):
            if not _numbers_match(report.get("units", {}).get("meters_per_blender_unit"), meters_per_unit):
                _problem(
                    problems,
                    "CONTRACT_UNIT_SCALE_MISMATCH",
                    "Audit unit scale does not match the contract authoring scale",
                    report=label,
                    contract=meters_per_unit,
                    audit=report.get("units", {}).get("meters_per_blender_unit"),
                )

    policy = comparison.get("conversion_policy") if isinstance(comparison.get("conversion_policy"), dict) else {}
    if geometry.get("uv_coordinate_preservation_required") is True and policy.get("allow_uv_reparameterization") is not False:
        _problem(
            problems,
            "CONTRACT_UV_POLICY_NOT_ENFORCED",
            "The contract requires UV-coordinate preservation but comparison allows reparameterization",
        )

    pivot = space.get("pivot")
    if pivot == "bottom_center" and contract_tolerance is not None:
        for label, report in (("source", source), ("imported", imported)):
            bounds = (report.get("scene", {}).get("evaluated_mesh_bounds") or {}).get("meters", {})
            minimum = bounds.get("min")
            maximum = bounds.get("max")
            root_name = report.get("scope", {}).get("name") if report.get("scope", {}).get("type") == "root_object" else None
            root = next((item for item in report.get("objects", []) if item.get("name") == root_name), None)
            expected_origin = (
                [(float(minimum[0]) + float(maximum[0])) / 2, (float(minimum[1]) + float(maximum[1])) / 2, float(minimum[2])]
                if isinstance(minimum, list) and isinstance(maximum, list) and len(minimum) == 3 and len(maximum) == 3
                else None
            )
            if root is None or not _number_lists_match(root.get("world_origin_m"), expected_origin, float(contract_tolerance)):
                _problem(
                    problems,
                    "CONTRACT_PIVOT_NOT_ENFORCED",
                    "The root origin is not at the contracted bottom-center pivot",
                    report=label,
                    expected=expected_origin,
                    actual=root.get("world_origin_m") if root else None,
                )
    elif pivot not in {None, "bottom_center"}:
        _problem(
            problems,
            "CONTRACT_PIVOT_POLICY_UNSUPPORTED",
            "This validator cannot automatically prove the requested pivot policy",
            pivot=pivot,
        )

    required_maps = textures.get("required_maps")
    if not isinstance(required_maps, list):
        _problem(problems, "CONTRACT_REQUIRED_MAPS_INVALID", "textures.required_maps must be a list")
    elif required_maps:
        _problem(
            problems,
            "CONTRACT_TEXTURE_PROFILE_UNSUPPORTED",
            "Bitmap/map contracts require dedicated texture evidence and cannot use the bundled constant-material validated profile",
            required_maps=required_maps,
        )

    rig = contract.get("rig")
    if rig is not None:
        if not isinstance(rig, dict):
            _problem(problems, "CONTRACT_RIG_INVALID", "rig must be an object when present")
        else:
            for requirement_field in ("require_armature", "require_all_weighted"):
                if requirements.get(requirement_field) is not True:
                    _problem(
                        problems,
                        "CONTRACT_RIG_GATE_NOT_ENFORCED",
                        "A required rig gate was not enabled in the audits",
                        requirement=requirement_field,
                    )
            if rig.get("normalized_weights_required") is True and requirements.get("require_normalized_weights") is not True:
                _problem(problems, "CONTRACT_NORMALIZED_WEIGHTS_NOT_ENFORCED", "Normalized weights were required but not gated")
            for contract_field, requirement_field in (("max_bones", "max_bones"), ("max_influences_per_vertex", "max_influences")):
                contract_limit = rig.get(contract_field)
                audit_limit = requirements.get(requirement_field)
                if not isinstance(contract_limit, int) or isinstance(contract_limit, bool) or not isinstance(audit_limit, int) or audit_limit > contract_limit:
                    _problem(
                        problems,
                        "CONTRACT_RIG_BUDGET_NOT_ENFORCED",
                        "An audit rig budget is absent or looser than the contract",
                        contract_field=contract_field,
                        contract=contract_limit,
                        audit=audit_limit,
                    )

            required_bones = rig.get("required_bones")
            if not isinstance(required_bones, list) or not all(isinstance(name, str) and name for name in required_bones):
                _problem(problems, "CONTRACT_REQUIRED_BONES_INVALID", "rig.required_bones must be a list of names")
                required_bones = []
            for label, report in (("source", source), ("imported", imported)):
                armatures = [item for item in report.get("objects", []) if "armature" in item]
                skeleton_name = rig.get("skeleton_name")
                armature = next((item for item in armatures if item.get("name") == skeleton_name), None)
                if armature is None:
                    _problem(
                        problems,
                        "CONTRACT_SKELETON_MISSING",
                        "The contracted skeleton is absent from an audit",
                        report=label,
                        skeleton=skeleton_name,
                    )
                    continue
                bone_data = armature["armature"].get("bone_data", [])
                bone_names = {bone.get("name") for bone in bone_data}
                missing_bones = sorted(set(required_bones) - bone_names)
                if missing_bones:
                    _problem(
                        problems,
                        "CONTRACT_REQUIRED_BONES_MISSING",
                        "Contracted bones are absent",
                        report=label,
                        missing=missing_bones,
                    )
                root_count = rig.get("root_count")
                actual_root_count = len(armature["armature"].get("root_bones", []))
                if isinstance(root_count, int) and actual_root_count != root_count:
                    _problem(
                        problems,
                        "CONTRACT_ROOT_COUNT_MISMATCH",
                        "Skeleton root count does not match the contract",
                        report=label,
                        contract=root_count,
                        actual=actual_root_count,
                    )
                hierarchy = rig.get("hierarchy")
                if isinstance(hierarchy, str) and ">" in hierarchy:
                    chain = [name.strip() for name in hierarchy.split(">") if name.strip()]
                    parents = {bone.get("name"): bone.get("parent") for bone in bone_data}
                    bad_links = [
                        {"child": child, "expected_parent": parent, "actual_parent": parents.get(child)}
                        for parent, child in zip(chain, chain[1:])
                        if parents.get(child) != parent
                    ]
                    if bad_links:
                        _problem(
                            problems,
                            "CONTRACT_RIG_HIERARCHY_MISMATCH",
                            "Skeleton hierarchy does not match the contracted chain",
                            report=label,
                            links=bad_links,
                        )
                elif hierarchy not in {None, ""}:
                    _problem(
                        problems,
                        "CONTRACT_RIG_HIERARCHY_UNSUPPORTED",
                        "The rig hierarchy format is not machine-verifiable",
                        hierarchy=hierarchy,
                    )

    animations = contract.get("animation")
    if animations:
        if requirements.get("require_actions") is not True:
            _problem(problems, "CONTRACT_ACTION_GATE_NOT_ENFORCED", "Contracted animation exists but actions were not required")
        if not isinstance(animations, list):
            _problem(problems, "CONTRACT_ANIMATION_INVALID", "animation must be a list")
        else:
            for clip in animations:
                if not isinstance(clip, dict):
                    _problem(problems, "CONTRACT_ANIMATION_ENTRY_INVALID", "Animation entries must be objects")
                    continue
                if not _numbers_match(requirements.get("expected_fps"), clip.get("fps")):
                    _problem(
                        problems,
                        "CONTRACT_FPS_NOT_ENFORCED",
                        "Audit FPS requirement does not match the animation contract",
                        clip=clip.get("name"),
                    )
                representative = clip.get("representative_frames")
                if clip.get("loop_seam") and not _number_lists_match(requirements.get("expected_loop_frames"), representative):
                    _problem(
                        problems,
                        "CONTRACT_LOOP_FRAMES_NOT_ENFORCED",
                        "Audit loop samples do not match the animation contract",
                        clip=clip.get("name"),
                    )
                for label, report in (("source", source), ("imported", imported)):
                    action = next(
                        (
                            item
                            for item in report.get("actions", [])
                            if item.get("name") == clip.get("name") and item.get("valid_bound_clip") is True
                        ),
                        None,
                    )
                    expected_range = [clip.get("frame_start"), clip.get("frame_end")]
                    if action is None or not _number_lists_match(action.get("frame_range"), expected_range):
                        _problem(
                            problems,
                            "CONTRACT_ANIMATION_CLIP_MISMATCH",
                            "A valid bound clip does not match the contracted name/range",
                            report=label,
                            clip=clip.get("name"),
                            expected_range=expected_range,
                            actual_range=action.get("frame_range") if action else None,
                        )

    delivery_formats = target.get("delivery_formats")
    if not isinstance(delivery_formats, list) or not delivery_formats:
        _problem(problems, "CONTRACT_DELIVERY_FORMATS_INVALID", "target.delivery_formats must be a non-empty list")
    else:
        output_suffixes = {Path(entry.get("path", "")).suffix.lower().removeprefix(".") for entry in output_index.values()}
        missing_formats = sorted(
            str(value).lower().removeprefix(".")
            for value in delivery_formats
            if str(value).lower().removeprefix(".") not in output_suffixes
        )
        if missing_formats:
            _problem(
                problems,
                "CONTRACT_DELIVERY_FORMAT_MISSING",
                "Receipt outputs do not contain every contracted delivery format",
                missing=missing_formats,
            )


def _audit_replay_arguments(report: dict, output: Path, output_root: Path) -> list[str]:
    requirements = report.get("requirements")
    if not isinstance(requirements, dict):
        raise ValueError("Audit replay requires a requirements object")
    arguments = ["--output", str(output), "--output-root", str(output_root), "--force"]

    scope = report.get("scope") or {}
    if scope.get("type") == "root_object" and isinstance(scope.get("name"), str):
        arguments.extend(("--root-object", scope["name"]))
    elif scope.get("type") == "collection" and isinstance(scope.get("name"), str):
        arguments.extend(("--scope-collection", scope["name"]))
    elif scope.get("type") != "active_scene":
        raise ValueError(f"Unsupported replay scope: {scope}")

    scene = report.get("scene") or {}
    if scene.get("pose_mode") == "REST":
        arguments.append("--rest-pose")
    elif isinstance(scene.get("frame_current"), (int, float)):
        arguments.extend(("--frame", str(int(scene["frame_current"]))))

    boolean_flags = {
        "require_mesh": "--require-mesh",
        "require_closed": "--require-closed",
        "require_outward_winding": "--require-outward-winding",
        "require_uv": "--require-uv",
        "require_material": "--require-material",
        "require_referenced_images_resolve": "--require-referenced-images-resolve",
        "require_armature": "--require-armature",
        "require_actions": "--require-actions",
        "require_all_weighted": "--require-all-weighted",
        "require_normalized_weights": "--require-normalized-weights",
    }
    for field, flag in boolean_flags.items():
        if requirements.get(field) is True:
            arguments.append(flag)

    scalar_flags = {
        "min_image_textures": "--min-image-textures",
        "max_triangles": "--max-triangles",
        "max_bones": "--max-bones",
        "max_deform_bones": "--max-deform-bones",
        "min_deform_bones": "--min-deform-bones",
        "max_influences": "--max-influences",
        "expected_ground_z_m": "--expected-ground-z-m",
        "tolerance_m": "--tolerance-m",
        "position_weld_tolerance_m": "--position-weld-tolerance-m",
        "expected_fps": "--expected-fps",
        "animation_tolerance": "--animation-tolerance",
    }
    for field, flag in scalar_flags.items():
        value = requirements.get(field)
        if value is not None:
            arguments.extend((flag, str(value)))

    vector_flags = {
        "expected_dimensions_m": "--expected-dimensions-m",
        "expected_loop_frames": "--expected-loop-frames",
    }
    for field, flag in vector_flags.items():
        values = requirements.get(field)
        if values is not None:
            if not isinstance(values, list):
                raise ValueError(f"Audit replay field must be a list: {field}")
            arguments.append(flag)
            arguments.extend(str(value) for value in values)

    units = report.get("units") or {}
    if units.get("conversion_source") == "explicit_argument":
        arguments.extend(("--meters-per-unit", str(units.get("meters_per_blender_unit"))))
    return arguments


def _audit_reproducible_view(report: dict) -> dict:
    value = copy.deepcopy(report)
    for field in ("run_id", "started_at", "generated_at"):
        value.pop(field, None)
    if isinstance(value.get("source"), dict):
        value["source"].pop("started_at", None)
    return value


def _replay_audit(
    stored: dict,
    trusted_blender: Path,
    output: Path,
    output_root: Path,
    problems: list[dict],
    *,
    label: str,
    runner=None,
) -> dict | None:
    auditor = _trusted_script("blender_asset_audit.py")
    source = stored.get("source") or {}
    mode = source.get("mode")
    command = [
        str(trusted_blender),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--offline-mode",
        "--python-exit-code",
        "1",
    ]
    if mode == "open_blend":
        input_path = Path(str(source.get("path", ""))).resolve()
        if not input_path.is_file() or input_path.suffix.lower() != ".blend":
            _problem(problems, "AUDIT_REPLAY_SOURCE_INVALID", "Source audit replay needs a real .blend", report=label)
            return None
        command.append(str(input_path))
    elif mode != "clean_exchange_import":
        _problem(problems, "AUDIT_REPLAY_ROLE_INVALID", "Audit replay role is unsupported", report=label, role=mode)
        return None
    command.extend(("--python", str(auditor), "--"))
    replay_arguments = _audit_replay_arguments(stored, output, output_root)
    if mode == "clean_exchange_import":
        input_path = Path(str(source.get("path", ""))).resolve()
        replay_arguments[0:0] = ["--input-file", str(input_path)]
    command.extend(replay_arguments)

    try:
        completed = (runner or subprocess.run)(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _problem(problems, "AUDIT_REPLAY_EXECUTION_ERROR", "Blender audit replay could not run", report=label, error=str(error))
        return None
    expected_exit = 2 if stored.get("audit_verdict") == "fail" else 0
    if completed.returncode != expected_exit:
        _problem(
            problems,
            "AUDIT_REPLAY_EXIT_MISMATCH",
            "Blender audit replay exit code does not match stored evidence",
            report=label,
            expected=expected_exit,
            actual=completed.returncode,
            stdout_tail=completed.stdout[-2000:],
            stderr_tail=completed.stderr[-2000:],
        )
    replayed = _load_evidence_json(output, problems, "AUDIT_REPLAY_REPORT_INVALID") if output.is_file() else None
    if replayed is None:
        return None
    _validate_audit_report(replayed, mode, problems, context=f"replayed_{label}")
    if _audit_reproducible_view(stored) != _audit_reproducible_view(replayed):
        _problem(
            problems,
            "AUDIT_REPLAY_CONTENT_MISMATCH",
            "Stored audit evidence differs from a fresh Blender replay of the hash-verified artifact",
            report=label,
        )
    return replayed


def _fresh_replay_audits(
    source: dict,
    imported: dict,
    trusted_blender: Path | None,
    problems: list[dict],
    *,
    runner=None,
) -> None:
    """Bind a validated claim to two new audits from an explicit Blender binary."""

    if trusted_blender is None:
        _problem(
            problems,
            "VALIDATED_REPLAY_REQUIRED",
            "Validated receipts require --blender-bin and two fresh audit replays",
        )
        return
    expanded_blender = trusted_blender.expanduser()
    if not expanded_blender.is_absolute():
        _problem(
            problems,
            "VALIDATED_REPLAY_BLENDER_INVALID",
            "--blender-bin must be an absolute path selected as trusted",
            path=str(trusted_blender),
        )
        return
    blender = expanded_blender.resolve()
    if not blender.is_file() or not os.access(blender, os.X_OK):
        _problem(
            problems,
            "VALIDATED_REPLAY_BLENDER_INVALID",
            "The explicitly trusted Blender path is not an executable file",
            path=str(blender),
        )
        return

    with tempfile.TemporaryDirectory(prefix="autota-auto-ta-replay-") as raw_root:
        output_root = Path(raw_root).resolve()
        _replay_audit(
            source,
            blender,
            output_root / "source-audit.json",
            output_root,
            problems,
            label="source",
            runner=runner,
        )
        _replay_audit(
            imported,
            blender,
            output_root / "imported-audit.json",
            output_root,
            problems,
            label="imported",
            runner=runner,
        )


def _output_reference(
    value,
    output_index: dict[str, dict],
    problems: list[dict],
    code: str,
    **context,
) -> Path | None:
    normalized = _normalized_path(value)
    if normalized is None or normalized not in output_index:
        _problem(
            problems,
            code,
            "Evidence path must reference a hash-verified receipt output",
            value=value,
            **context,
        )
        return None
    return Path(output_index[normalized]["path"]).resolve()


def _validate_gate_evidence(
    gate: dict,
    output_index: dict[str, dict],
    contract_entry: dict | None,
    problems: list[dict],
) -> None:
    identifier = gate.get("id")
    verdict = gate.get("verdict")
    evidence_status = gate.get("evidence_status")
    evidence = gate.get("evidence")
    if evidence_status not in ALLOWED_EVIDENCE_STATUSES:
        _problem(
            problems,
            "GATE_EVIDENCE_STATUS_INVALID",
            "Gate evidence_status is required and must be current, pending, stale, or rejected",
            id=identifier,
            evidence_status=evidence_status,
        )
    elif verdict in {"pass", "fail"} and evidence_status != "current":
        _problem(
            problems,
            "GATE_EVIDENCE_STATUS_MISMATCH",
            "A tested gate must bind current evidence",
            id=identifier,
            verdict=verdict,
            evidence_status=evidence_status,
        )
    elif verdict == "not_tested" and evidence_status == "current":
        _problem(
            problems,
            "GATE_EVIDENCE_STATUS_MISMATCH",
            "An untested gate cannot claim current accepted evidence",
            id=identifier,
            verdict=verdict,
            evidence_status=evidence_status,
        )

    reason = gate.get("reason")
    if verdict == "pass" and isinstance(reason, str) and reason.strip():
        _problem(
            problems,
            "PASS_GATE_REASON_CONFLICT",
            "A passing gate cannot carry a pending, stale, rejected, or failure reason",
            id=identifier,
        )
    if verdict == "not_tested" and (not isinstance(reason, str) or not reason.strip()):
        _problem(
            problems,
            "GATE_REASON_MISSING",
            "An untested gate must state a reason",
            id=identifier,
        )

    if gate.get("required") is True and verdict in {"pass", "fail"}:
        if not isinstance(evidence, dict) or not evidence:
            _problem(
                problems,
                "GATE_EVIDENCE_MISSING",
                "A tested required gate must contain non-empty evidence",
                id=identifier,
            )
            return
    if not isinstance(evidence, dict):
        return

    if identifier == "contract.asset_contract":
        if contract_entry is None:
            return
        if (
            _normalized_path(evidence.get("path")) != _normalized_path(contract_entry.get("path"))
            or str(evidence.get("sha256", "")).lower()
            != str(contract_entry.get("sha256", "")).lower()
        ):
            _problem(
                problems,
                "CONTRACT_GATE_EVIDENCE_MISMATCH",
                "Contract gate evidence does not match the top-level contract artifact",
                id=identifier,
            )

    if isinstance(identifier, str) and identifier.startswith("artifact.") and verdict in {"pass", "fail"}:
        artifacts = evidence.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            _problem(
                problems,
                "ARTIFACT_GATE_REFERENCES_MISSING",
                "A tested artifact gate must reference hash-verified receipt outputs",
                id=identifier,
            )
        else:
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    _problem(
                        problems,
                        "ARTIFACT_GATE_REFERENCE_INVALID",
                        "Artifact gate references must be objects",
                        id=identifier,
                        index=index,
                    )
                    continue
                artifact_path = _output_reference(
                    artifact.get("path"),
                    output_index,
                    problems,
                    "ARTIFACT_GATE_NOT_OUTPUT",
                    gate=identifier,
                    index=index,
                )
                if artifact_path is None:
                    continue
                output_entry = output_index[_normalized_path(str(artifact_path))]
                if (
                    str(artifact.get("sha256", "")).lower()
                    != str(output_entry.get("sha256", "")).lower()
                    or artifact.get("role") != output_entry.get("role")
                ):
                    _problem(
                        problems,
                        "ARTIFACT_GATE_REFERENCE_MISMATCH",
                        "Artifact gate path, hash, and role must match its receipt output",
                        id=identifier,
                        index=index,
                    )

    report_value = evidence.get("report")
    if report_value is not None:
        report_path = _output_reference(
            report_value,
            output_index,
            problems,
            "GATE_REPORT_NOT_OUTPUT",
            gate=identifier,
        )
        if report_path is not None:
            report = _load_evidence_json(report_path, problems, "GATE_REPORT_INVALID")
            expected_role = None
            if identifier == "source.technical_audit":
                expected_role = "open_blend"
            elif isinstance(identifier, str) and identifier.startswith("roundtrip.clean_"):
                expected_role = "clean_exchange_import"
            if report is not None and expected_role is not None:
                _validate_audit_report(report, expected_role, problems, context=str(identifier))
                actual = report.get("audit_verdict")
                claimed = evidence.get("audit_verdict")
                if claimed != actual:
                    _problem(
                        problems,
                        "GATE_AUDIT_CLAIM_MISMATCH",
                        "Gate evidence claim does not match the audit report",
                        gate=identifier,
                        claimed=claimed,
                        actual=actual,
                    )
                expected = "pass" if verdict == "pass" else "fail" if verdict == "fail" else None
                if expected is not None and actual != expected:
                    _problem(
                        problems,
                        "GATE_AUDIT_VERDICT_MISMATCH",
                        "Gate verdict does not match the audit report",
                        gate=identifier,
                        gate_verdict=verdict,
                        audit_verdict=actual,
                    )

    image_values = []
    if isinstance(evidence.get("image"), str):
        image_values.append(evidence["image"])
    if isinstance(evidence.get("images"), list):
        image_values.extend(evidence["images"])
    for image_value in image_values:
        _output_reference(
            image_value,
            output_index,
            problems,
            "VISUAL_EVIDENCE_NOT_OUTPUT",
            gate=identifier,
        )


def _validate_comparison_evidence(
    round_trip: dict,
    output_index: dict[str, dict],
    problems: list[dict],
    *,
    require_fresh_replay: bool = False,
    trusted_blender: Path | None = None,
) -> bool:
    before = len(problems)
    evidence_path = _output_reference(
        round_trip.get("evidence"),
        output_index,
        problems,
        "ROUNDTRIP_EVIDENCE_NOT_OUTPUT",
    )
    if evidence_path is None:
        return False
    comparison = _load_evidence_json(evidence_path, problems, "ROUNDTRIP_EVIDENCE_INVALID")
    if comparison is None:
        return False
    if comparison.get("schema_version") != "2.0":
        _problem(
            problems,
            "ROUNDTRIP_SCHEMA_INVALID",
            "Round-trip evidence must use comparator schema 2.0",
            actual=comparison.get("schema_version"),
        )

    trusted_comparator = _trusted_script("compare_asset_audits.py")
    implementation = comparison.get("comparator")
    if not isinstance(implementation, dict) or (
        _normalized_path(implementation.get("path")) != _normalized_path(str(trusted_comparator))
        or str(implementation.get("sha256", "")).lower() != _sha256(trusted_comparator).lower()
    ):
        _problem(
            problems,
            "ROUNDTRIP_COMPARATOR_UNTRUSTED",
            "Comparison evidence is not bound to the current trusted comparator implementation",
            actual=implementation,
            trusted_path=str(trusted_comparator),
            trusted_sha256=_sha256(trusted_comparator),
        )

    checks = comparison.get("checks")
    computed_failures = None
    if not isinstance(checks, list):
        _problem(problems, "ROUNDTRIP_CHECKS_INVALID", "Comparison checks must be a list")
    else:
        check_ids = []
        invalid_checks = []
        computed_failures = 0
        for index, check in enumerate(checks):
            if not isinstance(check, dict) or not isinstance(check.get("id"), str) or check.get("verdict") not in {"pass", "fail"}:
                invalid_checks.append(index)
                continue
            check_ids.append(check["id"])
            computed_failures += int(check["verdict"] == "fail")
        if invalid_checks:
            _problem(
                problems,
                "ROUNDTRIP_CHECK_ENTRY_INVALID",
                "Every comparison check must have a string id and pass/fail verdict",
                indices=invalid_checks,
            )
        duplicates = sorted({identifier for identifier in check_ids if check_ids.count(identifier) > 1})
        missing = sorted(EXPECTED_COMPARISON_CHECK_IDS - set(check_ids))
        unexpected = sorted(set(check_ids) - EXPECTED_COMPARISON_CHECK_IDS)
        if duplicates or missing or unexpected:
            _problem(
                problems,
                "ROUNDTRIP_CHECK_SET_INVALID",
                "Comparison evidence does not contain the exact trusted check set",
                duplicates=duplicates,
                missing=missing,
                unexpected=unexpected,
            )

    receipt_verdict = round_trip.get("verdict")
    actual_verdict = comparison.get("roundtrip_verdict")
    if actual_verdict != receipt_verdict:
        _problem(
            problems,
            "ROUNDTRIP_CONTENT_VERDICT_MISMATCH",
            "Receipt round-trip verdict does not match comparison evidence",
            receipt=receipt_verdict,
            evidence=actual_verdict,
        )
    declared_failures = comparison.get("failure_count")
    if computed_failures is not None and declared_failures != computed_failures:
        _problem(
            problems,
            "ROUNDTRIP_FAILURE_COUNT_MISMATCH",
            "Comparison failure_count does not equal the failed checks",
            declared=declared_failures,
            computed=computed_failures,
        )
    derived_verdict = None if computed_failures is None else "fail" if computed_failures else "pass"
    if derived_verdict is not None and actual_verdict != derived_verdict:
        _problem(
            problems,
            "ROUNDTRIP_CHECK_VERDICT_MISMATCH",
            "Comparison top-level verdict does not reduce from its check verdicts",
            declared=actual_verdict,
            computed=derived_verdict,
        )

    nested_reports = {}
    nested_paths = {}
    for field in ("source_report", "imported_report", "delivery"):
        entry = comparison.get(field)
        if not isinstance(entry, dict):
            _problem(
                problems,
                "ROUNDTRIP_CHAIN_ENTRY_MISSING",
                "Comparison evidence is missing a provenance entry",
                field=field,
            )
            continue
        nested_path = _output_reference(
            entry.get("path"),
            output_index,
            problems,
            "ROUNDTRIP_CHAIN_NOT_OUTPUT",
            field=field,
        )
        if nested_path is None:
            continue
        nested_paths[field] = nested_path
        output_entry = output_index[_normalized_path(str(nested_path))]
        if str(entry.get("sha256", "")).lower() != str(output_entry.get("sha256", "")).lower():
            _problem(
                problems,
                "ROUNDTRIP_CHAIN_HASH_MISMATCH",
                "Comparison provenance hash does not match the receipt output",
                field=field,
            )
        if field != "delivery":
            nested = _load_evidence_json(nested_path, problems, "ROUNDTRIP_AUDIT_INVALID")
            if nested is not None:
                nested_reports[field] = nested
                if nested.get("run_id") != entry.get("run_id"):
                    _problem(
                        problems,
                        "ROUNDTRIP_RUN_ID_MISMATCH",
                        "Comparison provenance run id does not match its audit report",
                        field=field,
                    )

    source = nested_reports.get("source_report")
    imported = nested_reports.get("imported_report")
    delivery = comparison.get("delivery") if isinstance(comparison.get("delivery"), dict) else None
    if source is not None:
        _validate_audit_report(source, "open_blend", problems, context="source_report")
    if imported is not None:
        _validate_audit_report(imported, "clean_exchange_import", problems, context="imported_report")
    if require_fresh_replay:
        if source is not None and imported is not None:
            _fresh_replay_audits(source, imported, trusted_blender, problems)
        elif trusted_blender is None:
            _problem(
                problems,
                "VALIDATED_REPLAY_REQUIRED",
                "Validated receipts require --blender-bin and two fresh audit replays",
            )
    if receipt_verdict == "pass":
        unsupported_materials = sorted(
            {
                f"{label}:{material.get('name')}"
                for label, report in (("source", source), ("imported", imported))
                if report is not None
                for material in report.get("materials", [])
                if material.get("semantics", {}).get("validation_profile")
                != "constant_principled_core_v1"
            }
        )
        if unsupported_materials:
            _problem(
                problems,
                "ROUNDTRIP_MATERIAL_PROFILE_UNSUPPORTED",
                "Validated material round trips currently support only unlinked, image-free constant Principled core materials",
                materials=unsupported_materials,
            )
    if source is not None and imported is not None and source.get("run_id") == imported.get("run_id"):
        _problem(problems, "ROUNDTRIP_RUN_IDS_NOT_DISTINCT", "Source and imported audit run ids must differ")
    if imported is not None and delivery is not None:
        imported_source = imported.get("source", {})
        if (
            _normalized_path(imported_source.get("path")) != _normalized_path(delivery.get("path"))
            or imported_source.get("sha256") != delivery.get("sha256")
        ):
            _problem(
                problems,
                "ROUNDTRIP_DELIVERY_CHAIN_MISMATCH",
                "Imported audit input does not match the compared delivery",
            )

    editable_outputs = [
        entry for entry in output_index.values() if entry.get("role") == "editable_source"
    ]
    if len(editable_outputs) != 1:
        _problem(
            problems,
            "ROUNDTRIP_EDITABLE_SOURCE_ROLE_INVALID",
            "A tested round trip requires exactly one editable_source output",
            count=len(editable_outputs),
        )
    elif source is not None:
        editable = editable_outputs[0]
        source_metadata = source.get("source", {})
        if (
            _normalized_path(editable.get("path")) != _normalized_path(source_metadata.get("path"))
            or str(editable.get("sha256", "")).lower()
            != str(source_metadata.get("sha256", "")).lower()
        ):
            _problem(
                problems,
                "ROUNDTRIP_EDITABLE_SOURCE_MISMATCH",
                "The editable_source output is not the .blend file used by the source audit",
            )

    engine_delivery_outputs = [
        entry
        for entry in output_index.values()
        if entry.get("role") == "engine_delivery"
        or (
            isinstance(entry.get("role"), str)
            and entry["role"].endswith("_engine_delivery")
        )
    ]
    if len(engine_delivery_outputs) != 1:
        _problem(
            problems,
            "ROUNDTRIP_ENGINE_DELIVERY_ROLE_INVALID",
            "A tested round trip requires exactly one engine-delivery output role",
            count=len(engine_delivery_outputs),
        )
    elif delivery is not None:
        engine_delivery = engine_delivery_outputs[0]
        if (
            _normalized_path(engine_delivery.get("path")) != _normalized_path(delivery.get("path"))
            or str(engine_delivery.get("sha256", "")).lower()
            != str(delivery.get("sha256", "")).lower()
        ):
            _problem(
                problems,
                "ROUNDTRIP_ENGINE_DELIVERY_MISMATCH",
                "The engine-delivery output is not the delivery used by the clean-import audit",
            )

    tolerance = comparison.get("tolerance_m")
    policy = comparison.get("conversion_policy")
    policy_valid = (
        isinstance(policy, dict)
        and isinstance(policy.get("allow_audit_warnings"), bool)
        and isinstance(policy.get("allow_uv_reparameterization"), bool)
    )
    if not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
        _problem(problems, "ROUNDTRIP_TOLERANCE_INVALID", "Comparison tolerance must be finite and non-negative")
    if not policy_valid:
        _problem(
            problems,
            "ROUNDTRIP_CONVERSION_POLICY_INVALID",
            "Comparison evidence must declare boolean audit-warning and UV policies",
            actual=policy,
        )

    if (
        source is not None
        and imported is not None
        and all(field in nested_paths for field in ("source_report", "imported_report", "delivery"))
        and isinstance(tolerance, (int, float))
        and math.isfinite(tolerance)
        and tolerance >= 0
        and policy_valid
    ):
        spec = importlib.util.spec_from_file_location("auto_ta_trusted_comparator", trusted_comparator)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load trusted comparator: {trusted_comparator}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source_path = nested_paths["source_report"]
        imported_path = nested_paths["imported_report"]
        delivery_path = nested_paths["delivery"]
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
                "normalized_path": module._normalized_path(str(delivery_path)),
                "sha256": _sha256(delivery_path),
            },
        }
        recomputed = module.compare(
            source,
            imported,
            float(tolerance),
            policy["allow_audit_warnings"],
            policy["allow_uv_reparameterization"],
            provenance,
        )
        compared_fields = (
            "roundtrip_verdict",
            "tolerance_m",
            "conversion_policy",
            "comparator",
            "source_report",
            "imported_report",
            "delivery",
            "checks",
            "failure_count",
        )
        mismatched_fields = [
            field
            for field in compared_fields
            if json.dumps(comparison.get(field), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            != json.dumps(recomputed.get(field), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        ]
        if mismatched_fields:
            _problem(
                problems,
                "ROUNDTRIP_RECOMPUTATION_MISMATCH",
                "Stored comparison evidence differs from an independent in-memory recomputation",
                fields=mismatched_fields,
            )

    return receipt_verdict == "pass" and actual_verdict == "pass" and len(problems) == before


def validate(
    receipt: dict,
    receipt_path: Path,
    *,
    trusted_blender: Path | None = None,
) -> dict:
    problems: list[dict] = []
    if receipt.get("schema_version") != "1.0":
        _problem(
            problems,
            "RECEIPT_SCHEMA_INVALID",
            "Receipt schema_version must be 1.0",
            actual=receipt.get("schema_version"),
        )
    status = receipt.get("status")
    if status not in ALLOWED_STATUSES:
        _problem(problems, "STATUS_INVALID", "Top-level status is invalid", actual=status, allowed=sorted(ALLOWED_STATUSES))

    started = _check_timestamp(receipt.get("started_at"), "started_at", problems)
    finished = _check_timestamp(receipt.get("finished_at"), "finished_at", problems)
    if started and finished and finished < started:
        _problem(problems, "TIMESTAMP_ORDER", "finished_at precedes started_at")

    contract_entry = receipt.get("asset_contract")
    contract = None
    if not isinstance(contract_entry, dict):
        _problem(
            problems,
            "ASSET_CONTRACT_INVALID",
            "asset_contract must be a path/SHA-256 artifact object",
            value=contract_entry,
        )
        contract_entry = None
    else:
        contract_path = _check_artifact(contract_entry, "asset_contract", 0, problems)
        if contract_path is not None:
            contract = _load_evidence_json(contract_path, problems, "ASSET_CONTRACT_JSON_INVALID")
            if contract is not None:
                required_contract_fields = {
                    "schema_version",
                    "job",
                    "target",
                    "space",
                    "geometry",
                    "textures",
                    "integration",
                    "acceptance",
                    "authorization",
                }
                missing = sorted(required_contract_fields - set(contract))
                if contract.get("schema_version") != "1.0" or missing:
                    _problem(
                        problems,
                        "ASSET_CONTRACT_SCHEMA_INVALID",
                        "Asset contract schema or required fields are invalid",
                        actual_schema=contract.get("schema_version"),
                        missing=missing,
                    )

    output_index: dict[str, dict] = {}
    for section in ("inputs", "outputs"):
        entries = receipt.get(section)
        if not isinstance(entries, list):
            _problem(problems, "ARTIFACT_LIST_INVALID", f"{section} must be a list", section=section)
            continue
        if section == "outputs" and not entries:
            _problem(problems, "OUTPUTS_EMPTY", "At least one output is required")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                _problem(problems, "ARTIFACT_ENTRY_INVALID", "Artifact entry must be an object", section=section, index=index)
            else:
                artifact_path = _check_artifact(entry, section, index, problems)
                if section == "outputs" and artifact_path is not None:
                    normalized = _normalized_path(str(artifact_path))
                    if normalized in output_index:
                        _problem(
                            problems,
                            "OUTPUT_PATH_DUPLICATE",
                            "Output artifact paths must be unique",
                            path=str(artifact_path),
                        )
                    else:
                        output_index[normalized] = entry

    gates = receipt.get("gates")
    required_verdicts = []
    identifiers = set()
    if not isinstance(gates, list) or not gates:
        _problem(problems, "GATES_INVALID", "gates must be a non-empty list")
        gates = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            _problem(problems, "GATE_ENTRY_INVALID", "Gate entry must be an object", index=index)
            continue
        identifier = gate.get("id")
        if not isinstance(identifier, str) or not identifier:
            _problem(problems, "GATE_ID_INVALID", "Gate id is required", index=index)
        elif identifier in identifiers:
            _problem(problems, "GATE_ID_DUPLICATE", "Gate ids must be unique", id=identifier)
        else:
            identifiers.add(identifier)
        if not isinstance(gate.get("required"), bool):
            _problem(problems, "GATE_REQUIRED_INVALID", "Gate required must be boolean", id=identifier)
        verdict = gate.get("verdict")
        if verdict not in ALLOWED_VERDICTS:
            _problem(problems, "GATE_VERDICT_INVALID", "Gate verdict is invalid", id=identifier, verdict=verdict)
        if gate.get("required") is True and verdict in ALLOWED_VERDICTS:
            required_verdicts.append(verdict)
        _validate_gate_evidence(gate, output_index, contract_entry, problems)

    required_pass_ids = {
        gate.get("id")
        for gate in gates
        if isinstance(gate, dict)
        and gate.get("required") is True
        and gate.get("verdict") == "pass"
    }
    if status == "validated":
        coverage = {
            "contract": "contract.asset_contract" in required_pass_ids,
            "artifact": any(identifier.startswith("artifact.") for identifier in required_pass_ids if isinstance(identifier, str)),
            "visual": any(identifier.startswith("visual.") for identifier in required_pass_ids if isinstance(identifier, str)),
            "source_audit": "source.technical_audit" in required_pass_ids,
            "clean_import_audit": any(identifier.startswith("roundtrip.clean_") for identifier in required_pass_ids if isinstance(identifier, str)),
            "semantic_comparison": "roundtrip.semantic_comparison" in required_pass_ids,
        }
        if isinstance(contract, dict) and contract.get("rig") is not None:
            coverage["rig"] = any("rig" in identifier for identifier in required_pass_ids if isinstance(identifier, str))
        if isinstance(contract, dict) and contract.get("animation"):
            coverage["animation"] = any("animation" in identifier for identifier in required_pass_ids if isinstance(identifier, str))
        missing_coverage = sorted(key for key, value in coverage.items() if not value)
        if missing_coverage:
            _problem(
                problems,
                "VALIDATED_GATE_COVERAGE_MISSING",
                "Validated delivery lacks required evidence domains",
                missing=missing_coverage,
            )

    round_trip = receipt.get("round_trip")
    round_trip_verdict = None
    round_trip_ok = False
    if not isinstance(round_trip, dict):
        _problem(problems, "ROUNDTRIP_INVALID", "round_trip must be an object")
    else:
        round_trip_verdict = round_trip.get("verdict")
        if round_trip_verdict not in ALLOWED_VERDICTS:
            _problem(
                problems,
                "ROUNDTRIP_VERDICT_INVALID",
                "round_trip.verdict is invalid",
                verdict=round_trip_verdict,
                allowed=sorted(ALLOWED_VERDICTS),
            )

        if round_trip_verdict in {"pass", "fail"}:
            normalized = _normalized_path(round_trip.get("evidence"))
            output_entry = output_index.get(normalized) if normalized is not None else None
            if output_entry is None:
                _problem(
                    problems,
                    "ROUNDTRIP_EVIDENCE_MISSING",
                    "Tested round-trip evidence must be a hash-verified receipt output",
                    value=round_trip.get("evidence"),
                )
            elif str(round_trip.get("sha256", "")).lower() != str(output_entry.get("sha256", "")).lower():
                _problem(
                    problems,
                    "ROUNDTRIP_HASH_MISMATCH",
                    "Round-trip evidence hash does not match the receipt output",
                    expected=round_trip.get("sha256"),
                    actual=output_entry.get("sha256"),
                )
            round_trip_ok = _validate_comparison_evidence(
                round_trip,
                output_index,
                problems,
                require_fresh_replay=status == "validated",
                trusted_blender=trusted_blender,
            )
        elif round_trip_verdict == "not_tested":
            reason = round_trip.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                _problem(
                    problems,
                    "ROUNDTRIP_REASON_MISSING",
                    "An untested round trip must state a reason",
                )

    if "fail" in required_verdicts or round_trip_verdict == "fail":
        expected_statuses = {"failed"}
    elif "not_tested" in required_verdicts or round_trip_verdict == "not_tested":
        expected_statuses = {"prototype", "blocked"}
    elif required_verdicts and all(value == "pass" for value in required_verdicts):
        expected_statuses = {"validated"} if round_trip_ok else {"prototype", "blocked"}
    else:
        expected_statuses = {"prototype", "blocked"}
    if status in ALLOWED_STATUSES and status not in expected_statuses:
        _problem(problems, "STATUS_REDUCTION_MISMATCH", "Top-level status does not follow required gate and round-trip verdicts", actual=status, expected=sorted(expected_statuses), required_verdicts=required_verdicts, round_trip_ok=round_trip_ok)

    return {
        "schema_version": "1.0",
        "run_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "receipt": {"path": str(receipt_path), "sha256": _sha256(receipt_path)},
        "validation_verdict": "fail" if problems else "pass",
        "problem_count": len(problems),
        "problems": problems,
    }


def _authorized_output(args) -> Path | None:
    if args.output is None and args.output_root is None:
        return None
    if not args.output or not args.output_root:
        raise ValueError("--output and --output-root must be provided together")
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


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    output = None
    receipt_path = None
    try:
        args = _parser().parse_args()
        trusted_blender = None
        if args.blender_bin:
            blender_argument = Path(args.blender_bin)
            if not blender_argument.is_absolute():
                raise ValueError(
                    "argument error: --blender-bin must be an absolute path "
                    "selected as trusted"
                )
            trusted_blender = blender_argument.expanduser().resolve()
        receipt_path = Path(args.receipt).resolve()
        output = _authorized_output(args)
        receipt = _read_json(receipt_path)
        report = validate(
            receipt,
            receipt_path,
            trusted_blender=trusted_blender,
        )
        report["run_id"] = run_id
        report["started_at"] = started_at
        if output is not None:
            _atomic_write(output, report)
        print(json.dumps({"receipt": str(receipt_path), "validation_verdict": report["validation_verdict"], "problem_count": report["problem_count"], "output": str(output) if output else None}))
        return 2 if report["validation_verdict"] == "fail" else 0
    except Exception as error:
        error_report = {
            "schema_version": "1.0",
            "run_id": run_id,
            "started_at": started_at,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "receipt": {"path": str(receipt_path) if receipt_path else None},
            "validation_verdict": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        if output is not None:
            try:
                _atomic_write(output, error_report)
            except Exception:
                pass
        print("AUTO_TA_RECEIPT_INTERNAL_ERROR=" + json.dumps(error_report, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
