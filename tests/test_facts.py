import pytest

from jobforge.facts import (Token, find_hedges, number_tokens, split_sentences, term_in,
                            unit_figures, word_count)


@pytest.mark.parametrize("text,expected", [
    ("cut costs 30%", [Token("percent", "30")]),
    ("cut costs 30 percent", [Token("percent", "30")]),
    ("saved $12,000", [Token("money", "12000")]),
    ("saved $12k", [Token("money", "12000")]),
    ("saved $12K a year", [Token("money", "12000")]),
    ("a $1.2M budget", [Token("money", "1200000")]),
    ("a $1.2 million budget", [Token("money", "1200000")]),
    ("$3 billion", [Token("money", "3000000000")]),
    ("3x faster", [Token("times", "3")]),
    ("3 times faster", [Token("times", "3")]),
    ("from 97.2% to 99.6%", [Token("percent", "97.2"), Token("percent", "99.6")]),
    ("team of 14", [Token("number", "14")]),
    ("since 2019", [Token("number", "2019")]),
    ("1,500 orders", [Token("number", "1500")]),
    ("12k orders", [Token("number", "12000")]),
    ("version v2", []),
    ("no numbers here", []),
    ("50.0%", [Token("percent", "50")]),
    # Issue #1: units that used to fall back to a plain number.
    ("cut costs 30 per cent", [Token("percent", "30")]),
    ("cut costs 30percent", [Token("percent", "30")]),
    ("cut costs 14\uff05", [Token("percent", "14")]),
    ("\uff11\uff14 orders", [Token("number", "14")]),
    ("saved €14", [Token("money", "14", "€")]),
    ("saved £2,000", [Token("money", "2000", "£")]),
    ("saved €1.5M", [Token("money", "1500000", "€")]),
    ("saved 12,000 dollars", [Token("money", "12000")]),
    ("saved 12,000 USD", [Token("money", "12000")]),
    ("saved 14 thousand dollars", [Token("money", "14000")]),
    ("saved 14 thousand", [Token("number", "14000")]),
    ("saved 300 euros", [Token("money", "300", "€")]),
    ("saved 300 GBP", [Token("money", "300", "£")]),
    # Issue #10: "m" and "mm" mean million only with money; otherwise the
    # figure is taken as written (meters, millimeters).
    ("held 0.05 mm", [Token("number", "0.05")]),
    ("a 3 m beam", [Token("number", "3")]),
    ("a 12m span", [Token("number", "12")]),
    ("2MM rows", [Token("number", "2")]),
    ("a $5mm deal", [Token("money", "5000000")]),
    ("saved 4m dollars", [Token("money", "4000000")]),
    ("2 million rows", [Token("number", "2000000")]),
])
def test_number_tokens(text, expected):
    assert number_tokens(text) == expected


def test_currencies_do_not_match_each_other():
    assert number_tokens("$14") != number_tokens("€14")
    assert number_tokens("€14") != number_tokens("£14")


def test_dollar_spellings_match():
    assert number_tokens("$12,000") == number_tokens("12,000 dollars") == number_tokens("$12k")


def test_precision_is_kept():
    # D-37: "49.7%" must not match an atom that says "50%".
    assert number_tokens("49.7%") != number_tokens("50%")


def test_token_display():
    assert [str(t) for t in number_tokens("$5 7% 3x 9")] == ["$5", "7%", "3x", "9"]
    assert [str(t) for t in number_tokens("€5 £6")] == ["€5", "£6"]


@pytest.mark.parametrize("text", ["about 50%", "~50%", "~ $5", "approximately 20 people",
                                  "roughly $3k", "nearly 40", "around 12", "an estimated 30%",
                                  "Almost 9 years"])
def test_hedges_found(text):
    assert find_hedges(text)


@pytest.mark.parametrize("text", ["over 50 stores", "more than 20 people", "up to 30%",
                                  "about the team", "50%"])
def test_not_hedges(text):
    assert not find_hedges(text)


@pytest.mark.parametrize("term,text,hit", [
    ("SAP", "used SAP daily", True),
    ("SAP", "sapling", False),
    ("Excel", "excel at things", True),       # case-insensitive above 2 chars
    ("Go", "go to the store", False),         # short terms are case-sensitive
    ("Go", "wrote services in Go", True),
    ("C", "C and C++", True),
    ("C++", "wrote C++ code", True),
    ("C", "C++ only", False),
    ("Google Sheets", "in google sheets", True),
    ("", "anything", False),
    # Issue #1: Cyrillic and Greek look-alikes match the Latin term.
    ("SAP", "used S\u0410P daily", True),                 # one Cyrillic A
    ("SAP", "used \u0405\u0410\u0420 daily", True),       # all Cyrillic
    ("Excel", "in \u0395xcel", True),                     # Greek capital epsilon
    ("Lakeside Grocery Co-op", "at Lakeside Gr\u043ecery Co-op", True),
])
def test_term_in(term, text, hit):
    assert term_in(term, text) is hit


def test_word_count():
    assert word_count("I'm a well-known leader, 3 times.") == 6


