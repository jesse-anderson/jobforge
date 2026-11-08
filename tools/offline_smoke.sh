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
printf 'x' >> "$work"/bad/wheels/*.whl
if sh "$work/bad/install.sh"; then
    echo "error: install.sh installed a wheel that does not match SHA256SUMS" >&2
    exit 1
fi

sudo unshare --net -- env PATH="$PATH" HOME="$HOME" \
    PIPX_HOME="$work/pipx" PIPX_BIN_DIR="$work/bin" sh -eu -c '
    if curl -sS --max-time 5 https://pypi.org >/dev/null 2>&1; then
        echo "error: the network is still reachable" >&2
        exit 1
    fi
    sh "$1/install.sh"
    "$2/bin/jobforge" --version
    "$2/bin/jobforge" init "$2/ws"
    test -f "$2/ws/CLAUDE.md"
' sh "$dir" "$work"
echo "offline install OK"
