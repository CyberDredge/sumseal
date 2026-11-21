# CLAUDE.md: evidex

Zero-dependency Python library and CLI that records a manifest (SHA-256, size, times, optional source) of a folder of files and verifies it later. `SPEC.md` is the source of truth. Owner: CyberDredge (GitHub). Repo location: `C:\evidex` (Windows). The repo is private until the owner flips it public at launch.

## Rules (non-negotiable)
- **Approval first.** No commit, push, PR, merge, tag, deploy, delete, reset, rebase, branch deletion, file move, or anything touching secrets without the owner's explicit approval in that session. Say what is ready and let the owner decide.
- **Write as if public.** No real case data, real people, real URLs, tokens, API keys, `.env` content, personal details, or email addresses anywhere (code, tests, docs, commit text). Examples use only `example.com`, `example.net`, `example.org` and made-up file names.
- Never mention any employer, client, contract, or employment-related detail anywhere in this repo (code, docs, LICENSE, commit messages).
- **No network access** in code or tests. No DNS lookups.
- **Zero runtime dependencies** (standard library only). Dev dependency: `pytest` only.
- **Fail closed.** Never guess. Ambiguous or unreadable input is an error or an explicit result, never silently skipped.
- **Every behavior change needs a row in the SPEC.md test table and a test.**
- Write invisible, control and look-alike characters in tests and code as `\uXXXX` escapes, never raw.
- **Never claim "court-ready", "admissible", or legal authenticity** in code, docs, or messages. evidex records integrity only.
- Stay inside `C:\evidex`. Do not touch any folder outside C:\evidex.
- Keep it small. If something is not in SPEC.md, ask before adding it.
- **CI budget.** While the repo is private, CI is one Linux job on Python 3.12 only. No Windows or macOS runners, no version matrix, no larger runners, no scheduled workflows, until the owner flips the repo public. Always run the full `pytest` locally before asking to push, because GitHub Actions minutes may be used up and CI may not run. Do not open PRs; the owner pushes straight to `main` after approving.

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
- `src/evidex/`: `hashing.py`, `manifest.py`, `verify.py`, `report.py`, `cli.py`, `__main__.py` (so `python -m evidex` works).
- `tests/`: table-driven tests that follow the SPEC.md table row for row.
- `examples/demo/`: tiny fictional files used by the README example and a test.
- `README.md`, `SECURITY.md`, `CHANGELOG.md`, `.github/workflows/ci.yml`, `.github/dependabot.yml`.

## Session routine
- Start: read this file and SPEC.md, then run `git status` and `pytest`, and say where the build stands.
- End: update "Build status" below and add a dated entry to the SPEC.md decisions log.
- End every session with a short recap in this exact shape: **Done / Not done / Needs approval / Next step.** Keep it plain, not clinical. Include exact paths and the commit hash if one was made.

## Build status (update at the end of each session)
- Step 1 (scaffold, hashing core, canonical JSON and digest): done 2026-11-21, tests green locally (Python 3.13, Windows), including the owner's pre-push changes. Committed and pushed to origin/main.
- Step 2 (`create`, collision and special-file rules): done 2026-11-21, 41 passed and 5 skipped locally (Windows; the skipped tests need Linux). Committed locally, not pushed.
- Step 3 (`verify`, results and exit codes): done 2026-11-21, 84 passed and 7 skipped locally (Windows; the skipped tests need Linux). Not committed yet, waiting for owner approval.
- Steps 4 to 6: not started.
- Next: owner reviews and approves the step 3 commit, then says "go" for step 4 (`add-source`, `digest`, `report`).
