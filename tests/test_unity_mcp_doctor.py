from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/configure-unity-mcp/scripts/unity_mcp_doctor.py"
SPEC = importlib.util.spec_from_file_location("gamemaker_unity_mcp_doctor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
DOCTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DOCTOR
SPEC.loader.exec_module(DOCTOR)


class UnityMcpDoctorSecurityTests(unittest.TestCase):
    def _project(self, root: Path, url: str) -> Path:
        project = root / "UnityProject"
        for directory in ("Assets", "Packages", "ProjectSettings", ".codex"):
            (project / directory).mkdir(parents=True, exist_ok=True)
        (project / "Packages/manifest.json").write_text(
            '{"dependencies": {}}', encoding="utf-8"
        )
        (project / ".codex/config.toml").write_text(
            f'[mcp_servers.unityMCP]\nurl = "{url}"\n', encoding="utf-8"
        )
        return project

    def _run(self, project: Path, *extra: str) -> tuple[int, dict]:
        stdout = io.StringIO()
        codex_home = project.parent / "codex-home"
        codex_home.mkdir(exist_ok=True)
        with (
            mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}),
            mock.patch.object(DOCTOR, "find_unity_editors", return_value=[]),
            mock.patch.object(DOCTOR.shutil, "which", return_value=None),
            contextlib.redirect_stdout(stdout),
        ):
            result = DOCTOR.main(["--project", str(project), "--json", *extra])
        return result, json.loads(stdout.getvalue())

    def test_remote_url_is_redacted_and_not_probed_by_default(self) -> None:
        secret_url = "http://alice:s3cr3t@10.20.30.40:8123/mcp?token=hidden#frag"
        with tempfile.TemporaryDirectory() as raw:
            project = self._project(Path(raw), secret_url)
            with (
                mock.patch.object(DOCTOR, "tcp_listening") as tcp,
                mock.patch.object(DOCTOR, "port_owner") as owner,
            ):
                _result, payload = self._run(project)

        tcp.assert_not_called()
        owner.assert_not_called()
        serialized = json.dumps(payload)
        for secret in ("alice", "s3cr3t", "token", "hidden", "frag", "?"):
            self.assertNotIn(secret, serialized)
        self.assertEqual("http://10.20.30.40:8123/mcp", payload["url"])
        port_check = next(check for check in payload["checks"] if check["name"] == "mcp_port")
        self.assertIn("not probed", port_check["detail"])

    def test_remote_probe_requires_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = self._project(Path(raw), "https://mcp.example.test/mcp")
            with mock.patch.object(
                DOCTOR,
                "tcp_listening",
                return_value=(False, "bounded test probe"),
            ) as tcp:
                self._run(project, "--allow-remote-probe")

        tcp.assert_called_once_with("mcp.example.test", 443)

    def test_loopback_literals_are_recognized_without_dns(self) -> None:
        for host in ("localhost", "LOCALHOST.", "127.0.0.1", "127.8.9.10", "::1"):
            with self.subTest(host=host):
                self.assertTrue(DOCTOR.is_loopback_host(host))
        self.assertFalse(DOCTOR.is_loopback_host("example.test"))

    def test_package_and_launch_log_urls_are_sanitized_at_output_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = self._project(Path(raw), "http://127.0.0.1:8080/mcp")
            package_url = (
                "git+ssh://pkguser:pkgsecret@github.com/CoplayDev/unity-mcp.git"
                "?path=/MCPForUnity&token=packagehidden#v1"
            )
            (project / "Packages/manifest.json").write_text(
                json.dumps(
                    {"dependencies": {"com.coplaydev.unity-mcp": package_url}}
                ),
                encoding="utf-8",
            )
            lock_url = (
                "ssh://lockuser:locksecret@github.com/CoplayDev/unity-mcp.git"
                "?token=lockhidden#locked"
            )
            (project / "Packages/packages-lock.json").write_text(
                json.dumps(
                    {
                        "dependencies": {
                            "com.coplaydev.unity-mcp": {"version": lock_url}
                        }
                    }
                ),
                encoding="utf-8",
            )
            log_dir = project / "Library/MCPForUnity/Logs"
            log_dir.mkdir(parents=True)
            (log_dir / "server-launch-8080.log").write_text(
                "Uvicorn running on "
                "http://loguser:logsecret@127.0.0.1:8080/mcp?key=loghidden#frag\n"
                "Plugin registered: "
                "https://pluginuser:pluginsecret@example.invalid/?token=pluginhidden\n"
                "Registered 42 tools\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    DOCTOR, "tcp_listening", return_value=(False, "fixture")
                ),
                mock.patch.object(DOCTOR, "port_owner", return_value=None),
            ):
                _result, payload = self._run(project)

        serialized = json.dumps(payload)
        for secret in (
            "pkguser",
            "pkgsecret",
            "packagehidden",
            "lockuser",
            "locksecret",
            "lockhidden",
            "loguser",
            "logsecret",
            "loghidden",
            "pluginuser",
            "pluginsecret",
            "pluginhidden",
        ):
            self.assertNotIn(secret, serialized)
        package_check = next(
            check for check in payload["checks"] if check["name"] == "unity_mcp_package"
        )
        self.assertEqual(
            "git+ssh://github.com/CoplayDev/unity-mcp.git", package_check["detail"]
        )
        lock_check = next(
            check for check in payload["checks"] if check["name"] == "package_lock"
        )
        self.assertEqual(
            "ssh://github.com/CoplayDev/unity-mcp.git", lock_check["detail"]
        )
        launch_check = next(
            check for check in payload["checks"] if check["name"] == "launch_log"
        )
        self.assertIn("server=http://127.0.0.1:8080/mcp", launch_check["detail"])
        self.assertIn("plugin=registered", launch_check["detail"])
        self.assertNotIn("Plugin registered:", launch_check["detail"])


if __name__ == "__main__":
    unittest.main()
