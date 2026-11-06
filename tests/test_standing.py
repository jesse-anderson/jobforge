"""Standing exit tests from SOW section 4: T-STD and T-PII."""
import json
import os
import pkgutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

import jobforge

from conftest import REPO

pytestmark = pytest.mark.critical


def test_t_std_runtime_imports_only_the_standard_library():
    """T-STD: importing every runtime module pulls in nothing third-party."""
    # __main__ runs the CLI on import, so it is checked through cli instead.
    modules = [m.name for m in pkgutil.walk_packages(jobforge.__path__, "jobforge.")
               if not m.name.endswith("__main__")]
    assert "jobforge.cli" in modules
    # Only what importing Jobforge adds counts. Site hooks loaded at
    # interpreter startup (pywin32 on Windows, for one) are the machine's.
    code = (
        "import sys, json\n"
        "before = set(sys.modules)\n"
        f"for m in {modules!r}: __import__(m)\n"
        "added = set(sys.modules) - before\n"
        "print(json.dumps(sorted({n.split('.')[0] for n in added})))\n"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, cwd=REPO / "src")
    assert out.returncode == 0, out.stderr
    loaded = set(json.loads(out.stdout))
    allowed = set(sys.stdlib_module_names) | {"jobforge", "__main__", "builtins", "sys"}
    third_party = sorted(m for m in loaded - allowed if not m.startswith("_"))
    assert third_party == [], third_party


def test_pyproject_declares_no_runtime_dependencies():
    import tomllib
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []


# T-PII. The denylist is itself PII, so it never lives in the repo: it comes
# from a file outside the tree (JOBFORGE_PII_DENYLIST, or the default path) or
# a CI secret. Without it the test skips with a visible warning.
DEFAULT_DENYLIST = Path.home() / ".config" / "jobforge" / "pii_denylist.txt"
SCANNED_SUFFIXES = {".py", ".md", ".toml", ".json", ".txt", ".html", ".yml", ".yaml", ".cfg", ".ini"}
# Maintainer names are allowed in these files (SOW T-PII).
NAME_ALLOWLIST = {"pyproject.toml", "LICENSE", "SOW.md", "DECISIONS.md", "COMPONENTS.md",
                  "MAINTAINING.md", "MVP.md", "CLAUDE.md", "AGENTS.md"}


def _denylist() -> list[str] | None:
    path = Path(os.environ.get("JOBFORGE_PII_DENYLIST", DEFAULT_DENYLIST))
    if not path.exists():
        return None
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def _tracked_files() -> list[Path]:
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv"}
    out = []
    for p in REPO.rglob("*"):
        if p.is_file() and p.suffix in SCANNED_SUFFIXES and not (set(p.parts) & skip_dirs):
            if not any(part.endswith(".egg-info") for part in p.parts):
                out.append(p)
    return out


def test_t_pii_no_denylisted_string_in_the_repo():
    terms = _denylist()
    if terms is None:
        warnings.warn("T-PII skipped: no denylist. Set JOBFORGE_PII_DENYLIST or create "
                      f"{DEFAULT_DENYLIST} (one term per line). Maintainers must run this.")
        pytest.skip("no PII denylist available")
    hits = []
    for path in _tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in terms:
            name_term = term.startswith("name:")
            needle = term.split(":", 1)[1] if name_term else term
            if name_term and path.name in NAME_ALLOWLIST:
                continue
            if needle.lower() in text:
                hits.append(f"{path.relative_to(REPO).as_posix()}: {needle!r}")
    assert hits == [], "\n".join(hits)
