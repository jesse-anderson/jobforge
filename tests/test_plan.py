"""D-30 item 3: a bad or partial plan is rejected clearly."""
import pytest

from jobforge.atoms import load_inventory
from jobforge.plan import resolve

pytestmark = pytest.mark.critical


def run(ws, plan, pending=frozenset()):
    return resolve(plan, load_inventory(ws), set(pending))


def has(errors, needle):
    return any(needle in e for e in errors)


def test_john_smith_plan_resolves(ws, john_plan):
    out, errors, warnings = run(ws, john_plan)
    assert errors == [] and warnings == []
    assert [s.head.id for s in out.experience] == ["northwind", "lakeside"]
    assert out.experience[0].lines[1].text.startswith("Lead 14 associates")  # rewording
    assert out.experience[0].lines[0].text.startswith("Raised order pick accuracy")  # atom text
    assert out.letter.paragraphs()[0].startswith("Prairie Freight is hiring")
    assert [a.id for a in out.education] == ["edu.harper"]


def test_education_defaults_to_all(ws, john_plan):
    del john_plan["education"]
    out, errors, _ = run(ws, john_plan)
    assert not errors and [a.id for a in out.education] == ["edu.harper"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p.update(version=2), "version must be 1"),
    (lambda p: p.pop("version"), "version must be 1"),
    (lambda p: p.update(bullets=[]), "unknown key 'bullets'"),
    (lambda p: p.pop("cover_letter"), "cover_letter is required"),
    (lambda p: p["cover_letter"].update(hook=""), "cover_letter.hook is empty"),
    (lambda p: p["cover_letter"].update(body=5), "cover_letter.body must be text"),
    (lambda p: p["cover_letter"].update(sign="x"), "unknown key(s) ['sign']"),
    (lambda p: p["cover_letter"].update(cites="northwind"), "cover_letter.cites must be a list"),
    (lambda p: p["cover_letter"]["cites"].append("ghost"), "no atom with id 'ghost'"),
    (lambda p: p["experience"][0].update(role="ghost"), "no atom with id 'ghost'"),
    (lambda p: p["experience"][0].update(role="summary.main"), "is a summary, expected role"),
    (lambda p: p["experience"][0].update(id="northwind"), "unknown key(s) ['id']"),
    (lambda p: p["experience"][0]["bullets"].append(5), "must be an atom id or"),
    (lambda p: p["experience"][0]["bullets"].append({"atom": "northwind.safety", "text": ""}),
     "text must be non-empty"),
    (lambda p: p["experience"][0]["bullets"].append({"atom": "northwind.safety", "why": "x"}),
     "unknown key(s) ['why']"),
    (lambda p: p["experience"][0].update(bullets="northwind.safety"), "bullets must be a list"),
    (lambda p: p.update(experience={}), "experience must be a list"),
    (lambda p: p["experience"].append("lakeside"), "must be an object like"),
    (lambda p: p["experience"].append({"role": "lakeside"}), "'lakeside' appears twice"),
    (lambda p: p["experience"][1]["bullets"].append("lakeside.shrink"), "'lakeside.shrink' appears twice"),
    (lambda p: p.update(skills=["northwind"]), "is a role, expected skill"),
    (lambda p: p.update(skills="skill.office"), "skills must be a list"),
    (lambda p: p.update(credentials=[""]), "expected an atom id"),
    (lambda p: p.update(summary="summary.main"), "summary must be an object"),
    (lambda p: p.update(summary={"atom": "summary.main", "style": "x"}), "unknown key(s) ['style']"),
    (lambda p: p.update(fit={"score": "great"}), "fit.score must be one of"),
    (lambda p: p.update(fit="strong"), "fit must be an object"),
    (lambda p: p.update(experience=[], projects=[], education=[]), "the resume would be empty"),
])
def test_plan_errors(ws, john_plan, mutate, needle):
    mutate(john_plan)
    _, errors, _ = run(ws, john_plan)
    assert has(errors, needle), errors


def test_bullet_under_another_employers_role_is_a_hard_failure(ws, john_plan):
    # D-40 and SOW finding 7: this was only a warning in the private repo.
    john_plan["experience"][1]["bullets"].append("northwind.overtime")
    _, errors, _ = run(ws, john_plan)
    assert has(errors, "bullet 'northwind.overtime' belongs to role 'northwind' "
                       "(Northwind Distribution), not role 'lakeside' (Lakeside Grocery Co-op)")


def test_personal_project_bullet_cannot_go_under_a_role(ws, john_plan):
    john_plan["experience"][0]["bullets"].append("shift-scheduler.users")
    _, errors, _ = run(ws, john_plan)
    assert has(errors, "belongs to project 'shift-scheduler', not role 'northwind'")


def test_role_bullet_cannot_go_under_a_project(ws, john_plan):
    john_plan["projects"][0]["bullets"].append("northwind.safety")
    _, errors, _ = run(ws, john_plan)
    assert has(errors, "not project 'shift-scheduler'")


def test_pending_atom_points_to_confirm(ws, john_plan):
    john_plan["experience"][0]["bullets"].append("northwind.new")
    _, errors, _ = run(ws, john_plan, pending={"northwind.new"})
    assert has(errors, "'northwind.new' is still pending") and has(errors, "jobforge confirm")


def test_out_of_order_experience_warns(ws, john_plan):
    john_plan["experience"].reverse()
    _, errors, warnings = run(ws, john_plan)
    assert not errors and any("reverse-chronological" in w for w in warnings)


def test_include_writeup_without_url_warns(ws, john_plan):
    john_plan["projects"][0]["include_writeup"] = True
    _, errors, warnings = run(ws, john_plan)
    assert not errors and any("no writeup_url" in w for w in warnings)


def test_letter_paragraphs_join_wrapped_lines(ws, john_plan):
    john_plan["cover_letter"]["body"] = "Line one\ncontinues here.\n\nSecond para."
    out, errors, _ = run(ws, john_plan)
    assert out.letter.paragraphs()[1:3] == ["Line one continues here.", "Second para."]
