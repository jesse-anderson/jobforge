"""`jobforge confirm`: the user decides which drafted facts become real.

Agents write drafted atoms to `profile/pending/`. Nothing there is used until
the user keeps it here (D-35, SOW A-3). Kept atoms are appended to
`profile/atoms/confirmed.toml`, so a hand-edited atom file is never rewritten
and its comments survive. Pending files are the agent's drafts, so they are
rewritten to hold only what is still undecided.

A job-related fact must belong to a known role; one that does not cannot be
kept (D-40).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import tomlw
from .atoms import (CONFIRM_ORDER, Atom, Inventory, check_references, load_inventory,
                    parse_file, read_files)
from .errors import JobforgeError
from .workspace import Workspace

CONFIRMED_FILE = "confirmed.toml"

NO_TERMINAL = ("`jobforge confirm` asks you about each drafted fact, so it needs a "
               "terminal you can type in, and this one cannot take answers. An agent's "
               "shell, or a `!` command inside an agent, cannot answer for you. Open a "
               "terminal window yourself and run:\n\n  cd \"{root}\"\n  jobforge confirm")


@dataclass
class Outcome:
    kept: list[str]
    dropped: list[str]
    skipped: list[str]
    refused: list[str]


_FIELD_LABELS = (
    ("text", "Text"), ("title", "Title"), ("name", "Name"), ("school", "School"),
    ("credential", "Credential"), ("field", "Field"), ("label", "Label"),
    ("items", "Items"), ("issuer", "Issuer"), ("date", "Date"), ("expires", "Expires"),
    ("location", "Location"), ("details", "Details"), ("url", "URL"),
    ("writeup_url", "Writeup URL"), ("url_status", "URL status"),
    ("aliases", "Also called"), ("facts", "Also states"), ("reword_of", "Rewords"), ("tags", "Tags"),
)


def describe(atom: Atom, owner: Atom | None) -> str:
    lines = [f"{atom.kind.upper()}  {atom.id}"]
    if atom.kind == "role":
        lines.append(f"  {atom.get('title')} at {atom.get('employer')}, "
                     f"{atom.get('start')} to {atom.get('end') or 'present'}")
    if owner is not None and atom.kind != "role":
        lines.append(f"  Employer: {owner.get('employer')} (role {owner.id!r}, "
                     f"{owner.get('title')})")
    elif atom.kind in ("bullet", "project"):
        ctx = atom.get("context") or atom.get("project") or atom.get("role")
        lines.append(f"  Belongs to: {ctx}")
    # Every field the user is asked to keep is shown. A date or field of study
    # confirmed unseen is still a fact the check will trust (issue #2 run).
    shown = {"id", "employer", "start", "end", "role", "project", "context",
             "phrasing", "basis", "defense"} | ({"title"} if atom.kind == "role" else set())
    for key, label in _FIELD_LABELS:
        value = atom.get(key)
        if key in shown or value in (None, "", []):
            continue
        shown.add(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"  {label}: {value}")
    for key, value in atom.fields.items():  # anything a later schema adds
        if key not in shown and value not in (None, "", []):
            lines.append(f"  {key.capitalize()}: {value}")
    if atom.get("basis"):
        lines.append(f"  How you know: {atom.get('basis')}")
    if atom.get("defense"):
        lines.append(f"  Your explanation: {atom.get('defense')}")
    for p in atom.phrasings:
        lines.append(f"  Also worded ({p.get('use', 'any')}): {p.get('text')}")
    return "\n".join(lines)


def serialize(atom: Atom) -> str:
    fields = {k: v for k, v in atom.fields.items() if k != "phrasing"}
    fields = {"id": fields.pop("id"), **fields}
    children = {"phrasing": atom.phrasings} if atom.phrasings else None
    return tomlw.table_array_entry(atom.kind, fields, children)


def _append(path: Path, text: str) -> None:
    prefix = ""
    if not path.exists():
        prefix = ("# Facts you confirmed with `jobforge confirm`. You may edit this "
                  "file by hand;\n# Jobforge only ever appends to it.\n\n")
    elif not path.read_text(encoding="utf-8").endswith("\n\n"):
        prefix = "\n"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(prefix + text)


def _rewrite_pending(path: Path, remaining: list[Atom]) -> None:
    if not remaining:
        path.unlink()
        return
    header = ("# Drafted facts waiting for `jobforge confirm`. Nothing here is used "
              "until you keep it.\n\n")
    # Write beside it, then replace: a Ctrl+C mid-write never leaves the
    # drafts still waiting there empty or half-written (#77).
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(header + "\n".join(serialize(a) for a in remaining),
                       encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def run_confirm(ws: Workspace, ask: Callable[[str], str] | None = None,
                say: Callable[[str], None] | None = None) -> Outcome:
    interactive = ask is not None or (sys.stdin is not None and sys.stdin.isatty())
    ask = ask or input
    say = say or print
    confirmed = load_inventory(ws)  # raises if confirmed atoms are broken
    ws.check_inside(ws.atoms_dir / CONFIRMED_FILE)  # confirm appends to it (#28)

    errors: list[str] = []
    per_file: dict[Path, list[Atom]] = {}
    for path in read_files(ws.pending_dir):
        if not ws.contains(path):
            errors.append(ws.outside_message(path))
            continue
        per_file[path] = parse_file(path, ws.rel(path), errors)
    if errors:
        raise JobforgeError("Some drafted facts in profile/pending/ are malformed. "
                            "Fix or delete them first:", errors)
    # A pending fact identical to a confirmed one was already kept: an earlier
    # run was stopped before it cleared pending/ (#77). Clear it now.
    already = {a.id for atoms in per_file.values() for a in atoms
               if (c := confirmed.atoms.get(a.id)) and (c.kind, c.fields) == (a.kind, a.fields)}
    if already:
        for path, atoms in per_file.items():
            if any(a.id in already for a in atoms):
                per_file[path] = [a for a in atoms if a.id not in already]
                _rewrite_pending(path, per_file[path])
        say(f"Cleared from profile/pending/, already confirmed: {', '.join(sorted(already))}.")
    pending = [a for atoms in per_file.values() for a in atoms]
    if not pending:
        say("Nothing to confirm: profile/pending/ is empty.")
        return Outcome([], [], [], [])

    for atom in pending:
        if atom.id in confirmed.atoms:
            errors.append(f"{ws.rel(atom.source)}: {atom.label()} has the same id as a "
                          f"confirmed atom. Rename one of them.")
    if errors:
        raise JobforgeError("Cannot confirm:", errors)
    if not interactive:
        raise JobforgeError(NO_TERMINAL.format(root=ws.root))

    order = sorted(pending, key=lambda a: CONFIRM_ORDER.index(a.kind))
    live = dict(confirmed.atoms)
    out = Outcome([], [], [], [])
    decided: set[str] = set()
    target = ws.atoms_dir / CONFIRMED_FILE
    say(f"{len(order)} drafted fact(s) to review. For each: [k]eep, [d]rop, "
        f"[s]kip (decide later; edit the file in profile/pending/), [q]uit.\n")

    for atom in order:
        problems: list[str] = []
        trial = dict(live)
        trial[atom.id] = atom
        check_references(trial, ws.rel, problems, only={atom.id})
        missing_role = bool(problems)
        if atom.kind == "bullet" and not (atom.get("defense") or "").strip():
            # D-36: how the user knows it, in their words. Prep sheets are
            # built from it (D-38), so a new bullet is not kept without it.
            problems.append(
                f"no defense note. Add how you know it to {ws.rel(atom.source)}, "
                f"e.g. defense = \"Monthly report from the warehouse system\", "
                f"then run confirm again (D-36).")
        owner = Inventory(trial).owner_role(atom)
        say(describe(atom, owner))
        if problems:
            say("  Cannot keep this yet:\n" + "\n".join(f"    {p}" for p in problems))
            if atom.kind == "bullet" and missing_role:
                say("  (Keep or add the role it belongs to first, then run confirm again.)")
            out.refused.append(atom.id)
            say("")
            continue
        while True:
            try:
                answer = ask("  Keep this fact? [k/d/s/q] ").strip().lower()[:1]
            except EOFError:
                say("\n  Input ended, so confirm stopped here. Your answers so far are "
                    "saved; the rest stay in profile/pending/.")
                answer = "q"
            except KeyboardInterrupt:  # Ctrl+C: the natural way to quit (#77)
                say("\n  Stopped. Your answers so far are saved; the rest stay in "
                    "profile/pending/.")
                answer = "q"
            if answer in ("k", "d", "s", "q"):
                break
            say("  Please answer k, d, s, or q.")
        say("")
        if answer == "q":
            out.skipped.extend(a.id for a in order if a.id not in decided
                               and a.id not in out.refused)
            break
        if answer == "s":
            out.skipped.append(atom.id)
            continue
        decided.add(atom.id)
        if answer == "k":
            _append(target, serialize(atom))
            live[atom.id] = atom
            out.kept.append(atom.id)
        else:
            out.dropped.append(atom.id)

    gone = set(out.kept) | set(out.dropped)
    for path, atoms in per_file.items():
        if any(a.id in gone for a in atoms):
            _rewrite_pending(path, [a for a in atoms if a.id not in gone])

    load_inventory(ws)  # prove the confirmed set still loads cleanly
    say(f"Kept {len(out.kept)}, dropped {len(out.dropped)}, left pending "
        f"{len(out.skipped) + len(out.refused)}.")
    return out
