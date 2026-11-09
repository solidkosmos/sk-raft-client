@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Build the documentation site of the SK-RAFT Python client.
rem
rem Usage: build_docs.bat
rem
rem The script keeps a virtual environment in .venv next to this script.
rem On the first run, it creates the environment and installs the
rem packages of requirements-docs.txt (this needs internet access). Then
rem it runs build_docs.py. build_docs.sh is the same script for Linux.
rem
rem The script creates the environment with the Python that the PYTHON
rem variable gives, else with the py launcher (py -3), else with python.
rem It must be Python 3.11 or later.

setlocal EnableExtensions
set "HERE=%~dp0"
set "VENV=%HERE%.venv"
set "VENV_PYTHON=%VENV%\Scripts\python.exe"

if exist "%VENV_PYTHON%" goto :install

set "PY="
set "PYARGS="
if defined PYTHON set "PY=%PYTHON%"
if not defined PY (
    where py >nul 2>nul && set "PY=py" && set "PYARGS=-3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Cannot build the documentation: Python 3 is not installed. 1>&2
    exit /b 1
)
"%PY%" %PYARGS% -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
    echo Cannot build the documentation: Python 3.11 or later is needed. 1>&2
    exit /b 1
)
echo Create the virtual environment %VENV%
"%PY%" %PYARGS% -m venv "%VENV%"
if errorlevel 1 exit /b 1

:install
rem pip does nothing (and does not use the network) when the packages are
rem already installed.
"%VENV_PYTHON%" -m pip install --quiet --disable-pip-version-check -r "%HERE%requirements-docs.txt"
if errorlevel 1 exit /b 1

"%VENV_PYTHON%" "%HERE%build_docs.py"
exit /b %ERRORLEVEL%
