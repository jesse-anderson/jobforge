"""Pull checkable facts out of text.

The fact check (D-32) is mechanical: wording is free, but every checkable
token in a deliverable must appear in an atom the plan cites. This module
finds those tokens. It deliberately knows nothing about plans or atoms.

A number token is normalized to (kind, value) so equivalent spellings match:
"$12,000", "$12k" and "$12K" are all ("money", "12000"); "30%" and
"30 percent" are both ("percent", "30"). Precision is kept, so "49.7%" does
not match "50%" (D-37: no more precision than the basis supports).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_MULT = {"k": Decimal(1_000), "m": Decimal(1_000_000), "mm": Decimal(1_000_000),
         "million": Decimal(1_000_000), "b": Decimal(1_000_000_000),
         "bn": Decimal(1_000_000_000), "billion": Decimal(1_000_000_000)}

NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<money>\$\s?)?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<dec>\.\d+)?"
    r"(?:\s?(?P<unit>%|percent\b|x\b|times\b|k\b|mm\b|m\b|million\b|bn\b|b\b|billion\b))?",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class Token:
    kind: str   # "money" | "percent" | "times" | "number"
    value: str  # normalized decimal string

    def __str__(self) -> str:
        if self.kind == "money":
            return f"${self.value}"
        if self.kind == "percent":
            return f"{self.value}%"
        if self.kind == "times":
            return f"{self.value}x"
        return self.value


def _norm(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s


def number_tokens(text: str) -> list[Token]:
    out: list[Token] = []
    for m in NUMBER_RE.finditer(text):
        raw = m.group("int").replace(",", "") + (m.group("dec") or "")
        try:
            val = Decimal(raw)
        except InvalidOperation:  # pragma: no cover - regex guarantees digits
            continue
        unit = (m.group("unit") or "").lower()
        if unit in ("%", "percent"):
            out.append(Token("percent", _norm(val)))
        elif unit in ("x", "times"):
            out.append(Token("times", _norm(val)))
        elif unit in _MULT:
            kind = "money" if m.group("money") else "number"
            out.append(Token(kind, _norm(val * _MULT[unit])))
        elif m.group("money"):
            out.append(Token("money", _norm(val)))
        else:
            out.append(Token("number", _norm(val)))
    return out


# A hedge word directly before a figure. "about 50%" invites the question it
# tries to avoid (D-37). "over" and "more than" are claims of a bound, not
# hedges, so they are allowed.
HEDGE_RE = re.compile(
    r"(?:~\s?|\b(?:about|approximately|approx\.?|roughly|nearly|almost|around|circa"
    r"|an estimated|estimated|some)\s+)\$?\d[\d,]*(?:\.\d+)?%?",
    re.IGNORECASE,
)


def find_hedges(text: str) -> list[str]:
    return [m.group(0) for m in HEDGE_RE.finditer(text)]


def term_in(term: str, text: str) -> bool:
    """Whole-word, case-insensitive match. Terms of two characters or fewer
    ("Go", "C", "R") match case-sensitively, so "go" in prose is not the Go
    language."""
    term = term.strip()
    if not term:
        return False
    flags = 0 if len(term) <= 2 else re.IGNORECASE
    pattern = r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])"
    return re.search(pattern, text, flags) is not None


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """Rough sentence split, good enough for employer attribution in prose.
    Splits on . ! ? followed by whitespace and a capital or digit, without
    breaking decimals or URLs."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", text.strip())
    return [p.strip() for p in parts if p.strip()]
