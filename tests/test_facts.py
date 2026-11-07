import pytest

from jobforge.facts import (Token, find_hedges, number_tokens, split_sentences, term_in,
                            word_count)


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
