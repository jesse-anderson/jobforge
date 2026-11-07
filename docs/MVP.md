# MVP definition

- **Status:** accepted 2026-11-06 (D-47). **The MVP is the public launch**,
  released as a `0.x` preview. Answers to the open questions are at the
  bottom.
- **Reads with:** `docs/COMPONENTS.md` for vocabulary, `docs/SOW.md` for the
  full road to 1.0.

The SOW defines 1.0: thirteen personas, variants, prep sheets, PDF, an
index, link checking, a guided setup with images, and a 100% / 80% coverage
gate. That is the right finish line and too far away to be the first thing
anyone uses. The MVP is the smallest Jobforge that does the job a person
would otherwise pay a resume site for, with the one promise that makes it
worth using instead: **it never states a fact you did not give it.** Roughly
80% of the value for 20% of the work.

---

## 1. Problems the MVP solves

1. **Tailoring costs money.** Resume tailoring sites charge a subscription to
   people who are, by definition, looking for income. Jobforge is free and runs
   on the user's machine (D-25).
2. **AI tailoring invents things.** Paste a resume into a chatbot and ask for
   a tailored version, and numbers drift, tools appear that the person never
   used, and achievements move between employers. The candidate then gets
   asked about them in an interview. Jobforge checks every fact mechanically
   against what the user confirmed (D-32, D-40).
3. **The output gets mangled by the ATS.** Jobforge always produces a `.docx`
   built for text extraction, and reads it back to prove what a parser will
   see (D-23, D-31).
4. **Nobody remembers what they sent where.** Every application leaves a
   folder with the posting, the plan, and the exact files sent, plus a ledger
   entry with dated status changes.

## 2. Problems the MVP does not solve

| Not solved | Why | When |
|---|---|---|
| Finding jobs automatically | No scraper, by design (D-04, D-45). The agent may look for postings on request, and they still enter through `prepare`. | Never as a scraper |
| Seeing the search over time (charts, velocity, Sankey) | The report is deferred (D-46). **The data it needs is recorded from day one**, so nothing is lost. | After MVP |
| Several framings per job | Variants (D-34) | 1.0 |
| Interview and HR prep | Prep sheets (D-38) | 1.0 |
| PDF | Needs Tectonic, the biggest setup cost (D-23) | 1.0 |
| Copy-paste text for application forms | `ats --form`. High value, but needs the profile's form extras | First after MVP |
| Checking that project links are alive | Network check (D-42). The MVP still requires a project's URL to appear in the document. | 1.0 |
| Users without a terminal agent | A lesser chatbot version or a Claude Skill is welcome (M-2), but does not gate the MVP | After MVP |

---

## 3. What the user does (exact behavior)

This is the acceptance script. The MVP is done when a person who is not a
maintainer can do all of it on Windows or Linux from the README alone.

**Setup, once.**

1. `pip install jobforge` (or clone and run `python -m jobforge`). Python
   3.11+.
2. `jobforge init ~/jobsearch`. Creates the workspace: `profile/`,
   `profile/pending/`, `intake/`, `jobs/`, a marker file, and generated
   `CLAUDE.md` and `AGENTS.md`. Running any other command outside a workspace
   fails with a message saying to run `init`. It never guesses.
3. User drops an old resume (`.docx`, `.pdf`, `.txt`, or pasted text) into
   `intake/`, opens their agent in the workspace, and says something like
   "set me up".
4. The agent reads the intake and writes **pending** atoms: roles with
   employer, title, and dates; bullets bound to a role; skills; education.
   Where the old resume is unclear about which job something happened at, it
   asks (D-40). It does not write live atoms.
5. User runs `jobforge confirm`. For each pending fact it shows the fact, its
   employer and role, its basis, and its defense note, and asks keep / edit /
   drop. Only kept facts become live. A job-related fact with no role cannot
   be kept.

**Per job.**

6. User gives the agent a posting URL or pastes the description. The agent
   runs `jobforge prepare --from-url <url>` or `--from-text <file|->`. This
   writes `jobs/<company>__<title>__<date>/job.json`. If the page blocks
   scripted requests, `prepare` says to paste the text instead. If the
   company comes out looking like a domain (`google.com`) or the title still
   carries the site's suffix, `prepare` stops and asks for `--company` /
   `--title` (FINDINGS F23, F27).
7. The agent writes `plan.json` in that folder: which atoms, in what order,
   what wording, and the cover letter. It may ask the user questions to
   surface a missing fact; any new fact goes to pending and through
   `confirm` first (D-35).
8. The agent runs `jobforge check <job>`. This validates the plan and runs
   the fact check without rendering, and prints every problem with the line
   it came from. The agent fixes the plan and repeats.
9. The agent (or user) runs `jobforge apply <job>`. It re-runs the checks; if
   anything fails, **no files are written**. If it passes, it writes
   `First_Last_Resume.docx`, `First_Last_Cover_Letter.docx`, and the working
   `cover_letter.md`, then reads both `.docx` files back as text and checks
   them again (hidden characters, project URLs present, facts unchanged).
