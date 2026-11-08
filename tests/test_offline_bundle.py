"""#163: the offline install bundle. One zip per release with the wheel,
install scripts that check it before installing, and checksums; CI installs
it with the network off before anything is published."""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import REPO

_spec = importlib.util.spec_from_file_location("offline_bundle",
                                               REPO / "tools" / "offline_bundle.py")
ob = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ob)

VERSION = "0.1.0"
TOP = f"jobforge-offline-{VERSION}/"
WHEEL = f"jobforge-{VERSION}-py3-none-any.whl"
RELEASE = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
PR_FLOW = (REPO / ".github" / "workflows" / "offline-bundle.yml").read_text(encoding="utf-8")
SCRIPTS = REPO / "tools" / "offline"


def fake_wheel(dist: Path, name: str = WHEEL, requires: tuple[str, ...] = ()) -> Path:
    dist.mkdir(parents=True, exist_ok=True)
    meta = "Metadata-Version: 2.4\nName: jobforge\nVersion: 0.1.0\n"
    meta += "".join(f"Requires-Dist: {r}\n" for r in requires)
    path = dist / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("jobforge/__init__.py", '__version__ = "0.1.0"\n')
        zf.writestr("jobforge-0.1.0.dist-info/METADATA", meta)
    return path


@pytest.fixture
def built(tmp_path):
    wheel = fake_wheel(tmp_path / "dist")
    out = tmp_path / "bundle"
    return wheel, out, ob.build(tmp_path / "dist", out, VERSION)


# --- The zip ------------------------------------------------------------------

def test_bundle_holds_the_wheel_scripts_readme_and_checksums(built):
    wheel, _, path = built
    assert path.name == f"jobforge-offline-{VERSION}.zip"
    with zipfile.ZipFile(path) as zf:
        assert sorted(zf.namelist()) == sorted(TOP + n for n in [
            "wheels/" + WHEEL, "install.sh", "install.ps1", "README.md", "SHA256SUMS"])
        assert zf.read(TOP + "wheels/" + WHEEL) == wheel.read_bytes()
        sums = zf.read(TOP + "SHA256SUMS").decode("ascii")
        assert sums == f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  wheels/{WHEEL}\n"
        # install.sh keeps its executable bit; the rest do not get one.
        modes = {i.filename: i.external_attr >> 16 for i in zf.infolist()}
        assert modes[TOP + "install.sh"] == 0o755 and modes[TOP + "README.md"] == 0o644


def test_bundle_text_names_its_version_and_uses_lf(built):
    with zipfile.ZipFile(built[2]) as zf:
        for name in ("install.sh", "install.ps1", "README.md"):
            text = zf.read(TOP + name).decode("utf-8")
            assert "{version}" not in text and VERSION in text, name
            assert "\r" not in text, name  # "set -eu\r" would break sh


def test_release_assets_carry_the_zip_checksum(built):
    _, out, path = built
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert (out / "SHA256SUMS").read_bytes() == f"{digest}  {path.name}\n".encode("ascii")
    assert sorted(p.name for p in out.iterdir()) == ["SHA256SUMS", path.name]


def test_the_same_wheel_makes_the_same_zip(tmp_path, built):
    wheel, _, path = built
    again = ob.build(wheel.parent, tmp_path / "again", VERSION)
    assert again.read_bytes() == path.read_bytes()


@pytest.mark.parametrize("wheels,error", [
    ([], "found 0"),
    ([WHEEL, "jobforge-0.0.9-py3-none-any.whl"], "found 2"),
    (["jobforge-0.2.0-py3-none-any.whl"], f"expected {WHEEL}"),  # not the tagged version
])
def test_bundle_needs_exactly_the_version_wheel(tmp_path, wheels, error):
    (tmp_path / "dist").mkdir()
    for name in wheels:
        fake_wheel(tmp_path / "dist", name)
    with pytest.raises(ob.BundleError, match=error):
        ob.build(tmp_path / "dist", tmp_path / "out", VERSION)


