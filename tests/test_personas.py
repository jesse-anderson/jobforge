"""MVP gate item 1: John Smith and three archetypes (trades, entry level,
career changer) pass end to end, and the fact check catches a planted
violation in each (MVP.md section 5, SOW 0.8 exit tests)."""
import json
import shutil

import pytest

from jobforge.apply import apply, run_check
from jobforge.docx import extract_text
from jobforge.errors import JobforgeError
from jobforge.extract import from_text
from jobforge.prepare import prepare
from jobforge.profile import load_profile
from jobforge.scan import find_hidden

from conftest import PERSONAS, TODAY, edit_plan, make_workspace

pytestmark = pytest.mark.critical
NAMES = ["john_smith", "trades", "entry_level", "career_changer"]


def setup(tmp_path, name):
    persona = PERSONAS / name
    ws = make_workspace(tmp_path / name, persona)
    posting = (persona / "posting.txt").read_text(encoding="utf-8")
    title, company = posting.splitlines()[0].split(", ", 1)
    job, _ = from_text(posting, company=company, title=title)
    folder, _ = prepare(ws, job, today=TODAY)
    shutil.copy(persona / "plan.json", folder / "plan.json")
    return ws, folder


@pytest.mark.parametrize("name", NAMES)
def test_persona_end_to_end(tmp_path, name):
    ws, folder = setup(tmp_path, name)
    result = run_check(ws, folder)
    assert result.ok, result.errors
    assert result.pages <= load_profile(ws).page_limit
    out = apply(ws, folder, today=TODAY)
    stem = load_profile(ws).file_stem
    resume = extract_text(folder / f"{stem}_Resume.docx")
    letter = extract_text(folder / f"{stem}_Cover_Letter.docx")
    assert out["resume"].endswith(f"{stem}_Resume.docx")
    assert find_hidden(resume) == [] and find_hidden(letter) == []
    assert load_profile(ws).name in resume.splitlines()[0]


@pytest.mark.parametrize("name", NAMES)
def test_persona_planted_invented_figure(tmp_path, name):
    ws, folder = setup(tmp_path, name)
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body=p["cover_letter"]["body"] + " That work saved $987,654."))
    with pytest.raises(JobforgeError) as exc:
        apply(ws, folder, today=TODAY)
    assert any("$987654" in d for d in exc.value.details)
    assert not list(folder.glob("*.docx"))


@pytest.mark.parametrize("name", NAMES)
def test_persona_planted_never_claim(tmp_path, name):
    ws, folder = setup(tmp_path, name)
    term = load_profile(ws).never_claim[0]
    edit_plan(folder, lambda p: p["cover_letter"].update(
        close=p["cover_letter"]["close"] + f" I also know {term}."))
    result = run_check(ws, folder)
    assert any(f"claims {term!r}" in e for e in result.errors), result.errors


@pytest.mark.parametrize("name", ["john_smith", "trades", "career_changer"])
def test_persona_employer_swap_is_refused(tmp_path, name):
    """Every persona with more than one role: moving a bullet to another
    role is refused (D-40), even when the employer is the same company."""
    ws, folder = setup(tmp_path, name)
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    first, second = plan["experience"][0], plan["experience"][1]
    moved = second["bullets"][0]
    moved_id = moved if isinstance(moved, str) else moved["atom"]
    edit_plan(folder, lambda p: p["experience"][0]["bullets"].append(moved_id))
    result = run_check(ws, folder)
    assert any(f"bullet {moved_id!r} belongs to role {second['role']!r}" in e
               and f"not role {first['role']!r}" in e for e in result.errors), result.errors


def test_career_changer_variant_keeps_facts_under_the_original_employer(tmp_path):
    ws, folder = setup(tmp_path, "career_changer")
    apply(ws, folder, today=TODAY)
    lines = extract_text(folder / "Dana_Brooks_Resume.docx").splitlines()
    maple = next(i for i, l in enumerate(lines) if "Maple Street Market" in l)
    corner = next(i for i, l in enumerate(lines) if "Corner Books" in l)
    remodel = next(i for i, l in enumerate(lines) if "Coordinated 4 contractors" in l)
    events = next(i for i, l in enumerate(lines) if "Coordinated 60 events" in l)
    assert maple < remodel < corner < events


def test_career_changer_cannot_credit_retail_figure_to_new_industry_employer(tmp_path):
    ws, folder = setup(tmp_path, "career_changer")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body="At Corner Books I coordinated 4 contractors and came in $15K under budget."))
    result = run_check(ws, folder)
    assert any("(names 'Corner Books')" in e for e in result.errors), result.errors


def test_entry_level_resume_has_no_invented_experience(tmp_path):
    ws, folder = setup(tmp_path, "entry_level")
    apply(ws, folder, today=TODAY)
    resume = extract_text(folder / "Alex_Chen_Resume.docx")
    assert "Experience" not in resume.splitlines()
    assert "Projects" in resume.splitlines()
    # Every bullet on the page is one of Alex's confirmed facts or its rewording.
    bullets = [l for l in resume.splitlines() if l.startswith("•")]
    assert len(bullets) == 3


def test_entry_level_school_project_url_is_on_the_page(tmp_path):
    ws, folder = setup(tmp_path, "entry_level")
    apply(ws, folder, today=TODAY)
    assert "example.com/alexchen/bike-share" in extract_text(folder / "Alex_Chen_Resume.docx")


def test_trades_fact_from_apprentice_years_stays_there(tmp_path):
    ws, folder = setup(tmp_path, "trades")
    apply(ws, folder, today=TODAY)
    lines = extract_text(folder / "Maria_Garcia_Resume.docx").splitlines()
    apprentice = next(i for i, l in enumerate(lines) if l.startswith("Electrical Apprentice"))
    hours = next(i for i, l in enumerate(lines) if "8,000 hours" in l)
    assert hours > apprentice
