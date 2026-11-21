# evidex: spec (DRAFT v0.1)

Status: approved picks recorded 2026-11-21. Source of truth for the build. Update the "Build decisions log" at the bottom as you go.

## One line

Record exactly which files you collected and what state they were in, then prove later that nothing changed. Zero dependencies, deterministic output, plain-language results.

## Positioning (prior art checked 2026-11-21, quick search only)

- Capture tools exist: Bellingcat's Auto Archiver (archives URLs), Forensic OSINT and Hunchly (commercial page capture).
- Validators exist for a single tool's own captures (for example CaseCapture's validation page).
- evidex does neither. It is a small integrity manifest for files you already have, from any source.
- Recheck prior art once more before the public launch. This was a quick search, not a survey.

## Goals

1. `create` a manifest of a folder: path, size, SHA-256, file modified time, time hashed.
2. `verify` later and say clearly what is OK, CHANGED, MISSING, NEW, or UNREADABLE.
3. Record where a file came from (`add-source`).
4. Print a manifest digest the owner can anchor somewhere outside the folder (email to self, notebook).
5. Produce a readable report (Markdown or CSV).
6. Standard library only. Python 3.11 or newer. Windows, macOS and Linux.

## Non-goals (v1)

- Capturing or archiving web pages.
- Key signing or any cryptographic identity.
- RFC 3161 trusted timestamps (planned for v0.2, would shell out to `openssl`).
- GUI, cloud, accounts, telemetry, encryption.
- Any claim about legal authenticity or admissibility.
- Any shared code or integration with other projects.

## Manifest format (JSON, `schema_version` 1)

Fields: `schema_version`, `tool_version`, `created_utc`, `collector`, `case_id` (optional), `root_name` (folder name only, never an absolute path), `hash_algorithm` (`"sha256"`), `excludes` (the globs used, may be empty), `skipped` (special files recorded, may be empty), `files`.

Each entry in `files`: `path` (POSIX style, relative, NFC-normalized), `size`, `sha256` (lowercase hex), `mtime_utc`, `hashed_utc`, and optionally `source` (`url`, `accessed_utc`, `note`).

- `files` sorted by `path` (UTF-8 byte order).
- Each entry in `skipped`: `path` and `kind` (`symlink`, `reparse_point` or `other`), sorted by `path` (UTF-8 byte order).
- `excludes` lists the globs exactly as given. Each glob is matched case-sensitively (`fnmatch.fnmatchcase`) against the relative POSIX path of every file and folder; `*` also matches `/`. A matching folder is left out whole.
- All times are UTC, ISO 8601, whole seconds, ending in `Z`.
- **Manifest digest** = SHA-256 of the canonical form: `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` encoded as UTF-8. NaN and Infinity are rejected with an error, never written. Reformatting the file on disk never changes the digest.
- The file on disk is pretty-printed (2-space indent) for humans.

## CLI

```
evidex create <folder> --collector NAME [--case ID] [--exclude GLOB]... [--skip-special] [--out FILE]
evidex verify <folder> [--manifest FILE]
evidex add-source <manifest> <relative-path> <url> --accessed TIME [--note TEXT]
evidex digest <manifest>
evidex report <manifest> [--format md|csv]
```

- `create` writes the manifest next to the folder by default (`<folder-name>.evidex.json` in the parent), so the manifest is never a NEW file inside the folder it describes. `--out` overrides. It prints the manifest digest.
- `add-source` refuses a path that is not in the manifest. It rewrites the manifest and prints the new digest. Anchor the digest only after your last edit.
  - The path must match a recorded file exactly (case-sensitive, `/` between folders; NFD input is normalized to NFC). Skipped special items cannot get a source.
  - An existing source is never overwritten (exit 2, manifest untouched).
  - The URL must have a scheme (such as `https:`) and no spaces, control or invisible characters. It is never fetched.
  - `--accessed` must be a real UTC time written exactly like `2026-01-02T03:04:05Z`. Other forms and offsets are refused, never converted.
  - The rewrite is atomic (temporary file in the same folder, then replace). The previous and new digests are both printed.
