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
    # Issue #92 (audit A9): hyphens, slashes, and runs of spaces are one space.
    ("Six Sigma Black Belt", "a Six Sigma Black-Belt", True),
    ("Six Sigma Black Belt", "a Six Sigma Black/Belt", True),
    ("Six Sigma Black Belt", "a Six Sigma  Black   Belt", True),
    ("Six Sigma Black Belt", "a Six-Sigma Black\u2011Belt", True),  # non-breaking hyphen
    ("Black-Belt", "a black belt holder", True),             # variant on the term side
    ("CI/CD", "built CI CD pipelines", True),
    ("Lakeside Grocery Co-op", "at Lakeside Grocery Co op", True),
    ("Six Sigma Black Belt", "Six Sigma Black Belts", False),  # still whole words
    ("Six Sigma Black Belt", "Six Sigma Blackbelt", False),    # joined is a different word
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


# --- #84: figures written in words ------------------------------------------
# Cardinals are the same figure as their digits; fractions and multiples are
# kinds of their own until their equivalences are decided ("a third" is not
# 33%, "doubled" is not 2x), the safe direction.

@pytest.mark.critical
@pytest.mark.parametrize("text,expected", [
    ("Cut weekly overtime thirty-five percent", [Token("percent", "35")]),
    ("Cut weekly overtime thirty five per cent", [Token("percent", "35")]),
    ("Lead a team of forty associates", [Token("number", "40")]),
    ("Lead a team of Forty associates", [Token("number", "40")]),
    ("a team of twelve", [Token("number", "12")]),
    ("one hundred and twenty orders", [Token("number", "120")]),
    ("twenty-five hundred orders", [Token("number", "2500")]),
    ("a hundred stores", [Token("number", "100")]),
    ("a dozen drivers", [Token("number", "12")]),
    ("two million rows", [Token("number", "2000000")]),
    ("saved forty thousand dollars", [Token("money", "40000")]),
    ("saved twelve thousand euros", [Token("money", "12000", "€")]),
    ("three times faster", [Token("times", "3")]),
    ("one percent", [Token("percent", "1")]),
    ("zero recordable injuries", [Token("number", "0")]),
    ("a twelve-person crew", [Token("number", "12")]),
    # Fractions.
    ("Cut weekly overtime by a third", [Token("fraction", "1/3")]),
    ("cut costs by one-third", [Token("fraction", "1/3")]),
    ("a quarter of the fleet", [Token("fraction", "1/4")]),
    ("two-thirds of the stores", [Token("fraction", "2/3")]),
    ("three quarters of orders", [Token("fraction", "3/4")]),
    ("cut returns in half", [Token("fraction", "1/2")]),
    ("cut returns by half", [Token("fraction", "1/2")]),
    ("half of the routes", [Token("fraction", "1/2")]),
    # Multiples.
    ("Tripled schedule coverage", [Token("multiple", "3")]),
    ("doubled throughput", [Token("multiple", "2")]),
    ("doubling throughput", [Token("multiple", "2")]),
    ("halved returns", [Token("multiple", "0.5")]),
    ("a tenfold increase", [Token("multiple", "10")]),
    # Digits and words in one line, in the order written.
    ("from 12 sites to forty", [Token("number", "12"), Token("number", "40")]),
])
def test_number_words_are_figures(text, expected):
    assert number_tokens(text) == expected


@pytest.mark.critical
@pytest.mark.parametrize("text", [
    "one of the busiest docks",                 # "one" alone is a pronoun as often as a figure
    "the one tool everyone used",
    "worked with a third party vendor",          # an ordinal, not a fraction
    "worked with third-party vendors",
    "covered third shift",
    "closed every deal in a quarter",            # a time period
    "in the first half of 2023",                 # names 2023, which digits already check
    "doubled as the safety lead",
    "a double shift",                            # an adjective, not a multiple
    "rolled out two-factor sign-in",             # names of things
    "earned a Six Sigma Green Belt",
    "wired three-phase service",
    "built a zero-trust network",
    "on behalf of the team",
    "twice-daily rotation checks",
    "someone, anyone, everyone, often, tension, eighteenth",  # number words inside words
])
def test_words_that_are_not_figures(text):
    assert [t for t in number_tokens(text) if t.kind != "number" or t.value != "2023"] == []


@pytest.mark.critical
def test_words_match_their_digits():
    assert number_tokens("forty") == number_tokens("40")
    assert number_tokens("thirty-five percent") == number_tokens("35%")
    assert number_tokens("forty thousand dollars") == number_tokens("$40,000")


@pytest.mark.critical
def test_fractions_and_multiples_do_not_match_digits():
    assert number_tokens("by a third") != number_tokens("33%")
    assert number_tokens("by half") != number_tokens("50%")
    assert number_tokens("doubled") != number_tokens("2x")


@pytest.mark.critical
def test_number_word_with_a_look_alike_letter_is_still_a_figure():
    # Cyrillic "о" in "fоrty" (issue #1's trick, applied to words).
    assert number_tokens("a team of fоrty") == [Token("number", "40")]


@pytest.mark.critical
def test_number_words_keep_how_they_were_written_and_their_precision():
    tok, = number_tokens("saved twelve thousand dollars")
    assert tok.shown == "twelve thousand dollars"
    assert tok.step == 1000  # no more precise than "$12k"
    tok, = number_tokens("Tripled coverage")
    assert str(tok) == "Tripled" and tok.shown == "Tripled"
    tok, = number_tokens("by a third")
    assert str(tok) == "a third"
    assert number_tokens("zero")[0].step == 1
