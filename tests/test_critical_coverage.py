"""Issue #49: the critical-path files are held to 100% coverage, by one
list in pyproject.toml and one command that runs the same in CI and before
every push, on any OS."""
import importlib.util

from conftest import REPO

_spec = importlib.util.spec_from_file_location("critical_coverage",
                                               REPO / "tools" / "critical_coverage.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

COMMAND = "python tools/critical_coverage.py"


def test_every_listed_file_exists():
    # A renamed file would drop out of the check silently.
    files = gate.critical_files()
    assert files and all((REPO / f).is_file() for f in files), files


def test_list_covers_the_core_of_d30():
    files = set(gate.critical_files())
    for name in ("workspace.py", "profile.py", "agent/__init__.py", "extract.py",
                 "prepare.py", "plan.py", "render.py", "docx.py", "scan.py",
                 "factcheck.py", "facts.py", "apply.py", "ledger.py"):
        assert f"src/jobforge/{name}" in files, name


def test_command_holds_every_listed_file_to_100():
    cmd = gate.command(["src/jobforge/a.py", "src/jobforge/b.py"])
    assert cmd[1:4] == ["-m", "coverage", "report"]
    assert "--fail-under=100" in cmd
    assert "--include=src/jobforge/a.py,src/jobforge/b.py" in cmd


def test_main_runs_the_command_from_the_repo_root(monkeypatch):
    seen = {}

    def call(cmd, cwd):
        seen.update(cmd=cmd, cwd=cwd)
        return 2
    monkeypatch.setattr(gate.subprocess, "call", call)
    assert gate.main() == 2  # the coverage exit code is passed through
    assert seen["cwd"] == REPO and seen["cmd"] == gate.command(gate.critical_files())


def test_ci_runs_it_after_the_overall_check():
    ci = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert ci.index("--fail-under=95") < ci.index(COMMAND)


def test_the_pre_push_rule_names_it_everywhere_it_is_stated():
    for doc in ("CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md",
                ".github/pull_request_template.md", "docs/MAINTAINING.md"):
        assert COMMAND in (REPO / doc).read_text(encoding="utf-8"), doc
