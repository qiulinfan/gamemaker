from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _points_directly_to(source: Path, destination: Path) -> bool:
    if source.is_file() and destination.is_file():
        return os.path.samefile(source, destination)
    if destination.is_symlink():
        return destination.resolve() == source.resolve()
    is_junction = getattr(destination, "is_junction", None)
    return bool(is_junction and is_junction() and destination.resolve() == source.resolve())


@unittest.skipUnless(os.name == "nt", "PowerShell lifecycle is exercised on Windows")
class PowerShellLinkLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pwsh = shutil.which("pwsh")
        (ROOT / "Temp").mkdir(exist_ok=True)
        cls.fixture = tempfile.TemporaryDirectory(
            prefix="installer-bundle-", dir=ROOT / "Temp"
        )
        cls.fixture_root = Path(cls.fixture.name)
        cls.bundle_root = cls.fixture_root / "bundle"
        shutil.copytree(
            ROOT,
            cls.bundle_root,
            ignore=shutil.ignore_patterns(".git", "Temp", "__pycache__", "*.pyc"),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.cleanup()

    def run_ps(
        self,
        script: str,
        *arguments: str,
        expect: int = 0,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if not self.pwsh:
            self.skipTest("pwsh is unavailable")
        result = subprocess.run(
            [
                self.pwsh,
                "-NoLogo",
                "-NoProfile",
                "-File",
                str(self.bundle_root / "scripts" / script),
                *arguments,
            ],
            cwd=cwd or self.bundle_root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(
            expect,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def test_link_doctor_unlink_round_trip(self) -> None:
        codex_home = self.fixture_root / "round-trip-home"
        unrelated_cwd = self.fixture_root / "unrelated-game"
        unrelated_cwd.mkdir()
        self.run_ps(
            "link.ps1", "-CodexHome", str(codex_home), cwd=unrelated_cwd
        )

        skill_source = self.bundle_root / "skills" / "auto-ta"
        skill_link = codex_home / "skills" / "auto-ta"
        agent_source = self.bundle_root / ".codex" / "agents" / "autota-technical-artist.toml"
        agent_link = codex_home / "agents" / "autota-technical-artist.toml"
        product_link = codex_home / "workflow-products" / "autota"
        receipt = codex_home / "state" / "autota" / "install-receipt.json"
        self.assertTrue(_points_directly_to(skill_source, skill_link))
        self.assertTrue(_points_directly_to(agent_source, agent_link))
        self.assertTrue(_points_directly_to(self.bundle_root, product_link))
        self.assertEqual(skill_source.resolve(), skill_link.resolve())
        receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual("autota", receipt_value["product"])
        self.assertEqual(20, len(receipt_value["entries"]))

        doctor = self.run_ps(
            "doctor.ps1", "-CodexHome", str(codex_home), cwd=unrelated_cwd
        )
        self.assertIn("AUTOTA_DOCTOR_OK", doctor.stdout)

        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home))
        self.assertFalse(skill_link.exists())
        self.assertFalse(agent_link.exists())
        self.assertFalse(os.path.lexists(product_link))
        self.assertFalse(receipt.exists())

    def test_linker_refuses_real_destination(self) -> None:
        codex_home = self.fixture_root / "conflict-home"
        conflict = codex_home / "skills" / "auto-ta"
        conflict.mkdir(parents=True)
        marker = conflict / "owned-by-user.txt"
        marker.write_text("preserve", encoding="utf-8")
        self.run_ps("link.ps1", "-CodexHome", str(codex_home), expect=1)
        self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows hard-link ownership behavior")
    def test_force_never_replaces_wrong_owner_hardlink(self) -> None:
        codex_home = self.fixture_root / "wrong-hardlink-home"
        destination = codex_home / "agents" / "autota-technical-artist.toml"
        destination.parent.mkdir(parents=True)
        other_source = self.fixture_root / "user-owned-agent.toml"
        other_source.write_text('name = "user_owned"\n', encoding="utf-8")
        os.link(other_source, destination)

        self.run_ps(
            "link.ps1", "-CodexHome", str(codex_home), "-Force", expect=1
        )
        self.assertTrue(os.path.samefile(other_source, destination))
        self.assertEqual(
            'name = "user_owned"\n', destination.read_text(encoding="utf-8")
        )

        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home))
        self.assertTrue(os.path.samefile(other_source, destination))
        destination.unlink()
        other_source.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows receipt-path behavior")
    def test_receipt_storage_conflicts_fail_before_any_link_mutation(self) -> None:
        cases = (
            "receipt-directory",
            "state-file",
            "autota-file",
            "state-junction",
            "autota-junction",
        )
        for case in cases:
            with self.subTest(case=case):
                codex_home = self.fixture_root / f"receipt-conflict-{case}"
                external = self.fixture_root / f"receipt-external-{case}"
                if case == "receipt-directory":
                    (codex_home / "state/autota/install-receipt.json").mkdir(
                        parents=True
                    )
                elif case == "state-file":
                    codex_home.mkdir()
                    (codex_home / "state").write_text("preserve", encoding="utf-8")
                elif case == "autota-file":
                    (codex_home / "state").mkdir(parents=True)
                    (codex_home / "state/autota").write_text(
                        "preserve", encoding="utf-8"
                    )
                else:
                    if case == "state-junction":
                        codex_home.mkdir()
                        junction_path = codex_home / "state"
                    else:
                        (codex_home / "state").mkdir(parents=True)
                        junction_path = codex_home / "state/autota"
                    external.mkdir()
                    (external / "marker.txt").write_text("preserve", encoding="utf-8")
                    environment = os.environ.copy()
                    environment["AUTOTA_TEST_LINK"] = str(junction_path)
                    environment["AUTOTA_TEST_TARGET"] = str(external)
                    created = subprocess.run(
                        [
                            self.pwsh,
                            "-NoLogo",
                            "-NoProfile",
                            "-Command",
                            "New-Item -ItemType Junction -Path $env:AUTOTA_TEST_LINK -Target $env:AUTOTA_TEST_TARGET | Out-Null",
                        ],
                        cwd=self.fixture_root,
                        env=environment,
                        text=True,
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    self.assertEqual(0, created.returncode, msg=created.stderr)

                self.run_ps("link.ps1", "-CodexHome", str(codex_home), expect=1)
                for relative in (
                    "skills/auto-ta",
                    "agents/autota-technical-artist.toml",
                    "workflow-products/autota",
                ):
                    self.assertFalse(os.path.lexists(codex_home / relative))
                if external.exists():
                    self.assertEqual(
                        "preserve",
                        (external / "marker.txt").read_text(encoding="utf-8"),
                    )

    @unittest.skipUnless(os.name == "nt", "Windows reparse-parent behavior")
    def test_managed_destination_reparse_parents_fail_before_external_write(self) -> None:
        for parent_name in ("skills", "agents", "workflow-products"):
            with self.subTest(parent=parent_name):
                codex_home = self.fixture_root / f"destination-parent-{parent_name}"
                external = self.fixture_root / f"destination-external-{parent_name}"
                codex_home.mkdir()
                external.mkdir()
                marker = external / "marker.txt"
                marker.write_text("preserve", encoding="utf-8")
                environment = os.environ.copy()
                environment["AUTOTA_TEST_LINK"] = str(codex_home / parent_name)
                environment["AUTOTA_TEST_TARGET"] = str(external)
                created = subprocess.run(
                    [
                        self.pwsh,
                        "-NoLogo",
                        "-NoProfile",
                        "-Command",
                        "New-Item -ItemType Junction -Path $env:AUTOTA_TEST_LINK -Target $env:AUTOTA_TEST_TARGET | Out-Null",
                    ],
                    cwd=self.fixture_root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(0, created.returncode, msg=created.stderr)

                self.run_ps("link.ps1", "-CodexHome", str(codex_home), expect=1)
                self.assertEqual([marker], list(external.iterdir()))
                self.assertFalse(
                    os.path.lexists(
                        codex_home / "state/autota/install-receipt.json"
                    )
                )

    @unittest.skipUnless(os.name == "nt", "Windows reparse-parent behavior")
    def test_unlink_preflights_recorded_destination_parents(self) -> None:
        codex_home = self.fixture_root / "unlink-parent-home"
        external = self.fixture_root / "unlink-parent-external"
        self.run_ps("link.ps1", "-CodexHome", str(codex_home))
        for destination in (codex_home / "agents").iterdir():
            destination.unlink()
        (codex_home / "agents").rmdir()
        external.mkdir()
        marker = external / "marker.txt"
        marker.write_text("preserve", encoding="utf-8")
        environment = os.environ.copy()
        environment["AUTOTA_TEST_LINK"] = str(codex_home / "agents")
        environment["AUTOTA_TEST_TARGET"] = str(external)
        created = subprocess.run(
            [
                self.pwsh,
                "-NoLogo",
                "-NoProfile",
                "-Command",
                "New-Item -ItemType Junction -Path $env:AUTOTA_TEST_LINK -Target $env:AUTOTA_TEST_TARGET | Out-Null",
            ],
            cwd=self.fixture_root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, created.returncode, msg=created.stderr)

        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home), expect=1)
        self.assertEqual([marker], list(external.iterdir()))
        self.assertTrue(os.path.lexists(codex_home / "skills/auto-ta"))
        self.assertTrue(
            os.path.lexists(codex_home / "workflow-products/autota")
        )

    def test_bundle_validation_fails_before_codex_home_write(self) -> None:
        invalid_bundle = self.fixture_root / "invalid-bundle"
        shutil.copytree(
            self.bundle_root,
            invalid_bundle,
            ignore=shutil.ignore_patterns("Temp", "__pycache__", "*.pyc"),
        )
        manifest = invalid_bundle / "workflow.bundle.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "schema_version = 1", "schema_version = 999", 1
            ),
            encoding="utf-8",
        )
        codex_home = self.fixture_root / "invalid-bundle-home"
        if not self.pwsh:
            self.skipTest("pwsh is unavailable")
        result = subprocess.run(
            [
                self.pwsh,
                "-NoLogo",
                "-NoProfile",
                "-File",
                str(invalid_bundle / "scripts/link.ps1"),
                "-CodexHome",
                str(codex_home),
            ],
            cwd=self.fixture_root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Bundle validation failed before linking", result.stderr)
        self.assertFalse(codex_home.exists())

    def test_powershell_path_resolver_preserves_filesystem_root(self) -> None:
        if not self.pwsh:
            self.skipTest("pwsh is unavailable")
        environment = os.environ.copy()
        environment["AUTOTA_TEST_VOLUME_ROOT"] = Path(ROOT.anchor).as_posix()
        command = (
            ". $env:AUTOTA_TEST_CONTRACT; "
            "Resolve-AutoTAPath -Path $env:AUTOTA_TEST_VOLUME_ROOT"
        )
        environment["AUTOTA_TEST_CONTRACT"] = str(
            self.bundle_root / "scripts/LinkContract.ps1"
        )
        result = subprocess.run(
            [self.pwsh, "-NoLogo", "-NoProfile", "-Command", command],
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertEqual(Path(ROOT.anchor), Path(result.stdout.strip()))

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_force_replaces_dangling_junction(self) -> None:
        if not self.pwsh:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory(
            prefix="autota-codex-dangling-", dir=self.fixture_root
        ) as temporary:
            root = Path(temporary)
            codex_home = root / "home"
            skill_root = codex_home / "skills"
            skill_root.mkdir(parents=True)
            wrong_target = root / "wrong-target"
            wrong_target.mkdir()
            destination = skill_root / "auto-ta"
            environment = os.environ.copy()
            environment["AUTOTA_TEST_LINK"] = str(destination)
            environment["AUTOTA_TEST_TARGET"] = str(wrong_target)
            created = subprocess.run(
                [
                    self.pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:AUTOTA_TEST_LINK -Target $env:AUTOTA_TEST_TARGET | Out-Null",
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, created.returncode, msg=created.stderr)
            wrong_target.rmdir()
            self.assertTrue(os.path.lexists(destination))

            self.run_ps("link.ps1", "-CodexHome", str(codex_home), "-Force")
            self.assertTrue(
                _points_directly_to(self.bundle_root / "skills" / "auto-ta", destination)
            )
            self.run_ps("unlink.ps1", "-CodexHome", str(codex_home))

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_link_cleans_receipt_owned_deleted_skill_link(self) -> None:
        codex_home = self.fixture_root / "stale-home"
        self.run_ps("link.ps1", "-CodexHome", str(codex_home))
        stale_source = self.bundle_root / "skills" / "obsolete-skill"
        stale_source.mkdir()
        stale_destination = codex_home / "skills" / "obsolete-skill"
        environment = os.environ.copy()
        environment["AUTOTA_STALE_SOURCE"] = str(stale_source)
        environment["AUTOTA_STALE_DEST"] = str(stale_destination)
        created = subprocess.run(
            [
                self.pwsh,
                "-NoLogo",
                "-NoProfile",
                "-Command",
                "New-Item -ItemType Junction -Path $env:AUTOTA_STALE_DEST -Target $env:AUTOTA_STALE_SOURCE | Out-Null",
            ],
            cwd=self.bundle_root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, created.returncode, msg=created.stderr)
        receipt_path = codex_home / "state" / "autota" / "install-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["entries"].append(
            {
                "inventory_id": "skill:obsolete-skill",
                "source": str(stale_source),
                "destination": str(stale_destination),
                "kind": "directory",
                "link_type": "Junction",
            }
        )
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        stale_source.rmdir()

        self.run_ps("link.ps1", "-CodexHome", str(codex_home))
        self.assertFalse(os.path.lexists(stale_destination))
        refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertNotIn(
            "skill:obsolete-skill",
            {entry["inventory_id"] for entry in refreshed["entries"]},
        )
        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home))

    def test_detached_hardlink_is_preserved_fail_safe(self) -> None:
        codex_home = self.fixture_root / "detached-hardlink-home"
        self.run_ps("link.ps1", "-CodexHome", str(codex_home))
        source = self.bundle_root / ".codex" / "agents" / "autota-obsolete.toml"
        destination = codex_home / "agents" / "autota-obsolete.toml"
        source.write_text('name = "obsolete"\n', encoding="utf-8")
        os.link(source, destination)
        receipt_path = codex_home / "state" / "autota" / "install-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["entries"].append(
            {
                "inventory_id": "agent:autota_obsolete",
                "source": str(source),
                "destination": str(destination),
                "kind": "file",
                "link_type": "HardLink",
            }
        )
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        source.unlink()
        source.write_text('name = "replacement"\n', encoding="utf-8")

        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home), expect=1)
        self.assertTrue(destination.is_file())
        remaining = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {"agent:autota_obsolete"},
            {entry["inventory_id"] for entry in remaining["entries"]},
        )
        destination.unlink()
        source.unlink()
        receipt_path.unlink()

    def test_corrupt_or_wrong_checkout_receipt_cannot_remove_links(self) -> None:
        codex_home = self.fixture_root / "corrupt-receipt-home"
        self.run_ps("link.ps1", "-CodexHome", str(codex_home))
        skill_link = codex_home / "skills" / "auto-ta"
        receipt_path = codex_home / "state" / "autota" / "install-receipt.json"
        original = json.loads(receipt_path.read_text(encoding="utf-8"))

        wrong = dict(original)
        wrong["repository_root"] = str(self.fixture_root / "different-checkout")
        receipt_path.write_text(json.dumps(wrong), encoding="utf-8")
        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home), expect=1)
        self.assertTrue(os.path.lexists(skill_link))

        corrupt = json.loads(json.dumps(original))
        corrupt["entries"][0]["destination"] = str(
            codex_home / "skills" / "unrelated-user-link"
        )
        receipt_path.write_text(json.dumps(corrupt), encoding="utf-8")
        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home), expect=1)
        self.assertTrue(os.path.lexists(skill_link))

        receipt_path.write_text(json.dumps(original), encoding="utf-8")
        self.run_ps("unlink.ps1", "-CodexHome", str(codex_home))

    def test_overlapping_codex_home_is_rejected_before_write(self) -> None:
        overlapping = self.bundle_root / "TempCodexHome"
        self.run_ps("link.ps1", "-CodexHome", str(overlapping), expect=1)
        self.assertFalse(overlapping.exists())


