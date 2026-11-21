"""`digest` and `report` rows from the SPEC.md required test table."""

import csv
import io
import json

import pytest

from evidex.cli import main
from evidex.manifest import create, manifest_digest
from evidex.report import CSV_COLUMNS, DISCLAIMER, render_csv, render_markdown

COLLECTOR = "Example Collector"
SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def run(capsys, *args):
    try:
        code = main([str(a) for a in args])
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


def entry(path, **extra):
    base = {
        "path": path, "size": 3, "sha256": SHA_ABC,
        "mtime_utc": "2026-01-01T00:00:00Z", "hashed_utc": "2026-01-02T03:04:05Z",
    }
    base.update(extra)
    return base


def sample(files=None, skipped=None, **extra):
    manifest = {
        "schema_version": 1, "tool_version": "0.1.0.dev0",
        "created_utc": "2026-01-02T03:04:05Z", "collector": COLLECTOR,
        "root_name": "demo-case", "hash_algorithm": "sha256",
        "excludes": [], "skipped": skipped or [], "files": files or [entry("a.txt")],
    }
    manifest.update(extra)
    return manifest


@pytest.fixture
def manifest_file(tmp_path):
    folder = tmp_path / "case"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"abc")
    (folder / "\u00e9t\u00e9.txt").write_bytes(b"summer")
    out_path, _, _ = create(folder, collector=COLLECTOR, case_id="CASE-001")
    return out_path


# Row: digest -------------------------------------------------------------------------


def test_digest_prints_manifest_digest(manifest_file, capsys):
    code, out, err = run(capsys, "digest", manifest_file)
    assert code == 0, err
    expected = manifest_digest(json.loads(manifest_file.read_text(encoding="utf-8")))
    assert out == expected + "\n"

    # Reformatting the file on disk does not change what digest prints.
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_file.write_text(json.dumps(data, indent="\t", ensure_ascii=True), encoding="utf-8")
    assert run(capsys, "digest", manifest_file)[1] == expected + "\n"


@pytest.mark.parametrize("args", [["digest"], ["digest", "{missing}"]], ids=["no-file", "missing"])
def test_digest_bad_arguments_exit_2(tmp_path, capsys, args):
    places = {"{missing}": str(tmp_path / "missing.json")}
    assert run(capsys, *[places.get(a, a) for a in args])[0] == 2


# Row: report Markdown ------------------------------------------------------------------


def test_markdown_report_contents():
    manifest = sample(
        case_id="CASE-001",
        excludes=["*.tmp"],
        files=[
            entry("a.txt", source={"url": "https://example.com/p", "accessed_utc": "2026-01-01T12:00:00Z",
                                   "note": "fictional"}),
            entry("sub/b.txt"),
        ],
        skipped=[{"path": "link.txt", "kind": "symlink"}],
    )
    text = render_markdown(manifest)
    assert text.startswith("# evidex manifest report\n")
    for expected in (
        "| Folder | demo-case |",
        "| Collector | Example Collector |",
        "| Case ID | CASE-001 |",
        f"| Manifest digest (sha256) | {manifest_digest(manifest)} |",
        "| Files | 2 |",
        "| Excludes | \\*.tmp |",
        f"| a.txt | 3 | {SHA_ABC} | 2026-01-01T00:00:00Z | 2026-01-02T03:04:05Z | "
        "https://example.com/p (accessed 2026-01-01T12:00:00Z) fictional |",
        f"| sub/b.txt | 3 | {SHA_ABC} | 2026-01-01T00:00:00Z | 2026-01-02T03:04:05Z |  |",
        "| link.txt | symlink |",
        DISCLAIMER,
    ):
        assert expected in text, expected
    lowered = text.lower()
    assert "court-ready" not in lowered and "admissible" not in lowered


def test_markdown_report_escapes_special_characters():
    manifest = sample(files=[entry("a|b*c_[d]<e>`f`#g.txt"), entry("evil\u202etxt.exe")])
    text = render_markdown(manifest)
    assert "| a\\|b\\*c\\_\\[d\\]\\<e\\>\\`f\\`\\#g.txt |" in text
    assert "'evil\\\\u202etxt.exe'" in text
    assert "\u202e" not in text


def test_markdown_report_without_case_or_skipped():
    text = render_markdown(sample())
    assert "| Case ID | (none) |" in text
    assert "## Skipped special items\n\nNone." in text


# Row: report CSV ------------------------------------------------------------------------


def test_csv_report_rows_and_formula_guard():
    manifest = sample(
        files=[
            entry("=cmd.txt", source={"url": "https://example.com/p", "accessed_utc": "2026-01-01T12:00:00Z",
                                      "note": "@SUM(1,2), with comma"}),
            entry("a.txt"),
            entry("-draft.txt"),
        ]
    )
    rows = list(csv.reader(io.StringIO(render_csv(manifest))))
    assert rows[0] == list(CSV_COLUMNS)
    assert rows[1] == [
        "'=cmd.txt", "3", SHA_ABC, "2026-01-01T00:00:00Z", "2026-01-02T03:04:05Z",
        "https://example.com/p", "2026-01-01T12:00:00Z", "'@SUM(1,2), with comma",
    ]
    assert rows[2][:2] == ["a.txt", "3"] and rows[2][5:] == ["", "", ""]
    assert rows[3][0] == "'-draft.txt"
    assert len(rows) == 4


# Row: report output encoding --------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["md", "csv"])
def test_report_cli_writes_utf8(manifest_file, capsysbinary, fmt):
    try:
        code = main(["report", str(manifest_file), "--format", fmt])
    except SystemExit as exc:
        code = exc.code
    out, err = capsysbinary.readouterr()
    assert code == 0, err
    text = out.decode("utf-8")  # strict: fails if anything was not UTF-8
    assert "\u00e9t\u00e9.txt" in text
    assert ("# evidex manifest report" in text) == (fmt == "md")


def test_report_default_is_markdown(manifest_file, capsysbinary):
    assert main(["report", str(manifest_file)]) == 0
    assert capsysbinary.readouterr().out.startswith(b"# evidex manifest report")


@pytest.mark.parametrize(
    "args", [["report"], ["report", "{file}", "--format", "pdf"], ["report", "{missing}"]],
    ids=["no-file", "bad-format", "missing"],
)
def test_report_bad_arguments_exit_2(manifest_file, capsys, args):
    places = {"{file}": str(manifest_file), "{missing}": str(manifest_file.parent / "missing.json")}
    assert run(capsys, *[places.get(a, a) for a in args])[0] == 2
