"""`add-source` rows from the SPEC.md required test table."""

import json
import os
import unicodedata

import pytest

from evidex.cli import main
from evidex.manifest import manifest_digest, validate_manifest

COLLECTOR = "Example Collector"
URL = "https://example.com/post/42"
WHEN = "2026-01-02T03:04:05Z"


def run(capsys, *args):
    try:
        code = main([str(a) for a in args])
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


@pytest.fixture
def case(tmp_path, capsys):
    """A folder with a manifest; returns (folder, manifest path)."""
    folder = tmp_path / "case"
    (folder / "sub").mkdir(parents=True)
    (folder / "a.txt").write_bytes(b"abc")
    (folder / "sub" / "b.txt").write_bytes(b"bravo")
    (folder / "caf\u00e9.txt").write_bytes(b"coffee")
    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    assert code == 0, err
    return folder, tmp_path / "case.evidex.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def leftovers(path):
    return [n for n in os.listdir(path.parent) if n.endswith(".tmp")]


# Row: add-source adds a source -------------------------------------------------


def test_add_source_records_source(case, capsys):
    folder, manifest = case
    before = load(manifest)

    code, out, err = run(
        capsys, "add-source", manifest, "sub/b.txt", URL, "--accessed", WHEN,
        "--note", "saved by hand",
    )

    assert code == 0, err
    after = load(manifest)
    entry = next(e for e in after["files"] if e["path"] == "sub/b.txt")
    assert entry["source"] == {"url": URL, "accessed_utc": WHEN, "note": "saved by hand"}
    # Everything else is untouched, including key order.
    entry_without_source = {k: v for k, v in entry.items() if k != "source"}
    assert entry_without_source == next(e for e in before["files"] if e["path"] == "sub/b.txt")
    assert [e for e in after["files"] if e["path"] != "sub/b.txt"] == [
        e for e in before["files"] if e["path"] != "sub/b.txt"
    ]
    assert list(after) == list(before)
    assert {k: v for k, v in after.items() if k != "files"} == {
        k: v for k, v in before.items() if k != "files"
    }
    # Old and new digests printed; the new one matches the file on disk.
    assert f"Previous digest (sha256):     {manifest_digest(before)}" in out
    assert f"New manifest digest (sha256): {manifest_digest(after)}" in out
    assert manifest_digest(after) != manifest_digest(before)
    assert "Anchor the digest only after your last edit." in out
    # Still pretty-printed, LF only, no temp files left, verify still OK.
    raw = manifest.read_bytes()
    assert b"\r\n" not in raw and b'\n  "schema_version": 1,' in raw
    assert leftovers(manifest) == []
    assert run(capsys, "verify", folder)[0] == 0


def test_add_source_without_note_and_with_nfd_path(case, capsys):
    folder, manifest = case
    nfd = unicodedata.normalize("NFD", "caf\u00e9.txt")
    code, out, err = run(capsys, "add-source", manifest, nfd, URL, "--accessed", WHEN)
    assert code == 0, err
    entry = next(e for e in load(manifest)["files"] if e["path"] == "caf\u00e9.txt")
    assert entry["source"] == {"url": URL, "accessed_utc": WHEN}


# Rows: unknown path / skipped item / existing source -----------------------------


@pytest.mark.parametrize(
    "path,message",
    [
        ("missing.txt", "path is not in the manifest"),
        ("A.txt", "path is not in the manifest"),  # case matters
        ("./a.txt", "path is not in the manifest"),
        ("sub\\b.txt", "use / between folders"),
    ],
    ids=["unknown", "wrong-case", "dot-slash", "backslash"],
)
def test_add_source_on_unknown_path_exit_2(case, capsys, path, message):
    folder, manifest = case
    before = manifest.read_bytes()
    code, out, err = run(capsys, "add-source", manifest, path, URL, "--accessed", WHEN)
    assert code == 2
    assert message in err
    assert manifest.read_bytes() == before


