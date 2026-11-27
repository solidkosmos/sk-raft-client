@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Install JupyterLab into the virtual environment of the SK-RAFT Python
rem client, .venv, in the examples folder (the folder above this one). When
rem .venv does not exist, install_client.bat makes it first, with the client.
rem sk-raft -j (or --jupyter) runs this script when .venv has no JupyterLab,
rem then starts JupyterLab from .venv. It needs the internet (pip gets
rem JupyterLab from the Python Package Index). --no-pause: no pause at the
rem end (sk-raft calls it so).
setlocal
set "NOPAUSE="
if /i "%~1"=="--no-pause" set "NOPAUSE=1"

cd /d "%~dp0.."
if errorlevel 1 (
    echo Error: cannot open the examples folder %~dp0..
    if not defined NOPAUSE pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" call "%~dp0install_client.bat" --no-pause
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Error: the SK-RAFT Python client is not installed: see the messages above.
    if not defined NOPAUSE pause
    exit /b 1
)

echo Installing JupyterLab into %CD%\.venv ...
".venv\Scripts\python.exe" -m pip install jupyterlab
if errorlevel 1 (
    echo.
    echo Error: pip could not install JupyterLab: its message is above. Make sure that this computer is connected to the internet, then run this script again.
    if not defined NOPAUSE pause
    exit /b 1
)

echo.
echo JupyterLab is installed. To start it, type: sk-raft -j
echo.
if not defined NOPAUSE pause
exit /b 0

