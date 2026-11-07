"""D-30 item 6: the ledger records dated events and never loses them."""
import datetime as dt
import tomllib

import pytest

from jobforge.errors import JobforgeError
from jobforge.extract import from_text
from jobforge.jobs import format_table, list_jobs
from jobforge.ledger import (GHOSTED, STAGES, append_event, current_status, parse_date,
                             RECORDABLE, record_event,
                             read_events, resolve_job)
from jobforge.prepare import prepare

from conftest import TODAY

pytestmark = pytest.mark.critical
LONG = "Posting text. " * 30
D = dt.date


def add_job(ws, company, title, day=TODAY):
    job, _ = from_text(LONG, company=company, title=title)
    return prepare(ws, job, today=day)[0]


def test_events_append_and_read_back_in_date_order(job_folder):
    append_event(job_folder, "applied", D(2026, 11, 21))
    append_event(job_folder, "screen", D(2026, 12, 2), note='recruiter call "30 min"')
    append_event(job_folder, "interview", D(2026, 12, 9))
    events = read_events(job_folder)
    assert [e.stage for e in events] == ["prepared", "applied", "screen", "interview"]
    assert events[2].note == 'recruiter call "30 min"'


def test_ledger_file_is_valid_toml_and_append_only(job_folder):
    path = job_folder / "ledger.toml"
    path.write_text(path.read_text(encoding="utf-8") + "# my own comment\n", encoding="utf-8")
    append_event(job_folder, "applied", D(2026, 11, 21))
    text = path.read_text(encoding="utf-8")
    assert "# my own comment" in text
    assert len(tomllib.loads(text)["event"]) == 2


def test_unknown_stage_rejected(job_folder):
    with pytest.raises(JobforgeError, match="Unknown stage 'ghosted'"):
        append_event(job_folder, GHOSTED)


def test_hand_edited_bad_ledger_reports_clearly(job_folder):
    (job_folder / "ledger.toml").write_text('[[event]]\ndate = "2026-11-20"\nstage = "applied"\n',
                                            encoding="utf-8")
    with pytest.raises(JobforgeError, match="needs a date written like"):
        read_events(job_folder)
    (job_folder / "ledger.toml").write_text('[[event]]\ndate = 2026-11-20\nstage = "hired"\n',
                                            encoding="utf-8")
    with pytest.raises(JobforgeError, match="unknown stage 'hired'"):
        read_events(job_folder)
    (job_folder / "ledger.toml").write_text("[[event]\n", encoding="utf-8")
    with pytest.raises(JobforgeError, match="not valid TOML"):
        read_events(job_folder)


# Red-team follow-up to F7 (#28): `applied --mark` on a ledger it cannot
# read says why and writes nothing, instead of a traceback or appending
# to a file that is already broken.
@pytest.mark.parametrize("content", [b"\xff\xfe", b"[[event\n"])
def test_append_refuses_a_ledger_it_cannot_read(job_folder, content):
    path = job_folder / "ledger.toml"
    path.write_bytes(content)
    with pytest.raises(JobforgeError, match=f"{job_folder.name}/ledger.toml is not"):
        append_event(job_folder, "applied", D(2026, 11, 21))
    assert path.read_bytes() == content


def test_applied_mark_on_a_non_utf8_ledger_exits_1(ws, job_folder, monkeypatch, capsys):
    from jobforge.cli import main
    (job_folder / "ledger.toml").write_bytes(b"\xff\xfe")
    monkeypatch.chdir(ws.root)
    assert main(["applied", "--mark", job_folder.name, "--status", "applied"]) == 1
    assert "ledger.toml is not UTF-8 text" in capsys.readouterr().err


def test_no_ledger_means_no_events(tmp_path):
    assert read_events(tmp_path) == []
    assert current_status([], TODAY, 30) == "unknown"


@pytest.mark.parametrize("days,status", [(29, "applied"), (30, GHOSTED), (90, GHOSTED)])
def test_ghosted_is_computed_after_threshold(job_folder, days, status):
    append_event(job_folder, "applied", TODAY)
    events = read_events(job_folder)
    assert current_status(events, TODAY + dt.timedelta(days=days), 30) == status