10. User reads the documents and submits them themselves. Jobforge never
    submits anything.
11. `jobforge applied --mark <job> --status applied`. Later, as things
    happen: `--status screen`, `--status interview`, `--status rejected`,
    and so on, each with an optional `--date` and `--note`.
12. `jobforge jobs` lists every job with company, title, current status, and
    last date, filterable by status and company. (`search` is an alias.)

### What the fact check enforces in the MVP

All of it is code. None of it depends on the agent behaving.

- Every number, percentage, money figure, date, and duration written in
  digits, and every employer, credential, and tool the inventory knows,
  appears in a confirmed atom the plan cites (D-32). What this leaves out is
  under "Known limits of the fact check" below.
- A bullet renders only under its own role. A sentence in the cover letter
  that names an employer carries only facts from that employer's atoms or the
  profile (D-40). The sentences after it in the same paragraph that name no
  employer may not use another employer's facts (#83).
- The posting's figures and tools appear in the letter only in a sentence
  about the employer ("you", "your", or its name) with no "I", "my", or
  "we": "Your 6 sites" passes, "I bring 20 years" does not when only the
  posting says 20 (#83).
- No hedged figures ("~50%", "about 50%", "roughly") and no precision beyond
  the basis ("49.7%" from an estimate of "half") (D-37).
- Nothing on the profile's never-claim list.
- A project with a `url` shows the **full URL** as visible text wherever the
  project is mentioned. Matching the host or a path segment is not enough
  (FINDINGS F22).
- One number for the cover-letter word limit, in the profile, read by both
  the validator and the generated agent instructions, so they cannot disagree
  (FINDINGS F19).
- Text quoted from the posting (the job title in a "Re:" line) is exempt from
  the user-voice rules such as the dash ban, so a posting's own en dash does
  not block the render (FINDINGS F21).
- Resume page fill is estimated against the profile's page limit and
  **warns**; it does not block until PDF gives a real page count.

### Known limits of the fact check

Found in the audit (#1), rechecked 2026-11-07. These pass `jobforge check`
today, so the agent's instructions and the user's own read of each
deliverable still matter.

- **Figures written in words** ("thirty-five percent", "a team of forty",
  "tripled") are not read as figures (#84).
- **Job titles are not checked.** A line can carry another role's title or
  an invented one (#89).
- **Unknown names.** An employer, credential, or tool that appears nowhere in
  the inventory or the never-claim list cannot be told apart from an ordinary
  word, so it is not caught. Only names Jobforge already knows are checked.
- **Short names and synonyms.** An employer written by a short name or an
  abbreviation binds to its role only when recorded as an alias on the role
  (#22). A synonym of a known term ("Postgres" for "PostgreSQL") is a
  different term. Hyphen, slash, and spacing variants ("Black-Belt" for
  "Black Belt") do match.
- **Pronouns across paragraphs.** Within a paragraph, a sentence that names
  no employer is read as the last one named ("There I also..."). One that
  refers back to an employer from an earlier paragraph is checked against
  every cited fact (#83, #90).
- **The posting's figures in the letter.** A sentence about the employer
  that also claims something for the user without "I", "my", or "we"
  ("Your team of 20 would get a lead with 20 years on the floor") may still
  quote the posting (#83).
- **Some hedges pass:** "close to 25%", "25%+" (#91).

### What the ledger records

The report is deferred, but the report can only chart what was recorded, so
the ledger records events, not just a current status:

```toml
[[event]]
date = 2026-11-20
stage = "applied"

[[event]]
date = 2026-12-02
stage = "screen"
note = "recruiter call, 30 min"
```

Stages: `prepared`, `applied`, `skipped`, `screen`, `interview`, `offer`,
`accepted`, `declined`, `rejected`, `withdrawn`. Repeats are allowed
(several `interview` events are rounds 1, 2, 3). **Ghosted is computed, not
entered:** an `applied` job with no later event after `ghost_after_days`
(profile setting, default 30).

From that, every metric the report will show is derivable later:
applications per day (velocity), callback rate (share of applied jobs that
reach `screen` or beyond), time to first response, and the outcome Sankey.
`ghost_after_days = 30` is confirmed (M-3); the other metric definitions are
Jesse's to confirm when the report is built.

---

## 4. What the end product looks like

A single folder the user owns. Nothing outside it, nothing on a server.

```
jobsearch/
  .jobforge                 workspace marker
  CLAUDE.md                 generated; do not edit
  AGENTS.md                 generated; do not edit
  profile/
    profile.toml            name, contact, voice rules, page limit
    atoms/*.toml            confirmed facts
    pending/*.toml          agent drafts awaiting `confirm`
  intake/                   old resumes and samples
  jobs/
    acme__process_engineer__2026-11-20/
      job.json              the posting
      plan.json             the agent's choices
      check.json            last check result
      John_Smith_Resume.docx
      John_Smith_Cover_Letter.docx
      cover_letter.md       working file, never sent
      ledger.toml           dated events for this job
```

Ledger events live in each job folder, so the folder is the whole record of
one application and `jobs` is a scan of the folders (fast enough at MVP
scale; the index from D-29 comes with 1.0). This differs from the private
repo, which keeps one central ledger file and has to merge human
fields back in on every rebuild. With the events in the folder there is
nothing to merge and nothing to lose.

The commands, all of them:

| Command | Does |
|---|---|
| `jobforge init <dir>` | Make a workspace, write agent files |
| `jobforge confirm` | Review pending facts; keep / edit / drop |
| `jobforge inventory` | List confirmed atoms (for the agent and the user) |
| `jobforge prepare --from-url / --from-text` | Capture a posting into a job folder |
| `jobforge check <job>` | Validate plan and fact check, write nothing else |
| `jobforge apply <job>` | Check, then render deliverables |
| `jobforge applied --mark <job> --status <stage>` | Record an event |
| `jobforge jobs` (`search`) | List jobs and status |

Agent layer in the MVP: one canonical source generating `CLAUDE.md` and
`AGENTS.md` (others later), covering the setup interview, fact interviews,
plan writing, the check-and-fix loop, and finding postings on request. One
agent, no delegation, no hooks required.

---

## 5. MVP gate

Mapped onto the SOW, the MVP is roughly phases 0.1 to 0.4 plus the
`confirm` and generated-instructions parts of 0.7 and the ledger events from
0.6. It is done when:

1. **The acceptance script in section 3 passes for John Smith and three
   archetypes**: trades, entry level, and career changer. Those are the three
   the SOW expects to break the atom model (thin inventory, non-engineering
   wording, cross-industry translation).
2. **Critical paths at 100% coverage**: intake, plan validation, fact check,
   employer binding, rendering, ledger. The 80% bar for everything else stays
   a 1.0 gate.
3. **A planted-violation suite** fails with the right message for each:
   changed number, added money figure, hedged figure, false precision, fact
   moved to another employer, never-claim tool, missing project URL, URL
   present only behind a label.
4. **Every `.docx` reads back clean**: no zero-width characters, soft hyphens,
   stray non-breaking spaces, or control characters (D-31 subset).
5. **T-PII, T-STD, T-XPLAT** pass (SOW section 4).
6. **One real person who is not a maintainer** goes from install to a
   submitted application with only the README, and their friction log is
   either fixed or documented.
7. The VM checklist runs once on each OS before the release is published.
8. T-PII runs over the repo's **whole history**, not just the latest
   commit, since passing this gate makes the repo public (D-44). If it
   finds anything, the public repo gets a squashed fresh history.

### Build status (2026-11-06)

| Gate item | State |
|---|---|
| 1. Acceptance script, John Smith + trades, entry level, career changer | **Automated and passing** (`tests/test_personas.py`), from `prepare` to read-back. The agent half (setup interview, plan writing) is still a manual run. |
| 2. Critical paths at 100% | Overall 99% line and branch coverage, every module 97% or higher. A separate critical-only number is not computed yet (tests are marked `critical`). |
| 3. Planted-violation suite | **Passing** (`tests/test_factcheck.py`, plus one planted violation, one never-claim, and one employer swap per persona). |
| 4. `.docx` reads back clean | **Passing.** `apply` itself reads every document back and refuses to finish if text is lost or a hidden character appears. |
| 5. T-PII, T-STD, T-XPLAT | T-STD passing. T-PII written; skips until a maintainer supplies the denylist. T-XPLAT waits on CI, which needs the GitHub remote. |
| 6. A real non-maintainer, README only | Not started. |
| 7. VM checklist once per OS | Draft in `docs/VM_CHECKLIST.md`; not run. |

Also still needed before the public flip: the `LICENSE` file (official
PolyForm Noncommercial 1.0.0 text), and the D-17/D-18 employer names out of
DECISIONS.md and SOW.md.

---

## 6. Questions, answered 2026-11-06 (D-47)

| # | Question | Answer |
|---|---|---|
| M-1 | Is the MVP the moment the repo goes public? | **Yes**, as a `0.x` preview release. 1.0 keeps the SOW's full suite. PRs stay closed either way (D-19). |
| M-2 | The "chatbot" path: a plain chat app whose code sandbox installs and runs Jobforge. | **Welcome as a lesser version, or as a Claude Skill.** Not part of the MVP gate. Chat sandboxes are wiped after each session, so the workspace stays one self-contained folder the user can keep and re-upload. |
| M-3 | Ledger stages and the ghosted threshold. | As listed in section 3; `ghost_after_days = 30`. |
| M-4 | Add `jobforge check`. | **Yes.** |
| M-5 | Report technology. | **Plain HTML, CSS, and JavaScript, no build step**, as a starting position. Fewer dependencies is the rule; details stay open between the maintainers. |
| M-6 | What "Job Apps" means. | **The whole workstream**: Jobforge plus the behind-the-scenes repos. |
