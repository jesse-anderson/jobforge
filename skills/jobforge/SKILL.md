---
name: jobforge
description: Help someone apply for jobs with a resume and cover letter tailored to one job posting, built only from facts they confirmed. Use when the user wants help with a job search, a resume, or a cover letter and wants nothing invented. Runs Jobforge, a free local command-line tool, so it needs an agent that can run commands.
---

# Jobforge

Jobforge turns a person's real work history into a resume and cover letter
for one job posting, as `.docx` files built for applicant tracking systems.
You do the writing: drafting facts from old resumes, asking questions, and
choosing and wording what goes in. Jobforge does the rest, and refuses to
write a document that states something the user did not confirm.

**The one rule: Never state a fact the user has not confirmed.**
`jobforge check` enforces it, so an invented figure, employer, or tool only
costs a round trip.

What it is not: Jobforge calls no model API (D-12); the agent you are is
the only model involved. Everything stays in one folder on the user's
computer, and their data never leaves it.

## 1. Is it installed?

```
jobforge --version
```

If that prints a version, go to step 3.

## 2. Install it

Ask the user before installing anything: it changes their computer, and on
Linux `sudo` needs their password, so they may want to run those lines
themselves. Jobforge needs Python 3.11 or newer.

On Linux, with pipx (Ubuntu and Debian block `pip` for the system Python):

```
sudo apt install pipx
pipx ensurepath
pipx install jobforge
```

`pipx ensurepath` takes effect in a new terminal. Until then, run
`~/.local/bin/jobforge`.

On Windows:

```
pip install jobforge
```

If any of this fails, the README's "Set up (once)" section is the source of
truth: https://github.com/jesse-anderson/jobforge#set-up-once

## 3. Find or make the workspace

Everything about the user lives in one workspace folder. If they already
have one (a folder with a `.jobforge` file in it), use it. Otherwise ask
where they want it, and make it:

```
jobforge init ~/jobsearch
```

## 4. Hand off

Work from inside the workspace from now on:

```
cd ~/jobsearch
```

Then read the workspace's `CLAUDE.md`, or `AGENTS.md` if your tool reads
that file instead. `jobforge init` generated it for this version of
Jobforge, from `src/jobforge/agent/instructions.md`. It is the full set of
instructions: setting the user up, confirming facts, and applying to a job.
Follow it over anything in this skill. If the user upgrades Jobforge later,
`jobforge init --refresh` updates it.
