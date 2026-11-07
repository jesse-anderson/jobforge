# Components and vocabulary

The reference for what each part of the project is called, what it does, where
it lives, and whether it is being worked on now. When a task, issue, or
commit message names a component, it uses the names in this file. If two
people mean different things by one word, this file is wrong and gets fixed.

- **Written:** 2026-11-06
- **Governing record:** `docs/DECISIONS.md`. Where this file and DECISIONS.md
  disagree, DECISIONS.md wins.

---

## The one-paragraph version

**Jobforge** is a free, locally run tool that turns a person's real work
history into a resume and cover letter tailored to one job posting, and never
states a fact the person did not give it. It has three layers: a
deterministic **engine** (a Python package) that does every step that can be
done by code, an **agent layer** (instruction files for the user's own AI
coding agent) that does only the steps that need language, and a **report**
(a static web page) that shows the user their search over time. The scraper
and dashboard are a separate, private project and are not part of Jobforge.

---

## Map

```
                        PUBLIC (source-available at launch)
 +-----------------------------------------------------------------------+
 |  Jobforge  (repo: jesse-anderson/jobforge)                            |
 |                                                                       |
 |   Agent layer  ----writes---->  plan.json, pending facts              |
 |   (CLAUDE.md, AGENTS.md...)          |                                |
 |        |                             v                                |
 |        +-------runs-------->  Engine (jobforge CLI, Python)           |
 |                                 |  validates, fact-checks, renders    |
 |                                 v                                     |
 |                       .docx deliverables + ledger                     |
 |                                 |                                     |
 |                                 v                                     |
 |                       Report (static HTML)   [deferred, post-MVP]     |
 +-----------------------------------------------------------------------+

                        PRIVATE (never public)
 +--------------------------------+   +----------------------------------+
 |  jobs  (the earlier tool)   |   |  the maintainers' private notes                    |
 |  scraper, dashboard,           |   |  maintainer notes, reviews,      |
 |  Cloudflare, each maintainer's |   |  blog drafts, anything that      |
 |  real applications             |   |  names a real person's search    |
 +--------------------------------+   +----------------------------------+
```

---

## Components

### Jobforge

The project and the product, as a whole. When someone outside says
"Jobforge" they mean the thing they install. Inside the team, say which layer
you mean (engine, agent layer, report) whenever it matters.

- Repo: `jesse-anderson/jobforge`. Private during development, made public
  at launch (see "Repos" below).
- PyPI name: `jobforge` (D-03; free as of 2026-10-17, reserve with 0.1).
- License: PolyForm Noncommercial 1.0.0 (D-39). Call it
  **source-available**, never "open source", since the noncommercial clause
  fails the OSI definition.

### Engine

The deterministic core: the `jobforge` Python package and its CLI. Everything
that can be done by code is done here, so it behaves the same every time and
cannot hallucinate.

- Code: `src/jobforge/`.
- Runtime is **stdlib only** (D-13). Dev and test dependencies are fine.
- Python 3.11+ (D-41, Q-3). Windows and Linux (D-14).
- Owns: workspace setup (`init`), job intake (`prepare --from-url /
  --from-text`), the profile and atom files, plan validation, the fact check,
  rendering `.docx` (and PDF when opted in), the ledger, job listing, and the
  ATS form text.
- Ported by hand from `the earlier tool/`, file by file, with a PII check on each
  file (D-08, SOW section 3).

> **Naming note.** Jesse's first draft called the engine "Jobforge". Use
> "engine" for the package and "Jobforge" for the project, so "Jobforge does
> X" is never ambiguous about whether code or an agent does X.

### Agent layer

The instructions, commands, and hooks that tell the user's own AI coding agent
(Claude Code first; Codex, Gemini CLI and others as failover) how to drive the
engine. There are no model API calls in Jobforge (D-12): the user's agent is
the LLM, and the user pays for it.

- Source: `src/jobforge/agent/`. One canonical instruction source; the
  `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` files are **generated** from it, and a
  test fails if a generated file is stale (D-11).
- Shipped inside the Python package, because `jobforge init` has to write
  these files into the user's workspace and a PyPI user never sees the repo
  (SOW A-18).

**The rule for this layer: the agent does only what needs language.** In
practice that is four jobs:

| Agent job | Output the engine checks |
|---|---|
| Drafting facts from the user's old resumes (setup) | Pending atoms, which only `jobforge confirm` can make live |
| Interviewing the user for missing facts and defense notes | Pending atoms, same gate |
| Writing the plan for one job: which facts, which wording, the letter | `plan.json`, which `apply` validates and fact-checks |
| Finding postings on request (D-28) | A URL or pasted text handed to `prepare` |

Everything else (parsing a posting, picking file names, rendering, checking
numbers, recording status) is an engine command the agent runs. Two
consequences:

1. **No safety guarantee may rest on the agent behaving.** If an instruction
   says "never invent a number", the engine also checks for invented numbers.
   Instructions and hooks make the agent efficient; code makes it safe.
2. **The agent never edits a deliverable.** It writes `plan.json`; the engine
   writes the `.docx`. If the output is wrong, the plan or the atoms are fixed,
   never the document.

