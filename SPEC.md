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

Every behavior change needs a row here and a test.

## Repo layout

```
src/evidex/{__init__,__main__,hashing,manifest,verify,report,cli}.py
tests/
examples/demo/        (tiny fictional text files)
README.md  SECURITY.md  CHANGELOG.md  LICENSE (MIT)  CLAUDE.md  SPEC.md  pyproject.toml
.github/workflows/ci.yml  .github/dependabot.yml
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
- CI budget (2026-11-21): the owner is on GitHub Pro with Actions minutes used up until the monthly reset. Run the full test suite locally before every push. CI may not run until the reset or the public flip, and that is expected.

## Open items for the owner

- Check the name on GitHub and for trademark conflicts before launch.
- Register the PyPI name only at release.

## Build decisions log

- 2026-11-21, step 1: Added the scaffold (`pyproject.toml` with setuptools build backend, no runtime deps, `pytest` as the only dev extra; `.gitignore`), `src/evidex/__init__.py` (`__version__ = "0.1.0.dev0"`), `hashing.py` (`hash_file` returns hex SHA-256 and the byte count actually read, 1 MiB chunks, OSError propagates, no skipping) and `manifest.py` (`canonical_bytes` exactly as specified, `manifest_digest`, `pretty_text` with 2-space indent). Tests cover the rows "Empty file", "File containing `abc`" and "Reformatted manifest on disk", plus chunk-boundary and exact-canonical-form checks. `cli.py`, `__main__.py`, `verify.py`, `report.py`, LICENSE and README come in their own steps. `readme` left out of `pyproject.toml` until README.md exists (step 5).
- 2026-11-21, step 1 pre-push changes (owner request): version set to `0.1.0.dev0`; build requires `setuptools>=77` (needed for the SPDX `license = "MIT"` string); `.gitattributes` added with `* text=auto eol=lf`; `canonical_bytes` now passes `allow_nan=False`, so NaN and Infinity raise `ValueError` (new test-table row and test); removed an owner open item; CLAUDE.md now says "Do not touch any folder outside C:\evidex" instead of listing other project paths.
- 2026-11-21, step 2: Added `create` in `manifest.py` (`build_manifest`, `write_manifest`, `create`, `find_collisions`), a CLI with only the `create` command so far (`cli.py`, `__main__.py`, `evidex` console script). It checks everything before hashing and reports all problems at once; no partial manifest is ever written. Collisions are checked per folder level on NFC-then-casefold keys, so `Docs/` vs `docs/` is caught too. Note: full Unicode case-folding also flags pairs like `straße` and `STRASSE`, which is the fail-closed choice. Decisions the spec left open: `skipped` entries are `{path, kind}`; exclude globs use `fnmatchcase` on the relative POSIX path and prune matching folders; times are whole seconds; Windows reparse points count as special (stops junctions from pulling in files from outside the folder); file names that are not valid UTF-8 are an error; `create` refuses to overwrite an existing manifest (opened with exclusive create). New test-table rows for each. On this Windows machine 41 tests pass and 5 skip (FIFO, unreadable file, undecodable name, and two case-collision-on-disk tests need Linux or a case-sensitive filesystem); CI on Linux will run them.
