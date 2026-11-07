"""Issue #30: files saved with a UTF-8 byte order mark are read like any
other. Windows PowerShell 5.1 (`Out-File`, `Set-Content -Encoding utf8`) and
older Notepad write one, so a Windows user's agent writing through
PowerShell produces them. Files Jobforge writes stay BOM-free."""
import datetime as _dt

import pytest

from jobforge.apply import run_check
from jobforge.atoms import load_inventory
from jobforge.cli import main
from jobforge.confirm import run_confirm
from jobforge.ledger import append_event, read_events
from jobforge.jobs import list_jobs
from jobforge.prepare import read_job
from jobforge.profile import load_profile

from conftest import JOHN, TODAY, add_atoms

pytestmark = pytest.mark.critical

BOM = b"\xef\xbb\xbf"


def add_bom(path):
    data = path.read_bytes()
    assert not data.startswith(BOM)
    path.write_bytes(BOM + data)


def test_plan_with_bom(ws, job_folder):
    add_bom(job_folder / "plan.json")
    result = run_check(ws, job_folder)
    assert result.ok, result.errors


def test_profile_with_bom(ws):
    add_bom(ws.profile_path)
    assert load_profile(ws).name == "John Smith"


def test_confirmed_atoms_with_bom(ws):
    for path in ws.atoms_dir.glob("*.toml"):
        add_bom(path)
    inv = load_inventory(ws)
    assert inv.warnings == [] and inv.get("northwind.team") is not None


def test_pending_atoms_with_bom_are_confirmed_without_one(ws):
    path = add_atoms(ws, '[[bullet]]\nid = "northwind.new"\nrole = "northwind"\n'
                         'text = "Did 3 audits"\nbasis = "records"\n'
                         'defense = "Audit sign-off sheets."\n', "d.toml", pending=True)
    add_bom(path)
    answers = iter(["k"])
    run_confirm(ws, ask=lambda prompt: next(answers), say=lambda *_: None)
    assert load_inventory(ws).get("northwind.new") is not None
    for kept in ws.atoms_dir.glob("*.toml"):
        assert BOM not in kept.read_bytes()[3:], kept  # never copied mid-file


def test_job_json_with_bom(ws, job_folder):
    add_bom(job_folder / "job.json")
    assert read_job(job_folder)["company"] == "Prairie Freight Co."
    assert [r.company for r in list_jobs(ws, today=TODAY)] == ["Prairie Freight Co."]


def test_ledger_with_bom_reads_and_appends(ws, job_folder):
    add_bom(job_folder / "ledger.toml")
    append_event(job_folder, "applied", TODAY, "")
    assert [e.stage for e in read_events(job_folder)] == ["prepared", "applied"]


def test_posting_file_with_bom(ws, tmp_path, monkeypatch):
    posting = tmp_path / "posting.txt"
    posting.write_bytes(BOM + (JOHN / "posting.txt").read_bytes())
    monkeypatch.chdir(ws.root)
    assert main(["prepare", "--from-text", str(posting), "--company", "Prairie Freight Co.",
                 "--title", "Operations Supervisor"]) == 0
    folder = next((ws.root / "jobs").iterdir())
    assert not read_job(folder)["description"].startswith("﻿")


def test_files_jobforge_writes_have_no_bom(ws, job_folder):
    append_event(job_folder, "applied", _dt.date(2026, 11, 1), "")
    for name in ("job.json", "ledger.toml"):
        assert not (job_folder / name).read_bytes().startswith(BOM), name
