"""The CLI end to end, the way a user (or their agent) runs it."""
import datetime as _dt
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
    today = _dt.date.today().isoformat()
    code, out, _ = run("applied", "--mark", "prairie", "--status", "applied", "--date", today)
    assert code == 0 and f"applied on {today}" in out
    code, out, _ = run("jobs")
    assert code == 0 and "Prairie Freight Co." in out
    code, out, _ = run("search", "--status", "prepared")
    assert "No jobs match" in out  # #86: was "No jobs yet", with a job listed above


# Issue #86 (audit A16): a status typo, or a filter that matches nothing, told
# a user with jobs that they had none.
def test_jobs_rejects_an_unknown_status_and_names_the_valid_ones(run, capsys):
    prepare_john(run)
    with pytest.raises(SystemExit) as exc:
        main(["jobs", "--status", "aplied"])
    err = capsys.readouterr().err
    assert exc.value.code == 2 and "invalid choice: 'aplied'" in err
    for status in ("applied", "ghosted", "unknown", "unreadable"):
        assert status in err


@pytest.mark.parametrize("args", [("--status", "offer"), ("--company", "Nowhere"),
                                  ("forklift-free text that matches nothing",)])
def test_jobs_says_no_jobs_match_when_a_filter_empties_the_list(run, args):
    prepare_john(run)
    code, out, _ = run("jobs", *args)
    assert code == 0 and "No jobs match" in out and "No jobs yet" not in out


def test_apply_with_a_locked_docx_exits_1_without_a_traceback(run, ws, monkeypatch):
    # Issue #32: Word holds the resume open on Windows.
    from jobforge import apply as apply_mod
    prepare_john(run)
    folder = next(ws.jobs_dir.iterdir())
    shutil.copy(JOHN / "plan.json", folder / "plan.json")
    assert run("apply", "prairie")[0] == 0

    def locked(src, dst):
        raise PermissionError(13, "Access is denied", str(dst))
    monkeypatch.setattr(apply_mod, "_move", locked)
    code, out, err = run("apply", "prairie")
    assert code == 1 and "Traceback" not in err
    assert "Close John_Smith_Resume.docx" in err and "Nothing was changed" in err


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


def test_applied_future_date_exits_1(run, ws):
    # Issue #34.
    prepare_john(run)
    code, _, err = run("applied", "--mark", "prairie", "--status", "applied", "--date", "2099-01-01")
    assert code == 1 and "2099-01-01 is in the future" in err


def test_applied_before_prepared_warns(run, ws):
    prepare_john(run)
    code, out, err = run("applied", "--mark", "prairie", "--status", "applied", "--date", "2020-01-01")
    assert code == 0 and "applied on 2020-01-01" in out
    assert "warning:" in err and "before this job was prepared" in err


def test_applied_rejects_unknown_stage(run):
    code, _, err = run("applied", "--mark", "x", "--status", "ghosted")
    assert code == 1 and "Unknown stage 'ghosted'" in err and "prepared" not in err


def test_applied_refuses_prepared(run, ws):
    # Issue #35.
    prepare_john(run)
    code, _, err = run("applied", "--mark", "prairie", "--status", "prepared")
    assert code == 1 and "recorded by `jobforge prepare`" in err


def test_applied_help_lists_no_prepared(capsys):
    with pytest.raises(SystemExit):
        main(["applied", "--help"])
    help_text = capsys.readouterr().out
    assert "applied, skipped, screen" in help_text and "prepared" not in help_text


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


# Red-team finding F7 (#28): a broken ledger is a warning naming the file,
# and every other job is still listed.
def test_jobs_warns_about_a_broken_ledger_and_lists_the_rest(run, ws):
    run("import", str(SAMPLE_CSV), "--write")
    folders = sorted(ws.jobs_dir.iterdir())
    (folders[0] / "ledger.toml").write_text("[[event\n", encoding="utf-8")
    code, out, err = run("jobs")
    assert code == 0
    assert f"warning: {folders[0].name}/ledger.toml is not valid TOML" in err
    assert all(f.name in out for f in folders)
    assert err.count("warning:") == 1


