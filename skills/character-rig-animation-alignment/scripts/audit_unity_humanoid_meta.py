#!/usr/bin/env python3
"""Gate two Unity humanoid FBX importers against structural scale regressions.

The parser deliberately uses only the Python standard library. Unity ``.meta``
files contain YAML tags that make a general YAML dependency inconvenient, while
the ModelImporter fields used here have a small and stable indentation contract.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


EXIT_PASS = 0
EXIT_GATE_FAILURE = 2
EXIT_INTERNAL_ERROR = 3

DEFAULT_REQUIRED_HUMAN = (
    "Hips",
    "Spine",
    "Head",
    "LeftUpperLeg",
    "RightUpperLeg",
    "LeftLowerLeg",
    "RightLowerLeg",
    "LeftFoot",
    "RightFoot",
    "LeftUpperArm",
    "RightUpperArm",
    "LeftLowerArm",
    "RightLowerArm",
    "LeftHand",
    "RightHand",
)

_HUMAN_DESCRIPTION_RE = re.compile(r"^  humanDescription:\s*$")
_HUMAN_RE = re.compile(r"^    human:\s*$")
_SKELETON_RE = re.compile(r"^    skeleton:\s*$")
_HUMAN_ENTRY_RE = re.compile(r"^    - boneName:\s*(.*?)\s*$")
_HUMAN_NAME_RE = re.compile(r"^      humanName:\s*(.*?)\s*$")
_SKELETON_ENTRY_RE = re.compile(r"^    - name:\s*(.*?)\s*$")
_PARENT_NAME_RE = re.compile(r"^      parentName:\s*(.*?)\s*$")
_VECTOR_RE = re.compile(r"^      (position|scale):\s*\{(.*?)\}\s*$")
_IMPORTER_INT_RE = {
    "animationType": re.compile(r"^  animationType:\s*(-?\d+)\s*$"),
    "avatarSetup": re.compile(r"^  avatarSetup:\s*(-?\d+)\s*$"),
}


class MetaFormatError(ValueError):
    """Raised when a present ModelImporter structure cannot be parsed safely."""


@dataclass(frozen=True)
class HumanMapping:
    bone_name: str
    human_name: str
    line: int


@dataclass(frozen=True)
class SkeletonBone:
    name: str
    parent_name: str | None
    position: tuple[float, float, float] | None
    scale: tuple[float, float, float] | None
    line: int


@dataclass(frozen=True)
class ImportMeta:
    path: Path
    animation_type: int | None
    avatar_setup: int | None
    mappings: tuple[HumanMapping, ...]
    skeleton: tuple[SkeletonBone, ...]


def _slot_key(value: str) -> str:
    """Normalize Unity's spaced finger names to HumanBodyBones-style keys."""

    return "".join(character.lower() for character in value if character.isalnum())


def _slot_label(value: str) -> str:
    return "".join(character for character in value if character.isalnum())


def _parse_vector(payload: str, path: Path, line_number: int) -> tuple[float, float, float]:
    components: dict[str, float] = {}
    for item in payload.split(","):
        if ":" not in item:
            raise MetaFormatError(f"{path}:{line_number}: malformed vector component {item!r}")
        key, raw_value = item.split(":", 1)
        key = key.strip()
        if key not in {"x", "y", "z", "w"}:
            raise MetaFormatError(f"{path}:{line_number}: unknown vector component {key!r}")
        try:
            components[key] = float(raw_value.strip())
        except ValueError as error:
            raise MetaFormatError(
                f"{path}:{line_number}: invalid float {raw_value.strip()!r}"
            ) from error
    if not all(axis in components for axis in ("x", "y", "z")):
        raise MetaFormatError(f"{path}:{line_number}: vector must contain x, y, and z")
    vector = (components["x"], components["y"], components["z"])
    if not all(math.isfinite(value) for value in vector):
        raise MetaFormatError(f"{path}:{line_number}: vector contains a non-finite value")
    return vector


