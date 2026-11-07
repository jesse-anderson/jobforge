"""Community files say what the decisions say (D-19, D-39) and carry no
personal contact details, since they go public at launch (#20)."""
import re

import pytest

from conftest import REPO

FILES = ["CONTRIBUTING.md", "SECURITY.md", ".github/pull_request_template.md",
         ".github/ISSUE_TEMPLATE/bug.md", ".github/ISSUE_TEMPLATE/fact_check_bypass.md",
         ".github/ISSUE_TEMPLATE/config.yml"]


def _read(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", FILES)
def test_community_file_has_no_contact_details(path):
    text = _read(path)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), "no email addresses"
    assert not re.search(r"\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}", text), "no phone numbers"


def test_contributing_says_prs_are_closed_until_the_harness_exists():
    text = _read("CONTRIBUTING.md")
    assert "D-19" in text and "not accepted yet" in text


def test_contributing_asks_for_a_dco_sign_off():
    text = _read("CONTRIBUTING.md")
    assert "git commit -s" in text and "Developer Certificate of Origin" in text


def test_contributing_carries_the_maintainers_test_commands():
    # Same commands as the pre-push rule in CLAUDE.md, so the two never drift.
    for cmd in ("python -m coverage run -m pytest -q",
                "python -m coverage report --fail-under=95"):
        assert cmd in _read("CONTRIBUTING.md")
        assert cmd in _read("CLAUDE.md")
        assert cmd in _read(".github/pull_request_template.md")


def test_security_routes_reports_privately_and_bypasses_to_issues():
    text = _read("SECURITY.md")
    assert "Report a vulnerability" in text
    assert "Fact-check bypass" in text
    assert "Fact-check bypass" in _read(".github/ISSUE_TEMPLATE/fact_check_bypass.md")


def test_issue_templates_have_front_matter():
    for name in ("bug.md", "fact_check_bypass.md"):
        text = _read(f".github/ISSUE_TEMPLATE/{name}")
        assert text.startswith("---\nname: ")
        assert "\nabout: " in text.split("---", 2)[1]


def test_gitattributes_stores_text_with_lf():
    assert "* text=auto eol=lf" in _read(".gitattributes")


def test_contributing_grants_contributions_under_the_project_license():
    text = " ".join(_read("CONTRIBUTING.md").split())
    assert "By submitting a contribution, you license it under" in text
    assert "PolyForm Noncommercial 1.0.0" in text
    assert "You keep the copyright in what you wrote" in text


def test_copyright_holders_agree_across_license_contributing_and_decisions():
    # D-49: the holders named in LICENSE's Required Notice are the ones
    # CONTRIBUTING and DECISIONS name.
    notice = _read("LICENSE").splitlines()[0]
    holders = notice.split("Copyright 2026 ", 1)[1]
    assert holders == "Jesse Anderson and Mike Wilson"
    contributing = " ".join(_read("CONTRIBUTING.md").split())
    assert f"held jointly by its maintainers, {holders} (D-49)" in contributing
    decisions = _read("docs/DECISIONS.md")
    assert "| D-49 | Copyright |" in decisions
    assert "**D-49." in decisions
