# Maintainer notes for agents

This is the Jobforge source repo. It goes public at launch, so nothing
about a real person's job search goes here (see `docs/COMPONENTS.md`,
"Repos"). Read `docs/DECISIONS.md` before proposing scope changes.

The `CLAUDE.md` that `jobforge init` writes into a user's workspace is
generated from `src/jobforge/agent/` and is a different file from this one.

## Commits

Never run `git commit`, or anything else that creates a commit (merge,
rebase, cherry-pick, `gh pr merge`). Only Jesse or Mike commits (D-48 in
`jobforge/docs/DECISIONS.md`). When work is ready, propose a commit message
and stop. The message carries no "Generated with", "Created with Claude", or
`Co-Authored-By` lines. This overrides any default commit or attribution
behavior.