def _find_line(lines: Sequence[str], pattern: re.Pattern[str], start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if pattern.match(lines[index]):
            return index
    return None


def _parse_human_mappings(
    lines: Sequence[str], start: int, end: int, path: Path
) -> tuple[HumanMapping, ...]:
    mappings: list[HumanMapping] = []
    current_bone: str | None = None
    current_human: str | None = None
    current_line: int | None = None

    def finish() -> None:
        nonlocal current_bone, current_human, current_line
        if current_bone is None:
            return
        if not current_bone or not current_human:
            raise MetaFormatError(
                f"{path}:{current_line}: human mapping requires non-empty boneName and humanName"
            )
        mappings.append(HumanMapping(current_bone, current_human, current_line or 0))
        current_bone = current_human = None
        current_line = None

    for index in range(start, end):
        line = lines[index]
        entry_match = _HUMAN_ENTRY_RE.match(line)
        if entry_match:
            finish()
            current_bone = entry_match.group(1)
            current_line = index + 1
            continue
        name_match = _HUMAN_NAME_RE.match(line)
        if name_match and current_bone is not None:
            current_human = name_match.group(1)
    finish()
    return tuple(mappings)


def _parse_skeleton(
    lines: Sequence[str], start: int, end: int, path: Path
) -> tuple[SkeletonBone, ...]:
    skeleton: list[SkeletonBone] = []
    current: dict[str, Any] | None = None

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        name = current["name"]
        if not name:
            raise MetaFormatError(f"{path}:{current['line']}: skeleton entry has no name")
        skeleton.append(
            SkeletonBone(
                name=name,
                parent_name=current.get("parent_name"),
                position=current.get("position"),
                scale=current.get("scale"),
                line=current["line"],
            )
        )
        current = None

    for index in range(start, end):
        line = lines[index]
        entry_match = _SKELETON_ENTRY_RE.match(line)
        if entry_match:
            finish()
            current = {"name": entry_match.group(1), "line": index + 1}
            continue
        if current is None:
            continue
        parent_match = _PARENT_NAME_RE.match(line)
        if parent_match:
            current["parent_name"] = parent_match.group(1) or None
            continue
        vector_match = _VECTOR_RE.match(line)
        if vector_match:
            current[vector_match.group(1)] = _parse_vector(
                vector_match.group(2), path, index + 1
            )
    finish()
    return tuple(skeleton)


def parse_meta(path: Path) -> ImportMeta:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    importer_values: dict[str, int | None] = {name: None for name in _IMPORTER_INT_RE}
    for name, pattern in _IMPORTER_INT_RE.items():
        matches = [int(match.group(1)) for line in lines if (match := pattern.match(line))]
        if len(matches) > 1:
            raise MetaFormatError(f"{path}: multiple top-level {name} fields")
        if matches:
            importer_values[name] = matches[0]

    description_index = _find_line(lines, _HUMAN_DESCRIPTION_RE)
    if description_index is None:
        return ImportMeta(
            path=path,
            animation_type=importer_values["animationType"],
            avatar_setup=importer_values["avatarSetup"],
            mappings=(),
            skeleton=(),
        )

    section_end = len(lines)
    for index in range(description_index + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            section_end = index
            break

    human_index = _find_line(lines, _HUMAN_RE, description_index + 1)
    skeleton_index = _find_line(lines, _SKELETON_RE, description_index + 1)
    if human_index is None or human_index >= section_end:
        human_index = None
    if skeleton_index is None or skeleton_index >= section_end:
        skeleton_index = None

    mappings: tuple[HumanMapping, ...] = ()
    if human_index is not None:
        human_end = skeleton_index if skeleton_index is not None else section_end
        mappings = _parse_human_mappings(lines, human_index + 1, human_end, path)

    skeleton: tuple[SkeletonBone, ...] = ()
    if skeleton_index is not None:
        skeleton_end = section_end
        for index in range(skeleton_index + 1, section_end):
            if re.match(r"^    [A-Za-z_][^:]*:", lines[index]):
                skeleton_end = index
                break
        skeleton = _parse_skeleton(lines, skeleton_index + 1, skeleton_end, path)

    return ImportMeta(
        path=path,
        animation_type=importer_values["animationType"],
        avatar_setup=importer_values["avatarSetup"],
        mappings=mappings,
        skeleton=skeleton,
    )


def _group_by(items: Iterable[Any], key_function: Any) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in items:
        grouped.setdefault(key_function(item), []).append(item)
    return grouped


def _duplicate_report(groups: dict[str, list[Any]], label_function: Any) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "entries": [label_function(item) for item in items],
            "lines": [item.line for item in items],
        }
        for key, items in sorted(groups.items())
        if len(items) > 1
    ]


