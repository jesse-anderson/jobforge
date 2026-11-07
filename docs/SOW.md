# Jobforge: phased statement of work

-   **Drafted:** 2026-10-17
-   **Maintainers:** Jesse Anderson, Mike Wilson
    -   Mike Wilson responsible for testing + ux + ui of deliverables
        -   Nice to have. Job mapping by date, response flag(ghosted, 1st screen, 2nd screen, 3rd screen, ..., offer), salary, etc.
        -   Metrics driven by Jesse analytical, UI / UX driven by Mike.
-   **Governing record:** `docs/DECISIONS.md`. Decision IDs (D-xx) below refer to it. Where this SOW and DECISIONS.md disagree, DECISIONS.md wins and this file gets corrected.

## Status update (2026-11-06)

-   Folder is now `jobforge`, beside a private `the maintainers' private notes` (D-44). GitHub remotes not yet created. Still no code.
-   **The MVP in `docs/MVP.md` is accepted and is the public launch** (D-47). It cuts across these phases (roughly 0.1 to 0.4, plus `confirm`, generated agent files, `check`, and ledger events). The phases below still define 1.0.
-   Vocabulary and repo boundaries: `docs/COMPONENTS.md`.

## Status (as of 2026-10-17, after audit pass 2)

-   **Where we are:** scope decided (D-01 to D-43), this SOW audited twice, git initialized with nothing committed, no code ported. The folder is still named `the old working folder`.
-   **Where we want to be:** Jobforge 1.0 on PyPI and in a public repo, on Windows and Linux. A guided setup with images. John Smith plus thirteen personas pass end to end. The no-invented-facts, employer-binding, and project-URL checks are enforced by code.
-   **How we get there:** phases 0.1 to 0.9 in section 5, gated by section 5.10. Section 6 questions are answered (D-41). Q-7 (phase ownership) is assigned just before the first 48-72 hour sprint. Next step: commit these docs, then start 0.1.

## 1. Purpose

Turn the private `the earlier tool` package into **Jobforge**: a free, source-available (PolyForm Noncommercial 1.0.0, D-39), locally run (D-25) tool that turns a person's real work history into tailored resumes, cover letters, and interview prep for a specific job posting, using the person's own terminal coding agent for the writing (D-11, D-12) and never inventing a fact (D-32).

The finish line for this SOW is **1.0**: a public repo and PyPI package that a user with basic CLI skills (D-01) can install on Windows or Linux (D-14), set up with a guided walkthrough, and use end to end. The baseline check is that **John Smith** (D-10) gets from a clean install to a submitted-quality `.docx`.

## 2. Scope

### Preconditions (met)

-   Employer IP cleared: the tool is carved out of one employer's agreement (D-17), and no code derives from another employer's work, time, or equipment (D-18).

### In scope

-   Porting, by hand, the resume-tailoring code from `the earlier tool` into a new repo (D-08), with no shared git history.
-   All current subcommands except those that exist only for the scraped corpus (D-04, D-06): `prepare`, `apply`, `cover`, `ats` (with `--form`), `applied`, `inventory`, and `search` with its new meaning (D-27). New commands: `init` (0.1), `index` (0.6), `prep` (0.7), `confirm` (0.7).
-   Per-job folders that hold the job, plan, deliverables, and intermediate one-offs such as fit scoring and notes (D-06).
-   New capabilities decided in DECISIONS.md: per-user profile (D-08), structured atoms (D-33), the fact check (D-32, D-37), variants (D-34), fact interviews (D-35, D-36), prep sheets (D-38), job index (D-29), agent-assisted discovery (D-28), document checks (D-31), optional PDF (D-23), employer binding (D-40), project URLs (D-42), and the `reword_of` schema field that the full CV will need (D-43).
-   Thirteen fictional personas used as fixtures and examples (D-09).
-   Tests to the D-15 bar, CI on Windows and Linux, a maintainer-run clean-VM release check (D-24), docs and a guided setup with images (D-01).

### Out of scope (for this SOW)

-   The scraper, dashboard, Cloudflare pipeline, `fetch`, `source`, `jobs_db`, the chunk corpus (D-04).
-   Pluggable corpus / bring-your-own-scraper (D-05), model API calls (D-12), a template system (D-26), macOS support (D-14), the full CV command (D-43): roadmap only.
-   Any hosted service, ever (D-25).
-   Migrating the private `jobs` repo onto Jobforge (D-20).
-   Accepting external PRs. That waits on the regression tooling (D-19), scheduled after 1.0 in section 7.

## 3. What the source code looks like today

Surveyed 2026-10-17. `the earlier tool/` is about 3,700 lines across 11 modules (plus an empty `__init__.py` and a 3-line `__main__.py`), plus `instructions.md` (orchestrator brief) and `prompts/tailor_v1.md` (worker system prompt, 448 lines).

