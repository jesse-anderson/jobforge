"""Edge cases on critical paths that the main tests do not reach."""
import json

import pytest

from jobforge import extract
from jobforge.atoms import load_inventory
from jobforge.cli import main
from jobforge.confirm import describe
from jobforge.errors import JobforgeError
from jobforge.extract import from_text, from_url
from jobforge.inventory import render_markdown
from jobforge.ledger import resolve_job
from jobforge.plan import resolve
from jobforge.prepare import prepare, read_job, similar_jobs
from jobforge.profile import load_profile
from jobforge.render import resume_blocks
from jobforge.workspace import ENV_VAR, init_workspace

from conftest import TODAY, add_atoms

LONG = "Real posting text. " * 20


def page(ld: str, title: str = "Welder | Acme Careers", body: str = LONG) -> str:
    return (f"<html><head><title>{title}</title>"
            f'<script type="application/ld+json">{ld}</script></head>'
            f"<body><p>{body}</p></body></html>")


def test_malformed_json_ld_block_is_skipped():
    html = page("{not json") .replace(
        "</head>", '<script type="application/ld+json">'
                   '{"@type": "JobPosting", "title": "Welder", '
                   '"hiringOrganization": "Acme", "jobLocation": "Peoria, IL", '
                   f'"description": "{LONG}"}}</script></head>')
    job, _ = from_url("https://example.com/j", fetch=lambda u: html)
    assert (job.company, job.title, job.location) == ("Acme", "Welder", "Peoria, IL")


def test_json_ld_without_description_or_title_falls_back():
    ld = json.dumps({"@type": "JobPosting", "hiringOrganization": {"name": "Acme"},
                     "jobLocation": [{"address": {"addressLocality": ""}}], "description": " "})
    job, warnings = from_url("https://example.com/j", fetch=lambda u: page(ld))
    assert job.title == "Welder"           # from <title>, suffix stripped
    assert job.location == ""
    assert "Real posting text." in job.description
    assert warnings  # page text was used


def test_no_title_anywhere_asks_for_one():
    html = f"<html><body><p>{LONG}</p></body></html>"
    with pytest.raises(JobforgeError, match="Pass --title"):
        from_url("https://example.com/j", company="Acme", fetch=lambda u: html)


def test_fetch_html_reads_and_decodes(monkeypatch):
    class Resp:
        class headers:
            @staticmethod
            def get_content_charset():
                return "latin-1"

        def read(self):
            return "café".encode("latin-1")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(extract.urllib.request, "urlopen", lambda req, timeout: Resp())
    assert extract.fetch_html("https://example.com") == "café"


def test_read_job_rejects_bad_json(tmp_path):
    (tmp_path / "job.json").write_text("{", encoding="utf-8")
    with pytest.raises(JobforgeError, match="not valid JSON"):
        read_job(tmp_path)


def test_similar_jobs_tolerates_odd_folders(ws):
    job, _ = from_text(LONG, company="Acme", title="Welder")
    assert similar_jobs(ws, job) == []
    ws.jobs_dir.rmdir()
    assert similar_jobs(ws, job) == []
    ws.jobs_dir.mkdir()
    (ws.jobs_dir / "stray.txt").write_text("x")
    (ws.jobs_dir / "broken").mkdir()
    (ws.jobs_dir / "broken" / "job.json").write_text("{")
    assert similar_jobs(ws, job) == []


def test_resolve_job_prefers_an_exact_name(ws):
    job, _ = from_text(LONG, company="Acme", title="Welder")
    a, _ = prepare(ws, job, today=TODAY)
    job2, _ = from_text(LONG, company="Acme", title="Welder 2")
    prepare(ws, job2, today=TODAY)
    assert resolve_job(ws, a.name) == a


def test_inventory_markdown_covers_every_kind(ws):
    add_atoms(ws, '[[project]]\nid = "wms"\ntitle = "WMS rollout"\ncontext = "northwind"\n'
                  'url = "https://example.com/gone"\nurl_status = "dead"\ntext = "Moved to a new WMS"\n'
                  '[[bullet]]\nid = "northwind.acc2"\nrole = "northwind"\n'
                  'text = "Accuracy rose to 99.6%"\nbasis = "records"\nreword_of = "northwind.accuracy"\n')
    md = render_markdown(load_inventory(ws))
    assert "### `wms`: WMS rollout (at Northwind Distribution)" in md
    assert "example.com/gone" not in md
    assert "rewords `northwind.accuracy`" in md
    for heading in ("## Roles", "## Projects", "## Summaries", "## Skills",
                    "## Credentials", "## Education"):
        assert heading in md


def test_inventory_markdown_when_empty(tmp_path):
    ws = init_workspace(tmp_path)
    assert "No confirmed facts yet" in render_markdown(load_inventory(ws))


def test_describe_shows_url(ws):
    inv = load_inventory(ws)
    assert "URL: https://example.com/shift-scheduler" in describe(inv.get("shift-scheduler"), None)


def test_education_details_render(ws, john_plan):
    add_atoms(ws, '[[education]]\nid = "edu.cert"\nschool = "Night School"\n'
                  'credential = "Certificate"\ndetails = "Courses: Logistics, Safety"\n')
    john_plan["education"] = ["edu.cert"]
    plan, errors, _ = resolve(john_plan, load_inventory(ws))
    assert not errors
    texts = [b.text() for b in resume_blocks(plan, load_profile(ws))]
    assert "Courses: Logistics, Safety" in texts


def test_cli_check_prints_warnings(ws, job_folder, monkeypatch, capsys):
    monkeypatch.chdir(ws.root)
    monkeypatch.delenv(ENV_VAR, raising=False)
    plan = json.loads((job_folder / "plan.json").read_text(encoding="utf-8"))
    plan["experience"].reverse()
    (job_folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert main(["check", "prairie"]) == 0
    assert "reverse-chronological" in capsys.readouterr().out


def test_cli_ctrl_c_exits_130(ws, monkeypatch, capsys):
    monkeypatch.chdir(ws.root)
    monkeypatch.delenv(ENV_VAR, raising=False)

    def boom(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr("jobforge.confirm.run_confirm", boom)
    assert main(["confirm"]) == 130


def test_inventory_markdown_lists_a_roles_aliases(ws):
    # Issue #9: the agent reads the inventory, so it sees every name in use.
    add_atoms(ws, '[[role]]\nid = "kt"\nemployer = "Kestrel Testing Laboratories"\n'
                  'aliases = ["KT", "Kestrel Labs"]\ntitle = "Engineer"\nstart = "2020"\n')
    assert "Also called: KT, Kestrel Labs" in render_markdown(load_inventory(ws))
