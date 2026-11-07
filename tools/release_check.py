"""Check that a release tag matches the package version before anything is
built for PyPI (#54). PyPI never lets a version be reused, even after it is
deleted, so a wrong or development version must stop here.

    python tools/release_check.py v0.1.0            # for PyPI
    python tools/release_check.py v0.1.0rc1 --test  # for TestPyPI

Exit 0 when the tag is "v" plus the package version. For PyPI the version
must also be a final release (no .dev, a, b, rc); TestPyPI takes any."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
FINAL_RE = re.compile(r"^\d+\.\d+\.\d+$")


def package_version(init: Path = ROOT / "src" / "jobforge" / "__init__.py") -> str:
    m = VERSION_RE.search(init.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"No __version__ in {init}.")
    return m.group(1)


def problems(tag: str, version: str, *, test: bool) -> list[str]:
    out = []
    if tag != f"v{version}":
        out.append(f"Tag {tag!r} does not match the package version {version!r}; "
                   f"tag it v{version}, or change __version__ first.")
    if not test and not FINAL_RE.match(version):
        out.append(f"{version!r} is not a final release (X.Y.Z). Only a tested final "
                   f"version goes to PyPI; use --test for TestPyPI.")
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    test = "--test" in args
    tags = [a for a in args if a != "--test"]
    if len(tags) != 1:
        print(__doc__)
        return 2
    found = problems(tags[0], package_version(), test=test)
    for p in found:
        print(f"error: {p}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
