# The workspace format

Every file Jobforge reads or writes in a workspace, and every field in it.
This is format 1, the format of every workspace from 0.1.0 on. The rule for
changing it is D-53 in `DECISIONS.md`.

Each field is one of:

- **stable**: Jobforge needs it. Renaming it, removing it, or changing what
  it means is a format change.
- **optional**: may be left out, and has a default. Renaming or removing it
  is a format change too, since Jobforge refuses unknown names and a
  workspace that uses the old name would stop loading. Leaving it out never
  is a change.
- **internal**: Jobforge's own working state, free to change in any release.

A format change bumps the number in the marker and ships with a migration in
`jobforge init --refresh`. Adding an optional section or field, with a
default, is not a format change: an older Jobforge refuses the new name with
an "unknown section" or "unknown key" error, and updating Jobforge fixes it
(D-53).

```
<workspace>/
  .jobforge                 the marker (stable)
  CLAUDE.md, AGENTS.md      generated agent instructions (internal)
  profile/
    profile.toml            the user's profile (stable)
    atoms/*.toml            confirmed facts (stable)
    pending/*.toml          drafted facts awaiting `confirm` (stable)
  intake/                   the user's own files; Jobforge only reads them
  jobs/
    <company>__<title>__<YYYY-MM-DD>/
      job.json              the posting (stable)
      plan.json             the agent's choices (stable)
      ledger.toml           dated events (stable)
      check.json            last check result (internal)
      cover_letter.md       working file (internal)
      <Name>_Resume.docx    deliverables; Jobforge never reads them back
      <Name>_Cover_Letter.docx
```

All text files are UTF-8. A byte-order mark is accepted on read.

## The marker: `.jobforge`

TOML. Its presence is what makes a folder a workspace; every command walks
up from the current folder to find it.

- `format = 1` (stable): the workspace format. A marker with no `format`
  line is format 1: 0.1.0 and 0.1.1 wrote none. `init --refresh` adds it. A
  higher number than this Jobforge reads stops every command with "This
  workspace needs a newer Jobforge". Jobforge 0.1.0 and 0.1.1 do not read the
  line, so they fail on whatever they do not recognize instead.
- `created` (internal): the date `init` ran.
- `created_by` (internal): the Jobforge version that ran `init`.

## `profile/profile.toml`

TOML, written by `init` and then edited by the user or their agent. An
unknown section or key is refused.

- `[person]`
  - `name` (stable): printed on the resume and letter, and the source of the
    file names.
  - `email`, `phone`, `location` (optional): text, default empty.
  - `links` (optional): a list of full URLs.
  - `file_stem` (optional): the file name stem when `name` has no Latin
    letters (D-52).
- `[settings]`
  - `page_limit` (optional): resume pages, default 1.
  - `cover_letter_max_words` (optional): default 300.
  - `ghost_after_days` (optional): days with no reply before an application
    shows as ghosted, default 30.
- `[voice]`
  - `add_banned_words`, `allow_words`, `add_banned_phrases` (optional):
    lists of text, added to or taken from the built-in list.
  - `ban_dashes` (optional): true or false, default true.
- `[claims]`
  - `never_claim` (optional): tools, skills, or credentials the user does
    not have.

## Atoms: `profile/atoms/*.toml` and `profile/pending/*.toml`

TOML, as arrays of tables, one per kind: `[[role]]`, `[[bullet]]`, and so on.
Any number of files; the file name is free. The same fields in both folders:
`confirm` moves an atom from `pending/` to `atoms/`. Every atom has an `id`
(stable): lowercase letters, digits, `_`, `.`, and `-`, unique across the
workspace. An unknown field is refused.

Dates are text, `"YYYY"` or `"YYYY-MM"`; `end` may also be `"present"`.
`basis` is `"measured"`, `"records"`, or `"estimate"`.

