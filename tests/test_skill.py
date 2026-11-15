"""#161: `skills/jobforge/SKILL.md`, the agent's entry point before a
workspace exists. It installs the way the README does, starts with
`jobforge init`, and hands off to the workspace's generated instructions
instead of copying them, so the two cannot drift."""
import re

from conftest import REPO

SKILL_DIR = REPO / "skills" / "jobforge"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")
INSTRUCTIONS = (REPO / "src" / "jobforge" / "agent" / "instructions.md").read_text(
    encoding="utf-8")


def _frontmatter() -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", SKILL, re.S)
    assert m, "SKILL.md starts with --- frontmatter ---"
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        assert sep and key == key.strip(), f"one `key: value` per line: {line!r}"
        fields[key] = value.strip()
    return fields


def _commands(text: str) -> list[str]:
    """Every line inside a ``` block, with any trailing comment dropped."""
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
    return [line.split("#", 1)[0].strip() for b in blocks for line in b.splitlines()
            if line.split("#", 1)[0].strip()]


def test_frontmatter_is_an_agent_skill():
    # The Agent Skills layout: a folder named for the skill, holding SKILL.md
    # whose frontmatter has a matching `name` and a `description`.
    fm = _frontmatter()
    assert set(fm) == {"name", "description"}
    assert fm["name"] == SKILL_DIR.name == "jobforge"
    assert re.fullmatch(r"[a-z0-9-]{1,64}", fm["name"])
    assert 0 < len(fm["description"]) <= 1024
    # When to use it: a job search, a resume, or a cover letter.
    for word in ("job", "resume", "cover letter"):
        assert word in fm["description"].lower(), word


def test_install_commands_are_the_readmes():
    setup = README.split("## Set up (once)", 1)[1].split("\n## ", 1)[0]
    readme = set(_commands(setup))
    skill = [c for c in _commands(SKILL) if not c.startswith(("jobforge ", "cd "))]
    assert skill, "the skill shows how to install"
    for cmd in skill:
        assert cmd in readme, f"{cmd!r} is not an install step in the README"
    assert "pipx install jobforge" in skill and "pip install jobforge" in skill


def test_linux_uses_pipx_and_windows_pip():
    linux = SKILL.split("On Linux", 1)[1].split("On Windows", 1)[0]
    assert "pipx install jobforge" in linux and "pip install jobforge" not in \
        linux.replace("pipx install jobforge", "")
    assert "pip install jobforge" in SKILL.split("On Windows", 1)[1]


def test_skill_asks_before_installing():
    # Installing changes the user's machine, and `sudo` needs their password.
    assert "Ask the user before installing" in SKILL


def test_skill_starts_with_init_and_names_check():
    assert "jobforge init" in SKILL and "jobforge check" in SKILL
    assert "jobforge --version" in SKILL  # how to tell it is installed


def test_skill_hands_off_to_the_workspace_instructions():
    assert "CLAUDE.md" in SKILL and "AGENTS.md" in SKILL
    assert "src/jobforge/agent/instructions.md" in SKILL


def test_skill_does_not_copy_the_workspace_instructions():
    # A copied line would drift from the generated file. Short lines
    # ("## Commands") may repeat; a sentence may not.
    for line in INSTRUCTIONS.splitlines():
        line = line.strip()
        if len(line) >= 40:
            assert line not in SKILL, line


def test_skill_states_the_one_rule_and_what_it_is_not():
    assert "Never state a fact the user has not confirmed" in SKILL
    assert "no model API" in SKILL and "D-12" in SKILL
    assert "never leaves" in SKILL


def test_skill_has_no_contact_details():
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", SKILL), "no email addresses"
    assert not re.search(r"\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}", SKILL), "no phone numbers"


def test_readme_points_to_the_skill():
    link = "https://github.com/jesse-anderson/jobforge/blob/main/skills/jobforge/SKILL.md"
    assert link in README.split("## Set up (once)", 1)[1].split("\n## ", 1)[0]
