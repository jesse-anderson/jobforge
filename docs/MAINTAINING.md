# Maintaining

How the two maintainers (Jesse Anderson, Mike Wilson) split and track work.
Maintainer-only; users never need this file.

## Where things go

| Thing | Where |
|---|---|
| A task, bug, or feature | GitHub issue on `jobforge` |
| A decision | New dated entry in `docs/DECISIONS.md` (never edit an old answer) |
| Anything naming a real person's search, pay, employer, or contacts | `the maintainers' private notes`, filed under the issue number; the issue never points there |
| Scraper or dashboard work | An issue on `jobs`, not here (COMPONENTS.md) |

Issues and commit history in this repo **become public at launch**. Write
them as if a stranger will read them, because one will.

## Assigning work

- **Assignee** on the issue is the owner. One owner per issue.
- **Labels**: one `area:` and, if useful, `type:`.
  - `area:engine`, `area:agent`, `area:report`, `area:docs`
  - `type:decision` for anything that needs a DECISIONS.md entry before work
    starts
- **Milestones** match SOW phases (`0.1` ... `0.9`, `1.0`) once phase
  ownership is assigned (Q-7, pending until just before the first 48-72 hour
  sprint).

## Commits are made by people (D-48)

- Only Jesse or Mike commits, in every repo in this project. An AI agent
  never runs `git commit`, or anything else that creates a commit (merge,
  rebase, cherry-pick, `gh pr merge`).
- An agent may propose a commit message. It carries **no** "Generated with",
  "Created with Claude", or `Co-Authored-By` lines.
- The maintainer reads the diff, then commits under their own name. Once PRs
  open to outsiders, maintainers also sign off (`git commit -s`, D-39).

Put the same rule in the `CLAUDE.md` and `AGENTS.md` that live in each repo,
so every agent session reads it.

## Tests

Every change ships with tests, written in the same change. No exceptions for
"small" fixes: most of the private repo's bugs were small.

- Run: `python -m pytest` (works without installing; pytest finds `src/`).
- Coverage: `python -m coverage run -m pytest && python -m coverage report`.
  CI fails under 95%. Code on a critical path (D-30, D-51; the list is in
  `pyproject.toml`) is held to 100% by `python tools/critical_coverage.py`,
  in CI and before every push; mark its tests `@pytest.mark.critical`.
- Tests never touch the network. Stub the fetch (see `tests/test_intake.py`).
- A bug fix starts with a test that fails without the fix.
- New fact-check rules get a planted-violation test and a clean-passes test.
- Persona fixtures in `fixtures/personas/` are fictional, always.
- The README's sample pages (`docs/samples/`) are John Smith's application.
  When a change alters what it renders, `test_sample_documents_are_not_stale`
  fails: run `python tools/readme_samples.py` (Word on Windows, LibreOffice
  and poppler-utils on Linux), look at the new images, and commit them with
  the change (#104).
- Before every push, run the suite with coverage and paste the pytest
  summary and coverage TOTAL into the PR. CI is Ubuntu only while the repo
  is private, so that local run is the only Windows check.

## Branches and merging

- `main` is always green on Windows and Linux CI.
- Work on a branch named `<owner>/<topic>`, e.g. `mike/report-sankey`,
  `jesse/fact-check`.
- Merge by PR, even between the two of us, so the other maintainer sees it.
  Reference the issue (`Closes #12`).
- External PRs stay closed until the regression tooling exists (D-19).

## Releasing

Releases publish from `.github/workflows/release.yml` with trusted
publishing: no token is stored anywhere. Only a pushed version tag starts
it, never a branch push or a PR (#54, #69).

1. In a PR, set `__version__` in `src/jobforge/__init__.py`, and merge it.
2. On that commit: `git tag vX.Y.Z` then `git push origin vX.Y.Z`. The tag
   must be `v` plus the version exactly; `tools/release_check.py` stops the
   run otherwise.
3. The `build` job checks the tag, runs the suite with coverage, builds the
   wheel and sdist, runs `twine check`, and installs the wheel in a clean
   venv to run `jobforge --version` and `jobforge init`. Then the `windows`
   job installs that same wheel on a fresh Windows runner and runs the
   clean-machine checklist (`tools/clean_windows.ps1`); its transcript is
   the `clean-windows-release` artifact. Nothing uploads if any of that
   fails.
4. The tag decides where it goes:

   | Tag | Goes to |
   |---|---|
   | `v0.1.0` (final) | PyPI |
   | `v0.1.0rc1`, `b1`, `a1` (pre-release) | TestPyPI, then PyPI if that succeeded |
   | anything else, e.g. `v0.1.0.dev1` | TestPyPI only |

5. Check it: in a clean environment, `pip install jobforge==X.Y.Z` on
   Windows and `pipx install jobforge==X.Y.Z` on Linux, then
   `jobforge --version`. For a TestPyPI-only build, add
   `--index-url https://test.pypi.org/simple/` (pip) or the full pipx
   command in `docs/VM_CHECKLIST.md` step 3.

A version can never be reused on PyPI or TestPyPI, even after it is
deleted, so a mistake costs a version number: bump it and tag again. Yank a
bad release on pypi.org instead of deleting it. Until a final release
exists, a plain `pip install jobforge` installs the newest pre-release.

The `pypi` and `testpypi` environments (Settings > Environments) deploy
from `v*` tags only.

## Moving code from `jobs`

Every file copied from the private `jobs` repo is ported by hand, one file per
commit, and checked against the PII denylist before it is committed (D-08,
T-PII). Never merge, cherry-pick, or subtree anything from `jobs`: its
history carries both maintainers' real applications.
