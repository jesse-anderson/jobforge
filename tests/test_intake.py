"""D-30 item 2: job intake from a URL (saved HTML, fetch stubbed) and from
pasted text, including the private repo's failures F23 and F27."""
import json
import re
import urllib.error

import pytest

from jobforge import extract
from jobforge.errors import JobforgeError
from jobforge.extract import (FetchBlocked, from_text, from_url, html_to_text,
                              looks_like_domain, strip_title_suffix)
from jobforge.ledger import read_events
from jobforge.prepare import folder_name, prepare, slug

from conftest import FIXTURES, TODAY

pytestmark = pytest.mark.critical
HTML = FIXTURES / "html"
LONG = "Real posting text. " * 20


def fake_fetch(name):
    return lambda url: (HTML / name).read_text(encoding="utf-8")


def test_json_ld_posting():
    job, warnings = from_url("https://acme.example.com/jobs/1", fetch=fake_fetch("jsonld_posting.html"))
    assert job.company == "Acme Manufacturing"
    assert job.title == "Maintenance Technician"
    assert job.location == "Peoria, IL, US"
    assert job.source == "json-ld"
    assert "12 press lines" in job.description
    assert "Ignored when JSON-LD exists" not in job.description
    assert "<p>" not in job.description
    assert warnings == []


def test_page_text_fallback_strips_suffix_and_requires_company():
    # F23: no JSON-LD, title carries " - Google Careers", company unknown.
    with pytest.raises(JobforgeError, match="Pass --company"):
        from_url("https://careers.google.com/jobs/123", fetch=fake_fetch("no_jsonld_google_style.html"))
    job, warnings = from_url("https://careers.google.com/jobs/123", company="Google",
                             fetch=fake_fetch("no_jsonld_google_style.html"))
    assert job.title == "Field Applications Engineer"
    assert job.company == "Google"
    assert job.source == "page-text"
    assert any("No structured posting data" in w for w in warnings)


def test_domain_company_is_refused_and_placeholders_stripped():
    # F27: Breezy page, company from og:site_name is a hostname.
    with pytest.raises(JobforgeError, match="web address, not a company name"):
        from_url("https://ironbark.breezy.hr/p/1", fetch=fake_fetch("breezy_placeholders.html"))
    job, _ = from_url("https://ironbark.breezy.hr/p/1", company="Ironbark",
                      fetch=fake_fetch("breezy_placeholders.html"))
    assert job.title == "GPU Compute Engineer"
    assert "%" not in job.description


def test_blocked_board_says_to_paste():
    def blocked(url):
        raise FetchBlocked("Could not read it: HTTP 403.\n" + extract.PASTE_HINT)
    with pytest.raises(FetchBlocked, match="--from-text"):
        from_url("https://example.com/j", fetch=blocked)


