"""`jobforge check` and `jobforge apply`.

`check` validates the plan and runs the fact check without writing anything
but `check.json`, so the agent can loop on errors cheaply (D-47, M-4).

`apply` runs the same checks, renders both documents into a temporary folder,
reads them back the way an ATS would, checks what came back, and only then
moves them into the job folder. If anything fails, no deliverable is written
or replaced (D-30 item 3).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .atoms import Inventory, load_inventory, pending_ids
from .docx import extract_text, write_docx
from .errors import JobforgeError
from .factcheck import Report, check_plan, live_url, url_key
from .plan import ResolvedPlan, load_plan, resolve
from .prepare import read_job
from .profile import Profile, load_profile
from .render import estimate_pages, letter_blocks, letter_markdown, resume_blocks
from .scan import find_hidden
from .workspace import Workspace

CHECK_NAME = "check.json"
COVER_MD_NAME = "cover_letter.md"


@dataclass
class CheckResult:
    folder: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    plan: ResolvedPlan | None = None
    profile: Profile | None = None
    inventory: Inventory | None = None
    job: dict = field(default_factory=dict)
    pages: float | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings,
                "estimated_pages": round(self.pages, 2) if self.pages is not None else None,
                "checked": _dt.datetime.now().isoformat(timespec="seconds")}

    def write(self) -> None:
        (self.folder / CHECK_NAME).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def failure(self, verb: str) -> JobforgeError:
        return JobforgeError(f"{verb} failed for {self.folder.name}. Fix the plan "
                             f"(or your atoms) and run it again:", self.errors)


def run_check(ws: Workspace, folder: Path) -> CheckResult:
    result = CheckResult(folder)
    result.job = read_job(folder)
    result.profile = load_profile(ws)
    result.inventory = load_inventory(ws)
    result.warnings.extend(result.inventory.warnings)
    plan_dict = load_plan(folder)
    resolved, errors, warnings = resolve(plan_dict, result.inventory, pending_ids(ws))
    result.errors.extend(errors)
    result.warnings.extend(warnings)
    if errors:
        result.write()
        return result
    result.plan = resolved
    rep = check_plan(resolved, result.inventory, result.profile, result.job)
    result.errors.extend(rep.errors)
    result.warnings.extend(rep.warnings)

    blocks = resume_blocks(resolved, result.profile)
    result.pages = estimate_pages(blocks)
    if result.pages > result.profile.page_limit:
        result.warnings.append(
            f"the resume is estimated at {result.pages:.1f} pages; your limit is "
            f"{result.profile.page_limit}. Drop a bullet, project, or skills line.")
    result.write()
    return result


def verify_readback(text: str, expected_lines: list[str], urls: list[str],
                    label: str) -> Report:
    """Check a document as read back from disk: every line we meant to write
    is there unchanged, every URL is visible text, and nothing hidden."""
    rep = Report()
    for hidden in find_hidden(text):
        rep.errors.append(f"{label}: hidden character: {hidden}. Remove it from the "
                          f"atom or plan text it came from.")
    flat = " ".join(text.split())
    for line in expected_lines:
        if " ".join(line.split()) not in flat:
            rep.errors.append(f"{label}: text did not survive the round trip: {line[:80]!r}")
    lower = flat.lower()
    for url in urls:
        if url_key(url) not in lower:
            rep.errors.append(f"{label}: URL {url} is not visible in the document text")
    return rep


def _move(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def _swap_in(tmp: Path, folder: Path, names: list[str]) -> None:
    """Replace each folder/name with tmp/name, all or nothing (#32).

    The old files are moved aside first, so a file another program holds
    (Word locks an open .docx on Windows) is found before anything changes.
    On any failure the new files are taken out and the old ones put back."""
    aside = tmp / "previous"
    aside.mkdir()
    moved, placed = [], []
    current = names[0]
    try:
        for current in names:
            if (folder / current).exists():
                _move(folder / current, aside / current)
                moved.append(current)
        for current in names:
            _move(tmp / current, folder / current)
            placed.append(current)
    except OSError as exc:
        for name in placed:
            (folder / name).unlink(missing_ok=True)
        for name in moved:
            _move(aside / name, folder / name)
        if isinstance(exc, PermissionError):
            raise JobforgeError(
                f"Close {current} (it is open in another program, such as Word), then "
                f"run `jobforge apply` again. Nothing was changed.") from None
        raise


def apply(ws: Workspace, folder: Path, *, today: _dt.date | None = None) -> dict:
    result = run_check(ws, folder)
    if not result.ok:
        raise result.failure("Check")
    plan, profile, job = result.plan, result.profile, result.job

    resume_name = f"{profile.resume_stem}.docx"
    cover_name = f"{profile.cover_stem}.docx"
    r_blocks = resume_blocks(plan, profile)
    c_blocks = letter_blocks(plan, profile, job, today)

    resume_urls = [u for sec in plan.projects if (u := live_url(sec.head))]
    resume_lines = [ln.text for ln in plan.resume_lines()]

    tmp = Path(tempfile.mkdtemp(prefix=".jobforge-", dir=folder))
    try:
        r_path = write_docx(r_blocks, tmp / resume_name)
        c_path = write_docx(c_blocks, tmp / cover_name)
        rep = verify_readback(extract_text(r_path), resume_lines, resume_urls, resume_name)
        rep.extend(verify_readback(extract_text(c_path), plan.letter.paragraphs(), [],
                                   cover_name))
        if not rep.ok:
            result.errors.extend(rep.errors)
            result.write()
            raise result.failure("Apply")
        (tmp / COVER_MD_NAME).write_text(letter_markdown(plan, job), encoding="utf-8")
        _swap_in(tmp, folder, [resume_name, cover_name, COVER_MD_NAME])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    result.write()
    return {
        "folder": str(folder),
        "resume": str(folder / resume_name),
        "cover_letter": str(folder / cover_name),
        "working_copy": str(folder / COVER_MD_NAME),
        "estimated_pages": result.pages,
        "warnings": result.warnings,
    }
