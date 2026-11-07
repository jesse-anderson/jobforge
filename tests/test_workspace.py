import pytest

from jobforge.agent import AGENT_FILES, NOTES_MARKER
from jobforge.errors import WorkspaceError
from jobforge.workspace import (ENV_VAR, LAYOUT, MARKER, find_workspace, init_workspace,
                                refresh_workspace)

pytestmark = pytest.mark.critical


def test_init_creates_layout_marker_profile_and_agent_files(tmp_path):
    ws = init_workspace(tmp_path / "me")
    for sub in LAYOUT:
        assert (ws.root / sub).is_dir(), sub
    assert ws.marker.exists()
    assert ws.profile_path.exists()
    for name in AGENT_FILES:
        assert (ws.root / name).exists(), name


def test_init_into_existing_workspace_is_refused(tmp_path):
    init_workspace(tmp_path)
    with pytest.raises(WorkspaceError, match="already a Jobforge workspace"):
        init_workspace(tmp_path)


def test_init_on_a_file_is_refused(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(WorkspaceError, match="not a folder"):
        init_workspace(f)


def test_init_keeps_an_existing_profile(tmp_path):
    (tmp_path / "profile").mkdir()
    (tmp_path / "profile" / "profile.toml").write_text("# mine\n", encoding="utf-8")
    ws = init_workspace(tmp_path)
    assert ws.profile_path.read_text(encoding="utf-8") == "# mine\n"


def test_refresh_rewrites_agent_files_only(ws):
    profile_before = ws.profile_path.read_text(encoding="utf-8")
    atoms_before = sorted(p.name for p in ws.atoms_dir.iterdir())
    (ws.root / "CLAUDE.md").write_text("stale", encoding="utf-8")
    init_workspace(ws.root, refresh=True)
    assert "stale" not in (ws.root / "CLAUDE.md").read_text(encoding="utf-8")
    assert ws.profile_path.read_text(encoding="utf-8") == profile_before
    assert sorted(p.name for p in ws.atoms_dir.iterdir()) == atoms_before


# Issue #33: --refresh keeps what the user or their agent added.
NOTE = "Ask me before applying to staffing agencies.\n"


def claude_md(ws):
    return (ws.root / "CLAUDE.md").read_text(encoding="utf-8")


def set_limit(ws, words):
    text = ws.profile_path.read_text(encoding="utf-8")
    ws.profile_path.write_text(text.replace("cover_letter_max_words = 300",
                                            f"cover_letter_max_words = {words}"), encoding="utf-8")


def test_generated_files_end_with_a_notes_section(ws):
    for name in AGENT_FILES:
        assert NOTES_MARKER in (ws.root / name).read_text(encoding="utf-8")


def test_unedited_files_refresh_quietly(ws):
    _, notices = refresh_workspace(ws.root)
    assert notices == [] and not list(ws.root.glob("*.bak*"))


def test_notes_below_the_marker_survive_a_refresh(ws):
    path = ws.root / "CLAUDE.md"
    path.write_text(claude_md(ws) + NOTE, encoding="utf-8")
    set_limit(ws, 220)
    _, notices = refresh_workspace(ws.root)
    assert claude_md(ws).endswith(NOTE)
    assert "at most 220 words" in claude_md(ws)  # the generated part did refresh
    assert notices == [] and not list(ws.root.glob("*.bak*"))


def test_an_edit_above_the_marker_is_backed_up(ws):
    path = ws.root / "CLAUDE.md"
    edited = claude_md(ws).replace("## The one rule", "## The one rule\n\nMy own rule.") + NOTE
    path.write_text(edited, encoding="utf-8")
    _, notices = refresh_workspace(ws.root)
    assert (ws.root / "CLAUDE.md.bak").read_text(encoding="utf-8") == edited
    assert "My own rule." not in claude_md(ws) and claude_md(ws).endswith(NOTE)
    assert len(notices) == 1 and "CLAUDE.md.bak" in notices[0]


def test_an_older_file_with_an_added_line_is_backed_up(ws):
    # Workspaces made before #33 have no notes section.
    path = ws.root / "CLAUDE.md"
    legacy = claude_md(ws).split(NOTES_MARKER)[0].rsplit("\n<!--", 1)[0] + "\n" + NOTE
    path.write_text(legacy, encoding="utf-8")
    _, notices = refresh_workspace(ws.root)
    assert (ws.root / "CLAUDE.md.bak").read_text(encoding="utf-8") == legacy
    assert any("CLAUDE.md.bak" in n for n in notices)


def test_an_unedited_older_file_refreshes_quietly(ws):
    path = ws.root / "CLAUDE.md"
    path.write_text(claude_md(ws).split(NOTES_MARKER)[0].rsplit("\n<!--", 1)[0] + "\n",
                    encoding="utf-8")
    _, notices = refresh_workspace(ws.root)
    assert notices == [] and NOTES_MARKER in claude_md(ws)


def test_a_second_backup_never_replaces_the_first(ws):
    path = ws.root / "CLAUDE.md"
    for edit in ("First edit.", "Second edit."):
        path.write_text(claude_md(ws).replace("## The one rule", f"## The one rule\n{edit}"),
                        encoding="utf-8")
        refresh_workspace(ws.root)
    assert "First edit." in (ws.root / "CLAUDE.md.bak").read_text(encoding="utf-8")
    assert "Second edit." in (ws.root / "CLAUDE.md.bak2").read_text(encoding="utf-8")


def test_refresh_outside_a_workspace_fails(tmp_path):
    with pytest.raises(WorkspaceError, match="nothing to refresh"):
        init_workspace(tmp_path, refresh=True)


def test_find_walks_up_from_a_subfolder(ws):
    deep = ws.jobs_dir / "a" / "b"
    deep.mkdir(parents=True)
    assert find_workspace(deep, env={}).root == ws.root


def test_find_fails_loudly_outside_any_workspace(tmp_path):
    with pytest.raises(WorkspaceError, match="No Jobforge workspace found"):
        find_workspace(tmp_path, env={})


def test_find_never_falls_back_to_defaults(tmp_path):
    # FINDINGS F7: a missing profile was silently replaced by defaults.
    (tmp_path / "profile").mkdir()
    with pytest.raises(WorkspaceError):
        find_workspace(tmp_path, env={})


def test_explicit_and_env_override(ws, tmp_path):
    assert find_workspace(tmp_path, explicit=ws.root, env={}).root == ws.root
    assert find_workspace(tmp_path, env={ENV_VAR: str(ws.root)}).root == ws.root


def test_explicit_path_must_be_a_workspace(tmp_path):
    with pytest.raises(WorkspaceError, match=f"no {MARKER} file"):
        find_workspace(explicit=tmp_path, env={})


def test_rel_gives_forward_slash_paths(ws):
    assert ws.rel(ws.atoms_dir / "x.toml") == "profile/atoms/x.toml"
    assert ws.rel(ws.root.parent / "elsewhere") == str(ws.root.parent / "elsewhere")


def test_intake_dir_is_the_folder_init_makes(tmp_path):
    # #49: the README tells users to put their old resume here.
    ws = init_workspace(tmp_path / "w")
    assert ws.intake_dir == ws.root / "intake" and ws.intake_dir.is_dir()