def audit_one(meta: ImportMeta, required: Sequence[str], scale_tolerance: float) -> dict[str, Any]:
    human_groups = _group_by(meta.mappings, lambda mapping: _slot_key(mapping.human_name))
    mapped_bone_groups = _group_by(meta.mappings, lambda mapping: mapping.bone_name)
    skeleton_groups = _group_by(meta.skeleton, lambda bone: bone.name)
    unique_skeleton = {
        name: entries[0] for name, entries in skeleton_groups.items() if len(entries) == 1
    }

    duplicate_human = _duplicate_report(
        human_groups, lambda mapping: {"human": mapping.human_name, "bone": mapping.bone_name}
    )
    duplicate_mapped_bones = _duplicate_report(
        mapped_bone_groups,
        lambda mapping: {"human": mapping.human_name, "bone": mapping.bone_name},
    )
    duplicate_skeleton = _duplicate_report(
        skeleton_groups, lambda bone: {"name": bone.name, "parent": bone.parent_name}
    )

    missing_required = [
        required_name
        for required_name in required
        if len(human_groups.get(_slot_key(required_name), ())) != 1
    ]
    missing_mapped_bones: list[dict[str, str]] = []
    mapped_scale_violations: list[dict[str, Any]] = []
    incomplete_mapped_bones: list[dict[str, str]] = []
    checked_bones: set[str] = set()
    for mapping in meta.mappings:
        if mapping.bone_name in checked_bones:
            continue
        checked_bones.add(mapping.bone_name)
        bones = skeleton_groups.get(mapping.bone_name, ())
        if len(bones) != 1:
            missing_mapped_bones.append(
                {"human": _slot_label(mapping.human_name), "bone": mapping.bone_name}
            )
            continue
        bone = bones[0]
        if bone.position is None or bone.scale is None:
            incomplete_mapped_bones.append(
                {"human": _slot_label(mapping.human_name), "bone": mapping.bone_name}
            )
            continue
        max_deviation = max(abs(component - 1.0) for component in bone.scale)
        if max_deviation > scale_tolerance:
            mapped_scale_violations.append(
                {
                    "human": _slot_label(mapping.human_name),
                    "bone": mapping.bone_name,
                    "scale": list(bone.scale),
                    "max_deviation": max_deviation,
                }
            )

    importer_ok = meta.animation_type == 3 and meta.avatar_setup == 1
    passed = not any(
        (
            not importer_ok,
            duplicate_human,
            duplicate_mapped_bones,
            duplicate_skeleton,
            missing_required,
            missing_mapped_bones,
            incomplete_mapped_bones,
            mapped_scale_violations,
        )
    )
    return {
        "path": str(meta.path.resolve()),
        "passed": passed,
        "importer": {
            "animation_type": meta.animation_type,
            "animation_type_expected": 3,
            "avatar_setup": meta.avatar_setup,
            "avatar_setup_expected": 1,
            "passed": importer_ok,
        },
        "counts": {
            "human_mappings": len(meta.mappings),
            "skeleton_bones": len(meta.skeleton),
            "unique_human_slots": sum(len(entries) == 1 for entries in human_groups.values()),
        },
        "missing_required_human": missing_required,
        "duplicate_human_slots": duplicate_human,
        "duplicate_mapped_bones": duplicate_mapped_bones,
        "duplicate_skeleton_bones": duplicate_skeleton,
        "missing_mapped_skeleton_bones": missing_mapped_bones,
        "incomplete_mapped_skeleton_bones": incomplete_mapped_bones,
        "mapped_scale_violations": mapped_scale_violations,
        "_human_groups": human_groups,
        "_unique_skeleton": unique_skeleton,
    }


