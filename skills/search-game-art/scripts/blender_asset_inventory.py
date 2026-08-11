#!/usr/bin/env python3
"""Inventory meshes, rigs, materials, images, and actions inside Blender."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REQUIRED_ISOLATION_FLAGS = {
    "--background",
    "--factory-startup",
    "--disable-autoexec",
    "--offline-mode",
}
bpy: Any = None


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, help=".blend, .fbx, .glb, or .gltf to open/import")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Existing temporary root that must contain --output",
    )
    args = parser.parse_args(argv)
    if bool(args.output) != bool(args.output_root):
        parser.error("--output and --output-root must be supplied together")
    return args


def prepare_output(output: Path, output_root: Path) -> Path:
    root = output_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    destination = output.expanduser().resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Output must stay under --output-root: {root}") from exc
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def require_isolated_runtime(asset: Path, argv: list[str]) -> None:
    """Reject an untrusted .blend unless Blender started in the safe mode."""
    if asset.suffix.lower() != ".blend":
        return
    if "--" not in argv:
        raise RuntimeError("Missing Blender '--' argument boundary for untrusted .blend")
    boundary = argv.index("--")
    launch_args = argv[:boundary]
    if "--python" not in launch_args:
        raise RuntimeError("Inventory script was not launched with Blender --python")
    python_index = launch_args.index("--python")
    missing = sorted(
        flag
        for flag in REQUIRED_ISOLATION_FLAGS
        if flag not in launch_args or launch_args.index(flag) >= python_index
    )
    if missing:
        raise RuntimeError(
            "Untrusted .blend inventory requires isolation flags before the asset: "
            + ", ".join(missing)
        )
    if "--python-exit-code" not in launch_args:
        raise RuntimeError("Untrusted .blend inventory requires --python-exit-code 1")
    exit_code_index = launch_args.index("--python-exit-code")
    if (
        exit_code_index >= python_index
        or
        exit_code_index + 1 >= len(launch_args)
        or launch_args[exit_code_index + 1] != "1"
    ):
        raise RuntimeError("Untrusted .blend inventory requires --python-exit-code 1")
    if not bool(bpy.app.background):
        raise RuntimeError("Untrusted .blend inventory requires background Blender")
    if bpy.data.filepath:
        raise RuntimeError(
            "A .blend was loaded before the inventory safety gate; start from factory settings"
        )


def load_asset(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
        return
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if suffix == ".fbx":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()))
    elif suffix in {".glb", ".gltf"}:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    else:
        raise ValueError(f"Unsupported asset extension: {suffix}")


def action_record(action: bpy.types.Action) -> dict[str, object]:
    paths: list[str] = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for bag in getattr(strip, "channelbags", []):
                paths.extend(curve.data_path for curve in getattr(bag, "fcurves", []))
    if not paths and hasattr(action, "fcurves"):
        paths.extend(curve.data_path for curve in action.fcurves)
    return {
        "name": action.name,
        "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])],
        "curve_count": len(paths),
        "has_pose_bone_curves": any(path.startswith('pose.bones["') for path in paths),
        "has_object_transform_curves": any(path in {"location", "rotation_euler", "rotation_quaternion", "scale"} for path in paths),
    }


def build_inventory(asset: Path | None) -> dict[str, object]:
    objects = list(bpy.data.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    return {
        "asset": str(asset.resolve()) if asset else bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "scene_fps": bpy.context.scene.render.fps,
        "objects": {kind: sum(1 for obj in objects if obj.type == kind) for kind in sorted({obj.type for obj in objects})},
        "meshes": [
            {
                "name": obj.name,
                "vertices": len(obj.data.vertices),
                "edges": len(obj.data.edges),
                "polygons": len(obj.data.polygons),
                "dimensions": [float(value) for value in obj.dimensions],
                "material_slots": [slot.material.name if slot.material else None for slot in obj.material_slots],
            }
            for obj in meshes
        ],
        "armatures": [
            {
                "name": obj.name,
                "bone_count": len(obj.data.bones),
                "bones": [bone.name for bone in obj.data.bones],
            }
            for obj in armatures
        ],
        "materials": sorted(material.name for material in bpy.data.materials),
        "images": sorted({image.filepath or image.name for image in bpy.data.images}),
        "action_count": len(bpy.data.actions),
        "actions": [action_record(action) for action in sorted(bpy.data.actions, key=lambda item: item.name)],
    }


def main() -> int:
    global bpy
    import bpy as blender_python

    bpy = blender_python
    args = parse_args()
    output = prepare_output(args.output, args.output_root) if args.output else None
    if args.asset:
        require_isolated_runtime(args.asset, sys.argv)
        load_asset(args.asset)
    result = build_inventory(args.asset)
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
