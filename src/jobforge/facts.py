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
import unicodedata
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation

_MULT = {"k": Decimal(1_000), "thousand": Decimal(1_000),
         "m": Decimal(1_000_000), "mm": Decimal(1_000_000),
         "million": Decimal(1_000_000), "b": Decimal(1_000_000_000),
         "bn": Decimal(1_000_000_000), "billion": Decimal(1_000_000_000)}

# Currency, by symbol before the figure or by word after it. Dollars are ""
# so the common case reads plainly; other currencies never match dollars.
# "pounds" is left out: it is as often a weight.
_CURRENCY = {"$": "", "dollar": "", "dollars": "", "usd": "",
             "€": "€", "euro": "€", "euros": "€", "eur": "€",
             "£": "£", "gbp": "£"}

NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"(?:(?P<sym>[$€£])\s?)?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<dec>\.\d+)?"
    r"(?:\s?(?P<unit>%|per\s?cent\b|x\b|times\b|k\b|mm\b|m\b|thousand\b|million\b"
    r"|bn\b|b\b|billion\b))?"
    r"(?:\s?(?P<cur>dollars?\b|usd\b|euros?\b|eur\b|gbp\b))?",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class Token:
    kind: str   # "money" | "percent" | "times" | "number"
    value: str  # normalized decimal string
    currency: str = ""  # money only: "" for dollars, else the symbol
    # As written, for the precision check (#11); not part of equality, so
    # "76.0%" and "76%" are the same figure.
    places: int = field(default=0, compare=False)  # decimal places written
    shown: str = field(default="", compare=False)

    def __str__(self) -> str:
        if self.kind == "money":
            return f"{self.currency or '$'}{self.value}"
        if self.kind == "percent":
            return f"{self.value}%"
        if self.kind == "times":
            return f"{self.value}x"
        return self.value


def _norm(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s


def number_tokens(text: str) -> list[Token]:
    """Figures in `text`. NFKC first, so a fullwidth "１４％" is "14%" and
    cannot slip past as something else (issue #1)."""
    out: list[Token] = []
    for m in NUMBER_RE.finditer(unicodedata.normalize("NFKC", text)):
        raw = m.group("int").replace(",", "") + (m.group("dec") or "")
        try:
            val = Decimal(raw)
        except InvalidOperation:  # pragma: no cover - regex guarantees digits
            continue
        unit = re.sub(r"\s", "", (m.group("unit") or "").lower())
        cur_key = m.group("sym") or (m.group("cur") or "").lower()
        currency = _CURRENCY.get(cur_key) if cur_key else None
        if unit in ("%", "percent"):
            out.append(Token("percent", _norm(val)))
        elif unit in ("x", "times"):
            out.append(Token("times", _norm(val)))
        elif unit in _MULT:
            val *= _MULT[unit]
            out.append(Token("number", _norm(val)) if currency is None
                       else Token("money", _norm(val), currency))
        elif currency is not None:
            out.append(Token("money", _norm(val), currency))
        else:
            out.append(Token("number", _norm(val)))
        # A multiplier moves the decimal point ("$1.2M"), so places only
        # count for a figure written in full.
        dec = m.group("dec") or ""
        out[-1] = replace(out[-1], places=0 if unit in _MULT else max(len(dec) - 1, 0),
                          shown=m.group(0).strip())
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


# Cyrillic and Greek letters that look like Latin ones. Folded before terms
# are matched, so "SАP" with a Cyrillic А is still SAP (issue #1).
_LOOKALIKES = str.maketrans(
    "АВЕКМНОРСТХУЅаеорсухіјѕԁԛԝ"   # Cyrillic
    "ΑΒΕΖΗΙΚΜΝΟΡΤΥΧοιν",          # Greek
    "ABEKMHOPCTXYSaeopcyxijsdqw"
    "ABEZHIKMNOPTYXoiv",
)


def fold(text: str) -> str:
    """Text with compatibility forms (fullwidth letters) and look-alike
    letters mapped to plain Latin, for matching only."""
    return unicodedata.normalize("NFKC", text).translate(_LOOKALIKES)


def term_in(term: str, text: str) -> bool:
    """Whole-word, case-insensitive match. Terms of two characters or fewer
    ("Go", "C", "R") match case-sensitively, so "go" in prose is not the Go
    language. Look-alike letters count as the letter they imitate."""
    term = fold(term.strip())
    if not term:
        return False
    flags = 0 if len(term) <= 2 else re.IGNORECASE
    pattern = r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])"
    return re.search(pattern, fold(text), flags) is not None


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """Rough sentence split, good enough for employer attribution in prose.
    Splits on . ! ? followed by whitespace and a capital or digit, without
    breaking decimals or URLs."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", text.strip())
    return [p.strip() for p in parts if p.strip()]
