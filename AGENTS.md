# Maintainer notes for agents

This is the Jobforge source repo. It goes public at launch, so nothing
about a real person's job search goes here (see `docs/COMPONENTS.md`,
"Repos"). Read `docs/DECISIONS.md` before proposing scope changes.

The `CLAUDE.md` that `jobforge init` writes into a user's workspace is
generated from `src/jobforge/agent/` and is a different file from this one.

## Tests

Every change ships with tests, written in the same change. No exceptions for
"small" fixes: most of the private repo's bugs were small.

- Run: `python -m pytest` (works without installing; pytest finds `src/`).
- Coverage: `python -m coverage run -m pytest && python -m coverage report`.
  CI fails under 95%. Code on a critical path (D-30, D-51; listed in
  `pyproject.toml`) is held to 100% by `python tools/critical_coverage.py`;
  mark its tests `@pytest.mark.critical`.
- Tests never touch the network. Stub the fetch (see `tests/test_intake.py`).
- A bug fix starts with a test that fails without the fix.
- New fact-check rules get a planted-violation test and a clean-passes test.
- Persona fixtures in `fixtures/personas/` are fictional, always.

## Before every push

Run the whole suite with coverage before pushing a branch or opening a PR,
and paste the result into the PR description:

```
python -m coverage run -m pytest -q
python -m coverage report --fail-under=95
python tools/critical_coverage.py
```

Paste the pytest summary line (passed, skipped, failed) and the coverage
TOTAL line. Do not push a branch with a failing test, coverage under 95%, or
a critical-path file under 100% (the list is in `pyproject.toml`).
CI runs Ubuntu only while the repo is private, so this local run is the only
Windows check a change gets.

## Commits

Never run `git commit`, or anything else that creates a commit (merge,
rebase, cherry-pick, `gh pr merge`). Only Jesse or Mike commits (D-48 in
`jobforge/docs/DECISIONS.md`). When work is ready, propose a commit message
and stop. The message carries no "Generated with", "Created with Claude", or
`Co-Authored-By` lines. This overrides any default commit or attribution
behavior.
