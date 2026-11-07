# Design decisions log

This file records the scope questions asked at the start of the open-source
transition and the answers given, in the words they were given where possible.
Its job is to prevent drift: when a later change seems to contradict something
here, either the change is wrong or this file needs a new dated entry saying
what changed and why. Do not silently edit old answers.

- **Session:** 2026-10-17
- **Decided by:** Jesse Anderson (maintainer). Co-maintainer: Mike Wilson.
- **Source project:** the private `jobs` repo (`tailor/` package). Only the
  resume-tailoring side is being opened. The scraper, dashboard, and
  Cloudflare pipeline stay private.
- **Folder name:** `the old working folder` is a placeholder until the project name is
  chosen (see D-03).

---

## Summary of decisions

| ID | Topic | Decision |
|----|-------|----------|
| D-01 | Audience | Anyone. A CLI is the minimum skill required. A guided setup with images is highly desirable. |
| D-02 | Goal | A project with outside contributors, and a shakeup of the pay-to-use resume tailoring sites. |
| D-03 | Name | **Jobforge** (decided 2026-10-17). Repo under Jesse's personal GitHub account. |
| D-04 | Scraper / dashboard / Cloudflare | Out. Job input is ground truth only: a URL or a pasted job description. |
| D-05 | Pluggable corpus / bring-your-own-scraper | Deferred to the roadmap (nice to have). |
| D-06 | Subcommands | All of them, and more may be added. Per-job one-offs (scoring and similar) live in the per-job data folder. |
| D-07 | Voice corpus and deep personalization | Optional, per person, built up over time, starting at initial setup when the agent asks for resumes and writing samples. |
| D-08 | Repo and PII | New repo and folder. Per-user settings replace every hardcoded identity. |
| D-09 | Test personas | Thirteen fictional archetypes: nine by industry, plus career changer, entry level, logistics/driver, and returning to work. |
| D-10 | Sample persona | Covered by D-09. The baseline user is "John Smith". |
| D-11 | Model support | Claude first and heavily advertised. Ship CLAUDE.md, AGENTS.md, GEMINI.md and similar files as failover for other agents. |
| D-12 | Model APIs | None. The user's agentic terminal coding tool does the LLM work. API calls deferred to the roadmap. |
| D-13 | Packaging | Publish on PyPI. A thin entry point over a package that holds the real logic. |
| D-14 | Distribution / OS | Both PyPI and clone-and-run. Windows and Linux from day one. macOS unsupported unless someone contributes it. |
| D-15 | Tests | Required before launch. 100% of critical paths, at least 80% of everything else. |
| D-16 | License | ~~Free for personal use; commercial users must disclose, with penalties.~~ Superseded by D-39. |
| D-17 | Employer IP (employer A) | Tool is carved out in the employment agreement. Cleared. |
| D-18 | Employer IP (employer B) | No code, time, or equipment from that employer. Cleared. |
| D-19 | Contributions | Open to PRs, but not accepted until AI-based regression tooling exists. |
| D-20 | Private repo relationship | Out of scope. Personal nice to have. |
| D-21 | Timeline | No firm date. Sooner is better. |
| D-22 | Phasing / versioning | By deliverable. X.x versions; qualifying tests gate any major (X) bump. |
| D-23 | Output formats | `.docx` always. PDF opt-in at setup (Tectonic). README lists optional extras separately. |
| D-24 | Setup testing | Fresh-clone / fresh-install runs in clean Windows and Linux VMs before releases. Maintainer testing only; users never need a VM. |
| D-25 | Hosting | Never a hosted service. Runs locally, free to users. |
| D-26 | Templates | One template at 1.0. Template system on the roadmap. |
| D-27 | `search` | Searches the user's own prepared jobs. Name (`search` / `jobs`) open. |
| D-28 | Job discovery | Agent finds postings on request; package stores and indexes them. No scraper. |
| D-29 | Performance | Fast reads, slow writes OK. Rebuildable index updated on write; folders are truth. |
| D-30 | Critical paths | Setup, intake, plan validation, rendering, safety, ledger, index. |
| D-31 | Document checks | Tests open/read/close every `.docx`/PDF and fail on hidden characters. Test side only. |
| D-32 | No invented facts | Core promise, 100% tier. Facts map 1:1 to atoms; wording is free. Mechanical token check. |
| D-33 | Atom model | Structured facts plus optional phrasings by use/industry. Plain text, not LaTeX. |
| D-34 | Variants | Agent may produce `resume_1..N` per job for different framings; user picks; ledger records which was sent. |
| D-35 | Fact interviews | Agent asks to surface new facts; only confirmed user answers become facts. Ballparks OK; probe defensibility. |
| D-36 | Fact basis | Each fact is `measured`, `records`, or `estimate`, with the user's "how I know" note. |
| D-37 | Number style | Plain round figures ("50%"), never "~50%" or "about". No false precision. Enforced by the fact check. |
| D-38 | Prep sheets | HR screen and/or interview prep per job, built from defense notes. About 5 questions for the candidate to ask, plus the questions the interviewer is likely to ask. |
| D-39 | License | PolyForm Noncommercial 1.0.0 alone. No commercial license, no CLA; DCO sign-off. Nonprofits and public institutions covered. |
| D-40 | Employer binding | Every job-related atom belongs to exactly one role. A fact may only be claimed for the employer it happened at. Enforced by code. |
| D-41 | SOW questions | TOML atoms, Python 3.11+, page limit a profile setting, `jobs` command with `search` alias, John Smith separate, variants in subfolders. Phase ownership (Q-7) assigned just before the first 48-72 hour sprint. |
| D-42 | Project URLs | A project with a URL always shows it, as visible text. Projects with no URL are fine. Links rechecked when last check is over 7 days old; a dead link blocks the render. |
| D-43 | Full CV | Nice to have: render every atom except declared rewords. Schema supports it from 0.2; the command comes after 1.0. |
| D-44 | Repos | One product monorepo (`jobforge`: engine, agent layer, report), private until launch then public. A permanently private `the maintainers' private notes`. `jobs` unchanged. (2026-11-06) |
| D-45 | Scraper | Reaffirms D-04 with reasons: legal exposure and enabling agentic traffic against job boards. Its own sprint later. A job board we run is a separate, welcome idea. (2026-11-06) |
| D-46 | Report (UI) | Deferred past the MVP. A static page generated locally, showing applied count, velocity, callback rate, and an outcome Sankey. The ledger records what it needs from day one. (2026-11-06) |
| D-47 | MVP accepted | MVP.md accepted; it is the public launch (0.x preview). Chatbot/Claude Skill path welcome but not gating. Ghost after 30 days. `check` added. Report is plain HTML/CSS/JS, no build step. Job Apps = whole workstream. (2026-11-06) |
| D-48 | Commits | Only Jesse or Mike commit. AI may propose a commit message, with no AI attribution lines. (2026-11-06) |
| D-49 | Copyright | Jesse and Mike hold the copyright jointly; a license change needs both. Contributors keep their copyright and license contributions under PolyForm NC by submitting them, with a DCO sign-off. (2026-11-06) |
| D-50 | Rounding | Claiming less is fine: dropping decimals passes. Rounding that changes a figure is refused; the user confirms a rounded form once as a phrasing on the atom, and the agent offers it. (2026-11-06) |

