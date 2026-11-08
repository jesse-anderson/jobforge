#!/bin/sh
# Install Jobforge {version} from this folder, without the internet (#163).
# Checks the wheel against SHA256SUMS first and stops if it does not match.
# Uses pipx when it is installed (Ubuntu, Debian, and others block pip for
# the system Python), and pip otherwise.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"

if command -v sha256sum >/dev/null 2>&1; then
    check="sha256sum -c SHA256SUMS"
elif command -v shasum >/dev/null 2>&1; then
    check="shasum -a 256 -c SHA256SUMS"
else
    echo "error: no sha256sum or shasum to check the download with; not installing." >&2
    exit 1
fi
if ! $check; then
    echo "error: a file does not match SHA256SUMS; the bundle is damaged or was changed." >&2
    echo "Download it again from https://github.com/jesse-anderson/jobforge/releases" >&2
    exit 1
fi

wheel="$here/wheels/jobforge-{version}-py3-none-any.whl"
if command -v pipx >/dev/null 2>&1; then
    # pipx splits --pip-args like a shell, so the path is quoted inside it.
    pipx install --force --pip-args="--no-index --find-links '$here/wheels'" "$wheel"
elif python3 -m pip install --upgrade --no-index --find-links "$here/wheels" jobforge; then
    :
else
    echo "error: pip could not install here. On Ubuntu or Debian, install pipx" >&2
    echo "(sudo apt install pipx), then run this script again." >&2
    exit 1
fi
echo "Installed Jobforge {version}. Next: jobforge init ~/jobsearch"
