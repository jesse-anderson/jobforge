"""D-11: one canonical instruction source; the generated files cannot drift
from it, from the CLI, or from the profile's limits."""
import re

import pytest

from jobforge.agent import AGENT_FILES, GENERATED_HEADER, render, source_text, values_for
from jobforge.cli import _parser
from jobforge.profile import load_profile
from jobforge.workspace import init_workspace


def test_workspace_agent_files_match_the_source(ws):
    expected = render(values_for(ws))
    for name in AGENT_FILES:
        assert (ws.root / name).read_text(encoding="utf-8") == expected


def test_every_command_in_the_instructions_exists():
    commands = set(_parser()._subparsers._group_actions[0].choices)
    mentioned = set(re.findall(r"`jobforge ([a-z]+)", source_text()))
    assert mentioned, "instructions mention no commands?"
    assert mentioned <= commands, mentioned - commands


def test_every_flag_in_the_instructions_exists():
    parser = _parser()
    sub = parser._subparsers._group_actions[0].choices
    for cmd, rest in re.findall(r"`jobforge ([a-z]+)([^`]*)`", source_text()):
        flags = set(re.findall(r"(--[a-z-]+)", rest))
        known = {opt for a in sub[cmd]._actions for opt in a.option_strings}
        assert flags <= known, (cmd, flags - known)


def test_limits_come_from_the_profile(ws):
    # F19: the instructions and the validator state the same number.
    text = (ws.root / "CLAUDE.md").read_text(encoding="utf-8")
    p = load_profile(ws)
    assert f"at most {p.cover_letter_max_words} words" in text
    assert f"{p.ghost_after_days} days" in text
    ws.profile_path.write_text(ws.profile_path.read_text(encoding="utf-8").replace(
        "cover_letter_max_words = 300", "cover_letter_max_words = 220"), encoding="utf-8")
    init_workspace(ws.root, refresh=True)
    assert "at most 220 words" in (ws.root / "CLAUDE.md").read_text(encoding="utf-8")


def test_starter_profile_renders_with_defaults(tmp_path):
    ws = init_workspace(tmp_path)
    text = (ws.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "helping the user apply" in text
    assert "{{" not in text


def test_generated_files_say_so():
    assert render({"name": "x", "cover_letter_max_words": 1, "page_limit": 1,
                   "ghost_after_days": 1, "dash_rule": ""}).startswith(GENERATED_HEADER)


def test_missing_value_is_an_error():
    with pytest.raises(KeyError, match="cover_letter_max_words"):
        render({"name": "x"})


def test_instructions_state_the_core_rules():
    text = source_text()
    for must in ("Never state a fact the user has not confirmed", "profile/pending/",
                 "jobforge confirm", "Never edit a `.docx`", "never record that yourself",
                 "Never guess an employer"):
        assert must in text, must


def test_example_atoms_in_the_instructions_are_valid(tmp_path):
    """The TOML example the agent copies from must itself load."""
    from jobforge.atoms import load_inventory
    block = re.search(r"## Atom format\n\n```toml\n(.*?)```", source_text(), re.S).group(1)
    ws = init_workspace(tmp_path)
    (ws.atoms_dir / "example.toml").write_text(block, encoding="utf-8")
    inv = load_inventory(ws)
    assert inv.employer_of(inv.get("acme.downtime")) == "Acme Manufacturing"


def test_example_plan_in_the_instructions_resolves(tmp_path):
    """The plan.json example must match the real schema."""
    import json

    from jobforge.atoms import load_inventory
    from jobforge.plan import resolve
    text = source_text()
    atoms = re.search(r"## Atom format\n\n```toml\n(.*?)```", text, re.S).group(1)
    atoms += ('\n[[bullet]]\nid = "acme.safety"\nrole = "acme"\n'
              'text = "Led 3 safety audits"\nbasis = "records"\n')
    plan = json.loads(re.search(r"```json\n(.*?)```", text, re.S).group(1))
    ws = init_workspace(tmp_path)
    (ws.atoms_dir / "example.toml").write_text(atoms, encoding="utf-8")
    plan["cover_letter"]["cites"] = ["acme.downtime"]
    _, errors, _ = resolve(plan, load_inventory(ws))
    assert errors == []


def test_instructions_send_the_user_to_their_own_terminal_for_confirm():
    """Issue #2 run: the agent suggested `! jobforge confirm`, which cannot
    take typed answers."""
    text = source_text()
    assert "in a terminal window of their\n   own" in text
    assert "Never suggest the `!` prefix" in text
    assert "! jobforge confirm" not in text


def test_instructions_list_every_fit_score():
    """Issue #2 run: the agent wrote "medium", because the example only
    showed "strong"."""
    from jobforge.plan import FIT_SCORES
    line = next(l for l in source_text().splitlines() if "`fit.score` is one of" in l)
    for score in FIT_SCORES:
        assert f"`{score}`" in line, score


def test_instructions_treat_a_skills_list_as_claims():
    """Issue #2 run: a broad skills item from an old resume was carried
    over unquestioned and later cited as a fit."""
    text = source_text()
    assert "A skills list is claims too" in text
    assert "never_claim" in text.split("A skills list is claims too", 1)[1].split("\n6.", 1)[0]
