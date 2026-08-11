#!/usr/bin/env python3
"""Run the bundled Blender inventory under a fail-closed isolation contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


ISOLATION_ARGUMENTS = (
    "--background",
    "--factory-startup",
    "--disable-autoexec",
    "--offline-mode",
    "--python-exit-code",
    "1",
)
SUPPORTED_ASSET_SUFFIXES = {".blend", ".fbx", ".glb", ".gltf"}
DEFAULT_TIMEOUT_SECONDS = 300


def build_command(
    blender: str,
    asset: Path,
    output: Path,
    output_root: Path,
    inventory_script: Path,
) -> list[str]:
    command = [
        blender,
        *ISOLATION_ARGUMENTS,
        "--python",
        str(inventory_script.resolve()),
        "--",
        "--asset",
        str(asset.resolve()),
        "--output",
        str(output.resolve()),
        "--output-root",
        str(output_root.resolve()),
    ]
    return command


def prepare_output(output: Path, output_root: Path) -> tuple[Path, Path]:
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
    return destination, root


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_bounded(
    command: list[str],
    timeout_seconds: int,
    *,
    popen_factory=None,
    tree_terminator=None,
) -> int:
    popen_factory = popen_factory or subprocess.Popen
    tree_terminator = tree_terminator or terminate_process_tree
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    process = popen_factory(command, **kwargs)
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        tree_terminator(process)
        process.wait()
        print(
            f"BLOCKED: Blender inventory exceeded {timeout_seconds}s and its process tree was terminated.",
            file=sys.stderr,
        )
        return 124


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blender",
        required=True,
        type=Path,
        help="Explicit absolute path to a trusted Blender executable",
    )
    parser.add_argument("--asset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    args = parser.parse_args()

    if not 1 <= args.timeout_seconds <= 3600:
        parser.error("--timeout-seconds must be between 1 and 3600")

    asset = args.asset.expanduser().resolve(strict=True)
    if not asset.is_file():
        parser.error(f"asset is not a file: {asset}")
    if asset.suffix.lower() not in SUPPORTED_ASSET_SUFFIXES:
        parser.error(f"unsupported asset extension: {asset.suffix.lower()}")
    try:
        output, output_root = prepare_output(args.output, args.output_root)
    except (FileExistsError, NotADirectoryError, OSError, ValueError) as exc:
        parser.error(str(exc))

    if not args.blender.is_absolute():
        parser.error("--blender must be an absolute path to an explicitly trusted executable")
    try:
        blender = args.blender.expanduser().resolve(strict=True)
    except OSError as exc:
        parser.error(f"trusted Blender executable cannot be resolved: {exc}")
    if not blender.is_file():
        parser.error(f"trusted Blender executable is not a file: {blender}")

    inventory_script = Path(__file__).with_name("blender_asset_inventory.py")
    command = build_command(str(blender), asset, output, output_root, inventory_script)
    try:
        return run_bounded(command, args.timeout_seconds)
    except OSError as exc:
        print(f"Failed to launch Blender: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
