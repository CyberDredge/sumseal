"""`create` rows from the SPEC.md required test table."""

import json
import os
import re
import subprocess
import sys

import pytest

from evidex import __version__
from evidex.cli import main
from evidex.manifest import find_collisions, manifest_digest

UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
SHA_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
COLLECTOR = "Example Collector"


def run(capsys, *args):
    try:
        code = main([str(a) for a in args])
    except SystemExit as exc:  # argparse usage errors
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


def make(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def manifest_path(folder):
    return folder.parent / (folder.name + ".evidex.json")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def symlink_or_skip(target, link, is_dir=False):
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create symlinks here: {exc}")


# Row: Create on a normal folder ----------------------------------------------


def test_create_normal_folder(tmp_path, capsys):
    folder = make(
        tmp_path / "case-folder",
        {
            "alpha.txt": b"abc",
            "Zeta.txt": b"zeta",
            ".hidden": b"",
            "sub/c.txt": b"c",
            "sub/deeper/d.bin": b"",
            "\u00e9t\u00e9.txt": b"summer",
            "nfd-cafe\u0301.txt": b"stored as NFC",
        },
    )
    before = sorted(os.listdir(folder))

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, "--case", "CASE-001")

    assert code == 0, err
    on_disk = manifest_path(folder)
    raw = on_disk.read_bytes()
    manifest = load(on_disk)

    # Written next to the folder, never inside it.
    assert sorted(os.listdir(folder)) == before
    # Printed digest matches the file as read back from disk.
    assert f"Manifest digest (sha256): {manifest_digest(manifest)}" in out
    assert "Recorded 7 files from case-folder" in out

    assert list(manifest) == [
        "schema_version", "tool_version", "created_utc", "collector", "case_id",
        "root_name", "hash_algorithm", "excludes", "skipped", "files",
    ]
    assert manifest["schema_version"] == 1
    assert manifest["tool_version"] == __version__
    assert manifest["collector"] == COLLECTOR
    assert manifest["case_id"] == "CASE-001"
    assert manifest["root_name"] == "case-folder"
    assert manifest["hash_algorithm"] == "sha256"
    assert manifest["excludes"] == []
    assert manifest["skipped"] == []
    assert UTC.match(manifest["created_utc"])

    # Hidden files included, POSIX relative paths, NFC, UTF-8 byte order.
    assert [f["path"] for f in manifest["files"]] == [
        ".hidden",
        "Zeta.txt",
        "alpha.txt",
        "nfd-caf\u00e9.txt",
        "sub/c.txt",
        "sub/deeper/d.bin",
        "\u00e9t\u00e9.txt",
    ]
    by_path = {f["path"]: f for f in manifest["files"]}
    assert by_path["alpha.txt"]["sha256"] == SHA_ABC
    assert by_path["alpha.txt"]["size"] == 3
    assert by_path[".hidden"]["sha256"] == SHA_EMPTY
    for entry in manifest["files"]:
        assert list(entry) == ["path", "size", "sha256", "mtime_utc", "hashed_utc"]
        assert UTC.match(entry["mtime_utc"]) and UTC.match(entry["hashed_utc"])

    # No absolute paths; pretty-printed with LF line endings.
    text = raw.decode("utf-8")
    assert str(tmp_path) not in text and tmp_path.as_posix() not in text
    assert b"\r\n" not in raw
    assert '\n  "schema_version": 1,' in text


def test_case_id_is_optional_and_out_is_honoured(tmp_path, capsys):
    folder = make(tmp_path / "f", {"a.txt": b"abc"})
    out = tmp_path / "elsewhere.json"
    code, stdout, err = run(capsys, "create", folder, "--collector", COLLECTOR, "--out", out)
    assert code == 0, err
    assert not manifest_path(folder).exists()
    assert "case_id" not in load(out)


def test_python_dash_m_works(tmp_path):
    folder = make(tmp_path / "f", {"a.txt": b"abc"})
    result = subprocess.run(
        [sys.executable, "-m", "evidex", "create", str(folder), "--collector", COLLECTOR],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "Manifest digest (sha256): " in result.stdout


# Rows: Symlink without / with --skip-special ---------------------------------


def test_symlink_without_skip_special_is_error(tmp_path, capsys):
    folder = make(tmp_path / "f", {"real.txt": b"abc"})
    symlink_or_skip(folder / "real.txt", folder / "link.txt")

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)

    assert code == 2
    assert not manifest_path(folder).exists()
    assert "link.txt (symlink)" in err
    assert "--skip-special" in err


