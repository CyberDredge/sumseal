"""Readable reports of a manifest, as Markdown or CSV text."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from .manifest import manifest_digest

DISCLAIMER = (
    "sumseal records and checks file integrity. It does not prove who created a file "
    "or that its content is genuine, and it is not legal advice."
)

CSV_COLUMNS = (
    "path", "size", "sha256", "mtime_utc", "hashed_utc",
    "source_url", "source_accessed_utc", "source_note",
)

_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|#~])")
_CSV_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _md(value: Any) -> str:
    """Escape a value for a Markdown table cell. Unprintable text is shown escaped."""
    text = str(value)
    if not text.isprintable():
        text = ascii(text)
    return _MD_SPECIAL.sub(r"\\\1", text)


def _source_cell(entry: dict[str, Any]) -> str:
    source = entry.get("source")
    if not source:
        return ""
    text = f"{_md(source['url'])} (accessed {_md(source['accessed_utc'])})"
    if "note" in source:
        text += f" {_md(source['note'])}"
    return text


def render_markdown(manifest: dict[str, Any]) -> str:
    excludes = manifest["excludes"]
    rows = [
        ("Folder", manifest["root_name"]),
        ("Collector", manifest["collector"]),
        ("Case ID", manifest.get("case_id", "(none)")),
        ("Created (UTC)", manifest["created_utc"]),
        ("Tool version", manifest["tool_version"]),
        ("Hash algorithm", manifest["hash_algorithm"]),
        ("Manifest digest (sha256)", manifest_digest(manifest)),
        ("Files", len(manifest["files"])),
        ("Skipped special items", len(manifest["skipped"])),
        ("Excludes", ", ".join(excludes) if excludes else "(none)"),
    ]
    lines = ["# sumseal manifest report", "", "| Field | Value |", "|---|---|"]
    lines += [f"| {name} | {_md(value)} |" for name, value in rows]
    lines += [
        "", "## Files", "",
        "| Path | Size (bytes) | SHA-256 | Modified (UTC) | Hashed (UTC) | Source |",
        "|---|---:|---|---|---|---|",
    ]
    for entry in manifest["files"]:
        lines.append(
            f"| {_md(entry['path'])} | {entry['size']} | {entry['sha256']} | "
            f"{entry['mtime_utc']} | {entry['hashed_utc']} | {_source_cell(entry)} |"
        )
    lines += ["", "## Skipped special items", ""]
    if manifest["skipped"]:
        lines += ["| Path | Kind |", "|---|---|"]
        lines += [f"| {_md(item['path'])} | {_md(item['kind'])} |" for item in manifest["skipped"]]
    else:
        lines.append("None.")
    lines += ["", "---", "", DISCLAIMER, ""]
    return "\n".join(lines)


def _csv_cell(value: Any) -> str:
    """Prefix text that a spreadsheet would run as a formula with a single quote."""
    text = str(value)
    return "'" + text if text.startswith(_CSV_FORMULA_START) else text


def render_csv(manifest: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for entry in manifest["files"]:
        source = entry.get("source", {})
        writer.writerow(
            _csv_cell(value)
            for value in (
                entry["path"], entry["size"], entry["sha256"], entry["mtime_utc"],
                entry["hashed_utc"], source.get("url", ""),
                source.get("accessed_utc", ""), source.get("note", ""),
            )
        )
    return buffer.getvalue()