**A chatbot path** is welcome as a lesser version, or shipped as a Claude
Skill: a plain chat app whose code sandbox installs Jobforge and runs it for
one job (D-47, M-2). It is not part of the MVP. The sandbox is wiped after
each session, so the user keeps the workspace folder and re-uploads it.

**Hooks** (Claude Code only) are a convenience, for example running
`jobforge check` every time `plan.json` is written so errors come back
immediately. Because other agents have no hooks, nothing may depend on them.

**Delegation** (a smart model handing work to a cheaper one) is a cost
optimization for the user, since they pay for tokens. It is **not in the
MVP**. Today's private flow has an orchestrator spawning a worker for the
plan; Jobforge starts with one agent and adds delegation once the plan step
is stable, and only where the cheaper model's output is still checked by the
engine. Agents other than Claude Code may not support picking a subagent
model, so the single-agent flow must always work.

### Report

A static web page, generated by the engine, that the user (or their agent)
opens in a browser to see their search: jobs applied to, velocity
(applications per day over time), callback rate, and a Sankey diagram of
outcomes (applied, screened, interviewed, offered, rejected, ghosted).

- **Deferred. Not in the MVP** (D-46). The data it needs *is* in the MVP; see
  "Ledger" below.
- Source: `src/jobforge/report/` (templates and assets, shipped in the
  package).
- Output: `report/index.html` in the user's workspace, opened from disk.
- Owner area: UI/UX is Mike's per the SOW header; metrics definitions are
  Jesse's.

Constraints any implementation must meet:

1. **No build step, and users never run Node or npm.** The report is plain
   HTML, CSS, and JavaScript (D-47, M-5). Fewer dependencies is the rule:
   anything added has to justify itself, and TypeScript or a bundler would
   need a new decision.
2. **It works from `file://`.** Browsers block `fetch()` of local files, so
   the engine writes the data into the page (inline JSON, or a `data.js`
   that sets a global), not a separate JSON the page fetches.
3. **No CDN at runtime.** It must open offline. Any chart library is vendored
   into the package, and its license must be compatible.
4. **Date-only strings are local dates.** `new Date("2026-09-07")` is UTC
   midnight and renders as Sep 6 in US time zones. The private dashboard hit
   exactly this (FINDINGS F16).
