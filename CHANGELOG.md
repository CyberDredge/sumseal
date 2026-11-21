# Changelog

All notable changes to evidex are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

- `evidex create`: records a folder's files (path, size, SHA-256, modified time, time hashed) in a JSON manifest next to the folder and prints the manifest digest. Stops on symlinks and special files unless `--skip-special` is given, on name collisions after case-folding or Unicode normalization, on unreadable files, on non-UTF-8 names and on empty folders. Supports recorded `--exclude` globs. Never overwrites an existing manifest.
- `evidex verify`: reports OK, CHANGED, MISSING, NEW and UNREADABLE per file with exit codes 0, 1 and 2. A modified-time-only change is a note. Validates the manifest strictly and prints its digest.
- `evidex add-source`: records where a file came from (URL, access time, optional note). Never overwrites an existing source. Rewrites the manifest atomically and prints the old and new digests.
- `evidex digest`: prints the manifest digest.
- `evidex report`: Markdown or CSV report, always UTF-8.
- `evidex --version`.
- Tiny fictional demo folder in `examples/demo`.
