"""`jobforge import`: bring past applications into the ledger (issue #8).

For someone arriving mid-search with a tracker of their own. Each CSV row
becomes a job folder holding a `job.json` marked as imported and a
`ledger.toml` with the user's own dates. Nothing else: Jobforge did not
prepare, plan, or render these applications, so an import records only what
happened and never fabricates evidence (no plan, no resume, no `prepared`
event, no guessed date).

Lessons from importing a real tracker by hand in the private repo:
- Preview first. Reading the preview caught mistakes no validator would, so
  `plan_import` writes nothing and the CLI only writes on `--write`.
- Never make a date up or more exact than given. Dates are YYYY-MM-DD; "9/1"
  and "~09-01" are errors, and a later status ("rejected") needs its own date.
- A row with no applied date is a lead, not an application.
- The same company and title in two cities are two jobs, so duplicates are
  matched by URL, or by company, title, and location together.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import re
from dataclasses import dataclass, field

from .errors import JobforgeError
from .extract import Job
from .ledger import RECORDABLE, Event, append_event, job_folders
from .prepare import folder_name, read_job, slug
from .workspace import Workspace

# Accepted header spellings, compared lowercase with spaces and underscores
# folded, so "Date Applied", "applied_date", and "Applied Date" all work.
COLUMNS: dict[str, tuple[str, ...]] = {
    "company": ("company", "employer"),
    "title": ("title", "role", "position", "job title"),
    "location": ("location", "city"),
    "url": ("url", "link", "posting", "posting url", "job url"),
    "applied": ("applied", "applied date", "date applied", "applied on", "applied at"),
    "status": ("status", "stage"),
    "status_date": ("status date", "outcome date", "stage date"),
    "notes": ("notes", "note"),
}
REQUIRED = ("company", "title", "applied")
# "prepared" is something Jobforge does, so it cannot have happened before
# Jobforge. "ghosted" is computed (D-47), so it imports as "applied".
STATUSES = RECORDABLE + ("ghosted",)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class ImportRow:
    line: int
    company: str
    title: str
    action: str = "new"       # "new" | "duplicate" | "error"
    message: str = ""
    folder: str = ""
    events: list[Event] = field(default_factory=list)
    job: dict = field(default_factory=dict)


@dataclass
class ImportPlan:
    rows: list[ImportRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def count(self, action: str) -> int:
        return sum(1 for r in self.rows if r.action == action)


def _header_map(header: list[str]) -> tuple[dict[str, int], list[str]]:
    lookup = {alias: name for name, aliases in COLUMNS.items() for alias in aliases}
    index: dict[str, int] = {}
    unused: list[str] = []
    for i, raw in enumerate(header):
        key = re.sub(r"[\s_]+", " ", raw.strip().lower())
        name = lookup.get(key)
        if name and name not in index:
            index[name] = i
        elif key:
            unused.append(raw.strip())
    return index, unused


def _date(value: str, label: str, today: _dt.date) -> _dt.date:
    try:
        if not DATE_RE.match(value):
            raise ValueError
        day = _dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} {value!r} must be written YYYY-MM-DD") from None
    if day > today:
        raise ValueError(f"{label} {value} is in the future")
    return day


def _events(cell: dict[str, str], today: _dt.date) -> list[Event]:
    """The ledger events one row stands for. Raises ValueError with a message
    for the user."""
    status = cell["status"].lower() or "applied"
    if status not in STATUSES:
        raise ValueError(f"unknown status {cell['status']!r}; use one of: "
                         f"{', '.join(STATUSES)}")
    if not cell["applied"]:
        raise ValueError("no applied date. A row without one is a lead, not an "
                         "application; leave it out or add the date")
    applied = _date(cell["applied"], "applied date", today)
    note = cell["notes"]
    if status in ("applied", "ghosted"):
        return [Event(applied, "applied", note)]
    later = _date(cell["status_date"], "status_date", today) if cell["status_date"] else None
    if status == "skipped":
        return [Event(later or applied, "skipped", note)]
    if later is None:
        raise ValueError(f"status {status!r} needs the date it happened, in a "
                         f"status_date column. Jobforge does not guess it; or "
                         f"import the row as applied and record the rest with "
                         f"`jobforge applied`")
    if later < applied:
        raise ValueError(f"status_date {later} is before the applied date {applied}")
    return [Event(applied, "applied", ""), Event(later, status, note)]


def plan_import(ws: Workspace, text: str, *,
                today: _dt.date | None = None) -> ImportPlan:
    """Read a tracker CSV and decide what each row becomes. Writes nothing."""
    today = today or _dt.date.today()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if not header:
        raise JobforgeError("The file is empty or has no header row. The first "
                            "row should name the columns, e.g. company,title,"
                            "applied,status,status_date,notes.")
    index, unused = _header_map(header)
    missing = [c for c in REQUIRED if c not in index]
    if missing:
        raise JobforgeError(f"The file has no {' or '.join(missing)} column. "
                            f"Columns found: {', '.join(h for h in header if h)}.")
    plan = ImportPlan()
    if unused:
        plan.warnings.append(f"column(s) {', '.join(map(repr, unused))} are not "
                             f"imported. Known columns: {', '.join(COLUMNS)}.")

    by_url: dict[str, str] = {}
    by_key: dict[tuple, str] = {}
    taken: set[str] = set()
    for folder in job_folders(ws):
        job = read_job(folder)
        taken.add(folder.name)
        if job.get("url"):
            by_url[job["url"]] = f"jobs/{folder.name}"
        by_key[(slug(job.get("company", "")), slug(job.get("title", "")),
                slug(job.get("location", "")))] = f"jobs/{folder.name}"

    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        cell = {name: (raw[i].strip() if i < len(raw) else "")
                for name, i in index.items()}
        for name in COLUMNS:
            cell.setdefault(name, "")
        row = ImportRow(reader.line_num, cell["company"], cell["title"])
        plan.rows.append(row)
        try:
            if not cell["company"] or not cell["title"]:
                raise ValueError("company and title are both required")
            row.events = _events(cell, today)
        except ValueError as exc:
            row.action, row.message = "error", str(exc)
            continue

        key = (slug(cell["company"]), slug(cell["title"]), slug(cell["location"]))
        earlier = (cell["url"] and by_url.get(cell["url"])) or by_key.get(key)
        if earlier:
            row.action, row.message = "duplicate", f"already recorded: {earlier}"
            continue
        here = f"line {row.line} of this file"
        if cell["url"]:
            by_url[cell["url"]] = here
        by_key[key] = here

        job = Job(cell["company"], cell["title"], "", url=cell["url"],
                  location=cell["location"], source="import")
        name = base = folder_name(job, row.events[0].date)
        n = 1
        while name in taken:
            n += 1
            name = f"{base}__{n}"
        taken.add(name)
        row.folder = name
        row.job = {**job.to_dict(), "imported": today.isoformat()}
    return plan


def write_import(ws: Workspace, plan: ImportPlan) -> list[str]:
    """Write every new row. All or nothing: with any error row, nothing is
    written, the way `apply` refuses a half-checked plan."""
    errors = [r for r in plan.rows if r.action == "error"]
    if errors:
        raise JobforgeError(
            f"Nothing imported: {len(errors)} row(s) have problems. Fix or delete "
            f"them, then run the import again:",
            [f"line {r.line}: {r.message}" for r in errors])
    written = []
    for row in plan.rows:
        if row.action != "new":
            continue
        folder = ws.jobs_dir / row.folder
        folder.mkdir(parents=True)
        (folder / "job.json").write_text(
            json.dumps(row.job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for ev in row.events:
            append_event(folder, ev.stage, ev.date, ev.note)
        written.append(row.folder)
    return written


def import_csv(ws: Workspace, text: str, *, write: bool = False,
               today: _dt.date | None = None) -> ImportPlan:
    plan = plan_import(ws, text, today=today)
    if write:
        write_import(ws, plan)
    return plan


def format_preview(plan: ImportPlan) -> str:
    lines = []
    for r in plan.rows:
        lines.append(f"{r.action.upper():<10} line {r.line:<4} {r.company} | {r.title}")
        if r.action == "new":
            events = ", ".join(f"{e.stage} {e.date.isoformat()}" for e in r.events)
            lines.append(f"{'':<10} -> jobs/{r.folder}: {events}")
        else:
            lines.append(f"{'':<10} {r.message}")
    lines += [f"warning: {w}" for w in plan.warnings]
    lines.append(f"{plan.count('new')} new, {plan.count('duplicate')} duplicate, "
                 f"{plan.count('error')} error")
    return "\n".join(lines)
