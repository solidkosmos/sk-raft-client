#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Install JupyterLab into the virtual environment of the SK-RAFT Python
# client, .venv, in the examples folder (the folder above this one). When
# .venv does not exist, install_client.sh makes it first, with the client.
# sk-raft -j (or --jupyter) runs this script when .venv has no JupyterLab,
# then starts JupyterLab from .venv. To run it yourself, in the examples
# folder, type:
#
#   sh get_started/install_jupyter.sh
#
# It needs the internet (pip gets JupyterLab from the Python Package Index).
set -u

cd "$(dirname "$0")/.." || exit 1
here=$(pwd)

if [ ! -x .venv/bin/python ]; then
    sh get_started/install_client.sh || exit 1
    echo ""
fi

echo "Installing JupyterLab into $here/.venv ..."
if ! .venv/bin/python -m pip install jupyterlab; then
    echo "" >&2
    echo "Error: pip could not install JupyterLab: its message is above." \
        "Make sure that this computer is connected to the internet, then run" \
        "this script again." >&2
    exit 1
fi

echo ""
echo "JupyterLab is installed. To start it, type: sk-raft -j"
