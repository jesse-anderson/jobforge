"""The release path (#54): only a version tag publishes, every upload waits
for a maintainer, no token is stored, and only a final version that matches
the tag reaches PyPI (a PyPI version can never be reused)."""
import importlib.util

import pytest

from conftest import REPO

WORKFLOW = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


def _tool():
    spec = importlib.util.spec_from_file_location("release_check",
                                                  REPO / "tools" / "release_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_runs_only_on_version_tags():
    on = WORKFLOW.split("\non:", 1)[1].split("\njobs:", 1)[0]
    assert 'tags: ["v*"]' in on
    for trigger in ("branches", "pull_request", "workflow_dispatch", "schedule"):
        assert trigger not in on, trigger


def test_every_upload_waits_in_an_environment_and_uses_trusted_publishing():
    for job in ("testpypi", "pypi"):
        header = WORKFLOW.split(f"\n  {job}:\n", 1)[1].split("steps:", 1)[0]
        assert f"name: {job}" in header
        assert "id-token: write" in header
    assert "password" not in WORKFLOW and "secrets." not in WORKFLOW


def test_build_checks_the_tag_and_tests_before_building():
    build = WORKFLOW.split("\n  build:\n", 1)[1].split("\n  testpypi:\n", 1)[0]
    order = [build.index(s) for s in ("tools/release_check.py", "pytest", "python -m build",
                                      "twine check", "jobforge --version")]
    assert order == sorted(order)


def test_package_version_is_read_from_the_package():
    assert _tool().package_version() == __import__("jobforge").__version__


@pytest.mark.parametrize("tag,version,test,ok", [
    ("v0.1.0", "0.1.0", False, True),
    ("v0.1.0", "0.1.1", False, False),        # tag and version disagree
    ("v0.1.0.dev0", "0.1.0.dev0", False, False),  # never a dev build to PyPI
    ("v0.1.0rc1", "0.1.0rc1", False, True),   # a pre-release may reach PyPI
    ("v0.1.0b2", "0.1.0b2", False, True),
    ("v0.1.0.dev1", "0.1.0.dev1", False, False),  # never a dev build to PyPI
    ("v0.1.0rc", "0.1.0rc", False, False),    # a pre-release needs its number
    ("v0.1.0rc1", "0.1.0rc1", True, True),
    ("v0.1.0.dev0", "0.1.0.dev0", True, True),
    ("0.1.0", "0.1.0", True, False),          # the tag needs its "v"
])
def test_release_check(tag, version, test, ok):
    assert (_tool().problems(tag, version, test=test) == []) is ok


def test_release_check_cli_exit_codes(capsys):
    tool = _tool()
    v = tool.package_version()
    assert tool.main([f"v{v}", "--test"]) == 0
    assert tool.main(["v9.9.9"]) == 1
    assert "does not match" in capsys.readouterr().err
    assert tool.main([]) == 2


def test_a_pre_release_reaches_pypi_only_after_testpypi():
    pypi = WORKFLOW.split("\n  pypi:\n", 1)[1].split("steps:", 1)[0]
    assert "needs: [build, testpypi]" in pypi
    assert "needs.testpypi.result == 'success'" in pypi
    assert "needs.build.outputs.target == 'pypi'" in pypi  # finals skip TestPyPI
    testpypi = WORKFLOW.split("\n  testpypi:\n", 1)[1].split("steps:", 1)[0]
    assert "'both'" in testpypi and "'testpypi'" in testpypi
