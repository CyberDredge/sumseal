"""Manifest canonical form and digest.

The manifest digest is the SHA-256 of the canonical JSON form, so reformatting
the file on disk (indentation, key order, whitespace) never changes it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = 1


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
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
