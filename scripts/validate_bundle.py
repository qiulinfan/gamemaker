#!/usr/bin/env python3
"""Validate the portable Gamemaker bundle without third-party packages."""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from pathlib import Path


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CORE_FORBIDDEN = {
    "dreamweaver": re.compile(r"dreamweaver", re.IGNORECASE),
    "multica": re.compile(r"multica", re.IGNORECASE),
    "google-drive": re.compile(r"google\s*drive|googledrivefs", re.IGNORECASE),
    "personal-windows-root": re.compile(
        r"c:(?:[\\/]|\\\\)+users(?:[\\/]|\\\\)+rynne", re.IGNORECASE
    ),
    "personal-drive-root": re.compile(
        r"g:(?:[\\/]|\\\\)+my\s+drive", re.IGNORECASE
    ),
}
CORE_TEXT_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".py", ".ps1", ".sh"}
EXPECTED_LINK_SCRIPTS = {
    "link.ps1",
    "unlink.ps1",
    "doctor.ps1",
    "link.sh",
    "unlink.sh",
    "doctor.sh",
}
UNITY_MUTATING_SKILLS = {
    "auto-ta",
    "build-unity-scene",
    "character-rig-animation-alignment",
    "play-unity-game",
}
UNITY_MUTATING_AGENTS = {"gamemaker-technical-artist"}
UNITY_MUTATION_MARKERS = {
    "Console clear",
    "Play",
    "Stop",
    "screenshot",
    "load/reload/reset",
    "test execution",
    "settings",
    "asset import/refresh",
    "save",
}


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_toml(path: Path, errors: list[str]) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"{path}: invalid TOML: {exc}")
        return {}


