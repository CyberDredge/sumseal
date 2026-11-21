# Changelog

All notable changes to sumseal are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

## [0.1.0] - 2026-11-21

First public release.

### Changed

- A closed output pipe (for example `sumseal report X | head`) now exits 1 quietly instead of reporting an internal error. On Windows, `verify` and `create` piped to a command that exits early can still show an internal error and exit 3.
- `create` stops with an error, and writes nothing, if `--out` points inside the folder being recorded.
- Unexpected errors now print `sumseal: internal error: <type>: <message>` and exit with code 3 instead of showing a traceback.
- Renamed the project from evidex to sumseal before the first release. The command is `sumseal` and manifests are named `<folder-name>.sumseal.json`.

### Added

- `sumseal create`: records a folder's files (path, size, SHA-256, modified time, time hashed) in a JSON manifest next to the folder and prints the manifest digest. Stops on symlinks and special files unless `--skip-special` is given, on name collisions after case-folding or Unicode normalization, on unreadable files, on non-UTF-8 names and on empty folders. Supports recorded `--exclude` globs and notes any glob that matched nothing. Never overwrites an existing manifest, and never leaves a partial one behind if writing fails.
- `sumseal verify`: reports OK, CHANGED, MISSING, NEW and UNREADABLE per file with exit codes 0, 1 and 2. A modified-time-only change is a note. Validates the manifest strictly and prints its digest.
- `sumseal add-source`: records where a file came from (URL, access time, optional note). Never overwrites an existing source. Rewrites the manifest atomically, keeping its file permissions, and prints the old and new digests.
- `sumseal digest`: prints the manifest digest.
- `sumseal report`: Markdown or CSV report, always UTF-8.
- `sumseal --version`.
- `sumseal verify --expect-digest HEX`: compares the manifest digest with the anchored one; a mismatch prints `MISMATCH` and exits 1.
- Project links (homepage and issues) in the package metadata.
- Tiny fictional demo folder in `examples/demo`.
