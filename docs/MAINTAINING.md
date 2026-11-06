# Maintaining

How the two maintainers (Jesse Anderson, Mike Wilson) split and track work.
Maintainer-only; users never need this file.

## Where things go

| Thing | Where |
|---|---|
| A task, bug, or feature | GitHub issue on `jobforge` |
| A decision | New dated entry in `docs/DECISIONS.md` (never edit an old answer) |
| Anything naming a real person's search, pay, employer, or contacts | `jobforge-ops`, linked from the issue as "details in ops" |
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
  CI fails under 95%. Code on a D-30 critical path is held to 100%; mark its
  tests `@pytest.mark.critical`.
- Tests never touch the network. Stub the fetch (see `tests/test_intake.py`).
- A bug fix starts with a test that fails without the fix.
- New fact-check rules get a planted-violation test and a clean-passes test.
- Persona fixtures in `fixtures/personas/` are fictional, always.

## Branches and merging

- `main` is always green on Windows and Linux CI.
- Work on a branch named `<owner>/<topic>`, e.g. `mike/report-sankey`,
  `jesse/fact-check`.
- Merge by PR, even between the two of us, so the other maintainer sees it.
  Reference the issue (`Closes #12`).
- External PRs stay closed until the regression tooling exists (D-19).

## Moving code from `jobs`

Every file copied from the private `jobs` repo is ported by hand, one file per
commit, and checked against the PII denylist before it is committed (D-08,
T-PII). Never merge, cherry-pick, or subtree anything from `jobs`: its
history carries both maintainers' real applications.
