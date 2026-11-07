"""`jobforge inventory`: every confirmed fact, grouped by employer.

The agent reads this before writing a plan, so it is laid out the way a plan
is built: roles with their bullets, projects with theirs, then the rest.
"""
from __future__ import annotations

from .atoms import Atom, Inventory
from .render import date_range


def _bullet(a: Atom) -> list[str]:
    out = [f"- `{a.id}`: {a.get('text')}  _(basis: {a.get('basis')})_"]
    for p in a.phrasings:
        out.append(f"  - also ({p.get('use', 'any')}): {p.get('text')}")
    if a.get("reword_of"):
        out.append(f"  - rewords `{a.get('reword_of')}`")
    return out


def render_markdown(inv: Inventory) -> str:
    out = ["# Confirmed facts", ""]
    bullets = inv.of_kind("bullet")

    roles = sorted(inv.of_kind("role"), key=lambda r: r.get("start") or "", reverse=True)
    if roles:
        out += ["## Roles", ""]
    for r in roles:
        out.append(f"### `{r.id}`: {r.get('title')} at {r.get('employer')} "
                   f"({date_range(r.get('start'), r.get('end'))})")
        if r.get("aliases"):
            out.append(f"Also called: {', '.join(r.get('aliases'))}")
        for b in bullets:
            if b.get("role") == r.id:
                out += _bullet(b)
        out.append("")

    projects = inv.of_kind("project")
    if projects:
        out += ["## Projects", ""]
    for p in projects:
        ctx = p.get("context")
        owner = inv.get(ctx)
        where = f"at {owner.get('employer')}" if owner else ctx
        url = f" {p.get('url')}" if p.get("url") and p.get("url_status") != "dead" else ""
        out.append(f"### `{p.id}`: {p.get('title')} ({where}){url}")
        if p.get("text"):
            out.append(p.get("text"))
        for b in bullets:
            if b.get("project") == p.id:
                out += _bullet(b)
        out.append("")

    for kind, title, fmt in (
        ("summary", "Summaries", lambda a: a.get("text")),
        ("skill", "Skills", lambda a: f"{a.get('label')}: {', '.join(a.get('items'))}"),
        ("credential", "Credentials", lambda a: " | ".join(
            x for x in (a.get("name"), a.get("issuer"), a.get("date")) if x)),
        ("education", "Education", lambda a: " | ".join(
            x for x in (a.get("school"), a.get("credential"), a.get("field"), a.get("date")) if x)),
    ):
        atoms = inv.of_kind(kind)
        if atoms:
            out += [f"## {title}", ""]
            out += [f"- `{a.id}`: {fmt(a)}" for a in atoms]
            out.append("")
    if len(out) == 2:
        out.append("No confirmed facts yet. Draft some into profile/pending/ and run "
                   "`jobforge confirm`.")
    return "\n".join(out).rstrip() + "\n"