def test_fetch_html_turns_http_errors_into_paste_hint(monkeypatch):
    def raise_403(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(extract.urllib.request, "urlopen", raise_403)
    with pytest.raises(FetchBlocked, match="HTTP 403 Forbidden"):
        extract.fetch_html("https://example.com/j")

    def raise_url(req, timeout):
        raise urllib.error.URLError("name not resolved")
    monkeypatch.setattr(extract.urllib.request, "urlopen", raise_url)
    with pytest.raises(FetchBlocked, match="Could not reach"):
        extract.fetch_html("https://example.com/j")


def test_almost_empty_page_says_to_paste():
    html = "<html><head><title>Welder | Jobs</title></head><body><div id=app></div></body></html>"
    with pytest.raises(JobforgeError, match="almost no description"):
        from_url("https://x.example.com/1", company="Acme", fetch=lambda u: html)


def test_url_must_be_http():
    with pytest.raises(JobforgeError, match="not an http"):
        from_url("example.com/jobs/1", fetch=lambda u: "")


@pytest.mark.parametrize("raw,clean", [
    ("Process Engineer | Acme Careers", "Process Engineer"),
    ("Field Applications Engineer — Google Careers", "Field Applications Engineer"),
    ("Welder - Jobs at Acme", "Welder"),
    ("Data Analyst at Ironbark Compute Group", "Data Analyst"),
    ("Software Engineer - Infrastructure", "Software Engineer - Infrastructure"),
    ("Driver  ::  Indeed", "Driver"),
])
def test_strip_title_suffix(raw, clean):
    assert strip_title_suffix(raw) == clean


@pytest.mark.parametrize("name,is_domain", [
    ("google.com", True), ("ironbark.breezy.hr", True), ("jobs.example.co.uk", True),
    ("Google", False), ("Acme Co.", False), ("Prairie Freight Co.", False),
])
def test_looks_like_domain(name, is_domain):
    assert looks_like_domain(name) is is_domain


def test_from_text_plain_and_html():
    job, _ = from_text(LONG, company="Acme", title="Welder")
    assert job.source == "manual" and job.description.startswith("Real posting text.")
    job, _ = from_text("<div><p>" + LONG + "</p><ul><li>Item</li></ul></div>",
                       company="Acme", title="Welder")
    assert "<" not in job.description and "Item" in job.description


@pytest.mark.parametrize("kwargs,needle", [
    ({"text": "  ", "company": "A", "title": "T"}, "empty"),
    ({"text": LONG, "company": None, "title": "T"}, "needs --company and --title"),
    ({"text": LONG, "company": "A", "title": ""}, "needs --company and --title"),
    ({"text": "short", "company": "A", "title": "T"}, "almost no description"),
    ({"text": LONG, "company": "A", "title": "T", "url": "example.com/x"}, "not an http"),
])
def test_from_text_errors(kwargs, needle):
    text = kwargs.pop("text")
    with pytest.raises(JobforgeError, match=needle):
        from_text(text, **kwargs)


def test_hidden_characters_in_postings_are_cleaned():
    title = "Operations Supervisor​"
    job, _ = from_text(LONG + "­ﬁnal", company="Prairie Freight", title=title)
    assert job.title == "Operations Supervisor"
    assert job.company == "Prairie Freight"
    assert "­" not in job.description and "final" in job.description


def test_html_to_text_drops_scripts_and_keeps_blocks():
    text = html_to_text("<p>One</p><script>var x=1</script><style>p{}</style><p>Two</p>")
    assert text == "One\n\nTwo"


def test_prepare_writes_job_and_first_event(ws):
    job, _ = from_text(LONG, company="Acme Co.", title="Line Lead / 2nd Shift")
    folder, warnings = prepare(ws, job, today=TODAY)
    assert folder.name == "acme_co__line_lead_2nd_shift__2026-11-20"
    data = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    assert data["company"] == "Acme Co." and data["prepared"] == "2026-11-20"
    events = read_events(folder)
    assert [(e.stage, e.date) for e in events] == [("prepared", TODAY)]
    assert warnings == []


def test_prepare_twice_needs_force(ws):
    job, _ = from_text(LONG, company="Acme", title="Welder")
    folder, _ = prepare(ws, job, today=TODAY)
    with pytest.raises(JobforgeError, match="--force"):
        prepare(ws, job, today=TODAY)
    prepare(ws, job, today=TODAY, force=True)
    assert len(read_events(folder)) == 1  # force does not add a second "prepared"


def test_prepare_warns_about_an_earlier_folder(ws):
    job, _ = from_text(LONG, company="Acme", title="Welder", url="https://example.com/j/1")
    prepare(ws, job, today=TODAY)
    import datetime as dt
    _, warnings = prepare(ws, job, today=TODAY + dt.timedelta(days=3))
    assert any("already have a folder" in w for w in warnings)


def test_slug_is_bounded_and_never_empty():
    assert slug("!!!") == "untitled"
    assert len(slug("x" * 200)) <= 40


def test_folder_name_format():
    job, _ = from_text(LONG, company="A&B", title="C/D")
    assert folder_name(job, TODAY) == "a_b__c_d__2026-11-20"


# Issue #4: one posting from each common board, saved with the real page's
# structure (2026-11) and fictional text. Each either gives correct fields or
# stops and asks for what it could not read. Never a domain or an entity code
# as the company (F23), never a %PLACEHOLDER% in the description (F27).
BOARDS = [
    # fixture, url, company, title, location, source, a phrase from the posting
    ("lever_posting.html", "https://jobs.lever.co/harborpoint/00000000-0000-4000-8000-000000000002",
     "Harbor Point Logistics", "Warehouse Operations Lead", "Memphis, Tennessee", "json-ld",
     "400,000 sq ft cross-dock"),
    ("ashby_posting.html", "https://jobs.ashbyhq.com/northbeam/00000000-0000-4000-8000-000000000001",
     "Northbeam Energy", "Controls Engineer", "Denver, CO, USA", "json-ld", "Modbus and DNP3"),
]


@pytest.mark.parametrize("fixture,url,company,title,location,source,phrase", BOARDS,
                         ids=[b[0].split(".")[0] for b in BOARDS])
def test_board_posting_fields(fixture, url, company, title, location, source, phrase):
    job, warnings = from_url(url, fetch=fake_fetch(fixture))
    assert (job.company, job.title, job.location, job.source) == (company, title, location, source)
    assert phrase in job.description
    assert not looks_like_domain(job.company)
    assert not re.search(r"%[A-Z][A-Z0-9_]{2,}%", job.description)
    assert bool(warnings) is (source == "page-text")


def test_google_careers_posting_asks_for_the_company():
    url = "https://www.google.com/about/careers/applications/jobs/results/123-technical-support-engineer"
    with pytest.raises(JobforgeError, match="Pass --company"):
        from_url(url, fetch=fake_fetch("google_careers_job.html"))
    job, warnings = from_url(url, company="Google", fetch=fake_fetch("google_careers_job.html"))
    assert job.title == "Technical Support Engineer, Cloud Storage"
    assert job.source == "page-text"
    assert "storage performance" in job.description
    assert any("No structured posting data" in w for w in warnings)


def test_workday_entity_code_is_not_taken_as_the_company():
    """Workday's JSON-LD names an internal legal entity ("2100 NVIDIA USA"),
    which would go out as "Dear 4100 Fernwood Industries USA Hiring Team"."""
    url = ("https://fernwood.wd5.myworkdayjobs.com/en-US/External/job/US-OH-Dayton/"
           "Senior-Process-Engineer---Molding_JR0000001")
    with pytest.raises(JobforgeError, match="entity code") as exc:
        from_url(url, fetch=fake_fetch("workday_posting.html"))
    assert "Pass --company" in exc.value.render()
    job, warnings = from_url(url, company="Fernwood Industries",
                             fetch=fake_fetch("workday_posting.html"))
    assert job.company == "Fernwood Industries"
    assert job.title == "Senior Process Engineer – Molding"
    assert job.location == "US, OH, Dayton, United States of America"
    assert job.source == "json-ld" and warnings == []
    assert "30 presses" in job.description


def test_a_company_you_name_that_starts_with_digits_is_kept():
    job, _ = from_url("https://x.example.com/1", company="99 Cents Only Stores",
                      fetch=fake_fetch("workday_posting.html"))
    assert job.company == "99 Cents Only Stores"
