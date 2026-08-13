#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2.0,<3",
#   "pillow>=11,<13",
# ]
# ///
"""Build, pixelize, and audit deterministic 2D sprite artifacts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, UnidentifiedImageError
from PIL.PngImagePlugin import PngInfo


SCHEMA_VERSION = 1
TOOL_NAME = "create-2d-game-art.sprite-pipeline"
TOOL_VERSION = "1.0.0"
MAX_DIMENSION = 8192
MAX_FRAMES = 4096
MAX_SOURCE_DIMENSION = 32768
MAX_SOURCE_PIXELS = 64_000_000
MAX_ENCODED_IMAGE_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_PREVIEW_DIMENSION = 32768
MAX_PREVIEW_PIXELS = 64_000_000
PNG_BINDING_KEY = "create-2d-game-art-binding-sha256"
OKLAB_DISTANCE_BUDGET = 1_000_000
MAX_OKLAB_DISTANCE_EVALUATIONS = 100_000_000
ANCHORS = (
    "top-left",
    "top-center",
    "center",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)


class PipelineError(ValueError):
    """A user-actionable contract or artifact error."""


@dataclass(frozen=True)
class FrameSource:
    frame_id: str
    path: Path
    source_ref: str
    state: str | None
    direction: str | None
    duration_ms: int


@dataclass(frozen=True)
class DecodedRaster:
    image: Image.Image
    binding_sha256: str | None
    encoded_format: str | None
    encoded_mode: str
    sha256: str


def _read_bounded_bytes(path: Path, maximum: int, label: str) -> bytes:
    try:
        with path.open("rb") as handle:
            payload = handle.read(maximum + 1)
    except OSError as exc:
        raise PipelineError(f"cannot read {label} {path.name}: {exc}") from exc
    if len(payload) > maximum:
        raise PipelineError(f"{label} exceeds the bounded byte budget: {path.name}")
    return payload


def _rgba_digest(image: Image.Image) -> str:
    rgba = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(b"RGBA\0")
    digest.update(rgba.width.to_bytes(8, "big"))
    digest.update(rgba.height.to_bytes(8, "big"))
    digest.update(rgba.tobytes())
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _manifest_binding_payload(manifest: dict[str, Any]) -> dict[str, Any] | None:
    operation = manifest.get("operation")
    keys = {
        "build": ("contract", "frames", "operation", "schema_version", "tool"),
        "pixelize": (
            "contract",
            "operation",
            "schema_version",
            "source",
            "sprite",
            "tool",
        ),
    }.get(operation)
    artifact = manifest.get("artifact")
    identity_keys = (
        "alpha",
        "format",
        "mode",
        "palette_color_count_visible",
        "rgba_sha256",
        "size_px",
    )
    if (
        keys is None
        or any(key not in manifest for key in keys)
        or not isinstance(artifact, dict)
        or any(key not in artifact for key in identity_keys)
    ):
        return None
    return {
        "artifact_identity": {key: artifact[key] for key in identity_keys},
        **{key: manifest[key] for key in keys},
    }


def _artifact_binding_identity(image: Image.Image) -> dict[str, Any]:
    facts = _image_facts(image)
    return {
        "alpha": facts["alpha"],
        "format": "PNG",
        "mode": "RGBA",
        "palette_color_count_visible": facts["palette_color_count_visible"],
        "rgba_sha256": facts["rgba_sha256"],
        "size_px": facts["size_px"],
    }


def _natural_key(value: str) -> list[tuple[int, int | str]]:
    parts = re.split(r"(\d+)", value.casefold())
    return [(1, int(part)) if part.isdigit() else (0, part) for part in parts]


def _require_int(name: str, value: int, minimum: int, maximum: int) -> None:
    if value < minimum or value > maximum:
        raise PipelineError(f"{name} must be between {minimum} and {maximum}; got {value}")


def _require_output_root(raw_root: str) -> Path:
    root = Path(raw_root).expanduser().resolve()
    if not root.is_dir():
        raise PipelineError(f"--output-root must name an existing directory: {raw_root}")
    return root


def _resolve_output(root: Path, raw_path: str, suffix: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise PipelineError(f"output path is not portable: {raw_path!r}")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PipelineError(f"output escapes --output-root: {raw_path}") from exc
    if candidate.suffix.casefold() != suffix:
        raise PipelineError(f"output must use {suffix}: {raw_path}")
    portable = candidate.relative_to(root).as_posix()
    if not _is_portable_relative_path(portable, suffix):
        raise PipelineError(f"output path is not portable: {raw_path}")
    return candidate


def _relative_output(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_portable_relative_path(value: Any, suffix: str | None = None) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value == "."
        or "\x00" in value
        or "\\" in value
    ):
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return False
    if ".." in posix.parts or ".." in windows.parts:
        return False
    if suffix is not None and not value.casefold().endswith(suffix.casefold()):
        return False
    return True


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _portable_path_identity(path: Path) -> str:
    return unicodedata.normalize("NFD", os.path.abspath(path)).casefold()


def _paths_alias(left: Path, right: Path) -> bool:
    if _portable_path_identity(left) == _portable_path_identity(right):
        return True
    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, OSError):
        return False


def _preflight_outputs(root: Path, paths: Iterable[Path], force: bool) -> None:
    resolved = list(paths)
    if any(
        _paths_alias(resolved[left], resolved[right])
        for left in range(len(resolved))
        for right in range(left + 1, len(resolved))
    ):
        raise PipelineError("output paths must be distinct")
    for path in resolved:
        if path.exists() and path.is_dir():
            raise PipelineError(f"output path is a directory: {path.name}")
        if path.exists() and not force:
            raise PipelineError(f"refusing to overwrite existing output: {path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        parent = path.parent.resolve()
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise PipelineError(f"output parent escapes --output-root: {path.name}") from exc


def _stage_image(
    image: Image.Image,
    destination: Path,
    *,
    binding_sha256: str | None = None,
) -> Path:
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(raw_temp)
    try:
        pnginfo = None
        if binding_sha256 is not None:
            pnginfo = PngInfo()
            pnginfo.add_text(PNG_BINDING_KEY, binding_sha256)
        image.convert("RGBA").save(
            temporary,
            format="PNG",
            optimize=False,
            compress_level=9,
            pnginfo=pnginfo,
        )
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _stage_json(payload: dict[str, Any], destination: Path) -> Path:
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _commit_staged(staged: list[tuple[Path, Path]]) -> None:
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    try:
        for _, destination in staged:
            if os.path.lexists(destination):
                descriptor, raw_backup = tempfile.mkstemp(
                    prefix=f".{destination.name}.",
                    suffix=".rollback",
                    dir=destination.parent,
                )
                os.close(descriptor)
                backup = Path(raw_backup)
                backup.unlink()
                os.replace(destination, backup)
                backups[destination] = backup
        for temporary, destination in staged:
            os.replace(temporary, destination)
            installed.append(destination)
    except Exception as commit_error:
        rollback_errors: list[str] = []
        for destination in reversed(installed):
            try:
                destination.unlink(missing_ok=True)
            except OSError as exc:
                rollback_errors.append(f"cannot remove new {destination.name}: {exc}")
        for destination, backup in reversed(list(backups.items())):
            if not os.path.lexists(backup):
                backups.pop(destination, None)
                continue
            if os.path.lexists(destination):
                rollback_errors.append(
                    f"cannot restore {destination.name}: destination is still occupied"
                )
                continue
            try:
                os.replace(backup, destination)
                backups.pop(destination, None)
            except OSError as exc:
                rollback_errors.append(f"cannot restore {destination.name}: {exc}")
        if rollback_errors:
            preserved = [
                str(path) for path in backups.values() if os.path.lexists(path)
            ]
            raise PipelineError(
                "output commit failed and rollback was incomplete; "
                f"preserved backups={preserved}; errors={rollback_errors}"
            ) from commit_error
        raise
    else:
        cleanup_errors: list[str] = []
        for destination, backup in list(backups.items()):
            try:
                backup.unlink(missing_ok=True)
                backups.pop(destination, None)
            except OSError as exc:
                cleanup_errors.append(f"cannot remove {backup}: {exc}")
        if cleanup_errors:
            raise PipelineError(
                "outputs were committed but rollback copies were preserved; "
                + "; ".join(cleanup_errors)
            )
    finally:
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _decode_rgba(path: Path) -> DecodedRaster:
    if not path.is_file():
        raise PipelineError(f"input image does not exist: {path.name}")
    payload = _read_bounded_bytes(
        path, MAX_ENCODED_IMAGE_BYTES, "encoded image"
    )
    try:
        with Image.open(io.BytesIO(payload)) as source:
            if (
                source.width < 1
                or source.height < 1
                or source.width > MAX_SOURCE_DIMENSION
                or source.height > MAX_SOURCE_DIMENSION
                or source.width * source.height > MAX_SOURCE_PIXELS
            ):
                raise PipelineError(
                    f"input image dimensions exceed the bounded decode budget: {path.name}"
                )
            source.load()
            encoded_format = source.format
            encoded_mode = source.mode
            binding_sha256 = source.info.get(PNG_BINDING_KEY)
            image = source.convert("RGBA")
    except (OSError, UnidentifiedImageError, ValueError, Image.DecompressionBombError) as exc:
        raise PipelineError(f"cannot decode input image {path.name}: {exc}") from exc
    if image.width < 1 or image.height < 1:
        raise PipelineError(f"input image has invalid dimensions: {path.name}")
    return DecodedRaster(
        image=image,
        binding_sha256=binding_sha256 if isinstance(binding_sha256, str) else None,
        encoded_format=encoded_format,
        encoded_mode=encoded_mode,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _load_rgba(path: Path) -> Image.Image:
    return _decode_rgba(path).image


def _remove_connected_corner_background(
    image: Image.Image, tolerance: int
) -> Image.Image:
    """Clear only corner-connected pixels similar to a corner reference color."""

    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    height, width, _ = rgba.shape
    corners = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
    references: list[np.ndarray] = []
    queue: deque[tuple[int, int]] = deque()
    visited = np.zeros((height, width), dtype=bool)

    for x, y in corners:
        if rgba[y, x, 3] == 0:
            continue
        color = rgba[y, x, :3].astype(np.int16)
        if not any(np.array_equal(color, reference) for reference in references):
            references.append(color)
        queue.append((x, y))

    if not references:
        return image.convert("RGBA")

    def similar(x: int, y: int) -> bool:
        if rgba[y, x, 3] == 0:
            return True
        color = rgba[y, x, :3].astype(np.int16)
        return any(int(np.max(np.abs(color - reference))) <= tolerance for reference in references)

    while queue:
        x, y = queue.popleft()
        if visited[y, x] or not similar(x, y):
            continue
        visited[y, x] = True
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    rgba[visited, :3] = 0
    rgba[visited, 3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _anchor_offset(
    outer_width: int, outer_height: int, inner_width: int, inner_height: int, anchor: str
) -> tuple[int, int]:
    horizontal = anchor.split("-")[-1] if "-" in anchor else "center"
    vertical = anchor.split("-")[0] if "-" in anchor else "center"
    if anchor == "center":
        horizontal = vertical = "center"

    if horizontal == "left":
        x = 0
    elif horizontal == "right":
        x = outer_width - inner_width
    else:
        x = (outer_width - inner_width) // 2

    if vertical == "top":
        y = 0
    elif vertical == "bottom":
        y = outer_height - inner_height
    else:
        y = (outer_height - inner_height) // 2
    return x, y


def _fit_image(
    image: Image.Image,
    width: int,
    height: int,
    fit: str,
    anchor: str,
    resample: Image.Resampling,
) -> Image.Image:
    if fit == "stretch":
        return image.resize((width, height), resample=resample)

    scale = min(width / image.width, height / image.height)
    if fit == "cover":
        scale = max(width / image.width, height / image.height)
    resized_width = max(1, round(image.width * scale))
    resized_height = max(1, round(image.height * scale))
    resized = image.resize((resized_width, resized_height), resample=resample)
    offset_x, offset_y = _anchor_offset(
        width, height, resized_width, resized_height, anchor
    )
    if fit == "cover":
        left = max(0, -offset_x)
        top = max(0, -offset_y)
        return resized.crop((left, top, left + width, top + height))
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(resized, (offset_x, offset_y))
    return canvas


def _srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.04045,
        values / 12.92,
        ((values + 0.055) / 1.055) ** 2.4,
    )


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.0031308,
        values * 12.92,
        1.055 * np.maximum(values, 0.0) ** (1.0 / 2.4) - 0.055,
    )


def _rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    linear = _srgb_to_linear(rgb)
    red, green, blue = linear[..., 0], linear[..., 1], linear[..., 2]
    long = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    medium = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    short = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    long_root = np.cbrt(long)
    medium_root = np.cbrt(medium)
    short_root = np.cbrt(short)
    return np.stack(
        (
            0.2104542553 * long_root
            + 0.7936177850 * medium_root
            - 0.0040720468 * short_root,
            1.9779984951 * long_root
            - 2.4285922050 * medium_root
            + 0.4505937099 * short_root,
            0.0259040371 * long_root
            + 0.7827717662 * medium_root
            - 0.8086757660 * short_root,
        ),
        axis=-1,
    )


def _oklab_to_rgb(oklab: np.ndarray) -> np.ndarray:
    light, axis_a, axis_b = oklab[..., 0], oklab[..., 1], oklab[..., 2]
    long_root = light + 0.3963377774 * axis_a + 0.2158037573 * axis_b
    medium_root = light - 0.1055613458 * axis_a - 0.0638541728 * axis_b
    short_root = light - 0.0894841775 * axis_a - 1.2914855480 * axis_b
    long = long_root**3
    medium = medium_root**3
    short = short_root**3
    linear = np.stack(
        (
            4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
            -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
            -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short,
        ),
        axis=-1,
    )
    return np.clip(_linear_to_srgb(np.clip(linear, 0.0, 1.0)), 0.0, 1.0)


def _nearest_centroids(data: np.ndarray, centroids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = np.empty(len(data), dtype=np.int32)
    minimum = np.empty(len(data), dtype=np.float64)
    chunk_size = max(1, OKLAB_DISTANCE_BUDGET // max(1, len(centroids)))
    for start in range(0, len(data), chunk_size):
        stop = min(len(data), start + chunk_size)
        distances = np.sum(
            (data[start:stop, None, :] - centroids[None, :, :]) ** 2,
            axis=2,
        )
        chunk_labels = np.argmin(distances, axis=1)
        labels[start:stop] = chunk_labels
        minimum[start:stop] = distances[np.arange(stop - start), chunk_labels]
    return labels, minimum


def _weighted_oklab_palette(
    colors: np.ndarray, counts: np.ndarray, size: int, seed: int
) -> np.ndarray:
    data = _rgb_to_oklab(colors.astype(np.float64) / 255.0)
    size = min(size, len(data))
    if size == len(data):
        return colors.copy()

    rng = np.random.default_rng(seed)
    centroids = [data[int(np.argmax(counts))]]
    minimum_distances = np.sum((data - centroids[0]) ** 2, axis=1)
    for _ in range(1, size):
        weights = minimum_distances * counts
        total = float(np.sum(weights))
        if total <= 0.0:
            remaining = [
                index
                for index in range(len(data))
                if not any(np.array_equal(data[index], item) for item in centroids)
            ]
            chosen = remaining[0]
        else:
            chosen = int(rng.choice(len(data), p=weights / total))
        centroids.append(data[chosen])
        distance = np.sum((data - data[chosen]) ** 2, axis=1)
        minimum_distances = np.minimum(minimum_distances, distance)

    centroid_array = np.stack(centroids)
    for _ in range(30):
        labels, minimum_to_centroid = _nearest_centroids(data, centroid_array)
        updated = centroid_array.copy()
        for index in range(size):
            members = labels == index
            if np.any(members):
                updated[index] = np.average(data[members], axis=0, weights=counts[members])
            else:
                farthest = int(np.argmax(minimum_to_centroid * counts))
                updated[index] = data[farthest]
        if np.allclose(updated, centroid_array, rtol=0.0, atol=1e-10):
            centroid_array = updated
            break
        centroid_array = updated

    return np.rint(_oklab_to_rgb(centroid_array) * 255.0).astype(np.uint8)


def _quantize_oklab(image: Image.Image, colors: int, seed: int) -> Image.Image:
    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    mask = rgba[..., 3] > 0
    if not np.any(mask):
        return image.convert("RGBA")
    opaque_rgb = rgba[..., :3][mask]
    unique, inverse, counts = np.unique(
        opaque_rgb, axis=0, return_inverse=True, return_counts=True
    )
    palette_size = min(colors, len(unique))
    estimated_evaluations = len(unique) * palette_size * 31
    if estimated_evaluations > MAX_OKLAB_DISTANCE_EVALUATIONS:
        raise PipelineError(
            "OKLab palette reduction exceeds the bounded work budget; "
            "reduce the frame size/colors or use --palette median-cut"
        )
    palette = _weighted_oklab_palette(unique, counts.astype(np.float64), colors, seed)
    unique_oklab = _rgb_to_oklab(unique.astype(np.float64) / 255.0)
    palette_oklab = _rgb_to_oklab(palette.astype(np.float64) / 255.0)
    labels, _ = _nearest_centroids(unique_oklab, palette_oklab)
    mapped_unique = palette[labels]
    rgba[..., :3][mask] = mapped_unique[inverse]
    rgba[..., :3][~mask] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _quantize_median_cut(image: Image.Image, colors: int, dither: bool) -> Image.Image:
    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    mask = rgba[..., 3] > 0
    if not np.any(mask):
        return image.convert("RGBA")
    rgb = rgba[..., :3].copy()
    opaque = rgb[mask]
    unique, counts = np.unique(opaque, axis=0, return_counts=True)
    fill = unique[int(np.argmax(counts))]
    rgb[~mask] = fill
    rgb_image = Image.fromarray(rgb, mode="RGB")
    quantized = rgb_image.quantize(
        colors=min(colors, 256),
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE,
    ).convert("RGB")
    output = np.dstack((np.array(quantized, dtype=np.uint8), rgba[..., 3]))
    output[..., :3][~mask] = 0
    return Image.fromarray(output, mode="RGBA")


def _process_image(image: Image.Image, args: argparse.Namespace) -> Image.Image:
    if args.background == "corner-connected":
        image = _remove_connected_corner_background(image, args.background_tolerance)

    alpha = np.array(image.getchannel("A"), dtype=np.uint8)
    rgb = ImageEnhance.Contrast(image.convert("RGB")).enhance(args.contrast)
    image = rgb.convert("RGBA")
    image.putalpha(Image.fromarray(alpha, mode="L"))

    resampling = {
        "nearest": Image.Resampling.NEAREST,
        "box": Image.Resampling.BOX,
        "lanczos": Image.Resampling.LANCZOS,
    }[args.resample]
    image = _fit_image(
        image,
        args.frame_width,
        args.frame_height,
        args.fit,
        args.anchor,
        resampling,
    )

    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    clear = rgba[..., 3] < args.alpha_threshold
    rgba[clear] = 0
    rgba[..., :3][rgba[..., 3] == 0] = 0
    image = Image.fromarray(rgba, mode="RGBA")

    if args.palette == "median-cut":
        image = _quantize_median_cut(image, args.colors, args.dither)
    elif args.palette == "oklab":
        image = _quantize_oklab(image, args.colors, args.seed)
    return image


def _validate_processing_args(args: argparse.Namespace) -> None:
    _require_int("--frame-width", args.frame_width, 1, MAX_DIMENSION)
    _require_int("--frame-height", args.frame_height, 1, MAX_DIMENSION)
    _require_int("--background-tolerance", args.background_tolerance, 0, 255)
    _require_int("--alpha-threshold", args.alpha_threshold, 0, 255)
    if not math.isfinite(args.contrast) or args.contrast <= 0.0 or args.contrast > 10.0:
        raise PipelineError("--contrast must be greater than 0 and at most 10")
    if args.palette == "none":
        if args.colors is not None or args.dither:
            raise PipelineError("--colors/--dither require --palette median-cut or oklab")
    else:
        if args.colors is None:
            raise PipelineError("--colors is required when palette reduction is enabled")
        _require_int("--colors", args.colors, 2, 256)
    if args.palette == "oklab" and args.dither:
        raise PipelineError("--dither is supported only by --palette median-cut")


def _load_frame_data(path: Path, default_duration: int) -> list[FrameSource]:
    encoded = _read_bounded_bytes(path, MAX_MANIFEST_BYTES, "frame-data")
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read --frame-data: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "frames"}:
        raise PipelineError("--frame-data must contain exactly schema_version and frames")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1 or not isinstance(payload.get("frames"), list):
        raise PipelineError("--frame-data requires schema_version 1 and a frames array")
    if not payload["frames"]:
        raise PipelineError("--frame-data frames must not be empty")
    if len(payload["frames"]) > MAX_FRAMES:
        raise PipelineError(f"--frame-data exceeds the {MAX_FRAMES} frame limit")

    base = path.parent.resolve()
    allowed = {"path", "id", "state", "direction", "duration_ms"}
    frames: list[FrameSource] = []
    for index, raw in enumerate(payload["frames"]):
        if not isinstance(raw, dict) or not {"path", "id"}.issubset(raw):
            raise PipelineError(f"frame-data frame {index} requires path and id")
        unknown = set(raw) - allowed
        if unknown:
            raise PipelineError(f"frame-data frame {index} has unknown keys: {sorted(unknown)}")
        raw_path = raw["path"]
        frame_id = raw["id"]
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise PipelineError(f"frame-data frame {index} path must be relative")
        source = (base / raw_path).resolve()
        try:
            source.relative_to(base)
        except ValueError as exc:
            raise PipelineError(f"frame-data frame {index} path escapes its directory") from exc
        if not isinstance(frame_id, str) or not frame_id.strip():
            raise PipelineError(f"frame-data frame {index} id must be a non-empty string")
        duration = raw.get("duration_ms", default_duration)
        if not isinstance(duration, int) or isinstance(duration, bool):
            raise PipelineError(f"frame-data frame {index} duration_ms must be an integer")
        _require_int(f"frame-data frame {index} duration_ms", duration, 1, 60000)
        state = raw.get("state")
        direction = raw.get("direction")
        for label, value in (("state", state), ("direction", direction)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise PipelineError(f"frame-data frame {index} {label} must be null or non-empty")
        frames.append(
            FrameSource(
                frame_id=frame_id.strip(),
                path=source,
                source_ref=source.relative_to(base).as_posix(),
                state=state.strip() if isinstance(state, str) else None,
                direction=direction.strip() if isinstance(direction, str) else None,
                duration_ms=duration,
            )
        )
    return frames


def _discover_frames(directory: Path, pattern: str, duration: int) -> list[FrameSource]:
    base = directory.expanduser().resolve()
    if not base.is_dir():
        raise PipelineError(f"--input-dir must name an existing directory: {directory}")
    pattern_path = Path(pattern)
    if pattern_path.is_absolute() or ".." in pattern_path.parts:
        raise PipelineError("--pattern must stay within --input-dir")
    try:
        discovered = []
        for candidate in base.glob(pattern):
            if candidate.is_file():
                discovered.append(candidate)
                if len(discovered) > MAX_FRAMES:
                    raise PipelineError(f"input exceeds the {MAX_FRAMES} frame limit")
    except PipelineError:
        raise
    except (OSError, ValueError) as exc:
        raise PipelineError(f"invalid --pattern: {exc}") from exc
    discovered.sort(key=lambda item: _natural_key(item.relative_to(base).as_posix()))
    for left, right in zip(discovered, discovered[1:]):
        left_name = left.relative_to(base).as_posix()
        right_name = right.relative_to(base).as_posix()
        if _natural_key(left_name) == _natural_key(right_name):
            raise PipelineError(
                "input filenames have ambiguous natural order; use --frame-data: "
                f"{left_name}, {right_name}"
            )
    if not discovered:
        raise PipelineError("no input frames matched --pattern")
    frames = []
    resolved_sources: set[Path] = set()
    for candidate in discovered:
        alias_relative = candidate.relative_to(base)
        resolved = candidate.resolve()
        try:
            source_relative = resolved.relative_to(base)
        except ValueError as exc:
            raise PipelineError(
                f"input frame resolves outside --input-dir: {alias_relative.as_posix()}"
            ) from exc
        if resolved in resolved_sources:
            raise PipelineError(
                f"multiple input paths resolve to the same source frame: {source_relative.as_posix()}"
            )
        resolved_sources.add(resolved)
        frame_id = alias_relative.with_suffix("").as_posix().replace("/", "__")
        frames.append(
            FrameSource(
                frame_id,
                resolved,
                source_relative.as_posix(),
                None,
                None,
                duration,
            )
        )
    return frames


def _validate_unique_frame_ids(frames: list[FrameSource]) -> None:
    seen: set[str] = set()
    for frame in frames:
        normalized = frame.frame_id.casefold()
        if normalized in seen:
            raise PipelineError(f"duplicate frame id: {frame.frame_id}")
        seen.add(normalized)


def _image_facts(
    image: Image.Image,
    *,
    binding_sha256: str | None = None,
    encoded_format: str | None = None,
    encoded_mode: str | None = None,
) -> dict[str, Any]:
    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[..., 3]
    visible = alpha > 0
    palette_colors = (
        int(len(np.unique(rgba[..., :3][visible], axis=0))) if np.any(visible) else 0
    )
    return {
        "alpha": {
            "fully_opaque_pixels": int(np.sum(alpha == 255)),
            "fully_transparent_pixels": int(np.sum(alpha == 0)),
            "partially_transparent_pixels": int(np.sum((alpha > 0) & (alpha < 255))),
        },
        "binding_sha256": binding_sha256,
        "format": encoded_format,
        "mode": encoded_mode if encoded_mode is not None else image.mode,
        "palette_color_count_visible": palette_colors,
        "rgba_sha256": _rgba_digest(image),
        "size_px": [image.width, image.height],
    }


def _processing_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "alpha_threshold": args.alpha_threshold,
        "anchor": args.anchor,
        "background": args.background,
        "background_tolerance": args.background_tolerance,
        "colors": args.colors,
        "contrast": args.contrast,
        "dither": bool(args.dither),
        "fit": args.fit,
        "frame_size_px": [args.frame_width, args.frame_height],
        "palette": args.palette,
        "resample": args.resample,
        "seed": args.seed if args.palette == "oklab" else None,
    }


def _pivot(args: argparse.Namespace) -> list[int]:
    if args.pivot == "custom":
        if args.pivot_x is None or args.pivot_y is None:
            raise PipelineError("--pivot custom requires --pivot-x and --pivot-y")
        x, y = args.pivot_x, args.pivot_y
    else:
        if args.pivot_x is not None or args.pivot_y is not None:
            raise PipelineError("--pivot-x/--pivot-y require --pivot custom")
        positions = {
            "center": (args.frame_width // 2, args.frame_height // 2),
            "bottom-center": (args.frame_width // 2, 0),
            "bottom-left": (0, 0),
        }
        x, y = positions[args.pivot]
    _require_int("pivot x", x, 0, args.frame_width)
    _require_int("pivot y", y, 0, args.frame_height)
    return [x, y]


def _make_preview(sheet: Image.Image, scale: int, rects: list[dict[str, int]]) -> Image.Image:
    width, height = sheet.size
    checker = Image.new("RGBA", (width, height), (50, 50, 50, 255))
    draw = ImageDraw.Draw(checker)
    tile = 4
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(82, 82, 82, 255))
    checker.alpha_composite(sheet)
    draw = ImageDraw.Draw(checker)
    for rect in rects:
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=(255, 0, 255, 255))
    return checker.resize((width * scale, height * scale), Image.Resampling.NEAREST)


def _run_build(args: argparse.Namespace) -> int:
    _validate_processing_args(args)
    _require_int("--duration-ms", args.duration_ms, 1, 60000)
    _require_int("--padding", args.padding, 0, 1024)
    _require_int("--preview-scale", args.preview_scale, 1, 64)
    pivot = _pivot(args)

    if args.frame_data:
        frame_data_path = Path(args.frame_data).expanduser().resolve()
        frames = _load_frame_data(frame_data_path, args.duration_ms)
        control_inputs = {frame_data_path}
    else:
        frames = _discover_frames(Path(args.input_dir), args.pattern, args.duration_ms)
        control_inputs = set()
    _validate_unique_frame_ids(frames)

    columns = args.columns or min(8, len(frames))
    _require_int("--columns", columns, 1, MAX_FRAMES)
    rows = math.ceil(len(frames) / columns)
    sheet_width = columns * args.frame_width + (columns + 1) * args.padding
    sheet_height = rows * args.frame_height + (rows + 1) * args.padding
    _require_int("sheet width", sheet_width, 1, MAX_DIMENSION)
    _require_int("sheet height", sheet_height, 1, MAX_DIMENSION)
    if args.preview and (
        sheet_width * args.preview_scale > MAX_PREVIEW_DIMENSION
        or sheet_height * args.preview_scale > MAX_PREVIEW_DIMENSION
        or sheet_width * sheet_height * args.preview_scale * args.preview_scale
        > MAX_PREVIEW_PIXELS
    ):
        raise PipelineError("preview exceeds the bounded raster budget")

    root = _require_output_root(args.output_root)
    output = _resolve_output(root, args.output, ".png")
    manifest_path = _resolve_output(root, args.manifest, ".json")
    preview_path = _resolve_output(root, args.preview, ".png") if args.preview else None
    output_paths = [output, manifest_path] + ([preview_path] if preview_path else [])
    source_paths = {frame.path for frame in frames} | control_inputs
    overlapping_sources = [
        path
        for path in output_paths
        if any(_paths_alias(path, source) for source in source_paths)
    ]
    if overlapping_sources:
        raise PipelineError(
            "output must not overwrite an input frame or frame-data file: "
            + ", ".join(path.name for path in overlapping_sources)
        )
    _preflight_outputs(root, output_paths, args.force)

    sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    frame_records: list[dict[str, Any]] = []
    rects: list[dict[str, int]] = []
    for index, frame in enumerate(frames):
        decoded_source = _decode_rgba(frame.path)
        source = decoded_source.image
        source_facts = _image_facts(source)
        processed = _process_image(source, args)
        column = index % columns
        row = index // columns
        x = args.padding + column * (args.frame_width + args.padding)
        y = args.padding + row * (args.frame_height + args.padding)
        sheet.alpha_composite(processed, (x, y))
        rect = {
            "height": args.frame_height,
            "width": args.frame_width,
            "x": x,
            "y": y,
        }
        rects.append(rect)
        frame_records.append(
            {
                "direction": frame.direction,
                "duration_ms": frame.duration_ms,
                "id": frame.frame_id,
                "pivot_px_from_bottom_left": pivot,
                "processed_rgba_sha256": _rgba_digest(processed),
                "rect_px_top_left": rect,
                "source": {
                    "path": frame.source_ref,
                    "rgba_sha256": source_facts["rgba_sha256"],
                    "sha256": decoded_source.sha256,
                    "size_px": source_facts["size_px"],
                },
                "state": frame.state,
            }
        )

    contract = {
        "layout": {
            "columns": columns,
            "frame_count": len(frames),
            "frame_size_px": [args.frame_width, args.frame_height],
            "origin": "top-left",
            "padding_px": args.padding,
            "pivot_origin": "bottom-left",
            "rows": rows,
        },
        "processing": _processing_contract(args),
    }
    manifest_fields = {
        "contract": contract,
        "frames": frame_records,
        "operation": "build",
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
    }
    binding_payload = {
        "artifact_identity": _artifact_binding_identity(sheet),
        **manifest_fields,
    }
    binding_sha256 = _canonical_sha256(binding_payload)
    staged: list[tuple[Path, Path]] = []
    try:
        staged_sheet = _stage_image(
            sheet, output, binding_sha256=binding_sha256
        )
        staged.append((staged_sheet, output))
        decoded_sheet = _decode_rgba(staged_sheet)
        artifact = _image_facts(
            decoded_sheet.image,
            binding_sha256=decoded_sheet.binding_sha256,
            encoded_format=decoded_sheet.encoded_format,
            encoded_mode=decoded_sheet.encoded_mode,
        )
        artifact.update(
            {
                "path": _relative_output(root, output),
                "sha256": decoded_sheet.sha256,
            }
        )
        manifest: dict[str, Any] = {
            "artifact": artifact,
            **manifest_fields,
        }

        if preview_path:
            preview = _make_preview(sheet, args.preview_scale, rects)
            staged_preview = _stage_image(preview, preview_path)
            staged.append((staged_preview, preview_path))
            decoded_preview = _decode_rgba(staged_preview)
            manifest["preview"] = {
                "path": _relative_output(root, preview_path),
                "scale": args.preview_scale,
                "sha256": decoded_preview.sha256,
                "size_px": [preview.width, preview.height],
            }
        staged_manifest = _stage_json(manifest, manifest_path)
        staged.append((staged_manifest, manifest_path))
        _commit_staged(staged)
    except Exception:
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    print(
        json.dumps(
            {
                "frame_count": len(frames),
                "manifest": _relative_output(root, manifest_path),
                "output": _relative_output(root, output),
                "status": "built",
            },
            sort_keys=True,
        )
    )
    return 0


def _run_pixelize(args: argparse.Namespace) -> int:
    _validate_processing_args(args)
    _require_int("--preview-scale", args.preview_scale, 1, 64)
    pivot = _pivot(args)
    if args.preview and (
        args.frame_width * args.preview_scale > MAX_PREVIEW_DIMENSION
        or args.frame_height * args.preview_scale > MAX_PREVIEW_DIMENSION
        or args.frame_width
        * args.frame_height
        * args.preview_scale
        * args.preview_scale
        > MAX_PREVIEW_PIXELS
    ):
        raise PipelineError("preview exceeds the bounded raster budget")
    root = _require_output_root(args.output_root)
    source_path = Path(args.input).expanduser().resolve()
    output = _resolve_output(root, args.output, ".png")
    manifest_path = _resolve_output(root, args.manifest, ".json")
    preview_path = _resolve_output(root, args.preview, ".png") if args.preview else None
    output_paths = [output, manifest_path] + ([preview_path] if preview_path else [])
    if any(_paths_alias(source_path, path) for path in output_paths):
        raise PipelineError("input and output paths must be distinct")
    _preflight_outputs(root, output_paths, args.force)

    decoded_source = _decode_rgba(source_path)
    source = decoded_source.image
    source_facts = _image_facts(source)
    processed = _process_image(source, args)
    contract = {"processing": _processing_contract(args)}
    source_record = {
        "path": source_path.name,
        "rgba_sha256": source_facts["rgba_sha256"],
        "sha256": decoded_source.sha256,
        "size_px": source_facts["size_px"],
    }
    sprite_record = {
        "pivot_origin": "bottom-left",
        "pivot_px_from_bottom_left": pivot,
    }
    manifest_fields = {
        "contract": contract,
        "operation": "pixelize",
        "schema_version": SCHEMA_VERSION,
        "source": source_record,
        "sprite": sprite_record,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
    }
    binding_payload = {
        "artifact_identity": _artifact_binding_identity(processed),
        **manifest_fields,
    }
    binding_sha256 = _canonical_sha256(binding_payload)
    staged: list[tuple[Path, Path]] = []
    try:
        staged_image = _stage_image(
            processed, output, binding_sha256=binding_sha256
        )
        staged.append((staged_image, output))
        decoded_artifact = _decode_rgba(staged_image)
        artifact = _image_facts(
            decoded_artifact.image,
            binding_sha256=decoded_artifact.binding_sha256,
            encoded_format=decoded_artifact.encoded_format,
            encoded_mode=decoded_artifact.encoded_mode,
        )
        artifact.update(
            {
                "path": _relative_output(root, output),
                "sha256": decoded_artifact.sha256,
            }
        )
        manifest: dict[str, Any] = {
            "artifact": artifact,
            **manifest_fields,
        }
        if preview_path:
            preview = _make_preview(
                processed,
                args.preview_scale,
                [
                    {
                        "height": args.frame_height,
                        "width": args.frame_width,
                        "x": 0,
                        "y": 0,
                    }
                ],
            )
            staged_preview = _stage_image(preview, preview_path)
            staged.append((staged_preview, preview_path))
            decoded_preview = _decode_rgba(staged_preview)
            manifest["preview"] = {
                "path": _relative_output(root, preview_path),
                "scale": args.preview_scale,
                "sha256": decoded_preview.sha256,
                "size_px": [preview.width, preview.height],
            }
        staged_manifest = _stage_json(manifest, manifest_path)
        staged.append((staged_manifest, manifest_path))
        _commit_staged(staged)
    except Exception:
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    print(
        json.dumps(
            {
                "manifest": _relative_output(root, manifest_path),
                "output": _relative_output(root, output),
                "status": "pixelized",
            },
            sort_keys=True,
        )
    )
    return 0


def _check(
    checks: list[dict[str, Any]], check_id: str, passed: bool, observed: Any
) -> None:
    checks.append(
        {"id": check_id, "observed": observed, "result": "pass" if passed else "fail"}
    )


def _rectangles_overlap(left: dict[str, int], right: dict[str, int]) -> bool:
    return not (
        left["x"] + left["width"] <= right["x"]
        or right["x"] + right["width"] <= left["x"]
        or left["y"] + left["height"] <= right["y"]
        or right["y"] + right["height"] <= left["y"]
    )


def _read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    encoded = _read_bounded_bytes(path, MAX_MANIFEST_BYTES, "manifest")
    if len(encoded) < 2:
        raise PipelineError("manifest exceeds the bounded JSON size")
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise PipelineError("manifest root must be an object")
    return payload, hashlib.sha256(encoded).hexdigest()


def _run_audit(args: argparse.Namespace) -> int:
    root = _require_output_root(args.output_root)
    image_path = Path(args.image).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    output = _resolve_output(root, args.output, ".json")
    if any(_paths_alias(output, path) for path in (image_path, manifest_path)):
        raise PipelineError("audit output must differ from its inputs")
    _preflight_outputs(root, [output], args.force)

    decoded_image = _decode_rgba(image_path)
    image = decoded_image.image
    manifest, manifest_sha256 = _read_manifest(manifest_path)
    facts = _image_facts(
        image,
        binding_sha256=decoded_image.binding_sha256,
        encoded_format=decoded_image.encoded_format,
        encoded_mode=decoded_image.encoded_mode,
    )
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "schema.version",
        type(manifest.get("schema_version")) is int
        and manifest.get("schema_version") == 1,
        manifest.get("schema_version"),
    )
    tool = manifest.get("tool")
    _check(
        checks,
        "schema.tool",
        isinstance(tool, dict)
        and set(tool) == {"name", "version"}
        and tool.get("name") == TOOL_NAME
        and tool.get("version") == TOOL_VERSION,
        tool,
    )
    operation = manifest.get("operation")
    _check(checks, "schema.operation", operation in {"build", "pixelize"}, operation)
    expected_top_level = {
        "build": {"artifact", "contract", "frames", "operation", "schema_version", "tool"},
        "pixelize": {
            "artifact",
            "contract",
            "operation",
            "schema_version",
            "source",
            "sprite",
            "tool",
        },
    }.get(operation, set())
    optional_top_level = {"preview"} if operation in {"build", "pixelize"} else set()
    actual_top_level = set(manifest)
    _check(
        checks,
        "schema.top_level",
        bool(expected_top_level)
        and expected_top_level.issubset(actual_top_level)
        and actual_top_level <= expected_top_level | optional_top_level,
        sorted(actual_top_level),
    )

    artifact = manifest.get("artifact")
    _check(checks, "artifact.record", isinstance(artifact, dict), type(artifact).__name__)
    if not isinstance(artifact, dict):
        artifact = {}
    expected_artifact_keys = {
        "alpha",
        "binding_sha256",
        "format",
        "mode",
        "palette_color_count_visible",
        "path",
        "rgba_sha256",
        "sha256",
        "size_px",
    }
    _check(
        checks,
        "artifact.schema",
        set(artifact) == expected_artifact_keys,
        sorted(artifact),
    )
    portable_artifact_path = _is_portable_relative_path(artifact.get("path"), ".png")
    _check(checks, "artifact.path", portable_artifact_path, artifact.get("path"))
    if portable_artifact_path:
        declared_image = (root / artifact["path"]).resolve(strict=False)
        try:
            declared_image.relative_to(root)
            declared_image_confined = True
        except ValueError:
            declared_image_confined = False
        _check(
            checks,
            "artifact.path_confined",
            declared_image_confined,
            artifact.get("path"),
        )
        _check(
            checks,
            "artifact.path_binding",
            declared_image_confined and _paths_alias(declared_image, image_path),
            artifact.get("path"),
        )
    encoded_sha256 = decoded_image.sha256
    _check(
        checks,
        "artifact.sha256",
        _is_sha256(artifact.get("sha256"))
        and artifact.get("sha256") == encoded_sha256,
        encoded_sha256,
    )
    _check(
        checks,
        "artifact.rgba_sha256",
        _is_sha256(artifact.get("rgba_sha256"))
        and artifact.get("rgba_sha256") == facts["rgba_sha256"],
        facts["rgba_sha256"],
    )
    binding_payload = _manifest_binding_payload(manifest)
    try:
        expected_binding = (
            _canonical_sha256(binding_payload) if binding_payload is not None else None
        )
    except (TypeError, ValueError):
        expected_binding = None
    _check(
        checks,
        "artifact.binding",
        _is_sha256(expected_binding)
        and artifact.get("binding_sha256") == expected_binding
        and facts["binding_sha256"] == expected_binding,
        {
            "declared": artifact.get("binding_sha256"),
            "encoded": facts["binding_sha256"],
            "expected": expected_binding,
        },
    )
    _check(
        checks,
        "artifact.size",
        artifact.get("size_px") == facts["size_px"],
        facts["size_px"],
    )
    _check(
        checks,
        "artifact.format",
        artifact.get("format") == "PNG" and facts["format"] == "PNG",
        {"declared": artifact.get("format"), "encoded": facts["format"]},
    )
    _check(
        checks,
        "artifact.mode",
        artifact.get("mode") == "RGBA" and facts["mode"] == "RGBA",
        {"declared": artifact.get("mode"), "encoded": facts["mode"]},
    )
    _check(
        checks,
        "artifact.palette",
        artifact.get("palette_color_count_visible") == facts["palette_color_count_visible"],
        facts["palette_color_count_visible"],
    )
    _check(checks, "artifact.alpha", artifact.get("alpha") == facts["alpha"], facts["alpha"])

    contract = manifest.get("contract")
    _check(checks, "contract.record", isinstance(contract, dict), type(contract).__name__)
    processing = contract.get("processing") if isinstance(contract, dict) else None
    expected_contract_keys = (
        {"layout", "processing"}
        if operation == "build"
        else {"processing"}
        if operation == "pixelize"
        else set()
    )
    _check(
        checks,
        "contract.schema",
        isinstance(contract, dict) and set(contract) == expected_contract_keys,
        sorted(contract) if isinstance(contract, dict) else None,
    )
    expected_processing_keys = {
        "alpha_threshold",
        "anchor",
        "background",
        "background_tolerance",
        "colors",
        "contrast",
        "dither",
        "fit",
        "frame_size_px",
        "palette",
        "resample",
        "seed",
    }
    processing_valid = isinstance(processing, dict) and set(processing) == expected_processing_keys
    _check(checks, "contract.processing_schema", processing_valid, processing)
    if processing_valid:
        frame_size = processing.get("frame_size_px")
        processing_values_valid = (
            isinstance(frame_size, list)
            and len(frame_size) == 2
            and all(type(value) is int and 1 <= value <= MAX_DIMENSION for value in frame_size)
            and processing.get("fit") in {"contain", "cover", "stretch"}
            and processing.get("anchor") in ANCHORS
            and processing.get("resample") in {"nearest", "box", "lanczos"}
            and type(processing.get("contrast")) in {int, float}
            and math.isfinite(processing["contrast"])
            and 0 < processing["contrast"] <= 10
            and processing.get("background") in {"keep", "corner-connected"}
            and type(processing.get("background_tolerance")) is int
            and 0 <= processing["background_tolerance"] <= 255
            and type(processing.get("alpha_threshold")) is int
            and 0 <= processing["alpha_threshold"] <= 255
            and processing.get("palette") in {"none", "median-cut", "oklab"}
            and type(processing.get("dither")) is bool
        )
        palette = processing.get("palette")
        colors = processing.get("colors")
        seed = processing.get("seed")
        if palette == "none":
            processing_values_valid = (
                processing_values_valid
                and colors is None
                and seed is None
                and processing.get("dither") is False
            )
        else:
            processing_values_valid = (
                processing_values_valid
                and type(colors) is int
                and 2 <= colors <= 256
                and (
                    (palette == "oklab" and type(seed) is int)
                    or (palette == "median-cut" and seed is None)
                )
                and (palette != "oklab" or processing.get("dither") is False)
            )
        _check(checks, "contract.processing_values", processing_values_valid, processing)
        if processing_values_valid and palette != "none":
            _check(
                checks,
                "artifact.palette_budget",
                facts["palette_color_count_visible"] <= colors,
                facts["palette_color_count_visible"],
            )

    preview = manifest.get("preview")
    if preview is not None:
        preview_valid = (
            isinstance(preview, dict)
            and set(preview) == {"path", "scale", "sha256", "size_px"}
            and _is_portable_relative_path(preview.get("path"), ".png")
            and type(preview.get("scale")) is int
            and 1 <= preview["scale"] <= 64
            and _is_sha256(preview.get("sha256"))
            and isinstance(preview.get("size_px"), list)
            and len(preview["size_px"]) == 2
            and all(type(value) is int and value > 0 for value in preview["size_px"])
        )
        _check(checks, "preview.schema", preview_valid, preview)
        if preview_valid:
            preview_path = (root / preview["path"]).resolve(strict=False)
            try:
                preview_path.relative_to(root)
                preview_path_confined = not any(
                    _paths_alias(preview_path, protected)
                    for protected in (image_path, manifest_path, output)
                )
            except ValueError:
                preview_path_confined = False
            _check(
                checks,
                "preview.path_binding",
                preview_path_confined,
                preview["path"],
            )
            expected_preview_size = [
                facts["size_px"][0] * preview["scale"],
                facts["size_px"][1] * preview["scale"],
            ]
            _check(
                checks,
                "preview.contract_size",
                preview["size_px"] == expected_preview_size,
                preview["size_px"],
            )
            preview_file_valid = preview_path_confined and preview_path.is_file()
            _check(checks, "preview.exists", preview_file_valid, preview["path"])
            if preview_file_valid:
                decoded_preview = _decode_rgba(preview_path)
                preview_image = decoded_preview.image
                _check(
                    checks,
                    "preview.sha256",
                    decoded_preview.sha256 == preview["sha256"],
                    decoded_preview.sha256,
                )
                _check(
                    checks,
                    "preview.format",
                    decoded_preview.encoded_format == "PNG",
                    decoded_preview.encoded_format,
                )
                _check(
                    checks,
                    "preview.mode",
                    decoded_preview.encoded_mode == "RGBA",
                    decoded_preview.encoded_mode,
                )
                preview_rects: list[dict[str, int]] | None = None
                if operation == "pixelize":
                    preview_rects = [
                        {
                            "height": image.height,
                            "width": image.width,
                            "x": 0,
                            "y": 0,
                        }
                    ]
                elif operation == "build" and isinstance(manifest.get("frames"), list):
                    declared_rects = [
                        frame.get("rect_px_top_left")
                        for frame in manifest["frames"]
                        if isinstance(frame, dict)
                    ]
                    if len(declared_rects) == len(manifest["frames"]) and all(
                        isinstance(rect, dict)
                        and set(rect) == {"x", "y", "width", "height"}
                        and all(type(value) is int for value in rect.values())
                        and rect["x"] >= 0
                        and rect["y"] >= 0
                        and rect["width"] > 0
                        and rect["height"] > 0
                        and rect["x"] + rect["width"] <= image.width
                        and rect["y"] + rect["height"] <= image.height
                        for rect in declared_rects
                    ):
                        preview_rects = declared_rects
                preview_content_valid = False
                observed_preview_digest = _rgba_digest(preview_image)
                expected_preview_digest = None
                if preview_rects is not None:
                    expected_preview = _make_preview(
                        image, preview["scale"], preview_rects
                    )
                    expected_preview_digest = _rgba_digest(expected_preview)
                    preview_content_valid = (
                        preview_image.size == expected_preview.size
                        and observed_preview_digest == expected_preview_digest
                    )
                _check(
                    checks,
                    "preview.content",
                    preview_content_valid,
                    {
                        "actual_rgba_sha256": observed_preview_digest,
                        "expected_rgba_sha256": expected_preview_digest,
                    },
                )
                _check(
                    checks,
                    "preview.size",
                    [preview_image.width, preview_image.height] == preview["size_px"],
                    [preview_image.width, preview_image.height],
                )

    if operation == "build":
        frames = manifest.get("frames")
        layout = contract.get("layout") if isinstance(contract, dict) else None
        valid_frames = isinstance(frames, list) and 0 < len(frames) <= MAX_FRAMES
        _check(checks, "layout.frames", valid_frames, len(frames) if isinstance(frames, list) else None)
        expected_layout_keys = {
            "columns",
            "frame_count",
            "frame_size_px",
            "origin",
            "padding_px",
            "pivot_origin",
            "rows",
        }
        _check(
            checks,
            "layout.record",
            isinstance(layout, dict) and set(layout) == expected_layout_keys,
            layout,
        )
        if valid_frames and isinstance(layout, dict):
            expected_count = layout.get("frame_count")
            _check(
                checks,
                "layout.frame_count",
                type(expected_count) is int and expected_count == len(frames),
                len(frames),
            )
            columns = layout.get("columns")
            rows = layout.get("rows")
            padding = layout.get("padding_px")
            frame_size = layout.get("frame_size_px")
            layout_values_valid = (
                set(layout) == expected_layout_keys
                and type(columns) is int
                and 1 <= columns <= MAX_FRAMES
                and type(rows) is int
                and rows == math.ceil(len(frames) / columns)
                and type(padding) is int
                and 0 <= padding <= 1024
                and isinstance(frame_size, list)
                and len(frame_size) == 2
                and all(type(value) is int and 1 <= value <= MAX_DIMENSION for value in frame_size)
                and layout.get("origin") == "top-left"
                and layout.get("pivot_origin") == "bottom-left"
                and (
                    not processing_valid
                    or frame_size == processing.get("frame_size_px")
                )
            )
            _check(checks, "layout.values", layout_values_valid, layout)
            if layout_values_valid:
                expected_size = [
                    columns * frame_size[0] + (columns + 1) * padding,
                    rows * frame_size[1] + (rows + 1) * padding,
                ]
                _check(checks, "layout.sheet_size", expected_size == facts["size_px"], facts["size_px"])
                rects: list[dict[str, int]] = []
                ids: set[str] = set()
                expected_frame_keys = {
                    "direction",
                    "duration_ms",
                    "id",
                    "pivot_px_from_bottom_left",
                    "processed_rgba_sha256",
                    "rect_px_top_left",
                    "source",
                    "state",
                }
                frame_mask = np.zeros((image.height, image.width), dtype=bool)
                for index, frame in enumerate(frames):
                    if not isinstance(frame, dict):
                        _check(checks, f"frame.{index}.record", False, type(frame).__name__)
                        continue
                    _check(
                        checks,
                        f"frame.{index}.schema",
                        set(frame) == expected_frame_keys,
                        sorted(frame),
                    )
                    frame_id = frame.get("id")
                    unique = (
                        isinstance(frame_id, str)
                        and bool(frame_id.strip())
                        and frame_id.casefold() not in ids
                    )
                    _check(checks, f"frame.{index}.id", unique, frame_id)
                    if isinstance(frame_id, str):
                        ids.add(frame_id.casefold())
                    _check(
                        checks,
                        f"frame.{index}.duration",
                        type(frame.get("duration_ms")) is int
                        and 1 <= frame["duration_ms"] <= 60000,
                        frame.get("duration_ms"),
                    )
                    for label in ("state", "direction"):
                        value = frame.get(label)
                        _check(
                            checks,
                            f"frame.{index}.{label}",
                            value is None
                            or (isinstance(value, str) and bool(value.strip())),
                            value,
                        )
                    pivot = frame.get("pivot_px_from_bottom_left")
                    pivot_valid = (
                        isinstance(pivot, list)
                        and len(pivot) == 2
                        and all(type(value) is int for value in pivot)
                        and 0 <= pivot[0] <= frame_size[0]
                        and 0 <= pivot[1] <= frame_size[1]
                    )
                    _check(checks, f"frame.{index}.pivot", pivot_valid, pivot)
                    source = frame.get("source")
                    source_valid = (
                        isinstance(source, dict)
                        and set(source)
                        == {"path", "rgba_sha256", "sha256", "size_px"}
                        and _is_portable_relative_path(source.get("path"))
                        and _is_sha256(source.get("rgba_sha256"))
                        and _is_sha256(source.get("sha256"))
                        and isinstance(source.get("size_px"), list)
                        and len(source["size_px"]) == 2
                        and all(
                            type(value) is int and value > 0
                            for value in source["size_px"]
                        )
                    )
                    _check(checks, f"frame.{index}.source", source_valid, source)
                    rect = frame.get("rect_px_top_left")
                    rect_valid = (
                        isinstance(rect, dict)
                        and set(rect) == {"x", "y", "width", "height"}
                        and all(type(value) is int for value in rect.values())
                        and rect["width"] == frame_size[0]
                        and rect["height"] == frame_size[1]
                        and rect["x"] >= 0
                        and rect["y"] >= 0
                        and rect["x"] + rect["width"] <= image.width
                        and rect["y"] + rect["height"] <= image.height
                    )
                    _check(checks, f"frame.{index}.rect", rect_valid, rect)
                    if not rect_valid:
                        continue
                    frame_mask[
                        rect["y"] : rect["y"] + rect["height"],
                        rect["x"] : rect["x"] + rect["width"],
                    ] = True
                    column = index % columns
                    row = index // columns
                    expected_rect = {
                        "height": frame_size[1],
                        "width": frame_size[0],
                        "x": padding + column * (frame_size[0] + padding),
                        "y": padding + row * (frame_size[1] + padding),
                    }
                    _check(checks, f"frame.{index}.grid", rect == expected_rect, rect)
                    crop = image.crop(
                        (
                            rect["x"],
                            rect["y"],
                            rect["x"] + rect["width"],
                            rect["y"] + rect["height"],
                        )
                    )
                    _check(
                        checks,
                        f"frame.{index}.rgba_sha256",
                        _is_sha256(frame.get("processed_rgba_sha256"))
                        and frame.get("processed_rgba_sha256") == _rgba_digest(crop),
                        _rgba_digest(crop),
                    )
                    rects.append(rect)
                overlap = any(
                    _rectangles_overlap(rects[left], rects[right])
                    for left in range(len(rects))
                    for right in range(left + 1, len(rects))
                )
                _check(checks, "layout.no_overlap", not overlap, overlap)
                sheet_alpha = np.array(image.getchannel("A"), dtype=np.uint8)
                visible_outside_frames = int(np.count_nonzero(sheet_alpha[~frame_mask]))
                _check(
                    checks,
                    "layout.transparent_gutters",
                    visible_outside_frames == 0,
                    visible_outside_frames,
                )

    if operation == "pixelize":
        source = manifest.get("source")
        source_valid = (
            isinstance(source, dict)
            and set(source) == {"path", "rgba_sha256", "sha256", "size_px"}
            and _is_portable_relative_path(source.get("path"))
            and _is_sha256(source.get("rgba_sha256"))
            and _is_sha256(source.get("sha256"))
            and isinstance(source.get("size_px"), list)
            and len(source["size_px"]) == 2
            and all(type(value) is int and value > 0 for value in source["size_px"])
        )
        _check(checks, "source.record", source_valid, source)
        sprite = manifest.get("sprite")
        sprite_valid = (
            isinstance(sprite, dict)
            and set(sprite) == {"pivot_origin", "pivot_px_from_bottom_left"}
            and sprite.get("pivot_origin") == "bottom-left"
            and isinstance(sprite.get("pivot_px_from_bottom_left"), list)
            and len(sprite["pivot_px_from_bottom_left"]) == 2
            and all(type(value) is int for value in sprite["pivot_px_from_bottom_left"])
            and 0 <= sprite["pivot_px_from_bottom_left"][0] <= image.width
            and 0 <= sprite["pivot_px_from_bottom_left"][1] <= image.height
        )
        _check(checks, "sprite.record", sprite_valid, sprite)
        if processing_valid:
            _check(
                checks,
                "pixelize.frame_size",
                processing.get("frame_size_px") == facts["size_px"],
                facts["size_px"],
            )

    verdict = "pass" if all(item["result"] == "pass" for item in checks) else "fail"
    report = {
        "artifact": {
            "manifest_sha256": manifest_sha256,
            "png": facts,
            "png_sha256": decoded_image.sha256,
        },
        "checks": checks,
        "operation": "audit",
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "verdict": verdict,
    }
    staged_report = _stage_json(report, output)
    _commit_staged([(staged_report, output)])
    print(
        json.dumps(
            {
                "failed_checks": sum(item["result"] == "fail" for item in checks),
                "output": _relative_output(root, output),
                "status": verdict,
            },
            sort_keys=True,
        )
    )
    return 0 if verdict == "pass" else 1


def _add_processing_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--frame-width", type=int, required=True, help="Logical output frame width in pixels.")
    parser.add_argument("--frame-height", type=int, required=True, help="Logical output frame height in pixels.")
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--anchor", choices=ANCHORS, default="bottom-center")
    parser.add_argument("--resample", choices=("nearest", "box", "lanczos"), default="lanczos")
    parser.add_argument("--contrast", type=float, default=1.0)
    parser.add_argument("--background", choices=("keep", "corner-connected"), default="keep")
    parser.add_argument("--background-tolerance", type=int, default=24)
    parser.add_argument("--alpha-threshold", type=int, default=1)
    parser.add_argument("--palette", choices=("none", "median-cut", "oklab"), default="none")
    parser.add_argument("--colors", type=int, help="Target visible palette size (2-256).")
    parser.add_argument("--dither", action="store_true", help="Use Floyd-Steinberg dithering with median-cut.")
    parser.add_argument("--seed", type=int, default=123, help="Deterministic OKLab k-means seed.")


def _add_pivot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pivot",
        choices=("center", "bottom-center", "bottom-left", "custom"),
        default="bottom-center",
    )
    parser.add_argument("--pivot-x", type=int)
    parser.add_argument("--pivot-y", type=int)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create deterministic sprites and sprite sheets with auditable manifests."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {TOOL_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Process ordered frames into one sprite sheet.")
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-dir", help="Directory to search for source frames.")
    source.add_argument("--frame-data", help="Strict JSON file defining frame order and metadata.")
    build.add_argument("--pattern", default="*.png", help="Glob relative to --input-dir (default: *.png).")
    build.add_argument("--duration-ms", type=int, default=100, help="Default frame duration.")
    build.add_argument("--columns", type=int, default=0, help="Sheet columns; 0 chooses up to eight.")
    build.add_argument("--padding", type=int, default=0, help="Transparent outer and inter-cell padding.")
    _add_pivot_arguments(build)
    build.add_argument("--output-root", required=True)
    build.add_argument("--output", required=True, help="PNG path, absolute or relative to --output-root.")
    build.add_argument("--manifest", required=True, help="JSON path, absolute or relative to --output-root.")
    build.add_argument("--preview", help="Optional checkerboard/grid preview PNG.")
    build.add_argument("--preview-scale", type=int, default=4)
    build.add_argument("--force", action="store_true", help="Replace only the explicitly named output files.")
    _add_processing_arguments(build)
    build.set_defaults(handler=_run_build)

    pixelize = subparsers.add_parser("pixelize", help="Convert one source image into one logical sprite frame.")
    pixelize.add_argument("--input", required=True)
    pixelize.add_argument("--output-root", required=True)
    pixelize.add_argument("--output", required=True)
    pixelize.add_argument("--manifest", required=True)
    pixelize.add_argument("--preview", help="Optional checkerboard/grid preview PNG.")
    pixelize.add_argument("--preview-scale", type=int, default=4)
    pixelize.add_argument("--force", action="store_true", help="Replace only the explicitly named output files.")
    _add_pivot_arguments(pixelize)
    _add_processing_arguments(pixelize)
    pixelize.set_defaults(handler=_run_pixelize)

    audit = subparsers.add_parser("audit", help="Re-read a PNG and verify it against its manifest.")
    audit.add_argument("--image", required=True)
    audit.add_argument("--manifest", required=True)
    audit.add_argument("--output-root", required=True)
    audit.add_argument("--output", required=True)
    audit.add_argument("--force", action="store_true", help="Replace only the explicitly named audit report.")
    audit.set_defaults(handler=_run_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (
        OSError,
        ValueError,
        TypeError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
