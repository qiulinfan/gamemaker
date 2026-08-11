#!/usr/bin/env python3
"""Produce a deterministic, non-extracting audit of an asset archive or directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
import stat
import struct
import zipfile


EXECUTABLE_SUFFIXES = {
    ".app",
    ".bat",
    ".cmd",
    ".com",
    ".command",
    ".dll",
    ".dylib",
    ".exe",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".py",
    ".scr",
    ".sh",
    ".so",
    ".vbs",
}
AUTO_COMPILED_SUFFIXES = {".asmdef", ".asmref", ".boo", ".cs", ".rsp"}
LICENSE_NAMES = {"copying", "copyright", "license", "licence", "notice", "readme"}
DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_UNCOMPRESSED_BYTES = 1_073_741_824
DEFAULT_MAX_SINGLE_FILE_BYTES = 536_870_912
DEFAULT_MAX_RATIO = 200.0
ARCHIVE_SUFFIXES = {
    ".7z": "7z",
    ".bz2": "bzip2",
    ".cab": "cab",
    ".gz": "gzip",
    ".rar": "rar",
    ".tar": "tar",
    ".tar.bz2": "tar.bz2",
    ".tar.gz": "tar.gz",
    ".tar.xz": "tar.xz",
    ".tbz": "tar.bz2",
    ".tbz2": "tar.bz2",
    ".tgz": "tar.gz",
    ".txz": "tar.xz",
    ".xz": "xz",
    ".zip": "zip",
}
WINDOWS_RESERVED_DEVICE_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_unsafe(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    components = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if path.is_absolute() or ".." in path.parts:
        return True
    for component in components:
        if ":" in component or component.endswith((".", " ")):
            return True
        canonical_component = component.rstrip(" .").casefold()
        device_stem = canonical_component.split(".", 1)[0].rstrip(" ")
        if device_stem in WINDOWS_RESERVED_DEVICE_NAMES:
            return True
    return False


def windows_canonical_archive_path(name: str) -> str:
    """Return the extraction identity Win32 would use for collision checks."""

    normalized = name.replace("\\", "/")
    return "/".join(
        component.rstrip(" .").casefold()
        for component in normalized.split("/")
        if component not in {"", "."}
    )


def looks_like_license(name: str) -> bool:
    stem = "".join(character for character in Path(name).stem.lower() if character.isalnum())
    return any(token in stem for token in LICENSE_NAMES)


def summarize_entries(entries: list[tuple[str, int]]) -> dict[str, object]:
    suffixes = Counter((Path(name).suffix.lower() or "[no extension]") for name, _ in entries if not name.endswith("/"))
    files = [(name, size) for name, size in entries if not name.endswith("/")]
    return {
        "file_count": len(files),
        "total_uncompressed_bytes": sum(size for _, size in files),
        "extensions": dict(sorted(suffixes.items())),
        "license_candidates": sorted(name for name, _ in files if looks_like_license(name)),
        "unexpected_executables": sorted(name for name, _ in files if Path(name).suffix.lower() in EXECUTABLE_SUFFIXES),
        "unsafe_paths": sorted(name for name, _ in entries if is_unsafe(name)),
        "files": [{"path": name, "size_bytes": size} for name, size in sorted(files)],
    }


def risky_code_entry(name: str) -> bool:
    normalized = PurePosixPath(name.replace("\\", "/"))
    return any(
        Path(part).suffix.lower() in EXECUTABLE_SUFFIXES | AUTO_COMPILED_SUFFIXES
        for part in normalized.parts
    )


def archive_format_from_name(path: Path) -> str | None:
    lower_name = path.name.lower()
    for suffix in sorted(ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lower_name.endswith(suffix):
            return ARCHIVE_SUFFIXES[suffix]
    return None


def archive_format_from_magic(path: Path) -> str | None:
    with path.open("rb") as handle:
        header = handle.read(600)
    signatures = (
        (b"Rar!\x1a\x07", "rar"),
        (b"7z\xbc\xaf'\x1c", "7z"),
        (b"\x1f\x8b", "gzip"),
        (b"BZh", "bzip2"),
        (b"\xfd7zXZ\x00", "xz"),
        (b"MSCF", "cab"),
    )
    for signature, name in signatures:
        if header.startswith(signature):
            return name
    if len(header) >= 262 and header[257:262] == b"ustar":
        return "tar"
    return None


def declared_zip_entry_count(path: Path) -> int | None:
    """Read the classic EOCD count before ZipFile allocates an entry list."""

    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - (65_535 + 22)))
        tail = handle.read()
    marker = tail.rfind(b"PK\x05\x06")
    if marker < 0 or marker + 22 > len(tail):
        return None
    fields = struct.unpack_from("<4s4H2LH", tail, marker)
    comment_length = fields[7]
    if marker + 22 + comment_length > len(tail):
        return None
    return int(fields[4])


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


def audit(
    path: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_single_file_bytes: int = DEFAULT_MAX_SINGLE_FILE_BYTES,
    max_ratio: float = DEFAULT_MAX_RATIO,
) -> dict[str, object]:
    if path.is_dir():
        entries = [(item.relative_to(path).as_posix(), item.stat().st_size) for item in path.rglob("*") if item.is_file()]
        return {
            "path": str(path.resolve()),
            "kind": "directory",
            "verdict": "pass",
            "safe_to_extract": False,
            **summarize_entries(entries),
        }

    if not path.is_file():
        raise FileNotFoundError(path)

    base: dict[str, object] = {
        "path": str(path.resolve()),
        "kind": "file",
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if zipfile.is_zipfile(path):
        declared_entries = declared_zip_entry_count(path)
        if declared_entries is None:
            base.update(
                {
                    "kind": "zip",
                    "verdict": "blocked",
                    "path_scan_passed": False,
                    "safe_to_extract": False,
                    "blocked_reasons": ["zip_central_directory_metadata_invalid"],
                }
            )
            return base
        if declared_entries > max_files:
            base.update(
                {
                    "kind": "zip",
                    "declared_entry_count": declared_entries,
                    "verdict": "blocked",
                    "path_scan_passed": False,
                    "safe_to_extract": False,
                    "blocked_reasons": ["declared_entry_count_limit_exceeded"],
                    "limits": {"max_files": max_files},
                }
            )
            return base
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
        entries = [(item.filename, item.file_size) for item in infos]
        base["kind"] = "zip"
        base.update(summarize_entries(entries))
        symlink_entries: list[str] = []
        special_entries: list[str] = []
        encrypted_entries: list[str] = []
        zero_compressed_entries: list[str] = []
        ratios: list[float] = []
        normalized_names: list[str] = []
        for item in infos:
            normalized_names.append(windows_canonical_archive_path(item.filename))
            mode = (item.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(mode)
            if stat.S_ISLNK(mode):
                symlink_entries.append(item.filename)
            elif file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                special_entries.append(item.filename)
            if item.flag_bits & 0x1:
                encrypted_entries.append(item.filename)
            if not item.is_dir() and item.file_size:
                if item.compress_size == 0:
                    zero_compressed_entries.append(item.filename)
                ratios.append(item.file_size / max(1, item.compress_size))
        duplicate_entries = sorted(
            name for name, count in Counter(normalized_names).items() if count > 1
        )
        code_entries = sorted(
            item.filename for item in infos if not item.is_dir() and risky_code_entry(item.filename)
        )
        oversized_entries = sorted(
            item.filename
            for item in infos
            if not item.is_dir() and item.file_size > max_single_file_bytes
        )
        max_ratio_observed = max(ratios, default=1.0)
        base.update(
            {
                "entry_count": len(infos),
                "symlink_entries": sorted(symlink_entries),
                "special_entries": sorted(special_entries),
                "encrypted_entries": sorted(encrypted_entries),
                "zero_compressed_entries": sorted(zero_compressed_entries),
                "duplicate_entries": duplicate_entries,
                "code_or_executable_entries": code_entries,
                "oversized_entries": oversized_entries,
                "max_compression_ratio": max_ratio_observed,
                "limits": {
                    "max_files": max_files,
                    "max_uncompressed_bytes": max_uncompressed_bytes,
                    "max_single_file_bytes": max_single_file_bytes,
                    "max_ratio": max_ratio,
                },
            }
        )
        blocked_reasons: list[str] = []
        if base.get("unsafe_paths"):
            blocked_reasons.append("unsafe_archive_paths")
        if base.get("unexpected_executables"):
            blocked_reasons.append("unexpected_executables")
        if not base.get("license_candidates"):
            blocked_reasons.append("missing_license_evidence")
        if symlink_entries or special_entries:
            blocked_reasons.append("link_or_special_entries")
        if encrypted_entries:
            blocked_reasons.append("encrypted_entries_cannot_be_audited")
        if zero_compressed_entries:
            blocked_reasons.append("nonempty_zero_compressed_entries")
        if duplicate_entries:
            blocked_reasons.append("duplicate_or_case_colliding_paths")
        if code_entries:
            blocked_reasons.append("code_or_auto_compiled_entries_require_review")
        if len(infos) > max_files:
            blocked_reasons.append("entry_count_limit_exceeded")
        if int(base["total_uncompressed_bytes"]) > max_uncompressed_bytes:
            blocked_reasons.append("total_uncompressed_limit_exceeded")
        if oversized_entries:
            blocked_reasons.append("single_file_limit_exceeded")
        if max_ratio_observed > max_ratio:
            blocked_reasons.append("compression_ratio_limit_exceeded")
        base["verdict"] = "blocked" if blocked_reasons else "pass"
        base["path_scan_passed"] = not base.get("unsafe_paths")
        base["safe_to_extract"] = not blocked_reasons
        base["blocked_reasons"] = blocked_reasons
        return base

    named_format = archive_format_from_name(path)
    magic_format = archive_format_from_magic(path)
    suspected_format = magic_format or named_format
    if suspected_format is not None:
        base.update(
            {
                "kind": "unsupported_archive",
                "archive_format": suspected_format,
                "verdict": "blocked",
                "safe_to_extract": False,
                "blocked_reasons": [
                    "unsupported_or_invalid_archive_format; only ZIP is supported"
                ],
            }
        )
        return base

    base["verdict"] = "pass"
    base["safe_to_extract"] = False
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Asset archive, file, or extracted directory")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Existing temporary root that must contain --output",
    )
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument(
        "--max-uncompressed-bytes", type=int, default=DEFAULT_MAX_UNCOMPRESSED_BYTES
    )
    parser.add_argument(
        "--max-single-file-bytes", type=int, default=DEFAULT_MAX_SINGLE_FILE_BYTES
    )
    parser.add_argument("--max-ratio", type=float, default=DEFAULT_MAX_RATIO)
    args = parser.parse_args()
    if bool(args.output) != bool(args.output_root):
        parser.error("--output and --output-root must be supplied together")
    if (
        args.max_files < 1
        or args.max_uncompressed_bytes < 1
        or args.max_single_file_bytes < 1
        or args.max_ratio < 1
    ):
        parser.error("archive limits must all be positive and --max-ratio must be >= 1")
    result = audit(
        args.path,
        max_files=args.max_files,
        max_uncompressed_bytes=args.max_uncompressed_bytes,
        max_single_file_bytes=args.max_single_file_bytes,
        max_ratio=args.max_ratio,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        try:
            output = prepare_output(args.output, args.output_root)
        except (FileExistsError, NotADirectoryError, OSError, ValueError) as exc:
            parser.error(str(exc))
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 2 if result.get("verdict") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
