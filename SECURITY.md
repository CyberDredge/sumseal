# Security policy

## Supported versions

Only the latest release of sumseal is supported. Fixes are made on `main` and shipped in the next release.

## Reporting a vulnerability

Please report security problems privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for a security problem.

Include what you ran, what you expected, what happened, and the sumseal version (`sumseal --version`). Use made-up file names and data in any example.

## What sumseal protects against

- Accidental or unnoticed changes to files after they were recorded: edits, deletions, additions, files turned into links.
- Changes to the manifest itself, **if** you anchored the manifest digest somewhere outside the folder. Compare the digest `verify` prints with the one you anchored.

## What sumseal does not protect against

- Someone who can change both the folder and the manifest, when you have not anchored the digest elsewhere. They can simply make a new manifest.
- Anything about who created a file or whether its content is genuine. sumseal records integrity only.
- Changes that happened before the manifest was created.
- Someone swapping files in the folder while sumseal is running (for example replacing a file with a link between the folder scan and the hash). Record and verify folders that are not being changed at the same time.
- Weaknesses in SHA-256 itself (none practical are known today).

## Design choices that matter for security

- No network access and no DNS lookups, in code or tests. Recorded URLs are never fetched.
- Standard library only, no runtime dependencies.
- Links and Windows reparse points are never followed. `create` stops on them unless told to record and skip them.
- `verify` only opens files it found by walking the folder. Paths in the manifest are only used to look those files up, so a tampered manifest cannot make it read outside the folder.
- Manifests are loaded strictly (duplicate keys, NaN, bad types and unsafe paths are errors) and rewritten atomically.
- File names with control or invisible characters are printed escaped. CSV reports guard against spreadsheet formula injection.
