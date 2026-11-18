#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Open a shell in the examples folder, with the SK-RAFT Python client ready
# (its virtual environment .venv active). In a terminal, type:
#
#   sh get_started/open_terminal.sh
#
# Type exit to leave it. When the client is not installed yet,
# install_client.sh installs it first.
set -u

cd "$(dirname "$0")/.." || exit 1
here=$(pwd)
if [ ! -f .venv/bin/activate ]; then
    sh get_started/install_client.sh || exit 1
    echo ""
fi

ready="The SK-RAFT Python client is ready. For example: python get_started/list_devices.py"
if command -v bash >/dev/null 2>&1; then
    # bash with the usual ~/.bashrc, then the client; the start file
    # removes itself.
    rc=$(mktemp) || exit 1
    cat > "$rc" <<EOF
[ -f "\$HOME/.bashrc" ] && . "\$HOME/.bashrc"
cd "$here" && . .venv/bin/activate
rm -f "$rc"
echo "$ready"
echo "Type exit to leave."
EOF
    exec bash --rcfile "$rc" -i
fi

# Without bash: the shell of the user, with the client first on its PATH.
. .venv/bin/activate
echo "$ready"
echo "Type exit to leave."
exec "${SHELL:-/bin/sh}" -i