def compare(
    reference: ImportMeta,
    candidate: ImportMeta,
    reference_audit: dict[str, Any],
    candidate_audit: dict[str, Any],
    ratio_min: float,
    ratio_max: float,
    min_common: int,
) -> dict[str, Any]:
    reference_human = reference_audit["_human_groups"]
    candidate_human = candidate_audit["_human_groups"]
    reference_skeleton = reference_audit["_unique_skeleton"]
    candidate_skeleton = candidate_audit["_unique_skeleton"]

    ratios: list[dict[str, Any]] = []
    unusable: list[dict[str, str]] = []
    common_keys = sorted(set(reference_human) & set(candidate_human))
    for key in common_keys:
        reference_mappings = reference_human[key]
        candidate_mappings = candidate_human[key]
        if len(reference_mappings) != 1 or len(candidate_mappings) != 1:
            continue
        reference_mapping = reference_mappings[0]
        candidate_mapping = candidate_mappings[0]
        reference_bone = reference_skeleton.get(reference_mapping.bone_name)
        candidate_bone = candidate_skeleton.get(candidate_mapping.bone_name)
        if reference_bone is None or candidate_bone is None:
            continue
        if reference_bone.position is None or candidate_bone.position is None:
            continue
        reference_length = math.sqrt(sum(value * value for value in reference_bone.position))
        candidate_length = math.sqrt(sum(value * value for value in candidate_bone.position))
        if reference_length <= 1e-9 or candidate_length <= 1e-9:
            unusable.append(
                {
                    "human": _slot_label(reference_mapping.human_name),
                    "reason": "zero_or_near_zero_local_segment_length",
                }
            )
            continue
        ratio = candidate_length / reference_length
        ratios.append(
            {
                "human": _slot_label(reference_mapping.human_name),
                "reference_bone": reference_mapping.bone_name,
                "candidate_bone": candidate_mapping.bone_name,
                "reference_parent": reference_bone.parent_name,
                "candidate_parent": candidate_bone.parent_name,
                "reference_length": reference_length,
                "candidate_length": candidate_length,
                "ratio": ratio,
                "passed": ratio_min <= ratio <= ratio_max,
            }
        )

    ratios.sort(key=lambda item: item["human"])
    out_of_range = [item for item in ratios if not item["passed"]]
    median_ratio = statistics.median(item["ratio"] for item in ratios) if ratios else None
    suspected_scale = None
    if median_ratio is not None:
        if 0.005 <= median_ratio <= 0.02:
            suspected_scale = "candidate_is_about_1_percent_of_reference"
        elif 50.0 <= median_ratio <= 200.0:
            suspected_scale = "candidate_is_about_100_times_reference"

    enough_common = len(ratios) >= min_common
    return {
        "passed": enough_common and not out_of_range,
        "common_human_slots": len(common_keys),
        "comparable_local_segments": len(ratios),
        "minimum_comparable_required": min_common,
        "enough_comparable_segments": enough_common,
        "ratio_bounds_inclusive": {"minimum": ratio_min, "maximum": ratio_max},
        "median_ratio": median_ratio,
        "suspected_uniform_scale_error": suspected_scale,
        "unusable_common_slots": unusable,
        "out_of_range": out_of_range,
        "ratios": ratios,
    }


def _failure(code: str, message: str, details: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    if details not in (None, [], {}):
        result["details"] = details
    return result


def collect_failures(
    reference_audit: dict[str, Any], candidate_audit: dict[str, Any], comparison: dict[str, Any]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for role, audit in (("reference", reference_audit), ("candidate", candidate_audit)):
        importer = audit["importer"]
        if not importer["passed"]:
            failures.append(
                _failure(
                    f"{role}.importer_not_humanoid_create_avatar",
                    f"{role} must use animationType=3 and avatarSetup=1",
                    importer,
                )
            )
        for field, code, message in (
            ("missing_required_human", "missing_required_human", "required human slots are missing or duplicated"),
            ("duplicate_human_slots", "duplicate_human_slots", "human slots are mapped more than once"),
            ("duplicate_mapped_bones", "duplicate_mapped_bones", "a skeleton bone is mapped to multiple human slots"),
            ("duplicate_skeleton_bones", "duplicate_skeleton_bones", "skeleton names are duplicated"),
            ("missing_mapped_skeleton_bones", "missing_mapped_skeleton_bones", "mapped bones are absent or duplicated in skeleton"),
            ("incomplete_mapped_skeleton_bones", "incomplete_mapped_skeleton_bones", "mapped skeleton bones lack position or scale"),
            ("mapped_scale_violations", "mapped_scale_violations", "mapped skeleton scale is not sufficiently close to one"),
        ):
            if audit[field]:
                failures.append(_failure(f"{role}.{code}", f"{role} {message}", audit[field]))

    if not comparison["enough_comparable_segments"]:
        failures.append(
            _failure(
                "comparison.insufficient_common_segments",
                "too few common human slots have comparable local segment lengths",
                {
                    "actual": comparison["comparable_local_segments"],
                    "required": comparison["minimum_comparable_required"],
                },
            )
        )
    if comparison["out_of_range"]:
        failures.append(
            _failure(
                "comparison.segment_ratio_out_of_range",
                "one or more candidate/reference local segment length ratios are outside the gate",
                comparison["out_of_range"],
            )
        )
    return failures


def _public_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in audit.items() if not key.startswith("_")}


def _required_human(values: Sequence[str] | None) -> list[str]:
    if not values:
        return list(DEFAULT_REQUIRED_HUMAN)
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for value in raw_value.split(","):
            value = value.strip()
            key = _slot_key(value)
            if not key:
                continue
            if key not in seen:
                result.append(_slot_label(value))
                seen.add(key)
    if not result:
        raise ValueError("--required-human did not contain a human slot name")
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Unity humanoid ModelImporter .fbx.meta files by HumanBodyBones "
            "mapping and local skeleton segment scale."
        )
    )
    parser.add_argument("--reference", required=True, type=Path, help="Trusted reference .fbx.meta")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate .fbx.meta to gate")
    parser.add_argument("--ratio-min", type=float, default=0.5, help="Inclusive minimum candidate/reference segment ratio (default: 0.5)")
    parser.add_argument("--ratio-max", type=float, default=1.5, help="Inclusive maximum candidate/reference segment ratio (default: 1.5)")
    parser.add_argument("--min-common", type=int, default=15, help="Minimum comparable common human slots (default: 15)")
    parser.add_argument(
        "--required-human",
        action="append",
        metavar="SLOT[,SLOT...]",
        help=(
            "Required HumanBodyBones slots; repeat or comma-separate. If omitted, "
            "the 15 core body slots are required."
        ),
    )
    parser.add_argument("--scale-tolerance", type=float, default=0.001, help="Maximum absolute mapped scale deviation from 1 (default: 0.001)")
    parser.add_argument("--output", type=Path, help="Also write the JSON report to this path")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Authorized root that must contain --output (required with --output)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly allow replacement of the authorized output file",
    )
    return parser


