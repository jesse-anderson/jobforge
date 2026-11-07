"""Issue #40: the README's install steps work on a stock Linux. Ubuntu ships
no `python`, and pip is blocked for the system Python (PEP 668) on Debian and
Ubuntu since 23.04, so Linux installs with pipx. The VM checklist follows the
README, so it says the same."""
from conftest import REPO


def _section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


README = (REPO / "README.md").read_text(encoding="utf-8")
CHECKLIST = (REPO / "docs" / "VM_CHECKLIST.md").read_text(encoding="utf-8")


def test_python_check_names_python3_for_linux():
    needs = _section(README, "## What you need")
    assert "python3 --version" in needs


def test_linux_setup_uses_pipx():
    setup = _section(README, "## Set up (once)")
    linux = setup.split("On Linux", 1)[1].split("On Windows", 1)[0]
    for step in ("sudo apt install pipx", "pipx ensurepath", "pipx install jobforge"):
        assert step in linux, step
    assert "pip install jobforge" not in linux.replace("pipx install jobforge", "")


def test_windows_setup_keeps_pip():
    setup = _section(README, "## Set up (once)")
    assert "pip install jobforge" in setup.split("On Windows", 1)[1]


def test_readme_says_how_to_uninstall_on_each_os():
    setup = _section(README, "## Set up (once)")
    assert "pipx uninstall jobforge" in setup and "pip uninstall jobforge" in setup


def test_checklist_installs_and_uninstalls_like_the_readme():
    for step in ("pipx install jobforge", "pipx install .", "pipx uninstall jobforge",
                 "pip install jobforge", "pip uninstall jobforge", "python3 --version"):
        assert step in CHECKLIST, step


def test_checklist_commands_can_be_typed_as_written():
    # #3, Linux run: `<posting.txt>` typed as written is a shell redirect,
    # so no placeholder in angle brackets inside a command.
    import re
    for span in re.findall(r"`([^`]+)`", CHECKLIST):
        assert not re.search(r"<[\w./ -]+>", span), span


def test_checklist_carries_the_fixes_from_the_linux_run():
    flat = " ".join(CHECKLIST.split())
    # pipx looks for its own pip on the index it is given; TestPyPI has none.
    assert "--index-url https://test.pypi.org/simple/" in flat
    assert '--pip-args="--extra-index-url https://pypi.org/simple/"' in flat
    # Reverting a running VM's snapshot restores its clock too.
    assert "timedatectl" in flat
    # Not preinstalled on Ubuntu Desktop; and #3 asks for Google Docs as well.
    assert "sudo apt install libreoffice" in flat and "Google Docs" in flat


def test_readme_links_are_absolute_so_they_work_on_pypi():
    # PyPI renders the README as the project page and cannot follow a
    # relative link such as (LICENSE) or (#what-you-need) (#54).
    import re
    relative = [link for link in re.findall(r"\]\(([^)\s]+)\)", README)
                if not link.startswith(("https://", "http://", "mailto:"))]
    assert relative == []


def test_pypi_sidebar_links_to_the_repo():
    import tomllib
    urls = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["urls"]
    base = "https://github.com/jesse-anderson/jobforge"
    assert urls["Homepage"] == base and urls["Source"] == base
    assert urls["Issues"] == base + "/issues"
