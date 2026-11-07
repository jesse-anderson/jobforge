"""End to end: check and apply on a prepared job (D-30 items 3, 4, 5)."""
import json

import pytest

from jobforge import apply as apply_mod
from jobforge.apply import CHECK_NAME, COVER_MD_NAME, apply, run_check, verify_readback
from jobforge.docx import extract_text
from jobforge.errors import JobforgeError
from jobforge.scan import find_hidden

from conftest import TODAY, add_atoms, edit_plan

pytestmark = pytest.mark.critical
DELIVERABLES = ("John_Smith_Resume.docx", "John_Smith_Cover_Letter.docx", COVER_MD_NAME)


def test_check_passes_and_writes_only_check_json(ws, job_folder):
    before = set(p.name for p in job_folder.iterdir())
    result = run_check(ws, job_folder)
    assert result.ok, result.errors
    assert set(p.name for p in job_folder.iterdir()) == before | {CHECK_NAME}
    report = json.loads((job_folder / CHECK_NAME).read_text(encoding="utf-8"))
    assert report["ok"] is True and report["estimated_pages"] < 1


def test_apply_writes_named_deliverables(ws, job_folder):
    out = apply(ws, job_folder, today=TODAY)
    for name in DELIVERABLES:
        assert (job_folder / name).exists(), name
    assert out["estimated_pages"] < 1
    # No temporary folders left behind.
    assert not [p for p in job_folder.iterdir() if p.name.startswith(".jobforge-")]


def test_deliverables_read_back_clean(ws, job_folder):
    apply(ws, job_folder, today=TODAY)
    resume = extract_text(job_folder / "John_Smith_Resume.docx")
    letter = extract_text(job_folder / "John_Smith_Cover_Letter.docx")
    assert find_hidden(resume) == [] and find_hidden(letter) == []
    assert "example.com/shift-scheduler" in resume
    assert "99.6%" in resume
    assert "Dear Prairie Freight Co. Hiring Team," in letter
    # The working copy's heading and cites never reach the deliverable.
    assert "working copy" not in letter and "northwind.accuracy" not in letter


def test_failing_plan_writes_no_deliverables(ws, job_folder):
    edit_plan(job_folder, lambda p: p["experience"][0]["bullets"].__setitem__(
        0, {"atom": "northwind.accuracy", "text": "Raised pick accuracy to 100%"}))
    with pytest.raises(JobforgeError) as exc:
        apply(ws, job_folder, today=TODAY)
    assert any("100%" in d for d in exc.value.details)
    for name in DELIVERABLES:
        assert not (job_folder / name).exists()
    report = json.loads((job_folder / CHECK_NAME).read_text(encoding="utf-8"))
    assert report["ok"] is False and report["errors"]


def test_failing_plan_leaves_earlier_deliverables_untouched(ws, job_folder):
    apply(ws, job_folder, today=TODAY)
    before = (job_folder / "John_Smith_Resume.docx").read_bytes()
    edit_plan(job_folder, lambda p: p.update(version=9))
    with pytest.raises(JobforgeError):
        apply(ws, job_folder, today=TODAY)
    assert (job_folder / "John_Smith_Resume.docx").read_bytes() == before


def test_structural_errors_stop_before_the_fact_check(ws, job_folder):
    edit_plan(job_folder, lambda p: p["experience"][0].update(role="ghost"))
    result = run_check(ws, job_folder)
    assert not result.ok and result.plan is None


def test_postings_own_en_dash_does_not_block(ws, job_folder):
    # F21: a dash in the posted title is the employer's, not the user's.
    data = json.loads((job_folder / "job.json").read_text(encoding="utf-8"))
    data["title"] = "Operations Supervisor – Second Shift"
    (job_folder / "job.json").write_text(json.dumps(data), encoding="utf-8")
    apply(ws, job_folder, today=TODAY)
    letter = extract_text(job_folder / "John_Smith_Cover_Letter.docx")
    assert "Operations Supervisor – Second Shift" in letter


def test_hidden_character_in_an_atom_blocks_apply(ws, job_folder):
    add_atoms(ws, '[[bullet]]\nid = "northwind.zw"\nrole = "northwind"\n'
                  'text = "Ran cycle​counts weekly"\nbasis = "records"\n')
    edit_plan(job_folder, lambda p: p["experience"][0]["bullets"].append("northwind.zw"))
    with pytest.raises(JobforgeError) as exc:
        apply(ws, job_folder, today=TODAY)
    assert any("zero-width space" in d for d in exc.value.details)
    assert not (job_folder / "John_Smith_Resume.docx").exists()


def test_long_resume_warns(ws, job_folder):
    lines = "\n".join(
        f'[[bullet]]\nid = "northwind.x{i}"\nrole = "northwind"\n'
        f'text = "Handled task number {i} {"with a lot of detail " * 6}"\nbasis = "records"\n'
        for i in range(40))
    add_atoms(ws, lines)
    edit_plan(job_folder, lambda p: p["experience"][0]["bullets"].extend(
        f"northwind.x{i}" for i in range(40)))
    result = run_check(ws, job_folder)
    assert result.ok
    assert any("estimated at" in w for w in result.warnings)


def test_apply_twice_overwrites(ws, job_folder):
    apply(ws, job_folder, today=TODAY)
    edit_plan(job_folder, lambda p: p["experience"][1].update(bullets=["lakeside.shrink"]))
    apply(ws, job_folder, today=TODAY)
    assert "Trained 30" not in extract_text(job_folder / "John_Smith_Resume.docx")


