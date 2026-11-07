"""Atoms: the user's confirmed facts, in plain TOML (D-33, D-41).

A file in `profile/atoms/` (confirmed) or `profile/pending/` (agent drafts)
holds any mix of these tables:

    [[role]]        one job held: employer, title, dates
    [[bullet]]      one achievement, bound to exactly one role or project
    [[project]]     a project, with a context: a role id, or personal /
                    school / volunteer
    [[skill]]       one skills line: a label and items
    [[credential]]  a license or certification
    [[education]]   a school record
    [[summary]]     a summary paragraph

Binding is a field, never an ID prefix, so renaming an ID cannot move a fact
to another employer (D-40). Every problem in every file is collected and
reported together, with the file and atom it came from.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .errors import JobforgeError
from .facts import find_hedges, number_tokens
from .workspace import Workspace

BASIS = ("measured", "records", "estimate")
PHRASING_USES = ("resume", "cover", "email", "any")
PROJECT_CONTEXTS = ("personal", "school", "volunteer")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")
DATE_FIELDS = ("start", "end", "date")

# kind -> (required fields, optional fields)
SCHEMA: dict[str, tuple[set[str], set[str]]] = {
    "role": ({"id", "employer", "title", "start"},
             {"end", "location", "notes", "aliases", "title_aliases"}),
    "bullet": ({"id", "text", "basis"},
               {"role", "project", "defense", "facts", "phrasing", "reword_of", "tags"}),
    "project": ({"id", "title", "context"},
                {"text", "url", "writeup_url", "url_status", "basis", "defense",
                 "facts", "phrasing", "reword_of", "tags"}),
    "skill": ({"id", "label", "items"}, {"tags"}),
    "credential": ({"id", "name"}, {"issuer", "date", "expires", "tags"}),
    "education": ({"id", "school", "credential"},
                  {"field", "date", "location", "details", "tags"}),
    "summary": ({"id", "text"}, {"basis", "defense", "facts", "phrasing", "reword_of", "tags"}),
}
KINDS = tuple(SCHEMA)
# Order `confirm` presents pending atoms in, so a role is confirmed before the
# bullets that point at it.
CONFIRM_ORDER = ("role", "project", "summary", "skill", "credential", "education", "bullet")


@dataclass
class Atom:
    kind: str
    id: str
    fields: dict
    source: Path

    def get(self, key: str, default=None):
        return self.fields.get(key, default)

    @property
    def phrasings(self) -> list[dict]:
        return list(self.fields.get("phrasing") or [])

    def texts(self) -> list[str]:
        """Every piece of text that states this atom's facts: the main text,
        each phrasing, the explicit `facts` list, and descriptive fields.

        A date field contributes its year only. "2020-04" read as text would
        make "4" a fact, and a bullet under that role could claim "a team of
        4" (issue #1)."""
        out: list[str] = []
        for key in ("text", "title", "employer", "name", "issuer", "school",
                    "credential", "field", "details", "label", "location",
                    "url", "writeup_url"):
            v = self.fields.get(key)
            if isinstance(v, str) and v:
                out.append(v)
        for key in DATE_FIELDS:
            v = self.fields.get(key)
            if isinstance(v, str) and DATE_RE.match(v):
                out.append(v[:4])
        out.extend(str(i) for i in self.fields.get("items") or [])
        out.extend(str(a) for a in self.fields.get("aliases") or [])
        out.extend(str(a) for a in self.fields.get("title_aliases") or [])
        out.extend(str(f) for f in self.fields.get("facts") or [])
        out.extend(p.get("text", "") for p in self.phrasings)
        return out

    def label(self) -> str:
        return f"{self.kind} {self.id!r}"


