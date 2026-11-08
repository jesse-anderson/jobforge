#!/bin/sh
# Install the offline bundle (#163) on Linux with the network cut off, the
# way a user would: check the zip, unzip it, run install.sh, use jobforge.
# Also checks that install.sh refuses a changed wheel. Needs sudo for the
# network namespace, so it is for CI runners, not users.
#   sh tools/offline_smoke.sh bundle/jobforge-offline-X.Y.Z.zip
set -eu
zip=$(realpath "$1")
work=$(mktemp -d)

(cd "$(dirname "$zip")" && sha256sum -c SHA256SUMS)
python3 -m zipfile -e "$zip" "$work/good"
dir=$(ls -d "$work"/good/jobforge-offline-*)

# A changed wheel must stop install.sh before anything is installed.
cp -r "$dir" "$work/bad"
# A loop: sh does not expand a wildcard in a redirection target.
for whl in "$work"/bad/wheels/*.whl; do printf 'x' >> "$whl"; done
if HOME="$work/home" sh "$work/bad/install.sh"; then
    echo "error: install.sh installed a wheel that does not match SHA256SUMS" >&2
    exit 1
fi
test ! -e "$work/home/.local"  # nothing was installed

# A fresh home, as on a new machine; nothing of the runner's is used.
sudo unshare --net -- env PATH="$PATH" HOME="$work/home" sh -eu -c '
    if curl -sS --max-time 5 https://pypi.org >/dev/null 2>&1; then
        echo "error: the network is still reachable" >&2
        exit 1
    fi
    sh "$1/install.sh"
    "$HOME/.local/bin/jobforge" --version
    "$HOME/.local/bin/jobforge" init "$2/ws"
    test -f "$2/ws/CLAUDE.md"
' sh "$dir" "$work"
echo "offline install OK"