| Module        | Lines | Fate                                                                                           |
|---------------------------|-----------------------:|---------------------|
| `apply.py`    |   799 | Port. Split rendering from identity; drop hardcoded header/education blocks and `RESUME_STEM`. |
| `validate.py` |   479 | Port and extend. Becomes the home of the fact check.                                           |
| `ats.py`      |   473 | Port. `CONTACT`, `EDUCATION`, `ROLE_EXTRAS` move to the profile.                               |
| `corpus.py`   |   333 | **Drop** (scraped corpus).                                                                     |
| `docx.py`     |   297 | Port as is; already dependency-free.                                                           |
| `cli.py`      |   284 | Rewrite around the new command set and workspace.                                              |
| `atoms.py`    |   257 | **Replace.** Parses LaTeX `%% ID:` blocks from `master.tex`; D-33 needs structured facts.      |
| `applied.py`  |   253 | Port. Add variant tracking (D-34) and the index (D-29).                                        |
| `extract.py`  |   241 | Port. Already serves `--from-url` / `--from-text`.                                             |
| `jobs_db.py`  |   225 | **Drop** (scraped corpus).                                                                     |
| `prepare.py`  |    92 | Port. Currently resolves jobs via `JobRow` from the DB; must take only URL or text.            |

Findings that shape the plan:

1.  **The package is not stdlib-only today.** `atoms.py` imports PyYAML. D-13 says the runtime stays stdlib-only unless we record a reason, so the atom file format had to be decided: TOML via `tomllib` (D-41, Q-1).
2.  **There are no automated tests.** D-15 sets the bar at 100% / 80%, so tests are written alongside every phase. They cannot be saved for the end.
3.  **The one-page resume check reads the LaTeX log.** With `.docx` as the guaranteed output and PDF opt-in (D-23), most users will have no LaTeX log to read. It becomes an estimate, checked against the real page count when PDF is on (D-41, Q-2).
4.  **The validator encodes one person's voice.** Banned cover-letter words and phrases, `FORBIDDEN_BRIDGE_TOOLS`, and `explicitly_not_held` are tuned to Jesse. They become profile-driven, with a sensible default set.
5.  **About 53 references to Jesse, his employers, or his paths** sit in the code and prompts. Every one goes or moves into the profile. A PII scan is part of every phase's exit tests (T-PII below).
6.  **The agent instructions assume an orchestrator spawning a worker** with paths into the private repo. They are rewritten as the canonical instruction source (D-11).
7.  **Employer binding is only a warning today.** A bullet is tied to its role by ID prefix (`exp.acme.b3` under `exp.acme`), and `validate.py` only *warns* when a plan puts it under a different role, so a true fact can be rendered under the wrong employer. Replacing `atoms.py` would drop even that prefix convention. D-40 makes the binding explicit in the atom schema and a hard failure (0.2, 0.4).
8.  **Education lives in three places** (`EDUCATION_BLOCK`, `DOCX_EDUCATION`, `ats.py` `EDUCATION`). Jobforge gives it one home: education and credential atoms. The profile does not repeat it (0.2).
9.  **Project URLs are half enforced.** A cover letter that mentions a project with a public URL but omits the URL is a hard failure today (`validate.py`). On the resume the URL prints as visible text, because the renderer pulls it from project data, but nothing checks the rendered output for it. D-42 makes it a check on every deliverable (0.4).

## 4. Versioning and gates (D-22)

-   Versions run `0.1` through `0.9`, then `1.0`. Each minor version is one phase with a fixed set of deliverables.
-   A phase is done when its **exit tests** pass on Windows and Linux in CI. Exit tests accumulate: every later phase must keep passing every earlier phase's exit tests.
-   **Major bump gate:** `1.0` requires the full qualifying suite in section 5.10. Any later major version gets its own suite, written down before the work on it starts.
-   Patch versions (`0.4.1`) are for fixes inside a phase and carry no new scope.
-   Coverage is reported in two numbers: D-30 critical paths and everything else. Critical code and functions are marked explicitly in the test config. Critical code must be at 100% in the phase that adds it. The 80% bar for the rest is a 1.0 gate (D-15), tracked but not enforced in each phase.
-   **Tests never touch the network.** `--from-url` is tested against saved HTML fixtures with the fetch stubbed out, so CI results do not depend on a job board being up.
-   **Every PyPI release, before and after 1.0, runs the VM checklist** (D-24), not just the first one. The VM exists only to give maintainers an untainted repo and machine to test in. Users run Jobforge directly on their own Windows or Linux machine and never need a VM.

Standing exit tests that apply to every phase from the one that introduces them:

