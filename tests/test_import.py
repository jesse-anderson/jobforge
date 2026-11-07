"""`jobforge import`: past applications into the ledger (issue #8).

An import records only what happened: a job.json marked as imported and
ledger events with the user's own dates. It never invents a date, a plan, or
a resume. Ledger is a critical path (D-30)."""
import datetime as _dt
import json

import pytest

from jobforge.errors import JobforgeError
from jobforge.extract import Job
from jobforge.importer import format_preview, import_csv, plan_import
from jobforge.ledger import job_folders, read_events
from jobforge.prepare import prepare, similar_jobs

from conftest import FIXTURES, REPO, TODAY

pytestmark = pytest.mark.critical

SAMPLE = (FIXTURES / "import" / "sample_tracker.csv").read_text(encoding="utf-8")
HEADER = "company,title,location,url,applied,status,status_date,notes\n"


def d(s):
    return _dt.date.fromisoformat(s)


def run(ws, text, write=True):
    return import_csv(ws, text, write=write, today=TODAY)


def one(ws, row, header=HEADER):
    plan = plan_import(ws, header + row + "\n", today=TODAY)
    assert len(plan.rows) == 1, plan.rows
    return plan.rows[0]


def events_by_company(ws):
    out = {}
    for f in job_folders(ws):
        job = json.loads((f / "job.json").read_text(encoding="utf-8"))
        out.setdefault(job["company"], []).append(
            [(e.stage, e.date.isoformat(), e.note) for e in read_events(f)])
    return out


# --- A clean import ---------------------------------------------------------

def test_sample_imports_every_row(ws):
    plan = run(ws, SAMPLE)
    assert [r.action for r in plan.rows] == ["new"] * 6
    assert len(job_folders(ws)) == 6


def test_events_carry_the_users_dates(ws):
    run(ws, SAMPLE)
    ev = events_by_company(ws)
    assert ev["Prairie Freight Co."] == [[("applied", "2026-09-02", ""),
                                          ("rejected", "2026-09-20", "Form rejection")]]
    assert ev["Riverbend Logistics"] == [[
        ("applied", "2026-09-05", ""),
        ("interview", "2026-09-18", "Second round with the site manager")]]
    assert ev["Cedar Mill Foods"] == [[("applied", "2026-09-10", "")]]


def test_no_prepared_event_since_jobforge_prepared_nothing(ws):
    run(ws, SAMPLE)
    for f in job_folders(ws):
        assert "prepared" not in [e.stage for e in read_events(f)]


def test_ghosted_imports_as_applied(ws):
    # Ghosted is computed from an old "applied" (D-47), never entered.
    run(ws, SAMPLE)
    assert events_by_company(ws)["Harbor Point Supply"] == [[("applied", "2026-09-12", "")]]


def test_skipped_is_one_event(ws):
    run(ws, SAMPLE)
    lakeview = sorted(events_by_company(ws)["Lakeview Cold Storage"])
    assert [("skipped", "2026-09-15", "Night shift only")] in lakeview


def test_job_json_is_marked_imported_with_no_description(ws):
    run(ws, SAMPLE)
    folder = next(f for f in job_folders(ws) if f.name.startswith("prairie_freight"))
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    assert job["source"] == "import" and job["description"] == ""
    assert job["imported"] == TODAY.isoformat()
    assert job["url"] == "https://example.com/jobs/prairie-ops"
    assert job["location"] == "Springfield, IL"
    assert not (folder / "plan.json").exists()


def test_folder_is_named_for_the_applied_date(ws):
    run(ws, SAMPLE)
    assert "prairie_freight_co__operations_supervisor__2026-09-02" in [
        f.name for f in job_folders(ws)]


def test_location_twins_are_two_jobs(ws):
    # Same company, title, and date in two cities: two folders, not a clash.
    run(ws, SAMPLE)
    names = sorted(f.name for f in job_folders(ws) if f.name.startswith("lakeview"))
    assert names == ["lakeview_cold_storage__distribution_supervisor__2026-09-15",
                     "lakeview_cold_storage__distribution_supervisor__2026-09-15__2"]


