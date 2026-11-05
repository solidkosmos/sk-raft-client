SK-RAFT documentation
=====================

This folder contains the documentation of the SK-RAFT Python client, as a
website. It does not need the internet.


Open the documentation
----------------------

Usually, open index.html in a web browser (double-click it).

If the pages show no styles, or the links and the search do not work, the
browser cannot read the other files of this folder. This occurs on Linux
with browsers from Flatpak or Snap, for example the Firefox of Ubuntu
(Snap) and the Firefox of Fedora Silverblue (Flatpak). The sandbox of the
browser gives it only the file that you open.

Then start the documentation server:

    Linux:    ./open_docs.sh
    Windows:  open_docs.bat (double-click it)
    Other:    python3 open_docs.py

The server uses Python, and only this computer can connect to it. It opens
the documentation in the default browser. Keep its window open while you
read. Stop it with Ctrl+C.

Options:

    --no-browser   Do not open the browser. Only print the address.
    --port PORT    Use this port. The default is a free port.


If you cannot use the server
----------------------------

Give the browser access to this folder. Then type the address of
index.html in the address bar. Do not double-click it.

Firefox from Flatpak:

    flatpak override --user --filesystem=/path/to/this/folder:ro \
        org.mozilla.firefox

    Then restart Firefox and open file:///path/to/this/folder/index.html

    You can also give the access with the Flatseal application.

Any sandboxed browser: most of them can read the Downloads folder. Put
this folder in Downloads, and open
file:///home/<user>/Downloads/<this folder>/index.html
