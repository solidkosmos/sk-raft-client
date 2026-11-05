# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Open the SK-RAFT documentation in the web browser.

The script serves the documentation on this computer only (127.0.0.1)
with the web server of Python, and opens it in the default browser. It
does not use the network.

Use it when the browser cannot open index.html from the disk. This
occurs with Firefox and Chromium from Flatpak or Snap on Linux: the
sandbox gives the browser only the file that you open, and not the
other files of the documentation.

The script uses only the standard library. Stop it with Ctrl+C.

Usage:
    python open_docs.py [--port PORT] [--no-browser]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Sequence

# The directory of the documentation. It contains this script.
DOCS_DIR = Path(__file__).resolve().parent

# The address of the server. Only this computer can connect to it.
HOST = "127.0.0.1"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """A request handler that does not log each request."""

    # Give the correct types also on Windows, where the registry can
    # change them (for example, .js to text/plain). The base class
    # declares extensions_map the same way, so it is not a ClassVar.
    extensions_map = {  # noqa: RUF012
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".css": "text/css",
        ".html": "text/html",
        ".js": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def log_message(self, format: str, *args: object) -> None:
        """Do not log the requests."""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Serve the documentation until Ctrl+C.

    Parameters:
        argv (Optional[Sequence[str]]): The arguments. If None, use the
            arguments of the process.

    Returns:
        int: The exit code. 0 if the server stopped normally.
    """
    parser = argparse.ArgumentParser(
        description="Open the SK-RAFT documentation in the web browser.",
    )
    parser.add_argument(
        "--port", type=int, default=0,
        help="the port of the server. Default: a free port.",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="do not open the browser. Only print the address.",
    )
    args = parser.parse_args(argv)

    # The script must be in the folder of the built documentation. In
    # another folder, the server would only show a list of files.
    if not (DOCS_DIR / "index.html").is_file():
        print(
            f"Cannot open the documentation: {DOCS_DIR} has no index.html.\n"
            "Run this script from the folder of the built documentation, "
            "for example\napi/python/dist/docs after build_docs, or the "
            "folder of the extracted\nskraft-docs zip file.",
            file=sys.stderr,
        )
        return 1

    handler = functools.partial(QuietHandler, directory=str(DOCS_DIR))
    try:
        server = http.server.ThreadingHTTPServer((HOST, args.port), handler)
    except OSError as e:
        print(f"Cannot start the server on port {args.port}: {e}",
              file=sys.stderr)
        return 1

    with server:
        url = f"http://{HOST}:{server.server_address[1]}/"
        print(f"The documentation is at {url}", flush=True)
        print("Keep this window open while you read. Stop with Ctrl+C.",
              flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
