"""Issue #48: README badges, and a coverage badge that CI publishes to
GitHub Pages instead of committing (D-48), with no token."""
import importlib.util
import json

import pytest

from conftest import REPO

_spec = importlib.util.spec_from_file_location("coverage_badge",
                                               REPO / "tools" / "coverage_badge.py")
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)

README = (REPO / "README.md").read_text(encoding="utf-8")
WORKFLOW = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
BADGE_URL = "https://jesse-anderson.github.io/jobforge/coverage-badge.json"


@pytest.mark.parametrize("percent,color", [
    (99.4, "brightgreen"), (90, "brightgreen"), (89.9, "green"), (80, "yellowgreen"),
    (70, "yellow"), (60, "orange"), (59.9, "red"),
])
def test_badge_color_bands(percent, color):
    assert cb.color(percent) == color


def test_badge_is_a_shields_endpoint_file(tmp_path):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"totals": {"percent_covered": 99.43}}), encoding="utf-8")
    out = tmp_path / "_site" / "coverage-badge.json"
    assert cb.main([str(report), str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "schemaVersion": 1, "label": "coverage", "message": "99%", "color": "brightgreen"}


def badges():
    """The badge lines right under the title."""
    lines = README.split("\n")
    assert lines[0] == "# Jobforge"
    return [ln for ln in lines[1:lines.index("Turn your real work history into a resume "
                                             "and cover letter tailored to one")] if ln]


def test_badges_sit_under_the_title_and_each_links_somewhere():
    found = badges()
    assert len(found) == 6
    for line in found:
        assert line.startswith("[![") and line.endswith(")"), line


@pytest.mark.parametrize("needle", [
    "actions/workflows/tests.yml/badge.svg",     # tests
    f"img.shields.io/endpoint?url={BADGE_URL}",  # coverage, from Pages
    "python-3.11%2B", "](LICENSE)", "Windows%20%7C%20Linux", "dependencies-none",
])
def test_each_badge_is_there(needle):
    assert any(needle in line for line in badges()), needle


def test_ci_publishes_the_badge_where_the_readme_reads_it():
    job = WORKFLOW.split("\n  badge:\n", 1)[1]
    assert "tools/coverage_badge.py coverage.json _site/coverage-badge.json" in job
    assert "actions/upload-pages-artifact" in job and "actions/deploy-pages" in job
    assert BADGE_URL.rsplit("/", 1)[1] == "coverage-badge.json"


def test_ci_badge_job_runs_only_on_main_once_public_and_never_commits():
    job = WORKFLOW.split("\n  badge:\n", 1)[1]
    condition = job.split("if:", 1)[1].split("\n", 1)[0]
    for part in ("github.event_name == 'push'", "github.ref == 'refs/heads/main'",
                 "!github.event.repository.private"):
        assert part in condition, part
    assert "git commit" not in job and "git push" not in job and "secrets." not in job
