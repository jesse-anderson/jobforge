"""John Smith and the thirteen archetypes (D-09) pass end to end, and the
fact check catches a planted violation in each. The MVP gate needs John,
trades, entry level, and career changer (MVP.md section 5); the rest are
the SOW 0.8 exit tests for 1.0."""
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
NAMES = ["john_smith", "trades", "entry_level", "career_changer",
         "factory", "service", "healthcare_aide", "office", "software_dev",
         "engineer", "educator", "nurse", "driver", "returning"]
# Every persona with two or more roles gets the employer swap (D-40).
MULTI_ROLE = [n for n in NAMES if n != "entry_level"]


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


@pytest.mark.parametrize("name", MULTI_ROLE)
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


def resume_text(ws, folder) -> str:
    apply(ws, folder, today=TODAY)
    return extract_text(folder / f"{load_profile(ws).file_stem}_Resume.docx")


def test_factory_rounded_quality_figure_is_refused(tmp_path):
    """Scrap of 4.1% is not "4%": rounding a quality figure changes it (D-37)."""
    ws, folder = setup(tmp_path, "factory")
    edit_plan(folder, lambda p: p["experience"][0]["bullets"].__setitem__(1, {
        "atom": "greatlakes.lead.scrap",
        "text": "Cut bracket line scrap from 4% to 2.3% with a first-piece inspection"}))
    result = run_check(ws, folder)
    assert any("the figure 4%" in e for e in result.errors), result.errors


def test_service_short_job_fact_stays_with_its_employer(tmp_path):
    """Five short jobs: opening the coffee shop cannot be credited to the
    restaurant in the letter."""
    ws, folder = setup(tmp_path, "service")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body="At Copper Pot Bistro I opened alone 3 mornings a week."))
    result = run_check(ws, folder)
    assert any("(names 'Copper Pot Bistro')" in e and "figure 3" in e
               for e in result.errors), result.errors


def test_healthcare_aide_cannot_claim_the_postings_preferred_certification(tmp_path):
    ws, folder = setup(tmp_path, "healthcare_aide")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        close="I also hold an EKG Technician certification."))
    result = run_check(ws, folder)
    assert any("claims 'EKG Technician certification'" in e for e in result.errors), result.errors


def test_office_tool_must_come_from_a_cited_atom(tmp_path):
    """Tools-heavy and few figures: the tool names are the facts. Dentrix is
    Patricia's, but only from the dental office, which this letter does not
    cite."""
    ws, folder = setup(tmp_path, "office")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        close="I have also used Dentrix for years."))
    result = run_check(ws, folder)
    assert any("mentions 'Dentrix'" in e for e in result.errors), result.errors


def test_software_dev_project_url_on_resume_and_required_in_letter(tmp_path):
    ws, folder = setup(tmp_path, "software_dev")
    resume = resume_text(ws, folder)
    assert "example.com/sampatel/tidycsv" in resume
    # The retired status page is listed without its dead URL.
    assert "Tallgrass Status Page" in resume
    assert "tallgrass-status" not in resume
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body=p["cover_letter"]["body"].replace(" (example.com/sampatel/tidycsv)", "")))
    result = run_check(ws, folder)
    assert any("mentions project 'tidycsv' but not its URL" in e
               for e in result.errors), result.errors


@pytest.mark.parametrize("text,bad", [
    ("Raised pump efficiency from 72.53% to 76% at 450 gpm", "the figure 72.53%"),
    ("Raised pump efficiency from 72.5% to 77% at 450 gpm", "the figure 77%"),
    ("Raised pump efficiency from 72.5% to about 76% at 450 gpm", "hedged figure"),
])
def test_engineer_precision_is_held_to_the_atom(tmp_path, text, bad):
    """D-37: no added precision, no rounding, no hedging. 76% may stand for
    the atom's 76.0%; 72.53% may not stand for 72.5%."""
    ws, folder = setup(tmp_path, "engineer")
    edit_plan(folder, lambda p: p["experience"][0]["bullets"].__setitem__(
        0, {"atom": "delta.impeller", "text": text}))
    result = run_check(ws, folder)
    assert any(bad in e for e in result.errors), result.errors


