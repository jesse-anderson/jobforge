"""Issue #45: nothing in this repo names or points to the maintainers'
private repos, since the repo goes public. The names are built from pieces
here so this file does not hold them either (and so T-PII, once the names
are on the denylist, does not flag the test that guards them).

Text is checked with its line breaks flattened, so a mention wrapped across
two lines is still found. The `jobs` command and a job's `jobs/` folder are
not mentions of a repo and stay."""
import re
import subprocess

from conftest import REPO

OWNER = "jesse" + "-anderson"
NAMES = [
    "jobforge" + "-ops",
    OWNER + "/" + "jobs",
    "tailor" + "-oss",
    "jobs" + "/tailor",
    "jobs" + "/data",
    "jobs" + "/frontend",
    "private `" + "jobs`",
    "jobs" + " repo",
    "private" + " repo",
    "ops" + " repo",
]
PATTERN = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in NAMES) + r")(?![\w-])",
                     re.IGNORECASE)
# release.yml's note about the Free plan means any GitHub repo that is
# private, not one of ours.
ALLOWED = {(".github/workflows/release.yml", "private" + " repo")}


def tracked_text_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout.split()
    for rel in out:
        path = REPO / rel
        try:
            yield rel, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue


def test_no_private_repo_is_named_or_pointed_to():
    found = []
    for rel, text in tracked_text_files():
        flat = " ".join(text.split())
        for m in PATTERN.finditer(flat):
            if (rel, m.group(0).lower()) in ALLOWED:
                continue
            found.append(f"{rel}: ...{flat[max(0, m.start() - 40):m.end() + 40]}...")
    assert not found, "\n".join(found)


def test_the_guard_finds_a_wrapped_mention():
    text = "kept in the\nprivate " + "repo next door"
    assert PATTERN.search(" ".join(text.split()))
