#!/usr/bin/env python3
"""Build and persist the validated AutoTA Codex link contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import tomllib
from typing import Any


PRODUCT = "autota"
RECEIPT_SCHEMA_VERSION = 1
SAFE_NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class ContractError(RuntimeError):
    pass


def _absolute_lexical(path: Path) -> Path:
    """Normalize a user path without following any symlink or reparse point."""

    return Path(os.path.abspath(path.expanduser()))


def _load_validator(root: Path):
    path = root / "scripts" / "validate_bundle.py"
    spec = importlib.util.spec_from_file_location("autota_validate_bundle", path)
    if spec is None or spec.loader is None:
        raise ContractError(f"Cannot load bundle validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _path_under(base: Path, relative: str, label: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ContractError(f"{label} must be a non-empty relative path")
    candidate = Path(os.path.abspath(base / relative))
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ContractError(f"{label} escapes CODEX_HOME: {relative}") from exc
    return candidate


def _is_reparse_point(path: Path) -> bool:
    """Detect symlinks and Windows reparse points without following them."""

    try:
        metadata = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(metadata, "st_file_attributes", 0) & reparse_flag)


def preflight_receipt_path(path: Path, codex_home: Path) -> None:
    """Fail before link mutation if receipt storage is not a real local path."""

    canonical_home = _absolute_lexical(codex_home)
    expected = canonical_home / "state" / "autota" / "install-receipt.json"
    candidate = _absolute_lexical(path)
    if not _same_path(candidate, expected):
        raise ContractError(f"Unexpected install receipt path: {path}")

    for parent in (canonical_home / "state", canonical_home / "state" / "autota"):
        if not os.path.lexists(parent):
            continue
        if _is_reparse_point(parent):
            raise ContractError(
                f"Install receipt parent must not be a symlink or reparse point: {parent}"
            )
        if not parent.is_dir():
            raise ContractError(f"Install receipt parent is not a directory: {parent}")

    if os.path.lexists(candidate):
        if _is_reparse_point(candidate):
            raise ContractError(
                f"Install receipt must not be a symlink or reparse point: {candidate}"
            )
        if not candidate.is_file():
            raise ContractError(f"Install receipt path is not a regular file: {candidate}")


def preflight_managed_destination_ancestors(
    entries: list[dict[str, str]], codex_home: Path
) -> None:
    """Reject ancestor redirection before stale cleanup or link mutation."""

    canonical_home = _absolute_lexical(codex_home)
    ancestors: set[Path] = {canonical_home}
    for entry in entries:
        destination = _absolute_lexical(Path(entry["destination"]))
        try:
            destination.relative_to(canonical_home)
        except ValueError as exc:
            raise ContractError(
                f"Managed destination escapes CODEX_HOME: {destination}"
            ) from exc
        current = destination.parent
        while True:
            ancestors.add(current)
            if _same_path(current, canonical_home):
                break
            parent = current.parent
            if _same_path(parent, current):
                raise ContractError(
                    f"Managed destination is not lexically below CODEX_HOME: {destination}"
                )
            current = parent

    for ancestor in sorted(ancestors, key=lambda item: len(item.parts)):
        if not os.path.lexists(ancestor):
            continue
        if _is_reparse_point(ancestor):
            raise ContractError(
                "Managed destination parent must not be a symlink or reparse "
                f"point: {ancestor}"
            )
        if not ancestor.is_dir():
            raise ContractError(
                f"Managed destination parent is not a directory: {ancestor}"
            )


def build_inventory(root: Path, codex_home: Path) -> dict[str, Any]:
    root = root.expanduser().resolve(strict=True)
    codex_home = _absolute_lexical(codex_home)
    if root == codex_home or root in codex_home.parents or codex_home in root.parents:
        raise ContractError(
            "CODEX_HOME and the AutoTA repository must not overlap; "
            "the product-root link would be recursive or ambiguously owned"
        )
    errors = _load_validator(root).validate(root)
    if errors:
        raise ContractError("Bundle validation failed before linking:\n" + "\n".join(errors))
    with (root / "workflow.bundle.toml").open("rb") as handle:
        manifest = tomllib.load(handle)
    link = manifest["link"]
    entries: list[dict[str, str]] = []

    def append(source: Path, destination: Path, kind: str, inventory_id: str) -> None:
        entries.append(
            {
                "inventory_id": inventory_id,
                "source": str(source.resolve(strict=True)),
                "destination": str(destination),
                "kind": kind,
            }
        )

    for skill in manifest["skills"]:
        source = root / skill["path"]
        destination = _path_under(
            codex_home,
            f"{link['skills_destination']}/{skill['name']}",
            f"skills[{skill['name']}].destination",
        )
        append(source, destination, "directory", f"skill:{skill['name']}")

    for agent in manifest["agents"]:
        source = root / agent["path"]
        destination = _path_under(
            codex_home,
            f"{link['agents_destination']}/{source.name}",
            f"agents[{agent['name']}].destination",
        )
        append(source, destination, "file", f"agent:{agent['name']}")

    product_destination = _path_under(
        codex_home, link["product_destination"], "link.product_destination"
    )
    append(root, product_destination, "directory", "product-root:autota")

    destinations = [entry["destination"] for entry in entries]
    if len(destinations) != len(set(destinations)):
        raise ContractError("Manifest link inventory contains duplicate destinations")
    receipt_path = _path_under(
        codex_home, link["receipt_destination"], "link.receipt_destination"
    )
    if str(receipt_path) in set(destinations):
        raise ContractError("Install receipt cannot overlap a managed link destination")
    preflight_managed_destination_ancestors(entries, codex_home)
    preflight_receipt_path(receipt_path, codex_home)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "product": PRODUCT,
        "repository_root": str(root),
        "codex_home": str(codex_home),
        "receipt_path": str(receipt_path),
        "entries": entries,
    }


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.fspath(left)) == os.path.normcase(os.fspath(right))


def _validate_receipt_entry(
    entry: Any, codex_home: Path, repository_root: Path
) -> dict[str, str]:
    if not isinstance(entry, dict):
        raise ContractError("Install receipt entry must be an object")
    required = {"inventory_id", "source", "destination", "kind", "link_type"}
    if set(entry) != required or not all(isinstance(entry[key], str) for key in required):
        raise ContractError(
            "Install receipt entries must contain exactly inventory_id, source, "
            "destination, kind, and link_type strings"
        )
    if entry["kind"] not in {"directory", "file"}:
        raise ContractError(f"Invalid receipt kind: {entry['kind']}")
    destination = Path(os.path.abspath(entry["destination"]))
    source = Path(os.path.abspath(entry["source"]))
    try:
        destination.relative_to(codex_home)
    except ValueError as exc:
        raise ContractError(f"Receipt destination escapes CODEX_HOME: {destination}") from exc
    try:
        source.relative_to(repository_root)
    except ValueError as exc:
        raise ContractError(f"Receipt source escapes repository root: {source}") from exc

    inventory_id = entry["inventory_id"]
    kind = entry["kind"]
    link_type = entry["link_type"]
    if inventory_id == "product-root:autota":
        expected_source = repository_root
        expected_destination = codex_home / "workflow-products" / "autota"
        valid = (
            kind == "directory"
            and link_type in {"Junction", "SymbolicLink", "symlink"}
            and _same_path(source, expected_source)
            and _same_path(destination, expected_destination)
        )
    elif inventory_id.startswith("skill:"):
        name = inventory_id.removeprefix("skill:")
        expected_source = repository_root / "skills" / name
        expected_destination = codex_home / "skills" / name
        valid = (
            bool(SAFE_NAME_RE.fullmatch(name))
            and kind == "directory"
            and link_type in {"Junction", "SymbolicLink", "symlink"}
            and _same_path(source, expected_source)
            and _same_path(destination, expected_destination)
        )
    elif inventory_id.startswith("agent:"):
        name = inventory_id.removeprefix("agent:")
        filename = name.replace("_", "-") + ".toml"
        expected_source = repository_root / ".codex" / "agents" / filename
        expected_destination = codex_home / "agents" / filename
        valid = (
            name.startswith("autota_")
            and bool(SAFE_NAME_RE.fullmatch(name))
            and kind == "file"
            and link_type in {"HardLink", "SymbolicLink", "symlink"}
            and _same_path(source, expected_source)
            and _same_path(destination, expected_destination)
        )
    else:
        valid = False
    if not valid:
        raise ContractError(
            "Receipt entry is outside the AutoTA product namespace: "
            f"{inventory_id} -> {destination}"
        )
    normalized = dict(entry)
    normalized["destination"] = str(destination)
    normalized["source"] = str(source)
    return normalized


def read_receipt(
    path: Path, codex_home: Path, repository_root: Path
) -> dict[str, Any] | None:
    canonical_home = _absolute_lexical(codex_home)
    canonical_root = repository_root.expanduser().resolve(strict=True)
    expected_path = canonical_home / "state" / "autota" / "install-receipt.json"
    path = _absolute_lexical(path)
    if not _same_path(path, expected_path):
        raise ContractError(f"Unexpected install receipt path: {path}")
    preflight_receipt_path(path, canonical_home)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid install receipt {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"Install receipt is not an object: {path}")
    expected_keys = {"schema_version", "product", "repository_root", "entries"}
    if set(value) != expected_keys:
        raise ContractError(
            f"Install receipt fields are not the exact managed schema: {path}"
        )
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION or value.get("product") != PRODUCT:
        raise ContractError(f"Unsupported install receipt identity: {path}")
    receipt_root = value.get("repository_root")
    if not isinstance(receipt_root, str) or not _same_path(
        Path(os.path.abspath(receipt_root)), canonical_root
    ):
        raise ContractError(
            f"Install receipt belongs to a different checkout: {receipt_root!r}"
        )
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise ContractError(f"Install receipt entries must be a list: {path}")
    normalized_entries = [
        _validate_receipt_entry(entry, canonical_home, canonical_root) for entry in entries
    ]
    destinations = [entry["destination"] for entry in normalized_entries]
    if len(destinations) != len(set(destinations)):
        raise ContractError(f"Install receipt has duplicate destinations: {path}")
    inventory_ids = [entry["inventory_id"] for entry in normalized_entries]
    if len(inventory_ids) != len(set(inventory_ids)):
        raise ContractError(f"Install receipt has duplicate inventory IDs: {path}")
    preflight_managed_destination_ancestors(normalized_entries, canonical_home)
    value["entries"] = normalized_entries
    return value


def write_receipt(path: Path, inventory: dict[str, Any], entries: list[dict[str, str]]) -> None:
    preflight_receipt_path(path, Path(inventory["codex_home"]))
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "product": PRODUCT,
        "repository_root": inventory["repository_root"],
        "entries": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "receipt"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            if args.root is None:
                parser.error("inventory requires --root")
            value = build_inventory(args.root, args.codex_home)
        else:
            if args.receipt is None or args.root is None:
                parser.error("receipt requires --receipt and --root")
            value = read_receipt(args.receipt, args.codex_home, args.root)
    except (ContractError, OSError, tomllib.TOMLDecodeError) as exc:
        print(str(exc), file=os.sys.stderr)
        return 1
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
