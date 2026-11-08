"""Every GitHub Action the workflows run is pinned to a commit ID.

A tag such as `@v4` or `@release/v1` can be moved to different code at any
time. The release workflow publishes to PyPI under our name with trusted
publishing, so a moved tag on any action it runs could publish anything.
A commit ID cannot move. Dependabot (.github/dependabot.yml) proposes updates.
"""
import re

from conftest import REPO

WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$", re.MULTILINE)


def test_there_are_workflows_to_check():
    assert {p.name for p in WORKFLOWS} >= {"tests.yml", "release.yml", "clean-windows.yml"}


def test_every_action_is_pinned_to_a_commit_with_its_version_noted():
    found = []
    for path in WORKFLOWS:
        for action, rest in USES.findall(path.read_text(encoding="utf-8")):
            found.append(action)
            name, _, ref = action.partition("@")
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{path.name}: {action} is not pinned"
            assert re.search(r"#\s*v\d+\.\d+\.\d+", rest), f"{path.name}: {action} has no version comment"
    assert found  # the pattern still matches the files


def test_the_same_action_is_pinned_to_one_commit_everywhere():
    pins: dict[str, set[str]] = {}
    for path in WORKFLOWS:
        for action, _ in USES.findall(path.read_text(encoding="utf-8")):
            name, _, ref = action.partition("@")
            pins.setdefault(name, set()).add(ref)
    assert {n: r for n, r in pins.items() if len(r) > 1} == {}


def test_dependabot_watches_the_actions():
    config = (REPO / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert "package-ecosystem: github-actions" in config
