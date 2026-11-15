"""The workspace format (#142, D-53): the version in `.jobforge`, the check
every command makes, and the documented format in docs/FORMAT.md."""
from __future__ import annotations

import dataclasses
import re
import shutil
import tomllib

import pytest

from jobforge import __version__
from jobforge.atoms import SCHEMA
from jobforge.cli import main
from jobforge.errors import WorkspaceError
from jobforge.extract import Job
from jobforge.ledger import STAGES
from jobforge.plan import PLAN_VERSION, TOP_KEYS
from jobforge.profile import _SECTIONS
from jobforge.workspace import (FORMAT, MARKER, find_workspace, init_workspace,
                                refresh_workspace, workspace_format)

from conftest import FIXTURES, REPO

pytestmark = pytest.mark.critical

FORMAT1 = FIXTURES / "workspaces" / "format1"
JOB = "prairie_freight_co__operations_supervisor__2026-11-20"
MARKER_010 = ('# Marks this folder as a Jobforge workspace. Do not delete.\n'
              'created = 2026-11-08\ncreated_by = "0.1.0"\n')


def _marker(ws) -> dict:
    return tomllib.loads(ws.marker.read_text(encoding="utf-8"))


def _set_marker(ws, text: str) -> None:
    ws.marker.write_text(text, encoding="utf-8")


# --- The version in the marker ---------------------------------------------

def test_init_writes_the_format(tmp_path):
    ws = init_workspace(tmp_path / "me")
    data = _marker(ws)
    assert data["format"] == FORMAT == 1
    assert data["created_by"] == __version__ and "created" in data


def test_a_marker_with_no_format_line_is_format_1(ws):
    # 0.1.0 and 0.1.1 wrote no format line, and their files are format 1.
    _set_marker(ws, MARKER_010)
    assert workspace_format(ws) == 1
    assert find_workspace(explicit=ws.root) == ws


def test_an_empty_marker_is_format_1(ws):
    _set_marker(ws, "")
    assert workspace_format(ws) == 1


def test_a_newer_workspace_asks_for_a_newer_jobforge(ws):
    _set_marker(ws, MARKER_010 + "format = 2\n")
    for find in (lambda: find_workspace(explicit=ws.root),
                 lambda: find_workspace(start=ws.jobs_dir, env={})):
        with pytest.raises(WorkspaceError) as err:
            find()
        msg = str(err.value)
        assert "needs a newer Jobforge" in msg and "format 2" in msg
        assert f"Jobforge {__version__} reads format 1" in msg
        assert "pipx upgrade jobforge" in msg and "pip install -U jobforge" in msg


def test_refresh_refuses_a_newer_workspace(ws):
    # An older Jobforge rewriting a newer workspace's agent files would hand
    # the agent instructions for the wrong format.
    _set_marker(ws, "format = 2\n")
    before = (ws.root / "CLAUDE.md").read_text(encoding="utf-8")
    with pytest.raises(WorkspaceError, match="needs a newer Jobforge"):
        refresh_workspace(ws.root)
    assert (ws.root / "CLAUDE.md").read_text(encoding="utf-8") == before
    assert _marker(ws)["format"] == 2


@pytest.mark.parametrize("line", ['format = "1"', "format = 0", "format = -1",
                                  "format = true", "format = 1.5"])
def test_a_format_that_is_not_a_version_is_refused(ws, line):
    _set_marker(ws, MARKER_010 + line + "\n")
    with pytest.raises(WorkspaceError, match=r"format should be a whole number like 1"):
        find_workspace(explicit=ws.root)


def test_a_marker_that_is_not_toml_is_refused(ws):
    _set_marker(ws, "format = \n")
    with pytest.raises(WorkspaceError, match=rf"{MARKER} in .* is not valid TOML"):
        find_workspace(explicit=ws.root)


def test_a_marker_that_is_not_utf8_is_refused(ws):
    ws.marker.write_bytes("created_by = \"caf\xe9\"\n".encode("latin-1"))
    with pytest.raises(WorkspaceError, match="is not UTF-8 text"):
        find_workspace(explicit=ws.root)


def test_refresh_writes_the_format_line_once(ws):
    _set_marker(ws, MARKER_010)
    _, notices = refresh_workspace(ws.root)
    assert any(f"format = {FORMAT}" in n for n in notices)
    data = _marker(ws)
    assert data["format"] == FORMAT
    assert data["created_by"] == "0.1.0"  # what made it is kept
    _, notices = refresh_workspace(ws.root)
    assert not any("format" in n for n in notices)
    assert ws.marker.read_text(encoding="utf-8").count("format =") == 1