- `[[role]]`: a job the user held.
  - stable: `id`, `employer`, `title`, `start`.
  - optional: `end`, `location`, `notes`, `aliases` (other names for the
    employer), `title_aliases` (other titles the user confirmed, #89).
- `[[bullet]]`: one fact about the user's work.
  - stable: `id`, `text`, `basis`.
  - optional: `role` or `project` (the id it belongs to, D-40), `defense`
    (how the user knows it), `facts` (extra figures or terms the line may
    state), `phrasing`, `reword_of` (the id this rewords), `tags`.
- `[[project]]`: something the user built outside a job, or inside one.
  - stable: `id`, `title`, `context` (`"personal"`, `"school"`, or
    `"volunteer"`).
  - optional: `text`, `url`, `writeup_url`, `url_status` (only `"dead"`),
    `basis`, `defense`, `facts`, `phrasing`, `reword_of`, `tags`.
- `[[skill]]`: a labeled group of skills.
  - stable: `id`, `label`, `items` (a list).
  - optional: `tags`.
- `[[credential]]`: a license or certificate.
  - stable: `id`, `name`.
  - optional: `issuer`, `date`, `expires`, `tags`.
- `[[education]]`
  - stable: `id`, `school`, `credential`.
  - optional: `field`, `date`, `location`, `details`, `tags`.
- `[[summary]]`: a resume summary.
  - stable: `id`, `text`.
  - optional: `basis`, `defense`, `facts`, `phrasing`, `reword_of`, `tags`.

`phrasing` is written as `[[<kind>.phrasing]]` entries under the atom, each
with `text` (stable) and optional `use` (`"resume"`, `"cover"`, `"email"`,
or `"any"`, the default) and `industry`.

## `jobs/<folder>/job.json`

JSON, one object, written by `prepare` or `import`. The folder name is
`<company>__<title>__<YYYY-MM-DD>`, plain ASCII (D-52); Jobforge finds jobs
by their `job.json`, not by the name, so a renamed folder still works.

- `company`, `title`, `description` (stable): the posting.
- `url`, `location` (optional): text, default empty.
- `source` (internal): how the posting was read: `"json-ld"`, `"page-text"`,
  or `"manual"`.
- `imported` (optional): the date `import` made the job, as
  `"YYYY-MM-DD"`. A job with it came from the user's tracker and has no
  posting text.

## `jobs/<folder>/plan.json`

JSON, written by the agent for each job and checked by `check` and `apply`.
It carries its own version, `"version": 1`, separate from the workspace
format: the agent writes a fresh plan for every job, so the plan can change
on its own schedule. Workspace format 1 reads plan version 1. An unknown key
is refused. The full shape is in the docstring of `src/jobforge/plan.py`.

- `version` (stable): 1.
- `cover_letter` (stable): `hook`, `body`, `close`, and `cites`.
- `summary`, `experience`, `projects`, `skills`, `credentials`, `education`
  (optional): which atoms the resume uses, in order, with any rewordings.
- `fit`, `gaps`, `notes` (optional): for the user; never rendered.

## `jobs/<folder>/ledger.toml`

TOML, appended to and never rewritten. One `[[event]]` per thing that
happened to the application.

- `date` (stable): a TOML date, `2026-11-20`, with no quotes.
- `stage` (stable): one of `prepared`, `applied`, `skipped`, `screen`,
  `interview`, `offer`, `accepted`, `declined`, `rejected`, `withdrawn`.
  "Ghosted" is never stored; `jobs` works it out.
- `note` (optional): text.

## Internal files

Free to change in any release, so nothing outside Jobforge should read them.

- `CLAUDE.md` and `AGENTS.md`: rewritten by `init --refresh`, which keeps
  anything below the notes line and backs up any other edit (#33).
- `check.json`: the result of the last `check`, for the agent.
- `cover_letter.md`: the letter as a working file, with its cites.
- `<id>.editing` in `profile/pending/`: `confirm`'s temporary file while the
  user edits an atom.
