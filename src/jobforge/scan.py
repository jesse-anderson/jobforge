"""Find characters that scramble an ATS but are invisible to a reader (D-31).

Zero-width characters split a keyword so it no longer matches; a soft hyphen
or a ligature glyph does the same; a non-breaking space where a space belongs
can glue two words into one token. None of them show on screen, which is the
problem. `apply` runs this over the text read back from every document.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_NAMED = {
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "‍": "zero-width joiner",
    "⁠": "word joiner",
    "﻿": "zero-width no-break space (BOM)",
    "­": "soft hyphen",
    " ": "non-breaking space",
    " ": "narrow non-breaking space",
    " ": "figure space",
    "᠎": "Mongolian vowel separator",
}
_BIDI = set("‪‫‬‭‮⁦⁧⁨⁩‎‏")
_LIGATURES = {chr(c) for c in range(0xFB00, 0xFB07)}


@dataclass(frozen=True)
class Hidden:
    char: str
    name: str
    index: int
    context: str

    def __str__(self) -> str:
        return f"{self.name} (U+{ord(self.char):04X}) near {self.context!r}"


def _name(ch: str) -> str | None:
    if ch in _NAMED:
        return _NAMED[ch]
    if ch in _BIDI:
        return "text direction control"
    if ch in _LIGATURES:
        return "ligature glyph"
    cat = unicodedata.category(ch)
    if cat == "Cc" and ch not in "\n\t\r":
        return "control character"
    if cat == "Co":
        return "private-use character"
    if cat == "Cf":
        return "invisible formatting character"
    if cat == "Cs":  # half of a broken character; no file can store it (#28)
        return "lone surrogate"
    return None


def find_hidden(text: str) -> list[Hidden]:
    found = []
    for i, ch in enumerate(text):
        name = _name(ch)
        if name:
            lo, hi = max(0, i - 20), min(len(text), i + 20)
            ctx = "".join(c if not _name(c) else "?" for c in text[lo:hi])
            found.append(Hidden(ch, name, i, " ".join(ctx.split())))
    return found


_LOOKALIKE_SCRIPTS = ("CYRILLIC", "GREEK")


@dataclass(frozen=True)
class MixedScript:
    word: str
    script: str  # "Cyrillic" or "Greek"

    def __str__(self) -> str:
        odd = ", ".join(f"U+{ord(c):04X}" for c in self.word
                        if unicodedata.name(c, "").startswith(self.script.upper()))
        return (f"the word {self.word!r} mixes Latin and {self.script} letters "
                f"({odd}) that look alike")


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    return unicodedata.name(ch, "").split(" ", 1)[0] or None


def find_mixed_script(text: str) -> list[MixedScript]:
    """Words that mix Latin letters with Cyrillic or Greek ones. They read
    as one word and match nothing: not a keyword in an ATS, not a term in
    the fact check (issue #1). A word wholly in another script is fine."""
    found = []
    for word in re.findall(r"\w+", text):
        scripts = {_script(c) for c in word} - {None}
        if "LATIN" in scripts:
            for other in _LOOKALIKE_SCRIPTS:
                if other in scripts:
                    found.append(MixedScript(word, other.capitalize()))
                    break
    return found


def clean(text: str) -> str:
    """Replace non-breaking spaces with spaces and drop the rest. Used on
    text that comes from outside (a job posting), never on the user's own
    atoms, which are reported instead of silently changed."""
    out = []
    for ch in text:
        name = _name(ch)
        if name is None:
            out.append(ch)
        elif ch in (" ", " ", " "):
            out.append(" ")
        elif ch in _LIGATURES:
            out.append(unicodedata.normalize("NFKC", ch))
    return "".join(out)
