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
# "m" and "mm" are also meters and millimeters, so they mean million only
# beside a currency ("$5mm", "4m dollars"). Elsewhere the figure is taken as
# written, 1:1 (issue #10).
_MONEY_ONLY = {"m", "mm"}

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
    # "76.0%" and "76%" are the same figure. `step` is the smallest amount the
    # figure states: 0.1 for "76.0%", 100000 for "$1.2M", 1 for "$1,200,000".
    step: Decimal = field(default=Decimal(1), compare=False)
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
        mult = Decimal(1)
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
        elif unit in _MONEY_ONLY and currency is None:
            out.append(Token("number", _norm(val)))
        elif unit in _MULT:
            mult = _MULT[unit]
            val *= mult
            out.append(Token("number", _norm(val)) if currency is None
                       else Token("money", _norm(val), currency))
        elif currency is not None:
            out.append(Token("money", _norm(val), currency))
        else:
            out.append(Token("number", _norm(val)))
        # "$1.20M" states the figure to $10,000: the last written digit's
        # place, times the multiplier.
        places = max(len(m.group("dec") or "") - 1, 0)
        out[-1] = replace(out[-1], step=Decimal(1).scaleb(-places) * mult,
                          shown=m.group(0).strip())
    return out


# Common units, each under one name however it is written (issue #10). The
# check compares units, never converts them, so the list only has to name
# what people write on a resume.
#
# Abbreviations match exactly as cased: "MB" (bytes) and "Mb" (bits) differ
# eightfold, and "2MM" and "$5M" stay money slang. "in", "s", "g", and "A"
# are left out: "12 in Chicago" is not inches.
_UNIT_ABBR = {
    # length, area, volume
    "µm": "µm", "mm": "mm", "cm": "cm", "m": "m", "km": "km", "ft": "ft", "yd": "yd",
    "mi": "mi", "sq ft": "ft2", "sq. ft.": "ft2", "sqft": "ft2", "ft²": "ft2",
    "sq m": "m2", "m²": "m2", "cu ft": "ft3", "cu yd": "yd3", "m³": "m3",
    "L": "L", "mL": "mL", "ml": "mL", "gal": "gal", "bbl": "bbl",
    # weight
    "mg": "mg", "kg": "kg", "lb": "lb", "lbs": "lb", "oz": "oz",
    # time
    "ns": "ns", "µs": "µs", "ms": "ms", "sec": "sec", "secs": "sec", "min": "min",
    "mins": "min", "hr": "hr", "hrs": "hr", "wk": "wk", "wks": "wk", "yr": "yr", "yrs": "yr",
    # data, bandwidth, frequency
    "KB": "KB", "kB": "KB", "MB": "MB", "GB": "GB", "TB": "TB", "PB": "PB",
    "Kb": "Kb", "Mb": "Mb", "Gb": "Gb", "Tb": "Tb",
    "kbps": "kbps", "Kbps": "kbps", "Mbps": "Mbps", "Gbps": "Gbps", "Tbps": "Tbps",
    "Hz": "Hz", "kHz": "kHz", "MHz": "MHz", "GHz": "GHz",
    # electrical and energy
    "mV": "mV", "V": "V", "kV": "kV", "mA": "mA", "mAh": "mAh", "W": "W", "kW": "kW",
    "MW": "MW", "GW": "GW", "kWh": "kWh", "MWh": "MWh", "GWh": "GWh",
    "BTU": "BTU", "btu": "BTU",
    # pressure, flow, speed, temperature
    "psi": "psi", "PSI": "psi", "bar": "bar", "kPa": "kPa", "MPa": "MPa",
    "gpm": "gpm", "GPM": "gpm", "cfm": "cfm", "CFM": "cfm", "rpm": "rpm", "RPM": "rpm",
    "mph": "mph", "MPH": "mph", "kph": "km/h", "km/h": "km/h", "°F": "°F", "°C": "°C",
}
# Words match in any case, with or without a plural "s".
_UNIT_WORDS = {
    "micron": "µm", "millimeter": "mm", "millimetre": "mm", "centimeter": "cm",
    "centimetre": "cm", "meter": "m", "metre": "m", "kilometer": "km", "kilometre": "km",
    "inch": "in", "inches": "in", "foot": "ft", "feet": "ft", "yard": "yd", "mile": "mi",
    "square foot": "ft2", "square feet": "ft2", "square meter": "m2", "square metre": "m2",
    "acre": "acre", "hectare": "ha", "cubic foot": "ft3", "cubic feet": "ft3",
    "cubic yard": "yd3", "cubic meter": "m3", "cubic metre": "m3",
    "liter": "L", "litre": "L", "milliliter": "mL", "millilitre": "mL", "gallon": "gal",
    "barrel": "bbl", "milligram": "mg", "gram": "g", "kilogram": "kg", "kilo": "kg",
    "pound": "lb", "ounce": "oz", "ton": "ton", "tonne": "tonne",
    "nanosecond": "ns", "microsecond": "µs", "millisecond": "ms", "second": "sec",
    "minute": "min", "hour": "hr", "day": "day", "week": "wk", "month": "mo", "year": "yr",
    "kilobyte": "KB", "megabyte": "MB", "gigabyte": "GB", "terabyte": "TB",
    "petabyte": "PB", "hertz": "Hz", "kilohertz": "kHz", "megahertz": "MHz",
    "gigahertz": "GHz", "volt": "V", "kilovolt": "kV", "amp": "A", "ampere": "A",
    "milliamp": "mA", "watt": "W", "kilowatt": "kW", "megawatt": "MW",
    "kilowatt-hour": "kWh", "kilowatt hour": "kWh", "megawatt-hour": "MWh",
    "megawatt hour": "MWh", "miles per hour": "mph", "kilometers per hour": "km/h",
    "knot": "kn", "gallons per minute": "gpm", "cubic feet per minute": "cfm",
    "revolutions per minute": "rpm", "degree fahrenheit": "°F", "degrees fahrenheit": "°F",
    "degree celsius": "°C", "degrees celsius": "°C",
}