@dataclass
class Inventory:
    atoms: dict[str, Atom] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[Atom]:
        return [a for a in self.atoms.values() if a.kind == kind]

    def get(self, atom_id: str) -> Atom | None:
        return self.atoms.get(atom_id)

    def owner_role(self, atom: Atom) -> Atom | None:
        """The role an atom's facts belong to (D-40): a role is its own owner,
        a bullet's is its role (or its project's role), a project's is its
        context role. Personal, school, and volunteer work have no employer."""
        if atom.kind == "role":
            return atom
        if atom.kind == "bullet":
            if atom.get("role"):
                return self.atoms.get(atom.get("role"))
            if atom.get("project"):
                proj = self.atoms.get(atom.get("project"))
                return self.owner_role(proj) if proj else None
        if atom.kind == "project":
            ctx = atom.get("context")
            target = self.atoms.get(ctx) if ctx not in PROJECT_CONTEXTS else None
            return target if target and target.kind == "role" else None
        return None

    def employer_of(self, atom: Atom) -> str | None:
        role = self.owner_role(atom)
        return role.get("employer") if role else None

    def employers(self) -> dict[str, list[Atom]]:
        """Employer name -> its role atoms."""
        out: dict[str, list[Atom]] = {}
        for role in self.of_kind("role"):
            out.setdefault(role.get("employer"), []).append(role)
        return out

    def role_titles(self) -> list[str]:
        """Every role's title and the other titles the user confirmed for it
        (`title_aliases`: "Data Engineer" for an official "Software Engineer",
        #89)."""
        out: list[str] = []
        for role in self.of_kind("role"):
            for title in [role.get("title"), *(role.get("title_aliases") or [])]:
                if title and title.strip() and title.strip() not in out:
                    out.append(title.strip())
        return out

    def employer_names(self) -> dict[str, list[str]]:
        """Employer name -> every name it goes by: the full name first, then
        the aliases from any of its roles ("KT" for "Kestrel Testing", #9)."""
        out: dict[str, list[str]] = {}
        for employer, roles in self.employers().items():
            names = [employer]
            for role in roles:
                for alias in role.get("aliases") or []:
                    if alias.strip() and alias.strip() not in names:
                        names.append(alias.strip())
            out[employer] = names
        return out


def read_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.toml") if p.is_file()) if folder.exists() else []


