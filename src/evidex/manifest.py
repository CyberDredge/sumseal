"""Manifest creation, canonical form and digest.

The manifest digest is the SHA-256 of the canonical JSON form, so reformatting
the file on disk (indentation, key order, whitespace) never changes it.

``create`` follows the fail-closed rules in SPEC.md: it never guesses and never
skips anything silently. Every problem is collected and reported together, and
no manifest is written unless the whole folder was recorded.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import stat
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .hashing import HASH_ALGORITHM, hash_file

SCHEMA_VERSION = 1
MANIFEST_SUFFIX = ".evidex.json"

KIND_SYMLINK = "symlink"
KIND_REPARSE_POINT = "reparse_point"
KIND_OTHER = "other"


class EvidexError(Exception):
    """Usage or input error. The CLI prints it with its details and exits with 2."""

    def __init__(self, message: str, details: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.details = list(details)


# --- canonical form and digest ----------------------------------------------


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    """Return the canonical UTF-8 encoding of ``manifest`` as defined in SPEC.md.

    NaN and Infinity are not valid JSON; they raise ValueError (fail closed).
    """
    text = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def manifest_digest(manifest: dict[str, Any]) -> str:
    """Return the lowercase hex SHA-256 of the canonical form of ``manifest``."""
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def pretty_text(manifest: dict[str, Any]) -> str:
    """Return the human-readable on-disk form (2-space indent, trailing newline)."""
    return json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


# --- times -------------------------------------------------------------------


def format_utc(seconds: int) -> str:
    """Format whole seconds since the epoch as ISO 8601 UTC ending in ``Z``."""
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> str:
    """Return the current time as ISO 8601 UTC, whole seconds, ending in ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- paths, collisions, excludes ---------------------------------------------


def collision_key(name: str) -> str:
    """Key under which two names count as the same (NFC, then case-folded)."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", name).casefold())


def find_collisions(names: Iterable[str]) -> list[list[str]]:
    """Return groups of distinct names that collide after case-folding or NFC/NFD.

    Each group is sorted, and groups are sorted by their first name.
    """
    groups: dict[str, set[str]] = {}
    for name in names:
        groups.setdefault(collision_key(name), set()).add(name)
    return sorted(sorted(group) for group in groups.values() if len(group) > 1)


def _utf8_order(path: str) -> bytes:
    return path.encode("utf-8")


def _join(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name


def _excluded(rel_path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel_path, pattern) for pattern in patterns)


def _reason(exc: BaseException) -> str:
    if isinstance(exc, OSError) and exc.strerror:
        return exc.strerror
    return str(exc) or type(exc).__name__


def _is_reparse_point(entry: os.DirEntry[str]) -> bool:
    """True for Windows reparse points (junctions, mount points, cloud files)."""
    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


# --- scanning ----------------------------------------------------------------


class _Scan:
    def __init__(self) -> None:
        self.files: list[tuple[str, str]] = []  # (manifest path, filesystem path)
        self.special: list[dict[str, str]] = []
        self.problems: list[str] = []


def _scan(root: str, patterns: Sequence[str]) -> _Scan:
    scan = _Scan()
    _scan_dir(root, "", patterns, scan)
    return scan


def _scan_dir(dir_os: str, dir_rel: str, patterns: Sequence[str], scan: _Scan) -> None:
    try:
        with os.scandir(dir_os) as listing:
            entries = sorted(listing, key=lambda e: e.name)
    except OSError as exc:
        scan.problems.append(f"{dir_rel or '.'}: cannot list folder ({_reason(exc)})")
        return

    kept: list[tuple[os.DirEntry[str], str]] = []
    for entry in entries:
        try:
            entry.name.encode("utf-8")
        except UnicodeEncodeError:
            shown = ascii(_join(dir_rel, entry.name))
            scan.problems.append(f"{shown}: file name is not valid UTF-8")
            continue
        rel = _join(dir_rel, unicodedata.normalize("NFC", entry.name))
        if not _excluded(rel, patterns):
            kept.append((entry, rel))

    for group in find_collisions(entry.name for entry, _ in kept):
        shown = ", ".join(ascii(_join(dir_rel, name)) for name in group)
        scan.problems.append(
            f"names collide after case-folding or Unicode normalization: {shown}"
        )

    for entry, rel in kept:
        try:
            if entry.is_symlink():
                scan.special.append({"path": rel, "kind": KIND_SYMLINK})
            elif _is_reparse_point(entry):
                scan.special.append({"path": rel, "kind": KIND_REPARSE_POINT})
            elif entry.is_dir(follow_symlinks=False):
                _scan_dir(entry.path, rel, patterns, scan)
            elif entry.is_file(follow_symlinks=False):
                scan.files.append((rel, entry.path))
            else:
                scan.special.append({"path": rel, "kind": KIND_OTHER})
        except OSError as exc:
            scan.problems.append(f"{rel}: cannot inspect ({_reason(exc)})")


# --- create ------------------------------------------------------------------


def default_output_path(folder: str | os.PathLike[str]) -> Path:
    """``<folder-name>.evidex.json`` in the folder's parent."""
    absolute = Path(os.path.abspath(folder))
    return absolute.parent / (absolute.name + MANIFEST_SUFFIX)


