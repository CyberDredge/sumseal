# CLAUDE.md: sumseal

Zero-dependency Python library and CLI that records a manifest (SHA-256, size, times, optional source) of a folder of files and verifies it later. `SPEC.md` is the source of truth. Owner: CyberDredge (GitHub). Repo location: `C:\evidex` (Windows). The repo is private until the owner flips it public at launch.

## Rules (non-negotiable)
- **Approval first.** No commit, push, PR, merge, tag, deploy, delete, reset, rebase, branch deletion, file move, or anything touching secrets without the owner's explicit approval in that session. Say what is ready and let the owner decide.
  - Deleting counts even for scratch files or folders you created yourself: ask first, or leave them and tell the owner.
- **Write as if public.** No real case data, real people, real URLs, tokens, API keys, `.env` content, personal details, or email addresses anywhere (code, tests, docs, commit text). Examples use only `example.com`, `example.net`, `example.org` and made-up file names. One exception: the only real URLs allowed are the project's own Homepage and Issues links in `pyproject.toml` `[project.urls]`, and `tests/test_hygiene.py` enforces that.
- Never mention any employer, client, contract, or employment-related detail anywhere in this repo (code, docs, LICENSE, commit messages).
- **No network access** in code or tests. No DNS lookups.
- **Zero runtime dependencies** (standard library only). Dev dependency: `pytest` only.
- **Fail closed.** Never guess. Ambiguous or unreadable input is an error or an explicit result, never silently skipped.
- **Every behavior change needs a row in the SPEC.md test table and a test.**
- Write invisible, control and look-alike characters in tests and code as `\uXXXX` escapes, never raw.
- **Never claim "court-ready", "admissible", or legal authenticity** in code, docs, or messages. sumseal records integrity only.
- Stay inside `C:\evidex`. Do not touch any folder outside C:\evidex.
- Keep it small. If something is not in SPEC.md, ask before adding it.
- **CI budget.** While the repo is private, CI is one Linux job on Python 3.12 only. No Windows or macOS runners, no version matrix, no larger runners, no scheduled workflows, until the owner flips the repo public. Always run the full `pytest` locally before asking to push, because GitHub Actions minutes may be used up and CI may not run. Do not open PRs; the owner pushes straight to `main` after approving.
- **Branch protection.** A GitHub ruleset on `main` (set by the owner on 2026-11-21) blocks force pushes and deletion. It does not require pull requests or status checks. Never force-push or try to get around it. If a history rewrite is ever truly needed, ask the owner, who switches the ruleset off for that push and back on afterwards.

## Commands (PowerShell, from C:\evidex)
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```
Requires Python 3.11 or newer.

## Where things are
- `SPEC.md`: design, manifest format, CLI, required test table, build order, decisions log at the bottom.
- `src/sumseal/`: `hashing.py`, `manifest.py`, `verify.py`, `report.py`, `cli.py`, `__main__.py` (so `python -m sumseal` works).
- `tests/`: table-driven tests that follow the SPEC.md table row for row.
- `examples/demo/`: tiny fictional files used by the README example and a test.
- `README.md`, `SECURITY.md`, `CHANGELOG.md`, `.github/workflows/ci.yml`. No Dependabot until the public flip.

## Session routine
- Start: read this file and SPEC.md, then run `git status` and `pytest`, and say where the build stands.
- End: update "Build status" below and add a dated entry to the SPEC.md decisions log.
- End every session with a short recap in this exact shape: **Done / Not done / Needs approval / Next step.** Keep it plain, not clinical. Include exact paths and the commit hash if one was made.

## Build status (update at the end of each session)
- History was rewritten on 2026-11-21 to remove personal details from every commit, and the rewritten history is now on GitHub (`main` up to date with `origin/main`). No force push is needed or allowed; see Branch protection. GitHub Actions minutes are used up until 2026-12-14, so CI may not run before then.
- Step 1 (scaffold, hashing core, canonical JSON and digest): done 2026-11-21, committed locally.
- Step 2 (`create`, collision and special-file rules): done 2026-11-21, committed locally.
- Step 3 (`verify`, results and exit codes): done 2026-11-21, committed locally.
- Step 4 (`add-source`, `digest`, `report`): done 2026-11-21. Windows 127 passed, 7 skipped; Linux (WSL Ubuntu, Python 3.12) 133 passed, 1 skipped. Committed.
- Step 5 (README, SECURITY.md, CHANGELOG, LICENSE, demo, CI, CLI polish): done 2026-11-21, committed and pushed. Dependabot removed afterwards, to be added at the public flip.
- Step 6 (self-review, hygiene tests, dogfood run): done 2026-11-21. Windows 169 passed, 10 skipped; Linux 178 passed, 1 skipped (warnings as errors). Committed (a4a92ed) and pushed.
- Linux test run (from PowerShell): `wsl -d Ubuntu -e sh -c 'cd /mnt/c/evidex && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ~/.venvs/evidex-test/bin/python -m pytest -q -p no:cacheprovider'`
- Renamed from evidex to sumseal on 2026-11-21 (commit 442d2fa). GitHub repository renamed to CyberDredge/sumseal and the git remote updated. The local folder is still `C:\evidex`.
- Prior art rechecked and name checked on 2026-11-21 (see SPEC.md).
- Approved spec changes, 2026-11-21: exit 3 for internal errors, `verify --expect-digest`, `create` refuses `--out` inside the recorded folder, `[project.urls]` in `pyproject.toml`. Windows 193 passed, 10 skipped; Linux 201 passed, 2 skipped (warnings as errors). Committed locally with owner approval; not pushed.
- Closed output pipe, 2026-11-21: `BrokenPipeError` now exits 1 silently; on Windows, `verify`/`create` to a closed pipe still exit 3 (OSError errno 22, known limit, owner decision). Windows 202 passed, 10 skipped; Linux 210 passed, 2 skipped (warnings as errors). Committed locally with owner approval; not pushed.
- Next, at the public flip (owner decides when): owner flips the repo public and turns on private vulnerability reporting; widen CI to Python 3.11 to 3.13 on Linux and Windows; re-add Dependabot and pin Actions to commit SHAs; owner confirms the name on the official USPTO search. Then release 0.1.0 (version, tag, CHANGELOG date, PyPI) only with owner approval.
