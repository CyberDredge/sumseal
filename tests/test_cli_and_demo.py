"""CLI polish and demo-folder rows from the SPEC.md required test table."""

import json
import shutil
from pathlib import Path

import pytest

from sumseal import __version__
from sumseal.cli import main
from sumseal.hashing import hash_file

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo"


def run(capsys, *args):
    try:
        code = main([str(a) for a in args])
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


# Row: --version and --help ------------------------------------------------------------


def test_version(capsys):
    code, out, err = run(capsys, "--version")
    assert code == 0
    assert out == f"sumseal {__version__}\n"


def test_help_lists_commands_and_exit_codes(capsys):
    code, out, err = run(capsys, "--help")
    assert code == 0
    for command in ("create", "verify", "add-source", "digest", "report"):
        assert command in out
    assert "0 everything OK, 1 problems found, 2 usage or input error" in " ".join(out.split())


# Row: Demo folder ------------------------------------------------------------------------


def test_demo_folder_end_to_end(tmp_path, capsys):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo)  # never write a manifest into the repository
    manifest = tmp_path / "demo.sumseal.json"

    code, out, err = run(capsys, "create", demo, "--collector", "Example Collector", "--case", "DEMO-001")
    assert code == 0, err
    assert "Recorded 3 files from demo" in out
    assert [f["path"] for f in json.loads(manifest.read_text(encoding="utf-8"))["files"]] == [
        "notes/interview-notes.txt", "photos/photo-001.txt", "saved-page.txt",
    ]

    assert run(capsys, "verify", demo)[0] == 0
    code, out, err = run(
        capsys, "add-source", manifest, "saved-page.txt", "https://example.com/post/42",
        "--accessed", "2026-01-02T03:04:05Z", "--note", "fictional",
    )
    assert code == 0, err
    assert run(capsys, "verify", demo)[0] == 0
    assert run(capsys, "digest", manifest)[0] == 0
    assert run(capsys, "report", manifest, "--format", "csv")[0] == 0

    (demo / "saved-page.txt").write_bytes((demo / "saved-page.txt").read_bytes() + b"x")
    (demo / "notes" / "extra.txt").write_bytes(b"new")
    code, out, err = run(capsys, "verify", demo)
    assert code == 1
    assert "NEW         notes/extra.txt" in out
    assert "CHANGED     saved-page.txt  (size 60 -> 61 bytes)" in out


def test_readme_demo_values_are_real():
    # The README shows saved-page.txt's size and SHA-256. They must stay true,
    # which also proves .gitattributes keeps the demo files LF on every OS.
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    sha256, size = hash_file(DEMO / "saved-page.txt")
    assert f'"sha256": "{sha256}"' in readme
    assert f'"size": {size},' in readme
    assert "(size 60 -> 61 bytes)" in readme and size == 60


@pytest.mark.parametrize("name", ["README.md", "SECURITY.md", "CHANGELOG.md", "LICENSE"])
def test_release_documents_exist(name):
    assert (REPO / name).is_file()