| ID      | Test                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
|-----------------------------|-------------------------------------------|
| T-PII   | No string from a denylist (Jesse's and Mike's personal details, employer names, private paths) appears anywhere in the repo or built package, including fixtures and docs. **The denylist itself is PII, so it never lives in the repo:** it is a CI secret plus a local file outside the tree for each maintainer. Without it, the test skips with a visible warning, so contributor runs do not fail. The maintainer names in `LICENSE`, this SOW, and DECISIONS.md are allowlisted. |
| T-STD   | Importing the runtime package pulls in no third-party module. Dev and test dependencies are exempt.                                                                                                                                                                                                                                                                                                                                                                                    |
| T-XPLAT | Full suite green on Windows and Linux CI runners.                                                                                                                                                                                                                                                                                                                                                                                                                                      |

## 5. Phases

Sizes are relative (S, M, L) because there is no fixed date (D-21).

### 0.1 Foundation (S)

Goal: an empty but real project that installs, runs, and tests.

Deliverables - Repo renamed from `the old working folder` to `jobforge`, hosted under Jesse's personal GitHub account (D-03 update). - `pyproject.toml`, package `jobforge` under `src/`, console entry point `jobforge` that dispatches into the package (D-13). `python -m jobforge` works from a clone (D-14). `requires-python = ">=3.11"` (D-41, Q-3). - `LICENSE` with PolyForm Noncommercial 1.0.0 text (D-39). README stub that says "source-available", never "open source". - `jobforge init <dir>` creates an empty workspace: `profile/`, `intake/`, `jobs/`, plus a workspace marker file. Both install paths end up with the same layout (D-14). - CI: test-only workflow on Windows and Linux (D-15). No scraping, no scheduled runs. - Test harness, coverage tooling with critical/non-critical split. - `CONTRIBUTING.md` stating PRs are closed until the regression tooling exists, and that commits will need DCO sign-off when they open (D-19, D-39). - **VM checklist, first draft (D-24):** a maintainer-only document (not part of the user guide) listing the steps to test an untainted clone and a fresh `pip install` in a clean Windows and Linux VM. Section 4 requires it before every PyPI release, including this phase's `0.1.0`, so it cannot wait for 0.9. It grows each phase. - Reserve `jobforge` on PyPI with a minimal real `0.1.0` release (the `init` command and help). TestPyPI does not reserve the real name, and PyPI can reclaim empty placeholder packages, so the release must actually do something.

Exit tests: `init` creates the layout on both OSes; CLI help runs; T-STD, T-PII, T-XPLAT pass.

### 0.2 Data model and John Smith (M)

Goal: the profile and atom formats exist, load, and validate.

Deliverables - **Profile schema:** name, contact, file-name stem, ATS form extras (`ROLE_EXTRAS` equivalent, keyed by role atom ID), voice rules (banned words and phrases, defaulting to the current list), tools never to claim (`explicitly_not_held` equivalent), resume page limit (default 1, see D-41). Replaces every hardcoded identity block (D-08). The default voice rules keep the general AI-tell words and phrases and drop entries that are specific to one person. - **Atom schema (D-33, D-36):** an atom has an ID, a type (role, bullet, project, skill, credential, education), structured facts, a basis per fact (`measured` / `records` / `estimate`), a defense note, and optional phrasings tagged by use (resume / cover / email) and industry. - **Employer binding (D-40):** a role atom holds employer, title, location, and dates. Every bullet names its role by ID; every project names a role or `personal` / `school` / `volunteer`. Binding is a field, not an ID prefix, so renaming an ID cannot move a fact between employers. - **Project URL (D-42):** a project atom has an optional `url` (live demo, repo, or published page), an optional `writeup_url`, and an optional `url_status = "dead"`. Each URL is checked at load to be a well-formed `http(s)` URL. Many projects have neither, and that is valid. - **Profile setting:** `link_check_days`, default 7 (D-42 update). - **`reword_of` (D-43):** an atom that only restates another names the original. The loader warns when two atoms state the same facts and neither is marked. Nothing uses the field before the CV command, but atoms written from day one carry it. - **One home for education (finding 8):** education and credential atoms hold the full record, with each field marked for resume, form, or both, so the ATS form can carry what the one-page resume drops. - Loader and schema validator with clear, line-specific error messages a non-technical user can act on. - Writes never rewrite a file the user has edited by hand. New atoms are appended or go in new files, so comments survive. "Lossless" below means the loaded data, not byte-for-byte text. - Format: TOML, read with `tomllib`, written by a small in-house writer (D-41, Q-1). - **John Smith** persona: complete profile and atoms, plus one sample job description (D-10). - `jobforge inventory` ported to the new format.

Exit tests: John Smith loads cleanly; each schema violation produces the expected message, including a bullet with no role, a bullet naming an unknown role, and a project with no context; round-trip load then dump is lossless; appending an atom leaves the rest of a commented file unchanged. a malformed project URL is rejected; two unmarked atoms with the same facts raise the reword warning. John Smith has at least two employers and one personal project with a live URL, so binding and URLs are exercised from the start.