# #72: a broken job.json is a warning naming the file, the same as a broken
# ledger, and the job stays listed as unreadable.
def test_jobs_warns_about_a_broken_job_json_and_lists_the_rest(run, ws):
    run("import", str(SAMPLE_CSV), "--write")
    folders = sorted(ws.jobs_dir.iterdir())
    (folders[0] / "job.json").write_bytes(b'{"company": "Caf\xe9"}')
    code, out, err = run("jobs")
    assert code == 0
    assert f"warning: {folders[0].name}/job.json is not UTF-8 text" in err
    assert all(f.name in out for f in folders)
    assert err.count("warning:") == 1
    code, out, _ = run("jobs", "--status", "unreadable")
    assert code == 0 and folders[0].name in out and folders[1].name not in out


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


# Issue #52: on Windows, output to a pipe (how every agent runs jobforge) is
# encoded with the locale code page, so a non-Latin name crashed the print
# after the folder was already written. PYTHONIOENCODING=cp1252 reproduces
# that on Linux; the unset case is what proves the fix on Windows.
@pytest.mark.parametrize("forced", ["cp1252", None])
@pytest.mark.parametrize("company", ["Łódź Foods", "株式会社テスト"])
def test_piped_output_prints_non_latin_names(tmp_path, forced, company):
    import os
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8", ENV_VAR)}
    env["PYTHONPATH"] = str(REPO / "src")
    if forced:
        env["PYTHONIOENCODING"] = forced

    def jobforge(*args, cwd):
        return subprocess.run([sys.executable, "-m", "jobforge", *args], capture_output=True,
                              env=env, cwd=cwd)

    assert jobforge("init", str(tmp_path / "ws"), cwd=tmp_path).returncode == 0
    ws = tmp_path / "ws"
    done = jobforge("prepare", "--from-text", str(JOHN / "posting.txt"), "--company", company,
                    "--title", "Cook", cwd=ws)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert company in done.stdout.decode("utf-8")
    listed = jobforge("jobs", cwd=ws)
    assert listed.returncode == 0 and company in listed.stdout.decode("utf-8")


def test_utf8_output_falls_back_to_replacing():
    # A stream that cannot switch encoding still never raises on print.
    from jobforge.cli import _utf8_output

    class Stubborn:
        calls = []

        def reconfigure(self, **kw):
            self.calls.append(kw)
            if "encoding" in kw:
                raise ValueError("can't change encoding now")
    stream = Stubborn()
    _utf8_output(stream)
    assert stream.calls == [{"encoding": "utf-8"}, {"errors": "replace"}]


def test_utf8_output_leaves_plain_streams_alone():
    import io
    from jobforge.cli import _utf8_output
    _utf8_output(io.StringIO())  # no reconfigure method: nothing to do


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


# Issue #87 (audit A19): a posting file saved as Windows-1252 (older Notepad)
# was read with U+FFFD in place of every accent, curly quote, and dash.
POSTING_1252 = ("Café Rouge is hiring a “shift lead” – nights. " * 12)


def prepare_from(run, ws, path):
    code, out, err = run("prepare", "--from-text", str(path), "--company", "Café Rouge",
                         "--title", "Shift Lead")
    folder = next(ws.jobs_dir.iterdir(), None)
    desc = json.loads((folder / "job.json").read_text(encoding="utf-8"))["description"] \
        if folder else ""
    return code, err, desc


def test_prepare_reads_a_windows_1252_posting(run, ws, tmp_path):
    posting = tmp_path / "posting.txt"
    posting.write_bytes(POSTING_1252.encode("cp1252"))
    code, err, desc = prepare_from(run, ws, posting)
    assert code == 0, err
    assert "�" not in desc
    assert "Café Rouge" in desc and "“shift lead”" in desc and "–" in desc
    assert "not UTF-8; read it as Windows-1252" in err


def test_prepare_reads_a_utf8_posting_without_a_warning(run, ws, tmp_path):
    posting = tmp_path / "posting.txt"
    posting.write_bytes(POSTING_1252.encode("utf-8"))
    code, err, desc = prepare_from(run, ws, posting)
    assert code == 0 and "warning" not in err
    assert "Café Rouge" in desc and "�" not in desc


def test_prepare_refuses_a_posting_that_is_not_text(run, ws, tmp_path):
    posting = tmp_path / "posting.txt"
    posting.write_bytes(b"\x81\x8d\x8f" * 100)
    code, err, _ = prepare_from(run, ws, posting)
    assert code == 1 and "is not UTF-8 or Windows-1252 text" in err
    assert "--from-text -" in err  # pasting is the way out
    assert not any(ws.jobs_dir.iterdir())


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
