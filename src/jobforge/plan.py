"""`plan.json`: the agent's choices for one job, and its validation.

The plan is the only thing the agent writes for a job. It picks atoms, orders
them, may reword them, and drafts the cover letter. The engine checks it and
renders it; the agent never edits a deliverable (COMPONENTS.md).

Schema, version 1:

    {
      "version": 1,
      "summary":     {"atom": "<summary id>", "text": "<optional rewording>",
                      "cites": ["<extra atom ids the rewording draws on>"]},
      "experience":  [{"role": "<role id>",
                       "bullets": ["<bullet id>",
                                   {"atom": "<bullet id>", "text": "<rewording>"}]}],
      "projects":    [{"project": "<id>", "bullets": [...], "include_writeup": false}],
      "skills":      ["<skill id>", ...],
      "credentials": ["<credential id>", ...],
      "education":   ["<education id>", ...],     # default: all, in file order
      "cover_letter": {"hook": "...", "body": "...", "close": "...",
                       "cites": ["<atom ids the letter's facts come from>"]},
      "fit":   {"score": "strong|moderate|stretch|wrong_shape", "summary": "..."},
      "gaps":  [...],      # free-form; kept for the user, never rendered
      "notes": "..."       # free-form; never rendered
    }

A bullet given as a bare id renders the atom's own text. Given as an object
with "text", it renders the rewording, which the fact check then holds to the
atom's facts (D-32).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .atoms import Atom, Inventory
from .errors import JobforgeError

PLAN_VERSION = 1
TOP_KEYS = {"version", "summary", "experience", "projects", "skills", "credentials",
            "education", "cover_letter", "fit", "gaps", "notes"}
FIT_SCORES = ("strong", "moderate", "stretch", "wrong_shape")


@dataclass
class Line:
    """One piece of text the agent authored or selected, with the atoms its
    facts must come from."""
    where: str
    text: str
    cites: list[Atom]
    owner: Atom | None = None  # the bullet/summary atom this line renders


@dataclass
class Section:
    head: Atom  # role or project
    lines: list[Line]
    include_writeup: bool = False


@dataclass
class Letter:
    hook: str
    body: str
    close: str
    cites: list[Atom]

    def paragraphs(self) -> list[str]:
        out = []
        for part in (self.hook, self.body, self.close):
            for para in part.strip().split("\n\n"):
                para = " ".join(line.strip() for line in para.splitlines() if line.strip())
                if para:
                    out.append(para)
        return out

    def text(self) -> str:
        return "\n\n".join(self.paragraphs())


@dataclass
class ResolvedPlan:
    summary: Line | None = None
    experience: list[Section] = field(default_factory=list)
    projects: list[Section] = field(default_factory=list)
    skills: list[Atom] = field(default_factory=list)
    credentials: list[Atom] = field(default_factory=list)
    education: list[Atom] = field(default_factory=list)
    letter: Letter | None = None
    fit: dict = field(default_factory=dict)

    def resume_lines(self) -> list[Line]:
        out = [self.summary] if self.summary else []
        for sec in self.experience + self.projects:
            out.extend(sec.lines)
        return out


def load_plan(folder: Path) -> dict:
    path = folder / "plan.json"
    if not path.exists():
        raise JobforgeError(f"{folder.name} has no plan.json yet. Your agent writes it; "
                            f"see the instructions in CLAUDE.md or AGENTS.md.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise JobforgeError(f"{folder.name}/plan.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise JobforgeError(f"{folder.name}/plan.json must be a JSON object.")
    return data


def resolve(plan: dict, inv: Inventory, pending: set[str] | frozenset = frozenset()
            ) -> tuple[ResolvedPlan, list[str], list[str]]:
    """Check the plan's structure and references. Returns the resolved plan,
    errors, and warnings. Callers must not render when errors is non-empty."""
    errors: list[str] = []
    warnings: list[str] = []
    out = ResolvedPlan()

    if plan.get("version") != PLAN_VERSION:
        errors.append(f"version must be {PLAN_VERSION}, got {plan.get('version')!r}")
    for key in sorted(set(plan) - TOP_KEYS):
        errors.append(f"unknown key {key!r}; allowed: {', '.join(sorted(TOP_KEYS))}")

    def lookup(atom_id, where: str, kinds: tuple[str, ...]) -> Atom | None:
        if not isinstance(atom_id, str) or not atom_id:
            errors.append(f"{where}: expected an atom id, got {atom_id!r}")
            return None
        atom = inv.get(atom_id)
        if atom is None:
            if atom_id in pending:
                errors.append(f"{where}: {atom_id!r} is still pending. Only confirmed "
                              f"facts can be used; run `jobforge confirm` first.")
            else:
                errors.append(f"{where}: no atom with id {atom_id!r}")
            return None
        if atom.kind not in kinds:
            errors.append(f"{where}: {atom_id!r} is a {atom.kind}, expected "
                          f"{' or '.join(kinds)}")
            return None
        return atom

    def id_list(key: str, kinds: tuple[str, ...]) -> list[Atom]:
        raw = plan.get(key, [])
        if not isinstance(raw, list):
            errors.append(f"{key} must be a list of atom ids")
            return []
        atoms = [lookup(a, f"{key}[{i}]", kinds) for i, a in enumerate(raw)]
        return [a for a in atoms if a]

    def text_field(obj: dict, key: str, where: str, required: bool = False) -> str:
        v = obj.get(key, "")
        if not isinstance(v, str):
            errors.append(f"{where}.{key} must be text")
            return ""
        if required and not v.strip():
            errors.append(f"{where}.{key} is empty")
        return v.strip()

    # Summary
    summary = plan.get("summary")
    if summary is not None:
        if not isinstance(summary, dict):
            errors.append('summary must be an object like {"atom": "<summary id>"}')
        else:
            extra = set(summary) - {"atom", "text", "cites"}
            if extra:
                errors.append(f"summary has unknown key(s) {sorted(extra)}")
            atom = lookup(summary.get("atom"), "summary.atom", ("summary",))
            cites = _cites(summary.get("cites", []), "summary.cites", lookup, errors)
            if atom:
                text = text_field(summary, "text", "summary") or atom.get("text")
                out.summary = Line("summary", text, [atom, *cites], owner=atom)

    # Experience and projects
    def sections(key: str, head_key: str, head_kind: str) -> list[Section]:
        raw = plan.get(key, [])
        if not isinstance(raw, list):
            errors.append(f"{key} must be a list")
            return []
        result = []
        for i, entry in enumerate(raw):
            where = f"{key}[{i}]"
            if not isinstance(entry, dict):
                errors.append(f'{where} must be an object like {{"{head_key}": "<id>", "bullets": [...]}}')
                continue
            allowed = {head_key, "bullets"} | ({"include_writeup"} if head_kind == "project" else set())
            extra = set(entry) - allowed
            if extra:
                errors.append(f"{where} has unknown key(s) {sorted(extra)}")
            head = lookup(entry.get(head_key), f"{where}.{head_key}", (head_kind,))
            bullets_raw = entry.get("bullets", [])
            if not isinstance(bullets_raw, list):
                errors.append(f"{where}.bullets must be a list")
                bullets_raw = []
            lines = []
            for j, b in enumerate(bullets_raw):
                bw = f"{where}.bullets[{j}]"
                if isinstance(b, str):
                    atom_id, text = b, None
                elif isinstance(b, dict):
                    extra_b = set(b) - {"atom", "text"}
                    if extra_b:
                        errors.append(f"{bw} has unknown key(s) {sorted(extra_b)}")
                    atom_id, text = b.get("atom"), b.get("text")
                    if text is not None and (not isinstance(text, str) or not text.strip()):
                        errors.append(f"{bw}.text must be non-empty text, or left out")
                        text = None
                else:
                    errors.append(f"{bw} must be an atom id or {{\"atom\": ..., \"text\": ...}}")
                    continue
                atom = lookup(atom_id, bw, ("bullet",))
                if not atom or not head:
                    continue
                bound = atom.get(head_kind)
                if bound != head.id:
                    errors.append(_binding_error(bw, atom, head, inv))
                    continue
                lines.append(Line(bw, (text or atom.get("text")).strip(), [atom], owner=atom))
            if head:
                writeup = bool(entry.get("include_writeup")) if head_kind == "project" else False
                if writeup and not head.get("writeup_url"):
                    warnings.append(f"{where}: include_writeup is set but {head.id!r} has "
                                    f"no writeup_url")
                result.append(Section(head, lines, writeup))
        return result

    out.experience = sections("experience", "role", "role")
    out.projects = sections("projects", "project", "project")
    out.skills = id_list("skills", ("skill",))
    out.credentials = id_list("credentials", ("credential",))
    if "education" in plan:
        out.education = id_list("education", ("education",))
    else:
        out.education = inv.of_kind("education")

    for key, secs in (("experience", out.experience), ("projects", out.projects)):
        seen: set[str] = set()
        for sec in secs:
            if sec.head.id in seen:
                errors.append(f"{key}: {sec.head.id!r} appears twice")
            seen.add(sec.head.id)
            ids = [ln.owner.id for ln in sec.lines]
            for dup in sorted({i for i in ids if ids.count(i) > 1}):
                errors.append(f"{key} {sec.head.id!r}: bullet {dup!r} appears twice")

    starts = [(s.head.get("start") or "") for s in out.experience]
    if starts != sorted(starts, reverse=True):
        warnings.append("experience is not in reverse-chronological order (most "
                        "recent role first)")

    if not (out.experience or out.projects or out.education):
        errors.append("the resume would be empty: include at least one role, "
                      "project, or education entry")

    # Cover letter
    cl = plan.get("cover_letter")
    if not isinstance(cl, dict):
        errors.append('cover_letter is required: {"hook": ..., "body": ..., '
                      '"close": ..., "cites": [...]}')
    else:
        extra = set(cl) - {"hook", "body", "close", "cites"}
        if extra:
            errors.append(f"cover_letter has unknown key(s) {sorted(extra)}")
        hook = text_field(cl, "hook", "cover_letter", required=True)
        body = text_field(cl, "body", "cover_letter", required=True)
        close = text_field(cl, "close", "cover_letter", required=True)
        cites = _cites(cl.get("cites", []), "cover_letter.cites", lookup, errors)
        out.letter = Letter(hook, body, close, cites)

    fit = plan.get("fit")
    if fit is not None:
        if not isinstance(fit, dict):
            errors.append("fit must be an object")
        elif fit.get("score") not in FIT_SCORES:
            errors.append(f"fit.score must be one of {', '.join(FIT_SCORES)}")
        else:
            out.fit = fit
    return out, errors, warnings


def _cites(raw, where: str, lookup, errors: list[str]) -> list[Atom]:
    if not isinstance(raw, list):
        errors.append(f"{where} must be a list of atom ids")
        return []
    any_kind = ("role", "bullet", "project", "skill", "credential", "education", "summary")
    atoms = [lookup(a, f"{where}[{i}]", any_kind) for i, a in enumerate(raw)]
    return [a for a in atoms if a]


def _binding_error(where: str, bullet: Atom, head: Atom, inv: Inventory) -> str:
    """D-40: a bullet renders only under its own role or project."""
    def describe(atom: Atom | None) -> str:
        if atom is None:
            return "nothing"
        if atom.kind == "role":
            return f"role {atom.id!r} ({atom.get('employer')})"
        return f"{atom.kind} {atom.id!r}"
    owner_id = bullet.get("role") or bullet.get("project")
    return (f"{where}: bullet {bullet.id!r} belongs to {describe(inv.get(owner_id))}, "
            f"not {describe(head)}. A fact may only be listed under the job or project "
            f"it happened in.")
