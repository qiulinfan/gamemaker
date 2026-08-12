from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScriptSyntaxTests(unittest.TestCase):
    def test_all_python_files_parse(self) -> None:
        for path in sorted(ROOT.rglob("*.py")):
            if ".git" in path.parts:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_posix_scripts_parse(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if not shell:
            self.skipTest("No POSIX shell is available")
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    [shell, "-n"],
                    cwd=ROOT,
                    input=path.read_bytes(),
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    msg=result.stderr.decode("utf-8", errors="replace"),
                )

    def test_shell_files_are_lf_and_git_attributes_enforce_lf(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(attributes, r"(?m)^\*\.sh\s+text\s+eol=lf\s*$")
        for path in sorted(ROOT.rglob("*.sh")):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(b"\r", path.read_bytes())
                result = subprocess.run(
                    ["git", "check-attr", "eol", "--", str(path.relative_to(ROOT))],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(0, result.returncode, msg=result.stderr)
                self.assertTrue(result.stdout.rstrip().endswith("eol: lf"), msg=result.stdout)

    @unittest.skipUnless(os.name == "nt", "PowerShell syntax is validated on Windows")
    def test_powershell_scripts_parse(self) -> None:
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("pwsh is unavailable")
        command = (
            "$failed = $false; "
            "Get-ChildItem -Recurse -File -Filter '*.ps1' | ForEach-Object { "
            "$tokens = $null; $errors = $null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            "$_.FullName, [ref]$tokens, [ref]$errors); "
            "if ($errors.Count -gt 0) { "
            "$failed = $true; $errors | ForEach-Object { Write-Error $_.Message } "
            "} }; if ($failed) { exit 1 }"
        )
        result = subprocess.run(
            [pwsh, "-NoLogo", "-NoProfile", "-Command", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_playtest_capture_is_provider_neutral(self) -> None:
        script = (
            ROOT
            / "skills"
            / "record-windows-playtest"
            / "scripts"
            / "Invoke-WindowsPlaytestCapture.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("PublishRoot", script)
        self.assertIn("PUBLISHED_TO_MOUNT", script)
        self.assertNotIn("GoogleDriveFS", script)
        self.assertNotIn("Dreamweaver", script)
        self.assertNotIn(r"G:\My Drive", script)
        self.assertIn("#requires -Version 7.0", script)
        self.assertIn("PSVersionTable.PSVersion.Major -lt 7", script)
        self.assertEqual(
            1,
            script.count("Write-JsonFileAtomic -Value $state -Path $captureStatePath"),
        )
        self.assertIn("$process.Kill($true)", script)
        self.assertIn("[System.IO.Directory]::Move($publishStagingDirectory", script)

    @unittest.skipUnless(os.name == "nt", "Windows capture completion requires PowerShell and FFmpeg")
    def test_playtest_capture_completes_local_and_mounted_delivery(self) -> None:
        pwsh = shutil.which("pwsh")
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not pwsh or not ffmpeg or not ffprobe:
            self.skipTest("pwsh, ffmpeg, and ffprobe are required")

        temp_root = ROOT / "Temp"
        temp_root.mkdir(exist_ok=True)
        capture_script = (
            ROOT
            / "skills"
            / "record-windows-playtest"
            / "scripts"
            / "Invoke-WindowsPlaytestCapture.ps1"
        )
        with tempfile.TemporaryDirectory(prefix="capture-complete-", dir=temp_root) as temporary:
            run_root = Path(temporary)
            video = run_root / "fixture.mp4"
            generated = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:s=320x240:r=15",
                    "-t",
                    "3.2",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, generated.returncode, msg=generated.stderr)

            def write_state(name: str, video_path: Path) -> Path:
                state_path = run_root / f"{name}.capture.json"
                started = datetime.now(timezone.utc) - timedelta(seconds=10)
                state_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "status": "RECORDING",
                            "ffmpeg_pid": 2_000_000_000,
                            "ffmpeg_path": ffmpeg,
                            "source_process": "fixture",
                            "source_window": "Fixture",
                            "video_path": str(video_path),
                            "state_path": str(state_path),
                            "started_utc": started.isoformat(),
                            "expected_end_utc": (started + timedelta(seconds=3)).isoformat(),
                            "duration_seconds": 3,
                            "framerate": 15,
                        }
                    ),
                    encoding="utf-8",
                )
                return state_path

            local_state = write_state("local", video)
            local = subprocess.run(
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-File",
                    str(capture_script),
                    "-Action",
                    "Complete",
                    "-StatePath",
                    str(local_state),
                    "-IssueId",
                    "local-fixture",
                    "-Revision",
                    "fixture-revision",
                    "-Verdict",
                    "PASS",
                    "-Summary",
                    "Local completion fixture.",
                    "-SkipPublish",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, local.returncode, msg=local.stderr)
            local_result = json.loads(local.stdout)
            self.assertEqual("VALIDATED_LOCAL", local_result["delivery_state"])
            local_receipt = json.loads(Path(local_result["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(3, local_receipt["schema_version"])
            self.assertNotIn("local_path", local_receipt["capture"])
            self.assertNotIn("mount_path", local_receipt["delivery"])

            completed_state = json.loads(local_state.read_text(encoding="utf-8"))
            completed_state["status"] = "RECORDING"
            for key in ("completed_utc", "receipt_path", "delivery_state"):
                completed_state.pop(key, None)
            local_state.write_text(json.dumps(completed_state), encoding="utf-8")
            receipt_before_replay = Path(local_result["receipt_path"]).read_bytes()
            replay = subprocess.run(
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-File",
                    str(capture_script),
                    "-Action",
                    "Complete",
                    "-StatePath",
                    str(local_state),
                    "-IssueId",
                    "local-fixture",
                    "-Revision",
                    "fixture-revision",
                    "-Verdict",
                    "PASS",
                    "-Summary",
                    "Replay must fail.",
                    "-SkipPublish",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(0, replay.returncode)
            self.assertIn("Refusing to overwrite", replay.stderr)
            self.assertEqual(
                receipt_before_replay, Path(local_result["receipt_path"]).read_bytes()
            )

            mounted_video = run_root / "fixture-mounted.mp4"
            shutil.copy2(video, mounted_video)
            mounted_state = write_state("mounted", mounted_video)
            mount_root = run_root / "mount"
            mount_root.mkdir()
            mounted = subprocess.run(
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-File",
                    str(capture_script),
                    "-Action",
                    "Complete",
                    "-StatePath",
                    str(mounted_state),
                    "-IssueId",
                    "mounted-fixture",
                    "-Revision",
                    "fixture-revision",
                    "-Verdict",
                    "PASS",
                    "-Summary",
                    "Mounted completion fixture.",
                    "-PublishRoot",
                    str(mount_root),
                    "-PublishBaseUrl",
                    "https://example.invalid/review",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, mounted.returncode, msg=mounted.stderr)
            mounted_result = json.loads(mounted.stdout)
            self.assertEqual("PUBLISHED_TO_MOUNT", mounted_result["delivery_state"])
            self.assertTrue(Path(mounted_result["publish_video_path"]).is_file())
            published_receipt_path = Path(mounted_result["publish_receipt_path"])
            self.assertTrue(published_receipt_path.is_file())
            published_text = published_receipt_path.read_text(encoding="utf-8")
            published_receipt = json.loads(published_text)
            self.assertEqual(3, published_receipt["schema_version"])

            def strings(value: object) -> list[str]:
                if isinstance(value, str):
                    return [value]
                if isinstance(value, dict):
                    return [item for child in value.values() for item in strings(child)]
                if isinstance(value, list):
                    return [item for child in value for item in strings(child)]
                return []

            private_roots = {
                str(run_root.resolve()),
                str(mount_root.resolve()),
                str(Path.home().resolve()),
            }
            username = Path.home().name
            for value in strings(published_receipt):
                with self.subTest(receipt_value=value):
                    self.assertFalse(
                        Path(value).is_absolute() or value.startswith("/"),
                        msg=f"published receipt contains an absolute path: {value}",
                    )
                    self.assertFalse(
                        value.startswith("\\\\"),
                        msg=f"published receipt contains a UNC path: {value}",
                    )
                    for private_root in private_roots:
                        self.assertNotIn(private_root.casefold(), value.casefold())
                    if username:
                        self.assertNotIn(username.casefold(), value.casefold())

            self.assertIn("artifact_id", published_receipt["capture"])
            self.assertIn("artifact_id", published_receipt["delivery"])
            self.assertNotIn("local_path", published_text)
            self.assertNotIn("mount_path", published_text)

            rollback_fixture: tuple[Path, Path, str] | None = None
            embedded_private_paths = {
                "windows": r"Review note embeds C:\Users\private\clip.mp4 and must fail.",
                "windows-backtick": r"Review note embeds `C:\Users\private\clip.mp4` and must fail.",
                "windows-angle": r"Review note embeds <C:\Users\private\clip.mp4> and must fail.",
                "unc": r"Review note embeds \\server\share\clip.mp4 and must fail.",
                "unc-backtick": r"Review note embeds `\\server\share\clip.mp4` and must fail.",
                "unc-angle": r"Review note embeds <\\server\share\clip.mp4> and must fail.",
                "posix": "Review note embeds /home/private/clip.mp4 and must fail.",
                "posix-backtick": "Review note embeds `/home/private/clip.mp4` and must fail.",
                "posix-angle": "Review note embeds </home/private/clip.mp4> and must fail.",
            }
            for label, unsafe_summary in embedded_private_paths.items():
                blocked_video = run_root / f"fixture-path-{label}.mp4"
                shutil.copy2(video, blocked_video)
                blocked_state = write_state(f"path-{label}", blocked_video)
                blocked_mount = run_root / f"path-{label}-mount"
                blocked_mount.mkdir()
                issue_id = f"path-{label}-fixture"
                blocked = subprocess.run(
                    [
                        pwsh,
                        "-NoLogo",
                        "-NoProfile",
                        "-File",
                        str(capture_script),
                        "-Action",
                        "Complete",
                        "-StatePath",
                        str(blocked_state),
                        "-IssueId",
                        issue_id,
                        "-Revision",
                        "fixture-revision",
                        "-Verdict",
                        "PASS",
                        "-Summary",
                        unsafe_summary,
                        "-PublishRoot",
                        str(blocked_mount),
                        "-PublishBaseUrl",
                        "https://example.invalid/review",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                with self.subTest(embedded_path=label):
                    self.assertNotEqual(0, blocked.returncode)
                    self.assertIn("absolute filesystem path", blocked.stderr)
                    self.assertEqual(
                        "RECORDING",
                        json.loads(blocked_state.read_text(encoding="utf-8"))["status"],
                    )
                    self.assertEqual(
                        [],
                        [item for item in blocked_mount.rglob("*") if item.is_file()],
                    )
                    self.assertEqual(
                        [],
                        [item for item in blocked_mount.rglob("*") if ".staging-" in item.name],
                    )
                    self.assertEqual([], list(run_root.glob(f"{issue_id}-*.receipt.json")))
                if rollback_fixture is None:
                    rollback_fixture = (blocked_state, blocked_mount, issue_id)

            assert rollback_fixture is not None
            retry_state, retry_mount, retry_issue = rollback_fixture
            retry = subprocess.run(
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-File",
                    str(capture_script),
                    "-Action",
                    "Complete",
                    "-StatePath",
                    str(retry_state),
                    "-IssueId",
                    retry_issue,
                    "-Revision",
                    "fixture-revision",
                    "-Verdict",
                    "PASS",
                    "-Summary",
                    "Retry after transactional rollback.",
                    "-PublishRoot",
                    str(retry_mount),
                    "-PublishBaseUrl",
                    "https://example.invalid/review",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, retry.returncode, msg=retry.stderr)
            retry_result = json.loads(retry.stdout)
            self.assertTrue(Path(retry_result["publish_video_path"]).is_file())
            self.assertTrue(Path(retry_result["publish_receipt_path"]).is_file())

            private_url_video = run_root / "fixture-private-url.mp4"
            shutil.copy2(video, private_url_video)
            private_url_state = write_state("private-url", private_url_video)
            private_url_mount = run_root / "private-url-mount"
            private_url_mount.mkdir()
            rejected_url = subprocess.run(
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-File",
                    str(capture_script),
                    "-Action",
                    "Complete",
                    "-StatePath",
                    str(private_url_state),
                    "-IssueId",
                    "private-url-fixture",
                    "-Revision",
                    "fixture-revision",
                    "-Verdict",
                    "PASS",
                    "-Summary",
                    "Private URL must be rejected.",
                    "-PublishRoot",
                    str(private_url_mount),
                    "-PublishBaseUrl",
                    "https://user:secret@example.invalid/review?token=secret#fragment",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(0, rejected_url.returncode)
            self.assertIn("must not contain userinfo", rejected_url.stderr)
            self.assertEqual([], list(private_url_mount.iterdir()))


if __name__ == "__main__":
    unittest.main()