def _resolve_inventory_path(root: Path, raw_path: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        errors.append(f"{label}: path must be a non-empty string")
        return None
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes repository root: {raw_path}")
        return None
    if not candidate.exists():
        errors.append(f"{label}: missing path: {raw_path}")
    return candidate


def _parse_skill_frontmatter(skill_file: Path, errors: list[str]) -> tuple[dict[str, str], str]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{skill_file}: cannot read: {exc}")
        return {}, ""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        errors.append(f"{skill_file}: SKILL.md must start with YAML frontmatter")
        return {}, normalized
    marker = normalized.find("\n---\n", 4)
    if marker < 0:
        errors.append(f"{skill_file}: YAML frontmatter is not closed")
        return {}, normalized
    frontmatter_text = normalized[4:marker]
    body = normalized[marker + 5 :]
    values: dict[str, str] = {}
    keys: list[str] = []
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            errors.append(f"{skill_file}: unsupported multiline or nested frontmatter: {line!r}")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        keys.append(key)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    if keys != ["name", "description"]:
        errors.append(f"{skill_file}: frontmatter keys must be exactly name, description in that order")
    if not values.get("description"):
        errors.append(f"{skill_file}: description is required")
    if len(body.splitlines()) > 500:
        errors.append(f"{skill_file}: body exceeds the 500-line progressive-disclosure limit")
    return values, body


def _validate_skill(root: Path, skill_dir: Path, manifest_name: str, errors: list[str]) -> None:
    skill_file = skill_dir / "SKILL.md"
    values, text = _parse_skill_frontmatter(skill_file, errors)
    actual_name = values.get("name", "")
    if actual_name != manifest_name:
        errors.append(f"{skill_file}: manifest name {manifest_name!r} != frontmatter {actual_name!r}")
    if skill_dir.name != actual_name:
        errors.append(f"{skill_file}: directory name must equal frontmatter name")
    if actual_name and not SKILL_NAME_RE.fullmatch(actual_name):
        errors.append(f"{skill_file}: invalid Skill name {actual_name!r}")

    metadata_file = skill_dir / "agents" / "openai.yaml"
    if not metadata_file.is_file():
        errors.append(f"{skill_dir}: missing agents/openai.yaml")
    else:
        metadata = metadata_file.read_text(encoding="utf-8")
        for key in ("display_name", "short_description", "default_prompt"):
            if not re.search(rf"^\s*{key}:\s*\"[^\"]+\"\s*$", metadata, re.MULTILINE):
                errors.append(f"{metadata_file}: missing quoted {key}")
        if ("$" + actual_name) not in metadata:
            errors.append(f"{metadata_file}: default_prompt must mention the Skill name with a dollar prefix")

    for match in re.finditer(r"\]\(((?:references|scripts)/[^)#]+)", text):
        resource = skill_dir / match.group(1)
        if not resource.is_file():
            errors.append(f"{skill_file}: missing linked resource {match.group(1)}")

    allowed_top_level = {"SKILL.md", "agents", "assets", "references", "scripts"}
    for child in skill_dir.iterdir():
        if child.name not in allowed_top_level:
            errors.append(f"{skill_dir}: unexpected top-level Skill entry {child.name}")


def _validate_agents(
    root: Path, manifest: dict, skill_names: set[str], errors: list[str]
) -> None:
    entries = manifest.get("agents", [])
    if not isinstance(entries, list):
        errors.append("workflow.bundle.toml: agents must be an array of tables")
        return
    manifest_names: set[str] = set()
    manifest_paths: set[str] = set()
    covered_skills: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"agents[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected table")
            continue
        name = entry.get("name")
        path_value = entry.get("path")
        if not isinstance(name, str) or not name.startswith("gamemaker_"):
            errors.append(f"{label}: name must use gamemaker_ namespace")
            continue
        if name in manifest_names:
            errors.append(f"{label}: duplicate agent name {name}")
        manifest_names.add(name)
        if isinstance(path_value, str):
            manifest_paths.add(path_value)
        path = _resolve_inventory_path(root, path_value, label, errors)
        if path is None or not path.is_file():
            continue
        config = _load_toml(path, errors)
        for required in ("name", "description", "developer_instructions"):
            if not isinstance(config.get(required), str) or not config[required].strip():
                errors.append(f"{path}: missing required custom-agent field {required}")
        if config.get("name") != name:
            errors.append(f"{path}: name does not match manifest {name}")
        if path.stem.replace("-", "_") != name:
            errors.append(f"{path}: filename should conventionally match agent name")
        primary_skills = entry.get("primary_skills")
        if not isinstance(primary_skills, list) or not primary_skills:
            errors.append(f"{label}: primary_skills must be a non-empty array")
        elif not all(isinstance(skill, str) for skill in primary_skills):
            errors.append(f"{label}: primary_skills entries must be strings")
        else:
            covered_skills.update(primary_skills)
            unknown = sorted(set(primary_skills) - skill_names)
            if unknown:
                errors.append(f"{label}: unknown primary_skills {unknown}")

    disk_paths = {
        _relative(root, path)
        for path in (root / ".codex" / "agents").glob("*.toml")
        if path.is_file()
    }
    if disk_paths != manifest_paths:
        errors.append(
            "workflow.bundle.toml: agent inventory mismatch; "
            f"manifest={sorted(manifest_paths)} disk={sorted(disk_paths)}"
        )
    uncovered = sorted(skill_names - covered_skills)
    if uncovered:
        errors.append(
            f"workflow.bundle.toml: Skills without a primary agent owner: {uncovered}"
        )


def _validate_profiles(root: Path, manifest: dict, errors: list[str]) -> None:
    entries = manifest.get("profiles", [])
    if not isinstance(entries, list):
        errors.append("workflow.bundle.toml: profiles must be an array of tables")
        return
    manifest_ids: set[str] = set()
    manifest_paths: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"profiles[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected table")
            continue
        profile_id = entry.get("id")
        if not isinstance(profile_id, str) or not SKILL_NAME_RE.fullmatch(profile_id):
            errors.append(f"{label}: invalid profile id")
            continue
        if profile_id in manifest_ids:
            errors.append(f"{label}: duplicate profile id {profile_id}")
        manifest_ids.add(profile_id)
        if entry.get("enabled_by_default") is not False:
            errors.append(f"{label}: profiles must be disabled by default")
        path_value = entry.get("path")
        if isinstance(path_value, str):
            manifest_paths.add(path_value)
        expected_path = f"profiles/{profile_id}/profile.toml"
        if path_value != expected_path:
            errors.append(f"{label}: path must be {expected_path!r}")
        path = _resolve_inventory_path(root, path_value, label, errors)
        if path is None or not path.is_file():
            continue
        config = _load_toml(path, errors)
        profile = config.get("profile", {})
        if profile.get("id") != profile_id:
            errors.append(f"{path}: profile.id does not match manifest")
        if profile.get("enabled_by_default") is not False:
            errors.append(f"{path}: profile must be disabled by default")

    disk_ids = {
        child.name for child in (root / "profiles").iterdir() if child.is_dir()
    }
    if disk_ids != manifest_ids:
        errors.append(
            "workflow.bundle.toml: profile inventory mismatch; "
            f"manifest={sorted(manifest_ids)} disk={sorted(disk_ids)}"
        )
    disk_paths = {
        _relative(root, child / "profile.toml")
        for child in (root / "profiles").iterdir()
        if child.is_dir() and (child / "profile.toml").is_file()
    }
    if disk_paths != manifest_paths:
        errors.append(
            "workflow.bundle.toml: profile path inventory mismatch; "
            f"manifest={sorted(manifest_paths)} disk={sorted(disk_paths)}"
        )


