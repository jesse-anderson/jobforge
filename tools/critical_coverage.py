"""Fail unless every critical-path file is at 100% line and branch coverage
(D-30, D-51). CI fails the whole suite under 95%; this holds the files that
guard a user's facts and documents to 100%.

Run after the suite, from the repo root, on any OS:

    python -m coverage run -m pytest -q
    python tools/critical_coverage.py

The list lives in pyproject.toml, under [tool.jobforge] critical."""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def critical_files(pyproject: Path = ROOT / "pyproject.toml") -> list[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return [f"src/jobforge/{name}" for name in data["tool"]["jobforge"]["critical"]]


def command(files: list[str]) -> list[str]:
    return [sys.executable, "-m", "coverage", "report", "--fail-under=100",
            "--include=" + ",".join(files)]


def main() -> int:
    return subprocess.call(command(critical_files()), cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