def test_a_runtime_dependency_stops_the_bundle(tmp_path):
    # The bundle carries only Jobforge's wheel; a dependency would send pip
    # online. D-13 says there are none, so this fails loudly if that changes.
    fake_wheel(tmp_path / "dist", requires=("requests>=2", 'pytest>=8; extra == "dev"'))
    with pytest.raises(ob.BundleError, match="requests>=2") as e:
        ob.build(tmp_path / "dist", tmp_path / "out", VERSION)
    assert "pytest" not in str(e.value)  # extras are never installed


def test_dev_extras_are_not_runtime_dependencies(tmp_path):
    wheel = fake_wheel(tmp_path, requires=('pytest>=8; extra == "dev"',
                                           'coverage>=7 ; extra=="dev"'))
    assert ob.runtime_requirements(wheel) == []


def test_a_wheel_without_metadata_is_refused(tmp_path):
    path = tmp_path / WHEEL
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("jobforge/__init__.py", "")
    with pytest.raises(ob.BundleError, match="no METADATA"):
        ob.runtime_requirements(path)


def test_bundle_never_goes_into_dist(tmp_path):
    # The PyPI upload sends everything in dist/, zip included.
    fake_wheel(tmp_path / "dist")
    with pytest.raises(ob.BundleError, match="outside dist"):
        ob.build(tmp_path / "dist", tmp_path / "dist", VERSION)


def test_cli_exit_codes(tmp_path, capsys):
    fake_wheel(tmp_path / "dist")
    assert ob.main([str(tmp_path / "dist"), "--out", str(tmp_path / "b"),
                    "--version", VERSION]) == 0
    assert capsys.readouterr().out.strip().endswith(f"jobforge-offline-{VERSION}.zip")
    assert ob.main([str(tmp_path / "dist"), "--out", str(tmp_path / "c"),
                    "--version", "9.9.9"]) == 1
    assert "expected jobforge-9.9.9" in capsys.readouterr().err
    assert ob.main([]) == 2


def test_cli_reads_the_package_version_by_default(tmp_path, capsys):
    version = __import__("jobforge").__version__
    fake_wheel(tmp_path / "dist", f"jobforge-{version}-py3-none-any.whl")
    assert ob.main([str(tmp_path / "dist"), "--out", str(tmp_path / "b")]) == 0
    assert f"jobforge-offline-{version}.zip" in capsys.readouterr().out


# --- The install scripts, run for real against stand-ins for pip and pipx -----

def _unzip(path: Path, dest: Path) -> Path:
    with zipfile.ZipFile(path) as zf:
        zf.extractall(dest)
    return dest / TOP.rstrip("/")


def _tamper(folder: Path) -> None:
    with open(folder / "wheels" / WHEEL, "ab") as f:
        f.write(b"x")


SH = shutil.which("sh")
HASHER = shutil.which("sha256sum") or shutil.which("shasum")
needs_sh = pytest.mark.skipif(not (SH and HASHER), reason="needs sh and sha256sum")


