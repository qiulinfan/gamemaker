from __future__ import annotations

import gzip
import importlib.util
import subprocess
import sys
import tarfile
import tempfile
import unittest
import stat
from pathlib import Path
from types import SimpleNamespace
import zipfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "skills" / "search-game-art" / "scripts"


def load_script(name: str, filename: str):
    path = SCRIPT_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_script("autota_artifact_audit", "audit_artifact.py")
INVENTORY = load_script("autota_blender_inventory", "blender_asset_inventory.py")
RUNNER = load_script("autota_blender_inventory_runner", "run_blender_inventory.py")


class ArtifactAcquisitionSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / "Temp").mkdir(exist_ok=True)

    def test_only_safe_zip_is_granted_extraction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-audit-", dir=ROOT / "Temp") as temporary:
            run_root = Path(temporary)
            safe_zip = run_root / "safe.zip"
            with zipfile.ZipFile(safe_zip, "w") as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr("model.glb", b"fixture")
            result = AUDIT.audit(safe_zip)
            self.assertEqual("zip", result["kind"])
            self.assertEqual("pass", result["verdict"])
            self.assertIs(True, result["safe_to_extract"])

            plain_asset = run_root / "model.blend"
            plain_asset.write_bytes(b"BLENDER-v300")
            plain_result = AUDIT.audit(plain_asset)
            self.assertEqual("file", plain_result["kind"])
            self.assertEqual("pass", plain_result["verdict"])
            self.assertIs(False, plain_result["safe_to_extract"])

    def test_zip_links_code_missing_license_and_resource_bombs_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zip-policy-", dir=ROOT / "Temp") as temporary:
            run_root = Path(temporary)
            no_license = run_root / "no-license.zip"
            with zipfile.ZipFile(no_license, "w") as archive:
                archive.writestr("model.glb", b"fixture")

            code_zip = run_root / "code.zip"
            with zipfile.ZipFile(code_zip, "w") as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr("Assets/Editor/Install.cs", "class Install {}")
                archive.writestr("tools/setup.py", "print('unsafe')")

            symlink_zip = run_root / "symlink.zip"
            link = zipfile.ZipInfo("linked-model")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(symlink_zip, "w") as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr(link, "../../outside")

            ratio_zip = run_root / "ratio.zip"
            with zipfile.ZipFile(
                ratio_zip, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr("zeros.bin", b"0" * 1_000_000)

            expectations = {
                no_license: "missing_license_evidence",
                code_zip: "code_or_auto_compiled_entries_require_review",
                symlink_zip: "link_or_special_entries",
                ratio_zip: "compression_ratio_limit_exceeded",
            }
            for path, reason in expectations.items():
                with self.subTest(path=path.name):
                    result = AUDIT.audit(path)
                    self.assertEqual("blocked", result["verdict"])
                    self.assertIs(False, result["safe_to_extract"])
                    self.assertIn(reason, result["blocked_reasons"])

            budget_result = AUDIT.audit(
                no_license,
                max_files=1,
                max_uncompressed_bytes=1,
                max_single_file_bytes=1,
                max_ratio=1,
            )
            self.assertIn("total_uncompressed_limit_exceeded", budget_result["blocked_reasons"])
            self.assertIn("single_file_limit_exceeded", budget_result["blocked_reasons"])

    def test_declared_entry_budget_blocks_before_zipfile_inventory_allocation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zip-count-", dir=ROOT / "Temp") as raw:
            archive_path = Path(raw) / "many.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr("model.glb", "fixture")
            self.assertEqual(2, AUDIT.declared_zip_entry_count(archive_path))
            with mock.patch.object(
                AUDIT.zipfile,
                "ZipFile",
                side_effect=AssertionError("ZipFile inventory must not be allocated"),
            ):
                result = AUDIT.audit(archive_path, max_files=1)
            self.assertEqual("blocked", result["verdict"])
            self.assertIn(
                "declared_entry_count_limit_exceeded", result["blocked_reasons"]
            )

    def test_zip_paths_fail_closed_under_windows_canonicalization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zip-paths-", dir=ROOT / "Temp") as raw:
            run_root = Path(raw)
            unsafe_members = {
                "nested-colon": ["LICENSE.txt", "assets/bad:name.glb"],
                "reserved-device": ["LICENSE.txt", "assets/CON.txt", "Lpt1.fbx"],
                "reserved-directory": ["LICENSE.txt", "aux/"],
                "trailing-dot-space": ["LICENSE.txt", "assets./model.glb", "bad /model.glb"],
            }
            for label, members in unsafe_members.items():
                archive_path = run_root / f"{label}.zip"
                with zipfile.ZipFile(archive_path, "w") as archive:
                    for member in members:
                        archive.writestr(member, "fixture")
                with self.subTest(policy=label):
                    result = AUDIT.audit(archive_path)
                    self.assertEqual("blocked", result["verdict"])
                    self.assertIs(False, result["safe_to_extract"])
                    self.assertIn("unsafe_archive_paths", result["blocked_reasons"])

            collision = run_root / "canonical-collision.zip"
            with zipfile.ZipFile(collision, "w") as archive:
                archive.writestr("LICENSE.txt", "fixture")
                archive.writestr("Models/Hero.glb", "first")
                archive.writestr("models/hero.GLB", "second")
            result = AUDIT.audit(collision)
            self.assertEqual("blocked", result["verdict"])
            self.assertIs(False, result["safe_to_extract"])
            self.assertIn(
                "duplicate_or_case_colliding_paths", result["blocked_reasons"]
            )
            self.assertIn("models/hero.glb", result["duplicate_entries"])

    def test_rar_7z_tar_gz_and_renamed_archives_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-formats-", dir=ROOT / "Temp") as temporary:
            run_root = Path(temporary)
            rar = run_root / "asset.rar"
            rar.write_bytes(b"Rar!\x1a\x07\x01\x00fixture")
            seven_zip = run_root / "asset.7z"
            seven_zip.write_bytes(b"7z\xbc\xaf'\x1cfixture")
            source = run_root / "payload.txt"
            source.write_text("fixture", encoding="utf-8")
            tar_gz = run_root / "asset.tar.gz"
            with tarfile.open(tar_gz, "w:gz") as archive:
                archive.add(source, arcname="payload.txt")
            renamed_gzip = run_root / "asset.bin"
            with gzip.open(renamed_gzip, "wb") as handle:
                handle.write(b"fixture")
            invalid_zip = run_root / "invalid.zip"
            invalid_zip.write_bytes(b"not a zip")

            for path in (rar, seven_zip, tar_gz, renamed_gzip, invalid_zip):
                with self.subTest(path=path.name):
                    result = AUDIT.audit(path)
                    self.assertEqual("unsupported_archive", result["kind"])
                    self.assertEqual("blocked", result["verdict"])
                    self.assertIs(False, result["safe_to_extract"])

            for path in (rar, seven_zip, tar_gz):
                with self.subTest(cli=path.name):
                    completed = subprocess.run(
                        [sys.executable, str(SCRIPT_ROOT / "audit_artifact.py"), str(path)],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    self.assertEqual(2, completed.returncode, msg=completed.stderr)

    def test_inventory_command_and_runtime_require_isolation_before_asset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="blend-isolation-", dir=ROOT / "Temp") as temporary:
            run_root = Path(temporary)
            asset = run_root / "untrusted.blend"
            asset.write_bytes(b"BLENDER-v300")
            output = run_root / "inventory.json"
            command = RUNNER.build_command(
                "blender",
                asset,
                output,
                run_root,
                SCRIPT_ROOT / "blender_asset_inventory.py",
            )
            python_index = command.index("--python")
            boundary = command.index("--")
            for flag in INVENTORY.REQUIRED_ISOLATION_FLAGS:
                self.assertLess(command.index(flag), python_index)
            self.assertEqual("1", command[command.index("--python-exit-code") + 1])
            self.assertGreater(command.index(str(asset.resolve())), boundary)

            INVENTORY.bpy = SimpleNamespace(
                app=SimpleNamespace(background=True),
                data=SimpleNamespace(filepath=""),
            )
            INVENTORY.require_isolated_runtime(asset, command)
            for flag in INVENTORY.REQUIRED_ISOLATION_FLAGS:
                unsafe = list(command)
                unsafe.remove(flag)
                with self.subTest(missing_flag=flag):
                    with self.assertRaises(RuntimeError):
                        INVENTORY.require_isolated_runtime(asset, unsafe)

            already_open = SimpleNamespace(
                app=SimpleNamespace(background=True),
                data=SimpleNamespace(filepath=str(asset)),
            )
            INVENTORY.bpy = already_open
            with self.assertRaisesRegex(RuntimeError, "loaded before"):
                INVENTORY.require_isolated_runtime(asset, command)

    def test_existing_or_escaped_reports_fail_before_launch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report-output-", dir=ROOT / "Temp") as temporary:
            run_root = Path(temporary)
            existing = run_root / "existing.json"
            existing.write_text("owned", encoding="utf-8")
            escaped = run_root.parent / "escaped.json"
            for prepare in (AUDIT.prepare_output, INVENTORY.prepare_output):
                with self.subTest(prepare=prepare.__module__):
                    with self.assertRaises(FileExistsError):
                        prepare(existing, run_root)
                    with self.assertRaises(ValueError):
                        prepare(escaped, run_root)
            with self.assertRaises(FileExistsError):
                RUNNER.prepare_output(existing, run_root)
            with self.assertRaises(ValueError):
                RUNNER.prepare_output(escaped, run_root)

            asset = run_root / "untrusted.blend"
            asset.write_bytes(b"BLENDER-v300")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_ROOT / "run_blender_inventory.py"),
                    "--blender",
                    "must-not-launch",
                    "--asset",
                    str(asset),
                    "--output",
                    str(existing),
                    "--output-root",
                    str(run_root),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(2, completed.returncode, msg=completed.stderr)
            self.assertEqual("owned", existing.read_text(encoding="utf-8"))

    def test_blender_timeout_terminates_the_injected_process_tree(self) -> None:
        class FakeProcess:
            pid = 4242

            def __init__(self) -> None:
                self.wait_calls = 0

            def wait(self, timeout=None):
                self.wait_calls += 1
                if timeout is not None:
                    raise subprocess.TimeoutExpired(["blender"], timeout)
                return -9

        process = FakeProcess()
        launched: list[tuple[list[str], dict[str, object]]] = []
        terminated: list[FakeProcess] = []

        def factory(command, **kwargs):
            launched.append((command, kwargs))
            return process

        result = RUNNER.run_bounded(
            ["blender", "--background"],
            1,
            popen_factory=factory,
            tree_terminator=terminated.append,
        )
        self.assertEqual(124, result)
        self.assertEqual([process], terminated)
        self.assertEqual(2, process.wait_calls)
        self.assertEqual("blender", launched[0][0][0])


if __name__ == "__main__":
    unittest.main()
