"""SOW 0.2 exit tests: John Smith loads, and each schema violation produces
the expected message."""
import pytest

from jobforge.atoms import load_inventory, pending_ids
from jobforge.errors import JobforgeError

from conftest import add_atoms

pytestmark = pytest.mark.critical


def errors_for(ws, toml):
    add_atoms(ws, toml)
    with pytest.raises(JobforgeError) as exc:
        load_inventory(ws)
    return exc.value.details


def test_john_smith_loads_cleanly(ws):
    inv = load_inventory(ws)
    assert len(inv.of_kind("role")) == 2
    assert inv.employer_of(inv.get("northwind.accuracy")) == "Northwind Distribution"
    assert inv.employer_of(inv.get("lakeside.shrink")) == "Lakeside Grocery Co-op"
    # A personal project and its bullet belong to no employer (D-40).
    assert inv.employer_of(inv.get("shift-scheduler")) is None
    assert inv.employer_of(inv.get("shift-scheduler.users")) is None
    assert inv.warnings == []


def test_john_smith_has_what_the_sow_requires(ws):
    # SOW 0.2: at least two employers and one personal project with a live URL.
    inv = load_inventory(ws)
    assert len(inv.employers()) >= 2
    assert any(p.get("context") == "personal" and p.get("url") for p in inv.of_kind("project"))


@pytest.mark.parametrize("toml,needle", [
    ('[[bullet]]\nid = "x.a"\ntext = "Did 5 things"\nbasis = "records"\n',
     "must name the role it happened in"),
    ('[[bullet]]\nid = "x.a"\nrole = "nobody"\ntext = "Did 5 things"\nbasis = "records"\n',
     "role 'nobody' does not exist"),
    ('[[bullet]]\nid = "x.a"\nrole = "summary.main"\ntext = "t"\nbasis = "records"\n',
     "is a summary, not a role"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\nproject = "shift-scheduler"\ntext = "t"\nbasis = "records"\n',
     "not both"),
    ('[[bullet]]\nid = "x.a"\nproject = "nope"\ntext = "t"\nbasis = "records"\n',
     "project 'nope' does not exist"),
    ('[[bullet]]\nid = "x.a"\nproject = "northwind"\ntext = "t"\nbasis = "records"\n',
     "is a role, not a project"),
    ('[[project]]\nid = "p"\ntitle = "P"\n', "missing required field 'context'"),
    ('[[project]]\nid = "p"\ntitle = "P"\ncontext = "hobby"\n', "context 'hobby' must be a role id"),
    ('[[project]]\nid = "p"\ntitle = "P"\ncontext = "personal"\nurl = "example.com/p"\n',
     "not a full http(s) URL"),
    ('[[project]]\nid = "p"\ntitle = "P"\ncontext = "personal"\nwriteup_url = "ftp://x.com/a"\n',
     "not a full http(s) URL"),
    ('[[project]]\nid = "p"\ntitle = "P"\ncontext = "personal"\nurl_status = "alive"\n',
     'url_status may only be "dead"'),
    ('[[role]]\nid = "r"\nemployer = "E"\ntitle = "T"\nstart = "2020"\nsalary = "1"\n',
     "unknown field 'salary'"),
    ('[[role]]\nid = "R!"\nemployer = "E"\ntitle = "T"\nstart = "2020"\n', "must be lowercase"),
    ('[[role]]\nid = "r"\nemployer = "E"\ntitle = "T"\nstart = "March 2020"\n', "must be YYYY or YYYY-MM"),
    ('[[role]]\nid = "r"\nemployer = "E"\ntitle = "T"\nstart = "2020-13"\n', "must be YYYY or YYYY-MM"),
    ('[[role]]\nid = "r"\nemployer = "E"\ntitle = "T"\nstart = "2020"\nend = "2019"\n', "is before start"),
    ('[[role]]\nid = "r"\nemployer = ""\ntitle = "T"\nstart = "2020"\n', "'employer' is empty"),
    ('[[role]]\nid = "r"\nemployer = 5\ntitle = "T"\nstart = "2020"\n', "must be text in quotes"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "guess"\n', "basis must be one of"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\nfacts = "30%"\n',
     "'facts' must be a list"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\nreword_of = "ghost"\n',
     "reword_of 'ghost' does not exist"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\nreword_of = "x.a"\n',
     "points at itself"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\n'
     '[[bullet.phrasing]]\nuse = "tweet"\ntext = "t"\n', "use must be one of"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\n'
     '[[bullet.phrasing]]\ntext = ""\n', "needs non-empty text"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\n'
     '[[bullet.phrasing]]\ntext = "t"\ntone = "warm"\n', "unknown field(s) ['tone']"),
    ('[[bullet]]\nid = "x.a"\nrole = "northwind"\ntext = "t"\nbasis = "records"\nphrasing = "x"\n',
     "must be written as [[<kind>.phrasing]]"),
    ('[[hobby]]\nid = "h"\n', "unknown section [[hobby]]"),
    ('[role]\nid = "r"\n', "must be written [[role]]"),
    ('[[role]]\nid = "northwind"\nemployer = "E"\ntitle = "T"\nstart = "2020"\n', "id already used"),
    ('[[skill]]\nid = "s"\nlabel = "L"\nitems = "a, b"\n', "'items' must be a list"),
])
def test_schema_violations(ws, toml, needle):
    details = errors_for(ws, toml)
    assert any(needle in d for d in details), details


