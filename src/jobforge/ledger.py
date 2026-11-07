"""The ledger: what happened to each application, as dated events.

Events live in each job folder's `ledger.toml`, so the folder is the whole
record of one application and there is nothing central to rebuild or lose
(MVP.md section 4). Events are only ever appended.

The report (deferred, D-46) needs history, not just a current status, to
chart velocity, callback rate, and the outcome Sankey, so history is recorded
from the first `prepare`. "Ghosted" is never entered; it is computed from an
`applied` with nothing after it for `ghost_after_days` (D-47).
"""
from __future__ import annotations

import datetime as _dt
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import tomlw
from .errors import JobforgeError
from .workspace import Workspace

STAGES = ("prepared", "applied", "skipped", "screen", "interview", "offer",
          "accepted", "declined", "rejected", "withdrawn")
# Stages that count as hearing back from the employer, for callback rate.
RESPONSE_STAGES = frozenset({"screen", "interview", "offer", "accepted", "declined", "rejected"})
GHOSTED = "ghosted"
LEDGER_NAME = "ledger.toml"


@dataclass(frozen=True)
class Event:
    date: _dt.date
    stage: str
    note: str = ""


def append_event(folder: Path, stage: str, date: _dt.date | None = None,
                 note: str = "") -> Event:
    if stage not in STAGES:
        raise JobforgeError(f"Unknown stage {stage!r}. Use one of: {', '.join(STAGES)}.")
    date = date or _dt.date.today()
    path = folder / LEDGER_NAME
    entry = tomlw.table_array_entry("event", {"date": date, "stage": stage,
                                              "note": note or None})
    prefix = ""
    if not path.exists():
        prefix = ("# Dated events for this application. Append with\n"
                  "# `jobforge applied --mark <job> --status <stage>`.\n\n")
    elif not path.read_text(encoding="utf-8").endswith("\n\n"):
        prefix = "\n"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(prefix + entry)
    return Event(date, stage, note)


def read_events(folder: Path) -> list[Event]:
    path = folder / LEDGER_NAME
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as exc:
        raise JobforgeError(f"{folder.name}/{LEDGER_NAME} is not valid TOML: {exc}") from exc
    events = []
    for n, raw in enumerate(data.get("event", []), 1):
        date, stage = raw.get("date"), raw.get("stage")
        if not isinstance(date, _dt.date) or isinstance(date, _dt.datetime):
            raise JobforgeError(f"{folder.name}/{LEDGER_NAME}: event #{n} needs a "
                                f"date written like 2026-11-20 (no quotes)")
        if stage not in STAGES:
            raise JobforgeError(f"{folder.name}/{LEDGER_NAME}: event #{n} has unknown "
                                f"stage {stage!r}")
        events.append(Event(date, stage, str(raw.get("note") or "")))
    # Stable sort: same-day events keep the order they were written.
    return sorted(events, key=lambda e: e.date)


def record_event(folder: Path, stage: str, date: _dt.date | None = None, note: str = "",
                 *, today: _dt.date | None = None) -> tuple[Event, list[str]]:
    """`jobforge applied`: append what happened, refusing a date that cannot
    be right (#34). Returns the event and any warnings."""
    today = today or _dt.date.today()
    date = date or today
    if date > today:
        raise JobforgeError(f"{date.isoformat()} is in the future. Record an event on "
                            f"or after the day it happens.")
    warnings = []
    prepared = [e.date for e in read_events(folder) if e.stage == "prepared"]
    if prepared and date < prepared[0]:
        warnings.append(f"{date.isoformat()} is before this job was prepared "
                        f"({prepared[0].isoformat()}). Recorded anyway: that is right "
                        f"if you applied before making the folder.")
    return append_event(folder, stage, date, note), warnings


def current_status(events: list[Event], today: _dt.date, ghost_after_days: int) -> str:
    if not events:
        return "unknown"
    last = events[-1]
    if last.stage == "applied" and (today - last.date).days >= ghost_after_days:
        return GHOSTED
    return last.stage


def parse_date(text: str | None) -> _dt.date | None:
    if not text:
        return None
    try:
        return _dt.date.fromisoformat(text)
    except ValueError as exc:
        raise JobforgeError(f"Date {text!r} must be written YYYY-MM-DD.") from exc


def job_folders(ws: Workspace) -> list[Path]:
    if not ws.jobs_dir.exists():
        return []
    return sorted(p for p in ws.jobs_dir.iterdir()
                  if p.is_dir() and (p / "job.json").exists())


def resolve_job(ws: Workspace, ref: str) -> Path:
    """Find a job folder by path, exact name, or a unique piece of its name."""
    candidate = Path(ref)
    if candidate.is_dir() and (candidate / "job.json").exists():
        return candidate.resolve()
    folders = job_folders(ws)
    exact = [f for f in folders if f.name == ref]
    if exact:
        return exact[0]
    hits = [f for f in folders if ref.lower() in f.name.lower()]
    if not hits:
        raise JobforgeError(f"No job folder matches {ref!r}. Run `jobforge jobs` to list them.")
    if len(hits) > 1:
        raise JobforgeError(f"{ref!r} matches more than one job; be more specific:",
                            [h.name for h in hits])
    return hits[0]