def parse_file(path: Path, rel: str, errors: list[str]) -> list[Atom]:
    """Parse one atom file. Schema problems go into `errors`."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"{rel}: not valid TOML: {exc}")
        return []
    except UnicodeDecodeError:
        errors.append(f"{rel}: is not UTF-8 text")
        return []

    atoms: list[Atom] = []
    for kind, entries in data.items():
        if kind not in SCHEMA:
            errors.append(f"{rel}: unknown section [[{kind}]]; expected one of "
                          f"{', '.join(KINDS)}")
            continue
        if not isinstance(entries, list):
            errors.append(f"{rel}: [{kind}] must be written [[{kind}]] (a list of entries)")
            continue
        for n, entry in enumerate(entries, 1):
            where = f"{rel}: {kind} #{n}"
            atom_id = entry.get("id")
            if isinstance(atom_id, str) and atom_id:
                where = f"{rel}: {kind} {atom_id!r}"
            problems = check_fields(kind, entry)
            errors.extend(f"{where}: {p}" for p in problems)
            # Keep any atom with a usable id, even one with other problems, so
            # duplicate ids and broken references are reported in the same run.
            if isinstance(atom_id, str) and ID_RE.match(atom_id):
                atoms.append(Atom(kind, atom_id, dict(entry), path))
    return atoms


def check_fields(kind: str, entry: dict) -> list[str]:
    """Problems with one atom's own fields (not its references)."""
    required, optional = SCHEMA[kind]
    problems: list[str] = []
    for key in sorted(required - set(entry)):
        problems.append(f"missing required field {key!r}")
    for key in sorted(set(entry) - required - optional):
        problems.append(f"unknown field {key!r}; allowed: "
                        f"{', '.join(sorted(required | optional))}")

    atom_id = entry.get("id")
    if "id" in entry and (not isinstance(atom_id, str) or not ID_RE.match(atom_id)):
        problems.append(f"id {atom_id!r} must be lowercase letters, digits, and . _ - "
                        f"(e.g. 'acme.downtime')")

    list_fields = {"facts", "tags", "items", "aliases", "title_aliases"}
    for key, v in entry.items():
        if key == "phrasing":
            continue
        if key in list_fields:
            if not isinstance(v, list) or not all(isinstance(i, str) for i in v):
                problems.append(f"{key!r} must be a list of text items")
            elif key in ("aliases", "title_aliases") and not all(i.strip() for i in v):
                problems.append(f"{key!r} has an empty name")
        elif not isinstance(v, str):
            problems.append(f"{key!r} must be text in quotes, got {type(v).__name__}")
        elif key in ("text", "title", "employer", "name", "label", "school",
                     "credential") and not v.strip():
            problems.append(f"{key!r} is empty")

    if kind == "bullet":
        has_role, has_project = bool(entry.get("role")), bool(entry.get("project"))
        if not has_role and not has_project:
            problems.append("a bullet must name the role it happened in (role = "
                            "\"<role id>\") or its project (project = \"<id>\")")
        elif has_role and has_project:
            problems.append("a bullet belongs to a role or a project, not both")

    if "basis" in entry and entry.get("basis") not in BASIS:
        problems.append(f"basis must be one of {', '.join(BASIS)}, got {entry.get('basis')!r}")

    for key in ("start", "end", "date", "expires"):
        v = entry.get(key)
        if isinstance(v, str) and v and not (DATE_RE.match(v) or (key == "end" and v == "present")):
            hint = ' or "present"' if key == "end" else ""
            problems.append(f"{key} {v!r} must be YYYY or YYYY-MM{hint}")
    if kind == "role" and isinstance(entry.get("start"), str) and isinstance(entry.get("end"), str):
        s, e = entry["start"], entry["end"]
        if DATE_RE.match(s) and DATE_RE.match(e) and e < s:
            problems.append(f"end {e!r} is before start {s!r}")

    for key in ("url", "writeup_url"):
        v = entry.get(key)
        if isinstance(v, str) and v and not is_http_url(v):
            problems.append(f"{key} {v!r} is not a full http(s) URL "
                            f"(e.g. https://example.com/page)")
    if "url_status" in entry and entry.get("url_status") != "dead":
        problems.append('url_status may only be "dead" (marks a URL that no longer works)')

    phr = entry.get("phrasing")
    if phr is not None:
        if not isinstance(phr, list) or not all(isinstance(p, dict) for p in phr):
            problems.append("phrasing must be written as [[<kind>.phrasing]] entries")
        else:
            for i, p in enumerate(phr, 1):
                extra = set(p) - {"use", "text", "industry"}
                if extra:
                    problems.append(f"phrasing #{i} has unknown field(s) {sorted(extra)}")
                if not isinstance(p.get("text"), str) or not p.get("text", "").strip():
                    problems.append(f"phrasing #{i} needs non-empty text")
                if p.get("use", "any") not in PHRASING_USES:
                    problems.append(f"phrasing #{i} use must be one of {', '.join(PHRASING_USES)}")
    return problems


def is_http_url(v: str) -> bool:
    parsed = urlparse(v)
    return parsed.scheme in ("http", "https") and "." in parsed.netloc and " " not in v


