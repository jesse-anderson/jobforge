"""`jobforge jobs` (alias `search`): list the user's own jobs (D-27).

A scan of the job folders. At MVP scale (hundreds of jobs) reading a few
hundred small files is well under a second; the rebuildable index from D-29
comes with 1.0, with a performance test to prove when it is needed.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass

from .errors import JobforgeError
from .ledger import current_status, job_folders, read_events
from .workspace import Workspace

UNREADABLE = "unreadable"


@dataclass
class JobRow:
    folder: str
    company: str
    title: str
    status: str
    last_date: str
    url: str
    problem: str = ""  # why the ledger could not be read, if it could not


def list_jobs(ws: Workspace, *, today: _dt.date | None = None, ghost_after_days: int = 30,
              status: str | None = None, company: str | None = None,
              text: str | None = None) -> list[JobRow]:
    today = today or _dt.date.today()
    rows = []
    for folder in job_folders(ws):
        try:
            job = json.loads((folder / "job.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):  # bad JSON or not UTF-8 (#28): skip it
            continue
        # A broken ledger keeps the job in the list, marked, so one bad
        # hand edit never hides the rest (#28).
        try:
            events, problem = read_events(folder), ""
        except JobforgeError as exc:
            events, problem = [], str(exc)
        row = JobRow(
            folder=folder.name,
            company=str(job.get("company", "")),
            title=str(job.get("title", "")),
            status=UNREADABLE if problem else current_status(events, today, ghost_after_days),
            last_date=events[-1].date.isoformat() if events else "",
            url=str(job.get("url", "")),
            problem=problem,
        )
        if status and row.status != status:
            continue
        if company and company.lower() not in row.company.lower():
            continue
        if text:
            hay = " ".join([row.company, row.title, str(job.get("description", ""))]).lower()
            if text.lower() not in hay:
                continue
        rows.append(row)
    return rows


def _fit(text: str, cap: int | None) -> str:
    if cap is None or len(text) <= cap:
        return text
    return text[:cap - 1].rstrip() + "…"


def format_table(rows: list[JobRow]) -> str:
    if not rows:
        return "No jobs yet. Add one with `jobforge prepare --from-url <url>`."
    headers = ("STATUS", "DATE", "COMPANY", "TITLE", "FOLDER")
    # COMPANY and TITLE may be shortened, visibly. FOLDER never is: it is the
    # name users type back into `applied --mark`, `check`, and `apply` (#39).
    caps = (None, None, 40, 40, None)
    data = [tuple(_fit(c, cap) for c, cap in
                  zip((r.status, r.last_date, r.company, r.title, r.folder), caps))
            for r in rows]
    widths = [max(len(h), *(len(d[i]) for d in data)) for i, h in enumerate(headers)]

    def fmt(cells):
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

    return "\n".join([fmt(headers), *(fmt(d) for d in data)])
