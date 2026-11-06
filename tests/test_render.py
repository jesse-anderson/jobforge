import datetime as dt

from jobforge.atoms import load_inventory
from jobforge.docx import Block, Run
from jobforge.plan import resolve
from jobforge.profile import load_profile
from jobforge.render import (date_range, estimate_pages, fmt_date, letter_blocks,
                             letter_markdown, resume_blocks)

from conftest import add_atoms

JOB = {"company": "Prairie Freight Co.", "title": "Operations Supervisor",
       "url": "https://example.com/jobs/1"}


def resolved(ws, plan):
    out, errors, _ = resolve(plan, load_inventory(ws))
    assert not errors, errors
    return out


def texts(blocks):
    return [b.text() for b in blocks]


def test_dates():
    assert fmt_date("2020-04") == "Apr 2020"
    assert fmt_date("2016") == "2016"
    assert fmt_date("present") == "Present"
    assert fmt_date(None) == ""
    assert date_range("2020-04", "present") == "Apr 2020 to Present"
    assert date_range("2020", None) == "2020"
    assert date_range(None, None) == ""


def test_resume_sections_in_order(ws, john_plan):
    blocks = resume_blocks(resolved(ws, john_plan), load_profile(ws))
    headings = [b.text() for b in blocks if b.kind == "heading"]
    assert headings == ["Summary", "Experience", "Projects", "Skills", "Credentials", "Education"]
    t = texts(blocks)
    assert t[0] == "John Smith"
    assert t[1] == "john.smith@example.com | 555-0100 | Springfield, IL | example.com/johnsmith"
    assert ("Warehouse Supervisor | Northwind Distribution | Springfield, IL | "
            "Apr 2020 to Present") in t


def test_no_dash_from_the_engine(ws, john_plan):
    # The engine never adds a dash the user did not write.
    for b in resume_blocks(resolved(ws, john_plan), load_profile(ws)):
        assert "–" not in b.text() and "—" not in b.text()


def test_empty_sections_are_left_out(ws, john_plan):
    john_plan.update(projects=[], skills=[], credentials=[])
    john_plan.pop("summary")
    headings = [b.text() for b in resume_blocks(resolved(ws, john_plan), load_profile(ws))
                if b.kind == "heading"]
    assert headings == ["Experience", "Education"]


def test_project_url_is_visible_text(ws, john_plan):
    blocks = resume_blocks(resolved(ws, john_plan), load_profile(ws))
    line = next(b for b in blocks if b.text().startswith("Shift Scheduler"))
    assert "example.com/shift-scheduler" in line.text()


def test_dead_url_is_not_rendered_and_writeup_is(ws, john_plan):
    add_atoms(ws, '[[project]]\nid = "old"\ntitle = "Old Tool"\ncontext = "personal"\n'
                  'url = "https://example.com/old"\nurl_status = "dead"\n'
                  'writeup_url = "https://example.com/old/post"\n')
    john_plan["projects"] = [{"project": "old", "include_writeup": True}]
    blocks = resume_blocks(resolved(ws, john_plan), load_profile(ws))
    line = next(b for b in blocks if b.text().startswith("Old Tool"))
    assert "example.com/old/post" in line.text()
    assert "example.com/old |" not in line.text() + " |"


def test_letter_has_no_working_copy_material(ws, john_plan):
    plan = resolved(ws, john_plan)
    blocks = letter_blocks(plan, load_profile(ws), JOB, dt.date(2026, 11, 20))
    t = texts(blocks)
    assert t[2] == "Nov 20, 2026"
    assert t[3] == "Re: Operations Supervisor | Prairie Freight Co."
    assert t[4] == "Dear Prairie Freight Co. Hiring Team,"
    assert t[-2:] == ["Sincerely,", "John Smith"]
    joined = "\n".join(t)
    assert "Cover letter" not in joined and "northwind." not in joined and "#" not in joined


def test_letter_without_company(ws, john_plan):
    blocks = letter_blocks(resolved(ws, john_plan), load_profile(ws), {}, dt.date(2026, 1, 2))
    assert "Dear Hiring Team," in texts(blocks)


def test_working_copy_says_do_not_send(ws, john_plan):
    md = letter_markdown(resolved(ws, john_plan), JOB)
    assert md.startswith("# Cover letter (working copy, do not send)")
    assert "`northwind.accuracy`" in md


def test_page_estimate_grows_with_content():
    short = [Block("title", [Run("A")]), Block("para", [Run("x" * 50)])]
    long = short + [Block("bullet", [Run("y" * 200)])] * 60
    assert estimate_pages(short) < 0.2
    assert estimate_pages(long) > 1.5


def test_john_smith_fits_one_page(ws, john_plan):
    assert estimate_pages(resume_blocks(resolved(ws, john_plan), load_profile(ws))) < 1
