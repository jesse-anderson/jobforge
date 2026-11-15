"""The core promise (D-32): planted violations, each caught with the right
message; clean plans pass. Critical tier."""
import pytest

from jobforge.atoms import load_inventory
from jobforge.factcheck import check_plan, url_key, vocabulary
from jobforge.plan import resolve
from jobforge.profile import load_profile

from conftest import add_atoms

pytestmark = pytest.mark.critical

JOB = {"company": "Prairie Freight Co.", "title": "Operations Supervisor",
       "location": "Springfield, IL",
       "description": "We run 6 cross-dock facilities and need a lead for a team of 20."}


def check(ws, plan, job=JOB):
    inv = load_inventory(ws)
    resolved, errors, _ = resolve(plan, inv)
    assert errors == [], errors
    return check_plan(resolved, inv, load_profile(ws), job)


def letter_body(plan, text, keep_project=False):
    """Replace the letter body. The fixture letter cites John's personal
    project, which then requires its URL in the text; drop that cite unless
    the test is about projects."""
    plan["cover_letter"]["body"] = text
    if not keep_project:
        plan["cover_letter"]["cites"] = [
            c for c in plan["cover_letter"]["cites"] if not c.startswith("shift-scheduler")]


def expect(rep, needle):
    assert any(needle in e for e in rep.errors), rep.errors


def test_clean_john_smith_plan_passes(ws, john_plan):
    rep = check(ws, john_plan)
    assert rep.ok, rep.errors


# --- Resume lines -----------------------------------------------------------

