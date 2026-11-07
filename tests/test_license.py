"""The license ships, unaltered, with its Required Notice (D-39)."""
import hashlib
import tomllib

from conftest import REPO

# SHA-256 of PolyForm-Noncommercial-1.0.0.md from
# github.com/polyformproject/polyform-licenses at tag 1.0.0. The license
# text must stay word for word; only the Required Notice line above it is ours.
OFFICIAL_SHA256 = "c0ea4a896d2c8c394b29f9427589996db826cd501c512279ff0ed3ef48fabbe5"
NOTICE = "Required Notice: Copyright 2026 Jesse Anderson and Mike Wilson"


def _license_text() -> str:
    # newline="" keeps the bytes as checked out; normalize Windows line ends.
    with open(REPO / "LICENSE", encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def test_license_starts_with_the_required_notice():
    first, blank, *_ = _license_text().split("\n")
    assert first == NOTICE
    assert blank == ""


def test_license_text_is_the_official_polyform_noncommercial_text():
    body = _license_text().split("\n", 2)[2]
    assert body.startswith("# PolyForm Noncommercial License 1.0.0\n")
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == OFFICIAL_SHA256


def test_package_metadata_names_and_ships_the_license():
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "LicenseRef-PolyForm-Noncommercial-1.0.0"
    assert project["license-files"] == ["LICENSE"]


def test_readme_links_to_the_license():
    assert "](LICENSE)" in (REPO / "README.md").read_text(encoding="utf-8")
