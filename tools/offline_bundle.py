"""Build the offline install bundle for a release (#163): the release's wheel,
install scripts that check it before installing, and a checksum manifest,
in one zip a user or an agent can install from without reaching PyPI.

    python tools/offline_bundle.py dist --out bundle

Writes into `--out` (never into `dist/`, which the PyPI upload sends whole):

    jobforge-offline-X.Y.Z.zip   the bundle
    SHA256SUMS                   the zip's checksum, for the GitHub Release

The zip holds one folder, jobforge-offline-X.Y.Z/, with wheels/, install.sh,
install.ps1, README.md, and SHA256SUMS for the wheels. The same wheel always
gives byte-for-byte the same zip.

Exit 0 on success, 1 when the bundle cannot be built (the reason goes to
stderr), 2 on bad arguments."""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "tools" / "offline"
FILES = ["install.sh", "install.ps1", "README.md"]
# A fixed date, so the same wheel always makes the same zip.
_STAMP = (2020, 1, 1, 0, 0, 0)


class BundleError(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_wheel(dist: Path, version: str) -> Path:
    """The one Jobforge wheel for `version` in `dist`."""
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise BundleError(f"Expected one wheel in {dist}, found {len(wheels)}.")
    expected = f"jobforge-{version}-py3-none-any.whl"
    if wheels[0].name != expected:
        raise BundleError(f"Found {wheels[0].name}, expected {expected}.")
    return wheels[0]


def runtime_requirements(wheel: Path) -> list[str]:
    """Requires-Dist lines a plain install would fetch. Extras ("dev") are
    not installed, so they do not count."""
    with zipfile.ZipFile(wheel) as zf:
        names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise BundleError(f"{wheel.name} has no METADATA.")
        meta = Parser().parsestr(zf.read(names[0]).decode("utf-8"))
    return [r for r in meta.get_all("Requires-Dist") or []
            if not re.search(r"\bextra\s*==", r)]


def _add(zf: zipfile.ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name, date_time=_STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o755 if executable else 0o644) << 16
    zf.writestr(info, data)


def bundle_bytes(wheel: Path, version: str) -> bytes:
    """The zip, in memory. Refuses a wheel with runtime dependencies: the
    bundle carries only the Jobforge wheel, so pip would go online for them."""
    deps = runtime_requirements(wheel)
    if deps:
        raise BundleError("The wheel needs " + ", ".join(deps) + "; the offline bundle "
                          "would have to carry their wheels too (D-13 says none).")
    top = f"jobforge-offline-{version}/"
    data = wheel.read_bytes()
    sums = f"{sha256(data)}  wheels/{wheel.name}\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        _add(zf, top + "wheels/" + wheel.name, data)
        for name in FILES:
            text = (TEMPLATES / name).read_text(encoding="utf-8").replace("{version}", version)
            _add(zf, top + name, text.encode("utf-8"), executable=name.endswith(".sh"))
        _add(zf, top + "SHA256SUMS", sums.encode("ascii"))
    return buf.getvalue()


def build(dist: Path, out: Path, version: str) -> Path:
    if out.resolve() == dist.resolve():
        raise BundleError("Write the bundle outside dist/: the PyPI upload sends all of dist/.")
    data = bundle_bytes(find_wheel(dist, version), version)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"jobforge-offline-{version}.zip"
    zip_path.write_bytes(data)
    (out / "SHA256SUMS").write_text(f"{sha256(data)}  {zip_path.name}\n", encoding="ascii",
                                    newline="\n")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the offline install bundle (#163).")
    p.add_argument("dist", type=Path, help="folder holding the built wheel")
    p.add_argument("--out", type=Path, required=True, help="folder to write the bundle into")
    p.add_argument("--version", help="package version (default: __version__)")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.version is None:
        sys.path.insert(0, str(ROOT / "tools"))
        from release_check import package_version
        args.version = package_version()
    try:
        path = build(args.dist, args.out, args.version)
    except BundleError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
