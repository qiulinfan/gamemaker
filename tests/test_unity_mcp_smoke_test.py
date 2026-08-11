from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "skills"
    / "configure-unity-mcp"
    / "scripts"
    / "unity_mcp_smoke_test.py"
)
SPEC = importlib.util.spec_from_file_location("gamemaker_unity_mcp_smoke_test", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class FakeWrongInstanceClient:
    def __init__(self, reported_root: Path) -> None:
        self.reported_root = reported_root
        self.resource_reads: list[str] = []
        self.tool_calls: list[tuple[str, dict[str, object]]] = []
        self.discovery_calls = 0

    async def __aenter__(self) -> "FakeWrongInstanceClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read_resource(self, uri: str) -> list[SimpleNamespace]:
        self.resource_reads.append(uri)
        payload = {
            "success": True,
            "data": {
                "projectRoot": str(self.reported_root),
                "projectName": self.reported_root.name,
                "unityVersion": "fixture",
            },
        }
        return [SimpleNamespace(text=json.dumps(payload))]

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> SimpleNamespace:
        self.tool_calls.append((name, arguments))
        raise AssertionError("wrong-instance test must not call any Unity tool")

    async def list_tools(self) -> list[object]:
        self.discovery_calls += 1
        return []

    async def list_resources(self) -> list[object]:
        self.discovery_calls += 1
        return []

    async def list_resource_templates(self) -> list[object]:
        self.discovery_calls += 1
        return []


class UnityMcpMutationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_project_instance_fails_before_every_tool_call(self) -> None:
        temp_root = ROOT / "Temp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="unity-instance-", dir=temp_root) as temporary:
            fixture_root = Path(temporary)
            expected = fixture_root / "expected-project"
            reported = fixture_root / "wrong-project"
            for project in (expected, reported):
                (project / "Assets").mkdir(parents=True)
                (project / "ProjectSettings").mkdir()

            client = FakeWrongInstanceClient(reported)
            args = argparse.Namespace(
                url="http://127.0.0.1:8080/mcp",
                full=True,
                expected_project_root=str(expected.resolve()),
            )

            with self.assertRaisesRegex(SMOKE.SmokeFailure, "project root mismatch"):
                await SMOKE.run(args, client_factory=lambda _url: client)

            self.assertEqual([SMOKE.PROJECT_INFO_URI], client.resource_reads)
            self.assertEqual([], client.tool_calls, "wrong Unity instance was mutated")
            self.assertEqual(0, client.discovery_calls)

    async def test_full_mode_without_expected_root_never_connects(self) -> None:
        connected = False

        def client_factory(_url: str) -> object:
            nonlocal connected
            connected = True
            raise AssertionError("missing identity must fail before connecting")

        args = argparse.Namespace(
            url="http://127.0.0.1:8080/mcp",
            full=True,
            expected_project_root=None,
        )
        with self.assertRaisesRegex(SMOKE.SmokeFailure, "is required"):
            await SMOKE.run(args, client_factory=client_factory)
        self.assertFalse(connected)


class UnityMcpScreenshotBoundaryTests(unittest.TestCase):
    def test_screenshot_path_is_confined_to_new_project_temp_file(self) -> None:
        temp_root = ROOT / "Temp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="unity-screen-", dir=temp_root) as raw:
            project = Path(raw)
            (project / "Temp").mkdir()
            expected = SMOKE.authorized_screenshot_path(
                project.resolve(), "Temp/MCPValidation", "capture.png"
            )
            self.assertEqual(
                (project / "Temp/MCPValidation/capture.png").resolve(), expected
            )

            expected.parent.mkdir(parents=True)
            expected.write_bytes(b"existing")
            with self.assertRaisesRegex(SMOKE.SmokeFailure, "overwrite"):
                SMOKE.authorized_screenshot_path(
                    project.resolve(), "Temp/MCPValidation", "capture.png"
                )

    def test_screenshot_path_rejects_escape_and_nested_filename(self) -> None:
        temp_root = ROOT / "Temp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="unity-screen-", dir=temp_root) as raw:
            project = Path(raw).resolve()
            (project / "Temp").mkdir()
            for folder, name in (
                ("Assets", "capture.png"),
                ("Temp/../../outside", "capture.png"),
                ("Temp/MCPValidation", "nested/capture.png"),
            ):
                with self.subTest(folder=folder, name=name):
                    with self.assertRaises(SMOKE.SmokeFailure):
                        SMOKE.authorized_screenshot_path(project, folder, name)


if __name__ == "__main__":
    unittest.main()
