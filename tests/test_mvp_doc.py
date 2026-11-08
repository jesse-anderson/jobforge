"""docs/MVP.md says what the fact check does not catch (#1).

The audit found that "every employer, title, credential, and tool" overclaimed:
the check only knows names in the inventory, and some gaps are open issues.
The doc has to say so, so nobody reads the promise as stronger than the code.
"""
from conftest import REPO


def _section(text: str, heading: str) -> str:
    body = text.split(heading, 1)[1]
    return " ".join(body.split("\n### ", 1)[0].split())  # phrases may wrap


def test_mvp_lists_the_known_limits_of_the_fact_check():
    mvp = (REPO / "docs" / "MVP.md").read_text(encoding="utf-8")
    limits = _section(mvp, "### Known limits of the fact check")
    for limit, issue in [("Number words in names", "#84"), ("Titles in lowercase or one word", "#89"),
                         ("Unknown names", ""), ("alias", "#22"), ("synonym", ""),
                         ("Pronouns", "#90"), ("posting's figures", "#83"),
                         ("hedges", "#91")]:
        assert limit in limits, limit
        assert issue in limits, issue
    # Fixed since the audit, so no longer a limit: hyphen and spacing variants,
    # and figures written in words (#84).
    assert "#92" not in limits and "do match" in limits
    assert "are not read as figures" not in limits


def test_mvp_says_figures_in_words_are_checked():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "A figure written in words is a figure (#84)" in enforced
    assert '"a third" is not "33%"' in enforced


def test_mvp_says_the_letter_quotes_the_posting_only_about_the_employer():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "only in a sentence about the employer" in enforced and "#83" in enforced


def test_mvp_says_a_sentence_carries_the_employer_before_it():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "in the same paragraph that name no employer" in enforced


def test_mvp_no_longer_promises_every_title_and_tool():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "employer, title, credential, and tool" not in enforced
    assert "the inventory knows" in enforced and "Known limits" in enforced


def test_mvp_says_titles_are_checked():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "title_aliases" in enforced and "#89" in enforced


def test_build_status_covers_every_gate_item():
    """The gate list and its status table stay in step: every numbered gate
    item has a row, and the table is not the first draft's."""
    mvp = (REPO / "docs" / "MVP.md").read_text(encoding="utf-8")
    gate = mvp.split("## 5. MVP gate", 1)[1].split("\n---", 1)[0]
    items = [line.split(".", 1)[0] for line in gate.splitlines()
             if line[:1].isdigit() and ". " in line[:4]]
    table = gate.split("### Build status", 1)[1]
    rows = [line.split("|")[1].strip().split(".", 1)[0] for line in table.splitlines()
            if line.startswith("| ") and line[2:3].isdigit()]
    assert items and rows == items, (items, rows)
    assert "### Build status (2026-11-06)" not in mvp
    assert "not computed yet" not in table and "not run." not in table