### 0.3 Port and depersonalize (L)

Goal: the existing pipeline runs on the new data model with no trace of the private repo.

Deliverables - Port `extract.py`, `prepare.py`, `docx.py`, `apply.py`, `ats.py`, `applied.py`, `validate.py` into the package, file by file, each one checked against T-PII on the way in (D-08). - `prepare --from-url` and `--from-text` (file, stdin, pasted HTML) write a job folder under the workspace. No `JobRow` from a database (D-04). The job folder is also where fit scoring and other per-job one-offs live (D-06); `fit_score` from `plan.json` feeds the ledger and search. - `apply` renders resume and cover letter `.docx` from the profile plus atoms, named from the profile stem (`John_Smith_Resume.docx`). - `cover` re-renders only the cover letter. - `ats` and `ats --form` read the profile and atoms instead of module constants. Any form field the profile cannot answer (reason for leaving, for example) prints as `UNCONFIRMED` and is never invented, as in the private repo today. - `cover_letter.md` stays the working artifact and is never a deliverable. - The current worker prompt and orchestrator brief are depersonalized and pointed at the new paths. This is an interim version; 0.7 rewrites them.

Exit tests: John Smith runs `prepare` (from text and from a saved HTML fixture) and then `apply` to produce both `.docx` files; a fixture of a board that blocks scripted requests fails with the "paste the text instead" message (D-30 item 2); `.docx` text round-trips through `extract_text`; ATS output is ASCII with CRLF, and unanswered form fields read `UNCONFIRMED`; the working markdown never appears in a deliverable; T-PII on the ported code.

### 0.4 Fact integrity (L)

Goal: the core promise is enforced by code.

Deliverables - **Fact check (D-32):** pull checkable tokens out of every deliverable line (numbers, percentages, money, dates, durations, employers, titles, credentials, tools) and require each to appear in an atom the plan cites. Wording around them is free. Profile fields (name, contact) count as a source too; everything else, education included, comes from atoms. - **Employer binding check (D-40):** a bullet renders only under its own role, as a hard failure (it is a warning today, finding 7). In prose (cover letter, and later emails and prep sheets), a sentence that names an employer may only carry tokens from atoms bound to that employer, or from the profile. A `personal`, `school`, or `volunteer` project is never placed under, or credited to, an employer. Sentence-level attribution is a heuristic, tuned on the personas in 0.8. - **Project URL check (D-42):** for every project a deliverable mentions (resume or cover letter, every variant) **whose atom has a `url`**, the URL must appear in the text read back from the rendered `.docx` with `extract_text`, as visible text and not only as a hyperlink target. A project with no `url`, or one marked `url_status = "dead"`, is not checked. `writeup_url` is the plan's choice. Ports and extends the existing cover-letter check. - **Precision and style rule (D-37):** no "\~", "about", "roughly" or similar before a figure in a deliverable; no figure more precise than its basis allows. - **Plan validation hardening (D-30 item 3):** a bad or partial `plan.json` is rejected with a clear message and produces no files. - **Variants (D-34):** a plan may describe several resume and cover letter variants; each renders into its own subfolder (`variants/2/`) with clean file names, so the file sent is always `John_Smith_Resume.docx` (D-41, Q-8). Each is checked independently. - Voice rules and never-claim lists read from the profile (finding 4). - Page-limit check (D-41, Q-2): an estimate from the template's line capacity, against the profile's page limit. Confirmation against the real page count arrives with PDF in 0.5.

Exit tests: a fixture suite of planted violations (changed number, added dollar figure, hedged figure, false precision, unknown employer, claimed not-held tool, missing atom ID, bullet moved under another employer's role, a cover-letter sentence crediting employer A with employer B's figure, personal project credited to an employer, project URL missing from the resume, project URL present only as a hyperlink behind a label, variant file name with a suffix) each fails with the right message; clean plans pass, including one with a project that has no URL and one marked dead; every variant is checked. This module is critical tier.

### 0.5 Documents and PDF (M)

Goal: what an ATS sees is exactly what we meant.

Deliverables - **Document scanner (D-31), test side:** open every generated `.docx`, read it, close it, and fail on zero-width characters, soft hyphens, misplaced non-breaking spaces, control characters, private-use glyphs, and out-of-order text. Same for PDF once it exists, plus ligature checks. - **Optional PDF (D-23):** Tectonic path ported. When PDF is not set up, `apply` prints a clear one-line note instead of silently skipping. The setup question that turns PDF on is built in 0.7; this phase adds the config flag it sets. - One template, the current look, cleaned of personal content (D-26). - **Link check (D-42 update):** a dead link is worse than none. - Results (status and date per URL) live in a rebuildable cache file in the workspace. - `apply` checks any link it is about to render whose last check is older than `link_check_days` (default 7). `jobforge links` checks all of them on demand. - 404, 410, or a name that no longer resolves blocks `apply` with a message: fix the URL or mark it `url_status = "dead"`. The link is never dropped silently. - 403, 429, timeouts, or no network print an "unverified" warning and do not block. - No background task or OS scheduler; users may schedule `jobforge     links` themselves. Tests stub the fetch and the clock.

