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
        if self.kind in ("fraction", "multiple"):
            return self.shown or self.value  # "a third", "Tripled" (#84)
        return self.value


def _norm(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s


def number_tokens(text: str) -> list[Token]:
    """Figures in `text`, in digits or in words (#84), in the order written.
    NFKC first, so a fullwidth "１４％" is "14%" and cannot slip past as
    something else (issue #1)."""
    found = _digit_tokens(text) + _word_tokens(text)
    return [tok for _, tok in sorted(found, key=lambda pair: pair[0])]


def _digit_tokens(text: str) -> list[tuple[int, Token]]:
    out: list[Token] = []
    starts: list[int] = []
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
        starts.append(m.start())
    return list(zip(starts, out))


# --- Figures in words (#84) ---------------------------------------------------
# When a digit is refused, words are the first thing a model reaches for, so
# "forty", "thirty-five percent", "a third", and "tripled" are figures too.
# A cardinal is the same figure as its digits ("forty" is 40). A fraction or a
# multiple is a kind of its own until equivalences are decided: "a third" is
# not "33%" and "doubled" is not "2x", the safe direction.

_SMALL = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split(), start=2)}
_SCALE = {"hundred": 100, "dozen": 12}
_BIG = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_UNITS = "|".join(sorted([*_SMALL, *_TENS], key=len, reverse=True))
_WORD = "|".join(sorted([*_SMALL, *_TENS, *_SCALE, *_BIG], key=len, reverse=True))

# A run of number words: "thirty-five", "one hundred and twenty", "a dozen".
# It starts with a number word, or "a" before a scale ("a hundred"), never
# with a bare scale: "12 thousand" is the digit reader's.
CARDINAL_RE = re.compile(
    r"(?<![\w-])(?P<run>(?:(?:a\s+(?=(?:hundred|thousand|million|billion|dozen)\b))"
    rf"(?:{_WORD})|(?:{_UNITS}))\b(?:(?:\s+and\s+|[\s-]+)(?:{_WORD})\b)*)"
    r"(?:\s?(?P<unit>%|per\s?cent\b|times\b))?"
    r"(?:\s(?P<cur>dollars?\b|usd\b|euros?\b|eur\b|gbp\b))?",
    re.IGNORECASE,
)

_DENOM = {"half": 2, "halves": 2, "third": 3, "thirds": 3, "quarter": 4, "quarters": 4,
          "fourth": 4, "fourths": 4, "fifth": 5, "fifths": 5, "tenth": 10, "tenths": 10}
# "two-thirds" and "one-third" say they are fractions. "a third" and "half"
# also name a shift, a party, or a part of the year, so they count only as an
# amount: after "by", before "of" or "the", or "in half" ("in a quarter" is
# a time).
FRACTION_RE = re.compile(
    r"(?<![\w-])(?:"
    r"(?P<n>two|three|four|five|six|seven|eight|nine)[\s-]+"
    r"(?P<d>halves|thirds|quarters|fourths|fifths|tenths)\b"
    r"|one-(?P<d1>half|third|quarter|fourth|fifth|tenth)\b"
    r"|(?<=\bby\s)(?:(?:a|one)\s+)?(?P<d2>half|third|quarter)\b(?![\s-]party)"
    r"|(?<=\bin\s)(?P<d4>half)\b"
    r"|(?<!first\s)(?<!second\s)(?<!other\s)(?<!back\s)(?<!front\s)(?<!the\s)"
    r"(?:(?:a|one)\s+)?(?P<d3>half|third|quarter)(?=\s+(?:of|the)\b)"
    r")",
    re.IGNORECASE,
)

_MULTIPLE = {"doubl": "2", "tripl": "3", "quadrupl": "4", "halv": "0.5"}
# "doubled" and "tripling"; never "a double shift" or "doubled as the lead".
MULTIPLE_RE = re.compile(
    r"(?<![\w-])(?:(?P<verb>doubl|tripl|quadrupl|halv)(?:ed|ing)(?!\s+as\b)"
    r"|(?P<fold>two|three|four|five|six|seven|eight|nine|ten|twenty|hundred)fold)(?![\w-])",
    re.IGNORECASE,
)

# Names that start with a number word but state no figure.
_NAMES = re.compile(r"\b(?:two[\s-]factor|six\s+sigma|three[\s-]phase|zero[\s-](?:trust|day))\b",
                    re.IGNORECASE)


def _cardinal(run: str) -> Decimal | None:
    words = [w for w in re.split(r"[\s-]+", run.lower()) if w != "and"]
    if words == ["one"]:
        return None  # "one of the docks": a pronoun as often as a figure
    total, current = 0, 0
    for w in words:
        if w == "a":
            current = 1
        elif w in _SCALE:
            current = (current or 1) * _SCALE[w]
        elif w in _BIG:
            total += (current or 1) * _BIG[w]
            current = 0
        else:
            current += _SMALL.get(w) or _TENS.get(w, 0)
    return Decimal(total + current)


