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
])
def test_number_tokens(text, expected):
    assert number_tokens(text) == expected


def test_precision_is_kept():
    # D-37: "49.7%" must not match an atom that says "50%".
    assert number_tokens("49.7%") != number_tokens("50%")


def test_token_display():
    assert [str(t) for t in number_tokens("$5 7% 3x 9")] == ["$5", "7%", "3x", "9"]


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
])
def test_term_in(term, text, hit):
    assert term_in(term, text) is hit


def test_word_count():
    assert word_count("I'm a well-known leader, 3 times.") == 6


def test_split_sentences_keeps_decimals_and_urls():
    s = split_sentences("Accuracy rose to 99.6% here. See example.com/x. Then 3 more.")
    assert s == ["Accuracy rose to 99.6% here.", "See example.com/x.", "Then 3 more."]