def test_symlink_with_skip_special_is_recorded(tmp_path, capsys):
    folder = make(tmp_path / "f", {"real.txt": b"abc", "sub/inner.txt": b"x"})
    symlink_or_skip(folder / "real.txt", folder / "link.txt")
    symlink_or_skip(folder / "sub", folder / "linkdir", is_dir=True)

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")

    assert code == 0, err
    manifest = load(manifest_path(folder))
    assert manifest["skipped"] == [
        {"path": "link.txt", "kind": "symlink"},
        {"path": "linkdir", "kind": "symlink"},
    ]
    # Linked file and linked folder contents are not followed.
    assert [f["path"] for f in manifest["files"]] == ["real.txt", "sub/inner.txt"]
    assert "Skipped 2 special items" in out


# Row: Junction or other reparse point (Windows only) --------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_junction_is_treated_like_a_symlink(tmp_path, capsys):
    winapi = pytest.importorskip("_winapi")
    if not hasattr(winapi, "CreateJunction"):
        pytest.skip("CreateJunction not available")
    outside = make(tmp_path / "outside", {"not-in-folder.txt": b"x"})
    folder = make(tmp_path / "f", {"real.txt": b"abc"})
    winapi.CreateJunction(str(outside), str(folder / "j"))

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    assert code == 2
    assert not manifest_path(folder).exists()
    assert "j (reparse_point)" in err

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")
    assert code == 0, err
    manifest = load(manifest_path(folder))
    assert manifest["skipped"] == [{"path": "j", "kind": "reparse_point"}]
    assert [f["path"] for f in manifest["files"]] == ["real.txt"]


# Row: FIFO or other non-regular file (POSIX only) -----------------------------


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
def test_fifo_is_special(tmp_path, capsys):
    folder = make(tmp_path / "f", {"real.txt": b"abc"})
    os.mkfifo(folder / "pipe")

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    assert code == 2
    assert not manifest_path(folder).exists()
    assert "pipe (other)" in err

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")
    assert code == 0, err
    assert load(manifest_path(folder))["skipped"] == [{"path": "pipe", "kind": "other"}]


# Rows: Case-colliding names / NFC vs NFD names --------------------------------


@pytest.mark.parametrize(
    "names,expected",
    [
        (["Report.txt", "report.TXT", "other.txt"], [["Report.txt", "report.TXT"]]),
        (["caf\u00e9.txt", "cafe\u0301.txt"], [["cafe\u0301.txt", "caf\u00e9.txt"]]),
        (["CAFE\u0301.txt", "caf\u00e9.txt"], [["CAFE\u0301.txt", "caf\u00e9.txt"]]),
        (["a.txt", "b.txt"], []),
    ],
    ids=["case", "nfc-vs-nfd", "case-and-nfd", "no-collision"],
)
def test_collision_rule(names, expected):
    # Runs on every platform, even where the filesystem cannot hold both names.
    assert find_collisions(names) == expected


@pytest.mark.parametrize(
    "first,second",
    [("Report.txt", "report.TXT"), ("Docs/a.txt", "docs/b.txt")],
    ids=["files", "folders"],
)
def test_case_colliding_names_on_disk_are_error(tmp_path, capsys, first, second):
    (tmp_path / "CaseProbe").write_bytes(b"")
    if (tmp_path / "caseprobe").exists():
        pytest.skip("case-insensitive filesystem cannot hold both names")
    folder = make(tmp_path / "f", {first: b"1", second: b"2"})

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)

    assert code == 2
    assert not manifest_path(folder).exists()
    assert "collide" in err


def test_nfc_vs_nfd_names_on_disk_are_error(tmp_path, capsys):
    folder = make(tmp_path / "f", {"caf\u00e9.txt": b"1", "cafe\u0301.txt": b"2"})
    if len(os.listdir(folder)) != 2:
        pytest.skip("filesystem normalizes names, cannot hold both")

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)

    assert code == 2
    assert not manifest_path(folder).exists()
    # Names are shown escaped so the invisible difference is visible.
    assert "'caf\\xe9.txt'" in err and "'cafe\\u0301.txt'" in err


# Row: Empty folder -------------------------------------------------------------


@pytest.mark.parametrize(
    "files,extra",
    [({}, []), ({"sub/deeper/.keep-dir/x": None}, []), ({"a.tmp": b"x"}, ["--exclude", "*.tmp"])],
    ids=["empty", "only-empty-subfolders", "everything-excluded"],
)
def test_empty_folder_is_error(tmp_path, capsys, files, extra):
    folder = tmp_path / "f"
    folder.mkdir()
    for rel, data in files.items():
        if data is None:
            (folder / rel).mkdir(parents=True)
        else:
            (folder / rel).write_bytes(data)

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, *extra)

    assert code == 2
    assert not manifest_path(folder).exists()
    assert "no files to record" in err


# Row: --exclude -----------------------------------------------------------------