def test_add_source_on_skipped_item_exit_2(tmp_path, capsys):
    folder = tmp_path / "case"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"abc")
    try:
        os.symlink(folder / "a.txt", folder / "link.txt")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create symlinks here: {exc}")
    assert run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")[0] == 0
    manifest = tmp_path / "case.evidex.json"
    before = manifest.read_bytes()

    code, out, err = run(capsys, "add-source", manifest, "link.txt", URL, "--accessed", WHEN)

    assert code == 2
    assert "skipped special item" in err
    assert manifest.read_bytes() == before


def test_existing_source_is_never_overwritten(case, capsys):
    folder, manifest = case
    assert run(capsys, "add-source", manifest, "a.txt", URL, "--accessed", WHEN)[0] == 0
    before = manifest.read_bytes()

    code, out, err = run(
        capsys, "add-source", manifest, "a.txt", "https://example.net/other",
        "--accessed", "2026-02-03T04:05:06Z",
    )

    assert code == 2
    assert "already has a source" in err and URL in err
    assert manifest.read_bytes() == before


# Row: bad URL, time or note ---------------------------------------------------------


@pytest.mark.parametrize(
    "url,accessed,extra",
    [
        ("", WHEN, []),
        ("example.com/page", WHEN, []),
        ("https://example.com/a b", WHEN, []),
        ("https://example.com/\u200bhidden", WHEN, []),
        (URL, "2026-01-02", []),
        (URL, "2026-01-02T03:04:05+00:00", []),
        (URL, "2026-01-02 03:04:05Z", []),
        (URL, "2026-13-02T03:04:05Z", []),
        (URL, "2026-02-30T03:04:05Z", []),
        (URL, "", []),
        (URL, WHEN, ["--note", ""]),
        (URL, WHEN, ["--note", "   "]),
    ],
    ids=[
        "empty-url", "no-scheme", "space-in-url", "zero-width-space", "date-only",
        "offset-not-z", "space-not-t", "month-13", "feb-30", "empty-time",
        "empty-note", "blank-note",
    ],
)
def test_bad_url_time_or_note_exit_2(case, capsys, url, accessed, extra):
    folder, manifest = case
    before = manifest.read_bytes()
    code, out, err = run(capsys, "add-source", manifest, "a.txt", url, "--accessed", accessed, *extra)
    assert code == 2
    assert manifest.read_bytes() == before
    assert leftovers(manifest) == []


# Row: Invalid source in a manifest ------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "https://example.com",
        {"accessed_utc": WHEN},
        {"url": URL},
        {"url": URL, "accessed_utc": "yesterday"},
        {"url": "no scheme", "accessed_utc": WHEN},
        {"url": URL, "accessed_utc": WHEN, "note": ""},
    ],
    ids=["not-object", "no-url", "no-time", "bad-time", "bad-url", "empty-note"],
)
def test_invalid_source_in_manifest_exit_2(case, capsys, source):
    folder, manifest = case
    data = load(manifest)
    data["files"][0]["source"] = source
    assert validate_manifest(data)
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert run(capsys, "verify", folder)[0] == 2
    assert run(capsys, "digest", manifest)[0] == 2


# Row: Bad arguments (add-source) ------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ["add-source"],
        ["add-source", "{manifest}", "a.txt"],
        ["add-source", "{manifest}", "a.txt", URL],
        ["add-source", "{missing}", "a.txt", URL, "--accessed", WHEN],
    ],
    ids=["nothing", "no-url", "no-accessed", "missing-manifest"],
)
def test_add_source_bad_arguments_exit_2(case, capsys, args):
    folder, manifest = case
    places = {"{manifest}": str(manifest), "{missing}": str(manifest.parent / "missing.json")}
    code, out, err = run(capsys, *[places.get(a, a) for a in args])
    assert code == 2


# Row: add-source keeps the manifest's permissions (POSIX only) ----------------------


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")
@pytest.mark.parametrize("mode", [0o644, 0o640, 0o600])
def test_add_source_keeps_file_mode(case, capsys, mode):
    folder, manifest = case
    manifest.chmod(mode)
    assert run(capsys, "add-source", manifest, "a.txt", URL, "--accessed", WHEN)[0] == 0
    assert manifest.stat().st_mode & 0o777 == mode