- `digest` prints only the digest (one line), so it can be scripted.
- `report` writes UTF-8 to standard output, whatever the console or pipe encoding. Markdown has every manifest field, the digest, files with sources, skipped items and the disclaimer, with Markdown special characters escaped and unprintable names escaped. CSV has one row per file (`path,size,sha256,mtime_utc,hashed_utc,source_url,source_accessed_utc,source_note`). Cells starting with `=`, `+`, `-`, `@`, tab or carriage return get a leading `'` so spreadsheets do not run them as formulas.
- Exit codes: `0` everything OK, `1` problems found, `2` usage or input error.

## Verify results

| Result | Meaning |
|---|---|
| OK | Present, same size, same hash |
| CHANGED | Present, size or hash differs |
| MISSING | In the manifest, not in the folder |
| NEW | In the folder, not in the manifest |
| UNREADABLE | Cannot be read. Counts as a problem |

A changed modified time alone is a printed note, not a failure (copying files changes it).

- `verify` prints the manifest digest so it can be compared with the anchored one.
- The manifest's `excludes` apply again, so excluded files are never NEW.
- Items in `skipped` are checked by kind only (never hashed): same kind is OK, a different kind or a regular file is CHANGED, gone is MISSING. A recorded file that is now a symlink or special item is CHANGED. A new symlink or special item is NEW.
- A folder that cannot be listed is UNREADABLE, and every recorded path inside it is UNREADABLE, not MISSING.
- Only paths found by walking the folder are opened. Manifest paths are lookup keys, so a tampered manifest cannot make `verify` read outside the folder.
- Names with control, invisible or format characters are printed escaped (for example `'report\u202etxt.exe'`).
- The manifest is validated strictly before anything is compared. Invalid JSON, a UTF-8 BOM, duplicate keys, NaN or Infinity, wrong `schema_version` or `hash_algorithm`, bad field types, non-NFC, absolute or `..` paths, and duplicate paths are all errors (exit 2).
- Names on disk that collide after case-folding or NFC/NFD, or that are not valid UTF-8, make `verify` stop with exit 2.

## Fail closed (never guess, never skip silently)

- Symlinks and non-regular files make `create` stop with a list, unless `--skip-special` is given. Skipped items are then recorded in `skipped`. On Windows, every reparse point (junctions, mount points, cloud placeholder files) counts as special. Links are never followed.
- Unreadable file: `create` stops, writes no manifest.
- File names that are not valid UTF-8: error.
- `create` never overwrites an existing manifest file.
- Paths that collide after case-folding or NFC/NFD normalization: error.
- Empty folder: error.
- No implicit ignores. Hidden files are included. Exclusions are explicit and recorded in the manifest.
- Files are hashed in 1 MiB chunks. Absolute paths never appear in the manifest.
- No network access and no DNS lookups, in code or tests.

## Required test table

