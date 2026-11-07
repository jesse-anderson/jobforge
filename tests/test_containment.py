"""Red-team findings F2 and F3 (#28): Jobforge reads and writes only inside
the workspace. A <job> path outside it, or a symlink that leads out, is
refused before anything is read or written."""
import os
import shutil

import pytest

from jobforge.apply import apply, run_check
from jobforge.atoms import load_inventory
from jobforge.confirm import CONFIRMED_FILE, run_confirm
from jobforge.errors import JobforgeError
from jobforge.ledger import append_event, job_folders, resolve_job
from jobforge.profile import load_profile

from conftest import JOHN, TODAY, add_atoms

pytestmark = pytest.mark.critical


def link(target, at):
    try:
        os.symlink(target, at)
    except (OSError, NotImplementedError):  # Windows without the privilege
        pytest.skip("cannot create symlinks here")


@pytest.fixture
def outside(tmp_path):
    """A folder next to the workspace, holding a job of its own."""
    folder = tmp_path / "outside"
    folder.mkdir()
    return folder


def copy_job(job_folder, to):
    shutil.copy(job_folder / "job.json", to / "job.json")
    shutil.copy(JOHN / "plan.json", to / "plan.json")


# --- F2: a <job> path outside the workspace ------------------------------

def test_job_path_outside_the_workspace_is_refused(ws, job_folder, outside):
    copy_job(job_folder, outside)
    with pytest.raises(JobforgeError, match="outside this workspace"):
        resolve_job(ws, str(outside))
    assert sorted(p.name for p in outside.iterdir()) == ["job.json", "plan.json"]


def test_job_path_inside_the_workspace_still_works(ws, job_folder):
    assert resolve_job(ws, str(job_folder)) == job_folder.resolve()


# --- F3: symlinks that lead out ------------------------------------------

