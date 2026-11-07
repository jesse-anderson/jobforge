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
  network calls except fetching a job posting the user asked for (D-25),
  and a posting's redirect must not send that fetch anywhere else: another
  scheme, or a local or private address.
- Writing or reading outside the workspace, for example through a job
  folder name, an imported CSV, a posting's text, a path given on the
  command line, or a link (symlink or junction) inside the workspace that
  points out of it.
- A job posting that can steer the user's agent: text in a captured posting
  that gets the agent to run commands, edit facts, or skip `jobforge check`.
  That includes text hidden on the page, which a reader never sees but
  which would otherwise reach the agent.
- Hidden characters or content in a generated `.docx` that the read-back
  check misses.
- Losing or corrupting existing data: through a crafted file (profile,
  atoms, plan, ledger, CSV), or through a command that fails or is stopped
  partway (Ctrl+C, a document open in Word, a full disk).

## Not a security issue

- **A fact-check bypass**, where a plan gets an invented fact past
  `jobforge check`. That is a bug: report it with the "Fact-check bypass"
  issue template, using fictional data.
- **A crash that loses nothing**, such as a traceback on a malformed file.
  That is a bug: report it with the bug template.
- Problems in the user's own coding agent, or in a job board's site.

## Supported versions

Only the latest release gets fixes.