def test_a_reply_is_never_ghosted(job_folder):
    append_event(job_folder, "applied", TODAY)
    append_event(job_folder, "rejected", TODAY + dt.timedelta(days=5))
    events = read_events(job_folder)
    assert current_status(events, TODAY + dt.timedelta(days=200), 30) == "rejected"


def test_stage_list_matches_mvp():
    assert STAGES == ("prepared", "applied", "skipped", "screen", "interview", "offer",
                      "accepted", "declined", "rejected", "withdrawn")


def test_parse_date():
    assert parse_date("2026-11-20") == TODAY
    assert parse_date(None) is None
    with pytest.raises(JobforgeError, match="YYYY-MM-DD"):
        parse_date("11/20/2026")


def test_resolve_job_by_name_piece_path_and_ambiguity(ws):
    a = add_job(ws, "Acme", "Welder")
    add_job(ws, "Acme", "Painter")
    assert resolve_job(ws, "welder") == a
    assert resolve_job(ws, a.name) == a
    assert resolve_job(ws, str(a)) == a.resolve()
    with pytest.raises(JobforgeError, match="more than one job"):
        resolve_job(ws, "acme")
    with pytest.raises(JobforgeError, match="No job folder matches"):
        resolve_job(ws, "zzz")


def test_list_jobs_status_and_filters(ws):
    a = add_job(ws, "Acme", "Welder")
    b = add_job(ws, "Bolt Works", "Painter")
    append_event(a, "applied", TODAY)
    rows = list_jobs(ws, today=TODAY + dt.timedelta(days=40))
    status = {r.company: r.status for r in rows}
    assert status == {"Acme": GHOSTED, "Bolt Works": "prepared"}
    assert [r.company for r in list_jobs(ws, today=TODAY, status="applied")] == ["Acme"]
    assert [r.company for r in list_jobs(ws, today=TODAY, company="bolt")] == ["Bolt Works"]
    assert [r.company for r in list_jobs(ws, today=TODAY, text="painter")] == ["Bolt Works"]
    assert list_jobs(ws, today=TODAY, text="nothing-matches") == []
    assert b.name in format_table(list_jobs(ws, today=TODAY))


# Issue #34: `applied` refuses dates that cannot be right, like `import`.
def test_applied_in_the_future_is_refused(job_folder):
    with pytest.raises(JobforgeError, match="2099-01-01 is in the future"):
        record_event(job_folder, "applied", D(2099, 1, 1), today=TODAY)
    assert [e.stage for e in read_events(job_folder)] == ["prepared"]


def test_applied_before_prepared_is_recorded_with_a_warning(job_folder):
    # Real when someone applied, then made the folder afterwards.
    ev, warnings = record_event(job_folder, "applied", D(2020, 1, 1), today=TODAY)
    assert ("applied", D(2020, 1, 1)) in [(e.stage, e.date) for e in read_events(job_folder)]
    assert len(warnings) == 1 and "before this job was prepared (2026-11-20)" in warnings[0]


def test_applied_on_or_after_prepared_is_quiet(job_folder):
    _, warnings = record_event(job_folder, "applied", TODAY, today=TODAY)
    assert warnings == []


def test_imported_job_has_no_prepared_date_to_compare(ws):
    from jobforge.importer import import_csv
    import_csv(ws, "company,title,applied\nCedar Mill Foods,Clerk,2026-09-10\n",
               write=True, today=TODAY)
    folder = next(ws.jobs_dir.iterdir())
    _, warnings = record_event(folder, "rejected", D(2026, 9, 1), today=TODAY)
    assert warnings == []


# Issue #35: "prepared" is recorded by `prepare`, never by the user.
def test_applied_refuses_prepared(job_folder):
    with pytest.raises(JobforgeError, match="recorded by `jobforge prepare`"):
        record_event(job_folder, "prepared", TODAY, today=TODAY)
    assert [e.stage for e in read_events(job_folder)] == ["prepared"]


def test_recordable_stages_are_every_stage_but_prepared():
    assert RECORDABLE == tuple(s for s in STAGES if s != "prepared")


# Issue #39: FOLDER is the name users type back into `applied --mark`,
# `check`, and `apply`, so it is never shortened.
def row(folder, company="Lakeview Cold Storage", title="Distribution Supervisor"):
    from jobforge.jobs import JobRow
    return JobRow(folder=folder, company=company, title=title, status="applied",
                  last_date="2026-09-15", url="")