def test_ledger_linked_outside_is_refused(ws, job_folder, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("victim line\n", encoding="utf-8")
    (job_folder / "ledger.toml").unlink()
    link(victim, job_folder / "ledger.toml")
    with pytest.raises(JobforgeError, match="ledger.toml links outside this workspace"):
        resolve_job(ws, job_folder.name)
    assert victim.read_text(encoding="utf-8") == "victim line\n"


def test_check_json_linked_outside_is_refused(ws, job_folder, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("{}", encoding="utf-8")
    link(victim, job_folder / "check.json")
    with pytest.raises(JobforgeError, match="check.json links outside"):
        resolve_job(ws, job_folder.name)
    assert victim.read_text(encoding="utf-8") == "{}"


def test_job_folder_linked_outside_is_not_listed_or_resolved(ws, job_folder, outside):
    copy_job(job_folder, outside)
    link(outside, ws.jobs_dir / "linked__clerk__2026-11-07")
    assert [f.name for f in job_folders(ws)] == [job_folder.name]
    with pytest.raises(JobforgeError):
        resolve_job(ws, "linked__clerk")
    with pytest.raises(JobforgeError, match="outside this workspace"):
        resolve_job(ws, str(ws.jobs_dir / "linked__clerk__2026-11-07"))
    assert sorted(p.name for p in outside.iterdir()) == ["job.json", "plan.json"]


def test_atoms_file_linked_outside_is_refused_without_reading_it(ws, tmp_path):
    secret = tmp_path / "secret.toml"
    secret.write_text('[[private_section]]\nid = "x"\n', encoding="utf-8")
    link(secret, ws.atoms_dir / "z_link.toml")
    with pytest.raises(JobforgeError) as exc:
        load_inventory(ws)
    shown = exc.value.render()
    assert "z_link.toml links outside this workspace" in shown
    assert "private_section" not in shown


def test_atoms_file_linked_inside_the_workspace_is_fine(ws):
    extra = ws.root / "extra"
    extra.mkdir()
    (extra / "more.toml").write_text('[[skill]]\nid = "skill.more"\nlabel = "More"\n'
                                     'items = ["Excel"]\n', encoding="utf-8")
    link(extra / "more.toml", ws.atoms_dir / "more.toml")
    assert load_inventory(ws).get("skill.more") is not None


def test_profile_linked_outside_is_refused(ws, tmp_path):
    outside_profile = tmp_path / "profile.toml"
    shutil.copy(ws.profile_path, outside_profile)
    ws.profile_path.unlink()
    link(outside_profile, ws.profile_path)
    with pytest.raises(JobforgeError, match="profile.toml links outside this workspace"):
        load_profile(ws)


def test_confirm_will_not_append_to_a_file_linked_outside(ws, tmp_path):
    victim = tmp_path / "victim.toml"
    victim.write_text("# victim\n", encoding="utf-8")
    link(victim, ws.atoms_dir / CONFIRMED_FILE)
    add_atoms(ws, '[[skill]]\nid = "skill.extra"\nlabel = "Extra"\nitems = ["Excel"]\n',
              "d.toml", pending=True)
    with pytest.raises(JobforgeError) as exc:
        run_confirm(ws, ask=lambda prompt: "k", say=lambda *_: None)
    assert "links outside this workspace" in exc.value.render()
    assert victim.read_text(encoding="utf-8") == "# victim\n"


def test_confirm_will_not_create_a_file_through_a_dangling_link(ws, tmp_path):
    # The loader skips a link to nothing; confirm would have created it.
    target = tmp_path / "new_victim.toml"
    link(target, ws.atoms_dir / CONFIRMED_FILE)
    add_atoms(ws, '[[skill]]\nid = "skill.extra"\nlabel = "Extra"\nitems = ["Excel"]\n',
              "d.toml", pending=True)
    with pytest.raises(JobforgeError, match="links outside this workspace"):
        run_confirm(ws, ask=lambda prompt: "k", say=lambda *_: None)
    assert not target.exists()


def test_pending_file_linked_outside_is_refused_and_not_read(ws, tmp_path):
    from jobforge.atoms import pending_ids
    secret = tmp_path / "secret.toml"
    secret.write_text('[[skill]]\nid = "skill.secret"\nlabel = "S"\nitems = ["x"]\n',
                      encoding="utf-8")
    link(secret, ws.pending_dir / "z_link.toml")
    assert "skill.secret" not in pending_ids(ws)
    with pytest.raises(JobforgeError) as exc:
        run_confirm(ws, ask=lambda prompt: "k", say=lambda *_: None)
    assert "z_link.toml links outside this workspace" in exc.value.render()


def test_apply_and_applied_never_write_outside(ws, job_folder, outside):
    # End to end through the public functions, as the CLI calls them.
    copy_job(job_folder, outside)
    with pytest.raises(JobforgeError):
        apply(ws, resolve_job(ws, str(outside)), today=TODAY)
    with pytest.raises(JobforgeError):
        append_event(resolve_job(ws, str(outside)), "applied", TODAY)
    with pytest.raises(JobforgeError):
        run_check(ws, resolve_job(ws, str(outside)))
    assert sorted(p.name for p in outside.iterdir()) == ["job.json", "plan.json"]


# The refusals above need real symlinks, which Windows only allows with
# Developer Mode, so those tests skip there and the critical-path gate (D-51)
# would fail on a standard Windows machine. These reach the same refusal code
# on every OS by making the containment check say "outside" for one file.

def leads_outside(monkeypatch, *names):
    """Treat files with these names as resolving outside the workspace."""
    from jobforge.workspace import Workspace
    inside = Workspace.contains
    monkeypatch.setattr(Workspace, "contains",
                        lambda self, path: path.name not in names and inside(self, path))


def test_check_inside_refuses_a_file_that_leads_outside(ws, monkeypatch):
    leads_outside(monkeypatch, "profile.toml")
    with pytest.raises(JobforgeError, match="profile/profile.toml links outside this workspace"):
        ws.check_inside(ws.profile_dir / "profile.toml")


def test_check_inside_names_a_path_outside_the_workspace_in_full(ws, outside, monkeypatch):
    stray = outside / "notes.toml"
    stray.write_text("", encoding="utf-8")
    leads_outside(monkeypatch, "notes.toml")
    with pytest.raises(JobforgeError) as exc:
        ws.check_inside(stray)
    assert str(stray) in exc.value.message


def test_check_inside_allows_a_file_that_does_not_exist_yet(ws, monkeypatch):
    leads_outside(monkeypatch, "new.toml")
    ws.check_inside(ws.atoms_dir / "new.toml")  # nothing to follow yet


def test_confirm_refuses_a_drafted_file_that_leads_outside(ws, monkeypatch):
    add_atoms(ws, '[[skill]]\nid = "skills.x"\nlabel = "Tools"\nitems = ["Excel"]\n',
              "away.toml", pending=True)
    leads_outside(monkeypatch, "away.toml")
    with pytest.raises(JobforgeError) as exc:
        run_confirm(ws, ask=lambda q: "k", say=lambda s: None)
    assert any("away.toml links outside this workspace" in d for d in exc.value.details)
    assert not (ws.atoms_dir / CONFIRMED_FILE).exists()  # nothing was kept