Exit tests: scanner runs over John Smith's output for `.docx` and PDF; planted hidden characters are caught; with no Tectonic, `apply` succeeds and reports PDF as off; with Tectonic in CI, PDF compiles; the page-limit estimate agrees with the real PDF page count on every fixture; project URLs survive PDF text extraction; with stubbed fetches and clock, `apply` skips links checked within 7 days, rechecks older ones, blocks on 404, 410, and DNS failure, warns without blocking on 403, 429, timeout, and offline, and renders a `url_status = "dead"` project with no URL; `links` reports the same results on demand.

### 0.6 Job store, search, ledger (M)

Goal: many jobs stay fast.

Deliverables - **Index (D-29):** a rebuildable index updated on every write (`prepare`, `apply`, ledger marks, discovered jobs). Folders stay the source of truth; `jobforge index --rebuild` regenerates it. - **`search` (D-27):** filter and keyword search across the user's own jobs by company, title, keyword, status, fit score. The command is `jobs`, with `search` as an alias (D-41, Q-4). - **Ledger (D-30 item 6):** `applied` rebuilds while preserving status, applied_at, comp, notes; records which variant was sent (D-34). - A place in the job store for discovered-but-not-prepared postings (D-28), so the agent can add a list and the user can promote entries with `prepare`.

Exit tests: after any write, search equals a full rebuild; ledger human fields survive regeneration; **performance test** with a synthetic store of 2,000 jobs keeps `search` and `applied` under a set threshold (proposed 1 second on CI hardware) while writes are unconstrained.

### 0.7 Agent layer (L)

Goal: the agent can take a new user from nothing to a first application.

