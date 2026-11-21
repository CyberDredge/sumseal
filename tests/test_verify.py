"""`verify` rows from the SPEC.md required test table."""

import json
import os
import sys
import unicodedata

import pytest

from evidex.cli import main
from evidex.manifest import manifest_digest, pretty_text

COLLECTOR = "Example Collector"
BASE = {"a.txt": b"abc", "sub/b.txt": b"bravo", ".hidden": b""}
POSIX_NON_ROOT = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX only, and root can read anything",
)


def run(capsys, *args):
    try:
        code = main([str(a) for a in args])
    except SystemExit as exc:
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


def created(tmp_path, capsys, *extra, files=None):
    folder = make(tmp_path / "case", BASE if files is None else files)
    code, out, err = run(capsys, "create", folder, "--collector", COLLECTOR, *extra)
    assert code == 0, err
    return folder


def line(result, path, detail=""):
    text = f"{result:<10}  {path}"
    return text + (f"  ({detail})" if detail else "")


def symlink_or_skip(target, link, is_dir=False):
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create symlinks here: {exc}")


# Rows: Unchanged folder / Verify prints the manifest digest -------------------


def test_unchanged_folder_all_ok(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    code, out, err = run(capsys, "verify", folder)
    assert code == 0, err
    assert "OK 3  CHANGED 0  MISSING 0  NEW 0  UNREADABLE 0" in out
    assert "Result: everything matches the manifest." in out
    digest = manifest_digest(json.loads(manifest_path(folder).read_text(encoding="utf-8")))
    assert f"Manifest digest (sha256): {digest}" in out


# Row: One byte flipped (plus size changes) -------------------------------------


@pytest.mark.parametrize(
    "path,new_content,detail",
    [
        ("a.txt", b"abd", "content differs, same size"),
        ("a.txt", b"abcd", "size 3 -> 4 bytes"),
        (".hidden", b"x", "size 0 -> 1 bytes"),
    ],
    ids=["byte-flipped", "byte-appended", "empty-file-filled"],
)
def test_changed_content(tmp_path, capsys, path, new_content, detail):
    folder = created(tmp_path, capsys)
    (folder / path).write_bytes(new_content)
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("CHANGED", path, detail) in out
    assert "Result: problems found." in out


# Rows: File deleted / File added ------------------------------------------------


def test_file_deleted_is_missing(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    (folder / "sub" / "b.txt").unlink()
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("MISSING", "sub/b.txt") in out


def test_file_added_is_new(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    (folder / "sub" / "new.txt").write_bytes(b"new")
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("NEW", "sub/new.txt") in out


# Rows: Unreadable file / Unreadable subfolder (POSIX only) --------------------------


@POSIX_NON_ROOT
def test_unreadable_file(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    target = folder / "a.txt"
    target.chmod(0)
    try:
        code, out, err = run(capsys, "verify", folder)
    finally:
        target.chmod(0o600)
    assert code == 1
    assert "UNREADABLE  a.txt  (cannot read" in out


@POSIX_NON_ROOT
def test_unreadable_subfolder_is_not_reported_missing(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    sub = folder / "sub"
    sub.chmod(0)
    try:
        code, out, err = run(capsys, "verify", folder)
    finally:
        sub.chmod(0o700)
    assert code == 1
    assert "UNREADABLE  sub  (cannot list folder" in out
    assert line("UNREADABLE", "sub/b.txt", "inside a folder that cannot be read") in out
    assert "MISSING" not in out.replace("MISSING 0", "")


# Row: mtime-only change -----------------------------------------------------------


def test_mtime_only_change_is_a_note(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    os.utime(folder / "a.txt", (1_000_000_000, 1_000_000_000))
    code, out, err = run(capsys, "verify", folder)
    assert code == 0, err
    assert "note: a.txt: modified time changed (" in out
    assert "-> 2001-09-09T01:46:40Z), content unchanged" in out


# Rows: special items at verify ------------------------------------------------------


def test_skipped_item_unchanged_is_ok(tmp_path, capsys):
    folder = make(tmp_path / "case", BASE)
    symlink_or_skip(folder / "a.txt", folder / "link.txt")
    assert run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")[0] == 0
    code, out, err = run(capsys, "verify", folder)
    assert code == 0, err
    assert "OK 4  CHANGED 0" in out


def test_symlink_added_after_create_is_new(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    symlink_or_skip(folder / "a.txt", folder / "link.txt")
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("NEW", "link.txt", "symlink, not in the manifest") in out


def test_file_replaced_by_symlink_is_changed(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    (folder / "a.txt").unlink()
    symlink_or_skip(folder / "sub" / "b.txt", folder / "a.txt")
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("CHANGED", "a.txt", "recorded as a file, now symlink") in out


@pytest.mark.parametrize("replace_with_file", [False, True], ids=["removed", "now-a-file"])
def test_skipped_item_removed_or_replaced(tmp_path, capsys, replace_with_file):
    folder = make(tmp_path / "case", BASE)
    symlink_or_skip(folder / "a.txt", folder / "link.txt")
    assert run(capsys, "create", folder, "--collector", COLLECTOR, "--skip-special")[0] == 0
    (folder / "link.txt").unlink()
    if replace_with_file:
        (folder / "link.txt").write_bytes(b"regular now")
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    if replace_with_file:
        assert line("CHANGED", "link.txt", "recorded as symlink, now a regular file") in out
    else:
        assert line("MISSING", "link.txt") in out


# Row: --exclude on verify ----------------------------------------------------------


def test_excluded_files_are_not_new_on_verify(tmp_path, capsys):
    folder = created(tmp_path, capsys, "--exclude", "*.tmp")
    (folder / "scratch.tmp").write_bytes(b"x")
    (folder / "sub" / "more.tmp").write_bytes(b"x")
    code, out, err = run(capsys, "verify", folder)
    assert code == 0, err


# Row: Colliding names at verify -------------------------------------------------------


def test_colliding_names_at_verify_are_error(tmp_path, capsys):
    folder = created(tmp_path, capsys)
    make(folder, {"caf\u00e9.txt": b"1", "cafe\u0301.txt": b"2"})
    if sum(name.startswith("caf") for name in os.listdir(folder)) != 2:
        pytest.skip("filesystem normalizes names, cannot hold both")
    code, out, err = run(capsys, "verify", folder)
    assert code == 2
    assert "cannot be matched" in err


# Row: Names with control or invisible characters ---------------------------------------


def test_invisible_characters_are_printed_escaped(tmp_path, capsys):
    name = "report\u202etxt.exe"  # right-to-left override
    folder = created(tmp_path, capsys, files={name: b"abc"})
    (folder / name).write_bytes(b"abd")
    code, out, err = run(capsys, "verify", folder)
    assert code == 1
    assert line("CHANGED", "'report\\u202etxt.exe'", "content differs, same size") in out
    assert "\u202e" not in out


# Rows: --manifest, Invalid or missing manifest --------------------------------------------


def test_manifest_option(tmp_path, capsys):
    folder = make(tmp_path / "case", BASE)
    elsewhere = tmp_path / "kept" / "record.json"
    elsewhere.parent.mkdir()
    assert run(capsys, "create", folder, "--collector", COLLECTOR, "--out", elsewhere)[0] == 0

    code, out, err = run(capsys, "verify", folder, "--manifest", elsewhere)
    assert code == 0, err

    code, out, err = run(capsys, "verify", folder)  # default location has no manifest
    assert code == 2
    assert "manifest not found" in err


def _set(key, value):
    def mutate(manifest):
        manifest[key] = value
    return mutate


def _set_file(key, value):
    def mutate(manifest):
        manifest["files"][0][key] = value
    return mutate


def _duplicate_path(manifest):
    manifest["files"].append(dict(manifest["files"][0]))


def _bad_skipped(manifest):
    manifest["skipped"] = [{"path": "link.txt", "kind": "bogus"}]


def _drop_collector(manifest):
    del manifest["collector"]


DICT_MUTATIONS = {
    "schema-version-2": _set("schema_version", 2),
    "schema-version-bool": _set("schema_version", True),
    "hash-md5": _set("hash_algorithm", "md5"),
    "files-not-list": _set("files", {}),
    "excludes-empty-glob": _set("excludes", [""]),
    "created-not-utc": _set("created_utc", "2026-01-02 03:04:05"),
    "collector-missing": _drop_collector,
    "skipped-bad-kind": _bad_skipped,
    "size-negative": _set_file("size", -1),
    "size-bool": _set_file("size", True),
    "size-string": _set_file("size", "3"),
    "sha-uppercase": _set_file("sha256", "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD"),
    "sha-short": _set_file("sha256", "ba7816bf"),
    "mtime-missing": _set_file("mtime_utc", None),
    "path-parent": _set_file("path", "sub/../a.txt"),
    "path-absolute": _set_file("path", "/a.txt"),
    "path-nfd": _set_file("path", unicodedata.normalize("NFD", "caf\u00e9.txt")),
    "duplicate-path": _duplicate_path,
}

RAW_MUTATIONS = {
    "not-json": lambda text: b"{",
    "top-level-list": lambda text: b"[]",
    "duplicate-key": lambda text: text.replace("{", '{\n  "collector": "Other",', 1).encode(),
    "nan": lambda text: text.replace('"size": 3', '"size": NaN', 1).encode(),
    "utf8-bom": lambda text: b"\xef\xbb\xbf" + text.encode(),
    "not-utf8": lambda text: b"\xff\xfe",
}


@pytest.mark.parametrize(
    "mutation",
    list(DICT_MUTATIONS) + list(RAW_MUTATIONS),
)
def test_invalid_manifest_exit_2(tmp_path, capsys, mutation):
    folder = created(tmp_path, capsys)
    path = manifest_path(folder)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"].sort(key=lambda f: f["path"] != "a.txt")  # a.txt (size 3) first
    text = pretty_text(manifest)
    if mutation in DICT_MUTATIONS:
        DICT_MUTATIONS[mutation](manifest)
        data = json.dumps(manifest, indent=2).encode()
    else:
        data = RAW_MUTATIONS[mutation](text)
    path.write_bytes(data)

    code, out, err = run(capsys, "verify", folder)

    assert code == 2
    assert err.startswith("evidex: error: ")


# Row: Bad arguments (verify) ------------------------------------------------------------


@pytest.mark.parametrize(
    "args", [["verify"], ["verify", "{missing}"], ["verify", "{folder}", "--bogus"]],
    ids=["no-folder", "missing-folder", "unknown-flag"],
)
def test_verify_bad_arguments_exit_2(tmp_path, capsys, args):
    folder = created(tmp_path, capsys)
    places = {"{folder}": str(folder), "{missing}": str(tmp_path / "missing")}
    code, out, err = run(capsys, *[places.get(a, a) for a in args])
    assert code == 2
