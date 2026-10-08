#!/usr/bin/env sh
# Unpack the prebuilt design files (bitstream, EBD, LL and XDC files).
# The ZIP file must be in the same directory as this script.
# The result is basys3/<top>/ and zedboard/<top>/ in this directory.
set -eu

cd "$(dirname "$0")"
ZIP="design_examples.zip"

if [ ! -f "$ZIP" ]; then
    echo "Error: $ZIP not found in $(pwd)" >&2
    exit 1
fi

if command -v unzip >/dev/null 2>&1; then
    unzip -o -q "$ZIP"
elif command -v python3 >/dev/null 2>&1; then
    python3 -m zipfile -e "$ZIP" .
else
    echo "Error: install unzip or python3 to extract $ZIP" >&2
    exit 1
fi

echo "Design files extracted to $(pwd)"
