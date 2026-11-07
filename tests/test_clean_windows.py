"""#56: the clean-machine checklist runs unattended on a fresh Windows runner.
The script must keep up with docs/VM_CHECKLIST.md, stay readable by Windows
PowerShell 5.1, and the workflow must stay cheap while the repo is private."""
import re

from conftest import REPO

SCRIPT = (REPO / "tools" / "clean_windows.ps1").read_text(encoding="utf-8")
WORKFLOW = (REPO / ".github" / "workflows" / "clean-windows.yml").read_text(encoding="utf-8")
CHECKLIST = (REPO / "docs" / "VM_CHECKLIST.md").read_text(encoding="utf-8")


def test_script_covers_every_checklist_step():
    steps = CHECKLIST.split("## Steps", 1)[1].split("\n## ", 1)[0]
    numbered = set(re.findall(r"^(\d+)\. ", steps, re.MULTILINE))
    covered = set(re.findall(r'^(?:Step|Skip) "(\d+)"', SCRIPT, re.MULTILINE))
    assert numbered and numbered == covered, (numbered - covered, covered - numbered)


def test_only_the_steps_that_need_a_person_are_skipped():
    assert re.findall(r'^Skip "(\w+)"', SCRIPT, re.MULTILINE) == ["13"]


def test_script_is_ascii_for_windows_powershell():
    # PowerShell 5.1 reads a script without a BOM in the ANSI code page, so a
    # non-ASCII literal would be garbled before jobforge ever saw it.
    assert SCRIPT.isascii()


def test_workflow_runs_by_hand_or_when_the_script_changes():
    on = WORKFLOW.split("\non:", 1)[1].split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in on
    assert "tools/clean_windows.ps1" in on and "push:" not in on and "schedule" not in on


def test_workflow_runs_both_install_paths_on_windows_and_keeps_the_transcript():
    assert "runs-on: windows-latest" in WORKFLOW
    assert "install: [checkout, pypi, wheel]" in WORKFLOW
    # The wheel path is what release.yml gates on; built here the same way.
    build = WORKFLOW.split("- name: Build the wheel", 1)[1].split("- name:", 1)[0]
    assert "if: matrix.install == 'wheel'" in build and "python -m build --wheel" in build
    upload = WORKFLOW.split("actions/upload-artifact", 1)
    assert "if: always()" in upload[0].rsplit("- name:", 1)[1]
    assert "clean-windows-out/" in upload[1]
    assert "git commit" not in WORKFLOW and "git push" not in WORKFLOW