@unittest.skipIf(os.name == "nt", "POSIX symlink lifecycle is exercised on POSIX hosts")
class PosixLinkLifecycleTests(unittest.TestCase):
    def test_link_doctor_unlink_round_trip(self) -> None:
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX sh is unavailable")
        with tempfile.TemporaryDirectory(prefix="autota-posix-home-") as temporary:
            unrelated = Path(temporary) / "unrelated-game"
            unrelated.mkdir()
            subprocess.run(
                [shell, str(ROOT / "scripts" / "link.sh"), temporary],
                cwd=unrelated,
                timeout=60,
                check=True,
            )
            subprocess.run(
                [shell, str(ROOT / "scripts" / "doctor.sh"), temporary],
                cwd=unrelated,
                timeout=60,
                check=True,
            )
            self.assertTrue((Path(temporary) / "skills" / "auto-ta").is_symlink())
            subprocess.run(
                [shell, str(ROOT / "scripts" / "unlink.sh"), temporary],
                cwd=unrelated,
                timeout=60,
                check=True,
            )
            self.assertFalse((Path(temporary) / "skills" / "auto-ta").exists())

    def test_posix_receipt_cleans_deleted_skill_symlink(self) -> None:
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX sh is unavailable")
        stale_source = ROOT / "skills" / "obsolete-skill"
        self.assertFalse(stale_source.exists())
        try:
            with tempfile.TemporaryDirectory(prefix="autota-posix-stale-") as raw:
                codex_home = Path(raw)
                subprocess.run(
                    [shell, str(ROOT / "scripts/link.sh"), str(codex_home)],
                    cwd=codex_home,
                    timeout=60,
                    check=True,
                )
                stale_source.mkdir()
                stale_destination = codex_home / "skills" / "obsolete-skill"
                stale_destination.symlink_to(stale_source, target_is_directory=True)
                receipt_path = (
                    codex_home / "state/autota/install-receipt.json"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["entries"].append(
                    {
                        "inventory_id": "skill:obsolete-skill",
                        "source": str(stale_source.resolve()),
                        "destination": str(stale_destination),
                        "kind": "directory",
                        "link_type": "symlink",
                    }
                )
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                stale_source.rmdir()

                subprocess.run(
                    [shell, str(ROOT / "scripts/link.sh"), str(codex_home)],
                    cwd=codex_home,
                    timeout=60,
                    check=True,
                )
                self.assertFalse(os.path.lexists(stale_destination))
                refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertNotIn(
                    "skill:obsolete-skill",
                    {entry["inventory_id"] for entry in refreshed["entries"]},
                )
                subprocess.run(
                    [shell, str(ROOT / "scripts/unlink.sh"), str(codex_home)],
                    cwd=codex_home,
                    timeout=60,
                    check=True,
                )
        finally:
            if stale_source.is_dir():
                stale_source.rmdir()

    def test_posix_receipt_parent_conflicts_fail_before_links(self) -> None:
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX sh is unavailable")
        with tempfile.TemporaryDirectory(prefix="autota-posix-conflicts-") as raw:
            root = Path(raw)
            for case in (
                "state-file",
                "autota-file",
                "state-symlink",
                "autota-symlink",
            ):
                with self.subTest(case=case):
                    codex_home = root / case
                    external = root / f"{case}-external"
                    if case == "state-file":
                        codex_home.mkdir()
                        (codex_home / "state").write_text("preserve", encoding="utf-8")
                    elif case == "autota-file":
                        (codex_home / "state").mkdir(parents=True)
                        (codex_home / "state/autota").write_text(
                            "preserve", encoding="utf-8"
                        )
                    else:
                        if case == "state-symlink":
                            codex_home.mkdir()
                            symlink_path = codex_home / "state"
                        else:
                            (codex_home / "state").mkdir(parents=True)
                            symlink_path = codex_home / "state/autota"
                        external.mkdir()
                        (external / "marker").write_text("preserve", encoding="utf-8")
                        symlink_path.symlink_to(external, target_is_directory=True)
                    result = subprocess.run(
                        [shell, str(ROOT / "scripts/link.sh"), str(codex_home)],
                        cwd=root,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse(os.path.lexists(codex_home / "skills/auto-ta"))
                    self.assertFalse(
                        os.path.lexists(
                            codex_home / "workflow-products/autota"
                        )
                    )
                    if external.exists():
                        self.assertEqual(
                            "preserve", (external / "marker").read_text(encoding="utf-8")
                        )

    def test_posix_managed_destination_symlink_parents_fail_before_external_write(self) -> None:
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX sh is unavailable")
        with tempfile.TemporaryDirectory(prefix="autota-posix-destinations-") as raw:
            root = Path(raw)
            for parent_name in ("skills", "agents", "workflow-products"):
                with self.subTest(parent=parent_name):
                    codex_home = root / f"home-{parent_name}"
                    external = root / f"external-{parent_name}"
                    codex_home.mkdir()
                    external.mkdir()
                    marker = external / "marker"
                    marker.write_text("preserve", encoding="utf-8")
                    (codex_home / parent_name).symlink_to(
                        external, target_is_directory=True
                    )
                    result = subprocess.run(
                        [shell, str(ROOT / "scripts/link.sh"), str(codex_home)],
                        cwd=root,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual([marker], list(external.iterdir()))
                    self.assertFalse(
                        os.path.lexists(
                            codex_home / "state/autota/install-receipt.json"
                        )
                    )


if __name__ == "__main__":
    unittest.main()