# Text is NFKC-normalized before matching ("µ" becomes Greek "μ", "²" becomes
# "2"), so the table is too.
_UNIT_ABBR_N = {unicodedata.normalize("NFKC", k): v for k, v in _UNIT_ABBR.items()}


def _alt(words):
    """Longest first, so "sq ft" wins over "ft"; a space matches any run."""
    return "|".join(re.escape(w).replace(r"\ ", r"\s+")
                    for w in sorted(words, key=len, reverse=True))


# A figure, at most two words, then a unit: "650,000 accident-free miles".
UNIT_RE = re.compile(
    r"(?<![\w.])(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?"
    r"(?:\s+[A-Za-z][\w-]*){0,2}?\s*(?:(?<=\d)|(?<=\s))"
    rf"(?:(?P<abbr>{_alt(_UNIT_ABBR_N)})|(?i:(?P<word>{_alt(_UNIT_WORDS)})s?))(?![\w-])")


@dataclass(frozen=True)
class UnitFigure:
    value: str  # normalized, as in Token
    unit: str   # one name per unit: "mi" for mi, mile, miles
    shown: str  # as written, for messages


def unit_figures(text: str) -> list[UnitFigure]:
    """Figures written with a common unit. The fact check holds each to the
    unit its atom uses: no rewording "miles" as "km" (issue #10)."""
    out = []
    for m in UNIT_RE.finditer(unicodedata.normalize("NFKC", text)):
        val = Decimal(m.group("int").replace(",", "") + (m.group("dec") or ""))
        written = m.group("abbr") or m.group("word")
        key = re.sub(r"\s+", " ", written)
        unit = _UNIT_ABBR_N[key] if m.group("abbr") else _UNIT_WORDS[key.lower()]
        out.append(UnitFigure(_norm(val), unit, m.group(0)))
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
