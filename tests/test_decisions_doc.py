"""docs/DECISIONS.md says what the code enforces (#83 item 5: "self
referential integrity"), so a decision cannot promise more than the code."""
from conftest import REPO


def _decision(number: int) -> str:
    text = " ".join((REPO / "docs" / "DECISIONS.md").read_text(encoding="utf-8").split())
    return text.split(f"**D-{number}.", 1)[1].split(f"**D-{number + 1}.", 1)[0]


def test_d36_says_what_is_enforced():
    d36 = _decision(36)
    assert "will not keep a new bullet without a `defense` note" in d36
    assert "names them in one warning" in d36
