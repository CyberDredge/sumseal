# sumseal

Record exactly which files you collected and what state they were in, then check later that nothing changed. Zero dependencies, deterministic output, plain-language results.

> **What sumseal is and is not.** sumseal records and checks file integrity. It does not prove who created a file or that its content is genuine, and it is not legal advice. Whether a manifest is accepted as evidence is decided by courts and counsel, not by this tool.

sumseal writes a small JSON manifest of a folder: every file's path, size, SHA-256, modified time and the time it was hashed, plus where a file came from if you record it. Later, `sumseal verify` tells you, file by file, what is OK, CHANGED, MISSING, NEW or UNREADABLE.

- Standard library only. Python 3.11 or newer. Windows, macOS and Linux.
- No network access, ever. URLs you record are stored, never fetched.
- Fails closed: anything ambiguous or unreadable is an error or an explicit result, never silently skipped.

## Install

```
python -m pip install sumseal
```

Or, from a clone of this repository, `python -m pip install .`

This installs the `sumseal` command. `python -m sumseal` works too.

On Windows with Smart App Control turned on, the `sumseal` command may be blocked, because the small launcher that pip creates is not signed. Run `python -m sumseal` instead; it does the same thing.

## 60-second example

The repository has a tiny folder of fictional files in `examples/demo`.

**1. Record the folder.** The manifest is written next to the folder (here `examples/demo.sumseal.json`), never inside it.

```
$ sumseal create examples/demo --collector "Example Collector" --case DEMO-001
Recorded 3 files from demo
Manifest: examples/demo.sumseal.json
Manifest digest (sha256): 8084a7ad...046e0a
Anchor this digest somewhere outside the folder.
```

**2. Anchor the digest.** Copy the manifest digest somewhere the folder's owner cannot quietly change: an email to yourself, a paper notebook, a ticket. The digest covers the whole manifest, so if anyone edits the manifest later, its digest no longer matches what you anchored.

**3. Check the folder later.**

```
$ sumseal verify examples/demo
Manifest: examples/demo.sumseal.json
Manifest digest (sha256): 8084a7ad...046e0a
Compare this digest with the one you anchored when the manifest was made.

OK 3  CHANGED 0  MISSING 0  NEW 0  UNREADABLE 0
Result: everything matches the manifest.
```

If a file was edited and another added, you would see:

```
NEW         notes/extra.txt
CHANGED     saved-page.txt  (size 60 -> 61 bytes)

OK 2  CHANGED 1  MISSING 0  NEW 1  UNREADABLE 0
Result: problems found.
```

**4. Optionally record a source, then report.**

```
$ sumseal add-source examples/demo.sumseal.json saved-page.txt https://example.com/post/42 --accessed 2026-01-02T03:04:05Z --note "fictional"
$ sumseal digest examples/demo.sumseal.json
$ sumseal report examples/demo.sumseal.json --format md
```

`add-source` changes the manifest, so it prints a new digest. Anchor the digest only after your last edit.

## Commands

```
sumseal create <folder> --collector NAME [--case ID] [--exclude GLOB]... [--skip-special] [--out FILE]
sumseal verify <folder> [--manifest FILE] [--expect-digest HEX]
sumseal add-source <manifest> <relative-path> <url> --accessed TIME [--note TEXT]
sumseal digest <manifest>
sumseal report <manifest> [--format md|csv]
sumseal --version
```

- `create` refuses to overwrite an existing manifest, and refuses an `--out` path inside the folder being recorded (nothing is written). `--exclude` globs are matched case-sensitively against each relative path (`*` also matches `/`), a matching folder is left out whole, and the globs are recorded in the manifest so `verify` applies them again.
- `verify --expect-digest HEX` compares the manifest digest with the one you anchored (64 lowercase hex characters). A different digest prints a `MISMATCH` line and exits 1; a match is confirmed in the output.
- `add-source` needs the path exactly as it appears in the manifest (use `/` between folders) and a UTC time written like `2026-01-02T03:04:05Z`. It never overwrites a source that is already there.
- `report` writes UTF-8 to standard output. In CSV, cells that start with `=`, `+`, `-` or `@` get a leading `'` so spreadsheets do not run them as formulas.

### Verify results

| Result | Meaning |
|---|---|
| OK | Present, same size, same hash |
| CHANGED | Present, size or hash differs (or a file became a link, or the reverse) |
| MISSING | In the manifest, not in the folder |
| NEW | In the folder, not in the manifest |
| UNREADABLE | Cannot be read. Counts as a problem |

A changed modified time alone is printed as a note, not a failure, because copying files changes it.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Everything OK |
| 1 | Problems found, or output cut short because the command reading it exited early (for example when `sumseal report` is piped to `head`). Nothing is printed in that case |
| 2 | Usage or input error (including an invalid manifest) |
| 3 | Internal error: a bug in sumseal. The message starts with `sumseal: internal error:`; please report it |

On Windows, piping `verify` or `create` to a command that exits early can show an internal-error message and exit 3.

## Fail-closed rules

- Symlinks, junctions and other special files stop `create` with a list, unless you pass `--skip-special`. Skipped items are then recorded in the manifest. Links are never followed.
- An unreadable file, an empty folder, or names that collide after ignoring case or Unicode normalization (for example the same accented name stored in two different Unicode forms) stop `create`. No manifest is written.
- Hidden files are included. Nothing is ignored unless you exclude it, and exclusions are recorded.
- `verify` validates the manifest strictly before comparing anything, and only opens files it finds by walking the folder, so a tampered manifest cannot make it read anything outside the folder.
- File names with control or invisible characters are printed escaped, so they cannot disguise themselves in the output.

## Manifest format

JSON, `schema_version` 1, pretty-printed with 2-space indentation. A fictional example:

```json
{
  "schema_version": 1,
  "tool_version": "0.1.0",
  "created_utc": "2026-01-02T03:04:05Z",
  "collector": "Example Collector",
  "case_id": "DEMO-001",
  "root_name": "demo",
  "hash_algorithm": "sha256",
  "excludes": [],
  "skipped": [],
  "files": [
    {
      "path": "saved-page.txt",
      "size": 60,
      "sha256": "8aae1eee4992ad3b220ce4c4dc8efe5728acbc85ac68bce4f3cd396e36bda368",
      "mtime_utc": "2026-01-01T00:00:00Z",
      "hashed_utc": "2026-01-02T03:04:05Z",
      "source": {
        "url": "https://example.com/post/42",
        "accessed_utc": "2026-01-02T03:04:05Z",
        "note": "fictional"
      }
    }
  ]
}
```

- `root_name` is the folder name only. Absolute paths never appear.
- `case_id` and `source` are optional. `note` inside `source` is optional.
- `files` are sorted by `path` in UTF-8 byte order. Paths are relative, use `/`, and are NFC-normalized.
- `skipped` entries are `{"path", "kind"}`, where `kind` is `symlink`, `reparse_point` or `other`.
- All times are UTC, whole seconds, ending in `Z`.
- **Manifest digest** = SHA-256 of `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` encoded as UTF-8. Reformatting the file never changes the digest.

## Development

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell; on macOS or Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

The only development dependency is `pytest`. Tests never use the network.

## License

MIT. See [LICENSE](LICENSE).
