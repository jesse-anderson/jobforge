"""Check the README's coverage badge against the measured coverage (#48, #101).

The badge is a static shields.io badge with the number written into the
README, so it shows a real percentage while the repo is private. CI runs
this after the suite and fails when the README number is not the measured
one, so it cannot go stale. Nothing is committed from CI (D-48) and no token
is needed. Run after the suite:

    python -m coverage json -o coverage.json
    python tools/coverage_badge.py coverage.json README.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BADGE = re.compile(r"img\.shields\.io/badge/coverage-(\d+)%25-([a-z]+)\)")


def color(percent: float) -> str:
    """The same bands as linreg-core's badge."""
    for floor, name in ((90, "brightgreen"), (85, "green"), (80, "yellowgreen"),
                        (70, "yellow"), (60, "orange")):
        if percent >= floor:
            return name
    return "red"


def badge_url(shown: int) -> str:
    return f"https://img.shields.io/badge/coverage-{shown}%25-{color(shown)}"


def check(shown: int, readme: str) -> str | None:
    """None when the README's badge shows `shown`; otherwise what to fix."""
    want = badge_url(shown)
    found = BADGE.search(readme)
    if found is None:
        return f"README.md has no coverage badge; add one with {want}"
    if not want.endswith(f"coverage-{found.group(1)}%25-{found.group(2)}"):
        return (f"README.md's coverage badge shows {found.group(1)}% ({found.group(2)}); "
                f"coverage is {shown}%. Change its image to {want}")
    return None


def main(argv: list[str]) -> int:
    report, readme = Path(argv[0]), Path(argv[1])
    # The TOTAL that `coverage report` prints: never rounded up to 100.
    totals = json.loads(report.read_text(encoding="utf-8"))["totals"]
    shown = int(totals["percent_covered_display"])
    problem = check(shown, readme.read_text(encoding="utf-8"))
    if problem:
        print(problem)
        return 1
    print(f"coverage badge: {shown}%, matches README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