def test_missing_plan_and_job(ws, job_folder):
    (job_folder / "plan.json").unlink()
    with pytest.raises(JobforgeError, match="no plan.json yet"):
        run_check(ws, job_folder)
    (job_folder / "job.json").unlink()
    with pytest.raises(JobforgeError, match="no job.json"):
        run_check(ws, job_folder)


def test_plan_not_json(ws, job_folder):
    (job_folder / "plan.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(JobforgeError, match="not valid JSON"):
        run_check(ws, job_folder)
    (job_folder / "plan.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(JobforgeError, match="must be a JSON object"):
        run_check(ws, job_folder)


def test_readback_failure_blocks_and_cleans_up(ws, job_folder, monkeypatch):
    # Simulate a writer bug that drops text: the read-back must catch it.
    monkeypatch.setattr(apply_mod, "extract_text", lambda path: "John Smith")
    with pytest.raises(JobforgeError) as exc:
        apply(ws, job_folder, today=TODAY)
    assert any("did not survive the round trip" in d for d in exc.value.details)
    assert not (job_folder / "John_Smith_Resume.docx").exists()
    assert not [p for p in job_folder.iterdir() if p.name.startswith(".jobforge-")]


def test_verify_readback_reports_missing_url_and_hidden():
    rep = verify_readback("Line one here", ["Line one here", "Line two"],
                          ["https://example.com/a"], "doc")
    assert any("non-breaking space" in e for e in rep.errors)
    assert any("Line two" in e for e in rep.errors)
    assert any("example.com/a" in e for e in rep.errors)


# Issue #32: a deliverable open in Word (locked on Windows) must not crash
# apply or leave the folder's files out of step. All or nothing.
def lock(monkeypatch, folder, name):
    """Moving onto or away from folder/name fails, as with a file Word holds."""
    real = apply_mod._move
    locked = folder / name

    def move(src, dst):
        if locked in (src, dst):
            raise PermissionError(13, "Access is denied", str(locked))
        real(src, dst)
    monkeypatch.setattr(apply_mod, "_move", move)


def snapshot(folder):
    return {n: (folder / n).read_bytes() for n in DELIVERABLES}


@pytest.mark.parametrize("name", DELIVERABLES)
def test_locked_deliverable_changes_nothing(ws, job_folder, monkeypatch, name):
    apply(ws, job_folder, today=TODAY)
    before = snapshot(job_folder)
    edit_plan(job_folder, lambda p: p["experience"][1].update(bullets=["lakeside.shrink"]))
    lock(monkeypatch, job_folder, name)
    with pytest.raises(JobforgeError, match=f"Close {name}") as exc:
        apply(ws, job_folder, today=TODAY)
    assert "Nothing was changed" in exc.value.message
    assert snapshot(job_folder) == before
    assert not [p for p in job_folder.iterdir() if p.name.startswith(".jobforge-")]


def test_failure_placing_a_new_file_restores_the_old_ones(ws, job_folder, monkeypatch):
    # The old files moved aside, then a new one could not be placed.
    apply(ws, job_folder, today=TODAY)
    before = snapshot(job_folder)
    edit_plan(job_folder, lambda p: p["experience"][1].update(bullets=["lakeside.shrink"]))
    real = apply_mod._move
    target = job_folder / "John_Smith_Cover_Letter.docx"

    def move(src, dst):
        if dst == target and src.parent.name.startswith(".jobforge-"):  # the new file
            raise PermissionError(13, "Access is denied", str(dst))
        real(src, dst)
    monkeypatch.setattr(apply_mod, "_move", move)
    with pytest.raises(JobforgeError, match="Close John_Smith_Cover_Letter.docx"):
        apply(ws, job_folder, today=TODAY)
    assert snapshot(job_folder) == before


@pytest.mark.parametrize("nth", range(1, 7))
def test_ctrl_c_during_the_swap_loses_nothing(ws, job_folder, monkeypatch, nth):
    # Found red-teaming (#28): Ctrl+C is not an OSError, so the rollback was
    # skipped and the cleanup deleted the old files moved aside.
    apply(ws, job_folder, today=TODAY)
    before = snapshot(job_folder)
    real = apply_mod._move
    calls = {"n": 0}

    def move(src, dst):
        calls["n"] += 1
        if calls["n"] == nth:
            raise KeyboardInterrupt
        real(src, dst)
    monkeypatch.setattr(apply_mod, "_move", move)
    with pytest.raises(KeyboardInterrupt):
        apply(ws, job_folder, today=TODAY)
    assert snapshot(job_folder) == before
    assert not [p for p in job_folder.iterdir() if p.name.startswith(".jobforge-")]


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="needs a real Windows lock")
def test_real_windows_lock_changes_nothing(ws, job_folder):
    apply(ws, job_folder, today=TODAY)
    before = snapshot(job_folder)
    with open(job_folder / "John_Smith_Resume.docx", "rb"):
        with pytest.raises(JobforgeError, match="Close John_Smith_Resume.docx"):
            apply(ws, job_folder, today=TODAY)
    assert snapshot(job_folder) == before


def test_other_file_errors_roll_back_and_are_not_called_a_lock(ws, job_folder, monkeypatch):
    # A full disk is not "close the file in Word": roll back, then report it.
    apply(ws, job_folder, today=TODAY)
    before = snapshot(job_folder)
    real = apply_mod._move

    def move(src, dst):
        if dst == job_folder / COVER_MD_NAME and src.parent.name.startswith(".jobforge-"):
            raise OSError(28, "No space left on device")
        real(src, dst)
    monkeypatch.setattr(apply_mod, "_move", move)
    with pytest.raises(OSError, match="No space"):
        apply(ws, job_folder, today=TODAY)
    assert snapshot(job_folder) == before
