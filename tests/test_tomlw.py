import datetime as dt
import tomllib

import pytest

from jobforge import tomlw


@pytest.mark.parametrize("v", [
    "plain", 'quote " and back\\slash', "line\nbreak\ttab\rcr", "control \x01 char",
    "unicode café ✓", "", 0, -5, 3.25, True, False, dt.date(2026, 11, 20),
    ["a", "b"], [], [1, 2],
])
def test_values_round_trip_through_tomllib(v):
    text = f"x = {tomlw.value(v)}\n"
    assert tomllib.loads(text)["x"] == (list(v) if isinstance(v, tuple) else v)


def test_table_array_entry_with_children_round_trips():
    text = tomlw.table_array_entry(
        "bullet",
        {"id": "a.b", "text": 'Cut costs 30% "fast"', "facts": ["30%"], "note": None},
        {"phrasing": [{"use": "cover", "text": "I cut costs 30%."},
                      {"text": "Costs fell 30%."}]},
    )
    data = tomllib.loads(text)
    (entry,) = data["bullet"]
    assert entry["text"] == 'Cut costs 30% "fast"'
    assert "note" not in entry
    assert [p["text"] for p in entry["phrasing"]] == ["I cut costs 30%.", "Costs fell 30%."]


def test_keys_that_need_quoting():
    text = tomlw.table_array_entry("t", {"has space": "v"})
    assert tomllib.loads(text)["t"][0]["has space"] == "v"


@pytest.mark.parametrize("bad", [{"a": 1}, [["nested"]], [{"a": 1}], object(),
                                 float("nan"), dt.datetime(2026, 1, 1)])
def test_unsupported_values_are_refused(bad):
    with pytest.raises((TypeError, ValueError)):
        tomlw.value(bad)


def test_tables_must_go_in_children():
    with pytest.raises(TypeError, match="children"):
        tomlw.table_array_entry("t", {"sub": {"a": 1}})


def test_empty_key_refused():
    with pytest.raises(TypeError):
        tomlw.table_array_entry("t", {"": 1})