def _validate_arguments(arguments: argparse.Namespace) -> None:
    if not math.isfinite(arguments.ratio_min) or not math.isfinite(arguments.ratio_max):
        raise ValueError("ratio bounds must be finite")
    if arguments.ratio_min <= 0 or arguments.ratio_max < arguments.ratio_min:
        raise ValueError("ratio bounds must satisfy 0 < --ratio-min <= --ratio-max")
    if arguments.min_common < 1:
        raise ValueError("--min-common must be at least 1")
    if not math.isfinite(arguments.scale_tolerance) or arguments.scale_tolerance < 0:
        raise ValueError("--scale-tolerance must be finite and non-negative")


def _authorized_output(arguments: argparse.Namespace) -> Path | None:
    if arguments.output is None and arguments.output_root is None:
        return None
    if arguments.output is None or arguments.output_root is None:
        raise ValueError("--output and --output-root must be provided together")
    root = arguments.output_root.expanduser().resolve(strict=False)
    output = arguments.output.expanduser().resolve(strict=False)
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"--output escapes --output-root: {output}") from exc
    if output.exists() and output.is_dir():
        raise IsADirectoryError(output)
    if (output.exists() or os.path.lexists(output)) and not arguments.force:
        raise FileExistsError(
            f"Refusing to overwrite existing report without --force: {output}"
        )
    return output


def _emit(report: dict[str, Any], output: Path | None) -> None:
    payload = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    sys.stdout.write(payload)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            if temporary.exists():
                temporary.unlink()


def run(arguments: argparse.Namespace) -> int:
    _validate_arguments(arguments)
    required = _required_human(arguments.required_human)
    reference = parse_meta(arguments.reference)
    candidate = parse_meta(arguments.candidate)
    reference_audit = audit_one(reference, required, arguments.scale_tolerance)
    candidate_audit = audit_one(candidate, required, arguments.scale_tolerance)
    comparison = compare(
        reference,
        candidate,
        reference_audit,
        candidate_audit,
        arguments.ratio_min,
        arguments.ratio_max,
        arguments.min_common,
    )
    failures = collect_failures(reference_audit, candidate_audit, comparison)
    report = {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "configuration": {
            "ratio_min": arguments.ratio_min,
            "ratio_max": arguments.ratio_max,
            "min_common": arguments.min_common,
            "required_human": required,
            "scale_tolerance": arguments.scale_tolerance,
        },
        "reference": _public_audit(reference_audit),
        "candidate": _public_audit(candidate_audit),
        "comparison": comparison,
        "failures": failures,
    }
    _emit(report, arguments.output)
    return EXIT_PASS if not failures else EXIT_GATE_FAILURE


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    output: Path | None = None
    try:
        output = _authorized_output(arguments)
        arguments.output = output
        return run(arguments)
    except (OSError, UnicodeError, MetaFormatError, ValueError) as error:
        report = {
            "schema_version": 1,
            "status": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        try:
            _emit(report, output)
        except OSError:
            sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return EXIT_INTERNAL_ERROR
    except Exception as error:  # Keep the CLI's exit contract even for unexpected defects.
        report = {
            "schema_version": 1,
            "status": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