def test_split_sentences_keeps_decimals_and_urls():
    s = split_sentences("Accuracy rose to 99.6% here. See example.com/x. Then 3 more.")
    assert s == ["Accuracy rose to 99.6% here.", "See example.com/x.", "Then 3 more."]


@pytest.mark.parametrize("text,expected", [
    # Issue #10: common units, each under one name however it is spelled.
    ("drove 650,000 miles", [("650000", "mi")]),
    ("drove 650,000 accident-free miles", [("650000", "mi")]),
    ("drove 650,000 km", [("650000", "km")]),
    ("a 12 m span", [("12", "m")]),
    ("12 meters of conveyor", [("12", "m")]),
    ("held 0.05 mm", [("0.05", "mm")]),
    ("rated to 3,000 psi at 450 gpm", [("3000", "psi"), ("450", "gpm")]),
    ("lifts 50 lbs", [("50", "lb")]),
    ("1,800 gallons a day", [("1800", "gal")]),
    ("a 6 inch pipe", [("6", "in")]),
    # Not units: "in" as a word, million slang, figures with no unit nearby.
    ("trained 12 in Chicago", []),
    ("2MM rows and $5M", []),
    ("3 castings to a local foundry", []),
    ("cut setup from 40 minutes to 15", [("40", "min")]),
    # Jesse's review: the units people write, by family.
    ("cut p99 latency to 300 ms", [("300", "ms")]),
    ("cut p99 latency to 300 milliseconds", [("300", "ms")]),
    ("a 2 second timeout", [("2", "sec")]),
    ("worked 50 hrs a week", [("50", "hr")]),
    ("closed it in 3 weeks", [("3", "wk")]),
    ("a 4 year degree", [("4", "yr")]),
    ("a 120 MB cache", [("120", "MB")]),
    ("a 120 Mb link", [("120", "Mb")]),
    ("moved 4 TB nightly over 10 Gbps", [("4", "TB"), ("10", "Gbps")]),
    ("a 1.5 GHz part", [("1.5", "GHz")]),
    ("a 480 V panel and 75 kW drive", [("480", "V"), ("75", "kW")]),
    ("saved 120,000 kWh a year", [("120000", "kWh")]),
    ("a 10,000 sq ft warehouse", [("10000", "ft2")]),
    ("a 10,000 square feet warehouse", [("10000", "ft2")]),
    ("held 38°F in the cooler", [("38", "°F")]),
    ("held 3 degrees Celsius", [("3", "°C")]),
    ("poured 40 cubic yards", [("40", "yd3")]),
    ("rated to 150 bar and 1,750 RPM", [("150", "bar"), ("1750", "rpm")]),
    ("cruised at 400 km/h", [("400", "km/h")]),
    ("a 2.5 oz sample", [("2.5", "oz")]),
    ("a 250 mL dose", [("250", "mL")]),
    # More words that are not units.
    ("led the 2 second-shift crews", []),
    ("filed 5 W-2 forms", []),
    ("rolled out 5G at 3 sites", []),
    ("a 22-stop route", []),
    ("team of 14 at 2 sites", []),
    # Issue #37: a hyphen between the figure and the unit, and a multiplier
    # before the unit.
    ("a 650,000-km record", [("650000", "km")]),
    ("a 40-hour setup", [("40", "hr")]),
    ("a 12-month contract", [("12", "mo")]),
    ("a 5,000-sq-ft cross-dock", [("5000", "ft2")]),
    ("drove 650k km", [("650000", "km")]),
    ("drove 650K miles", [("650000", "mi")]),
    ("drove 0.65 million km", [("650000", "km")]),
    ("moved 1.2M lbs", [("1200000", "lb")]),
    ("a 5 km run", [("5", "km")]),       # k is not a multiplier inside "km"
    ("a 3-year-old truck", []),           # an age, not a duration
    ("covered 12-15 minutes", [("15", "min")]),
    ("a 401k match from day one", []),    # a multiplier needs its unit next
])
def test_unit_figures(text, expected):
    assert [(f.value, f.unit) for f in unit_figures(text)] == expected


def test_every_unit_spelling_is_read():
    """Each listed spelling, after a figure, reads as its unit (issue #10)."""
    from jobforge.facts import _UNIT_ABBR, _UNIT_WORDS
    for spelling, unit in [*_UNIT_ABBR.items(), *_UNIT_WORDS.items()]:
        found = [(f.value, f.unit) for f in unit_figures(f"reached 12 {spelling} last year")]
        assert found[:1] == [("12", unit)], (spelling, found)


@pytest.mark.parametrize("text,step", [
    # Precision is the smallest amount a figure states (Jesse's review, #24).
    ("$1.2M", "100000"), ("$1.20M", "10000"), ("$1,200,000", "1"),
    ("2.5 million", "100000"), ("12k", "1000"), ("76.0%", "0.1"), ("76%", "1"),
    ("0.05 mm", "0.01"),
])
def test_token_step(text, step):
    from decimal import Decimal
    assert number_tokens(text)[0].step == Decimal(step)
