# CLAUDE.md: sumseal

Zero-dependency Python library and CLI that records a manifest (SHA-256, size, times, optional source) of a folder of files and verifies it later. `SPEC.md` is the source of truth. Owner: CyberDredge (GitHub). Repo location: `C:\evidex` (Windows). The repo is public (since 2026-11-21) and released on PyPI as `sumseal`.

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
- **CI.** The repo is public, so standard GitHub-hosted runners are free. CI runs Python 3.11 to 3.13 on Linux and Windows. No macOS runners, larger runners or scheduled workflows without the owner's approval. Always run the full `pytest` locally before asking to push. Do not open PRs; the owner pushes straight to `main` after approving. Dependabot may open PRs for GitHub Actions updates; the owner decides on each.
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
- `README.md`, `SECURITY.md`, `CHANGELOG.md`, `.github/workflows/ci.yml`, `.github/dependabot.yml` (GitHub Actions only).

## Session routine
- Start: read this file and SPEC.md, then run `git status` and `pytest`, and say where the build stands.
- End: update "Build status" below and add a dated entry to the SPEC.md decisions log.
- End every session with a short recap in this exact shape: **Done / Not done / Needs approval / Next step.** Keep it plain, not clinical. Include exact paths and the commit hash if one was made.

## Build status (update at the end of each session)
- History was rewritten on 2026-11-21 to remove personal details from every commit, and the rewritten history is now on GitHub (`main` up to date with `origin/main`). No force push is needed or allowed; see Branch protection.
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
- Public-flip prep, 2026-11-21 (prepared, not committed): CI widened to Python 3.11 to 3.13 on Linux and Windows with warnings as errors and a `pull_request` trigger (for Dependabot); Actions pinned to commit SHAs (checkout v7.0.1, setup-python v7.1.0); `.github/dependabot.yml` re-added (Actions only, monthly, at most 2 PRs); version 0.1.0 in `pyproject.toml` and `__init__.py`; CHANGELOG `[0.1.0] - 2026-11-21` (move the date if the release happens later); README install now `pip install sumseal`; SECURITY.md supports the latest release. Full history scanned: no personal details, only noreply author addresses. Windows 192 passed, 20 skipped (symlink tests skip in this session); Linux 210 passed, 2 skipped (warnings as errors). Wheel builds to `dist/`.
- Released 2026-11-21: prep committed (1f53ffa) and pushed; repo made public; private vulnerability reporting on; the CI workflow (disabled by hand while private) re-enabled and run on 1f53ffa: all 6 jobs green (Linux and Windows, Python 3.11 to 3.13); `main` ruleset still active; tag `v0.1.0` pushed. USPTO search for "sumseal" and "sum seal" found no marks (quick check, not legal advice).
- PyPI: owner uploaded 0.1.0 on 2026-11-21. A clean venv install of `sumseal==0.1.0` ran `create` and `verify` on the demo: all OK.
- 2026-11-21 follow-up: PyPI token replaced with one scoped to sumseal (owner). Launch audit: repo, CI on 65333c6, tag, PyPI files and metadata all correct. The GitHub repo description ended with leftover setup text ("Visibility: choose Private."); the owner is fixing it in the repo's About box. CLAUDE.md updated for the public repo.
- Next: optional website mention, GitHub release for `v0.1.0`, profile link. For 0.1.1: the README's relative LICENSE link is broken on PyPI; the sdist leaves out `tests/conftest.py` and `examples/demo/`, so tests run from the sdist partly fail.