def build_manifest(
    folder: str | os.PathLike[str],
    *,
    collector: str,
    case_id: str | None = None,
    excludes: Sequence[str] = (),
    skip_special: bool = False,
) -> dict[str, Any]:
    """Scan and hash ``folder`` and return the manifest as a dict.

    Raises EvidexError (with every problem listed) instead of returning a
    partial manifest.
    """
    absolute = os.path.abspath(folder)
    if not os.path.isdir(absolute):
        raise EvidexError(f"not a folder: {os.fspath(folder)}")
    root_name = unicodedata.normalize("NFC", os.path.basename(absolute))
    if not root_name:
        raise EvidexError("cannot record a drive or filesystem root; pick a folder")
    if not collector or not collector.strip():
        raise EvidexError("--collector must not be empty")
    if case_id is not None and not case_id.strip():
        raise EvidexError("--case must not be empty when given")
    if any(not pattern for pattern in excludes):
        raise EvidexError("--exclude must not be an empty pattern")

    patterns = [unicodedata.normalize("NFC", pattern) for pattern in excludes]
    created = utc_now()
    scan = _scan(absolute, patterns)

    if scan.problems:
        raise EvidexError("cannot create a manifest; no manifest written", scan.problems)
    if scan.special and not skip_special:
        raise EvidexError(
            "found symlinks or special files; no manifest written. "
            "Use --skip-special to record them in 'skipped' and leave them out",
            [f"{item['path']} ({item['kind']})" for item in scan.special],
        )
    if not scan.files:
        raise EvidexError(f"no files to record in {root_name}; no manifest written")

    entries: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for rel, path in scan.files:
        try:
            mtime = format_utc(os.stat(path).st_mtime_ns // 1_000_000_000)
            sha256, size = hash_file(path)
        except (OSError, ValueError, OverflowError) as exc:
            unreadable.append(f"{rel}: cannot read ({_reason(exc)})")
            continue
        entries.append(
            {
                "path": rel,
                "size": size,
                "sha256": sha256,
                "mtime_utc": mtime,
                "hashed_utc": utc_now(),
            }
        )
    if unreadable:
        raise EvidexError("unreadable files; no manifest written", unreadable)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "created_utc": created,
        "collector": collector,
    }
    if case_id is not None:
        manifest["case_id"] = case_id
    manifest.update(
        {
            "root_name": root_name,
            "hash_algorithm": HASH_ALGORITHM,
            "excludes": list(excludes),
            "skipped": sorted(scan.special, key=lambda item: _utf8_order(item["path"])),
            "files": sorted(entries, key=lambda item: _utf8_order(item["path"])),
        }
    )
    return manifest


def write_manifest(manifest: dict[str, Any], out: str | os.PathLike[str]) -> str:
    """Write ``manifest`` pretty-printed to a new file and return its digest.

    Never overwrites: an existing file at ``out`` is an error and stays untouched.
    """
    data = pretty_text(manifest).encode("utf-8")
    digest = manifest_digest(manifest)
    try:
        with open(out, "xb") as handle:
            handle.write(data)
    except FileExistsError:
        raise EvidexError(
            f"output file already exists, not overwriting: {os.fspath(out)}"
        ) from None
    except OSError as exc:
        raise EvidexError(f"cannot write {os.fspath(out)} ({_reason(exc)})") from None
    return digest


def create(
    folder: str | os.PathLike[str],
    *,
    collector: str,
    case_id: str | None = None,
    excludes: Sequence[str] = (),
    skip_special: bool = False,
    out: str | os.PathLike[str] | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    """Build and write a manifest. Returns (output path, digest, manifest)."""
    manifest = build_manifest(
        folder,
        collector=collector,
        case_id=case_id,
        excludes=excludes,
        skip_special=skip_special,
    )
    out_path = Path(out) if out is not None else default_output_path(folder)
    digest = write_manifest(manifest, out_path)
    return out_path, digest, manifest
