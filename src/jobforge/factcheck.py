"""The fact check: nothing in a deliverable that the user did not confirm.

Mechanical, never model-judged (D-32). For every line the agent authored or
selected:

- Every figure (number, percentage, money, multiple, year) must appear in an
  atom the line cites. Wording around it is free.
- No hedged figures, and no more precision than the atom states (D-37).
- A bullet's text names no employer but its own; a cover-letter sentence that
  names an employer carries only figures and tools from that employer's atoms
  (D-40). Personal, school, and volunteer work belongs to no employer.
- Nothing on the never-claim list; no known tool or credential the cited atoms
  do not mention.
- A cited or named project with a live URL shows the full URL (D-42); a host
  or one path segment is not enough (FINDINGS F22).
- Voice rules apply to text the user authors, never to text quoted from the
  posting (FINDINGS F21).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .atoms import Atom, Inventory
from .facts import (find_hedges, number_tokens, split_sentences, term_in, unit_figures,
                    word_count)
from .plan import Line, ResolvedPlan
from .profile import Profile, display_url
from .scan import find_mixed_script


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def _pool_text(atoms: list[Atom], inv: Inventory) -> str:
    """All text the cited atoms state, plus the role each belongs to (a bullet
    may mention its own employer, title, and dates)."""
    texts: list[str] = []
    seen: set[str] = set()
    for atom in atoms:
        chain = [atom]
        role = inv.owner_role(atom)
        if role:
            chain.append(role)
        if atom.kind == "bullet" and atom.get("project"):
            proj = inv.get(atom.get("project"))
            if proj:
                chain.append(proj)
        for a in chain:
            if a.id not in seen:
                seen.add(a.id)
                texts.extend(a.texts())
    return "\n".join(texts)


def vocabulary(inv: Inventory, profile: Profile) -> list[str]:
    """Tool, skill, and credential terms the check can recognize: every skill
    item, every credential name, and the never-claim list."""
    terms: set[str] = set()
    for skill in inv.of_kind("skill"):
        for item in skill.get("items") or []:
            terms.add(item.strip())
    for cred in inv.of_kind("credential"):
        terms.add(cred.get("name").strip())
    terms.update(t for t in profile.never_claim)
    return sorted((t for t in terms if t), key=len, reverse=True)


def _strip_contact(text: str, profile: Profile) -> str:
    """The text with the user's own contact details removed. "Reach me at
    555-0100" states no fact, but the profile is not a source of facts
    either: its digits must not let a letter claim "100 drivers" (issue #1)."""
    items = [profile.phone, profile.email, *profile.links,
             *(display_url(u) for u in profile.links)]
    for item in sorted((i for i in items if i), key=len, reverse=True):
        text = re.sub(re.escape(item), " ", text, flags=re.IGNORECASE)
    return text


def check_figures(text: str, pool: str, where: str, rep: Report, extra_pool: str = "") -> None:
    # Each figure -> its most precise written form in the facts.
    have: dict = {}
    for tok in number_tokens(pool + "\n" + extra_pool):
        if tok not in have or tok.step < have[tok].step:
            have[tok] = tok
    for tok in number_tokens(text):
        if tok not in have:
            rep.errors.append(
                f"{where}: the figure {tok} is not in the facts this line cites. "
                f"Use a figure the atom states, or add the fact (with `jobforge "
                f"confirm`) before using it.")
        elif tok.step < have[tok].step:
            # "76.00%" for a confirmed "76.0%", or "$1,200,000" for "$1.2M",
            # claims exactness the user never stated (D-37, #11). A coarser
            # figure ("76%", "$1.2M" for "$1,200,000") claims less, so passes.
            rep.errors.append(
                f"{where}: the figure {tok.shown} is more precise than the facts "
                f"({have[tok].shown}). Write it as the atom does (D-37).")
    # Same figure, other unit: "650,000 km" for an atom's "650,000 miles" is a
    # different fact. Only units both sides write are compared (#10).
    pool_units: dict[str, list] = {}
    for uf in unit_figures(pool + "\n" + extra_pool):
        pool_units.setdefault(uf.value, []).append(uf)
    for uf in unit_figures(text):
        stated = pool_units.get(uf.value, [])
        if stated and uf.unit not in {s.unit for s in stated}:
            rep.errors.append(
                f"{where}: {uf.shown} changes the unit; the facts say {stated[0].shown}. "
                f"Keep the unit the atom uses; never convert one unit to another.")
    for hedge in find_hedges(text):
        rep.errors.append(f"{where}: hedged figure {hedge!r}. State figures plainly "
                          f"('50%', not 'about 50%') (D-37).")


def check_terms(text: str, pool: str, vocab: list[str], profile: Profile, where: str,
                rep: Report) -> None:
    for term in profile.never_claim:
        if term_in(term, text):
            rep.errors.append(f"{where}: claims {term!r}, which your profile says "
                              f"never to claim.")
    never = {t.lower() for t in profile.never_claim}
    for term in vocab:
        if term.lower() in never:
            continue
        if term_in(term, text) and not term_in(term, pool):
            rep.errors.append(f"{where}: mentions {term!r}, but none of the atoms this "
                              f"line cites do. Cite the atom where you used it.")


def employers_named(text: str, inv: Inventory) -> dict[str, str]:
    """Employer -> the name the text calls it by, full name or alias (#9).
    An employer named twice ("Northwind Distribution, or Northwind") is one."""
    out: dict[str, str] = {}
    for employer, names in inv.employer_names().items():
        written = next((n for n in names if term_in(n, text)), None)
        if written:
            out[employer] = written
    return out


def check_employers(text: str, line_atoms: list[Atom], inv: Inventory, where: str,
                    rep: Report) -> None:
    """A resume line may only name the employer its facts belong to."""
    own = {inv.employer_of(a) for a in line_atoms} - {None}
    for employer, written in employers_named(text, inv).items():
        if employer not in own:
            owners = ", ".join(sorted(own)) or "no employer (personal, school, or volunteer work)"
            rep.errors.append(f"{where}: names {written!r}, but this fact belongs to "
                              f"{owners} (D-40).")


def _dash_chars() -> dict[str, str]:
    """Every dash or hyphen but the ASCII one, with its name (#88): the dash
    punctuation in the general and supplemental punctuation blocks and the
    small and fullwidth forms, plus the minus sign. Hyphens that belong to
    another script (Hebrew maqaf, Armenian hyphen, Japanese wave dash) live in
    that script's block, join words there, and are left alone."""
    blocks = [*range(0x2010, 0x2E80), *range(0xFE30, 0xFF10)]
    return {chr(c): unicodedata.name(chr(c)).lower() for c in blocks
            if unicodedata.category(chr(c)) == "Pd" or c == 0x2212}


_DASHES = _dash_chars()


def check_voice(text: str, profile: Profile, where: str, rep: Report) -> None:
    if profile.ban_dashes:
        for ch in sorted(set(text) & _DASHES.keys(), key=text.index):
            name = _DASHES[ch]
            article = "an" if name[0] in "aeiou" else "a"
            fix = ("Type a plain hyphen (-) instead." if "hyphen" in name
                   else "Use a comma, colon, or period.")
            rep.errors.append(f"{where}: contains {article} {name} "
                              f"({ch}, U+{ord(ch):04X}). {fix}")
    lower = text.lower()
    words = set(re.findall(r"[a-z][a-z'-]*", lower))
    hits = sorted(w for w in profile.banned_words if w in words)
    if hits:
        rep.errors.append(f"{where}: uses banned word(s) {hits}.")
    phrase_hits = [p for p in profile.banned_phrases if p in lower]
    if phrase_hits:
        rep.errors.append(f"{where}: uses banned phrase(s) {phrase_hits}.")


def check_scripts(text: str, where: str, rep: Report) -> None:
    for m in find_mixed_script(text):
        rep.errors.append(f"{where}: {m}. Retype the word in plain letters; an "
                          f"ATS will not match it as written.")


def check_atom_ids(text: str, inv: Inventory, where: str, rep: Report) -> None:
    leaked = sorted(a for a in inv.atoms if "." in a and re.search(
        r"(?<![\w.])" + re.escape(a) + r"(?![\w])", text))
    if leaked:
        rep.errors.append(f"{where}: contains atom id(s) {leaked}. Ids are internal; "
                          f"cite atoms in `cites`, not in the prose.")


def url_key(url: str) -> str:
    """Comparable form of a URL: no scheme, no www., no trailing slash."""
    return display_url(url).lower()


def live_url(atom: Atom) -> str | None:
    if atom.get("url_status") == "dead":
        return None
    return atom.get("url") or None


def check_line(line: Line, inv: Inventory, profile: Profile, vocab: list[str],
               rep: Report) -> None:
    pool = _pool_text(line.cites, inv)
    check_figures(line.text, pool, line.where, rep)
    check_terms(line.text, pool, vocab, profile, line.where, rep)
    check_employers(line.text, line.cites, inv, line.where, rep)
    check_atom_ids(line.text, inv, line.where, rep)
    check_scripts(line.text, line.where, rep)
    # Voice rules are for text the agent wrote. An atom rendered as the user
    # wrote it is their own wording and is not second-guessed.
    if line.owner is None or line.text != (line.owner.get("text") or "").strip():
        check_voice(line.text, profile, line.where, rep)


def check_letter(plan: ResolvedPlan, inv: Inventory, profile: Profile, vocab: list[str],
                 rep: Report, job: dict | None = None) -> None:
    letter = plan.letter
    if letter is None:
        return
    text = letter.text()
    where = "cover_letter"
    cites = letter.cites
    # Figures about the employer, quoted from its own posting, are ground truth
    # too ("your 40 locations"). They are not claims about the user. How far
    # the posting is trusted depends on how it was captured (#16):
    #   json-ld    the posting itself: trusted quietly.
    #   manual     pasted, maybe a whole page: trusted, but every figure the
    #              letter takes only from it is named once for the user.
    #   page-text  the whole page, other listings included: its description
    #              is not trusted at all.
    posting = description = ""
    source = ""
    if job:
        source = str(job.get("source") or "manual")
        description = str(job.get("description", ""))
        posting = " ".join(str(job.get(k, "")) for k in ("company", "title", "location"))
        if source != "page-text":
            posting += " " + description
    facts = _pool_text(cites, inv)
    pool = "\n".join([facts, posting])

    check_voice(text, profile, where, rep)
    check_atom_ids(text, inv, where, rep)
    check_scripts(text, where, rep)
    for term in profile.never_claim:
        if term_in(term, text):
            rep.errors.append(f"{where}: claims {term!r}, which your profile says "
                              f"never to claim.")

    n = word_count(text)
    if n > profile.cover_letter_max_words:
        rep.errors.append(f"{where}: {n} words; the limit is "
                          f"{profile.cover_letter_max_words} (profile setting "
                          f"cover_letter_max_words). Cut it down.")

    employers = inv.employers()
    for i, sentence in enumerate(split_sentences(text), 1):
        sw = f"{where} sentence {i}"
        named = employers_named(sentence, inv)
        figures = _strip_contact(sentence, profile)
        if len(named) == 1:
            # Only that employer's facts may appear here.
            (employer, written), = named.items()
            bound = [a for a in cites if inv.employer_of(a) == employer]
            bound += employers[employer]
            scoped = _pool_text(bound, inv)
            check_figures(figures, scoped, f"{sw} (names {written!r})", rep)
            check_terms(sentence, scoped, vocab, profile, f"{sw} (names {written!r})", rep)
        else:
            if len(named) > 1:
                rep.warnings.append(f"{sw}: names {len(named)} employers "
                                    f"({', '.join(named.values())}); check each figure is "
                                    f"credited to the right one.")
            check_figures(figures, pool, sw, rep)
            check_terms(sentence, pool, vocab, profile, sw, rep)

    figures = number_tokens(_strip_contact(text, profile))
    own = set(number_tokens(facts))
    from_page = [t for t in figures if t not in own and t in set(number_tokens(description))]
    if from_page and source == "page-text":
        rep.warnings.append(
            f"{where}: {', '.join(dict.fromkeys(map(str, from_page)))} appear only in the "
            f"posting, which was saved from the whole page and may include other "
            f"listings. To quote the employer's figures, paste just the posting with "
            f"`jobforge prepare --from-text <file> --url <link> --force`; the link "
            f"makes it replace this capture instead of making a second folder.")
    elif from_page and source == "manual":
        rep.warnings.append(
            f"{where}: {', '.join(dict.fromkeys(map(str, from_page)))} come only from the "
            f"posting, not your facts. Check the pasted posting says this about the "
            f"employer, not about another job on the page.")

    # Projects: cited, or named by title, with a live URL -> full URL in text.
    mentioned = {a.id: a for a in cites if a.kind == "project"}
    for a in cites:
        if a.kind == "bullet" and a.get("project"):
            proj = inv.get(a.get("project"))
            if proj:
                mentioned[proj.id] = proj
    for proj in inv.of_kind("project"):
        if term_in(proj.get("title"), text):
            mentioned[proj.id] = proj
    text_l = text.lower()
    for proj in mentioned.values():
        url = live_url(proj)
        if url and url_key(url) not in text_l:
            rep.errors.append(
                f"{where}: mentions project {proj.get('title')!r} but not its URL. "
                f"Include {display_url(url)} so a reader can check it (D-42).")


def check_plan(plan: ResolvedPlan, inv: Inventory, profile: Profile,
               job: dict | None = None) -> Report:
    rep = Report()
    vocab = vocabulary(inv, profile)
    for line in plan.resume_lines():
        check_line(line, inv, profile, vocab, rep)
    check_letter(plan, inv, profile, vocab, rep, job)
    return rep
