"""`jobforge prepare`: capture one posting into a job folder."""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .errors import JobforgeError
from .extract import Job
from .ledger import append_event
from .profile import plain_letters
from .workspace import Workspace

SLUG_MAX = 40


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", plain_letters(s).strip()).strip("_").lower()
    return s[:SLUG_MAX].rstrip("_") or "untitled"


def folder_name(job: Job, today: _dt.date) -> str:
    return f"{slug(job.company)}__{slug(job.title)}__{today.isoformat()}"


def read_job(folder: Path) -> dict:
    path = folder / "job.json"
    if not path.exists():
        raise JobforgeError(f"{folder.name} has no job.json. Run `jobforge prepare` first.")
    try:
        job = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise JobforgeError(f"{folder.name}/job.json is not valid JSON: {exc}") from exc
    except UnicodeDecodeError:  # #28, F6
        raise JobforgeError(f"{folder.name}/job.json is not UTF-8 text. Save it as UTF-8, "
                            f"or capture the posting again with `jobforge prepare`.") from None
    if not isinstance(job, dict):  # #72: a list or a number has no fields to read
        raise JobforgeError(f"{folder.name}/job.json must be a JSON object, the "
                            f"{{...}} that `jobforge prepare` writes.")
    return job


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
            other = json.loads((folder / "job.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):  # bad JSON or not UTF-8: not this one (#28)
            continue
        same_url = job.url and other.get("url") == job.url
        same_role = (slug(other.get("company", "")) == slug(job.company)
                     and slug(other.get("title", "")) == slug(job.title))
        if same_url or same_role:
            hits.append(folder.name)
    return hits


def same_posting(other: dict, job: Job) -> bool:
    """Whether a saved job.json is this posting: the same URL, or, when either
    has none, the same company, title, and location as written. Not by slug:
    every non-Latin company slugs to "untitled" (#31)."""
    if job.url and other.get("url"):
        return other.get("url") == job.url

    def norm(v) -> str:
        return " ".join(str(v or "").split()).casefold()
    return all(norm(other.get(k)) == norm(getattr(job, k)) for k in
               ("company", "title", "location"))


def prepare(ws: Workspace, job: Job, *, force: bool = False,
            today: _dt.date | None = None) -> tuple[Path, list[str]]:
    """Write jobs/<company>__<title>__<date>/job.json and the first ledger
    event. Returns the folder and warnings.

    A different posting that would get the same name (another city, the same
    day) gets the next free one, `__2`, `__3`, as `jobforge import` does. Only
    the same posting can be replaced, and only with `force` (#31)."""
    today = today or _dt.date.today()
    base = name = folder_name(job, today)
    n = 1
    while (ws.jobs_dir / name / "job.json").exists():
        if same_posting(read_job(ws.jobs_dir / name), job):
            if not force:
                raise JobforgeError(f"jobs/{name}/job.json already holds this same "
                                    f"posting. Use --force to replace its text.")
            break
        n += 1
        name = f"{base}__{n}"
    folder = ws.jobs_dir / name
    warnings = []
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