def test_changed_number(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 35% by rebuilding the schedule"}
    expect(check(ws, john_plan), "the figure 35% is not in the facts")


def test_added_money_figure(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime",
        "text": "Cut weekly overtime 25%, saving $40,000 a year, by rebuilding the schedule"}
    expect(check(ws, john_plan), "the figure $40000 is not in the facts")


def test_hedged_figure(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime about 25% with a new schedule"}
    expect(check(ws, john_plan), "hedged figure 'about 25%'")


@pytest.mark.parametrize("hedge", ["close to 25%", "just under 25%", "just over 25%",
                                   "upwards of 25%"])
def test_more_hedged_figures(ws, john_plan, hedge):
    # #91: D-37 refuses these like "about 25%".
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": f"Cut weekly overtime {hedge} with a new schedule"}
    expect(check(ws, john_plan), f"hedged figure {hedge!r}")


def test_false_precision(ws, john_plan):
    # The atom says 25% (an estimate). 24.8% is precision nobody gave.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 24.8% with a new schedule"}
    expect(check(ws, john_plan), "the figure 24.8% is not in the facts")


def test_equivalent_spelling_of_a_figure_passes(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Rebuilt the shift schedule and weekly overtime fell 25 percent"}
    assert check(ws, john_plan).ok


def test_rewording_with_same_facts_passes(ws, john_plan):
    john_plan["experience"][1]["bullets"][0] = {
        "atom": "lakeside.shrink", "text": "Introduced twice-daily rotation checks, cutting produce shrink 18%"}
    assert check(ws, john_plan).ok


def test_fact_from_another_employer_in_a_bullet(ws, john_plan):
    # True fact, wrong employer: an invented fact under D-40.
    john_plan["experience"][1]["bullets"][0] = {
        "atom": "lakeside.shrink", "text": "Reduced produce shrink 18% using the Northwind Distribution method"}
    expect(check(ws, john_plan), "names 'Northwind Distribution', but this fact belongs to "
                                 "Lakeside Grocery Co-op")


def test_figure_from_another_atom_is_not_borrowed(ws, john_plan):
    # 99.6% is true, but it belongs to a different bullet than the one cited.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut overtime 25% and held 99.6% accuracy"}
    expect(check(ws, john_plan), "the figure 99.6% is not in the facts")


def test_month_in_role_dates_is_not_a_figure(ws, john_plan):
    # Issue #1: Northwind starts "2020-04"; the 04 must not allow "4".
    john_plan["experience"][0]["bullets"][1] = {
        "atom": "northwind.team", "text": "Lead a team of 4 supervisors and 14 associates"}
    expect(check(ws, john_plan), "the figure 4 is not in the facts")


def test_month_in_cited_role_dates_is_not_a_figure_in_the_summary(ws, john_plan):
    # Issue #1: Lakeside runs "2016-06" to "2020-03"; neither 6 nor 3 is a fact.
    john_plan["summary"] = {"atom": "summary.main", "cites": ["lakeside"],
                            "text": "Warehouse supervisor with 9 years who has run 6 sites."}
    expect(check(ws, john_plan), "the figure 6 is not in the facts")


def test_year_from_role_dates_passes(ws, john_plan):
    john_plan["experience"][0]["bullets"][1] = {
        "atom": "northwind.team", "text": "Lead 14 associates across two shifts since 2020"}
    assert check(ws, john_plan).ok


@pytest.mark.parametrize("claim,figure", [
    ("cut labor cost 14 per cent", "14%"),
    ("cut labor cost 14\uff05", "14%"),
    ("saved €14", "€14"),
    ("saved 14 thousand dollars", "$14000"),
])
def test_unit_change_does_not_borrow_a_count(ws, john_plan, claim, figure):
    # Issue #1: "14 associates" must not back 14 percent or 14 of a currency.
    john_plan["experience"][0]["bullets"][1] = {
        "atom": "northwind.team", "text": f"Lead 14 associates and {claim}"}
    expect(check(ws, john_plan), f"the figure {figure} is not in the facts")


def test_never_claim_tool_in_a_bullet(ws, john_plan):
    john_plan["experience"][0]["bullets"][0] = {
        "atom": "northwind.accuracy", "text": "Raised pick accuracy from 97.2% to 99.6% with SAP scanning"}
    expect(check(ws, john_plan), "claims 'SAP'")


def test_never_claim_with_a_look_alike_letter(ws, john_plan):
    # Issue #1: a Cyrillic A makes "SAP" a different string.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 25% using S\u0410P"}
    rep = check(ws, john_plan)
    expect(rep, "claims 'SAP'")
    expect(rep, "mixes Latin and Cyrillic")


@pytest.mark.parametrize("written", ["Six Sigma Black-Belt", "Six Sigma Black/Belt",
                                     "Six Sigma  Black Belt", "Six-Sigma Black Belt"])
def test_never_claim_matches_hyphen_slash_and_spacing_variants(ws, john_plan, written):
    # Issue #92 (audit A9): a hyphen or extra space made a different string.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": f"Cut weekly overtime 25% as a {written}"}
    expect(check(ws, john_plan), "claims 'Six Sigma Black Belt'")


def test_never_claim_written_all_in_cyrillic(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 25% using \u0405\u0410\u0420"}
    expect(check(ws, john_plan), "claims 'SAP'")


def test_other_employer_with_a_look_alike_letter(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime",
        "text": "Cut weekly overtime 25%, a method from Lakeside Gr\u043ecery Co-op"}
    expect(check(ws, john_plan), "names 'Lakeside Grocery Co-op'")


def test_all_cyrillic_word_passes(ws, john_plan):
    john_plan["experience"][0]["bullets"][1] = {
        "atom": "northwind.team",
        "text": "Lead 14 associates, including new arrivals from \u041a\u0438\u0457\u0432"}
    assert check(ws, john_plan).ok


def test_known_tool_not_in_cited_atom(ws, john_plan):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 25% with a schedule built in Excel"}
    expect(check(ws, john_plan), "mentions 'Excel', but none of the atoms this line cites do")


def test_tool_in_cited_atom_passes(ws, john_plan):
    john_plan["projects"][0]["bullets"] = [{
        "atom": "shift-scheduler.users",
        "text": "Built a Google Sheets scheduling template used by 40 small businesses"}]
    assert check(ws, john_plan).ok


def test_summary_rewording_checks_figures(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main",
                            "text": "Warehouse supervisor with 12 years in distribution."}
    expect(check(ws, john_plan), "the figure 12 is not in the facts")


def test_summary_may_cite_extra_atoms(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind.accuracy"],
                            "text": "Warehouse supervisor with 9 years in distribution; raised pick accuracy to 99.6%."}
    assert check(ws, john_plan).ok


# Issue #90: the summary was checked as one line against all its cites, so a
# sentence could credit one employer with another's figure (D-40).
def test_summary_credits_employer_a_with_employer_bs_figure(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["lakeside.shrink", "northwind"],
                            "text": "At Northwind Distribution, reduced produce shrink 18%."}
    expect(check(ws, john_plan),
           'summary, "At Northwind Distribution, reduced produce shrink..." '
           "(names 'Northwind Distribution'): the figure 18% is not in the facts")


def test_summary_names_each_employer_with_its_own_figures(ws, john_plan):
    john_plan["summary"] = {
        "atom": "summary.main", "cites": ["lakeside.shrink", "northwind.accuracy"],
        "text": "At Northwind Distribution I raised pick accuracy to 99.6%. "
                "At Lakeside Grocery Co-op I reduced produce shrink 18%."}
    assert check(ws, john_plan).ok


def test_summary_sentence_naming_no_employer_uses_all_its_cites(ws, john_plan):
    john_plan["summary"] = {
        "atom": "summary.main", "cites": ["lakeside.shrink", "northwind"],
        "text": "I reduced produce shrink 18%. I work at Northwind Distribution."}
    assert check(ws, john_plan).ok


def test_summary_two_employers_in_one_sentence_warns(ws, john_plan):
    john_plan["summary"] = {
        "atom": "summary.main", "cites": ["lakeside", "northwind"],
        "text": "Supervisor at Lakeside Grocery Co-op and then Northwind Distribution."}
    rep = check(ws, john_plan)
    assert any(w.startswith('summary, "Supervisor at Lakeside Grocery Co-op and...": '
                            "names 2 employers") for w in rep.warnings), rep.warnings


def test_summary_in_the_users_own_words_is_not_scoped(ws, john_plan):
    # The user confirmed this summary as written; 9 years spans both jobs.
    add_atoms(ws, '[[summary]]\nid = "summary.own"\n'
                  'text = "Supervisor at Northwind Distribution with 9 years in operations."\n')
    john_plan["summary"] = {"atom": "summary.own", "cites": ["northwind"]}
    assert check(ws, john_plan).ok
    john_plan["summary"]["text"] = "Supervisor at Northwind Distribution for 9 years."
    expect(check(ws, john_plan), "(names 'Northwind Distribution'): the figure 9")


def test_voice_rules_apply_to_rewordings_only(ws, john_plan):
    add_atoms(ws, '[[bullet]]\nid = "northwind.robust"\nrole = "northwind"\n'
                  'text = "Built a robust receiving checklist"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append("northwind.robust")
    assert check(ws, john_plan).ok  # the user's own words are not second-guessed
    john_plan["experience"][0]["bullets"][-1] = {
        "atom": "northwind.robust", "text": "Leveraged a receiving checklist"}
    expect(check(ws, john_plan), "banned word(s) ['leveraged']")


def test_dash_in_a_rewording(ws, john_plan):
    john_plan["experience"][0]["bullets"][3] = {
        "atom": "northwind.safety", "text": "Ran 2 years without a recordable injury — weekly huddles"}
    expect(check(ws, john_plan), "em dash")


def test_atom_id_leak_in_a_bullet(ws, john_plan):
    john_plan["experience"][0]["bullets"][3] = {
        "atom": "northwind.safety", "text": "Ran 2 years injury-free (northwind.safety)"}
    expect(check(ws, john_plan), "contains atom id(s) ['northwind.safety']")


# --- Role titles (#89) -------------------------------------------------------
# A title is a claim like an employer (D-40): a line may name only a title its
# own role holds, as written or as one of the role's title_aliases.

def bullet(plan, role_index, atom, text):
    plan["experience"][role_index]["bullets"][0] = {"atom": atom, "text": text}


def test_role_own_title_passes(ws, john_plan):
    bullet(john_plan, 0, "northwind.accuracy",
           "As Warehouse Supervisor, raised order pick accuracy from 97.2% to 99.6%")
    assert check(ws, john_plan).ok


def test_another_roles_title_fails(ws, john_plan):
    bullet(john_plan, 1, "lakeside.shrink",
           "As Warehouse Supervisor, reduced produce shrink 18% with rotation checks")
    expect(check(ws, john_plan), "mentions 'Warehouse Supervisor'")


def test_invented_title_in_a_bullet_fails(ws, john_plan):
    bullet(john_plan, 0, "northwind.accuracy",
           "As Operations Manager, raised order pick accuracy from 97.2% to 99.6%")
    expect(check(ws, john_plan), "names the title 'Operations Manager'")


def test_inflated_title_fails(ws, john_plan):
    bullet(john_plan, 0, "northwind.accuracy",
           "As Senior Warehouse Supervisor, raised pick accuracy from 97.2% to 99.6%")
    expect(check(ws, john_plan), "names the title 'Senior Warehouse Supervisor'")


def test_invented_title_in_the_summary_fails(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind"],
                            "text": "Operations Manager with 9 years in distribution."}
    expect(check(ws, john_plan), "names the title 'Operations Manager'")


def test_another_roles_title_in_the_summary_fails(ws, john_plan):
    # The summary atom itself says "Warehouse supervisor", so use Lakeside's.
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind"],
                            "text": "Shift Lead with 9 years in distribution."}
    expect(check(ws, john_plan), "mentions 'Shift Lead'")


def test_invented_title_in_the_letter_fails(ws, john_plan):
    letter_body(john_plan, "As Distribution Center Manager I lead 14 associates.")
    expect(check(ws, john_plan), "names the title 'Distribution Center Manager'")


def test_letter_may_name_the_postings_title(ws, john_plan):
    letter_body(john_plan, "I would like to be your next Operations Supervisor.")
    assert check(ws, john_plan).ok


# #119 review: a title that belongs to someone else is not a claim.
@pytest.mark.parametrize("text", [
    "I would welcome a call with your Hiring Manager.",
    "I have worked closely with Plant Managers and a Regional Director.",
    "I work with a Plant Manager and the Regional Director every week.",
    "I report to your Regional Director or the Operations Manager.",
    "I report to the Operations Manager on the second shift.",
    "I would report to Regional Director Lee.",
    "Your Operations Manager would get a steady second shift.",
    "Hiring Manager, thank you for reading.",
])
def test_letter_may_name_other_peoples_titles(ws, john_plan, text):
    letter_body(john_plan, text)
    rep = check(ws, john_plan)
    assert rep.ok, rep.errors


@pytest.mark.parametrize("text,title", [
    ("I was the Operations Manager on the second shift.", "Operations Manager"),
    ("I was promoted to Operations Manager last spring.", "Operations Manager"),
    ("I rose to the Regional Director role.", "Regional Director"),
    ("The Operations Manager role is mine today.", "Operations Manager"),
    ("I was Store Manager and then Regional Director.", "Regional Director"),
    ("I was Store Manager and a Regional Director.", "Regional Director"),
    ("Operations Manager and Regional Director, both mine.", "Regional Director"),
])
def test_a_title_the_user_holds_is_still_a_claim(ws, john_plan, text, title):
    letter_body(john_plan, text)
    expect(check(ws, john_plan), f"names the title {title!r}")


def test_letter_title_bound_to_the_employer_it_names(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside")
    letter_body(john_plan, "At Lakeside Grocery Co-op I was the Warehouse Supervisor.")
    expect(check(ws, john_plan), "(names 'Lakeside Grocery Co-op'): mentions "
                                 "'Warehouse Supervisor'")


def with_title_aliases(ws, role_id, names):
    path = ws.atoms_dir / "work.toml"
    text = path.read_text(encoding="utf-8")
    quoted = ", ".join(f'"{n}"' for n in names)
    text = text.replace(f'[[role]]\nid = "{role_id}"\n',
                        f'[[role]]\nid = "{role_id}"\ntitle_aliases = [{quoted}]\n')
    path.write_text(text, encoding="utf-8")


def test_title_alias_passes_under_its_own_role(ws, john_plan):
    # Jesse on #89: an official title can undersell the work ("Software
    # Engineer" doing data engineering). The user confirms the other names.
    with_title_aliases(ws, "northwind", ["Inventory Control Lead"])
    bullet(john_plan, 0, "northwind.accuracy",
           "As Inventory Control Lead, raised order pick accuracy from 97.2% to 99.6%")
    assert check(ws, john_plan).ok


def test_title_alias_fails_under_another_role(ws, john_plan):
    with_title_aliases(ws, "northwind", ["Inventory Control Lead"])
    bullet(john_plan, 1, "lakeside.shrink",
           "As Inventory Control Lead, reduced produce shrink 18% with rotation checks")
    expect(check(ws, john_plan), "mentions 'Inventory Control Lead'")


@pytest.mark.parametrize("text", [
    "Trained 6 Forklift Operators on the new scan-to-confirm picks",  # plural, not a title
    "Worked with the warehouse supervisor on rotation checks",       # lowercase prose
    "As Manager on duty, ran rotation checks twice a day",          # one word: a known limit
])
def test_title_like_words_that_claim_no_title_pass(ws, john_plan, text):
    add_atoms(ws, f'[[bullet]]\nid = "lakeside.extra"\nrole = "lakeside"\n'
                  f'text = "{text}"\nbasis = "records"\n')
    john_plan["experience"][1]["bullets"].append("lakeside.extra")
    assert check(ws, john_plan).ok


# --- Cover letter -----------------------------------------------------------

def test_letter_invented_figure(ws, john_plan):
    letter_body(john_plan, "I cut overtime 40% at my current job.")
    expect(check(ws, john_plan), "the figure 40% is not in the facts")


def test_letter_figure_from_uncited_atom(ws, john_plan):
    letter_body(john_plan, "I reduced produce shrink 18% with rotation checks.")
    expect(check(ws, john_plan), "the figure 18% is not in the facts")


def test_letter_credits_employer_a_with_employer_bs_figure(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Northwind Distribution I reduced shrink 18% with rotation checks.")
    expect(check(ws, john_plan), "(names 'Northwind Distribution')")


def test_letter_credits_employer_with_personal_project_figure(ws, john_plan):
    letter_body(john_plan, "At Northwind Distribution, 40 small businesses use my scheduler "
                           "(example.com/shift-scheduler).", keep_project=True)
    expect(check(ws, john_plan), "the figure 40 is not in the facts")


def test_letter_figure_from_profile_phone_is_not_a_fact(ws, john_plan):
    # Issue #1: John's phone is 555-0100; its digits are not achievements.
    letter_body(john_plan, "I have trained 100 drivers.")
    expect(check(ws, john_plan), "the figure 100 is not in the facts")


def test_letter_figure_from_profile_phone_in_an_employer_sentence(ws, john_plan):
    letter_body(john_plan, "At Northwind Distribution I trained 555 drivers.")
    expect(check(ws, john_plan), "the figure 555 is not in the facts")


def test_letter_may_give_contact_details(ws, john_plan):
    letter_body(john_plan, "You can reach me at 555-0100 or john.smith@example.com, "
                           "and my work is at example.com/johnsmith.")
    assert check(ws, john_plan).ok


def test_letter_right_employer_passes(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Lakeside Grocery Co-op I reduced produce shrink 18%.")
    assert check(ws, john_plan).ok


def test_letter_two_employers_in_one_sentence_warns(ws, john_plan):
    letter_body(john_plan, "I worked at Lakeside Grocery Co-op and then Northwind Distribution.")
    rep = check(ws, john_plan)
    assert any("names 2 employers" in w for w in rep.warnings)


# Issue #93: letter errors numbered sentences across hook, body, and close
# together ("cover_letter sentence 2"). They name the part and quote the start.
def test_letter_error_names_the_part_and_quotes_the_sentence(ws, john_plan):
    letter_body(john_plan, "I lead a team of 14. I cut overtime 40% at my current job.")
    rep = check(ws, john_plan)
    expect(rep, 'cover_letter body, "I cut overtime 40% at my...": '
                "the figure 40% is not in the facts")
    assert not any("sentence" in e for e in rep.errors), rep.errors


@pytest.mark.parametrize("part", ["hook", "close"])
def test_letter_error_in_hook_or_close_names_that_part(ws, john_plan, part):
    john_plan["cover_letter"][part] = "I saved $1M."
    expect(check(ws, john_plan), f'cover_letter {part}, "I saved $1M.": the figure')


def test_letter_error_counts_sentences_within_its_own_paragraph(ws, john_plan):
    # A paragraph that ends without a stop is still its own sentence.
    letter_body(john_plan, "Hello there\n\nI saved $1M.")
    expect(check(ws, john_plan), 'cover_letter body, "I saved $1M.": the figure')


def test_letter_employer_error_quotes_the_sentence(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Northwind Distribution I reduced shrink 18% with rotation checks.")
    expect(check(ws, john_plan), 'cover_letter body, "At Northwind Distribution I reduced '
                                 "shrink...\" (names 'Northwind Distribution')")


def test_letter_two_employers_warning_quotes_the_sentence(ws, john_plan):
    letter_body(john_plan, "I worked at Lakeside Grocery Co-op and then Northwind Distribution.")
    rep = check(ws, john_plan)
    assert any(w.startswith('cover_letter body, "I worked at Lakeside Grocery Co-op...": '
                            "names 2 employers") for w in rep.warnings), rep.warnings


# Issue #83 item 3 (audit A11): a sentence that names no employer carries the
# last one named earlier in its paragraph, so "There I also..." cannot take
# another employer's fact.
def test_letter_sentence_carries_the_employer_named_before_it(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Northwind Distribution I lead 14 associates. "
                           "There I also reduced produce shrink 18%.")
    expect(check(ws, john_plan), 'cover_letter body, "There I also reduced produce shrink..." '
                                 "(follows 'Northwind Distribution'): the figure 18%")


def test_carried_sentence_may_use_facts_that_belong_to_no_employer(ws, john_plan):
    # Skills, credentials, and personal projects are no employer's: the nurse
    # persona's "I chart in Epic" after a hospital sentence must pass.
    letter_body(john_plan, "At Northwind Distribution I lead 14 associates. "
                           "I also built a shift scheduling template that 40 small "
                           "businesses use (example.com/shift-scheduler).", keep_project=True)
    assert check(ws, john_plan).ok, check(ws, john_plan).errors


@pytest.mark.parametrize("text", [
    # A new paragraph starts fresh.
    "At Northwind Distribution I lead 14 associates.\n\nI also reduced produce shrink 18%.",
    # Naming the other employer again is the fix the agent makes.
    "At Northwind Distribution I lead 14 associates. "
    "At Lakeside Grocery Co-op I reduced produce shrink 18%.",
    # Two employers in one sentence: nothing single to carry.
    "I worked at Lakeside Grocery Co-op and then Northwind Distribution. "
    "I reduced produce shrink 18%.",
])
def test_letter_carry_forward_stops_where_it_should(ws, john_plan, text):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, text)
    rep = check(ws, john_plan)
    assert rep.ok, rep.errors


def test_letter_sentence_about_the_employer_carries_nothing(ws, john_plan):
    letter_body(john_plan, "At Northwind Distribution I lead 14 associates. "
                           "Your team of 20 needs a steady second shift.")
    assert check(ws, john_plan).ok, check(ws, john_plan).errors


def test_summary_sentence_carries_the_employer_named_before_it(ws, john_plan):
    john_plan["summary"] = {
        "atom": "summary.main", "cites": ["lakeside.shrink", "northwind.accuracy"],
        "text": "At Northwind Distribution I raised pick accuracy to 99.6%. "
                "I also reduced produce shrink 18%."}
    expect(check(ws, john_plan), "(follows 'Northwind Distribution'): the figure 18%")


def test_meters_written_short_match_the_atom(ws, john_plan):
    # Issue #10: "12 m" for an atom's "12 meters" is the same figure.
    add_atoms(ws, '[[bullet]]\nid = "northwind.conveyor"\nrole = "northwind"\n'
                  'text = "Laid out 12 meters of new conveyor"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append(
        {"atom": "northwind.conveyor", "text": "Laid out 12 m of new conveyor"})
    assert check(ws, john_plan).ok


def with_aliases(ws, northwind, lakeside=()):
    """Give John's two employers the short names people use for them (#9)."""
    path = ws.atoms_dir / "work.toml"
    text = path.read_text(encoding="utf-8")
    for employer, names in (("Northwind Distribution", northwind),
                            ("Lakeside Grocery Co-op", lakeside)):
        if names:
            quoted = ", ".join(f'"{n}"' for n in names)
            text = text.replace(f'employer = "{employer}"\n',
                                f'employer = "{employer}"\naliases = [{quoted}]\n')
    path.write_text(text, encoding="utf-8")


def test_letter_short_name_without_alias_is_not_bound(ws, john_plan):
    # Without aliases, "Northwind" alone is not the employer name: the
    # sentence falls back to the letter's whole pool.
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Northwind I reduced shrink 18% with rotation checks.")
    assert check(ws, john_plan).ok


def test_letter_alias_binds_the_sentence_to_its_employer(ws, john_plan):
    # Issue #9: the short name scopes the sentence like the full one.
    with_aliases(ws, ["Northwind"])
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Northwind I reduced shrink 18% with rotation checks.")
    expect(check(ws, john_plan), "(names 'Northwind')")


def test_letter_acronym_alias_binds_the_sentence(ws, john_plan):
    with_aliases(ws, ["NWD"])
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At NWD I reduced shrink 18% with rotation checks.")
    expect(check(ws, john_plan), "the figure 18% is not in the facts")


def test_letter_right_employer_by_alias_passes(ws, john_plan):
    with_aliases(ws, ["Northwind"], ["Lakeside"])
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "At Lakeside I reduced produce shrink 18%.")
    assert check(ws, john_plan).ok


def test_letter_full_name_and_its_alias_are_one_employer(ws, john_plan):
    with_aliases(ws, ["Northwind"])
    letter_body(john_plan, "Northwind Distribution, or Northwind as we call it, is where I work.")
    rep = check(ws, john_plan)
    assert rep.ok and not any("employers" in w for w in rep.warnings)


def test_letter_two_employers_by_alias_warns(ws, john_plan):
    with_aliases(ws, ["Northwind"], ["Lakeside"])
    letter_body(john_plan, "I worked at Lakeside and then Northwind.")
    rep = check(ws, john_plan)
    assert any("names 2 employers" in w for w in rep.warnings)


def test_bullet_naming_another_employers_alias(ws, john_plan):
    with_aliases(ws, ["Northwind"])
    john_plan["experience"][1]["bullets"][0] = {
        "atom": "lakeside.shrink", "text": "Reduced produce shrink 18% using the Northwind method"}
    expect(check(ws, john_plan), "names 'Northwind', but this fact belongs to "
                                 "Lakeside Grocery Co-op")


def test_bullet_may_name_its_own_employers_alias(ws, john_plan):
    with_aliases(ws, ["Northwind"], ["Lakeside"])
    john_plan["experience"][1]["bullets"][0] = {
        "atom": "lakeside.shrink", "text": "Reduced produce shrink 18% at Lakeside"}
    assert check(ws, john_plan).ok


def test_unit_changed_from_the_atom_is_caught(ws, john_plan):
    # Issue #10: same number, different unit, is a different fact.
    add_atoms(ws, '[[bullet]]\nid = "northwind.conveyor2"\nrole = "northwind"\n'
                  'text = "Laid out 120 feet of new conveyor"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append(
        {"atom": "northwind.conveyor2", "text": "Laid out 120 meters of new conveyor"})
    expect(check(ws, john_plan), "120 meters changes the unit; the facts say 120 feet")


@pytest.mark.parametrize("atom,line,ok", [
    ("Cut p99 latency to 300 ms", "Cut p99 latency to 300 milliseconds", True),
    ("Cut p99 latency to 300 ms", "Cut p99 latency to 300 seconds", False),
    ("Shrank the nightly export to 120 MB", "Shrank the nightly export to 120 Mb", False),
    ("Held the cooler at 38°F", "Held the cooler at 38 degrees Fahrenheit", True),
    ("Held the cooler at 38°F", "Held the cooler at 38°C", False),
    ("Ran a 10,000 sq ft cross-dock", "Ran a 10,000 square feet cross-dock", True),
    ("Ran a 10,000 sq ft cross-dock", "Ran a 10,000 ft cross-dock", False),
    ("Closed the backlog in 3 weeks", "Closed the backlog in 3 months", False),
])
def test_units_across_families(ws, john_plan, atom, line, ok):
    # Jesse's review on #24: the check covers the units people write.
    add_atoms(ws, f'[[bullet]]\nid = "northwind.unit"\nrole = "northwind"\n'
                  f'text = "{atom}"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append({"atom": "northwind.unit", "text": line})
    rep = check(ws, john_plan)
    if ok:
        assert rep.ok, rep.errors
    else:
        expect(rep, "changes the unit")


@pytest.mark.parametrize("atom,line,ok", [
    # Issue #37: each of these used to pass.
    ("Drove 650,000 miles", "Set a 650,000-km record", False),
    ("Cut setup to 40 minutes", "Cut setup to a 40-hour job", False),
    ("Drove 650,000 miles", "Drove 650k km", False),
    ("Drove 650,000 miles", "Drove 0.65 million km", False),
    # Clean passes stay clean.
    ("Worked a 40-hour week", "Worked a 40-hour week", True),
    ("Drove 650,000 miles", "Drove 650k miles", True),
    ("Led the 2 second-shift crews", "Led the 2 second-shift crews", True),
])
def test_hyphenated_and_multiplied_units(ws, john_plan, atom, line, ok):
    add_atoms(ws, f'[[bullet]]\nid = "northwind.unit"\nrole = "northwind"\n'
                  f'text = "{atom}"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append({"atom": "northwind.unit", "text": line})
    rep = check(ws, john_plan)
    if ok:
        assert rep.ok, rep.errors
    else:
        expect(rep, "changes the unit")


def test_unit_spelled_differently_passes(ws, john_plan):
    add_atoms(ws, '[[bullet]]\nid = "northwind.conveyor2"\nrole = "northwind"\n'
                  'text = "Laid out 120 feet of new conveyor"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append(
        {"atom": "northwind.conveyor2", "text": "Laid out 120 ft of new conveyor"})
    assert check(ws, john_plan).ok


def test_money_with_added_cents_is_added_precision(ws, john_plan):
    # Issue #11: "$84,000" confirmed; "$84,000.00" claims an exactness the
    # user never stated.
    add_atoms(ws, '[[bullet]]\nid = "northwind.savings"\nrole = "northwind"\n'
                  'text = "Saved $84,000 a year on pallet rentals"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append(
        {"atom": "northwind.savings", "text": "Saved $84,000.00 a year on pallet rentals"})
    expect(check(ws, john_plan), "the figure $84,000.00 is more precise than the facts ($84,000)")


def test_letter_figure_with_added_decimal_is_caught(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("lakeside.shrink")
    letter_body(john_plan, "I reduced produce shrink 18.0% with rotation checks.")
    expect(check(ws, john_plan), "the figure 18.0% is more precise than the facts (18%)")


@pytest.mark.parametrize("atom,line,ok", [
    # Jesse's review on #24: precision is the smallest amount a figure states.
    # "$1.2M" is to the nearest $100,000; "$1.20M" to $10,000; "$1,200,000"
    # to the dollar. A line may state a figure no more finely than its atom.
    ("Ran a $1.2M budget", "Ran a $1.20M budget", False),
    ("Ran a $1.2M budget", "Ran a $1,200,000 budget", False),
    ("Ran a $1.2M budget", "Ran a $1.2 million budget", True),
    ("Ran a $1,200,000 budget", "Ran a $1.2M budget", True),
    ("Ran a $1,200,000 budget", "Ran a $1,200,000 budget", True),
    ("Served 2.5 million riders", "Served 2.50 million riders", False),
    ("Served 2.5 million riders", "Served 2,500,000 riders", False),
    ("Shipped 12,000 orders", "Shipped 12k orders", True),
    ("Shipped 12k orders", "Shipped 12,000 orders", False),
])
def test_precision_counts_the_multiplier(ws, john_plan, atom, line, ok):
    add_atoms(ws, f'[[bullet]]\nid = "northwind.scale"\nrole = "northwind"\n'
                  f'text = "{atom}"\nbasis = "records"\n')
    john_plan["experience"][0]["bullets"].append({"atom": "northwind.scale", "text": line})
    rep = check(ws, john_plan)
    if ok:
        assert rep.ok, rep.errors
    else:
        expect(rep, "is more precise than the facts")


def test_letter_may_quote_the_postings_figures(ws, john_plan):
    letter_body(john_plan, "Your 6 cross-dock facilities and a second-shift team of 20 "
                           "need steady leadership.")
    assert check(ws, john_plan).ok


# Issue #83 item 1 (audit A4): the posting's figures and tools are about the
# employer. A sentence may use them only when it is about the employer ("you",
# "your", or the company's name) and not about the user ("I", "my", "we").
@pytest.mark.parametrize("text,needle", [
    ("I bring 20 years of supervising warehouse teams.", "the figure 20"),
    ("Your team of 20 is the size I lead now.", "the figure 20"),
    ("My last team was 20 people.", "the figure 20"),
    ("We ran 6 cross-dock facilities.", "the figure 6"),
])
def test_letter_sentence_about_the_user_cannot_take_the_postings_figures(
        ws, john_plan, text, needle):
    letter_body(john_plan, text)
    expect(check(ws, john_plan), f'{needle} is in the posting, not your facts')


@pytest.mark.parametrize("text", [
    "Your 6 cross-dock facilities need a steady second shift.",
    "Prairie Freight runs 6 cross-dock facilities.",
    "Prairie Freight Co. needs a lead for a team of 20.",
])
def test_letter_sentence_about_the_employer_may_quote_the_posting(ws, john_plan, text):
    letter_body(john_plan, text)
    assert check(ws, john_plan).ok, check(ws, john_plan).errors


EXCEL_JOB = {**JOB, "description": JOB["description"] + " Schedules are kept in Excel."}


def with_excel_skill(ws):
    add_atoms(ws, '[[skill]]\nid = "skills.office"\nlabel = "Office"\nitems = ["Excel"]\n')


def test_letter_cannot_claim_a_tool_only_the_posting_names(ws, john_plan):
    with_excel_skill(ws)
    letter_body(john_plan, "I keep every schedule in Excel.")
    expect(check(ws, john_plan, EXCEL_JOB), "'Excel' is in the posting, not your facts")


def test_letter_may_name_the_postings_tool_about_the_employer(ws, john_plan):
    with_excel_skill(ws)
    letter_body(john_plan, "Your schedules live in Excel.")
    assert check(ws, john_plan, EXCEL_JOB).ok


def test_letter_never_claim(ws, john_plan):
    letter_body(john_plan, "I have used SAP for inventory.")
    expect(check(ws, john_plan), "claims 'SAP'")


def test_letter_never_claim_with_a_look_alike_letter(ws, john_plan):
    letter_body(john_plan, "I have used S\u0410P for inventory.")
    rep = check(ws, john_plan)
    expect(rep, "claims 'SAP'")
    expect(rep, "mixes Latin and Cyrillic")


def test_letter_tool_not_cited(ws, john_plan):
    letter_body(john_plan, "I run our receiving in Manhattan WMS.")
    expect(check(ws, john_plan), "mentions 'Manhattan WMS'")


def test_letter_banned_word_phrase_dash(ws, john_plan):
    letter_body(john_plan, "I am passionate about safety and I'm excited to leverage it – truly.")
    rep = check(ws, john_plan)
    expect(rep, "banned word(s) ['leverage', 'passionate']")
    expect(rep, "banned phrase(s) [\"i'm excited to\", 'passionate about']")
    expect(rep, "en dash")


# Issue #16: how far the letter may trust the posting depends on how it was
# captured. Structured data (json-ld) is the posting itself; a whole-page
# capture (page-text) may hold other listings; a paste is whatever the user
# selected.
POSTING_FIGURES = "Your 6 cross-dock facilities and a second-shift team of 20 need a steady lead."
OWN_FIGURE = "I lead a team of 14 associates across two shifts."


def test_letter_may_quote_a_structured_postings_figures_quietly(ws, john_plan):
    letter_body(john_plan, POSTING_FIGURES)
    rep = check(ws, john_plan, {**JOB, "source": "json-ld"})
    assert rep.ok and not any("only from the posting" in w for w in rep.warnings)


def test_letter_figure_only_in_a_page_capture_is_refused(ws, john_plan):
    letter_body(john_plan, POSTING_FIGURES)
    rep = check(ws, john_plan, {**JOB, "source": "page-text"})
    expect(rep, "the figure 6 is not in the facts")
    expect(rep, "the figure 20 is not in the facts")
    assert any("whole page" in w for w in rep.warnings), rep.warnings
    # #31: --force replaces only the same posting, so the advice carries --url.
    assert any("--url <link> --force" in w for w in rep.warnings), rep.warnings


def test_letter_without_posting_figures_passes_a_page_capture(ws, john_plan):
    letter_body(john_plan, OWN_FIGURE)
    rep = check(ws, john_plan, {**JOB, "source": "page-text"})
    assert rep.ok, rep.errors
    assert not any("whole page" in w for w in rep.warnings)


def test_letter_figure_only_in_a_pasted_posting_warns(ws, john_plan):
    letter_body(john_plan, POSTING_FIGURES)
    rep = check(ws, john_plan, {**JOB, "source": "manual"})
    assert rep.ok, rep.errors
    only = [w for w in rep.warnings if "only from the posting" in w]
    assert len(only) == 1 and "6, 20" in only[0], rep.warnings


def test_letter_figure_in_the_facts_and_the_posting_does_not_warn(ws, john_plan):
    # 14 is John's own figure; that the posting also says 14 changes nothing.
    letter_body(john_plan, OWN_FIGURE)
    job = {**JOB, "source": "manual", "description": "Lead a team of 14."}
    rep = check(ws, john_plan, job)
    assert rep.ok and not any("only from the posting" in w for w in rep.warnings)


def test_letter_dashes_allowed_when_profile_says_so(ws, john_plan):
    text = ws.profile_path.read_text(encoding="utf-8").replace("ban_dashes = true", "ban_dashes = false")
    ws.profile_path.write_text(text, encoding="utf-8")
    letter_body(john_plan, "Safety matters — a lot.")
    assert check(ws, john_plan).ok


# Issue #88 (audit A12): the dash ban caught only the em and en dash.
OTHER_DASHES = [("‒", "figure dash"), ("―", "horizontal bar"),
                ("⸺", "two-em dash"),
                ("⸻", "three-em dash"), ("﹘", "small em dash"),
                ("︱", "presentation form for vertical em dash")]
UNICODE_HYPHENS = [("‐", "hyphen"), ("‑", "non-breaking hyphen"),
                   ("－", "fullwidth hyphen-minus"), ("﹣", "small hyphen-minus"),
                   ("−", "minus sign")]  # #114: "−20%" wants a hyphen, not a comma


def dash_bullet(john_plan, ch):
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime",
        "text": f"Cut weekly overtime 25% {ch} by rebuilding the shift schedule"}


@pytest.mark.parametrize("ch,name", OTHER_DASHES)
def test_every_dash_is_banned(ws, john_plan, ch, name):
    dash_bullet(john_plan, ch)
    rep = check(ws, john_plan)
    expect(rep, f"contains a {name} ({ch}, U+{ord(ch):04X}). Use a comma, colon, or period.")


@pytest.mark.parametrize("ch,name", UNICODE_HYPHENS)
def test_a_unicode_hyphen_asks_for_a_plain_one(ws, john_plan, ch, name):
    # They look like a hyphen but an ATS will not match "scan<U+2011>to" as
    # "scan-to"; the advice is to retype it, not to restructure the sentence.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime",
        "text": f"Cut weekly overtime 25% by rebuilding the shift{ch}schedule"}
    expect(check(ws, john_plan), f"({ch}, U+{ord(ch):04X}). Type a plain hyphen (-) instead.")


@pytest.mark.parametrize("ch", [c for c, _ in OTHER_DASHES + UNICODE_HYPHENS])
def test_other_dashes_allowed_when_profile_says_so(ws, john_plan, ch):
    text = ws.profile_path.read_text(encoding="utf-8").replace("ban_dashes = true",
                                                               "ban_dashes = false")
    ws.profile_path.write_text(text, encoding="utf-8")
    dash_bullet(john_plan, ch)
    assert check(ws, john_plan).ok


@pytest.mark.parametrize("word", ["scan-to-confirm",          # ASCII hyphen
                                  "בית־ספר",  # Hebrew maqaf
                                  "հայ֊երեն"])
def test_plain_and_script_hyphens_are_not_dashes(ws, john_plan, word):
    # A word in Hebrew or Armenian is joined with its own script's hyphen.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": f"Cut weekly overtime 25% with {word} checks"}
    assert not [e for e in check(ws, john_plan).errors if "U+" in e and "contains" in e]


def test_letter_word_limit_comes_from_profile(ws, john_plan):
    # F19: one number, in the profile, read by both the check and the instructions.
    letter_body(john_plan, " ".join(["word"] * 400))
    expect(check(ws, john_plan), "the limit is 300 (profile setting")


def test_letter_atom_id_leak(ws, john_plan):
    letter_body(john_plan, "See northwind.accuracy for details.")
    expect(check(ws, john_plan), "contains atom id(s) ['northwind.accuracy']")


def test_letter_project_url_missing(ws, john_plan):
    letter_body(john_plan, "I also built a shift scheduling template that 40 small businesses use.",
                keep_project=True)
    expect(check(ws, john_plan), "Include example.com/shift-scheduler")


def test_letter_project_named_by_title_needs_url(ws, john_plan):
    john_plan["cover_letter"]["cites"] = ["northwind.team"]
    letter_body(john_plan, "I built Shift Scheduler in my spare time.")
    expect(check(ws, john_plan), "mentions project 'Shift Scheduler' but not its URL")


def test_letter_url_host_only_is_not_enough(ws, john_plan):
    # F22: matching a host or one path segment let letters through with no URL.
    letter_body(john_plan, "My template is used by 40 small businesses (see example.com).",
                keep_project=True)
    expect(check(ws, john_plan), "Include example.com/shift-scheduler")


def test_letter_url_last_segment_only_is_not_enough(ws, john_plan):
    letter_body(john_plan, "My shift-scheduler template is used by 40 small businesses.",
                keep_project=True)
    expect(check(ws, john_plan), "Include example.com/shift-scheduler")


def test_letter_full_url_with_scheme_passes(ws, john_plan):
    letter_body(john_plan, "40 small businesses use my template: https://example.com/shift-scheduler/",
                keep_project=True)
    assert check(ws, john_plan).ok


def test_dead_project_url_is_not_required(ws, john_plan):
    text = (ws.atoms_dir / "other.toml").read_text(encoding="utf-8").replace(
        'url = "https://example.com/shift-scheduler"',
        'url = "https://example.com/shift-scheduler"\nurl_status = "dead"')
    (ws.atoms_dir / "other.toml").write_text(text, encoding="utf-8")
    letter_body(john_plan, "I also built a shift scheduling template that 40 small businesses use.",
                keep_project=True)
    assert check(ws, john_plan).ok


def test_project_without_url_needs_none(ws, john_plan):
    add_atoms(ws, '[[project]]\nid = "dock"\ntitle = "Dock Board"\ncontext = "personal"\n')
    john_plan["cover_letter"]["cites"].append("dock")
    letter_body(john_plan, "I made a Dock Board for my team.")
    assert check(ws, john_plan).ok


def test_url_key():
    assert url_key("https://www.Example.com/a/") == "example.com/a"


def test_vocabulary_includes_skills_credentials_and_never_claim(ws):
    vocab = vocabulary(load_inventory(ws), load_profile(ws))
    for term in ("Manhattan WMS", "Excel", "OSHA 10-Hour General Industry", "SAP"):
        assert term in vocab


# Issue #49: the remaining fact-check branches, each with the behavior it guards.
def test_without_a_job_the_letter_cannot_quote_posting_figures(ws, john_plan):
    # No job.json to trust: a figure only the posting states is not a fact.
    letter_body(john_plan, "Your 6 cross-dock facilities need a steady lead.")
    expect(check(ws, john_plan, job=None), "the figure 6 is not in the facts")


# Issue #122: a career-wide figure in a sentence that names an employer fails
# (the check cannot tell "with 9 years" from "for 9 years"), but the message
# said the figure was not in the line's facts when it was.
CAREER = "the figure 9 is not in Northwind Distribution's facts. If it is about your whole career"


def test_summary_career_figure_next_to_an_employer_says_what_to_do(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind"],
                            "text": "Warehouse supervisor at Northwind Distribution with 9 "
                                    "years in distribution."}
    rep = check(ws, john_plan)
    expect(rep, CAREER)
    assert not any("is not in the facts this line cites" in e for e in rep.errors), rep.errors


def test_summary_career_figure_in_its_own_sentence_passes(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind"],
                            "text": "Warehouse supervisor with 9 years in distribution. "
                                    "Currently at Northwind Distribution."}
    assert check(ws, john_plan).ok, check(ws, john_plan).errors


def test_letter_career_figure_next_to_an_employer_says_what_to_do(ws, john_plan):
    john_plan["cover_letter"]["cites"].append("summary.main")
    letter_body(john_plan, "At Northwind Distribution I bring 9 years in distribution.")
    expect(check(ws, john_plan), CAREER)


def test_another_employers_figure_keeps_the_d40_message(ws, john_plan):
    # Not career-wide: Lakeside's 18% credited to Northwind stays the D-40
    # error, with no advice to move it.
    john_plan["summary"] = {"atom": "summary.main", "cites": ["lakeside.shrink", "northwind"],
                            "text": "At Northwind Distribution, reduced produce shrink 18%."}
    rep = check(ws, john_plan)
    expect(rep, "(names 'Northwind Distribution'): the figure 18% is not in the facts")
    assert not any("whole career" in e for e in rep.errors), rep.errors


def test_a_figure_in_no_cited_fact_keeps_the_plain_message(ws, john_plan):
    john_plan["summary"] = {"atom": "summary.main", "cites": ["northwind"],
                            "text": "Warehouse supervisor at Northwind Distribution with 11 "
                                    "years in distribution."}
    expect(check(ws, john_plan), "the figure 11 is not in the facts this line cites")


def test_a_plan_without_a_letter_gets_no_letter_errors(ws, john_plan):
    from dataclasses import replace
    from jobforge.factcheck import Report, check_letter
    inv = load_inventory(ws)
    resolved, errors, _ = resolve(john_plan, inv)
    rep = Report()
    check_letter(replace(resolved, letter=None), inv, load_profile(ws), [], rep, JOB)
    assert errors == [] and rep.errors == [] and rep.warnings == []


def test_bullet_whose_project_is_missing_counts_only_its_own_text(ws):
    # The loader refuses a dangling project reference; the check still must
    # not crash or borrow facts if it ever meets one.
    from pathlib import Path
    from jobforge.atoms import Atom, Inventory
    from jobforge.factcheck import Report, _pool_text, check_letter
    from jobforge.plan import Letter, ResolvedPlan
    bullet = Atom("bullet", "x.b", {"id": "x.b", "project": "gone", "text": "Saved 12 hours",
                                    "basis": "records"}, Path("x.toml"))
    inv = Inventory({"x.b": bullet})
    assert _pool_text([bullet], inv).strip() == "Saved 12 hours"
    rep = Report()
    plan = ResolvedPlan(letter=Letter("I saved 12 hours.", "", "", [bullet]))
    check_letter(plan, inv, load_profile(ws), [], rep, None)
    assert rep.errors == []


# Issue #85 (audit A13): a hidden character fails `check`, not only `apply`'s
# read-back, so the agent's check loop catches it a round earlier.
HIDDEN = [("\u200b", "zero-width space"), ("\u202e", "text direction control"),
          ("\u00ad", "soft hyphen")]


def plant(plan, where, ch):
    if where == "bullet":
        plan["experience"][0]["bullets"][2] = {
            "atom": "northwind.overtime",
            "text": f"Cut weekly over{ch}time 25% by rebuilding the shift schedule"}
    elif where == "summary":
        plan["summary"] = {"atom": "summary.main",
                           "text": f"Warehouse super{ch}visor with 9 years in distribution."}
    else:  # a part of the letter: hook, body, or close
        part = where.split(".")[1]
        plan["cover_letter"][part] = plan["cover_letter"][part].replace(
            "second", f"sec{ch}ond", 1)


@pytest.mark.parametrize("ch,name", HIDDEN)
@pytest.mark.parametrize("where,label", [
    ("bullet", "experience[0].bullets[2]"), ("summary", "summary"),
    ("cover_letter.hook", "cover_letter hook"), ("cover_letter.close", "cover_letter close"),
])
def test_hidden_character_fails_check(ws, john_plan, ch, name, where, label):
    plant(john_plan, where, ch)
    rep = check(ws, john_plan)
    hits = [e for e in rep.errors if "hidden character" in e]
    assert len(hits) == 1, rep.errors
    assert hits[0].startswith(label) and name in hits[0]
    assert "Remove it from the atom or plan text it came from" in hits[0]


def test_hidden_character_in_the_letter_body_fails_check(ws, john_plan):
    john_plan["cover_letter"]["body"] = john_plan["cover_letter"]["body"].replace(
        "associates", "asso\u200bciates", 1)
    expect(check(ws, john_plan), "cover_letter body: hidden character: zero-width space")


def test_hidden_character_cannot_slip_a_never_claim_term_past_check(ws, john_plan):
    # "S<U+200B>AP" was invisible to never-claim; now the character itself fails.
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime 25% using S\u200bAP"}
    expect(check(ws, john_plan), "hidden character: zero-width space")


def test_a_minus_sign_in_a_figure_asks_for_a_plain_hyphen(ws, john_plan):
    # #114: "Use a comma, colon, or period" is wrong advice for "−5°C".
    john_plan["experience"][0]["bullets"][2] = {
        "atom": "northwind.overtime", "text": "Cut weekly overtime \u221225% by rebuilding the shift schedule"}
    rep = check(ws, john_plan)
    expect(rep, "contains a minus sign (\u2212, U+2212). Type a plain hyphen (-) instead.")
    assert not any("comma" in e for e in rep.errors if "U+2212" in e)
