"""Write the coverage badge as a shields.io endpoint file (#48).

CI runs this on main after the suite and publishes the file to GitHub Pages;
the README's badge reads it from there. Nothing is committed (D-48) and no
token is needed. Run after the suite:

    python -m coverage json -o coverage.json
    python tools/coverage_badge.py coverage.json _site/coverage-badge.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def color(percent: float) -> str:
    """The same bands as linreg-core's badge."""
    for floor, name in ((90, "brightgreen"), (85, "green"), (80, "yellowgreen"),
                        (70, "yellow"), (60, "orange")):
        if percent >= floor:
            return name
    return "red"


def badge(percent: float) -> dict:
    return {"schemaVersion": 1, "label": "coverage", "message": f"{percent:.0f}%",
            "color": color(percent)}


def main(argv: list[str]) -> int:
    report, out = Path(argv[0]), Path(argv[1])
    percent = json.loads(report.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(badge(percent)) + "\n", encoding="utf-8")
    print(f"coverage badge: {badge(percent)['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
