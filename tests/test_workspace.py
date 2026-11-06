import pytest

from jobforge.agent import AGENT_FILES
from jobforge.errors import WorkspaceError
from jobforge.workspace import ENV_VAR, LAYOUT, MARKER, find_workspace, init_workspace

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