def test_table_shows_location_twins_in_full():
    twins = ["lakeview_cold_storage__distribution_supervisor__2026-09-15",
             "lakeview_cold_storage__distribution_supervisor__2026-09-15__2"]
    lines = format_table([row(f) for f in twins]).splitlines()[1:]
    assert [line.split()[-1] for line in lines] == twins


def test_table_marks_a_shortened_company_or_title():
    long_company = "The Very Long Regional Cold Storage and Logistics Cooperative"
    out = format_table([row("x__y__2026-09-15", company=long_company)])
    assert long_company not in out and "…" in out
    assert "The Very Long Regional Cold Storage" in out


def test_table_never_marks_what_fits():
    out = format_table([row("acme__welder__2026-09-15", company="Acme", title="Welder")])
    assert "…" not in out


def test_list_skips_broken_folders(ws):
    add_job(ws, "Acme", "Welder")
    bad = ws.jobs_dir / "broken"
    bad.mkdir()
    (bad / "job.json").write_text("{", encoding="utf-8")
    assert len(list_jobs(ws, today=TODAY)) == 1


# Red-team finding F7 (#28): one broken ledger.toml must not stop the
# listing. The job stays in it, marked unreadable, with the reason.
def test_list_keeps_a_job_whose_ledger_is_broken(ws):
    good = add_job(ws, "Acme", "Welder")
    bad = add_job(ws, "Bolt", "Painter")
    (bad / "ledger.toml").write_text("[[event\n", encoding="utf-8")
    rows = {r.company: r for r in list_jobs(ws, today=TODAY)}
    assert rows["Acme"].status == "prepared" and rows["Acme"].problem == ""
    assert rows["Bolt"].status == "unreadable" and rows["Bolt"].last_date == ""
    assert f"{bad.name}/ledger.toml is not valid TOML" in rows["Bolt"].problem
    assert good.name in format_table(list(rows.values()))


def test_list_keeps_a_job_whose_ledger_is_not_utf8(ws):
    bad = add_job(ws, "Bolt", "Painter")
    (bad / "ledger.toml").write_bytes(b'[[event]]\nnote = "\xff"\n')
    [only] = list_jobs(ws, today=TODAY)
    assert only.status == "unreadable"
    assert f"{bad.name}/ledger.toml is not UTF-8 text" in only.problem


def test_non_utf8_ledger_reports_clearly(job_folder):
    (job_folder / "ledger.toml").write_bytes(b"\xff\xfe")
    with pytest.raises(JobforgeError, match="ledger.toml is not UTF-8 text"):
        read_events(job_folder)


def test_empty_table_message(ws):
    assert "No jobs yet" in format_table([])


def test_listing_is_fast_at_hundreds_of_jobs(ws):
    # D-29: reads stay fast. The index arrives with 1.0; until then, prove a
    # scan of 300 jobs is quick.
    import time
    for i in range(300):
        folder = ws.jobs_dir / f"co{i}__t__2026-11-20"
        folder.mkdir()
        (folder / "job.json").write_text('{"company": "C", "title": "T"}', encoding="utf-8")
        append_event(folder, "applied", TODAY)
    start = time.perf_counter()
    rows = list_jobs(ws, today=TODAY)
    assert len(rows) == 300
    assert time.perf_counter() - start < 2.0


def test_no_jobs_folder_lists_nothing(tmp_path):
    # #49: a workspace whose jobs/ folder was deleted lists no jobs, no crash.
    from jobforge.ledger import job_folders
    from jobforge.workspace import init_workspace
    ws = init_workspace(tmp_path / "w")
    ws.jobs_dir.rmdir()
    assert job_folders(ws) == [] and list_jobs(ws, today=TODAY) == []


def test_append_to_a_hand_edited_ledger_ending_in_a_blank_line(job_folder):
    # #49: no extra blank lines pile up, and every event still reads back.
    path = job_folder / "ledger.toml"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n", encoding="utf-8")
    append_event(job_folder, "applied", TODAY)
    assert "\n\n\n" not in path.read_text(encoding="utf-8")
    assert [e.stage for e in read_events(job_folder)] == ["prepared", "applied"]
