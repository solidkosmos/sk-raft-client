@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Install the SK-RAFT Python client (api\python) into a virtual
rem environment, .venv, in the examples folder (the folder above this one).
rem Do this one time, after the installation of SK-RAFT: double-click this
rem file. It needs Python 3.9 or a later version, and the internet (pip gets
rem grpcio and protobuf from the Python Package Index). Then double-click
rem open_terminal.bat to use the client. --no-pause: no pause at the end
rem (open_terminal.bat calls it so).
setlocal
set "NOPAUSE="
if /i "%~1"=="--no-pause" set "NOPAUSE=1"

cd /d "%~dp0.."
if errorlevel 1 (
    echo Error: cannot open the examples folder %~dp0..
    if not defined NOPAUSE pause
    exit /b 1
)
if not exist "api\python\pyproject.toml" (
    echo Error: there is no api\python in %CD%. This script must stay in the get_started folder of the SK-RAFT client, next to the api folder. Do not copy it to another place.
    if not defined NOPAUSE pause
    exit /b 1
)

rem The Python launcher py, else python.
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Error: Python is not installed. Install Python 3.9 or a later version from https://www.python.org/downloads/ and select "Add python.exe to PATH". Then run this script again.
    if not defined NOPAUSE pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Making the virtual environment %CD%\.venv ...
    %PY% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo Error: Python could not make the virtual environment .venv: its message is above. Install Python 3.9 or a later version from https://www.python.org/downloads/ and run this script again.
    if not defined NOPAUSE pause
    exit /b 1
)

echo Installing the SK-RAFT Python client from api\python ...
".venv\Scripts\python.exe" -m pip install "api\python"
if errorlevel 1 (
    echo.
    echo Error: pip could not install the client: its message is above. Make sure that this computer is connected to the internet, then run this script again. For a computer without internet access, read api\python\offline_bundle\README.md.
    if not defined NOPAUSE pause
    exit /b 1
)

echo.
echo The SK-RAFT Python client is installed.
echo To use it, double-click open_terminal.bat in the folder get_started.
echo.
if not defined NOPAUSE pause
exit /b 0
