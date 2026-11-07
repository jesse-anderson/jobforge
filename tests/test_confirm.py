"""D-35 / SOW A-3: only facts the user keeps become live."""
import pytest

from jobforge.atoms import load_inventory
from jobforge.confirm import CONFIRMED_FILE, run_confirm
from jobforge.errors import JobforgeError

from conftest import add_atoms

pytestmark = pytest.mark.critical

DRAFT = '''
[[bullet]]
id = "acme.uptime"
role = "acme"
text = "Kept press uptime at 98% across 12 lines"
basis = "records"
defense = "Monthly uptime report."

[[bullet.phrasing]]
use = "cover"
text = "I kept our 12 press lines at 98% uptime."

[[role]]
id = "acme"
employer = "Acme Manufacturing"
title = "Maintenance Technician"
start = "2014-01"
end = "2016-05"

[[skill]]
id = "skill.plc"
label = "Controls"
items = ["PLC ladder logic"]
'''


def script(*answers):
    it = iter(answers)
    return lambda prompt: next(it)


def quiet(_):
    pass


def test_roles_come_first_and_kept_atoms_go_live(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    said = []
    # Review order is role, skill, bullet: keep, drop, keep.
    out = run_confirm(ws, ask=script("k", "d", "k"), say=said.append)
    assert out.kept == ["acme", "acme.uptime"]
    assert out.dropped == ["skill.plc"]
    inv = load_inventory(ws)
    assert inv.employer_of(inv.get("acme.uptime")) == "Acme Manufacturing"
    assert inv.get("acme.uptime").phrasings[0]["text"].startswith("I kept our 12")
    assert not (ws.pending_dir / "draft.toml").exists()


def test_order_is_role_then_skill_then_bullet(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    seen = []
    def ask(prompt):
        return "s"
    def say(msg):
        if msg and msg.split()[0] in ("ROLE", "SKILL", "BULLET"):
            seen.append(msg.split()[0])
    run_confirm(ws, ask=ask, say=say)
    assert seen == ["ROLE", "SKILL", "BULLET"]


def test_skip_leaves_it_pending_and_drop_removes_it(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    out = run_confirm(ws, ask=script("k", "s", "d"), say=quiet)
    assert out.kept == ["acme"] and out.skipped == ["skill.plc"] and out.dropped == ["acme.uptime"]
    remaining = (ws.pending_dir / "draft.toml").read_text(encoding="utf-8")
    assert "skill.plc" in remaining and "acme.uptime" not in remaining and 'id = "acme"' not in remaining


def test_bullet_whose_role_was_dropped_is_refused(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    said = []
    out = run_confirm(ws, ask=script("d", "s"), say=said.append)
    assert out.refused == ["acme.uptime"]
    assert any("Cannot keep this yet" in m for m in said)
    assert load_inventory(ws).get("acme.uptime") is None


def test_bullet_with_no_role_at_all_is_refused(ws):
    add_atoms(ws, '[[bullet]]\nid = "x.a"\nrole = "nowhere"\ntext = "Did 3 things"\nbasis = "records"\n',
              "d.toml", pending=True)
    out = run_confirm(ws, ask=script(), say=quiet)
    assert out.refused == ["x.a"]


def test_malformed_pending_file_is_reported(ws):
    add_atoms(ws, '[[bullet]]\nid = "x.a"\ntext = "t"\nbasis = "records"\n', "d.toml", pending=True)
    with pytest.raises(JobforgeError, match="malformed") as exc:
        run_confirm(ws, ask=script(), say=quiet)
    assert any("must name the role" in d for d in exc.value.details)


def test_id_clash_with_confirmed_atom(ws):
    add_atoms(ws, '[[skill]]\nid = "skill.office"\nlabel = "L"\nitems = ["x"]\n', "d.toml", pending=True)
    with pytest.raises(JobforgeError, match="Cannot confirm"):
        run_confirm(ws, ask=script(), say=quiet)


def test_nothing_pending(ws):
    said = []
    out = run_confirm(ws, ask=script(), say=said.append)
    assert out.kept == [] and "Nothing to confirm" in said[0]


def test_quit_keeps_the_rest_pending(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    out = run_confirm(ws, ask=script("k", "q"), say=quiet)
    assert out.kept == ["acme"]
    assert set(out.skipped) == {"skill.plc", "acme.uptime"}


def test_bad_answers_are_asked_again(ws):
    add_atoms(ws, '[[skill]]\nid = "skill.new"\nlabel = "L"\nitems = ["x"]\n', "d.toml", pending=True)
    said = []
    out = run_confirm(ws, ask=script("maybe", "", "K"), say=said.append)
    assert out.kept == ["skill.new"]
    assert said.count("  Please answer k, d, s, or q.") == 2


def test_confirmed_file_is_append_only(ws):
    target = ws.atoms_dir / CONFIRMED_FILE
    target.write_text("# my notes stay\n\n[[skill]]\nid = \"skill.mine\"\nlabel = \"M\"\nitems = [\"y\"]\n",
                      encoding="utf-8")
    add_atoms(ws, '[[skill]]\nid = "skill.new"\nlabel = "L"\nitems = ["x"]\n', "d.toml", pending=True)
    run_confirm(ws, ask=script("k"), say=quiet)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# my notes stay")
    assert load_inventory(ws).get("skill.new") is not None


def test_describe_shows_employer_basis_and_defense(ws):
    add_atoms(ws, '[[bullet]]\nid = "northwind.new"\nrole = "northwind"\ntext = "Did 3 audits"\n'
                  'basis = "estimate"\ndefense = "My count."\n', "d.toml", pending=True)
    said = []
    run_confirm(ws, ask=script("s"), say=said.append)
    shown = "\n".join(said)
    assert "Employer: Northwind Distribution" in shown
    assert "How you know: estimate" in shown and "Your explanation: My count." in shown


def test_describe_shows_a_roles_aliases(ws):
    # Issue #9: the agent drafts aliases; the user sees them before keeping.
    add_atoms(ws, '[[role]]\nid = "kt"\nemployer = "Kestrel Testing Laboratories"\n'
                  'aliases = ["KT", "Kestrel Labs"]\ntitle = "Engineer"\nstart = "2020"\n',
              "d.toml", pending=True)
    said = []
    run_confirm(ws, ask=script("s"), say=said.append)
    assert "Also called: KT, Kestrel Labs" in "\n".join(said)


def test_describe_shows_a_roles_title_aliases(ws):
    # Issue #89: a title alias is a claim; the user sees it before keeping.
    add_atoms(ws, '[[role]]\nid = "kt"\nemployer = "Kestrel Testing Laboratories"\n'
                  'title = "Software Engineer"\ntitle_aliases = ["Data Engineer"]\n'
                  'start = "2020"\n', "d.toml", pending=True)
    said = []
    run_confirm(ws, ask=script("s"), say=said.append)
    assert "Also titled: Data Engineer" in "\n".join(said)


def test_without_a_terminal_confirm_stops_before_asking(ws, monkeypatch):
    """Issue #2 run: `! jobforge confirm` inside an agent has no stdin, and
    confirm crashed with an EOFError traceback on the first prompt."""
    import io
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    with pytest.raises(JobforgeError, match="needs a terminal") as exc:
        run_confirm(ws, say=quiet)
    assert str(ws.root) in exc.value.render()
    assert (ws.pending_dir / "draft.toml").exists()
    assert not (ws.atoms_dir / CONFIRMED_FILE).exists()


def test_without_a_terminal_nothing_pending_still_reports(ws, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    said = []
    out = run_confirm(ws, say=said.append)
    assert out.kept == [] and "Nothing to confirm" in said[0]


def test_input_ending_mid_review_keeps_earlier_answers(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    answers = iter(["k"])

    def ask(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    said = []
    out = run_confirm(ws, ask=ask, say=said.append)
    assert out.kept == ["acme"]
    assert out.skipped == ["skill.plc", "acme.uptime"]
    assert any("Input ended" in s for s in said)
    assert load_inventory(ws).get("acme") is not None


# Issue #77: Ctrl+C at a prompt left kept facts in pending/ as well, and the
# next confirm refused ("same id as a confirmed atom") until hand-edited.
def pending_ids(ws):
    from jobforge.atoms import parse_file, read_files
    return sorted(a.id for p in read_files(ws.pending_dir) for a in parse_file(p, "", []))


@pytest.mark.parametrize("at", [1, 2, 3])
def test_ctrl_c_at_a_prompt_keeps_earlier_answers(ws, at):
    # Order is role, skill, bullet; answers keep, drop, keep. Ctrl+C at question `at`.
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    answers = iter(["k", "d", "k"][:at - 1])

    def ask(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    said = []
    out = run_confirm(ws, ask=ask, say=said.append)
    decided = ["acme", "skill.plc", "acme.uptime"][:at - 1]
    assert out.kept + out.dropped == decided
    assert any("Stopped" in s and "saved" in s for s in said)
    # Every fact is in exactly one place: confirmed, dropped, or still pending.
    still = pending_ids(ws)
    assert not set(still) & set(decided)
    assert sorted(still + decided) == ["acme", "acme.uptime", "skill.plc"]
    # And the next confirm runs, finishing the rest.
    rest = run_confirm(ws, ask=lambda _: "k", say=quiet)
    assert sorted(rest.kept) == still and pending_ids(ws) == []


def test_a_fact_already_confirmed_is_cleared_from_pending(ws):
    # Ctrl+C between keeping a fact and rewriting pending/ (not at a prompt)
    # leaves it in both places. The next run sees the identical copy, clears
    # it from pending/, and goes on, instead of refusing.
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    run_confirm(ws, ask=lambda _: "k", say=quiet)  # all three kept
    add_atoms(ws, DRAFT, "draft.toml", pending=True)  # the stale copy
    said = []
    out = run_confirm(ws, ask=script(), say=said.append)
    assert out.kept == [] and pending_ids(ws) == []
    assert any("already confirmed" in s and "acme" in s for s in said)


def test_already_confirmed_copy_is_cleared_and_the_rest_reviewed(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    run_confirm(ws, ask=script("k", "d", "d"), say=quiet)  # keep acme only
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    out = run_confirm(ws, ask=script("k", "k"), say=quiet)  # skill, bullet
    assert out.kept == ["skill.plc", "acme.uptime"] and pending_ids(ws) == []


def test_clearing_a_stale_copy_leaves_other_pending_files_untouched(ws):
    add_atoms(ws, DRAFT, "draft.toml", pending=True)
    run_confirm(ws, ask=lambda _: "k", say=quiet)
    add_atoms(ws, DRAFT, "draft.toml", pending=True)  # the stale copy
    other = add_atoms(ws, '[[skill]]\nid = "skill.forklift"\nlabel = "Equipment"\n'
                          'items = ["Reach truck"]\n', "other.toml", pending=True)
    before = other.read_bytes()
    out = run_confirm(ws, ask=script("s"), say=quiet)
    assert out.skipped == ["skill.forklift"] and other.read_bytes() == before
    assert not (ws.pending_dir / "draft.toml").exists()


def test_ctrl_c_while_rewriting_pending_loses_nothing(ws, monkeypatch):
    # The rewrite goes through a temp file, so the pending file is never
    # left empty or half-written.
    import jobforge.confirm as confirm_mod
    path = add_atoms(ws, DRAFT, "draft.toml", pending=True)
    before = path.read_bytes()

    def interrupted(src, dst):
        raise KeyboardInterrupt
    monkeypatch.setattr(confirm_mod.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_confirm(ws, ask=script("d", "s", "s"), say=quiet)
    assert path.read_bytes() == before
    assert sorted(p.name for p in ws.pending_dir.iterdir()) == ["draft.toml"]


def test_review_shows_dates_and_details_the_user_is_confirming():
    """Issue #2 run: a credential's date and a degree's field and date were
    confirmed without ever being shown."""
    from pathlib import Path

    from jobforge.atoms import Atom
    from jobforge.confirm import describe
    cred = Atom("credential", "cred.osha30", {
        "id": "cred.osha30", "name": "OSHA 30-Hour General Industry",
        "issuer": "OSHA Training Institute", "date": "2019", "expires": "2029"}, Path("p"))
    text = describe(cred, None)
    for shown in ("OSHA 30-Hour General Industry", "Issuer: OSHA Training Institute",
                  "Date: 2019", "Expires: 2029"):
        assert shown in text, text
    edu = Atom("education", "edu.cc", {
        "id": "edu.cc", "school": "Prairie Ridge Community College",
        "credential": "Associate of Applied Science",
        "field": "Industrial Maintenance Technology", "date": "2011",
        "location": "Decatur, IL", "details": "Dean's list"}, Path("p"))
    text = describe(edu, None)
    for shown in ("Field: Industrial Maintenance Technology", "Date: 2011",
                  "Location: Decatur, IL", "Details: Dean's list"):
        assert shown in text, text


@pytest.mark.parametrize("kind", ["role", "bullet", "project", "skill", "credential",
                                  "education", "summary"])
def test_review_shows_every_schema_field(kind):
    """No field the schema allows is hidden from the person confirming it."""
    from pathlib import Path

    from jobforge.atoms import SCHEMA, Atom
    from jobforge.confirm import describe
    required, optional = SCHEMA[kind]
    fields = {}
    for key in sorted(required | optional):
        if key in ("phrasing", "role", "project", "context"):
            continue  # shown as "Also worded" / the owner line
        fields[key] = ["v-" + key] if key in ("facts", "tags", "items") else "v-" + key
    fields["id"] = "x.y"
    text = describe(Atom(kind, "x.y", fields, Path("p")), None)
    for key, value in fields.items():
        if key == "id":
            continue
        shown = value[0] if isinstance(value, list) else value
        assert shown in text, (key, text)


def test_keeping_into_a_file_ending_in_a_blank_line(ws):
    # #49: appending adds no extra blank lines.
    live = ws.atoms_dir / CONFIRMED_FILE
    live.write_text("# Facts you confirmed.\n\n", encoding="utf-8")
    add_atoms(ws, '[[skill]]\nid = "skill.extra"\nlabel = "Extra"\nitems = ["Excel"]\n',
              "d.toml", pending=True)
    run_confirm(ws, ask=script("k"), say=quiet)
    assert "\n\n\n" not in live.read_text(encoding="utf-8")
    assert load_inventory(ws).get("skill.extra") is not None


def test_refused_project_gets_no_bullet_advice(ws):
    # #49: a project whose context role does not exist is refused; the
    # "keep the role first" hint is only for bullets.
    add_atoms(ws, '[[project]]\nid = "ghost.tool"\ntitle = "Tool"\ncontext = "ghost"\n',
              "d.toml", pending=True)
    said = []
    out = run_confirm(ws, ask=script("k"), say=said.append)
    shown = "\n".join(said)
    assert out.refused == ["ghost.tool"] and "Cannot keep this yet" in shown
    assert "Keep or add the role it belongs to first" not in shown