def test_exclude_leaves_files_out_and_records_globs(tmp_path, capsys):
    folder = make(
        tmp_path / "f",
        {"keep.txt": b"k", "skip.tmp": b"s", "sub/also.tmp": b"s", "cache/x.txt": b"c"},
    )
    code, out, err = run(
        capsys, "create", folder, "--collector", COLLECTOR,
        "--exclude", "*.tmp", "--exclude", "cache",
    )
    assert code == 0, err
    manifest = load(manifest_path(folder))
    assert [f["path"] for f in manifest["files"]] == ["keep.txt"]
    assert manifest["excludes"] == ["*.tmp", "cache"]
    assert "Excluded: *.tmp, cache" in out


# Row: Unreadable file during create (POSIX only) ---------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read anything")
def test_unreadable_file_during_create_is_error(tmp_path, capsys):
    folder = make(tmp_path / "f", {"ok.txt": b"abc", "locked.txt": b"secret"})
    locked = folder / "locked.txt"
    locked.chmod(0)
    try:
        code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    finally:
        locked.chmod(0o600)
    assert code == 2
    assert not manifest_path(folder).exists()
    assert "locked.txt: cannot read" in err


# Row: File name not valid UTF-8 (Linux only) ------------------------------------


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux only")
def test_undecodable_file_name_is_error(tmp_path, capsys):
    folder = make(tmp_path / "f", {"ok.txt": b"abc"})
    try:
        fd = os.open(os.fsencode(folder) + b"/bad\xff.txt", os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
    except OSError as exc:
        pytest.skip(f"filesystem rejects the name: {exc}")

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)

    assert code == 2
    assert not manifest_path(folder).exists()
    assert "not valid UTF-8" in err


# Row: Output file already exists ---------------------------------------------------


def test_existing_output_is_never_overwritten(tmp_path, capsys):
    folder = make(tmp_path / "f", {"a.txt": b"abc"})
    existing = manifest_path(folder)
    existing.write_bytes(b"earlier manifest")

    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)

    assert code == 2
    assert existing.read_bytes() == b"earlier manifest"
    assert "already exists" in err


# Row: Bad arguments ------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["bogus"],
        ["create"],
        ["create", "{folder}"],
        ["create", "{folder}", "--collector", ""],
        ["create", "{folder}", "--collector", "   "],
        ["create", "{folder}", "--collector", COLLECTOR, "--case", ""],
        ["create", "{folder}", "--collector", COLLECTOR, "--exclude", ""],
        ["create", "{folder}", "--collector", COLLECTOR, "--no-such-flag"],
        ["create", "{missing}", "--collector", COLLECTOR],
        ["create", "{file}", "--collector", COLLECTOR],
    ],
    ids=[
        "no-command", "unknown-command", "no-folder", "no-collector", "empty-collector",
        "blank-collector", "empty-case", "empty-exclude", "unknown-flag",
        "missing-folder", "file-not-folder",
    ],
)
def test_bad_arguments_exit_2(tmp_path, capsys, args):
    folder = make(tmp_path / "f", {"a.txt": b"abc"})
    places = {
        "{folder}": str(folder),
        "{missing}": str(tmp_path / "missing"),
        "{file}": str(folder / "a.txt"),
    }
    code, out, err = run(capsys, *[places.get(a, a) for a in args])
    assert code == 2
    assert not manifest_path(folder).exists()
    assert err


# Rows: self-review fixes (step 6) -------------------------------------------------


def test_exclude_that_matches_nothing_is_noted(tmp_path, capsys):
    folder = make(tmp_path / "f", {"a.txt": b"abc", "sub/b.tmp": b"x"})
    code, out, err = run(
        capsys, "create", folder, "--collector", COLLECTOR,
        "--exclude", "sub/*.tmp", "--exclude", "nothing-*.xyz", "--exclude", "sub\\*.tmp",
    )
    assert code == 0, err
    assert "note: --exclude nothing-*.xyz matched nothing" in out
    assert "note: --exclude sub\\*.tmp matched nothing (use / between folders)" in out
    assert "--exclude sub/*.tmp matched nothing" not in out
    # All globs are still recorded exactly as given.
    assert load(manifest_path(folder))["excludes"] == ["sub/*.tmp", "nothing-*.xyz", "sub\\*.tmp"]


def test_invisible_characters_in_create_errors_are_escaped(tmp_path, capsys):
    folder = make(tmp_path / "f", {"real.txt": b"abc"})
    symlink_or_skip(folder / "real.txt", folder / "link\u202etxt.exe")
    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    assert code == 2
    assert "'link\\u202etxt.exe' (symlink)" in err
    assert "\u202e" not in err


def test_failed_write_leaves_no_partial_manifest(tmp_path, capsys, monkeypatch):
    import evidex.manifest as manifest_module

    folder = make(tmp_path / "f", {"a.txt": b"abc"})

    def disk_full(fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(manifest_module.os, "fsync", disk_full)
    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR)
    assert code == 2
    assert "No space left on device" in err
    assert not manifest_path(folder).exists()
