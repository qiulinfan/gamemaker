#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastmcp>=3.4,<4",
# ]
# ///
"""Read-only or full end-to-end smoke test for MCP for Unity."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import Client

REQUIRED_TOOLS = {
    "execute_code",
    "manage_scene",
    "manage_gameobject",
    "manage_components",
    "manage_editor",
    "manage_camera",
    "read_console",
}
PROJECT_INFO_URI = "mcpforunity://project/info"


class SmokeFailure(RuntimeError):
    pass


def canonical_project_root(value: Any, label: str) -> Path:
    """Resolve an explicit local Unity project root or fail closed."""
    if not isinstance(value, str) or not value.strip():
        raise SmokeFailure(f"{label} is required")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise SmokeFailure(f"{label} must be an absolute path: {value!r}")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SmokeFailure(f"{label} cannot be resolved: {value!r}: {exc}") from exc
    if not resolved.is_dir():
        raise SmokeFailure(f"{label} is not a directory: {resolved}")
    missing_markers = [
        marker for marker in ("Assets", "ProjectSettings") if not (resolved / marker).is_dir()
    ]
    if missing_markers:
        raise SmokeFailure(
            f"{label} is not a Unity project root; missing: "
            + ", ".join(missing_markers)
        )
    return resolved


def same_canonical_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.fspath(left)) == os.path.normcase(os.fspath(right))


def authorized_screenshot_path(
    project_root: Path, output_folder: str, screenshot_name: str
) -> Path:
    """Confine MCP-created evidence to a new file under project Temp/."""

    folder = Path(output_folder)
    name = Path(screenshot_name)
    if folder.is_absolute() or not output_folder.strip():
        raise SmokeFailure("--output-folder must be a non-empty project-relative path")
    if (
        not screenshot_name.strip()
        or name.name != screenshot_name
        or screenshot_name in {".", ".."}
    ):
        raise SmokeFailure("--screenshot-name must be a single file name")
    temp_root = (project_root / "Temp").resolve(strict=False)
    destination = (project_root / folder / name).resolve(strict=False)
    try:
        destination.relative_to(temp_root)
    except ValueError as exc:
        raise SmokeFailure("Screenshot output must remain under the Unity project Temp directory") from exc
    if destination.exists() or os.path.lexists(destination):
        raise SmokeFailure(f"Refusing to overwrite existing screenshot evidence: {destination}")
    return destination


def structured(result: Any) -> dict[str, Any]:
    value = getattr(result, "structured_content", None)
    if isinstance(value, dict):
        return value
    content = getattr(result, "content", None)
    if content:
        text = getattr(content[0], "text", None)
        if isinstance(text, str):
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise SmokeFailure(f"Tool returned no structured data: {result!r}")


def require_success(label: str, result: Any) -> dict[str, Any]:
    value = structured(result)
    if not value.get("success"):
        raise SmokeFailure(
            f"{label} failed: {value.get('error') or value.get('message') or value}"
        )
    return value


async def read_json_resource(client: Client, uri: str) -> dict[str, Any]:
    values = await client.read_resource(uri)
    if not values:
        raise SmokeFailure(f"Resource returned no content: {uri}")
    text = getattr(values[0], "text", None)
    if not isinstance(text, str):
        raise SmokeFailure(f"Resource is not text JSON: {uri}")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise SmokeFailure(f"Resource JSON is not an object: {uri}")
    if value.get("success") is False:
        raise SmokeFailure(
            f"Resource failed: {uri}: {value.get('error') or value.get('message')}"
        )
    return value


async def verify_project_identity(
    client: Any, expected_root: Path, before_operation: str
) -> dict[str, Any]:
    """Bind a mutation to the explicitly authorized Unity project."""
    value = await read_json_resource(client, PROJECT_INFO_URI)
    data = value.get("data")
    if not isinstance(data, dict):
        raise SmokeFailure(
            f"{PROJECT_INFO_URI} has no data object; refusing {before_operation}"
        )
    reported_value = data.get("projectRoot")
    try:
        reported_root = canonical_project_root(
            reported_value, f"{PROJECT_INFO_URI} data.projectRoot"
        )
    except SmokeFailure as exc:
        raise SmokeFailure(f"{exc}; refusing {before_operation}") from exc
    if not same_canonical_path(expected_root, reported_root):
        raise SmokeFailure(
            "Unity project root mismatch before "
            f"{before_operation}: expected {expected_root}, reported {reported_root}; "
            "refusing to mutate the connected Editor"
        )
    return {
        "expected_project_root": str(expected_root),
        "reported_project_root": str(reported_root),
        "project_name": data.get("projectName"),
        "unity_version": data.get("unityVersion"),
    }


async def call_mutating_tool(
    client: Any,
    expected_root: Path,
    tool_name: str,
    arguments: dict[str, Any],
    operation: str,
) -> Any:
    """Revalidate the routed Unity instance immediately before a mutation."""
    await verify_project_identity(client, expected_root, operation)
    return await client.call_tool(tool_name, arguments)


async def editor_state(client: Client, retry_timeout: float = 10.0) -> dict[str, Any]:
    """Read editor state through transient domain-reload/bridge reconnect gaps."""
    deadline = asyncio.get_running_loop().time() + retry_timeout
    latest_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        try:
            value = await read_json_resource(client, "mcpforunity://editor/state")
            data = value.get("data")
            if not isinstance(data, dict):
                raise SmokeFailure("editor/state has no data object")
            return data
        except SmokeFailure as exc:
            latest_error = exc
            await asyncio.sleep(0.5)
    raise SmokeFailure(
        f"editor/state stayed unavailable for {retry_timeout}s: {latest_error}"
    )


async def wait_for_play_state(
    client: Client, expected: bool, timeout: float
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    latest: dict[str, Any] | None = None
    latest_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        remaining = max(0.5, deadline - asyncio.get_running_loop().time())
        try:
            latest = await editor_state(client, retry_timeout=min(3.0, remaining))
        except SmokeFailure as exc:
            latest_error = exc
            await asyncio.sleep(0.5)
            continue
        play_mode = latest.get("editor", {}).get("play_mode", {})
        if bool(play_mode.get("is_playing")) is expected and (
            expected or not bool(play_mode.get("is_changing"))
        ):
            return latest
        await asyncio.sleep(0.5)
    raise SmokeFailure(
        f"Timed out waiting for is_playing={expected}; "
        f"latest state={latest}; latest error={latest_error}"
    )


async def get_active_scene(client: Client) -> dict[str, Any]:
    result = await client.call_tool("manage_scene", {"action": "get_active"})
    return require_success("manage_scene get_active", result)["data"]


async def get_hierarchy(client: Client) -> dict[str, Any]:
    result = await client.call_tool(
        "manage_scene",
        {
            "action": "get_hierarchy",
            "page_size": 50,
            "max_depth": 4,
            "max_children_per_node": 200,
            "include_transform": True,
        },
    )
    return require_success("manage_scene get_hierarchy", result)["data"]


def choose_camera(hierarchy: dict[str, Any], preferred_name: str) -> dict[str, Any]:
    items = hierarchy.get("items")
    if not isinstance(items, list):
        raise SmokeFailure("Hierarchy has no items")
    cameras = [
        item
        for item in items
        if isinstance(item, dict) and "Camera" in item.get("componentTypes", [])
    ]
    if not cameras:
        raise SmokeFailure("No root GameObject with a Camera component was found")
    for camera in cameras:
        if camera.get("name") == preferred_name:
            return camera
    return cameras[0]


async def camera_fov(client: Client, instance_id: int) -> float:
    uri = f"mcpforunity://scene/gameobject/{instance_id}/component/Camera"
    value = await read_json_resource(client, uri)
    component = value.get("data", {}).get("component", {})
    properties = component.get("properties", {})
    fov = properties.get("fieldOfView")
    if not isinstance(fov, (int, float)):
        raise SmokeFailure(f"Camera fieldOfView is unavailable at {uri}")
    return float(fov)


async def wait_for_file(path: Path, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return
        await asyncio.sleep(0.5)
    raise SmokeFailure(f"Screenshot did not appear within {timeout}s: {path}")


def csharp_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


async def run(
    args: argparse.Namespace, client_factory: Any | None = None
) -> dict[str, Any]:
    expected_project_root: Path | None = None
    if args.full:
        expected_project_root = canonical_project_root(
            getattr(args, "expected_project_root", None), "--expected-project-root"
        )
    if client_factory is None:
        from fastmcp import Client

        client_factory = Client

    report: dict[str, Any] = {
        "url": args.url,
        "mode": "full" if args.full else "read-only",
    }

    async with client_factory(args.url) as client:
        if expected_project_root is not None:
            report["project_identity"] = await verify_project_identity(
                client, expected_project_root, "full smoke test setup"
            )

        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        tool_names = {tool.name for tool in tools}
        missing_tools = sorted(REQUIRED_TOOLS - tool_names)
        if missing_tools:
            raise SmokeFailure(
                "Required Unity tools are missing: " + ", ".join(missing_tools)
            )

        report["discovery"] = {
            "tool_count": len(tools),
            "resource_count": len(resources),
            "resource_template_count": len(templates),
            "required_tools_present": sorted(REQUIRED_TOOLS),
        }

        scene_before = await get_active_scene(client)
        hierarchy_before = await get_hierarchy(client)
        camera_before = choose_camera(hierarchy_before, args.camera_name)
        camera_id_before = int(camera_before["instanceID"])
        fov_before = await camera_fov(client, camera_id_before)

        report["scene_before"] = scene_before
        report["hierarchy"] = {
            "total": hierarchy_before.get("total"),
            "roots": [
                {
                    "name": item.get("name"),
                    "instanceID": item.get("instanceID"),
                    "componentTypes": item.get("componentTypes"),
                }
                for item in hierarchy_before.get("items", [])
                if isinstance(item, dict)
            ],
        }
        report["inspector_read"] = {
            "camera": camera_before.get("name"),
            "instanceID": camera_id_before,
            "fieldOfView": fov_before,
        }

        if not args.full:
            return report

        if bool(scene_before.get("isDirty")):
            raise SmokeFailure(
                "The active scene is dirty; refusing the full mutation/Play test"
            )
        scene_path = scene_before.get("path")
        if not isinstance(scene_path, str) or not scene_path:
            raise SmokeFailure(
                "The full test requires a saved scene path so it can reload "
                "from disk after the Inspector mutation"
            )

        assert expected_project_root is not None
        clear_result = await call_mutating_tool(
            client,
            expected_project_root,
            "read_console",
            {"action": "clear"},
            "Console clear",
        )
        require_success("read_console clear", clear_result)

        target_fov = max(1.0, min(179.0, fov_before + args.fov_delta))
        changed_fov: float | None = None
        restored_fov: float | None = None

        try:
            mutation = await call_mutating_tool(
                client,
                expected_project_root,
                "manage_components",
                {
                    "action": "set_property",
                    "target": camera_id_before,
                    "search_method": "by_id",
                    "component_type": "Camera",
                    "property": "fieldOfView",
                    "value": target_fov,
                },
                "Camera FOV mutation",
            )
            require_success("manage_components set_property", mutation)
            changed_fov = await camera_fov(client, camera_id_before)
            if not math.isclose(changed_fov, target_fov, rel_tol=0, abs_tol=1e-4):
                raise SmokeFailure(
                    f"Inspector mutation mismatch: expected {target_fov}, got {changed_fov}"
                )
        finally:
            # Restore the visible value first, then reopen the originally clean
            # scene from disk. Reopening clears the dirty flag without saving
            # test-induced serialization changes.
            try:
                await call_mutating_tool(
                    client,
                    expected_project_root,
                    "manage_components",
                    {
                        "action": "set_property",
                        "target": camera_id_before,
                        "search_method": "by_id",
                        "component_type": "Camera",
                        "property": "fieldOfView",
                        "value": fov_before,
                    },
                    "Camera FOV restoration",
                )
            finally:
                escaped_path = csharp_string(scene_path)
                reload_result = await call_mutating_tool(
                    client,
                    expected_project_root,
                    "execute_code",
                    {
                        "action": "execute",
                        "code": (
                            "return UnityEditor.SceneManagement.EditorSceneManager"
                            f'.OpenScene("{escaped_path}", '
                            "UnityEditor.SceneManagement.OpenSceneMode.Single).path;"
                        ),
                        "safety_checks": True,
                        "compiler": "auto",
                    },
                    "clean scene reload",
                )
                require_success("execute_code reload clean scene", reload_result)

        hierarchy_restored = await get_hierarchy(client)
        camera_restored = choose_camera(hierarchy_restored, args.camera_name)
        restored_fov = await camera_fov(client, int(camera_restored["instanceID"]))
        scene_restored = await get_active_scene(client)
        if not math.isclose(restored_fov, fov_before, rel_tol=0, abs_tol=1e-4):
            raise SmokeFailure(
                f"Inspector value did not restore after scene reload: "
                f"{fov_before} → {restored_fov}"
            )
        if bool(scene_restored.get("isDirty")):
            raise SmokeFailure("The scene is still dirty after disk reload")

        entered_play = False
        runtime_fov: float | None = None
        screenshot_path: Path | None = None
        expected_screenshot_path = authorized_screenshot_path(
            expected_project_root, args.output_folder, args.screenshot_name
        )
        console_errors: dict[str, Any] | None = None

        try:
            play_result = await call_mutating_tool(
                client,
                expected_project_root,
                "manage_editor",
                {"action": "play"},
                "Play Mode entry",
            )
            require_success("manage_editor play", play_result)
            entered_play = True
            await wait_for_play_state(client, True, args.timeout)

            runtime_hierarchy = await get_hierarchy(client)
            runtime_camera = choose_camera(runtime_hierarchy, args.camera_name)
            runtime_camera_id = int(runtime_camera["instanceID"])
            runtime_fov = await camera_fov(client, runtime_camera_id)

            screenshot_result = await call_mutating_tool(
                client,
                expected_project_root,
                "manage_camera",
                {
                    "action": "screenshot",
                    "capture_source": "game_view",
                    "screenshot_file_name": args.screenshot_name,
                    "output_folder": args.output_folder,
                    "include_image": False,
                    "max_resolution": args.max_resolution,
                },
                "Game View screenshot",
            )
            screenshot_data = require_success(
                "manage_camera screenshot", screenshot_result
            ).get("data", {})
            full_path = screenshot_data.get("fullPath")
            if not isinstance(full_path, str):
                raise SmokeFailure("Screenshot result did not include data.fullPath")
            returned_path = Path(full_path).expanduser()
            if not returned_path.is_absolute():
                raise SmokeFailure("Screenshot data.fullPath must be absolute")
            screenshot_path = returned_path.resolve(strict=False)
            if not same_canonical_path(screenshot_path, expected_screenshot_path):
                raise SmokeFailure(
                    "Screenshot path escaped or differed from the authorized output: "
                    f"expected {expected_screenshot_path}, returned {screenshot_path}"
                )
            await wait_for_file(screenshot_path, args.timeout)
            if not same_canonical_path(
                screenshot_path.resolve(strict=True), expected_screenshot_path
            ):
                raise SmokeFailure("Screenshot evidence resolves outside its authorized path")

            errors_result = await client.call_tool(
                "read_console",
                {
                    "action": "get",
                    "types": ["error"],
                    "count": 50,
                    "format": "detailed",
                    "include_stacktrace": False,
                },
            )
            console_errors = require_success("read_console get errors", errors_result)
        finally:
            if entered_play:
                stop_result = await call_mutating_tool(
                    client,
                    expected_project_root,
                    "manage_editor",
                    {"action": "stop"},
                    "Play Mode stop",
                )
                require_success("manage_editor stop", stop_result)
                await wait_for_play_state(client, False, args.timeout)

        hierarchy_after = await get_hierarchy(client)
        camera_after = choose_camera(hierarchy_after, args.camera_name)
        fov_after = await camera_fov(client, int(camera_after["instanceID"]))
        scene_after = await get_active_scene(client)

        if not math.isclose(fov_after, fov_before, rel_tol=0, abs_tol=1e-4):
            raise SmokeFailure(
                f"Serialized FOV did not restore after Stop: {fov_before} → {fov_after}"
            )
        if bool(scene_after.get("isDirty")):
            raise SmokeFailure("The active scene is dirty after the full smoke test")

        report["full_test"] = {
            "inspector_fov_before": fov_before,
            "inspector_fov_after_mutation": changed_fov,
            "inspector_fov_after_disk_reload": restored_fov,
            "entered_play": True,
            "runtime_fov": runtime_fov,
            "stopped_play": True,
            "serialized_fov_after_stop": fov_after,
            "scene_dirty_after": scene_after.get("isDirty"),
            "screenshot": str(screenshot_path) if screenshot_path else None,
            "screenshot_bytes": (
                screenshot_path.stat().st_size
                if screenshot_path and screenshot_path.is_file()
                else None
            ),
            "console_errors": (
                console_errors.get("data", []) if console_errors else []
            ),
        }
        return report


def print_human(report: dict[str, Any]) -> None:
    identity = report.get("project_identity")
    if identity:
        print(
            "[PASS] project identity: "
            f"{identity['reported_project_root']} matches the authorized root"
        )
    discovery = report["discovery"]
    print(
        f"[PASS] discovery: {discovery['tool_count']} tools, "
        f"{discovery['resource_count']} resources, "
        f"{discovery['resource_template_count']} templates"
    )
    scene = report["scene_before"]
    print(
        f"[PASS] scene: {scene.get('name')!r} path={scene.get('path')!r} "
        f"dirty={scene.get('isDirty')}"
    )
    hierarchy = report["hierarchy"]
    names = ", ".join(root["name"] for root in hierarchy["roots"])
    print(f"[PASS] hierarchy: {hierarchy['total']} root object(s): {names}")
    inspector = report["inspector_read"]
    print(
        f"[PASS] inspector: {inspector['camera']} "
        f"fieldOfView={inspector['fieldOfView']}"
    )
    if "full_test" in report:
        full = report["full_test"]
        print(
            "[PASS] inspector mutation/restore: "
            f"{full['inspector_fov_before']} → "
            f"{full['inspector_fov_after_mutation']} → "
            f"{full['inspector_fov_after_disk_reload']}"
        )
        print(
            "[PASS] play/stop: "
            f"runtime_fov={full['runtime_fov']}; "
            f"serialized_fov_after_stop={full['serialized_fov_after_stop']}"
        )
        print(
            f"[PASS] game view: {full['screenshot']} ({full['screenshot_bytes']} bytes)"
        )
        print(
            f"[PASS] stop/cleanup: scene_dirty={full['scene_dirty_after']}; "
            f"console_error_entries={len(full['console_errors'])}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="http://127.0.0.1:8080/mcp", help="MCP endpoint"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Test Play, runtime Inspector mutation, Game View, and Stop",
    )
    parser.add_argument(
        "--expected-project-root",
        help=(
            "Absolute local Unity project root reported by project/info; "
            "required with --full"
        ),
    )
    parser.add_argument("--camera-name", default="Main Camera")
    parser.add_argument("--fov-delta", type=float, default=-1.0)
    parser.add_argument("--output-folder", default="Temp/MCPValidation")
    parser.add_argument("--screenshot-name", default="unity-mcp-smoke-gameview.png")
    parser.add_argument("--max-resolution", type=int, default=960)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.full and not args.expected_project_root:
        parser.error("--expected-project-root is required with --full")

    try:
        report = asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 - convert all CLI failures to one report
        if args.json:
            print(
                json.dumps(
                    {"success": False, "error": f"{type(exc).__name__}: {exc}"},
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"success": True, **report}, indent=2, ensure_ascii=False))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
