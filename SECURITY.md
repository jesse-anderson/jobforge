# Security

Jobforge runs on your own machine and holds your work history, contact
details, and job applications. A bug that could expose or corrupt that data
is a security problem.

## Report privately

Use GitHub's private reporting: the repository's **Security** tab, then
**Report a vulnerability**. Do not open a public issue, and do not include
anyone's real personal data in the report.

You will get a reply within 7 days. Once a fix ships, the report is credited
to you unless you would rather stay anonymous.

## In scope

- Anything that sends a user's data off their machine. Jobforge makes no
  network calls except fetching a job posting the user asked for (D-25).
- Writing or reading outside the workspace, for example through a job
  folder name, an imported CSV, or a posting's text.
- A job posting that can steer the user's agent: text in a captured posting
  that gets the agent to run commands, edit facts, or skip `jobforge check`.
- Hidden characters or content in a generated `.docx` that the read-back
  check misses.
- A crafted file (profile, atoms, plan, CSV) that crashes Jobforge in a way
  that loses or corrupts existing data.

## Not a security issue

- **A fact-check bypass**, where a plan gets an invented fact past
  `jobforge check`. That is a bug: report it with the "Fact-check bypass"
  issue template, using fictional data.
- Problems in the user's own coding agent, or in a job board's site.

## Supported versions

Only the latest release gets fixes.