Deliverables - **Canonical instruction source** with generated `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and similar, so they cannot drift (D-11). A test fails if a generated file is out of date. - **Setup interview:** the agent asks for old resumes and writing samples in `intake/` or pasted in, drafts atoms with facts and basis, and asks the user to confirm each before it is saved (D-07, D-35). Asks the PDF question (D-23). Voice corpus offered as optional (D-07). When an old resume is unclear about which job something happened at (skills lists, summaries, merged roles), the agent asks rather than guessing (D-40). - **Agent files in the workspace (D-14):** `init` writes the generated agent files into the user's workspace, since a PyPI user runs their agent there and never sees the repo. `init --refresh` updates them after an upgrade without touching the profile, atoms, or jobs. - **Fact interviews (D-35):** the instructions direct the agent to ask about secondary effects and costs instead of assuming them, to record only confirmed answers, and to probe defensibility on large or cross-industry claims. - **Confirmation enforced in code, not just in instructions.** Agent-drafted atoms and facts land in `profile/pending/`. Only `jobforge confirm` (interactive: shows each fact, its employer and role, its basis, and the defense note, then asks yes / edit / drop) moves them into the live atoms. A job-related fact with no role cannot be confirmed (D-40). `apply` and the fact check read only confirmed atoms. This makes D-35 testable and keeps a misbehaving agent from writing facts directly. - **Prep sheets (D-38):** `jobforge prep <job> --stage hr|interview|both` builds the sheet for the variant sent (D-38 update): - **Questions to expect from the interviewer:** one per significant claim on the variant, answered from its defense note; one per job requirement, pointing to the atom that covers it; gaps where no atom covers a requirement, flagged for the candidate to prepare, never answered by the tool; stage-specific standards (salary, availability, why looking for HR), with anything unanswered marked `UNCONFIRMED`. - **About five questions for the candidate to ask** the interviewer (D-41, Q-5). - **Discovery (D-28):** instructions for finding postings by industry and location and adding them to the job store as real URLs or pasted text. - The worker prompt rewritten for the new atom model and generalized beyond engineering resumes.

Exit tests: generated agent files match the source; `init` puts them in a new workspace and `init --refresh` updates them without touching user data; atoms in `pending/` are ignored by `apply` until confirmed; `confirm` accepts, edits, and drops correctly with scripted input, and refuses a job-related fact with no role; prep sheet pulls exactly the defense notes for the claims on the sent variant, lists an expected question for each, flags an uncovered job requirement as a gap with no written answer, and marks unanswered HR-stage items `UNCONFIRMED`. Agent behavior itself (does it ask good questions) is checked by a manual Claude Code run of the setup interview for John Smith, recorded in the phase notes. It is not automatable until the 1.x regression tooling.

### 0.8 Thirteen personas (L)

Goal: prove it works for people who are not software engineers.

Deliverables - The thirteen archetype personas (D-09): trades, factory, service, blue-collar healthcare, general office, software developer, engineer, educator, white-collar healthcare, career changer, entry level, logistics/driver, returning to work. John Smith is separate (D-41, Q-6). Each has a profile, atoms, at least one job description, a hand-checked `plan.json`, and expected outputs. At least the software developer, engineer, and educator personas have a project with a live URL (D-42). - End-to-end runs for every persona through `prepare` → `apply` → fact check → document scanner. - Fixes to the atom model, template, or validator that the personas expose (expected most for trades, service, entry level, and returning to work).

Exit tests: all thirteen plus John Smith pass end to end on both OSes; the fact check catches a planted violation in each persona, and an employer swap in every persona with more than one employer (D-40); the career-changer persona's cross-industry variant keeps every fact under its original employer; the entry-level persona produces a resume without padding; the returning-to-work persona's cover letter contains no volunteered gap explanation.

### 0.9 Setup, docs, release candidate (M)

Goal: a stranger can install it.

Deliverables - **Guided setup with images (D-01)** for Windows and Linux: install Python, install Jobforge (PyPI and clone), install a terminal agent, run `init`, first application. - README: what it is, the no-invented-facts promise, comparison to paid tailoring sites (D-02), required steps, then a separate **optional extras** section (PDF, voice corpus) (D-23), license summary (D-39). - **VM checklist (D-24)** finished, so either maintainer can run it on a clean Windows and a clean Linux VM. Started in 0.1. Maintainer-only; the images go in the user guide above, not here. - TestPyPI release and install from it. - Trademark search on "Jobforge" (D-03).

Exit tests: both maintainers complete the VM checklist on both OSes from the TestPyPI package and from a fresh clone, with every friction point logged and either fixed or documented.

### 1.0 Launch

Gate: the qualifying suite (section 5.10) passes. Then publish to PyPI, make the repo public, announce.

### 5.10 Qualifying suite for 1.0

1.  All exit tests from 0.1 to 0.9 green on Windows and Linux.
2.  Coverage: 100% of D-30 critical paths, 80% or more of everything else (D-15).
3.  All thirteen personas and John Smith pass end to end (D-09, D-10).
4.  Document scanner clean on every persona's output (D-31).
5.  Fact check catches every planted violation in the fixture suite (D-32, D-37), including every employer-binding violation (D-40) and every missing project URL (D-42).
6.  Performance test within threshold (D-29).
7.  VM checklist completed on both OSes from the real PyPI release candidate (D-24).
8.  T-PII clean across the whole repo and the built package.

## 6. Decisions this SOW needed

**Answered 2026-10-17 as D-41**, all as recommended below, except Q-7 (phase ownership), which is still open for the maintainers. The table is kept as the record of what was asked.

| ID  | Question                                                                                                                                                                           | Needed by | Recommendation                                                                                                                                                                                                                                                                  |
|----------------|----------------|-----------------|-------------------------|
| Q-1 | Atom/profile file format, given stdlib-only (finding 1). YAML needs PyYAML; `tomllib` reads TOML from Python 3.11 but cannot write it; JSON is stdlib but unfriendly to hand-edit. | 0.2       | TOML, read with `tomllib`, written by a small in-house writer for the narrow subset we emit. Readable for non-technical users, comments allowed, no dependency. Sets the floor at Python 3.11.                                                                                  |
| Q-2 | Page-limit check without a LaTeX log (finding 3), and whether the limit is always one page.                                                                                        | 0.4       | Estimate page fill from the template's known line capacity (the validator already measures rendered bullet width), and confirm against the real page count when PDF is on. Make the limit a profile setting, default 1: educators, clinicians, and long careers often expect 2. |
| Q-3 | Minimum Python version.                                                                                                                                                            | 0.1       | 3.11 (follows Q-1).                                                                                                                                                                                                                                                             |
| Q-4 | `search` or `jobs` as the command name (D-27).                                                                                                                                     | 0.6       | `jobs`, with `search` as an alias.                                                                                                                                                                                                                                              |
| Q-5 | "About five questions" means questions the candidate asks the interviewer (D-38, interpretation unconfirmed).                                                                      | 0.7       | Confirm.                                                                                                                                                                                                                                                                        |
| Q-6 | Is John Smith one of the thirteen or a separate generic persona (D-09)?                                                                                                            | 0.2       | Separate and deliberately plain, so the walkthrough is not tied to an industry.                                                                                                                                                                                                 |
| Q-7 | Who owns which phase between the two maintainers.                                                                                                                                  | 0.1       | Assign at kickoff.                                                                                                                                                                                                                                                              |
| Q-8 | Variant file naming (D-34 gives `John_Smith_Resume_2.docx` as an example). A `_2` in an uploaded file name tells the employer other versions exist.                                | 0.4       | Each variant in its own subfolder (`variants/2/`) holding clean-named files, so the file actually sent is always `John_Smith_Resume.docx`.                                                                                                                                      |

## 7. After 1.0

-   **1.x: regression tooling (D-19).** Before/after diffs of rendered resumes and cover letters across all personas, ATS parse scoring, and model-judged quality review layered on top of the mechanical fact check (D-32). When it can flag regressions automatically, open external PRs with DCO sign-off (D-39). Proposed as the gate for **2.0** under D-22: "2.0 = contributions open", qualifying suite written before work starts.
-   **Full CV (D-43), nice to have:** `jobforge cv` renders every atom except those marked `reword_of`, with no page limit, project URLs per D-42, and the full education record. It is the first post-1.0 feature candidate because the schema is ready for it and it reuses the 1.0 renderer, fact check, and document scanner unchanged.
-   **Roadmap, unscheduled:** template system (D-26), direct model API calls (D-12), pluggable corpus (D-05), macOS (D-14, contributed).

## 8. Risks

| Risk                                                                                                              | Mitigation                                                                                                                                                            |
|-------------------------|------------------------------------------------|
| The fact check is too strict and blocks honest rewording, or too loose and lets inventions through.               | Planted-violation fixtures in 0.4; persona runs in 0.8 tune it on real variety before launch.                                                                         |
| The atom model fits engineers and breaks on trades or service resumes.                                            | John Smith early (0.2), all personas before launch (0.8), model changes allowed until 0.8 exits.                                                                      |
| Setup is the biggest pain point for users (D-24).                                                                 | The guided setup with images (0.9) is what users get. Maintainers walk the same steps from a clean VM before every release, so they hit the friction first. |
| It only works on the maintainers' machines: leftover packages, Tectonic on PATH, an old workspace, or the private repo next door hide bugs. | Every release is tested from an untainted repo in a clean Windows and Linux VM (D-24 clarification). The VM is maintainer-only; users never need one. |
| Agents other than Claude follow the instructions poorly.                                                          | One canonical source (D-11); Claude is the tested path; others are best effort and documented as such.                                                                |
| A true fact is credited to the wrong employer, especially when a variant reframes it for another industry (D-40). | Binding is a schema field (0.2), a hard check on bullets and a sentence-level check on prose (0.4), and planted employer swaps in every multi-employer persona (0.8). |
| PII leaks from the private repo during the port.                                                                  | Hand port file by file, T-PII in every phase, fresh history (D-08).                                                                                                   |
| Name conflict ("JobForge" GitHub org exists).                                                                     | Trademark search in 0.9; repo under Jesse's personal account (D-03 update).                                                                                           |

## 9. Audit log

### Pass 1 (2026-10-17)

Checked the draft against every entry in DECISIONS.md and against the surveyed source code. Fixed in place:

| \#   | Finding                                                                                                                           | Fix                                                                                                                       |
|-----------------|------------------------------------|--------------------|
| A-1  | **The PII test's denylist would itself be PII committed to the repo.**                                                            | Denylist kept as a CI secret plus a local file outside the tree; test skips with a warning without it (section 4, T-PII). |
| A-2  | Persona count was inconsistent: "twelve more" listed thirteen, and John Smith's place was unclear.                                | Thirteen archetypes plus John Smith, tied to Q-6 (0.8, 5.10).                                                             |
| A-3  | D-35's "only confirmed facts" relied on the agent behaving. Nothing in code enforced it, so it could not be tested.               | Added `profile/pending/` and `jobforge confirm`; `apply` reads confirmed atoms only (0.7).                                |
| A-4  | 0.7's exit test implied automated testing of agent conversation quality, which cannot be automated before the regression tooling. | Split into code-level tests plus a recorded manual Claude Code run (0.7).                                                 |
| A-5  | "Reserve on PyPI via TestPyPI" does not reserve the real name, and empty placeholders can be reclaimed.                           | Minimal working `0.1.0` real release (0.1).                                                                               |
| A-6  | D-06 (per-job scoring and one-offs) was not covered.                                                                              | Added to scope and to 0.3.                                                                                                |
| A-7  | New commands (`init`, `index`, `prep`, `confirm`) were missing from the scope list.                                               | Added (section 2).                                                                                                        |
| A-8  | The one-page cap was assumed universal; educator, healthcare, and long-career personas often need 2.                              | Page limit is a profile setting, default 1 (Q-2, 0.2).                                                                    |
| A-9  | The page estimate (0.4) had no check against reality.                                                                             | 0.5 exit test: estimate agrees with real PDF page count.                                                                  |
| A-10 | A 100% critical-coverage gate in every phase conflicted with D-15's "before launch" wording for the 80% bar.                      | Critical code at 100% in the phase that adds it; 80% is a 1.0 gate (section 4).                                           |
| A-11 | `--from-url` tests would hit live job boards and fail randomly.                                                                   | No network in tests; saved HTML fixtures (section 4).                                                                     |
| A-12 | D-24 VM runs were only scheduled for 0.9.                                                                                         | Required before every PyPI release (section 4).                                                                           |
| A-13 | The default voice rules would carry one person's preferences to every user.                                                       | Defaults keep general AI-tell rules and drop person-specific ones (0.2).                                                  |
| A-14 | D-17 and D-18 (employer IP) were not referenced.                                                                                  | Listed as met preconditions (section 2).                                                                                  |

Not changed, noted for review: - Q-1 (TOML) sets the floor at Python 3.11. That is fine for new installs but excludes older distro Pythons; the setup guide should say so. - Sizes (S/M/L) are judgment calls with no date attached (D-21). Revisit after 0.2, once the data model shows how hard the port really is.

### Pass 2 (2026-10-17)

Re-read both files from disk, not from memory, and checked them again against DECISIONS.md and the source code (`validate.py`, module line counts). Also covered the instruction given during this pass, recorded as D-40: job-related atoms must map to the right employer.

| \#   | Finding                                                                                                                                                                                                                                                                                                                                               | Fix                                                                                                                                                                                                                                                                                            |
|-----------------|------------------------------------|--------------------|
| A-15 | **Facts could be credited to the wrong employer.** The fact check only asked whether each token appears in *some* cited atom, so "At Acme I cut costs 90%" passed when the 90% happened elsewhere. The current code ties bullets to roles by ID prefix and only *warns* on a mismatch (`validate.py`), and replacing `atoms.py` would drop even that. | D-40 added. Binding is a schema field (0.2); a hard check on bullets and a sentence-level check on prose (0.4); setup asks when unclear and `confirm` refuses a fact with no role (0.7); employer-swap fixtures for every multi-employer persona (0.8); qualifying-suite item 5; new risk row. |
| A-16 | Education was planned in both the profile and the atoms, which brings back the "edit three times" problem D-08 set out to remove.                                                                                                                                                                                                                     | One home: education and credential atoms, fields marked resume / form (finding 8, 0.2).                                                                                                                                                                                                        |
| A-17 | Section 4 requires the VM checklist before every PyPI release, including 0.1's, but the checklist was first written in 0.9.                                                                                                                                                                                                                           | Draft in 0.1, grown each phase, finished in 0.9.                                                                                                                                                                                                                                               |
| A-18 | D-14 says the workspace gets the agent files, but nothing put them there. A PyPI user never sees the repo, so their agent would have no instructions.                                                                                                                                                                                                 | `init` writes them; `init --refresh` updates them after an upgrade (0.7).                                                                                                                                                                                                                      |
| A-19 | The 0.2 "lossless round trip" plus an in-house TOML writer would strip the comments from hand-edited files whenever `confirm` saved.                                                                                                                                                                                                                  | Writes never rewrite a hand-edited file; lossless means the loaded data (0.2).                                                                                                                                                                                                                 |
| A-20 | D-30 item 2 (clear failure when a board blocks scripted requests) is critical tier, but no exit test covered it.                                                                                                                                                                                                                                      | Blocked-board fixture added to 0.3.                                                                                                                                                                                                                                                            |
| A-21 | The private repo's rule that unanswerable ATS form fields read `UNCONFIRMED` and are never invented was not carried over.                                                                                                                                                                                                                             | Added to 0.3.                                                                                                                                                                                                                                                                                  |
| A-22 | Variant file names like `John_Smith_Resume_2.docx` tell an employer other versions exist.                                                                                                                                                                                                                                                             | Q-8, recommending a subfolder per variant with clean file names.                                                                                                                                                                                                                               |
| A-23 | Module count said 12, but the table listed 11.                                                                                                                                                                                                                                                                                                        | Corrected: 11 modules plus `__init__.py` and `__main__.py`.                                                                                                                                                                                                                                    |

Not changed, noted for review: - Sentence-level employer attribution in prose is a heuristic. Expect false positives on sentences that name two employers; 0.8 tunes it. - The 0.6 performance threshold (1 second) is still a proposal. Fix it at the start of 0.6.

### Revisions after pass 2 (2026-10-17)

Not an audit, recorded so the changes are traceable: - Section 6 answered as D-41 (Q-8 answered directly, the rest delegated); Q-7 open. Phases updated to cite the answers instead of the questions. - D-42 (project URLs always shown) added to the 0.2 schema, 0.4 checks, 0.5 optional `links` command, 0.8 personas, and the qualifying suite. - D-43 (full CV) added as a `reword_of` field in 0.2 and a post-1.0 command in section 7. - D-42 update: projects without a URL pass; `writeup_url` optional; links rechecked by `apply` when older than 7 days, dead links block, unclear results warn (0.2, 0.4, 0.5). - Q-7 pending until just before the first sprint; repo under Jesse's personal account; Q-5 confirmed; prep sheets add expected interviewer questions (D-38 update, 0.7).