def test_refresh_adds_the_line_to_a_marker_with_no_newline_at_the_end(ws):
    _set_marker(ws, 'created_by = "0.1.0"')
    refresh_workspace(ws.root)
    assert _marker(ws) == {"created_by": "0.1.0", "format": FORMAT}


def test_cli_says_to_update_jobforge(ws, capsys):
    _set_marker(ws, "format = 2\n")
    assert main(["--workspace", str(ws.root), "jobs"]) == 2
    assert "needs a newer Jobforge" in capsys.readouterr().err


def test_cli_refresh_says_it_recorded_the_format(ws, capsys):
    _set_marker(ws, MARKER_010)
    assert main(["init", "--refresh", str(ws.root)]) == 0
    assert f"format = {FORMAT}" in capsys.readouterr().out


# --- A format-1 workspace keeps working ------------------------------------
# fixtures/workspaces/format1 is a workspace as 0.1.0 wrote it. Every later
# Jobforge must read it and use it, from inventory through apply (D-53).

@pytest.fixture
def old_ws(tmp_path):
    root = tmp_path / "old"
    shutil.copytree(FORMAT1, root)
    return root


def test_format_1_workspace_still_works(old_ws, capsys):
    ws = ["--workspace", str(old_ws)]
    assert main([*ws, "inventory"]) == 0
    assert main([*ws, "jobs"]) == 0
    assert "applied" in capsys.readouterr().out
    assert main([*ws, "check", JOB]) == 0, capsys.readouterr()
    assert main([*ws, "apply", JOB]) == 0, capsys.readouterr()
    assert list((old_ws / "jobs" / JOB).glob("*.docx"))


def test_format_1_workspace_refreshes_to_the_current_format(old_ws):
    assert "format" not in tomllib.loads((old_ws / MARKER).read_text(encoding="utf-8"))
    ws, _ = refresh_workspace(old_ws)
    assert workspace_format(ws) == FORMAT
    assert main(["--workspace", str(old_ws), "check", JOB]) == 0


def test_the_fixture_is_still_the_0_1_0_shape():
    # Regenerating the fixture with a newer Jobforge would hide a break.
    marker = tomllib.loads((FORMAT1 / MARKER).read_text(encoding="utf-8"))
    assert marker == {"created": marker["created"], "created_by": "0.1.0"}
    assert not (FORMAT1 / "CLAUDE.md").exists()


# --- docs/FORMAT.md lists every field the code reads -----------------------

DOC = (REPO / "docs" / "FORMAT.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", DOC, re.M | re.S)
    assert m, heading
    return m.group(1)


def _named(name: str, text: str) -> bool:
    return f"`{name}`" in text


def test_format_doc_states_the_current_format():
    assert f"format = {FORMAT}" in _section("The marker: `.jobforge`")
    assert f'"version": {PLAN_VERSION}' in _section("`jobs/<folder>/plan.json`")


def test_format_doc_lists_every_profile_key():
    text = _section("`profile/profile.toml`")
    for section, keys in _SECTIONS.items():
        assert _named(f"[{section}]", text), section
        for key in keys:
            assert _named(key, text), f"[{section}] {key}"


def test_format_doc_lists_every_atom_field():
    text = _section("Atoms: `profile/atoms/*.toml` and `profile/pending/*.toml`")
    for kind, (required, optional) in SCHEMA.items():
        assert _named(f"[[{kind}]]", text), kind
        for name in required | optional:
            assert _named(name, text), f"{kind}.{name}"


def test_format_doc_lists_every_job_field():
    text = _section("`jobs/<folder>/job.json`")
    for f in dataclasses.fields(Job):
        assert _named(f.name, text), f.name
    assert _named("imported", text)


def test_format_doc_lists_every_plan_key():
    text = _section("`jobs/<folder>/plan.json`")
    for key in TOP_KEYS:
        assert _named(key, text), key


def test_format_doc_lists_every_ledger_field_and_stage():
    text = _section("`jobs/<folder>/ledger.toml`")
    for name in ("[[event]]", "date", "stage", "note", *STAGES):
        assert _named(name, text), name


def test_format_doc_names_what_is_internal():
    text = _section("Internal files")
    for name in ("check.json", "cover_letter.md", "CLAUDE.md", "AGENTS.md", ".editing"):
        assert name in text, name


def test_decisions_record_the_format_rule():
    decisions = (REPO / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "| D-53 | Workspace format |" in decisions
    assert "**D-53." in decisions and "docs/FORMAT.md" in decisions
