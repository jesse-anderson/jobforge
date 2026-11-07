"""Issue #48: README badges. Issue #101: the coverage badge shows a real
number while the repo is private: a static badge that CI checks against the
measured coverage, with nothing committed (D-48) and no token."""
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


@pytest.mark.parametrize("percent,color", [
    (99.4, "brightgreen"), (90, "brightgreen"), (89.9, "green"), (80, "yellowgreen"),
    (70, "yellow"), (60, "orange"), (59.9, "red"),
])
def test_badge_color_bands(percent, color):
    assert cb.color(percent) == color


def test_badge_url_takes_its_color_from_the_number():
    assert cb.badge_url(99) == "https://img.shields.io/badge/coverage-99%25-brightgreen"
    assert cb.badge_url(84) == "https://img.shields.io/badge/coverage-84%25-yellowgreen"


def write_report(tmp_path, percent=99.67, display="99"):
    """coverage.py's own TOTAL: 99.67% prints as 99, never 100."""
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"totals": {"percent_covered": percent,
                                             "percent_covered_display": display}}),
                      encoding="utf-8")
    return report


def readme_with(tmp_path, image):
    readme = tmp_path / "README.md"
    readme.write_text(f"# Jobforge\n\n[![coverage]({image})](https://example.com)\n",
                      encoding="utf-8")
    return readme


def test_matching_badge_passes(tmp_path, capsys):
    readme = readme_with(tmp_path, "https://img.shields.io/badge/coverage-99%25-brightgreen")
    assert cb.main([str(write_report(tmp_path)), str(readme)]) == 0
    assert "99%, matches README.md" in capsys.readouterr().out


@pytest.mark.parametrize("image,shows", [
    ("https://img.shields.io/badge/coverage-97%25-brightgreen", "97% (brightgreen)"),
    ("https://img.shields.io/badge/coverage-99%25-green", "99% (green)"),
])
def test_stale_badge_fails_and_says_what_to_paste(tmp_path, capsys, image, shows):
    readme = readme_with(tmp_path, image)
    assert cb.main([str(write_report(tmp_path)), str(readme)]) == 1
    out = capsys.readouterr().out
    assert f"shows {shows}; coverage is 99%" in out
    assert "https://img.shields.io/badge/coverage-99%25-brightgreen" in out


def test_badge_shows_what_coverage_report_prints_not_a_rounded_up_100(tmp_path):
    readme = readme_with(tmp_path, "https://img.shields.io/badge/coverage-100%25-brightgreen")
    assert cb.main([str(write_report(tmp_path, 99.67, "99")), str(readme)]) == 1


def test_missing_badge_fails(tmp_path, capsys):
    readme = readme_with(tmp_path, "https://img.shields.io/badge/python-3.11%2B-blue")
    assert cb.main([str(write_report(tmp_path)), str(readme)]) == 1
    assert "has no coverage badge" in capsys.readouterr().out


def test_readme_badge_color_matches_its_number():
    found = cb.BADGE.search(README)
    assert found, "README.md has no coverage badge"
    assert cb.color(int(found.group(1))) == found.group(2)


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
    "img.shields.io/badge/coverage-",            # coverage, checked by CI
    "python-3.11%2B", "](https://github.com/jesse-anderson/jobforge/blob/main/LICENSE)", "Windows%20%7C%20Linux", "dependencies-none",
])
def test_each_badge_is_there(needle):
    assert any(needle in line for line in badges()), needle


def test_ci_checks_the_readme_badge_after_the_suite_and_never_commits():
    job = WORKFLOW.split("\n  test:\n", 1)[1]
    step = job.split("- name: Check the README coverage badge", 1)[1]
    assert job.index("coverage run -m pytest") < job.index("Check the README coverage badge")
    assert "python tools/coverage_badge.py coverage.json README.md" in step
    assert "if: matrix.python == '3.13'" in step
    assert "git commit" not in WORKFLOW and "git push" not in WORKFLOW


def test_no_pages_job_left():
    # The badge no longer reads a file published to Pages (#101).
    assert "deploy-pages" not in WORKFLOW and "\n  badge:\n" not in WORKFLOW
    assert "img.shields.io/endpoint" not in README
