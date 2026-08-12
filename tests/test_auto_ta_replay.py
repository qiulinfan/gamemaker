from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/auto-ta/scripts/validate_receipt.py"
SPEC = importlib.util.spec_from_file_location("gamemaker_auto_ta_validate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AutoTaFreshReplayTests(unittest.TestCase):
    def _reports(self, root: Path) -> tuple[dict, dict, Path]:
        blender = root / "trusted-blender"
        blender.write_bytes(b"explicit test executable")
        blender.chmod(0o755)
        blend = root / "source.blend"
        blend.write_bytes(b"BLENDER")
        delivery = root / "delivery.glb"
        delivery.write_bytes(b"glTF")
        auditor = ROOT / "skills/auto-ta/scripts/blender_asset_audit.py"

        def report(label: str, mode: str, source: Path) -> dict:
            return {
                "schema_version": "2.0",
                "run_id": f"stored-{label}",
                "started_at": "2026-01-01T00:00:00+00:00",
                "generated_at": "2026-01-01T00:00:01+00:00",
                "audit_verdict": "pass",
                "source": {
                    "mode": mode,
                    "path": str(source.resolve()),
                    "sha256": sha256(source),
                },
                "runtime": {
                    "audit_script": {
                        "path": str(auditor.resolve()),
                        "sha256": sha256(auditor),
                    }
                },
                "requirements": {},
                "scope": {"type": "active_scene"},
                "scene": {},
            }

        return (
            report("source", "open_blend", blend),
            report("imported", "clean_exchange_import", delivery),
            blender,
        )

    def test_two_fresh_replays_are_invoked_with_isolation_flags(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source, imported, blender = self._reports(Path(raw))
            commands: list[list[str]] = []

            def runner(command, **_kwargs):
                commands.append(command)
                stored = imported if "--input-file" in command else source
                replay = copy.deepcopy(stored)
                replay["run_id"] = "fresh-" + replay["run_id"]
                output = Path(command[command.index("--output") + 1])
                output.write_text(json.dumps(replay), encoding="utf-8")
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

            problems: list[dict] = []
            VALIDATOR._fresh_replay_audits(
                source, imported, blender, problems, runner=runner
            )

        self.assertEqual([], problems)
        self.assertEqual(2, len(commands))
        for command in commands:
            prefix = command[:7]
            self.assertEqual(str(blender.resolve()), prefix[0])
            self.assertEqual(
                [
                    "--background",
                    "--factory-startup",
                    "--disable-autoexec",
                    "--offline-mode",
                    "--python-exit-code",
                    "1",
                ],
                prefix[1:],
            )

    def test_replay_mismatch_blocks_validated_claim(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source, imported, blender = self._reports(Path(raw))

            def runner(command, **_kwargs):
                replay = copy.deepcopy(imported if "--input-file" in command else source)
                replay["run_id"] = "fresh"
                replay["unexpected_change"] = True
                Path(command[command.index("--output") + 1]).write_text(
                    json.dumps(replay), encoding="utf-8"
                )
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

            problems: list[dict] = []
            VALIDATOR._fresh_replay_audits(
                source, imported, blender, problems, runner=runner
            )

        self.assertEqual(
            ["AUDIT_REPLAY_CONTENT_MISMATCH", "AUDIT_REPLAY_CONTENT_MISMATCH"],
            [problem["code"] for problem in problems],
        )

    def test_replay_timeout_blocks_both_audits(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source, imported, blender = self._reports(Path(raw))
            calls = 0

            def runner(command, **_kwargs):
                nonlocal calls
                calls += 1
                raise subprocess.TimeoutExpired(command, 300)

            problems: list[dict] = []
            VALIDATOR._fresh_replay_audits(
                source, imported, blender, problems, runner=runner
            )

        self.assertEqual(2, calls)
        self.assertEqual(
            ["AUDIT_REPLAY_EXECUTION_ERROR", "AUDIT_REPLAY_EXECUTION_ERROR"],
            [problem["code"] for problem in problems],
        )

    def test_validated_replay_fails_closed_without_explicit_blender(self) -> None:
        problems: list[dict] = []
        VALIDATOR._fresh_replay_audits({}, {}, None, problems)
        self.assertEqual("VALIDATED_REPLAY_REQUIRED", problems[0]["code"])

        problems = []
        VALIDATOR._fresh_replay_audits({}, {}, Path("blender"), problems)
        self.assertEqual("VALIDATED_REPLAY_BLENDER_INVALID", problems[0]["code"])

    def test_cli_rejects_relative_blender_before_resolving_or_reading_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_root = Path(raw)
            relative_blender = run_root / "blender.exe"
            relative_blender.write_bytes(b"must never execute")
            for argument in ("blender.exe", "~/trusted/blender"):
                with self.subTest(argument=argument):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "missing-receipt.json",
                            "--blender-bin",
                            argument,
                        ],
                        cwd=run_root,
                        text=True,
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    self.assertEqual(3, completed.returncode)
                    self.assertIn(
                        "--blender-bin must be an absolute path", completed.stdout
                    )
                    self.assertNotIn("FileNotFoundError", completed.stdout)

    def test_skill_examples_anchor_all_bundled_scripts_outside_game_cwd(self) -> None:
        skill = (ROOT / "skills/auto-ta/SKILL.md").read_text(encoding="utf-8")
        for variable, script_name in (
            ("$AuditScript", "blender_asset_audit.py"),
            ("$CompareScript", "compare_asset_audits.py"),
            ("$ReceiptValidator", "validate_receipt.py"),
        ):
            with self.subTest(variable=variable):
                self.assertIn(f"{variable} = (Resolve-Path -LiteralPath", skill)
                self.assertIn(script_name, skill)
        self.assertIn("$CodexHome 'skills\\auto-ta'", skill)
        self.assertNotIn("python scripts/", skill)

    def test_skill_trigger_is_explicitly_3d_and_excludes_sprite_work(self) -> None:
        skill = (ROOT / "skills/auto-ta/SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill.split("---", maxsplit=2)[1]
        self.assertIn("3D Technical Art Skill", frontmatter)
        self.assertIn(
            "Do not use for standalone 2D art, sprite creation, or sprite-sheet work",
            frontmatter,
        )

        metadata = (ROOT / "skills/auto-ta/agents/openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Build and validate 3D game art assets", metadata)


if __name__ == "__main__":
    unittest.main()