def _validate_portability(root: Path, errors: list[str]) -> None:
    scan_roots = [root / "skills", root / ".codex" / "agents", root / "workflows"]
    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CORE_TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in CORE_FORBIDDEN.items():
                if pattern.search(text):
                    errors.append(
                        f"{_relative(root, path)}: portable core contains profile-specific token {label}"
                    )


def _validate_python(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*.py")):
        if ".git" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            errors.append(f"{_relative(root, path)}: Python syntax failure: {exc}")


def _validate_unity_identity_gates(root: Path, errors: list[str]) -> None:
    required_markers = {
        "mcpforunity://project/info",
        "data.projectRoot",
        "UNITY_PROJECT_MISMATCH",
        "canonical",
        "exact",
    }
    contract_files = [
        (f"Skill {name}", root / "skills" / name / "SKILL.md")
        for name in sorted(UNITY_MUTATING_SKILLS)
    ] + [
        (f"agent {name}", root / ".codex" / "agents" / f"{name}.toml")
        for name in sorted(UNITY_MUTATING_AGENTS)
    ]
    for label, contract_file in contract_files:
        text = contract_file.read_text(encoding="utf-8", errors="replace")
        missing = sorted(marker for marker in required_markers if marker not in text)
        if missing:
            errors.append(
                f"{_relative(root, contract_file)}: Unity-mutating {label} lacks "
                f"fail-closed project identity markers {missing}"
            )
        if "every individual Unity MCP tool call" not in text or "Immediately before exactly one" not in text:
            errors.append(
                f"{_relative(root, contract_file)}: project identity must be "
                "re-read immediately before every individual mutating tool call"
            )
        missing_mutations = sorted(
            marker for marker in UNITY_MUTATION_MARKERS if marker not in text
        )
        if missing_mutations:
            errors.append(
                f"{_relative(root, contract_file)}: project identity gate does not "
                f"enumerate mutating operations {missing_mutations}"
            )


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    manifest_path = root / "workflow.bundle.toml"
    manifest = _load_toml(manifest_path, errors)
    if manifest.get("schema_version") != 1:
        errors.append("workflow.bundle.toml: schema_version must be 1")

    bundle = manifest.get("bundle", {})
    if bundle.get("name") != "gamemaker":
        errors.append("workflow.bundle.toml: bundle.name must be gamemaker")
    expected_roots = {
        "skills_root": "skills",
        "workflows_root": "workflows",
        "profiles_root": "profiles",
        "agents_root": ".codex/agents",
    }
    for key, expected in expected_roots.items():
        if bundle.get(key) != expected:
            errors.append(f"workflow.bundle.toml: bundle.{key} must be {expected!r}")

    link = manifest.get("link", {})
    expected_links = {
        "skills_destination": "skills",
        "agents_destination": "agents",
        "product_destination": "workflow-products/gamemaker",
        "receipt_destination": "state/gamemaker/install-receipt.json",
        "mode": "direct-working-tree-link",
    }
    for key, expected in expected_links.items():
        if link.get(key) != expected:
            errors.append(f"workflow.bundle.toml: link.{key} must be {expected!r}")

    skill_entries = manifest.get("skills", [])
    manifest_skill_names: set[str] = set()
    manifest_skill_paths: set[str] = set()
    if not isinstance(skill_entries, list):
        errors.append("workflow.bundle.toml: skills must be an array of tables")
    else:
        for index, entry in enumerate(skill_entries):
            label = f"skills[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: expected table")
                continue
            name = entry.get("name")
            path_value = entry.get("path")
            if not isinstance(name, str):
                errors.append(f"{label}: missing name")
                continue
            if name in manifest_skill_names:
                errors.append(f"{label}: duplicate Skill name {name}")
            manifest_skill_names.add(name)
            if isinstance(path_value, str):
                manifest_skill_paths.add(path_value)
            path = _resolve_inventory_path(root, path_value, label, errors)
            if path is not None and path.is_dir():
                _validate_skill(root, path, name, errors)

    disk_skill_paths = {
        _relative(root, child)
        for child in (root / "skills").iterdir()
        if child.is_dir() and child.name != "__pycache__"
    }
    if disk_skill_paths != manifest_skill_paths:
        errors.append(
            "workflow.bundle.toml: Skill inventory mismatch; "
            f"manifest={sorted(manifest_skill_paths)} disk={sorted(disk_skill_paths)}"
        )

    entries = manifest.get("workflows", [])
    manifest_workflow_paths: set[str] = set()
    if not isinstance(entries, list):
        errors.append("workflow.bundle.toml: workflows must be an array of tables")
    else:
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            label = f"workflows[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: expected table")
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"{label}: missing name")
            elif name in seen:
                errors.append(f"{label}: duplicate name {name}")
            else:
                seen.add(name)
            path_value = entry.get("path")
            if isinstance(path_value, str):
                manifest_workflow_paths.add(path_value)
            path = _resolve_inventory_path(root, path_value, label, errors)
            if path is not None and not path.is_file():
                errors.append(f"{label}: workflow path must be a file")
            entry_skill = entry.get("entry_skill")
            if entry_skill not in manifest_skill_names:
                errors.append(f"{label}: unknown entry_skill {entry_skill!r}")

    disk_workflow_paths = {
        _relative(root, path)
        for path in (root / "workflows").iterdir()
        if path.is_file()
    }
    if disk_workflow_paths != manifest_workflow_paths:
        errors.append(
            "workflow.bundle.toml: workflow inventory mismatch; "
            f"manifest={sorted(manifest_workflow_paths)} disk={sorted(disk_workflow_paths)}"
        )

    _validate_agents(root, manifest, manifest_skill_names, errors)
    _validate_profiles(root, manifest, errors)
    _validate_portability(root, errors)
    _validate_python(root, errors)
    _validate_unity_identity_gates(root, errors)

    legal = manifest.get("legal", {})
    license_path = root / "LICENSE"
    if legal.get("status") == "unresolved":
        if legal.get("license_file") not in {"", None}:
            errors.append("workflow.bundle.toml: unresolved legal status must not name a license file")
        if license_path.exists():
            errors.append("LICENSE exists while manifest legal status is unresolved")
    elif not license_path.is_file():
        errors.append("Resolved legal status requires a LICENSE file")

    existing_link_scripts = {
        path.name for path in (root / "scripts").iterdir() if path.name in EXPECTED_LINK_SCRIPTS
    }
    if existing_link_scripts != EXPECTED_LINK_SCRIPTS:
        errors.append(
            "scripts: missing link lifecycle commands: "
            f"{sorted(EXPECTED_LINK_SCRIPTS - existing_link_scripts)}"
        )

    attributes_path = root / ".gitattributes"
    attributes = attributes_path.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^\*\.sh\s+text\s+eol=lf\s*$", attributes, re.MULTILINE):
        errors.append(".gitattributes: *.sh must be normalized with text eol=lf")
    for shell_script in sorted(root.rglob("*.sh")):
        if b"\r" in shell_script.read_bytes():
            errors.append(f"{_relative(root, shell_script)}: shell script contains CR bytes")

    gitignore = (root / ".gitignore").read_text(encoding="utf-8", errors="replace")
    if "__pycache__/" not in gitignore or "*.py[cod]" not in gitignore:
        errors.append(".gitignore: generated Python caches must be ignored")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"GAMEMAKER_BUNDLE_INVALID errors={len(errors)}", file=sys.stderr)
        return 1
    print("GAMEMAKER_BUNDLE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