def check_references(atoms: dict[str, Atom], rel_of, errors: list[str],
                     only: set[str] | None = None) -> None:
    """Cross-atom rules: bindings point at real atoms of the right kind
    (D-40), and reword_of names a real atom (D-43)."""
    for atom in atoms.values():
        if only is not None and atom.id not in only:
            continue
        where = f"{rel_of(atom.source)}: {atom.label()}"
        if atom.kind == "bullet":
            if atom.get("role"):
                target = atoms.get(atom.get("role"))
                if target is None:
                    errors.append(f"{where}: role {atom.get('role')!r} does not exist. "
                                  f"Every bullet must belong to a known role.")
                elif target.kind != "role":
                    errors.append(f"{where}: role {atom.get('role')!r} is a "
                                  f"{target.kind}, not a role")
            if atom.get("project"):
                target = atoms.get(atom.get("project"))
                if target is None:
                    errors.append(f"{where}: project {atom.get('project')!r} does not exist")
                elif target.kind != "project":
                    errors.append(f"{where}: project {atom.get('project')!r} is a "
                                  f"{target.kind}, not a project")
        if atom.kind == "project":
            ctx = atom.get("context")
            if ctx not in PROJECT_CONTEXTS:
                target = atoms.get(ctx)
                if target is None or target.kind != "role":
                    errors.append(
                        f"{where}: context {ctx!r} must be a role id, or one of "
                        f"{', '.join(PROJECT_CONTEXTS)}. A personal project is "
                        f"never credited to an employer.")
        if atom.get("reword_of"):
            if atom.get("reword_of") not in atoms:
                errors.append(f"{where}: reword_of {atom.get('reword_of')!r} does not exist")
            elif atom.get("reword_of") == atom.id:
                errors.append(f"{where}: reword_of points at itself")


def _warnings(inv: Inventory, rel_of) -> None:
    seen: dict[tuple, Atom] = {}
    for atom in inv.atoms.values():
        for text in [atom.get("text") or ""] + [p.get("text", "") for p in atom.phrasings]:
            hedges = find_hedges(text)
            if hedges:
                inv.warnings.append(
                    f"{rel_of(atom.source)}: {atom.label()} hedges a figure "
                    f"({', '.join(hedges)}). State it plainly, e.g. '50%', and "
                    f"record basis = \"estimate\" (D-37).")
        if atom.kind not in ("bullet", "project", "summary"):
            continue
        toks = frozenset(number_tokens(atom.get("text") or ""))
        if not toks:
            continue
        key = (atom.kind, atom.get("role") or atom.get("project") or atom.get("context"), toks)
        other = seen.get(key)
        if other and not atom.get("reword_of") and not other.get("reword_of"):
            inv.warnings.append(
                f"{atom.label()} and {other.label()} state the same figures "
                f"({', '.join(sorted(map(str, toks)))}). If one rewords the other, "
                f"mark it with reword_of, or merge them as phrasings (D-43).")
        seen.setdefault(key, atom)


def load_inventory(ws: Workspace, *, include_pending: bool = False) -> Inventory:
    """Load confirmed atoms (and optionally pending ones). Raises
    JobforgeError listing every problem found."""
    errors: list[str] = []
    atoms: dict[str, Atom] = {}
    folders = [ws.atoms_dir] + ([ws.pending_dir] if include_pending else [])
    for folder in folders:
        for path in read_files(folder):
            if not ws.contains(path):  # never read a file outside (#28, F3)
                errors.append(ws.outside_message(path))
                continue
            for atom in parse_file(path, ws.rel(path), errors):
                if atom.id in atoms:
                    errors.append(f"{ws.rel(path)}: {atom.label()}: id already used "
                                  f"in {ws.rel(atoms[atom.id].source)}")
                    continue
                atoms[atom.id] = atom
    check_references(atoms, ws.rel, errors)
    if errors:
        raise JobforgeError("Your atoms have problems. Fix these and try again:", errors)
    inv = Inventory(atoms)
    _warnings(inv, ws.rel)
    return inv


def pending_ids(ws: Workspace) -> set[str]:
    """IDs currently waiting in profile/pending/ (parse problems ignored;
    `confirm` reports those)."""
    ids: set[str] = set()
    for path in read_files(ws.pending_dir):
        if ws.contains(path):
            ids.update(a.id for a in parse_file(path, ws.rel(path), []))
    return ids
