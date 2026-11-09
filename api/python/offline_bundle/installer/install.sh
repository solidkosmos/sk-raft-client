#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Install the SK-RAFT Python client from this offline bundle.
# Usage: ./install.sh [--venv PATH]
# Set PYTHON to use a specific interpreter, for example
# PYTHON=python3.11 ./install.sh

here=$(cd "$(dirname "$0")" && pwd)

if [ -n "$PYTHON" ]; then
    python=$PYTHON
elif command -v python3 >/dev/null 2>&1; then
    python=python3
elif command -v python >/dev/null 2>&1; then
    python=python
else
    echo "Cannot install: Python 3 is not installed." >&2
    exit 1
fi

exec "$python" "$here/install.py" "$@"