---

## 1. Goals and audience

### Q1. Who is it for?
> Anyone at all. We will want to run a CLI no matter what and that is the
> basic competency required. A guided setup, however, with images is highly
> desirable!

**D-01.** The CLI stays the interface and is the floor for user skill. Plan
for a guided setup walkthrough with screenshots or images as a first-class
deliverable, not an afterthought.

### Q2. What does success look like?
> Project with outside contributors, and also a shakeup to these crappy
> pay-driven resume tailoring sites.

**D-02.** Success means outside contributors, plus a free, credible
alternative to paid resume-tailoring services. Docs and positioning should
make that comparison explicit.

### Q3. Name and identity?
> It should have one of those stupid catchy names. We can go back and forth.

**D-03.** Open item. Needs its own name, PyPI availability check, and repo
rename once chosen.

**D-03 update (2026-10-17): the name is Jobforge.** Runners-up: Jobsmith,
Worksmith, Measure Twice. Reasoning: a plain word anyone gets ("forge your
resume"), it reads as craft and fits the blue-collar personas, and it gives
the CLI a natural verb. Checked that day: `jobforge` is free on PyPI. A
GitHub organization named `JobForge` already exists, so the repo will live
under a personal or new org namespace. Do a trademark search before launch.

---

## 2. Boundary

### Q4. Is the scraper / dashboard / Cloudflare pipeline out?
> The dashboard, scraper and Cloudflare are out. We will only rely on ground
> truths via web link or copy-pasted job descriptions.

**D-04.** Out. Job input is `prepare --from-url` and `prepare --from-text`
(file or stdin) only. Strip `jobs_db`, `fetch`, `source`, the chunk corpus,
the SQLite backend, Cloudflare Access handling, and anything that depends on
`job_key` resolving against a scraped DB.

### Q5. Plain `job.json` schema or a pluggable corpus interface?
> Defer to nice to haves / future roadmap. That is convoluted and people will
> complain that their badly coded scraper doesn't work.

**D-05.** Roadmap only. The documented `job.json` schema is the contract for
now. Part of the reason is support load: a plugin interface invites bug
reports about scrapers we do not own.

### Q6. Which subcommands go in?
> All of it should be included and we may add more. Intermediate job scoring
> and other one-offs may be useful to have in a per-job / data folder.

**D-06.** Ship everything: `prepare`, `apply`, `ats` (including `--form`),
`applied` (ledger), `search` where it still makes sense without a corpus,
and the `.docx` writer plus `extract_text` round-trip. Intermediate artifacts
(fit scoring, notes, one-off analyses) belong in the per-job folder next to
`job.json` and `plan.json`.

*Follow-up:* `search` queries the scraped corpus today. With D-04 it needs
a new meaning (search across the user's own prepared jobs?) or removal.
Decide during extraction.

### Follow-up (answered 2026-10-17). What does `search` do without a corpus?
> Searches your own jobs. Initially the search will suck, but over time be
> better. Also note, we can always ask the agent to look for jobs in X
> industry near Y location and build out a list as well. We need to be
> careful to ensure that the list doesn't grow so much that it bogs down the
> system. Fast / efficient reads are important. Slow writes are OK.

**D-27. `search` searches the user's own jobs**, meaning every job folder
they have prepared, by company, title, keyword, status, and fit score. It
starts basic and improves over time. Command name still open: `search`, or
`jobs` so it is not mistaken for searching the internet.

**D-28. Agent-assisted discovery is allowed and fits D-04.** The user can
ask their agent to find jobs in an industry near a location and add them to
a list. Each entry is still a real posting URL or pasted description, so the
ground-truth rule holds. Discovery is the agent's job and lives in the
agent instruction files; the package only stores and indexes what comes
back. No scraper ships.

**D-29. Fast reads, slow writes.** The job list must not bog down as it
grows. Reads (`search`, `applied`, the listing commands) must stay fast at
hundreds to low thousands of jobs; writes (`prepare`, adding discovered
jobs, `apply`) can be slow. In practice: keep an index that is updated on
write, so reads never walk every folder and parse every `job.json`. The
index is a cache that can always be rebuilt from the folders, so folders
remain the source of truth. Add a performance test with a large synthetic
job list to the qualifying suite.

### Q7. Is the voice corpus in scope?
> The blog voice / corpus is on a per-person basis, but inherently optional.
> We can think of many of these things, such as filling out the larger atoms
> and writing samples, as inherently a more personalized approach which will
> inevitably occur over a time period. This should occur at initial setup
> when Claude or other agents begin to ask for resume files to be dropped
> into a folder or copy-pasted in over time.

**D-07.** In scope, optional, per user. Personalization is progressive:
- **Initial setup:** the agent asks the user to drop existing resumes, cover
  letters, and writing samples into a known intake folder, or paste them in.
  The agent drafts the first atom inventory from them.
- **Over time:** atoms get richer and the voice corpus grows as the user
  applies to more jobs.
- Nothing in the core flow may *require* a voice corpus.

---

## 3. Personal data and history

### Q8. New repo or scrub this one?
> New repo / folder, for the love of god. Yes, per-user settings are desired.

**D-08.** New repo with no shared history with `jobs`. Code is copied
forward on purpose, file by file, and checked for PII on the way in.
Everything currently hardcoded to Jesse moves into per-user settings:
`HEADER_BLOCK`, `EDUCATION_BLOCK`, `DOCX_CONTACT`, `DOCX_EDUCATION`,
`ats.py` `CONTACT` / `EDUCATION` / `ROLE_EXTRAS`, and the `RESUME_STEM` /
`COVER_STEM` filenames (which become `<First>_<Last>_Resume` built from the
profile). Doing this also removes the "edit three times" invariant from the
private repo.

Nothing from `the earlier tool's data/applications/`, the private contact details,
the writing samples, or `docs/` (which holds third-party documents) enters this
repo.

### Q9 / Q10. Hardcoded identity and a sample persona
> For testing purposes we will have archetypal roles. Blue collar: trades,
> factory, service industry, healthcare. White collar: general office,
> software developer, engineer, educator, healthcare. Ten, actually.

**D-09.** Ship fictional archetype personas, each with a complete profile,
atom inventory, at least one sample job description, and expected outputs,
used both as onboarding examples and as test fixtures:

| # | Collar | Archetype |
|---|--------|-----------|
| 1 | Blue | Trades |
| 2 | Blue | Factory / manufacturing floor |
| 3 | Blue | Service industry |
| 4 | Blue | Healthcare (e.g. CNA, tech) |
| 5 | White | General office |
| 6 | White | Software developer |
| 7 | White | Engineer |
| 8 | White | Educator |
| 9 | White | Healthcare (e.g. nurse, clinical) |
| 10 | — | ~~Open: the answer says ten but lists nine.~~ Resolved 2026-10-17, see below. |

**D-09 update (2026-10-17): thirteen personas, not ten.** The tenth is a
**career changer**, and three more were added because each one exercises a
failure mode the first nine miss. None of the four gets cut.

| # | Collar | Archetype | What it stress-tests |
|---|--------|-----------|----------------------|
| 10 | — | **Career changer** (e.g. retail manager into project coordination) | Translating experience when the job description and the person's history use different words. People with mixed skill sets (engineering, software, trades, operations) rarely think of themselves as career changers. |
| 11 | — | **Entry level / first job / new graduate** | A thin atom inventory. The tool must not pad or invent anything. |
| 12 | Blue | **Logistics / driver** (CDL, warehouse, delivery) | Resumes carried by certifications (CDL class, endorsements, safety record). |
| 13 | — | **Returning to work** (multi-year caregiving or other gap) | Handling a gap without volunteering weaknesses in the letter. |

The baseline demo user stays John Smith (D-10). He can be one of the
thirteen or a separate generic persona; decide when fixtures are built.

The archetypes exist to prove the tool works for people who are not
software engineers. The current atom format and LaTeX template grew up
around one engineering resume, so trades and service resumes are where it
is most likely to break.

**D-10.** The baseline demo user is **John Smith**. "Our base covered" means
John Smith can go from a clean install to a tailored resume and cover letter.

---

## 4. The LLM step

### Q11. Prompts, API, or model-agnostic?
> I have my own qualms with using other models; however, I believe it may be
> a net positive to have the generic CLAUDE.md, GEMINI.md, AGENTS.md etc.
> files. This isn't to say that we aren't going to heavily advertise using
> this with Claude. I just want it for failover protection in case someone
> uses it with another model.

**D-11.** Claude Code is the primary, advertised path. Also ship agent
instruction files for other tools (AGENTS.md, GEMINI.md, and similar).
Keep one canonical instruction source and generate or mirror the others from
it, so they cannot drift apart. The `plan.json` contract is documented
independently of any model.

### Q12. Which API providers?
> No APIs. Agentic coding in a terminal is much better. They can deal with it
> themselves. Or we can defer API-based calls to a nice to have.

**D-12.** No model API calls in the package. The user's terminal agent writes
`plan.json`; the package validates and renders it. Direct API calls go on the
roadmap.

---

## 5. Engineering constraints

### Q13. Stdlib-only, or relax it for packaging?
> A packaging approach would be nice and would lend quite a bit of credence
> to the project if we publish on PyPI. So we can build out the software
> infrastructure such that we have a relatively simple Python script that is
> called, but the underlying Python files contain all the nuanced code.

**D-13.** Publish to PyPI with a `pyproject.toml`. A thin console entry
point dispatches into the package where the logic lives. Keep the runtime
stdlib-only unless there is a recorded reason not to (zero-dependency
`.docx` writing already works); dev and test dependencies are fine.

### Q14. PyPI or clone-and-run? Which OSes?
> Both. We want it to be able to get grabbed on PyPI as well as a simple
> clone-only repo. That means we may have the project in a
> project-in-a-project sort of design, but I am OK with that. I would like
> Windows and Linux from the get-go. I don't have a Mac, and unless someone
> buys me one it's their problem.

**D-14.** Two install paths, both supported:
1. `pip install <name>`, then run the CLI against a user workspace folder.
2. `git clone`, then run from the repo.

The installed package should be able to scaffold a user workspace (profile,
intake folder, jobs folder, agent instruction files), so both paths end up
in the same layout. Windows and Linux are tested in CI. macOS is
unsupported and accepted as contributed.

*Open from the original Q15:* whether PDF via tectonic/pdflatex stays
required or `.docx` becomes the primary output with PDF optional, and
whether resume templates are swappable. Not answered this session.

### Q15 (answered 2026-10-17). PDF required? Swappable templates?
> PDF optional, but we will state in our README what the other nice to
> haves are. Also note, we can decision-gate it to the user to ask them if
> they also want a PDF option. Oftentimes our testing beyond the raw code
> level will be a fresh pull of the repo in a VM or similar to assess what a
> user would actually encounter in the setup. Setup is likely to be the
> biggest pain point. I don't want to make this a cloud service, since that
> means it costs money, which means it costs people, who likely don't have a
> job, money. Template system on roadmap.

**D-23. `.docx` is the guaranteed output; PDF is opt-in.** Every install
produces `.docx`, the format to submit. During setup the user is asked
whether they also want PDF; if yes, setup walks them through installing
Tectonic. If PDF was not set up, `apply` says so plainly instead of silently
skipping it, which is what the private repo does today. The README lists
optional extras (PDF, voice corpus, etc.) in their own section, kept apart
from the required steps.

**D-24. Setup gets tested as a user meets it.** Beyond unit and integration
tests, release testing includes a fresh clone or `pip install` in a clean VM
(Windows and Linux) and walking the real setup. Setup is expected to be the
biggest pain point, so it gets the most end-to-end attention. Document the
VM checklist so either maintainer can run it.

**D-24 clarification (2026-10-17): the VM is for maintainers only.**
> The vm is purely to test a "clean" repo. Users won't need to run anything
> in a vm. It is purely so we have an untainted repo to run testing in.

The VM gives maintainers an untainted repo and machine, with none of the
packages, PATH entries, workspaces, or private-repo files a development
machine collects, so bugs those leftovers would hide show up before users
meet them. Users install and run Jobforge directly on their own Windows or
Linux machine. The VM checklist is a maintainer document and never appears
in the user setup guide; the guide's images (D-01) are a separate
deliverable.

**D-25. Never a hosted service.** Jobforge runs on the user's machine. A
cloud service costs money to run, and that cost ends up with users, many of
whom are out of work. Any proposal that needs a server we pay for conflicts
with this decision.

**D-26. One template at 1.0; a template system is on the roadmap.**

### Q17. Tests and CI before launch?
> Required before launch, and we need to exercise 100% of the critical paths
> and at least 80% of the non-critical. A lot of tests and a lot of
> convolution, but robustness is paramount.

**D-15.** Launch gate: 100% coverage of critical paths, at least 80% of the
rest. Define "critical path" in writing early (at minimum: workspace setup,
`prepare` from URL and text, `plan.json` validation, `apply` producing
`.tex` / `.docx` / PDF, `ats` output, ASCII/CRLF guarantees, ledger rebuild).
CI runs tests only and never scrapes.

### Follow-up (answered 2026-10-17). What counts as a critical path?
Draft proposed: (1) setup, (2) job intake, (3) `plan.json` validation,
(4) rendering, (5) safety guarantees, (6) ledger, (7) index. Accepted, with
these changes:

> We need to actually run a .docx check in some capacity in which a file is
> programmatically opened, read, and then closed. Same with PDF when that
> comes up, to avoid "hidden" chars that will scramble the ATS and reject a
> candidate. We can have it on the testing side, and not as a requirement
> for users.
>
> No invented facts is the biggest appeal of this tooling. It should map
> back 1 to 1 with whatever is stated within the atoms. That isn't to say
> there won't be one truth stated X number of times in different atoms and
> the agent chooses the best wording. "I cut disposal costs by 90%" /
> "Operational efficiency achieved through 90% reduction in disposal
> expenses." That is dependent on the industry and the way they like things
> worded, or how something may sound in a cover letter / email as opposed to
> a resume.

**D-30. The critical-path list (100% coverage tier):**
1. Setup: workspace, profile, intake folder, agent files, PDF opt-in.
2. Job intake: `prepare --from-url` (JSON-LD, then page text, clear failure
   when blocked) and `--from-text` (file, stdin, pasted HTML).
3. Plan validation: a bad or partial `plan.json` is rejected clearly and
   never produces a half-built document.
4. Rendering: `.docx` resume and cover letter from profile plus atoms,
   output named from the profile.
5. Safety: ATS text is ASCII with CRLF line endings; `cover_letter.md` never
   leaks into deliverables; no invented facts (D-32).
6. Ledger: `applied` rebuilds without losing status, applied_at, comp, notes.
7. Index: after any write, search results equal a full rebuild.

**D-31. File-level document checks, test side only.** Tests open every
generated `.docx` (and PDF, once it exists) programmatically, read it,
close it, and inspect what an ATS parser would see. They fail on hidden or
hostile characters: zero-width characters, soft hyphens, non-breaking
spaces where a normal space belongs, control characters, private-use
glyphs, PDF ligatures (fi/fl) that extract as a single glyph, and text out
of reading order. The checks run across all D-09 personas. This is
test-suite tooling; users do not need it installed.

**D-32. No invented facts is the core promise, and it is in the 100% tier
at 1.0.** Every fact in a deliverable maps one-to-one to a fact stated in
the user's atoms. *Wording* is free; *facts* are not. One fact may be
phrased many ways, and the agent picks the phrasing that suits the
industry and the document (resume bullet vs cover letter vs email):

- "I cut disposal costs by 90%."
- "Operational efficiency achieved through a 90% reduction in disposal
  expenses."

Both state the same fact (disposal costs, down 90%). Changing it to 85%,
"waste costs" in a different scope, or a dollar figure nobody gave is an
invented fact.

Design direction (to confirm in the SOW): verification is mechanical, not
judged by a model. Pull the checkable tokens out of each output line
(numbers, percentages, money, dates, durations, employers, titles,
credentials, tools) and require every one to appear in an atom the plan
cites. Wording can change freely around them. Model-judged checks can be
added later through the D-19 regression tooling, on top of this, never in
place of it.

---

### Follow-up (answered 2026-10-17). Atom data model
Options offered: (1) facts plus optional phrasings, (2) phrasings only with
facts pulled out automatically, (3) keep the LaTeX `master.tex` format.

> 1. Now the main agent can always ask questions. So if they believe a
> wording is better they can actually create multiple versions for a
> resume. This could look like resume_1, resume_2, resume_3. This will
> ensure that, generally, the best wording could be chosen for an industry.
> This should help career changers be able to speak to their own industry
> as well as others. "Reduce Python pipeline AWS RAM usage 97% by rewrite to
> Rust function" -> "Enhance operational efficiency by eliminating
> bottlenecked step in business operations by 50%." Now note here that this
> would require asking the user some questions about the nature of that
> bottleneck. Here we are assuming that we did reduce RAM usage dramatically
> and that will effectively reduce costs, but the actual rewrite to Rust had
> an externality in the form of cutting run time in half. Logically the next
> question to ask would then be what the cost savings look like. We want
> this grounded in the applicant's knowledge. So at times a ballpark figure
> is OK, and at other times we need to question the defensibility of the
> claim by asking the user to explain in more detail so they don't bomb the
> interview.

**D-33. Atoms are facts plus optional phrasings.** Each atom stores its
facts in structured form (what changed, by how much, where, with what)
and may carry several stored phrasings tagged by use (resume, cover letter,
email) and optionally by industry. The agent may reuse a phrasing or write a
new one; either way the D-32 check runs against the stored facts. Atoms
live in a plain-text format a non-technical user can read and edit (YAML
or similar), not LaTeX.

**D-34. Several resume variants per job are allowed.** When more than one
framing could work, the agent may produce `resume_1`, `resume_2`,
`resume_3` (same for cover letters) in the job folder, each worded for a
different industry or angle, and the user picks. All variants pass the same
checks. This matters most for career changers, who need to speak to their
own industry and to the one they are moving into. The ledger records which
variant was actually sent. (Exact file naming to follow the profile-based
stem from D-08, e.g. `John_Smith_Resume_2.docx`.)

**D-35. The agent interviews the user to surface new facts, and only the
user's answers become facts.** Translating a bullet across industries often
needs a fact that is not written down yet. Worked example:

| Step | Content |
|------|---------|
| Stated fact | Rewrote a Python pipeline step in Rust; AWS RAM use down 97%. |
| Agent asks | What did that do to the pipeline's run time? |
| User answers | It roughly halved. |
| New fact | Pipeline run time cut ~50% (secondary effect of the rewrite). |
| Agent asks next | Did lower RAM or shorter runs save money? Roughly how much? |
| Translated bullet | "Improved operational efficiency by removing a bottleneck step, cutting process time 50%." |

Rules:
- The agent never infers a secondary effect and writes it down as fact
  ("less RAM must mean lower cost"). It asks, and the user's answer is what
  gets recorded.
- New facts are added to the atoms only after the user confirms them, so
  the D-32 check covers them like any other fact.
- **Ballpark figures are allowed** when the user knows them roughly, and
  are recorded as estimates.
- **Defensibility check:** for claims an interviewer is likely to probe
  (big numbers, cost savings, anything cross-industry), the agent asks the
  user to explain how they know it. If they cannot explain it, the claim is
  softened or dropped. The aim is that nothing on the resume makes the
  candidate bomb the interview.

### Follow-up (answered 2026-10-17). How are estimates stored and shown?
Proposed: (1) each fact records its basis and a "how I know" note, (2) the
fact check also enforces precision, (3) a per-job interview prep sheet built
from the notes.

> 1, 2, 3. Also note we should likely, depending on the stage, do HR or
> interview prep or both. Whatever is likely to be easier. Now we can one-shot
> things and add more questions than desired, but overall we want to sit
> around 5 good questions that invite a discussion. Note we should do XX%
> and never ~XX%, since that invites questioning.

**D-36. Every fact records its basis and a defense note.** Basis is one of
`measured`, `records`, or `estimate`. The defense note is the user's own
explanation of how they know, taken from the D-35 defensibility answers.

**D-37. Precision is checked, and numbers are stated plainly.** An
estimate is written as a clean round figure: "50%", "cut in half". Never
"~50%", "about 50%", or "roughly 50%" in a deliverable, since hedging
invites the question it tries to avoid. Never more precision than the basis
supports either: an estimate of "about half" may not appear as "49.7%". The
D-32 check enforces both.

**D-38. Per-job prep sheets, by stage.** The job folder gets a prep sheet
for the stage the user is at: an **HR / phone screen** sheet, an
**interview** sheet, or both, whichever is easier for that job. Each sheet
pulls the defense notes for every claim on the resume variant that was
actually sent (D-34), so "how did you get 50%?" always has an answer ready.

Each sheet aims for **about five good questions that invite discussion**.
The agent may generate more and trim, but the target is five strong ones
rather than a long list. *(Interpretation to confirm: these are questions
for the candidate to ask the interviewer. Likely questions the candidate
will be asked are covered by the defense notes.)*

### Q18. License?
> I would like a license which lets the everyman use the software for
> themselves, BUT corporations, if they do use it, need to explicitly
> disclose its use, with penalties or similar for non-attribution. Even if a
> license is close to that sort of legal verbiage, I am fine. "Free for
> personal, non-commercial use, BUT..."

**D-16.** Source-available: free for personal non-commercial use;
commercial use requires disclosure and attribution, with consequences for
non-compliance.

*Open items to settle before the first public commit:*
- A non-commercial restriction means the project will not meet the OSI
  definition of "open source". Docs should say "source-available" or
  "free for personal use" and avoid the "open source" label.
- Candidate starting points: PolyForm Noncommercial 1.0.0 with a separate
  commercial license that carries the disclosure and attribution terms, or
  a Business Source License variant. Penalty clauses should be reviewed by a
  lawyer.
- Contributors need a CLA or DCO that allows dual licensing, or the
  commercial terms cannot cover their code.

### Follow-up (answered 2026-10-17). Which license?
Options offered: (1) PolyForm Noncommercial plus a separate commercial
license carrying disclosure and penalty terms, (2) PolyForm Noncommercial
alone, (3) Business Source License.

> 2. This avoids siloing the project such that only two contributors are
> working, and honestly there are great people out there with great ideas. I
> can always use this as some sort of resume fodder, and that itself could
> be worth six figures.

**D-39. License: PolyForm Noncommercial 1.0.0, alone. This supersedes the
commercial-disclosure part of D-16.** There is no separate commercial
license and no attribution-penalty scheme. Reasons:
- A dual-license model needs every contributor to sign over relicensing
  rights (a CLA). That friction keeps a project down to its maintainers.
  Without it, contributions simply come in under the same license
  ("inbound = outbound").
- The project's value to the maintainers is as a public body of work and a
  portfolio piece, not license revenue.

Consequences:
- Commercial use is simply not permitted. Reselling Jobforge as a paid
  tailoring service is exactly what the license forbids.
- PolyForm Noncommercial already permits use by charitable organizations,
  educational institutions, public research and government institutions,
  so nonprofits, schools, and public job centers can use it to help people
  without asking.
- No CLA. Use a DCO sign-off (`git commit -s`) when PRs open, so each
  contribution has a clear record of who wrote it and that they had the
  right to submit it.
- Still not OSI "open source". Describe it as source-available or "free for
  personal and nonprofit use".

### Follow-up (stated 2026-10-17, during SOW audit pass 2). Employer mapping
> Also note, we need to make sure we are correctly mapping atoms that are
> job related to the appropriate employer.

**D-40. Every job-related atom is bound to the role it happened in, and
claims stay with their employer.** Moving a true fact to the wrong employer
is an invented fact under D-32, even though every number in it is real.
- Every bullet atom names its role (one role atom = one employer, title, and
  date range). An atom with no role, or an unknown one, fails to load.
- A project names its context: a role, or `personal`, `school`, or
  `volunteer`. A personal project is never presented as work for an
  employer.
- A bullet renders only under its own role. Today's private code only
  *warns* when a bullet sits under the wrong role (`validate.py`, the
  `startswith(rid + ".")` check); in Jobforge that is a hard failure.
- In prose (cover letters, emails, prep sheets), a sentence that names an
  employer may only carry facts from atoms bound to that employer.
- During setup, when an old resume is ambiguous about where something
  happened, the agent asks. A fact with no employer cannot be confirmed.

### Follow-up (answered 2026-10-17). SOW questions Q-1 to Q-8
> One subfolder per variant works. Answer the questions you need.

**D-41. Answers to the SOW's open questions** (`docs/SOW.md`, section 6).
Q-8 was answered directly. The rest were delegated ("answer the questions
you need") and take the SOW's recommendation. Any of them can be reopened
with a new dated entry.

| Q | Answer |
|---|--------|
| Q-1 | Atoms and profile are **TOML**, read with stdlib `tomllib`, written by a small in-house writer for the subset we emit. Satisfies D-33's "YAML or similar" and keeps the runtime stdlib-only (D-13). |
| Q-2 | Page fill is **estimated** from the template's line capacity, and checked against the real page count when PDF is on. The page limit is a **profile setting, default 1**. |
| Q-3 | Minimum **Python 3.11** (needed for `tomllib`). The setup guide says so. |
| Q-4 | The command is **`jobs`**, with `search` as an alias, so it is not mistaken for searching the internet. |
| Q-5 | The prep sheet's "about five questions" are **questions the candidate asks the interviewer**. Questions the candidate will be asked are covered by the defense notes (D-38). |
| Q-6 | **John Smith is separate** from the thirteen archetypes, deliberately plain so the walkthrough is not tied to one industry. Fourteen fixture personas in all. |
| Q-7 | **Open.** Phase ownership between Jesse and Mike is theirs to settle at kickoff. |
| Q-8 | **One subfolder per variant** (`variants/2/`), each holding clean-named files, so the file sent is always `John_Smith_Resume.docx`. |

**D-34 update (2026-10-17):** variant naming follows Q-8 above, replacing
the `John_Smith_Resume_2.docx` example.

### Follow-up (answered 2026-10-17). Phase ownership, repo home, prep questions
> The ownership of the phases will begin just prior to a 48-72hr sprint.
> That can still be pending. It can go under my own personal account.
> Questions candidates ask the interviewer is fine. We should also have
> expected questions from the interviewer as well.

- **Q-7 stays pending on purpose.** Jesse and Mike assign phases just
  before the first 48 to 72 hour sprint. It does not block preparation.
- **D-03 update: the repo lives under Jesse's personal GitHub account**,
  not a new organization. That avoids the existing "JobForge" org.
- **Q-5 confirmed:** the "about five" are questions the candidate asks the
  interviewer.

**D-38 update: prep sheets also list the questions the interviewer is
likely to ask.** Each comes with the candidate's material for answering it,
drawn from the defense notes and atoms. Sources, in order:
1. **The claims on the variant that was sent.** Every big number, cost
   saving, or cross-industry claim gets its "how did you get that?"
   question, answered from its defense note (D-36).
2. **The job description's requirements**, matched against the atoms.
   Where an atom covers a requirement, the sheet points to it.
3. **Gaps.** Where no atom covers a requirement, the sheet says so and
   asks the candidate to prepare an answer. It never writes one, since the
   answer would be an invented fact (D-32). The prep sheet is private to
   the candidate, so it may name gaps that the cover letter never would.
4. **Stage-specific standards.** The HR screen sheet covers questions like
   salary expectations, availability, and why the candidate is looking. The
   interview sheet leans on the claims and requirements. Anything the
   candidate has not answered in their atoms or profile (reason for leaving,
   for example) is marked `UNCONFIRMED`, never filled in.

### Follow-up (stated 2026-10-17). Project URLs and a full CV
> Also keep in mind for projects that contain some sort of live url we need
> to ensure that we always include the url. Additionally, as a nice to
> have, we should be able to generate a CV which is essentially all atoms
> (sans the atoms that are inherently rewords of other atoms).

**D-42. A project's live URL always goes with it.** If a project atom has
a URL (a live demo, a repo, a published page), every deliverable that
mentions the project shows it: resume, CV, and cover letter (the cover
letter check already exists in the private repo). The visible text is the
URL itself, not a label like "Demo", because a hyperlink's target is lost
when an ATS extracts text, and a label alone tells the reader nothing.
Enforced by reading the rendered `.docx` back to text and requiring the
URL, not by trusting the plan. Since a dead link is worse than none, an
optional command checks that project URLs still resolve; it runs on the
user's machine on request, never in tests (tests stay offline).

**D-42 update (2026-10-17): links are rechecked weekly, and a missing URL
is fine.**
> I think a dead link is worse than none, so there should be some check
> there at least every week or similar. Additionally I don't think we need
> to fail projects without links if there is no link in the database. Some
> projects are inherently without writeups or urls...

- **No URL, no check.** The URL rule only applies to a project whose atom
  has a URL. Plenty of projects have no demo, repo, or writeup, and they
  render normally.
- **A writeup link stays optional.** A project may also carry a
  `writeup_url`. The plan chooses whether to include it, but if it is
  included it gets the same link check.
- **Weekly recheck, with no scheduler.** Each link's last check result and
  date are stored in a cache file in the workspace. When `apply` is about to
  put a link in a deliverable and that link was last checked more than 7
  days ago (a profile setting), it checks it first. `jobforge links` runs
  the check on demand. No background task or OS scheduler is needed, so
  setup stays the same on Windows and Linux. Users who want a true weekly
  job can schedule `jobforge links` themselves.
- **A dead link blocks the render.** A not-found response (404 or 410) or a
  name that no longer resolves stops `apply` with a message. The user then
  fixes the URL or marks it dead (`url_status = "dead"`), which treats the
  project as having no URL. Silently dropping the link is not allowed,
  since that would quietly change a deliverable.
- **Unclear results only warn.** Many sites refuse scripted requests (403,
  429) or time out, and the user may be offline. Those results print a
  warning that the link could not be verified and do not block, since a
  link-checking failure should not stop someone applying.

**D-43. Full CV, as a nice to have.** A CV renders every atom: all roles,
all bullets, all projects (with URLs, per D-42), the full education record,
publications, and credentials. It has no page limit. Atoms that only
reword another atom are left out, so each fact appears once. To make that
possible:
- Different wordings of one fact belong in one atom as phrasings (D-33),
  so most rewording never creates a second atom.
- When a separate atom does restate another (a summary line repeating a
  bullet, for example), it carries a `reword_of` field naming the original.
  The CV skips it.
- The loader warns when two atoms state the same facts and neither is
  marked, so undeclared rewords get caught.

The `reword_of` field is in the schema from the start, so atoms written
before the CV command exists already carry it. The command itself comes
after 1.0.

### Q19 / Q20. Employer IP
> [Employer A] I specifically carved out this tool.
> [Employer B] No, it is not.

**D-17, D-18.** Cleared. The tool is carved out of employer A's agreement,
and no code comes from employer B's work, time, or equipment. Employer names
are kept out of this repo.

---

## 7. Governance and maintenance

### Q21. Maintainer time and PRs?
> I have one more contributor, Mike Wilson, who will roughly split the time
> with me. BUT I am open to PRs and contributing, as it can make this tool far
> better. With the caveat that we heavily invest in AI-based regression
> tooling: before/after resume and cover letter comparisons, ATS scoring,
> etc. We can carve out the PR stuff right now, but we won't be accepting
> until we have that infra imagined.

**D-19.** Two maintainers, split roughly evenly. External PRs are welcome
in principle but closed until a regression harness exists that can:
- produce before/after diffs of rendered resumes and cover letters across
  the D-09 personas,
- score ATS parseability (e.g. `.docx` text round-trip, keyword coverage),
- flag quality regressions automatically.

CONTRIBUTING.md can be written now, saying exactly this.

### Q22. Relationship to the private repo?
> That is outside the scope. That is a personal nice to have. For now, we
> just want to have our base covered, in which we have this functionality
> for John Smith.

**D-20.** Out of scope. The private `jobs` repo is not migrated onto this
one as part of the SOW.

---

## 8. Timeline and phasing

### Q23. Target date?
> No firm target date. But the sooner I open source this, the sooner society
> won't get fleeced by these overnight resume companies. And Anthropic gets
> money from Claude Code usage. We both win, really.

**D-21.** No date. Prioritize a shippable launch over polish.

### Q24. Phasing?
> Deliverable is primarily the target. We will want an X.x format and make
> sure we have qualifying tests before making an X jump.

**D-22.** Phases are defined by deliverables. Versions use `X.x`. Moving
from X to X+1 requires a defined set of qualifying tests to pass, and each
major version's qualifying suite is written down before work on it starts.

---

## Open items

1. ~~Project name (D-03).~~ Resolved: Jobforge. Rename the folder from
   `the old working folder` to `jobforge`, and reserve the PyPI name.
2. ~~Tenth archetype persona (D-09).~~ Resolved: thirteen personas.
3. ~~New meaning for `search` without a scraped corpus (D-06).~~ Resolved:
   D-27 through D-29. The name (`search` vs `jobs`) is still open.
4. ~~PDF required vs optional; swappable templates (original Q15).~~
   Resolved: D-23 through D-26.
5. ~~License text, commercial terms, and CLA/DCO (D-16).~~ Resolved: D-39.
6. ~~Written definition of "critical path" for the coverage gate (D-15).~~
   Resolved: D-30 through D-32.
7. ~~Atom data model: how one fact carries several phrasings (D-32).~~
   Resolved: D-33 through D-35.
8. ~~How estimates are recorded and shown (follows D-35).~~ Resolved:
   D-36 through D-38.
9. ~~SOW questions Q-1 to Q-8.~~ Resolved: D-41. Q-7 (phase ownership)
   is deliberately pending until just before the first 48-72 hour sprint.

---

## Session 2026-11-06: repos, scraper, report

Decided by Jesse Anderson, with the repo layout delegated ("your call for
whatever is the most tidy"). Supporting documents: `docs/COMPONENTS.md`
(vocabulary and repos) and `docs/MVP.md` (proposed MVP, not yet accepted).

### Repos
> Create/define the canonical repos: the official soon-to-be home for the
> open-source public repo and all behind-the-scenes repos for operational
> clarity. First active development in private, then open source.

**D-44. One product repo, one private ops repo, and `jobs` as it is.**
- `jesse-anderson/jobforge` holds the engine, the agent layer, and the
  report. Private during development; the same repo goes public at launch
  after T-PII runs over its whole history (a squashed fresh history if that
  finds anything).
- `the maintainers' private notes` is permanently private: reviews of the
  private repos, sprint notes that mention real searches, blog drafts.
- `the earlier tool` keeps the scraper, dashboard, and both maintainers'
  real applications. Its history is never made public.
- Not split into engine / agent / UI repos, because the agent files and the
  report both have to ship inside the PyPI package (`init` writes the agent
  files; the engine generates the report), and separate repos would let the
  agent instructions drift from the `plan.json` schema they describe.
- The folder was copied from `the old working folder` to `jobforge` on 2026-11-06 (the
  rename itself was blocked by a lock on the old folder; delete
  `the old working folder` once nothing has it open).

### Scraper
> Scraper is deferred to another sprint / project. Jobforge / Job apps will
> give 80% of the functionality for 20% of the work. There's also legal
> liability in FOSS scrapers and enabling targeting agentic attacks on job
> boards (10 agents each hammering a board * 10,000 people = cloud bills =
> monetary damages). That isn't to say that I'm not amenable to OUR job
> board being worked on.

**D-45. The scraper stays out of Jobforge (D-04), for two more reasons:**
shipping scrapers for boards we do not own is a legal exposure, and a
public, agent-driven scraper multiplies traffic against those boards by the
number of users, which is someone else's cloud bill and a damages claim.
Scraper work is its own sprint in `jobs`. A job board that we run is a
separate idea Jesse is open to; it is not scheduled and would need its own
answer to D-25 (no hosted service).

Boundary this implies for intake: reading **one** posting the user handed
us, including from a known ATS's structured feed, is intake. Listing **all**
postings on a board is scraping, and does not ship.

### Report
> UI is deferred as a "nice to have". More likely than not, a rendered
> static site that can be opened by the agent for metrics like jobs applied
> to, "velocity" (jobs applied to per day over time), call back rate, etc.
> See Sankey diagram.

**D-46. The report is deferred past the MVP**, and will be a static page the
engine generates into the workspace, opened from disk: applications to date,
velocity, callback rate, and a Sankey of outcomes. Constraints are in
`docs/COMPONENTS.md` (no Node for users, works from `file://`, no CDN, local
dates). Deferring the page does not defer its data: the ledger records dated
events from the MVP onward, since a chart cannot be built from history that
was never written down.

### MVP questions (answered 2026-11-06)
Answers to the open questions in `docs/MVP.md`, which is now accepted.

> M-1 the mvp is the moment the repo goes public. m-2 I am fine with the
> chatbot being a lesser version or shipping as a claude skill. m-3 I am
> fine with ghost after 30 days. m4 Yes. m5 we can go back and forth, but
> less dependencies the better so maybe pure js / css / html to avoid build
> steps... m6 job apps means the whole workstream.

**D-47. The MVP in `docs/MVP.md` is accepted, and it is the public launch.**
- **M-1:** the repo goes public when the MVP gate passes, as a `0.x` preview
  release. 1.0 keeps the full SOW qualifying suite (section 5.10).
- **M-2:** a chatbot path is welcome as a lesser version, or shipped as a
  Claude Skill. It is not part of the MVP gate. The workspace stays one
  self-contained folder so it remains possible.
- **M-3:** ledger stages as listed in MVP.md; `ghost_after_days = 30`.
- **M-4:** `jobforge check <job>` is added: validate and fact-check without
  writing deliverables.
- **M-5:** the report is plain HTML, CSS, and JavaScript with no build step,
  as a starting position. Fewer dependencies is the rule; the details stay
  open between the maintainers.
- **M-6:** "Job Apps" is the name of the whole workstream: Jobforge plus the
  behind-the-scenes repos.

### Commits (stated 2026-11-06)
> Whenever a commit needs to be done it is done by mike or jesse, never by
> AI and at best the AI gives the commit message sans created with Claude or
> similar.

**D-48. Only the maintainers commit.** An AI agent never runs `git commit`
(or anything that creates a commit, such as a merge or rebase) in any of the
project's repos. At most it proposes a commit message, which carries no
"Generated with" or "Co-Authored-By" attribution lines. The maintainer
reviews the change and commits it under their own name.

### Copyright and contributions (stated 2026-11-06)
> Does the license cover contributors?

Answered: the license covers users, not contributions coming in. Asked to
make the contribution terms explicit and record who holds the copyright:
> Make those fixes and put the line in.

**D-49. The maintainers hold the copyright jointly; contributions come in
under the project license.**
- Jesse Anderson and Mike Wilson are joint copyright holders of Jobforge,
  as the `Required Notice` line in `LICENSE` states. Changing the license,
  or offering the code under any other license, needs both to agree.
- An outside contributor keeps the copyright in what they write. By
  submitting it they license it under PolyForm Noncommercial 1.0.0 and
  certify the DCO with a sign-off (`CONTRIBUTING.md`). There is no CLA
  (D-39).
- Consequence: relicensing later needs every contributor's agreement or a
  rewrite of their code. Settle any commercial plan before outside PRs open
  (D-19).
- The DCO's phrase "the open source license indicated in the file" is read
  as this project's license.

### Rounding (stated 2026-11-06)
> I think claiming less is ok, better to be loose or hell even round down
> when it comes to saving money or be conservative overall.

**D-50. Claim less, never more; rounding is the user's call, made once.**
- A figure may be written with less precision than its atom, as long as the
  value is the same: "76%" for a confirmed "76.0%". It may never be written
  with more ("76.00%", "$1.20M" for "$1.2M"). The fact check enforces both
  (#11, #26).
- Rounding that changes the number ("$36k" for "$36,753") stays refused by
  the check. Whether rounding down is conservative depends on what the
  number measures: down is safe for money saved or units shipped, and an
  overclaim for downtime, cost, or a defect rate. Code cannot tell which, and
  guessing is what the check exists to prevent.
- Instead, the user confirms the rounded form once, as a phrasing on the
  atom. It then passes everywhere, and the rounding was the user's choice.
  During setup the agent offers a plain rounded form for long or exact
  figures ("Want this recorded as $36k too?"), rounding in the conservative
  direction for what the figure measures.