def test_educator_resume_runs_past_one_page_within_her_limit_of_two(tmp_path):
    ws, folder = setup(tmp_path, "educator")
    result = run_check(ws, folder)
    assert result.ok, result.errors
    assert 1 < result.pages <= 2
    assert not any("estimated at" in w for w in result.warnings), result.warnings
    # The same resume against the default limit of 1 is flagged.
    ws.profile_path.write_text(ws.profile_path.read_text(encoding="utf-8").replace(
        "page_limit = 2", "page_limit = 1"), encoding="utf-8")
    assert any("estimated at" in w for w in run_check(ws, folder).warnings)


def test_educator_school_project_is_bound_to_her_current_employer(tmp_path):
    """The science night site is a work project (context = a role): its
    bullet renders under Projects but is still Larkspur's fact (D-40)."""
    ws, folder = setup(tmp_path, "educator")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body="At Briar Glen Elementary School I published 30 demonstration "
             "guides (example.com/gholloway/science-night)."))
    result = run_check(ws, folder)
    assert any("(names 'Briar Glen Elementary School')" in e and "figure 30" in e
               for e in result.errors), result.errors


def test_nurse_unit_size_cannot_move_between_hospitals(tmp_path):
    ws, folder = setup(tmp_path, "nurse")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body="At Prairie View Hospital I worked in a 24-bed medical ICU."))
    result = run_check(ws, folder)
    assert any("(names 'Prairie View Hospital')" in e and "figure 24" in e
               for e in result.errors), result.errors


@pytest.mark.parametrize("miles,ok", [("650K", True), ("65,000", False), ("700,000", False)])
def test_driver_safety_record_mileage(tmp_path, miles, ok):
    """650K is the same figure as 650,000; any other mileage is not."""
    ws, folder = setup(tmp_path, "driver")
    edit_plan(folder, lambda p: p["experience"][0]["bullets"].__setitem__(0, {
        "atom": "redline.miles",
        "text": f"Drove {miles} accident-free miles in 48 states hauling dry van and reefer freight"}))
    result = run_check(ws, folder)
    assert result.ok is ok, result.errors


def test_driver_credentials_render_with_the_medical_card(tmp_path):
    ws, folder = setup(tmp_path, "driver")
    resume = resume_text(ws, folder)
    for name in ("Class A Commercial Driver's License (CDL)", "Tanker (N) Endorsement",
                 "DOT Medical Card"):
        assert name in resume


GAP_WORDS = ("gap", "career break", "time away", "caregiv", "stay-at-home",
             "back to work", "return to work", "returning to work", "since 2018")


def test_returning_letter_does_not_volunteer_the_gap(tmp_path):
    ws, folder = setup(tmp_path, "returning")
    apply(ws, folder, today=TODAY)
    letter = extract_text(folder / "Laura_Bennett_Cover_Letter.docx").lower()
    assert not [w for w in GAP_WORDS if w in letter]
    # The volunteer work during those years is on the resume, with no employer.
    resume = extract_text(folder / "Laura_Bennett_Resume.docx")
    assert "Westfield Elementary PTO Treasurer" in resume


def test_returning_planted_gap_explanation_is_refused(tmp_path):
    ws, folder = setup(tmp_path, "returning")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        close="I took a career break for caregiving and am ready to return to work."))
    result = run_check(ws, folder)
    banned = [e for e in result.errors if "banned phrase" in e]
    assert banned and all(p in banned[0] for p in ("career break", "caregiving", "return to work"))


def test_engineer_short_unit_is_not_read_as_million(tmp_path):
    """Issue #10: "0.003 m" used to read as 3,000 and match the fixture's
    3,000 psi. A figure with a unit is now taken as written."""
    ws, folder = setup(tmp_path, "engineer")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body="At Northfield I held a 0.003 m clearance on a pressure test fixture.",
        cites=p["cover_letter"]["cites"] + ["northfield.fixture"]))
    result = run_check(ws, folder)
    assert any("the figure 0.003 is not in the facts" in e for e in result.errors), result.errors


@pytest.mark.parametrize("name", ["Delta", "DPW", "Delta Pump Works"])
def test_engineer_letter_short_employer_name_is_bound(tmp_path, name):
    """Issue #9 repro: Northfield's figures credited to Delta by its short
    name or acronym are caught like the full name."""
    ws, folder = setup(tmp_path, "engineer")
    edit_plan(folder, lambda p: p["cover_letter"].update(
        body=f"At {name} I cut valve test setup from 40 minutes to 15.",
        cites=p["cover_letter"]["cites"] + ["northfield.fixture"]))
    result = run_check(ws, folder)
    assert any(f"(names {name!r})" in e and "40" in e for e in result.errors), result.errors
