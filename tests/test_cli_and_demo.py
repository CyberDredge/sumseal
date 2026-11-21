"""CLI polish and demo-folder rows from the SPEC.md required test table."""

import json
import shutil
import subprocess
import sys
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
    assert ("0 everything OK, 1 problems found or output cut short by a closed pipe, "
            "2 usage or input error, 3 internal error" in " ".join(out.split()))


# Row: Unexpected exception -----------------------------------------------------------


def test_unexpected_exception_is_internal_error_exit_3(tmp_path, capsys, monkeypatch):
    import sumseal.cli as cli

    def broken(args):
        raise RuntimeError("something broke")

    monkeypatch.setitem(cli.COMMANDS, "digest", broken)
    code, out, err = run(capsys, "digest", tmp_path / "any.sumseal.json")
    assert code == 3
    assert out == ""
    assert err == "sumseal: internal error: RuntimeError: something broke\n"


def test_expected_errors_stay_exit_2(tmp_path, capsys):
    code, out, err = run(capsys, "digest", tmp_path / "missing.sumseal.json")
    assert code == 2
    assert "internal error" not in err


# Row: Closed output pipe --------------------------------------------------------------


class ClosedPipe:
    """A stdout whose reader has gone away: every write raises BrokenPipeError."""

    def __init__(self):
        self.buffer = self  # `report` writes bytes to sys.stdout.buffer

    def write(self, data):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        pass


def demo_manifest(tmp_path, capsys):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo)
    code, out, err = run(capsys, "create", demo, "--collector", "Example Collector")
    assert code == 0, err
    return tmp_path / "demo.sumseal.json"


@pytest.mark.parametrize(
    "command",
    [["digest"], ["report"], ["report", "--format", "csv"]],
    ids=["digest-text", "report-md-bytes", "report-csv-bytes"],
)
def test_closed_pipe_is_exit_1_and_silent(tmp_path, capsys, monkeypatch, command):
    manifest = demo_manifest(tmp_path, capsys)
    monkeypatch.setattr("sys.stdout", ClosedPipe())
    code, out, err = run(capsys, command[0], manifest, *command[1:])
    assert code == 1
    assert err == ""
    assert "internal error" not in err


def test_closed_pipe_on_verify_is_exit_1(tmp_path, capsys, monkeypatch):
    demo = tmp_path / "demo"
    demo_manifest(tmp_path, capsys)
    monkeypatch.setattr("sys.stdout", ClosedPipe())
    code, out, err = run(capsys, "verify", demo)
    assert code == 1
    assert err == ""


def test_missing_stdout_is_not_an_internal_error(tmp_path, capsys, monkeypatch):
    # With no stdout at all (sys.stdout is None, as under pythonw), print() writes
    # nothing to the console, and the command must still run normally.
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo)
    monkeypatch.setattr("sys.stdout", None)
    code, out, err = run(capsys, "create", demo, "--collector", "Example Collector")
    assert code == 0, err
    assert "internal error" not in err
    assert err == ""
    assert (tmp_path / "demo.sumseal.json").is_file()


@pytest.mark.parametrize(
    "error",
    [RuntimeError("boom"), ConnectionResetError(104, "reset"), OSError(22, "Invalid argument")],
    ids=["runtime-error", "connection-reset", "oserror-einval"],
)
def test_other_errors_are_not_treated_as_a_closed_pipe(tmp_path, capsys, monkeypatch, error):
    import sumseal.cli as cli

    def broken(args):
        raise error

    monkeypatch.setitem(cli.COMMANDS, "digest", broken)
    code, out, err = run(capsys, "digest", tmp_path / "any.sumseal.json")
    assert code == 3
    assert err.startswith(f"sumseal: internal error: {type(error).__name__}: ")


def test_real_closed_pipe_end_to_end(tmp_path, capsys):
    # A real reader that stops after one line, like `sumseal report X | head -1`.
    folder = tmp_path / "many"
    folder.mkdir()
    for i in range(2000):  # report is far bigger than any pipe buffer
        (folder / f"file-{i:04d}.txt").write_bytes(b"x")
    code, out, err = run(capsys, "create", folder, "--collector", "Example Collector")
    assert code == 0, err

    child = subprocess.Popen(
        [sys.executable, "-m", "sumseal", "report", str(tmp_path / "many.sumseal.json")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert child.stdout.readline() == b"# sumseal manifest report" + b"\n"
    child.stdout.close()
    stderr = child.stderr.read()
    child.stderr.close()
    assert child.wait(timeout=60) == 1
    assert stderr == b""


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