def test_preview_writes_nothing(ws):
    plan = run(ws, SAMPLE, write=False)
    assert [r.action for r in plan.rows] == ["new"] * 6
    assert job_folders(ws) == []


# --- Re-import and duplicates -----------------------------------------------

def test_reimport_skips_every_row(ws):
    run(ws, SAMPLE)
    plan = run(ws, SAMPLE)
    assert [r.action for r in plan.rows] == ["duplicate"] * 6
    assert len(job_folders(ws)) == 6


def test_duplicate_of_a_prepared_job_by_url(ws):
    job = Job("Prairie Freight Co.", "Operations Supervisor", "posting text",
              url="https://example.com/jobs/prairie-ops")
    folder, _ = prepare(ws, job, today=TODAY)
    row = one(ws, "Prairie Freight,Ops Supervisor,,https://example.com/jobs/prairie-ops,"
                  "2026-09-02,applied,,")
    assert row.action == "duplicate" and folder.name in row.message


def test_duplicate_by_company_title_and_location(ws):
    run(ws, HEADER + "Cedar Mill Foods,Shift Supervisor,\"Decatur, IL\",,2026-09-10,applied,,\n")
    row = one(ws, "cedar mill foods,Shift  Supervisor,\"Decatur, IL\",,2026-10-01,applied,,")
    assert row.action == "duplicate"


def test_duplicate_within_the_same_file(ws):
    text = HEADER + ("Cedar Mill Foods,Shift Supervisor,,,2026-09-10,applied,,\n" * 2)
    plan = run(ws, text, write=False)
    assert [r.action for r in plan.rows] == ["new", "duplicate"]
    assert "line 2" in plan.rows[1].message


def test_prepare_warns_about_an_imported_job(ws):
    run(ws, SAMPLE)
    job = Job("Riverbend Logistics", "Warehouse Manager", "posting text",
              url="https://example.com/jobs/riverbend-wm")
    assert any(h.startswith("riverbend_logistics") for h in similar_jobs(ws, job))


# --- Bad rows ---------------------------------------------------------------

@pytest.mark.parametrize("date,why", [
    ("9/2/2026", "YYYY-MM-DD"),
    ("~2026-09-02", "YYYY-MM-DD"),
    ("2026-13-02", "YYYY-MM-DD"),
    ("2026-12-01", "in the future"),
])
def test_bad_applied_date(ws, date, why):
    row = one(ws, f"Cedar Mill Foods,Shift Supervisor,,,{date},applied,,")
    assert row.action == "error" and why in row.message


def test_missing_applied_date_is_a_lead_not_an_application(ws):
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,,applied,,")
    assert row.action == "error" and "no applied date" in row.message


def test_unknown_status(ws):
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,2026-09-10,phone call,,")
    assert row.action == "error" and "'phone call'" in row.message
    assert "rejected" in row.message


def test_prepared_is_not_an_import_status(ws):
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,2026-09-10,prepared,,")
    assert row.action == "error"


def test_later_status_needs_its_own_date(ws):
    # Never guess when a rejection happened.
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,2026-09-10,rejected,,")
    assert row.action == "error" and "status_date" in row.message


def test_status_date_before_applied(ws):
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,2026-09-10,rejected,2026-09-01,")
    assert row.action == "error" and "before" in row.message


def test_bad_status_date(ws):
    row = one(ws, "Cedar Mill Foods,Shift Supervisor,,,2026-09-10,rejected,soon,")
    assert row.action == "error" and "status_date" in row.message


def test_missing_company_or_title(ws):
    assert one(ws, ",Shift Supervisor,,,2026-09-10,applied,,").action == "error"
    assert one(ws, "Cedar Mill Foods,,,,2026-09-10,applied,,").action == "error"


def test_any_error_writes_nothing(ws):
    text = SAMPLE + "Bad Row Co.,Clerk,,,not-a-date,applied,,\n"
    with pytest.raises(JobforgeError, match="1 row"):
        run(ws, text)
    assert job_folders(ws) == []


# --- File shape -------------------------------------------------------------

def test_header_aliases_bom_and_blank_lines(ws):
    text = ("﻿Employer,Job Title,Applied Date,Stage\n"
            "Cedar Mill Foods,Shift Supervisor,2026-09-10,applied\n"
            ",,,\n\n")
    plan = plan_import(ws, text, today=TODAY)
    assert [r.action for r in plan.rows] == ["new"]


