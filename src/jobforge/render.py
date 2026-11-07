"""Turn a resolved plan into document blocks.

One template at 1.0 (D-26): name, contact line, then Summary, Experience,
Projects, Skills, Credentials, Education, each only if it has content. Dates
are written "Mar 2019 to Present" so the engine never puts a dash on the page
that the user did not write. Every URL is visible text (D-42).
"""
from __future__ import annotations

import datetime as _dt
import math

from .atoms import Atom
from .docx import Block, Run
from .factcheck import live_url
from .plan import ResolvedPlan
from .profile import Profile, display_url

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def fmt_date(value: str | None) -> str:
    if not value:
        return ""
    if value == "present":
        return "Present"
    year, _, month = value.partition("-")
    return f"{MONTHS[int(month) - 1]} {year}" if month else year


def date_range(start: str | None, end: str | None) -> str:
    s, e = fmt_date(start), fmt_date(end)
    if s and e:
        return f"{s} to {e}"
    return s or e


def _join(parts: list[str]) -> str:
    return " | ".join(p for p in parts if p)


def header_blocks(profile: Profile) -> list[Block]:
    return [
        Block("title", [Run(profile.name, bold=True)], align="center"),
        Block("para", [Run(_join(profile.contact_items()))], align="center"),
    ]


def role_line(role: Atom) -> list[Run]:
    return [Run(role.get("title"), bold=True),
            Run(" | " + _join([role.get("employer"), role.get("location") or "",
                               date_range(role.get("start"), role.get("end"))]))]


def project_line(project: Atom, include_writeup: bool) -> list[Run]:
    runs = [Run(project.get("title"), bold=True)]
    url = live_url(project)
    if url:
        runs += [Run(" | "), Run(display_url(url), href=url)]
    if include_writeup and project.get("writeup_url"):
        w = project.get("writeup_url")
        runs += [Run(" | Writeup: "), Run(display_url(w), href=w)]
    if project.get("text"):
        runs.append(Run(" | " + project.get("text")))
    return runs


def resume_blocks(plan: ResolvedPlan, profile: Profile) -> list[Block]:
    blocks = header_blocks(profile)

    def section(title: str, body: list[Block]) -> None:
        if body:
            blocks.append(Block("heading", [Run(title)]))
            blocks.extend(body)

    if plan.summary:
        section("Summary", [Block("para", [Run(plan.summary.text)])])

    body: list[Block] = []
    for sec in plan.experience:
        body.append(Block("para", role_line(sec.head)))
        body.extend(Block("bullet", [Run(ln.text)]) for ln in sec.lines)
    section("Experience", body)

    body = []
    for sec in plan.projects:
        body.append(Block("para", project_line(sec.head, sec.include_writeup)))
        body.extend(Block("bullet", [Run(ln.text)]) for ln in sec.lines)
    section("Projects", body)

    section("Skills", [
        Block("para", [Run(s.get("label") + ": ", bold=True), Run(", ".join(s.get("items")))])
        for s in plan.skills])

    section("Credentials", [
        Block("bullet", [Run(_join([c.get("name"), c.get("issuer") or "",
                                    fmt_date(c.get("date"))]))])
        for c in plan.credentials])

    body = []
    for e in plan.education:
        degree = e.get("credential") + (f", {e.get('field')}" if e.get("field") else "")
        body.append(Block("para", [Run(e.get("school"), bold=True),
                                   Run(" | " + _join([degree, e.get("location") or "",
                                                      fmt_date(e.get("date"))]))]))
        if e.get("details"):
            body.append(Block("para", [Run(e.get("details"))]))
    section("Education", body)
    return blocks


def letter_blocks(plan: ResolvedPlan, profile: Profile, job: dict,
                  today: _dt.date | None = None) -> list[Block]:
    """Built from the plan's hook, body, and close only. The working
    `cover_letter.md` carries a heading and a cites list for review; none of
    that belongs in what an employer receives."""
    today = today or _dt.date.today()
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    blocks = header_blocks(profile)
    blocks.append(Block("para", [Run(f"{MONTHS[today.month - 1]} {today.day}, {today.year}")]))
    if title or company:
        blocks.append(Block("para", [Run("Re: ", bold=True), Run(_join([title, company]))]))
    blocks.append(Block("para", [Run(f"Dear {company} Hiring Team," if company
                                     else "Dear Hiring Team,")]))
    blocks.extend(Block("para", [Run(p)]) for p in plan.letter.paragraphs())
    blocks.append(Block("para", [Run("Sincerely,")]))
    blocks.append(Block("para", [Run(profile.name)]))
    return blocks


def letter_markdown(plan: ResolvedPlan, job: dict) -> str:
    """The working copy for review. Never a deliverable (D-30 item 5)."""
    lines = [f"# Cover letter (working copy, do not send): {job.get('company', '')}, "
             f"{job.get('title', '')}", ""]
    url = (job.get("url") or "").strip()
    if url:  # a posting pasted with --from-text has none (#106)
        lines += [f"_Posting: {url}_", ""]
    lines += [p + "\n" for p in plan.letter.paragraphs()]
    lines += ["---", "", "## Facts cited", ""]
    lines += [f"- `{a.id}` ({a.kind})" for a in plan.letter.cites]
    return "\n".join(lines) + "\n"


# Page-fill estimate. Letter paper, 0.5in margins, Calibri 10.5pt: about 115
# characters per line and 58 lines per page. Headings and the title take extra
# vertical space. This is a warning-only estimate until PDF gives a real count
# (D-41, Q-2).
CHARS_PER_LINE = 115
LINES_PER_PAGE = 58
_BLOCK_COST = {"title": 2.0, "heading": 1.8}


def estimate_pages(blocks: list[Block]) -> float:
    lines = 0.0
    for b in blocks:
        n = len(b.text()) + (2 if b.kind == "bullet" else 0)
        wrapped = max(1, math.ceil(n / CHARS_PER_LINE))
        lines += max(wrapped, _BLOCK_COST.get(b.kind, 0))
    return lines / LINES_PER_PAGE