| Case | Expected |
|---|---|
| Unchanged folder | all OK, exit 0 |
| One byte flipped | CHANGED, exit 1 |
| File deleted | MISSING, exit 1 |
| File added | NEW, exit 1 |
| Unreadable file (POSIX only, skipped on Windows) | UNREADABLE, exit 1 |
| Empty file | sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| File containing `abc` | sha256 `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |
| Symlink without `--skip-special` | error, no manifest |
| Symlink with `--skip-special` | recorded in `skipped` |
| Case-colliding names | error |
| NFC vs NFD names | error |
| Empty folder | error |
| Reformatted manifest on disk | same digest |
| NaN or Infinity in manifest | error, no canonical form or digest |
| `add-source` on unknown path | exit 2 |
| `--exclude` | files left out and the glob recorded |
| mtime-only change | note printed, exit 0 |
| Bad arguments | exit 2 |
| Create on a normal folder | manifest next to the folder; all files (hidden included) with relative NFC POSIX paths in UTF-8 byte order; digest printed; exit 0 |
| Junction or other reparse point (Windows only) | treated like a symlink |
| FIFO or other non-regular file (POSIX only) | error without `--skip-special`, recorded in `skipped` with it |
| Unreadable file during `create` (POSIX only, skipped on Windows) | error, no manifest |
| File name not valid UTF-8 (Linux only) | error, no manifest |
| Output file already exists | error, existing file untouched |
| Verify prints the manifest digest | digest equals the manifest's digest |
| Size change, or empty file filled | CHANGED, exit 1 |
| Unreadable subfolder at verify (POSIX only) | folder and its recorded files UNREADABLE, none MISSING, exit 1 |
| Skipped item unchanged | OK, exit 0 |
| Symlink added after `create` | NEW, exit 1 |
| File replaced by a symlink | CHANGED, exit 1 |
| Skipped item removed, or replaced by a regular file | MISSING or CHANGED, exit 1 |
| `--exclude` at verify | excluded files are not NEW, exit 0 |
| Colliding names at verify | exit 2 |
| Names with control or invisible characters | printed escaped |
| `--manifest` given, or default manifest missing | uses that file; missing manifest is exit 2 |
| Invalid manifest (bad JSON, BOM, duplicate key, NaN, wrong schema or algorithm, bad types, unsafe or duplicate paths) | exit 2 |
| `add-source` adds a source | source recorded, old and new digest printed, rest of the manifest unchanged, verify still OK |
| `add-source` on a skipped item, or on an entry that already has a source | exit 2, manifest unchanged |
| `add-source` with a bad URL, bad time or empty note | exit 2, manifest unchanged, no temp file left |
| Invalid `source` in a manifest | exit 2 |
| `digest` | prints the manifest digest; same after reformatting |
| `report` Markdown | all fields, digest, files, sources, skipped items, disclaimer; special characters escaped |
| `report` CSV | one row per file; formula-like cells prefixed with `'` |
| `report` output encoding | UTF-8 bytes whatever the console or pipe |
| `--version` and `--help` | version printed; help lists the commands and exit codes; exit 0 |
| Demo folder (`examples/demo`) | create, verify, add-source, digest and report work on a copy; edits show as CHANGED and NEW |
| README demo values | the size and SHA-256 the README shows match the demo file |
| `--exclude` that matches nothing | note printed (with a hint if it contains a backslash), glob still recorded, exit 0 |
| Special or unreadable names in `create` errors | printed escaped |
| Writing a new manifest fails part way | error, no partial file left |
| `add-source` keeps the manifest's permissions (POSIX only) | file mode unchanged |
| Hygiene: no network | tests cannot resolve names or open connections; source imports no network modules |
| Hygiene: zero runtime dependencies | `pyproject.toml` has no dependencies; source imports only the standard library |
| Hygiene: wording | no "court-ready" or "admissible" in code, public docs or examples; README carries the disclaimer |
| Hygiene: URLs, email addresses, home paths | only example.com, example.net and example.org; no email addresses or user home paths |
| Hygiene: invisible characters and clean Python | `.py` files are plain ASCII and compile without warnings; no invisible or control characters in text files |

Every behavior change needs a row here and a test.

## Repo layout

```
src/evidex/{__init__,__main__,hashing,manifest,verify,report,cli}.py
tests/
examples/demo/        (tiny fictional text files)
README.md  SECURITY.md  CHANGELOG.md  LICENSE (MIT)  CLAUDE.md  SPEC.md  pyproject.toml
.github/workflows/ci.yml   (Dependabot: add at the public flip)
```

## Build order

1. Scaffold, hashing core, canonical JSON and digest.
2. `create`, including the collision and special-file rules.
3. `verify`, results and exit codes.
4. `add-source`, `digest`, `report`.
5. CLI polish, README, SECURITY.md, CHANGELOG, CI. While the repo is private, CI is ONE job on Linux with Python 3.12 only (private-repo Actions minutes are capped and Windows jobs cost double). At the public flip, widen it to Python 3.11 to 3.13 on Linux and Windows, which is free on public repos. No larger runners, ever.
6. Self-review, hygiene tests, and a dogfood run on a folder of the owner's own files (no case data).

Cut features, not days, if time runs short. Release steps (flip public, tag, PyPI) happen only with the owner's explicit approval.

## README disclaimer (required, plain language)

evidex records and checks file integrity. It does not prove who created a file or that its content is genuine, and it is not legal advice. Whether a manifest is accepted as evidence is decided by courts and counsel, not by this tool. Never describe evidex as "court-ready" or "admissible" anywhere.

## Definition of done (v1)

- All build steps done, tests green on Python 3.11 to 3.13 on Linux and Windows.
- README with install, a 60-second example, the disclaimer, and the manifest format.
- Dogfood run completed on the owner's own files with notes in the decisions log.
- Prior art rechecked and noted.

## Decisions (resolved 2026-11-21)

