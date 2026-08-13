#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6,<7",
# ]
# ///
"""Validate a portable create-2d-game-art production receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml


SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
MAX_AUDIT_BYTES = 32 * 1024 * 1024
MAX_FRAME_MANIFEST_BYTES = 16 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"validated", "prototype", "blocked", "failed"}
SOURCE_ROLES = {
    "user_authored",
    "generated_source",
    "licensed_source",
    "working_frame",
}
OUTPUT_ROLES = {
    "editable_source",
    "engine_delivery",
    "frame_manifest",
    "preview",
    "audit",
}
RESULTS = {"pass", "fail", "not_tested", "not_applicable"}
EVIDENCE_DOMAINS = (
    "artifact",
    "visual_native_scale",
    "visual_gameplay_scale",
    "animation",
    "tileset_or_ui",
    "engine_import",
)

TOP_LEVEL_KEYS = {
    "schema_version",
    "job",
    "sources",
    "outputs",
    "implementation",
    "evidence",
    "gates",
    "modifications",
    "limitations",
    "next_owner",
    "next_action",
}
JOB_KEYS = {"id", "status", "contract_path"}
SOURCE_KEYS = {
    "path",
    "role",
    "sha256",
    "creator",
    "source_url",
    "license",
    "generation_provenance",
}
OUTPUT_KEYS = {"path", "role", "sha256"}
IMPLEMENTATION_KEYS = {
    "tool",
    "version",
    "command_or_action",
    "processing_contract",
}
EVIDENCE_KEYS = {"id", "path", "sha256", "description"}
ENGINE_EVIDENCE_KEYS = EVIDENCE_KEYS | {
    "engine_delivery_path",
    "engine_delivery_sha256",
    "project_revision",
}
GATE_KEYS = {"id", "required", "result", "evidence", "reason"}
AUDIT_KEYS = {"artifact", "checks", "operation", "schema_version", "tool", "verdict"}
AUDIT_TOOL_KEYS = {"name", "version"}
AUDIT_ARTIFACT_KEYS = {"manifest_sha256", "png", "png_sha256"}
AUDIT_PNG_KEYS = {
    "alpha",
    "binding_sha256",
    "format",
    "mode",
    "palette_color_count_visible",
    "rgba_sha256",
    "size_px",
}
AUDIT_ALPHA_KEYS = {
    "fully_opaque_pixels",
    "fully_transparent_pixels",
    "partially_transparent_pixels",
}
AUDIT_CHECK_KEYS = {"id", "observed", "result"}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader which refuses silently overwritten mapping keys."""

    def compose_node(self, parent: Any, index: Any) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise yaml.composer.ComposerError(
                None,
                None,
                "YAML aliases are not allowed in a production receipt",
                event.start_mark,
            )
        return super().compose_node(parent, index)


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _problem(problems: list[dict[str, Any]], code: str, message: str, **context: Any) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if context:
        item["context"] = context
    problems.append(item)


def _check_keys(
    value: Any,
    expected: set[str],
    location: str,
    problems: list[dict[str, Any]],
) -> bool:
    if not isinstance(value, dict):
        _problem(problems, "SCHEMA_TYPE_INVALID", "Expected a mapping", location=location)
        return False
    actual = set(value)
    non_string = [repr(key) for key in actual if not isinstance(key, str)]
    if non_string:
        _problem(
            problems,
            "SCHEMA_KEY_INVALID",
            "Mapping keys must be strings",
            location=location,
            keys=sorted(non_string),
        )
    missing = sorted(expected - actual)
    unknown = sorted(str(key) for key in actual - expected)
    if missing:
        _problem(
            problems,
            "SCHEMA_KEYS_MISSING",
            "Required keys are missing",
            location=location,
            keys=missing,
        )
    if unknown:
        _problem(
            problems,
            "SCHEMA_KEYS_UNKNOWN",
            "Unknown keys are not allowed",
            location=location,
            keys=unknown,
        )
    return not missing and not unknown and not non_string


