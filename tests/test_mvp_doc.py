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
    for limit, issue in [("written in words", "#84"), ("titles are not checked", "#89"),
                         ("Unknown names", ""), ("alias", "#22"), ("synonym", ""),
                         ("Pronouns", "#90"), ("posting's figures", "#83"),
                         ("hedges", "#91")]:
        assert limit in limits, limit
        assert issue in limits, issue
    # Fixed since the audit, so no longer a limit: hyphen and spacing variants.
    assert "#92" not in limits and "do match" in limits


def test_mvp_says_the_letter_quotes_the_posting_only_about_the_employer():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "only in a sentence about the employer" in enforced and "#83" in enforced


def test_mvp_no_longer_promises_every_title_and_tool():
    enforced = _section((REPO / "docs" / "MVP.md").read_text(encoding="utf-8"),
                        "### What the fact check enforces in the MVP")
    assert "employer, title, credential, and tool" not in enforced
    assert "the inventory knows" in enforced and "Known limits" in enforced