- Name: `evidex`. Free on PyPI as of 2026-11-21. GitHub and trademark not checked.
- RFC 3161 timestamping: v0.2, not v0.1.
- Build folder: `C:\evidex`, no OneDrive.
- Repo: private until the owner flips it public at launch.
- License: MIT. Python 3.11 or newer.
- CI budget (2026-11-21): the owner is on GitHub Pro with Actions minutes used up until the monthly reset on 2026-12-14. Run the full test suite locally before every push. CI may not run until the reset or the public flip, and that is expected.

## Open items for the owner

- Check the name on GitHub and for trademark conflicts before launch.
- Register the PyPI name only at release.

## Build decisions log

- 2026-11-21, step 1: Added the scaffold (`pyproject.toml` with setuptools build backend, no runtime deps, `pytest` as the only dev extra; `.gitignore`), `src/evidex/__init__.py` (`__version__ = "0.1.0.dev0"`), `hashing.py` (`hash_file` returns hex SHA-256 and the byte count actually read, 1 MiB chunks, OSError propagates, no skipping) and `manifest.py` (`canonical_bytes` exactly as specified, `manifest_digest`, `pretty_text` with 2-space indent). Tests cover the rows "Empty file", "File containing `abc`" and "Reformatted manifest on disk", plus chunk-boundary and exact-canonical-form checks. `cli.py`, `__main__.py`, `verify.py`, `report.py`, LICENSE and README come in their own steps. `readme` left out of `pyproject.toml` until README.md exists (step 5).
- 2026-11-21, step 1 pre-push changes (owner request): version set to `0.1.0.dev0`; build requires `setuptools>=77` (needed for the SPDX `license = "MIT"` string); `.gitattributes` added with `* text=auto eol=lf`; `canonical_bytes` now passes `allow_nan=False`, so NaN and Infinity raise `ValueError` (new test-table row and test); removed an owner open item; CLAUDE.md now says "Do not touch any folder outside C:\evidex" instead of listing other project paths.
- 2026-11-21, step 2: Added `create` in `manifest.py` (`build_manifest`, `write_manifest`, `create`, `find_collisions`), a CLI with only the `create` command so far (`cli.py`, `__main__.py`, `evidex` console script). It checks everything before hashing and reports all problems at once; no partial manifest is ever written. Collisions are checked per folder level on NFC-then-casefold keys, so `Docs/` vs `docs/` is caught too. Note: full Unicode case-folding also flags pairs like `straße` and `STRASSE`, which is the fail-closed choice. Decisions the spec left open: `skipped` entries are `{path, kind}`; exclude globs use `fnmatchcase` on the relative POSIX path and prune matching folders; times are whole seconds; Windows reparse points count as special (stops junctions from pulling in files from outside the folder); file names that are not valid UTF-8 are an error; `create` refuses to overwrite an existing manifest (opened with exclusive create). New test-table rows for each. On this Windows machine 41 tests pass and 5 skip (FIFO, unreadable file, undecodable name, and two case-collision-on-disk tests need Linux or a case-sensitive filesystem); CI on Linux will run them.
- 2026-11-21, step 3: Added `verify` (`verify.py`, CLI `verify <folder> [--manifest FILE]`) and strict `load_manifest`/`validate_manifest` in `manifest.py`. The folder walk became the shared `scan_folder`; a folder or entry that cannot be read is now a separate list, which `create` still treats as fatal and `verify` reports as UNREADABLE. `verify` prints only problem lines and notes, then a count line and a one-line result. Decisions the spec left open (each now in the Verify section and the test table): the digest is printed on verify; special items are checked by kind; an unlistable folder makes its recorded files UNREADABLE instead of MISSING; manifest paths are never joined onto the folder; unprintable names are shown escaped; a UTF-8 BOM in the manifest is an error; unknown extra keys in the manifest are allowed and ignored; `files` order is not checked when loading. On this Windows machine 84 tests pass and 7 skip (POSIX-only permission, FIFO and undecodable-name tests, and case-sensitive filesystem tests). WSL Ubuntu has Python 3.12 but no pytest, so those 7 have not been run anywhere yet.
- 2026-11-21, after step 3: Ran the full suite on Linux (WSL Ubuntu, Python 3.12, non-root user, pytest in a venv at `~/.venvs/evidex-test` outside the repo, run with `PYTHONPATH=src` so nothing is installed into the repo): 90 passed, 1 skipped (the Windows-only junction test). All seven POSIX-only tests that skip on Windows pass there. Added `.claude/` to `.gitignore`. Removed the owner's first name, the machine name and another project's name from CLAUDE.md and SPEC.md, and reworded the step 1 log entry. Recorded the Actions minutes reset date (2026-12-14).
- 2026-11-21, step 4: Added `add-source` (`add_source`, `replace_manifest`, `parse_utc`, `url_problem`, `source_problems` in `manifest.py`), `digest`, and `report.py` (Markdown and CSV); the CLI now dispatches all five commands from one table. `load_manifest` now also checks `source` objects. Decisions the spec left open (each now in the CLI section and the test table): an existing source is never overwritten (no `--replace` yet); the URL needs a scheme and no whitespace or invisible characters; `--accessed` accepts only the manifest's own UTC form, never converts; rewrites are atomic and refuse to write anything `load_manifest` would reject; `digest` prints the bare hex; `report` writes UTF-8 bytes to stdout because Windows pipes otherwise use the locale code page and would mangle non-ASCII names; the Markdown report ends with the required disclaimer; CSV cells that look like formulas get a leading `'`. Tests: Windows 127 passed, 7 skipped; Linux (WSL Ubuntu, Python 3.12) 133 passed, 1 skipped (Windows-only junction test). History note: commits were rewritten on 2026-11-21 to remove personal details, so the next push must be `git push --force-with-lease origin main`.
- 2026-11-21, step 5: Added README.md (install from a clone, 60-second example on `examples/demo`, the required disclaimer near the top, commands, results, exit codes, fail-closed rules, manifest format), SECURITY.md (private reporting through GitHub's "Report a vulnerability", what evidex does and does not protect against), CHANGELOG.md (Keep a Changelog, Unreleased), LICENSE (MIT, CyberDredge), `examples/demo/` (three fictional text files; `examples/*.evidex.json` ignored), `.github/workflows/ci.yml` (one job, ubuntu-latest, Python 3.12, push to main and manual run, read-only token, 10-minute timeout) and `.github/dependabot.yml` (GitHub Actions only, monthly, at most 2 open PRs). CLI polish: `--version` and an exit-code note in `--help`. `pyproject.toml` now has `readme`, author, keywords and classifiers (no license classifier, since setuptools 77 rejects it next to an SPDX `license`). Actions are pinned to major tags (`checkout@v4`, `setup-python@v5`), not commit SHAs. The CI job was rehearsed in a clean WSL copy with a fresh venv: install OK, 141 passed, 1 skipped. Tests: Windows 135 passed, 7 skipped; Linux 141 passed, 1 skipped.
- 2026-11-21, after step 5: Removed `.github/dependabot.yml` (owner decision). While private it only watched two Actions already pinned to major tags, and it opens pull requests, which this repo does not use. Add it back at the public flip, ideally together with pinning Actions to commit SHAs.
- 2026-11-21, step 6: Self-review fixes: names in `create` error lists are printed escaped; a failed write of a new manifest removes the partial file; an `--exclude` that matches nothing prints a note (with a `/` hint when it contains a backslash); `add-source` keeps the manifest's file permissions; the manifest path printed by `create` and `verify` is escaped. Known limit, now in SECURITY.md: files swapped while evidex runs (scan-then-hash race) are not detected. Hygiene tests added (`tests/test_hygiene.py`, plus `tests/conftest.py`, which blocks name lookups and connections in every test). The new ASCII check caught raw non-ASCII characters in five test files and a raw right-to-left override in this file, all written by tooling that turned `\uXXXX` escapes into real characters; all were converted back to escapes. Tests: Windows 169 passed, 10 skipped; Linux 178 passed, 1 skipped; both with warnings as errors.
- 2026-11-21, dogfood run (owner's own non-case files: the evidex repo folder itself, 2,095 files including `.venv` and `.git`; manifests written outside the repo): `create` and `verify` each took about 1 second, all OK. A pytest run in between changed nothing detectable (rewritten caches were byte-identical), which is correct. On a full copy, an edited file showed CHANGED with the size difference, a deleted file MISSING, an added file NEW, and two mtime-only changes as notes with exit 1 overall; times converted to UTC correctly from a UTC+8 machine. Excludes such as `.venv`, `.git` and `*/__pycache__` cut it to 29 files as expected. Reports: 2,122-line Markdown, 2,096-line CSV. No bugs found. A run on a personal folder is left to the owner.
