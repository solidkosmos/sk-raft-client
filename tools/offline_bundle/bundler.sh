#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Make an offline installation bundle of the SK-RAFT Python client.
# Run this script on a computer that has internet access.
#
# Usage: ./bundler.sh [options of make_bundle.py]
#
# Without options, the bundle is for Linux x86_64 and Windows amd64, and
# for the Python version that runs the bundler. With options, the script
# gives them to make_bundle.py as they are. For the options, run:
# ./bundler.sh --help
#
# bundler.bat is the same script for Windows.
#
# The script uses the first Python that it finds:
#   1. the Python that the PYTHON variable gives,
#   2. the Python of the active virtual environment,
#   3. the Python of .venv in this repository,
#   4. python3.
# If that Python has no pip, the script creates a temporary virtual
# environment and deletes it at the end.

set -eu

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
bundler="$here/make_bundle.py"

if [ -n "${PYTHON:-}" ]; then
    python=$PYTHON
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    python=$VIRTUAL_ENV/bin/python
elif [ -x "$root/.venv/bin/python" ]; then
    python=$root/.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
    python=python3
else
    echo "Cannot make the bundle: Python 3 is not installed." >&2
    exit 1
fi

tmp_venv=""
cleanup() {
    if [ -n "$tmp_venv" ]; then
        rm -rf "$tmp_venv"
    fi
}
trap cleanup EXIT INT TERM

if ! "$python" -m pip --version >/dev/null 2>&1; then
    tmp_venv=$(mktemp -d)
    echo "$python has no pip. Create a temporary virtual environment."
    if ! "$python" -m venv "$tmp_venv"; then
        echo "Cannot make the bundle: cannot create a virtual" \
            "environment with $python." >&2
        exit 1
    fi
    python=$tmp_venv/bin/python
fi

if [ "$#" -eq 0 ]; then
    set -- --target linux-x86_64 --target windows-amd64
fi

"$python" "$bundler" "$@"
