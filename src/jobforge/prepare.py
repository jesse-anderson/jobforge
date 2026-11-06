"""`jobforge prepare`: capture one posting into a job folder."""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .errors import JobforgeError
from .extract import Job
from .ledger import append_event
from .workspace import Workspace

SLUG_MAX = 40


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s.strip()).strip("_").lower()
    return s[:SLUG_MAX].rstrip("_") or "untitled"


def folder_name(job: Job, today: _dt.date) -> str:
    return f"{slug(job.company)}__{slug(job.title)}__{today.isoformat()}"


def read_job(folder: Path) -> dict:
    path = folder / "job.json"
    if not path.exists():
        raise JobforgeError(f"{folder.name} has no job.json. Run `jobforge prepare` first.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JobforgeError(f"{folder.name}/job.json is not valid JSON: {exc}") from exc


def similar_jobs(ws: Workspace, job: Job, exclude: Path | None = None) -> list[str]:
    """Earlier job folders for the same posting: same URL, or same company and
    title. A warning, not a block: reapplying can be deliberate."""
    hits = []
    if not ws.jobs_dir.exists():
        return hits
    for folder in sorted(ws.jobs_dir.iterdir()):
        if not folder.is_dir() or (exclude and folder.resolve() == exclude.resolve()):
            continue
        try:
            other = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        same_url = job.url and other.get("url") == job.url
        same_role = (slug(other.get("company", "")) == slug(job.company)
                     and slug(other.get("title", "")) == slug(job.title))
        if same_url or same_role:
            hits.append(folder.name)
    return hits


def prepare(ws: Workspace, job: Job, *, force: bool = False,
            today: _dt.date | None = None) -> tuple[Path, list[str]]:
    """Write jobs/<company>__<title>__<date>/job.json and the first ledger
    event. Returns the folder and warnings."""
    today = today or _dt.date.today()
    folder = ws.jobs_dir / folder_name(job, today)
    warnings = []
    if (folder / "job.json").exists() and not force:
        raise JobforgeError(f"jobs/{folder.name}/job.json already exists. "
                            f"Use --force to replace the posting text.")
    earlier = similar_jobs(ws, job, exclude=folder)
    if earlier:
        warnings.append("You already have a folder for this posting: "
                        + ", ".join(earlier))
    folder.mkdir(parents=True, exist_ok=True)
    data = job.to_dict()
    data["prepared"] = today.isoformat()
    (folder / "job.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    if not (folder / "ledger.toml").exists():
        append_event(folder, "prepared", today)
    return folder, warnings