5. **One source of truth.** The report reads the ledger and nothing else. No
   browser localStorage state that can disagree with it (the private
   dashboard's two notions of "applied" are the cautionary tale).

> **Do not confuse the report with the dashboard.** "The UI" has meant the
> private Cloudflare dashboard in `the earlier tool's dashboard/` until now. That dashboard
> lists scraped jobs, is TypeScript plus Vite, and is deployed behind
> Cloudflare Access. The report is new, per user, local, and has no scraped
> data in it. Say "report" or "dashboard", never just "the UI".

### Scraper

The nightly job-board scraper in the private `jobs` repo (`scraping/`,
`scripts/`, 140+ company adapters), plus the SQLite corpus it fills.

- **Not part of Jobforge, and never will be in this form** (D-04, D-45).
  Reasons: legal exposure from shipping scrapers for boards we do not own, and
  the risk of enabling mass agentic traffic against job boards (ten agents
  per user times ten thousand users is someone's cloud bill, and a damages
  claim).
- Its own sprint or project later. Bugs found in it (most of Mike's FINDINGS)
  are fixed in `jobs`, not here.
- Jobforge's replacement for it is ground truth only: a posting URL or pasted
  text the user (or their agent, D-28) supplies.

### Dashboard

The private web page in `the earlier tool's dashboard/` that lists scraped jobs, deployed to
Cloudflare Pages behind Cloudflare Access by the pipeline machine. Part of
the scraper project, not of Jobforge. See the warning under "Report".

### Job board (ours, future)

A job board run by us, as distinct from scraping other people's. Jesse is
open to it as its own project. It is not scheduled, and note D-25: Jobforge
is never a hosted service, so a board we run would be a separate product with
its own decisions about cost.

### Job Apps

The tracker label for this whole workstream: Jobforge plus the
behind-the-scenes repos that support it. Tasks tagged "Job Apps" belong to
it; tasks tagged "Global" cut across projects. (Confirmed, D-47.)

---

## Data vocabulary

Terms the engine and agent layer share. Most come from DECISIONS.md.

| Term | Meaning |
|---|---|
| **Workspace** | The user's own folder, made by `jobforge init`. Holds the profile, atoms, intake, jobs, ledger, and generated agent files. Everything about one person lives here and nowhere else. A marker file identifies it; commands find it by walking up from the current directory and **fail loudly** if there is none, never falling back to defaults (FINDINGS F7 is what silent fallback costs). |
| **Profile** | Identity and settings: name, contact, file-name stem, voice rules, page limit, never-claim list (D-08). TOML. |
| **Atom** | One fact about the user, in TOML: a role, bullet, project, skill, credential, or education entry. Carries structured facts, a basis per fact, a defense note, and optional phrasings (D-33, D-36). |
| **Role** | An atom for one job held: employer, title, location, dates. Every job-related fact belongs to exactly one role (D-40). |
| **Basis** | How the user knows a fact: `measured`, `records`, or `estimate` (D-36). |
| **Defense note** | The user's own words on how they know a fact, used to prepare for "how did you get that number?" (D-35, D-36). |
| **Pending** | Facts an agent drafted that the user has not confirmed. Live in `profile/pending/`. The engine ignores them until `jobforge confirm` (SOW A-3). |
| **Intake** | The folder the user drops old resumes, letters, and writing samples into at setup (D-07). |
| **Job folder** | One folder per posting under `jobs/`, holding `job.json`, `plan.json`, the deliverables, and any per-job notes (D-06). |
| **`job.json`** | The posting as captured by `prepare`: company, title, location, URL, description. Ground truth. |
| **`plan.json`** | The agent's choices for one job: which atoms, in what order, with what wording, plus the cover letter. The contract between agent layer and engine. |
| **Deliverables** | The files sent to an employer: `First_Last_Resume.docx`, `First_Last_Cover_Letter.docx` (and PDFs if enabled). Never `cover_letter.md`, which is a working file. |
| **Variant** | A second or third framing of the same application, in `variants/2/` etc., with clean file names (D-34, Q-8). Not in the MVP. |
| **Fact check** | The mechanical check that every number, money figure, date, employer, title, credential, and tool in a deliverable appears in an atom the plan cites, under the right employer, with no hedging or false precision (D-32, D-37, D-40). The core promise. |
| **Ledger** | The record of what was applied to and what happened next. Folders are evidence; status and dates are user facts preserved across rebuilds. |
| **Prep sheet** | Per-job HR or interview prep built from defense notes (D-38). Not in the MVP. |
| **Persona** | A fictional user used as a fixture and example. John Smith is the baseline; thirteen archetypes follow (D-09, D-10). |

---

## Repos

Three repos. The rule for where something goes:

- **Would a stranger installing Jobforge need it, or benefit from reading
  it?** It goes in `jobforge`.
- **Is it about building Jobforge, but names a real person's job search,
  money, or contacts, or is not ready to be public?** It goes in
  `the maintainers' private notes`.
- **Is it someone's actual job search, or the scraper?** It goes in `jobs`.

| Repo | Visibility | Holds | Never holds |
|---|---|---|---|
| `jesse-anderson/jobforge` | Private now; **public at launch** | Engine, agent layer, report, fictional personas, tests, user and maintainer docs, DECISIONS and SOW | Any real person's data. Anything here will be public, including issue and commit history. |
| `the maintainers' private notes` | Private, permanently | Reviews of the private repos (e.g. the FINDINGS review), sprint notes that mention real searches, blog drafts before publishing, launch logistics | Code. If code is needed, it belongs in `jobforge`. |
| `the earlier tool` | Private, permanently | Scraper, dashboard, Cloudflare pipeline, both maintainers' real applications | Nothing from it is ever copied into `jobforge` without a PII check (D-08). Its history must never be made public. |

**Why one product repo and not three (engine, agent, report).** The agent
layer and the report both have to ship inside the PyPI package, because
`init` writes the agent files into the workspace and the engine generates the
report, and a user who ran `pip install` has nothing else. Split repos would
mean three version numbers that must match, and the agent instructions would
drift from the `plan.json` schema they describe. One repo, one version, one
test suite that proves the instructions and the engine agree.

**Going public.** Development happens in the private `jobforge` repo, and the
same repo is flipped public at launch. Before the flip: run T-PII over the
whole history (not just the tip), and if anything turns up, publish a
squashed fresh history instead. Issues and PRs become public too, so personal
context goes in `the maintainers' private notes`, filed under the issue number. The Jobforge
issue carries only what a user could follow and never points to a private
repo.

### Planned layout of `jobforge`

```
jobforge/
  pyproject.toml          console entry point `jobforge` (0.1)
  LICENSE                 PolyForm Noncommercial 1.0.0 (0.1)
  README.md
  CONTRIBUTING.md         PRs closed until regression tooling (D-19)
  src/jobforge/
    cli.py, ...           engine
    agent/                canonical instruction source, generated files
    report/               report templates and assets (post-MVP)
  tests/
  fixtures/personas/      John Smith + archetypes (fictional only)
  docs/
    DECISIONS.md          the governing record
    SOW.md                phases 0.1 to 1.0
    COMPONENTS.md         this file
    MVP.md                what the MVP (the public launch) is and is not
    MAINTAINING.md        how the two maintainers split and track work
```

Only `docs/` and `README.md` exist as of 2026-11-06. The rest is built in
SOW phase 0.1.

### Local folders

On each maintainer's machine, the repos are siblings:

```
GitHub/
  jobforge/        product
  the maintainers' private notes/    private notes
  jobs/            scraper, dashboard, real applications
```

Do not nest one repo inside another, and do not run Jobforge with a
workspace inside any of these repos. A test workspace goes somewhere outside
them, so no real application ever lands in a tracked folder by accident.
