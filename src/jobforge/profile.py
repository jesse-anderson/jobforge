"""The user's profile: identity, settings, voice rules, never-claim list.

Replaces every hardcoded identity block in the private repo (D-08). Facts
about work history are not here; they are atoms.
"""
from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field

from .errors import JobforgeError
from .workspace import Workspace

# General AI-tell vocabulary. Kept from the private validator minus anything
# specific to one person (SOW A-13). Users add or allow words in [voice].
DEFAULT_BANNED_WORDS = frozenset({
    "leverage", "leveraging", "leverages", "leveraged",
    "elevate", "elevating", "elevated",
    "innovative", "transformative", "robust",
    "seamless", "seamlessly", "cutting-edge", "world-class",
    "synergy", "synergies", "synergistic",
    "holistic", "holistically", "paradigm",
    "delve", "delving", "delved",
    "unlock", "unlocking", "unlocked",
    "empower", "empowering", "empowered", "empowerment",
    "unleash", "unleashing", "unleashed",
    "tapestry", "passionate", "thrilled", "realm",
})

DEFAULT_BANNED_PHRASES = (
    "i'm excited to", "i am excited to", "thrilled to", "passionate about",
    "strong believer", "deeply passionate", "look forward to hearing",
    "thank you for your consideration", "dive into", "dive deep",
    "navigate the complexities", "navigating the complexities",
    "in the landscape of", "in the realm of",
)

_SECTIONS = {
    "person": {"name", "email", "phone", "location", "links", "file_stem"},
    "settings": {"page_limit", "cover_letter_max_words", "ghost_after_days"},
    "voice": {"add_banned_words", "allow_words", "add_banned_phrases", "ban_dashes"},
    "claims": {"never_claim"},
}


@dataclass
class Profile:
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = field(default_factory=list)
    file_stem: str = ""
    page_limit: int = 1
    cover_letter_max_words: int = 300
    ghost_after_days: int = 30
    banned_words: frozenset[str] = DEFAULT_BANNED_WORDS
    banned_phrases: tuple[str, ...] = DEFAULT_BANNED_PHRASES
    ban_dashes: bool = True
    never_claim: list[str] = field(default_factory=list)

    @property
    def resume_stem(self) -> str:
        return f"{self.file_stem}_Resume"

    @property
    def cover_stem(self) -> str:
        return f"{self.file_stem}_Cover_Letter"

    def contact_items(self) -> list[str]:
        """Contact details in display order. URLs are shown as visible text
        without the scheme, because a link's target is lost when an ATS
        extracts text (D-42)."""
        items = [self.email, self.phone, self.location]
        items += [display_url(u) for u in self.links]
        return [i for i in items if i]


def display_url(url: str) -> str:
    """`https://www.example.com/x/` -> `example.com/x`."""
    u = re.sub(r"^https?://", "", url.strip(), flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)
    return u.rstrip("/")


# Letters NFKD leaves whole, spelled the way their languages write them in
# plain Latin letters.
_UNDECOMPOSED = str.maketrans({
    "Ł": "L", "ł": "l", "Ø": "O", "ø": "o", "Đ": "D", "đ": "d", "Ð": "D", "ð": "d",
    "Ħ": "H", "ħ": "h", "ı": "i", "ß": "ss", "Æ": "AE", "æ": "ae", "Œ": "OE",
    "œ": "oe", "Þ": "Th", "þ": "th"})


