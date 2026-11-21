"""SHA-256 hashing of files, read in fixed-size chunks."""

from __future__ import annotations

import hashlib
import os

HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 1024 * 1024  # 1 MiB, per SPEC.md


def hash_file(path: str | os.PathLike[str]) -> tuple[str, int]:
    """Return (lowercase hex SHA-256, size in bytes) of the file at ``path``.

    The size is the number of bytes actually read and hashed, so the two values
    always describe the same content even if the file changes on disk later.
    Any OSError (missing, unreadable, a directory) propagates to the caller;
    nothing is skipped or guessed here.
    """
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size