def test_errors_name_the_file_and_atom(ws):
    details = errors_for(ws, '[[bullet]]\nid = "x.a"\ntext = "t"\nbasis = "records"\n')
    assert details[0].startswith("profile/atoms/extra.toml: bullet 'x.a':")


def test_all_problems_reported_together(ws):
    details = errors_for(ws, '[[bullet]]\nid = "x.a"\ntext = "t"\nbasis = "nope"\n'
                             '[[bullet]]\nid = "x.b"\nrole = "ghost"\ntext = "t"\nbasis = "records"\n')
    assert len(details) >= 3


def test_invalid_toml_names_the_file(ws):
    details = errors_for(ws, "[[role]\nid=")
    assert details[0].startswith("profile/atoms/extra.toml: not valid TOML")


def test_non_utf8_file(ws):
    (ws.atoms_dir / "bad.toml").write_bytes(b"id = \"\xff\xfe\"\n")
    with pytest.raises(JobforgeError) as exc:
        load_inventory(ws)
    assert any("not UTF-8" in d for d in exc.value.details)


def test_project_bound_to_a_role_takes_its_employer(ws):
    add_atoms(ws, '[[project]]\nid = "wms"\ntitle = "WMS rollout"\ncontext = "northwind"\n'
                  '[[bullet]]\nid = "wms.a"\nproject = "wms"\ntext = "Moved 3 docks"\nbasis = "records"\n')
    inv = load_inventory(ws)
    assert inv.employer_of(inv.get("wms.a")) == "Northwind Distribution"


def test_dead_url_and_writeup_are_valid(ws):
    add_atoms(ws, '[[project]]\nid = "old"\ntitle = "Old"\ncontext = "school"\n'
                  'url = "https://example.com/old"\nurl_status = "dead"\n'
                  'writeup_url = "https://example.com/old/writeup"\n')
    assert load_inventory(ws).get("old").get("url_status") == "dead"


def test_project_without_url_is_fine(ws):
    add_atoms(ws, '[[project]]\nid = "nourl"\ntitle = "No URL"\ncontext = "volunteer"\n')
    load_inventory(ws)


def test_hedged_atom_warns(ws):
    add_atoms(ws, '[[bullet]]\nid = "northwind.h"\nrole = "northwind"\n'
                  'text = "Saved about 20% on packaging"\nbasis = "estimate"\n')
    inv = load_inventory(ws)
    assert any("hedges a figure" in w for w in inv.warnings)


def test_unmarked_reword_warns_and_marked_does_not(ws):
    body = ('[[bullet]]\nid = "northwind.acc2"\nrole = "northwind"\n'
            'text = "Pick accuracy went from 97.2% to 99.6% after scan-to-confirm"\nbasis = "records"\n')
    add_atoms(ws, body)
    assert any("state the same figures" in w for w in load_inventory(ws).warnings)
    add_atoms(ws, body + 'reword_of = "northwind.accuracy"\n')
    assert not any("state the same figures" in w for w in load_inventory(ws).warnings)


def test_pending_atoms_are_not_loaded_by_default(ws):
    add_atoms(ws, '[[bullet]]\nid = "northwind.new"\nrole = "northwind"\ntext = "t"\nbasis = "records"\n',
              pending=True)
    assert load_inventory(ws).get("northwind.new") is None
    assert load_inventory(ws, include_pending=True).get("northwind.new") is not None
    assert pending_ids(ws) == {"northwind.new"}


def test_texts_include_phrasings_and_facts(ws):
    add_atoms(ws, '[[bullet]]\nid = "northwind.f"\nrole = "northwind"\ntext = "Cut spend in half"\n'
                  'basis = "estimate"\nfacts = ["50%"]\n[[bullet.phrasing]]\ntext = "Halved spend"\n')
    texts = load_inventory(ws).get("northwind.f").texts()
    assert "50%" in texts and "Halved spend" in texts