def test_status_defaults_to_applied(ws):
    plan = plan_import(ws, "company,title,applied\nCedar Mill Foods,Clerk,2026-09-10\n",
                       today=TODAY)
    assert [e.stage for e in plan.rows[0].events] == ["applied"]


def test_unknown_columns_are_reported(ws):
    plan = plan_import(ws, "company,title,applied,comp\nCedar Mill Foods,Clerk,2026-09-10,$50k\n",
                       today=TODAY)
    assert plan.rows[0].action == "new"
    assert any("'comp'" in w for w in plan.warnings)


def test_blank_header_cells_are_ignored_quietly(ws):
    # Spreadsheets often save a trailing comma on every line.
    plan = plan_import(ws, "company,title,applied,\nCedar Mill Foods,Clerk,2026-09-10,\n",
                       today=TODAY)
    assert plan.rows[0].action == "new" and plan.warnings == []


def test_missing_required_column(ws):
    with pytest.raises(JobforgeError, match="applied"):
        plan_import(ws, "company,title\nCedar Mill Foods,Clerk\n", today=TODAY)


def test_empty_file(ws):
    with pytest.raises(JobforgeError, match="no header"):
        plan_import(ws, "", today=TODAY)


def test_preview_table(ws):
    text = SAMPLE + "Bad Row Co.,Clerk,,,not-a-date,applied,,\n"
    out = format_preview(plan_import(ws, text, today=TODAY))
    assert "NEW" in out and "ERROR" in out and "line 8" in out
    assert "applied 2026-09-02, rejected 2026-09-20" in out
    assert "6 new, 0 duplicate, 1 error" in out


def test_readme_example_imports_cleanly(ws):
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Bring in past applications", 1)[1]
    example = section.split("```", 2)[1].lstrip("\n")
    plan = plan_import(ws, example, today=TODAY)
    assert plan.rows and [r.action for r in plan.rows] == ["new"] * len(plan.rows)
    assert plan.warnings == []


# --- #78: an interrupted --write, then the same import again ---------------
# A Ctrl+C partway through left a folder without job.json (the rerun crashed),
# a row without all its events (the rerun called it a duplicate and skipped
# it), or an empty job.json (the rerun refused). The rerun now finishes.

def interrupt_at(monkeypatch, n):
    """Ctrl+C at the nth write step: making a folder, writing a job.json
    (left empty, as a cut write leaves it), or appending one event."""
    from pathlib import Path
    import jobforge.importer as importer
    steps = {"n": 0}

    def step():
        steps["n"] += 1
        return steps["n"] == n

    real_mkdir, real_write, real_append = Path.mkdir, Path.write_text, importer.append_event

    def mkdir(self, *a, **k):
        real_mkdir(self, *a, **k)
        if self.parent.name == "jobs" and step():
            raise KeyboardInterrupt

    def write_text(self, data, *a, **k):
        if self.name == "job.json" and step():
            real_write(self, "", *a, **k)
            raise KeyboardInterrupt
        return real_write(self, data, *a, **k)

    def append(folder, *a, **k):
        if step():
            raise KeyboardInterrupt
        return real_append(folder, *a, **k)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(importer, "append_event", append)
    return steps


def test_rerun_after_ctrl_c_at_any_step_finishes_the_import(ws, tmp_path, monkeypatch):
    from conftest import make_workspace
    clean = make_workspace(tmp_path / "clean")
    run(clean, SAMPLE)
    want = events_by_company(clean)
    n = 1
    while True:
        work = make_workspace(tmp_path / f"w{n}")
        with monkeypatch.context() as m:
            steps = interrupt_at(m, n)
            try:
                run(work, SAMPLE)
                interrupted = False
            except KeyboardInterrupt:
                interrupted = True
        if not interrupted:
            break
        plan = run(work, SAMPLE)  # the same import again
        assert events_by_company(work) == want, (n, format_preview(plan))
        assert all((f / "job.json").exists() for f in work.jobs_dir.iterdir()), n
        n += 1
    assert n > 20  # every folder, job.json, and event of the sample was a step