def _blank(text: str, span: tuple[int, int]) -> str:
    return text[:span[0]] + " " * (span[1] - span[0]) + text[span[1]:]


def _word_tokens(text: str) -> list[tuple[int, Token]]:
    # Folded, so a Cyrillic "о" in "fоrty" is still forty (issue #1). Each
    # match is blanked once read, so "two-thirds" is not also the number 2.
    text = _NAMES.sub(lambda m: " " * len(m.group(0)), fold(text))
    out: list[tuple[int, Token]] = []
    for m in list(FRACTION_RE.finditer(text)):
        numer = _SMALL.get((m.group("n") or "").lower(), 1)
        denom = _DENOM[next(d for d in m.group("d", "d1", "d2", "d3", "d4") if d).lower()]
        out.append((m.start(), Token("fraction", f"{numer}/{denom}", shown=m.group(0))))
        text = _blank(text, m.span())
    for m in list(MULTIPLE_RE.finditer(text)):
        value = (_MULTIPLE[m.group("verb").lower()] if m.group("verb")
                 else _norm(_cardinal(m.group("fold"))))
        out.append((m.start(), Token("multiple", value, shown=m.group(0))))
        text = _blank(text, m.span())
    for m in CARDINAL_RE.finditer(text):
        unit = re.sub(r"\s", "", (m.group("unit") or "").lower())
        value = _cardinal(m.group("run"))
        if value is None:
            if not unit:
                continue
            value = Decimal(1)  # "one percent" is a figure
        cur = (m.group("cur") or "").lower()
        if unit in ("%", "percent"):
            tok = Token("percent", _norm(value))
        elif unit == "times":
            tok = Token("times", _norm(value))
        elif cur:
            tok = Token("money", _norm(value), _CURRENCY[cur])
        else:
            tok = Token("number", _norm(value))
        # Words state a figure no finer than their last nonzero place:
        # "twelve thousand" is "$12k", not "$12,000".
        digits = str(int(value))
        zeros = len(digits) - len(digits.rstrip("0")) if value else 0
        out.append((m.start(), replace(tok, step=Decimal(10) ** zeros,
                                       shown=m.group(0).strip())))
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
    """Longest first, so "sq ft" wins over "ft"; a space matches any run of
    spaces or hyphens ("sq-ft")."""
    return "|".join(re.escape(w).replace(r"\ ", r"[\s-]+")
                    for w in sorted(words, key=len, reverse=True))


# A multiplier between the figure and the unit: "650k km", "0.65 million km"
# (#37). Not "m" or "mm", which are units here; "k" only as its own word, so
# "5 km" stays kilometers.
_UNIT_MULT = {"k": Decimal(1_000), "K": Decimal(1_000), "thousand": Decimal(1_000),
              "M": Decimal(1_000_000), "million": Decimal(1_000_000),
              "bn": Decimal(1_000_000_000), "billion": Decimal(1_000_000_000)}

# A figure, then a unit: right after a multiplier ("650k km", #37), right
# after a hyphen ("650,000-km", #37), or after at most two words ("650,000
# accident-free miles"). A multiplier needs its unit next, so "401k match
# from day one" is not 401,000 days.
UNIT_RE = re.compile(
    r"(?<![\w.])(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?"
    rf"(?:\s?(?P<mult>{_alt(_UNIT_MULT)})(?![\w-])[\s-]*"
    r"|-|(?:\s+[A-Za-z][\w-]*){0,2}?\s*(?:(?<=\d)|(?<=\s)))"
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
        if m.group("mult"):
            val *= _UNIT_MULT[m.group("mult")]
        written = m.group("abbr") or m.group("word")
        key = re.sub(r"[\s-]+", " ", written)
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


# Hyphens (any dash), slashes, and runs of whitespace all read as one space
# when matching a term, so "Black-Belt", "Black/Belt", and "Black  Belt" are
# "Black Belt" (#92).
_TERM_GAPS = re.compile(r"[\s/\-‐-―−]+")


def _term_form(text: str) -> str:
    return _TERM_GAPS.sub(" ", fold(text)).strip()


def term_in(term: str, text: str) -> bool:
    """Whole-word, case-insensitive match. Terms of two characters or fewer
    ("Go", "C", "R") match case-sensitively, so "go" in prose is not the Go
    language. Look-alike letters count as the letter they imitate, and
    hyphens, slashes, and spacing do not matter."""
    term = _term_form(term)
    if not term:
        return False
    flags = 0 if len(term) <= 2 else re.IGNORECASE
    pattern = r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])"
    return re.search(pattern, _term_form(text), flags) is not None


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """Rough sentence split, good enough for employer attribution in prose.
    Splits on . ! ? followed by whitespace and a capital or digit, without
    breaking decimals or URLs."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", text.strip())
    return [p.strip() for p in parts if p.strip()]