def _nonempty_string(
    value: Any, location: str, problems: list[dict[str, Any]]
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        _problem(
            problems,
            "STRING_REQUIRED",
            "Expected a non-empty string",
            location=location,
        )
        return None
    return value


def _string(value: Any, location: str, problems: list[dict[str, Any]]) -> str | None:
    if not isinstance(value, str):
        _problem(problems, "STRING_INVALID", "Expected a string", location=location)
        return None
    return value


def _sha(value: Any, location: str, problems: list[dict[str, Any]]) -> str | None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _problem(
            problems,
            "SHA256_INVALID",
            "Expected a lowercase 64-character SHA-256",
            location=location,
        )
        return None
    return value


def _portable_path(
    value: Any, location: str, problems: list[dict[str, Any]]
) -> str | None:
    if not isinstance(value, str) or not value:
        _problem(problems, "PATH_INVALID", "Expected a non-empty portable path", location=location)
        return None
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if (
        "\x00" in value
        or "\\" in value
        or value.startswith("//")
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        _problem(
            problems,
            "PATH_NOT_PORTABLE",
            "Path must be a normalized provenance-root-relative POSIX path",
            location=location,
            path=value,
        )
        return None
    return value


def _path_identity(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


def _resolve_confined(
    root: Path, value: str, location: str, problems: list[dict[str, Any]]
) -> Path | None:
    candidate = root.joinpath(*PurePosixPath(value).parts)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        _problem(
            problems,
            "PATH_ESCAPES_ROOT",
            "Resolved path escapes the provenance root",
            location=location,
            path=value,
        )
        return None
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> tuple[object, ...]:
    """Return a stable identity which also catches hard-link aliases."""
    facts = path.stat()
    if facts.st_ino:
        return ("inode", int(facts.st_dev), int(facts.st_ino))
    return ("path", str(path))


def _load_strict_json(
    encoded: bytes,
    location: str,
    label: str,
    problems: list[dict[str, Any]],
) -> Any | None:
    try:
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate key {key!r}")
                result[key] = value
            return result

        return json.loads(encoded.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        _problem(
            problems,
            f"{label.upper()}_PARSE_INVALID",
            f"{label} must be one strict UTF-8 JSON document",
            location=location,
            error=str(error),
        )
        return None


def _expected_audit_check_ids(
    manifest: Any, problems: list[dict[str, Any]]
) -> set[str] | None:
    """Derive the complete passing check inventory for one bound manifest."""
    location = "outputs[role=frame_manifest]"
    if not isinstance(manifest, dict):
        _problem(
            problems,
            "AUDIT_MANIFEST_SCHEMA_INVALID",
            "Frame manifest root must be an object",
            location=location,
        )
        return None
    operation = manifest.get("operation")
    contract = manifest.get("contract")
    processing = contract.get("processing") if isinstance(contract, dict) else None
    if operation not in {"build", "pixelize"} or not isinstance(processing, dict):
        _problem(
            problems,
            "AUDIT_MANIFEST_SCHEMA_INVALID",
            "Frame manifest must declare a supported operation and processing contract",
            location=location,
        )
        return None

    expected = {
        "schema.version",
        "schema.tool",
        "schema.operation",
        "schema.top_level",
        "artifact.record",
        "artifact.schema",
        "artifact.path",
        "artifact.path_confined",
        "artifact.path_binding",
        "artifact.sha256",
        "artifact.rgba_sha256",
        "artifact.binding",
        "artifact.size",
        "artifact.format",
        "artifact.mode",
        "artifact.palette",
        "artifact.alpha",
        "contract.record",
        "contract.schema",
        "contract.processing_schema",
        "contract.processing_values",
    }
    if processing.get("palette") != "none":
        expected.add("artifact.palette_budget")
    if "preview" in manifest:
        expected.update(
            {
                "preview.schema",
                "preview.path_binding",
                "preview.contract_size",
                "preview.exists",
                "preview.sha256",
                "preview.format",
                "preview.mode",
                "preview.content",
                "preview.size",
            }
        )
    if operation == "pixelize":
        expected.update({"source.record", "sprite.record", "pixelize.frame_size"})
        return expected

    frames = manifest.get("frames")
    if not isinstance(frames, list) or not frames:
        _problem(
            problems,
            "AUDIT_MANIFEST_SCHEMA_INVALID",
            "Build manifest must contain at least one frame",
            location=f"{location}.frames",
        )
        return None
    expected.update(
        {
            "layout.frames",
            "layout.record",
            "layout.frame_count",
            "layout.values",
            "layout.sheet_size",
            "layout.no_overlap",
            "layout.transparent_gutters",
        }
    )
    for index in range(len(frames)):
        expected.update(
            {
                f"frame.{index}.schema",
                f"frame.{index}.id",
                f"frame.{index}.duration",
                f"frame.{index}.state",
                f"frame.{index}.direction",
                f"frame.{index}.pivot",
                f"frame.{index}.source",
                f"frame.{index}.rect",
                f"frame.{index}.grid",
                f"frame.{index}.rgba_sha256",
            }
        )
    return expected


def _validate_audit_output(
    audit_bytes: bytes,
    manifest_bytes: bytes,
    expected_manifest_sha: str,
    expected_delivery_sha: str,
    problems: list[dict[str, Any]],
) -> None:
    """Validate the trusted pipeline audit and bind it to receipt outputs."""
    location = "outputs[role=audit]"
    audit = _load_strict_json(audit_bytes, location, "audit", problems)
    if audit is None or not _check_keys(audit, AUDIT_KEYS, location, problems):
        return
    manifest = _load_strict_json(
        manifest_bytes,
        "outputs[role=frame_manifest]",
        "audit_manifest",
        problems,
    )
    expected_check_ids = (
        _expected_audit_check_ids(manifest, problems) if manifest is not None else None
    )

    if type(audit["schema_version"]) is not int or audit["schema_version"] != 1:
        _problem(
            problems,
            "AUDIT_SCHEMA_VERSION_INVALID",
            "Audit schema_version must be integer 1",
            location=f"{location}.schema_version",
        )
    if audit["operation"] != "audit":
        _problem(
            problems,
            "AUDIT_OPERATION_INVALID",
            "Audit operation must be audit",
            location=f"{location}.operation",
        )

    tool = audit["tool"]
    if _check_keys(tool, AUDIT_TOOL_KEYS, f"{location}.tool", problems):
        if tool["name"] != "create-2d-game-art.sprite-pipeline" or tool["version"] != "1.0.0":
            _problem(
                problems,
                "AUDIT_TOOL_INVALID",
                "Audit must come from the trusted sprite pipeline version",
                location=f"{location}.tool",
                actual=_json_safe(tool),
            )

    artifact = audit["artifact"]
    if _check_keys(artifact, AUDIT_ARTIFACT_KEYS, f"{location}.artifact", problems):
        manifest_sha = _sha(
            artifact["manifest_sha256"],
            f"{location}.artifact.manifest_sha256",
            problems,
        )
        delivery_sha = _sha(
            artifact["png_sha256"],
            f"{location}.artifact.png_sha256",
            problems,
        )
        if manifest_sha is not None and manifest_sha != expected_manifest_sha:
            _problem(
                problems,
                "AUDIT_MANIFEST_BINDING_MISMATCH",
                "Audit must bind the exact frame_manifest SHA-256",
                expected=expected_manifest_sha,
                actual=manifest_sha,
            )
        if delivery_sha is not None and delivery_sha != expected_delivery_sha:
            _problem(
                problems,
                "AUDIT_ENGINE_DELIVERY_BINDING_MISMATCH",
                "Audit must bind the exact engine_delivery SHA-256",
                expected=expected_delivery_sha,
                actual=delivery_sha,
            )

        png = artifact["png"]
        if _check_keys(png, AUDIT_PNG_KEYS, f"{location}.artifact.png", problems):
            if png["format"] != "PNG":
                _problem(problems, "AUDIT_PNG_FORMAT_INVALID", "Audited artifact format must be PNG")
            if png["mode"] != "RGBA":
                _problem(problems, "AUDIT_PNG_MODE_INVALID", "Audited artifact mode must be RGBA")
            _sha(png["binding_sha256"], f"{location}.artifact.png.binding_sha256", problems)
            _sha(png["rgba_sha256"], f"{location}.artifact.png.rgba_sha256", problems)
            palette_count = png["palette_color_count_visible"]
            if type(palette_count) is not int or palette_count < 0:
                _problem(
                    problems,
                    "AUDIT_PNG_PALETTE_INVALID",
                    "Audited palette count must be a non-negative integer",
                )
            size = png["size_px"]
            if (
                not isinstance(size, list)
                or len(size) != 2
                or any(type(value) is not int or value <= 0 for value in size)
            ):
                _problem(
                    problems,
                    "AUDIT_PNG_SIZE_INVALID",
                    "Audited PNG size must contain two positive integers",
                )
            alpha = png["alpha"]
            if _check_keys(alpha, AUDIT_ALPHA_KEYS, f"{location}.artifact.png.alpha", problems):
                if any(type(alpha[key]) is not int or alpha[key] < 0 for key in AUDIT_ALPHA_KEYS):
                    _problem(
                        problems,
                        "AUDIT_PNG_ALPHA_INVALID",
                        "Audited alpha counts must be non-negative integers",
                    )

    checks = audit["checks"]
    check_ids: set[str] = set()
    check_identities: set[str] = set()
    checks_pass = isinstance(checks, list) and bool(checks)
    if not isinstance(checks, list) or not checks:
        _problem(
            problems,
            "AUDIT_CHECKS_INVALID",
            "Audit checks must be a non-empty list",
            location=f"{location}.checks",
        )
    else:
        for index, check in enumerate(checks):
            check_location = f"{location}.checks[{index}]"
            if not _check_keys(check, AUDIT_CHECK_KEYS, check_location, problems):
                checks_pass = False
                continue
            identifier = _nonempty_string(check["id"], f"{check_location}.id", problems)
            if identifier is not None:
                identity = unicodedata.normalize("NFC", identifier).casefold()
                if identity in check_identities:
                    _problem(
                        problems,
                        "AUDIT_CHECK_ID_DUPLICATE",
                        "Audit check IDs must be unique",
                        id=identifier,
                    )
                    checks_pass = False
                check_identities.add(identity)
                check_ids.add(identifier)
            if check["result"] != "pass":
                _problem(
                    problems,
                    "AUDIT_CHECK_FAILED",
                    "Every structural audit check must pass",
                    id=identifier,
                    actual=check["result"],
                )
                checks_pass = False
            _json_compatible(check["observed"], f"{check_location}.observed", problems)

    if expected_check_ids is not None and check_ids != expected_check_ids:
        _problem(
            problems,
            "AUDIT_CHECK_INVENTORY_MISMATCH",
            "Audit checks must exactly match the complete operation-specific inventory",
            missing=sorted(expected_check_ids - check_ids),
            unexpected=sorted(check_ids - expected_check_ids),
        )
        checks_pass = False

    expected_verdict = "pass" if checks_pass else "fail"
    if audit["verdict"] != expected_verdict:
        _problem(
            problems,
            "AUDIT_VERDICT_INCONSISTENT",
            "Audit verdict must be derived from its checks",
            expected=expected_verdict,
            actual=audit["verdict"],
        )
    if audit["verdict"] != "pass":
        _problem(
            problems,
            "AUDIT_VERDICT_NOT_PASS",
            "The required structural audit must pass",
            actual=audit["verdict"],
        )


def _verify_file(
    root: Path,
    value: str,
    expected_sha: str,
    location: str,
    problems: list[dict[str, Any]],
    cache: dict[Path, str],
) -> Path | None:
    path = _resolve_confined(root, value, location, problems)
    if path is None:
        return None
    if not path.is_file():
        _problem(
            problems,
            "FILE_MISSING",
            "Referenced file does not exist",
            location=location,
            path=value,
        )
        return None
    try:
        if path in cache:
            actual = cache[path]
        else:
            actual = _file_sha256(path)
            cache[path] = actual
    except OSError as error:
        _problem(
            problems,
            "FILE_UNREADABLE",
            "Referenced file could not be hashed",
            location=location,
            path=value,
            error=str(error),
        )
        return None
    if actual != expected_sha:
        _problem(
            problems,
            "FILE_HASH_MISMATCH",
            "Referenced file does not match its SHA-256",
            location=location,
            path=value,
            expected=expected_sha,
            actual=actual,
        )
        return None
    return path


def _verify_file_snapshot(
    root: Path,
    value: str,
    expected_sha: str,
    location: str,
    label: str,
    maximum: int,
    problems: list[dict[str, Any]],
    cache: dict[Path, str],
) -> tuple[Path, bytes] | None:
    """Verify and return the exact bounded bytes used by semantic validation."""
    path = _resolve_confined(root, value, location, problems)
    if path is None:
        return None
    if not path.is_file():
        _problem(
            problems,
            "FILE_MISSING",
            "Referenced file does not exist",
            location=location,
            path=value,
        )
        return None
    try:
        with path.open("rb") as stream:
            encoded = stream.read(maximum + 1)
    except OSError as error:
        _problem(
            problems,
            "FILE_UNREADABLE",
            "Referenced file could not be read",
            location=location,
            path=value,
            error=str(error),
        )
        return None
    if len(encoded) > maximum:
        _problem(
            problems,
            "FILE_TOO_LARGE",
            f"{label} exceeds the bounded byte limit",
            location=location,
            path=value,
        )
        return None
    actual = hashlib.sha256(encoded).hexdigest()
    cache[path] = actual
    if actual != expected_sha:
        _problem(
            problems,
            "FILE_HASH_MISMATCH",
            "Referenced file does not match its SHA-256",
            location=location,
            path=value,
            expected=expected_sha,
            actual=actual,
        )
        return None
    return path, encoded


def _json_compatible(value: Any, location: str, problems: list[dict[str, Any]]) -> None:
    if value is None or isinstance(value, (str, bool)) or type(value) is int:
        return
    if type(value) is float:
        if value != value or value in {float("inf"), float("-inf")}:
            _problem(problems, "VALUE_NOT_FINITE", "Numbers must be finite", location=location)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_compatible(item, f"{location}[{index}]", problems)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _problem(problems, "SCHEMA_KEY_INVALID", "Mapping keys must be strings", location=location)
            else:
                _json_compatible(item, f"{location}.{key}", problems)
        return
    _problem(
        problems,
        "VALUE_TYPE_INVALID",
        "Value must be JSON-compatible",
        location=location,
        actual_type=type(value).__name__,
    )


def _validate_string_list(value: Any, location: str, problems: list[dict[str, Any]]) -> None:
    if not isinstance(value, list):
        _problem(problems, "SCHEMA_TYPE_INVALID", "Expected a list", location=location)
        return
    for index, item in enumerate(value):
        _nonempty_string(item, f"{location}[{index}]", problems)


def _validate_receipt(data: Any, provenance_root: Path) -> dict[str, Any]:
    problems: list[dict[str, Any]] = []
    file_cache: dict[Path, str] = {}
    if not _check_keys(data, TOP_LEVEL_KEYS, "$", problems):
        return _report(data, problems, None)

    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        _problem(
            problems,
            "SCHEMA_VERSION_INVALID",
            "schema_version must be integer 1",
            actual=data["schema_version"],
        )

    job = data["job"]
    declared_status: str | None = None
    if _check_keys(job, JOB_KEYS, "job", problems):
        _nonempty_string(job["id"], "job.id", problems)
        if not isinstance(job["status"], str) or job["status"] not in STATUSES:
            _problem(
                problems,
                "STATUS_INVALID",
                "job.status is not an allowed status",
                actual=job["status"],
                allowed=sorted(STATUSES),
            )
        elif isinstance(job["status"], str):
            declared_status = job["status"]
        _portable_path(job["contract_path"], "job.contract_path", problems)

    sources = data["sources"]
    if not isinstance(sources, list):
        _problem(problems, "SCHEMA_TYPE_INVALID", "Expected a list", location="sources")
        sources = []
    source_paths: set[str] = set()
    source_files: set[tuple[object, ...]] = set()
    for index, entry in enumerate(sources):
        location = f"sources[{index}]"
        if not _check_keys(entry, SOURCE_KEYS, location, problems):
            continue
        path = _portable_path(entry["path"], f"{location}.path", problems)
        digest = _sha(entry["sha256"], f"{location}.sha256", problems)
        if not isinstance(entry["role"], str) or entry["role"] not in SOURCE_ROLES:
            _problem(problems, "SOURCE_ROLE_INVALID", "Unknown source role", location=location, actual=entry["role"])
        for field in ("creator", "source_url", "license", "generation_provenance"):
            _string(entry[field], f"{location}.{field}", problems)
        if path is not None:
            identity = _path_identity(path)
            if identity in source_paths:
                _problem(problems, "SOURCE_PATH_DUPLICATE", "Source paths must be portable-unique", path=path)
            source_paths.add(identity)
        if path is not None and digest is not None:
            verified = _verify_file(provenance_root, path, digest, location, problems, file_cache)
            if verified is not None:
                file_identity = _file_identity(verified)
                if file_identity in source_files:
                    _problem(problems, "SOURCE_FILE_ALIAS", "Two source paths resolve to the same file", path=path)
                source_files.add(file_identity)

    outputs = data["outputs"]
    if not isinstance(outputs, list):
        _problem(problems, "SCHEMA_TYPE_INVALID", "Expected a list", location="outputs")
        outputs = []
    output_paths: set[str] = set()
    output_files: set[tuple[object, ...]] = set()
    verified_output_bytes_by_role: dict[str, bytes] = {}
    output_by_role: dict[str, list[dict[str, Any]]] = {}
    for index, entry in enumerate(outputs):
        location = f"outputs[{index}]"
        if not _check_keys(entry, OUTPUT_KEYS, location, problems):
            continue
        path = _portable_path(entry["path"], f"{location}.path", problems)
        digest = _sha(entry["sha256"], f"{location}.sha256", problems)
        role = entry["role"]
        if not isinstance(role, str) or role not in OUTPUT_ROLES:
            _problem(problems, "OUTPUT_ROLE_INVALID", "Unknown output role", location=location, actual=role)
        else:
            output_by_role.setdefault(role, []).append(entry)
        if path is not None:
            identity = _path_identity(path)
            if identity in output_paths:
                _problem(problems, "OUTPUT_PATH_DUPLICATE", "Output paths must be portable-unique", path=path)
            if identity in source_paths:
                _problem(
                    problems,
                    "SOURCE_OUTPUT_PATH_ALIAS",
                    "Source and output paths must be distinct",
                    path=path,
                )
            output_paths.add(identity)
        if path is not None and digest is not None:
            snapshot_limit = {
                "audit": MAX_AUDIT_BYTES,
                "frame_manifest": MAX_FRAME_MANIFEST_BYTES,
            }.get(role)
            if snapshot_limit is None:
                verified = _verify_file(
                    provenance_root, path, digest, location, problems, file_cache
                )
                snapshot = None
            else:
                verified_snapshot = _verify_file_snapshot(
                    provenance_root,
                    path,
                    digest,
                    location,
                    f"{role} output",
                    snapshot_limit,
                    problems,
                    file_cache,
                )
                verified, snapshot = (
                    verified_snapshot if verified_snapshot is not None else (None, None)
                )
            if verified is not None:
                file_identity = _file_identity(verified)
                if file_identity in output_files:
                    _problem(problems, "OUTPUT_FILE_ALIAS", "Two output paths resolve to the same file", path=path)
                if file_identity in source_files:
                    _problem(
                        problems,
                        "SOURCE_OUTPUT_FILE_ALIAS",
                        "A source and output resolve to the same file",
                        path=path,
                    )
                output_files.add(file_identity)
                if isinstance(role, str) and role in OUTPUT_ROLES:
                    if snapshot is not None:
                        verified_output_bytes_by_role[role] = snapshot
    for role in ("engine_delivery", "frame_manifest", "audit"):
        count = len(output_by_role.get(role, []))
        if count != 1:
            _problem(
                problems,
                "OUTPUT_ROLE_CARDINALITY_INVALID",
                "Exactly one required output role must be declared",
                role=role,
                actual=count,
            )

    deliveries = output_by_role.get("engine_delivery", [])
    manifests = output_by_role.get("frame_manifest", [])
    audits = output_by_role.get("audit", [])
    if (
        len(deliveries) == 1
        and len(manifests) == 1
        and len(audits) == 1
        and "audit" in verified_output_bytes_by_role
        and "frame_manifest" in verified_output_bytes_by_role
        and isinstance(deliveries[0].get("sha256"), str)
        and isinstance(manifests[0].get("sha256"), str)
        and SHA256_RE.fullmatch(deliveries[0]["sha256"]) is not None
        and SHA256_RE.fullmatch(manifests[0]["sha256"]) is not None
    ):
        _validate_audit_output(
            verified_output_bytes_by_role["audit"],
            verified_output_bytes_by_role["frame_manifest"],
            manifests[0]["sha256"],
            deliveries[0]["sha256"],
            problems,
        )

    implementation = data["implementation"]
    if _check_keys(implementation, IMPLEMENTATION_KEYS, "implementation", problems):
        if implementation["tool"] != "create-2d-game-art.sprite-pipeline":
            _problem(
                problems,
                "IMPLEMENTATION_TOOL_INVALID",
                "implementation.tool must name the trusted sprite pipeline",
                actual=implementation["tool"],
            )
        _nonempty_string(implementation["version"], "implementation.version", problems)
        _nonempty_string(implementation["command_or_action"], "implementation.command_or_action", problems)
        if not isinstance(implementation["processing_contract"], dict):
            _problem(
                problems,
                "SCHEMA_TYPE_INVALID",
                "processing_contract must be a mapping",
                location="implementation.processing_contract",
            )
        else:
            _json_compatible(implementation["processing_contract"], "implementation.processing_contract", problems)

    evidence = data["evidence"]
    evidence_refs: set[str] = set()
    engine_entries: list[dict[str, Any]] = []
    if _check_keys(evidence, set(EVIDENCE_DOMAINS), "evidence", problems):
        for domain in EVIDENCE_DOMAINS:
            entries = evidence[domain]
            if not isinstance(entries, list):
                _problem(problems, "SCHEMA_TYPE_INVALID", "Evidence domain must be a list", location=f"evidence.{domain}")
                continue
            domain_ids: set[str] = set()
            for index, entry in enumerate(entries):
                location = f"evidence.{domain}[{index}]"
                expected = ENGINE_EVIDENCE_KEYS if domain == "engine_import" else EVIDENCE_KEYS
                if not _check_keys(entry, expected, location, problems):
                    continue
                identifier = _nonempty_string(entry["id"], f"{location}.id", problems)
                path = _portable_path(entry["path"], f"{location}.path", problems)
                digest = _sha(entry["sha256"], f"{location}.sha256", problems)
                _nonempty_string(entry["description"], f"{location}.description", problems)
                if identifier is not None:
                    identity = unicodedata.normalize("NFC", identifier).casefold()
                    if identity in domain_ids:
                        _problem(problems, "EVIDENCE_ID_DUPLICATE", "Evidence IDs must be unique within a domain", domain=domain, id=identifier)
                    domain_ids.add(identity)
                    evidence_refs.add(f"{domain}:{identifier}")
                if path is not None and digest is not None:
                    _verify_file(provenance_root, path, digest, location, problems, file_cache)
                if domain == "engine_import":
                    engine_entries.append(entry)
                    delivery_path = _portable_path(
                        entry["engine_delivery_path"],
                        f"{location}.engine_delivery_path",
                        problems,
                    )
                    delivery_sha = _sha(
                        entry["engine_delivery_sha256"],
                        f"{location}.engine_delivery_sha256",
                        problems,
                    )
                    _nonempty_string(entry["project_revision"], f"{location}.project_revision", problems)
                    deliveries = output_by_role.get("engine_delivery", [])
                    if len(deliveries) == 1 and (delivery_path is not None and delivery_sha is not None):
                        expected_delivery = deliveries[0]
                        if (
                            delivery_path != expected_delivery.get("path")
                            or delivery_sha != expected_delivery.get("sha256")
                        ):
                            _problem(
                                problems,
                                "ENGINE_DELIVERY_BINDING_MISMATCH",
                                "Engine evidence must bind the exact engine_delivery path and SHA-256",
                                location=location,
                            )

    gates = data["gates"]
    parsed_gates: list[dict[str, Any]] = []
    if not isinstance(gates, list) or not gates:
        _problem(problems, "GATES_INVALID", "gates must be a non-empty list", location="gates")
        gates = []
    gate_ids: set[str] = set()
    for index, gate in enumerate(gates):
        location = f"gates[{index}]"
        if not _check_keys(gate, GATE_KEYS, location, problems):
            continue
        parsed_gates.append(gate)
        identifier = _nonempty_string(gate["id"], f"{location}.id", problems)
        if identifier is not None:
            identity = unicodedata.normalize("NFC", identifier).casefold()
            if identity in gate_ids:
                _problem(problems, "GATE_ID_DUPLICATE", "Gate IDs must be unique", id=identifier)
            gate_ids.add(identity)
        if type(gate["required"]) is not bool:
            _problem(problems, "GATE_REQUIRED_INVALID", "Gate required must be a boolean", id=identifier)
        result = gate["result"]
        if not isinstance(result, str) or result not in RESULTS:
            _problem(problems, "GATE_RESULT_INVALID", "Gate result is not allowed", id=identifier, actual=result)
        refs = gate["evidence"]
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            _problem(problems, "GATE_EVIDENCE_INVALID", "Gate evidence must be a list of non-empty domain:id references", id=identifier)
            refs = []
        else:
            if len(refs) != len(set(refs)):
                _problem(problems, "GATE_EVIDENCE_DUPLICATE", "Gate evidence references must be unique", id=identifier)
            for ref in refs:
                if ref not in evidence_refs:
                    _problem(problems, "GATE_EVIDENCE_UNKNOWN", "Gate evidence reference does not exist", id=identifier, evidence=ref)
        reason = gate["reason"]
        if not isinstance(reason, str):
            _problem(problems, "GATE_REASON_INVALID", "Gate reason must be a string", id=identifier)
        if result in {"pass", "fail"} and not refs:
            _problem(problems, "GATE_EVIDENCE_REQUIRED", "A pass or fail gate must cite evidence", id=identifier)
        if result in {"not_tested", "not_applicable"} and (
            not isinstance(reason, str) or not reason.strip()
        ):
            _problem(problems, "GATE_REASON_REQUIRED", "An untested or not-applicable gate must state a reason", id=identifier)
        if gate["required"] is True and result == "not_applicable":
            _problem(problems, "REQUIRED_GATE_NOT_APPLICABLE", "A required gate cannot be not_applicable", id=identifier)

    _validate_string_list(data["modifications"], "modifications", problems)
    _validate_string_list(data["limitations"], "limitations", problems)
    _nonempty_string(data["next_owner"], "next_owner", problems)
    _nonempty_string(data["next_action"], "next_action", problems)

    any_fail = any(gate.get("result") == "fail" for gate in parsed_gates)
    blocker = any(
        gate.get("required") is True
        and gate.get("result") == "not_tested"
        and isinstance(gate.get("id"), str)
        and gate["id"].startswith("blocker.")
        for gate in parsed_gates
    )
    required_gates = [gate for gate in parsed_gates if gate.get("required") is True]
    all_required_pass = bool(required_gates) and all(
        gate.get("result") == "pass" for gate in required_gates
    )
    engine_pass = any(
        gate.get("required") is True
        and gate.get("result") == "pass"
        and isinstance(gate.get("id"), str)
        and gate["id"].startswith("engine.")
        and any(
            isinstance(ref, str) and ref.startswith("engine_import:")
            for ref in gate.get("evidence", [])
        )
        for gate in parsed_gates
    )
    if any_fail:
        reduced_status = "failed"
    elif blocker:
        reduced_status = "blocked"
    elif all_required_pass and engine_entries and engine_pass:
        reduced_status = "validated"
    else:
        reduced_status = "prototype"

    if declared_status is not None and declared_status != reduced_status:
        _problem(
            problems,
            "STATUS_REDUCTION_MISMATCH",
            "Declared status does not match deterministic gate/evidence reduction",
            declared=declared_status,
            reduced=reduced_status,
        )
    return _report(data, problems, reduced_status)


def _report(data: Any, problems: list[dict[str, Any]], reduced_status: str | None) -> dict[str, Any]:
    declared = None
    if isinstance(data, dict) and isinstance(data.get("job"), dict):
        declared = data["job"].get("status")
    return {
        "schema_version": SCHEMA_VERSION,
        "validation_verdict": "fail" if problems else "pass",
        "declared_status": _json_safe(declared),
        "reduced_status": reduced_status,
        "problem_count": len(problems),
        "problems": _json_safe(problems),
    }


def validate(receipt: Path, provenance_root: Path | None = None) -> dict[str, Any]:
    """Load and validate one receipt. Syntax failures are validation problems."""
    root = (provenance_root or receipt.parent).resolve()
    if not root.is_dir():
        raise ValueError(f"Provenance root is not a directory: {root}")
    try:
        raw = receipt.read_bytes()
    except OSError as error:
        raise ValueError(f"Receipt is not readable: {receipt}: {error}") from error
    if len(raw) > MAX_RECEIPT_BYTES:
        return _report(None, [{"code": "RECEIPT_TOO_LARGE", "message": "Receipt exceeds the size limit"}], None)
    try:
        text = raw.decode("utf-8")
        data = yaml.load(text, Loader=UniqueKeyLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        return _report(
            None,
            [{"code": "RECEIPT_PARSE_INVALID", "message": "Receipt is not valid single-document UTF-8 YAML/JSON", "context": {"error": str(error)}}],
            None,
        )
    return _validate_receipt(data, root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument(
        "--provenance-root",
        type=Path,
        help="Root for all portable receipt paths (default: receipt directory)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        report = validate(args.receipt.resolve(), args.provenance_root)
        report["receipt"] = str(args.receipt.resolve())
        if args.receipt.is_file():
            report["receipt_sha256"] = _file_sha256(args.receipt.resolve())
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["validation_verdict"] == "pass" else 2
    except (OSError, ValueError) as error:
        print(f"CREATE_2D_RECEIPT_ERROR={error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
