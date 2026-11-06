"""`jobforge jobs` (alias `search`): list the user's own jobs (D-27).

A scan of the job folders. At MVP scale (hundreds of jobs) reading a few
hundred small files is well under a second; the rebuildable index from D-29
comes with 1.0, with a performance test to prove when it is needed.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass

from .ledger import current_status, job_folders, read_events
from .workspace import Workspace


@dataclass
class JobRow:
    folder: str
    company: str
    title: str
    status: str
    last_date: str
    url: str


def list_jobs(ws: Workspace, *, today: _dt.date | None = None, ghost_after_days: int = 30,
              status: str | None = None, company: str | None = None,
              text: str | None = None) -> list[JobRow]:
    today = today or _dt.date.today()
    rows = []
    for folder in job_folders(ws):
        try:
            job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        events = read_events(folder)
        row = JobRow(
            folder=folder.name,
            company=str(job.get("company", "")),
            title=str(job.get("title", "")),
            status=current_status(events, today, ghost_after_days),
            last_date=events[-1].date.isoformat() if events else "",
            url=str(job.get("url", "")),
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


def format_table(rows: list[JobRow]) -> str:
    if not rows:
        return "No jobs yet. Add one with `jobforge prepare --from-url <url>`."
    headers = ("STATUS", "DATE", "COMPANY", "TITLE", "FOLDER")
    data = [(r.status, r.last_date, r.company, r.title, r.folder) for r in rows]
    widths = [min(max(len(h), *(len(d[i]) for d in data)), 40) for i, h in enumerate(headers)]

    def fmt(cells):
        return "  ".join(c[:w].ljust(w) for c, w in zip(cells, widths)).rstrip()

    return "\n".join([fmt(headers), *(fmt(d) for d in data)])
