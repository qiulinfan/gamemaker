from __future__ import annotations

import importlib.util
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"
SPEC = importlib.util.spec_from_file_location("gamemaker_validate_bundle", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class BundleContractTests(unittest.TestCase):
    def test_static_bundle_contract(self) -> None:
        self.assertEqual([], VALIDATOR.validate(ROOT))

    def test_expected_skill_inventory(self) -> None:
        with (ROOT / "workflow.bundle.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        names = {entry["name"] for entry in manifest["skills"]}
        self.assertEqual(
            {
                "auto-ta",
                "build-unity-scene",
                "character-rig-animation-alignment",
                "configure-unity-mcp",
                "coordinate-game-production",
                "create-2d-game-art",
                "deliver-unity-feature",
                "discuss-game-design",
                "iterate-unity-level",
                "play-unity-game",
                "record-windows-playtest",
                "search-game-art",
                "write-game-design-brief",
            },
            names,
        )

    def test_profiles_are_opt_in(self) -> None:
        with (ROOT / "workflow.bundle.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        self.assertEqual(
            {"dreamweaver", "multica", "google-drive"},
            {entry["id"] for entry in manifest["profiles"]},
        )
        self.assertTrue(all(entry["enabled_by_default"] is False for entry in manifest["profiles"]))

    def test_personal_path_regexes_cover_native_and_serialized_separators(self) -> None:
        pattern = VALIDATOR.CORE_FORBIDDEN["personal-windows-root"]
        for value in (
            r"C:\Users\rynne\project",
            "C:/Users/rynne/project",
            r"C:\\Users\\rynne\\project",
        ):
            with self.subTest(value=value):
                self.assertIsNotNone(pattern.search(value))

    def test_historical_case_is_profile_only(self) -> None:
        case = (
            ROOT
            / "profiles"
            / "dreamweaver"
            / "case-studies"
            / "character-rig-animation-alignment.md"
        )
        self.assertGreater(case.stat().st_size, 10_000)
        self.assertFalse(
            (
                ROOT
                / "skills"
                / "character-rig-animation-alignment"
                / "references"
                / "dreamweaver-case-study.md"
            ).exists()
        )

    def test_unresolved_license_is_explicit(self) -> None:
        with (ROOT / "workflow.bundle.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        self.assertEqual("unresolved", manifest["legal"]["status"])
        self.assertFalse((ROOT / "LICENSE").exists())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("No license could be established", readme)

    def test_readme_documents_product_root_receipt_and_runtime_contracts(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for marker in (
            "${CODEX_HOME}/workflow-products/gamemaker",
            "${CODEX_HOME}/state/gamemaker/install-receipt.json",
            "iTerm2",
            "`zsh`",
            "PowerShell 7+",
            "$env:CODEX_HOME",
            "detached hardlink",
            "unrelated game cwd",
            "Python 3.11+ and `uv`",
        ):
            self.assertIn(marker, readme)

        self.assertIn("command -v uv", (ROOT / "scripts/doctor.sh").read_text(encoding="utf-8"))
        self.assertIn("Get-Command uv", (ROOT / "scripts/doctor.ps1").read_text(encoding="utf-8"))

    def test_readme_routes_macos_to_iterm2_and_posix_only(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        macos = readme.split("macOS —", 1)[1].split("Linux —", 1)[0]
        self.assertIn("iTerm2", macos)
        self.assertIn("`zsh`", macos)
        self.assertIn("`bash`", macos)
        self.assertIn("./scripts/link.sh", macos)
        self.assertIn("./scripts/doctor.sh", macos)
        self.assertNotIn("pwsh", macos.lower())

    def test_powershell_lifecycle_entrypoints_are_windows_only(self) -> None:
        for script_name in ("link.ps1", "doctor.ps1", "unlink.ps1"):
            script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
            with self.subTest(script=script_name):
                self.assertIn("if (-not $IsWindows)", script)
                self.assertIn("use ./scripts/", script)

    def test_unity_mutating_skills_have_exact_project_identity_gate(self) -> None:
        contract_files = [
            ROOT / "skills" / skill_name / "SKILL.md"
            for skill_name in sorted(VALIDATOR.UNITY_MUTATING_SKILLS)
        ] + [
            ROOT / ".codex" / "agents" / f"{agent_name}.toml"
            for agent_name in sorted(VALIDATOR.UNITY_MUTATING_AGENTS)
        ]
        for contract_file in contract_files:
            text = contract_file.read_text(encoding="utf-8")
            with self.subTest(contract=contract_file.relative_to(ROOT)):
                for marker in (
                    "mcpforunity://project/info",
                    "data.projectRoot",
                    "UNITY_PROJECT_MISMATCH",
                    "canonical",
                    "exact",
                    "every individual Unity MCP tool call",
                    "Immediately before exactly one",
                    "Console clear",
                    "Play",
                    "Stop",
                    "screenshot",
                    "load/reload/reset",
                    "test execution",
                    "settings",
                    "asset import/refresh",
                    "save",
                ):
                    self.assertIn(marker, text)

    def test_validator_rejects_each_unity_mutator_without_per_call_gate(self) -> None:
        (ROOT / "Temp").mkdir(exist_ok=True)
        source_files = [
            ROOT / "skills" / skill_name / "SKILL.md"
            for skill_name in sorted(VALIDATOR.UNITY_MUTATING_SKILLS)
        ] + [
            ROOT / ".codex" / "agents" / f"{agent_name}.toml"
            for agent_name in sorted(VALIDATOR.UNITY_MUTATING_AGENTS)
        ]
        for source in source_files:
            with self.subTest(contract=source.relative_to(ROOT)):
                with tempfile.TemporaryDirectory(
                    prefix="unity-gate-", dir=ROOT / "Temp"
                ) as raw:
                    fixture_root = Path(raw)
                    for contract_file in source_files:
                        destination = fixture_root / contract_file.relative_to(ROOT)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(contract_file, destination)
                    target = fixture_root / source.relative_to(ROOT)
                    target.write_text(
                        target.read_text(encoding="utf-8").replace(
                            "mcpforunity://project/info", "removed-project-info"
                        ),
                        encoding="utf-8",
                    )
                    errors: list[str] = []
                    VALIDATOR._validate_unity_identity_gates(fixture_root, errors)
                    self.assertTrue(
                        any(str(source.relative_to(ROOT)).replace("\\", "/") in error for error in errors),
                        msg=errors,
                    )

    def test_unity_mcp_persistence_and_remote_probe_require_explicit_authority(self) -> None:
        text = (ROOT / "skills/configure-unity-mcp/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Read-only diagnosis (default)", text)
        self.assertIn("Bounded current-session setup", text)
        self.assertIn("Persistent setup", text)
        self.assertIn("Only for explicitly authorized persistent setup", text)
        self.assertIn("Do not enable `Auto-Start Server on Editor Load`", text)
        self.assertIn("--allow-remote-probe", text)
        platform_text = (
            ROOT / "skills/configure-unity-mcp/references/platforms.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Copy the complete `configure-unity-mcp` folder", platform_text)
        self.assertIn("complete `gamemaker` product repository", platform_text)
        troubleshooting = (
            ROOT / "skills/configure-unity-mcp/references/troubleshooting.md"
        ).read_text(encoding="utf-8")
        self.assertIn("bounded current-session setup by default", troubleshooting)
        self.assertIn("Leave Auto-Start\ndisabled", troubleshooting)
        self.assertIn("explicitly authorizes persistent background startup", troubleshooting)
        self.assertNotIn("6. Enable auto-start", troubleshooting)

    def test_animation_alignment_requires_visible_semantic_oracles(self) -> None:
        skill = (
            ROOT / "skills/character-rig-animation-alignment/SKILL.md"
        ).read_text(encoding="utf-8")
        gates = (
            ROOT
            / "skills/character-rig-animation-alignment/references/alignment-gates.md"
        ).read_text(encoding="utf-8")
        for text in (skill, gates):
            self.assertIn("visible", text.lower())
            self.assertIn("semantic axis", text)
            self.assertIn("independent", text)
            self.assertIn("correction", text)

    def test_playtest_records_and_reports_editor_cleanup_baseline(self) -> None:
        skill = (ROOT / "skills/play-unity-game/SKILL.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "pre-session Editor baseline",
            "dirty flag",
            "Prefab Stage",
            "PASS`, `FAIL`, or `BLOCKED",
            "cleanup outcome",
        ):
            self.assertIn(marker, skill)


if __name__ == "__main__":
    unittest.main()
