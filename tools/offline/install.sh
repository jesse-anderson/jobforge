#!/bin/sh
# Install Jobforge {version} from this folder, without the internet (#163).
# Checks the wheel against SHA256SUMS first and stops if it does not match.
#
# Installs into its own environment, the way pipx would, but never goes
# online: pipx's first run downloads a newer pip for itself, which fails
# offline. The environment is ~/.local/share/jobforge/venv, and `jobforge` is
# linked into ~/.local/bin. Set PYTHON to use another Python 3.11+.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
python=${PYTHON:-python3}
dest="${XDG_DATA_HOME:-$HOME/.local/share}/jobforge"
bin="$HOME/.local/bin"

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

if ! "$python" -m venv --clear "$dest/venv"; then
    echo "error: could not make a Python environment in $dest/venv." >&2
    echo "On Ubuntu or Debian, Python's venv module is a separate package:" >&2
    echo "sudo apt install python3-venv, then run this script again." >&2
    exit 1
fi
"$dest/venv/bin/python" -m pip install --no-index --find-links "$here/wheels" jobforge
mkdir -p "$bin"
ln -sf "$dest/venv/bin/jobforge" "$bin/jobforge"

echo "Installed Jobforge {version} in $dest/venv, linked from $bin/jobforge."
case ":$PATH:" in
    *":$bin:"*) ;;
    *) echo "Add $bin to your PATH (or open a new terminal), then:" ;;
esac
echo "Next: jobforge init ~/jobsearch"
echo "To remove it: rm -r $dest $bin/jobforge"
