#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Install the SK-RAFT Python client (api/python) into a virtual environment,
# .venv, in the examples folder (the folder above this one). Do this one time,
# after the installation of SK-RAFT. In the examples folder, type:
#
#   sh get_started/install_client.sh
#
# It needs Python 3.9 or a later version with its venv module, and the
# internet (pip gets grpcio and protobuf from the Python Package Index). Then
# type sh get_started/open_terminal.sh to use the client.
set -u

cd "$(dirname "$0")/.." || exit 1
here=$(pwd)
if [ ! -f api/python/pyproject.toml ]; then
    echo "Error: there is no api/python in $here. This script must stay in" \
        "the get_started folder of the SK-RAFT client, next to the api" \
        "folder. Do not copy it to another place." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed. Install Python 3.9 or a later" \
        "version (Ubuntu: sudo apt install python3 python3-venv)." >&2
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    existed=
    [ -e .venv ] && existed=1
    echo "Making the virtual environment $here/.venv ..."
    if ! python3 -m venv .venv; then
        # Remove only a .venv that this script made.
        [ -z "$existed" ] && rm -rf .venv
        echo "Error: python3 could not make the virtual environment: its" \
            "message is above. On Ubuntu and Debian, install its venv module:" \
            "sudo apt install python3-venv" >&2
        exit 1
    fi
fi

echo "Installing the SK-RAFT Python client from api/python ..."
if ! .venv/bin/python -m pip install api/python; then
    echo "" >&2
    echo "Error: pip could not install the client: its message is above." \
        "Make sure that this computer is connected to the internet, then run" \
        "this script again. For a computer without internet access, read" \
        "api/python/offline_bundle/README.md." >&2
    exit 1
fi

echo ""
echo "The SK-RAFT Python client is installed."
echo "To use it, type: sh \"$here/get_started/open_terminal.sh\""
