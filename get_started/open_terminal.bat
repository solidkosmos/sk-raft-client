@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Open a Command Prompt in the examples folder, with the SK-RAFT Python
rem client ready (its virtual environment .venv active). Double-click this
rem file. When the client is not installed yet, install_client.bat installs
rem it first.
cd /d "%~dp0.."
if errorlevel 1 (
    echo Error: cannot open the examples folder %~dp0..
    pause
    exit /b 1
)
if not exist ".venv\Scripts\activate.bat" call "%~dp0install_client.bat" --no-pause
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo The SK-RAFT Python client is not installed: see the messages above.
    pause
    exit /b 1
)
title SK-RAFT Client
cmd /k ""%CD%\.venv\Scripts\activate.bat" & echo. & echo The SK-RAFT Python client is ready. For example: python get_started\list_devices.py & echo."
