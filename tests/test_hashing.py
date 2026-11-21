"""Hashing rows from the SPEC.md required test table."""

import hashlib

import pytest

from sumseal.hashing import CHUNK_SIZE, hash_file

# (SPEC.md row, file content, expected sha256)
HASH_ROWS = [
    (
        "Empty file",
        b"",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    (
        "File containing abc",
        b"abc",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    ),
]


@pytest.mark.parametrize(
    "content,expected", [(c, e) for _, c, e in HASH_ROWS], ids=[r for r, _, _ in HASH_ROWS]
)
def test_known_hashes(tmp_path, content, expected):
    target = tmp_path / "sample.txt"
    target.write_bytes(content)
    assert hash_file(target) == (expected, len(content))


@pytest.mark.parametrize(
    "size", [CHUNK_SIZE - 1, CHUNK_SIZE, CHUNK_SIZE + 1, 2 * CHUNK_SIZE + 7]
)
def test_chunk_boundaries_match_one_shot_hash(tmp_path, size):
    # Supports the "Files are hashed in 1 MiB chunks" rule: chunking must not
    # change the result at or around a chunk boundary.
    content = bytes(i % 251 for i in range(size))
    target = tmp_path / "large.bin"
    target.write_bytes(content)
    assert hash_file(target) == (hashlib.sha256(content).hexdigest(), size)


def test_missing_file_raises(tmp_path):
    # Fail closed: an unreadable path is an error, never a silent result.
    with pytest.raises(OSError):
        hash_file(tmp_path / "does-not-exist.txt")
