"""Issue #111: no invisible or text-direction character is written literally
in the repo's own files. GitHub flags a file holding one ("hidden or
bidirectional Unicode text", the Trojan Source pattern, CVE-2021-42574), and
an editor or formatter can strip one a test depends on. Write them as
escapes ("\\u200b") instead. Visible non-ASCII (dashes, bullets) is fine."""
import unicodedata

from jobforge.scan import _name

from conftest import REPO

FOLDERS = ("src", "tests", "docs", "fixtures", ".github")
SUFFIXES = {".py", ".md", ".toml", ".json", ".txt", ".yml", ".yaml", ".csv"}


def invisible(ch: str) -> bool:
    if ch in "\n\t\r ":
        return False
    return unicodedata.category(ch) in ("Cf", "Zs", "Zl", "Zp") or _name(ch) is not None


def repo_text_files():
    yield from REPO.glob("*.md")
    for folder in FOLDERS:
        for path in sorted((REPO / folder).rglob("*")):
            if path.suffix in SUFFIXES and path.is_file() and "__pycache__" not in path.parts:
                yield path


def test_no_invisible_characters_written_literally():
    found = []
    for path in repo_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # a file kept in another encoding on purpose
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for ch in dict.fromkeys(c for c in line if invisible(c)):
                found.append(f"{path.relative_to(REPO)}:{n}: U+{ord(ch):04X} "
                             f"{unicodedata.name(ch, '?').lower()}")
    assert not found, "write these as escapes:\n" + "\n".join(found)


def test_the_guard_catches_what_it_should():
    for ch in ("\u200b", "\u202e", "\u00ad", "\u00a0", "\ufeff", "\ufb01", "\u2066"):
        assert invisible(ch), f"U+{ord(ch):04X}"
    for ch in ("a", " ", "–", "—", "•", "é", "中"):
        assert not invisible(ch), f"U+{ord(ch):04X}"
