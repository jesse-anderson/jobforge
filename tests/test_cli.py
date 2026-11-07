"""The CLI end to end, the way a user (or their agent) runs it."""
import json
import shutil
import subprocess
import sys

import pytest

from jobforge import __version__
from jobforge.cli import main
from jobforge.workspace import ENV_VAR

from conftest import JOHN, REPO, add_atoms


@pytest.fixture
def run(ws, monkeypatch, capsys):
    monkeypatch.chdir(ws.root)
    monkeypatch.delenv(ENV_VAR, raising=False)

    def _run(*argv):
        code = main(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err
    return _run


def prepare_john(run):
    code, out, err = run("prepare", "--from-text", str(JOHN / "posting.txt"),
                         "--company", "Prairie Freight Co.", "--title", "Operations Supervisor")
    assert code == 0, err
    return out


def test_no_command_prints_help(run):
    code, out, _ = run()
    assert code == 0 and "usage: jobforge" in out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_init_and_refresh(tmp_path, capsys):
    assert main(["init", str(tmp_path / "w")]) == 0
    assert "Created a Jobforge workspace" in capsys.readouterr().out
    assert main(["init", "--refresh", str(tmp_path / "w")]) == 0
    assert main(["init", str(tmp_path / "w")]) == 2  # already a workspace
    assert "already a Jobforge workspace" in capsys.readouterr().err


def test_refresh_says_when_it_backs_up(tmp_path, capsys):
    # Issue #33: never drop the user's edits silently.
    main(["init", str(tmp_path / "w")])
    path = tmp_path / "w" / "CLAUDE.md"
    path.write_text(path.read_text(encoding="utf-8").replace("## The one rule",
                                                             "## The one rule\nMine."),
                    encoding="utf-8")
    capsys.readouterr()
    assert main(["init", "--refresh", str(tmp_path / "w")]) == 0
    assert "CLAUDE.md.bak" in capsys.readouterr().out


def test_outside_a_workspace_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert main(["jobs"]) == 2
    assert "No Jobforge workspace found" in capsys.readouterr().err


def test_full_flow(run, ws):
    out = prepare_john(run)
    assert "Prepared jobs/prairie_freight_co__operations_supervisor__" in out
    folder = next(ws.jobs_dir.iterdir())
    shutil.copy(JOHN / "plan.json", folder / "plan.json")

    code, out, _ = run("check", "prairie")
    assert code == 0 and "Check passed" in out
    code, out, _ = run("apply", "prairie")
    assert code == 0 and "John_Smith_Resume.docx" in out and "do not send" in out
    code, out, _ = run("applied", "--mark", "prairie", "--status", "applied", "--date", "2026-11-21")
    assert code == 0 and "applied on 2026-11-21" in out
    code, out, _ = run("jobs")
    assert code == 0 and "Prairie Freight Co." in out
    code, out, _ = run("search", "--status", "prepared")
    assert "No jobs yet" in out


def test_check_failure_exits_1_with_details(run, ws):
    prepare_john(run)
    folder = next(ws.jobs_dir.iterdir())
    plan = json.loads((JOHN / "plan.json").read_text(encoding="utf-8"))
    plan["cover_letter"]["body"] = "I saved $1M."
    (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    code, _, err = run("check", "prairie")
    assert code == 1 and "$1000000" in err
    code, _, err = run("apply", "prairie")
    assert code == 1 and "Check failed" in err


def test_inventory_prints_facts_and_warnings(run, ws):
    add_atoms(ws, '[[bullet]]\nid = "northwind.h"\nrole = "northwind"\n'
                  'text = "Saved roughly 10% on tape"\nbasis = "estimate"\n')
    code, out, err = run("inventory")
    assert code == 0 and "`northwind.accuracy`" in out and "Northwind Distribution" in out
    assert "hedges a figure" in err


def test_prepare_errors_reach_the_user(run, tmp_path, monkeypatch):
    code, _, err = run("prepare", "--from-text", str(tmp_path / "missing.txt"),
                       "--company", "A", "--title", "B")
    assert code == 1 and "does not exist" in err
    import urllib.error
    from jobforge import extract

    def offline(req, timeout):  # tests never touch the network
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(extract, "_open", offline)
    code, _, err = run("prepare", "--from-url", "https://example.com/x", "--company", "A")
    assert code == 1 and "--from-text" in err


def test_prepare_from_stdin(run, monkeypatch, ws):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("Posting text here. " * 20))
    code, out, err = run("prepare", "--from-text", "-", "--company", "Acme", "--title", "Welder")
    assert code == 0, err


def test_applied_rejects_unknown_stage(run):
    with pytest.raises(SystemExit):
        run("applied", "--mark", "x", "--status", "ghosted")


class FakeTerminal:
    """Stands in for an interactive stdin; answers come from a patched input()."""
    def isatty(self):
        return True


def test_confirm_via_cli(run, ws, monkeypatch):
    add_atoms(ws, '[[skill]]\nid = "skill.new"\nlabel = "L"\nitems = ["x"]\n', "d.toml", pending=True)
    monkeypatch.setattr("builtins.input", lambda prompt: "k")
    monkeypatch.setattr("sys.stdin", FakeTerminal())
    code, out, _ = run("confirm")
    assert code == 0 and "Kept 1" in out


def test_jobs_works_with_a_starter_profile(tmp_path, monkeypatch, capsys):
    main(["init", str(tmp_path / "w")])
    monkeypatch.chdir(tmp_path / "w")
    assert main(["jobs"]) == 0
    assert "No jobs yet" in capsys.readouterr().out


def test_python_dash_m_entry_point(tmp_path):
    import os
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    proc = subprocess.run([sys.executable, "-m", "jobforge", "--version"],
                          capture_output=True, text=True, env=env, cwd=tmp_path)
    assert proc.returncode == 0 and __version__ in proc.stdout


# --- import (issue #8) -------------------------------------------------------

SAMPLE_CSV = REPO / "fixtures" / "import" / "sample_tracker.csv"


def test_import_previews_by_default(run, ws):
    code, out, _ = run("import", str(SAMPLE_CSV))
    assert code == 0
    assert "NEW" in out and "6 new, 0 duplicate, 0 error" in out
    assert "run again with --write" in out
    assert not any(ws.jobs_dir.iterdir())


def test_import_write_then_jobs_lists_them(run):
    code, out, _ = run("import", str(SAMPLE_CSV), "--write")
    assert code == 0 and "Imported 6 job(s)" in out
    code, out, _ = run("jobs", "--status", "rejected")
    assert code == 0 and "Prairie Freight Co." in out
    code, out, _ = run("import", str(SAMPLE_CSV), "--write")
    assert code == 0 and "Imported 0 job(s)" in out and "0 new, 6 duplicate" in out


def test_import_with_bad_rows(run, ws, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("company,title,applied\nCedar Mill Foods,Clerk,9/1/2026\n", encoding="utf-8")
    code, out, _ = run("import", str(bad))
    assert code == 1 and "ERROR" in out and "Fix the rows marked ERROR" in out
    code, _, err = run("import", str(bad), "--write")
    assert code == 1 and "Nothing imported" in err
    assert not any(ws.jobs_dir.iterdir())


def test_import_reads_a_windows_1252_export(run, tmp_path):
    csv_file = tmp_path / "excel.csv"
    csv_file.write_bytes("company,title,applied\nCafé Rouge,Clerk,2026-09-10\n"
                         .encode("cp1252"))
    code, out, err = run("import", str(csv_file))
    assert code == 0 and "Café Rouge" in out
    assert "not UTF-8; read it as Windows-1252" in err


def test_import_reads_excel_utf8_bom(run, tmp_path):
    csv_file = tmp_path / "excel.csv"
    csv_file.write_bytes("company,title,applied\nCafé Rouge,Clerk,2026-09-10\n"
                         .encode("utf-8-sig"))
    code, out, err = run("import", str(csv_file))
    assert code == 0 and "Café Rouge" in out and err == ""


def test_import_refuses_undecodable_bytes(run, tmp_path):
    csv_file = tmp_path / "binary.csv"
    csv_file.write_bytes(b"company,title,applied\n\x81\x8d,Clerk,2026-09-10\n")
    code, _, err = run("import", str(csv_file))
    assert code == 1 and "CSV UTF-8" in err


def test_import_missing_file(run):
    code, _, err = run("import", "nope.csv")
    assert code == 1 and "does not exist" in err


def test_confirm_without_a_terminal_gives_a_message_not_a_traceback(run, ws, monkeypatch):
    """Issue #2 run: `! jobforge confirm` from inside an agent session."""
    import io
    add_atoms(ws, '[[skill]]\nid = "skill.x"\nlabel = "X"\nitems = ["Excel"]\n',
              "draft.toml", pending=True)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    code, out, err = run("confirm")
    assert code != 0
    assert "needs a terminal" in err and "Traceback" not in err
