SK-RAFT Python client: offline installation bundle
===================================================

This bundle installs the SK-RAFT Python client (skraft) and its
dependencies on a computer that has no internet access. bundle.json tells
which platforms and Python versions the bundle supports.

Requirements
------------
- Python 3 of a version that bundle.json gives.
- On Debian and Ubuntu: the python3-venv package.

Install
-------
Linux:

    ./install.sh

Windows (double-click install.bat, or run it in a command prompt):

    install.bat

The installer does not use the network. It installs into:

- the active virtual environment, if one is active, or
- the virtual environment that --venv PATH gives, or
- .venv in the current directory.

The installer creates the virtual environment if it does not exist.

Then activate the virtual environment and use the client:

    source .venv/bin/activate        (Linux)
    .venv\Scripts\activate           (Windows)
    python -c "import skraft"
