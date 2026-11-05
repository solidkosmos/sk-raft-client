#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Build the documentation site of the SK-RAFT Python client.
#
# Usage: ./build_docs.sh
#
# The script keeps a virtual environment in .venv next to this script. On
# the first run, it creates the environment and installs the packages of
# requirements-docs.txt (this needs internet access). Then it runs
# build_docs.py. build_docs.bat is the same script for Windows.
#
# The script creates the environment with the Python that the PYTHON
# variable gives, else with python3. It must be Python 3.11 or later.

set -eu

here=$(cd "$(dirname "$0")" && pwd)
venv="$here/.venv"
python="$venv/bin/python"

if [ ! -x "$python" ]; then
    base=${PYTHON:-python3}
    if ! command -v "$base" >/dev/null 2>&1; then
        echo "Cannot build the documentation: $base is not installed." >&2
        exit 1
    fi
    if ! "$base" -c "import sys; sys.exit(sys.version_info < (3, 11))"
    then
        echo "Cannot build the documentation: $base is older than" \
            "Python 3.11." >&2
        exit 1
    fi
    echo "Create the virtual environment $venv"
    "$base" -m venv "$venv"
fi

# pip does nothing (and does not use the network) when the packages are
# already installed.
"$python" -m pip install --quiet --disable-pip-version-check \
    -r "$here/requirements-docs.txt"

"$python" "$here/build_docs.py"
