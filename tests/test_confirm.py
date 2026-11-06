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
