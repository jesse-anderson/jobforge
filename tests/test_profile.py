import pytest

from jobforge.errors import JobforgeError
from jobforge.profile import (DEFAULT_BANNED_WORDS, display_url, load_profile,
                              profile_from_dict, stem_from_name)
from jobforge.workspace import init_workspace


def test_john_smith_profile_loads(ws):
    p = load_profile(ws)
    assert p.name == "John Smith"
    assert p.resume_stem == "John_Smith_Resume"
    assert p.cover_stem == "John_Smith_Cover_Letter"
    assert p.never_claim == ["SAP", "Six Sigma Black Belt"]
    assert p.contact_items() == ["john.smith@example.com", "555-0100", "Springfield, IL",
                                 "example.com/johnsmith"]


def test_starter_profile_asks_for_a_name(tmp_path):
    ws = init_workspace(tmp_path)
    with pytest.raises(JobforgeError) as exc:
        load_profile(ws)
    assert any("name is empty" in d for d in exc.value.details)


def test_missing_profile(ws):
    ws.profile_path.unlink()
    with pytest.raises(JobforgeError, match="missing"):
        load_profile(ws)


def test_invalid_toml_names_the_file(ws):
    ws.profile_path.write_text("[person\nname = 1", encoding="utf-8")
    with pytest.raises(JobforgeError, match="profile/profile.toml is not valid TOML"):
        load_profile(ws)


@pytest.mark.parametrize("name,stem", [
    ("John Smith", "John_Smith"),
    ("Mary-Jane O'Neil", "Mary-Jane_ONeil"),
    ("  Ana   María  López ", "Ana_Mara_Lpez"),
])
def test_stem_from_name(name, stem):
    assert stem_from_name(name) == stem


def test_explicit_file_stem_wins():
    p = profile_from_dict({"person": {"name": "José Núñez", "file_stem": "Jose_Nunez"}})
    assert p.resume_stem == "Jose_Nunez_Resume"


def test_bad_file_stem_rejected():
    with pytest.raises(JobforgeError) as exc:
        profile_from_dict({"person": {"name": "A B", "file_stem": "a/b"}})
    assert any("file_stem" in d for d in exc.value.details)


def test_voice_add_and_allow():
    p = profile_from_dict({"person": {"name": "A B"},
                           "voice": {"add_banned_words": ["Synergize"],
                                     "allow_words": ["robust"],
                                     "add_banned_phrases": ["Hit the ground running"]}})
    assert "synergize" in p.banned_words
    assert "robust" not in p.banned_words
    assert "hit the ground running" in p.banned_phrases
    assert "leverage" in p.banned_words


def test_defaults_carry_no_person_specific_rules():
    # SOW A-13: the defaults are general AI-tell words only.
    assert "excited" not in DEFAULT_BANNED_WORDS  # was a personal rule in the private repo
    assert "ecosystem" not in DEFAULT_BANNED_WORDS


@pytest.mark.parametrize("data,needle", [
    ({"person": {"name": "A"}, "extra": {}}, "unknown section [extra]"),
    ({"person": {"name": "A", "nick": "x"}}, "unknown key 'nick'"),
    ({"person": {"name": 5}}, "[person] name should be text"),
    ({"person": {"name": "A"}, "settings": {"page_limit": "one"}}, "page_limit should be a whole number"),
    ({"person": {"name": "A"}, "settings": {"page_limit": 9}}, "between 1 and 5"),
    ({"person": {"name": "A"}, "settings": {"page_limit": True}}, "whole number"),
    ({"person": {"name": "A", "links": ["github.com/me"]}}, "not a full http(s) URL"),
    ({"person": {"name": "A", "links": "https://x.com"}}, "list of text items"),
    ({"person": {"name": "A"}, "voice": {"ban_dashes": "yes"}}, "true or false"),
    ({"person": "A"}, "[person] should be a table"),
])
def test_profile_errors(data, needle):
    with pytest.raises(JobforgeError) as exc:
        profile_from_dict(data)
    assert any(needle in d for d in exc.value.details), exc.value.details


def test_page_limit_two_is_allowed():
    assert profile_from_dict({"person": {"name": "A"}, "settings": {"page_limit": 2}}).page_limit == 2


@pytest.mark.parametrize("url,shown", [
    ("https://www.example.com/x/", "example.com/x"),
    ("http://example.com", "example.com"),
    ("https://github.com/me", "github.com/me"),
])
def test_display_url(url, shown):
    assert display_url(url) == shown
