"""Compare a folder with its manifest.

Only paths found by walking the folder are ever opened. Paths in the manifest
are used as lookup keys, never joined onto the folder, so a tampered manifest
cannot make verify read anything outside the folder.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .hashing import hash_file
from .manifest import (
    EvidexError,
    default_output_path,
    format_utc,
    load_manifest,
    manifest_digest,
    scan_folder,
)

OK = "OK"
CHANGED = "CHANGED"
MISSING = "MISSING"
NEW = "NEW"
UNREADABLE = "UNREADABLE"
RESULTS = (OK, CHANGED, MISSING, NEW, UNREADABLE)
PROBLEMS = frozenset({CHANGED, MISSING, NEW, UNREADABLE})


@dataclass(frozen=True)
class Finding:
    path: str
    result: str
    detail: str = ""


@dataclass
class VerifyReport:
    manifest_path: Path
    digest: str
    manifest: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {result: sum(f.result == result for f in self.findings) for result in RESULTS}

    @property
    def ok(self) -> bool:
        return not any(f.result in PROBLEMS for f in self.findings)


def _utf8_order(path: str) -> bytes:
    return path.encode("utf-8")


def _under(path: str, blocked: str) -> bool:
    return blocked == "" or path == blocked or path.startswith(blocked + "/")


def verify(
    folder: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str] | None = None,
) -> VerifyReport:
    """Verify ``folder`` against its manifest and return every finding."""
    absolute = os.path.abspath(folder)
    if not os.path.isdir(absolute):
        raise EvidexError(f"not a folder: {os.fspath(folder)}")
    path = Path(manifest_path) if manifest_path is not None else default_output_path(folder)
    manifest = load_manifest(path)
    report = VerifyReport(manifest_path=path, digest=manifest_digest(manifest), manifest=manifest)

    patterns = [unicodedata.normalize("NFC", p) for p in manifest["excludes"]]
    scan = scan_folder(absolute, patterns)
    if scan.problems:
        raise EvidexError("cannot verify: the folder has names that cannot be matched", scan.problems)

    recorded_files = {entry["path"]: entry for entry in manifest["files"]}
    recorded_special = {item["path"]: item["kind"] for item in manifest["skipped"]}
    disk_files = dict(scan.files)
    disk_special = {item["path"]: item["kind"] for item in scan.special}
    blocked = [rel for rel, _ in scan.unreadable]

    findings: list[Finding] = [
        Finding(rel or ".", UNREADABLE, why) for rel, why in scan.unreadable
    ]
    paths = set(recorded_files) | set(recorded_special) | set(disk_files) | set(disk_special)
    for rel in sorted(paths, key=_utf8_order):
        if any(_under(rel, b) for b in blocked):
            if rel not in blocked and (rel in recorded_files or rel in recorded_special):
                findings.append(Finding(rel, UNREADABLE, "inside a folder that cannot be read"))
            continue
        findings.append(
            _compare(rel, recorded_files.get(rel), recorded_special.get(rel),
                     disk_files.get(rel), disk_special.get(rel), report.notes)
        )
    report.findings = sorted(findings, key=lambda f: _utf8_order(f.path))
    return report


def _compare(
    rel: str,
    recorded: dict[str, Any] | None,
    recorded_kind: str | None,
    disk_path: str | None,
    disk_kind: str | None,
    notes: list[str],
) -> Finding:
    if recorded is None and recorded_kind is None:
        return Finding(rel, NEW, f"{disk_kind}, not in the manifest" if disk_kind else "")

    if recorded is None:  # recorded as a skipped special item
        if disk_kind == recorded_kind:
            return Finding(rel, OK, f"{recorded_kind}, skipped and not hashed")
        if disk_kind is not None:
            return Finding(rel, CHANGED, f"recorded as {recorded_kind}, now {disk_kind}")
        if disk_path is not None:
            return Finding(rel, CHANGED, f"recorded as {recorded_kind}, now a regular file")
        return Finding(rel, MISSING)

    if disk_kind is not None:
        return Finding(rel, CHANGED, f"recorded as a file, now {disk_kind}")
    if disk_path is None:
        return Finding(rel, MISSING)

    try:
        mtime = format_utc(os.stat(disk_path).st_mtime_ns // 1_000_000_000)
        sha256, size = hash_file(disk_path)
    except (OSError, ValueError, OverflowError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        return Finding(rel, UNREADABLE, f"cannot read ({reason})")

    if size != recorded["size"]:
        return Finding(rel, CHANGED, f"size {recorded['size']} -> {size} bytes")
    if sha256 != recorded["sha256"]:
        return Finding(rel, CHANGED, "content differs, same size")
    if mtime != recorded["mtime_utc"]:
        shown = rel if rel.isprintable() else ascii(rel)
        notes.append(
            f"{shown}: modified time changed ({recorded['mtime_utc']} -> {mtime}), content unchanged"
        )
    return Finding(rel, OK)