def plain_letters(text: str) -> str:
    """Accents folded to plain letters: "Núñez" -> "Nunez", "Łódź" -> "Lodz"
    (D-52). File and folder names are ASCII because the resume's file name
    goes through ATS uploads, email, and zip tools that mangle anything else,
    and a recruiter sees the result. Letters with no Latin form are left as
    they are, for the caller to drop."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_UNDECOMPOSED))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def stem_from_name(name: str) -> str:
    parts = [re.sub(r"[^A-Za-z0-9-]", "", p) for p in plain_letters(name).split()]
    return "_".join(p for p in parts if p)


def _type_error(where: str, expected: str, got: object) -> str:
    return f"{where} should be {expected}, got {type(got).__name__} {got!r}"


def load_profile(ws: Workspace) -> Profile:
    path = ws.profile_path
    rel = ws.rel(path)
    if not path.exists():
        raise JobforgeError(f"{rel} is missing. Restore it from a backup, or "
                            f"start a new workspace with `jobforge init <folder>`.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as exc:
        raise JobforgeError(f"{rel} is not valid TOML: {exc}") from exc
    return profile_from_dict(data, rel)


def profile_from_dict(data: dict, rel: str = "profile.toml") -> Profile:
    errors: list[str] = []

    for section, body in data.items():
        if section not in _SECTIONS:
            errors.append(f"unknown section [{section}]; expected one of "
                          f"{sorted(_SECTIONS)}")
            continue
        if not isinstance(body, dict):
            errors.append(f"[{section}] should be a table")
            continue
        for key in body:
            if key not in _SECTIONS[section]:
                errors.append(f"[{section}] has unknown key {key!r}; expected "
                              f"one of {sorted(_SECTIONS[section])}")

    person = data.get("person", {}) if isinstance(data.get("person"), dict) else {}
    settings = data.get("settings", {}) if isinstance(data.get("settings"), dict) else {}
    voice = data.get("voice", {}) if isinstance(data.get("voice"), dict) else {}
    claims = data.get("claims", {}) if isinstance(data.get("claims"), dict) else {}

    def get_str(table: dict, section: str, key: str) -> str:
        v = table.get(key, "")
        if not isinstance(v, str):
            errors.append(_type_error(f"[{section}] {key}", "text in quotes", v))
            return ""
        return v.strip()

    def get_int(table: dict, section: str, key: str, default: int, lo: int, hi: int) -> int:
        v = table.get(key, default)
        if isinstance(v, bool) or not isinstance(v, int):
            errors.append(_type_error(f"[{section}] {key}", "a whole number", v))
            return default
        if not lo <= v <= hi:
            errors.append(f"[{section}] {key} should be between {lo} and {hi}, got {v}")
            return default
        return v

    def get_list(table: dict, section: str, key: str) -> list[str]:
        v = table.get(key, [])
        if not isinstance(v, list) or not all(isinstance(i, str) for i in v):
            errors.append(_type_error(f"[{section}] {key}", "a list of text items", v))
            return []
        return [i.strip() for i in v if i.strip()]

    name = get_str(person, "person", "name")
    if not name:
        errors.append("[person] name is empty. Set it to your name as it should "
                      "appear on your resume.")
    links = get_list(person, "person", "links")
    for link in links:
        if not re.match(r"^https?://[^\s/]+\.[^\s]+$", link):
            errors.append(f"[person] links: {link!r} is not a full http(s) URL")
    stem = get_str(person, "person", "file_stem") or stem_from_name(name)
    if name and not stem:
        errors.append("[person] name has no letters a file name can use (A-Z, 0-9), "
                      "so set the file name yourself under [person], in plain "
                      'letters: file_stem = "Li_Xiaolong" makes Li_Xiaolong_Resume.docx.')
    elif name and not re.fullmatch(r"[A-Za-z0-9_-]+", stem):
        errors.append(f"[person] file_stem {stem!r} may only use letters, digits, "
                      f"_ and -")

    ban_dashes = voice.get("ban_dashes", True)
    if not isinstance(ban_dashes, bool):
        errors.append(_type_error("[voice] ban_dashes", "true or false", ban_dashes))
        ban_dashes = True

    banned_words = set(DEFAULT_BANNED_WORDS)
    banned_words |= {w.lower() for w in get_list(voice, "voice", "add_banned_words")}
    banned_words -= {w.lower() for w in get_list(voice, "voice", "allow_words")}
    phrases = tuple(DEFAULT_BANNED_PHRASES) + tuple(
        p.lower() for p in get_list(voice, "voice", "add_banned_phrases"))

    profile = Profile(
        name=name,
        email=get_str(person, "person", "email"),
        phone=get_str(person, "person", "phone"),
        location=get_str(person, "person", "location"),
        links=links,
        file_stem=stem,
        page_limit=get_int(settings, "settings", "page_limit", 1, 1, 5),
        cover_letter_max_words=get_int(settings, "settings", "cover_letter_max_words", 300, 50, 1000),
        ghost_after_days=get_int(settings, "settings", "ghost_after_days", 30, 1, 365),
        banned_words=frozenset(banned_words),
        banned_phrases=phrases,
        ban_dashes=ban_dashes,
        never_claim=get_list(claims, "claims", "never_claim"),
    )
    if errors:
        raise JobforgeError(f"{rel} has problems:", errors)
    return profile