def _run_sh(folder: Path, tmp_path: Path, stub: str) -> tuple[int, str]:
    """Run install.sh with only the system tools it needs on PATH, plus a
    stand-in `stub` (pipx or python3) that records how it was called."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "calls.txt"
    script = bin_dir / stub
    script.write_text(f'#!/bin/sh\necho "$@" >> "{log.as_posix()}"\n', newline="\n")
    script.chmod(0o755)
    system = {str(Path(shutil.which(t)).parent) for t in ("sh", "dirname")
              if shutil.which(t)} | {str(Path(HASHER).parent)}
    # install.sh prefers pipx, so the pip path is testable only without one.
    if stub == "python3" and any(Path(d, "pipx").exists() for d in system):
        pytest.skip("a real pipx sits beside the system tools")
    env = {**os.environ, "PATH": os.pathsep.join([str(bin_dir), *sorted(system)])}
    proc = subprocess.run([SH, str(folder / "install.sh")], env=env, capture_output=True,
                          text=True)
    return proc.returncode, log.read_text() if log.exists() else ""


@needs_sh
def test_install_sh_checks_then_installs_with_pipx_offline(tmp_path, built):
    folder = _unzip(built[2], tmp_path / "x")
    code, calls = _run_sh(folder, tmp_path, "pipx")
    assert code == 0
    assert calls.startswith("install --force --pip-args=--no-index --find-links ")
    assert calls.strip().endswith(WHEEL)


@needs_sh
def test_install_sh_falls_back_to_pip_offline(tmp_path, built):
    folder = _unzip(built[2], tmp_path / "x")
    code, calls = _run_sh(folder, tmp_path, "python3")
    assert code == 0
    assert calls.startswith("-m pip install --upgrade --no-index --find-links ")
    assert calls.strip().endswith(" jobforge")


@needs_sh
def test_install_sh_refuses_a_changed_wheel(tmp_path, built):
    folder = _unzip(built[2], tmp_path / "x")
    _tamper(folder)
    code, calls = _run_sh(folder, tmp_path, "pipx")
    assert code != 0 and calls == ""  # nothing installed


POWERSHELL = shutil.which("powershell")
needs_ps = pytest.mark.skipif(not POWERSHELL, reason="needs Windows PowerShell")


def _run_ps(folder: Path, tmp_path: Path) -> tuple[int, str, str]:
    log = tmp_path / "calls.txt"
    fake = tmp_path / "python.cmd"
    fake.write_text(f'@echo %* >> "{log}"\r\n', encoding="ascii")
    proc = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                           str(folder / "install.ps1"), "-Python", str(fake)],
                          capture_output=True, text=True)
    return proc.returncode, log.read_text() if log.exists() else "", proc.stdout


@needs_ps
def test_install_ps1_checks_then_installs_offline(tmp_path, built):
    folder = _unzip(built[2], tmp_path / "x")
    code, calls, out = _run_ps(folder, tmp_path)
    assert code == 0, out
    assert f"wheels/{WHEEL}: OK" in out
    assert calls.startswith("-m pip install --upgrade --no-index --find-links ")
    assert calls.strip().endswith(" jobforge")


@needs_ps
@pytest.mark.parametrize("damage", ["tamper", "missing", "empty"])
def test_install_ps1_refuses_a_damaged_bundle(tmp_path, built, damage):
    folder = _unzip(built[2], tmp_path / "x")
    if damage == "tamper":
        _tamper(folder)
    elif damage == "missing":
        (folder / "wheels" / WHEEL).unlink()
    else:
        (folder / "SHA256SUMS").write_text("\n")
    code, calls, out = _run_ps(folder, tmp_path)
    assert code == 1 and calls == "", out


def test_scripts_check_the_checksums_before_installing():
    sh = (SCRIPTS / "install.sh").read_text(encoding="utf-8")
    assert sh.index("-c SHA256SUMS") < sh.index("pipx install") < sh.index("python3 -m pip")
    ps = (SCRIPTS / "install.ps1").read_text(encoding="utf-8")
    assert ps.index("Get-FileHash") < ps.index("-m pip install")
    for text in (sh, ps):
        assert "--no-index --find-links" in text


def test_scripts_are_ascii_for_windows_powershell():
    # PowerShell 5.1 reads a script without a BOM in the ANSI code page.
    for name in ("install.ps1", "install.sh", "README.md"):
        assert (SCRIPTS / name).read_text(encoding="utf-8").isascii(), name
    assert (REPO / "tools" / "offline_smoke.ps1").read_text(encoding="utf-8").isascii()


# --- CI: nothing is published until the bundle installs with the network off --

def _job(name: str) -> str:
    """One job of release.yml: jobs are separated by a blank line."""
    return RELEASE.split(f"\n  {name}:\n", 1)[1].split("\n\n  ", 1)[0]


def test_release_builds_the_bundle_from_the_tested_wheel_outside_dist():
    build = _job("build")
    step = "python tools/offline_bundle.py dist --out bundle"
    assert build.index("/tmp/smoke/bin/jobforge init") < build.index(step)
    assert "name: offline\n          path: bundle/" in build


def test_release_installs_the_bundle_offline_on_both_systems():
    offline = _job("offline")
    assert "needs: build" in offline and "os: [ubuntu-latest, windows-latest]" in offline
    assert "name: offline" in offline
    assert "sh tools/offline_smoke.sh" in offline and r"tools\offline_smoke.ps1" in offline


def test_no_upload_until_the_offline_install_passed():
    assert "needs: [build, windows, offline]" in _job("testpypi")
    pypi = _job("pypi")
    assert "needs: [build, windows, offline, testpypi]" in pypi
    assert "needs.offline.result == 'success'" in pypi


def test_github_release_follows_pypi_with_only_the_bundle():
    job = _job("github-release")
    assert "needs: [build, pypi]" in job and "needs.pypi.result == 'success'" in job
    assert "contents: write" in job and "--verify-tag" in job
    assert "bundle/jobforge-offline-*.zip bundle/SHA256SUMS" in job
    assert "'--prerelease'" in job and "'both'" in job
    # Only this job may write to the repo.
    assert RELEASE.count("contents: write") == 1
    assert "secrets." not in RELEASE


def test_pr_workflow_runs_the_same_checks_by_hand_or_when_the_bundle_changes():
    on = PR_FLOW.split("\non:", 1)[1].split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in on and "push:" not in on and "schedule" not in on
    for path in ("tools/offline_bundle.py", "tools/offline/**", "tools/offline_smoke.sh",
                 "tools/offline_smoke.ps1", ".github/workflows/release.yml"):
        assert path in on, path
    for cmd in ("python tools/offline_bundle.py dist --out bundle",
                "sh tools/offline_smoke.sh bundle/jobforge-offline-*.zip",
                r"tools\offline_smoke.ps1 -Zip (Get-ChildItem bundle\*.zip)[0].FullName"):
        assert cmd in PR_FLOW and cmd in RELEASE, cmd
    assert "git commit" not in PR_FLOW and "git push" not in PR_FLOW


def test_smoke_scripts_cut_the_network_and_try_a_changed_wheel():
    sh = (REPO / "tools" / "offline_smoke.sh").read_text(encoding="utf-8")
    assert "unshare --net" in sh and "the network is still reachable" in sh
    assert sh.index("printf 'x' >>") < sh.index("unshare --net")
    ps = (REPO / "tools" / "offline_smoke.ps1").read_text(encoding="utf-8")
    assert "PIP_INDEX_URL" in ps and ps.index('Add-Content $wheel "x"') < ps.index("PIP_INDEX_URL")
    for text in (sh, ps):
        assert "--version" in text and "init" in text and "CLAUDE.md" in text


# --- Docs ---------------------------------------------------------------------

def test_readme_documents_the_offline_install():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    setup = readme.split("## Set up (once)", 1)[1].split("\n## ", 1)[0]
    for needle in ("jobforge-offline-X.Y.Z.zip", "SHA256SUMS", "sh install.sh", "install.ps1",
                   "python -m pip install --no-index --find-links ./wheels jobforge",
                   "https://github.com/jesse-anderson/jobforge/releases"):
        assert needle in setup, needle
    bundled = (SCRIPTS / "README.md").read_text(encoding="utf-8")
    assert "python -m pip install --no-index --find-links ./wheels jobforge" in bundled
    assert "Python\n3.11 or newer" in bundled


def test_maintaining_describes_the_bundle_in_the_release_steps():
    text = (REPO / "docs" / "MAINTAINING.md").read_text(encoding="utf-8")
    steps = " ".join(text.split("## Releasing", 1)[1].split("\n## ", 1)[0].split())
    for needle in ("tools/offline_bundle.py", "network off", "github-release",
                   "jobforge-offline-X.Y.Z.zip"):
        assert needle in steps, needle
