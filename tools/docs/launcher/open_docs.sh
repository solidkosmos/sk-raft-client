#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Open the SK-RAFT documentation in the web browser, through a server on
# this computer only. See README.txt. Stop it with Ctrl+C.
#
# Usage: ./open_docs.sh [--port PORT] [--no-browser]

here=$(cd "$(dirname "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
    python=python3
elif command -v python >/dev/null 2>&1; then
    python=python
else
    echo "Cannot open the documentation: Python 3 is not installed." >&2
    echo "Open index.html in the browser instead. See README.txt." >&2
    exit 1
fi

exec "$python" "$here/open_docs.py" "$@"
