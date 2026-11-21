"""Canonical JSON and manifest digest rows from the SPEC.md required test table."""

import json

import pytest

from evidex.manifest import canonical_bytes, manifest_digest, pretty_text

SAMPLE = {
    "schema_version": 1,
    "tool_version": "0.1.0",
    "created_utc": "2026-01-02T03:04:05Z",
    "collector": "Example Collector",
    "root_name": "demo-case",
    "hash_algorithm": "sha256",
    "excludes": [],
    "skipped": [],
    "files": [
        {
            "path": "notes/caf\u00e9.txt",
            "size": 3,
            "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "mtime_utc": "2026-01-01T00:00:00Z",
            "hashed_utc": "2026-01-02T03:04:05Z",
            "source": {
                "url": "https://example.com/page",
                "accessed_utc": "2026-01-01T12:00:00Z",
                "note": "fictional example",
            },
        }
    ],
}


def test_reformatted_manifest_same_digest(tmp_path):
    # SPEC.md row: "Reformatted manifest on disk" -> same digest.
    on_disk = tmp_path / "demo-case.evidex.json"
    on_disk.write_text(pretty_text(SAMPLE), encoding="utf-8")
    original = manifest_digest(json.loads(on_disk.read_text(encoding="utf-8")))

    variants = [
        json.dumps(SAMPLE),  # default separators, no indent
        json.dumps(SAMPLE, indent=4, ensure_ascii=True),  # wider indent, \u escapes
        json.dumps(dict(reversed(list(SAMPLE.items()))), indent="\t"),  # key order, tabs
        "\n\n  " + json.dumps(SAMPLE, separators=(" , ", " : ")) + "  \n",
    ]
    for text in variants:
        on_disk.write_text(text, encoding="utf-8")
        reloaded = json.loads(on_disk.read_text(encoding="utf-8"))
        assert manifest_digest(reloaded) == original


def test_content_change_changes_digest():
    changed = json.loads(json.dumps(SAMPLE))
    changed["files"][0]["size"] = 4
    assert manifest_digest(changed) != manifest_digest(SAMPLE)


def test_canonical_form_is_exact():
    # Pins the SPEC.md definition: sorted keys, no spaces, raw UTF-8 (no \u escapes).
    assert canonical_bytes({"b": 1, "a": "caf\u00e9", "c": [2, {"z": 0, "y": None}]}) == (
        b'{"a":"caf\xc3\xa9","b":1,"c":[2,{"y":null,"z":0}]}'
    )


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "-inf"]
)
def test_nan_or_infinity_raises(bad):
    # SPEC.md row: "NaN or Infinity in manifest" -> error, no canonical form or digest.
    manifest = json.loads(json.dumps(SAMPLE))
    manifest["files"][0]["size"] = bad
    with pytest.raises(ValueError):
        canonical_bytes(manifest)
    with pytest.raises(ValueError):
        manifest_digest(manifest)


def test_pretty_text_round_trips_and_uses_two_space_indent():
    text = pretty_text(SAMPLE)
    assert text.endswith("\n")
    assert '\n  "schema_version": 1' in text
    assert json.loads(text) == SAMPLE
