"""Audit a Blender asset and emit machine-readable JSON.

Run this script with Blender's bundled Python. Examples:

  blender --background --factory-startup --disable-autoexec --offline-mode \
    --python-exit-code 1 asset.blend --python blender_asset_audit.py -- \
    --output audit.json --output-root . --force --require-mesh

  blender --background --factory-startup --disable-autoexec --offline-mode \
    --python-exit-code 1 --python blender_asset_audit.py -- \
    --import-file asset.glb --output import-audit.json --output-root . --force

The script uses only modules bundled with Blender. Physical measurements are
reported in both Blender Units and meters. Gate failures exit 2; internal
errors exit 3. The caller should still pass ``--python-exit-code 1`` so an
unexpected Blender-side Python exception can never look successful.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import bmesh
import bpy


SCHEMA_VERSION = "2.0"


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(f"argument error: {message}")


def _argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Audit an open .blend or a cleanly imported exchange asset")
    parser.add_argument("--input-file", help="Cleanly import a .glb, .gltf, or .fbx before auditing")
    parser.add_argument("--output", required=True, help="JSON report path")
    parser.add_argument("--output-root", required=True, help="Authorized directory that must contain the report")
    parser.add_argument("--force", action="store_true", help="Replace an existing report atomically")

    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--scope-collection", help="Audit this collection and all nested objects")
    scope.add_argument("--root-object", help="Audit this object and all descendants")

    pose = parser.add_mutually_exclusive_group()
    pose.add_argument("--frame", type=int, help="Evaluate geometry at this frame")
    pose.add_argument("--rest-pose", action="store_true", help="Evaluate armatures in REST pose")

    parser.add_argument("--require-mesh", action="store_true")
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument(
        "--require-outward-winding",
        action="store_true",
        help="Require every closed connected shell to have consistent, outward face winding",
    )
    parser.add_argument("--require-uv", action="store_true")
    parser.add_argument("--require-material", action="store_true")
    parser.add_argument("--require-referenced-images-resolve", action="store_true")
    parser.add_argument("--min-image-textures", type=int)
    parser.add_argument("--require-armature", action="store_true")
    parser.add_argument("--require-actions", action="store_true")
    parser.add_argument("--require-all-weighted", action="store_true")
    parser.add_argument("--require-normalized-weights", action="store_true")
    parser.add_argument("--max-triangles", type=int)
    parser.add_argument("--max-bones", type=int, help="Maximum total bones")
    parser.add_argument("--max-deform-bones", type=int)
    parser.add_argument("--min-deform-bones", type=int)
    parser.add_argument("--max-influences", type=int)

    parser.add_argument("--expected-dimensions-m", type=float, nargs=3, metavar=("X", "Y", "Z"))
    parser.add_argument("--expected-ground-z-m", type=float)
    parser.add_argument("--tolerance-m", type=float, default=0.001)
    parser.add_argument("--meters-per-unit", type=float, help="Explicit conversion for non-METRIC scenes")
    parser.add_argument("--position-weld-tolerance-m", type=float, default=0.000001)

    parser.add_argument("--expected-fps", type=float)
    parser.add_argument("--expected-loop-frames", type=float, nargs=3, metavar=("START", "MID", "END"))
    parser.add_argument("--animation-tolerance", type=float, default=0.00001)
    return parser


def _finite(name: str, value: float | None, *, minimum: float | None = None, positive: bool = False) -> None:
    if value is None:
        return
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _validate_args(args) -> None:
    for name in (
        "max_triangles",
        "max_bones",
        "max_deform_bones",
        "min_deform_bones",
        "max_influences",
        "min_image_textures",
    ):
        value = getattr(args, name)
        if value is not None and value < 0:
            raise ValueError(f"--{name.replace('_', '-')} must be non-negative")

    if args.expected_dimensions_m:
        for index, value in enumerate(args.expected_dimensions_m):
            _finite(f"expected_dimensions_m[{index}]", value, positive=True)
    _finite("expected_ground_z_m", args.expected_ground_z_m)
    _finite("tolerance_m", args.tolerance_m, minimum=0.0)
    _finite("meters_per_unit", args.meters_per_unit, positive=True)
    _finite("position_weld_tolerance_m", args.position_weld_tolerance_m, minimum=0.0)
    _finite("expected_fps", args.expected_fps, positive=True)
    _finite("animation_tolerance", args.animation_tolerance, minimum=0.0)

    if args.expected_loop_frames:
        start, middle, end = args.expected_loop_frames
        for index, value in enumerate(args.expected_loop_frames):
            _finite(f"expected_loop_frames[{index}]", value)
        if not start < middle < end:
            raise ValueError("--expected-loop-frames must satisfy START < MID < END")

    if args.require_outward_winding and not args.require_closed:
        raise ValueError("--require-outward-winding requires --require-closed")

    if args.input_file:
        path = Path(args.input_file).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {path}")
        if path.suffix.lower() not in {".glb", ".gltf", ".fbx"}:
            raise ValueError("--input-file supports only .glb, .gltf, and .fbx")
        if path.suffix.lower() in {".glb", ".gltf"} and args.meters_per_unit is not None:
            raise ValueError("GLB/glTF units are meters; do not pass --meters-per-unit")
        if path.suffix.lower() == ".fbx" and args.meters_per_unit is None:
            raise ValueError("FBX import requires explicit --meters-per-unit because FBX unit metadata varies")


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rounded(values, digits: int = 9) -> list[float]:
    return [round(float(value), digits) for value in values]


def _canonical_digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _quantized_position(vector, meters_per_unit: float, tolerance_m: float) -> tuple[int, int, int]:
    quantum = tolerance_m if tolerance_m > 0 else 1e-9
    return tuple(
        int(round(float(vector[index]) * meters_per_unit / quantum))
        for index in range(3)
    )


def _mesh_semantic_digests(
    mesh,
    matrix_world,
    material_names: list[str | None],
    meters_per_unit: float | None,
    position_tolerance_m: float,
) -> dict:
    if meters_per_unit is None:
        return {
            "position_quantum_m": None,
            "surface_triangle_digest": None,
            "normal_triangle_digest": None,
            "uv_triangle_digest": None,
            "material_triangle_digest": None,
        }

    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active
    surface_signatures = []
    normal_signatures = []
    uv_signatures = []
    material_signatures = []
    normal_matrix = matrix_world.to_3x3().inverted_safe().transposed()
    for triangle in mesh.loop_triangles:
        positions = [
            _quantized_position(
                matrix_world @ mesh.vertices[vertex_index].co,
                meters_per_unit,
                position_tolerance_m,
            )
            for vertex_index in triangle.vertices
        ]
        surface_signature = tuple(sorted(positions))
        surface_signatures.append(surface_signature)

        normal_corners = []
        for loop_index in triangle.loops:
            vertex_index = mesh.loops[loop_index].vertex_index
            position = _quantized_position(
                matrix_world @ mesh.vertices[vertex_index].co,
                meters_per_unit,
                position_tolerance_m,
            )
            normal = (normal_matrix @ mesh.corner_normals[loop_index].vector).normalized()
            normal_corners.append(
                (
                    position,
                    tuple(int(round(float(value) / 1e-5)) for value in normal),
                )
            )
        normal_signatures.append(tuple(sorted(normal_corners)))

        polygon = mesh.polygons[triangle.polygon_index]
        material_index = int(polygon.material_index)
        material_name = (
            material_names[material_index]
            if 0 <= material_index < len(material_names)
            else None
        )
        material_signatures.append((surface_signature, material_name))

        if uv_layer is not None:
            corners = []
            for loop_index in triangle.loops:
                vertex_index = mesh.loops[loop_index].vertex_index
                position = _quantized_position(
                    matrix_world @ mesh.vertices[vertex_index].co,
                    meters_per_unit,
                    position_tolerance_m,
                )
                uv = uv_layer.data[loop_index].uv
                uv_signature = (
                    int(round(float(uv.x) / 1e-6)),
                    int(round(float(uv.y) / 1e-6)),
                )
                corners.append((position, uv_signature))
            uv_signatures.append(tuple(sorted(corners)))

    surface_signatures.sort()
    normal_signatures.sort()
    material_signatures.sort(key=repr)
    uv_signatures.sort()
    return {
        "position_quantum_m": position_tolerance_m if position_tolerance_m > 0 else 1e-9,
        "surface_triangle_digest": _canonical_digest(surface_signatures),
        "normal_triangle_digest": _canonical_digest(normal_signatures),
        "uv_triangle_digest": _canonical_digest(uv_signatures) if uv_layer is not None else None,
        "material_triangle_digest": _canonical_digest(material_signatures),
    }


def _raw_bounds(points) -> dict | None:
    points = list(points)
    if not points:
        return None
    minimum = [min(float(point[index]) for point in points) for index in range(3)]
    maximum = [max(float(point[index]) for point in points) for index in range(3)]
    return {
        "min": minimum,
        "max": maximum,
        "dimensions": [maximum[index] - minimum[index] for index in range(3)],
    }


def _combine_raw_bounds(bounds_items) -> dict | None:
    items = [item for item in bounds_items if item]
    if not items:
        return None
    minimum = [min(item["min"][index] for item in items) for index in range(3)]
    maximum = [max(item["max"][index] for item in items) for index in range(3)]
    return {
        "min": minimum,
        "max": maximum,
        "dimensions": [maximum[index] - minimum[index] for index in range(3)],
    }


def _format_bounds(raw: dict | None, meters_per_unit: float | None) -> dict | None:
    if raw is None:
        return None
    report = {
        "blender_units": {key: _rounded(raw[key]) for key in ("min", "max", "dimensions")},
        "meters": None,
    }
    if meters_per_unit is not None:
        report["meters"] = {
            key: _rounded(value * meters_per_unit for value in raw[key])
            for key in ("min", "max", "dimensions")
        }
    return report


def _issue(issues: list[dict], severity: str, code: str, message: str, **context) -> None:
    item = {"severity": severity, "code": code, "message": message}
    if context:
        item["context"] = context
    issues.append(item)


def _topology(mesh) -> dict:
    mesh.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    result = {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "polygons": len(mesh.polygons),
        "triangles": len(mesh.loop_triangles),
        "boundary_edges": sum(1 for edge in bm.edges if edge.is_boundary),
        "non_manifold_edges_excluding_boundaries": sum(
            1 for edge in bm.edges if not edge.is_manifold and not edge.is_boundary
        ),
        "loose_edges": sum(1 for edge in bm.edges if not edge.link_faces),
        "loose_vertices": sum(1 for vertex in bm.verts if not vertex.link_edges),
        "degenerate_faces": sum(1 for face in bm.faces if face.calc_area() <= 1e-12),
    }
    bm.free()
    return result


def _closed_component_reports(bm, meters_per_unit: float | None) -> list[dict]:
    """Report connected face shells and their orientation after position welding.

    Signed volume is meaningful only for a closed, consistently wound shell. A
    positive value follows Blender's outward/right-handed convention. Computing
    each disconnected shell separately prevents a large correct shell from
    cancelling or hiding a smaller inverted shell.
    """

    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    bm.verts.index_update()
    unseen = set(bm.faces)
    reports = []
    while unseen:
        seed = min(unseen, key=lambda face: face.index)
        stack = [seed]
        component_faces = set()
        while stack:
            face = stack.pop()
            if face not in unseen:
                continue
            unseen.remove(face)
            component_faces.add(face)
            for edge in face.edges:
                stack.extend(linked for linked in edge.link_faces if linked in unseen)

        component_edges = {edge for face in component_faces for edge in face.edges}
        component_vertices = {vertex for face in component_faces for vertex in face.verts}
        closed = bool(component_faces) and all(len(edge.link_faces) == 2 for edge in component_edges)
        winding_conflicts = sum(
            1
            for edge in component_edges
            if len(edge.link_loops) == 2 and edge.link_loops[0].vert is edge.link_loops[1].vert
        )

        signed_volume = None
        volume_epsilon = None
        orientation = "open"
        if closed:
            origin = min(component_vertices, key=lambda vertex: vertex.index).co.copy()
            signed_volume = 0.0
            for face in component_faces:
                points = [vertex.co - origin for vertex in face.verts]
                for index in range(1, len(points) - 1):
                    signed_volume += float(points[0].dot(points[index].cross(points[index + 1]))) / 6.0
            spans = [
                max(float(vertex.co[axis]) for vertex in component_vertices)
                - min(float(vertex.co[axis]) for vertex in component_vertices)
                for axis in range(3)
            ]
            extent = max(spans, default=0.0)
            volume_epsilon = max(1e-18, extent**3 * 1e-12)
            if winding_conflicts:
                orientation = "inconsistent"
            elif signed_volume > volume_epsilon:
                orientation = "outward"
            elif signed_volume < -volume_epsilon:
                orientation = "inward"
            else:
                orientation = "zero_or_indeterminate"

        reports.append(
            {
                "faces": len(component_faces),
                "edges": len(component_edges),
                "vertices": len(component_vertices),
                "closed": closed,
                "winding_conflict_edges": winding_conflicts,
                "signed_volume_blender_units_cubed": (
                    round(signed_volume, 12) if signed_volume is not None else None
                ),
                "signed_volume_meters_cubed": (
                    round(signed_volume * meters_per_unit**3, 12)
                    if signed_volume is not None and meters_per_unit is not None
                    else None
                ),
                "volume_epsilon_blender_units_cubed": volume_epsilon,
                "orientation": orientation,
            }
        )
    return sorted(
        reports,
        key=lambda item: (not item["closed"], item["orientation"], item["faces"], item["vertices"]),
    )


def _position_welded_topology(
    mesh,
    matrix_world,
    distance_bu: float,
    meters_per_unit: float | None,
) -> dict:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(matrix_world)
    before = len(bm.verts)
    if bm.verts and distance_bu >= 0:
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=distance_bu)
    bm.normal_update()
    components = _closed_component_reports(bm, meters_per_unit)
    result = {
        "vertices": len(bm.verts),
        "merged_vertices": before - len(bm.verts),
        "edges": len(bm.edges),
        "polygons": len(bm.faces),
        "triangles": sum(max(0, len(face.verts) - 2) for face in bm.faces),
        "boundary_edges": sum(1 for edge in bm.edges if edge.is_boundary),
        "non_manifold_edges_excluding_boundaries": sum(
            1 for edge in bm.edges if not edge.is_manifold and not edge.is_boundary
        ),
        "loose_edges": sum(1 for edge in bm.edges if not edge.link_faces),
        "loose_vertices": sum(1 for vertex in bm.verts if not vertex.link_edges),
        "degenerate_faces": sum(1 for face in bm.faces if face.calc_area() <= 1e-12),
        "connected_face_components": len(components),
        "closed_components": sum(1 for item in components if item["closed"]),
        "open_components": sum(1 for item in components if not item["closed"]),
        "outward_closed_components": sum(1 for item in components if item["orientation"] == "outward"),
        "inward_closed_components": sum(1 for item in components if item["orientation"] == "inward"),
        "indeterminate_closed_components": sum(
            1 for item in components if item["orientation"] in {"inconsistent", "zero_or_indeterminate"}
        ),
        "winding_conflict_edges": sum(item["winding_conflict_edges"] for item in components),
        "components": components,
    }
    bm.free()
    return result


def _uv_report(mesh) -> dict:
    layers = [layer.name for layer in mesh.uv_layers]
    active = mesh.uv_layers.active
    if active is None:
        return {
            "layers": layers,
            "active": None,
            "finite": False,
            "unique_coordinates": 0,
            "nonzero_area_polygons": 0,
            "collapsed_polygon_count": len(mesh.polygons),
            "polygon_count": len(mesh.polygons),
        }

    coordinates = [loop.uv.copy() for loop in active.data]
    finite = all(math.isfinite(float(value)) for uv in coordinates for value in uv)
    unique_coordinates = len({(round(float(uv.x), 9), round(float(uv.y), 9)) for uv in coordinates})
    nonzero_area = 0
    for polygon in mesh.polygons:
        points = [active.data[index].uv for index in polygon.loop_indices]
        area_twice = 0.0
        for index, point in enumerate(points):
            following = points[(index + 1) % len(points)]
            area_twice += float(point.x) * float(following.y) - float(following.x) * float(point.y)
        if abs(area_twice) > 1e-12:
            nonzero_area += 1
    return {
        "layers": layers,
        "active": active.name,
        "finite": finite,
        "unique_coordinates": unique_coordinates,
        "nonzero_area_polygons": nonzero_area,
        "collapsed_polygon_count": len(mesh.polygons) - nonzero_area,
        "polygon_count": len(mesh.polygons),
    }


def _material_assignment_report(obj, mesh) -> dict:
    slots = [slot.material.name if slot.material else None for slot in obj.material_slots]
    missing_polygons = 0
    used_indices = set()
    for polygon in mesh.polygons:
        index = int(polygon.material_index)
        used_indices.add(index)
        if index >= len(slots) or not slots[index]:
            missing_polygons += 1
    return {
        "slots": slots,
        "used_slot_indices": sorted(used_indices),
        "polygons_without_material": missing_polygons,
    }


def _find_armature(obj):
    armature = obj.find_armature()
    if armature is not None:
        return armature
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object is not None:
            return modifier.object
    return None


def _weight_report(
    obj,
    mesh,
    armature,
    meters_per_unit: float | None,
    position_tolerance_m: float,
) -> dict:
    deform_names = {
        bone.name for bone in armature.data.bones if bone.use_deform
    } if armature else set()
    group_names = {group.index: group.name for group in obj.vertex_groups}
    weighted = 0
    unweighted = 0
    non_normalized = 0
    max_influences = 0
    unrelated_positive_assignments = 0
    canonical_signatures = set()

    for vertex in mesh.vertices:
        weights = []
        named_weights = []
        for element in vertex.groups:
            name = group_names.get(element.group)
            weight = float(element.weight)
            if weight <= 0:
                continue
            if name in deform_names:
                weights.append(weight)
                named_weights.append((name, round(weight, 6)))
            else:
                unrelated_positive_assignments += 1
        has_weight = bool(weights)
        weighted += int(has_weight)
        unweighted += int(not has_weight)
        non_normalized += int(has_weight and abs(sum(weights) - 1.0) > 1e-4)
        max_influences = max(max_influences, len(weights))
        if meters_per_unit is not None:
            position = _quantized_position(
                obj.matrix_world @ vertex.co,
                meters_per_unit,
                position_tolerance_m,
            )
            canonical_signatures.add((position, tuple(sorted(named_weights))))

    return {
        "armature": armature.name if armature else None,
        "deform_bone_groups": sorted(name for name in group_names.values() if name in deform_names),
        "unrelated_vertex_groups": sorted(name for name in group_names.values() if name not in deform_names),
        "weighted_vertices": weighted,
        "unweighted_vertices": unweighted,
        "non_normalized_vertices": non_normalized,
        "max_influences": max_influences,
        "unrelated_positive_assignments": unrelated_positive_assignments,
        "canonical_position_weight_signature_count": len(canonical_signatures),
        "canonical_position_weight_digest": (
            _canonical_digest(sorted(canonical_signatures, key=repr))
            if meters_per_unit is not None
            else None
        ),
    }


def _evaluated_mesh(evaluated_obj, depsgraph):
    try:
        return evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    except (TypeError, RuntimeError):
        return evaluated_obj.to_mesh()


def _mesh_report(obj: bpy.types.Object, issues: list[dict], args, meters_per_unit: float | None):
    mesh = obj.data
    depsgraph = bpy.context.evaluated_depsgraph_get()
    source_topology = _topology(mesh)
    source_bounds_raw = _raw_bounds(obj.matrix_world @ vertex.co for vertex in mesh.vertices)
    weld_distance_bu = (
        args.position_weld_tolerance_m / meters_per_unit
        if meters_per_unit is not None
        else 0.0
    )
    source_welded = _position_welded_topology(
        mesh,
        obj.matrix_world,
        weld_distance_bu,
        meters_per_unit,
    )
    source_material_names = [slot.material.name if slot.material else None for slot in obj.material_slots]
    source_semantic_digests = _mesh_semantic_digests(
        mesh,
        obj.matrix_world,
        source_material_names,
        meters_per_unit,
        args.position_weld_tolerance_m,
    )

    evaluated_obj = obj.evaluated_get(depsgraph)
    evaluated_mesh = _evaluated_mesh(evaluated_obj, depsgraph)
    try:
        evaluated_topology = _topology(evaluated_mesh)
        evaluated_bounds_raw = _raw_bounds(
            evaluated_obj.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices
        )
        evaluated_welded = _position_welded_topology(
            evaluated_mesh,
            evaluated_obj.matrix_world,
            weld_distance_bu,
            meters_per_unit,
        )
        evaluated_uv = _uv_report(evaluated_mesh)
        evaluated_material_assignment = _material_assignment_report(evaluated_obj, evaluated_mesh)
        evaluated_material_names = [
            slot.material.name if slot.material else None
            for slot in evaluated_obj.material_slots
        ]
        evaluated_semantic_digests = _mesh_semantic_digests(
            evaluated_mesh,
            evaluated_obj.matrix_world,
            evaluated_material_names,
            meters_per_unit,
            args.position_weld_tolerance_m,
        )
    finally:
        evaluated_obj.to_mesh_clear()

    source_uv = _uv_report(mesh)
    material_assignment = _material_assignment_report(obj, mesh)
    scale = _rounded(obj.scale)
    determinant = float(obj.matrix_world.to_3x3().determinant())

    if any(abs(value - 1.0) > 1e-5 for value in scale):
        _issue(issues, "warning", "MESH_UNAPPLIED_SCALE", "Mesh object has non-unit scale", object=obj.name, scale=scale)
    if abs(determinant) <= 1e-12:
        _issue(issues, "error", "MESH_SINGULAR_TRANSFORM", "Mesh world transform is singular", object=obj.name)
    elif determinant < 0:
        _issue(issues, "error", "MESH_NEGATIVE_DETERMINANT", "Mesh world transform has a negative determinant", object=obj.name)

    if source_welded["non_manifold_edges_excluding_boundaries"]:
        _issue(issues, "error", "MESH_NON_MANIFOLD", "Position-welded mesh has non-manifold edges other than boundaries", object=obj.name, count=source_welded["non_manifold_edges_excluding_boundaries"])
    if source_welded["degenerate_faces"]:
        _issue(issues, "error", "MESH_DEGENERATE_FACES", "Position-welded mesh has zero-area faces", object=obj.name, count=source_welded["degenerate_faces"])
    if source_welded["loose_vertices"] or source_welded["loose_edges"]:
        _issue(issues, "warning", "MESH_LOOSE_GEOMETRY", "Position-welded mesh has loose geometry", object=obj.name, vertices=source_welded["loose_vertices"], edges=source_welded["loose_edges"])
    if args.require_closed and source_welded["boundary_edges"]:
        _issue(issues, "error", "MESH_GEOMETRIC_BOUNDARY_EDGES", "Closed geometry was required but position-welded boundary edges exist", object=obj.name, count=source_welded["boundary_edges"], raw_boundary_edges=source_topology["boundary_edges"])
    if args.require_outward_winding:
        if source_welded["winding_conflict_edges"]:
            _issue(issues, "error", "MESH_INCONSISTENT_WINDING", "Closed geometry has shared edges whose adjacent faces use the same direction", object=obj.name, count=source_welded["winding_conflict_edges"])
        if source_welded["inward_closed_components"]:
            _issue(issues, "error", "MESH_INWARD_WINDING", "One or more closed connected shells have inward face winding", object=obj.name, count=source_welded["inward_closed_components"])
        if source_welded["indeterminate_closed_components"]:
            _issue(issues, "error", "MESH_WINDING_INDETERMINATE", "One or more closed connected shells have inconsistent winding or near-zero signed volume", object=obj.name, count=source_welded["indeterminate_closed_components"])
    if args.require_uv:
        if not source_uv["layers"] or not evaluated_uv["layers"]:
            _issue(issues, "error", "MESH_UV_MISSING", "A UV map was required on source and evaluated geometry", object=obj.name)
        elif not source_uv["finite"] or not evaluated_uv["finite"]:
            _issue(issues, "error", "MESH_UV_NONFINITE", "UV coordinates contain non-finite values", object=obj.name)
        elif source_uv["collapsed_polygon_count"] or evaluated_uv["collapsed_polygon_count"]:
            _issue(
                issues,
                "error",
                "MESH_UV_COLLAPSED",
                "One or more polygons have zero UV area",
                object=obj.name,
                source_collapsed=source_uv["collapsed_polygon_count"],
                evaluated_collapsed=evaluated_uv["collapsed_polygon_count"],
            )
    if args.require_material and (
        material_assignment["polygons_without_material"]
        or evaluated_material_assignment["polygons_without_material"]
    ):
        _issue(
            issues,
            "error",
            "MESH_MATERIAL_ASSIGNMENT_MISSING",
            "One or more source or evaluated polygons have no populated material assignment",
            object=obj.name,
            source_count=material_assignment["polygons_without_material"],
            evaluated_count=evaluated_material_assignment["polygons_without_material"],
        )
    if args.require_material and not material_assignment["slots"]:
        _issue(issues, "error", "MESH_MATERIAL_MISSING", "A material was required but no slots exist", object=obj.name)

    if evaluated_welded["non_manifold_edges_excluding_boundaries"]:
        _issue(issues, "error", "EVALUATED_MESH_NON_MANIFOLD", "Position-welded evaluated mesh has non-manifold edges other than boundaries", object=obj.name, count=evaluated_welded["non_manifold_edges_excluding_boundaries"])
    if evaluated_welded["degenerate_faces"]:
        _issue(issues, "error", "EVALUATED_MESH_DEGENERATE_FACES", "Position-welded evaluated mesh has zero-area faces", object=obj.name, count=evaluated_welded["degenerate_faces"])
    if args.require_closed and evaluated_welded["boundary_edges"]:
        _issue(issues, "error", "EVALUATED_MESH_GEOMETRIC_BOUNDARY_EDGES", "Closed geometry was required but position-welded evaluated boundary edges exist", object=obj.name, count=evaluated_welded["boundary_edges"], raw_boundary_edges=evaluated_topology["boundary_edges"])
    if args.require_outward_winding:
        if evaluated_welded["winding_conflict_edges"]:
            _issue(issues, "error", "EVALUATED_MESH_INCONSISTENT_WINDING", "Evaluated closed geometry has shared edges whose adjacent faces use the same direction", object=obj.name, count=evaluated_welded["winding_conflict_edges"])
        if evaluated_welded["inward_closed_components"]:
            _issue(issues, "error", "EVALUATED_MESH_INWARD_WINDING", "One or more evaluated closed connected shells have inward face winding", object=obj.name, count=evaluated_welded["inward_closed_components"])
        if evaluated_welded["indeterminate_closed_components"]:
            _issue(issues, "error", "EVALUATED_MESH_WINDING_INDETERMINATE", "One or more evaluated closed connected shells have inconsistent winding or near-zero signed volume", object=obj.name, count=evaluated_welded["indeterminate_closed_components"])

    armature_modifiers = [
        modifier.object.name if modifier.object else None
        for modifier in obj.modifiers
        if modifier.type == "ARMATURE"
    ]
    if any(target is None for target in armature_modifiers):
        _issue(issues, "error", "ARMATURE_MODIFIER_TARGET_MISSING", "An Armature modifier has no target", object=obj.name)
    armature = _find_armature(obj)
    weights = _weight_report(
        obj,
        mesh,
        armature,
        meters_per_unit,
        args.position_weld_tolerance_m,
    )
    if armature is not None:
        if args.require_all_weighted and weights["unweighted_vertices"]:
            _issue(issues, "error", "SKIN_UNWEIGHTED_VERTICES", "Armature-driven mesh has vertices without deform-bone weights", object=obj.name, count=weights["unweighted_vertices"])
        elif weights["unweighted_vertices"]:
            _issue(issues, "warning", "SKIN_UNWEIGHTED_VERTICES", "Armature-driven mesh has vertices without deform-bone weights", object=obj.name, count=weights["unweighted_vertices"])
        if args.require_normalized_weights and weights["non_normalized_vertices"]:
            _issue(issues, "error", "SKIN_NON_NORMALIZED_VERTICES", "Deform-bone weights do not sum to one", object=obj.name, count=weights["non_normalized_vertices"])
        elif weights["non_normalized_vertices"]:
            _issue(issues, "warning", "SKIN_NON_NORMALIZED_VERTICES", "Deform-bone weights do not sum to one", object=obj.name, count=weights["non_normalized_vertices"])
        if args.max_influences is not None and weights["max_influences"] > args.max_influences:
            _issue(issues, "error", "SKIN_MAX_INFLUENCES", "Per-vertex deform-bone influence budget exceeded", object=obj.name, actual=weights["max_influences"], maximum=args.max_influences)

    report = {
        "source_topology": source_topology,
        "source_position_welded_topology": source_welded,
        "source_semantic_digests": source_semantic_digests,
        "evaluated_topology": evaluated_topology,
        "evaluated_position_welded_topology": evaluated_welded,
        "evaluated_semantic_digests": evaluated_semantic_digests,
        "position_weld_tolerance_m": args.position_weld_tolerance_m,
        "source_world_bounds": _format_bounds(source_bounds_raw, meters_per_unit),
        "evaluated_world_bounds": _format_bounds(evaluated_bounds_raw, meters_per_unit),
        "source_uv": source_uv,
        "evaluated_uv": evaluated_uv,
        "material_assignment": material_assignment,
        "evaluated_material_assignment": evaluated_material_assignment,
        "vertex_groups": [group.name for group in obj.vertex_groups],
        "armature_modifiers": armature_modifiers,
        "weights": weights,
    }
    return report, source_bounds_raw, evaluated_bounds_raw


def _object_report(obj: bpy.types.Object, issues: list[dict], args, meters_per_unit: float | None):
    report = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "location": _rounded(obj.location),
        "rotation_euler": _rounded(obj.rotation_euler),
        "scale": _rounded(obj.scale),
        "matrix_world": _rounded(value for row in obj.matrix_world for value in row),
        "world_origin_blender_units": _rounded(obj.matrix_world.translation),
        "world_origin_m": (
            _rounded(value * meters_per_unit for value in obj.matrix_world.translation)
            if meters_per_unit is not None
            else None
        ),
        "dimensions_blender_units": _rounded(obj.dimensions),
        "visible_render": not obj.hide_render,
        "modifiers": [
            {"name": modifier.name, "type": modifier.type, "show_render": bool(modifier.show_render)}
            for modifier in obj.modifiers
        ],
    }
    source_bounds = None
    evaluated_bounds = None
    if obj.type == "MESH":
        report["mesh"], source_bounds, evaluated_bounds = _mesh_report(
            obj, issues, args, meters_per_unit
        )
    elif obj.type == "ARMATURE":
        bones = list(obj.data.bones)
        report["armature"] = {
            "bones": len(bones),
            "deform_bones": sum(1 for bone in bones if bone.use_deform),
            "control_bones": sum(1 for bone in bones if not bone.use_deform),
            "root_bones": [bone.name for bone in bones if bone.parent is None],
            "bone_data": [
                {
                    "name": bone.name,
                    "parent": bone.parent.name if bone.parent else None,
                    "use_connect": bool(bone.use_connect),
                    "use_deform": bool(bone.use_deform),
                    "head_local": _rounded(bone.head_local),
                    "tail_local": _rounded(bone.tail_local),
                    "matrix_local": _rounded(
                        value for row in bone.matrix_local for value in row
                    ),
                    "length_blender_units": round(float(bone.length), 9),
                    "length_m": round(float(bone.length) * meters_per_unit, 9) if meters_per_unit else None,
                }
                for bone in bones
            ],
            "constraints": [
                {
                    "owner_bone": pose_bone.name,
                    "name": constraint.name,
                    "type": constraint.type,
                    "target": constraint.target.name if getattr(constraint, "target", None) else None,
                    "subtarget": getattr(constraint, "subtarget", None),
                    "pole_target": constraint.pole_target.name if getattr(constraint, "pole_target", None) else None,
                    "pole_subtarget": getattr(constraint, "pole_subtarget", None),
                    "chain_count": getattr(constraint, "chain_count", None),
                    "use_stretch": getattr(constraint, "use_stretch", None),
                    "influence": round(float(constraint.influence), 9),
                    "mute": bool(constraint.mute),
                }
                for pose_bone in obj.pose.bones
                for constraint in pose_bone.constraints
            ],
        }
    elif obj.type == "LIGHT":
        report["light"] = {"light_type": obj.data.type, "energy": float(obj.data.energy)}
    elif obj.type == "CAMERA":
        report["camera"] = {"camera_type": obj.data.type, "lens_mm": float(obj.data.lens)}
    return report, source_bounds, evaluated_bounds


def _curve_sources(action: bpy.types.Action):
    legacy_fcurves = getattr(action, "fcurves", None)
    if legacy_fcurves is not None:
        return [(None, fcurve) for fcurve in legacy_fcurves]
    result = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                result.extend((int(channelbag.slot.handle), fcurve) for fcurve in channelbag.fcurves)
    return result


def _action_bindings(objects) -> dict[str, list[dict]]:
    bindings: dict[str, list[dict]] = defaultdict(list)
    seen_owners = set()
    owners = []
    for obj in objects:
        owners.append(("OBJECT", obj.name, obj))
        data = getattr(obj, "data", None)
        if data is not None:
            owners.append(("DATA", f"{obj.name}:{data.name}", data))
        shape_keys = getattr(data, "shape_keys", None) if data is not None else None
        if shape_keys is not None:
            owners.append(("SHAPE_KEYS", f"{obj.name}:{shape_keys.name}", shape_keys))

    for owner_type, owner_name, owner in owners:
        pointer = owner.as_pointer() if hasattr(owner, "as_pointer") else id(owner)
        if pointer in seen_owners:
            continue
        seen_owners.add(pointer)
        animation_data = getattr(owner, "animation_data", None)
        if animation_data is None:
            continue
        action = getattr(animation_data, "action", None)
        if action is not None:
            action_slot = getattr(animation_data, "action_slot", None)
            bindings[action.name].append(
                {
                    "owner_type": owner_type,
                    "owner": owner_name,
                    "source": "active_action",
                    "slot_handle": int(action_slot.handle) if action_slot is not None else None,
                    "slot_identifier": getattr(action_slot, "identifier", None),
                }
            )
        for track in getattr(animation_data, "nla_tracks", []):
            for strip in track.strips:
                if strip.action is not None:
                    action_slot = getattr(strip, "action_slot", None)
                    bindings[strip.action.name].append(
                        {
                            "owner_type": owner_type,
                            "owner": owner_name,
                            "source": "nla_strip",
                            "slot_handle": int(action_slot.handle) if action_slot is not None else None,
                            "slot_identifier": getattr(action_slot, "identifier", None),
                            "track": track.name,
                            "strip": strip.name,
                            "frame_start": float(strip.frame_start),
                            "frame_end": float(strip.frame_end),
                            "action_frame_start": float(strip.action_frame_start),
                            "action_frame_end": float(strip.action_frame_end),
                            "scale": float(strip.scale),
                            "repeat": float(strip.repeat),
                        }
                    )
    return bindings


def _action_report(action: bpy.types.Action, bindings: list[dict]) -> dict:
    frame_range = getattr(action, "frame_range", (0.0, 0.0))
    layers = getattr(action, "layers", None)
    channels = []
    total_keyframes = 0
    total_samples = 0
    for slot_handle, fcurve in _curve_sources(action):
        keyframes = [
            {
                "frame": round(float(point.co.x), 9),
                "value": round(float(point.co.y), 9),
                "interpolation": point.interpolation,
            }
            for point in fcurve.keyframe_points
        ]
        samples = [
            {"frame": round(float(point.co.x), 9), "value": round(float(point.co.y), 9)}
            for point in fcurve.sampled_points
        ]
        total_keyframes += len(keyframes)
        total_samples += len(samples)
        channels.append(
            {
                "slot_handle": slot_handle,
                "data_path": fcurve.data_path,
                "array_index": fcurve.array_index,
                "extrapolation": fcurve.extrapolation,
                "mute": bool(fcurve.mute),
                "is_valid": bool(getattr(fcurve, "is_valid", True)),
                "modifier_types": [modifier.type for modifier in fcurve.modifiers],
                "keyframes": keyframes,
                "sampled_points": samples,
            }
        )
    usable_channels = [
        channel
        for channel in channels
        if not channel["mute"]
        and channel["is_valid"]
        and (channel["keyframes"] or channel["sampled_points"])
    ]
    modern_channel_handles = {
        channel["slot_handle"]
        for channel in usable_channels
        if channel["slot_handle"] is not None
    }
    if modern_channel_handles:
        binding_channel_match = any(
            binding.get("slot_handle") in modern_channel_handles
            for binding in bindings
        )
    else:
        binding_channel_match = bool(bindings and usable_channels)
    valid = bool(
        bindings
        and usable_channels
        and binding_channel_match
        and frame_range[1] > frame_range[0]
    )
    return {
        "name": action.name,
        "frame_range": _rounded(frame_range),
        "layers": len(layers) if layers is not None else None,
        "slots": [
            {"handle": int(slot.handle), "identifier": slot.identifier, "target_id_type": slot.target_id_type}
            for slot in getattr(action, "slots", [])
        ],
        "fcurve_count": len(channels),
        "usable_fcurve_count": len(usable_channels),
        "keyframe_count": total_keyframes,
        "sampled_point_count": total_samples,
        "bindings": bindings,
        "binding_channel_match": binding_channel_match,
        "valid_bound_clip": valid,
        "channels": channels,
    }


def _redacted_dependency_path(filepath: str) -> str:
    parsed = urlsplit(filepath)
    if parsed.scheme and parsed.netloc:
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit((parsed.scheme, hostname + port, parsed.path, "", ""))
    return filepath


def _socket_semantics(socket) -> dict:
    links = sorted(
        [
            {
                "from_node_type": link.from_node.type,
                "from_socket": link.from_socket.name,
            }
            for link in socket.links
        ],
        key=repr,
    )
    default_value = getattr(socket, "default_value", None)
    if isinstance(default_value, (int, float, bool, str)):
        default = round(float(default_value), 6) if isinstance(default_value, float) else default_value
    elif default_value is not None and hasattr(default_value, "__iter__"):
        default = _rounded(default_value, 6)
    else:
        default = None
    return {"linked": bool(socket.is_linked), "default": default, "links": links}


def _packed_image_sha256(image) -> str | None:
    packed_file = getattr(image, "packed_file", None) if image is not None else None
    if packed_file is None:
        return None
    try:
        return hashlib.sha256(bytes(packed_file.data)).hexdigest()
    except (AttributeError, BufferError, TypeError, ValueError):
        return None


def _material_report(
    material: bpy.types.Material,
    require_referenced_images_resolve: bool,
    issues: list[dict],
) -> dict:
    image_nodes = []
    node_tree = material.node_tree
    principled_nodes = []
    material_outputs = []
    if node_tree:
        for node in node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                tracked_inputs = {
                    socket.name: _socket_semantics(socket)
                    for socket in node.inputs
                }
                principled_nodes.append({"inputs": tracked_inputs})
            if node.type == "OUTPUT_MATERIAL":
                surface = node.inputs.get("Surface")
                material_outputs.append(
                    {
                        "active": bool(getattr(node, "is_active_output", False)),
                        "surface": _socket_semantics(surface) if surface is not None else None,
                    }
                )
            if node.type != "TEX_IMAGE":
                continue
            image = getattr(node, "image", None)
            path = Path(bpy.path.abspath(image.filepath)) if image and image.filepath else None
            exists = bool(path and path.is_file())
            packed = bool(image and image.packed_file)
            content_sha256 = _packed_image_sha256(image) or (_sha256(path) if exists else None)
            if require_referenced_images_resolve and image is None:
                _issue(
                    issues,
                    "error",
                    "MATERIAL_IMAGE_UNASSIGNED",
                    "An image-texture node has no image assigned",
                    material=material.name,
                    node=node.name,
                )
            elif require_referenced_images_resolve and not packed and not exists:
                _issue(issues, "error", "MATERIAL_IMAGE_MISSING", "Material image is neither packed nor present on disk", material=material.name, node=node.name, image=image.name, filepath=_redacted_dependency_path(str(path) if path else ""))
            image_nodes.append(
                {
                    "node": node.name,
                    "image": image.name if image else None,
                    "filepath": _redacted_dependency_path(str(path) if path else "") if image else None,
                    "exists": exists,
                    "sha256": _sha256(path) if exists else None,
                    "content_sha256": content_sha256,
                    "colorspace": image.colorspace_settings.name if image else None,
                    "size": [int(value) for value in image.size] if image else None,
                    "channels": int(image.channels) if image else None,
                    "alpha_mode": image.alpha_mode if image else None,
                    "packed": packed,
                }
            )
    direct_active_principled_output = any(
        output["active"]
        and output["surface"] is not None
        and output["surface"]["linked"]
        and len(output["surface"]["links"]) == 1
        and output["surface"]["links"][0]["from_node_type"] == "BSDF_PRINCIPLED"
        for output in material_outputs
    )
    tracked_inputs_unlinked = all(
        not socket["linked"]
        for principled in principled_nodes
        for socket in principled["inputs"].values()
    )
    validation_profile = (
        "constant_principled_core_v1"
        if len(principled_nodes) == 1
        and not image_nodes
        and direct_active_principled_output
        and tracked_inputs_unlinked
        else "complex_material_unvalidated"
    )
    semantics = {
        "validation_profile": validation_profile,
        "use_nodes": bool(node_tree),
        "surface_render_method": getattr(material, "surface_render_method", None),
        "use_backface_culling": getattr(material, "use_backface_culling", None),
        "principled_nodes": sorted(principled_nodes, key=repr),
        "material_outputs": sorted(material_outputs, key=repr),
        "images": sorted(
            [
                {
                    "content_sha256": item["content_sha256"],
                    "colorspace": item["colorspace"],
                    "size": item["size"],
                    "channels": item["channels"],
                    "alpha_mode": item["alpha_mode"],
                }
                for item in image_nodes
            ],
            key=repr,
        ),
    }
    return {
        "name": material.name,
        "use_nodes": bool(node_tree),
        "node_count": len(node_tree.nodes) if node_tree else 0,
        "image_nodes": image_nodes,
        "semantics": semantics,
        "semantic_digest": _canonical_digest(semantics),
    }


def _scope_objects(args):
    if args.scope_collection:
        collection = bpy.data.collections.get(args.scope_collection)
        if collection is None:
            raise ValueError(f"Collection does not exist: {args.scope_collection}")
        objects = list(collection.all_objects)
        scope = {"type": "collection", "name": collection.name}
    elif args.root_object:
        root = bpy.data.objects.get(args.root_object)
        if root is None:
            raise ValueError(f"Root object does not exist: {args.root_object}")
        objects = [root, *list(root.children_recursive)]
        scope = {"type": "root_object", "name": root.name}
    else:
        objects = list(bpy.context.scene.objects)
        scope = {"type": "active_scene", "name": bpy.context.scene.name}
    unique = {obj.as_pointer(): obj for obj in objects}
    return sorted(unique.values(), key=lambda item: item.name), scope


def _animation_signature(objects, frame: float) -> list[float]:
    scene = bpy.context.scene
    scene.frame_set(int(math.floor(frame)), subframe=float(frame - math.floor(frame)))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    signature = []
    for obj in sorted(objects, key=lambda item: item.name):
        evaluated = obj.evaluated_get(depsgraph)
        signature.extend(float(value) for row in evaluated.matrix_world for value in row)
        if evaluated.type == "ARMATURE":
            for bone in sorted(evaluated.pose.bones, key=lambda item: item.name):
                signature.extend(float(value) for row in bone.matrix for value in row)
    return signature


def _loop_report(objects, frames, tolerance: float) -> dict:
    original_frame = float(bpy.context.scene.frame_current) + float(bpy.context.scene.frame_subframe)
    try:
        start_signature = _animation_signature(objects, frames[0])
        middle_signature = _animation_signature(objects, frames[1])
        end_signature = _animation_signature(objects, frames[2])
    finally:
        bpy.context.scene.frame_set(int(math.floor(original_frame)), subframe=original_frame - math.floor(original_frame))
    if not (len(start_signature) == len(middle_signature) == len(end_signature)):
        return {"frames": _rounded(frames), "comparable": False, "start_end_match": False, "middle_differs": False}
    start_end_delta = max((abs(a - b) for a, b in zip(start_signature, end_signature)), default=0.0)
    start_middle_delta = max((abs(a - b) for a, b in zip(start_signature, middle_signature)), default=0.0)
    return {
        "frames": _rounded(frames),
        "comparable": True,
        "signature_values": len(start_signature),
        "pose_digests_1e-6": {
            "start": _canonical_digest([round(value, 6) for value in start_signature]),
            "middle": _canonical_digest([round(value, 6) for value in middle_signature]),
            "end": _canonical_digest([round(value, 6) for value in end_signature]),
        },
        "motion_digests_1e-6": {
            "start_to_middle": _canonical_digest(
                [round(middle - start, 6) for start, middle in zip(start_signature, middle_signature)]
            ),
            "start_to_end": _canonical_digest(
                [round(end - start, 6) for start, end in zip(start_signature, end_signature)]
            ),
        },
        "motion_delta_vectors": {
            "start_to_middle": [
                round(middle - start, 9)
                for start, middle in zip(start_signature, middle_signature)
            ],
            "start_to_end": [
                round(end - start, 9)
                for start, end in zip(start_signature, end_signature)
            ],
        },
        "start_end_max_abs_delta": round(start_end_delta, 12),
        "start_middle_max_abs_delta": round(start_middle_delta, 12),
        "tolerance": tolerance,
        "start_end_match": start_end_delta <= tolerance,
        "middle_differs": start_middle_delta > tolerance,
    }


def _unit_context(args) -> dict:
    scene = bpy.context.scene
    if args.meters_per_unit is not None:
        factor = args.meters_per_unit
        source = "explicit_argument"
    elif scene.unit_settings.system == "METRIC":
        factor = float(scene.unit_settings.scale_length)
        source = "scene_metric_scale_length"
    else:
        factor = None
        source = "unavailable"
    return {
        "unit_system": scene.unit_settings.system,
        "scale_length": float(scene.unit_settings.scale_length),
        "meters_per_blender_unit": factor,
        "conversion_source": source,
    }


def _geometry_gate_requested(args) -> bool:
    return any(
        (
            args.require_mesh,
            args.require_closed,
            args.require_outward_winding,
            args.require_uv,
            args.require_material,
            args.require_referenced_images_resolve,
            args.min_image_textures is not None,
            args.require_all_weighted,
            args.require_normalized_weights,
            args.max_triangles is not None,
            args.max_influences is not None,
            args.expected_dimensions_m is not None,
            args.expected_ground_z_m is not None,
        )
    )


def audit(args, run_id: str, input_metadata: dict) -> dict:
    issues: list[dict] = []
    scene = bpy.context.scene
    if args.frame is not None:
        scene.frame_set(args.frame)
    if args.rest_pose:
        for obj in scene.objects:
            if obj.type == "ARMATURE":
                obj.data.pose_position = "REST"

    objects_in_scope, scope = _scope_objects(args)
    units = _unit_context(args)
    meters_per_unit = units["meters_per_blender_unit"]
    physical_gate = args.expected_dimensions_m is not None or args.expected_ground_z_m is not None
    if physical_gate and meters_per_unit is None:
        _issue(issues, "error", "SCENE_METERS_PER_UNIT_UNAVAILABLE", "Physical gates require a METRIC scene or explicit --meters-per-unit")

    object_reports = []
    source_bounds_items = []
    evaluated_bounds_items = []
    for obj in objects_in_scope:
        report, source_bounds, evaluated_bounds = _object_report(
            obj, issues, args, meters_per_unit
        )
        object_reports.append(report)
        source_bounds_items.append(source_bounds)
        evaluated_bounds_items.append(evaluated_bounds)

    type_counts = Counter(item["type"] for item in object_reports)
    source_triangles = sum(
        item.get("mesh", {}).get("source_topology", {}).get("triangles", 0)
        for item in object_reports
    )
    evaluated_triangles = sum(
        item.get("mesh", {}).get("evaluated_topology", {}).get("triangles", 0)
        for item in object_reports
    )
    source_scene_bounds_raw = _combine_raw_bounds(source_bounds_items)
    evaluated_scene_bounds_raw = _combine_raw_bounds(evaluated_bounds_items)
    armature_reports = [item["armature"] for item in object_reports if "armature" in item]
    total_bones = sum(item["bones"] for item in armature_reports)
    deform_bones = sum(item["deform_bones"] for item in armature_reports)
    skinned_meshes = sum(
        1 for item in object_reports if item.get("mesh", {}).get("weights", {}).get("armature")
    )

    bindings = _action_bindings(objects_in_scope)
    action_reports = [_action_report(action, bindings.get(action.name, [])) for action in bpy.data.actions]
    usable_actions = [item for item in action_reports if item["valid_bound_clip"]]

    mesh_count = type_counts.get("MESH", 0)
    if not mesh_count:
        severity = "error" if _geometry_gate_requested(args) else "warning"
        _issue(issues, severity, "SCENE_NO_MESH", "Audit scope contains no mesh objects")
    elif _geometry_gate_requested(args) and evaluated_triangles == 0:
        _issue(issues, "error", "SCENE_NO_EVALUATED_TRIANGLES", "Geometry gates were requested but evaluated triangle count is zero")
    if args.require_armature and not armature_reports:
        _issue(issues, "error", "SCENE_ARMATURE_MISSING", "An armature was required but none exists in scope")
    if args.require_armature and armature_reports and total_bones == 0:
        _issue(issues, "error", "SCENE_ARMATURE_EMPTY", "An armature exists but contains no bones")
    if args.require_actions and not usable_actions:
        _issue(issues, "error", "SCENE_BOUND_ACTION_MISSING", "A non-empty action bound to an in-scope owner was required")
    if (args.require_all_weighted or args.require_normalized_weights or args.max_influences is not None) and not skinned_meshes:
        _issue(issues, "error", "SCENE_SKINNED_MESH_MISSING", "Skin-weight gates were requested but no in-scope mesh is associated with an armature")
    if args.max_triangles is not None and evaluated_triangles > args.max_triangles:
        _issue(issues, "error", "SCENE_TRIANGLE_BUDGET", "Evaluated triangle budget exceeded", actual=evaluated_triangles, maximum=args.max_triangles)
    if args.max_bones is not None and total_bones > args.max_bones:
        _issue(issues, "error", "SCENE_BONE_BUDGET", "Total bone budget exceeded", actual=total_bones, maximum=args.max_bones)
    if args.max_deform_bones is not None and deform_bones > args.max_deform_bones:
        _issue(issues, "error", "SCENE_DEFORM_BONE_BUDGET", "Deform bone budget exceeded", actual=deform_bones, maximum=args.max_deform_bones)
    if args.min_deform_bones is not None and deform_bones < args.min_deform_bones:
        _issue(issues, "error", "SCENE_DEFORM_BONES_TOO_FEW", "Minimum deform bone count was not met", actual=deform_bones, minimum=args.min_deform_bones)

    if args.expected_dimensions_m is not None and meters_per_unit is not None:
        if evaluated_scene_bounds_raw is None:
            _issue(issues, "error", "SCENE_DIMENSIONS_UNAVAILABLE", "Expected dimensions were provided but no evaluated mesh bounds exist")
        else:
            actual = [value * meters_per_unit for value in evaluated_scene_bounds_raw["dimensions"]]
            deltas = [abs(actual[index] - args.expected_dimensions_m[index]) for index in range(3)]
            if any(delta > args.tolerance_m for delta in deltas):
                _issue(issues, "error", "SCENE_DIMENSIONS_MISMATCH", "Evaluated scene dimensions do not match the expected meter dimensions", actual_m=_rounded(actual), expected_m=_rounded(args.expected_dimensions_m), absolute_delta_m=_rounded(deltas), tolerance_m=args.tolerance_m)
    if args.expected_ground_z_m is not None and meters_per_unit is not None:
        if evaluated_scene_bounds_raw is None:
            _issue(issues, "error", "SCENE_GROUND_UNAVAILABLE", "Expected ground height was provided but no evaluated mesh bounds exist")
        else:
            actual = evaluated_scene_bounds_raw["min"][2] * meters_per_unit
            delta = abs(actual - args.expected_ground_z_m)
            if delta > args.tolerance_m:
                _issue(issues, "error", "SCENE_GROUND_MISMATCH", "Evaluated scene minimum Z does not match the expected meter height", actual_m=round(actual, 9), expected_m=args.expected_ground_z_m, absolute_delta_m=round(delta, 9), tolerance_m=args.tolerance_m)

    effective_fps = float(scene.render.fps) / float(scene.render.fps_base)
    if args.expected_fps is not None and abs(effective_fps - args.expected_fps) > 1e-9:
        _issue(issues, "error", "SCENE_FPS_MISMATCH", "Effective scene FPS does not match the contract", actual=effective_fps, expected=args.expected_fps)
    loop = None
    if args.expected_loop_frames is not None:
        loop = _loop_report(objects_in_scope, args.expected_loop_frames, args.animation_tolerance)
        if not loop["comparable"]:
            _issue(issues, "error", "ANIMATION_LOOP_NOT_COMPARABLE", "Animation loop signatures could not be compared")
        else:
            if not loop["start_end_match"]:
                _issue(issues, "error", "ANIMATION_LOOP_SEAM", "Start and end poses differ beyond tolerance", **loop)
            if not loop["middle_differs"]:
                _issue(issues, "error", "ANIMATION_LOOP_NO_MOTION", "Middle pose does not differ from the start pose", **loop)

    used_materials = {}
    for obj in objects_in_scope:
        if obj.type == "MESH":
            for slot in obj.material_slots:
                if slot.material:
                    used_materials[slot.material.name] = slot.material
    material_reports = [
        _material_report(material, args.require_referenced_images_resolve, issues)
        for material in sorted(used_materials.values(), key=lambda item: item.name)
    ]
    image_texture_count = sum(
        1
        for material in material_reports
        for node in material["image_nodes"]
        if node["image"] is not None
    )
    if args.min_image_textures is not None and image_texture_count < args.min_image_textures:
        _issue(
            issues,
            "error",
            "SCENE_IMAGE_TEXTURES_TOO_FEW",
            "The minimum assigned image-texture count was not met",
            actual=image_texture_count,
            minimum=args.min_image_textures,
        )

    severity_counts = Counter(item["severity"] for item in issues)
    verdict = "fail" if severity_counts.get("error", 0) else "pass_with_warnings" if issues else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": input_metadata["started_at"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_verdict": verdict,
        "source": input_metadata,
        "runtime": {
            "blender_version": bpy.app.version_string,
            "python_version": sys.version.split()[0],
            "background": bool(bpy.app.background),
            "disable_autoexec_flag": "--disable-autoexec" in sys.argv,
            "offline_mode_flag": "--offline-mode" in sys.argv,
            "python_exit_code_flag": "--python-exit-code" in sys.argv,
            "audit_script": {
                "path": str(Path(__file__).resolve()),
                "sha256": _sha256(Path(__file__).resolve()),
            },
        },
        "scope": {**scope, "object_count": len(objects_in_scope), "object_names": [obj.name for obj in objects_in_scope]},
        "units": units,
        "scene": {
            "name": scene.name,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
            "frame_subframe": scene.frame_subframe,
            "pose_mode": "REST" if args.rest_pose else "POSE",
            "fps": scene.render.fps,
            "fps_base": scene.render.fps_base,
            "effective_fps": effective_fps,
            "object_counts": dict(sorted(type_counts.items())),
            "source_triangles": source_triangles,
            "evaluated_triangles": evaluated_triangles,
            "source_mesh_bounds": _format_bounds(source_scene_bounds_raw, meters_per_unit),
            "evaluated_mesh_bounds": _format_bounds(evaluated_scene_bounds_raw, meters_per_unit),
            "total_bones": total_bones,
            "deform_bones": deform_bones,
            "skinned_meshes": skinned_meshes,
            "usable_bound_actions": len(usable_actions),
            "image_texture_count": image_texture_count,
        },
        "requirements": {
            "require_mesh": args.require_mesh,
            "require_closed": args.require_closed,
            "require_outward_winding": args.require_outward_winding,
            "require_uv": args.require_uv,
            "require_material": args.require_material,
            "require_referenced_images_resolve": args.require_referenced_images_resolve,
            "min_image_textures": args.min_image_textures,
            "require_armature": args.require_armature,
            "require_actions": args.require_actions,
            "require_all_weighted": args.require_all_weighted,
            "require_normalized_weights": args.require_normalized_weights,
            "max_triangles": args.max_triangles,
            "max_bones": args.max_bones,
            "max_deform_bones": args.max_deform_bones,
            "min_deform_bones": args.min_deform_bones,
            "max_influences": args.max_influences,
            "expected_dimensions_m": _rounded(args.expected_dimensions_m) if args.expected_dimensions_m else None,
            "expected_ground_z_m": args.expected_ground_z_m,
            "tolerance_m": args.tolerance_m,
            "position_weld_tolerance_m": args.position_weld_tolerance_m,
            "expected_fps": args.expected_fps,
            "expected_loop_frames": _rounded(args.expected_loop_frames) if args.expected_loop_frames else None,
            "animation_tolerance": args.animation_tolerance,
        },
        "animation_loop": loop,
        "objects": object_reports,
        "materials": material_reports,
        "actions": action_reports,
        "issues": issues,
        "issue_counts": dict(sorted(severity_counts.items())),
    }


def _import_exchange(path: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        result = bpy.ops.import_scene.gltf(
            filepath=str(path),
            merge_vertices=False,
            import_pack_images=True,
            import_shading="NORMALS",
            bone_heuristic="BLENDER",
            disable_bone_shape=True,
            guess_original_bind_pose=True,
            import_scene_extras=True,
            import_merge_material_slots=True,
        )
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0
    elif suffix == ".fbx":
        operator = getattr(bpy.ops.import_scene, "fbx", None)
        if operator is None:
            operator = getattr(bpy.ops.wm, "fbx_import", None)
        if operator is None:
            raise RuntimeError("This Blender build exposes no FBX import operator")
        result = operator(filepath=str(path))
    else:
        raise ValueError(f"Unsupported exchange format: {suffix}")
    if set(result) != {"FINISHED"}:
        raise RuntimeError(f"Import operator did not finish: {sorted(result)}")
    return {"operator_result": sorted(result), "format": suffix.removeprefix(".")}


def _authorized_output(args) -> tuple[Path, Path]:
    root = Path(args.output_root).resolve()
    output = Path(args.output).resolve()
    try:
        common = Path(os.path.commonpath([str(root), str(output)]))
    except ValueError as error:
        raise ValueError("--output and --output-root must be on the same filesystem") from error
    if common != root:
        raise ValueError(f"Report path escapes authorized output root: {output}")
    if output.exists() and not args.force:
        raise FileExistsError(f"Report already exists; pass --force to replace it: {output}")
    if output.exists() and output.is_dir():
        raise IsADirectoryError(f"Report path is a directory: {output}")
    return output, root


def _atomic_write(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    output = None
    try:
        args = _parser().parse_args(_argv())
        output, _ = _authorized_output(args)
        _validate_args(args)
        if args.input_file:
            input_path = Path(args.input_file).resolve()
            import_metadata = _import_exchange(input_path)
            source_mode = "clean_exchange_import"
        else:
            input_path = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
            import_metadata = None
            source_mode = "open_blend"
        input_metadata = {
            "started_at": started_at,
            "mode": source_mode,
            "path": str(input_path) if input_path else None,
            "sha256": _sha256(input_path),
            "import": import_metadata,
        }
        report = audit(args, run_id, input_metadata)
        _atomic_write(output, report)
        print("AUTO_TA_AUDIT=" + json.dumps({"run_id": run_id, "output": str(output), "audit_verdict": report["audit_verdict"]}))
        return 2 if report["audit_verdict"] == "fail" else 0
    except Exception as error:
        error_report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "started_at": started_at,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit_verdict": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        if output is not None:
            try:
                _atomic_write(output, error_report)
            except Exception:
                pass
        print("AUTO_TA_AUDIT_INTERNAL_ERROR=" + json.dumps(error_report, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