def test_rerun_finishes_a_row_whose_events_were_cut_short(ws):
    run(ws, SAMPLE)
    folder = next(f for f in job_folders(ws) if f.name.startswith("prairie_freight"))
    ledger = folder / "ledger.toml"
    full = ledger.read_text(encoding="utf-8")
    ledger.write_text(full.split("[[event]]", 2)[0] + "[[event]]" + full.split("[[event]]", 2)[1],
                      encoding="utf-8")  # only the first event kept
    assert [e.stage for e in read_events(folder)] == ["applied"]
    plan = plan_import(ws, SAMPLE, today=TODAY)
    row = next(r for r in plan.rows if r.company == "Prairie Freight Co.")
    assert row.action == "finish" and row.folder == folder.name
    assert "FINISH" in format_preview(plan) and "1 to finish" in format_preview(plan)
    run(ws, SAMPLE)
    assert [e.stage for e in read_events(folder)] == ["applied", "rejected"]


def test_rerun_leaves_a_job_the_user_has_updated_since(ws):
    # Events the user added after the import mean it is not an unfinished
    # import: still a duplicate, never touched.
    from jobforge.ledger import append_event
    run(ws, SAMPLE)
    folder = next(f for f in job_folders(ws) if f.name.startswith("riverbend"))
    append_event(folder, "offer", TODAY)
    before = (folder / "ledger.toml").read_bytes()
    plan = run(ws, SAMPLE)
    assert {r.action for r in plan.rows} == {"duplicate"}
    assert (folder / "ledger.toml").read_bytes() == before


def test_rerun_reuses_an_empty_folder_but_never_a_users_folder(ws):
    first = plan_import(ws, SAMPLE, today=TODAY).rows[0].folder
    second = plan_import(ws, SAMPLE, today=TODAY).rows[1].folder
    (ws.jobs_dir / first).mkdir(parents=True)            # left empty by a cut import
    (ws.jobs_dir / second).mkdir(parents=True)
    (ws.jobs_dir / second / "my_notes.txt").write_text("mine", encoding="utf-8")
    plan = run(ws, SAMPLE)
    assert plan.rows[0].folder == first and (ws.jobs_dir / first / "job.json").exists()
    assert plan.rows[1].folder == f"{second}__2"
    assert sorted(p.name for p in (ws.jobs_dir / second).iterdir()) == ["my_notes.txt"]


def test_an_unreadable_job_json_is_a_warning_not_a_refusal(ws):
    # Broken but not empty: someone's data, so it is reported, never reused.
    bad = ws.jobs_dir / "acme__welder__2026-09-01"
    bad.mkdir(parents=True)
    (bad / "job.json").write_text('{"company": "Acme"', encoding="utf-8")
    plan = run(ws, SAMPLE)
    assert plan.count("new") == 6
    assert any("acme__welder__2026-09-01/job.json" in w and "not checked" in w
               for w in plan.warnings)
    assert (bad / "job.json").read_text(encoding="utf-8") == '{"company": "Acme"'


def test_rerun_reuses_a_folder_holding_only_an_empty_job_json(ws):
    first = plan_import(ws, SAMPLE, today=TODAY).rows[0].folder
    (ws.jobs_dir / first).mkdir(parents=True)
    (ws.jobs_dir / first / "job.json").write_text("", encoding="utf-8")  # cut mid-write
    plan = run(ws, SAMPLE)
    assert plan.rows[0].folder == first and plan.warnings == []
    assert json.loads((ws.jobs_dir / first / "job.json").read_text(encoding="utf-8"))


def test_rerun_leaves_a_job_whose_ledger_it_cannot_read(ws):
    run(ws, SAMPLE)
    folder = next(f for f in job_folders(ws) if f.name.startswith("prairie_freight"))
    (folder / "ledger.toml").write_text("[[event\n", encoding="utf-8")
    plan = run(ws, SAMPLE)
    row = next(r for r in plan.rows if r.company == "Prairie Freight Co.")
    assert row.action == "duplicate"
    assert (folder / "ledger.toml").read_text(encoding="utf-8") == "[[event\n"
